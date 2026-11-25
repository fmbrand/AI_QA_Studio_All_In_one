"""Job handlers. Phase 1 has one: document ingest (plain-text extraction).

PDF, DOCX, XLSX and image parsing (with OCR) arrive with the Phase 2 context engine. Until then those
files are stored and marked 'stored' rather than pretending to have been parsed.
"""

import csv
import io
import json
import uuid

from sqlalchemy.orm import Session

from app.integrations.storage import get_storage
from app.models import DocumentExtraction, DocumentVersion, Job
from app.services.filetypes import TYPES
from app.worker.runner import JobError, handler

MAX_EXTRACT_CHARS = 2_000_000


def _version(db: Session, job: Job) -> DocumentVersion:
    try:
        version_id = uuid.UUID(job.input["document_version_id"])
    except (KeyError, ValueError) as exc:
        raise JobError("Job input is missing the document version") from exc
    version = db.get(DocumentVersion, version_id)
    if version is None:
        raise JobError("The document version no longer exists")
    return version


@handler("document_ingest")
def ingest_document(db: Session, job: Job) -> dict:
    version = _version(db, job)
    version.processing_status = "processing"
    job.stage, job.progress = "Reading file", 20
    db.flush()

    ext = "." + version.storage_key.rsplit(".", 1)[-1].lower()
    family = TYPES[ext].family if ext in TYPES else "binary"
    if family not in {"text", "csv", "json"}:
        version.processing_status = "stored"
        return {"extracted": False, "reason": "Parsing for this file type arrives with the Phase 2 context engine"}

    with get_storage().open(version.storage_key) as fh:
        raw = fh.read()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise JobError("The file is not valid UTF-8 text") from exc

    meta: dict[str, object] = {}
    if family == "csv":
        rows = list(csv.reader(io.StringIO(content)))
        meta = {"rows": max(0, len(rows) - 1), "columns": rows[0] if rows else []}
    elif family == "json":
        meta = {"top_level_type": type(json.loads(content)).__name__}

    truncated = len(content) > MAX_EXTRACT_CHARS
    text = content[:MAX_EXTRACT_CHARS]
    if truncated:
        meta["truncated"] = True
    job.stage, job.progress = "Saving extracted text", 80
    db.add(
        DocumentExtraction(
            document_version_id=version.id,
            project_id=version.project_id,
            extractor=f"{family}_v1",
            text=text,
            char_count=len(text),
            meta=meta,
        )
    )
    version.processing_status = "processed"
    version.processing_error = None
    return {"extracted": True, "char_count": len(text), **({"truncated": True} if truncated else {})}


def _mark_failed(db: Session, job: Job) -> None:
    try:
        version = db.get(DocumentVersion, uuid.UUID(job.input["document_version_id"]))
    except (KeyError, ValueError):
        return
    if version is not None:
        version.processing_status = "failed"
        version.processing_error = job.error


ingest_document.on_failure = _mark_failed  # type: ignore[attr-defined]
