import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query, Response, status
from sqlalchemy import select

from app.api.deps import DB, Admin, CurrentUser, Owner, Viewer
from app.core.pagination import clamp_limit
from app.models import Role
from app.schemas.common import Envelope, ok
from app.schemas.projects import (
    MemberAddIn,
    MemberOut,
    MemberUpdateIn,
    ProjectCreateIn,
    ProjectOut,
    ProjectUpdateIn,
    RoleOut,
)
from app.services import projects as svc

router = APIRouter(tags=["projects"])


def _out(db, project, role: str) -> dict:  # type: ignore[no-untyped-def]
    return svc.to_out(project, role, svc.stats(db, [project.id])[project.id])


def _etag(response: Response, version: int) -> None:
    response.headers["ETag"] = f'"{version}"'


@router.get("/roles", response_model=Envelope[list[RoleOut]])
def list_roles(_: CurrentUser, db: DB) -> dict:
    return ok(list(db.execute(select(Role).order_by(Role.rank.desc())).scalars()))


@router.get("/projects", response_model=Envelope[list[ProjectOut]])
def list_projects(
    user: CurrentUser,
    db: DB,
    status_filter: Annotated[Literal["active", "archived"] | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    cursor: str | None = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> dict:
    items, page = svc.list_projects(db, user, status_filter, q, cursor, clamp_limit(limit))
    return ok(items, page)


@router.post("/projects", response_model=Envelope[ProjectOut], status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreateIn, user: CurrentUser, db: DB, response: Response) -> dict:
    project = svc.create_project(db, user, body)
    db.commit()
    _etag(response, project.version)
    return ok(_out(db, project, "owner"))


@router.get("/projects/{project_id}", response_model=Envelope[ProjectOut])
def get_project(access: Viewer, db: DB, response: Response) -> dict:
    _etag(response, access.project.version)
    return ok(_out(db, access.project, access.role))


@router.patch("/projects/{project_id}", response_model=Envelope[ProjectOut])
def update_project(
    body: ProjectUpdateIn,
    access: Admin,
    user: CurrentUser,
    db: DB,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> dict:
    project = svc.update_project(db, access, user, body, if_match)
    db.commit()
    _etag(response, project.version)
    return ok(_out(db, project, access.role))


@router.post("/projects/{project_id}/archive", response_model=Envelope[ProjectOut])
def archive_project(access: Admin, user: CurrentUser, db: DB, response: Response) -> dict:
    project = svc.set_archived(db, access, user, True)
    db.commit()
    _etag(response, project.version)
    return ok(_out(db, project, access.role))


@router.post("/projects/{project_id}/restore", response_model=Envelope[ProjectOut])
def restore_project(access: Admin, user: CurrentUser, db: DB, response: Response) -> dict:
    project = svc.set_archived(db, access, user, False)
    db.commit()
    _etag(response, project.version)
    return ok(_out(db, project, access.role))


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(access: Owner, user: CurrentUser, db: DB) -> Response:
    svc.soft_delete(db, access, user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/projects/{project_id}/members", response_model=Envelope[list[MemberOut]])
def list_members(access: Viewer, db: DB) -> dict:
    return ok(svc.list_members(db, access.project_id))


@router.post("/projects/{project_id}/members", response_model=Envelope[MemberOut], status_code=status.HTTP_201_CREATED)
def add_member(body: MemberAddIn, access: Admin, user: CurrentUser, db: DB) -> dict:
    member = svc.add_member(db, access, user, body.email, body.role)
    db.commit()
    return ok(member)


@router.patch("/projects/{project_id}/members/{user_id}", response_model=Envelope[MemberOut])
def change_member_role(user_id: uuid.UUID, body: MemberUpdateIn, access: Admin, user: CurrentUser, db: DB) -> dict:
    member = svc.change_member_role(db, access, user, user_id, body.role)
    db.commit()
    return ok(member)


@router.delete("/projects/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(user_id: uuid.UUID, access: Viewer, user: CurrentUser, db: DB) -> Response:
    """Admins remove others; any member can remove themselves (leave)."""
    svc.remove_member(db, access, user, user_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
