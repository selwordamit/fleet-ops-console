from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent


async def get_agent(session: AsyncSession, agent_id: int) -> Agent | None:
    # Primary-key lookup; returns None when the agent does not exist.
    return await session.get(Agent, agent_id)
