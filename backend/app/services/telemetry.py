import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.agent_state import write_agent_state
from app.models.telemetry import Telemetry
from app.realtime.socket import TELEMETRY_UPDATED_EVENT, emit_agent_telemetry_updated
from app.repositories.agent import get_agent
from app.repositories.telemetry import insert_telemetry
from app.schemas.telemetry import TelemetryCreate

logger = logging.getLogger(__name__)


class AgentNotFoundError(Exception):
    """Raised when telemetry targets an unknown agent; routes map it to HTTP 404."""

    def __init__(self, agent_id: int) -> None:
        self.agent_id = agent_id
        super().__init__(f"Agent {agent_id} not found")


async def update_latest_state(row: Telemetry) -> None:
    """Mirror the just-persisted telemetry into Redis as the agent's latest state.

    Module-level so it can be injected into ``TelemetryService`` as the Redis
    latest-state writer dependency (and mocked in tests without a live Redis).
    Delegates serialisation to the shared cache writer.
    """
    await write_agent_state(row)


class TelemetryService:
    """Owns the telemetry ingestion flow and the dependencies it orchestrates.

    Constructed once per request, bound to the request-scoped ``AsyncSession``
    (see the route provider). The agent lookup, telemetry insert, Redis writer,
    and Socket.IO emitter are injected as keyword arguments defaulting to the real
    implementations, so tests can substitute fakes. The repository owns the
    transaction boundary; the WebSocket emit is best-effort.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        get_agent=get_agent,
        insert_telemetry=insert_telemetry,
        update_latest_state=update_latest_state,
        emit_telemetry_updated=emit_agent_telemetry_updated,
    ) -> None:
        self._session = session
        self._get_agent = get_agent
        self._insert_telemetry = insert_telemetry
        self._update_latest_state = update_latest_state
        self._emit_telemetry_updated = emit_telemetry_updated

    async def ingest_telemetry(
        self, agent_id: int, payload: TelemetryCreate
    ) -> Telemetry:
        """Persist telemetry, refresh the Redis latest-state, and emit the live event.

        Fixed ordering: verify agent exists -> insert (repository commits) ->
        Redis write -> Socket.IO emit. The emit is best-effort: a push failure
        logs a WARNING and does not change the successful response, while a Redis
        or Postgres failure propagates and skips the emit. Raises
        AgentNotFoundError for an unknown agent.
        """

        if await self._get_agent(self._session, agent_id) is None:
            raise AgentNotFoundError(agent_id)

        telemetry = await self._insert_telemetry(self._session, agent_id, payload)

        try:
            await self._session.commit()
        except SQLAlchemyError:
            await self._session.rollback()
            raise
        await self._session.refresh(telemetry)

        await self._update_latest_state(telemetry)

        try:
            await self._emit_telemetry_updated(telemetry)
        except Exception:

            logger.warning(
                "telemetry_emit_failed",
                extra={"event": TELEMETRY_UPDATED_EVENT, "agent_id": telemetry.agent_id},
                exc_info=True,
            )

        return telemetry
