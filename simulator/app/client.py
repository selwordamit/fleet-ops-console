import logging
import time

import httpx

logger = logging.getLogger(__name__)


class BackendClient:

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._base_url = base_url
        self._timeout = timeout
        # Telemetry now goes out as one batch request per tick, so a small pool is
        # plenty; keepalive matches so the single connection is reused across ticks
        # instead of being torn down and reopened.
        self._client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=10),
        )

    async def register_agent(self, name: str, type_: str, status: str) -> int | None:
        """POST /api/agents to register an agent"""

        url = f"{self._base_url}/api/agents"

        # "type" is a Python builtin, so the arg is type_; the API field stays "type".
        payload = {"name": name, "type": type_, "status": status}

        start = time.time()
        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            # Keep the simulator running even if a single registration fails.
            logger.warning("Agent registration FAILED name=%s: %s", name, exc)
            return None

        duration = time.time() - start
        logger.info("register_agent took %.3fs agent=%s", duration, name)

        agent_id = resp.json()["id"]
        logger.info("Agent registered id=%s name=%s type=%s", agent_id, name, type_)
        return agent_id

    async def send_telemetry(self, agent_id: int, payload: dict) -> bool:
        """POST telemetry for an agent. Returns True if the backend accepted it."""

        url = f"{self._base_url}/api/agents/{agent_id}/telemetry"

        start = time.time()
        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Telemetry send FAILED agent_id=%s: %s", agent_id, exc)
            return False

        duration = time.time() - start
        # Debug level because telemetry is high-frequency.
        logger.debug("send_telemetry took %.3fs agent_id=%s", duration, agent_id)
        logger.debug("Telemetry sent agent_id=%s payload=%s", agent_id, payload)
        return True

    async def send_telemetry_batch(self, batch: list[dict]) -> bool:
        """POST telemetry for many agents in ONE request. Returns True if accepted.

        Each item in ``batch`` must carry agent_id plus the telemetry fields
        (lat, lng, speed, battery, status). Collapses what used to be one request
        per agent into a single request per tick.
        """

        url = f"{self._base_url}/api/agents/telemetry/batch"
        payload = {"agents": batch}

        start = time.time()
        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Telemetry batch send FAILED count=%d: %s", len(batch), exc)
            return False

        duration = time.time() - start
        logger.debug("send_telemetry_batch took %.3fs count=%d", duration, len(batch))
        return True
