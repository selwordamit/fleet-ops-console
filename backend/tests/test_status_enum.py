import pytest
from pydantic import ValidationError

from app.schemas.agent import AgentCreate
from app.schemas.enums import AgentStatus
from app.schemas.telemetry import TelemetryCreate

VALID_STATUSES = ["idle", "en-route", "stopped", "offline"]


def _agent(status):
    return AgentCreate(name="Truck 1", type="truck", status=status)


def _telemetry(status):
    return TelemetryCreate(lat=32.0, lng=34.8, speed=12.5, battery=80, status=status)


def test_enum_members_cover_allowed_statuses():
    assert {s.value for s in AgentStatus} == set(VALID_STATUSES)


@pytest.mark.parametrize("status", VALID_STATUSES)
def test_agent_accepts_valid_status(status):
    # use_enum_values=True means the validated value is the plain string.
    assert _agent(status).status == status


@pytest.mark.parametrize("status", VALID_STATUSES)
def test_telemetry_accepts_valid_status(status):
    assert _telemetry(status).status == status


@pytest.mark.parametrize("status", ["", "moving", "EN-ROUTE", "en_route", "active", "idle "])
def test_agent_rejects_invalid_status(status):
    with pytest.raises(ValidationError):
        _agent(status)


@pytest.mark.parametrize("status", ["", "moving", "EN-ROUTE", "en_route", "active"])
def test_telemetry_rejects_invalid_status(status):
    with pytest.raises(ValidationError):
        _telemetry(status)


def test_en_route_hyphen_value_round_trips():
    # The member identifier is en_route, but the accepted/stored value is "en-route".
    assert AgentStatus.en_route.value == "en-route"
    assert _agent("en-route").status == "en-route"
    assert _telemetry("en-route").status == "en-route"
