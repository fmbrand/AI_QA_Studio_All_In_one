"""Wiring between app settings and the ai_engine: which LLM, embedder and OCR are active, plus the one
place where model calls happen (logged to ai_generations, with one repair attempt on invalid output)."""

import time
import uuid
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ai_engine.documents.ocr import OCR
from ai_engine.embeddings import Embedder, build_embedder
from ai_engine.llm.base import LLMError, LLMProvider, LLMRequest
from ai_engine.llm.registry import LLMConfig, build_provider, describe
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import AIGeneration, AIPromptVersion

T = TypeVar("T", bound=BaseModel)

_llm_override: LLMProvider | None = None
_llm_override_set = False
_embedder_override: Embedder | None = None


def set_llm_provider(provider: LLMProvider | None) -> None:
    """Test hook: force a provider (or None) regardless of settings."""
    global _llm_override, _llm_override_set
    _llm_override, _llm_override_set = provider, True


def reset_overrides() -> None:
    global _llm_override, _llm_override_set, _embedder_override
    _llm_override, _llm_override_set, _embedder_override = None, False, None


def set_embedder(embedder: Embedder | None) -> None:
    global _embedder_override
    _embedder_override = embedder


def llm_config() -> LLMConfig:
    s = get_settings()
    return LLMConfig(
        provider=s.llm_provider,
        anthropic_model=s.anthropic_model,
        anthropic_api_key=s.anthropic_api_key.get_secret_value() if s.anthropic_api_key else None,
        anthropic_effort=s.anthropic_effort,
        openai_model=s.openai_model,
        openai_api_key=s.openai_api_key.get_secret_value() if s.openai_api_key else None,
        ollama_base_url=s.ollama_base_url,
        ollama_model=s.ollama_model,
        timeout=s.llm_timeout_seconds,
    )


def llm_configured() -> bool:
    return _llm_override is not None if _llm_override_set else get_settings().llm_provider != "none"


def get_llm() -> LLMProvider:
    if _llm_override_set:
        if _llm_override is None:
            raise not_configured()
        return _llm_override
    provider = build_provider(llm_config())
    if provider is None:
        raise not_configured()
    return provider


def not_configured() -> AppError:
    return AppError(
        503, "ai_not_configured",
        "No AI model is configured. Set LLM_PROVIDER (anthropic, openai or ollama) and its key in the "
        "backend environment, then restart the API and worker.",
    )  # fmt: skip


def get_embedder() -> Embedder:
    if _embedder_override is not None:
        return _embedder_override
    s = get_settings()
    return build_embedder(s.embedding_provider, s.embedding_model,
                          str(s.embedding_cache_dir) if s.embedding_cache_dir else None)  # fmt: skip


def get_ocr() -> OCR:
    s = get_settings()
    return OCR(s.tesseract_cmd, s.ocr_languages)


def status() -> dict[str, Any]:
    s = get_settings()
    provider, model = describe(llm_config())
    if _llm_override_set:
        provider, model = (_llm_override.name, _llm_override.model) if _llm_override else ("none", "")
    ocr = get_ocr()
    return {
        "llm": {"configured": llm_configured(), "provider": provider, "model": model},
        "embeddings": {"provider": s.embedding_provider, "model": s.embedding_model, "dimensions": 384},
        "ocr": {"available": ocr.available, "languages": s.ocr_languages},
    }


def prompt_version_id(db: Session, task: str, version: int, template_hash: str) -> uuid.UUID:
    db.execute(
        insert(AIPromptVersion)
        .values(id=uuid.uuid4(), task=task, version=version, template_hash=template_hash)
        .on_conflict_do_nothing(constraint="uq_ai_prompt_versions_task")
    )
    return db.execute(
        select(AIPromptVersion.id).where(AIPromptVersion.task == task, AIPromptVersion.version == version,
                                         AIPromptVersion.template_hash == template_hash)
    ).scalar_one()  # fmt: skip


def run_structured(
    db: Session,
    *,
    output_model: type[T],
    request: LLMRequest,
    task: str,
    prompt_version: uuid.UUID,
    project_id: uuid.UUID | None,
    job_id: uuid.UUID | None,
    retrieved_chunk_ids: list[str],
) -> tuple[T, uuid.UUID]:
    """Call the model, validate the reply against output_model, log every attempt.

    One repair attempt is made when the reply does not validate. Provider errors are re-raised as
    LLMError so the job runner can decide whether to retry."""
    provider = get_llm()
    attempt_request = request
    for attempt in (1, 2):
        started = time.monotonic()
        generation = AIGeneration(
            project_id=project_id, job_id=job_id, task=task, prompt_version_id=prompt_version,
            provider=provider.name, model=provider.model, status="failed", attempt=attempt,
            retrieved_chunk_ids=retrieved_chunk_ids,
        )  # fmt: skip
        try:
            result = provider.complete_json(attempt_request)
        except LLMError as exc:
            generation.latency_ms = int((time.monotonic() - started) * 1000)
            generation.error = str(exc)
            generation.provider_request_id = exc.provider_request_id
            db.add(generation)
            db.commit()
            raise
        generation.latency_ms = int((time.monotonic() - started) * 1000)
        generation.model = result.model
        generation.input_tokens, generation.output_tokens = result.input_tokens, result.output_tokens
        generation.provider_request_id = result.provider_request_id
        try:
            parsed = output_model.model_validate(result.data)
        except ValidationError as exc:
            generation.status = "invalid_output"
            generation.error = str(exc)[:4000]
            db.add(generation)
            db.commit()
            if attempt == 2:
                raise LLMError("The model's answer did not match the expected format twice.", retryable=False) from exc
            attempt_request = LLMRequest(
                system=request.system,
                user=request.user + "\n\nYour previous answer did not match the required JSON schema:\n"
                + str(exc)[:2000] + "\nReturn a corrected answer.",
                schema=request.schema, schema_name=request.schema_name,
                max_output_tokens=request.max_output_tokens,
            )  # fmt: skip
            continue
        generation.status = "succeeded"
        db.add(generation)
        db.flush()
        return parsed, generation.id
    raise AssertionError("unreachable")
