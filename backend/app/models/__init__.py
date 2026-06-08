# Importing models here registers their tables on Base.metadata, which is what
# Alembic autogenerate inspects. Any new model must be imported in this package.
from app.models.agent import Agent
from app.models.telemetry import Telemetry

__all__ = ["Agent", "Telemetry"]
