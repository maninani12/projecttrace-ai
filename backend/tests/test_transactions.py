import pytest
from conftest import analyzed_project
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionLocal, engine
from app.models import AnalysisJob, ProjectFile
from app.services.analysis import analyze


def test_analysis_failure_rolls_back_derived_rows(client, monkeypatch):
    pid, original = analyzed_project(client)

    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic failure with private details that must not be returned")

    monkeypatch.setattr("app.services.analysis.build_claims", fail)
    job = client.post(f"/api/v1/projects/{pid}/analyze").json()
    analyze(job["job_id"])
    overview = client.get(f"/api/v1/projects/{pid}").json()
    assert overview["snapshot"]["id"] == original["id"]
    assert overview["job"]["state"] == "FAILED"
    assert "private details" not in overview["job"]["error_summary"]
    with SessionLocal() as db:
        assert not list(
            db.scalars(select(ProjectFile).where(ProjectFile.snapshot_id == job["snapshot_id"]))
        )


def test_claim_page_queries_do_not_grow_per_claim(client):
    pid, _ = analyzed_project(client)
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        response = client.get(f"/api/v1/projects/{pid}/claims")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 8
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert len(statements) <= 8


def test_claim_search_filters_all_pages_case_insensitively(client):
    pid, _ = analyzed_project(client)
    response = client.get(f"/api/v1/projects/{pid}/claims?q=mOnGoDb&status=CONTRADICTED&limit=1")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["status"] == "CONTRADICTED"
    assert client.get(f"/api/v1/projects/{pid}/claims?q=%25").json()["total"] == 0


def test_database_guard_blocks_two_active_jobs(client):
    pid, _ = analyzed_project(client)
    job = client.post(f"/api/v1/projects/{pid}/analyze").json()
    with SessionLocal() as db:
        db.add(AnalysisJob(project_id=pid, snapshot_id=job["snapshot_id"], state="QUEUED"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_cancelled_queue_entry_never_analyzes(client):
    pid, original = analyzed_project(client)
    job = client.post(f"/api/v1/projects/{pid}/analyze").json()
    response = client.post(f"/api/v1/projects/{pid}/cancel")
    assert response.status_code == 200 and response.json()["state"] == "CANCELLED"
    analyze(job["job_id"])
    with SessionLocal() as db:
        assert not list(
            db.scalars(select(ProjectFile).where(ProjectFile.snapshot_id == job["snapshot_id"]))
        )
    assert client.get(f"/api/v1/projects/{pid}").json()["snapshot"]["id"] == original["id"]
