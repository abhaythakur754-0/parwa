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

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ParwaBaseError,
    RateLimitError,
    ValidationError,
)
from app.logger import configure_logging, get_logger
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.tenant import TenantMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_logger import RequestLoggerMiddleware
from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
)
from app.middleware.api_key_auth import APIKeyAuthMiddleware
from app.middleware.ip_allowlist import (
    IPAllowlistMiddleware,
)
from app.middleware.ai_entitlement import (
    AIEntitlementMiddleware,
)
from app.middleware.csrf import CSRFMiddleware  # FIX A3: CSRF protection
from app.api.auth import router as auth_router
from app.api.mfa import router as mfa_router
from app.api.api_keys import router as api_keys_router
from app.api.client import router as client_router
from app.api.admin import router as admin_router
from app.api.webhooks import router as webhook_router
from app.api.health import router as health_router
from app.api.user_details import router as user_details_router
from app.api.public import router as public_router
from app.api.pricing import router as pricing_router
from app.api.ai_engine import router as ai_engine_router
from app.api.ai_agent import router as ai_agent_router
from app.api.jarvis import router as jarvis_router
from app.api.onboarding import router as onboarding_router
from app.api.integrations import router as integrations_router
from app.api.knowledge_base import router as knowledge_base_router
from app.api.verification import router as verification_router  # Week 6 Day 10-11: Business Email OTP
from app.api.ticket_analytics import router as analytics_router  # Phase 4: Ticket analytics dashboard
from app.api.email_channel import router as email_channel_router  # Week 13 Day 1: Email channel admin endpoints
from app.api.ooo_detection import router as ooo_detection_router  # Week 13 Day 3: OOO detection endpoints (F-122)
from app.api.bounce_complaint import router as bounce_complaint_router  # Week 13 Day 3: Bounce/complaint endpoints (F-124)
from app.api.chat_widget import router as chat_widget_router  # Week 13 Day 4: Chat widget endpoints (F-122)
from app.api.sms_channel import router as sms_channel_router  # Week 13 Day 5: SMS channel endpoints (F-123)
from app.api.jarvis_control import router as jarvis_control_router  # Week 14 Day 1: Jarvis Command Center (F-087, F-088, F-089)
from app.api.jarvis_ops import router as jarvis_ops_router  # Week 14 Day 2: Quick Commands (F-090), Error Panel (F-091), Train from Error (F-092)
from app.api.agents import router as agents_router  # Week 14 Day 4: Agent Provisioning (F-095), Dynamic Instructions (F-096)
from app.api.agent_dashboard import router as agent_dashboard_router  # Week 15 Day 5: Agent Dashboard (F-097)
from app.api.dashboard import router as dashboard_router  # Week 15 Day 1: Dashboard Home (F-036), Activity Feed (F-037), KPI Metrics (F-038)
from app.api.analytics_advanced import router as analytics_advanced_router  # Week 15 Day 2: Adaptation (F-039), Savings (F-040), Workforce (F-041)
from app.api.analytics_intelligence import router as analytics_intelligence_router  # Week 15 Day 3: Growth Nudge (F-042), Forecast (F-043), CSAT Trends (F-044)
from app.api.reports import router as reports_router  # Week 15 Day 4: Export Reports (F-045)
from app.api.custom_integrations import router as custom_integrations_router  # Week 17: Custom Integration Builder (F-031)
from app.api.gdpr import router as gdpr_router  # Day 3: GDPR data privacy endpoints (E3)

