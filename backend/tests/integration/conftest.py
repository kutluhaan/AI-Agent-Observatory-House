"""Integration test fixtures — paylaşılan client + session teardown."""

import pytest
import uuid
from httpx import ASGITransport, AsyncClient

from app.core.database import engine
from app.core.redis import close_redis, get_redis_pool
from app.main import app


@pytest.fixture
async def client():
    """Her test: yeni httpx client (cookie izolasyonu). Redis test sonunda kapatılmaz."""
    await get_redis_pool()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="session", autouse=True)
async def _app_startup_state():
    """
    ASGITransport lifespan'i tetiklemediğinden, app startup'ında yapılan idempotent
    kayıtları test süreci için elle yap: tool registry (M9/M12) + HITL engine (M10).
    Trace consumer kasıtlı başlatılmaz — testler kendi drain/poll mantığını kullanır.
    """
    from app.core import clickhouse
    from app.services.agent.tools.builtin import register_builtin_tools
    from app.services.agent.tools.research import register_research_tools
    from app.services.hitl import init_hitl_engine

    register_builtin_tools()
    register_research_tools()
    redis = await get_redis_pool()
    init_hitl_engine(redis)
    try:
        await clickhouse.init_schema()
    except Exception:
        pass
    yield


@pytest.fixture(scope="session", autouse=True)
async def integration_session_cleanup():
    """Tüm integration testleri bitince pool'ları kapat."""
    yield
    await close_redis()
    await engine.dispose()

@pytest.fixture
def auth_user():
    return {
        "email": f"m3-test-{uuid.uuid4().hex[:12]}@example.com",
        "password": "Test1234!",
        "full_name": "M3 Integration User",
    }


@pytest.fixture(autouse=True)
async def clear_rate_limits():
    """Integration testlerinde register/login limit sayaçlarını sıfırla."""
    redis = await get_redis_pool()
    keys = await redis.keys("ratelimit:*")
    if keys:
        await redis.delete(*keys)
    yield