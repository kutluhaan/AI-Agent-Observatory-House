"""
Redis bağlantısı.

M3'te ilk kez aktif olarak kullanılıyor:
- Token whitelist/blacklist
- Rate limiting

Singleton pattern — uygulama boyunca tek bir connection pool.
"""
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

_redis_pool: aioredis.Redis | None = None


async def get_redis_pool() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """FastAPI dependency — endpoint'lerde Depends(get_redis) ile kullanılır."""
    pool = await get_redis_pool()
    yield pool


async def close_redis() -> None:
    """Uygulama kapanırken çağrılır — lifespan shutdown'da."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None
