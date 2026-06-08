"""
M3 Unit Testleri — jwt_service, password_service, token_store

DB bağlantısı gerekmez.
Redis için fakeredis kullanılır.
JWT için test key pair kullanılır.
"""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.responses import UnauthorizedError
from app.services import jwt_service
from app.services.password_service import (
    hash_password,
    validate_password_strength,
    verify_password,
)


# ─── Test JWT Key Pair ────────────────────────────────────
# Test için minimal RSA key pair (gerçek key değil)
TEST_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA2a2rwplBQLzHPZe5ekSKj/UEGehrSKuq/Mggn4PJNUZGLR91
PNPG6KCOAsepT/Gy9sDdqiMVIHK8LUmvCxnBXulnuvfxOIkXXnpBgmRPLHXBR/V
TzHHHrNqiPfbGxvNv1HkAE3KGn6BN/J1S7TYNKF/k9VrOhJ3TYKNS7UPiLqRK6e
E3mUlb2e4RUCUJCVj1OQknSdaHvLEBIZOTjHOTCUXJCTRJyDJh9tGrJTqAQvEh/
QkJGQ9R8AVMD0Y3Y5TbBbeMVvMnOiLiVs4xIAIY8X4QLDVMZ65NHaHZ9TnxWNF7
GpYS7OmDf4gZ7M9UQHkWP9h4bAoGfn2VRmz4RQIDAQABAoIBAHh+e5nZdRXYKJOK
5j8TzDp3EYGNNvMGnMR0w/a0jYJBgLNBW4HCJbLRE0vFc6MLcyPpLpCzUfCfC5vM
JQNS0MxVPZrz9EVfZm9d2K0/pDAtTk8eTZ8hmJNRMxRUmAvJR6UJpP8vBx0Q+jLy
5HHEXTe7DmBz3ANL6w1EVLfIkJ1IiSWMcqvQIJj0iFMC0jD0IIOH0dNRLa8Kfkw
RkHd9Y9JXlwNcb8cZjDFsKzqcJSH8Y3tDi4MVnTPWlHlLAyvbS4fNeq+DSlX1IiX
WFG7dWzH8Yh1Js+cUTsS1EvLfmFcDMRMsVNXBJZGBQ1bJuqd1O0qrxl6JBm1Bkh
A56Cz4ECgYEA7R3WmXN8G5pXVOWjS1BW8Hs+K6mBOJCJqXLaBqbxIlJSGIcnY+tT
8nzO1UVrJr5YdGaOI9vxA/3WL9SGKVO0C+R3MoKIk6aH/soxuMFk1Kb9Mu4WoUy7
K1sXE+MgaVXRmqJIoFoQQxQ7FjcCRvjqIoKsVK1LQZF9r0lEp7kCgYEA61YVSQZ5
vK4jOvjCzYjL7NLajXaDEO+0A5Bw2Y6gp3NPm5L+LHT5wlAHEA7pWs6xT89H0aqC
cPpZ8C+G0N9Q3yKI5OTNvROaA+Z5TfXjSEDCQKWn9T3HTbAXW5Vl3YUxT1D5I6/
x5xNrH0LfIMR29Q4CrLOKJ7XNdZrO2/rqjECgYEA2RuW0k9ZijEoHVvQ8p3/Lj0S
bN/2K1BKXJ5g3M6fKbUJuFqz7QFYX7aS6TN3VEGiAp6OY8EQh4xOiJUbW5PKPFQ
JxC6nFr4J6Y/E7Af3c0VJhkxzaF0MJgd5MFIP/IDzQFyA0XZ/oTUKL3CYJ7NHPG5
xrNIQfV4KZF6qGkCgYBGSBGX1E0H2Cs1TJnZKNB0q+Pz8VyFUxd5IB5PZpEFQ1G8
GRZY4IezR5h3L8KhVQRhJHbVhqPTcWdQvYHERFpZMmqEhGWlZUvA5Oc4ZzVQwCdC
LrG5UmvH3w43B9NRF6N5bnkKJqKJ1OeD1VDw+YK5MbRD6JWg5DZsJf/LgQKBgDzY
rJqF+hq6U3pJ/tA7bHIJFN/NeX7CX7J9QqPGx4V9xyR8cGBT0VHrxK+UgMLrNd/V
Dpc5Sv2IsTpVkp7EBhF5DqBT5rVc6j2e4Gqh8cQ5RzPq7BkJz6x3P3X0hRd1MqMm
I9HZaSl7ZEW9h/e+yBYD3TLRT/rNLNFW9yUf
-----END RSA PRIVATE KEY-----"""

TEST_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgQhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2a2rwplBQLzHPZe5ekSKj/
UEGehrSKuq/Mggn4PJNUZGLEf91PNPG6KCOAsepT/Gy9sDdqiMVIHK8LUmvCxnB
XulnuvfxOIkXXnpBgmRPLHXBR/VTzHHHrNqiPfbGxvNv1HkAE3KGn6BN/J1S7TY
NKF/k9VrOhJ3TYKNS7UPiLqRK6eE3mUlb2e4RUCUJCVj1OQknSdaHvLEBIZOTjH
OTCUXJCTRJyDJh9tGrJTqAQvEh/QkJGQ9R8AVMD0Y3Y5TbBbeMVvMnOiLiVs4xI
AIY8X4QLDVMZ65NHaHZ9TnxWNF7GpYS7OmDf4gZ7M9UQHkWP9h4bAoGfn2VRmz4
RQIDAQAB
-----END PUBLIC KEY-----"""


# ─── Fixtures ─────────────────────────────────────────────

@pytest.fixture
def mock_settings(monkeypatch):
    """JWT servisinin gerçek key yerine test key kullanması için."""
    monkeypatch.setattr("app.services.jwt_service.settings.jwt_private_key", TEST_PRIVATE_KEY)
    monkeypatch.setattr("app.services.jwt_service.settings.jwt_public_key", TEST_PUBLIC_KEY)
    monkeypatch.setattr("app.services.jwt_service.settings.jwt_access_token_expire_minutes", 15)
    monkeypatch.setattr("app.services.jwt_service.settings.jwt_refresh_token_expire_days", 7)


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


# ─── Token Store Tests ────────────────────────────────────

class TestTokenStore:
    """fakeredis ile test — gerçek Redis bağlantısı gerekmez."""

    @pytest.fixture
    def fake_redis(self):
        try:
            import fakeredis.aioredis
            return fakeredis.aioredis.FakeRedis(decode_responses=True)
        except ImportError:
            pytest.skip("fakeredis not installed")

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
