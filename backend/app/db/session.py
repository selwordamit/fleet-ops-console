from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


# The engine is the main database connection object.
# It owns the connection pool and should be created once per backend process,
# not inside every request.
engine = create_async_engine(settings.database_url)


# This factory creates AsyncSession objects.
# Each API request will later receive one session and use it to talk to PostgreSQL.
#
# expire_on_commit=False keeps model attributes available after commit,
# which is useful in async code after saving an object.
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    # FastAPI will use this function as a dependency later.
    # It opens a DB session, gives it to the request, and closes it automatically.
    async with async_session_factory() as session:
        yield session


async def check_db_connection() -> bool:
    # Simple live DB check.
    # If SELECT 1 succeeds, the backend can connect to PostgreSQL.
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    return True