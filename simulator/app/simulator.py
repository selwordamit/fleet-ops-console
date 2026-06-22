import asyncio
import logging
import random
import time
from dataclasses import dataclass

from .client import BackendClient
from .config import SimulatorConfig
from .placement import build_agent_specs

logger = logging.getLogger(__name__)

# Statuses accepted by the backend enum validation.
STATUSES = ["idle", "en-route", "stopped", "offline"]

# Weighted so en-route dominates and idle/stopped/offline are rarer.
STATUS_WEIGHTS = [2, 6, 1, 1]

MOVING_STATUS = "en-route"

# Reported once battery hits 0: a depleted agent can't drive.
DEPLETED_STATUS = "offline"

# Max movement per tick; 0.0003 deg is roughly ~30 m.
MAX_STEP_DEG = 0.0003

BATTERY_DRAIN_PER_TICK = 0.5


@dataclass
class AgentState:

    agent_id: int
    lat: float
    lng: float
    battery: float


class Simulator:
    """Registers agents through the backend, then streams telemetry for them."""

    def __init__(self, config: SimulatorConfig, client: BackendClient) -> None:
        self._config = config
        self._client = client
        self._agents: list[AgentState] = []

    async def register_agents(self) -> int:
        """Register every placement spec; returns how many succeeded."""

        specs = build_agent_specs(self._config)
        registered = 0

        start = time.time()
        for spec in specs:
            agent_id = await self._client.register_agent(spec.name, spec.type, spec.status)
            if agent_id is None:
                continue

            # Movement starts from the placement location.
            self._agents.append(
                AgentState(
                    agent_id=agent_id,
                    lat=spec.lat,
                    lng=spec.lng,
                    battery=100.0,
                )
            )
            registered += 1

        duration = time.time() - start
        logger.info("Total registration took %.3fs for %d agents", duration, registered)

        logger.info("Registered %d/%d agents", registered, len(specs))
        return registered

    async def run(self) -> None:
        """Send telemetry for all agents every telemetry_interval_seconds until stopped."""

        if not self._agents:
            logger.error("No agents registered; nothing to simulate. Exiting.")
            return

        logger.info(
            "Starting telemetry loop: %d agents every %.1fs",
            len(self._agents),
            self._config.telemetry_interval_seconds,
        )

        try:
            while True:
                sent = await self._tick()
                logger.info("Telemetry tick: %d/%d sent", sent, len(self._agents))
                await asyncio.sleep(self._config.telemetry_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Simulator stopped by user.")

    async def _tick(self) -> int:
        """Bundle every agent's telemetry into one request; returns how many were accepted.

        Replaces the previous one-request-per-agent fan-out (asyncio.gather over the
        whole fleet) with a single batch POST, so a 10k-agent fleet costs one HTTP
        request per tick instead of 10k.
        """

        batch = []
        for state in self._agents:
            item = _next_telemetry(state)
            item["agent_id"] = state.agent_id
            batch.append(item)

        start = time.time()
        accepted = await self._client.send_telemetry_batch(batch)
        # The batch endpoint accepts or rejects the whole request; on success
        # every item in the batch was buffered.
        sent = len(batch) if accepted else 0

        duration = time.time() - start
        logger.info(
            "Tick completed in %.3fs agents=%d sent=%d",
            duration,
            len(self._agents),
            sent,
        )
        return sent


def _next_telemetry(state: AgentState) -> dict:
    """Advance the agent by one step and build its telemetry payload (mutates state)."""

    # Small random step for controlled drift instead of teleporting across the map.
    state.lat += random.uniform(-MAX_STEP_DEG, MAX_STEP_DEG)
    state.lng += random.uniform(-MAX_STEP_DEG, MAX_STEP_DEG)

    state.battery = max(0.0, state.battery - BATTERY_DRAIN_PER_TICK)

    if state.battery <= 0.0:
        # Keep telemetry consistent: no en-route or speed at 0% battery.
        status = DEPLETED_STATUS
        speed = 0.0
    else:
        status = random.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
        # Only moving agents report a non-zero speed.
        speed = round(random.uniform(15.0, 70.0), 1) if status == MOVING_STATUS else 0.0

    return {
        "lat": round(state.lat, 6),
        "lng": round(state.lng, 6),
        "speed": speed,
        "battery": round(state.battery, 1),
        "status": status,
    }
