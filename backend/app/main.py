"""
PARWA FastAPI Application (BC-012)

Main FastAPI app with:
- Health/ready/metrics endpoints (BC-012)
- Structured JSON error responses (BC-012)
- No stack traces to users (BC-012)
- OpenAPI schema hidden when DEBUG=False (BC-011)
- Redis connection pool + tenant-scoped keys (BC-001)
- Socket.io server with tenant rooms (BC-005)
- Event buffer for reconnection recovery (BC-005)
- Middleware wired: error_handler, request_logger, tenant, rate_limit
- APIKeyAuthMiddleware wired (BC-011)
- CORS middleware configured (frontend cross-origin access)
- Security headers middleware (HSTS, CSP, X-Frame-Options)
"""

from contextlib import asynccontextmanager
import os
from datetime import datetime, timezone

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.app.config import get_settings
from backend.app.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ParwaBaseError,
    RateLimitError,
    ValidationError,
)
from backend.app.logger import configure_logging, get_logger
from backend.app.middleware.error_handler import ErrorHandlerMiddleware
from backend.app.middleware.tenant import TenantMiddleware
from backend.app.middleware.rate_limit import RateLimitMiddleware
from backend.app.middleware.request_logger import RequestLoggerMiddleware
from backend.app.middleware.security_headers import (
    SecurityHeadersMiddleware,
)
from backend.app.middleware.api_key_auth import APIKeyAuthMiddleware
from backend.app.api.auth import router as auth_router
from backend.app.api.mfa import router as mfa_router
from backend.app.api.api_keys import router as api_keys_router
from backend.app.api.client import router as client_router
from backend.app.api.admin import router as admin_router

# Track if logging has been configured (idempotent)
_logging_configured = False

# Current environment (set at import time for test route guards)
_CURRENT_ENV = os.environ.get("ENVIRONMENT", "development")


def _ensure_logging():
    """Ensure logging is configured (safe to call multiple times)."""
    global _logging_configured  # noqa: PLW0603
    if not _logging_configured:
        env = os.environ.get("ENVIRONMENT", "production")
        configure_logging(env)
        _logging_configured = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown.

    Startup:
    - Configure structured logging
    - OpenAPI visibility based on DEBUG flag (BC-011)
    - Initialize Redis connection pool
    - Register Socket.io ASGI app

    Shutdown:
    - Close Redis connection pool
    - Log shutdown event
    """
    settings = get_settings()
    configure_logging(settings.ENVIRONMENT)

    # Hide OpenAPI schema when not in debug mode (BC-011)
    if settings.DEBUG:
        app.docs_url = "/docs"
        app.redoc_url = "/redoc"
        app.openapi_url = "/openapi.json"
    else:
        app.docs_url = None
        app.redoc_url = None
        app.openapi_url = None

    # Initialize Redis connection pool (BC-012: fail-open on error)
    try:
        from backend.app.core.redis import get_redis
        redis_client = await get_redis()
        await redis_client.ping()
        logger = get_logger("lifespan")
        logger.info("redis_initialized")
    except Exception as exc:
        logger = get_logger("lifespan")
        logger.warning(
            "redis_init_failed_fail_open",
            error=str(exc),
        )

    # Register Socket.io ASGI app on /ws path
    try:
        from backend.app.core.socketio import create_socketio_app
        socketio_app = create_socketio_app()
        app.mount("/ws", socketio_app)
        logger.info("socketio_mounted", path="/ws")
    except Exception as exc:
        logger = get_logger("lifespan")
        logger.warning(
            "socketio_mount_failed",
            error=str(exc),
        )

    logger = get_logger("lifespan")
    logger.info(
        "parwa_startup",
        environment=settings.ENVIRONMENT,
        version="0.1.0",
    )
    yield

    # Shutdown: close Redis pool
    try:
        from backend.app.core.redis import close_redis
        await close_redis()
        logger.info("redis_closed")
    except Exception as exc:
        logger.warning("redis_close_error", error=str(exc))

    logger.info("parwa_shutdown")


app = FastAPI(
    title="PARWA API",
    description="AI-Powered Customer Support Platform",
    version="0.1.0",
    lifespan=lifespan,
    # docs/openapi set in lifespan after settings loaded to avoid
    # module-level crash when env vars missing (BC-011)
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# ── Middleware Stack (order matters: outermost first) ──────────────

# 1. Error handler (outermost) — correlation ID + structured errors
app.add_middleware(ErrorHandlerMiddleware)

# 2. Request logger — audit trail for every request
app.add_middleware(RequestLoggerMiddleware)

# 3. Tenant middleware — BC-001 multi-tenant isolation
app.add_middleware(TenantMiddleware)

# 4. Rate limit middleware — BC-011/BC-012 rate limiting
app.add_middleware(RateLimitMiddleware)

# 5. API Key auth — BC-011
app.add_middleware(APIKeyAuthMiddleware)

# 6. Security headers — BC-011/BC-012
app.add_middleware(SecurityHeadersMiddleware)

# 7. CORS middleware (frontend cross-origin access)
try:
    _settings = get_settings()
    _cors_origins = (
        [o.strip() for o in _settings.CORS_ORIGINS.split(",")]
        if _settings.CORS_ORIGINS
        else ["*"]
    )
except Exception:
    _cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(mfa_router)
app.include_router(api_keys_router)
app.include_router(client_router)
app.include_router(admin_router)


# ── Exception Handlers (BC-012: structured JSON, no stack traces) ───


@app.exception_handler(ParwaBaseError)
async def parwa_exception_handler(
    request: Request, exc: ParwaBaseError,
) -> JSONResponse:
    """Handle all PARWA custom exceptions with structured JSON."""
    data = exc.to_dict()
    # BC-012: Include correlation ID in every error response
    correlation_id = getattr(request.state, "correlation_id", None)
    if correlation_id:
        data["correlation_id"] = correlation_id
    return JSONResponse(
        status_code=exc.status_code,
        content=data,
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle 404 with structured JSON (BC-012)."""
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "NOT_FOUND",
                "message": f"The path {request.url.path} was not found",
                "details": None,
            }
        },
    )


