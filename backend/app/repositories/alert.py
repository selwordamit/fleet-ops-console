from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.schemas.enums import AlertSeverity, AlertType


async def get_active_alert(
    session: AsyncSession,
    agent_id: int,
    alert_type: AlertType,
) -> Alert | None:
    result = await session.scalars(
        select(Alert)
        .where(Alert.agent_id == agent_id)
        .where(Alert.alert_type == alert_type)
        .where(Alert.resolved_at.is_(None))
    )
    return result.first()


async def insert_alert(
    session: AsyncSession,
    agent_id: int,
    alert_type: AlertType,
    severity: AlertSeverity,
    value: float,
    threshold: float,
    message: str,
) -> Alert:
    row = Alert(
        agent_id=agent_id,
        alert_type=alert_type,
        severity=severity,
        value=value,
        threshold=threshold,
        message=message,
    )
    session.add(row)
    await session.flush()
    return row


async def resolve_alert(
    session: AsyncSession,
    alert: Alert,
    resolved_at: datetime,
) -> Alert:
    alert.resolved_at = resolved_at
    await session.flush()
    return alert


async def list_active_alerts(session: AsyncSession) -> list[Alert]:
    result = await session.scalars(
        select(Alert)
        .where(Alert.resolved_at.is_(None))
        .order_by(Alert.triggered_at.desc())
    )
    return list(result)