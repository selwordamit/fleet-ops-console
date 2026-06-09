import json

from app.cache.client import redis_client
from app.cache.keys import agent_state_key


async def read_agent_state(agent_id: int) -> dict | None:
    """Read an agent's latest state from Redis.

    Returns the decoded state dict, or None when the agent has no cached state yet
    (e.g. it was registered but has not reported telemetry). The caller decides how
    to represent the missing-state case; this accessor never raises on a cache miss.
    """
    raw = await redis_client.get(agent_state_key(agent_id))
    if raw is None:
        return None
    # redis_client uses decode_responses=True, so raw is already a str.
    return json.loads(raw)
