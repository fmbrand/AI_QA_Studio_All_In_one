import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Response, status

from app.api.deps import DB, Admin, CurrentUser, Engineer, Viewer
from app.schemas.common import Envelope, ok
from app.schemas.projects import ModuleConnectionsIn, ModuleCreateIn, ModuleOut, ModuleUpdateIn
from app.services import modules as svc

router = APIRouter(tags=["modules"])


def _connected(db, project_id, module_id) -> list[uuid.UUID]:  # type: ignore[no-untyped-def]
    return next((m["connected_module_ids"] for m in svc.list_modules(db, project_id) if m["id"] == module_id), [])


@router.get("/projects/{project_id}/modules", response_model=Envelope[list[ModuleOut]])
def list_modules(access: Viewer, db: DB) -> dict:
    return ok(svc.list_modules(db, access.project_id))


@router.post("/projects/{project_id}/modules", response_model=Envelope[ModuleOut], status_code=status.HTTP_201_CREATED)
def create_module(body: ModuleCreateIn, access: Engineer, user: CurrentUser, db: DB, response: Response) -> dict:
    module = svc.create_module(db, access, user, body)
    db.commit()
    response.headers["ETag"] = f'"{module.version}"'
    return ok(svc.to_out(module, []))


@router.get("/projects/{project_id}/modules/{module_id}", response_model=Envelope[ModuleOut])
def get_module(module_id: uuid.UUID, access: Viewer, db: DB, response: Response) -> dict:
    module = svc.get_module(db, access.project_id, module_id)
    response.headers["ETag"] = f'"{module.version}"'
    return ok(svc.to_out(module, _connected(db, access.project_id, module.id)))


@router.patch("/projects/{project_id}/modules/{module_id}", response_model=Envelope[ModuleOut])
def update_module(
    module_id: uuid.UUID,
    body: ModuleUpdateIn,
    access: Engineer,
    user: CurrentUser,
    db: DB,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> dict:
    module = svc.update_module(db, access, user, module_id, body, if_match)
    db.commit()
    response.headers["ETag"] = f'"{module.version}"'
    return ok(svc.to_out(module, _connected(db, access.project_id, module.id)))


@router.delete("/projects/{project_id}/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_module(module_id: uuid.UUID, access: Admin, user: CurrentUser, db: DB) -> Response:
    svc.delete_module(db, access, user, module_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/projects/{project_id}/modules/{module_id}/connections", response_model=Envelope[ModuleOut])
def set_connections(
    module_id: uuid.UUID, body: ModuleConnectionsIn, access: Engineer, user: CurrentUser, db: DB
) -> dict:
    targets = svc.set_connections(db, access, user, module_id, body.to_module_ids)
    db.commit()
    return ok(svc.to_out(svc.get_module(db, access.project_id, module_id), targets))
