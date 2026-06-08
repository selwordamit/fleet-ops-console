import inspect

from redis.asyncio import Redis

from app.core.config import settings
from app.cache.client import check_redis_connection, redis_client


def test_redis_url_default():
    # The default points at the docker-compose redis service.
    assert settings.redis_url == "redis://localhost:6379/0"


def test_redis_client_is_async_client():
    # Confirms we built an async Redis client, matching the async backend.
    assert isinstance(redis_client, Redis)


def test_check_redis_connection_is_coroutine():
    # Connecting to Redis is I/O work, so the probe must be awaitable.
    assert inspect.iscoroutinefunction(check_redis_connection)
