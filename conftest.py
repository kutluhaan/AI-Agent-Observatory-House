"""
Global test fixtures — spec'te tanımlanan test ortamı konfigürasyonu.

SQLite in-memory: integration testler için hızlı, gerçek PostgreSQL gerekmez.
PostgreSQL INET tipi SQLite'ta String olarak map'lenir.
"""
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import String, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.types import TypeDecorator

from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.main import app
from app.models.auth import EmailVerification, RefreshToken
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.services import jwt_service
from app.services.password_service import hash_password
from app.services.token_store import store_refresh_token

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ─── SQLite INET workaround ───────────────────────────────

class INETCompat(TypeDecorator):
    """PostgreSQL INET tipini SQLite için String'e dönüştürür."""
    impl = String
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        return str(value) if value is not None else None

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        return value


def _patch_inet_for_sqlite() -> None:
    """RefreshToken.ip_address kolonunu SQLite için patch'le."""
    from sqlalchemy.dialects.postgresql import INET
    from sqlalchemy import event as sa_event

    col = RefreshToken.__table__.c.get("ip_address")
    if col is not None and hasattr(col.type, "__class__") and col.type.__class__.__name__ == "INET":
        col.type = INETCompat()


_patch_inet_for_sqlite()


# ─── DB Fixtures ──────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def engine():
    _engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncGenerator[AsyncSession, None]:
    """Her test için izole session — rollback ile temizlenir."""
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


# ─── Redis Fixture ────────────────────────────────────────

@pytest_asyncio.fixture
async def redis():
    try:
        import fakeredis.aioredis
        fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
        yield fake
        await fake.flushall()
    except ImportError:
        pytest.skip("fakeredis not installed")


# ─── HTTP Client Fixture ──────────────────────────────────

@pytest_asyncio.fixture
async def client(db, redis) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI test client — DB ve Redis override edilmiş."""

    async def _get_db():
        yield db

    async def _get_redis():
        yield redis

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_redis] = _get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ─── Factory Fixtures ─────────────────────────────────────

@pytest_asyncio.fixture
async def test_user(db: AsyncSession) -> User:
    """Doğrulanmış, aktif test kullanıcısı — her test için benzersiz email."""
    user = User(
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("Test1234!"),
        full_name="Test User",
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def unverified_user(db: AsyncSession) -> User:
    """Doğrulanmamış kullanıcı — her test için benzersiz email."""
    user = User(
        email=f"unverified-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("Test1234!"),
        full_name="Unverified User",
        is_verified=False,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def test_org(db: AsyncSession, test_user: User) -> Organization:
    """Test organizasyonu — test_user owner. Her test için benzersiz slug."""
    org = Organization(
        name="Test Org",
        slug=f"test-org-{uuid.uuid4().hex[:8]}",
        plan="free",
        is_active=True,
        created_by=test_user.id,
    )
    db.add(org)
    await db.flush()

    membership = OrganizationMember(
        organization_id=org.id,
        user_id=test_user.id,
        role="owner",
    )
    db.add(membership)
    await db.flush()
    return org


# ─── RSA Key Fixture (integration testler için) ───────────

import os as _os
_TEST_DIR = _os.path.dirname(_os.path.abspath(__file__))

with open(_os.path.join(_TEST_DIR, "test_private.pem")) as _f:
    _TEST_PRIVATE_KEY = _f.read()
with open(_os.path.join(_TEST_DIR, "test_public.pem")) as _f:
    _TEST_PUBLIC_KEY = _f.read()


@pytest.fixture(autouse=True)
def patch_jwt_keys(monkeypatch):
    """Her test için geçerli RSA key'leri inject et."""
    monkeypatch.setattr("app.services.jwt_service.settings.jwt_private_key", _TEST_PRIVATE_KEY)
    monkeypatch.setattr("app.services.jwt_service.settings.jwt_public_key", _TEST_PUBLIC_KEY)
    monkeypatch.setattr("app.services.jwt_service.settings.jwt_access_token_expire_minutes", 15)
    monkeypatch.setattr("app.services.jwt_service.settings.jwt_refresh_token_expire_days", 7)
    monkeypatch.setattr("app.core.email.settings.resend_api_key", "test-key")
    monkeypatch.setattr("app.core.email.settings.frontend_url", "http://localhost:3000")
    monkeypatch.setattr("app.core.email.settings.email_from", "test@test.com")
