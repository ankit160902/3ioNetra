"""Shared Redis connection pool for all backend services.

All services (CacheService, RedisSessionManager, ConversationStorage) share
a single ConnectionPool to stay within the Redis connection limit.
Supports REDIS_URL (including rediss:// for TLS) or individual host/port/password.
"""

import logging
import redis.asyncio as aioredis
from config import settings

logger = logging.getLogger(__name__)

_pool: aioredis.ConnectionPool | None = None


def get_redis_pool() -> aioredis.ConnectionPool:
    """Return the singleton Redis connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        if settings.REDIS_URL:
            _pool = aioredis.ConnectionPool.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                socket_connect_timeout=5,
                socket_timeout=10,
                retry_on_timeout=True,
            )
            logger.info(
                f"Redis shared pool created from URL "
                f"(max_connections={settings.REDIS_MAX_CONNECTIONS})"
            )
        else:
            _pool = aioredis.ConnectionPool(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                socket_connect_timeout=3,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            logger.info(
                f"Redis shared pool created "
                f"(host={settings.REDIS_HOST}:{settings.REDIS_PORT}, "
                f"db={settings.REDIS_DB}, max_connections={settings.REDIS_MAX_CONNECTIONS})"
            )
    return _pool


def get_redis_client() -> aioredis.Redis:
    """Return a new Redis client backed by the shared connection pool."""
    return aioredis.Redis(connection_pool=get_redis_pool())


async def close_redis_pool() -> None:
    """Disconnect all connections in the shared pool. Call once at shutdown."""
    global _pool
    if _pool is not None:
        logger.info("Closing shared Redis connection pool...")
        await _pool.disconnect()
        _pool = None
