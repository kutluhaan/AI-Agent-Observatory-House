from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.redis import get_redis_pool
from app.services.auth_context import resolve_user_from_token

PUBLIC_PATHS = {
    "/health",
    "/auth/register",
    "/auth/login",
    "/auth/logout",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.current_user = None

        if request.url.path not in PUBLIC_PATHS:
            token = request.cookies.get("access_token")
            if token:
                redis = await get_redis_pool()
                request.state.current_user = await resolve_user_from_token(token, redis)

        return await call_next(request)