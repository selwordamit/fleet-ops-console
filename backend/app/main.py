import logging

import socketio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.agents import router as agents_router
from app.api.routes.health import router as health_router
from app.api.routes.telemetry import router as telemetry_router
from app.core.config import settings
from app.realtime.socket import sio

# Single, minimal logging setup for the whole backend process. Guarded so we do
# not clobber a host/uvicorn-provided configuration. Kept here (app assembly)
# rather than scattered across modules; intentionally not a logging framework.
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

logger = logging.getLogger(__name__)

# The FastAPI app owns all REST routes exactly as before.
api = FastAPI(title=settings.app_name)

api.include_router(health_router)
api.include_router(agents_router, prefix=settings.api_prefix)
api.include_router(telemetry_router, prefix=settings.api_prefix)


@api.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Single application-level handler for *unexpected* exceptions.

    Expected business failures (e.g. AgentNotFoundError) are translated to HTTP
    status codes in the routes and never reach here. This is the one place in our
    layers (repository / service / route / handler) that logs the traceback for an
    unhandled exception, so the lower layers re-raise without logging — no
    duplicate stack traces. The request path carries useful context (e.g. the
    agent id in /api/agents/{id}/telemetry) without logging request bodies or
    secrets. The client gets a safe, generic 500 with no internal details.
    """
    logger.exception(
        "unhandled_exception during %s %s",
        request.method,
        request.url.path,
        extra={"event": "http.unhandled_exception"},
    )
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


app = socketio.ASGIApp(sio, other_asgi_app=api)