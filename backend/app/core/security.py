"""Password hashing, JWT access tokens, refresh tokens and signed download URLs."""

import hashlib
import hmac
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher()  # Argon2id with library defaults
# A real hash used to equalise timing when the account does not exist.
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-password")

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.access_token_minutes)
    payload = {"sub": str(user_id), "iat": now, "exp": expires, "typ": "access"}
    token = jwt.encode(payload, settings.effective_jwt_secret, algorithm=JWT_ALGORITHM)
    return token, settings.access_token_minutes * 60


def decode_access_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, get_settings().effective_jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "access":
        return None
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        return None


def new_refresh_token() -> tuple[str, str]:
    """Return (raw token for the cookie, sha256 hash for the database)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _sign(message: str) -> str:
    key = get_settings().effective_jwt_secret.encode()
    return hmac.new(key, message.encode(), hashlib.sha256).hexdigest()


def sign_file_token(version_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """A short-lived token authorising one user to download one document version."""
    expires = int(time.time()) + get_settings().signed_url_seconds
    message = f"{version_id}.{user_id}.{expires}"
    return f"{message}.{_sign(message)}"


def verify_file_token(token: str) -> tuple[uuid.UUID, uuid.UUID] | None:
    parts = token.split(".")
    if len(parts) != 4:
        return None
    version_id, user_id, expires, signature = parts
    message = f"{version_id}.{user_id}.{expires}"
    if not hmac.compare_digest(signature, _sign(message)):
        return None
    try:
        if int(expires) < int(time.time()):
            return None
        return uuid.UUID(version_id), uuid.UUID(user_id)
    except ValueError:
        return None
