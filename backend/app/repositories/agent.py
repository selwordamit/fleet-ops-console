from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.schemas.agent import AgentCreate


async def get_agent(session: AsyncSession, agent_id: int) -> Agent | None:
    # Primary-key lookup; returns None when the agent does not exist.
    return await session.get(Agent, agent_id)


async def list_agents(session: AsyncSession) -> list[Agent]:
    # Newest first so freshly registered agents surface at the top.
    result = await session.scalars(select(Agent).order_by(Agent.id.desc()))
    return list(result)


async def insert_agent(session: AsyncSession, payload: AgentCreate) -> Agent:
    # Add and flush so the generated id/timestamps are available to the caller.
    # Commit is the service's responsibility (it owns the transaction boundary).
    row = Agent(name=payload.name, type=payload.type, status=payload.status)
    session.add(row)
    await session.flush()
    return row
