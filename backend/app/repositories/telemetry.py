from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telemetry import Telemetry
from app.schemas.telemetry import TelemetryCreate


async def get_latest_telemetry_for_agent(
    session: AsyncSession, agent_id: int
) -> Telemetry | None:
    result = await session.scalars(
        select(Telemetry)
        .where(Telemetry.agent_id == agent_id)
        .order_by(Telemetry.recorded_at.desc())
        .limit(1)
    )
    return result.first()


async def insert_telemetry(
    session: AsyncSession, agent_id: int, payload: TelemetryCreate
) -> Telemetry:
    row = Telemetry(
        agent_id=agent_id,
        lat=payload.lat,
        lng=payload.lng,
        speed=payload.speed,
        battery=payload.battery,
        status=payload.status,
    )
    session.add(row)
    return row
