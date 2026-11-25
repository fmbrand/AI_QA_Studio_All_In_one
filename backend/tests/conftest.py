"""Test fixtures. Tests run against a real PostgreSQL database (TEST_DATABASE_URL), migrated with Alembic,
and truncated between tests."""

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:5434/ai_qa_studio_test"
)
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-hs256-signing")
os.environ.setdefault("MAX_UPLOAD_MB", "1")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.ratelimit import login_limiter  # noqa: E402
from app.database.session import get_engine, get_session_factory  # noqa: E402
from app.integrations.storage import LocalStorage, set_storage  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "app/database/migrations"))
    cfg.attributes["database_url"] = get_settings().database_url
    command.upgrade(cfg, "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_state(tmp_path: Path) -> Iterator[Path]:
    with get_engine().begin() as conn:
        tables = (
            conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                    "AND tablename NOT IN ('roles', 'alembic_version')"
                )
            )
            .scalars()
            .all()
        )
        conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    login_limiter.reset()
    storage_dir = tmp_path / "storage"
    set_storage(LocalStorage(storage_dir))
    yield storage_dir
    set_storage(None)


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def session_factory():  # type: ignore[no-untyped-def]
    return get_session_factory()


# ---- helpers ----------------------------------------------------------------------------------


class Api:
    """Small helper around TestClient that keeps a user's bearer token."""

    def __init__(self, client: TestClient, token: str, user: dict[str, Any]) -> None:
        self.client, self.token, self.user = client, token, user

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, url: str, **kw: Any):  # type: ignore[no-untyped-def]
        return self.client.get(url, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    def post(self, url: str, **kw: Any):  # type: ignore[no-untyped-def]
        return self.client.post(url, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    def patch(self, url: str, **kw: Any):  # type: ignore[no-untyped-def]
        return self.client.patch(url, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    def put(self, url: str, **kw: Any):  # type: ignore[no-untyped-def]
        return self.client.put(url, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    def delete(self, url: str, **kw: Any):  # type: ignore[no-untyped-def]
        return self.client.delete(url, headers={**self.headers, **kw.pop("headers", {})}, **kw)


def register(client: TestClient, email: str, name: str = "Test User") -> Api:
    res = client.post("/api/v1/auth/register", json={"email": email, "name": name, "password": PASSWORD})
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    client.cookies.clear()  # each Api uses its bearer token; cookies are tested explicitly
    return Api(client, data["access_token"], data["user"])


def create_project(api: Api, name: str = "Booking App", **extra: Any) -> dict[str, Any]:
    body = {"name": name, "platform": "web", **extra}
    res = api.post("/api/v1/projects", json=body)
    assert res.status_code == 201, res.text
    return res.json()["data"]


def add_member(owner: Api, project_id: str, member: Api, role: str) -> None:
    res = owner.post(f"/api/v1/projects/{project_id}/members", json={"email": member.user["email"], "role": role})
    assert res.status_code == 201, res.text


@pytest.fixture
def owner(client: TestClient) -> Api:
    return register(client, "owner@example.com", "Olivia Owner")


@pytest.fixture
def outsider(client: TestClient) -> Api:
    return register(client, "outsider@example.com", "Oscar Outsider")


@pytest.fixture
def project(owner: Api) -> dict[str, Any]:
    return create_project(owner)


def tmp_file(content: bytes, suffix: str) -> Path:
    fh = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)  # noqa: SIM115
    fh.write(content)
    fh.close()
    return Path(fh.name)
