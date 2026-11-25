"""Phase 2 context engine: context chunks (pgvector + full text), requirements with versions,
key counters, prompt versions and AI generation log.

Revision ID: 0002_context_engine
Revises: 0001_foundation
Create Date: 2026-11-25 11:59:43.085298
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_context_engine"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "ai_prompt_versions",
        sa.Column("task", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("template_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_prompt_versions")),
        sa.UniqueConstraint("task", "version", "template_hash", name="uq_ai_prompt_versions_task"),
    )
    op.create_table(
        "key_counters",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_key_counters_project_id_projects"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("project_id", "scope", name=op.f("pk_key_counters")),
    )
    op.create_table(
        "requirements",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("current_version_id", sa.UUID(), nullable=True),
        sa.Column("current_version_no", sa.Integer(), server_default="1", nullable=False),
        sa.Column("approved_version_id", sa.UUID(), nullable=True),
        sa.Column("possible_duplicate_of", sa.UUID(), nullable=True),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'approved', 'rejected')", name=op.f("ck_requirements_status_valid")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_requirements_created_by_users")),
        sa.ForeignKeyConstraint(
            ["possible_duplicate_of"],
            ["requirements.id"],
            name=op.f("fk_requirements_possible_duplicate_of_requirements"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_requirements_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], name=op.f("fk_requirements_reviewed_by_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requirements")),
        sa.UniqueConstraint("project_id", "key", name="uq_requirements_project_key"),
    )
    op.create_index("ix_requirements_project_created", "requirements", ["project_id", "created_at"], unique=False)
    op.create_index("ix_requirements_project_status", "requirements", ["project_id", "status"], unique=False)
    op.create_table(
        "ai_generations",
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("task", sa.String(length=64), nullable=False),
        sa.Column("prompt_version_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("provider_request_id", sa.String(length=120), nullable=True),
        sa.Column("retrieved_chunk_ids", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_ai_generations_job_id_jobs"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_ai_generations_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["prompt_version_id"],
            ["ai_prompt_versions.id"],
            name=op.f("fk_ai_generations_prompt_version_id_ai_prompt_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_generations")),
    )
    op.create_index("ix_ai_generations_project_created", "ai_generations", ["project_id", "created_at"], unique=False)
    op.create_table(
        "requirement_versions",
        sa.Column("requirement_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("module_id", sa.UUID(), nullable=True),
        sa.Column("feature", sa.String(length=200), nullable=True),
        sa.Column("user_role", sa.String(length=120), nullable=True),
        sa.Column("priority", sa.String(length=16), server_default="medium", nullable=False),
        sa.Column("acceptance_criteria", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("source_refs", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=True),
        sa.Column("change_reason", sa.String(length=500), nullable=True),
        sa.Column("ai_generation_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence IN ('high', 'medium', 'low')",
            name=op.f("ck_requirement_versions_confidence_valid"),
        ),
        sa.CheckConstraint("origin IN ('ai', 'manual', 'edit')", name=op.f("ck_requirement_versions_origin_valid")),
        sa.CheckConstraint(
            "priority IN ('critical', 'high', 'medium', 'low')", name=op.f("ck_requirement_versions_priority_valid")
        ),
        sa.CheckConstraint(
            "type IN ('functional', 'non_functional', 'business_rule', 'user_role', 'permission', 'validation', 'dependency', 'workflow', 'acceptance_criteria', 'constraint')",
            name=op.f("ck_requirement_versions_type_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["ai_generation_id"],
            ["ai_generations.id"],
            name=op.f("fk_requirement_versions_ai_generation_id_ai_generations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_requirement_versions_created_by_users")),
        sa.ForeignKeyConstraint(
            ["module_id"], ["modules.id"], name=op.f("fk_requirement_versions_module_id_modules"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_requirement_versions_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["requirements.id"],
            name=op.f("fk_requirement_versions_requirement_id_requirements"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requirement_versions")),
        sa.UniqueConstraint("requirement_id", "version", name="uq_requirement_versions_req_version"),
    )
    op.create_index(
        "ix_requirement_versions_project_module", "requirement_versions", ["project_id", "module_id"], unique=False
    )
    op.create_foreign_key(
        "fk_requirements_current_version",
        "requirements",
        "requirement_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_requirements_approved_version",
        "requirements",
        "requirement_versions",
        ["approved_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "context_chunks",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("document_version_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("sheet", sa.String(length=120), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=False),
        sa.Column("embedding_model", sa.String(length=120), nullable=False),
        sa.Column(
            "content_tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', content)", persisted=True),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["uploaded_documents.id"],
            name=op.f("fk_context_chunks_document_id_uploaded_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.id"],
            name=op.f("fk_context_chunks_document_version_id_document_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_context_chunks_project_id_projects"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_context_chunks")),
    )
    op.create_index(
        "ix_context_chunks_embedding",
        "context_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_context_chunks_project_version",
        "context_chunks",
        ["project_id", "document_version_id", "chunk_index"],
        unique=False,
    )
    op.create_index("ix_context_chunks_tsv", "context_chunks", ["content_tsv"], unique=False, postgresql_using="gin")


def downgrade() -> None:
    op.drop_constraint("fk_requirements_current_version", "requirements", type_="foreignkey")
    op.drop_constraint("fk_requirements_approved_version", "requirements", type_="foreignkey")
    op.drop_index("ix_context_chunks_tsv", table_name="context_chunks", postgresql_using="gin")
    op.drop_index("ix_context_chunks_project_version", table_name="context_chunks")
    op.drop_index(
        "ix_context_chunks_embedding",
        table_name="context_chunks",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_table("context_chunks")
    op.drop_index("ix_requirement_versions_project_module", table_name="requirement_versions")
    op.drop_table("requirement_versions")
    op.drop_index("ix_ai_generations_project_created", table_name="ai_generations")
    op.drop_table("ai_generations")
    op.drop_index("ix_requirements_project_status", table_name="requirements")
    op.drop_index("ix_requirements_project_created", table_name="requirements")
    op.drop_table("requirements")
    op.drop_table("key_counters")
    op.drop_table("ai_prompt_versions")
