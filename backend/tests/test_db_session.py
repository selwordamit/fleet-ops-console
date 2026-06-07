import inspect

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.session import (
    async_session_factory,
    check_db_connection,
    engine,
    get_db_session,
)


def test_engine_is_async():
    assert isinstance(engine, AsyncEngine)


def test_session_factory_builds_async_sessions():
    assert isinstance(async_session_factory, async_sessionmaker)
    assert async_session_factory.class_ is AsyncSession


def test_get_db_session_is_async_generator():
    # FastAPI dependencies that manage a resource must be async generators.
    assert inspect.isasyncgenfunction(get_db_session)


def test_check_db_connection_is_coroutine():
    assert inspect.iscoroutinefunction(check_db_connection)
