from conftest import analyzed_project, authorize
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.main import app
from app.models import Project, ProjectSnapshot
from app.parsers.archive import ParsedFile
from app.parsers.source import detect
from app.services.analysis import analyze


def test_health_and_migrations(client):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


def test_auth_csrf_logout(client):
    auth = authorize(client)
    assert client.get("/api/v1/auth/me").json()["user"]["id"] == auth["user"]["id"]
    del client.headers["X-CSRF-Token"]
    assert client.post("/api/v1/projects", json={"name": "blocked"}).status_code == 403
    client.headers["X-CSRF-Token"] = auth["csrf"]
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/projects").status_code == 401


def test_full_evidence_workflow(client):
    pid, snapshot = analyzed_project(client)
    stack = {x["name"] for x in snapshot["summary"]["stack"]}
    assert {"React", "FastAPI", "PostgreSQL"} <= stack
    assert "MongoDB" not in stack
    claims = client.get(f"/api/v1/projects/{pid}/claims").json()["items"]
    mongo = next(c for c in claims if "MongoDB" in c["text"])
    matched = next(
        c for c in claims if c["text"] == "The frontend uses React and the backend uses FastAPI."
    )
    assert matched["status"] == "VERIFIED"
    assert mongo["status"] == "CONTRADICTED"
    assert any("database.py" in x["path"] for x in mongo["evidence"])
    jwt = next(c for c in claims if "JWT" in c["text"])
    assert jwt["status"] == "UNVERIFIED"
    response = client.post(
        f"/api/v1/projects/{pid}/ask", json={"question": "Which database does this project use?"}
    ).json()
    assert response["status"] == "VERIFIED"
    assert "PostgreSQL" in response["answer"]
    assert response["evidence"][0]["project_id"] == pid
    assert response["evidence"][0]["commit_sha"] == snapshot["commit_sha"]
    session = client.post(
        f"/api/v1/projects/{pid}/viva", json={"difficulty": "ADVERSARIAL EXAMINER"}
    ).json()
    assert "discrepancy" in session["questions"][0]["question"]
    qid = session["questions"][0]["id"]
    assert client.patch(f"/api/v1/projects/{pid}/viva/{qid}", json={"revision": True}).json()[
        "revision"
    ]
    doc = client.post(f"/api/v1/projects/{pid}/documents", json={"kind": "presentation"}).json()
    assert "Future Scope" in doc["content"]
    assert "UI / Application Screens" in doc["content"]
    assert "\n" in doc["content"]
    assert len(client.get(f"/api/v1/projects/{pid}/consistency").json()["items"]) >= 3
    assert client.get(f"/api/v1/projects/{pid}/deployment-audit").status_code == 200


def test_ownership_idor_all_views(client):
    pid, snapshot = analyzed_project(client)
    files = client.get(f"/api/v1/projects/{pid}/files").json()["items"]
    with TestClient(app) as intruder:
        authorize(intruder, "intruder@example.com")
        for route in [
            "",
            "/status",
            "/files",
            "/claims",
            "/evidence",
            "/consistency",
            "/documents",
            "/deployment-audit",
            f"/files/{files[0]['id']}",
        ]:
            assert intruder.get(f"/api/v1/projects/{pid}" + route).status_code == 404
        for route, body in [
            ("/ask", {"question": "Which database?"}),
            ("/viva", {}),
            ("/documents", {}),
            ("/github", {"url": "https://github.com/pallets/flask"}),
            ("/analyze", {}),
        ]:
            assert intruder.post(f"/api/v1/projects/{pid}" + route, json=body).status_code == 404
        other = intruder.post("/api/v1/projects", json={"name": "Other"}).json()["id"]
        assert (
            intruder.get(f"/api/v1/projects/{other}?snapshot_id={snapshot['id']}").status_code
            == 409
        )


def test_unknown_answers_remain_uncertain(client):
    pid, _ = analyzed_project(client)
    result = client.post(
        f"/api/v1/projects/{pid}/ask",
        json={"question": "Does this project have quantum encryption?"},
    ).json()
    assert result["status"] == "UNVERIFIED"


