# Setup guide

Two ways to run AI QA Studio: Docker Compose (closest to production) or the local development stack (fastest to iterate).

## 1. Docker Compose

```bash
cp .env.example .env
# Edit .env: set JWT_SECRET, e.g. python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up --build
```

This starts PostgreSQL (pgvector image), runs migrations once (`migrate` service), then the API, the worker and the web app.

| Service | URL |
| --- | --- |
| Web | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs (OpenAPI) | http://localhost:8000/api/docs |

Uploads are stored in the `uploads` volume, the database in `pgdata`. To seed a demo user:

```bash
docker compose run --rm api python scripts/seed.py
```

If the browser reaches the API on another host or port, set `PUBLIC_API_URL` and `CORS_ORIGINS` in `.env` and rebuild the `web` image (the API URL is baked into the frontend build). Behind HTTPS set `COOKIE_SECURE=true`.

## 2. Local development

### Prerequisites

- Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) (`pip install uv` works; then use `python -m uv` if `uv` is not on PATH)
- Node.js 22 or newer
- PostgreSQL 16+ server binaries (`initdb`, `pg_ctl`, `psql`). On Windows the EDB installer puts them in `C:\Program Files\PostgreSQL\<version>\bin`, which `devdb.py` finds automatically. Elsewhere set `PG_BIN`.

### Database

`backend/scripts/devdb.py` runs a private PostgreSQL cluster in `backend/.devdb` on `127.0.0.1:5434` with local trust authentication. It never touches a system PostgreSQL service and needs no password.

```bash
cd backend
python scripts/devdb.py start     # first run initialises the cluster and creates ai_qa_studio + ai_qa_studio_test
python scripts/devdb.py status
python scripts/devdb.py stop
```

**pgvector (required from Phase 2).** Semantic search needs the `vector` extension. Docker and CI images include it. Locally, if your PostgreSQL lacks it and you cannot install into it (Program Files needs admin rights on Windows), run the dev database from a private copy of the binaries instead:

```bash
python scripts/devdb.py stop
python scripts/devdb.py make-private                    # copies bin/lib/share into backend/.pgsql (~150 MB, gitignored)
# build pgvector (Windows: Visual Studio Build Tools; see the notes at the top of devdb.py), then:
python scripts/devdb.py install-pgvector path/to/pgvector
python scripts/devdb.py start                           # warns if pgvector is still missing
```

On Linux/macOS install your distribution's pgvector package (for example `postgresql-16-pgvector`, or `brew install pgvector`).

To use your own PostgreSQL instead, create two databases and point `DATABASE_URL` and `TEST_DATABASE_URL` at them in `backend/.env`:

```
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/ai_qa_studio
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/ai_qa_studio_test
```

### Backend

```bash
cd backend
cp .env.example .env
uv sync                                   # creates .venv from uv.lock
uv run alembic upgrade head
uv run python scripts/seed.py             # optional; prints a generated password once
uv run uvicorn app.main:app --reload --port 8000
```

In a second terminal start the worker, which processes uploads:

```bash
cd backend
uv run python -m app.worker
```

Without the worker, uploads stay "Queued". Several workers can run at once. The first indexed upload downloads the embedding model (about 130 MB) to `EMBEDDING_CACHE_DIR` or the system temp folder.

### AI and OCR (optional)

- **Language model.** Requirement extraction is off until you set `LLM_PROVIDER` in `backend/.env` and restart the API and worker:
  - Claude: `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY=...` (or leave the key empty and sign in with `ant auth login`). Default model `claude-opus-5-5`, effort `high`.
  - OpenAI: `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL`.
  - Ollama (free, local): `LLM_PROVIDER=ollama`, `OLLAMA_MODEL` (and `OLLAMA_BASE_URL` if not the default).
  Everything else (upload, indexing, search, manual requirements) works without a model.
