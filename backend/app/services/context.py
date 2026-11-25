"""The context engine's database side: index document versions and search them.

Search is hybrid: pgvector cosine similarity and PostgreSQL full-text ranking, merged with reciprocal
rank fusion. Only current versions of documents that are not deleted are searchable, and every query
is filtered by project first, so one project's knowledge never reaches another.
"""

import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, literal_column, or_, select
from sqlalchemy.orm import Session

from ai_engine.documents.chunking import chunk_document
from ai_engine.documents.parsers import parse_file
from app.core.config import get_settings
from app.integrations.storage import get_storage
from app.models import ContextChunk, DocumentExtraction, DocumentVersion, ModuleConnection, UploadedDocument
from app.services.ai_runtime import get_embedder, get_ocr

RRF_K = 60
CANDIDATES = 40


@dataclass
class IndexResult:
    char_count: int
    chunk_count: int
    warnings: list[str]
    meta: dict[str, Any]


def clear_index(db: Session, version_id: uuid.UUID) -> None:
    db.execute(delete(ContextChunk).where(ContextChunk.document_version_id == version_id))
    db.execute(delete(DocumentExtraction).where(DocumentExtraction.document_version_id == version_id))


def index_version(db: Session, version: DocumentVersion, report: Any = None) -> IndexResult:
    """Parse, chunk and embed one document version. Replaces any earlier index of that version."""
    settings = get_settings()
    extension = "." + version.storage_key.rsplit(".", 1)[-1].lower()
    # ignore_cleanup_errors: on Windows a parser that failed may still hold the temp file open.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        path = Path(tmp) / f"source{extension}"
        with get_storage().open(version.storage_key) as src, path.open("wb") as dst:
            while data := src.read(1024 * 1024):
                dst.write(data)
        if report:
            report("Reading the document", 20)
        try:
            parsed = parse_file(path, extension, get_ocr())
        except Exception as exc:  # corrupt or unreadable file: retrying will not help
            raise ValueError(f"{type(exc).__name__}: {exc}") from exc

    clear_index(db, version.id)
    meta = {**parsed.meta, "warnings": parsed.warnings,
            "ocr_pages": parsed.meta.get("ocr_pages", [])}  # fmt: skip
    db.add(DocumentExtraction(document_version_id=version.id, project_id=version.project_id,
                              extractor=f"{extension.lstrip('.')}_v2", text=parsed.text,
                              char_count=len(parsed.text), meta=meta))  # fmt: skip

    chunks = chunk_document(parsed, settings.chunk_size_chars, settings.chunk_overlap_chars)
    if chunks:
        if report:
            report(f"Indexing {len(chunks)} passages", 60)
        embedder = get_embedder()
        vectors = embedder.embed([c.text for c in chunks])
        for chunk, vector in zip(chunks, vectors, strict=True):
            db.add(ContextChunk(
                project_id=version.project_id, document_id=version.document_id, document_version_id=version.id,
                chunk_index=chunk.index, content=chunk.text, page=chunk.page, sheet=chunk.sheet,
                char_start=chunk.start, char_end=chunk.end, embedding=vector, embedding_model=embedder.model,
            ))  # fmt: skip
    return IndexResult(len(parsed.text), len(chunks), parsed.warnings, meta)


def _scope_module_ids(db: Session, project_id: uuid.UUID, module_ids: list[uuid.UUID], expand: bool) -> list[uuid.UUID]:
    if not module_ids or not expand:
        return module_ids
    connected = db.execute(
        select(ModuleConnection.to_module_id).where(
            ModuleConnection.project_id == project_id, ModuleConnection.from_module_id.in_(module_ids)
        )
    ).scalars()
    return list(dict.fromkeys([*module_ids, *connected]))


