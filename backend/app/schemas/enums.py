from enum import Enum


class AgentStatus(str, Enum):

    idle = "idle"
    en_route = "en-route"
    stopped = "stopped"
    offline = "offline"


class AlertType(str, Enum):

    low_battery = "low_battery"


class AlertSeverity(str, Enum):

    warning = "warning"
