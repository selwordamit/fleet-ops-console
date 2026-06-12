"""Unit tests for ingest_telemetry orchestration and its Socket.IO emit step.

These are pure orchestration tests: every external dependency (agent lookup,
Postgres insert, Redis mirror, Socket.IO emit) is mocked, so no live Postgres,
Redis, or Socket.IO server is needed. Dependencies are patched on
app.services.telemetry because ingest_telemetry calls them via names bound into
that module, not where they were originally defined.
"""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import app.services.telemetry as svc
from app.models.telemetry import Telemetry
from app.schemas.telemetry import TelemetryCreate


@pytest.fixture
def mocks(monkeypatch):
    """Patch all of ingest_telemetry's collaborators with success defaults.

    Individual tests override a single mock (e.g. make Redis raise) to exercise
    one failure path at a time.
    """

    row = Telemetry(agent_id=7)

    get_agent = AsyncMock(return_value=object())          # non-None => agent exists
    insert_telemetry = AsyncMock(return_value=row)
    update_latest_state = AsyncMock()                     # stands in for the Redis write
    emit = AsyncMock()

    monkeypatch.setattr(svc, "get_agent", get_agent)
    monkeypatch.setattr(svc, "insert_telemetry", insert_telemetry)
    monkeypatch.setattr(svc, "_update_latest_state", update_latest_state)
    monkeypatch.setattr(svc, "emit_agent_telemetry_updated", emit)

    return SimpleNamespace(
        row=row,
        session=AsyncMock(),                              # commit()/refresh() are awaitable no-ops
        payload=TelemetryCreate(lat=32.0, lng=34.8, speed=12.5, battery=80, status="en-route"),
        get_agent=get_agent,
        insert_telemetry=insert_telemetry,
        update_latest_state=update_latest_state,
        emit=emit,
    )


def test_successful_ingestion_emits_once_with_persisted_row(mocks):
    # Record relative call order to prove the emit happens after the Redis step.
    order = Mock()
    order.attach_mock(mocks.update_latest_state, "redis")
    order.attach_mock(mocks.emit, "emit")

    result = asyncio.run(svc.ingest_telemetry(mocks.session, 7, mocks.payload))

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
        asyncio.run(svc.ingest_telemetry(mocks.session, 7, mocks.payload))

    # Persistence happened, but the event must not fire on un-mirrored state.
    mocks.insert_telemetry.assert_awaited_once()
    mocks.emit.assert_not_awaited()


def test_emit_failure_is_best_effort_and_logs(mocks, caplog):
    mocks.emit.side_effect = RuntimeError("socket boom")

    with caplog.at_level(logging.WARNING, logger="app.services.telemetry"):
        result = asyncio.run(svc.ingest_telemetry(mocks.session, 7, mocks.payload))

    # Persistence already succeeded, so ingestion still returns the stored row.
    assert result is mocks.row
    mocks.emit.assert_awaited_once_with(mocks.row)
    assert "agent_id=7" in caplog.text
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_unknown_agent_raises_before_any_side_effects(mocks):
    mocks.get_agent.return_value = None

    with pytest.raises(svc.AgentNotFoundError):
        asyncio.run(svc.ingest_telemetry(mocks.session, 7, mocks.payload))

    mocks.insert_telemetry.assert_not_awaited()
    mocks.update_latest_state.assert_not_awaited()
    mocks.emit.assert_not_awaited()