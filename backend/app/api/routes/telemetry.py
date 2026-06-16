import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.telemetry import TelemetryCreate, TelemetryRead
from app.services.telemetry import AgentNotFoundError, TelemetryService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_telemetry_service(
    session: AsyncSession = Depends(get_db_session),
) -> TelemetryService:
    """Provide a TelemetryService bound to the request-scoped database session.

    One instance per request; never a global singleton holding a shared session.
    """
    return TelemetryService(session)


@router.post(
    "/agents/{agent_id}/telemetry",
    response_model=TelemetryRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_telemetry(
    agent_id: int,
    payload: TelemetryCreate,
    service: TelemetryService = Depends(get_telemetry_service),
) -> TelemetryRead:
    """Ingest one telemetry report (HTTP 201) or translate an unknown agent to 404.

    High-frequency endpoint: a successful ingest is intentionally not logged at
    INFO to avoid flooding. Only the expected unknown-agent rejection is logged
    (WARNING with agent_id); unexpected failures propagate to the global handler.
    The telemetry payload is not logged.
    """
    try:
        return await service.ingest_telemetry(agent_id, payload)
    except AgentNotFoundError as exc:
        logger.warning(
            "telemetry_agent_not_found",
            extra={"event": "telemetry.ingest.not_found", "agent_id": agent_id},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))