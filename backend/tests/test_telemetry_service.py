"""Unit tests for TelemetryService.ingest_telemetry orchestration and emit step.

Pure orchestration tests: every collaborator (agent lookup, Postgres insert,
Redis mirror, Socket.IO emit) is injected into the service constructor as a
mock, so no live Postgres, Redis, or Socket.IO server is needed. Building the
service this way also proves its dependencies are constructor-injectable.
"""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.models.telemetry import Telemetry
from app.schemas.telemetry import TelemetryCreate
from app.services.telemetry import AgentNotFoundError, TelemetryService


@pytest.fixture
def mocks():
    """Success-path collaborators; individual tests override one to fail."""

    row = Telemetry(agent_id=7)

    return SimpleNamespace(
        row=row,
        session=AsyncMock(),                              # commit()/refresh() are awaitable no-ops
        payload=TelemetryCreate(lat=32.0, lng=34.8, speed=12.5, battery=80, status="en-route"),
        get_agent=AsyncMock(return_value=object()),      # non-None => agent exists
        insert_telemetry=AsyncMock(return_value=row),
        update_latest_state=AsyncMock(),                 # stands in for the Redis write
        emit=AsyncMock(),
    )


def make_service(mocks) -> TelemetryService:
    """Construct the service with every collaborator injected (DI under test)."""

    return TelemetryService(
        mocks.session,
        get_agent=mocks.get_agent,
        insert_telemetry=mocks.insert_telemetry,
        update_latest_state=mocks.update_latest_state,
        emit_telemetry_updated=mocks.emit,
    )


def test_successful_ingestion_emits_once_with_persisted_row(mocks):
    # Record relative call order to prove the emit happens after the Redis step.
    order = Mock()
    order.attach_mock(mocks.update_latest_state, "redis")
    order.attach_mock(mocks.emit, "emit")

    result = asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    assert result is mocks.row
    mocks.insert_telemetry.assert_awaited_once()
    mocks.session.commit.assert_awaited_once()
    mocks.session.refresh.assert_awaited_once_with(mocks.row)
    mocks.update_latest_state.assert_awaited_once_with(mocks.row)
    mocks.emit.assert_awaited_once_with(mocks.row)
    assert [name for name, *_ in order.mock_calls] == ["redis", "emit"]


def test_redis_failure_propagates_and_skips_emit(mocks):
    mocks.update_latest_state.side_effect = RuntimeError("redis down")

    with pytest.raises(RuntimeError, match="redis down"):
        asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    # Persistence happened, but the event must not fire on un-mirrored state.
    mocks.insert_telemetry.assert_awaited_once()
    mocks.emit.assert_not_awaited()


def test_emit_failure_is_best_effort_and_logs(mocks, caplog):
    mocks.emit.side_effect = RuntimeError("socket boom")

    with caplog.at_level(logging.WARNING, logger="app.services.telemetry"):
        result = asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    # Persistence already succeeded, so ingestion still returns the stored row.
    assert result is mocks.row
    mocks.emit.assert_awaited_once_with(mocks.row)
    # Structured WARNING carrying the event name and agent_id, logged exactly once.
    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and getattr(r, "event", None) == "agent.telemetry.updated"
        and getattr(r, "agent_id", None) == 7
    ]
    assert len(warnings) == 1


def test_unknown_agent_raises_before_any_side_effects(mocks):
    mocks.get_agent.return_value = None

    with pytest.raises(AgentNotFoundError):
        asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    mocks.insert_telemetry.assert_not_awaited()
    mocks.update_latest_state.assert_not_awaited()
    mocks.emit.assert_not_awaited()
