import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.repositories.alert import (
    get_active_alert,
    insert_alert,
    resolve_alert,
)
from app.schemas.enums import AlertSeverity, AlertType

logger = logging.getLogger(__name__)


@dataclass
class AlertChange:
    """Returned when alert state changes; None means no change."""

    kind: Literal["triggered", "resolved"]
    alert: Alert


class AlertService:
    """Evaluates built-in alert rules and stages DB changes through the repository.

    Does not commit. The caller (TelemetryService) owns the full transaction so
    that telemetry and alert writes are committed atomically.

    Collaborators default to the real repository functions but are
    constructor-injectable for testing without a live database.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        get_active_alert=get_active_alert,
        insert_alert=insert_alert,
        resolve_alert=resolve_alert,
    ) -> None:
        self._session = session
        self._get_active_alert = get_active_alert
        self._insert_alert = insert_alert
        self._resolve_alert = resolve_alert

    async def evaluate_low_battery(
        self,
        agent_id: int,
        battery: float,
        threshold: float,
    ) -> AlertChange | None:
        """Evaluate the low-battery rule for one agent.

        Trigger when battery < threshold; resolve when battery >= threshold.
        Returns AlertChange on a state transition, None when nothing changes.
        """
        active = await self._get_active_alert(
            self._session, agent_id, AlertType.low_battery
        )

        if battery < threshold:
            if active is not None:
                return None  # already alerted — no duplicate
            alert = await self._insert_alert(
                self._session,
                agent_id=agent_id,
                alert_type=AlertType.low_battery,
                severity=AlertSeverity.warning,
                value=battery,
                threshold=threshold,
                message=f"Battery low: {battery}% below threshold {threshold}%",
            )
            logger.info(
                "alert_triggered",
                extra={
                    "event": "alert.triggered",
                    "agent_id": agent_id,
                    "alert_type": AlertType.low_battery,
                    "battery": battery,
                    "threshold": threshold,
                },
            )
            return AlertChange(kind="triggered", alert=alert)

        # battery >= threshold — healthy
        if active is None:
            return None  # already clear — nothing to resolve
        resolved = await self._resolve_alert(
            self._session,
            alert=active,
            resolved_at=datetime.now(tz=timezone.utc),
        )
        logger.info(
            "alert_resolved",
            extra={
                "event": "alert.resolved",
                "agent_id": agent_id,
                "alert_type": AlertType.low_battery,
                "battery": battery,
                "threshold": threshold,
            },
        )
        return AlertChange(kind="resolved", alert=resolved)
