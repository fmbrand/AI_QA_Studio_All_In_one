"""Keyset (cursor) pagination over (created_at DESC, id DESC)."""

import base64
import json
import uuid
from datetime import datetime
from typing import Any, TypeVar

from sqlalchemy import Select, and_, or_
from sqlalchemy.orm import InstrumentedAttribute

from app.core.errors import AppError

T = TypeVar("T")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    raw = json.dumps({"c": created_at.isoformat(), "i": str(row_id)})
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        return datetime.fromisoformat(data["c"]), uuid.UUID(data["i"])
    except (ValueError, KeyError, TypeError) as exc:
        raise AppError(400, "invalid_cursor", "The pagination cursor is invalid") from exc


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, limit))


def paginate(
    stmt: Select[Any],
    created_col: InstrumentedAttribute[datetime],
    id_col: InstrumentedAttribute[uuid.UUID],
    cursor: str | None,
    limit: int,
) -> Select[Any]:
    if cursor:
        created_at, row_id = decode_cursor(cursor)
        stmt = stmt.where(or_(created_col < created_at, and_(created_col == created_at, id_col < row_id)))
    return stmt.order_by(created_col.desc(), id_col.desc()).limit(limit + 1)


def page_meta(rows: list[Any], limit: int, cursor: str | None) -> tuple[list[Any], dict[str, Any]]:
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    return rows, {"cursor": cursor, "next_cursor": next_cursor, "limit": limit}
