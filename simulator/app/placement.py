# placement.py
#
# This file is responsible for deciding where simulated agents start on the map.
#
# It does not register agents in the backend and does not send telemetry.
# It only builds a clean list of AgentSpec objects that describe:
# - agent name
# - vehicle type
# - initial status
# - initial latitude/longitude
#
# Supported placement modes:
# - local_cluster:
#   Generate agents automatically around one base location.
#   Useful for testing map clustering and load around a specific area.
#
# - fixed_points:
#   Load exact agent locations from a JSON scenario file.
#   Useful for stable demos where the agents should always start in known places.
#
# Main responsibilities:
# - AgentSpec:
#   Represents the starting definition of one simulated agent.
#
# - build_agent_specs:
#   Chooses which placement strategy to use based on SIMULATION_MODE.
#
# - _local_cluster:
#   Generates AGENT_COUNT agents around base_lat/base_lng.
#
# - _fixed_points:
#   Loads agents from a JSON scenario file.
#
# - _resolve_scenario_path:
#   Resolves relative scenario paths from the project root.

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path

from .config import FIXED_POINTS, LOCAL_CLUSTER, SimulatorConfig

# Logger for this module.
logger = logging.getLogger(__name__)

# Project root path.
# This allows SCENARIO_FILE to work even if we run the simulator from another folder.
REPO_ROOT = Path(__file__).resolve().parents[2]

# Vehicle types used when agents are generated automatically in local_cluster mode.
VEHICLE_TYPES = ["truck", "van", "scooter"]

# Rough conversion: 1 degree of latitude is about 111 km.
# Longitude needs extra scaling because it changes based on latitude.
KM_PER_DEG_LAT = 111.0


@dataclass
class AgentSpec:
    """
    Starting definition for one simulated agent.

    This is not a database model.
    It is only used by the simulator before registering the agent in the backend.
    """

    name: str
    type: str
    status: str
    lat: float
    lng: float


def build_agent_specs(config: SimulatorConfig) -> list[AgentSpec]:
    """
    Build the list of simulated agents based on the configured placement mode.
    """

    if config.simulation_mode == LOCAL_CLUSTER:
        return _local_cluster(config)

    if config.simulation_mode == FIXED_POINTS:
        return _fixed_points(config)

    # Fail fast if the mode is not supported.
    raise ValueError(
        f"Unknown SIMULATION_MODE '{config.simulation_mode}'. "
        f"Supported modes: {LOCAL_CLUSTER}, {FIXED_POINTS}."
    )


def _local_cluster(config: SimulatorConfig) -> list[AgentSpec]:
    """
    Generate agents around one base location.

    This mode uses:
    - AGENT_COUNT
    - BASE_LAT
    - BASE_LNG
    - SPREAD_RADIUS_KM

    The layout is deterministic, meaning the same config creates the same positions.
    This is better for testing than random placement.
    """

    count = config.agent_count

    # Golden angle creates an even "sunflower-like" spread of points.
    # This avoids placing agents in straight lines or too close to the center.
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))

    # Longitude distance changes depending on latitude.
    # cos(latitude) adjusts the longitude scale to the current base location.
    lng_scale = KM_PER_DEG_LAT * math.cos(math.radians(config.base_lat))

    specs: list[AgentSpec] = []

    for i in range(count):
        # sqrt() helps spread points evenly across the whole circle area,
        # instead of placing too many agents near the center.
        r_km = config.spread_radius_km * math.sqrt((i + 0.5) / count)

        # Each agent gets a different angle around the base point.
        theta = i * golden_angle

        # Convert distance in km into latitude/longitude offsets.
        d_lat = (r_km * math.cos(theta)) / KM_PER_DEG_LAT
        d_lng = (r_km * math.sin(theta)) / lng_scale

        specs.append(
            AgentSpec(
                name=f"sim-agent-{i + 1}",

                # Cycle vehicle types: truck, van, scooter, truck, van, scooter...
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
    """
    Load exact agent locations from a JSON scenario file.

    In this mode, AGENT_COUNT is ignored.
    The number of agents is the number of entries in the scenario file.
    """

    path = _resolve_scenario_path(config.scenario_file)

    if not path.is_file():
        raise FileNotFoundError(f"Scenario file not found: {path}")

    # Read the JSON file and convert it into Python objects.
    raw = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(raw, list):
        raise ValueError(f"Scenario file {path} must contain a JSON list of agents.")

    required = ("name", "type", "status", "lat", "lng")
    specs: list[AgentSpec] = []

    for index, entry in enumerate(raw):
        # Validate that every scenario entry has the required fields.
        missing = [key for key in required if key not in entry]

        if missing:
            raise ValueError(f"Scenario entry {index} is missing fields: {missing}")

        specs.append(
            AgentSpec(
                name=entry["name"],
                type=entry["type"],
                status=entry["status"],

                # Convert to float to support values that may come as strings in JSON.
                lat=float(entry["lat"]),
                lng=float(entry["lng"]),
            )
        )

    logger.info("fixed_points: loaded %d agents from %s", len(specs), path)

    return specs


def _resolve_scenario_path(scenario_file: str) -> Path:
    """
    Resolve the scenario file path.

    If the path is absolute, use it as-is.
    If the path is relative, resolve it from the project root.
    """

    path = Path(scenario_file)

    return path if path.is_absolute() else REPO_ROOT / path