- **OCR.** Install Tesseract to read scanned PDF pages and images: `winget install UB-Mannheim.TesseractOCR` (admin), `apt install tesseract-ocr`, or `brew install tesseract`. It is detected automatically; set `TESSERACT_CMD` if it is not on PATH. Then use **Reprocess** on documents uploaded earlier.
- **AI evals** (spend real tokens): `LLM_PROVIDER=anthropic uv run python scripts/run_evals.py`.

### Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000 and create an account.

## Environment variables

Backend (`backend/.env`, or the root `.env` for Compose):

| Variable | Default | Purpose |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | `production` enforces a strong `JWT_SECRET` |
| `DATABASE_URL` | dev cluster URL | SQLAlchemy URL (`postgresql+psycopg://…`) |
| `TEST_DATABASE_URL` | dev test DB | Used by pytest; the schema is dropped on each run |
| `JWT_SECRET` | empty (dev fallback) | Signs access tokens and download links; 32+ chars in production |
| `ACCESS_TOKEN_MINUTES` | `15` | Access token lifetime |
| `REFRESH_TOKEN_DAYS` | `14` | Refresh cookie lifetime |
| `COOKIE_SECURE` | `false` | Set `true` behind HTTPS |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated web origins allowed to call the API |
| `STORAGE_LOCAL_DIR` | `./storage` | Where uploaded files are written |
| `MAX_UPLOAD_MB` | `25` | Per-file upload limit |
| `MAX_FAILED_LOGINS` / `LOCKOUT_MINUTES` | `10` / `15` | Account lockout |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | `5` | Per IP and per email |
| `LLM_PROVIDER` | `none` | `anthropic`, `openai`, `ollama`, or `none` (AI off) |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` / `ANTHROPIC_EFFORT` | empty / `claude-opus-5-5` / `high` | Claude settings |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | empty | OpenAI settings |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | `http://localhost:11434/v1` / empty | Local model settings |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | `fastembed` / `BAAI/bge-small-en-v1.5` | Local embeddings (384 dimensions; `hash` is test-only) |
| `EMBEDDING_CACHE_DIR` | system temp | Where the embedding model is stored |
| `TESSERACT_CMD` / `OCR_LANGUAGES` | auto / `eng` | OCR binary and languages |
| `CHUNK_SIZE_CHARS` / `CHUNK_OVERLAP_CHARS` | `1200` / `200` | Passage size for indexing |
| `EXTRACTION_WINDOW_CHARS` | `24000` | Source text per model call during extraction |

Frontend (`frontend/.env.local`): `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`) and `NEXT_PUBLIC_MAX_UPLOAD_MB`. Never put secrets in `NEXT_PUBLIC_*` variables.

## Running tests

```bash
# Backend: needs the test database (TEST_DATABASE_URL); wipes it each run
cd backend
uv run ruff check . && uv run ruff format --check .
uv run pytest

# Frontend unit and component tests
cd frontend
npm run lint && npm run typecheck && npm test

# End to end: start the API, worker and web app first (see above), then
cd frontend
npx playwright install chromium   # first time only
npm run e2e
```

Locally Playwright reuses the servers you started. In CI (`CI=true`) it starts the API and the web app itself; the worker always has to be started separately (the CI workflow runs it as a background step), otherwise uploads stay "Queued" and the upload test fails.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Uploads stay "Queued" | Start the worker: `uv run python -m app.worker` |
| "Cannot reach the server" in the browser | The API is not running on `NEXT_PUBLIC_API_URL`, or `CORS_ORIGINS` does not include the web origin |
| Signed out after every reload | The browser blocks the refresh cookie. Web and API must be same-site (for example both on `localhost`), and `COOKIE_SECURE=true` requires HTTPS |
| `devdb.py` cannot find `initdb` | Set `PG_BIN` to the PostgreSQL `bin` directory |
| Port 5434 already in use | Set `DEVDB_PORT` and update `DATABASE_URL` / `TEST_DATABASE_URL` |
| Migration fails with `extension "vector" is not available` | Install pgvector (see Database above) |
| "Extract with AI" is disabled | No language model is configured; set `LLM_PROVIDER` and restart API and worker |
| Documents show "No text found" | Scanned pages or images without OCR: install Tesseract, then Reprocess |
