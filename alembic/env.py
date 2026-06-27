import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from jobplatform.config import settings
from jobplatform.database import Base
import jobplatform.auth.models  # noqa: F401 — registers User with Base.metadata
import jobplatform.profiles.models  # noqa: F401 — registers Profile with Base.metadata
import jobplatform.preferences.models  # noqa: F401 — registers JobPreferences with Base.metadata
import jobplatform.resumes.models  # noqa: F401 — registers Resume with Base.metadata
import jobplatform.jobs.models  # noqa: F401 — registers Job with Base.metadata
import jobplatform.matching.models  # noqa: F401 — registers JobMatch with Base.metadata
import jobplatform.applications.models  # noqa: F401 — registers Application with Base.metadata

_db_url = os.environ.get("DATABASE_URL", settings.database_url)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=_db_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(_db_url)
    async with connectable.connect() as connection:
        def configure(conn):
            from pgvector.sqlalchemy import Vector
            conn.dialect.ischema_names["vector"] = Vector
            context.configure(conn, target_metadata=target_metadata)
        await connection.run_sync(configure)
        async with connection.begin():
            await connection.run_sync(lambda _: context.run_migrations())
    await connectable.dispose()


def run() -> None:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        asyncio.run(run_migrations_online())


run()
