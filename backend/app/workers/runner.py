"""RQ in production; a separate durable single-process DB worker for native local demos."""

import time
from datetime import timedelta

from sqlalchemy import select, update

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import AnalysisJob, ProjectSnapshot, now
from app.services.analysis import analyze


def dispatch(job_id):
    config = settings()
    if config.queue_mode == "rq":
        from redis import Redis
        from rq import Queue

        Queue("analysis", connection=Redis.from_url(config.redis_url)).enqueue(
            "app.services.analysis.analyze",
            job_id,
            job_timeout=config.job_timeout_seconds,
            result_ttl=3600,
            failure_ttl=86400,
        )


def cleanup():
    config = settings()
    cutoff = now() - timedelta(hours=config.upload_retention_hours)
    with SessionLocal.begin() as db:
        jobs = db.scalars(
            select(AnalysisJob).where(
                AnalysisJob.created_at < cutoff,
                AnalysisJob.state.in_(["COMPLETED", "FAILED", "CANCELLED"]),
            )
        )
        for job in jobs:
            if job.source_path:
                path = __import__("pathlib").Path(job.source_path).resolve()
                if path.parent == config.storage_dir and path.suffix == ".zip":
                    path.unlink(missing_ok=True)
                    job.source_path = None
        expired = db.scalars(
            select(AnalysisJob).where(
                AnalysisJob.state == "PROCESSING",
                AnalysisJob.updated_at < now() - timedelta(seconds=config.job_timeout_seconds),
            )
        )
        for job in expired:
            job.state = "FAILED"
            job.error_type = "WorkerTimeout"
            job.error_summary = "The worker stopped responding. Retry this analysis."
            db.get(ProjectSnapshot, job.snapshot_id).status = "FAILED"


def local_worker():
    last_cleanup = 0
    while True:
        if time.monotonic() - last_cleanup > 60:
            cleanup()
            last_cleanup = time.monotonic()
        with SessionLocal.begin() as db:
            job_id = db.scalar(
                select(AnalysisJob.id)
                .where(AnalysisJob.state == "QUEUED")
                .order_by(AnalysisJob.created_at)
                .limit(1)
            )
            if job_id:
                changed = db.execute(
                    update(AnalysisJob)
                    .where(AnalysisJob.id == job_id, AnalysisJob.state == "QUEUED")
                    .values(state="PROCESSING", updated_at=now())
                ).rowcount
                if not changed:
                    job_id = None
        if job_id:
            analyze(job_id)
        else:
            time.sleep(0.5)


if __name__ == "__main__":
    if settings().queue_mode == "rq":
        import sys

        from redis import Redis
        from rq import Queue, SpawnWorker, Worker

        connection = Redis.from_url(settings().redis_url)
        worker_class = SpawnWorker if sys.platform == "win32" else Worker
        worker_class([Queue("analysis", connection=connection)], connection=connection).work()
    else:
        local_worker()
