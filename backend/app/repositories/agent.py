from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.schemas.agent import AgentCreate


async def get_agent(session: AsyncSession, agent_id: int) -> Agent | None:
    return await session.get(Agent, agent_id)


async def list_agents(session: AsyncSession) -> list[Agent]:
    result = await session.scalars(select(Agent).order_by(Agent.id.desc()))
    return list(result)


async def insert_agent(session: AsyncSession, payload: AgentCreate) -> Agent:
    row = Agent(name=payload.name, type=payload.type, status=payload.status)
    session.add(row)
    return row
