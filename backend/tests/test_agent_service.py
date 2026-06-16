"""Unit tests for AgentService, proving its dependencies are constructor-injectable.

Collaborators (agent repository functions and the Redis state reader) are
injected as mocks, so these run without a live Postgres or Redis. They also lock
in two behaviors the refactor must preserve: the service owns the transaction
boundary (commit + refresh), and a missing agent raises AgentNotFoundError.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.agent import AgentCreate
from app.services.agent import AgentNotFoundError, AgentService


def test_create_agent_rolls_back_and_reraises_on_db_failure():
    # commit() raising a SQLAlchemyError must trigger rollback and propagate.
    session = AsyncMock()
    session.commit.side_effect = SQLAlchemyError("commit failed")
    insert_agent = AsyncMock(return_value=SimpleNamespace(id=1, type="truck"))
    payload = AgentCreate(name="Truck 1", type="truck", status="idle")

    service = AgentService(session, insert_agent=insert_agent)

    with pytest.raises(SQLAlchemyError):
        asyncio.run(service.create_agent(payload))

    session.rollback.assert_awaited_once()
    session.refresh.assert_not_awaited()  # never reached after a failed commit


def test_create_agent_commits_and_refreshes_injected_session():
    session = AsyncMock()
    row = SimpleNamespace(id=1, type="truck")  # id/type read by the success log
    insert_agent = AsyncMock(return_value=row)
    payload = AgentCreate(name="Truck 1", type="truck", status="idle")

    result = asyncio.run(
        AgentService(session, insert_agent=insert_agent).create_agent(payload)
    )

    assert result is row
    insert_agent.assert_awaited_once_with(session, payload)
    session.commit.assert_awaited_once()      # transaction owned by the service
    session.refresh.assert_awaited_once_with(row)


def test_get_agent_by_id_raises_when_missing():
    session = AsyncMock()
    get_agent = AsyncMock(return_value=None)

    service = AgentService(session, get_agent=get_agent)

    with pytest.raises(AgentNotFoundError):
        asyncio.run(service.get_agent_by_id(123))


def test_get_current_state_merges_repo_and_redis_reader():
    session = AsyncMock()
    agent = SimpleNamespace(
        id=1, name="Truck 1", type="truck", status="idle", last_seen=None
    )
    list_agents = AsyncMock(return_value=[agent])
    read_agent_state = AsyncMock(
        return_value={
            "lat": 32.0,
            "lng": 34.8,
            "speed": 12.5,
            "battery": 80,
            "status": "en-route",
            "recorded_at": "2026-06-15T08:00:00Z",
        }
    )

    service = AgentService(
        session, list_agents=list_agents, read_agent_state=read_agent_state
    )
    result = asyncio.run(service.get_current_state())

    assert len(result) == 1
    assert result[0].id == 1
    assert result[0].latest_state is not None
    assert result[0].latest_state.status == "en-route"
    read_agent_state.assert_awaited_once_with(1)
