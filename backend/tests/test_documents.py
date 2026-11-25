import io
import zipfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.worker.runner import run_pending
from tests.conftest import Api, add_member, register


def upload(api: Api, pid: str, name: str, content: bytes, **form: str):  # type: ignore[no-untyped-def]
    return api.post(f"/api/v1/projects/{pid}/documents", files={"file": (name, content)}, data=form)


def docx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


def test_upload_text_document_is_extracted_by_worker(
    owner: Api,
    project: dict[str, Any],
    session_factory,  # type: ignore[no-untyped-def]
    clean_state: Path,
) -> None:
    pid = project["id"]
    res = upload(owner, pid, "booking-rules.md", b"# Booking\nA customer can book a slot.", kind="requirement")
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    doc, job = data["document"], data["job"]
    assert doc["title"] == "booking-rules"
    assert doc["kind"] == "requirement"
    assert doc["current_version"]["processing_status"] == "queued"
    assert doc["current_version"]["content_type"] == "text/markdown"
    assert job["status"] == "queued" and job["kind"] == "document_ingest"
    assert list(clean_state.rglob("*.md")), "file was written to storage"

    assert run_pending(session_factory) == 1
    assert owner.get(f"/api/v1/jobs/{job['id']}").json()["data"]["status"] == "succeeded"
    detail = owner.get(f"/api/v1/projects/{pid}/documents/{doc['id']}").json()["data"]
    assert detail["current_version"]["processing_status"] == "processed"
    extractions = owner.get(f"/api/v1/projects/{pid}/documents/{doc['id']}/extractions").json()["data"]
    assert extractions[0]["text"] == "# Booking\nA customer can book a slot."
    assert extractions[0]["char_count"] == 37


def test_csv_extraction_records_shape(owner: Api, project: dict[str, Any], session_factory) -> None:  # type: ignore[no-untyped-def]
    pid = project["id"]
    doc = upload(owner, pid, "cases.csv", b"id,title\n1,Login\n2,Logout\n").json()["data"]["document"]
    run_pending(session_factory)
    ext = owner.get(f"/api/v1/projects/{pid}/documents/{doc['id']}/extractions").json()["data"][0]
    assert ext["meta"]["rows"] == 2 and ext["meta"]["columns"] == ["id", "title"]
    # Each row becomes a self-describing line so a chunk keeps its column names.
    assert ext["text"] == "id: 1 | title: Login\nid: 2 | title: Logout"


def test_corrupt_binary_fails_without_retrying(owner: Api, project: dict[str, Any], session_factory) -> None:  # type: ignore[no-untyped-def]
    pid = project["id"]
    pdf = upload(owner, pid, "spec.pdf", b"%PDF-1.4\n%header only, no objects\n").json()["data"]["document"]
    docx = upload(owner, pid, "spec.docx", docx_bytes()).json()["data"]["document"]
    run_pending(session_factory)
    for d in (pdf, docx):
        version = owner.get(f"/api/v1/projects/{pid}/documents/{d['id']}").json()["data"]["current_version"]
        assert version["processing_status"] == "failed"
        assert version["processing_error"].startswith("The file could not be read")
    jobs = owner.get(f"/api/v1/projects/{pid}/jobs").json()["data"]
    assert all(j["attempts"] == 1 for j in jobs)


def test_rejects_unsupported_and_mismatched_files(owner: Api, project: dict[str, Any]) -> None:
    pid = project["id"]
    exe = upload(owner, pid, "tool.exe", b"MZ\x90\x00")
    assert exe.status_code == 415 and exe.json()["code"] == "unsupported_file_type"
    assert ".pdf" in exe.json()["allowed_extensions"]
    assert upload(owner, pid, "fake.pdf", b"just text").status_code == 415
    assert upload(owner, pid, "fake.png", b"GIF89a....").status_code == 415
    assert upload(owner, pid, "fake.docx", b"PK\x03\x04 not a zip").status_code == 415
    assert upload(owner, pid, "binary.txt", b"abc\x00\x01").status_code == 415
    assert upload(owner, pid, "bad.json", b"{not json").json()["code"] == "invalid_json"
    assert upload(owner, pid, "empty.txt", b"").json()["code"] == "empty_file"


def test_rejects_files_over_the_size_limit(owner: Api, project: dict[str, Any]) -> None:
    res = upload(owner, project["id"], "big.txt", b"a" * (1024 * 1024 + 1))  # MAX_UPLOAD_MB=1 in tests
    assert res.status_code == 413
    assert res.json()["code"] == "file_too_large"


def test_duplicate_detection_and_versions(owner: Api, project: dict[str, Any]) -> None:
    pid = project["id"]
    first = upload(owner, pid, "rules.txt", b"v1 rules").json()["data"]["document"]
    dup = upload(owner, pid, "copy-of-rules.txt", b"v1 rules")
    assert dup.status_code == 409
    assert dup.json()["existing_document_id"] == first["id"]

    url = f"/api/v1/projects/{pid}/documents/{first['id']}/versions"
    same = owner.post(url, files={"file": ("rules.txt", b"v1 rules")})
    assert same.status_code == 409
    v2 = owner.post(url, files={"file": ("rules-v2.txt", b"v2 rules")})
    assert v2.status_code == 201
    detail = v2.json()["data"]["document"]
    assert detail["version_count"] == 2
    assert detail["current_version"]["version"] == 2
    assert [v["version"] for v in detail["versions"]] == [2, 1]

    # After deleting the document the same content may be uploaded again.
    assert owner.delete(f"/api/v1/projects/{pid}/documents/{first['id']}").status_code == 204
    assert upload(owner, pid, "rules.txt", b"v1 rules").status_code == 201


