from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.telemetry import router as telemetry_router
from app.core.config import settings

app = FastAPI(title=settings.app_name)

app.include_router(health_router)
app.include_router(telemetry_router, prefix=settings.api_prefix)
