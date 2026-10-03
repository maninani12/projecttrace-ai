"""Only one active analysis per project, including concurrent import requests."""

import sqlalchemy as sa

from alembic import op

revision = "20261003_job_guard"
down_revision = "4af2c5fa80d1"
branch_labels = None
depends_on = None


def upgrade():
    condition = sa.text("state IN ('QUEUED', 'PROCESSING')")
    op.create_index(
        "uq_jobs_active_project",
        "jobs",
        ["project_id"],
        unique=True,
        sqlite_where=condition,
        postgresql_where=condition,
    )


def downgrade():
    op.drop_index("uq_jobs_active_project", table_name="jobs")
