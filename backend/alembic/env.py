# ======================================================================================
# ALEMBIC ENV.PY | The Migration Engine & Database Bridge
# ======================================================================================
# This script runs automatically whenever an 'alembic' CLI command is executed.
#
# Core Responsibilities:
# 1. Single Source of Truth: Dynamically injects 'settings.database_url' from the 
#    app's core config into Alembic, preventing hardcoded credentials in source control.
# 2. Autogenerate Target: Connects 'Base.metadata' to Alembic so it can automatically
#    detect changes in your SQLAlchemy models (e.g., Vehicles, Agents).
# 3. Async/Sync Wrapper: Adapts Alembic's native synchronous execution to work seamlessly
#    with the project's asyncpg driver using SQLAlchemy's 'connection.run_sync()' tool.
# ======================================================================================

import asyncio  # Runs the async Alembic migration flow inside an event loop.

from logging.config import fileConfig  # Loads Alembic logging settings from alembic.ini.

from sqlalchemy import pool  # Lets us disable connection pooling during migrations.
from sqlalchemy.ext.asyncio import async_engine_from_config  # Builds an async SQLAlchemy engine from Alembic config.

from alembic import context  # Alembic runtime object used to configure and run migrations.

from app.core.config import settings  # App settings; used to read the database URL from one source of truth.
from app.db.base import Base  # Shared ORM Base; Alembic reads Base.metadata to detect model/table changes.


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

# Used to run migrations without DB connection
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