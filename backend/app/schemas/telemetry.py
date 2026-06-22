from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import AgentStatus


class TelemetryCreate(BaseModel):

    model_config = ConfigDict(use_enum_values=True)

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    speed: float = Field(ge=0)
    battery: float = Field(ge=0, le=100)
    status: AgentStatus


class TelemetryBatchItem(TelemetryCreate):
    """One agent's telemetry within a batch: the standard fields plus its agent_id.

    Inherits TelemetryCreate so the per-field validation (and use_enum_values) is
    identical to the single-agent ingest path; only agent_id is added.
    """

    agent_id: int = Field(gt=0)


class TelemetryBatchRequest(BaseModel):
    """One request carrying telemetry for many agents, sent once per simulator tick."""

    agents: list[TelemetryBatchItem]


class TelemetryRead(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    lat: float
    lng: float
    speed: float
    battery: float
    status: str
    recorded_at: datetime
