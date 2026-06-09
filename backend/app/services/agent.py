from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.repositories.agent import get_agent, insert_agent, list_agents
from app.schemas.agent import AgentCreate


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
