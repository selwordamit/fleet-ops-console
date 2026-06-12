from collections.abc import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(settings.database_url)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False, #Lets us return the rows in the Service layer
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:

    async with async_session_factory() as session:
        yield session



async def check_db_connection() -> bool:

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
