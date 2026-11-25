import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, IdMixin, TimestampMixin

REQUIREMENT_TYPES = (
    "functional", "non_functional", "business_rule", "user_role", "permission", "validation",
    "dependency", "workflow", "acceptance_criteria", "constraint",
)  # fmt: skip
REQUIREMENT_STATUSES = ("draft", "approved", "rejected")
PRIORITIES = ("critical", "high", "medium", "low")
ORIGINS = ("ai", "manual", "edit")
CONFIDENCE = ("high", "medium", "low")


class Requirement(IdMixin, TimestampMixin, Base):
    """The stable identity of a requirement (REQ-001). Its content lives in immutable versions."""

    __tablename__ = "requirements"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("requirement_versions.id", use_alter=True, ondelete="SET NULL",
                   name="fk_requirements_current_version"),
    )  # fmt: skip
    current_version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    approved_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("requirement_versions.id", use_alter=True, ondelete="SET NULL",
                   name="fk_requirements_approved_version"),
    )  # fmt: skip
    possible_duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("requirements.id", ondelete="SET NULL")
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_requirements_project_key"),
        CheckConstraint(f"status IN {REQUIREMENT_STATUSES}", name="status_valid"),
        Index("ix_requirements_project_status", "project_id", "status"),
        Index("ix_requirements_project_created", "project_id", "created_at"),
    )


class RequirementVersion(IdMixin, Base):
    """One immutable revision of a requirement. Edits add a version; nothing is overwritten."""

    __tablename__ = "requirement_versions"

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    module_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modules.id", ondelete="SET NULL")
    )
    feature: Mapped[str | None] = mapped_column(String(200))
    user_role: Mapped[str | None] = mapped_column(String(120))
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium", server_default="medium")
    acceptance_criteria: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list,
                                                           server_default="[]")  # fmt: skip
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list,
                                                              server_default="[]")  # fmt: skip
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[str | None] = mapped_column(String(16))
    change_reason: Mapped[str | None] = mapped_column(String(500))
    ai_generation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_generations.id", ondelete="SET NULL")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("requirement_id", "version", name="uq_requirement_versions_req_version"),
        CheckConstraint(f"type IN {REQUIREMENT_TYPES}", name="type_valid"),
        CheckConstraint(f"priority IN {PRIORITIES}", name="priority_valid"),
        CheckConstraint(f"origin IN {ORIGINS}", name="origin_valid"),
        CheckConstraint(f"confidence IS NULL OR confidence IN {CONFIDENCE}", name="confidence_valid"),
        Index("ix_requirement_versions_project_module", "project_id", "module_id"),
    )


class KeyCounter(Base):
    """Per-project counters for human-readable keys (REQ-001, later TC_001, GAP-001). Never reused."""

    __tablename__ = "key_counters"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    scope: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
