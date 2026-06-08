from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telemetry import Telemetry
from app.schemas.telemetry import TelemetryCreate


async def insert_telemetry(
    session: AsyncSession, agent_id: int, payload: TelemetryCreate
) -> Telemetry:
    # Add and flush so the generated id/recorded_at are available to the caller.
    # Commit is the service's responsibility (it owns the transaction boundary).
    row = Telemetry(
        agent_id=agent_id,
        lat=payload.lat,
        lng=payload.lng,
        speed=payload.speed,
        battery=payload.battery,
        status=payload.status,
    )
    session.add(row)
    await session.flush()
    return row
