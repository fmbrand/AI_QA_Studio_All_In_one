"""Check model citations against the real source text.

A citation is kept only if it names a source that was actually sent and its quote really appears in
that source (ignoring whitespace and case). A requirement with no surviving citation is discarded:
the platform never stores an AI claim it cannot point back to.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from ai_engine.prompts.requirement_extraction import ExtractedRequirement

MIN_QUOTE_CHARS = 8


@dataclass(frozen=True)
class SourceChunk:
    source_id: str
    chunk_id: str
    document_id: str
    document_version_id: str
    document_title: str
    page: int | None
    sheet: str | None
    char_start: int
    text: str


@dataclass
class GroundedRequirement:
    item: ExtractedRequirement
    source_refs: list[dict[str, Any]]


@dataclass
class GroundingReport:
    kept: list[GroundedRequirement] = field(default_factory=list)
    discarded_uncited: int = 0
    dropped_citations: int = 0


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _locate(quote: str, text: str) -> tuple[int, int] | None:
    """Character span of quote inside text, tolerant to whitespace and case differences."""
    exact = text.find(quote)
    if exact != -1:
        return exact, exact + len(quote)
    words = re.findall(r"\S+", quote)
    if not words:
        return None
    pattern = r"\s+".join(re.escape(w) for w in words)
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return (match.start(), match.end()) if match else None


def ground(requirements: list[ExtractedRequirement], chunks: dict[str, SourceChunk]) -> GroundingReport:
    report = GroundingReport()
    for item in requirements:
        refs: list[dict[str, Any]] = []
        seen: set[tuple[str, int]] = set()
        for citation in item.citations:
            chunk = chunks.get(citation.source_id.strip())
            quote = citation.quote.strip()
            span = _locate(quote, chunk.text) if chunk and len(_normalise(quote)) >= MIN_QUOTE_CHARS else None
            if chunk is None or span is None:
                report.dropped_citations += 1
                continue
            key = (chunk.chunk_id, span[0])
            if key in seen:
                continue
            seen.add(key)
            refs.append({
                "document_id": chunk.document_id,
                "document_version_id": chunk.document_version_id,
                "document_title": chunk.document_title,
                "chunk_id": chunk.chunk_id,
                "page": chunk.page,
                "sheet": chunk.sheet,
                "char_start": chunk.char_start + span[0],
                "char_end": chunk.char_start + span[1],
                "quote": chunk.text[span[0]:span[1]],
            })  # fmt: skip
        if refs:
            report.kept.append(GroundedRequirement(item=item, source_refs=refs))
        else:
            report.discarded_uncited += 1
    return report
