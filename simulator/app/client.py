# client.py
#
# This file defines BackendClient, the simulator's REST client.
#
# The simulator should not access Postgres or Redis directly.
# Instead, it sends all data through the backend API, just like a real external client.
#
# Main responsibilities:
# - BackendClient.__init__:
#   Stores the backend URL, timeout, and creates a reusable HTTP session.
#
# - BackendClient.register_agent:
#   Sends POST /api/agents to create/register a simulated agent in the backend.
#   Returns the created agent ID, or None if registration fails.
#
# - BackendClient.send_telemetry:
#   Sends POST /api/agents/{agent_id}/telemetry with the agent's latest telemetry.
#   Returns True if the backend accepted the telemetry, otherwise False.

import logging

import requests

logger = logging.getLogger(__name__)


class BackendClient:
    """
    Thin REST client used by the simulator.

    This class is the only communication layer between the simulator and the backend.
    """

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        """
        Initialize the client with backend connection settings.
        """

        # Backend base URL, for example: http://localhost:8000
        self._base_url = base_url

        # Max time to wait for a backend response before failing the request.
        self._timeout = timeout

        # Reusable HTTP session.
        # Useful because the simulator sends many requests to the same backend.
        self._session = requests.Session()

    def register_agent(self, name: str, type_: str, status: str) -> int | None:
        """
        Register a new simulated agent through the backend API.

        Returns:
            The created agent ID on success.
            None on failure.
        """

        # Build the endpoint URL: POST /api/agents
        url = f"{self._base_url}/api/agents"

        # type_ is used because "type" is a built-in Python name.
        # The API still expects the field name to be "type".
        payload = {"name": name, "type": type_, "status": status}

        try:
            # Send the agent creation request to the backend.
            resp = self._session.post(url, json=payload, timeout=self._timeout)

            # Raises an exception for HTTP errors such as 400, 422, 500.
            resp.raise_for_status()

        except requests.RequestException as exc:
            # If registration fails, log it and let the simulator continue safely.
            logger.warning("Agent registration FAILED name=%s: %s", name, exc)
            return None

        # The backend response should contain the created agent ID.
        agent_id = resp.json()["id"]

        logger.info("Agent registered id=%s name=%s type=%s", agent_id, name, type_)

        return agent_id

    def send_telemetry(self, agent_id: int, payload: dict) -> bool:
        """
        Send telemetry for an existing agent through the backend API.

        Returns:
            True if telemetry was accepted.
            False if sending failed.
        """

        # Build the endpoint URL: POST /api/agents/{agent_id}/telemetry
        url = f"{self._base_url}/api/agents/{agent_id}/telemetry"

        try:
            # Send telemetry to the backend.
            # The backend handles validation, DB write, Redis update, and future events.
            resp = self._session.post(url, json=payload, timeout=self._timeout)

            # Raises an exception for HTTP errors such as 404, 422, 500.
            resp.raise_for_status()

        except requests.RequestException as exc:
            # Return False instead of crashing the simulator.
            logger.warning("Telemetry send FAILED agent_id=%s: %s", agent_id, exc)
            return False

        # Debug is used because telemetry is sent frequently.
        logger.debug("Telemetry sent agent_id=%s payload=%s", agent_id, payload)

        return True