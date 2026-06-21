import asyncio
import logging

from .client import BackendClient
from .config import SimulatorConfig
from .simulator import Simulator

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    config = SimulatorConfig.from_env()

    # Log the resolved config once so the active mode/settings are visible at startup.
    logger.info(
        "Simulator config: backend_url=%s mode=%s agent_count=%s interval=%ss "
        "base=(%.5f, %.5f) spread_radius_km=%s scenario_file=%s",
        config.backend_url, config.simulation_mode, config.agent_count,
        config.telemetry_interval_seconds, config.base_lat, config.base_lng,
        config.spread_radius_km, config.scenario_file,
    )

    client = BackendClient(config.backend_url)
    simulator = Simulator(config, client)

    await simulator.register_agents()
    await simulator.run()


if __name__ == "__main__":
    asyncio.run(main())
