"""
AI Agent Observatory — FastAPI Application

M1: Temel iskelet, health check
M2: DB modelleri yüklendi (Base.metadata)
M3: Redis bağlantısı, auth router (register, login, logout, /me)
M4: refresh, switch-org, verify-email, resend-verification, Resend email
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.core.config import get_settings
from app.core.database import Base
from app.core.redis import close_redis, get_redis_pool
from app.core.responses import (
    AppError, 
    app_error_handler, 
    generic_error_handler,
    request_validation_error_handler,
    )
from app.middleware import AuthMiddleware

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

# ─── Health Check ─────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "ok",
        "version": "0.1.0",
        "env": settings.app_env,
    }
