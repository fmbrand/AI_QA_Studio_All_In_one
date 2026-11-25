"""Human-readable, per-project, never-reused keys (REQ-001, REQ-002, ...)."""

import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import KeyCounter

PREFIXES = {"requirement": "REQ-"}


def next_key(db: Session, project_id: uuid.UUID, scope: str) -> str:
    stmt = (
        insert(KeyCounter)
        .values(project_id=project_id, scope=scope, value=1)
        .on_conflict_do_update(index_elements=["project_id", "scope"], set_={"value": KeyCounter.value + 1})
        .returning(KeyCounter.value)
    )
    value = db.execute(stmt).scalar_one()
    return f"{PREFIXES[scope]}{value:03d}"
