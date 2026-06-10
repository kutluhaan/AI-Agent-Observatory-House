"""
Token Store — Redis üzerinde token whitelist/blacklist ve rate limiting.

Redis key yapısı:
  auth:refresh:{jti}     → user_id   TTL: 7 gün   (whitelist)
  auth:blacklist:{jti}   → "1"       TTL: 15 dk   (blacklist)
  ratelimit:{ep}:{id}    → count     TTL: pencere  (rate limit)
"""
from datetime import timedelta

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()


# ─── Key Builders ─────────────────────────────────────────

def _refresh_key(jti: str) -> str:
    return f"auth:refresh:{jti}"

def _blacklist_key(jti: str) -> str:
    return f"auth:blacklist:{jti}"

def _email_verify_key(token_hash: str) -> str:
    return f"auth:email_verify:{token_hash}"

def _pwd_reset_key(token_hash: str) -> str:
    return f"auth:pwd_reset:{token_hash}"

def _rate_limit_key(endpoint: str, identifier: str) -> str:
    return f"ratelimit:{endpoint}:{identifier}"


# ─── Refresh Token Whitelist ──────────────────────────────

async def store_refresh_token(
    redis: aioredis.Redis,
    jti: str,
    user_id: str,
) -> None:
    """Login veya token rotation'da yeni refresh token'ı whitelist'e ekler."""
    ttl = int(timedelta(days=settings.jwt_refresh_token_expire_days).total_seconds())
    await redis.set(_refresh_key(jti), user_id, ex=ttl)


async def get_refresh_token_user(
    redis: aioredis.Redis,
    jti: str,
) -> str | None:
    """Refresh token whitelist'te var mı? Varsa user_id döner."""
    return await redis.get(_refresh_key(jti))


async def consume_refresh_token(redis: aioredis.Redis, jti: str) -> str | None:
    """
    Atomik GET+DELETE — rotation'da tek kullanımlık tüketim.
    None dönerse token zaten revoke edilmiş veya hiç yoktu.
    """
    return await redis.getdel(_refresh_key(jti))


async def revoke_refresh_token(redis: aioredis.Redis, jti: str) -> None:
    """Logout'ta refresh token'ı whitelist'ten siler."""
    await redis.delete(_refresh_key(jti))


# ─── Access Token Blacklist ───────────────────────────────

async def blacklist_access_token(redis: aioredis.Redis, jti: str) -> None:
    """
    Logout'ta access token'ı blacklist'e ekler.
    TTL = access token expire süresi — sonra zaten geçersiz olur.
    """
    ttl = int(timedelta(minutes=settings.jwt_access_token_expire_minutes).total_seconds())
    await redis.set(_blacklist_key(jti), "1", ex=ttl)


async def is_access_token_blacklisted(redis: aioredis.Redis, jti: str) -> bool:
    """Her korumalı request'te çağrılır — token logout'ta blacklist'e alındı mı?"""
    return bool(await redis.exists(_blacklist_key(jti)))


# ─── Email Verification ───────────────────────────────────

async def store_email_verify_token(
    redis: aioredis.Redis,
    token_hash: str,
    user_id: str,
) -> None:
    await redis.set(_email_verify_key(token_hash), user_id, ex=86400)  # 24 saat


async def revoke_email_verify_token(redis: aioredis.Redis, token_hash: str) -> None:
    await redis.delete(_email_verify_key(token_hash))


# ─── Password Reset ───────────────────────────────────────

async def store_pwd_reset_token(
    redis: aioredis.Redis,
    token_hash: str,
    user_id: str,
) -> None:
    await redis.set(_pwd_reset_key(token_hash), user_id, ex=1800)  # 30 dakika

async def get_email_verify_user(
    redis: aioredis.Redis,
    token_hash: str,
) -> str | None:
    """Verify-email Redis fast-path — password reset pattern ile simetrik."""
    return await redis.get(_email_verify_key(token_hash))


async def get_pwd_reset_user(
    redis: aioredis.Redis,
    token_hash: str,
) -> str | None:
    return await redis.get(_pwd_reset_key(token_hash))


async def revoke_pwd_reset_token(redis: aioredis.Redis, token_hash: str) -> None:
    await redis.delete(_pwd_reset_key(token_hash))


# ─── Rate Limiting (Counter + TTL) ───────────────────────

# endpoint → (max_requests, window_seconds)
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "login":            (10, 900),    # 10 / 15 dakika — email bazlı
    "register":         (5, 3600),    # 5 / 1 saat — IP bazlı
    "forgot_password":  (5, 1800),    # 5 / 30 dakika — email bazlı
    "reset_password":   (10, 3600),   # 10 / 1 saat — IP bazlı
    "resend_verify":    (3, 3600),    # 3 / 1 saat — email bazlı
    "refresh":          (30, 60),     # 30 / 1 dakika — user_id bazlı
    "switch_org":       (20, 60),     # 20 / 1 dakika — user_id bazlı
    "general":          (100, 60),    # 100 / 1 dakika — user_id bazlı
}


async def check_rate_limit(
    redis: aioredis.Redis,
    endpoint: str,
    identifier: str,
) -> tuple[bool, int]:
    """
    Rate limit kontrolü. Sliding window yaklaşımı (counter + TTL).

    Returns:
        (is_allowed, retry_after_seconds)
        is_allowed=False ise 429 döndür, retry_after header'a ekle.
    """
    max_requests, window_seconds = RATE_LIMITS.get(endpoint, (100, 60))
    key = _rate_limit_key(endpoint, identifier)

    current = await redis.incr(key)
    if current == 1:
        # İlk istek — TTL set et
        await redis.expire(key, window_seconds)

    if current > max_requests:
        ttl = await redis.ttl(key)
        return False, max(ttl, 1)

    return True, 0
