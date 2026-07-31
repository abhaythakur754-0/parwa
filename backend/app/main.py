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
from app.middleware.activity_capture import ActivityCaptureMiddleware
from app.middleware.ai_entitlement import (
    AIEntitlementMiddleware,
)
from app.api.auth import router as auth_router
from app.api.mfa import router as mfa_router
from app.api.api_keys import router as api_keys_router
from app.api.client import router as client_router
from app.api.admin import router as admin_router
from app.api.admin_bootstrap import router as admin_bootstrap_router
from app.api.webhooks import router as webhook_router
from app.api.health import router as health_router
from app.api.user_details import router as user_details_router
from app.api.public import router as public_router
from app.api.pricing import router as pricing_router
from app.api.ai_engine import router as ai_engine_router
from app.api.ai_agent import router as ai_agent_router
from app.api.builder_agent import router as builder_agent_router  # Builder Agent: 4-stage agent creation pipeline
from app.api.jarvis import router as jarvis_router
from app.api.jarvis_cc import router as jarvis_cc_router
from app.api.onboarding import router as onboarding_router
from app.api.integrations import router as integrations_router
from app.api.crm_actions import router as crm_actions_router  # CRM action endpoints (called by MCP crm_server)
from app.api.ecommerce_actions import router as ecommerce_actions_router  # E-commerce action endpoints (called by MCP ecommerce_server)
from app.api.carrier_actions import router as carrier_actions_router  # Carrier action endpoints (called by MCP carrier_server)
from app.api.jarvis_integrations import router as jarvis_integrations_router  # Jarvis onboarding integration setup
from app.api.jarvis_onboarding import router as jarvis_onboarding_router  # Jarvis onboarding backend (awareness bridge)
from app.api.jarvis_routes import router as jarvis_routes_router  # Jarvis 3-Node Pipeline: SENSE→EVALUATE→NOTIFY (30+ endpoints)
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
from app.api.billing import router as billing_router  # Billing CRUD (DB-only, Razorpay is the provider)
from app.api.billing_razorpay import router as billing_razorpay_router  # Razorpay billing endpoints
from app.api.razorpay_checkout import router as razorpay_checkout_router  # Razorpay Standard Checkout
from app.api.notifications import router as notifications_router  # Notification CRUD + preferences
from app.api.customers import router as customers_router  # Customer management
from app.api.sla import router as sla_router  # SLA policy management
from app.api.channels import router as channels_router  # Channel management
from app.api.identity import router as identity_router  # Identity resolution
from app.api.cross_channel import router as cross_channel_router  # Cross-channel customer recognition (Phase 8)
from app.api.integration_cache import router as integration_cache_router  # Integration data cache (Phase 7)
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
from app.api.system_health import router as system_health_router  # System health monitoring for frontend dashboard
from app.api.approval import router as approval_router  # Approval queue + auto-approve rules
from app.api.audit import router as audit_router  # Phase 9: Audit trail & AI action logging
from app.api.escalation import router as escalation_router  # Escalation dashboard (was missing — caused 404s)
from app.api.dlq import router as dlq_router  # BC-018: DLQ ops dashboard + CRM-DLQ tile
from app.api.shadow_mode import router as shadow_mode_router  # Shadow Mode variant deployment dashboard
from app.api.debug import router as debug_router  # Debug endpoints for LLM testing

from app.api.deps import get_current_user
from database.models.core import User

