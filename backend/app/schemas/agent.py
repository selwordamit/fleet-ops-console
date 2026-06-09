from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import AgentStatus


class AgentCreate(BaseModel):
    """Incoming payload to register a new agent.

    `name`/`type` stay free-form strings; `status` is constrained to AgentStatus.
    `use_enum_values=True` stores the validated value as the plain string, so the
    service persists a clean string to Postgres and responses serialize cleanly.
    """

    model_config = ConfigDict(use_enum_values=True)

    name: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=50)
    status: AgentStatus


class AgentRead(BaseModel):
    """Agent as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    status: str
    last_seen: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentLatestState(BaseModel):
    """An agent's latest reported telemetry, sourced from Redis current-state.

    Mirrors the snapshot written on telemetry ingestion (agent:{id}:state). The
    agent_id is carried by the parent AgentCurrentState, so it is omitted here.
    """

    lat: float
    lng: float
    speed: float
    battery: float
    status: str
    recorded_at: datetime


class AgentCurrentState(BaseModel):
    """An agent's identity plus its latest state, for the live current-state view.

    latest_state is None when the agent exists in Postgres but has no Redis state
    yet (registered but not reporting). Identity fields come from Postgres.
    """

    id: int
    name: str
    type: str
    status: str
    last_seen: datetime | None
    latest_state: AgentLatestState | None
