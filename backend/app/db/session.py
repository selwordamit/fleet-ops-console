from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# One engine per process: it owns the connection pool, so it must be created once
# and shared, not per-request.
engine = create_async_engine(settings.database_url)

# Sessions are created from this factory. expire_on_commit=False keeps objects usable
# after commit, which matters for async code that reads attributes post-commit.
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    # Yields a session and guarantees it is closed even if the caller raises.
    # Shaped as a generator so it can be used directly as a FastAPI dependency later.
    async with async_session_factory() as session:
        yield session


async def check_db_connection() -> bool:
    # Minimal liveness probe: a successful SELECT 1 proves the engine can reach Postgres.
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
