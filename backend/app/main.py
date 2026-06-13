"""
PARWA — FastAPI Application Entry Point (Phase 1-5 Complete)

CORS middleware, all API routers, health check, and startup/shutdown events.

CRITICAL RULES:
- BC-001: All endpoints must use company_id from JWT token for tenant isolation
- BC-008: Never crash — all route handlers in try/except
- Paddle is ONLY for PARWA's own subscription billing
- No mock data, no placeholder emails
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.integrations import router as integrations_router
from app.api.billing import router as billing_router
from app.api.notifications import router as notifications_router
from app.api.knowledge import router as knowledge_router
from app.api.industry import router as industry_router
from app.api.connectors import router as connectors_router
from app.api.auth import router as auth_router
from app.api.variants import router as variants_router
from app.api.voice import router as voice_router
from app.api.monitoring import router as monitoring_router
from app.api.tickets import router as tickets_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialise services on startup, tear down on shutdown."""
    try:
        logger.info(
            "PARWA %s starting — API prefix: %s",
            settings.VERSION,
            settings.API_V1_PREFIX,
        )

        # Ensure all database tables exist
        try:
            from database.base import Base, engine
            from database.models import (  # noqa: F401 — registers all tables
                Company,
                User,
                CompanySetting,
                Integration,
                EventBuffer,
                Notification,
                Ticket,
                TicketMessage,
                KnowledgeDocument,
                FAQ,
                CustomConnector,
                SLARule,
            )
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables verified / created")
        except Exception as exc:
            logger.error("Database table creation failed: %s", exc)

        logger.info("PARWA %s startup complete", settings.VERSION)
        yield

    except Exception as exc:
        logger.error("PARWA lifespan error: %s", exc)
        yield
    finally:
        logger.info("PARWA %s shutting down", settings.VERSION)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="PARWA — Multi-tenant AI customer support platform (Phase 1-5 Complete)",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Register API routers
# ---------------------------------------------------------------------------

app.include_router(integrations_router, prefix=settings.API_V1_PREFIX)
app.include_router(billing_router, prefix=settings.API_V1_PREFIX)
app.include_router(notifications_router, prefix=settings.API_V1_PREFIX)
app.include_router(knowledge_router, prefix=settings.API_V1_PREFIX)
app.include_router(industry_router, prefix=settings.API_V1_PREFIX)
app.include_router(connectors_router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(variants_router, prefix=settings.API_V1_PREFIX)
app.include_router(voice_router, prefix=settings.API_V1_PREFIX)
app.include_router(monitoring_router, prefix=settings.API_V1_PREFIX)
app.include_router(tickets_router, prefix=settings.API_V1_PREFIX)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
def health_check() -> dict:
    """Return system health status. Never raises (BC-008)."""
    try:
        db_ok = False
        try:
            from database.base import engine
            with engine.connect() as conn:
                conn.execute(
                    __import__("sqlalchemy").text("SELECT 1")
                )
            db_ok = True
        except Exception as exc:
            logger.warning("Health check DB probe failed: %s", exc)

        return {
            "status": "healthy" if db_ok else "degraded",
            "project": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "database": "connected" if db_ok else "unavailable",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        return {
            "status": "degraded",
            "project": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "error": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
