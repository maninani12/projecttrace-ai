from sqlalchemy import create_engine, pool

from alembic import context
from app import models  # noqa: F401
from app.core.config import settings
from app.core.db import Base

target_metadata = Base.metadata


def run():
    url = settings().database_url
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = create_engine(url, poolclass=pool.NullPool)
        with engine.connect() as conn:
            context.configure(connection=conn, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()


run()
