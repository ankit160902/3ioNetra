import json
import logging
import hashlib
import time as _time
from collections import OrderedDict
from typing import Optional, Any
from config import settings

logger = logging.getLogger(__name__)


class _LRUCache:
    """In-memory LRU cache (L1) in front of Redis (L2).

    OrderedDict-based, max ``max_size`` entries, TTL-aware.
    Thread-safe under asyncio's single-threaded event loop.
    """

    def __init__(self, max_size: int = 200):
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if _time.monotonic() > expires_at:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        # Cap L1 TTL at 5 minutes to limit staleness
        capped_ttl = min(ttl, 300)
        expires_at = _time.monotonic() + capped_ttl
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (expires_at, value)
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)


class CacheService:
    """Redis-based caching service with in-memory LRU L1 layer."""

    def __init__(self):
        self._enabled = False
        self._l1 = _LRUCache(max_size=200)
        try:
            import redis.asyncio as aioredis
            import redis as sync_redis
            self._redis = aioredis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.CACHE_REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                max_connections=20,
                socket_connect_timeout=3,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            # Verify connection with a sync ping (same pattern as RedisSessionManager)
            test_client = sync_redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.CACHE_REDIS_DB,
                password=settings.REDIS_PASSWORD,
                socket_connect_timeout=3,
            )
            test_client.ping()
            test_client.close()
            self._enabled = True
            logger.info(f"CacheService initialized (Redis DB {settings.CACHE_REDIS_DB} + L1 LRU)")
        except Exception as e:
            logger.warning(f"CacheService disabled: Redis not available ({e})")

    def _generate_key(self, prefix: str, **kwargs) -> str:
        """Generate a deterministic cache key from input parameters."""
        # Sort keys to ensure deterministic ordering
        sorted_items = sorted(kwargs.items())
        serialized = json.dumps(sorted_items)
        hash_val = hashlib.md5(serialized.encode()).hexdigest()
        return f"cache:{prefix}:{hash_val}"

    async def get(self, prefix: str, **kwargs) -> Optional[Any]:
        """Retrieve a value from cache. Checks L1 (memory) then L2 (Redis)."""
        key = self._generate_key(prefix, **kwargs)

        # L1 check (zero-cost)
        l1_val = self._l1.get(key)
        if l1_val is not None:
            logger.debug(f"L1 Cache HIT for {key}")
            return l1_val

        if not self._enabled:
            return None

        try:
            data = await self._redis.get(key)
            if data:
                parsed = json.loads(data)
                # Backfill L1 (5-min cap)
                self._l1.set(key, parsed, 300)
                logger.debug(f"Cache HIT for {key}")
                return parsed
            logger.debug(f"Cache MISS for {key}")
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None

    async def set(self, prefix: str, val: Any, ttl: int = 3600, **kwargs) -> None:
        """Store a value in both L1 (memory) and L2 (Redis)."""
        key = self._generate_key(prefix, **kwargs)

        # Always write to L1 (even if Redis is down)
        self._l1.set(key, val, ttl)

        if not self._enabled:
            return

        try:
            await self._redis.setex(key, ttl, json.dumps(val))
            logger.debug(f"Cache SET for {key} (TTL={ttl}s)")
        except Exception as e:
            logger.error(f"Cache set error: {e}")

    async def close(self) -> None:
        """Close Redis connection."""
        if self._enabled:
            logger.info("Closing CacheService Redis connection...")
            await self._redis.close()
            self._enabled = False

_cache_service: Optional[CacheService] = None

def get_cache_service() -> CacheService:
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
