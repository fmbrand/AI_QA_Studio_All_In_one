"""Requirements: stable keys, immutable versions, review workflow, and AI extraction from documents."""

import difflib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from ai_engine.embeddings import cosine
from ai_engine.grounding import SourceChunk, ground
from ai_engine.llm.base import LLMRequest
from ai_engine.prompts import requirement_extraction as prompt
from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.core.pagination import page_meta, paginate
from app.models import DocumentVersion, Job, Module, Project, Requirement, RequirementVersion, UploadedDocument, User
from app.repositories.access import ProjectAccess
from app.schemas.requirements import RequirementCreateIn, RequirementUpdateIn
from app.services import activity, ai_runtime, jobs
from app.services.context import chunks_for_documents
from app.services.keys import next_key
from app.services.modules import get_module
from app.services.projects import ensure_active, require_version

EXTRACTION_JOB = "requirement_extraction"
DUPLICATE_THRESHOLD = 0.92
_VERSION_FIELDS = ("type", "title", "description", "module_id", "feature", "user_role", "priority",
                   "acceptance_criteria")  # fmt: skip


# ---- reading -----------------------------------------------------------------------------------


def _version_out(v: RequirementVersion) -> dict[str, Any]:
    return {c: getattr(v, c) for c in (
        "id", "version", "type", "title", "description", "module_id", "feature", "user_role", "priority",
        "acceptance_criteria", "source_refs", "origin", "confidence", "change_reason", "created_by", "created_at",
    )}  # fmt: skip


def _out(req: Requirement, current: RequirementVersion, approved_no: int | None, dup_key: str | None) -> dict[str, Any]:
    return {
        "id": req.id, "project_id": req.project_id, "key": req.key, "status": req.status,
        "current_version_no": req.current_version_no, "approved_version_no": approved_no,
        "possible_duplicate_of": req.possible_duplicate_of, "possible_duplicate_key": dup_key,
        "rejection_reason": req.rejection_reason, "reviewed_at": req.reviewed_at,
        "created_at": req.created_at, "updated_at": req.updated_at, "current": _version_out(current),
    }  # fmt: skip


def _base_query(project_id: uuid.UUID):  # type: ignore[no-untyped-def]
    approved = aliased(RequirementVersion)
    duplicate = aliased(Requirement)
    return (
        select(Requirement, RequirementVersion, approved.version, duplicate.key)
        .join(RequirementVersion, RequirementVersion.id == Requirement.current_version_id)
        .outerjoin(approved, approved.id == Requirement.approved_version_id)
        .outerjoin(duplicate, duplicate.id == Requirement.possible_duplicate_of)
        .where(Requirement.project_id == project_id, Requirement.deleted_at.is_(None))
    )


def list_requirements(
    db: Session, project_id: uuid.UUID, *, status: str | None, type_: str | None, priority: str | None,
    module_id: uuid.UUID | None, q: str | None, cursor: str | None, limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:  # fmt: skip
    stmt = _base_query(project_id)
    if status:
        stmt = stmt.where(Requirement.status == status)
    if type_:
        stmt = stmt.where(RequirementVersion.type == type_)
    if priority:
        stmt = stmt.where(RequirementVersion.priority == priority)
    if module_id:
        stmt = stmt.where(RequirementVersion.module_id == module_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Requirement.key.ilike(like), RequirementVersion.title.ilike(like),
                              RequirementVersion.description.ilike(like)))  # fmt: skip
    rows = db.execute(paginate(stmt, Requirement.created_at, Requirement.id, cursor, limit)).all()

    class _R:
        def __init__(self, row: Any) -> None:
            self.row, self.id, self.created_at = row, row[0].id, row[0].created_at

    wrapped, page = page_meta([_R(r) for r in rows], limit, cursor)
    return [_out(w.row[0], w.row[1], w.row[2], w.row[3]) for w in wrapped], page


