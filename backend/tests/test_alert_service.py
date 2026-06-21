"""Unit tests for AlertService.evaluate_low_battery.

All collaborators (session, repository functions) are injected as mocks so
these run without a live Postgres. Tests prove the four state transitions,
correct field values on trigger, timezone-aware timestamp on resolve, and
that the service never commits, rolls back, or refreshes.
"""

import asyncio
from datetime import timezone
from unittest.mock import AsyncMock, call

import pytest

from app.models.alert import Alert
from app.schemas.enums import AlertSeverity, AlertType
from app.services.alert import AlertChange, AlertService

AGENT_ID = 7
THRESHOLD = 15.0


def _make_service(
    *,
    get_active_alert,
    insert_alert=None,
    resolve_alert=None,
):
    """Return (AlertService, session) with collaborators injected."""
    session = AsyncMock()
    svc = AlertService(
        session,
        get_active_alert=get_active_alert,
        insert_alert=insert_alert if insert_alert is not None else AsyncMock(),
        resolve_alert=resolve_alert if resolve_alert is not None else AsyncMock(),
    )
    return svc, session


# ---------------------------------------------------------------------------
# Case 1 — no active alert, battery above threshold
# ---------------------------------------------------------------------------


def test_no_alert_battery_above_threshold_returns_none():
    svc, _ = _make_service(get_active_alert=AsyncMock(return_value=None))

    result = asyncio.run(svc.evaluate_low_battery(AGENT_ID, battery=20.0, threshold=THRESHOLD))

    assert result is None


def test_no_alert_battery_above_threshold_does_not_insert():
    insert_alert = AsyncMock()
    svc, _ = _make_service(
        get_active_alert=AsyncMock(return_value=None),
        insert_alert=insert_alert,
    )

    asyncio.run(svc.evaluate_low_battery(AGENT_ID, battery=20.0, threshold=THRESHOLD))

    insert_alert.assert_not_awaited()


# ---------------------------------------------------------------------------
# Case 2 — no active alert, battery below threshold
# ---------------------------------------------------------------------------


def test_no_alert_battery_below_threshold_returns_triggered():
    inserted = Alert(agent_id=AGENT_ID, alert_type=AlertType.low_battery)
    svc, _ = _make_service(
        get_active_alert=AsyncMock(return_value=None),
        insert_alert=AsyncMock(return_value=inserted),
    )

    result = asyncio.run(svc.evaluate_low_battery(AGENT_ID, battery=10.0, threshold=THRESHOLD))

    assert isinstance(result, AlertChange)
    assert result.kind == "triggered"
    assert result.alert is inserted


def test_trigger_passes_correct_fields_to_repository():
    inserted = Alert(agent_id=AGENT_ID, alert_type=AlertType.low_battery)
    insert_alert = AsyncMock(return_value=inserted)
    svc, session = _make_service(
        get_active_alert=AsyncMock(return_value=None),
        insert_alert=insert_alert,
    )

    asyncio.run(svc.evaluate_low_battery(AGENT_ID, battery=10.0, threshold=THRESHOLD))

    insert_alert.assert_awaited_once_with(
        session,
        agent_id=AGENT_ID,
        alert_type=AlertType.low_battery,
        severity=AlertSeverity.warning,
        value=10.0,
        threshold=THRESHOLD,
        message=f"Battery low: 10.0% below threshold {THRESHOLD}%",
    )


# ---------------------------------------------------------------------------
# Case 3 — active alert exists, battery still below threshold
# ---------------------------------------------------------------------------


def test_active_alert_battery_below_threshold_returns_none():
    active = Alert(agent_id=AGENT_ID, alert_type=AlertType.low_battery)
    svc, _ = _make_service(get_active_alert=AsyncMock(return_value=active))

    result = asyncio.run(svc.evaluate_low_battery(AGENT_ID, battery=10.0, threshold=THRESHOLD))

    assert result is None


def test_active_alert_battery_below_threshold_does_not_insert_duplicate():
    active = Alert(agent_id=AGENT_ID, alert_type=AlertType.low_battery)
    insert_alert = AsyncMock()
    svc, _ = _make_service(
        get_active_alert=AsyncMock(return_value=active),
        insert_alert=insert_alert,
    )

    asyncio.run(svc.evaluate_low_battery(AGENT_ID, battery=10.0, threshold=THRESHOLD))

    insert_alert.assert_not_awaited()