def test_list_filter_search_and_update(owner: Api, project: dict[str, Any]) -> None:
    pid = project["id"]
    module = owner.post(f"/api/v1/projects/{pid}/modules", json={"name": "Coupon"}).json()["data"]
    upload(owner, pid, "coupon-rules.txt", b"coupons", kind="business_logic", module_id=module["id"])
    other = upload(owner, pid, "api.json", b'{"openapi": "3.1.0"}', kind="api_spec").json()["data"]["document"]
    base = f"/api/v1/projects/{pid}/documents"
    assert [d["title"] for d in owner.get(f"{base}?kind=api_spec").json()["data"]] == ["api"]
    assert [d["title"] for d in owner.get(f"{base}?module_id={module['id']}").json()["data"]] == ["coupon-rules"]
    assert [d["title"] for d in owner.get(f"{base}?q=COUPON").json()["data"]] == ["coupon-rules"]

    res = owner.patch(f"{base}/{other['id']}", json={"title": "Public API", "module_id": module["id"]})
    assert res.status_code == 200
    assert res.json()["data"]["title"] == "Public API"
    assert res.json()["data"]["module_id"] == module["id"]
    cleared = owner.patch(f"{base}/{other['id']}", json={"clear_module": True}).json()["data"]
    assert cleared["module_id"] is None


def test_filename_is_sanitised(owner: Api, project: dict[str, Any]) -> None:
    res = upload(owner, project["id"], "../../etc/passwd.txt", b"harmless")
    assert res.status_code == 201
    assert res.json()["data"]["document"]["current_version"]["filename"] == "passwd.txt"


def test_signed_download_url(owner: Api, project: dict[str, Any], client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pid = project["id"]
    doc = upload(owner, pid, "notes.txt", b"hello download").json()["data"]["document"]
    vid = doc["current_version"]["id"]
    link = owner.get(f"/api/v1/projects/{pid}/documents/{doc['id']}/versions/{vid}/download-url").json()["data"]
    assert link["expires_in"] == 300
    res = client.get(link["url"])
    assert res.status_code == 200
    assert res.content == b"hello download"
    assert "attachment" in res.headers["content-disposition"]
    assert res.headers["x-content-type-options"] == "nosniff"

    tampered = link["url"][:-1] + ("0" if link["url"][-1] != "0" else "1")
    assert client.get(tampered).status_code == 404

    import app.core.security as security

    real_time = security.time.time
    monkeypatch.setattr(security.time, "time", lambda: real_time() + 3600)
    assert client.get(link["url"]).status_code == 404


def test_download_link_stops_working_when_member_is_removed(
    owner: Api, project: dict[str, Any], client: TestClient
) -> None:
    pid = project["id"]
    viewer = register(client, "v@example.com")
    add_member(owner, pid, viewer, "viewer")
    doc = upload(owner, pid, "secret.txt", b"secret").json()["data"]["document"]
    vid = doc["current_version"]["id"]
    url = viewer.get(f"/api/v1/projects/{pid}/documents/{doc['id']}/versions/{vid}/download-url").json()["data"]["url"]
    assert client.get(url).status_code == 200
    owner.delete(f"/api/v1/projects/{pid}/members/{viewer.user['id']}")
    assert client.get(url).status_code == 404


def test_viewer_can_read_but_not_upload(owner: Api, project: dict[str, Any], client: TestClient) -> None:
    pid = project["id"]
    viewer = register(client, "v@example.com")
    add_member(owner, pid, viewer, "viewer")
    upload(owner, pid, "a.txt", b"a")
    assert upload(viewer, pid, "b.txt", b"b").status_code == 403
    assert len(viewer.get(f"/api/v1/projects/{pid}/documents").json()["data"]) == 1


def test_failed_job_marks_version_failed(
    owner: Api,
    project: dict[str, Any],
    session_factory,  # type: ignore[no-untyped-def]
    clean_state: Path,
) -> None:
    pid = project["id"]
    doc = upload(owner, pid, "gone.txt", b"will vanish").json()["data"]["document"]
    for f in clean_state.rglob("*.txt"):
        f.unlink()  # simulate a storage failure
    run_pending(session_factory)
    run_pending(session_factory)
    run_pending(session_factory)
    version = owner.get(f"/api/v1/projects/{pid}/documents/{doc['id']}").json()["data"]["current_version"]
    assert version["processing_status"] == "failed"
    assert "FileNotFoundError" in version["processing_error"]
    jobs = owner.get(f"/api/v1/projects/{pid}/jobs").json()["data"]
    assert jobs[0]["status"] == "failed" and jobs[0]["attempts"] == 3


def test_cancel_queued_job(owner: Api, project: dict[str, Any], session_factory) -> None:  # type: ignore[no-untyped-def]
    job = upload(owner, project["id"], "c.txt", b"c").json()["data"]["job"]
    assert owner.post(f"/api/v1/jobs/{job['id']}/cancel").json()["data"]["status"] == "cancelled"
    assert run_pending(session_factory) == 0
    assert owner.post(f"/api/v1/jobs/{job['id']}/cancel").status_code == 409
