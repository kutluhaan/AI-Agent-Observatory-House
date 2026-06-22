"""
Google OAuth 2.0 yardımcıları — G1

Authorization-code akışı: authorize URL üret → kodu token'a çevir → token yenile →
bağlı hesabın email'ini al. Gmail oku + gönder scope'ları (en az yetki).
"""
from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.core.config import get_settings

settings = get_settings()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Gmail: oku + gönder (restricted scope; testing modunda doğrulama gerekmez)
GMAIL_SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def is_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",      # refresh_token almak için
        "prompt": "consent",           # her seferinde refresh_token garantile
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    """Yetki kodunu token'a çevirir → {access_token, refresh_token, expires_in, scope}."""
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        })
        r.raise_for_status()
        return r.json()


async def refresh_access_token(refresh_token: str) -> dict:
    """Refresh token ile yeni access_token → {access_token, expires_in, scope}."""
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(GOOGLE_TOKEN_URL, data={
            "refresh_token": refresh_token,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "grant_type": "refresh_token",
        })
        r.raise_for_status()
        return r.json()


async def get_account_email(access_token: str) -> str | None:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        if r.status_code != 200:
            return None
        return r.json().get("email")
