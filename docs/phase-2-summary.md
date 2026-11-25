# Phase 2 implementation summary

Phase 2 (AI context engine) makes every project's documents readable, searchable and citable, and adds requirements with AI extraction, review and version history. AI generation is built for Claude, OpenAI and Ollama but stays switched off until a provider is configured; everything else works without one.

## Delivered

| Area | What works |
| --- | --- |
| Parsing | PDF (per page), DOCX (headings, lists, tables in order), XLSX (per sheet), CSV, JSON, text/Markdown, images. Scanned PDF pages and images go to Tesseract when installed; otherwise a warning is stored and shown |
| Indexing | Overlapping passages that never cross a page or sheet, with exact character offsets; local embeddings (fastembed, 384-d); pgvector HNSW + PostgreSQL full text |
| Search | Hybrid ranking (cosine + full text, reciprocal rank fusion), project-isolated, current versions only, module scope with connected modules; Knowledge search page |
| AI layer | Provider interface with Claude (structured output, explicit effort, prompt caching, server-side refusal fallback), OpenAI and Ollama; versioned prompts; every call logged with tokens, latency and retrieved passages; one repair retry |
| Extraction | Requirements extracted from selected documents with citations; citations verified against the source text; uncited items discarded; duplicates merged within a run and flagged against existing requirements; open questions returned; idempotency key; atomic (no partial results) |
| Requirements | Stable `REQ-###` keys, immutable versions, edit → new draft version, approve/reject/bulk, diff, filters, soft delete |
| Safety | Uploaded text treated as data; no tools during analysis; AI can only create drafts; injection document in the eval set |
| Evals | Golden set (3 synthetic documents, 16 expected requirements, one injection case) with recall, citation-validity and forbidden-content checks; CI workflow that runs only with an API key |
| Ops | Worker survives database restarts; corrupt files fail fast; reprocess endpoint and button; Docker image with Tesseract and a baked embedding model; CI installs Tesseract and caches the model |

## Verification

- Backend: 85 tests (84 pass, the OCR test is skipped where Tesseract is not installed and runs in CI). New tests cover parsers on real PDF/DOCX/XLSX/PNG files, chunk offsets and page boundaries, the strict schema, grounding, indexing, hybrid search, isolation of search, version replacement, module scoping, reprocessing, requirement versioning and review, extraction with a scripted model (grounded drafts, discarded fabrications, duplicates, repair, atomic failure, retryable errors, idempotency, injection text not changing state). The OpenAPI-driven isolation suite covers all 10 new routes automatically.
- Frontend: lint, strict TypeScript and production build pass; 21 unit tests.
- End to end: 5 Playwright tests against the real API, worker, fastembed and pgvector, including knowledge search and the add → approve → edit → compare requirement flow.
- Not verified here: a real model run. No API key was available, so extraction against Claude/OpenAI/Ollama and the eval thresholds are untested until a key is configured.

## Fixed along the way

- The worker exited when the database restarted; it now waits and retries.
- The schema converter removed fields named `title` along with the JSON-Schema `title` keyword, which would have broken every model response. Caught by a unit test.
- On Windows a failed parser could keep a temp file open and mask the real error.

## Deviations

- Human corrections are made on requirements (new versions), not on raw chunks; reprocessing re-derives chunks from the file.
- The uploader chooses the document type; there is no AI classification step.
- Local development without admin rights uses a private copy of PostgreSQL with pgvector (`devdb.py make-private` / `install-pgvector`).
- Tesseract is optional locally; Docker and CI include it.

## Next: Phase 3

Figma analyzer, gap analysis, test case generator and bug report generator, built on the context engine and the approved requirements.
