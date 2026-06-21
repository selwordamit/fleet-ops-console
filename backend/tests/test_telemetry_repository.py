"""Unit tests for the telemetry repository.

All collaborators (AsyncSession) are injected as mocks so these run without a
live Postgres. Tests cover the new get_latest_telemetry_for_agent function and
confirm it follows project conventions (no commit, rollback, or refresh).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.models.telemetry import Telemetry
from app.repositories.telemetry import get_latest_telemetry_for_agent


def _scalars_result(items: list) -> MagicMock:
    result = MagicMock()
    result.first.return_value = items[0] if items else None
    result.__iter__ = MagicMock(side_effect=lambda: iter(items))
    return result


def test_get_latest_telemetry_returns_most_recent_row():
    row = Telemetry(agent_id=1)
    session = AsyncMock()
    session.scalars.return_value = _scalars_result([row])

    result = asyncio.run(get_latest_telemetry_for_agent(session, agent_id=1))

    assert result is row
    session.scalars.assert_awaited_once()


def test_get_latest_telemetry_returns_none_when_no_history():
    session = AsyncMock()
    session.scalars.return_value = _scalars_result([])

    result = asyncio.run(get_latest_telemetry_for_agent(session, agent_id=99))

    assert result is None


def test_get_latest_telemetry_does_not_commit_rollback_or_refresh():
    session = AsyncMock()
    session.scalars.return_value = _scalars_result([])

    asyncio.run(get_latest_telemetry_for_agent(session, agent_id=1))

    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
    session.refresh.assert_not_awaited()
