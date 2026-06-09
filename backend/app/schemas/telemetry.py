from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import AgentStatus


class TelemetryCreate(BaseModel):
    """Incoming telemetry payload. Bounds reject obviously invalid sensor data."""

    model_config = ConfigDict(use_enum_values=True)

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    speed: float = Field(ge=0)
    battery: float = Field(ge=0, le=100)
    # Constrained to the shared AgentStatus values; use_enum_values stores the plain string.
    status: AgentStatus


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