# Import webhook handlers so their @register_handler decorators fire and
# populate the registry. These modules have no other import side-effects.
import app.webhooks.paddle_handler   # noqa: F401, E402
import app.webhooks.brevo_handler    # noqa: F401, E402
import app.webhooks.twilio_handler   # noqa: F401, E402
import app.webhooks.shopify_handler  # noqa: F401, E402

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
    - Run database migrations (Alembic)
    - OpenAPI visibility based on DEBUG flag (BC-011)
    - Initialize Redis connection pool
    - Register Socket.io ASGI app
    - Pre-load Jarvis knowledge base

    Shutdown:
    - Close Redis connection pool
    - Log shutdown event
    """
    settings = get_settings()
    configure_logging(settings.ENVIRONMENT)

    # ── Run Alembic migrations on startup (Docker-safe) ──
    try:
        import subprocess
        result = subprocess.run(
            ["alembic", "-c", "/app/database/alembic.ini", "upgrade", "head"],
            cwd="/app/database",
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger = get_logger("lifespan")
            logger.info("alembic_migrations_completed")
        else:
            logger = get_logger("lifespan")
            logger.warning(
                "alembic_migrations_failed",
                returncode=result.returncode,
                stderr=result.stderr[:500] if result.stderr else "",
            )
    except Exception as exc:
        logger = get_logger("lifespan")
        logger.warning("alembic_migrations_error", error=str(exc))

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
        from app.core.redis import get_redis
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
        from app.core.socketio import create_socketio_app
        socketio_app = create_socketio_app()
        app.mount("/ws", socketio_app)
        logger.info("socketio_mounted", path="/ws")
    except Exception as exc:
        logger = get_logger("lifespan")
        logger.warning(
            "socketio_mount_failed",
            error=str(exc),
        )

    # Phase 7: Pre-load Jarvis knowledge base at startup
    try:
        from app.services.jarvis_knowledge_service import load_all_knowledge
        load_all_knowledge()
        logger = get_logger("lifespan")
        logger.info("jarvis_knowledge_loaded")
    except Exception as exc:
        logger = get_logger("lifespan")
        logger.warning(
            "jarvis_knowledge_load_failed",
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
        from app.core.redis import close_redis
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

# 7. IP allowlist — BC-012 (disabled by default)
# Set IP_ALLOWLIST_ENABLED=true to activate
app.add_middleware(IPAllowlistMiddleware)

# 8. AI Entitlement — Week 8: feature gating for /api/ai/ paths
app.add_middleware(AIEntitlementMiddleware)

# 8.5 CSRF protection — FIX A3: double-submit cookie pattern
app.add_middleware(CSRFMiddleware)

# 9. CORS middleware (frontend cross-origin access)
# FIX D1: Never fall back to wildcard when credentials are enabled.
# If CORS_ORIGINS is empty or settings fail, use an explicit allowlist
# or deny all — never allow every origin with cookies.
try:
    _settings = get_settings()
    if _settings.CORS_ORIGINS:
        _cors_origins = [
            o.strip() for o in _settings.CORS_ORIGINS.split(",")
            if o.strip()
        ]
    else:
        # No explicit origins configured — deny cross-origin in production
        import logging
        logging.getLogger("parwa.cors").warning(
            "CORS_ORIGINS not configured — cross-origin requests will be denied. "
            "Set CORS_ORIGINS env var to allow specific origins."
        )
        _cors_origins = []
except Exception:
    import logging
    logging.getLogger("parwa.cors").warning(
        "Failed to load CORS settings — cross-origin requests will be denied."
    )
    _cors_origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ────────────────────────────────────────────────────────

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(mfa_router)
app.include_router(api_keys_router)
app.include_router(client_router)
app.include_router(admin_router)
app.include_router(webhook_router)
app.include_router(user_details_router)
app.include_router(public_router)  # Public API for landing page (no auth required)
app.include_router(pricing_router)  # Pricing API (no auth required)
app.include_router(ai_engine_router)  # Week 8: AI Engine endpoints
app.include_router(ai_agent_router)  # SG-21/SG-22: AI agent assignments
app.include_router(jarvis_router)  # Week 6: Jarvis onboarding chat
app.include_router(onboarding_router)  # Week 6: Onboarding wizard (F-028 to F-035)
app.include_router(integrations_router)  # Week 6: Integration management (F-030/F-031)
app.include_router(knowledge_base_router)  # Week 6: Knowledge base (F-032/F-033)
app.include_router(verification_router)  # Week 6 Day 10-11: Business Email OTP verification
app.include_router(analytics_router)  # Phase 4: Ticket analytics dashboard
app.include_router(email_channel_router)  # Week 13 Day 1: Email channel admin endpoints
app.include_router(ooo_detection_router)  # Week 13 Day 3: OOO detection endpoints (F-122)
app.include_router(bounce_complaint_router)  # Week 13 Day 3: Bounce/complaint endpoints (F-124)
app.include_router(chat_widget_router)  # Week 13 Day 4: Chat widget endpoints (F-122)
app.include_router(sms_channel_router)  # Week 13 Day 5: SMS channel endpoints (F-123)
app.include_router(jarvis_control_router)  # Week 14 Day 1: Jarvis Command Center (F-087, F-088, F-089)
app.include_router(jarvis_ops_router)  # Week 14 Day 2: Quick Commands (F-090), Error Panel (F-091), Train from Error (F-092)
app.include_router(agents_router)  # Week 14 Day 4: Agent Provisioning (F-095), Dynamic Instructions (F-096)
app.include_router(agent_dashboard_router)  # Week 15 Day 5: Agent Dashboard (F-097)
app.include_router(dashboard_router)  # Week 15 Day 1: Dashboard Home (F-036), Activity Feed (F-037), KPI Metrics (F-038)
app.include_router(analytics_advanced_router)  # Week 15 Day 2: Adaptation (F-039), Savings (F-040), Workforce (F-041)
app.include_router(analytics_intelligence_router)  # Week 15 Day 3: Growth Nudge (F-042), Forecast (F-043), CSAT Trends (F-044)
app.include_router(reports_router)  # Week 15 Day 4: Export Reports (F-045)
app.include_router(custom_integrations_router)  # Week 17: Custom Integration Builder (F-031)
app.include_router(gdpr_router)  # Day 3: GDPR data privacy endpoints (E3)


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

    from app.core.event_buffer import get_events_since
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
