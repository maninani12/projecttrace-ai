import secrets
import shutil
from pathlib import Path
from uuid import UUID

from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from app.ai.providers import ProviderError
from app.core.config import ROOT, settings
from app.core.db import get_db
from app.models import (
    AnalysisJob,
    Claim,
    ConsistencyFinding,
    EvidenceChunk,
    GeneratedDocument,
    Project,
    ProjectFile,
    ProjectSnapshot,
    User,
    VivaQuestion,
    VivaSession,
    iso_time,
)
from app.retrieval.engine import evidence_dict
from app.schemas import (
    AnswerOut,
    AskQuestion,
    CreateProject,
    Credentials,
    DeleteRequest,
    DocumentRequest,
    GitHubImport,
    RevisionRequest,
    VivaRequest,
)
from app.security.auth import (
    COOKIE,
    DUMMY_PASSWORD_HASH,
    create_session,
    current_session,
    current_user,
    hasher,
)
from app.services.github import GitHubError, repository_parts
from app.services.intelligence import ask, claim_dict, claim_page, document, viva
from app.workers.runner import dispatch

router = APIRouter(prefix="/api/v1")


def valid_id(value):
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise HTTPException(422, "Invalid resource identifier.") from exc


def owned(db, project_id, user):
    project = db.scalar(
        select(Project).where(Project.id == valid_id(project_id), Project.owner_id == user.id)
    )
    if project is None:
        raise HTTPException(404, "Project not found.")
    return project


def snapshot_for(db, project, snapshot_id=None):
    snapshot_id = valid_id(snapshot_id) if snapshot_id else project.latest_snapshot_id
    snapshot = db.scalar(
        select(ProjectSnapshot).where(
            ProjectSnapshot.id == snapshot_id, ProjectSnapshot.project_id == project.id
        )
    )
    if snapshot is None or snapshot.status != "COMPLETED":
        raise HTTPException(409, "Analyze a repository snapshot before opening this view.")
    return snapshot


def job_dict(job):
    return {
        "id": job.id,
        "snapshot_id": job.snapshot_id,
        "state": job.state,
        "stage": job.stage,
        "error_type": job.error_type,
        "error_summary": job.error_summary,
        "created_at": iso_time(job.created_at),
    }


def enqueue(db, project, source_type, path=None, url=None):
    active = db.scalar(
        select(AnalysisJob).where(
            AnalysisJob.project_id == project.id, AnalysisJob.state.in_(["QUEUED", "PROCESSING"])
        )
    )
    if active:
        raise HTTPException(409, "An analysis is already running for this project.")
    snapshot = ProjectSnapshot(
        project_id=project.id, source_type=source_type, commit_sha="pending", status="QUEUED"
    )
    db.add(snapshot)
    db.flush()
    job = AnalysisJob(
        project_id=project.id,
        snapshot_id=snapshot.id,
        source_path=str(path) if path else None,
        source_url=url,
    )
    db.add(job)
    if url:
        project.repository_url = url
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An analysis is already running for this project.") from exc
    try:
        dispatch(job.id)
    except Exception as exc:
        job.state = "FAILED"
        job.error_type = "QueueUnavailable"
        job.error_summary = "The background queue is unavailable. Restore Redis and retry."
        snapshot.status = "FAILED"
        db.commit()
        raise HTTPException(503, job.error_summary) from exc
    return {"job_id": job.id, **job_dict(job)}


@router.post("/auth/register", status_code=201)
def register(body: Credentials, response: Response, db=Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "This email cannot be registered. Try signing in.")
    user = User(email=body.email, password_hash=hasher.hash(body.password))
    db.add(user)
    db.flush()
    return create_session(db, user, response)


