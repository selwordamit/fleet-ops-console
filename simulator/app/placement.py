import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path

from .config import FIXED_POINTS, LOCAL_CLUSTER, SimulatorConfig

logger = logging.getLogger(__name__)

# Resolve relative SCENARIO_FILE paths from here, so the working directory doesn't matter.
REPO_ROOT = Path(__file__).resolve().parents[2]

VEHICLE_TYPES = ["truck", "van", "scooter"]

# 1 degree of latitude is ~111 km; longitude is scaled by cos(latitude) below.
KM_PER_DEG_LAT = 111.0


@dataclass
class AgentSpec:
    """Starting definition for one simulated agent (not a DB model)."""

    name: str
    type: str
    status: str
    lat: float
    lng: float


def build_agent_specs(config: SimulatorConfig) -> list[AgentSpec]:
    """Build the agent list for the configured placement mode."""

    if config.simulation_mode == LOCAL_CLUSTER:
        return _local_cluster(config)
    if config.simulation_mode == FIXED_POINTS:
        return _fixed_points(config)

    raise ValueError(
        f"Unknown SIMULATION_MODE '{config.simulation_mode}'. "
        f"Supported modes: {LOCAL_CLUSTER}, {FIXED_POINTS}."
    )


def _local_cluster(config: SimulatorConfig) -> list[AgentSpec]:

    count = config.agent_count

    # Golden angle gives an even sunflower spread, avoiding lines or center clumping.
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))

    # Longitude km-per-degree shrinks toward the poles; correct it for this latitude.
    lng_scale = KM_PER_DEG_LAT * math.cos(math.radians(config.base_lat))

    specs: list[AgentSpec] = []

    for i in range(count):
        # sqrt keeps density even across the disc instead of bunching at the center.
        r_km = config.spread_radius_km * math.sqrt((i + 0.5) / count)
        theta = i * golden_angle

        d_lat = (r_km * math.cos(theta)) / KM_PER_DEG_LAT
        d_lng = (r_km * math.sin(theta)) / lng_scale

        specs.append(
            AgentSpec(
                name=f"sim-agent-{i + 1}",
                type=VEHICLE_TYPES[i % len(VEHICLE_TYPES)],
                status="idle",
                lat=config.base_lat + d_lat,
                lng=config.base_lng + d_lng,
            )
        )

    logger.info(
        "local_cluster: generated %d agents within %.2f km of (%.5f, %.5f)",
        len(specs),
        config.spread_radius_km,
        config.base_lat,
        config.base_lng,
    )

    return specs


def _fixed_points(config: SimulatorConfig) -> list[AgentSpec]:
    """Load exact agent locations from a JSON scenario file (AGENT_COUNT is ignored)."""

    path = _resolve_scenario_path(config.scenario_file)

    if not path.is_file():
        raise FileNotFoundError(f"Scenario file not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(raw, list):
        raise ValueError(f"Scenario file {path} must contain a JSON list of agents.")

    required = ("name", "type", "status", "lat", "lng")
    specs: list[AgentSpec] = []

    for index, entry in enumerate(raw):
        missing = [key for key in required if key not in entry]
        if missing:
            raise ValueError(f"Scenario entry {index} is missing fields: {missing}")

        specs.append(
            AgentSpec(
                name=entry["name"],
                type=entry["type"],
                status=entry["status"],
                # float() because JSON may carry coordinates as strings.
                lat=float(entry["lat"]),
                lng=float(entry["lng"]),
            )
        )

    logger.info("fixed_points: loaded %d agents from %s", len(specs), path)

    return specs


def _resolve_scenario_path(scenario_file: str) -> Path:
    """Return scenario_file as-is if absolute, otherwise resolved from the repo root."""

    path = Path(scenario_file)
    return path if path.is_absolute() else REPO_ROOT / path
