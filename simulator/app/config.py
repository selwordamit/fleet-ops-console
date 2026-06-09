# config.py
#
# This file defines the simulator runtime configuration.
#
# The simulator uses environment variables so we can change how it runs
# without changing the code.
#
# Main responsibilities:
# - Define supported simulation modes:
#   local_cluster = generate agents around one base location.
#   fixed_points = load exact agent locations from a JSON scenario file.
#
# - Define SimulatorConfig:
#   A small immutable config object that stores all simulator settings.
#
# - SimulatorConfig.from_env:
#   Reads environment variables and creates a SimulatorConfig instance.
#   If an environment variable is missing, it uses a safe default value.

import os
from dataclasses import dataclass

# Default location used only by local_cluster mode.
# These coordinates point to Tel Aviv center.
DEFAULT_BASE_LAT = 32.0853
DEFAULT_BASE_LNG = 34.7818

# Simulation mode: generate agents around a base location.
LOCAL_CLUSTER = "local_cluster"

# Simulation mode: load exact agent locations from a JSON scenario file.
FIXED_POINTS = "fixed_points"


@dataclass(frozen=True)
class SimulatorConfig:
    """
    Runtime configuration for the simulator.

    frozen=True means this config cannot be changed after it is created.
    This keeps the simulator run predictable and avoids accidental changes.
    """

    backend_url: str
    simulation_mode: str
    agent_count: int
    telemetry_interval_seconds: float
    base_lat: float
    base_lng: float
    spread_radius_km: float
    scenario_file: str

    @classmethod
    def from_env(cls) -> "SimulatorConfig":
        """
        Create SimulatorConfig from environment variables.

        Returns:
            A fully populated SimulatorConfig object.

        Notes:
            os.getenv("NAME", "default") reads an environment variable.
            If the variable does not exist, it uses the default value.
        """

        return cls(
            # Backend API base URL.
            # rstrip("/") removes a trailing slash to avoid URLs like //api/agents.
            backend_url=os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/"),

            # Choose how agents are placed: local_cluster or fixed_points.
            simulation_mode=os.getenv("SIMULATION_MODE", LOCAL_CLUSTER),

            # Number of agents to generate in local_cluster mode.
            # os.getenv returns strings, so we convert to int.
            agent_count=int(os.getenv("AGENT_COUNT", "10")),

            # How often each agent sends telemetry.
            # float allows values like 0.5 seconds.
            telemetry_interval_seconds=float(os.getenv("TELEMETRY_INTERVAL_SECONDS", "2")),

            # Base location for local_cluster mode.
            # fixed_points mode ignores these values.
            base_lat=float(os.getenv("BASE_LAT", str(DEFAULT_BASE_LAT))),
            base_lng=float(os.getenv("BASE_LNG", str(DEFAULT_BASE_LNG))),

            # Radius around the base location for local_cluster mode.
            spread_radius_km=float(os.getenv("SPREAD_RADIUS_KM", "2")),

            # JSON scenario file used by fixed_points mode.
            scenario_file=os.getenv("SCENARIO_FILE", "simulator/scenarios/israel_demo.json"),
        )