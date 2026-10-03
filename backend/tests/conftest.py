# Environment must be established before importing the application/database.
# ruff: noqa: E402
import os
import uuid
from pathlib import Path

import pytest

TEST_ROOT = Path(__file__).resolve().parents[2] / ".storage" / ("tests-" + uuid.uuid4().hex)
TEST_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///" + str(TEST_ROOT / "test.db")
os.environ["STORAGE_DIR"] = str(TEST_ROOT)
os.environ["APP_ENV"] = "test"
os.environ["QUEUE_MODE"] = "local"
os.environ["LLM_PROVIDER"] = "offline"
os.environ["EMBEDDING_MODEL"] = "hashing-v1"
os.environ["VECTOR_STORE"] = "faiss"
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete

from alembic import command
from app.core.db import SessionLocal
from app.main import app
from app.models import User
from app.security.middleware import limiter


def pytest_configure(config):
    config.option.basetemp = str(TEST_ROOT / "tmp")


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    yield


@pytest.fixture(autouse=True)
def reset(migrated_db):
    with SessionLocal.begin() as db:
        db.execute(delete(User))
    limiter.buckets.clear()


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def authorize(client, email="owner@example.com"):
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-safe-password"}
    )
    assert response.status_code == 201, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    return response.json()


def analyzed_project(client):
    from app.services.analysis import analyze

    authorize(client)
    project = client.post("/api/v1/projects", json={"name": "Evidence fixture"}).json()
    job = client.post(f"/api/v1/projects/{project['id']}/demo").json()
    analyze(job["job_id"])
    overview = client.get(f"/api/v1/projects/{project['id']}").json()
    assert overview["snapshot"], overview
    return project["id"], overview["snapshot"]
