"""Job runner: claims queued jobs from PostgreSQL and dispatches them to handlers.

Several workers can run at once: claiming uses FOR UPDATE SKIP LOCKED, so a job is taken by one
worker only. Jobs left 'running' by a crashed worker are re-queued after JOB_STALE_MINUTES, up to
JOB_MAX_ATTEMPTS attempts.

Handlers receive (db, job, report). `report(stage, progress)` writes progress through its own short
session, so the UI sees it immediately without committing the handler's unfinished work.
"""

import logging
import traceback
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text, update
from sqlalchemy.orm import Session, sessionmaker

from ai_engine.llm.base import LLMError
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Job

log = logging.getLogger("app.worker")

Report = Callable[[str, int], None]
Handler = Callable[[Session, Job, Report], dict[str, Any]]
HANDLERS: dict[str, Handler] = {}


class JobError(Exception):
    """Raise from a handler to fail the job with a user-facing message (no retry)."""


def handler(kind: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        HANDLERS[kind] = fn
        return fn

    return register


def _now() -> datetime:
    return datetime.now(UTC)


def recover_stale(db: Session) -> int:
    settings = get_settings()
    cutoff = _now() - timedelta(minutes=settings.job_stale_minutes)
    failed = db.execute(
        update(Job)
        .where(Job.status == "running", Job.locked_at < cutoff, Job.attempts >= settings.job_max_attempts)
        .values(status="failed", error="The job stopped responding too many times", finished_at=_now())
    ).rowcount
    requeued = db.execute(
        update(Job)
        .where(Job.status == "running", Job.locked_at < cutoff)
        .values(status="queued", stage="Re-queued after a worker stopped", locked_at=None)
    ).rowcount
    db.commit()
    return (failed or 0) + (requeued or 0)


def claim(db: Session) -> uuid.UUID | None:
    row = db.execute(
        text(
            """
        UPDATE jobs SET status = 'running', locked_at = now(), attempts = attempts + 1,
               started_at = COALESCE(started_at, now()), stage = 'Starting', updated_at = now()
        WHERE id = (
            SELECT id FROM jobs WHERE status = 'queued'
            ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
        )
        RETURNING id
        """
        )
    ).first()
    db.commit()
    return row[0] if row else None


def _reporter(session_factory: sessionmaker[Session], job_id: uuid.UUID) -> Report:
    def report(stage: str, progress: int) -> None:
        with session_factory() as s:
            s.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(stage=stage[:120], progress=max(0, min(99, progress)), locked_at=_now())
            )
            s.commit()

    return report


def _classify(exc: BaseException) -> tuple[bool, str]:
    """(retryable, message) for a handler failure."""
    if isinstance(exc, JobError):
        return False, str(exc)
    if isinstance(exc, AppError):
        return False, exc.detail
    if isinstance(exc, LLMError):
        return exc.retryable, str(exc)
    return True, f"{type(exc).__name__}: {exc}"


def run_job(session_factory: sessionmaker[Session], job_id: uuid.UUID) -> None:
    with session_factory() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        fn = HANDLERS.get(job.kind)
        try:
            if fn is None:
                raise JobError(f"No handler for job kind '{job.kind}'")
            result = fn(db, job, _reporter(session_factory, job_id))
            job = db.get(Job, job_id)
            assert job is not None
            db.refresh(job)
            job.status, job.progress, job.stage = "succeeded", 100, "Done"
            job.result, job.error, job.finished_at = result, None, _now()
            db.commit()
        except Exception as exc:
            db.rollback()
            job = db.get(Job, job_id)
            assert job is not None
            db.refresh(job)
            retryable, message = _classify(exc)
            retry = retryable and job.attempts < get_settings().job_max_attempts
            if retry:
                job.status, job.stage, job.locked_at = "queued", "Retrying after an error", None
            else:
                job.status, job.stage, job.finished_at = "failed", "Failed", _now()
            job.error = message
            on_fail = getattr(fn, "on_failure", None)
            if on_fail and not retry:
                on_fail(db, job)
            db.commit()
            log.warning("job %s (%s) failed: %s", job_id, job.kind, job.error)
            log.debug("".join(traceback.format_exception(exc)))


def run_pending(session_factory: sessionmaker[Session], max_jobs: int = 100) -> int:
    """Process queued jobs until none are left (or max_jobs). Returns the number processed."""
    import app.worker.handlers  # noqa: F401  (registers handlers)

    done = 0
    while done < max_jobs:
        with session_factory() as db:
            job_id = claim(db)
        if job_id is None:
            break
        run_job(session_factory, job_id)
        done += 1
    return done
