from enum import Enum


class AgentStatus(str, Enum):

    idle = "idle"
    en_route = "en-route"
    stopped = "stopped"
    offline = "offline"
