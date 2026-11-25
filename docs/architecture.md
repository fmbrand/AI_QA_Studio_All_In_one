# Architecture

Phase 1 ships four runtime components: the Next.js web app, the FastAPI API, the worker and PostgreSQL. Uploaded files go to object storage (local disk in Phase 1). Later phases add the AI engine (inside the worker), a sandboxed Playwright runner and a Playwright MCP gateway.

```mermaid
flowchart LR
  Browser[Next.js web app] -- REST + JWT --> API[FastAPI API]
  API -- SQL --> DB[(PostgreSQL)]
  API -- files --> Store[(Object storage)]
  API -- enqueue job --> DB
  Worker[Worker: python -m app.worker] -- claim job / results --> DB
  Worker -- read files --> Store
```

## Backend layout

```
backend/app
  api/deps.py         current user, project-role dependencies (Viewer / Engineer / Admin / Owner)
  api/v1/             routers: auth, projects (+members, roles), modules, documents (+files), activity (+jobs, dashboard)
  core/               settings, security (Argon2id, JWT, signed URLs), errors (RFC 9457), pagination, rate limit, logging
  database/           engine/session, declarative base, Alembic migrations
  models/             SQLAlchemy models
  schemas/            Pydantic request/response models
  repositories/       project access queries (membership-scoped)
  services/           domain logic: auth, projects, modules, documents, file types, jobs, activity
  integrations/       storage (local driver; S3 driver slots in behind the same protocol)
  worker/             job runner and handlers
```

Routers stay thin: they declare the required role, call one service, commit, and wrap the result. Services hold the rules (archived projects are read-only, last owner cannot leave, duplicate files are rejected) and write the audit log in the same transaction as the change.

## Authentication

- Passwords: Argon2id. Unknown emails are verified against a dummy hash so timing does not reveal which accounts exist.
- Access token: HS256 JWT, 15 minutes, held in browser memory only.
- Refresh token: random 48-byte token in an httpOnly, `SameSite=Strict` cookie scoped to `/api/v1/auth`; only its SHA-256 is stored. Every refresh rotates it. Presenting an already-rotated token revokes the whole token family (theft detection).
- Login: rate-limited per IP and per email (5/minute), account locks for 15 minutes after 10 failures.
- Password change revokes all refresh tokens.

## Authorization and project isolation

Roles are per project: Owner (40) > Admin (30) > QA Engineer (20) > Viewer (10). Each project route declares its minimum role through a dependency that loads the caller's membership for that project.

- Not a member, or the project is deleted: **404**, so project IDs are never confirmed to outsiders.
- Member below the required role: **403**.
- Every child lookup (module, document, version) filters by the project ID from the URL, so an ID from another project never resolves.
- Archived projects are read-only for everyone (409 `project_archived`) until restored.
- Download links are HMAC-signed, expire after 5 minutes, are bound to one user, and re-check membership when used.

`backend/tests/test_isolation.py` walks the OpenAPI schema and calls **every** project-scoped route as a non-member, asserting 404 and that no data changed. New routes are covered automatically.

## Background jobs

The `jobs` table is the queue. The worker claims the oldest queued job with `FOR UPDATE SKIP LOCKED`, so any number of workers can run. A handler failure is retried up to 3 attempts; a `JobError` fails immediately with a user-facing message. Jobs left running by a crashed worker are re-queued after 10 minutes. This replaces the Redis/arq queue in the blueprint: one less service, and jobs survive restarts.

Handlers receive a `report(stage, progress)` callback that writes progress through its own short session, so the UI sees progress without the handler committing unfinished work. Failures are classified: corrupt files, bad requests and model refusals fail at once; rate limits, outages and unexpected errors are retried. The worker loop waits and retries when the database is unreachable instead of exiting.

Jobs: `document_ingest` (parse, chunk, embed, index) and `requirement_extraction` (AI extraction).

## Context engine (Phase 2)

```mermaid
flowchart LR
  Upload[Document version] --> Parse[Parse: PDF, DOCX, XLSX, CSV, JSON, text, images]
  Parse -- scanned pages / images --> OCR[Tesseract OCR, optional]
  Parse --> Chunk[Chunks with page/sheet and exact char offsets]
  Chunk --> Embed[fastembed bge-small, 384-d]
  Embed --> Store[(context_chunks: pgvector + tsvector)]
  Store --> Search[Hybrid search: cosine + full text, RRF]
  Store --> Extract[Requirement extraction]
  Extract --> LLM[LLM provider: Claude / OpenAI / Ollama]
  LLM --> Ground[Grounding: every citation must match the source]
  Ground --> Drafts[Draft requirements with source refs]
```

The `ai_engine` package (next to `app`) holds everything that does not touch the database: parsers, OCR, chunking, embeddings, LLM providers, versioned prompts and grounding. App services call it and persist results.

