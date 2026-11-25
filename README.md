# AI QA Studio

A project-aware QA engineering workspace. Each software project gets its own isolated knowledge base (documents, modules, members, history), which later phases use for requirement analysis, gap analysis, test case and bug report generation, and Playwright automation.

**Status: Phases 1–2 are complete.**

- Phase 1 (foundation): authentication, projects, members and roles, modules, document uploads with versioning, background jobs, activity history and the dashboard.
- Phase 2 (context engine): PDF/Word/Excel/image parsing with optional OCR, semantic + keyword search with pgvector, and requirements with stable `REQ-###` keys, versions, review, and AI extraction where every requirement cites the exact source text.

AI generation supports Claude, OpenAI and Ollama and is off until `LLM_PROVIDER` is set; everything else works without it. Modules for later phases appear in the navigation, labelled with their phase, and show no placeholder data.

| Layer | Stack |
| --- | --- |
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, shadcn-style components, TanStack Query, Lucide |
| Backend | Python 3.12+, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic |
| Database | PostgreSQL 16+ with pgvector |
| AI | Provider-independent layer (Claude via the Anthropic SDK, OpenAI, Ollama), local fastembed embeddings, Tesseract OCR |
| Jobs | PostgreSQL-backed queue + `python -m app.worker` |
| Tests | pytest (backend), Vitest + Testing Library (frontend), Playwright (end to end) |

## Quick start

### Option A: Docker Compose

```bash
cp .env.example .env          # set JWT_SECRET to a long random string
docker compose up --build
```

Web app: http://localhost:3000 · API docs: http://localhost:8000/api/docs

### Option B: Local development (no Docker)

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 22+, PostgreSQL 16+ server binaries with pgvector (see the setup guide if yours lacks it). Optional: Tesseract for OCR, an API key for AI extraction.

```bash
# Backend (terminal 1)
cd backend
cp .env.example .env
uv sync
python scripts/devdb.py start        # throwaway PostgreSQL on 127.0.0.1:5434
uv run alembic upgrade head
uv run python scripts/seed.py         # optional demo user + project (prints the password)
uv run uvicorn app.main:app --reload --port 8000

# Worker (terminal 2)
cd backend && uv run python -m app.worker

# Frontend (terminal 3)
cd frontend
cp .env.example .env.local
npm install
npm run dev                           # http://localhost:3000
```

Full instructions, including Windows notes and using your own PostgreSQL: [docs/setup-guide.md](docs/setup-guide.md).

## Tests

```bash
cd backend && uv run pytest           # 85 tests: auth, projects, uploads, isolation, parsing, search, requirements, AI extraction
cd frontend && npm test               # 21 unit and component tests
cd frontend && npm run e2e            # 5 Playwright tests against the running stack
cd backend && uv run python scripts/run_evals.py   # AI golden set; needs LLM_PROVIDER and a key, costs tokens
```

CI (`.github/workflows/ci.yml`) runs lint, format, type checks, migrations drift check, all three suites and both Docker builds on every push and pull request.

## Repository layout

```
backend/    FastAPI app (app/), AI engine (ai_engine/), Alembic migrations, worker, evals, scripts, tests
frontend/   Next.js app (app/), components, lib (API client, queries), tests (unit, e2e)
docs/       architecture, database schema, API, setup and user guides, Phase 1 summary
.github/    CI workflow
docker-compose.yml
```

## Documentation

- [Architecture](docs/architecture.md)
- [Database schema](docs/database-schema.md)
- [API documentation](docs/api-documentation.md)
- [Setup guide](docs/setup-guide.md)
- [User guide](docs/user-guide.md)
- [Phase 1 implementation summary](docs/phase-1-summary.md)
- [Phase 2 implementation summary](docs/phase-2-summary.md)
