from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import AgentStatus


class AgentCreate(BaseModel):

    model_config = ConfigDict(use_enum_values=True)

    name: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=50)
    status: AgentStatus


class AgentRead(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    status: str
    last_seen: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentLatestState(BaseModel):

    lat: float
    lng: float
    speed: float
    battery: float
    status: str
    recorded_at: datetime


class AgentCurrentState(BaseModel):
    
    id: int
    name: str
    type: str
    status: str
    last_seen: datetime | None
    latest_state: AgentLatestState | None
