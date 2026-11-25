from typing import Any

from tests.conftest import Api, add_member, create_project, register


def test_create_project_makes_creator_owner(owner: Api) -> None:
    project = create_project(
        owner,
        "Checkout",
        platform="multi_platform",
        tech_stack=["React", "react", " Node "],
        application_url="https://shop.example.com",
        business_domain="E-commerce",
    )
    assert project["my_role"] == "owner"
    assert project["status"] == "active"
    assert project["tech_stack"] == ["React", "Node"]
    assert project["stats"] == {"members": 1, "modules": 0, "documents": 0}
    assert project["version"] == 1


def test_create_project_validates(owner: Api) -> None:
    res = owner.post("/api/v1/projects", json={"name": "  ", "platform": "desktop"})
    assert res.status_code == 422
    fields = {e["field"] for e in res.json()["errors"]}
    assert {"name", "platform"} <= fields
    res = owner.post("/api/v1/projects", json={"name": "X", "platform": "web", "application_url": "not a url"})
    assert res.status_code == 422


def test_list_only_shows_member_projects_and_filters(owner: Api, outsider: Api) -> None:
    create_project(owner, "Alpha")
    beta = create_project(owner, "Beta")
    create_project(outsider, "Outsider project")
    owner.post(f"/api/v1/projects/{beta['id']}/archive")

    names = [p["name"] for p in owner.get("/api/v1/projects").json()["data"]]
    assert sorted(names) == ["Alpha", "Beta"]
    active = owner.get("/api/v1/projects?status=active").json()["data"]
    assert [p["name"] for p in active] == ["Alpha"]
    search = owner.get("/api/v1/projects?q=alp").json()["data"]
    assert [p["name"] for p in search] == ["Alpha"]


def test_cursor_pagination(owner: Api) -> None:
    for i in range(5):
        create_project(owner, f"P{i}")
    first = owner.get("/api/v1/projects?limit=2").json()
    assert len(first["data"]) == 2
    cursor = first["meta"]["page"]["next_cursor"]
    assert cursor
    seen = [p["name"] for p in first["data"]]
    while cursor:
        page = owner.get(f"/api/v1/projects?limit=2&cursor={cursor}").json()
        seen += [p["name"] for p in page["data"]]
        cursor = page["meta"]["page"]["next_cursor"]
    assert sorted(seen) == [f"P{i}" for i in range(5)]
    assert len(set(seen)) == 5
    assert owner.get("/api/v1/projects?cursor=@@bad").status_code == 400


def test_update_requires_if_match_and_detects_conflicts(owner: Api, project: dict[str, Any]) -> None:
    url = f"/api/v1/projects/{project['id']}"
    assert owner.patch(url, json={"name": "New"}).status_code == 428

    res = owner.patch(url, json={"name": "New name", "tech_stack": ["Flutter"]}, headers={"If-Match": '"1"'})
    assert res.status_code == 200
    assert res.json()["data"]["name"] == "New name"
    assert res.json()["data"]["version"] == 2
    assert res.headers["etag"] == '"2"'

    stale = owner.patch(url, json={"name": "Stale"}, headers={"If-Match": '"1"'})
    assert stale.status_code == 412
    assert stale.json()["code"] == "version_conflict"


def test_update_can_clear_application_url(owner: Api) -> None:
    project = create_project(owner, application_url="https://a.example.com")
    url = f"/api/v1/projects/{project['id']}"
    res = owner.patch(url, json={"application_url": None}, headers={"If-Match": '"1"'})
    assert res.status_code == 200
    assert res.json()["data"]["application_url"] is None


