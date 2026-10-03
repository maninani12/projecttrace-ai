import hashlib
import hmac
import secrets
from datetime import UTC, timedelta

from argon2 import PasswordHasher
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select

from app.core.config import settings
from app.core.db import get_db
from app.models import Session, User, now

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_PASSWORD_HASH = hasher.hash(secrets.token_urlsafe(32))
COOKIE = "pt_session"


def token_hash(token):
    return hmac.new(settings().secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()


def create_session(db, user, response: Response):
    token, csrf = secrets.token_urlsafe(32), secrets.token_hex(32)
    row = Session(
        user_id=user.id,
        token_hash=token_hash(token),
        csrf=csrf,
        expires_at=now() + timedelta(hours=settings().session_hours),
    )
    db.add(row)
    db.commit()
    response.set_cookie(
        COOKIE,
        token,
        max_age=settings().session_hours * 3600,
        httponly=True,
        secure=settings().app_env == "production",
        samesite="lax",
        path="/api/v1",
    )
    return {
        "user": {"id": user.id, "email": user.email},
        "csrf": csrf,
        "mode": settings().llm_provider,
        "app_env": settings().app_env,
    }


def current_session(request: Request, db=Depends(get_db)):
    token = request.cookies.get(COOKIE, "")
    if len(token) > 100:
        raise HTTPException(401, "Session expired. Sign in again.")
    session = (
        db.scalar(select(Session).where(Session.token_hash == token_hash(token))) if token else None
    )
    if session is None or session.expires_at.replace(tzinfo=UTC) <= now():
        raise HTTPException(401, "Sign in to access your workspace.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token", "")
        if not secrets.compare_digest(csrf, session.csrf):
            raise HTTPException(403, "Security token missing or invalid. Refresh this page.")
    return session


def current_user(session=Depends(current_session), db=Depends(get_db)):
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "Session is no longer valid.")
    return user
