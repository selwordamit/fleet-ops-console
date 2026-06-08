import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.client import redis_client
from app.cache.keys import agent_state_key
from app.models.telemetry import Telemetry
from app.repositories.agent import get_agent
from app.repositories.telemetry import insert_telemetry
from app.schemas.telemetry import TelemetryCreate


class AgentNotFoundError(Exception):
    """Raised when telemetry is posted for an agent that does not exist."""

    def __init__(self, agent_id: int) -> None:
        self.agent_id = agent_id
        super().__init__(f"Agent {agent_id} not found")


async def ingest_telemetry(
    session: AsyncSession, agent_id: int, payload: TelemetryCreate
) -> Telemetry:
    # 1. Reject telemetry for unknown agents before writing anything.
    if await get_agent(session, agent_id) is None:
        raise AgentNotFoundError(agent_id)

    # 2. Persist durable history to Postgres.
    row = await insert_telemetry(session, agent_id, payload)
    await session.commit()
    await session.refresh(row)

    # 3. Mirror the latest state into Redis for fast current-state reads.
    # Done after commit: Postgres is the source of truth, so a Redis hiccup must
    # not roll back a stored report.
    await _update_latest_state(row)

    return row


async def _update_latest_state(row: Telemetry) -> None:
    state = {
        "agent_id": row.agent_id,
        "lat": row.lat,
        "lng": row.lng,
        "speed": row.speed,
        "battery": row.battery,
        "status": row.status,
        "recorded_at": row.recorded_at.isoformat(),
    }
    await redis_client.set(agent_state_key(row.agent_id), json.dumps(state))
