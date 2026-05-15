"""Redis-backed per-user rate limiter (token bucket, per minute)."""
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Max messages per user per 60-second window
DEFAULT_LIMIT = 20


async def check_rate_limit(user_id: str, limit: int = DEFAULT_LIMIT) -> bool:
    """Return True if request is within limit, False if rate-limited.

    Uses a Redis INCR + EXPIRE pattern. Key expires after 120s so the
    counter is always cleaned up even if the window logic drifts slightly.
    """
    try:
        from services.cache_service import get_cache_service
        cache = get_cache_service()
        if not cache._enabled:
            return True  # Redis down → don't block users

        window = int(time.time() // 60)
        key = f"ratelimit:{user_id}:{window}"

        count = await cache._redis.incr(key)
        if count == 1:
            # First request in this window — set expiry
            await cache._redis.expire(key, 120)
        return count <= limit
    except Exception as e:
        logger.warning(f"Rate limit check failed (allowing request): {e}")
        return True  # Fail open — never block on Redis error
