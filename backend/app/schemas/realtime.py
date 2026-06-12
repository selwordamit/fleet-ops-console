from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.schemas.enums import AgentStatus


def _iso_z(value: datetime) -> str:

    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class AgentLatestStatePayload(BaseModel):

    lat: float
    lng: float
    speed: float
    battery: float
    status: AgentStatus
    recorded_at: datetime

    # Converts Python datetime to a string in ISO-UTC format when converting to JSON,
    # because plain JSON doesn't know how to read or display time objects.
    @field_serializer("recorded_at", when_used="json")
    def _serialize_recorded_at(self, value: datetime) -> str:
        return _iso_z(value)


class AgentTelemetryUpdatedPayload(BaseModel):

    agent_id: int
    latest_state: AgentLatestStatePayload


class AgentTelemetryUpdatedEvent(BaseModel):

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["agent.telemetry.updated"] = "agent.telemetry.updated"
    payload: AgentTelemetryUpdatedPayload
    ts: datetime
    request_id: str | None = Field(default=None, alias="requestId")

    @field_serializer("ts", when_used="json")
    def _serialize_ts(self, value: datetime) -> str:
        return _iso_z(value)
