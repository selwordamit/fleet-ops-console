import inspect

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.session import (
    async_session_factory,
    check_db_connection,
    engine,
    get_db_session,
)


def test_engine_is_async():
    # Verifies that we created an async SQLAlchemy engine,
    # not a regular synchronous engine.
    assert isinstance(engine, AsyncEngine)


def test_session_factory_builds_async_sessions():
    # Verifies that the session factory is the async SQLAlchemy factory.
    assert isinstance(async_session_factory, async_sessionmaker)

    # Verifies that every session created by the factory will be AsyncSession.
    assert async_session_factory.class_ is AsyncSession


def test_get_db_session_is_async_generator():
    # FastAPI dependencies that open/close resources should use async generator + yield.
    assert inspect.isasyncgenfunction(get_db_session)


def test_check_db_connection_is_coroutine():
    # check_db_connection performs async DB I/O, so it must be an async function.
    assert inspect.iscoroutinefunction(check_db_connection)