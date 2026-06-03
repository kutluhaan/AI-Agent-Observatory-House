from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.redis import close_redis, get_redis_pool
from app.core.responses import AppError, app_error_handler, generic_error_handler

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Observatory API", env=settings.app_env)

    # Warm up Redis connection
    await get_redis_pool()
    logger.info("Redis connected")

    yield

    # Shutdown
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

# ─── Exception Handlers ───────────────────────────────────

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

# ─── Routers ──────────────────────────────────────────────

from app.api.auth import router as auth_router
from app.api.streaming import router as streaming_router

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(streaming_router, tags=["streaming"])


# ─── Health Check ─────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "ok",
        "version": "0.1.0",
        "env": settings.app_env,
    }
