import time
import uuid
from datetime import UTC, datetime

import pytest

from app.core.errors import AppError
from app.core.ids import uuid7
from app.core.pagination import clamp_limit, decode_cursor, encode_cursor
from app.core.ratelimit import RateLimiter
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    sign_file_token,
    verify_file_token,
    verify_password,
)
from app.services.filetypes import safe_filename


def test_uuid7_has_version_7_and_sorts_by_time() -> None:
    a = uuid7()
    time.sleep(0.002)
    b = uuid7()
    assert a.version == 7 and b.version == 7
    assert a.variant == uuid.RFC_4122
    assert str(a) < str(b)


def test_password_hashing() -> None:
    hashed = hash_password("a long passphrase")
    assert hashed.startswith("$argon2id$")
    assert verify_password("a long passphrase", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("anything", None)
    assert not verify_password("anything", "not-a-hash")


def test_access_token_round_trip_and_rejects_tampering() -> None:
    user_id = uuid7()
    token, expires_in = create_access_token(user_id)
    assert expires_in == 15 * 60
    assert decode_access_token(token) == user_id
    assert decode_access_token(token + "x") is None
    assert decode_access_token("not.a.jwt") is None


def test_file_token_is_bound_and_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    version, user = uuid7(), uuid7()
    token = sign_file_token(version, user)
    assert verify_file_token(token) == (version, user)
    forged = token.replace(str(user), str(uuid7()))
    assert verify_file_token(forged) is None
    assert verify_file_token("garbage") is None
    import app.core.security as security

    now = time.time()
    monkeypatch.setattr(security.time, "time", lambda: now + 10_000)
    assert verify_file_token(token) is None


def test_cursor_round_trip_and_invalid() -> None:
    ts, row = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC), uuid7()
    assert decode_cursor(encode_cursor(ts, row)) == (ts, row)
    with pytest.raises(AppError):
        decode_cursor("not-a-cursor!")
    assert clamp_limit(None) == 50
    assert clamp_limit(0) == 1
    assert clamp_limit(10_000) == 200


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\me\\spec.pdf", "spec.pdf"),
        ('bad<>:"|?*name.txt', "badname.txt"),
        ("...", "upload"),
        ("", "upload"),
    ],
)
def test_safe_filename(raw: str, expected: str) -> None:
    assert safe_filename(raw) == expected


def test_rate_limiter_window() -> None:
    limiter = RateLimiter()
    assert [limiter.hit("k", 2)[0] for _ in range(3)] == [True, True, False]
    assert limiter.hit("other", 2)[0] is True
    allowed, retry = limiter.hit("k", 2)
    assert not allowed and retry >= 1
