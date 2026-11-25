from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response, status

from app.api.deps import DB, CurrentUser
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ratelimit import login_limiter
from app.core.security import create_access_token
from app.schemas.auth import (
    LoginIn,
    MeOut,
    PasswordChangeIn,
    ProfileUpdateIn,
    RegisterIn,
    TokenOut,
    UserOut,
)
from app.schemas.common import Envelope, ok
from app.services import activity
from app.services import auth as auth_service

router = APIRouter(tags=["auth"])

COOKIE = "aiqa_refresh"
COOKIE_PATH = "/api/v1/auth"


def _set_cookie(response: Response, raw: str) -> None:
    settings = get_settings()
    response.set_cookie(
        COOKIE,
        raw,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )


def _clear_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(COOKIE, path=COOKIE_PATH, httponly=True, secure=settings.cookie_secure, samesite="strict")


def _token_payload(user) -> dict:  # type: ignore[no-untyped-def]
    token, expires_in = create_access_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": UserOut.model_validate(user),
    }


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/auth/register", response_model=Envelope[TokenOut], status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, request: Request, response: Response, db: DB) -> dict:
    allowed, retry = login_limiter.hit(f"register:{_client_ip(request)}", 10)
    if not allowed:
        raise AppError(
            429, "rate_limited", "Too many attempts. Wait a minute and try again.", headers={"Retry-After": str(retry)}
        )
    user = auth_service.register(db, body.email, body.name, body.password)
    raw, _ = auth_service.issue_refresh_token(db, user.id, user_agent=request.headers.get("user-agent"))
    db.commit()
    _set_cookie(response, raw)
    return ok(_token_payload(user))


@router.post("/auth/login", response_model=Envelope[TokenOut])
def login(body: LoginIn, request: Request, response: Response, db: DB) -> dict:
    limit = get_settings().login_rate_limit_per_minute
    for key in (f"login-ip:{_client_ip(request)}", f"login-email:{body.email.lower()}"):
        allowed, retry = login_limiter.hit(key, limit)
        if not allowed:
            raise AppError(
                429,
                "rate_limited",
                "Too many sign-in attempts. Wait a minute and try again.",
                headers={"Retry-After": str(retry)},
            )
    user = auth_service.authenticate(db, body.email, body.password)
    raw, _ = auth_service.issue_refresh_token(db, user.id, user_agent=request.headers.get("user-agent"))
    activity.record(
        db,
        actor_id=user.id,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        summary=f"{user.email} signed in",
    )
    db.commit()
    _set_cookie(response, raw)
    return ok(_token_payload(user))


@router.post("/auth/refresh", response_model=Envelope[TokenOut])
def refresh(request: Request, response: Response, db: DB, aiqa_refresh: Annotated[str | None, Cookie()] = None) -> dict:
    if not aiqa_refresh:
        raise AppError(401, "invalid_refresh_token", "Your session has expired. Please sign in again.")
    try:
        user, raw = auth_service.rotate_refresh_token(db, aiqa_refresh, request.headers.get("user-agent"))
    except AppError:
        _clear_cookie(response)
        raise
    db.commit()
    _set_cookie(response, raw)
    return ok(_token_payload(user))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, db: DB, aiqa_refresh: Annotated[str | None, Cookie()] = None) -> Response:
    if aiqa_refresh:
        auth_service.revoke_refresh_token(db, aiqa_refresh)
        db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_cookie(response)
    return response


@router.get("/me", response_model=Envelope[MeOut])
def me(user: CurrentUser, db: DB) -> dict:
    return ok({"user": UserOut.model_validate(user), "memberships": auth_service.memberships(db, user.id)})


@router.patch("/me", response_model=Envelope[UserOut])
def update_me(body: ProfileUpdateIn, user: CurrentUser, db: DB) -> dict:
    before = user.name
    user.name = body.name
    if before != body.name:
        activity.record(
            db,
            actor_id=user.id,
            action="user.updated",
            entity_type="user",
            entity_id=user.id,
            summary="Updated profile name",
            before={"name": before},
            after={"name": body.name},
        )
    db.commit()
    return ok(UserOut.model_validate(user))


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChangeIn, user: CurrentUser, db: DB) -> Response:
    auth_service.change_password(db, user, body.current_password, body.new_password)
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_cookie(response)
    return response
