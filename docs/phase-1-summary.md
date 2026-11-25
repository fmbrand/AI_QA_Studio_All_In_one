# Phase 1 implementation summary

Phase 1 (Foundation) delivers a working, persistent platform: authentication, projects, per-project roles, modules, document uploads with versions and background processing, the activity log, the dashboard, and the project workspace UI. No AI features yet, and no fake data.

## Delivered

| Area | What works |
| --- | --- |
| Auth | Register, sign in, rotating refresh cookie with reuse detection, sign out, profile, password change, rate limiting, lockout |
| Projects | Create, list (active/archived, search, cursor pagination), view, edit with version check, archive, restore, soft delete |
| Members | Add by email, change role, remove, leave; owner/admin rules; last-owner protection |
| Modules | Create, edit with version check, delete, connection graph |
| Documents | Multi-file upload, type and content validation, size limit, duplicate detection, versions, signed downloads, metadata edit, soft delete |
| Processing | PostgreSQL-backed job queue and worker; text/Markdown/CSV/JSON extraction; retries and stale-job recovery |
| Audit | Every mutation recorded with actor, before/after and request ID |
| UI | Sidebar with all 10 modules (future ones labelled by phase), project switcher, dashboard, projects list, workspace tabs, light/dark themes, mobile layout, loading/empty/error states |
| Ops | Docker images, Compose stack, CI (lint, format, types, migration drift, tests, e2e, image builds), seed script |

## Verification

- Backend: 57 pytest tests against real PostgreSQL, including an isolation suite that calls every project-scoped route (found from the OpenAPI schema) as a non-member and asserts 404 with no data change.
- Frontend: 21 Vitest unit and component tests; lint and strict TypeScript pass; production build passes.
- End to end: 3 Playwright tests against the running API, worker and web app (register → project → module → upload → extracted text → activity → sign out → sign in, data still there; session survives reload; anonymous users are redirected).

## Deviations from the blueprint

See the table at the end of [architecture.md](architecture.md#changes-from-the-blueprint). In short: tables are added per phase instead of all at once; the job queue uses PostgreSQL instead of Redis; isolation is enforced in queries and tests now, with row-level security planned for Phase 6; storage is local-disk only.

## Known limitations

- Only text, Markdown, CSV and JSON are extracted. PDF, DOCX, XLSX and image parsing (with OCR) is Phase 2.
- Members must already have an account; email invitations are not built.
- The login rate limiter is per API process; multi-instance deployments need a shared store.
- Uploads are buffered to a temp file before the size check rejects them; put a request-size limit in the reverse proxy in production.
- The S3 storage driver and the 30-day purge job are not built yet.
- The Docker images and Compose stack are built in CI but were not run on the development machine (no Docker available there).

## Open decisions carried forward

- Whether to add an `organizations` level above projects (tenancy for SaaS).
- Whether the QA Hub "QA Lead" role is needed alongside Owner/Admin/QA Engineer/Viewer.

## Next: Phase 2 (context engine)

Parsers with OCR for PDF/DOCX/XLSX/images, chunking with source spans, pgvector embeddings and hybrid retrieval, requirement extraction with stable REQ IDs and versions, the provider-independent AI layer with prompt versioning, and golden-set evaluations in CI.