# ---------------------------------------------------------------------------
# Case 4 — active alert exists, battery recovered above threshold
# ---------------------------------------------------------------------------


def test_active_alert_battery_above_threshold_returns_resolved():
    active = Alert(agent_id=AGENT_ID, alert_type=AlertType.low_battery)
    resolved = Alert(agent_id=AGENT_ID, alert_type=AlertType.low_battery)
    svc, _ = _make_service(
        get_active_alert=AsyncMock(return_value=active),
        resolve_alert=AsyncMock(return_value=resolved),
    )

    result = asyncio.run(svc.evaluate_low_battery(AGENT_ID, battery=20.0, threshold=THRESHOLD))

    assert isinstance(result, AlertChange)
    assert result.kind == "resolved"
    assert result.alert is resolved


def test_active_alert_battery_above_threshold_does_not_insert():
    active = Alert(agent_id=AGENT_ID, alert_type=AlertType.low_battery)
    insert_alert = AsyncMock()
    svc, _ = _make_service(
        get_active_alert=AsyncMock(return_value=active),
        insert_alert=insert_alert,
        resolve_alert=AsyncMock(return_value=active),
    )

    asyncio.run(svc.evaluate_low_battery(AGENT_ID, battery=20.0, threshold=THRESHOLD))

    insert_alert.assert_not_awaited()


# ---------------------------------------------------------------------------
# Case 5 — battery exactly equal to threshold, no active alert
# ---------------------------------------------------------------------------


def test_no_alert_battery_equal_threshold_returns_none():
    svc, _ = _make_service(get_active_alert=AsyncMock(return_value=None))

    result = asyncio.run(svc.evaluate_low_battery(AGENT_ID, battery=THRESHOLD, threshold=THRESHOLD))

    assert result is None


# ---------------------------------------------------------------------------
# Case 6 — battery exactly equal to threshold, active alert exists
# ---------------------------------------------------------------------------


def test_active_alert_battery_equal_threshold_resolves():
    active = Alert(agent_id=AGENT_ID, alert_type=AlertType.low_battery)
    resolved = Alert(agent_id=AGENT_ID, alert_type=AlertType.low_battery)
    resolve_alert = AsyncMock(return_value=resolved)
    svc, _ = _make_service(
        get_active_alert=AsyncMock(return_value=active),
        resolve_alert=resolve_alert,
    )

    result = asyncio.run(svc.evaluate_low_battery(AGENT_ID, battery=THRESHOLD, threshold=THRESHOLD))

    assert isinstance(result, AlertChange)
    assert result.kind == "resolved"
    resolve_alert.assert_awaited_once()


# ---------------------------------------------------------------------------
# Case 8 — resolve uses a timezone-aware UTC datetime
# ---------------------------------------------------------------------------


def test_resolve_passes_timezone_aware_utc_timestamp():
    active = Alert(agent_id=AGENT_ID, alert_type=AlertType.low_battery)
    resolve_alert = AsyncMock(return_value=active)
    svc, session = _make_service(
        get_active_alert=AsyncMock(return_value=active),
        resolve_alert=resolve_alert,
    )

    asyncio.run(svc.evaluate_low_battery(AGENT_ID, battery=20.0, threshold=THRESHOLD))

    _, kwargs = resolve_alert.call_args
    resolved_at = kwargs["resolved_at"]
    assert resolved_at.tzinfo is not None
    assert resolved_at.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# Case 9 — service never commits, rolls back, refreshes, or touches Redis/sockets
# ---------------------------------------------------------------------------


def test_service_does_not_commit_rollback_or_refresh_on_trigger():
    inserted = Alert(agent_id=AGENT_ID, alert_type=AlertType.low_battery)
    svc, session = _make_service(
        get_active_alert=AsyncMock(return_value=None),
        insert_alert=AsyncMock(return_value=inserted),
    )

    asyncio.run(svc.evaluate_low_battery(AGENT_ID, battery=10.0, threshold=THRESHOLD))

    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
    session.refresh.assert_not_awaited()


def test_service_does_not_commit_rollback_or_refresh_on_resolve():
    active = Alert(agent_id=AGENT_ID, alert_type=AlertType.low_battery)
    svc, session = _make_service(
        get_active_alert=AsyncMock(return_value=active),
        resolve_alert=AsyncMock(return_value=active),
    )

    asyncio.run(svc.evaluate_low_battery(AGENT_ID, battery=20.0, threshold=THRESHOLD))

    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
    session.refresh.assert_not_awaited()