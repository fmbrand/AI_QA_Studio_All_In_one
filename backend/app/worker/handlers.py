"""Job handlers: document indexing and AI requirement extraction."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import DocumentVersion, Job
from app.services import context, requirements
from app.worker.runner import JobError, Report, handler


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
def ingest_document(db: Session, job: Job, report: Report) -> dict[str, Any]:
    """Parse the file (with OCR where available), split it into passages, embed and index them."""
    version = _version(db, job)
    version.processing_status = "processing"
    try:
        result = context.index_version(db, version, report)
    except ValueError as exc:  # unreadable or malformed file
        raise JobError(f"The file could not be read: {exc}") from exc
    version.processing_error = None
    # "processed" = text is searchable; "stored" = kept, but nothing could be read from it.
    version.processing_status = "processed" if result.chunk_count else "stored"
    return {"extracted": result.chunk_count > 0, "char_count": result.char_count, "chunks": result.chunk_count,
            "warnings": result.warnings}  # fmt: skip


def _mark_failed(db: Session, job: Job) -> None:
    try:
        version = db.get(DocumentVersion, uuid.UUID(job.input["document_version_id"]))
    except (KeyError, ValueError):
        return
    if version is not None:
        version.processing_status = "failed"
        version.processing_error = job.error


ingest_document.on_failure = _mark_failed  # type: ignore[attr-defined]


@handler(requirements.EXTRACTION_JOB)
def extract_requirements(db: Session, job: Job, report: Report) -> dict[str, Any]:
    return requirements.run_extraction(db, job, report)
