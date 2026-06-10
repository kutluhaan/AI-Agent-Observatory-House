"""
M3 Unit Testleri — jwt_service, password_service, token_store

DB bağlantısı gerekmez.
Redis için fakeredis kullanılır.
JWT için test key pair kullanılır.
"""
import uuid
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.requests import Request

from app.core.responses import UnauthorizedError
from app.api.deps import get_current_user
from app.services.auth_context import CurrentUser, resolve_user_from_token
from app.services import jwt_service
from app.services.password_service import (
    hash_password,
    validate_password_strength,
    verify_password,
)


# ─── Test JWT Key Pair ────────────────────────────────────
# Test için minimal RSA key pair (gerçek key değil)
TEST_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCIbDYA9l1VHiqn
BIZfAyd+xgZvi2QVOVX/x+18fi2i0XRQQbtfPFqnc8kq3vaYlBtNOBcEvTn4Xz9k
NMnfglC+K3HHdWQQVRYAGnFLnRHyOZzXUzCfYsS0qcbeliJajlrgATtErXXZU5G/
5LqeIdmLoYI9J4i0xZHPRKbk7rIUniDySrKKUG2e3ztBzF8REmpU8Xvs5nhrks3E
krgC3tRPEQb6p3UNqEJLzYrD0tJmMiAvKxs74/+BghF++8B6KmWiWYxahUQYZi0U
mFGjLpJipWTci6ziVRjr/7aeQrrqK228lkaV+/fFaKmGhudp7ybAg9kh2vphimcS
4heF5eN/AgMBAAECggEAC4ffRf7iLfrvbqUqmQadOfvm41q2yjcfFmWBpI94Wqtg
LMBsOUUoAcCpn4laR9SM54lMI3G9tUk9BG0/JY3QNqKuv/B41WCRDCUwBPdxDYuN
FC4gjU2TLr9YOHbGzzylCwtPmnhxiOhQCMDT0ost5hLFUqyaw3Ic5utN5/USRue5
wkmwQrQGGTAqeGxgQysAu0xkUwx5TLkAdpd+PNjlz9uA6QNKxY1ChG28iBdpI0Fe
hgmRCaPqT3YpmLanFnQ5uhWI5Li7bjo7LOp9Z7Ak760ucUNEaxdnhVxIGUoPQVsn
FieAgjddVa9dhbImPfsTcrAfj1+2Lt0XgtVuXM73wQKBgQC9fpBKBRKtFb8c4TbV
FDgJ1/S/ZlbypgAEDNHcMWc5IUEqpwdYEDuUBXKLhr2NRdCsPEsCjKXgej3yPLpV
8CY2ZHp+IOcndNBVejG9I/xkCjatkL7CUrwRPHVFjui8Qu/16VnES/wZwJsPNbOo
8lC22Gz9BaU5Gdet43+zVuOT8QKBgQC4TVVrLs5eKj/WgE9iQ5CnPqsbgf6jUyl8
fvj8pVtC54Ei8zYy03W8VqxKfAfPliTMXrTCPNT/+E0pgkRiE60bcodjCHZURKzq
Z+NIsjUUQfdx9AFmfirjDFGXaErnS6VvE4pVyBxLeAfmrOaIrrUzh6yF7VnSuQUX
h1WE5IqebwKBgGqhI3RjcmTvTcFkgcRZQkdXvCNP5TFZc7zTseuj6R/etJrZrmpB
iCT9A727rkImvQuOSe8/UcAFSYJb5caiAf6tf7glr60mMG1I+2AhNc7daHM2dgFH
KQjR6nOfvRri18Ca9KZe05dyKE7gux4gbIbXNk0StixxfEofMCasiBchAoGBAIv/
AmGWfl/9C9zuPl7QH/NKoUMV7c02gI73DD8thDNAE1HvGT5mbkqQM/OoX26KCI3N
atUYzFtby5E6SKOPerEcwEazyN6eBBNSss0nwTYQHdxLkzy9neo2E0xFhpBHX/UO
DMi4ZvXUyXup3rv4qd/osV5SOybcMEf9HzMBP2K1AoGANXMneQ87cj5kcxnS43N9
8Qm7Mp0RTZauSSgswiUHOSoyyH4YKxovI8+Nrnvdkv5yZ/M289HtolGwJal5NxRQ
0z2XGVmObm6YQzJDcfKMK2ZSZeI5StEx3DXnKPG5RbTcusfj/iMvYwtLtH3Bx2Sa
FFUEX8Abs4Bl6ZWPZI0+mbM=
-----END PRIVATE KEY-----"""

TEST_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAiGw2APZdVR4qpwSGXwMn
fsYGb4tkFTlV/8ftfH4totF0UEG7Xzxap3PJKt72mJQbTTgXBL05+F8/ZDTJ34JQ
vitxx3VkEFUWABpxS50R8jmc11Mwn2LEtKnG3pYiWo5a4AE7RK112VORv+S6niHZ
i6GCPSeItMWRz0Sm5O6yFJ4g8kqyilBtnt87QcxfERJqVPF77OZ4a5LNxJK4At7U
TxEG+qd1DahCS82Kw9LSZjIgLysbO+P/gYIRfvvAeiplolmMWoVEGGYtFJhRoy6S
YqVk3Ius4lUY6/+2nkK66ittvJZGlfv3xWiphobnae8mwIPZIdr6YYpnEuIXheXj
fwIDAQAB
-----END PUBLIC KEY-----"""


