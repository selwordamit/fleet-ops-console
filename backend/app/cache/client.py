# ======================================================================================
# REDIS CLIENT | Operational/ephemeral state connection
# ======================================================================================
# This file manages runtime communication between FastAPI and the Redis Docker.
#
# Core Components:
# 1. Client: A single, long-lived async client. redis-py manages an internal connection
#    pool, so the client is created once and shared, not per-request.
# 2. check_redis_connection(): A minimal liveness probe used to verify connectivity.
#
# Scope for this checkpoint: connection only. No caching, pub/sub, presence, or rate
# limiting yet.
# ======================================================================================

from redis.asyncio import Redis

from app.core.config import settings

# One client per process. decode_responses=True returns str instead of bytes, which is
# convenient for the string keys/values this project will use later.
redis_client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)


async def check_redis_connection() -> bool:
    # Minimal liveness probe: a successful PING proves the client can reach Redis.
    return await redis_client.ping()
