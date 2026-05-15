import json
import logging
import hashlib
import time as _time
from collections import OrderedDict
from typing import Optional, Any
import redis.asyncio as aioredis
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


# Only these namespaces benefit from L1 (query-keyed, shared across users).
# User-specific keys (sessions, auth tokens) skip L1 to avoid thrash.
_L1_ELIGIBLE_PREFIXES = frozenset({"rag_search", "hyde", "reranker", "judge"})


class CacheService:
    """Redis-based caching service with in-memory LRU L1 layer."""

    def __init__(self):
        self._enabled = False
        self._l1 = _LRUCache(max_size=1000)
        try:
            from services.redis_pool import get_redis_pool
            import redis as sync_redis
            pool = get_redis_pool()
            if pool is None:
                raise RuntimeError("Redis pool not configured")
            self._redis = aioredis.Redis(connection_pool=pool)
            # Verify connection with a sync ping
            test_client = sync_redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                socket_connect_timeout=3,
            )
            test_client.ping()
            test_client.close()
            self._enabled = True
            logger.info(f"CacheService initialized (shared Redis pool + L1 LRU)")
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

        # L1 check — only for query-keyed namespaces (not user-specific keys)
        if prefix in _L1_ELIGIBLE_PREFIXES:
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
                # Backfill L1 for eligible namespaces only (5-min cap)
                if prefix in _L1_ELIGIBLE_PREFIXES:
                    self._l1.set(key, parsed, 300)
                logger.debug(f"Cache HIT for {key}")
                return parsed
            logger.debug(f"Cache MISS for {key}")
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None

    async def set(self, prefix: str, val: Any, ttl: int = 3600, **kwargs) -> None:
        """Store a value in both L1 (memory) and L2 (Redis)."""
        # Guard: Redis SETEX requires TTL > 0. Skip caching if TTL is zero/negative.
        if ttl <= 0:
            return

        key = self._generate_key(prefix, **kwargs)

        # Always write to L1 for eligible namespaces (even if Redis is down)
        if prefix in _L1_ELIGIBLE_PREFIXES:
            self._l1.set(key, val, ttl)

        if not self._enabled:
            return

        try:
            await self._redis.setex(key, ttl, json.dumps(val))
            logger.debug(f"Cache SET for {key} (TTL={ttl}s)")
        except Exception as e:
            logger.error(f"Cache set error: {e}")

    async def flush_prefix(self, prefix: str) -> int:
        """Delete all cache keys matching a prefix. Returns count deleted."""
        self._l1._store.clear()
        if not self._enabled:
            return 0
        count = 0
        try:
            keys = []
            async for key in self._redis.scan_iter(match=f"cache:{prefix}:*", count=200):
                keys.append(key)
                if len(keys) >= 200:
                    await self._redis.unlink(*keys)
                    count += len(keys)
                    keys = []
            if keys:
                await self._redis.unlink(*keys)
                count += len(keys)
            logger.info(f"Flushed {count} keys with prefix 'cache:{prefix}:*'")
        except Exception as e:
            logger.error(f"Cache flush error: {e}")
        return count

    async def close(self) -> None:
        """Release CacheService reference to Redis. Pool itself is closed by redis_pool.close_redis_pool()."""
        if self._enabled:
            logger.info("CacheService released Redis connection")
            self._enabled = False

_cache_service: Optional[CacheService] = None

def get_cache_service() -> CacheService:
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
