"""Background jobs stored in PostgreSQL. The worker claims them with FOR UPDATE SKIP LOCKED."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.models import Job


def enqueue(
    db: Session, kind: str, *, project_id: uuid.UUID | None, created_by: uuid.UUID | None, payload: dict[str, Any]
) -> Job:
    job = Job(
        kind=kind,
        project_id=project_id,
        created_by=created_by,
        input=payload,
        status="queued",
        stage="Waiting for a worker",
    )
    db.add(job)
    db.flush()
    return job


def get_job(db: Session, job_id: uuid.UUID) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise not_found("Job")
    return job


def list_project_jobs(db: Session, project_id: uuid.UUID, limit: int = 20) -> list[Job]:
    return list(
        db.execute(
            select(Job).where(Job.project_id == project_id).order_by(Job.created_at.desc()).limit(limit)
        ).scalars()
    )


def cancel(db: Session, job: Job) -> Job:
    if job.status != "queued":
        raise AppError(409, "job_not_cancellable", f"Only queued jobs can be cancelled (this one is {job.status})")
    job.status = "cancelled"
    job.stage = "Cancelled"
    return job
