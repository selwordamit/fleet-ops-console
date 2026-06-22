import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.agent_state import write_agent_state
from app.cache.client import redis_client
from app.cache.keys import agent_state_key
from app.core.config import settings
from app.db.session import async_session_factory
from app.models.agent import Agent
from app.models.telemetry import Telemetry
from app.realtime.socket import emit_agent_telemetry_updated, sio
from app.repositories.agent import get_agent
from app.repositories.telemetry import insert_telemetry
from app.schemas.telemetry import TelemetryCreate
from app.services.alert import AlertChange, AlertService

logger = logging.getLogger(__name__)

TELEMETRY_BATCH_EVENT = "agent.telemetry.batch"


class TelemetryBatcher:
    """Decouples the HTTP ingest path from expensive I/O by batching telemetry.

    Callers append to the buffer in O(1); a background loop drains it every
    flush_interval seconds with a single Postgres bulk insert, a Redis pipeline,
    and one Socket.IO broadcast — regardless of how many agents reported.
    """

    def __init__(self, flush_interval: float = 0.1) -> None:
        self._flush_interval = flush_interval
        self._buffer: list[tuple[int, TelemetryCreate]] = []
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None

    async def add(self, agent_id: int, payload: TelemetryCreate) -> None:
        """Append one telemetry item to the buffer (non-blocking for the caller)."""
        async with self._lock:
            self._buffer.append((agent_id, payload))

    def start(self) -> None:
        """Spawn the background flush loop. Call once at application startup."""
        self._task = asyncio.create_task(self._flush_loop())
        logger.info("TelemetryBatcher started flush_interval=%.3fs", self._flush_interval)

    async def stop(self) -> None:
        """Cancel the background loop and flush any remaining buffered items."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._drain()
        logger.info("TelemetryBatcher stopped")

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(self._flush_interval)
            await self._drain()

    async def _drain(self) -> None:
        """Atomically swap out the buffer then flush the snapshot off the hot path."""
        async with self._lock:
            if not self._buffer:
                return
            batch, self._buffer = self._buffer, []

        await self._flush(batch)

    async def _flush(self, batch: list[tuple[int, TelemetryCreate]]) -> None:
        """Persist a batch: bulk Postgres insert """
        flush_ts = datetime.now(timezone.utc)

        # --- 1. Bulk INSERT + alert evaluation in one transaction ---
        async with async_session_factory() as session:
            rows = [
                Telemetry(
                    agent_id=aid,
                    lat=p.lat,
                    lng=p.lng,
                    speed=p.speed,
                    battery=p.battery,
                    status=p.status,
                )
                for aid, p in batch
            ]
            session.add_all(rows)

            try:
                for aid, p in batch:
                    await AlertService(session).evaluate_telemetry_alerts(
                        agent_id=aid,
                        battery=p.battery,
                        low_battery_threshold=settings.low_battery_threshold,
                    )
                await session.commit()
            except SQLAlchemyError:
                await session.rollback()
                logger.error(
                    "telemetry_batch_flush_failed batch_size=%d",
                    len(batch),
                    exc_info=True,
                )
                return

        # --- 2. Bulk UPDATE Redis: last reading per agent wins for current state ---
        last_per_agent: dict[int, TelemetryCreate] = {}
        for aid, p in batch:
            last_per_agent[aid] = p

        try:
            pipe = redis_client.pipeline(transaction=False)
            for aid, p in last_per_agent.items():
                state = {
                    "agent_id": aid,
                    "lat": p.lat,
                    "lng": p.lng,
                    "speed": p.speed,
                    "battery": p.battery,
                    "status": p.status,
                    "recorded_at": flush_ts.isoformat(),
                }
                pipe.set(agent_state_key(aid), json.dumps(state))
            await pipe.execute()
        except Exception:
            logger.warning("telemetry_batch_redis_failed", exc_info=True)

        # --- 3. One Socket.IO broadcast for the entire flush window ---
        try:
            updates = [
                {
                    "agent_id": aid,
                    "lat": p.lat,
                    "lng": p.lng,
                    "speed": p.speed,
                    "battery": p.battery,
                    "status": p.status,
                }
                for aid, p in last_per_agent.items()
            ]
            await sio.emit(
                TELEMETRY_BATCH_EVENT,
                {
                    "type": TELEMETRY_BATCH_EVENT,
                    "payload": updates,
                    "ts": flush_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
        except Exception:
            logger.warning("telemetry_batch_emit_failed", exc_info=True)

        logger.debug(
            "telemetry_batch_flushed count=%d agents=%d",
            len(batch),
            len(last_per_agent),
        )


# Module-level singleton: started/stopped by the FastAPI lifespan hook in main.py.
batcher = TelemetryBatcher()


class AgentNotFoundError(Exception):
    """Raised when telemetry targets an unknown agent; routes map it to HTTP 404."""

    def __init__(self, agent_id: int) -> None:
        self.agent_id = agent_id
        super().__init__(f"Agent {agent_id} not found")


# In-memory set of existing agent ids, used to validate telemetry without a
# per-request Postgres SELECT. Loaded once at startup from the DB and kept in
# sync as new agents are created. Safe as module-level state because the backend
# runs as a single Uvicorn worker; a multi-worker deployment would need Redis.
_known_agent_ids: set[int] = set()


async def load_known_agents(session: AsyncSession) -> None:
    """Populate the agent-id cache from Postgres once at application startup."""
    ids = await session.scalars(select(Agent.id))
    _known_agent_ids.clear()
    _known_agent_ids.update(ids)
    logger.info("known_agents_loaded count=%d", len(_known_agent_ids))


def register_known_agent(agent_id: int) -> None:
    """Add a newly created agent to the cache so its telemetry is accepted."""
    _known_agent_ids.add(agent_id)


async def update_latest_state(row: Telemetry) -> None:
    """Mirror the just-persisted telemetry into Redis as the agent's latest state.

    Module-level so it can be injected into ``TelemetryService`` as the Redis
    latest-state writer dependency (and mocked in tests without a live Redis).
    Delegates serialisation to the shared cache writer.
    """
    await write_agent_state(row)


async def _evaluate_telemetry_alerts(
    session: AsyncSession,
    *,
    agent_id: int,
    battery: float,
    low_battery_threshold: float,
) -> list[AlertChange]:
    """Default alert evaluator: delegates to AlertService using the shared session."""
    return await AlertService(session).evaluate_telemetry_alerts(
        agent_id=agent_id,
        battery=battery,
        low_battery_threshold=low_battery_threshold,
    )


class TelemetryService:
    """Owns the telemetry ingestion flow and the dependencies it orchestrates.

    Constructed once per request, bound to the request-scoped ``AsyncSession``.
    All collaborators are injected as keyword arguments so tests can substitute
    fakes without a live database, Redis, or Socket.IO server.

    With batching enabled, ``ingest_telemetry`` validates the agent then delegates
    to the module-level ``batcher``; the expensive I/O (insert, Redis, alerts,
    emit) runs asynchronously in the batcher's flush loop.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        get_agent=get_agent,
        insert_telemetry=insert_telemetry,
        update_latest_state=update_latest_state,
        emit_telemetry_updated=emit_agent_telemetry_updated,
        evaluate_telemetry_alerts=_evaluate_telemetry_alerts,
        low_battery_threshold: float = settings.low_battery_threshold,
    ) -> None:
        self._session = session
        self._get_agent = get_agent
        self._insert_telemetry = insert_telemetry
        self._update_latest_state = update_latest_state
        self._emit_telemetry_updated = emit_telemetry_updated
        self._evaluate_telemetry_alerts = evaluate_telemetry_alerts
        self._low_battery_threshold = low_battery_threshold

    async def ingest_telemetry(
        self, agent_id: int, payload: TelemetryCreate
    ) -> Telemetry:
        """Validate the agent exists, buffer the telemetry, and return immediately.

        The 404 guard is an O(1) in-memory set check (no DB round-trip on the
        hot path) so the simulator gets an immediate rejection for unknown
        agents. The actual insert, alert evaluation, Redis update, and Socket.IO
        emit are handled by the TelemetryBatcher's background flush loop.

        Returns a placeholder Telemetry (id=0) so the route's response_model
        can serialise a valid receipt without waiting for the DB insert.
        """
        if agent_id not in _known_agent_ids:
            raise AgentNotFoundError(agent_id)

        await batcher.add(agent_id, payload)

        # Placeholder: id=0 signals "buffered, not yet persisted".
        # Clients should treat this response as a receipt, not the persisted row.
        return Telemetry(
            id=0,
            agent_id=agent_id,
            lat=payload.lat,
            lng=payload.lng,
            speed=payload.speed,
            battery=payload.battery,
            status=payload.status,
            recorded_at=datetime.now(timezone.utc),
        )
