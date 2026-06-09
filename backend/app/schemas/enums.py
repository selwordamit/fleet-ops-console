from enum import Enum


class AgentStatus(str, Enum):
    """Allowed operational status values for agents and telemetry reports.

    Subclasses `str` so the members compare/serialize as their plain string values.
    The `en_route` member name is a valid Python identifier; its value keeps the
    hyphenated wire form "en-route". This is the single source of truth shared by
    the Agent and Telemetry request schemas; the SQLAlchemy columns stay free-form
    `String` for now (validation lives at the API boundary, not the database).
    """

    idle = "idle"
    en_route = "en-route"
    stopped = "stopped"
    offline = "offline"
