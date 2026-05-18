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

from fastapi import Depends, FastAPI, Query, Request
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
from app.middleware.csrf import CSRFSecurityMiddleware
from app.middleware.api_key_auth import APIKeyAuthMiddleware
from app.middleware.ip_allowlist import (
    IPAllowlistMiddleware,
)
from app.middleware.ai_entitlement import (
    AIEntitlementMiddleware,
)
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
from app.api.jarvis_cc import router as jarvis_cc_router
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
from app.api.voice_channel import router as voice_channel_router  # Voice Channel: Twilio voice calls, call history, config
from app.api.workflow import router as workflow_router  # Week 10: Workflow API (now with LangGraph multi-agent)
from app.api.tickets import router as tickets_router  # BUG-3 FIX: Day 26 Ticket CRUD (was dead code in api_router)
from app.api.technique_config import router as technique_config_router  # BUG-3 FIX: SG-17 Technique Config Admin (was dead code in api_router)

# ── Previously Unregistered Routers (80+ dead endpoints now live) ──
from app.api.billing import router as billing_router  # Billing CRUD + Paddle integration
from app.api.billing_webhooks import router as billing_webhooks_router  # Paddle webhook endpoints
from app.api.notifications import router as notifications_router  # Notification CRUD + preferences
from app.api.customers import router as customers_router  # Customer management
from app.api.sla import router as sla_router  # SLA policy management
from app.api.channels import router as channels_router  # Channel management
from app.api.identity import router as identity_router  # Identity resolution
from app.api.custom_fields import router as custom_fields_router  # Custom field CRUD
from app.api.triggers import router as triggers_router  # Trigger management
from app.api.ticket_lifecycle import router as ticket_lifecycle_router  # Ticket lifecycle (escalate, reopen, freeze)
from app.api.ticket_lifecycle import incident_router  # Incident management
from app.api.ticket_lifecycle import spam_router  # Spam moderation
from app.api.ticket_messages import router as ticket_messages_router  # Ticket messages
from app.api.ticket_notes import router as ticket_notes_router  # Internal notes
from app.api.ticket_bulk import router as ticket_bulk_router  # Bulk ticket actions
from app.api.ticket_merge import router as ticket_merge_router  # Ticket merging
from app.api.ticket_search import router as ticket_search_router  # Ticket search
from app.api.ticket_timeline import router as ticket_timeline_router  # Ticket timeline
from app.api.ticket_assignment import router as ticket_assignment_router  # Ticket assignment
from app.api.ticket_assignment import rules_router as assignment_rules_router  # Assignment rules
from app.api.ticket_classification import router as ticket_classification_router  # Ticket classification
from app.api.ticket_templates import router as ticket_templates_router  # Ticket templates
from app.api.collisions import router as collisions_router  # Collision detection
from app.api.classification import router as classification_router  # Text classification
from app.api.signals import router as signals_router  # Signal extraction
from app.api.ai_classification import router as ai_classification_router  # AI classification
from app.api.ai_signals import router as ai_signals_router  # AI signal extraction
from app.api.rag import router as rag_router  # RAG retrieval
from app.api.response import router as response_api_router  # Response generation + brand voice + assignment + migration