def test_bad_upload_job_preserves_safe_error(client):
    authorize(client)
    pid = client.post("/api/v1/projects", json={"name": "Bad upload"}).json()["id"]
    response = client.post(
        f"/api/v1/projects/{pid}/upload",
        files={"file": ("bad.zip", b"not a zip", "application/zip")},
    )
    assert response.status_code == 202
    analyze(response.json()["job_id"])
    status = client.get(f"/api/v1/projects/{pid}/status").json()
    assert status["state"] == "FAILED"
    assert "valid ZIP" in status["error_summary"]
    assert client.get(f"/api/v1/projects/{pid}").json()["snapshot"] is None
    assert client.post(f"/api/v1/projects/{pid}/analyze").status_code == 202


def test_versions_preserved_and_stale_claim(client):
    import zipfile
    from io import BytesIO

    pid, old = analyzed_project(client)
    memory = BytesIO()
    with zipfile.ZipFile(memory, "w") as z:
        z.writestr("main.py", "from fastapi import FastAPI\napp = FastAPI()")
        z.writestr("README.md", "The project uses MongoDB as its database.")
    job = client.post(
        f"/api/v1/projects/{pid}/upload",
        files={"file": ("new.zip", memory.getvalue(), "application/zip")},
    ).json()
    analyze(job["job_id"])
    claims = client.get(f"/api/v1/projects/{pid}/claims").json()["items"]
    assert any(c["status"] == "STALE" and "PostgreSQL" in c["text"] for c in claims)
    previous = client.get(f"/api/v1/projects/{pid}?snapshot_id={old['id']}").json()
    assert "PostgreSQL" in [t["name"] for t in previous["snapshot"]["summary"]["stack"]]
    with SessionLocal() as db:
        assert (
            len(list(db.scalars(select(ProjectSnapshot).where(ProjectSnapshot.project_id == pid))))
            == 2
        )


def test_deletion_cascades(client):
    pid, _ = analyzed_project(client)
    assert (
        client.request(
            "DELETE", f"/api/v1/projects/{pid}", json={"confirmation": "wrong"}
        ).status_code
        == 422
    )
    assert (
        client.request(
            "DELETE", f"/api/v1/projects/{pid}", json={"confirmation": "Evidence fixture"}
        ).status_code
        == 200
    )
    with SessionLocal() as db:
        assert db.get(Project, pid) is None
        assert not list(
            db.scalars(select(ProjectSnapshot).where(ProjectSnapshot.project_id == pid))
        )


def test_rate_limit(client):
    authorize(client)
    config = settings()
    old = config.api_rate_per_minute
    config.api_rate_per_minute = 2
    try:
        assert client.get("/api/v1/projects").status_code == 200
        assert client.get("/api/v1/projects").status_code == 200
        response = client.get("/api/v1/projects")
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "60"
    finally:
        config.api_rate_per_minute = old


def test_validation_cors_and_injection(client):
    authorize(client)
    assert client.get("/api/v1/projects/not-a-uuid").status_code == 422
    assert (
        client.post(
            "/api/v1/projects", json={"name": "x"}, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.post("/api/v1/projects", json={"name": "x", "owner_id": "spoofed"}).status_code
        == 422
    )
    pid = client.post("/api/v1/projects", json={"name": "<script>alert(1)</script>"}).json()["id"]
    assert client.get(f"/api/v1/projects/{pid}").json()["name"] == "<script>alert(1)</script>"
    assert client.get("/api/v1/projects").headers["X-Content-Type-Options"] == "nosniff"
    assert (
        client.post(
            f"/api/v1/projects/{pid}/github", json={"url": "https://127.0.0.1/internal"}
        ).status_code
        == 422
    )
    assert (
        client.post(f"/api/v1/projects/{pid}/ask", json={"question": "x" * 2001}).status_code == 422
    )
    response = client.post(
        "/api/v1/projects", content="x" * 70000, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413


def test_readme_does_not_establish_technology():
    files = [ParsedFile("README.md", "Markdown", "Uses React, FastAPI and MongoDB.", 10, "x", 0)]
    assert detect(files) == []


def test_dependency_only_is_inferred():
    files = [ParsedFile("package.json", "JSON", '{"dependencies":{"react":"19"}}', 10, "x", 0)]
    assert detect(files)[0]["status"] == "INFERRED"
