import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.agent import AgentCreate, AgentCurrentState, AgentRead
from app.services.agent import AgentNotFoundError, AgentService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_agent_service(
    session: AsyncSession = Depends(get_db_session),
) -> AgentService:
    """Provide an AgentService bound to the request-scoped database session.

    One instance per request; never a global singleton that would hold a stale
    or shared session.
    """
    return AgentService(session)


@router.post(
    "/agents",
    response_model=AgentRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_agent(
    payload: AgentCreate,
    service: AgentService = Depends(get_agent_service),
) -> AgentRead:
    """Register a new agent and return the persisted record (HTTP 201).

    The request body is not logged; the service logs the created agent id as the
    business outcome.
    """
    logger.info("agent_create_requested", extra={"event": "agent.create.requested"})
    return await service.create_agent(payload)


@router.get("/agents", response_model=list[AgentRead])
async def list_all_agents(
    service: AgentService = Depends(get_agent_service),
) -> list[AgentRead]:
    """Return all registered agents (newest first)."""
    agents = await service.get_agents()
    logger.info(
        "agents_listed",
        extra={"event": "agent.list.completed", "count": len(agents)},
    )
    return agents


@router.get("/agents/current-state", response_model=list[AgentCurrentState])
async def list_current_state(
    service: AgentService = Depends(get_agent_service),
) -> list[AgentCurrentState]:
    """Return each agent merged with its latest cached state for the live view."""
    states = await service.get_current_state()
    logger.info(
        "agents_current_state_listed",
        extra={"event": "agent.current_state.completed", "count": len(states)},
    )
    return states


@router.get("/agents/{agent_id}", response_model=AgentRead)
async def get_one_agent(
    agent_id: int,
    service: AgentService = Depends(get_agent_service),
) -> AgentRead:
    """Return one registered agent or translate a missing agent into HTTP 404.

    The expected unknown-agent case is logged once here (WARNING) at the HTTP
    boundary; the service raises the domain exception without logging it.
    """
    try:
        return await service.get_agent_by_id(agent_id)
    except AgentNotFoundError as exc:
        logger.warning(
            "agent_not_found",
            extra={"event": "agent.get.not_found", "agent_id": agent_id},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))