import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.deps import DB, CurrentUser, Engineer, Viewer
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.pagination import clamp_limit
from app.core.security import sign_file_token, verify_file_token
from app.integrations.storage import get_storage, iter_file
from app.models import DocumentVersion, UploadedDocument
from app.repositories.access import get_project_access
from app.schemas.common import Envelope, ok
from app.schemas.documents import (
    DocumentDetailOut,
    DocumentKind,
    DocumentOut,
    DocumentUpdateIn,
    DownloadUrlOut,
    ExtractionOut,
    JobOut,
    UploadOut,
)
from app.services import documents as svc

router = APIRouter(tags=["documents"])


@router.post(
    "/projects/{project_id}/documents", response_model=Envelope[UploadOut], status_code=status.HTTP_201_CREATED
)
async def upload_document(
    access: Engineer,
    user: CurrentUser,
    db: DB,
    file: Annotated[UploadFile, File(description="The document to upload")],
    title: Annotated[str | None, Form(max_length=200)] = None,
    kind: Annotated[DocumentKind, Form()] = "other",
    module_id: Annotated[uuid.UUID | None, Form()] = None,
) -> dict:
    staged = await svc.stage_upload(file)
    try:
        document, job = svc.create_document(db, access, user, staged, title=title, kind=kind, module_id=module_id)
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        staged.cleanup()
    return ok({"document": svc.document_detail(db, access.project_id, document.id), "job": job})


@router.get("/projects/{project_id}/documents", response_model=Envelope[list[DocumentOut]])
def list_documents(
    access: Viewer,
    db: DB,
    kind: DocumentKind | None = None,
    module_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    cursor: str | None = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> dict:
    items, page = svc.list_documents(
        db, access.project_id, kind=kind, module_id=module_id, q=q, cursor=cursor, limit=clamp_limit(limit)
    )
    return ok(items, page)


@router.get("/projects/{project_id}/documents/{document_id}", response_model=Envelope[DocumentDetailOut])
def get_document(document_id: uuid.UUID, access: Viewer, db: DB) -> dict:
    return ok(svc.document_detail(db, access.project_id, document_id))


@router.patch("/projects/{project_id}/documents/{document_id}", response_model=Envelope[DocumentDetailOut])
def update_document(
    document_id: uuid.UUID, body: DocumentUpdateIn, access: Engineer, user: CurrentUser, db: DB
) -> dict:
    svc.update_document(db, access, user, document_id, body.title, body.kind, body.module_id, body.clear_module)
    db.commit()
    return ok(svc.document_detail(db, access.project_id, document_id))


@router.delete("/projects/{project_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: uuid.UUID, access: Engineer, user: CurrentUser, db: DB) -> Response:
    svc.delete_document(db, access, user, document_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/projects/{project_id}/documents/{document_id}/versions",
    response_model=Envelope[UploadOut],
    status_code=status.HTTP_201_CREATED,
)
async def upload_version(
    document_id: uuid.UUID, access: Engineer, user: CurrentUser, db: DB, file: Annotated[UploadFile, File()]
) -> dict:
    staged = await svc.stage_upload(file)
    try:
        document, job = svc.add_version(db, access, user, document_id, staged)
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        staged.cleanup()
    return ok({"document": svc.document_detail(db, access.project_id, document.id), "job": job})


@router.post("/projects/{project_id}/documents/{document_id}/reprocess", response_model=Envelope[JobOut],
             status_code=status.HTTP_202_ACCEPTED)  # fmt: skip
def reprocess_document(document_id: uuid.UUID, access: Engineer, user: CurrentUser, db: DB) -> dict:
    job = svc.reprocess(db, access, user, document_id)
    db.commit()
    return ok(job)


@router.get("/projects/{project_id}/documents/{document_id}/extractions", response_model=Envelope[list[ExtractionOut]])
def list_extractions(document_id: uuid.UUID, access: Viewer, db: DB) -> dict:
    return ok(svc.list_extractions(db, access.project_id, document_id))


@router.get(
    "/projects/{project_id}/documents/{document_id}/versions/{version_id}/download-url",
    response_model=Envelope[DownloadUrlOut],
)
def download_url(
    document_id: uuid.UUID, version_id: uuid.UUID, access: Viewer, user: CurrentUser, db: DB, request: Request
) -> dict:
    version = svc.get_version(db, access.project_id, document_id, version_id)
    token = sign_file_token(version.id, user.id)
    url = str(request.url_for("download_file", token=token))
    return ok({"url": url, "expires_in": get_settings().signed_url_seconds})


@router.get("/files/{token}", name="download_file", include_in_schema=True)
def download_file(token: str, db: DB) -> StreamingResponse:
    """Stream a document version. The signed token is short-lived and bound to one user; membership
    is checked again at download time."""
    parsed = verify_file_token(token)
    if parsed is None:
        raise AppError(404, "not_found", "This download link is invalid or has expired")
    version_id, user_id = parsed
    version = db.get(DocumentVersion, version_id)
    document = db.get(UploadedDocument, version.document_id) if version else None
    if (
        version is None
        or document is None
        or document.deleted_at is not None
        or get_project_access(db, version.project_id, user_id) is None
    ):
        raise AppError(404, "not_found", "This download link is invalid or has expired")
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(version.filename)}",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
        "Content-Length": str(version.size_bytes),
    }
    return StreamingResponse(
        iter_file(get_storage().open(version.storage_key)), media_type=version.content_type, headers=headers
    )
