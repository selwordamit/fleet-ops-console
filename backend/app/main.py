import socketio
from fastapi import FastAPI

from app.api.routes.agents import router as agents_router
from app.api.routes.health import router as health_router
from app.api.routes.telemetry import router as telemetry_router
from app.core.config import settings
from app.realtime.socket import sio

# The FastAPI app owns all REST routes exactly as before.
api = FastAPI(title=settings.app_name)

api.include_router(health_router)
api.include_router(agents_router, prefix=settings.api_prefix)
api.include_router(telemetry_router, prefix=settings.api_prefix)

app = socketio.ASGIApp(sio, other_asgi_app=api)