@app.exception_handler(422)
async def validation_error_handler(
    request: Request, exc: Exception,
) -> JSONResponse:
    """Handle 422 validation errors with structured JSON (BC-012)."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": None,
            }
        },
    )


@app.exception_handler(500)
async def internal_error_handler(
    request: Request, exc: Exception,
) -> JSONResponse:
    """Handle 500 errors — NO stack traces to users (BC-012)."""
    _ensure_logging()
    logger = get_logger("error_handler")
    logger.error(
        "internal_error",
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
        error_message=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "details": None,
            }
        },
    )


# ── Health Endpoints (BC-012) ──────────────────────────────────────


@app.get("/health", tags=["Health"])
async def health_check():
    """Liveness probe — returns 200 if app is running.

    BC-012: Health endpoint must exist and be publicly accessible.
    Checks Redis connectivity and reports subsystem health.
    """
    _ensure_logging()

    # Check Redis health (BC-012: detect Redis failures)
    redis_status = "unknown"
    try:
        from backend.app.core.redis import redis_health_check
        redis_info = await redis_health_check()
        redis_status = redis_info["status"]
    except Exception:
        redis_status = "unreachable"

    # Check DB health (BC-012: detect DB failures)
    db_status = "unknown"
    try:
        from database.base import check_db_health
        db_info = await check_db_health()
        db_status = db_info["status"]
    except Exception:
        db_status = "unreachable"

    healthy = (
        redis_status == "healthy" and db_status == "healthy"
    )
    overall = "healthy" if healthy else "degraded"

    return {
        "status": overall,
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subsystems": {
            "redis": {"status": redis_status},
            "database": {"status": db_status},
        },
    }


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness probe — returns 200 when dependencies are healthy.

    BC-012: Readiness endpoint must exist. Returns 503 if any
    critical dependency is unhealthy.
    """
    _ensure_logging()

    # Check Redis
    redis_ok = False
    try:
        from backend.app.core.redis import redis_health_check
        redis_info = await redis_health_check()
        redis_ok = redis_info["status"] == "healthy"
    except Exception:
        redis_ok = False

    # Check Database
    db_ok = False
    try:
        from database.base import check_db_health
        db_info = await check_db_health()
        db_ok = db_info["status"] == "healthy"
    except Exception:
        db_ok = False

    if not redis_ok or not db_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "subsystems": {
                    "redis": {"status": "ready" if redis_ok else "unhealthy"},
                    "database": {"status": "ready" if db_ok else "unhealthy"},
                },
            },
        )

    return {
        "status": "ready",
        "subsystems": {
            "redis": {"status": "ready"},
            "database": {"status": "ready"},
        },
    }


