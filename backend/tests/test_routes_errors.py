"""Route-level logging and error-handling tests.

The service providers are overridden with services whose collaborators are
mocked, so the HTTP boundary is exercised without a live Postgres/Redis. These
prove: expected domain exceptions translate to the right status + a single
structured WARNING; unexpected errors reach the global handler as a safe JSON
500 with no leaked internals; a low-frequency success emits an INFO log; and a
successful high-frequency telemetry ingest emits no INFO success log.
"""

import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.routes.agents import get_agent_service
from app.api.routes.telemetry import get_telemetry_service
from app.main import api
from app.services.agent import AgentService
from app.services.telemetry import TelemetryService

VALID_TELEMETRY = {"lat": 32.0, "lng": 34.8, "speed": 10.0, "battery": 50.0, "status": "idle"}


def _telemetry_row() -> SimpleNamespace:
    # Satisfies TelemetryRead (from_attributes) so the 201 response serializes.
    return SimpleNamespace(
        id=1,
        agent_id=5,
        lat=32.0,
        lng=34.8,
        speed=10.0,
        battery=50.0,
        status="idle",
        recorded_at=datetime.now(timezone.utc),
    )


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    api.dependency_overrides.clear()


def test_get_unknown_agent_returns_404_and_warns(caplog):
    api.dependency_overrides[get_agent_service] = lambda: AgentService(
        AsyncMock(), get_agent=AsyncMock(return_value=None)
    )

    with caplog.at_level(logging.WARNING, logger="app.api.routes.agents"):
        resp = TestClient(api).get("/api/agents/123")

    assert resp.status_code == 404
    assert resp.json() == {"detail": "Agent 123 not found"}
    assert [
        r
        for r in caplog.records
        if getattr(r, "event", None) == "agent.get.not_found"
        and getattr(r, "agent_id", None) == 123
        and r.levelno == logging.WARNING
    ]


def test_post_telemetry_unknown_agent_returns_404_and_warns(caplog):
    api.dependency_overrides[get_telemetry_service] = lambda: TelemetryService(
        AsyncMock(), get_agent=AsyncMock(return_value=None)
    )

    with caplog.at_level(logging.WARNING, logger="app.api.routes.telemetry"):
        resp = TestClient(api).post("/api/agents/99/telemetry", json=VALID_TELEMETRY)

    assert resp.status_code == 404
    assert resp.json() == {"detail": "Agent 99 not found"}
    assert [
        r
        for r in caplog.records
        if getattr(r, "event", None) == "telemetry.ingest.not_found"
        and getattr(r, "agent_id", None) == 99
        and r.levelno == logging.WARNING
    ]


def test_unexpected_exception_returns_safe_500_without_details():
    api.dependency_overrides[get_agent_service] = lambda: AgentService(
        AsyncMock(), list_agents=AsyncMock(side_effect=RuntimeError("db connection refused"))
    )

    client = TestClient(api, raise_server_exceptions=False)
    resp = client.get("/api/agents")

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal Server Error"}
    assert "db connection refused" not in resp.text
    assert "RuntimeError" not in resp.text


def test_list_current_state_success_logs_info(caplog):
    api.dependency_overrides[get_agent_service] = lambda: AgentService(
        AsyncMock(), list_agents=AsyncMock(return_value=[])
    )

    with caplog.at_level(logging.INFO, logger="app.api.routes.agents"):
        resp = TestClient(api).get("/api/agents/current-state")

    assert resp.status_code == 200
    assert resp.json() == []
    assert [
        r
        for r in caplog.records
        if getattr(r, "event", None) == "agent.current_state.completed"
        and getattr(r, "count", None) == 0
        and r.levelno == logging.INFO
    ]


def test_telemetry_success_emits_no_info_log(caplog):
    # High-frequency policy: a successful ingest must not produce an INFO success
    # log from either the telemetry route or the telemetry service.
    api.dependency_overrides[get_telemetry_service] = lambda: TelemetryService(
        AsyncMock(),
        get_agent=AsyncMock(return_value=object()),
        insert_telemetry=AsyncMock(return_value=_telemetry_row()),
        update_latest_state=AsyncMock(),
        emit_telemetry_updated=AsyncMock(),
        evaluate_telemetry_alerts=AsyncMock(return_value=[]),
    )

    with caplog.at_level(logging.INFO):
        resp = TestClient(api).post("/api/agents/5/telemetry", json=VALID_TELEMETRY)

    assert resp.status_code == 201
    noisy = [
        r
        for r in caplog.records
        if r.name in {"app.api.routes.telemetry", "app.services.telemetry"}
        and r.levelno >= logging.INFO
    ]
    assert noisy == []