def _searchable(project_id: uuid.UUID, module_ids: list[uuid.UUID]):  # type: ignore[no-untyped-def]
    """Base query over chunks of current, non-deleted documents of one project."""
    stmt = (
        select(ContextChunk, UploadedDocument.title, UploadedDocument.module_id, DocumentVersion.version)
        .join(DocumentVersion, DocumentVersion.id == ContextChunk.document_version_id)
        .join(UploadedDocument, UploadedDocument.id == DocumentVersion.document_id)
        .where(
            ContextChunk.project_id == project_id,
            UploadedDocument.project_id == project_id,
            UploadedDocument.deleted_at.is_(None),
            UploadedDocument.current_version_id == DocumentVersion.id,
        )
    )
    if module_ids:
        # Module-scoped search also includes documents not tied to any module (general documentation).
        stmt = stmt.where(or_(UploadedDocument.module_id.in_(module_ids), UploadedDocument.module_id.is_(None)))
    return stmt


def search(
    db: Session,
    project_id: uuid.UUID,
    query: str,
    *,
    module_ids: list[uuid.UUID] | None = None,
    expand_connected: bool = True,
    k: int = 8,
) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return []
    scope = _scope_module_ids(db, project_id, module_ids or [], expand_connected)
    vector = get_embedder().embed([query])[0]

    distance = ContextChunk.embedding.cosine_distance(vector)
    semantic = db.execute(
        _searchable(project_id, scope).add_columns(distance.label("distance")).order_by(distance).limit(CANDIDATES)
    ).all()

    ts_query = func.websearch_to_tsquery("english", query)
    rank = func.ts_rank_cd(ContextChunk.content_tsv, ts_query)
    lexical = db.execute(
        _searchable(project_id, scope)
        .add_columns(rank.label("rank"))
        .where(ContextChunk.content_tsv.op("@@")(ts_query))
        .order_by(literal_column("rank").desc())
        .limit(CANDIDATES)
    ).all()

    fused: dict[uuid.UUID, dict[str, Any]] = {}
    for position, row in enumerate(semantic):
        chunk = row[0]
        entry = fused.setdefault(chunk.id, {"row": row, "score": 0.0, "similarity": None, "lexical_rank": None})
        entry["score"] += 1 / (RRF_K + position + 1)
        entry["similarity"] = round(1 - float(row.distance), 4)
    for position, row in enumerate(lexical):
        chunk = row[0]
        entry = fused.setdefault(chunk.id, {"row": row, "score": 0.0, "similarity": None, "lexical_rank": None})
        entry["score"] += 1 / (RRF_K + position + 1)
        entry["lexical_rank"] = position + 1

    ranked = sorted(fused.values(), key=lambda e: e["score"], reverse=True)[:k]
    results = []
    for entry in ranked:
        chunk, title, module_id, version_no = entry["row"][0], entry["row"][1], entry["row"][2], entry["row"][3]
        results.append({
            "chunk_id": chunk.id, "document_id": chunk.document_id, "document_version_id": chunk.document_version_id,
            "document_title": title, "document_version": version_no, "module_id": module_id,
            "page": chunk.page, "sheet": chunk.sheet, "char_start": chunk.char_start, "char_end": chunk.char_end,
            "content": chunk.content, "score": round(entry["score"], 5), "similarity": entry["similarity"],
            "lexical_rank": entry["lexical_rank"],
        })  # fmt: skip
    return results


def chunks_for_documents(db: Session, project_id: uuid.UUID, document_ids: list[uuid.UUID]) -> list[Any]:
    """All chunks of the current versions of the given documents, in reading order."""
    return list(
        db.execute(
            _searchable(project_id, [])
            .where(UploadedDocument.id.in_(document_ids))
            .order_by(UploadedDocument.created_at, ContextChunk.chunk_index)
        ).all()
    )


def chunk_counts(db: Session, version_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not version_ids:
        return {}
    rows = db.execute(
        select(ContextChunk.document_version_id, func.count())
        .where(ContextChunk.document_version_id.in_(version_ids))
        .group_by(ContextChunk.document_version_id)
    ).all()
    return {vid: n for vid, n in rows}
