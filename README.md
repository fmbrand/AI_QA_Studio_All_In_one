# AI QA Studio

A project-aware QA engineering workspace. Each software project gets its own isolated knowledge base (documents, modules, members, history), which later phases use for requirement analysis, gap analysis, test case and bug report generation, and Playwright automation.

**Status: Phase 1 (Foundation) is complete.** Authentication, projects, members and roles, modules, document uploads with versioning, background processing, activity history and the dashboard all work end to end and are persisted in PostgreSQL. The AI modules (Phases 2–5) appear in the navigation, labelled with the phase that delivers them, and show no placeholder data.

| Layer | Stack |
| --- | --- |
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, shadcn-style components, TanStack Query, Lucide |
| Backend | Python 3.12+, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic |
| Database | PostgreSQL 16+ (pgvector image ready for Phase 2) |
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

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 22+, PostgreSQL 16+ server binaries.

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
cd backend && uv run pytest           # 57 tests: auth, projects, members, modules, uploads, isolation, units
cd frontend && npm test               # 21 unit and component tests
cd frontend && npm run e2e            # 3 Playwright tests against the running stack
```

CI (`.github/workflows/ci.yml`) runs lint, format, type checks, migrations drift check, all three suites and both Docker builds on every push and pull request.

## Repository layout

```
backend/    FastAPI app (app/), Alembic migrations, worker, scripts, tests
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