def test_archived_project_is_read_only_until_restored(owner: Api, project: dict[str, Any]) -> None:
    pid = project["id"]
    archived = owner.post(f"/api/v1/projects/{pid}/archive")
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"
    version = archived.json()["data"]["version"]

    blocked = owner.patch(f"/api/v1/projects/{pid}", json={"name": "x"}, headers={"If-Match": f'"{version}"'})
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "project_archived"
    assert owner.post(f"/api/v1/projects/{pid}/modules", json={"name": "Auth"}).status_code == 409
    assert owner.get(f"/api/v1/projects/{pid}").status_code == 200  # still readable

    assert owner.post(f"/api/v1/projects/{pid}/archive").status_code == 409  # already archived
    restored = owner.post(f"/api/v1/projects/{pid}/restore")
    assert restored.json()["data"]["status"] == "active"
    assert owner.post(f"/api/v1/projects/{pid}/modules", json={"name": "Auth"}).status_code == 201


def test_only_owner_can_delete_and_delete_hides_project(client, owner: Api, project: dict[str, Any]) -> None:  # type: ignore[no-untyped-def]
    admin = register(client, "admin@example.com")
    add_member(owner, project["id"], admin, "admin")
    assert admin.delete(f"/api/v1/projects/{project['id']}").status_code == 403
    assert owner.delete(f"/api/v1/projects/{project['id']}").status_code == 204
    assert owner.get(f"/api/v1/projects/{project['id']}").status_code == 404
    assert owner.get("/api/v1/projects").json()["data"] == []


def test_role_permissions_on_project_actions(client, owner: Api, project: dict[str, Any]) -> None:  # type: ignore[no-untyped-def]
    pid = project["id"]
    viewer = register(client, "viewer@example.com")
    engineer = register(client, "eng@example.com")
    add_member(owner, pid, viewer, "viewer")
    add_member(owner, pid, engineer, "qa_engineer")

    assert viewer.get(f"/api/v1/projects/{pid}").json()["data"]["my_role"] == "viewer"
    assert viewer.post(f"/api/v1/projects/{pid}/modules", json={"name": "Cart"}).status_code == 403
    assert engineer.post(f"/api/v1/projects/{pid}/modules", json={"name": "Cart"}).status_code == 201
    assert engineer.patch(f"/api/v1/projects/{pid}", json={"name": "x"}, headers={"If-Match": '"1"'}).status_code == 403
    assert engineer.post(f"/api/v1/projects/{pid}/archive").status_code == 403


def test_activity_log_records_project_changes(owner: Api, project: dict[str, Any]) -> None:
    pid = project["id"]
    owner.patch(f"/api/v1/projects/{pid}", json={"description": "Booking flows"}, headers={"If-Match": '"1"'})
    owner.post(f"/api/v1/projects/{pid}/archive")
    log = owner.get(f"/api/v1/projects/{pid}/activity").json()["data"]
    actions = [entry["action"] for entry in log]
    assert actions[:3] == ["project.archived", "project.updated", "project.created"]
    updated = log[1]
    assert updated["before"] == {"description": ""}
    assert updated["after"] == {"description": "Booking flows"}
    assert updated["actor_name"] == "Olivia Owner"


def test_dashboard_counts_only_real_data_for_caller(owner: Api, outsider: Api) -> None:
    empty = owner.get("/api/v1/dashboard").json()["data"]
    assert empty["totals"] == {
        "projects": 0,
        "active_projects": 0,
        "archived_projects": 0,
        "documents": 0,
        "modules": 0,
        "requirements": 0,
        "approved_requirements": 0,
    }
    a = create_project(owner, "A")
    create_project(owner, "B")
    create_project(outsider, "Not mine")
    owner.post(f"/api/v1/projects/{a['id']}/archive")
    owner.post(f"/api/v1/projects/{a['id']}/restore")
    b = owner.get("/api/v1/projects?q=B").json()["data"][0]
    owner.post(f"/api/v1/projects/{b['id']}/modules", json={"name": "Search"})
    owner.post(f"/api/v1/projects/{b['id']}/archive")
    data = owner.get("/api/v1/dashboard").json()["data"]
    assert data["totals"] == {
        "projects": 2, "active_projects": 1, "archived_projects": 1, "documents": 0, "modules": 1,
        "requirements": 0, "approved_requirements": 0,
    }  # fmt: skip
    assert all(item["project_id"] in {a["id"], b["id"]} for item in data["recent_activity"])
