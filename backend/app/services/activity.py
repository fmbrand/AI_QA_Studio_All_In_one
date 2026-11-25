"""Audit trail. Services call record() in the same transaction as the change they describe."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.context import request_id_var
from app.models import ActivityLog


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def record(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    summary: str,
    project_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    db.add(
        ActivityLog(
            project_id=project_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary[:300],
            before=_jsonable(before) if before is not None else None,
            after=_jsonable(after) if after is not None else None,
            request_id=request_id_var.get(),
        )
    )


def diff(before: dict[str, Any], after: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Keep only the fields that changed."""
    keys = [k for k in after if before.get(k) != after.get(k)]
    return {k: before.get(k) for k in keys}, {k: after[k] for k in keys}
