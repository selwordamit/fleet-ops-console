import json

from app.cache.client import redis_client
from app.cache.keys import agent_state_key


async def read_agent_state(agent_id: int) -> dict | None:

    raw = await redis_client.get(agent_state_key(agent_id))
    if raw is None:
        return None

    return json.loads(raw)
