# Central place for Redis key names so the format is defined once and reused.


def agent_state_key(agent_id: int) -> str:
    # Latest-known state for a single agent (fast read for the map/live view).
    return f"agent:{agent_id}:state"
