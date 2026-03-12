import json
import logging
import hashlib
from typing import Optional, Any
from config import settings

logger = logging.getLogger(__name__)

class CacheService:
    """Redis-based caching service for RAG and LLM responses."""
    
    def __init__(self):
        self._enabled = False
        try:
            import redis.asyncio as redis
            self._redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=1, # Use DB 1 for cache to separate from sessions
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
            self._enabled = True
            logger.info("CacheService initialized (Redis DB 1)")
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
        """Retrieve a value from cache."""
        if not self._enabled:
            return None
            
        key = self._generate_key(prefix, **kwargs)
        try:
            data = await self._redis.get(key)
            if data:
                logger.debug(f"Cache HIT for {key}")
                return json.loads(data)
            logger.debug(f"Cache MISS for {key}")
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None

    async def set(self, prefix: str, val: Any, ttl: int = 3600, **kwargs) -> None:
        """Store a value in cache."""
        if not self._enabled:
            return
            
        key = self._generate_key(prefix, **kwargs)
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
