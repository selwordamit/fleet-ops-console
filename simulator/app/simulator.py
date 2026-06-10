# simulator.py
#
# This file contains the main simulator engine.
#
# The simulator does two main things:
# 1. Registers simulated agents in the backend.
# 2. Sends controlled telemetry updates for those agents in a loop.
#
# Important:
# This file does not access Postgres or Redis directly.
# It uses BackendClient, which talks to the backend through REST API only.
#
# Main responsibilities:
# - AgentState:
#   Stores the live in-memory state of one registered simulated agent.
#
# - Simulator.__init__:
#   Stores the simulator config, backend client, and the registered agents list.
#
# - Simulator.register_agents:
#   Builds the agent starting specs and registers them in the backend.
#
# - Simulator.run:
#   Starts the infinite telemetry loop until the user stops it.
#
# - Simulator._tick:
#   Sends one telemetry update for each registered agent.
#
# - _next_telemetry:
#   Updates one agent's in-memory location/battery/status and builds the telemetry payload.

import logging
import random
import time
from dataclasses import dataclass

from .client import BackendClient
from .config import SimulatorConfig
from .placement import build_agent_specs

# Logger for this module.
logger = logging.getLogger(__name__)

# Only these statuses are accepted by the backend enum validation.
STATUSES = ["idle", "en-route", "stopped", "offline"]

# Weighted status selection:
# en-route is more common, while idle/stopped/offline happen less often.
STATUS_WEIGHTS = [2, 6, 1, 1]

MOVING_STATUS = "en-route"

# Max movement per telemetry tick.
# 0.0003 degrees is roughly around 30 meters, depending on location.
MAX_STEP_DEG = 0.0003

# Battery decreases by this value every telemetry tick.
BATTERY_DRAIN_PER_TICK = 0.5

@dataclass
class AgentState:
    """
    Live in-memory state for one registered simulated agent.

    This is not a database model.
    It only exists inside the simulator while it is running.
    """

    agent_id: int
    lat: float
    lng: float
    battery: float


class Simulator:
    """
    Main simulator engine.

    It registers agents through the backend,
    then repeatedly sends telemetry for them.
    """

    def __init__(self, config: SimulatorConfig, client: BackendClient) -> None:
        """
        Initialize the simulator with config and backend client.
        """

        self._config = config
        self._client = client

        # Holds the agents that were successfully registered in the backend.
        self._agents: list[AgentState] = []

    def register_agents(self) -> int:
        """
        Build agent specs and register each agent through the backend API.

        Returns:
            Number of agents successfully registered.
        """

        # Build starting agent definitions based on the configured placement mode.
        specs = build_agent_specs(self._config)

        registered = 0

        for spec in specs:
            # Register the agent in the backend and get its database ID.
            agent_id = self._client.register_agent(spec.name, spec.type, spec.status)

            # If registration failed, skip this agent.
            if agent_id is None:
                continue

            # Store the agent's live simulation state in memory.
            # Movement starts from the initial location created by placement.py.
            self._agents.append(
                AgentState(
                    agent_id=agent_id,
                    lat=spec.lat,
                    lng=spec.lng,
                    battery=100.0,
                )
            )

            registered += 1

        logger.info("Registered %d/%d agents", registered, len(specs))

        return registered

    def run(self) -> None:
        """
        Start the telemetry loop.

        The loop sends telemetry for all registered agents,
        then waits telemetry_interval_seconds before the next tick.
        """

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
                # One tick = one telemetry update attempt for every registered agent.
                sent = self._tick()

                logger.info("Telemetry tick: %d/%d sent", sent, len(self._agents))

                # Wait before sending the next telemetry batch.
                time.sleep(self._config.telemetry_interval_seconds)

        except KeyboardInterrupt:
            # Allows stopping the simulator with Ctrl+C.
            logger.info("Simulator stopped by user.")

    def _tick(self) -> int:
        """
        Send one telemetry update for each registered agent.

        Returns:
            Number of telemetry payloads successfully sent.
        """

        sent = 0

        for state in self._agents:
            # Build the next telemetry payload for this agent.
            payload = _next_telemetry(state)

            # Send telemetry through the backend REST API.
            if self._client.send_telemetry(state.agent_id, payload):
                sent += 1

        return sent


def _next_telemetry(state: AgentState) -> dict:
    """
    Advance one agent by a small movement step and build its telemetry payload.

    This function mutates the in-memory AgentState.
    """

    # Move the agent slightly from its current position.
    # This creates controlled movement instead of jumping randomly across the map.
    state.lat += random.uniform(-MAX_STEP_DEG, MAX_STEP_DEG)
    state.lng += random.uniform(-MAX_STEP_DEG, MAX_STEP_DEG)

    # Drain battery but never let it go below 0.
    state.battery = max(0.0, state.battery - BATTERY_DRAIN_PER_TICK)

    # Pick a status using weights.
    # Example: en-route is more likely than offline.
    status = random.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]

    # Only moving agents get speed.
    # Non-moving statuses report speed 0.
    speed = round(random.uniform(15.0, 70.0), 1) if status == MOVING_STATUS else 0.0

    return {
        # Rounded coordinates keep payloads clean and realistic enough for demo.
        "lat": round(state.lat, 6),
        "lng": round(state.lng, 6),
        "speed": speed,
        "battery": round(state.battery, 1),
        "status": status,
    }