# Import webhook handlers so their @register_handler decorators fire and
# populate the registry. These modules have no other import side-effects.
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

    # ── LLM Environment Bootstrap ──────────────────────────────────
    # LiteLLM requires GEMINI_API_KEY for gemini/ prefix models.
    # Render provides GOOGLE_AI_API_KEY; copy it so LiteLLM can find it.
    if not os.environ.get("GEMINI_API_KEY") and os.environ.get("GOOGLE_AI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_AI_API_KEY"]
    # Ensure LLM_PROVIDER defaults to litellm for production
    if not os.environ.get("LLM_PROVIDER"):
        os.environ["LLM_PROVIDER"] = "litellm"
    # Log LLM configuration at startup
    _lifespan_logger = get_logger("lifespan")
    _lifespan_logger.info(
        "llm_env_bootstrapped",
        provider=os.environ.get("LLM_PROVIDER", "unset"),
        has_gemini_key=bool(os.environ.get("GEMINI_API_KEY")),
        has_groq_key=bool(os.environ.get("GROQ_API_KEY")),
        has_cerebras_key=bool(os.environ.get("CEREBRAS_API_KEY")),
    )

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
        # Resolve database directory:
        # - DATABASE_DIR env var takes priority (e.g. for custom Docker layouts)
        # - Docker: /app/database (buildContext is backend/, so backend/database -> /app/database)
        # - Local: backend/database relative to this file
        _db_dir = os.environ.get("DATABASE_DIR", "")
        if not _db_dir or not pathlib.Path(_db_dir).exists():
            for candidate in [
                pathlib.Path("/app/database"),
                pathlib.Path(__file__).resolve().parents[1] / "database",
            ]:
                if candidate.exists():
                    _db_dir = str(candidate)
                    break
        if _db_dir:
            # Use sys.executable -m alembic for reliable discovery (the
            # bare `alembic` command may not be in PATH inside Docker).
            import sys as _sys
            result = subprocess.run(
                [_sys.executable, "-m", "alembic", "-c", f"{_db_dir}/alembic.ini", "upgrade", "head"],
                cwd=_db_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                logger = get_logger("lifespan")
                logger.info("alembic_migrations_completed")
            else:
                logger = get_logger("lifespan")
                logger.warning(
                    "alembic_migrations_failed",
                    returncode=result.returncode,
                    stdout=result.stdout[:500] if result.stdout else "",
                    stderr=result.stderr[:500] if result.stderr else "",
                )
        else:
            logger = get_logger("lifespan")
            logger.warning("alembic_skipped_database_dir_not_found")
    except Exception as exc:
        logger = get_logger("lifespan")
        logger.warning("alembic_migrations_error", error=str(exc))

    # ── Direct SQL fallback for trial columns ──
    # If alembic failed to run migration 032 (e.g., due to PATH issues
    # in the Docker container), add the trial columns directly via SQL.
    # This is idempotent — uses IF NOT EXISTS so it's safe to run every
    # startup. Once alembic catches up, this becomes a no-op.
    try:
        from sqlalchemy import text as _sql_text
        from database.base import SessionLocal as _SL
        _db = _SL()
        try:
            _db.execute(_sql_text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS is_trial BOOLEAN NOT NULL DEFAULT false"))
            _db.execute(_sql_text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS trial_started_at TIMESTAMP WITH TIME ZONE"))
            _db.execute(_sql_text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP WITH TIME ZONE"))
            _db.execute(_sql_text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS trial_tickets_used INTEGER NOT NULL DEFAULT 0"))
            _db.commit()
            _lg = get_logger("lifespan")
            _lg.info("trial_columns_ensured_via_sql_fallback")
        finally:
            _db.close()
    except Exception as exc:
        _lg = get_logger("lifespan")
        _lg.warning("trial_columns_sql_fallback_failed", error=str(exc))

    # ── Direct SQL fallback for knowledge_documents columns ──
    # Ensure file_path + storage_file_id columns exist (used for inline
    # content storage when S3/FileStorageService is unavailable).
    try:
        from sqlalchemy import text as _sql_text
        from database.base import SessionLocal as _SL
        _db = _SL()
        try:
            # Ensure ALL columns from the KnowledgeDocument model exist
            for col_def in [
                "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS file_path TEXT",
                "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS storage_file_id VARCHAR(36)",
                "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS category VARCHAR(100)",
                "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS chunk_count INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS error_message TEXT",
                "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS failed_at TIMESTAMP WITH TIME ZONE",
                "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
            ]:
                _db.execute(_sql_text(col_def))
            _db.commit()
            _lg.info("kb_columns_ensured_via_sql_fallback")
        finally:
            _db.close()
    except Exception as exc:
        _lg = get_logger("lifespan")
        _lg.warning("kb_columns_sql_fallback_failed", error=str(exc))

    # ── Direct SQL fallback for document_chunks table ──
    # The sync KB processing saves chunks to this table. If it doesn't exist
    # (Alembic failed), the upload endpoint crashes with 500 INTERNAL_ERROR.
    try:
        from sqlalchemy import text as _sql_text
        from database.base import SessionLocal as _SL
        _db = _SL()
        try:
            _db.execute(_sql_text("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id VARCHAR(36) PRIMARY KEY,
                    document_id VARCHAR(36),
                    company_id VARCHAR(36),
                    content TEXT NOT NULL,
                    embedding TEXT,
                    chunk_index INTEGER NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """))
            _db.execute(_sql_text(
                "CREATE INDEX IF NOT EXISTS ix_document_chunks_document_id ON document_chunks (document_id)"
            ))
            _db.execute(_sql_text(
                "CREATE INDEX IF NOT EXISTS ix_document_chunks_company_id ON document_chunks (company_id)"
            ))
            _db.commit()
            _lg.info("document_chunks_table_ensured_via_sql_fallback")
        finally:
            _db.close()
    except Exception as exc:
        _lg = get_logger("lifespan")
        _lg.warning("document_chunks_table_sql_fallback_failed", error=str(exc))

    # ── Direct SQL fallback for FlexPay tables ──
    # If alembic failed (connection error in subprocess), create the
    # flexpay_plans + flexpay_installments tables directly via SQL.
    # Also adds razorpay_token column (added after initial migration).
    try:
        from sqlalchemy import text as _sql_text
        from database.base import SessionLocal as _SL
        _db = _SL()
        try:
            # Create flexpay_plans table if not exists
            _db.execute(_sql_text("""
                CREATE TABLE IF NOT EXISTS flexpay_plans (
                    id VARCHAR(36) PRIMARY KEY,
                    company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    variant_tier VARCHAR(50) NOT NULL,
                    total_amount NUMERIC(10,2) NOT NULL,
                    installment_amount NUMERIC(10,2) NOT NULL,
                    extra_installment_amount NUMERIC(10,2),
                    total_installments INTEGER NOT NULL,
                    completed_installments INTEGER DEFAULT 0 NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    current_period_start TIMESTAMP,
                    current_period_end TIMESTAMP,
                    razorpay_customer_id VARCHAR(255),
                    razorpay_order_id VARCHAR(255),
                    razorpay_token VARCHAR(255),
                    consecutive_failures INTEGER DEFAULT 0 NOT NULL,
                    last_failure_reason TEXT,
                    last_failure_at TIMESTAMP,
                    max_retries INTEGER DEFAULT 3 NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    completed_at TIMESTAMP,
                    cancelled_at TIMESTAMP,
                    notes TEXT
                )
            """))
            _db.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_flexpay_plans_company_id ON flexpay_plans (company_id)"))
            _db.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_flexpay_plans_status ON flexpay_plans (status)"))

            # Create flexpay_installments table if not exists
            _db.execute(_sql_text("""
                CREATE TABLE IF NOT EXISTS flexpay_installments (
                    id VARCHAR(36) PRIMARY KEY,
                    plan_id VARCHAR(36) NOT NULL REFERENCES flexpay_plans(id) ON DELETE CASCADE,
                    company_id VARCHAR(36) NOT NULL,
                    installment_number INTEGER NOT NULL,
                    amount NUMERIC(10,2) NOT NULL,
                    is_extra BOOLEAN DEFAULT false,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    razorpay_payment_id VARCHAR(255),
                    razorpay_order_id VARCHAR(255),
                    razorpay_status VARCHAR(50),
                    scheduled_at TIMESTAMP,
                    processed_at TIMESTAMP,
                    failure_reason TEXT,
                    retry_count INTEGER DEFAULT 0,
                    retry_after TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))
            _db.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_flexpay_installments_plan_id ON flexpay_installments (plan_id)"))
            _db.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_flexpay_installments_status ON flexpay_installments (status)"))

            # Add razorpay_token column to flexpay_plans if not exists
            _db.execute(_sql_text("ALTER TABLE flexpay_plans ADD COLUMN IF NOT EXISTS razorpay_token VARCHAR(255)"))

            _db.commit()
            _lg = get_logger("lifespan")
            _lg.info("flexpay_tables_ensured_via_sql_fallback")
        finally:
            _db.close()
    except Exception as exc:
        _lg = get_logger("lifespan")
        _lg.warning("flexpay_tables_sql_fallback_failed", error=str(exc))

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

    # Phase 4: Pre-build unified 8-node PARWA pipeline at startup
    try:
        from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
        _parwa_graph = build_parwa_pipeline()
        _compiled = _parwa_graph.compile()
        # Store graph on app.state for API endpoints to use
        app.state.parwa_graph = _compiled
        logger = get_logger("lifespan")
        logger.info(
            "parwa_pipeline_v2_initialized",
            node_count=8,
            pipeline_type="unified_8node",
        )
    except Exception as exc:
        logger = get_logger("lifespan")
        logger.warning(
            "parwa_pipeline_init_failed_fail_open",
            error=str(exc),
            message="PARWA pipeline will be built on first request",
        )
        app.state.parwa_graph = None

    # Phase 2: Initialize Rust parwa_core bridge (Tier-1 hot-path replacement)
    try:
        from app.core.parwa_core_bridge import (
            is_parwa_core_available,
            get_parwa_rate_limiter,
            get_parwa_circuit_breaker,
            get_parwa_pii_redactor,
            get_bridge_diagnostics,
        )
        rust_available = is_parwa_core_available()
        if rust_available:
            # Pre-initialize singletons so they're warm before first request
            get_parwa_rate_limiter()
            get_parwa_circuit_breaker()
            get_parwa_pii_redactor()
            diagnostics = get_bridge_diagnostics()
            logger = get_logger("lifespan")
            logger.info(
                "parwa_core_initialized",
                rust_available=True,
                diagnostics=diagnostics,
            )
        else:
            logger = get_logger("lifespan")
            logger.warning(
                "parwa_core_not_available_fallback_to_python",
                rust_available=False,
            )
    except Exception as exc:
        logger = get_logger("lifespan")
        logger.warning(
            "parwa_core_init_failed_fallback_to_python",
            error=str(exc),
        )

    logger = get_logger("lifespan")
    logger.info(
        "parwa_startup",
        environment=settings.ENVIRONMENT,
        version=settings.APP_VERSION,
    )

    # ── Gap 6: Auto-resume pending escalations every 5 minutes ──
    # Celery beat is configured but the worker isn't running on Render free
    # tier. This lightweight in-process loop ensures escalations with human
    # guidance get re-processed automatically without requiring a human to
    # click "Resume" in the dashboard. Runs as a fire-and-forget background
    # task; all errors are caught and logged so the loop never dies.
    import asyncio

    async def _auto_resume_escalations_loop():
        # Wait 60s after startup before first run (let other services init)
        await asyncio.sleep(60)
        while True:
            try:
                from database.base import SessionLocal
                from database.models.core import Company
                from app.core.escalation_vault.resume_pipeline import auto_resume_pending

                db = SessionLocal()
                try:
                    companies = db.query(Company).filter(
                        Company.subscription_status == "active",
                    ).all()
                    total_resumed = 0
                    for company in companies:
                        try:
                            result = await auto_resume_pending(str(company.id))
                            resumed = result.get("resolved", 0)
                            if resumed > 0:
                                total_resumed += resumed
                                logger.info(
                                    "auto_resume_loop: company=%s resumed=%d",
                                    str(company.id)[:8], resumed,
                                )
                        except Exception as company_exc:
                            logger.warning(
                                "auto_resume_company_failed company=%s err=%s",
                                str(company.id)[:8], str(company_exc)[:200],
                            )
                    if total_resumed > 0:
                        logger.info(
                            "auto_resume_loop_complete: total_resumed=%d companies=%d",
                            total_resumed, len(companies),
                        )
                finally:
                    db.close()
            except Exception as loop_exc:
                logger.warning(
                    "auto_resume_loop_error err=%s",
                    str(loop_exc)[:200],
                )
            # Sleep 5 minutes before next run
            await asyncio.sleep(300)

    asyncio.create_task(_auto_resume_escalations_loop())
    logger.info("auto_resume_escalations_loop_started (runs every 5 min)")

    # ── Start the DB-backed pipeline worker pool ──────────────────
    # 7 persistent workers poll the database for tickets with status='open'
    # and process them. This starts on server startup so tickets are picked
    # up immediately, even after a server restart.
    try:
        from app.services.pipeline_dispatcher import _start_pipeline_workers
        _start_pipeline_workers()
        logger.info("pipeline_worker_pool_started_on_startup")
    except Exception as exc:
        logger.warning("pipeline_worker_pool_start_failed: %s", str(exc)[:200])

    # ── Stuck-ticket recovery loop ─────────────────────────────────
    # If a ticket's background dispatch thread fails to start (crash, OOM,
    # server restart), the ticket stays "open" forever with no AI response.
    # This loop checks every 3 minutes for tickets stuck in "open" status
    # for more than 15 minutes and re-dispatches them.
    #
    # IMPORTANT: The cutoff is 15 minutes (not 5) because with 7 concurrent
    # pipelines, a queue of 25 tickets takes ~4 minutes to drain. A 5-min
    # cutoff would re-dispatch tickets that are just waiting in the queue,
    # creating duplicate threads and causing OOM crashes.
    async def _stuck_ticket_recovery_loop():
        await asyncio.sleep(180)  # Wait 3 min after startup
        while True:
            try:
                from database.base import SessionLocal
                from database.models.tickets import Ticket, TicketMessage
                from datetime import datetime, timezone, timedelta
                from app.services.pipeline_dispatcher import dispatch_pipeline_for_ticket

                db = SessionLocal()
                try:
                    # Re-dispatch tickets stuck in 'open' for >15 min
                    # (truly orphaned — never picked up by workers)
                    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
                    stuck_tickets = db.query(Ticket).filter(
                        Ticket.status == "open",
                        Ticket.created_at < cutoff,
                    ).limit(5).all()

                    # Also re-dispatch tickets stuck in 'processing' for >5 min
                    # (worker crashed mid-pipeline — reset to open so workers
                    # pick them up again)
                    processing_cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
                    stuck_processing = db.query(Ticket).filter(
                        Ticket.status == "processing",
                        Ticket.updated_at < processing_cutoff,
                    ).limit(5).all()

                    all_stuck = stuck_tickets + stuck_processing

                    if all_stuck:
                        logger.info(
                            "stuck_ticket_recovery: %d open + %d processing stuck",
                            len(stuck_tickets), len(stuck_processing),
                        )

                    for ticket in all_stuck:
                        try:
                            # If ticket is stuck in 'processing', reset to 'open'
                            # so the DB-backed workers pick it up again
                            if ticket.status == "processing":
                                ticket.status = "open"
                                db.commit()
                                logger.info(
                                    "stuck_ticket_recovery: reset processing→open ticket %s",
                                    str(ticket.id)[:8],
                                )
                                continue

                            # For 'open' tickets: check if AI message exists
                            has_ai = db.query(TicketMessage).filter(
                                TicketMessage.ticket_id == str(ticket.id),
                                TicketMessage.role == "ai",
                            ).first()

                            if has_ai:
                                # Pipeline ran but didn't update status — mark as awaiting_human
                                ticket.status = "awaiting_human"
                                ticket.awaiting_human = True
                                db.commit()
                                logger.info(
                                    "stuck_ticket_recovery: ticket %s had AI msg, marking awaiting_human",
                                    str(ticket.id)[:8],
                                )
                            else:
                                # No AI message — pipeline never ran. Re-dispatch.
                                logger.info(
                                    "stuck_ticket_recovery: re-dispatching ticket %s",
                                    str(ticket.id)[:8],
                                )
                                dispatch_pipeline_for_ticket(
                                    ticket_id=str(ticket.id),
                                    company_id=ticket.company_id,
                                    priority=ticket.priority or "medium",
                                    channel="email",
                                    sync=True,
                                )
                        except Exception as ticket_exc:
                            logger.warning(
                                "stuck_ticket_recovery: failed for ticket %s: %s",
                                str(ticket.id)[:8], str(ticket_exc)[:150],
                            )
                finally:
                    db.close()
            except Exception as recovery_exc:
                logger.warning(
                    "stuck_ticket_recovery_loop_error: %s",
                    str(recovery_exc)[:200],
                )
            # Check every 3 minutes (was 2 — increased to reduce thread pile-up)
            await asyncio.sleep(180)

    asyncio.create_task(_stuck_ticket_recovery_loop())
    logger.info("stuck_ticket_recovery_loop_started (checks every 3 min, cutoff 15 min)")

    # ── Stuck KB document recovery loop ────────────────────────────
    # On Render free tier, the Celery worker may be sleeping or crashed.
    # When a user uploads a KB document, Celery's .delay() returns success
    # even if no worker is listening, so the document stays "processing"
    # forever. This loop checks every 2 minutes for KB documents stuck in
    # "pending" or "processing" for more than 2 minutes and re-processes
    # them synchronously (chunk + embed inline).
    async def _stuck_kb_recovery_loop():
        await asyncio.sleep(60)  # Wait 1 min after startup
        while True:
            try:
                import concurrent.futures

                def _recover_stuck_docs():
                    from database.base import SessionLocal
                    from database.models.onboarding import KnowledgeDocument, DocumentChunk
                    from app.shared.knowledge_base.chunker import chunk_text
                    from datetime import datetime, timezone, timedelta
                    import uuid

                    db = SessionLocal()
                    try:
                        cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
                        stuck = db.query(KnowledgeDocument).filter(
                            KnowledgeDocument.status.in_(["pending", "processing"]),
                        ).all()
                        recovered = 0
                        failed = 0
                        for doc in stuck:
                            updated = doc.updated_at or doc.created_at
                            if updated.tzinfo is None:
                                updated = updated.replace(tzinfo=timezone.utc)
                            if updated < cutoff:
                                logger.info(
                                    "stuck_kb_recovery: reprocessing doc %s (status=%s, age=%ss)",
                                    doc.id, doc.status, int((datetime.now(timezone.utc) - updated).total_seconds()),
                                )
                                try:
                                    # ── INLINE chunking (NO Celery/Redis dependency) ──
                                    # The previous approach used process_knowledge_document.apply()
                                    # which triggered a Celery broker connection to Redis. On Render,
                                    # the rediss:// URL is missing ssl_cert_reqs, so ALL recovery
                                    # attempts failed. This bypasses Celery entirely.
                                    content = ""
                                    file_path_val = getattr(doc, 'file_path', None) or ""
                                    if file_path_val.startswith("inline:"):
                                        content = file_path_val[len("inline:"):]
                                    else:
                                        logger.warning(
                                            "stuck_kb_recovery: doc %s has no inline content (file_path=%s)",
                                            doc.id, str(file_path_val)[:80],
                                        )
                                        # Mark as failed — can't recover without content
                                        doc.status = "failed"
                                        doc.error_message = "No content available (created before inline storage fix)"
                                        doc.failed_at = datetime.now(timezone.utc)
                                        db.commit()
                                        failed += 1
                                        continue

                                    if content and len(content) > 10:
                                        chunks = chunk_text(content, chunk_size=500, overlap=50)
                                        # Delete any existing chunks for this doc (idempotent)
                                        db.query(DocumentChunk).filter(
                                            DocumentChunk.document_id == str(doc.id)
                                        ).delete()
                                        # Save chunks without embeddings (instant)
                                        for i, chunk_content in enumerate(chunks):
                                            chunk = DocumentChunk(
                                                id=str(uuid.uuid4()),
                                                document_id=str(doc.id),
                                                company_id=str(doc.company_id),
                                                content=chunk_content,
                                                chunk_index=i,
                                                embedding=None,
                                            )
                                            db.add(chunk)
                                        doc.status = "completed"
                                        doc.chunk_count = len(chunks)
                                        doc.error_message = None
                                        doc.updated_at = datetime.now(timezone.utc)
                                        db.commit()
                                        recovered += 1
                                        logger.info(
                                            "stuck_kb_recovery: doc %s completed with %d chunks",
                                            doc.id, len(chunks),
                                        )
                                    else:
                                        doc.status = "failed"
                                        doc.error_message = "Content too short to process"
                                        db.commit()
                                        failed += 1
                                except Exception as inner:
                                    logger.warning(
                                        "stuck_kb_recovery: failed for doc %s: %s",
                                        doc.id, str(inner)[:200],
                                    )
                                    failed += 1
                        if recovered > 0 or failed > 0:
                            logger.info(
                                "stuck_kb_recovery: recovered=%d failed=%d", recovered, failed,
                            )
                    finally:
                        db.close()

                # Run the blocking recovery in a thread pool so we don't
                # block the async event loop.
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    await loop.run_in_executor(pool, _recover_stuck_docs)
            except Exception as exc:
                logger.warning("stuck_kb_recovery_loop_error: %s", str(exc)[:200])

            await asyncio.sleep(90)  # Check every 90s

    asyncio.create_task(_stuck_kb_recovery_loop())
    logger.info("stuck_kb_recovery_loop_started (checks every 90s, cutoff 60s)")

    # ── FlexPay daily installment scheduler ─────────────────────────
    # Runs every hour to find due installments and charge the customer's
    # stored card token via Razorpay. This is how days 2-30 of the
    # $100/day FlexPay plan get charged automatically.
    async def _flexpay_scheduler_loop():
        while True:
            try:
                from app.services.flexpay_scheduler import FlexPayScheduler
                scheduler = FlexPayScheduler()
                result = await scheduler.run_once()
                if result.get("processed", 0) > 0:
                    logger.info(
                        "flexpay_scheduler_loop: processed=%d successes=%d failures=%d",
                        result.get("processed", 0),
                        result.get("successes", 0),
                        result.get("failures", 0),
                    )
            except Exception as flexpay_exc:
                logger.warning(
                    "flexpay_scheduler_loop_error: %s",
                    str(flexpay_exc)[:200],
                )
            # Check every hour (installments are scheduled daily, so
            # hourly check ensures we don't miss any)
            await asyncio.sleep(3600)

    asyncio.create_task(_flexpay_scheduler_loop())
    logger.info("flexpay_scheduler_loop_started (runs every 1 hour)")

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

# 3. Activity capture — records non-agentic actions for Jarvis awareness
app.add_middleware(ActivityCaptureMiddleware)

# 4. AI Entitlement — Week 8: feature gating for /api/ai/ paths
#    CRITICAL ORDERING: In Starlette, middleware added LATER runs EARLIER
#    in the request cycle. AIEntitlementMiddleware reads request.state.company_id
#    which is set by TenantMiddleware. So TenantMiddleware must run FIRST
#    (be added AFTER AIEntitlementMiddleware). This is why we add
#    AIEntitlementMiddleware here at #4, BEFORE TenantMiddleware at #5.
app.add_middleware(AIEntitlementMiddleware)

# 5. Tenant middleware — BC-001 multi-tenant isolation
#    Runs AFTER AIEntitlementMiddleware in the request cycle (because it's
#    added later), so request.state.company_id IS set when AI entitlement
#    checks it.
app.add_middleware(TenantMiddleware)

# 6. Rate limit middleware — BC-011/BC-012 rate limiting
app.add_middleware(RateLimitMiddleware)

# 7. API Key auth — BC-011
app.add_middleware(APIKeyAuthMiddleware)

# 8. Security headers — BC-011/BC-012
app.add_middleware(SecurityHeadersMiddleware)

# 9. CSRF protection — Origin/Referer validation + double-submit cookie
app.add_middleware(CSRFSecurityMiddleware)

# 10. IP allowlist — BC-012 (disabled by default)
# Set IP_ALLOWLIST_ENABLED=true to activate
app.add_middleware(IPAllowlistMiddleware)

# 11. CORS middleware (frontend cross-origin access)
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
    # Allow Vercel preview deployments
    # e.g. chat1-fixes-parwa.vercel.app, parwa-git-main-abhaythakur754-0.vercel.app
    allow_origin_regex=r"https://[a-z0-9\-]+\.(vercel\.app)|https://[a-z0-9\-]+--[a-z0-9\-]+\.vercel\.app",
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
app.include_router(admin_bootstrap_router)
app.include_router(webhook_router)
app.include_router(user_details_router)
app.include_router(public_router)  # Public API for landing page (no auth required)
app.include_router(pricing_router)  # Pricing API (no auth required)
app.include_router(ai_engine_router)  # Week 8: AI Engine endpoints
app.include_router(ai_agent_router)  # SG-21/SG-22: AI agent assignments
app.include_router(builder_agent_router)  # Builder Agent: 4-stage agent creation + custom categories
app.include_router(jarvis_router)  # Week 6: Jarvis onboarding chat
app.include_router(jarvis_cc_router)  # Phase 2+: Jarvis Customer Care (awareness + commands)
app.include_router(onboarding_router)  # Week 6: Onboarding wizard (F-028 to F-035)
app.include_router(integrations_router)  # Week 6: Integration management (F-030/F-031)
app.include_router(crm_actions_router)  # CRM action endpoints (called by MCP crm_server)
app.include_router(ecommerce_actions_router)  # E-commerce action endpoints (called by MCP ecommerce_server)
app.include_router(carrier_actions_router)  # Carrier action endpoints (called by MCP carrier_server)
app.include_router(jarvis_integrations_router)  # Jarvis onboarding integration setup flow
app.include_router(jarvis_onboarding_router)  # Jarvis onboarding backend (awareness bridge to Activity Store)
app.include_router(jarvis_routes_router, tags=["jarvis-pipeline"])  # Jarvis 3-Node Pipeline: SENSE→EVALUATE→NOTIFY (quality, SLA, approvals, copilot, Wave 8)
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

# Billing (Razorpay is the provider; Paddle was removed)
app.include_router(billing_router, tags=["billing"])  # prefix: /api/billing
app.include_router(billing_razorpay_router)  # Razorpay billing (/api/billing/razorpay/*)
app.include_router(razorpay_checkout_router)  # Razorpay Standard Checkout (/api/razorpay/*)

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

# Phase 7: Integration data caching
app.include_router(integration_cache_router, prefix="/api/v1", tags=["integration-cache"])  # prefix: /integration-cache -> /api/v1/integration-cache

# Phase 8: Cross-channel customer recognition
app.include_router(cross_channel_router, prefix="/api/v1", tags=["cross-channel"])  # prefix: /cross-channel -> /api/v1/cross-channel

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

# System health monitoring (consumed by frontend system-health-store)
app.include_router(system_health_router, tags=["system-health"])  # prefix: /api/system/health

# Approval queue + auto-approve rules (human-in-the-loop)
app.include_router(approval_router, tags=["approvals"])  # prefix: /api/approvals (defined in router)

# Phase 9: Audit trail & AI action logging
app.include_router(audit_router, tags=["audit"])  # prefix: /api/v1/audit (defined in router)

# Escalation vault (dashboard — was missing from main.py, caused 404s on dashboard load)
app.include_router(escalation_router, tags=["escalation"])  # prefix: /api/escalations (plural — matches frontend)

# DLQ ops dashboard + CRM-DLQ tile (BC-018). Prefix: /api/dlq
# Used by frontend /dashboard/crm-dlq page + main dashboard CRM DLQ count tile.
app.include_router(dlq_router, tags=["dlq"])
app.include_router(shadow_mode_router, tags=["shadow-mode"])  # prefix: /api/shadow-mode
app.include_router(debug_router, prefix="/api/v1", tags=["debug"])  # prefix: /api/v1/debug


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
