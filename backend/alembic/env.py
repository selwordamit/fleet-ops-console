import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import settings
from app.db.base import Base


# Alembic's runtime config object.
# It reads static values from alembic.ini and lets us override them here.
config = context.config


# We do not store the database URL in alembic.ini.
# Instead, Alembic uses the same settings object as the application.
# This keeps one source of truth for the DB connection string.
config.set_main_option("sqlalchemy.url", settings.database_url)


# Load Alembic logging settings from alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Alembic uses this metadata for autogenerate.
# Future models like Agent, User, Telemetry, Alert, and Command
# will inherit from Base and register their tables here.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL migration output without connecting to the database.

    Used by:
        alembic upgrade head --sql
    """

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations using a real database connection.

    Alembic's migration execution is sync, so this function is called
    through connection.run_sync(...) from the async connection.
    """

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Connect to the database and apply migrations."""

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())