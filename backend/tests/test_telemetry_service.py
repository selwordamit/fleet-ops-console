"""Unit tests for TelemetryService.ingest_telemetry orchestration and emit step.

Pure orchestration tests: every collaborator (agent lookup, Postgres insert,
alert evaluator, Redis mirror, Socket.IO emit) is injected into the service
constructor as a mock, so no live Postgres, Redis, or Socket.IO server is needed.
"""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.models.alert import Alert
from app.models.telemetry import Telemetry
from app.schemas.telemetry import TelemetryCreate
from app.services.alert import AlertChange
from app.services.telemetry import AgentNotFoundError, TelemetryService

_THRESHOLD = 15.0


@pytest.fixture
def mocks():
    """Success-path collaborators; individual tests override one to fail."""

    row = Telemetry(agent_id=7)

    return SimpleNamespace(
        row=row,
        session=AsyncMock(),
        payload=TelemetryCreate(lat=32.0, lng=34.8, speed=12.5, battery=80, status="en-route"),
        get_agent=AsyncMock(return_value=object()),
        insert_telemetry=AsyncMock(return_value=row),
        update_latest_state=AsyncMock(),
        emit=AsyncMock(),
        evaluate_telemetry_alerts=AsyncMock(return_value=[]),  # no alert changes by default
    )


def make_service(mocks, *, low_battery_threshold: float = _THRESHOLD) -> TelemetryService:
    """Construct the service with every collaborator injected (DI under test)."""

    return TelemetryService(
        mocks.session,
        get_agent=mocks.get_agent,
        insert_telemetry=mocks.insert_telemetry,
        update_latest_state=mocks.update_latest_state,
        emit_telemetry_updated=mocks.emit,
        evaluate_telemetry_alerts=mocks.evaluate_telemetry_alerts,
        low_battery_threshold=low_battery_threshold,
    )


# ---------------------------------------------------------------------------
# Existing orchestration tests (behaviour must not change)
# ---------------------------------------------------------------------------


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

    mocks.insert_telemetry.assert_awaited_once()
    mocks.emit.assert_not_awaited()


def test_emit_failure_is_best_effort_and_logs(mocks, caplog):
    mocks.emit.side_effect = RuntimeError("socket boom")

    with caplog.at_level(logging.WARNING, logger="app.services.telemetry"):
        result = asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    assert result is mocks.row
    mocks.emit.assert_awaited_once_with(mocks.row)
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


# ---------------------------------------------------------------------------
# Alert evaluation — called with correct keyword arguments
# ---------------------------------------------------------------------------


def test_evaluate_telemetry_alerts_called_with_correct_args(mocks):
    payload = TelemetryCreate(lat=32.0, lng=34.8, speed=10.0, battery=10.0, status="en-route")

    asyncio.run(make_service(mocks, low_battery_threshold=20.0).ingest_telemetry(7, payload))

    mocks.evaluate_telemetry_alerts.assert_awaited_once_with(
        mocks.session,
        agent_id=7,
        battery=10.0,
        low_battery_threshold=20.0,
    )


def test_evaluate_telemetry_alerts_uses_configured_threshold(mocks):
    asyncio.run(make_service(mocks, low_battery_threshold=25.0).ingest_telemetry(7, mocks.payload))

    kwargs = mocks.evaluate_telemetry_alerts.await_args.kwargs
    assert kwargs["low_battery_threshold"] == 25.0


# ---------------------------------------------------------------------------
# No alert changes — existing telemetry behaviour is unaffected
# ---------------------------------------------------------------------------


def test_no_alert_changes_telemetry_refreshed_once(mocks):
    mocks.evaluate_telemetry_alerts.return_value = []

    asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    mocks.session.refresh.assert_awaited_once_with(mocks.row)


def test_no_alert_changes_commit_and_emit_proceed(mocks):
    mocks.evaluate_telemetry_alerts.return_value = []

    asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    mocks.session.commit.assert_awaited_once()
    mocks.emit.assert_awaited_once_with(mocks.row)


# ---------------------------------------------------------------------------
# Single alert change — alert row refreshed after commit
# ---------------------------------------------------------------------------


