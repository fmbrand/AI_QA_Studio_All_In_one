import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DB, CurrentUser, Viewer
from app.core.errors import AppError
from app.core.pagination import clamp_limit, page_meta, paginate
from app.models import ActivityLog, Job, Module, Project, UploadedDocument, User
from app.models.project import ROLE_RANK
from app.repositories.access import get_project_access, member_project_ids
from app.schemas.common import Envelope, ok
from app.schemas.documents import ActivityOut, DashboardOut, JobOut
from app.services import jobs as job_svc
from app.services.requirements import counts as requirement_counts

router = APIRouter(tags=["activity"])


def _with_actor_names(db: Session, logs: list[ActivityLog]) -> list[dict[str, Any]]:
    ids = {log.actor_id for log in logs if log.actor_id}
    names = dict(db.execute(select(User.id, User.name).where(User.id.in_(ids))).all()) if ids else {}
    return [{**ActivityOut.model_validate(log).model_dump(), "actor_name": names.get(log.actor_id)} for log in logs]


@router.get("/projects/{project_id}/activity", response_model=Envelope[list[ActivityOut]])
def project_activity(
    access: Viewer, db: DB, cursor: str | None = None, limit: Annotated[int | None, Query(ge=1, le=200)] = None
) -> dict:
    lim = clamp_limit(limit)
    stmt = select(ActivityLog).where(ActivityLog.project_id == access.project_id)
    logs = list(db.execute(paginate(stmt, ActivityLog.created_at, ActivityLog.id, cursor, lim)).scalars())
    logs, page = page_meta(logs, lim, cursor)
    return ok(_with_actor_names(db, logs), page)


@router.get("/projects/{project_id}/jobs", response_model=Envelope[list[JobOut]])
def project_jobs(access: Viewer, db: DB) -> dict:
    return ok(job_svc.list_project_jobs(db, access.project_id))


def _job_for_user(db: Session, job_id: uuid.UUID, user: User, min_role: str = "viewer") -> Job:
    job = job_svc.get_job(db, job_id)
    if job.project_id is None:
        if job.created_by != user.id:
            raise AppError(404, "not_found", "Job not found")
        return job
    access = get_project_access(db, job.project_id, user.id)
    if access is None:
        raise AppError(404, "not_found", "Job not found")
    if access.rank < ROLE_RANK[min_role]:
        raise AppError(403, "forbidden", "You cannot change this job")
    return job


@router.get("/jobs/{job_id}", response_model=Envelope[JobOut])
def get_job(job_id: uuid.UUID, user: CurrentUser, db: DB) -> dict:
    return ok(_job_for_user(db, job_id, user))


@router.post("/jobs/{job_id}/cancel", response_model=Envelope[JobOut])
def cancel_job(job_id: uuid.UUID, user: CurrentUser, db: DB) -> dict:
    job = job_svc.cancel(db, _job_for_user(db, job_id, user, "qa_engineer"))
    db.commit()
    return ok(job)


@router.get("/dashboard", response_model=Envelope[DashboardOut])
def dashboard(user: CurrentUser, db: DB) -> dict:
    """Cross-project totals for the caller, computed from stored data only."""
    mine = member_project_ids(user.id)
    status_counts = dict(
        db.execute(select(Project.status, func.count()).where(Project.id.in_(mine)).group_by(Project.status)).all()
    )
    documents = db.execute(
        select(func.count())
        .select_from(UploadedDocument)
        .where(UploadedDocument.project_id.in_(mine), UploadedDocument.deleted_at.is_(None))
    ).scalar_one()
    modules = db.execute(select(func.count()).select_from(Module).where(Module.project_id.in_(mine))).scalar_one()
    logs = list(
        db.execute(
            select(ActivityLog)
            .where(ActivityLog.project_id.in_(mine))
            .order_by(ActivityLog.created_at.desc())
            .limit(10)
        ).scalars()
    )
    recent_jobs = list(
        db.execute(select(Job).where(Job.project_id.in_(mine)).order_by(Job.created_at.desc()).limit(10)).scalars()
    )
    active, archived = status_counts.get("active", 0), status_counts.get("archived", 0)
    reqs = requirement_counts(db, mine)
    return ok(
        {
            "totals": {
                "projects": active + archived,
                "active_projects": active,
                "archived_projects": archived,
                "documents": documents,
                "modules": modules,
                "requirements": reqs["total"],
                "approved_requirements": reqs["approved"],
            },
            "recent_activity": _with_actor_names(db, logs),
            "recent_jobs": recent_jobs,
        }
    )
