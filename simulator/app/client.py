import logging

import httpx

logger = logging.getLogger(__name__)


class BackendClient:

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._base_url = base_url
        self._timeout = timeout
        # Pool sized to the simulator's send concurrency (MAX_CONCURRENT_SENDS=50):
        # no point allowing more open connections than there are concurrent sends,
        # and keepalive matches so connections are reused across waves/ticks
        # instead of being torn down and reopened.
        self._client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=50),
        )

    async def register_agent(self, name: str, type_: str, status: str) -> int | None:
        """POST /api/agents to register an agent"""

        url = f"{self._base_url}/api/agents"

        # "type" is a Python builtin, so the arg is type_; the API field stays "type".
        payload = {"name": name, "type": type_, "status": status}

        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            # Keep the simulator running even if a single registration fails.
            logger.warning("Agent registration FAILED name=%s: %s", name, exc)
            return None

        agent_id = resp.json()["id"]
        logger.info("Agent registered id=%s name=%s type=%s", agent_id, name, type_)
        return agent_id

    async def send_telemetry(self, agent_id: int, payload: dict) -> bool:
        """POST telemetry for an agent. Returns True if the backend accepted it."""

        url = f"{self._base_url}/api/agents/{agent_id}/telemetry"

        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Telemetry send FAILED agent_id=%s: %s", agent_id, exc)
            return False

        # Debug level because telemetry is high-frequency.
        logger.debug("Telemetry sent agent_id=%s payload=%s", agent_id, payload)
        return True