- **Parsing.** Each parser returns the full text plus segments mapping character ranges to a PDF page or spreadsheet sheet. PDF pages with almost no text are treated as scanned and sent to Tesseract when it is installed; otherwise a warning is stored and shown. Corrupt files fail the job immediately.
- **Chunking.** About 1,200 characters with 200 overlap, ending at paragraph, line or sentence breaks, never crossing a page or sheet. Every chunk stores `char_start`/`char_end` into the extraction text, which is what citations point at.
- **Embeddings.** Local fastembed (`BAAI/bge-small-en-v1.5`, 384 dimensions), so no document text leaves the server for indexing. A hash embedder exists for tests and is refused in production.
- **Search.** Two candidate lists (pgvector cosine with an HNSW index, and PostgreSQL `websearch_to_tsquery` full text) merged with reciprocal rank fusion. Only current versions of non-deleted documents of the caller's project are searched. A module filter adds its connected modules and documents without a module.

## AI layer and requirement extraction

- **Providers.** One interface, `complete_json(system, user, schema)`. Claude uses the Anthropic SDK with JSON-schema structured output, adaptive thinking with explicit effort, prompt caching on the system prompt, and the server-side refusal fallback (`fallbacks: "default"`). OpenAI and Ollama use the OpenAI SDK with strict JSON schema. `LLM_PROVIDER=none` turns AI off; the API answers 503 `ai_not_configured` and the UI explains it.
- **Prompts** live in `ai_engine/prompts/` with a `VERSION`; the app registers each version with a hash of the template and schema in `ai_prompt_versions`, and every call is logged in `ai_generations` (provider, model, prompt version, tokens, latency, retrieved chunk ids, outcome).
- **Prompt-injection defence.** Uploaded text is wrapped in `<source>` blocks and the system prompt states it is data, never instructions. The model has no tools. Output can only be draft requirements, never a status change. Engineer instructions travel in a separate, labelled block. The eval set includes an injection document.
- **Grounding.** Each extracted requirement must cite a source id that was actually sent and a quote that really appears in it (whitespace and case tolerant). Citations that fail are dropped; requirements with no valid citation are discarded and counted. Saved source refs carry document, version, page/sheet and exact character offsets.
- **Atomic runs.** All model calls for a run happen first; requirements are written only if every call succeeds. Invalid output gets one repair attempt. Duplicates are merged within a run and flagged (`possible_duplicate_of`) against existing requirements by embedding similarity ≥ 0.92.
- **Requirements** have a stable per-project key (`REQ-001`, from `key_counters`, never reused) and immutable versions. Editing creates a new version and returns an approved requirement to draft, keeping `approved_version_id` on the last approved one.
- **Evals.** `scripts/run_evals.py` runs the golden set in `evals/requirement_extraction` against a real model and fails below the recall and citation-validity thresholds or if forbidden (injected) content appears. CI runs it only when the `ANTHROPIC_API_KEY` secret exists.

## Uploads

1. Streamed to a temp file while hashing (SHA-256) and enforcing `MAX_UPLOAD_MB` (413).
2. Type check: allowed extension **and** matching content (PDF magic bytes, PNG/JPEG/WebP signatures, DOCX/XLSX zip structure, UTF-8 text without NUL bytes, parseable JSON) (415).
3. Duplicate check by hash within the project (409 with the existing document ID).
4. Stored under a server-generated key; the client filename is sanitised and kept only as metadata.
5. A `document_ingest` job is queued in the same transaction.

## Frontend

- App Router with route groups: `(auth)` for sign-in/registration and `(app)` for the authenticated shell.
- `lib/api.ts`: one fetch wrapper. Adds the bearer token and `If-Match`, refreshes once on 401 (shared promise so parallel requests refresh once), parses problem details into `ApiError`.
- `lib/queries.ts`: TanStack Query hooks. Document lists poll every 2 s only while a version is queued or processing.
- Every page handles loading, empty, error and success states. Write controls are hidden by role, but the API is the authority.
- Theme: CSS variables for light and dark, applied before first paint by an inline script.

## Changes from the blueprint

| Blueprint | Phase 1 | Why |
| --- | --- | --- |
| All 34 tables in the first migration | 13 tables needed now; later tables arrive with their phase | Unused tables would freeze design decisions before the features exist |
| arq on Redis | PostgreSQL job table | Fewer moving parts; durable; enough for current load |
| PostgreSQL row-level security | Membership check in every query + isolation test suite | RLS needs per-request DB roles; planned for Phase 6 hardening |
| S3 + local storage | Local driver behind a `Storage` protocol | S3 driver ships when a deployment needs it |
| SSE job progress | Polling | Simpler; SSE when AI jobs need finer progress |
| pnpm | npm | npm ships with Node; lockfile committed |
| `organizations` table | Not created | Tenancy decision still open |
| Human corrections to extracted context items (Phase 2) | Corrections happen on requirements (edit = new version); chunks are re-derived by reprocessing | Correcting raw chunks would diverge from the source file; requirements are the reviewed artifact |
| AI document-type classification (Phase 2) | The uploader chooses the document type | Cheap, accurate, and avoids a model call per upload |
