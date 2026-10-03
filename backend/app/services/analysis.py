import hashlib
import logging
from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import (
    AnalysisJob,
    Artifact,
    EvidenceChunk,
    Project,
    ProjectFile,
    ProjectSnapshot,
    now,
)
from app.parsers.archive import ArchiveError, read_archive
from app.parsers.source import chunk_file, code_metadata, detect
from app.retrieval.engine import embedder
from app.services.audit import audit
from app.services.claims import build_claims
from app.services.github import GitHubError, download_repository

log = logging.getLogger("projecttrace.analysis")


def stage(job_id, message):
    with SessionLocal.begin() as db:
        job = db.get(AnalysisJob, job_id)
        if job is None or job.state == "CANCELLED":
            raise ArchiveError("The analysis was cancelled.")
        job.stage = message
        job.updated_at = now()


def analyze(job_id):
    config = settings()
    with SessionLocal.begin() as db:
        job = db.get(AnalysisJob, job_id)
        if not job or job.state not in {"QUEUED", "PROCESSING"}:
            return
        job.state = "PROCESSING"
        job.stage = "Validating files"
        source_path, source_url, snapshot_id = job.source_path, job.source_url, job.snapshot_id
    try:
        branch = None
        sha = None
        if source_url:
            stage(job_id, "Retrieving public repository")
            path = config.storage_dir / (job_id + ".zip")
            path.parent.mkdir(parents=True, exist_ok=True)
            branch, sha = download_repository(source_url, path, config)
            with SessionLocal.begin() as db:
                db.get(AnalysisJob, job_id).source_path = str(path)
        else:
            path = Path(source_path)
        if sha is None:
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                while block := handle.read(1024 * 1024):
                    digest.update(block)
            sha = digest.hexdigest()
        stage(job_id, "Filtering sensitive values")
        files = list(read_archive(path, config))
        if not files:
            raise ArchiveError("No supported UTF-8 text files were found in this archive.")
        stage(job_id, "Detecting technologies")
        stack = detect(files)
        metadata = {f.path: code_metadata(f) for f in files}
        routes = [{"file": path, **r} for path, data in metadata.items() for r in data["routes"]]
        secret_findings = [
            {"path": f.path, "count": f.secrets, "value": "REDACTED"} for f in files if f.secrets
        ]
        stage(job_id, "Building evidence index")
        embedding = embedder(config.embedding_model)
        # Derived evidence and latest-snapshot pointer are committed atomically.
        with SessionLocal.begin() as db:
            snapshot = db.get(ProjectSnapshot, snapshot_id)
            project = db.get(Project, snapshot.project_id)
            previous_id = project.latest_snapshot_id
            snapshot.commit_sha = sha
            snapshot.branch = branch
            chunks = []
            for file in files:
                row = ProjectFile(
                    snapshot_id=snapshot.id,
                    path=file.path,
                    language=file.language,
                    content=file.content,
                    byte_size=file.size,
                    sha256=file.sha256,
                )
                db.add(row)
                db.flush()
                is_document = file.language in {"Markdown", "Text"}
                if file.path.lower().split("/")[-1].startswith("readme"):
                    db.add(Artifact(snapshot_id=snapshot.id, file_id=row.id, kind="README"))
                sections = list(chunk_file(file.content))
                if len(chunks) + len(sections) > config.max_chunks:
                    raise ArchiveError("Evidence exceeds the configured chunk count limit.")
                vectors = embedding.encode([s[2] for s in sections]) if sections else []
                for (start, end, text), vector in zip(sections, vectors, strict=True):
                    chunk = EvidenceChunk(
                        snapshot_id=snapshot.id,
                        file_id=row.id,
                        path=file.path,
                        start_line=start,
                        end_line=end,
                        content=text,
                        chunk_type="documentation" if is_document else "code",
                        embedding=vector.tolist(),
                        embedding_model=embedding.name,
                    )
                    db.add(chunk)
                    chunks.append(chunk)
            db.flush()
            claims = build_claims(db, snapshot, files, chunks, stack, previous_id)
            snapshot.summary = {
                "stack": stack,
                "file_count": len(files),
                "chunk_count": len(chunks),
                "claim_counts": dict(Counter(c.status for c in claims)),
                "languages": dict(Counter(f.language for f in files)),
                "secrets": secret_findings,
                "routes": routes,
                "metadata": metadata,
                "audit": audit(files, secret_findings, routes),
                "embedding_model": embedding.name,
                "limitations": [
                    "Static inspection only; no uploaded code or tests were executed.",
                    "Heuristic technology and claim detection can miss unfamiliar frameworks or complex behavior.",
                    "Binary files and unsupported encodings are omitted. No runtime/deployment claims are verified.",
                ],
            }
            snapshot.analyzed_at = now()
            snapshot.status = "COMPLETED"
            project.latest_snapshot_id = snapshot.id
            job = db.get(AnalysisJob, job_id)
            job.state = "COMPLETED"
            job.stage = "Analysis complete"
            job.error_type = None
            job.error_summary = None
        log.info("analysis_completed", extra={"job_id": job_id, "snapshot_id": snapshot_id})
    except Exception as exc:
        known = isinstance(exc, (ArchiveError, GitHubError))
        with SessionLocal.begin() as db:
            job = db.get(AnalysisJob, job_id)
            if job:
                job.state = "FAILED"
                job.stage = "Analysis failed"
                job.error_type = type(exc).__name__
                job.error_summary = (
                    str(exc)
                    if known
                    else "Analysis failed. Check service configuration, then retry."
                )
                db.get(ProjectSnapshot, snapshot_id).status = "FAILED"
        # Never include exception values: they may contain credentials or imported content.
        log.error("analysis_failed", extra={"job_id": job_id, "error_type": type(exc).__name__})
