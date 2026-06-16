import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.agent_state import read_agent_state
from app.models.agent import Agent
from app.repositories.agent import get_agent, insert_agent, list_agents
from app.schemas.agent import AgentCreate, AgentCurrentState, AgentLatestState

logger = logging.getLogger(__name__)


class AgentNotFoundError(Exception):
    """Raised when an agent id has no matching row; routes map it to HTTP 404."""

    def __init__(self, agent_id: int) -> None:
        self.agent_id = agent_id
        super().__init__(f"Agent {agent_id} not found")


class AgentService:
    """Agent read/write operations and the dependencies they orchestrate.

    Constructed per request and bound to the request-scoped session; owns the
    transaction boundary for writes. Collaborators default to the real
    implementations but can be injected for testing.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        insert_agent=insert_agent,
        get_agent=get_agent,
        list_agents=list_agents,
        read_agent_state=read_agent_state,
    ) -> None:
        self._session = session
        self._insert_agent = insert_agent
        self._get_agent = get_agent
        self._list_agents = list_agents
        self._read_agent_state = read_agent_state

    async def create_agent(self, payload: AgentCreate) -> Agent:
        """Persist a new agent and return the refreshed database row.

        Owns the transaction boundary: rolls back on a database failure and
        re-raises so the global handler logs the traceback once (no logging
        here). Logs the created agent id as the business outcome.
        """
        try:
            agent = await self._insert_agent(self._session, payload)
            await self._session.commit()
        except SQLAlchemyError:
            await self._session.rollback()
            raise
        await self._session.refresh(agent)
        logger.info(
            "agent_created",
            extra={"event": "agent.created", "agent_id": agent.id, "agent_type": agent.type},
        )
        return agent

    async def get_agents(self) -> list[Agent]:
        """Return all agents (newest first)."""
        return await self._list_agents(self._session)

    async def get_agent_by_id(self, agent_id: int) -> Agent:
        """Return one agent, or raise AgentNotFoundError if no row matches.

        The not-found case is logged at the route boundary, not here, to avoid a
        duplicate log for the same condition.
        """
        agent = await self._get_agent(self._session, agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id)
        return agent

    async def get_current_state(self) -> list[AgentCurrentState]:
        """Merge each agent's identity (Postgres) with its latest state (Redis).

        Agents with no cached state are returned with ``latest_state`` as None
        rather than skipped.
        """
        agents = await self._list_agents(self._session)
        result: list[AgentCurrentState] = []
        for agent in agents:
            raw = await self._read_agent_state(agent.id)
            latest = AgentLatestState(**raw) if raw is not None else None
            result.append(
                AgentCurrentState(
                    id=agent.id,
                    name=agent.name,
                    type=agent.type,
                    status=agent.status,
                    last_seen=agent.last_seen,
                    latest_state=latest,
                )
            )
        return result
