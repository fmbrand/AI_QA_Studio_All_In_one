"""Document uploads, versions, duplicate detection and downloads."""

import hashlib
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.core.ids import uuid7
from app.core.pagination import page_meta, paginate
from app.integrations.storage import get_storage
from app.models import DocumentExtraction, DocumentVersion, Job, UploadedDocument, User
from app.repositories.access import ProjectAccess
from app.services import activity, jobs
from app.services.filetypes import FileType, detect, safe_filename
from app.services.modules import get_module
from app.services.projects import ensure_active

INGEST_JOB = "document_ingest"


@dataclass
class StagedFile:
    path: Path
    filename: str
    size: int
    sha256: str
    ftype: FileType

    def cleanup(self) -> None:
        self.path.unlink(missing_ok=True)


async def stage_upload(upload: UploadFile) -> StagedFile:
    """Copy the upload to a temp file while hashing it; enforce the size limit and the type check."""
    limit = get_settings().max_upload_bytes
    digest = hashlib.sha256()
    size = 0
    tmp = tempfile.NamedTemporaryFile(delete=False, prefix="upload-", suffix=".bin")  # noqa: SIM115
    path = Path(tmp.name)
    try:
        with tmp:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise AppError(413, "file_too_large", f"Files must be {get_settings().max_upload_mb} MB or smaller")
                digest.update(chunk)
                tmp.write(chunk)
        if size == 0:
            raise AppError(422, "empty_file", "The file is empty")
        filename = safe_filename(upload.filename or "upload")
        ftype = detect(filename, path)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return StagedFile(path=path, filename=filename, size=size, sha256=digest.hexdigest(), ftype=ftype)


def find_duplicate(db: Session, project_id: uuid.UUID, sha256: str) -> tuple[uuid.UUID, int] | None:
    row = db.execute(
        select(DocumentVersion.document_id, DocumentVersion.version)
        .join(UploadedDocument, UploadedDocument.id == DocumentVersion.document_id)
        .where(
            DocumentVersion.project_id == project_id,
            DocumentVersion.sha256 == sha256,
            UploadedDocument.deleted_at.is_(None),
        )
        .limit(1)
    ).first()
    return (row[0], row[1]) if row else None


def _store_version(
    db: Session, user: User, document: UploadedDocument, version: int, staged: StagedFile
) -> tuple[DocumentVersion, Job]:
    version_id = uuid7()
    key = f"projects/{document.project_id}/documents/{document.id}/v{version}-{version_id}{staged.ftype.extension}"
    row = DocumentVersion(
        id=version_id,
        document_id=document.id,
        project_id=document.project_id,
        version=version,
        filename=staged.filename,
        content_type=staged.ftype.content_type,
        size_bytes=staged.size,
        sha256=staged.sha256,
        storage_key=key,
        processing_status="queued",
        uploaded_by=user.id,
    )
    db.add(row)
    db.flush()
    document.current_version_id = row.id
    job = jobs.enqueue(
        db, INGEST_JOB, project_id=document.project_id, created_by=user.id, payload={"document_version_id": str(row.id)}
    )
    with staged.path.open("rb") as fh:
        get_storage().put(key, fh)
    return row, job


def create_document(
    db: Session,
    access: ProjectAccess,
    user: User,
    staged: StagedFile,
    *,
    title: str | None,
    kind: str,
    module_id: uuid.UUID | None,
) -> tuple[UploadedDocument, Job]:
    ensure_active(access)
    dup = find_duplicate(db, access.project_id, staged.sha256)
    if dup:
        raise AppError(
            409,
            "duplicate_document",
            "This exact file is already in the project",
            extra={"existing_document_id": str(dup[0]), "existing_version": dup[1]},
        )
    if module_id:
        get_module(db, access.project_id, module_id)
    document = UploadedDocument(
        project_id=access.project_id,
        title=(title or "").strip()[:200] or Path(staged.filename).stem[:200],
        kind=kind,
        module_id=module_id,
        created_by=user.id,
    )
    db.add(document)
    db.flush()
    version, job = _store_version(db, user, document, 1, staged)
    activity.record(
        db,
        project_id=access.project_id,
        actor_id=user.id,
        action="document.uploaded",
        entity_type="document",
        entity_id=document.id,
        summary=f"Uploaded {staged.filename} as “{document.title}”",
        after={"filename": staged.filename, "size_bytes": staged.size, "kind": kind},
    )
    return document, job