def test_triggered_alert_change_refreshes_alert_row_after_commit(mocks):
    alert = Alert(agent_id=7)
    mocks.evaluate_telemetry_alerts.return_value = [AlertChange(kind="triggered", alert=alert)]

    asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    assert mocks.session.refresh.await_count == 2
    refreshed = [call.args[0] for call in mocks.session.refresh.await_args_list]
    assert mocks.row in refreshed
    assert alert in refreshed


def test_resolved_alert_change_refreshes_alert_row_after_commit(mocks):
    alert = Alert(agent_id=7)
    mocks.evaluate_telemetry_alerts.return_value = [AlertChange(kind="resolved", alert=alert)]

    asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    assert mocks.session.refresh.await_count == 2
    refreshed = [call.args[0] for call in mocks.session.refresh.await_args_list]
    assert alert in refreshed


def test_alert_refresh_happens_after_commit(mocks):
    alert = Alert(agent_id=7)
    mocks.evaluate_telemetry_alerts.return_value = [AlertChange(kind="triggered", alert=alert)]
    order = Mock()
    order.attach_mock(mocks.session.commit, "commit")
    order.attach_mock(mocks.session.refresh, "refresh")

    asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    names = [name for name, *_ in order.mock_calls]
    assert names.index("commit") < names.index("refresh")


# ---------------------------------------------------------------------------
# Multiple alert changes — each alert row refreshed
# ---------------------------------------------------------------------------


def test_multiple_alert_changes_each_refreshed_after_commit(mocks):
    alert_a = Alert(agent_id=7)
    alert_b = Alert(agent_id=7)
    mocks.evaluate_telemetry_alerts.return_value = [
        AlertChange(kind="triggered", alert=alert_a),
        AlertChange(kind="resolved", alert=alert_b),
    ]

    asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    # telemetry + alert_a + alert_b = 3 refresh calls
    assert mocks.session.refresh.await_count == 3
    refreshed = [call.args[0] for call in mocks.session.refresh.await_args_list]
    assert mocks.row in refreshed
    assert alert_a in refreshed
    assert alert_b in refreshed


# ---------------------------------------------------------------------------
# Alert evaluation failure before commit — rollback, exception propagates
# ---------------------------------------------------------------------------


def test_alert_evaluation_sqlalchemy_error_triggers_rollback(mocks):
    mocks.evaluate_telemetry_alerts.side_effect = SQLAlchemyError("db error during alert eval")

    with pytest.raises(SQLAlchemyError):
        asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    mocks.session.commit.assert_not_awaited()
    mocks.session.rollback.assert_awaited_once()


def test_alert_evaluation_sqlalchemy_error_skips_redis_and_emit(mocks):
    mocks.evaluate_telemetry_alerts.side_effect = SQLAlchemyError("db error during alert eval")

    with pytest.raises(SQLAlchemyError):
        asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    mocks.update_latest_state.assert_not_awaited()
    mocks.emit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Service-level scenarios (orchestration shape for trigger / no-op / resolve)
# ---------------------------------------------------------------------------


def test_battery_below_threshold_alert_change_is_refreshed(mocks):
    alert = Alert(agent_id=7)
    mocks.evaluate_telemetry_alerts.return_value = [AlertChange(kind="triggered", alert=alert)]

    asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    refreshed = [call.args[0] for call in mocks.session.refresh.await_args_list]
    assert alert in refreshed


def test_no_alert_change_only_telemetry_refreshed(mocks):
    mocks.evaluate_telemetry_alerts.return_value = []

    asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    mocks.session.refresh.assert_awaited_once_with(mocks.row)


def test_battery_recovery_resolved_alert_is_refreshed(mocks):
    alert = Alert(agent_id=7)
    mocks.evaluate_telemetry_alerts.return_value = [AlertChange(kind="resolved", alert=alert)]

    asyncio.run(make_service(mocks).ingest_telemetry(7, mocks.payload))

    refreshed = [call.args[0] for call in mocks.session.refresh.await_args_list]
    assert alert in refreshed
