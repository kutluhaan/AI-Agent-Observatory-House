import uuid
from dataclasses import dataclass

import redis.asyncio as aioredis

from app.core.responses import UnauthorizedError
from app.services import jwt_service
from app.services.token_store import is_access_token_blacklisted


@dataclass
class CurrentUser:
    user_id: uuid.UUID
    email: str
    jti: str
    org_id: uuid.UUID | None = None
    org_slug: str | None = None
    role: str | None = None


async def resolve_user_from_token(
    token: str,
    redis: aioredis.Redis,
) -> CurrentUser | None:
    """Token geçerliyse CurrentUser döner, değilse None."""
    try:
        payload = jwt_service.decode_access_token(token)
    except UnauthorizedError:
        return None

    jti = payload.get("jti", "")
    if await is_access_token_blacklisted(redis, jti):
        return None

    raw_org = payload.get("org_id")
    org_id = uuid.UUID(raw_org) if raw_org else None

    return CurrentUser(
        user_id=uuid.UUID(payload["sub"]),
        email=payload["email"],
        jti=jti,
        org_id=org_id,
        org_slug=payload.get("org_slug"),
        role=payload.get("role"),
    )