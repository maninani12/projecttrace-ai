import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(UTC)


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Identity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)


class Session(Identity, Base):
    __tablename__ = "sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Project(Identity, Base):
    __tablename__ = "projects"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    repository_url: Mapped[str | None] = mapped_column(String(300))
    latest_snapshot_id: Mapped[str | None] = mapped_column(String(36))


class ProjectSnapshot(Identity, Base):
    __tablename__ = "snapshots"
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(20))
    commit_sha: Mapped[str] = mapped_column(String(64))
    branch: Mapped[str | None] = mapped_column(String(200))
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")


class ProjectFile(Identity, Base):
    __tablename__ = "files"
    __table_args__ = (UniqueConstraint("snapshot_id", "path"),)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(500))
    language: Mapped[str] = mapped_column(String(40))
    content: Mapped[str] = mapped_column(Text)
    byte_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))


class EvidenceChunk(Identity, Base):
    __tablename__ = "chunks"
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), index=True
    )
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(String(500))
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    chunk_type: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON().with_variant(Vector(384), "postgresql"))
    embedding_model: Mapped[str] = mapped_column(String(200))


class Artifact(Identity, Base):
    __tablename__ = "artifacts"
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), index=True
    )
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))


class Claim(Identity, Base):
    __tablename__ = "claims"
    __table_args__ = (Index("ix_claims_snapshot_status", "snapshot_id", "status"),)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text)
    source_artifact: Mapped[str] = mapped_column(String(500))
    source_line: Mapped[int | None] = mapped_column(Integer)
    recommendation: Mapped[str] = mapped_column(Text, default="")


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), primary_key=True
    )
    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )


class ConsistencyFinding(Identity, Base):
    __tablename__ = "findings"
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), index=True
    )
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))
    recommendation: Mapped[str] = mapped_column(Text)


class AnalysisJob(Identity, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_state_created", "state", "created_at"),
        Index(
            "uq_jobs_active_project",
            "project_id",
            unique=True,
            sqlite_where=text("state IN ('QUEUED', 'PROCESSING')"),
            postgresql_where=text("state IN ('QUEUED', 'PROCESSING')"),
        ),
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), index=True
    )
    state: Mapped[str] = mapped_column(String(20), default="QUEUED")
    stage: Mapped[str] = mapped_column(String(100), default="Repository received")
    source_path: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(300))
    error_type: Mapped[str | None] = mapped_column(String(80))
    error_summary: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class VivaSession(Identity, Base):
    __tablename__ = "viva_sessions"
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), index=True
    )
    difficulty: Mapped[str] = mapped_column(String(30))


class VivaQuestion(Identity, Base):
    __tablename__ = "viva_questions"
    session_id: Mapped[str] = mapped_column(
        ForeignKey("viva_sessions.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(String(100))
    follow_up: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON)
    revision: Mapped[bool] = mapped_column(default=False)


class GeneratedDocument(Identity, Base):
    __tablename__ = "documents"
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    content: Mapped[str] = mapped_column(Text)


class AnswerCache(Identity, Base):
    __tablename__ = "answer_cache"
    __table_args__ = (UniqueConstraint("snapshot_id", "query_hash"),)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), index=True
    )
    query_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)


def iso_time(value):
    return value.replace(tzinfo=UTC).isoformat() if value.tzinfo is None else value.isoformat()
