import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, IdMixin, TimestampMixin

PLATFORMS = ("web", "android", "ios", "api", "multi_platform")
PROJECT_STATUSES = ("active", "archived")
ROLE_KEYS = ("owner", "admin", "qa_engineer", "viewer")
ROLE_RANK = {"viewer": 10, "qa_engineer": 20, "admin": 30, "owner": 40}


class Role(IdMixin, Base):
    __tablename__ = "roles"

    key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")


class Project(IdMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    project_type: Mapped[str] = mapped_column(String(80), nullable=False, default="", server_default="")
    application_url: Mapped[str | None] = mapped_column(String(2048))
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    business_domain: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default="")
    tech_stack: Mapped[list[str]] = mapped_column(ARRAY(String(60)), nullable=False, default=list, server_default="{}")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        CheckConstraint(f"platform IN {PLATFORMS}", name="platform_valid"),
        CheckConstraint(f"status IN {PROJECT_STATUSES}", name="status_valid"),
        Index("ix_projects_status_created", "status", "created_at"),
    )


class ProjectMember(IdMixin, TimestampMixin, Base):
    __tablename__ = "project_members"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    added_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),)


class Module(IdMixin, TimestampMixin, Base):
    __tablename__ = "modules"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (Index("uq_modules_project_name", "project_id", func.lower(name), unique=True),)


class ModuleConnection(IdMixin, Base):
    """A directed dependency between two modules of the same project (drives impact analysis later)."""

    __tablename__ = "module_connections"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    to_module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("from_module_id", "to_module_id", name="uq_module_connections_pair"),
        CheckConstraint("from_module_id <> to_module_id", name="not_self"),
    )