# ─── Fixtures ─────────────────────────────────────────────

@pytest.fixture
def mock_settings(monkeypatch):
    """JWT servisinin gerçek key yerine test key kullanması için."""
    monkeypatch.setattr("app.services.jwt_service.settings.jwt_private_key", TEST_PRIVATE_KEY)
    monkeypatch.setattr("app.services.jwt_service.settings.jwt_public_key", TEST_PUBLIC_KEY)
    monkeypatch.setattr("app.services.jwt_service.settings.jwt_access_token_expire_minutes", 15)
    monkeypatch.setattr("app.services.jwt_service.settings.jwt_refresh_token_expire_days", 7)

@pytest.fixture
def fake_redis():
    try:
        import fakeredis.aioredis
        return fakeredis.aioredis.FakeRedis(decode_responses=True)
    except ImportError:
        pytest.skip("fakeredis not installed")

# ─── Helper Functions ─────────────────────────────────────

def _make_request(*, current_user: CurrentUser | None = None) -> Request:
    """get_current_user unit testleri için minimal Starlette Request."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/auth/me",
        "headers": [],
        "query_string": b"",
    }
    request = Request(scope)
    request.state.current_user = current_user
    return request

# ─── Password Service Tests ───────────────────────────────

class TestPasswordService:

    def test_hash_returns_string(self):
        result = hash_password("Test1234!")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_not_plain_text(self):
        plain = "Test1234!"
        hashed = hash_password(plain)
        assert plain not in hashed

    def test_verify_correct_password(self):
        plain = "Test1234!"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("Test1234!")
        assert verify_password("WrongPass1!", hashed) is False

    def test_verify_empty_password(self):
        hashed = hash_password("Test1234!")
        assert verify_password("", hashed) is False

    def test_two_hashes_different(self):
        """Argon2id salt kullanır — aynı şifre iki farklı hash üretir."""
        plain = "Test1234!"
        h1 = hash_password(plain)
        h2 = hash_password(plain)
        assert h1 != h2

    def test_validate_strength_too_short(self):
        with pytest.raises(Exception) as exc:
            validate_password_strength("Ab1!")
        assert "PASSWORD_TOO_WEAK" in str(exc.value.code) or "8" in str(exc.value.message)

    def test_validate_strength_no_uppercase(self):
        with pytest.raises(Exception):
            validate_password_strength("test1234!")

    def test_validate_strength_no_number(self):
        with pytest.raises(Exception):
            validate_password_strength("TestPass!")

    def test_validate_strength_valid(self):
        # Exception fırlatmamalı
        validate_password_strength("Test1234!")
        validate_password_strength("SecurePass99")


# ─── JWT Service Tests ────────────────────────────────────

class TestJWTService:

    def test_hash_token_deterministic(self):
        """Aynı token her zaman aynı hash'i üretmeli."""
        token = "my-test-token"
        assert jwt_service.hash_token(token) == jwt_service.hash_token(token)

    def test_hash_token_different_inputs(self):
        assert jwt_service.hash_token("token1") != jwt_service.hash_token("token2")

    def test_hash_token_returns_hex(self):
        result = jwt_service.hash_token("test")
        assert len(result) == 64  # SHA-256 = 32 bytes = 64 hex chars
        int(result, 16)  # Geçerli hex string

    def test_generate_secure_token_unique(self):
        t1 = jwt_service.generate_secure_token()
        t2 = jwt_service.generate_secure_token()
        assert t1 != t2

    def test_generate_secure_token_url_safe(self):
        token = jwt_service.generate_secure_token()
        # URL-safe karakterler: letters, digits, -, _
        import re
        assert re.match(r'^[A-Za-z0-9_-]+$', token)

    def test_access_token_roundtrip(self, mock_settings):
        user_id = uuid.uuid4()
        token = jwt_service.create_access_token(user_id, "user@example.com")
        payload = jwt_service.decode_access_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["email"] == "user@example.com"
        assert payload["type"] == "access"
        assert payload["org_id"] is None
        assert payload["jti"]
        assert payload["exp"] > payload["iat"]
        
    def test_access_token_with_org_claims(self, mock_settings):
        user_id = uuid.uuid4()
        org_id = uuid.uuid4()
        token = jwt_service.create_access_token(
            user_id, "user@example.com",
            org_id=org_id, org_slug="acme", role="admin",
        )
        payload = jwt_service.decode_access_token(token)
        assert payload["org_id"] == str(org_id)
        assert payload["org_slug"] == "acme"
        assert payload["role"] == "admin"

    def test_refresh_token_roundtrip(self, mock_settings):
        user_id = uuid.uuid4()
        token, jti = jwt_service.create_refresh_token(user_id)
        payload = jwt_service.decode_refresh_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"
        assert payload["jti"] == jti

    def test_decode_access_as_refresh_raises(self, mock_settings):
        token = jwt_service.create_access_token(uuid.uuid4(), "a@b.com")
        with pytest.raises(UnauthorizedError) as exc:
            jwt_service.decode_refresh_token(token)
        assert exc.value.code == "INVALID_TOKEN"

    def test_decode_garbage_token_raises(self, mock_settings):
        with pytest.raises(UnauthorizedError):
            jwt_service.decode_access_token("not.a.jwt")

    def test_expired_access_token_raises(self, mock_settings):
        from jose import jwt as jose_jwt

        from app.services.jwt_service import ALGORITHM

        past = int((datetime.now(UTC) - timedelta(minutes=5)).timestamp())
        payload = {
            "sub": str(uuid.uuid4()),
            "email": "a@b.com",
            "type": "access",
            "jti": str(uuid.uuid4()),
            "iat": past - 3600,
            "exp": past,
        }
        token = jose_jwt.encode(
            payload, jwt_service.settings.jwt_private_key, algorithm=ALGORITHM
        )
        with pytest.raises(UnauthorizedError) as exc:
            jwt_service.decode_access_token(token)
        assert exc.value.code == "INVALID_TOKEN"