from app.api.deps import get_current_user
from database.models.core import User

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

    # Phase 6: Initialize Sentry error monitoring
    try:
        from app.core.sentry import init_sentry
        sentry_initialized = init_sentry()
        logger = get_logger("lifespan")
        logger.info("sentry_initialized", status=sentry_initialized)
    except Exception as exc:
        logger = get_logger("lifespan")
        logger.warning("sentry_init_failed", error=str(exc))

    # ── Run Alembic migrations on startup ──
    try:
        import subprocess
        import pathlib
        # Resolve database directory: Docker uses /app/database, local uses project root
        _db_dir = os.environ.get("DATABASE_DIR", "")
        if not _db_dir or not pathlib.Path(_db_dir).exists():
            # Try common locations
            for candidate in [
                pathlib.Path("/app/database"),
                pathlib.Path(__file__).resolve().parents[3] / "database",
            ]:
                if candidate.exists():
                    _db_dir = str(candidate)
                    break
        if _db_dir:
            result = subprocess.run(
                ["alembic", "-c", f"{_db_dir}/alembic.ini", "upgrade", "head"],
                cwd=_db_dir,
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
        else:
            logger = get_logger("lifespan")
            logger.warning("alembic_skipped_database_dir_not_found")
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

    # Phase 4: Pre-build LangGraph multi-agent graph at startup
    try:
        from app.core.langgraph import build_parwa_graph, get_checkpointer
        checkpointer = get_checkpointer()
        _parwa_graph = build_parwa_graph(checkpointer=checkpointer)
        # Store graph on app.state for API endpoints to use
        app.state.parwa_graph = _parwa_graph
        logger = get_logger("lifespan")
        logger.info(
            "langgraph_graph_initialized",
            node_count=19,
            has_checkpointer=checkpointer is not None,
        )
    except Exception as exc:
        logger = get_logger("lifespan")
        logger.warning(
            "langgraph_graph_init_failed_fail_open",
            error=str(exc),
            message="LangGraph graph will be built on first request",
        )
        app.state.parwa_graph = None

    logger = get_logger("lifespan")
    logger.info(
        "parwa_startup",
        environment=settings.ENVIRONMENT,
        version=settings.APP_VERSION,
    )
    yield

    # Shutdown: flush Sentry events
    try:
        from app.core.sentry import flush as sentry_flush
        sentry_flush(timeout=2.0)
    except Exception as exc:
        logger.warning("sentry_flush_error", error=str(exc))

    # Shutdown: close Redis pool
    try:
        from app.core.redis import close_redis
        await close_redis()
        logger.info("redis_closed")
    except Exception as exc:
        logger.warning("redis_close_error", error=str(exc))

    logger.info("parwa_shutdown")


# Load settings early to configure docs visibility at construction time.
# This avoids the issue where setting docs_url after construction does not
# register the OpenAPI routes (FastAPI registers routes at init time).
try:
    _init_settings = get_settings()
    _docs_url = "/docs" if _init_settings.DEBUG else None
    _redoc_url = "/redoc" if _init_settings.DEBUG else None
    _openapi_url = "/openapi.json" if _init_settings.DEBUG else None
except Exception:
    _docs_url = None
    _redoc_url = None
    _openapi_url = None

app = FastAPI(
    title="PARWA API",
    description="AI-Powered Customer Support Platform",
    version=_init_settings.APP_VERSION,  # R-05: Single source of truth from config
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
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

# 7. CSRF protection — Origin/Referer validation + double-submit cookie
app.add_middleware(CSRFSecurityMiddleware)

# 8. IP allowlist — BC-012 (disabled by default)
# Set IP_ALLOWLIST_ENABLED=true to activate
app.add_middleware(IPAllowlistMiddleware)

# 9. AI Entitlement — Week 8: feature gating for /api/ai/ paths
app.add_middleware(AIEntitlementMiddleware)

# 10. CORS middleware (frontend cross-origin access)
# SECURITY (C-05, L-16): Never fall back to wildcard ["*"] when
# allow_credentials=True. CORS origins must always be explicit,
# even when OpenAPI docs are hidden in non-debug mode.
# Per CORS spec, browsers reflect the requesting origin with credentials,
# effectively allowing any website to make credentialed requests.
try:
    _settings = get_settings()
    _cors_origins = (
        [o.strip() for o in _settings.CORS_ORIGINS.split(",") if o.strip()]
        if _settings.CORS_ORIGINS
        else [_settings.FRONTEND_URL]
    )
except Exception:
    # Fail closed: restrict to localhost rather than open wildcard
    _cors_origins = ["http://localhost:3000"]

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
app.include_router(jarvis_cc_router)  # Phase 2+: Jarvis Customer Care (awareness + commands)
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
app.include_router(voice_channel_router)  # Voice Channel: Twilio voice calls
app.include_router(workflow_router)  # Week 10: Workflow API (now with LangGraph multi-agent)
app.include_router(tickets_router, prefix="/api/v1", tags=["tickets"])  # BUG-3 FIX: Tickets at /api/v1/tickets (matches variant_check.py)
app.include_router(technique_config_router, tags=["technique-config"])  # BUG-3 FIX: Technique Config at /api/techniques/config (router already has prefix)

# ── Previously Unregistered Routers (80+ endpoints now live) ───────

# Billing & Paddle
app.include_router(billing_router, tags=["billing"])  # prefix: /api/billing
app.include_router(billing_webhooks_router, tags=["billing-webhooks"])  # prefix: /api/v1

# Notifications
app.include_router(notifications_router, prefix="/api/v1", tags=["notifications"])  # prefix: /notifications -> /api/v1/notifications

# Customer management
app.include_router(customers_router, prefix="/api/v1", tags=["customers"])  # prefix: /customers -> /api/v1/customers

# SLA management
app.include_router(sla_router, prefix="/api/v1", tags=["sla"])  # prefix: /sla -> /api/v1/sla

# Channel management
app.include_router(channels_router, prefix="/api/v1", tags=["channels"])  # prefix: /channels -> /api/v1/channels

# Identity resolution
app.include_router(identity_router, prefix="/api/v1", tags=["identity"])  # prefix: /identity -> /api/v1/identity

# Custom fields
app.include_router(custom_fields_router, prefix="/api/v1", tags=["custom-fields"])  # prefix: /custom-fields -> /api/v1/custom-fields

# Triggers
app.include_router(triggers_router, prefix="/api/v1", tags=["triggers"])  # prefix: /triggers -> /api/v1/triggers

# Ticket sub-routers (all under /api/v1 to match tickets_router prefix)
app.include_router(ticket_lifecycle_router, prefix="/api/v1", tags=["ticket-lifecycle"])  # prefix: /tickets -> /api/v1/tickets
app.include_router(incident_router, prefix="/api/v1", tags=["incidents"])  # prefix: /incidents -> /api/v1/incidents
app.include_router(spam_router, prefix="/api/v1", tags=["spam"])  # prefix: /spam -> /api/v1/spam
app.include_router(ticket_messages_router, prefix="/api/v1", tags=["ticket-messages"])  # prefix: /tickets -> /api/v1/tickets
app.include_router(ticket_notes_router, prefix="/api/v1", tags=["ticket-notes"])  # prefix: /tickets -> /api/v1/tickets
app.include_router(ticket_bulk_router, prefix="/api/v1", tags=["ticket-bulk"])  # prefix: /tickets/bulk -> /api/v1/tickets/bulk
app.include_router(ticket_merge_router, prefix="/api/v1", tags=["ticket-merge"])  # prefix: /tickets/merge -> /api/v1/tickets/merge
app.include_router(ticket_search_router, prefix="/api/v1", tags=["ticket-search"])  # prefix: /tickets -> /api/v1/tickets
app.include_router(ticket_timeline_router, prefix="/api/v1", tags=["ticket-timeline"])  # prefix: /tickets -> /api/v1/tickets
app.include_router(ticket_assignment_router, prefix="/api/v1", tags=["ticket-assignment"])  # prefix: /tickets -> /api/v1/tickets
app.include_router(assignment_rules_router, prefix="/api/v1", tags=["assignment-rules"])  # prefix: /assignments/rules -> /api/v1/assignments/rules
app.include_router(ticket_classification_router, prefix="/api/v1", tags=["ticket-classification"])  # prefix: /tickets -> /api/v1/tickets
app.include_router(ticket_templates_router, prefix="/api/v1", tags=["ticket-templates"])  # prefix: /templates -> /api/v1/templates
app.include_router(collisions_router, prefix="/api/v1", tags=["ticket-collisions"])  # prefix: /tickets -> /api/v1/tickets

# AI & Classification
app.include_router(classification_router, tags=["classification"])  # prefix: /api/classification
app.include_router(signals_router, tags=["signals"])  # prefix: /api/signals
app.include_router(ai_classification_router, tags=["ai-classification"])  # prefix: /api/ai/classification
app.include_router(ai_signals_router, tags=["ai-signals"])  # prefix: /api/ai/signals
app.include_router(rag_router, tags=["rag"])  # prefix: /api/rag

# Response generation + brand voice + AI assignment + migration
app.include_router(response_api_router, tags=["response"])  # combined router with sub-routers


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
    # M-08 FIX: Require explicit authentication on the events endpoint.
    # Previously relied only on middleware-level tenant scoping, allowing
    # unauthenticated requests to reach the handler.
    current_user: User = Depends(get_current_user),
):
    """Fetch events missed during disconnection (BC-005).

    On reconnect, the client calls this endpoint with their last_seen
    timestamp to fetch all events that occurred while disconnected.

    BC-001: Events are scoped to the requesting tenant.
    BC-005: Event buffer stores events for 24 hours.
    M-08: Requires explicit JWT authentication.
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
