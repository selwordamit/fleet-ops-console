import pytest
from pydantic import ValidationError

from app.schemas.telemetry import TelemetryCreate


def test_valid_payload():
    payload = TelemetryCreate(lat=32.0, lng=34.8, speed=12.5, battery=80, status="en-route")
    assert payload.lat == 32.0
    assert payload.status == "en-route"


@pytest.mark.parametrize(
    "field,value",
    [
        ("lat", -91),
        ("lat", 91),
        ("lng", -181),
        ("lng", 181),
        ("speed", -1),
        ("battery", -1),
        ("battery", 101),
    ],
)
def test_out_of_range_values_rejected(field, value):
    base = {"lat": 0, "lng": 0, "speed": 0, "battery": 50, "status": "idle"}
    base[field] = value
    with pytest.raises(ValidationError):
        TelemetryCreate(**base)


def test_empty_status_rejected():
    with pytest.raises(ValidationError):
        TelemetryCreate(lat=0, lng=0, speed=0, battery=50, status="")