# ─── Token Store Tests ────────────────────────────────────

class TestTokenStore:
    """fakeredis ile test — gerçek Redis bağlantısı gerekmez."""

    @pytest.mark.asyncio
    async def test_store_and_get_refresh_token(self, fake_redis, monkeypatch):
        monkeypatch.setattr(
            "app.services.token_store.settings.jwt_refresh_token_expire_days", 7
        )
        from app.services.token_store import store_refresh_token, get_refresh_token_user

        jti = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        await store_refresh_token(fake_redis, jti, user_id)
        result = await get_refresh_token_user(fake_redis, jti)
        assert result == user_id

    @pytest.mark.asyncio
    async def test_revoke_refresh_token(self, fake_redis, monkeypatch):
        monkeypatch.setattr(
            "app.services.token_store.settings.jwt_refresh_token_expire_days", 7
        )
        from app.services.token_store import (
            store_refresh_token, get_refresh_token_user, revoke_refresh_token
        )

        jti = str(uuid.uuid4())
        await store_refresh_token(fake_redis, jti, "user-123")
        await revoke_refresh_token(fake_redis, jti)
        result = await get_refresh_token_user(fake_redis, jti)
        assert result is None

    @pytest.mark.asyncio
    async def test_consume_refresh_token_atomic(self, fake_redis, monkeypatch):
        monkeypatch.setattr(
            "app.services.token_store.settings.jwt_refresh_token_expire_days", 7
        )
        from app.services.token_store import (
            consume_refresh_token,
            get_refresh_token_user,
            store_refresh_token,
        )

        jti = str(uuid.uuid4())
        user_id = "user-456"
        await store_refresh_token(fake_redis, jti, user_id)

        assert await consume_refresh_token(fake_redis, jti) == user_id
        assert await get_refresh_token_user(fake_redis, jti) is None
        assert await consume_refresh_token(fake_redis, jti) is None

    @pytest.mark.asyncio
    async def test_store_and_get_email_verify_token(self, fake_redis):
        from app.services.token_store import (
            get_email_verify_user,
            revoke_email_verify_token,
            store_email_verify_token,
        )

        token_hash = "a" * 64
        user_id = str(uuid.uuid4())

        await store_email_verify_token(fake_redis, token_hash, user_id)
        assert await get_email_verify_user(fake_redis, token_hash) == user_id

        await revoke_email_verify_token(fake_redis, token_hash)
        assert await get_email_verify_user(fake_redis, token_hash) is None

    @pytest.mark.asyncio
    async def test_blacklist_access_token(self, fake_redis, monkeypatch):
        monkeypatch.setattr(
            "app.services.token_store.settings.jwt_access_token_expire_minutes", 15
        )
        from app.services.token_store import blacklist_access_token, is_access_token_blacklisted

        jti = str(uuid.uuid4())
        assert not await is_access_token_blacklisted(fake_redis, jti)

        await blacklist_access_token(fake_redis, jti)
        assert await is_access_token_blacklisted(fake_redis, jti)

    @pytest.mark.asyncio
    async def test_rate_limit_allows_under_limit(self, fake_redis):
        from app.services.token_store import check_rate_limit

        # "login" limiti: 10/15dk
        for _ in range(5):
            allowed, _ = await check_rate_limit(fake_redis, "login", "test@test.com")
            assert allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_over_limit(self, fake_redis):
        from app.services.token_store import check_rate_limit

        # "login" limiti: 10/15dk — 11. istek bloklanmalı
        for _ in range(10):
            await check_rate_limit(fake_redis, "login", "blocked@test.com")

        allowed, retry_after = await check_rate_limit(fake_redis, "login", "blocked@test.com")
        assert allowed is False
        assert retry_after > 0

    @pytest.mark.asyncio
    async def test_rate_limit_different_identifiers_independent(self, fake_redis):
        from app.services.token_store import check_rate_limit

        # İki farklı email bağımsız sayaçlar kullanır
        for _ in range(10):
            await check_rate_limit(fake_redis, "login", "user1@test.com")

        # user1 bloklu
        allowed1, _ = await check_rate_limit(fake_redis, "login", "user1@test.com")
        assert allowed1 is False

        # user2 etkilenmez
        allowed2, _ = await check_rate_limit(fake_redis, "login", "user2@test.com")
        assert allowed2 is True


