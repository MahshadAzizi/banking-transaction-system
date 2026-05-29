import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.

# Interpret the config file for Python logging.
# This line sets up loggers basically.
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from src.infrastructure.database.engine import Base  # noqa: E402
from src.adapters.outbound.persistence.models import (
    AccountORM,
    TransactionORM,
    OutboxMessageORM,
)  # noqa: F401, E402

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url() -> str:
    from src.infrastructure.config.settings import get_settings

    return get_settings().database.url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Compare server defaults so Alembic detects func.now() changes
        compare_server_default=True,
        # Include schemas if you use multiple PostgreSQL schemas
        include_schemas=False,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_server_default=True,
        # compare_type=True tells Alembic to detect column type changes
        # e.g. String(64) → String(128) — generates ALTER COLUMN
        compare_type=True,
        include_schemas=False,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    WHY async engine here:
    Your application uses asyncpg (async PostgreSQL driver).
    Alembic historically used sync engines only. The async_engine_from_config
    wrapper lets Alembic run migrations through the same async driver
    that your application uses — consistent behavior, no sync/async mismatch.
    """
    # Override the sqlalchemy.url from alembic.ini with our settings URL
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        # NullPool: migrations are one-shot operations, not long-lived servers.
        # NullPool creates a connection, uses it, closes it — no pooling.
        # Avoids leaving open connections after migration finishes.
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
