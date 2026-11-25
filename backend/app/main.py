"""FastAPI application entry point."""

import uuid
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import activity, auth, documents, modules, projects
from app.core.config import get_settings
from app.core.context import request_id_var
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.database.session import get_engine


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    app = FastAPI(
        title="AI QA Studio API",
        version="0.1.0",
        description="Phase 1: authentication, projects, members, modules, documents, jobs and activity.",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if 0 < len(incoming) <= 64 and incoming.replace("-", "").isalnum() else uuid.uuid4().hex
        request.state.request_id = rid
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "If-Match", "X-Request-ID"],
        expose_headers=["ETag", "X-Request-ID", "Retry-After"],
    )

    api = APIRouter(prefix="/api/v1")

    @api.get("/health", tags=["system"])
    def health() -> dict:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"data": {"status": "ok", "database": "ok"}}

    for module in (auth, projects, modules, documents, activity):
        api.include_router(module.router)
    app.include_router(api)
    return app


app = create_app()