def get_document(db: Session, project_id: uuid.UUID, document_id: uuid.UUID) -> UploadedDocument:
    doc = db.execute(
        select(UploadedDocument).where(
            UploadedDocument.id == document_id,
            UploadedDocument.project_id == project_id,
            UploadedDocument.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if doc is None:
        raise not_found("Document")
    return doc


def add_version(
    db: Session, access: ProjectAccess, user: User, document_id: uuid.UUID, staged: StagedFile
) -> tuple[UploadedDocument, Job]:
    ensure_active(access)
    document = get_document(db, access.project_id, document_id)
    dup = find_duplicate(db, access.project_id, staged.sha256)
    if dup:
        same = dup[0] == document.id
        raise AppError(
            409,
            "duplicate_document",
            "This file is identical to an existing version of this document"
            if same
            else "This exact file is already in the project as another document",
            extra={"existing_document_id": str(dup[0]), "existing_version": dup[1]},
        )
    latest = (
        db.execute(
            select(func.max(DocumentVersion.version)).where(DocumentVersion.document_id == document.id)
        ).scalar_one()
        or 0
    )
    version, job = _store_version(db, user, document, latest + 1, staged)
    activity.record(
        db,
        project_id=access.project_id,
        actor_id=user.id,
        action="document.version_added",
        entity_type="document",
        entity_id=document.id,
        summary=f"Uploaded version {version.version} of “{document.title}”",
        after={"version": version.version, "filename": staged.filename},
    )
    return document, job


def _versions(db: Session, document_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[DocumentVersion]]:
    out: dict[uuid.UUID, list[DocumentVersion]] = {d: [] for d in document_ids}
    if document_ids:
        for v in db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id.in_(document_ids))
            .order_by(DocumentVersion.version.desc())
        ).scalars():
            out[v.document_id].append(v)
    return out


def to_out(doc: UploadedDocument, versions: list[DocumentVersion], detail: bool = False) -> dict[str, Any]:
    current = next((v for v in versions if v.id == doc.current_version_id), versions[0] if versions else None)
    out: dict[str, Any] = {
        "id": doc.id,
        "project_id": doc.project_id,
        "title": doc.title,
        "kind": doc.kind,
        "module_id": doc.module_id,
        "created_by": doc.created_by,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "current_version": current,
        "version_count": len(versions),
    }
    if detail:
        out["versions"] = versions
    return out


def list_documents(
    db: Session,
    project_id: uuid.UUID,
    *,
    kind: str | None,
    module_id: uuid.UUID | None,
    q: str | None,
    cursor: str | None,
    limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    stmt = select(UploadedDocument).where(
        UploadedDocument.project_id == project_id, UploadedDocument.deleted_at.is_(None)
    )
    if kind:
        stmt = stmt.where(UploadedDocument.kind == kind)
    if module_id:
        stmt = stmt.where(UploadedDocument.module_id == module_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                UploadedDocument.title.ilike(like),
                UploadedDocument.id.in_(
                    select(DocumentVersion.document_id).where(DocumentVersion.filename.ilike(like))
                ),
            )
        )
    docs = list(db.execute(paginate(stmt, UploadedDocument.created_at, UploadedDocument.id, cursor, limit)).scalars())
    docs, page = page_meta(docs, limit, cursor)
    versions = _versions(db, [d.id for d in docs])
    return [to_out(d, versions[d.id]) for d in docs], page


