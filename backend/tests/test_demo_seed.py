from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import settings
from app.core.db import SessionLocal
from app.main import app
from app.models import User
from app.security import demo_seed
from app.security.auth import hasher
from app.security.middleware import limiter

DEMO_EMAIL = "demo@projecttrace.ai"
DEMO_PASSWORD = "ProjectTrace@123"  # Published development credential, never a real secret.


def configure_seed(monkeypatch, environment, enabled=True):
    config = settings().model_copy(update={"app_env": environment, "seed_demo_user": enabled})
    monkeypatch.setattr(demo_seed, "settings", lambda: config)


@pytest.mark.parametrize("environment", ["development", "demo"])
def test_startup_seeds_hashed_user_and_login_survives_restart(monkeypatch, environment):
    configure_seed(monkeypatch, environment)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
        )
        assert response.status_code == 200
        identity = response.json()["user"]["id"]
        assert client.get("/api/v1/auth/me").json()["user"]["email"] == DEMO_EMAIL
        assert "HttpOnly" in response.headers["set-cookie"]
        client.headers["X-CSRF-Token"] = response.json()["csrf"]
        assert (
            client.post("/api/v1/projects", json={"name": "Seeded user project"}).status_code == 201
        )
        assert client.post("/api/v1/auth/logout").status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        password_hash = user.password_hash
        assert password_hash.startswith("$argon2id$")
        assert DEMO_PASSWORD not in password_hash
        assert hasher.verify(password_hash, DEMO_PASSWORD)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
        )
        assert response.status_code == 200
        assert response.json()["user"]["id"] == identity
        assert len(client.get("/api/v1/projects").json()["items"]) == 1
    with SessionLocal() as db:
        assert (
            db.scalar(select(func.count()).select_from(User).where(User.email == DEMO_EMAIL)) == 1
        )
        assert db.get(User, identity).password_hash == password_hash


@pytest.mark.parametrize("environment", ["production", "test"])
def test_seeding_never_touches_database_or_fixture_outside_demo(monkeypatch, environment, tmp_path):
    configure_seed(monkeypatch, environment, enabled=True)
    monkeypatch.setattr(demo_seed, "FIXTURE", tmp_path / "does-not-exist.json")

    def forbidden_database_access():
        pytest.fail("Seeding must not open the database in this environment")

    monkeypatch.setattr(demo_seed, "SessionLocal", forbidden_database_access)
    with TestClient(app):
        pass  # Exercise the actual FastAPI startup hook, not just the seed helper.
    assert demo_seed.seed_demo_user() is False


def test_explicit_opt_out(monkeypatch):
    configure_seed(monkeypatch, "development", enabled=False)
    assert demo_seed.seed_demo_user() is False
    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.email == DEMO_EMAIL)) is None


def test_existing_user_password_is_not_reset(monkeypatch):
    configure_seed(monkeypatch, "development")
    original_hash = hasher.hash("existing-user-chosen-password")
    with SessionLocal.begin() as db:
        db.add(User(email=DEMO_EMAIL, password_hash=original_hash))
    assert demo_seed.seed_demo_user() is False
    with SessionLocal() as db:
        assert (
            db.scalar(select(User).where(User.email == DEMO_EMAIL)).password_hash == original_hash
        )


def test_session_checks_do_not_consume_login_attempt_budget(client, monkeypatch):
    config = settings()
    monkeypatch.setattr(config, "auth_rate_per_minute", 1)
    monkeypatch.setattr(config, "api_rate_per_minute", 120)
    for _ in range(12):
        assert client.get("/api/v1/auth/me").status_code == 401
    credentials = {"email": DEMO_EMAIL, "password": "incorrect-demo-password"}
    assert client.post("/api/v1/auth/login", json=credentials).status_code == 401
    assert client.post("/api/v1/auth/login", json=credentials).status_code == 429
    assert client.get("/api/v1/auth/me").status_code == 401
    assert len(limiter.buckets["auth:testclient"]) == 1


def test_concurrent_startup_is_idempotent(monkeypatch):
    configure_seed(monkeypatch, "development")
    with ThreadPoolExecutor(max_workers=4) as pool:
        created = list(pool.map(lambda _: demo_seed.seed_demo_user(), range(4)))
    assert created.count(True) == 1
    with SessionLocal() as db:
        assert (
            db.scalar(select(func.count()).select_from(User).where(User.email == DEMO_EMAIL)) == 1
        )
