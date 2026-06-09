from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.agent import AgentCreate, AgentRead
from app.services.agent import (
    AgentNotFoundError,
    create_agent,
    get_agent_by_id,
    get_agents,
)

router = APIRouter()


@router.post(
    "/agents",
    response_model=AgentRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_agent(
    payload: AgentCreate,
    session: AsyncSession = Depends(get_db_session),
) -> AgentRead:
    # Thin handler: validation is in the schema, orchestration is in the service.
    return await create_agent(session, payload)


@router.get("/agents", response_model=list[AgentRead])
async def list_all_agents(
    session: AsyncSession = Depends(get_db_session),
) -> list[AgentRead]:
    return await get_agents(session)


@router.get("/agents/{agent_id}", response_model=AgentRead)
async def get_one_agent(
    agent_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> AgentRead:
    try:
        return await get_agent_by_id(session, agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
