"""Projects and project membership."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.core.pagination import page_meta, paginate
from app.models import Module, Project, ProjectMember, Role, UploadedDocument, User
from app.models.project import ROLE_RANK
from app.repositories.access import ProjectAccess, role_by_key
from app.schemas.projects import ProjectCreateIn, ProjectUpdateIn
from app.services import activity
from app.services.auth import find_user_by_email

_SNAPSHOT_FIELDS = (
    "name",
    "description",
    "project_type",
    "application_url",
    "platform",
    "business_domain",
    "tech_stack",
    "status",
)


def snapshot(project: Project) -> dict[str, Any]:
    return {f: getattr(project, f) for f in _SNAPSHOT_FIELDS}


def stats(db: Session, project_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    result = {pid: {"members": 0, "modules": 0, "documents": 0} for pid in project_ids}
    if not project_ids:
        return result
    queries = {
        "members": select(ProjectMember.project_id, func.count())
        .where(ProjectMember.project_id.in_(project_ids))
        .group_by(ProjectMember.project_id),
        "modules": select(Module.project_id, func.count())
        .where(Module.project_id.in_(project_ids))
        .group_by(Module.project_id),
        "documents": select(UploadedDocument.project_id, func.count())
        .where(UploadedDocument.project_id.in_(project_ids), UploadedDocument.deleted_at.is_(None))
        .group_by(UploadedDocument.project_id),
    }
    for key, stmt in queries.items():
        for pid, count in db.execute(stmt).all():
            result[pid][key] = count
    return result


def to_out(project: Project, role: str, project_stats: dict[str, int]) -> dict[str, Any]:
    return {
        **{
            c: getattr(project, c)
            for c in (
                "id",
                "name",
                "description",
                "project_type",
                "application_url",
                "platform",
                "business_domain",
                "tech_stack",
                "status",
                "archived_at",
                "version",
                "created_by",
                "created_at",
                "updated_at",
            )
        },
        "my_role": role,
        "stats": project_stats,
    }


def list_projects(
    db: Session, user: User, status: str | None, q: str | None, cursor: str | None, limit: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    stmt = (
        select(Project, Role.key)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .join(Role, Role.id == ProjectMember.role_id)
        .where(ProjectMember.user_id == user.id, Project.deleted_at.is_(None))
    )
    if status:
        stmt = stmt.where(Project.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Project.name.ilike(like), Project.business_domain.ilike(like)))
    rows = db.execute(paginate(stmt, Project.created_at, Project.id, cursor, limit)).all()
    rows, page = page_meta([_Row(p, r) for p, r in rows], limit, cursor)
    counts = stats(db, [r.id for r in rows])
    return [to_out(r.project, r.role, counts[r.id]) for r in rows], page


class _Row:
    """Adapter so page_meta can read created_at/id from a (project, role) pair."""

    def __init__(self, project: Project, role: str) -> None:
        self.project, self.role = project, role
        self.id, self.created_at = project.id, project.created_at


def create_project(db: Session, user: User, data: ProjectCreateIn) -> Project:
    payload = data.model_dump()
    payload["application_url"] = str(data.application_url) if data.application_url else None
    project = Project(**payload, created_by=user.id)
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role_id=role_by_key(db, "owner").id, added_by=user.id))
    activity.record(
        db,
        project_id=project.id,
        actor_id=user.id,
        action="project.created",
        entity_type="project",
        entity_id=project.id,
        summary=f"Created project {project.name}",
        after=snapshot(project),
    )
    return project


def require_version(current: int, if_match: str | None) -> None:
    """Optimistic concurrency: the client must send the ETag it last saw."""
    if if_match is None:
        raise AppError(428, "precondition_required", "Send an If-Match header with the version you edited")
    tag = if_match.strip().removeprefix("W/").strip('"')
    if tag != str(current):
        raise AppError(
            412,
            "version_conflict",
            "This item was changed by someone else. Reload it and apply your edit again.",
            extra={"current_version": current},
        )


def ensure_active(access: ProjectAccess) -> None:
    if access.project.status == "archived":
        raise AppError(409, "project_archived", "This project is archived and read-only. Restore it first.")


def update_project(
    db: Session, access: ProjectAccess, user: User, data: ProjectUpdateIn, if_match: str | None
) -> Project:
    project = access.project
    require_version(project.version, if_match)
    ensure_active(access)
    changes = data.model_dump(exclude_unset=True)
    if "application_url" in changes:
        changes["application_url"] = str(data.application_url) if data.application_url else None
    for field in ("name", "platform"):
        if field in changes and changes[field] is None:
            del changes[field]
    for field in ("description", "project_type", "business_domain", "tech_stack"):
        if field in changes and changes[field] is None:
            changes[field] = [] if field == "tech_stack" else ""
    before = snapshot(project)
    for key, value in changes.items():
        setattr(project, key, value)
    b, a = activity.diff(before, snapshot(project))
    if a:
        project.version += 1
        activity.record(
            db,
            project_id=project.id,
            actor_id=user.id,
            action="project.updated",
            entity_type="project",
            entity_id=project.id,
            summary=f"Updated {', '.join(a)} on {project.name}",
            before=b,
            after=a,
        )
    return project


def set_archived(db: Session, access: ProjectAccess, user: User, archived: bool) -> Project:
    project = access.project
    if archived == (project.status == "archived"):
        raise AppError(409, "no_change", f"Project is already {'archived' if archived else 'active'}")
    project.status = "archived" if archived else "active"
    project.archived_at = datetime.now(UTC) if archived else None
    project.version += 1
    action = "project.archived" if archived else "project.restored"
    activity.record(
        db,
        project_id=project.id,
        actor_id=user.id,
        action=action,
        entity_type="project",
        entity_id=project.id,
        summary=f"{'Archived' if archived else 'Restored'} {project.name}",
    )
    return project


def soft_delete(db: Session, access: ProjectAccess, user: User) -> None:
    project = access.project
    project.deleted_at = datetime.now(UTC)
    activity.record(
        db,
        project_id=project.id,
        actor_id=user.id,
        action="project.deleted",
        entity_type="project",
        entity_id=project.id,
        summary=f"Deleted {project.name} (recoverable for 30 days)",
    )


# ---- members -----------------------------------------------------------------------------------


def list_members(db: Session, project_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = db.execute(
        select(User.id, User.email, User.name, Role.key, ProjectMember.created_at)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .join(Role, Role.id == ProjectMember.role_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(Role.rank.desc(), User.name)
    ).all()
    return [{"user_id": r[0], "email": r[1], "name": r[2], "role": r[3], "added_at": r[4]} for r in rows]


def _member(db: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> tuple[ProjectMember, str] | None:
    row = db.execute(
        select(ProjectMember, Role.key)
        .join(Role, Role.id == ProjectMember.role_id)
        .where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
    ).first()
    return (row[0], row[1]) if row else None


def _owner_count(db: Session, project_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count())
        .select_from(ProjectMember)
        .join(Role, Role.id == ProjectMember.role_id)
        .where(ProjectMember.project_id == project_id, Role.key == "owner")
    ).scalar_one()


def _check_can_assign(access: ProjectAccess, target_role: str, current_target_role: str | None) -> None:
    """Admins manage roles below owner; only owners can grant, change or remove owner."""
    touches_owner = target_role == "owner" or current_target_role == "owner"
    if touches_owner and access.role != "owner":
        raise AppError(403, "owner_required", "Only an owner can grant or change the owner role")
    if ROLE_RANK[target_role] > access.rank:
        raise AppError(403, "forbidden", "You cannot grant a role above your own")


def add_member(db: Session, access: ProjectAccess, user: User, email: str, role: str) -> dict[str, Any]:
    ensure_active(access)
    target = find_user_by_email(db, email)
    if target is None:
        raise AppError(404, "user_not_found", "No account uses this email. Ask them to register first, then add them.")
    if _member(db, access.project_id, target.id):
        raise AppError(409, "already_member", "This person is already a member of the project")
    _check_can_assign(access, role, None)
    db.add(
        ProjectMember(
            project_id=access.project_id, user_id=target.id, role_id=role_by_key(db, role).id, added_by=user.id
        )
    )
    activity.record(
        db,
        project_id=access.project_id,
        actor_id=user.id,
        action="member.added",
        entity_type="member",
        entity_id=target.id,
        summary=f"Added {target.email} as {role}",
        after={"role": role},
    )
    return {
        "user_id": target.id,
        "email": target.email,
        "name": target.name,
        "role": role,
        "added_at": datetime.now(UTC),
    }


def change_member_role(
    db: Session, access: ProjectAccess, user: User, target_id: uuid.UUID, role: str
) -> dict[str, Any]:
    ensure_active(access)
    found = _member(db, access.project_id, target_id)
    if not found:
        raise not_found("Member")
    member, current = found
    if current == role:
        raise AppError(409, "no_change", f"This member is already {role}")
    _check_can_assign(access, role, current)
    if current == "owner" and _owner_count(db, access.project_id) <= 1:
        raise AppError(409, "last_owner", "A project needs at least one owner. Add another owner first.")
    member.role_id = role_by_key(db, role).id
    target = db.get(User, target_id)
    assert target is not None
    activity.record(
        db,
        project_id=access.project_id,
        actor_id=user.id,
        action="member.role_changed",
        entity_type="member",
        entity_id=target_id,
        summary=f"Changed {target.email} from {current} to {role}",
        before={"role": current},
        after={"role": role},
    )
    return {
        "user_id": target.id,
        "email": target.email,
        "name": target.name,
        "role": role,
        "added_at": member.created_at,
    }


def remove_member(db: Session, access: ProjectAccess, user: User, target_id: uuid.UUID) -> None:
    found = _member(db, access.project_id, target_id)
    if not found:
        raise not_found("Member")
    member, current = found
    leaving_self = target_id == user.id
    if not leaving_self:
        ensure_active(access)
        if access.rank < ROLE_RANK["admin"]:
            raise AppError(403, "forbidden", "Only admins and owners can remove members")
        _check_can_assign(access, current, current)
    if current == "owner" and _owner_count(db, access.project_id) <= 1:
        raise AppError(409, "last_owner", "A project needs at least one owner. Add another owner first.")
    target = db.get(User, target_id)
    db.delete(member)
    activity.record(
        db,
        project_id=access.project_id,
        actor_id=user.id,
        action="member.left" if leaving_self else "member.removed",
        entity_type="member",
        entity_id=target_id,
        summary=f"{target.email if target else target_id} {'left the project' if leaving_self else 'was removed'}",
        before={"role": current},
    )
