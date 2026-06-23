"""
AI Agent Observatory — FastAPI Application

M1: Temel iskelet, health check
M2: DB modelleri yüklendi (Base.metadata)
M3: Redis bağlantısı, auth router (register, login, logout, /me)
M4: refresh, switch-org, verify-email, resend-verification, Resend email
"""

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.core.config import get_settings
from app.core.database import Base
from app.core import clickhouse
from app.core.redis import close_redis, get_redis_pool
from app.core.responses import (
    AppError,
    app_error_handler,
    generic_error_handler,
    request_validation_error_handler,
    )
from app.middleware import AuthMiddleware
from app.services.hitl import init_hitl_engine
from app.services.trace_consumer import TraceConsumer, ensure_group
from app.ws.traces import manager as ws_manager

# M2: Tüm modelleri Base.metadata'ya kaydet
import app.models  # noqa: F401

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Observatory API", env=settings.app_env)

    # M2: DB model kontrolü
    table_count = len(Base.metadata.tables)
    logger.info("Database models loaded", table_count=table_count)

    # M3: Redis bağlantısı
    redis = await get_redis_pool()
    logger.info("Redis connected")

    # M8: ClickHouse şeması + trace consumer (CH erişilemezse app yine de açılır)
    consumer_task = None
    try:
        await clickhouse.init_schema()
        await ensure_group(redis)
        consumer = TraceConsumer(redis, ws_manager=ws_manager)
        consumer_task = asyncio.create_task(consumer.run())
        app.state.trace_consumer = consumer
        logger.info("Trace consumer started")
    except Exception as exc:
        logger.error("trace_pipeline.init_failed", error=str(exc))

    # M9: Built-in tool'ları kaydet
    from app.services.agent.tools.builtin import register_builtin_tools
    register_builtin_tools()
    # F8: ekip tool'ları (delegate / team_share / team_board)
    from app.services.agent.tools.team import register_team_tools
    register_team_tools()
    # G1: Gmail tool'ları (search / read / send)
    from app.services.agent.tools.gmail import register_gmail_tools
    register_gmail_tools()
    logger.info("Agent built-in tools registered")

    # Faz 3: Dosya sistemi tool'larını kaydet
    from app.services.agent.tools.files import register_file_tools
    register_file_tools()
    logger.info("Agent file-system tools registered")

    # Faz 4: Skill tool'larını kaydet
    from app.services.agent.tools.skills import register_skill_tools
    register_skill_tools()
    logger.info("Agent skill tools registered")

    # M10: HITL Engine başlat
    init_hitl_engine(redis)
    logger.info("HITL engine initialized")

    # M12: Research tool'ları kaydet
    from app.services.agent.tools.research import register_research_tools
    register_research_tools()
    logger.info("Research tools registered")

    yield

    # Shutdown
    if consumer_task is not None:
        app.state.trace_consumer.stop()
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
    clickhouse.close_clickhouse()
    await close_redis()
    logger.info("Observatory API shutdown complete")


app = FastAPI(
    title="AI Agent Observatory",
    description="Multi-tenant agent testing and observability platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# ─── CORS ─────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthMiddleware) # M3: Auth middleware

# ─── Exception Handlers ───────────────────────────────────
 
app.add_exception_handler(RequestValidationError, request_validation_error_handler)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

# ─── Routers ──────────────────────────────────────────────
 
# M3: Auth router
from app.api.v1.auth import router as auth_router
app.include_router(auth_router, prefix="/auth", tags=["auth"])

# M5: Organizations + Invitations router
from app.api.v1.organizations import router as org_router
from app.api.v1.invitations import router as inv_router
app.include_router(org_router, prefix="/organizations", tags=["organizations"])
app.include_router(inv_router, prefix="/invitations", tags=["invitations"])

# M7: Providers router
from app.api.v1.providers import router as providers_router
app.include_router(providers_router, prefix="/providers", tags=["providers"])

# M8: Traces router + WebSocket
from app.api.v1.traces import router as traces_router
from app.ws.traces import router as ws_router
app.include_router(traces_router, prefix="/traces", tags=["traces"])
app.include_router(ws_router, prefix="/ws", tags=["ws"])

# M9: Agents router
from app.api.v1.agents import router as agents_router
app.include_router(agents_router, prefix="/agents", tags=["agents"])

# Faz 1: Conversations (kalıcı sohbet thread'leri)
from app.api.v1.conversations import (
    router as conversations_router,
    agent_conversations_router,
)
app.include_router(agent_conversations_router, prefix="/agents", tags=["conversations"])
app.include_router(conversations_router, prefix="/conversations", tags=["conversations"])

# Faz 4: Agent knowledge router
from app.api.v1.knowledge import router as knowledge_router
app.include_router(knowledge_router, prefix="/agents", tags=["knowledge"])

# M10: HITL router
from app.api.v1.hitl import router as hitl_router
app.include_router(hitl_router, prefix="/hitl", tags=["hitl"])

# M11: Test Suites + Test Runs routers
from app.api.v1.test_suites import router as test_suites_router, test_runs_router
from app.ws.test_runs import router as test_runs_ws_router
app.include_router(test_suites_router, prefix="/test-suites", tags=["test-suites"])
app.include_router(test_runs_router, prefix="/test-runs", tags=["test-runs"])
app.include_router(test_runs_ws_router, prefix="/ws", tags=["ws"])

from app.api.v1.dashboard import router as dashboard_router
app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])

from app.api.v1.mcp_servers import router as mcp_servers_router
app.include_router(mcp_servers_router, prefix="/mcp-servers", tags=["mcp"])

from app.api.v1.teams import router as teams_router, team_runs_router
app.include_router(teams_router, prefix="/teams", tags=["teams"])
app.include_router(team_runs_router, prefix="/team-runs", tags=["teams"])

from app.api.v1.connections import router as connections_router
app.include_router(connections_router, prefix="/connections", tags=["connections"])

from app.ws.team_runs import router as team_runs_ws_router
app.include_router(team_runs_ws_router, prefix="/ws", tags=["ws"])

# ─── Health Check ─────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "ok",
        "version": "0.1.0",
        "env": settings.app_env,
    }
