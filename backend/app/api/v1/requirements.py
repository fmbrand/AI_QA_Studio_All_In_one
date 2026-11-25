import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status

from app.api.deps import DB, CurrentUser, Engineer, Viewer
from app.core.pagination import clamp_limit
from app.schemas.common import Envelope, ok
from app.schemas.documents import JobOut
from app.schemas.requirements import (
    AIStatusOut,
    BulkStatusIn,
    ContextHit,
    ContextSearchIn,
    ExtractIn,
    Priority,
    RejectIn,
    RequirementCreateIn,
    RequirementDetailOut,
    RequirementDiffOut,
    RequirementOut,
    RequirementStatus,
    RequirementType,
    RequirementUpdateIn,
)
from app.services import ai_runtime, context
from app.services import requirements as svc

router = APIRouter(tags=["requirements", "context"])


@router.get("/ai/status", response_model=Envelope[AIStatusOut])
def ai_status(_: CurrentUser) -> dict:
    """Which language model, embedding model and OCR are active. Never returns keys."""
    return ok(ai_runtime.status())


@router.post("/projects/{project_id}/context/search", response_model=Envelope[list[ContextHit]])
def search_context(body: ContextSearchIn, access: Viewer, db: DB) -> dict:
    hits = context.search(db, access.project_id, body.query, module_ids=body.module_ids,
                          expand_connected=body.expand_connected, k=body.k)  # fmt: skip
    return ok(hits)


@router.get("/projects/{project_id}/requirements", response_model=Envelope[list[RequirementOut]])
def list_requirements(
    access: Viewer, db: DB,
    status_filter: Annotated[RequirementStatus | None, Query(alias="status")] = None,
    type_filter: Annotated[RequirementType | None, Query(alias="type")] = None,
    priority: Priority | None = None,
    module_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    cursor: str | None = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> dict:  # fmt: skip
    items, page = svc.list_requirements(db, access.project_id, status=status_filter, type_=type_filter,
                                        priority=priority, module_id=module_id, q=q, cursor=cursor,
                                        limit=clamp_limit(limit))  # fmt: skip
    return ok(items, page)


@router.post("/projects/{project_id}/requirements", response_model=Envelope[RequirementDetailOut],
             status_code=status.HTTP_201_CREATED)  # fmt: skip
def create_requirement(body: RequirementCreateIn, access: Engineer, user: CurrentUser, db: DB,
                       response: Response) -> dict:  # fmt: skip
    req = svc.create_manual(db, access, user, body)
    db.commit()
    response.headers["ETag"] = f'"{req.current_version_no}"'
    return ok(svc.detail(db, access.project_id, req.id))


@router.post("/projects/{project_id}/requirements/extract", response_model=Envelope[JobOut],
             status_code=status.HTTP_202_ACCEPTED)  # fmt: skip
def extract_requirements(body: ExtractIn, access: Engineer, user: CurrentUser, db: DB,
                         idempotency_key: Annotated[str | None, Header(max_length=100)] = None) -> dict:  # fmt: skip
    """Queue AI extraction from indexed documents. Results arrive as draft requirements for review."""
    job = svc.start_extraction(db, access, user, body.document_ids, body.instructions, idempotency_key)
    db.commit()
    return ok(job)


@router.post("/projects/{project_id}/requirements/bulk-status", response_model=Envelope[dict])
def bulk_status(body: BulkStatusIn, access: Engineer, user: CurrentUser, db: DB) -> dict:
    result = svc.bulk_status(db, access, user, body.requirement_ids, body.status, body.reason)
    db.commit()
    return ok(result)


@router.get("/projects/{project_id}/requirements/{requirement_id}", response_model=Envelope[RequirementDetailOut])
def get_requirement(requirement_id: uuid.UUID, access: Viewer, db: DB, response: Response) -> dict:
    out = svc.detail(db, access.project_id, requirement_id)
    response.headers["ETag"] = f'"{out["current_version_no"]}"'
    return ok(out)


@router.patch("/projects/{project_id}/requirements/{requirement_id}", response_model=Envelope[RequirementDetailOut])
def update_requirement(requirement_id: uuid.UUID, body: RequirementUpdateIn, access: Engineer, user: CurrentUser,
                       db: DB, response: Response,
                       if_match: Annotated[str | None, Header()] = None) -> dict:  # fmt: skip
    req = svc.update(db, access, user, requirement_id, body, if_match)
    db.commit()
    response.headers["ETag"] = f'"{req.current_version_no}"'
    return ok(svc.detail(db, access.project_id, req.id))


@router.post("/projects/{project_id}/requirements/{requirement_id}/approve",
             response_model=Envelope[RequirementDetailOut])  # fmt: skip
def approve_requirement(requirement_id: uuid.UUID, access: Engineer, user: CurrentUser, db: DB) -> dict:
    svc.set_status(db, access, user, requirement_id, "approved")
    db.commit()
    return ok(svc.detail(db, access.project_id, requirement_id))


@router.post("/projects/{project_id}/requirements/{requirement_id}/reject",
             response_model=Envelope[RequirementDetailOut])  # fmt: skip
def reject_requirement(requirement_id: uuid.UUID, body: RejectIn, access: Engineer, user: CurrentUser,
                       db: DB) -> dict:  # fmt: skip
    svc.set_status(db, access, user, requirement_id, "rejected", body.reason)
    db.commit()
    return ok(svc.detail(db, access.project_id, requirement_id))


@router.delete("/projects/{project_id}/requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_requirement(requirement_id: uuid.UUID, access: Engineer, user: CurrentUser, db: DB) -> Response:
    svc.delete(db, access, user, requirement_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/projects/{project_id}/requirements/{requirement_id}/diff", response_model=Envelope[RequirementDiffOut])
def requirement_diff(requirement_id: uuid.UUID, access: Viewer, db: DB,
                     from_version: Annotated[int, Query(alias="from", ge=1)],
                     to_version: Annotated[int, Query(alias="to", ge=1)]) -> dict:  # fmt: skip
    return ok(svc.diff(db, access.project_id, requirement_id, from_version, to_version))
