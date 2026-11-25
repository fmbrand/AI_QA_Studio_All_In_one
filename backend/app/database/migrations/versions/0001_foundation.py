"""Phase 1 foundation: users, auth tokens, roles, projects, members, modules,
documents, jobs and the activity log.

Revision ID: 0001_foundation
Revises:
Create Date: 2026-11-25 09:55:44.569029
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("key", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("key", name=op.f("uq_roles_key")),
    )
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_superadmin", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("failed_login_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index("uq_users_email_lower", "users", [sa.literal_column("lower(email)")], unique=True)
    op.create_table(
        "projects",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("project_type", sa.String(length=80), server_default="", nullable=False),
        sa.Column("application_url", sa.String(length=2048), nullable=True),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("business_domain", sa.String(length=120), server_default="", nullable=False),
        sa.Column("tech_stack", postgresql.ARRAY(sa.String(length=60)), server_default="{}", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "platform IN ('web', 'android', 'ios', 'api', 'multi_platform')", name=op.f("ck_projects_platform_valid")
        ),
        sa.CheckConstraint("status IN ('active', 'archived')", name=op.f("ck_projects_status_valid")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_projects_created_by_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_index("ix_projects_status_created", "projects", ["status", "created_at"], unique=False)
    op.create_table(
        "refresh_tokens",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.UUID(), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_refresh_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index(op.f("ix_refresh_tokens_family_id"), "refresh_tokens", ["family_id"], unique=False)
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)
    op.create_table(
        "activity_logs",
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("summary", sa.String(length=300), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_activity_logs_actor_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_activity_logs_project_id_projects"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity_logs")),
    )
    op.create_index("ix_activity_logs_actor_created", "activity_logs", ["actor_id", "created_at"], unique=False)
    op.create_index("ix_activity_logs_project_created", "activity_logs", ["project_id", "created_at"], unique=False)
    op.create_table(
        "jobs",
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("stage", sa.String(length=120), nullable=True),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')", name=op.f("ck_jobs_status_valid")
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_jobs_created_by_users")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_jobs_project_id_projects"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index("ix_jobs_project_created", "jobs", ["project_id", "created_at"], unique=False)
    op.create_index("ix_jobs_status_created", "jobs", ["status", "created_at"], unique=False)
    op.create_table(
        "modules",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_modules_created_by_users")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_modules_project_id_projects"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_modules")),
    )
    op.create_index("uq_modules_project_name", "modules", ["project_id", sa.literal_column("lower(name)")], unique=True)
    op.create_table(
        "project_members",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("added_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"], name=op.f("fk_project_members_added_by_users")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_project_members_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name=op.f("fk_project_members_role_id_roles")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_project_members_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_members")),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
    )
    op.create_index(op.f("ix_project_members_user_id"), "project_members", ["user_id"], unique=False)
    op.create_table(
        "module_connections",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("from_module_id", sa.UUID(), nullable=False),
        sa.Column("to_module_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint("from_module_id <> to_module_id", name=op.f("ck_module_connections_not_self")),
        sa.ForeignKeyConstraint(
            ["from_module_id"],
            ["modules.id"],
            name=op.f("fk_module_connections_from_module_id_modules"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_module_connections_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["to_module_id"],
            ["modules.id"],
            name=op.f("fk_module_connections_to_module_id_modules"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_module_connections")),
        sa.UniqueConstraint("from_module_id", "to_module_id", name="uq_module_connections_pair"),
    )
    op.create_index(op.f("ix_module_connections_project_id"), "module_connections", ["project_id"], unique=False)
    op.create_table(
        "uploaded_documents",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=32), server_default="other", nullable=False),
        sa.Column("module_id", sa.UUID(), nullable=True),
        sa.Column("current_version_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "kind IN ('requirement', 'design', 'business_logic', 'api_spec', 'test_cases', 'screenshot', 'other')",
            name=op.f("ck_uploaded_documents_kind_valid"),
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_uploaded_documents_created_by_users")),
        sa.ForeignKeyConstraint(
            ["module_id"], ["modules.id"], name=op.f("fk_uploaded_documents_module_id_modules"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_uploaded_documents_project_id_projects"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uploaded_documents")),
    )
    op.create_index(
        "ix_uploaded_documents_project_created", "uploaded_documents", ["project_id", "created_at"], unique=False
    )
    op.create_table(
        "document_versions",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("processing_status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "processing_status IN ('queued', 'processing', 'processed', 'stored', 'failed')",
            name=op.f("ck_document_versions_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["uploaded_documents.id"],
            name=op.f("fk_document_versions_document_id_uploaded_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_document_versions_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], name=op.f("fk_document_versions_uploaded_by_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_versions")),
        sa.UniqueConstraint("document_id", "version", name="uq_document_versions_doc_version"),
    )
    op.create_index("ix_document_versions_project_sha", "document_versions", ["project_id", "sha256"], unique=False)
    op.create_foreign_key(
        "fk_uploaded_documents_current_version",
        "uploaded_documents",
        "document_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "document_extractions",
        sa.Column("document_version_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("extractor", sa.String(length=40), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.id"],
            name=op.f("fk_document_extractions_document_version_id_document_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_document_extractions_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_extractions")),
    )
    op.create_index(
        op.f("ix_document_extractions_document_version_id"),
        "document_extractions",
        ["document_version_id"],
        unique=False,
    )
    op.create_index(op.f("ix_document_extractions_project_id"), "document_extractions", ["project_id"], unique=False)

    roles = sa.table(
        "roles",
        sa.column("id", sa.UUID()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("rank", sa.SmallInteger()),
        sa.column("description", sa.Text()),
    )
    op.bulk_insert(
        roles,
        [
            {
                "id": uuid.UUID("00000000-0000-7000-8000-000000000040"),
                "key": "owner",
                "name": "Owner",
                "rank": 40,
                "description": "Full control, including deleting the project and managing owners",
            },
            {
                "id": uuid.UUID("00000000-0000-7000-8000-000000000030"),
                "key": "admin",
                "name": "Admin",
                "rank": 30,
                "description": "Manage members, settings and integrations; approve any artifact",
            },
            {
                "id": uuid.UUID("00000000-0000-7000-8000-000000000020"),
                "key": "qa_engineer",
                "name": "QA Engineer",
                "rank": 20,
                "description": "Upload sources, run AI jobs, create and approve QA artifacts",
            },
            {
                "id": uuid.UUID("00000000-0000-7000-8000-000000000010"),
                "key": "viewer",
                "name": "Viewer",
                "rank": 10,
                "description": "Read and export only",
            },
        ],
    )


def downgrade() -> None:
    op.drop_constraint("fk_uploaded_documents_current_version", "uploaded_documents", type_="foreignkey")
    op.drop_index(op.f("ix_document_extractions_project_id"), table_name="document_extractions")
    op.drop_index(op.f("ix_document_extractions_document_version_id"), table_name="document_extractions")
    op.drop_table("document_extractions")
    op.drop_index("ix_document_versions_project_sha", table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_index("ix_uploaded_documents_project_created", table_name="uploaded_documents")
    op.drop_table("uploaded_documents")
    op.drop_index(op.f("ix_module_connections_project_id"), table_name="module_connections")
    op.drop_table("module_connections")
    op.drop_index(op.f("ix_project_members_user_id"), table_name="project_members")
    op.drop_table("project_members")
    op.drop_index("uq_modules_project_name", table_name="modules")
    op.drop_table("modules")
    op.drop_index("ix_jobs_status_created", table_name="jobs")
    op.drop_index("ix_jobs_project_created", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_activity_logs_project_created", table_name="activity_logs")
    op.drop_index("ix_activity_logs_actor_created", table_name="activity_logs")
    op.drop_table("activity_logs")
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_family_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_projects_status_created", table_name="projects")
    op.drop_table("projects")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
    op.drop_table("roles")
