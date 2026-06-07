import inspect  # Helps us check what kind of function we have: async, generator, etc.

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.session import (
    async_session_factory,
    check_db_connection,
    engine,
    get_db_session,
)


def test_engine_is_async():
    # Checks that our database engine is async.
    # This is important because FastAPI works very well with async code.
    assert isinstance(engine, AsyncEngine)


def test_session_factory_builds_async_sessions():
    # Checks that our session factory creates async database sessions.
    assert isinstance(async_session_factory, async_sessionmaker)
    assert async_session_factory.class_ is AsyncSession


def test_get_db_session_is_async_generator():
    # Checks that get_db_session is built in the correct way for FastAPI.
    # It should give a DB session to the request, and close it after the request ends.
    assert inspect.isasyncgenfunction(get_db_session)


def test_check_db_connection_is_coroutine():
    # Checks that check_db_connection is an async function.
    # Because connecting to a database is I/O work, we need to await it.
    assert inspect.iscoroutinefunction(check_db_connection)