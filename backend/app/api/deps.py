"""
FastAPI Dependencies — Endpoint'lerde Depends() ile kullanılır.
"""
import redis.asyncio as aioredis
from fastapi import Cookie, Depends, Request

from app.core.redis import get_redis
from app.core.responses import UnauthorizedError
from app.services.auth_context import CurrentUser, resolve_user_from_token

# Route'lar buradan import edebilir
__all__ = ["CurrentUser", "get_current_user"]


async def get_current_user(
    request: Request,
    access_token: str | None = Cookie(default=None),
    redis: aioredis.Redis = Depends(get_redis),
) -> CurrentUser:
    # Middleware doldurduysa direkt kullan
    user = getattr(request.state, "current_user", None)
    if user is not None:
        return user

    # Cookie'den dene
    if not access_token:
        raise UnauthorizedError("INVALID_TOKEN", "Authentication required.")

    user = await resolve_user_from_token(access_token, redis)
    if user is None:
        raise UnauthorizedError("INVALID_TOKEN", "Authentication required.")

    return user