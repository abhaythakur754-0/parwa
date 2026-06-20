"""
Jarvis API — FastAPI Application

Creates the FastAPI app, wires CORS middleware, initializes
jarvis_db InMemory mode on startup, and mounts all routers.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("jarvis.api")

# ── App uptime tracker ─────────────────────────────────────────
_start_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup + shutdown lifecycle events."""
    global _start_time
    _start_time = time.time()

    # ── Initialize jarvis_db InMemory mode ────────────────────
    from app.core.jarvis_pipeline.jarvis_db import use_in_memory, reset_db

    reset_db()
    use_in_memory()
    logger.info("Jarvis DB initialized → InMemory mode (dev)")

    # ── Optionally warm caches / pre-load configs here ───────
    logger.info("Jarvis API started")

    yield

    # ── Shutdown ──────────────────────────────────────────────
    logger.info("Jarvis API shutting down")


# ── Create app ─────────────────────────────────────────────────

app = FastAPI(
    title="PARWA AI Customer Support Platform",
    description=(
        "Phase 9 — Full REST API for the PARWA AI CS Platform. "
        "Exposes chat pipeline, notifications, flags, quality coach, "
        "SLA tracking, approvals, emergency controls, SSE streaming, "
        "multi-tenant onboarding, and key-based auth."
    ),
    version="9.0.0",
    lifespan=lifespan,
)


# ── CORS (allow all origins for dev) ──────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Mount routers ──────────────────────────────────────────────

from app.api.jarvis_routes import router as jarvis_router
from app.api.sse import router as sse_router
from app.api.onboarding_routes import router as onboarding_router

app.include_router(jarvis_router, prefix="/api")
app.include_router(sse_router, prefix="/api")
app.include_router(onboarding_router, prefix="/api")


# ── Health check ──────────────────────────────────────────────

@app.get("/api/health", tags=["system"])
async def health_check():
    """Liveness probe. Returns app version, uptime, and DB status."""
    from app.core.jarvis_pipeline.jarvis_db import get_db

    db = get_db()
    uptime_s = time.time() - _start_time

    try:
        health = await db.get_integration_health("default_tenant")
        db_ok = True
    except Exception as exc:
        health = {}
        db_ok = False
        logger.error("Health check DB probe failed: %s", exc)

    return {
        "status": "healthy" if db_ok else "degraded",
        "app": "jarvis-api",
        "version": "9.0.0",
        "uptime_seconds": round(uptime_s, 1),
        "db_ok": db_ok,
        "integration_health": health,
    }
