import logging
from datetime import datetime, timezone

import socketio

from app.models.telemetry import Telemetry
from app.schemas.realtime import (
    AgentLatestStatePayload,
    AgentTelemetryUpdatedEvent,
    AgentTelemetryUpdatedPayload,
)

logger = logging.getLogger(__name__)

sio = socketio.AsyncServer(
    async_mode="asgi",  # so it can be wrapped by socketio.ASGIApp alongside FastAPI
    cors_allowed_origins="*",
)


def _envelope(event_type: str, payload: dict) -> dict:

    return {
        "type": event_type,
        "payload": payload,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@sio.event
async def connect(sid: str, environ: dict, auth: dict | None = None) -> None:
    """Log a new Socket.IO connection and send the client a readiness envelope."""

    logger.info("Socket.IO client connected: sid=%s", sid)

    # Readiness signal so the client knows the channel is live; not part of the
    # telemetry contract.
    await sio.emit("connection.ready", _envelope("connection.ready", {"sid": sid}), to=sid)


@sio.event
async def disconnect(sid: str) -> None:
    """Log a Socket.IO disconnection at the channel boundary."""

    logger.info("Socket.IO client disconnected: sid=%s", sid)


TELEMETRY_UPDATED_EVENT = "agent.telemetry.updated"


async def emit_agent_telemetry_updated(
    telemetry: Telemetry,
    request_id: str | None = None,
) -> None:
    """Broadcast the agent.telemetry.updated event built from a persisted row.

    Sends the contract envelope to every connected client (no rooms). Side effect
    only; callers stay transport-agnostic. Exceptions propagate to the caller,
    which applies the best-effort policy.
    """

    event = AgentTelemetryUpdatedEvent(
        payload=AgentTelemetryUpdatedPayload(
            agent_id=telemetry.agent_id,
            latest_state=AgentLatestStatePayload(
                lat=telemetry.lat,
                lng=telemetry.lng,
                speed=telemetry.speed,
                battery=telemetry.battery,
                status=telemetry.status,
                recorded_at=telemetry.recorded_at,
            ),
        ),
        ts=datetime.now(timezone.utc),
        request_id=request_id,
    )

    # No `to=` / `room=`: broadcast to every connected client (MVP fan-out).
    await sio.emit(TELEMETRY_UPDATED_EVENT, event.model_dump(mode="json", by_alias=True))

    logger.debug("Emitted %s agent_id=%s", TELEMETRY_UPDATED_EVENT, telemetry.agent_id)