def _get(db: Session, project_id: uuid.UUID, requirement_id: uuid.UUID) -> Requirement:
    req = db.execute(
        select(Requirement).where(Requirement.id == requirement_id, Requirement.project_id == project_id,
                                  Requirement.deleted_at.is_(None))
    ).scalar_one_or_none()  # fmt: skip
    if req is None:
        raise not_found("Requirement")
    return req


def _versions(db: Session, requirement_id: uuid.UUID) -> list[RequirementVersion]:
    return list(db.execute(
        select(RequirementVersion).where(RequirementVersion.requirement_id == requirement_id)
        .order_by(RequirementVersion.version.desc())
    ).scalars())  # fmt: skip


def detail(db: Session, project_id: uuid.UUID, requirement_id: uuid.UUID) -> dict[str, Any]:
    row = db.execute(_base_query(project_id).where(Requirement.id == requirement_id)).first()
    if row is None:
        raise not_found("Requirement")
    out = _out(row[0], row[1], row[2], row[3])
    out["versions"] = [_version_out(v) for v in _versions(db, requirement_id)]
    return out


def diff(db: Session, project_id: uuid.UUID, requirement_id: uuid.UUID, a: int, b: int) -> dict[str, Any]:
    _get(db, project_id, requirement_id)
    by_no = {v.version: v for v in _versions(db, requirement_id)}
    if a not in by_no or b not in by_no:
        raise AppError(404, "not_found", "Requirement version not found")
    va, vb = by_no[a], by_no[b]
    changes = [
        {"field": f, "before": getattr(va, f), "after": getattr(vb, f)}
        for f in (*_VERSION_FIELDS, "source_refs")
        if getattr(va, f) != getattr(vb, f)
    ]
    text_diff = list(difflib.unified_diff(
        va.description.splitlines(), vb.description.splitlines(), f"v{a}", f"v{b}", lineterm="", n=2,
    ))  # fmt: skip
    return {"from_version": a, "to_version": b, "changes": changes, "description_diff": text_diff}


# ---- writing -----------------------------------------------------------------------------------


def _check_module(db: Session, project_id: uuid.UUID, module_id: uuid.UUID | None) -> None:
    if module_id:
        get_module(db, project_id, module_id)


def create_manual(db: Session, access: ProjectAccess, user: User, data: RequirementCreateIn) -> Requirement:
    ensure_active(access)
    _check_module(db, access.project_id, data.module_id)
    req = _new_requirement(db, access.project_id, user.id)
    version = RequirementVersion(requirement_id=req.id, project_id=access.project_id, version=1,
                                 origin="manual", created_by=user.id, **data.model_dump())  # fmt: skip
    db.add(version)
    db.flush()
    req.current_version_id = version.id
    activity.record(
        db,
        project_id=access.project_id,
        actor_id=user.id,
        action="requirement.created",
        entity_type="requirement",
        entity_id=req.id,
        summary=f"Added {req.key}: {data.title[:200]}",
    )
    return req


