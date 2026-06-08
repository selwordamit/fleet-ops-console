from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TelemetryCreate(BaseModel):
    """Incoming telemetry payload. Bounds reject obviously invalid sensor data."""

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    speed: float = Field(ge=0)
    battery: float = Field(ge=0, le=100)
    # Free-form string for now (e.g. idle/en-route/stopped/offline); not yet an enum.
    status: str = Field(min_length=1, max_length=20)


class TelemetryRead(BaseModel):
    """Telemetry as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    lat: float
    lng: float
    speed: float
    battery: float
    status: str
    recorded_at: datetime
