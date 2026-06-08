"""
JWT Service — RS256 token üretimi ve doğrulaması.

RS256 seçildi çünkü:
- Asymmetric key pair: private key ile imzala, public key ile doğrula
- DB sızıntısında public key ele geçse bile token üretilemez
- HS256'da tek key her şeyi yapıyor — tehlikeli

Token tipleri:
- access: kısa ömürlü (15dk), her request'te doğrulanır
- refresh: uzun ömürlü (7gün), sadece /auth/refresh'te kullanılır
"""
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.responses import UnauthorizedError

settings = get_settings()

ALGORITHM = "RS256"


def create_access_token(
    user_id: uuid.UUID,
    email: str,
    org_id: uuid.UUID | None = None,
    org_slug: str | None = None,
    role: str | None = None,
) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "org_id": str(org_id) if org_id else None,
        "org_slug": org_slug,
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    return jwt.encode(payload, settings.jwt_private_key, algorithm=ALGORITHM)


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str]:
    """Returns: (raw_token, jti)"""
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    jti = str(uuid.uuid4())

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    token = jwt.encode(payload, settings.jwt_private_key, algorithm=ALGORITHM)
    return token, jti


def decode_token(token: str, *, token_type: str | None = None) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_public_key, algorithms=[ALGORITHM])
    except JWTError as e:
        if "expired" in str(e).lower():
            if token_type == "refresh":
                raise UnauthorizedError("REFRESH_TOKEN_EXPIRED", "Token has expired.")
            raise UnauthorizedError("INVALID_TOKEN", "Invalid token.")
        raise UnauthorizedError("INVALID_TOKEN", "Invalid token.")


def decode_access_token(token: str) -> dict[str, Any]:
    payload = decode_token(token, token_type="access")
    if payload.get("type") != "access":
        raise UnauthorizedError("INVALID_TOKEN", "Invalid token type.")
    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    payload = decode_token(token, token_type="refresh")
    if payload.get("type") != "refresh":
        raise UnauthorizedError("INVALID_TOKEN", "Invalid token type.")
    return payload


def hash_token(token: str) -> str:
    """SHA-256 hash — DB'de raw token saklanmaz."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_secure_token() -> str:
    """32 byte cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(32)
