import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
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

DOCUMENT_KINDS = (
    "requirement",
    "design",
    "business_logic",
    "api_spec",
    "test_cases",
    "screenshot",
    "other",
)
PROCESSING_STATUSES = ("queued", "processing", "processed", "stored", "failed")


class UploadedDocument(IdMixin, TimestampMixin, Base):
    __tablename__ = "uploaded_documents"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="other", server_default="other")
    module_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modules.id", ondelete="SET NULL")
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "document_versions.id", use_alter=True, ondelete="SET NULL", name="fk_uploaded_documents_current_version"
        ),
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"kind IN {DOCUMENT_KINDS}", name="kind_valid"),
        Index("ix_uploaded_documents_project_created", "project_id", "created_at"),
    )


class DocumentVersion(IdMixin, Base):
    __tablename__ = "document_versions"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploaded_documents.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="queued", server_default="queued"
    )
    processing_error: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_document_versions_doc_version"),
        CheckConstraint(f"processing_status IN {PROCESSING_STATUSES}", name="status_valid"),
        Index("ix_document_versions_project_sha", "project_id", "sha256"),
    )


class DocumentExtraction(IdMixin, Base):
    """Text extracted from one document version. Phase 2 adds structured items and chunks."""

    __tablename__ = "document_extractions"

    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    extractor: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
