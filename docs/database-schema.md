# Database schema (Phase 1)

PostgreSQL, managed only through Alembic migrations (`backend/app/database/migrations`). UUID v7 primary keys, `created_at`/`updated_at` timestamps, foreign keys with explicit `ON DELETE` behaviour. CI runs `alembic check` to fail on drift between models and migrations.

```mermaid
erDiagram
  users ||--o{ refresh_tokens : has
  users ||--o{ project_members : joins
  roles ||--o{ project_members : grants
  projects ||--o{ project_members : has
  projects ||--o{ modules : contains
  modules ||--o{ module_connections : from
  modules ||--o{ module_connections : to
  projects ||--o{ uploaded_documents : owns
  modules |o--o{ uploaded_documents : tags
  uploaded_documents ||--o{ document_versions : versions
  document_versions ||--o{ document_extractions : yields
  projects ||--o{ jobs : queues
  projects ||--o{ activity_logs : audits
  users ||--o{ activity_logs : acts
```

## Tables

| Table | Purpose | Key columns and rules |
| --- | --- | --- |
| `users` | Accounts | Unique `lower(email)`; Argon2id `password_hash`; `failed_login_count`, `locked_until` for lockout; `is_superadmin` (platform flag, unused in Phase 1) |
| `refresh_tokens` | Rotating refresh tokens | Unique `token_hash` (SHA-256); `family_id` links rotations; `revoked_at`, `replaced_by_id` |
| `roles` | Owner, Admin, QA Engineer, Viewer | Seeded by the migration with fixed IDs; `rank` 40/30/20/10 |
| `projects` | A software project | `platform` ∈ web, android, ios, api, multi_platform; `status` ∈ active, archived; `tech_stack` text[]; `version` for optimistic concurrency; `deleted_at` soft delete |
| `project_members` | Per-project role | Unique `(project_id, user_id)` |
| `modules` | Product areas | Unique `(project_id, lower(name))`; `version` |
| `module_connections` | Directed module graph | Unique pair; check `from <> to`; cascades when a module is deleted |
| `uploaded_documents` | A document in a project | `kind` ∈ requirement, design, business_logic, api_spec, test_cases, screenshot, other; optional `module_id` (set null on module delete); `current_version_id`; `deleted_at` |
| `document_versions` | Immutable file versions | Unique `(document_id, version)`; `sha256` indexed with `project_id` for duplicate detection; `storage_key`; `processing_status` ∈ queued, processing, processed, stored, failed |
| `document_extractions` | Extracted text per version | `extractor`, `text`, `char_count`, `meta` (CSV rows/columns, truncation) |
| `jobs` | Background work and its queue | `status` ∈ queued, running, succeeded, failed, cancelled; `progress`, `stage`, `attempts`, `locked_at`; JSON `input` / `result` |
| `activity_logs` | Append-only audit trail | `action`, `entity_type`, `entity_id`, `summary`, changed-field `before` / `after`, `request_id` |

## Indexes

- `(project_id, created_at)` on documents, jobs and activity for the paginated lists.
- `(status, created_at)` on jobs for the worker's claim query; `(status, created_at)` on projects.
- `(project_id, sha256)` on document versions for duplicate detection.
- Unique functional indexes on `lower(users.email)` and `(modules.project_id, lower(modules.name))`.

## Deletion behaviour

- Projects and documents are soft-deleted (`deleted_at`) and disappear from every query. A purge job (Phase 6) removes rows and files after 30 days.
- Modules are hard-deleted; their connections cascade and documents keep existing without a module.
- Deleting a user cascades their memberships and tokens; activity rows keep `actor_id = NULL`.

## Coming in later phases

Phase 2 adds `context_chunks` (pgvector embeddings), `requirements`, `requirement_versions` and `project_context`. Phase 3 adds design, gap, test case and bug tables; Phase 4 automation tables; Phase 5 `trace_links` and project snapshots. See the blueprint for the full model.
