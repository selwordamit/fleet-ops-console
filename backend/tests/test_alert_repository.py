"""Unit tests for the alert repository.

All collaborators (AsyncSession) are injected as mocks so these run without
a live Postgres. Tests lock in that the repository flushes staged writes but
does NOT commit, rollback, or refresh — the service owns the transaction.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.alert import Alert
from app.repositories.alert import (
    get_active_alert,
    insert_alert,
    list_active_alerts,
    resolve_alert,
)
from app.schemas.enums import AlertSeverity, AlertType


def _scalars_result(items: list) -> MagicMock:
    """Return a mock that mimics the ScalarResult returned by session.scalars()."""
    result = MagicMock()
    result.first.return_value = items[0] if items else None
    result.__iter__ = MagicMock(side_effect=lambda: iter(items))
    return result


def _session() -> AsyncMock:
    """AsyncSession mock with session.add() as a plain MagicMock.

    session.add() is synchronous in SQLAlchemy; leaving it as an AsyncMock
    causes a RuntimeWarning about an unawaited coroutine.
    """
    session = AsyncMock()
    session.add = MagicMock()
    return session


# ---------------------------------------------------------------------------
# get_active_alert
# ---------------------------------------------------------------------------


def test_get_active_alert_returns_matching_alert():
    alert = Alert(agent_id=1, alert_type=AlertType.low_battery)
    session = _session()
    session.scalars.return_value = _scalars_result([alert])

    result = asyncio.run(
        get_active_alert(session, agent_id=1, alert_type=AlertType.low_battery)
    )

    assert result is alert
    session.scalars.assert_awaited_once()


def test_get_active_alert_returns_none_when_not_found():
    session = _session()
    session.scalars.return_value = _scalars_result([])

    result = asyncio.run(
        get_active_alert(session, agent_id=99, alert_type=AlertType.low_battery)
    )

    assert result is None


def test_get_active_alert_issues_a_query():
    """Verify the repo issues a scalars() query (WHERE clauses are built at
    query-construction time; their correctness is covered by integration tests)."""
    session = _session()
    session.scalars.return_value = _scalars_result([])

    asyncio.run(get_active_alert(session, agent_id=5, alert_type=AlertType.low_battery))

    session.scalars.assert_awaited_once()


def test_get_active_alert_does_not_commit_or_flush():
    session = _session()
    session.scalars.return_value = _scalars_result([])

    asyncio.run(get_active_alert(session, agent_id=1, alert_type=AlertType.low_battery))

    session.commit.assert_not_awaited()
    session.flush.assert_not_awaited()


# ---------------------------------------------------------------------------
# insert_alert
# ---------------------------------------------------------------------------


def test_insert_alert_creates_row_with_correct_fields():
    session = _session()

    result = asyncio.run(
        insert_alert(
            session,
            agent_id=3,
            alert_type=AlertType.low_battery,
            severity=AlertSeverity.warning,
            value=10.0,
            threshold=15.0,
            message="Battery low",
        )
    )

    assert result.agent_id == 3
    assert result.alert_type == AlertType.low_battery
    assert result.severity == AlertSeverity.warning
    assert result.value == 10.0
    assert result.threshold == 15.0
    assert result.message == "Battery low"


def test_insert_alert_calls_add_then_flush():
    session = _session()

    result = asyncio.run(
        insert_alert(
            session,
            agent_id=3,
            alert_type=AlertType.low_battery,
            severity=AlertSeverity.warning,
            value=10.0,
            threshold=15.0,
            message="Battery low",
        )
    )

    session.add.assert_called_once_with(result)
    session.flush.assert_awaited_once()


def test_insert_alert_does_not_commit_rollback_or_refresh():
    session = _session()

    asyncio.run(
        insert_alert(
            session,
            agent_id=3,
            alert_type=AlertType.low_battery,
            severity=AlertSeverity.warning,
            value=10.0,
            threshold=15.0,
            message="Battery low",
        )
    )

    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
    session.refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# resolve_alert
# ---------------------------------------------------------------------------


def test_resolve_alert_sets_timezone_aware_timestamp():
    alert = Alert(agent_id=1, alert_type=AlertType.low_battery)
    ts = datetime(2026, 6, 20, 12, 0, 0, tzinfo=timezone.utc)
    session = _session()

    result = asyncio.run(resolve_alert(session, alert=alert, resolved_at=ts))

    assert result.resolved_at == ts


def test_resolve_alert_returns_same_alert_object():
    alert = Alert(agent_id=1, alert_type=AlertType.low_battery)
    ts = datetime(2026, 6, 20, 12, 0, 0, tzinfo=timezone.utc)
    session = _session()

    result = asyncio.run(resolve_alert(session, alert=alert, resolved_at=ts))

    assert result is alert


def test_resolve_alert_calls_flush():
    alert = Alert(agent_id=1, alert_type=AlertType.low_battery)
    ts = datetime(2026, 6, 20, 12, 0, 0, tzinfo=timezone.utc)
    session = _session()

    asyncio.run(resolve_alert(session, alert=alert, resolved_at=ts))

    session.flush.assert_awaited_once()


def test_resolve_alert_does_not_commit_rollback_or_refresh():
    alert = Alert(agent_id=1, alert_type=AlertType.low_battery)
    ts = datetime(2026, 6, 20, 12, 0, 0, tzinfo=timezone.utc)
    session = _session()

    asyncio.run(resolve_alert(session, alert=alert, resolved_at=ts))

    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
    session.refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# list_active_alerts
# ---------------------------------------------------------------------------


def test_list_active_alerts_returns_unresolved_alerts():
    active = Alert(agent_id=1, alert_type=AlertType.low_battery)
    session = _session()
    session.scalars.return_value = _scalars_result([active])

    result = asyncio.run(list_active_alerts(session))

    assert active in result
    session.scalars.assert_awaited_once()


def test_list_active_alerts_preserves_order_from_query():
    """The repository issues a single ORDER BY query; results come back in the
    order the DB returns them. We prove the repo does not re-sort client-side."""
    newer = Alert(agent_id=2, alert_type=AlertType.low_battery)
    older = Alert(agent_id=1, alert_type=AlertType.low_battery)
    session = _session()
    session.scalars.return_value = _scalars_result([newer, older])

    result = asyncio.run(list_active_alerts(session))

    assert result == [newer, older]


def test_list_active_alerts_returns_empty_list_when_none_active():
    session = _session()
    session.scalars.return_value = _scalars_result([])

    result = asyncio.run(list_active_alerts(session))

    assert result == []


def test_list_active_alerts_does_not_commit_or_flush():
    session = _session()
    session.scalars.return_value = _scalars_result([])

    asyncio.run(list_active_alerts(session))

    session.commit.assert_not_awaited()
    session.flush.assert_not_awaited()
