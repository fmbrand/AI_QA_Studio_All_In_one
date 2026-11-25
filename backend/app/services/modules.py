"""Project modules and the module dependency graph."""

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.models import Module, ModuleConnection, User
from app.repositories.access import ProjectAccess
from app.schemas.projects import ModuleCreateIn, ModuleUpdateIn
from app.services import activity
from app.services.projects import ensure_active, require_version


def _connections(db: Session, project_id: uuid.UUID) -> dict[uuid.UUID, list[uuid.UUID]]:
    out: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for src, dst in db.execute(
        select(ModuleConnection.from_module_id, ModuleConnection.to_module_id).where(
            ModuleConnection.project_id == project_id
        )
    ).all():
        out[src].append(dst)
    return out


def to_out(module: Module, connected: list[uuid.UUID]) -> dict[str, Any]:
    return {
        "id": module.id,
        "project_id": module.project_id,
        "name": module.name,
        "description": module.description,
        "version": module.version,
        "created_at": module.created_at,
        "updated_at": module.updated_at,
        "connected_module_ids": connected,
    }


def list_modules(db: Session, project_id: uuid.UUID) -> list[dict[str, Any]]:
    modules = (
        db.execute(select(Module).where(Module.project_id == project_id).order_by(func.lower(Module.name)))
        .scalars()
        .all()
    )
    conns = _connections(db, project_id)
    return [to_out(m, conns.get(m.id, [])) for m in modules]


def get_module(db: Session, project_id: uuid.UUID, module_id: uuid.UUID) -> Module:
    module = db.execute(
        select(Module).where(Module.id == module_id, Module.project_id == project_id)
    ).scalar_one_or_none()
    if module is None:
        raise not_found("Module")
    return module


def _name_taken(db: Session, project_id: uuid.UUID, name: str, exclude: uuid.UUID | None = None) -> bool:
    stmt = select(Module.id).where(Module.project_id == project_id, func.lower(Module.name) == name.lower())
    if exclude:
        stmt = stmt.where(Module.id != exclude)
    return db.execute(stmt).first() is not None


def create_module(db: Session, access: ProjectAccess, user: User, data: ModuleCreateIn) -> Module:
    ensure_active(access)
    if _name_taken(db, access.project_id, data.name):
        raise AppError(409, "module_exists", f"A module named “{data.name}” already exists")
    module = Module(project_id=access.project_id, name=data.name, description=data.description, created_by=user.id)
    db.add(module)
    db.flush()
    activity.record(
        db,
        project_id=access.project_id,
        actor_id=user.id,
        action="module.created",
        entity_type="module",
        entity_id=module.id,
        summary=f"Created module {module.name}",
    )
    return module


def update_module(
    db: Session, access: ProjectAccess, user: User, module_id: uuid.UUID, data: ModuleUpdateIn, if_match: str | None
) -> Module:
    module = get_module(db, access.project_id, module_id)
    require_version(module.version, if_match)
    ensure_active(access)
    changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise AppError(422, "validation_error", "Name must not be blank")
        if _name_taken(db, access.project_id, changes["name"], exclude=module.id):
            raise AppError(409, "module_exists", f"A module named “{changes['name']}” already exists")
    before = {"name": module.name, "description": module.description}
    for k, v in changes.items():
        setattr(module, k, v)
    b, a = activity.diff(before, {"name": module.name, "description": module.description})
    if a:
        module.version += 1
        activity.record(
            db,
            project_id=access.project_id,
            actor_id=user.id,
            action="module.updated",
            entity_type="module",
            entity_id=module.id,
            summary=f"Updated module {module.name}",
            before=b,
            after=a,
        )
    return module


def delete_module(db: Session, access: ProjectAccess, user: User, module_id: uuid.UUID) -> None:
    ensure_active(access)
    module = get_module(db, access.project_id, module_id)
    name = module.name
    db.delete(module)
    activity.record(
        db,
        project_id=access.project_id,
        actor_id=user.id,
        action="module.deleted",
        entity_type="module",
        entity_id=module_id,
        summary=f"Deleted module {name}",
    )


def set_connections(
    db: Session, access: ProjectAccess, user: User, module_id: uuid.UUID, to_ids: list[uuid.UUID]
) -> list[uuid.UUID]:
    """Replace the outgoing connections of a module. Targets must be other modules of the same project."""
    ensure_active(access)
    module = get_module(db, access.project_id, module_id)
    targets = list(dict.fromkeys(to_ids))
    if module.id in targets:
        raise AppError(422, "self_connection", "A module cannot be connected to itself")
    if targets:
        found = set(
            db.execute(
                select(Module.id).where(Module.project_id == access.project_id, Module.id.in_(targets))
            ).scalars()
        )
        missing = [str(t) for t in targets if t not in found]
        if missing:
            raise AppError(
                422,
                "unknown_modules",
                "Some connected modules do not exist in this project",
                extra={"module_ids": missing},
            )
    before = _connections(db, access.project_id).get(module.id, [])
    db.execute(delete(ModuleConnection).where(ModuleConnection.from_module_id == module.id))
    for target in targets:
        db.add(ModuleConnection(project_id=access.project_id, from_module_id=module.id, to_module_id=target))
    activity.record(
        db,
        project_id=access.project_id,
        actor_id=user.id,
        action="module.connections_set",
        entity_type="module",
        entity_id=module.id,
        summary=f"Set {len(targets)} connection(s) for {module.name}",
        before={"to": before},
        after={"to": targets},
    )
    return targets
