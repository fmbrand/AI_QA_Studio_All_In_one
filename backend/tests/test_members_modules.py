from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import Api, add_member, register


def members(api: Api, pid: str) -> dict[str, str]:
    return {m["email"]: m["role"] for m in api.get(f"/api/v1/projects/{pid}/members").json()["data"]}


def test_add_member_requires_existing_account_and_no_duplicates(
    owner: Api, project: dict[str, Any], client: TestClient
) -> None:
    pid = project["id"]
    missing = owner.post(f"/api/v1/projects/{pid}/members", json={"email": "ghost@example.com", "role": "viewer"})
    assert missing.status_code == 404
    assert missing.json()["code"] == "user_not_found"
    viewer = register(client, "v@example.com")
    add_member(owner, pid, viewer, "viewer")
    again = owner.post(f"/api/v1/projects/{pid}/members", json={"email": "V@example.com", "role": "viewer"})
    assert again.status_code == 409
    assert members(owner, pid) == {"owner@example.com": "owner", "v@example.com": "viewer"}
    # The new member now sees the project.
    assert [p["id"] for p in viewer.get("/api/v1/projects").json()["data"]] == [pid]


def test_admin_cannot_grant_or_touch_owner(owner: Api, project: dict[str, Any], client: TestClient) -> None:
    pid = project["id"]
    admin = register(client, "admin@example.com")
    other = register(client, "other@example.com")
    add_member(owner, pid, admin, "admin")
    res = admin.post(f"/api/v1/projects/{pid}/members", json={"email": other.user["email"], "role": "owner"})
    assert res.status_code == 403
    assert (
        admin.post(
            f"/api/v1/projects/{pid}/members", json={"email": other.user["email"], "role": "qa_engineer"}
        ).status_code
        == 201
    )
    owner_id = owner.user["id"]
    assert admin.patch(f"/api/v1/projects/{pid}/members/{owner_id}", json={"role": "viewer"}).status_code == 403
    assert admin.delete(f"/api/v1/projects/{pid}/members/{owner_id}").status_code == 403


def test_last_owner_cannot_leave_or_be_demoted(owner: Api, project: dict[str, Any], client: TestClient) -> None:
    pid = project["id"]
    me = owner.user["id"]
    assert owner.patch(f"/api/v1/projects/{pid}/members/{me}", json={"role": "admin"}).json()["code"] == "last_owner"
    assert owner.delete(f"/api/v1/projects/{pid}/members/{me}").json()["code"] == "last_owner"
    second = register(client, "second@example.com")
    add_member(owner, pid, second, "owner")
    assert owner.patch(f"/api/v1/projects/{pid}/members/{me}", json={"role": "admin"}).status_code == 200
    assert members(second, pid)["owner@example.com"] == "admin"


def test_member_can_leave_and_viewer_cannot_remove_others(
    owner: Api, project: dict[str, Any], client: TestClient
) -> None:
    pid = project["id"]
    viewer = register(client, "v@example.com")
    engineer = register(client, "e@example.com")
    add_member(owner, pid, viewer, "viewer")
    add_member(owner, pid, engineer, "qa_engineer")
    assert viewer.delete(f"/api/v1/projects/{pid}/members/{engineer.user['id']}").status_code == 403
    assert viewer.delete(f"/api/v1/projects/{pid}/members/{viewer.user['id']}").status_code == 204
    assert viewer.get(f"/api/v1/projects/{pid}").status_code == 404
    assert owner.delete(f"/api/v1/projects/{pid}/members/{engineer.user['id']}").status_code == 204
    assert set(members(owner, pid)) == {"owner@example.com"}


def test_modules_crud_unique_names_and_versioning(owner: Api, project: dict[str, Any]) -> None:
    base = f"/api/v1/projects/{project['id']}/modules"
    created = owner.post(base, json={"name": "Booking", "description": "Create bookings"})
    assert created.status_code == 201
    mid = created.json()["data"]["id"]
    assert owner.post(base, json={"name": "booking"}).json()["code"] == "module_exists"

    assert owner.patch(f"{base}/{mid}", json={"name": "Bookings"}).status_code == 428
    updated = owner.patch(f"{base}/{mid}", json={"name": "Bookings"}, headers={"If-Match": '"1"'})
    assert updated.status_code == 200
    assert updated.json()["data"]["version"] == 2
    assert owner.patch(f"{base}/{mid}", json={"name": "B"}, headers={"If-Match": '"1"'}).status_code == 412

    assert [m["name"] for m in owner.get(base).json()["data"]] == ["Bookings"]
    assert owner.delete(f"{base}/{mid}").status_code == 204
    assert owner.get(base).json()["data"] == []
    assert owner.get(f"{base}/{mid}").status_code == 404


def test_module_connections(owner: Api, project: dict[str, Any], client: TestClient) -> None:
    base = f"/api/v1/projects/{project['id']}/modules"
    ids = [owner.post(base, json={"name": n}).json()["data"]["id"] for n in ("Booking", "Payment", "Coupon")]
    booking, payment, coupon = ids
    res = owner.put(f"{base}/{booking}/connections", json={"to_module_ids": [payment, coupon, payment]})
    assert res.status_code == 200
    assert res.json()["data"]["connected_module_ids"] == [payment, coupon]
    listed = {m["name"]: m["connected_module_ids"] for m in owner.get(base).json()["data"]}
    assert sorted(listed["Booking"]) == sorted([payment, coupon])

    assert owner.put(f"{base}/{booking}/connections", json={"to_module_ids": [booking]}).status_code == 422

    # A module from another project cannot be connected.
    other_owner = register(client, "other@example.com")
    other_pid = other_owner.post("/api/v1/projects", json={"name": "Other", "platform": "api"}).json()["data"]["id"]
    foreign = other_owner.post(f"/api/v1/projects/{other_pid}/modules", json={"name": "X"}).json()["data"]["id"]
    res = owner.put(f"{base}/{booking}/connections", json={"to_module_ids": [foreign]})
    assert res.status_code == 422
    assert res.json()["code"] == "unknown_modules"

    owner.delete(f"{base}/{payment}")
    listed = {m["name"]: m["connected_module_ids"] for m in owner.get(base).json()["data"]}
    assert listed["Booking"] == [coupon]
