"""Cross-project isolation: every project-scoped route must answer 404 to a non-member and change nothing.

The route list is read from the OpenAPI schema, so a new project route is covered automatically."""

import re
import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import Api, create_project, register

ID_PARAMS = {"module_id", "document_id", "version_id", "user_id"}


def project_routes() -> list[tuple[str, str]]:
    routes = []
    for path, methods in app.openapi()["paths"].items():
        if "{project_id}" in path:
            routes.extend((method.upper(), path) for method in methods)
    return routes


def seed(owner: Api) -> dict[str, str]:
    project = create_project(owner, "Private project")
    pid = project["id"]
    module = owner.post(f"/api/v1/projects/{pid}/modules", json={"name": "Secret module"}).json()["data"]
    doc = owner.post(f"/api/v1/projects/{pid}/documents", files={"file": ("s.txt", b"secret")}).json()["data"]
    return {
        "project_id": pid,
        "module_id": module["id"],
        "document_id": doc["document"]["id"],
        "version_id": doc["document"]["current_version"]["id"],
        "user_id": owner.user["id"],
        "job_id": doc["job"]["id"],
    }


def call(api: Api, method: str, url: str) -> Any:
    if method == "GET":
        return api.get(url)
    if method == "DELETE":
        return api.delete(url)
    if url.endswith("/documents") or url.endswith("/versions"):
        return api.post(url, files={"file": ("x.txt", b"intrusion")})
    body: dict[str, Any] = {"name": "Hijack", "role": "owner", "email": api.user["email"], "to_module_ids": []}
    return getattr(api, method.lower())(url, json=body, headers={"If-Match": '"1"'})


def snapshot(owner: Api, ids: dict[str, str]) -> Any:
    pid = ids["project_id"]
    return (
        owner.get(f"/api/v1/projects/{pid}").json()["data"],
        owner.get(f"/api/v1/projects/{pid}/members").json()["data"],
        owner.get(f"/api/v1/projects/{pid}/modules").json()["data"],
        owner.get(f"/api/v1/projects/{pid}/documents").json()["data"],
    )


def test_every_project_route_is_closed_to_non_members(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    outsider = register(client, "outsider@example.com")
    ids = seed(owner)
    before = snapshot(owner, ids)

    routes = project_routes()
    assert len(routes) >= 18, routes  # sanity check that the schema walk found the routes
    for method, path in routes:
        url = "/api" + path if not path.startswith("/api") else path
        url = re.sub(r"\{(\w+)\}", lambda m: ids.get(m.group(1), str(uuid.uuid4())), url)
        res = call(outsider, method, url)
        assert res.status_code == 404, f"{method} {path} returned {res.status_code}: {res.text}"
        assert res.json()["code"] == "not_found"
        assert "Secret" not in res.text and "secret" not in res.text

    assert snapshot(owner, ids) == before, "a non-member request changed project data"


def test_non_member_cannot_see_jobs_or_list_foreign_projects(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    outsider = register(client, "outsider@example.com")
    ids = seed(owner)
    assert outsider.get(f"/api/v1/jobs/{ids['job_id']}").status_code == 404
    assert outsider.post(f"/api/v1/jobs/{ids['job_id']}/cancel").status_code == 404
    assert outsider.get("/api/v1/projects").json()["data"] == []
    dashboard = outsider.get("/api/v1/dashboard").json()["data"]
    assert dashboard["totals"]["projects"] == 0
    assert dashboard["recent_activity"] == [] and dashboard["recent_jobs"] == []
    assert outsider.get("/api/v1/me").json()["data"]["memberships"] == []


def test_ids_from_another_project_do_not_resolve(client: TestClient) -> None:
    """A member of project B cannot reach project A's module or document through B's URL."""
    owner = register(client, "owner@example.com")
    other = register(client, "other@example.com")
    ids = seed(owner)
    mine = create_project(other, "Mine")["id"]
    assert other.get(f"/api/v1/projects/{mine}/modules/{ids['module_id']}").status_code == 404
    assert other.get(f"/api/v1/projects/{mine}/documents/{ids['document_id']}").status_code == 404
    url = f"/api/v1/projects/{mine}/documents/{ids['document_id']}/versions/{ids['version_id']}/download-url"
    assert other.get(url).status_code == 404
    res = other.patch(f"/api/v1/projects/{mine}/documents/{ids['document_id']}", json={"title": "x"})
    assert res.status_code == 404
