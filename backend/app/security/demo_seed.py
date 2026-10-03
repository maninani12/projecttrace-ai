"""Seed a published, pre-hashed demo identity only in explicit demo environments."""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import User

FIXTURE = Path(__file__).resolve().parents[2] / "dev" / "demo-user.json"


def seed_demo_user() -> bool:
    config = settings()
    # Check before reading fixtures or opening a database session, regardless of opt-in.
    if config.app_env not in {"development", "demo"} or not config.seed_demo_user:
        return False

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if not fixture["password_hash"].startswith("$argon2id$"):
        raise ValueError("The development fixture must contain an Argon2id password hash.")
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == fixture["email"]))
        if existing is not None:
            return False
        db.add(User(email=fixture["email"], password_hash=fixture["password_hash"]))
        try:
            db.commit()
        except IntegrityError:
            # Multiple API workers may start together. Email uniqueness arbitrates the race.
            db.rollback()
            if db.scalar(select(User).where(User.email == fixture["email"])) is None:
                raise
            return False
    return True
