from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Agent(Base):
    """A registered fleet vehicle/device.

    First-version model: identity and operational status only. Telemetry,
    alert rules, and commands are separate concerns added in later phases.
    """

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Vehicle category, e.g. truck/van/scooter. Free-form string for now; no enum yet.
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Operational status (idle/en-route/stopped/offline). Defaults to offline because a
    # newly registered agent has not reported telemetry yet.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="offline", server_default="offline"
    )
    # Null until the agent's first telemetry report; used later for offline detection.
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