# ─── Auth Context Tests ───────────────────────────────────

class TestAuthContext:
    @pytest.mark.asyncio
    async def test_resolve_valid_token_returns_current_user(
        self, mock_settings, fake_redis
    ):
        user_id = uuid.uuid4()
        token = jwt_service.create_access_token(user_id, "user@example.com")

        user = await resolve_user_from_token(token, fake_redis)

        assert user is not None
        assert user.user_id == user_id
        assert user.email == "user@example.com"
        assert user.org_id is None
        assert user.jti

    @pytest.mark.asyncio
    async def test_resolve_invalid_token_returns_none(self, mock_settings, fake_redis):
        user = await resolve_user_from_token("not.a.jwt", fake_redis)
        assert user is None

    @pytest.mark.asyncio
    async def test_resolve_blacklisted_token_returns_none(
        self, mock_settings, fake_redis, monkeypatch
    ):
        from app.services.token_store import blacklist_access_token

        monkeypatch.setattr(
            "app.services.token_store.settings.jwt_access_token_expire_minutes", 15
        )
        user_id = uuid.uuid4()
        token = jwt_service.create_access_token(user_id, "user@example.com")
        payload = jwt_service.decode_access_token(token)

        await blacklist_access_token(fake_redis, payload["jti"])

        user = await resolve_user_from_token(token, fake_redis)
        assert user is None

    @pytest.mark.asyncio
    async def test_resolve_refresh_token_returns_none(self, mock_settings, fake_redis):
        user_id = uuid.uuid4()
        token, _ = jwt_service.create_refresh_token(user_id)

        # refresh token access decode ile parse edilemez → None
        user = await resolve_user_from_token(token, fake_redis)
        assert user is None

# ─── Get Current User (deps) Tests ────────────────────────

class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_returns_state_user_when_middleware_set(self, fake_redis):
        expected = CurrentUser(
            user_id=uuid.uuid4(),
            email="mw@example.com",
            jti=str(uuid.uuid4()),
        )
        request = _make_request(current_user=expected)

        user = await get_current_user(
            request, access_token=None, redis=fake_redis
        )

        assert user is expected

    @pytest.mark.asyncio
    async def test_resolves_from_cookie_when_state_empty(
        self, mock_settings, fake_redis
    ):
        user_id = uuid.uuid4()
        token = jwt_service.create_access_token(user_id, "cookie@example.com")
        request = _make_request()  # state boş

        user = await get_current_user(
            request, access_token=token, redis=fake_redis
        )

        assert user.user_id == user_id
        assert user.email == "cookie@example.com"

    @pytest.mark.asyncio
    async def test_raises_when_no_cookie_and_no_state(self, fake_redis):
        request = _make_request()

        with pytest.raises(UnauthorizedError) as exc:
            await get_current_user(
                request, access_token=None, redis=fake_redis
            )

        assert exc.value.code == "INVALID_TOKEN"

    @pytest.mark.asyncio
    async def test_raises_when_cookie_invalid(self, mock_settings, fake_redis):
        request = _make_request()

        with pytest.raises(UnauthorizedError) as exc:
            await get_current_user(
                request, access_token="bad.token.here", redis=fake_redis
            )

        assert exc.value.code == "INVALID_TOKEN"