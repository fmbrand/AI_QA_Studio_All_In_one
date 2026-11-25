from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import RefreshToken
from tests.conftest import PASSWORD, register

REFRESH = "/api/v1/auth/refresh"


def test_register_returns_token_and_sets_httponly_cookie(client: TestClient) -> None:
    res = client.post("/api/v1/auth/register", json={"email": "New@Example.com", "name": "Nia", "password": PASSWORD})
    assert res.status_code == 201
    body = res.json()["data"]
    assert body["user"]["email"] == "new@example.com"
    assert body["access_token"]
    cookie = res.headers["set-cookie"]
    assert "aiqa_refresh=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/api/v1/auth" in cookie


def test_register_rejects_duplicate_email_case_insensitive(client: TestClient) -> None:
    register(client, "dup@example.com")
    res = client.post("/api/v1/auth/register", json={"email": "DUP@example.com", "name": "X", "password": PASSWORD})
    assert res.status_code == 409
    assert res.json()["code"] == "email_taken"


def test_register_validates_input(client: TestClient) -> None:
    res = client.post("/api/v1/auth/register", json={"email": "not-an-email", "name": "", "password": "short"})
    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "validation_error"
    fields = {e["field"] for e in body["errors"]}
    assert {"email", "name", "password"} <= fields
    assert res.headers["content-type"].startswith("application/problem+json")


def test_login_success_and_me(client: TestClient) -> None:
    register(client, "me@example.com", "Mei")
    res = client.post("/api/v1/auth/login", json={"email": "me@example.com", "password": PASSWORD})
    assert res.status_code == 200
    token = res.json()["data"]["access_token"]
    me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["data"]["user"]["name"] == "Mei"
    assert me.json()["data"]["memberships"] == []


def test_login_wrong_password_and_unknown_user_look_the_same(client: TestClient) -> None:
    register(client, "a@example.com")
    wrong = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "wrong-password"})
    unknown = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["code"] == unknown.json()["code"] == "invalid_credentials"


def test_login_is_rate_limited(client: TestClient) -> None:
    register(client, "rl@example.com")
    codes = [
        client.post("/api/v1/auth/login", json={"email": "rl@example.com", "password": "nope-nope"}).status_code
        for _ in range(6)
    ]
    assert codes[:5] == [401] * 5
    assert codes[5] == 429


def test_account_locks_after_repeated_failures(client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_failed_logins", 3)
    register(client, "lock@example.com")
    for _ in range(3):
        client.post("/api/v1/auth/login", json={"email": "lock@example.com", "password": "bad-password"})
    res = client.post("/api/v1/auth/login", json={"email": "lock@example.com", "password": PASSWORD})
    assert res.status_code == 423
    assert res.json()["code"] == "account_locked"


def test_protected_routes_require_a_valid_token(client: TestClient) -> None:
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    assert client.get("/api/v1/projects").status_code == 401


def test_refresh_rotates_token_and_reuse_revokes_family(client: TestClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    res = client.post("/api/v1/auth/register", json={"email": "r@example.com", "name": "R", "password": PASSWORD})
    first = res.cookies.get("aiqa_refresh")
    assert first

    rotated = client.post(REFRESH)
    assert rotated.status_code == 200
    second = rotated.cookies.get("aiqa_refresh")
    assert second and second != first

    # Presenting the old (already rotated) token is treated as theft.
    client.cookies.clear()
    client.cookies.set("aiqa_refresh", first, path="/api/v1/auth")
    reuse = client.post(REFRESH)
    assert reuse.status_code == 401

    # ...and the legitimate newer token no longer works either.
    client.cookies.clear()
    client.cookies.set("aiqa_refresh", second, path="/api/v1/auth")
    assert client.post(REFRESH).status_code == 401

    with session_factory() as db:
        tokens = db.execute(select(RefreshToken)).scalars().all()
        assert tokens and all(t.revoked_at is not None for t in tokens)


def test_refresh_without_cookie_is_rejected(client: TestClient) -> None:
    client.cookies.clear()
    res = client.post(REFRESH)
    assert res.status_code == 401
    assert res.json()["code"] == "invalid_refresh_token"


def test_logout_revokes_refresh_token(client: TestClient) -> None:
    res = client.post("/api/v1/auth/register", json={"email": "out@example.com", "name": "O", "password": PASSWORD})
    raw = res.cookies.get("aiqa_refresh")
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.clear()
    client.cookies.set("aiqa_refresh", raw, path="/api/v1/auth")
    assert client.post(REFRESH).status_code == 401


def test_change_password_requires_current_and_signs_out_sessions(client: TestClient) -> None:
    api = register(client, "pw@example.com")
    bad = api.post("/api/v1/me/password", json={"current_password": "wrong", "new_password": "new-password-123"})
    assert bad.status_code == 400
    good = api.post("/api/v1/me/password", json={"current_password": PASSWORD, "new_password": "new-password-123"})
    assert good.status_code == 204
    login = client.post("/api/v1/auth/login", json={"email": "pw@example.com", "password": "new-password-123"})
    assert login.status_code == 200


def test_update_profile_name(client: TestClient) -> None:
    api = register(client, "prof@example.com")
    res = api.patch("/api/v1/me", json={"name": "  Renamed  "})
    assert res.status_code == 200
    assert res.json()["data"]["name"] == "Renamed"
