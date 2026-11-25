"""Claude via the official Anthropic Python SDK.

- Structured output through `output_config.format` (JSON schema), so the reply is guaranteed JSON.
- Adaptive thinking is always on for Claude Opus 5.5; depth is controlled with `output_config.effort`
  (set explicitly, because this model's default is `medium`).
- Server-side refusal fallback (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`) so a
  safety-classifier decline is retried on a suitable model inside the same call.
"""

import json
from typing import Any

import anthropic

from .base import LLMError, LLMRequest, LLMResult

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        effort: str = "high",
        timeout: float = 300.0,
        use_fallbacks: bool = True,
    ) -> None:
        self.model = model
        self.effort = effort
        self.use_fallbacks = use_fallbacks
        # With api_key=None the SDK resolves ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN or an `ant` profile.
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)

    def complete_json(self, request: LLMRequest) -> LLMResult:
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_output_tokens,
            # The system prompt is stable per prompt version, so cache it across calls.
            "system": [{"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": request.user}],
            "output_config": {
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": request.schema},
            },
        }
        try:
            if self.use_fallbacks:
                response = self._client.beta.messages.create(**params, betas=[FALLBACK_BETA], fallbacks="default")
            else:
                response = self._client.messages.create(**params)
        except anthropic.AuthenticationError as exc:
            raise LLMError("Anthropic rejected the API key. Check ANTHROPIC_API_KEY.", retryable=False) from exc
        except anthropic.PermissionDeniedError as exc:
            raise LLMError("The Anthropic API key lacks permission for this model.", retryable=False) from exc
        except anthropic.NotFoundError as exc:
            raise LLMError(f"Model {self.model} was not found. Check ANTHROPIC_MODEL.", retryable=False) from exc
        except anthropic.BadRequestError as exc:
            raise LLMError(f"Anthropic rejected the request: {exc.message}", retryable=False) from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("Anthropic rate limit reached; the job will retry.", retryable=True) from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Anthropic API error {exc.status_code}; the job will retry.",
                           retryable=exc.status_code >= 500) from exc  # fmt: skip
        except anthropic.APIConnectionError as exc:
            raise LLMError("Could not reach the Anthropic API; the job will retry.", retryable=True) from exc

        request_id = getattr(response, "_request_id", None)
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise LLMError(
                f"The model declined this content (category: {category or 'unspecified'}).",
                retryable=False, provider_request_id=request_id,
            )  # fmt: skip
        if response.stop_reason == "max_tokens":
            raise LLMError(
                "The model's answer was cut off at the output limit. Extract from fewer documents at a time.",
                retryable=False, provider_request_id=request_id,
            )  # fmt: skip
        text = "".join(block.text for block in response.content if block.type == "text")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("The model returned invalid JSON.", retryable=False, provider_request_id=request_id) from exc
        usage = response.usage
        return LLMResult(
            data=data,
            model=response.model,
            input_tokens=(usage.input_tokens or 0)
            + (getattr(usage, "cache_read_input_tokens", 0) or 0)
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0),
            output_tokens=usage.output_tokens or 0,
            stop_reason=response.stop_reason,
            provider_request_id=request_id,
        )
