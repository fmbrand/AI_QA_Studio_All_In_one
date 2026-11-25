"""Golden-set evaluation for requirement extraction, against a real model. Costs real tokens.

    LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=... uv run python scripts/run_evals.py

Runs every case in evals/requirement_extraction through the same parse -> chunk -> prompt -> model ->
grounding path the worker uses (no database needed) and reports, per case and overall:

- recall: share of expected requirements found (keyword match on title + description)
- citation validity: share of returned requirements whose citations survived grounding
- forbidden: phrases that must never appear (the injection case checks this)

Exits with status 1 when a threshold in expected.json is missed or a forbidden phrase appears.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai_engine.documents.chunking import chunk_document  # noqa: E402
from ai_engine.documents.parsers import parse_text  # noqa: E402
from ai_engine.grounding import SourceChunk, ground  # noqa: E402
from ai_engine.llm.base import LLMRequest  # noqa: E402
from ai_engine.llm.registry import build_provider  # noqa: E402
from ai_engine.prompts import requirement_extraction as prompt  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.services.ai_runtime import llm_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent / "evals" / "requirement_extraction"


def run_case(provider, name: str, text: str) -> tuple[list[prompt.ExtractedRequirement], int, int]:  # type: ignore[no-untyped-def]
    settings = get_settings()
    doc = parse_text(text.encode())
    chunks = chunk_document(doc, settings.chunk_size_chars, settings.chunk_overlap_chars)
    chunk_map, blocks = {}, []
    for i, c in enumerate(chunks, start=1):
        sid = f"S{i}"
        chunk_map[sid] = SourceChunk(sid, f"c{i}", "doc", "ver", name, c.page, c.sheet, c.start, c.text)
        blocks.append(prompt.SourceBlock(sid, name, c.page, c.sheet, c.text))
    request = LLMRequest(
        system=prompt.SYSTEM,
        user=prompt.render_user(project={"name": "Service Booking (eval)", "platform": "web"},
                                modules=["Booking", "Payments", "Reviews"], existing_titles=[],
                                instructions=None, sources=blocks),
        schema=prompt.SCHEMA, schema_name="requirement_extraction", max_output_tokens=settings.llm_max_output_tokens,
    )  # fmt: skip
    result = provider.complete_json(request)
    output = prompt.ExtractionOutput.model_validate(result.data)
    report = ground(output.requirements, chunk_map)
    print(f"  model={result.model} tokens in/out={result.input_tokens}/{result.output_tokens}")
    return [g.item for g in report.kept], len(output.requirements), report.discarded_uncited


def main() -> int:
    provider = build_provider(llm_config())
    if provider is None:
        print("Set LLM_PROVIDER (and its key) to run evals.")
        return 2
    spec = json.loads((ROOT / "expected.json").read_text(encoding="utf-8"))
    total_expected = total_found = total_returned = total_valid = 0
    failures: list[str] = []
    for name, case in spec["cases"].items():
        print(f"\n== {name}")
        kept, returned, discarded = run_case(provider, name, (ROOT / "cases" / name).read_text(encoding="utf-8"))
        texts = [f"{r.title} {r.description}".lower() for r in kept]
        found = [e["id"] for e in case["expected"] if any(all(k.lower() in t for k in e["keywords"]) for t in texts)]
        missed = [e["id"] for e in case["expected"] if e["id"] not in found]
        leaks = [f for f in case["forbidden"] if any(f.lower() in t for t in texts)]
        print(f"  returned={returned} grounded={len(kept)} discarded_uncited={discarded}")
        print(f"  recall={len(found)}/{len(case['expected'])} missed={missed or '-'}")
        if leaks:
            failures.append(f"{name}: forbidden content {leaks}")
        total_expected += len(case["expected"])
        total_found += len(found)
        total_returned += returned
        total_valid += len(kept)
    recall = total_found / total_expected if total_expected else 1.0
    validity = total_valid / total_returned if total_returned else 1.0
    t = spec["thresholds"]
    print(f"\nOVERALL recall={recall:.2f} (min {t['recall']})  citation_validity={validity:.2f} "
          f"(min {t['citation_validity']})")  # fmt: skip
    if recall < t["recall"]:
        failures.append(f"recall {recall:.2f} below {t['recall']}")
    if validity < t["citation_validity"]:
        failures.append(f"citation validity {validity:.2f} below {t['citation_validity']}")
    for f in failures:
        print(f"FAIL: {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
