from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.telemetry import TelemetryCreate, TelemetryRead
from app.services.telemetry import AgentNotFoundError, ingest_telemetry

router = APIRouter()


@router.post(
    "/agents/{agent_id}/telemetry",
    response_model=TelemetryRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_telemetry(
    agent_id: int,
    payload: TelemetryCreate,
    session: AsyncSession = Depends(get_db_session),
) -> TelemetryRead:
    # Thin handler: validation is in the schema, orchestration is in the service.
    try:
        return await ingest_telemetry(session, agent_id, payload)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
