# main.py
#
# This file is the entry point of the simulator.
# Its job is to start the simulator process and connect all main parts together:
# - load runtime configuration from environment variables
# - create the backend REST client
# - create the simulator engine
# - register simulated agents in the backend
# - start the telemetry loop
#
# This file should stay simple.
# It should not contain the simulation logic itself, database logic, or telemetry generation logic.
# Those responsibilities belong to the Simulator, BackendClient, and configuration modules.

import logging

from .client import BackendClient
from .config import SimulatorConfig
from .simulator import Simulator

logger = logging.getLogger(__name__)


def main() -> None:
    """
    Entry point of the simulator process.
    """

    # Configure global logging format and level for the simulator process.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # Load runtime settings such as backend URL, mode, agent count, interval, etc.
    config = SimulatorConfig.from_env()

    # Print the loaded config once at startup.
    # This helps verify which mode/settings the simulator is actually using.
    logger.info(
        "Simulator config: backend_url=%s mode=%s agent_count=%s interval=%ss "
        "base=(%.5f, %.5f) spread_radius_km=%s scenario_file=%s",
        config.backend_url, config.simulation_mode, config.agent_count,
        config.telemetry_interval_seconds, config.base_lat, config.base_lng,
        config.spread_radius_km, config.scenario_file,
    )

    # REST client used by the simulator to communicate with the backend API.
    client = BackendClient(config.backend_url)

    # Create the simulator with its config and backend client.
    simulator = Simulator(config, client)

    # First register all simulated agents in the backend.
    simulator.register_agents()

    # Start the telemetry loop.
    simulator.run()


# Run main() only when this file is executed directly.
# Prevents auto-running if this file is imported by another module.
if __name__ == "__main__":
    main()