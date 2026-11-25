"""Registration, login with lockout, and rotating refresh tokens with reuse detection."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ids import uuid7
from app.core.security import hash_password, hash_token, new_refresh_token, verify_password
from app.models import Project, ProjectMember, RefreshToken, Role, User
from app.services import activity


def _now() -> datetime:
    return datetime.now(UTC)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def find_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(func.lower(User.email) == normalize_email(email))).scalar_one_or_none()


def register(db: Session, email: str, name: str, password: str) -> User:
    if find_user_by_email(db, email):
        raise AppError(409, "email_taken", "An account with this email already exists")
    user = User(email=normalize_email(email), name=name, password_hash=hash_password(password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:  # concurrent registration with the same email
        db.rollback()
        raise AppError(409, "email_taken", "An account with this email already exists") from exc
    activity.record(
        db,
        actor_id=user.id,
        action="user.registered",
        entity_type="user",
        entity_id=user.id,
        summary=f"{user.email} registered",
    )
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    settings = get_settings()
    user = find_user_by_email(db, email)
    now = _now()
    if user and user.locked_until and user.locked_until > now:
        raise AppError(
            423,
            "account_locked",
            "Too many failed sign-in attempts. Try again later.",
            extra={"locked_until": user.locked_until.isoformat()},
        )
    if not verify_password(password, user.password_hash if user else None) or not user:
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.max_failed_logins:
                user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
                user.failed_login_count = 0
                activity.record(
                    db,
                    actor_id=user.id,
                    action="user.locked",
                    entity_type="user",
                    entity_id=user.id,
                    summary=f"{user.email} locked after failed sign-ins",
                )
            db.commit()
        raise AppError(401, "invalid_credentials", "Email or password is incorrect")
    if not user.is_active:
        raise AppError(401, "invalid_credentials", "Email or password is incorrect")
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    return user


def issue_refresh_token(
    db: Session, user_id: uuid.UUID, family_id: uuid.UUID | None = None, user_agent: str | None = None
) -> tuple[str, RefreshToken]:
    raw, digest = new_refresh_token()
    token = RefreshToken(
        id=uuid7(),
        user_id=user_id,
        family_id=family_id or uuid7(),
        token_hash=digest,
        expires_at=_now() + timedelta(days=get_settings().refresh_token_days),
        user_agent=(user_agent or "")[:300] or None,
    )
    db.add(token)
    return raw, token


def rotate_refresh_token(db: Session, raw: str, user_agent: str | None) -> tuple[User, str]:
    """Exchange a refresh token for a new one. Presenting a used token revokes its whole family."""
    invalid = AppError(401, "invalid_refresh_token", "Your session has expired. Please sign in again.")
    token = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)).with_for_update()
    ).scalar_one_or_none()
    if token is None:
        raise invalid
    now = _now()
    if token.revoked_at is not None:
        # Reuse of a rotated token: assume theft and end every session in this family.
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == token.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        activity.record(
            db,
            actor_id=token.user_id,
            action="auth.refresh_reuse",
            entity_type="user",
            entity_id=token.user_id,
            summary="Refresh token reuse detected; sessions revoked",
        )
        db.commit()
        raise invalid
    if token.expires_at <= now:
        raise invalid
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise invalid
    new_raw, new_token = issue_refresh_token(db, user.id, token.family_id, user_agent)
    token.revoked_at = now
    token.replaced_by_id = new_token.id
    return user, new_raw


def revoke_refresh_token(db: Session, raw: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw), RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def revoke_all_for_user(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.password_hash):
        raise AppError(400, "invalid_current_password", "The current password is incorrect")
    user.password_hash = hash_password(new)
    revoke_all_for_user(db, user.id)
    activity.record(
        db,
        actor_id=user.id,
        action="user.password_changed",
        entity_type="user",
        entity_id=user.id,
        summary="Password changed; other sessions signed out",
    )


def memberships(db: Session, user_id: uuid.UUID) -> list[dict[str, object]]:
    rows = db.execute(
        select(Project.id, Project.name, Project.status, Role.key)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .join(Role, Role.id == ProjectMember.role_id)
        .where(ProjectMember.user_id == user_id, Project.deleted_at.is_(None))
        .order_by(Project.name)
    ).all()
    return [{"project_id": r[0], "project_name": r[1], "project_status": r[2], "role": r[3]} for r in rows]
