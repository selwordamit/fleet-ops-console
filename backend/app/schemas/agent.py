from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    """Incoming payload to register a new agent.

    Fields are free-form strings for now (no enums yet); validation only enforces
    non-empty values within the column lengths defined on the Agent model.
    """

    name: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=50)
    status: str = Field(min_length=1, max_length=20)


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
