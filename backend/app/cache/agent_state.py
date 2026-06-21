import json

from app.cache.client import redis_client
from app.cache.keys import agent_state_key


async def read_agent_state(agent_id: int) -> dict | None:
    raw = await redis_client.get(agent_state_key(agent_id))
    if raw is None:
        return None
    return json.loads(raw)


async def write_agent_state(row) -> None:
    """Serialise a Telemetry row into Redis as the agent's current state."""
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
