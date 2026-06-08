from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Telemetry(Base):
    """A single telemetry report from an agent.

    Append-heavy history table: one row per report. Latest/current state is also
    mirrored into Redis for fast reads; this table is the durable record.
    """

    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(primary_key=True)
    # CASCADE so an agent's history is removed if the agent is deleted.
    # Indexed because telemetry is almost always queried per-agent.
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    speed: Mapped[float] = mapped_column(Float, nullable=False)
    battery: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # Server-set ingestion time for this first version; client-supplied timestamps
    # can be added later if the simulator/device needs to report its own clock.
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