@app.get("/metrics", tags=["Health"])
async def metrics():
    """Prometheus-style metrics endpoint.

    BC-012: Monitoring endpoint must exist.
    Reports build info, health status, and Redis/DB connectivity.
    """
    _ensure_logging()
    try:
        settings = get_settings()
        env = settings.ENVIRONMENT
    except Exception:
        env = "unknown"
    now = datetime.now(timezone.utc).isoformat()

    # Gather subsystem metrics
    redis_up = 0
    db_up = 0
    try:
        from backend.app.core.redis import redis_health_check
        redis_info = await redis_health_check()
        redis_up = 1 if redis_info["status"] == "healthy" else 0
    except Exception:
        redis_up = 0
    try:
        from database.base import check_db_health
        db_info = await check_db_health()
        db_up = 1 if db_info["status"] == "healthy" else 0
    except Exception:
        db_up = 0

    return PlainTextResponse(
        content=(
            "# HELP parwa_build_info PARWA build information\n"
            "# TYPE parwa_build_info gauge\n"
            f'parwa_build_info{{version="0.1.0",environment="{env}"}} 1\n'
            "# HELP parwa_health_check PARWA health status"
            " (1=healthy, 0=unhealthy)\n"
            "# TYPE parwa_health_check gauge\n"
            f'parwa_health_check{{status="healthy"}} 1\n'
            "# HELP parwa_redis_up Redis connectivity (1=up, 0=down)\n"
            "# TYPE parwa_redis_up gauge\n"
            f"parwa_redis_up {redis_up}\n"
            "# HELP parwa_database_up Database connectivity (1=up, 0=down)\n"
            "# TYPE parwa_database_up gauge\n"
            f"parwa_database_up {db_up}\n"
            f"# Last scraped at {now}\n"
        ),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# ── Events API (BC-005: reconnection recovery) ────────────────────


@app.get("/api/events/since", tags=["Events"])
async def get_events_since_endpoint(
    request: Request,
    last_seen: float = Query(
        ..., description="Epoch timestamp of last received event"
    ),
):
    """Fetch events missed during disconnection (BC-005).

    On reconnect, the client calls this endpoint with their last_seen
    timestamp to fetch all events that occurred while disconnected.

    BC-001: Events are scoped to the requesting tenant.
    BC-005: Event buffer stores events for 24 hours.
    """
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

    from backend.app.core.event_buffer import get_events_since
    events = await get_events_since(
        company_id=company_id,
        last_seen=last_seen,
    )

    return {
        "events": events,
        "count": len(events),
        "last_seen": last_seen,
    }


# ── Test-only routes (only active in test environment) ──────────

if _CURRENT_ENV == "test":

    @app.get("/test/raise/not-found")
    async def _test_raise_not_found():
        raise NotFoundError(
            message="Test resource not found",
            details={"id": "123"},
        )

    @app.get("/test/raise/validation")
    async def _test_raise_validation():
        raise ValidationError(
            message="Test validation",
            details=["field x invalid"],
        )

    @app.get("/test/raise/authentication")
    async def _test_raise_authentication():
        raise AuthenticationError(
            message="Test auth failed",
            details={"reason": "bad token"},
        )

    @app.get("/test/raise/authorization")
    async def _test_raise_authorization():
        raise AuthorizationError(
            message="Test forbidden",
            details={"required": "admin"},
        )

    @app.get("/test/raise/rate-limit")
    async def _test_raise_rate_limit():
        raise RateLimitError(
            message="Test rate limit",
            details={"retry_after": 60},
        )

    @app.get("/test/raise/internal")
    async def _test_raise_internal():
        raise ValueError("This simulates an unexpected 500 error")
