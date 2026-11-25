"""RFC 9457 problem-details errors and their exception handlers."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.errors")


class AppError(Exception):
    """An expected error with a stable machine-readable code."""

    def __init__(
        self,
        status: int,
        code: str,
        detail: str,
        *,
        errors: list[dict[str, Any]] | None = None,
        extra: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.errors = errors or []
        self.extra = extra or {}
        self.headers = headers


def not_found(what: str = "Resource") -> AppError:
    return AppError(404, "not_found", f"{what} not found")


def forbidden(detail: str = "You do not have permission to do this") -> AppError:
    return AppError(403, "forbidden", detail)


def conflict(code: str, detail: str, **extra: Any) -> AppError:
    return AppError(409, code, detail, extra=extra)


_TITLES = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    412: "Precondition Failed",
    413: "Payload Too Large",
    415: "Unsupported Media Type",
    422: "Unprocessable Content",
    423: "Locked",
    428: "Precondition Required",
    429: "Too Many Requests",
    500: "Internal Server Error",
}


def _problem(request: Request, status: int, code: str, detail: str, **fields: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": f"https://errors.ai-qa-studio.dev/{code}",
        "title": _TITLES.get(status, "Error"),
        "status": status,
        "detail": detail,
        "code": code,
        "request_id": getattr(request.state, "request_id", None),
    }
    body.update({k: v for k, v in fields.items() if v})
    return body


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        body = _problem(request, exc.status, exc.code, exc.detail, errors=exc.errors, **exc.extra)
        return JSONResponse(body, status_code=exc.status, headers=exc.headers, media_type="application/problem+json")

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(p) for p in e["loc"] if p not in ("body", "query", "path")), "message": e["msg"]}
            for e in exc.errors()
        ]
        body = _problem(request, 422, "validation_error", "The request is invalid", errors=errors)
        return JSONResponse(body, status_code=422, media_type="application/problem+json")

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        body = _problem(request, exc.status_code, code, str(exc.detail))
        return JSONResponse(body, status_code=exc.status_code, media_type="application/problem+json")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", extra={"request_id": getattr(request.state, "request_id", None)})
        body = _problem(request, 500, "internal_error", "An unexpected error occurred")
        return JSONResponse(body, status_code=500, media_type="application/problem+json")
