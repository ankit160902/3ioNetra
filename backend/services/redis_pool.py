"""Shared Redis async connection pool — single pool reused by all services."""
import logging
import redis.asyncio as aioredis
from typing import Optional

logger = logging.getLogger(__name__)

_pool: Optional[aioredis.ConnectionPool] = None


def get_redis_pool() -> Optional[aioredis.ConnectionPool]:
    """Return the shared async Redis connection pool, creating it on first call.

    Returns None if Redis settings are not configured (safe degraded mode).
    Pool size 50 per process: enough for concurrent coroutines without
    exhausting Redis server limits across many replicas.
    """
    global _pool
    if _pool is not None:
        return _pool

    from config import settings
    if not settings.REDIS_HOST:
        return None

    try:
        _pool = aioredis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
            max_connections=50,
            socket_connect_timeout=3,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        logger.info(f"Shared Redis pool created (host={settings.REDIS_HOST}:{settings.REDIS_PORT} max_connections=50)")
        return _pool
    except Exception as e:
        logger.error(f"Failed to create shared Redis pool: {e}")
        return None


async def close_redis_pool() -> None:
    """Disconnect the shared pool. Call on app shutdown."""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
        logger.info("Shared Redis pool closed")
