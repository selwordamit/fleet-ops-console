import os
from dataclasses import dataclass

# Default base location for local_cluster mode: Tel Aviv center.
DEFAULT_BASE_LAT = 32.0853
DEFAULT_BASE_LNG = 34.7818

# Supported placement modes.
LOCAL_CLUSTER = "local_cluster"  # generate agents around a base location
FIXED_POINTS = "fixed_points"    # load exact agent locations from a JSON scenario file


@dataclass(frozen=True)
class SimulatorConfig:
    """Immutable simulator settings; frozen to keep a run's behavior predictable."""

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
        """Build config from environment variables, falling back to safe defaults."""

        return cls(
            # rstrip("/") avoids double slashes like //api/agents.
            backend_url=os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/"),
            simulation_mode=os.getenv("SIMULATION_MODE", LOCAL_CLUSTER),
            agent_count=int(os.getenv("AGENT_COUNT", "10")),
            telemetry_interval_seconds=float(os.getenv("TELEMETRY_INTERVAL_SECONDS", "2")),
            # base_lat/base_lng apply to local_cluster mode; fixed_points ignores them.
            base_lat=float(os.getenv("BASE_LAT", str(DEFAULT_BASE_LAT))),
            base_lng=float(os.getenv("BASE_LNG", str(DEFAULT_BASE_LNG))),
            spread_radius_km=float(os.getenv("SPREAD_RADIUS_KM", "2")),
            scenario_file=os.getenv("SCENARIO_FILE", "simulator/scenarios/israel_demo.json"),
        )
