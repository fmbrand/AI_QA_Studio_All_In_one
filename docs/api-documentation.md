# API documentation

The live, complete reference is the OpenAPI schema served by the API: **http://localhost:8000/api/docs** (Swagger UI) and `/api/openapi.json`. This page covers the conventions and lists the Phase 1 endpoints.

## Conventions

- Base path: `/api/v1`. JSON in and out, except uploads (`multipart/form-data`) and downloads.
- Auth: `Authorization: Bearer <access token>`. Obtain tokens from register, login or refresh. The refresh token travels only in the `aiqa_refresh` httpOnly cookie (send requests with credentials).
- Success envelope:

  ```json
  { "data": { ... }, "meta": { "request_id": "…", "page": null } }
  ```

- Lists use cursor pagination: `?limit=50&cursor=<next_cursor>`; `meta.page = { cursor, next_cursor, limit }`. `limit` is capped at 200.
- Errors are RFC 9457 problem details (`application/problem+json`):

  ```json
  { "type": "https://errors.ai-qa-studio.dev/version_conflict", "title": "Precondition Failed", "status": 412,
    "detail": "This item was changed by someone else…", "code": "version_conflict", "request_id": "…",
    "errors": [{ "field": "name", "message": "…" }] }
  ```

- Optimistic concurrency: `PATCH` on projects and modules requires `If-Match: "<version>"` (428 without it, 412 if stale). Responses carry `ETag`.
- Every response has `X-Request-ID` (echoed if you send a valid one).

## Common error codes

| Status | Code | Meaning |
| --- | --- | --- |
| 401 | `unauthorized`, `invalid_credentials`, `invalid_refresh_token` | Missing/invalid token or bad sign-in |
| 403 | `forbidden`, `owner_required` | Member, but role too low |
| 404 | `not_found`, `user_not_found` | Missing, or a project you are not a member of |
| 409 | `project_archived`, `duplicate_document`, `email_taken`, `already_member`, `last_owner`, `module_exists`, `no_change` | Conflicts with current state |
| 412 / 428 | `version_conflict` / `precondition_required` | Concurrency check |
| 413 | `file_too_large` | Over `MAX_UPLOAD_MB` |
| 415 | `unsupported_file_type` | Extension not allowed, or content does not match it |
| 422 | `validation_error`, `empty_file`, `invalid_json`, `unknown_modules` | Invalid input |
| 423 | `account_locked` | Too many failed sign-ins |
| 429 | `rate_limited` | Slow down; see `Retry-After` |

## Endpoints

Minimum role per project route in brackets.

### Auth and account

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/auth/register` | `{email, name, password}` → 201 tokens + refresh cookie |
| POST | `/auth/login` | `{email, password}` → tokens + refresh cookie |
| POST | `/auth/refresh` | Cookie → new tokens, rotated cookie |
| POST | `/auth/logout` | Revokes the refresh token → 204 |
| GET | `/me` | User and project memberships |
| PATCH | `/me` | `{name}` |
| POST | `/me/password` | `{current_password, new_password}` → 204, signs out all sessions |

### Projects, roles and members

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/roles` | Role catalogue |
| GET | `/projects` | `?status=active\|archived&q=&cursor=&limit=` — only projects you belong to |
| POST | `/projects` | `{name, platform, description?, project_type?, application_url?, business_domain?, tech_stack?}`; you become Owner |
| GET | `/projects/{id}` [Viewer] | Includes `my_role` and `stats` |
| PATCH | `/projects/{id}` [Admin] | Requires `If-Match` |
| POST | `/projects/{id}/archive`, `/restore` [Admin] | |
| DELETE | `/projects/{id}` [Owner] | Soft delete |
| GET | `/projects/{id}/members` [Viewer] | |
| POST | `/projects/{id}/members` [Admin] | `{email, role}`; account must exist; only owners grant Owner |
| PATCH | `/projects/{id}/members/{user_id}` [Admin] | `{role}`; the last owner cannot be demoted |
| DELETE | `/projects/{id}/members/{user_id}` [Viewer for self, Admin for others] | Leave or remove |

### Modules

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/projects/{id}/modules` [Viewer] | Each with `connected_module_ids` |
| POST | `/projects/{id}/modules` [QA Engineer] | `{name, description?}`; names unique per project (case-insensitive) |
| GET | `/projects/{id}/modules/{module_id}` [Viewer] | |
| PATCH | `/projects/{id}/modules/{module_id}` [QA Engineer] | Requires `If-Match` |
| DELETE | `/projects/{id}/modules/{module_id}` [Admin] | |
| PUT | `/projects/{id}/modules/{module_id}/connections` [QA Engineer] | `{to_module_ids: []}` replaces outgoing connections |

### Documents and files

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/projects/{id}/documents` [QA Engineer] | Multipart: `file`, `kind?`, `title?`, `module_id?` → 201 `{document, job}` |
| GET | `/projects/{id}/documents` [Viewer] | `?kind=&module_id=&q=&cursor=&limit=` |
| GET | `/projects/{id}/documents/{doc_id}` [Viewer] | With all versions |
| PATCH | `/projects/{id}/documents/{doc_id}` [QA Engineer] | `{title?, kind?, module_id?, clear_module?}` |
| DELETE | `/projects/{id}/documents/{doc_id}` [QA Engineer] | Soft delete |
| POST | `/projects/{id}/documents/{doc_id}/versions` [QA Engineer] | Multipart `file` → new version |
| GET | `/projects/{id}/documents/{doc_id}/extractions` [Viewer] | Extracted text, newest version first |
| GET | `/projects/{id}/documents/{doc_id}/versions/{version_id}/download-url` [Viewer] | `{url, expires_in}` signed link |
| GET | `/files/{token}` | Streams the file; token is short-lived and user-bound |

### Jobs, activity, dashboard, health

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/projects/{id}/jobs` [Viewer] | 20 most recent |
| GET | `/jobs/{job_id}` | Visible to members of the job's project |
| POST | `/jobs/{job_id}/cancel` | QA Engineer; queued jobs only |
| GET | `/projects/{id}/activity` [Viewer] | Paginated audit trail with actor names |
| GET | `/dashboard` | Totals, recent activity and jobs across your projects |
| GET | `/health` | Database connectivity |
