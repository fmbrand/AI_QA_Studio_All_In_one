import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, IdMixin, TimestampMixin

JOB_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")


class Job(IdMixin, TimestampMixin, Base):
    """A unit of background work. The table doubles as the queue (SELECT ... FOR UPDATE SKIP LOCKED)."""

    __tablename__ = "jobs"

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", server_default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    stage: Mapped[str | None] = mapped_column(String(120))
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"status IN {JOB_STATUSES}", name="status_valid"),
        Index("ix_jobs_status_created", "status", "created_at"),
        Index("ix_jobs_project_created", "project_id", "created_at"),
    )
