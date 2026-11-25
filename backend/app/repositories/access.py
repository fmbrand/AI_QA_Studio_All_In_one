"""Project-scoped access queries. Every lookup of project data goes through a membership check."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project, ProjectMember, Role


@dataclass(frozen=True)
class ProjectAccess:
    project: Project
    role: str
    rank: int

    @property
    def project_id(self) -> uuid.UUID:
        return self.project.id


def get_project_access(db: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectAccess | None:
    """Return the caller's access to a live (not deleted) project, or None if they are not a member."""
    row = db.execute(
        select(Project, Role.key, Role.rank)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .join(Role, Role.id == ProjectMember.role_id)
        .where(
            Project.id == project_id,
            Project.deleted_at.is_(None),
            ProjectMember.user_id == user_id,
        )
    ).first()
    if row is None:
        return None
    project, role_key, rank = row
    return ProjectAccess(project=project, role=role_key, rank=rank)


def member_project_ids(user_id: uuid.UUID):  # type: ignore[no-untyped-def]
    """Sub-select of live project ids the user belongs to, for scoping cross-project queries."""
    return (
        select(ProjectMember.project_id)
        .join(Project, Project.id == ProjectMember.project_id)
        .where(ProjectMember.user_id == user_id, Project.deleted_at.is_(None))
    )


def role_by_key(db: Session, key: str) -> Role:
    return db.execute(select(Role).where(Role.key == key)).scalar_one()
