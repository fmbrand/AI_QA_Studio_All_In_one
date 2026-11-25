"""Per-request context shared with services (request id for logs and the audit trail)."""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
