from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.agent_state import read_agent_state
from app.models.agent import Agent
from app.repositories.agent import get_agent, insert_agent, list_agents
from app.schemas.agent import AgentCreate, AgentCurrentState, AgentLatestState


class AgentNotFoundError(Exception):
    """Raised when an agent is requested by id but does not exist."""

    def __init__(self, agent_id: int) -> None:
        self.agent_id = agent_id
        super().__init__(f"Agent {agent_id} not found")


async def create_agent(session: AsyncSession, payload: AgentCreate) -> Agent:
    # Persist the new agent and commit; the service owns the transaction boundary.
    row = await insert_agent(session, payload)
    await session.commit()
    await session.refresh(row)
    return row


async def get_agents(session: AsyncSession) -> list[Agent]:
    return await list_agents(session)


async def get_agent_by_id(session: AsyncSession, agent_id: int) -> Agent:
    agent = await get_agent(session, agent_id)
    if agent is None:
        raise AgentNotFoundError(agent_id)
    return agent


async def get_current_state(session: AsyncSession) -> list[AgentCurrentState]:
    # Postgres is the source of truth for which agents exist; Redis holds the
    # latest reported state. An agent with no cached state is included with a null
    # latest_state rather than being skipped or failing the whole request.
    agents = await list_agents(session)
    result: list[AgentCurrentState] = []
    for agent in agents:
        raw = await read_agent_state(agent.id)
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