def _new_requirement(db: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> Requirement:
    req = Requirement(project_id=project_id, key=next_key(db, project_id, "requirement"), status="draft",
                      current_version_no=1, created_by=user_id)  # fmt: skip
    db.add(req)
    db.flush()
    return req


def update(db: Session, access: ProjectAccess, user: User, requirement_id: uuid.UUID, data: RequirementUpdateIn,
           if_match: str | None) -> Requirement:  # fmt: skip
    """Edits never overwrite: they add a version. Editing an approved requirement returns it to draft."""
    ensure_active(access)
    req = _get(db, access.project_id, requirement_id)
    require_version(req.current_version_no, if_match)
    current = db.get(RequirementVersion, req.current_version_id)
    assert current is not None
    values = {f: getattr(current, f) for f in _VERSION_FIELDS}
    changes = data.model_dump(exclude_unset=True, exclude={"change_reason", "clear_module"})
    for key, value in changes.items():
        if value is None and key in ("type", "title", "priority", "acceptance_criteria", "description"):
            continue
        values[key] = value.strip() if isinstance(value, str) and key == "title" else value
    if data.clear_module:
        values["module_id"] = None
    if not values["title"]:
        raise AppError(422, "validation_error", "Title must not be blank")
    _check_module(db, access.project_id, values["module_id"])
    before = {f: getattr(current, f) for f in _VERSION_FIELDS}
    b, a = activity.diff(before, values)
    if not a:
        raise AppError(409, "no_change", "Nothing changed")
    new_no = req.current_version_no + 1
    version = RequirementVersion(requirement_id=req.id, project_id=access.project_id, version=new_no,
                                 origin="edit", source_refs=current.source_refs, confidence=current.confidence,
                                 change_reason=data.change_reason, created_by=user.id, **values)  # fmt: skip
    db.add(version)
    db.flush()
    previous_status = req.status
    req.current_version_id, req.current_version_no = version.id, new_no
    req.status = "draft"
    req.rejection_reason = None
    activity.record(db, project_id=access.project_id, actor_id=user.id, action="requirement.updated",
                    entity_type="requirement", entity_id=req.id,
                    summary=f"Edited {req.key} (v{new_no})"
                    + (" — needs re-approval" if previous_status == "approved" else ""),
                    before=b, after=a)  # fmt: skip
    return req


def set_status(db: Session, access: ProjectAccess, user: User, requirement_id: uuid.UUID, status: str,
               reason: str | None = None) -> Requirement:  # fmt: skip
    ensure_active(access)
    req = _get(db, access.project_id, requirement_id)
    if req.status == status:
        raise AppError(409, "no_change", f"{req.key} is already {status}")
    previous = req.status
    req.status = status
    req.reviewed_by, req.reviewed_at = user.id, datetime.now(UTC)
    if status == "approved":
        req.approved_version_id = req.current_version_id
        req.rejection_reason = None
    else:
        req.rejection_reason = reason
    activity.record(db, project_id=access.project_id, actor_id=user.id, action=f"requirement.{status}",
                    entity_type="requirement", entity_id=req.id,
                    summary=f"{'Approved' if status == 'approved' else 'Rejected'} {req.key} v{req.current_version_no}",
                    before={"status": previous}, after={"status": status, "reason": reason})  # fmt: skip
    return req


def bulk_status(db: Session, access: ProjectAccess, user: User, ids: list[uuid.UUID], status: str,
                reason: str | None) -> dict[str, Any]:  # fmt: skip
    changed, skipped = [], []
    for rid in dict.fromkeys(ids):
        req = db.execute(select(Requirement).where(Requirement.id == rid, Requirement.project_id == access.project_id,
                                                   Requirement.deleted_at.is_(None))).scalar_one_or_none()  # fmt: skip
        if req is None or req.status == status:
            skipped.append(str(rid))
            continue
        set_status(db, access, user, rid, status, reason)
        changed.append(str(rid))
    return {"changed": changed, "skipped": skipped}


def delete(db: Session, access: ProjectAccess, user: User, requirement_id: uuid.UUID) -> None:
    ensure_active(access)
    req = _get(db, access.project_id, requirement_id)
    req.deleted_at = datetime.now(UTC)
    activity.record(
        db,
        project_id=access.project_id,
        actor_id=user.id,
        action="requirement.deleted",
        entity_type="requirement",
        entity_id=req.id,
        summary=f"Deleted {req.key}",
    )


# ---- AI extraction -----------------------------------------------------------------------------


def start_extraction(db: Session, access: ProjectAccess, user: User, document_ids: list[uuid.UUID],
                     instructions: str | None, idempotency_key: str | None) -> Job:  # fmt: skip
    ensure_active(access)
    if not ai_runtime.llm_configured():
        raise ai_runtime.not_configured()
    if idempotency_key:
        existing = db.execute(
            select(Job).where(Job.project_id == access.project_id, Job.kind == EXTRACTION_JOB,
                              Job.created_by == user.id, Job.input["idempotency_key"].astext == idempotency_key)
        ).scalars().first()  # fmt: skip
        if existing:
            return existing
    ids = list(dict.fromkeys(document_ids))
    docs = db.execute(
        select(UploadedDocument, DocumentVersion.processing_status)
        .join(DocumentVersion, DocumentVersion.id == UploadedDocument.current_version_id)
        .where(UploadedDocument.id.in_(ids), UploadedDocument.project_id == access.project_id,
               UploadedDocument.deleted_at.is_(None))
    ).all()  # fmt: skip
    if len(docs) != len(ids):
        raise AppError(404, "not_found", "One or more documents were not found in this project")
    not_ready = [d.title for d, state in docs if state != "processed"]
    if not_ready:
        raise AppError(409, "documents_not_indexed",
                       "These documents have no indexed text yet: " + ", ".join(not_ready[:5]),
                       extra={"documents": not_ready})  # fmt: skip
    job = jobs.enqueue(db, EXTRACTION_JOB, project_id=access.project_id, created_by=user.id,
                       payload={"document_ids": [str(i) for i in ids], "instructions": instructions,
                                "idempotency_key": idempotency_key})  # fmt: skip
    activity.record(
        db,
        project_id=access.project_id,
        actor_id=user.id,
        action="requirement.extraction_started",
        entity_type="job",
        entity_id=job.id,
        summary=f"Started requirement extraction from {len(ids)} document(s)",
    )
    return job


def _windows(rows: list[Any], max_chars: int) -> list[list[Any]]:
    windows: list[list[Any]] = [[]]
    size = 0
    for row in rows:
        length = len(row[0].content)
        if windows[-1] and size + length > max_chars:
            windows.append([])
            size = 0
        windows[-1].append(row)
        size += length
    return [w for w in windows if w]


def run_extraction(db: Session, job: Job, report: Any) -> dict[str, Any]:
    """Worker side. All model calls happen first; requirements are written only if every call succeeds,
    so a failed run leaves no partial results."""
    settings = get_settings()
    project = db.get(Project, job.project_id)
    if project is None or project.deleted_at is not None:
        raise AppError(404, "not_found", "Project not found")
    document_ids = [uuid.UUID(i) for i in job.input["document_ids"]]
    rows = chunks_for_documents(db, project.id, document_ids)
    if not rows:
        raise AppError(409, "documents_not_indexed", "The selected documents have no indexed text")

    modules = list(db.execute(select(Module).where(Module.project_id == project.id)).scalars())
    module_by_name = {m.name.lower(): m.id for m in modules}
    existing = db.execute(
        _base_query(project.id).with_only_columns(Requirement.id, Requirement.key, RequirementVersion.title,
                                                  RequirementVersion.description).limit(2000)
    ).all()  # fmt: skip
    pv = ai_runtime.prompt_version_id(db, prompt.TASK, prompt.VERSION, prompt.TEMPLATE_HASH)
    project_info = {"name": project.name, "platform": project.platform, "domain": project.business_domain,
                    "type": project.project_type, "description": project.description[:2000]}  # fmt: skip

    windows = _windows(rows, settings.extraction_window_chars)
    grounded, open_questions, generation_ids = [], [], []
    dropped_citations = discarded = 0
    for number, window in enumerate(windows, start=1):
        report(f"Reading sources ({number} of {len(windows)})", 10 + int(70 * (number - 1) / len(windows)))
        chunk_map: dict[str, SourceChunk] = {}
        blocks = []
        for index, row in enumerate(window, start=1):
            chunk, title = row[0], row[1]
            sid = f"S{index}"
            chunk_map[sid] = SourceChunk(sid, str(chunk.id), str(chunk.document_id), str(chunk.document_version_id),
                                         title, chunk.page, chunk.sheet, chunk.char_start, chunk.content)  # fmt: skip
            blocks.append(prompt.SourceBlock(sid, title, chunk.page, chunk.sheet, chunk.content))
        request = LLMRequest(
            system=prompt.SYSTEM,
            user=prompt.render_user(project=project_info, modules=[m.name for m in modules],
                                    existing_titles=[f"{r[1]}: {r[2]}" for r in existing][:300],
                                    instructions=job.input.get("instructions"), sources=blocks),
            schema=prompt.SCHEMA, schema_name="requirement_extraction",
            max_output_tokens=settings.llm_max_output_tokens,
        )  # fmt: skip
        output, generation_id = ai_runtime.run_structured(
            db, output_model=prompt.ExtractionOutput, request=request, task=prompt.TASK, prompt_version=pv,
            project_id=project.id, job_id=job.id, retrieved_chunk_ids=[c.chunk_id for c in chunk_map.values()],
        )  # fmt: skip
        generation_ids.append(generation_id)
        result = ground(output.requirements, chunk_map)
        dropped_citations += result.dropped_citations
        discarded += result.discarded_uncited
        grounded.extend((g, generation_id) for g in result.kept)
        open_questions.extend(q.strip() for q in output.open_questions if q.strip())

    report("Checking for duplicates", 85)
    embedder = ai_runtime.get_embedder()
    new_vectors = embedder.embed([f"{g.item.title}. {g.item.description}" for g, _ in grounded]) if grounded else []
    old_vectors = embedder.embed([f"{r[2]}. {r[3]}" for r in existing]) if existing and grounded else []
    kept: list[tuple[Any, Any, list[float], uuid.UUID | None]] = []
    merged_in_run = flagged = 0
    for (g, gen_id), vector in zip(grounded, new_vectors, strict=True):
        if any(cosine(vector, k[2]) >= DUPLICATE_THRESHOLD for k in kept):
            merged_in_run += 1  # overlapping windows found the same requirement twice
            continue
        duplicate_of = None
        if old_vectors:
            best = max(range(len(old_vectors)), key=lambda i: cosine(vector, old_vectors[i]))
            if cosine(vector, old_vectors[best]) >= DUPLICATE_THRESHOLD:
                duplicate_of = existing[best][0]
                flagged += 1
        kept.append((g, gen_id, vector, duplicate_of))

    report("Saving draft requirements", 92)
    created_keys = []
    for g, gen_id, _vector, duplicate_of in kept:
        item = g.item
        req = _new_requirement(db, project.id, job.created_by)
        req.possible_duplicate_of = duplicate_of
        version = RequirementVersion(
            requirement_id=req.id, project_id=project.id, version=1, type=item.type, title=item.title.strip()[:300],
            description=item.description.strip()[:10000], module_id=module_by_name.get((item.module or "").lower()),
            feature=(item.feature or None) and item.feature[:200],
            user_role=(item.user_role or None) and item.user_role[:120],
            priority=item.priority, acceptance_criteria=[c.strip() for c in item.acceptance_criteria if c.strip()][:50],
            source_refs=g.source_refs, origin="ai", confidence=item.confidence, ai_generation_id=gen_id,
            created_by=job.created_by,
        )  # fmt: skip
        db.add(version)
        db.flush()
        req.current_version_id = version.id
        created_keys.append(req.key)
    unique_questions = list(dict.fromkeys(open_questions))[:50]
    activity.record(db, project_id=project.id, actor_id=job.created_by, action="requirement.extracted",
                    entity_type="job", entity_id=job.id,
                    summary=f"AI extracted {len(created_keys)} draft requirement(s) for review",
                    after={"created": created_keys[:100]})  # fmt: skip
    return {
        "created": len(created_keys), "keys": created_keys, "discarded_uncited": discarded,
        "dropped_citations": dropped_citations, "merged_duplicates": merged_in_run,
        "possible_duplicates": flagged, "open_questions": unique_questions,
        "model_calls": len(generation_ids), "windows": len(windows),
    }  # fmt: skip


def counts(db: Session, project_ids: Any) -> dict[str, int]:
    rows = db.execute(
        select(Requirement.status, func.count()).where(Requirement.project_id.in_(project_ids),
                                                       Requirement.deleted_at.is_(None)).group_by(Requirement.status)
    ).all()  # fmt: skip
    by = dict(rows)
    return {"total": sum(by.values()), "approved": by.get("approved", 0), "draft": by.get("draft", 0),
            "rejected": by.get("rejected", 0)}  # fmt: skip