@router.post("/auth/login")
def login(body: Credentials, response: Response, db=Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    # A real Argon2 check also runs for nonexistent users.
    target = user.password_hash if user else DUMMY_PASSWORD_HASH
    try:
        valid = hasher.verify(target, body.password)
    except (VerifyMismatchError, InvalidHashError):
        valid = False
    if not user or not valid:
        raise HTTPException(401, "Email or password is incorrect.")
    return create_session(db, user, response)


@router.post("/auth/demo")
def demo_login(request: Request, response: Response, db=Depends(get_db)):
    if settings().app_env == "production" or request.client.host not in {
        "127.0.0.1",
        "::1",
        "testclient",
    }:
        raise HTTPException(403, "Demo workspaces are available only on local development servers.")
    user = User(email=f"demo-{secrets.token_hex(8)}@projecttrace.local", password_hash="!disabled")
    db.add(user)
    db.flush()
    return create_session(db, user, response)


@router.get("/auth/me")
def me(user=Depends(current_user), session=Depends(current_session)):
    return {
        "user": {"id": user.id, "email": user.email},
        "csrf": session.csrf,
        "mode": settings().llm_provider,
        "app_env": settings().app_env,
    }


@router.post("/auth/logout")
def logout(response: Response, session=Depends(current_session), db=Depends(get_db)):
    db.delete(session)
    db.commit()
    response.delete_cookie(COOKIE, path="/api/v1")
    return {"ok": True}


@router.get("/projects")
def projects(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(current_user),
    db=Depends(get_db),
):
    rows = db.scalars(
        select(Project)
        .where(Project.owner_id == user.id)
        .order_by(Project.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": [
            {
                "id": p.id,
                "name": p.name,
                "latest_snapshot_id": p.latest_snapshot_id,
                "repository_url": p.repository_url,
            }
            for p in rows
        ]
    }


@router.post("/projects", status_code=201)
def create(body: CreateProject, user=Depends(current_user), db=Depends(get_db)):
    count = db.scalar(select(func.count()).select_from(Project).where(Project.owner_id == user.id))
    if count >= 50:
        raise HTTPException(409, "Workspace project limit reached. Delete an unused project first.")
    project = Project(owner_id=user.id, name=body.name)
    db.add(project)
    db.commit()
    return {"id": project.id, "name": project.name}


@router.get("/projects/{project_id}")
def overview(
    project_id: str, snapshot_id: str | None = None, user=Depends(current_user), db=Depends(get_db)
):
    p = owned(db, project_id, user)
    latest_job = db.scalar(
        select(AnalysisJob)
        .where(AnalysisJob.project_id == p.id)
        .order_by(AnalysisJob.created_at.desc())
        .limit(1)
    )
    history = list(
        db.scalars(
            select(ProjectSnapshot)
            .where(ProjectSnapshot.project_id == p.id)
            .order_by(ProjectSnapshot.created_at.desc())
            .limit(100)
        )
    )
    snapshot = snapshot_for(db, p, snapshot_id) if snapshot_id or p.latest_snapshot_id else None
    return {
        "id": p.id,
        "name": p.name,
        "repository_url": p.repository_url,
        "job": job_dict(latest_job) if latest_job else None,
        "snapshot": {
            "id": snapshot.id,
            "source_type": snapshot.source_type,
            "commit_sha": snapshot.commit_sha,
            "branch": snapshot.branch,
            "analyzed_at": iso_time(snapshot.analyzed_at),
            "summary": snapshot.summary,
        }
        if snapshot
        else None,
        "history": [
            {
                "id": s.id,
                "commit_sha": s.commit_sha,
                "status": s.status,
                "created_at": iso_time(s.created_at),
            }
            for s in history
        ],
    }


@router.post("/projects/{project_id}/upload", status_code=202)
async def upload(
    project_id: str, file: UploadFile = File(...), user=Depends(current_user), db=Depends(get_db)
):
    project = owned(db, project_id, user)
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(415, "Choose a ZIP archive.")
    config = settings()
    config.storage_dir.mkdir(parents=True, exist_ok=True)
    path = config.storage_dir / (secrets.token_hex(16) + ".zip")
    size = 0
    try:
        with path.open("wb") as handle:
            while block := await file.read(64 * 1024):
                size += len(block)
                if size > config.max_upload_mb * 1024**2:
                    raise HTTPException(413, "Upload exceeds the configured ZIP size limit.")
                handle.write(block)
        if not size:
            raise HTTPException(422, "The ZIP archive is empty.")
        return enqueue(db, project, "zip", path=path)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@router.post("/projects/{project_id}/github", status_code=202)
def github(project_id: str, body: GitHubImport, user=Depends(current_user), db=Depends(get_db)):
    p = owned(db, project_id, user)
    try:
        repository_parts(body.url)
    except GitHubError as exc:
        raise HTTPException(422, str(exc)) from exc
    return enqueue(db, p, "github", url=body.url)


@router.post("/projects/{project_id}/demo", status_code=202)
def sample(project_id: str, user=Depends(current_user), db=Depends(get_db)):
    p = owned(db, project_id, user)
    settings().storage_dir.mkdir(parents=True, exist_ok=True)
    destination = settings().storage_dir / (secrets.token_hex(16) + ".zip")
    shutil.copyfile(ROOT / "samples" / "mixed-demo.zip", destination)
    try:
        return enqueue(db, p, "demo", path=destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


@router.get("/projects/{project_id}/status")
def status(project_id: str, user=Depends(current_user), db=Depends(get_db)):
    p = owned(db, project_id, user)
    job = db.scalar(
        select(AnalysisJob)
        .where(AnalysisJob.project_id == p.id)
        .order_by(AnalysisJob.created_at.desc())
        .limit(1)
    )
    return job_dict(job) if job else {"state": "EMPTY", "stage": "Import a repository"}


@router.post("/projects/{project_id}/analyze", status_code=202)
def retry(project_id: str, user=Depends(current_user), db=Depends(get_db)):
    p = owned(db, project_id, user)
    old = db.scalar(
        select(AnalysisJob)
        .where(AnalysisJob.project_id == p.id)
        .order_by(AnalysisJob.created_at.desc())
        .limit(1)
    )
    if not old:
        raise HTTPException(409, "Import a repository first.")
    if not old.source_url and (not old.source_path or not Path(old.source_path).exists()):
        raise HTTPException(409, "The original upload expired. Upload the repository again.")
    old_snapshot = db.get(ProjectSnapshot, old.snapshot_id)
    return enqueue(db, p, old_snapshot.source_type, path=old.source_path, url=old.source_url)


@router.post("/projects/{project_id}/cancel")
def cancel_queued(project_id: str, user=Depends(current_user), db=Depends(get_db)):
    project = owned(db, project_id, user)
    job = db.scalar(
        select(AnalysisJob)
        .where(AnalysisJob.project_id == project.id, AnalysisJob.state == "QUEUED")
        .order_by(AnalysisJob.created_at.desc())
        .limit(1)
    )
    if not job:
        raise HTTPException(
            409, "Only queued analyses can be cancelled. Running analyses have a worker timeout."
        )
    changed = db.execute(
        update(AnalysisJob)
        .where(AnalysisJob.id == job.id, AnalysisJob.state == "QUEUED")
        .values(state="CANCELLED", stage="Analysis cancelled")
    ).rowcount
    if not changed:
        db.rollback()
        raise HTTPException(409, "This analysis has already started.")
    db.get(ProjectSnapshot, job.snapshot_id).status = "CANCELLED"
    db.commit()
    db.refresh(job)
    return job_dict(job)


@router.get("/projects/{project_id}/files")
def files(
    project_id: str,
    snapshot_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    user=Depends(current_user),
    db=Depends(get_db),
):
    s = snapshot_for(db, owned(db, project_id, user), snapshot_id)
    rows = db.scalars(
        select(ProjectFile)
        .where(ProjectFile.snapshot_id == s.id)
        .order_by(ProjectFile.path)
        .offset(offset)
        .limit(limit)
    )
    count = db.scalar(
        select(func.count()).select_from(ProjectFile).where(ProjectFile.snapshot_id == s.id)
    )
    return {
        "total": count,
        "items": [
            {"id": f.id, "path": f.path, "language": f.language, "byte_size": f.byte_size}
            for f in rows
        ],
    }


@router.get("/projects/{project_id}/files/{file_id}")
def file_content(project_id: str, file_id: str, user=Depends(current_user), db=Depends(get_db)):
    p = owned(db, project_id, user)
    row = db.scalar(
        select(ProjectFile)
        .join(ProjectSnapshot)
        .where(ProjectFile.id == valid_id(file_id), ProjectSnapshot.project_id == p.id)
    )
    if not row:
        raise HTTPException(404, "File not found.")
    return {
        "id": row.id,
        "path": row.path,
        "content": row.content,
        "language": row.language,
        "snapshot_id": row.snapshot_id,
    }


@router.get("/projects/{project_id}/evidence")
def evidence(
    project_id: str,
    q: str = Query("", max_length=200),
    snapshot_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(current_user),
    db=Depends(get_db),
):
    s = snapshot_for(db, owned(db, project_id, user), snapshot_id)
    query = select(EvidenceChunk).where(EvidenceChunk.snapshot_id == s.id)
    if q:
        query = query.where(EvidenceChunk.path.contains(q, autoescape=True))
    rows = db.scalars(
        query.order_by(EvidenceChunk.path, EvidenceChunk.start_line).offset(offset).limit(limit)
    )
    return {"items": [evidence_dict(c, s) for c in rows]}


@router.get("/projects/{project_id}/claims")
def claims(
    project_id: str,
    status: str | None = Query(None, pattern="^(VERIFIED|INFERRED|UNVERIFIED|CONTRADICTED|STALE)$"),
    q: str = Query("", max_length=200),
    snapshot_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(current_user),
    db=Depends(get_db),
):
    s = snapshot_for(db, owned(db, project_id, user), snapshot_id)
    query = select(Claim).where(Claim.snapshot_id == s.id)
    if status:
        query = query.where(Claim.status == status)
    if q:
        query = query.where(Claim.text.icontains(q, autoescape=True))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = list(db.scalars(query.order_by(Claim.created_at, Claim.id).offset(offset).limit(limit)))
    return {"total": total, "items": claim_page(db, rows, s)}


@router.get("/projects/{project_id}/consistency")
def consistency(
    project_id: str,
    snapshot_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(current_user),
    db=Depends(get_db),
):
    s = snapshot_for(db, owned(db, project_id, user), snapshot_id)
    rows = db.scalars(
        select(ConsistencyFinding)
        .where(ConsistencyFinding.snapshot_id == s.id)
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": [
            {
                "id": f.id,
                "kind": f.kind,
                "recommendation": f.recommendation,
                "claim": claim_dict(db, db.get(Claim, f.claim_id), s),
            }
            for f in rows
        ]
    }


@router.post("/projects/{project_id}/ask", response_model=AnswerOut)
def question(project_id: str, body: AskQuestion, user=Depends(current_user), db=Depends(get_db)):
    s = snapshot_for(db, owned(db, project_id, user), body.snapshot_id)
    try:
        return ask(db, s, body.question, settings())
    except ProviderError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/projects/{project_id}/viva")
def viva_generate(
    project_id: str, body: VivaRequest, user=Depends(current_user), db=Depends(get_db)
):
    return viva(db, snapshot_for(db, owned(db, project_id, user)), body.difficulty)


@router.patch("/projects/{project_id}/viva/{question_id}")
def mark_revision(
    project_id: str,
    question_id: str,
    body: RevisionRequest,
    user=Depends(current_user),
    db=Depends(get_db),
):
    p = owned(db, project_id, user)
    row = db.scalar(
        select(VivaQuestion)
        .join(VivaSession)
        .join(ProjectSnapshot)
        .where(VivaQuestion.id == valid_id(question_id), ProjectSnapshot.project_id == p.id)
    )
    if not row:
        raise HTTPException(404, "Question not found.")
    row.revision = body.revision
    db.commit()
    return {"id": row.id, "revision": row.revision}


@router.post("/projects/{project_id}/documents")
def generate_document(
    project_id: str, body: DocumentRequest, user=Depends(current_user), db=Depends(get_db)
):
    p = owned(db, project_id, user)
    return document(db, snapshot_for(db, p), body.kind, p)


@router.get("/projects/{project_id}/documents")
def documents(
    project_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(current_user),
    db=Depends(get_db),
):
    p = owned(db, project_id, user)
    rows = db.scalars(
        select(GeneratedDocument)
        .join(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == p.id)
        .order_by(GeneratedDocument.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": [
            {
                "id": d.id,
                "kind": d.kind,
                "content": d.content,
                "snapshot_id": d.snapshot_id,
                "created_at": iso_time(d.created_at),
            }
            for d in rows
        ]
    }


@router.get("/projects/{project_id}/deployment-audit")
def deployment_audit(
    project_id: str, snapshot_id: str | None = None, user=Depends(current_user), db=Depends(get_db)
):
    s = snapshot_for(db, owned(db, project_id, user), snapshot_id)
    return {"items": s.summary["audit"], "limitations": s.summary["limitations"]}


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: str, body: DeleteRequest, user=Depends(current_user), db=Depends(get_db)
):
    p = owned(db, project_id, user)
    if body.confirmation != p.name:
        raise HTTPException(422, "Type the exact project name to confirm deletion.")
    active = db.scalar(
        select(AnalysisJob).where(
            AnalysisJob.project_id == p.id, AnalysisJob.state.in_(["QUEUED", "PROCESSING"])
        )
    )
    if active:
        raise HTTPException(409, "Wait for active analysis to finish before deleting this project.")
    paths = list(db.scalars(select(AnalysisJob.source_path).where(AnalysisJob.project_id == p.id)))
    db.execute(delete(Project).where(Project.id == p.id))
    db.commit()
    for value in paths:
        if value:
            path = Path(value).resolve()
            if path.parent == settings().storage_dir and path.suffix == ".zip":
                path.unlink(missing_ok=True)
    return {"ok": True}
