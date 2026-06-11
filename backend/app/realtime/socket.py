"""Backend Socket.IO foundation.

This module owns the Socket.IO server instance and its lifecycle event handlers.
Scope for this checkpoint is intentionally tiny: prove that a client can connect
and disconnect, and log both. It does NOT emit telemetry yet — that flow
(`agent.telemetry.updated`, see docs/ws-protocol.md) is added in a later step.

The server is created here and mounted onto the FastAPI ASGI app in app/main.py.
"""

import logging
from datetime import datetime, timezone

import socketio

# No central logging config exists yet (core/logging is planned). Until then,
# ensure connect/disconnect lines are actually visible: if nothing has configured
# the root logger, add a basic stderr handler. Uvicorn configures its own loggers
# (which do not propagate), so this does not duplicate uvicorn output.
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# async_mode="asgi" lets this server be wrapped by socketio.ASGIApp alongside
# FastAPI. cors_allowed_origins="*" is a development-only convenience for the
# foundation; origin restriction and socket auth are deferred to a later step.
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
)


def _envelope(event_type: str, payload: dict) -> dict:
    """Wrap an outbound message in the project-standard envelope.

    Mirrors docs/ws-protocol.md ({type, payload, ts, requestId}). requestId is
    omitted here because connection.ready is not correlated to a request.
    """

    return {
        "type": event_type,
        "payload": payload,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@sio.event
async def connect(sid: str, environ: dict, auth: dict | None = None) -> None:
    """Called when a client establishes a Socket.IO connection.

    Returning normally (no exception, no False) accepts the connection. We do not
    authenticate yet — that is deferred to the socket auth checkpoint.
    """

    logger.info("Socket.IO client connected: sid=%s", sid)

    # Optional, simple readiness signal so a connecting client gets immediate
    # confirmation the channel is live. Not part of the telemetry contract.
    await sio.emit("connection.ready", _envelope("connection.ready", {"sid": sid}), to=sid)


@sio.event
async def disconnect(sid: str) -> None:
    """Called when a client disconnects."""

    logger.info("Socket.IO client disconnected: sid=%s", sid)