def document_detail(db: Session, project_id: uuid.UUID, document_id: uuid.UUID) -> dict[str, Any]:
    from app.services.context import chunk_counts

    doc = get_document(db, project_id, document_id)
    out = to_out(doc, _versions(db, [doc.id])[doc.id], detail=True)
    index = None
    if doc.current_version_id:
        extraction = (
            db.execute(
                select(DocumentExtraction).where(DocumentExtraction.document_version_id == doc.current_version_id)
            )
            .scalars()
            .first()
        )
        if extraction is not None:
            index = {
                "chunk_count": chunk_counts(db, [doc.current_version_id]).get(doc.current_version_id, 0),
                "char_count": extraction.char_count,
                "warnings": extraction.meta.get("warnings", []),
                "ocr_pages": extraction.meta.get("ocr_pages", []),
                "pages": extraction.meta.get("pages"),
            }
    out["index"] = index
    return out


def reprocess(db: Session, access: ProjectAccess, user: User, document_id: uuid.UUID) -> Job:
    """Re-run parsing and indexing for the current version (after enabling OCR, or for Phase 1 uploads)."""
    from app.services.context import clear_index

    ensure_active(access)
    doc = get_document(db, access.project_id, document_id)
    version = db.get(DocumentVersion, doc.current_version_id) if doc.current_version_id else None
    if version is None:
        raise not_found("Document version")
    if version.processing_status in ("queued", "processing"):
        raise AppError(409, "already_processing", "This document is already being processed")
    clear_index(db, version.id)
    version.processing_status, version.processing_error = "queued", None
    job = jobs.enqueue(db, INGEST_JOB, project_id=doc.project_id, created_by=user.id,
                       payload={"document_version_id": str(version.id)})  # fmt: skip
    activity.record(
        db,
        project_id=access.project_id,
        actor_id=user.id,
        action="document.reprocessed",
        entity_type="document",
        entity_id=doc.id,
        summary=f"Reprocessed “{doc.title}”",
    )
    return job


def update_document(
    db: Session,
    access: ProjectAccess,
    user: User,
    document_id: uuid.UUID,
    title: str | None,
    kind: str | None,
    module_id: uuid.UUID | None,
    clear_module: bool,
) -> UploadedDocument:
    ensure_active(access)
    doc = get_document(db, access.project_id, document_id)
    before = {"title": doc.title, "kind": doc.kind, "module_id": doc.module_id}
    if title is not None:
        if not title.strip():
            raise AppError(422, "validation_error", "Title must not be blank")
        doc.title = title.strip()
    if kind is not None:
        doc.kind = kind
    if clear_module:
        doc.module_id = None
    elif module_id is not None:
        get_module(db, access.project_id, module_id)
        doc.module_id = module_id
    b, a = activity.diff(before, {"title": doc.title, "kind": doc.kind, "module_id": doc.module_id})
    if a:
        activity.record(
            db,
            project_id=access.project_id,
            actor_id=user.id,
            action="document.updated",
            entity_type="document",
            entity_id=doc.id,
            summary=f"Updated “{doc.title}”",
            before=b,
            after=a,
        )
    return doc


def delete_document(db: Session, access: ProjectAccess, user: User, document_id: uuid.UUID) -> None:
    ensure_active(access)
    doc = get_document(db, access.project_id, document_id)
    doc.deleted_at = datetime.now(UTC)
    activity.record(
        db,
        project_id=access.project_id,
        actor_id=user.id,
        action="document.deleted",
        entity_type="document",
        entity_id=doc.id,
        summary=f"Deleted “{doc.title}”",
    )


def get_version(db: Session, project_id: uuid.UUID, document_id: uuid.UUID, version_id: uuid.UUID) -> DocumentVersion:
    get_document(db, project_id, document_id)
    version = db.execute(
        select(DocumentVersion).where(DocumentVersion.id == version_id, DocumentVersion.document_id == document_id)
    ).scalar_one_or_none()
    if version is None:
        raise not_found("Document version")
    return version


def list_extractions(db: Session, project_id: uuid.UUID, document_id: uuid.UUID) -> list[DocumentExtraction]:
    get_document(db, project_id, document_id)
    return list(
        db.execute(
            select(DocumentExtraction)
            .join(DocumentVersion, DocumentVersion.id == DocumentExtraction.document_version_id)
            .where(DocumentVersion.document_id == document_id, DocumentExtraction.project_id == project_id)
            .order_by(DocumentVersion.version.desc())
        ).scalars()
    )
