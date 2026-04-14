"""
PARWA Test Configuration — Mock external dependencies for unit tests.

Mocks modules that don't exist on disk (database, shared) and provides
test settings for app.config so no real DB/Redis/API keys are needed.

CRITICAL: Must NOT mock app.config as a standalone module type BEFORE
the real app package is discovered by Python's import system.
Instead, we set env vars and let app.config's Settings class validate
against them, then override get_settings to return a mock.
"""
import sys
import types
import os
from unittest.mock import MagicMock


# ════════════════════════════════════════════════════════════════════════
# Phase 1: Set required env vars BEFORE any app imports
# ════════════════════════════════════════════════════════════════════════
if not os.environ.get("SECRET_KEY"):
    os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only-32c"
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///test.db"
if not os.environ.get("JWT_SECRET_KEY"):
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-testing-32c"
if not os.environ.get("DATA_ENCRYPTION_KEY"):
    os.environ["DATA_ENCRYPTION_KEY"] = "test-encryption-key-for-testing-32"
if not os.environ.get("ENVIRONMENT"):
    os.environ["ENVIRONMENT"] = "test"


# ════════════════════════════════════════════════════════════════════════
# Phase 2: Mock modules that DON'T exist on disk
# ════════════════════════════════════════════════════════════════════════

_mock_db = MagicMock()

# ── database layer (doesn't exist as real package) ──────────────────
_fake_database = types.ModuleType("database")
_fake_base = types.ModuleType("database.base")
_fake_models = types.ModuleType("database.models")
_fake_jarvis_models = types.ModuleType("database.models.jarvis")
_fake_core_models = types.ModuleType("database.models.core")
_fake_onboarding_models = types.ModuleType("database.models.onboarding")

from unittest.mock import patch as _patch

_fake_base.Base = MagicMock()
_fake_base.engine = MagicMock()
_fake_base.SessionLocal = MagicMock(return_value=_mock_db)

def _fake_get_db():
    """Fake get_db generator for tests."""
    try:
        yield _mock_db
    finally:
        pass

_fake_base.get_db = _fake_get_db
_fake_base.get_tenant_db = _fake_get_db
_fake_base.init_db = MagicMock()
_fake_base.TenantSession = MagicMock()
_fake_core_models.__all__ = []
_fake_onboarding_models.__all__ = []

# User and Company are imported from database.models.core by deps.py
_MockUser = type("User", (), {"id": None, "company_id": None, "role": None, "is_active": True})
_MockCompany = type("Company", (), {"id": None})
setattr(_fake_core_models, "User", _MockUser)
setattr(_fake_core_models, "Company", _MockCompany)
setattr(_fake_core_models, "RefreshToken", MagicMock(name="RefreshToken"))
setattr(_fake_core_models, "OAuthAccount", MagicMock(name="OAuthAccount"))

for model_name in [
    "JarvisSession", "JarvisMessage", "JarvisKnowledgeUsed",
    "JarvisActionTicket", "Ticket", "TicketMessage",
    "TicketIntent", "ClassificationCorrection", "TicketPriority",
    "TicketStatusChange", "TicketMerge", "Customer",
    "CustomerChannel", "OnboardingSession",
    "AITokenBudget", "Subscription",
    "OverageCharge", "OverageRecord", "Invoice",
    "AuditEntry", "Webhook", "WebhookDelivery",
]:
    setattr(_fake_jarvis_models, model_name, MagicMock(name=model_name))

for model_name in ["DocumentChunk", "KnowledgeDocument"]:
    setattr(_fake_onboarding_models, model_name, MagicMock(name=model_name))

# ── Attribute chain support for ORM mock queries ─────────────────
class _AttrChainer:
    """Supports SQLAlchemy-style attribute chaining on mock model classes.
    e.g., EmailDeliveryEvent.created_at.desc() for order_by() calls,
    Model.severity.in_([...]) for filter expressions.
    """
    def __getattr__(self, name):
        return _AttrChainer()
    def desc(self):
        return self
    def asc(self):
        return self
    def __ge__(self, other):
        return True  # Always pass for mock filter comparisons
    def __le__(self, other):
        return True
    def __eq__(self, other):
        return True  # Filters always match in mocks
    def __ne__(self, other):
        return False
    def in_(self, *args):
        return self  # Support .in_() for filter expressions
    def isnot(self, *args):
        return self  # Support .isnot() for filter expressions
    def contains(self, *args):
        return self  # Support .contains() for JSON column queries
    def __bool__(self):
        return True

# ── database.models.email_channel and outbound_email (Week 13) ────
_fake_email_channel = types.ModuleType("database.models.email_channel")
_fake_outbound_email = types.ModuleType("database.models.outbound_email")
_fake_tickets_models = types.ModuleType("database.models.tickets")

# Customer mock with optional fields used by bounce/complaint service
_MockCustomer = type("Customer", (), {
    "id": None, "company_id": None, "email": None, "name": None,
    "email_valid": True, "email_status": None, "email_opt_out": False,
    "notification_preferences": None,
})
setattr(_fake_tickets_models, "Customer", _MockCustomer)

# Ticket/TicketMessage needed by outbound_email_service.py (imports from database.models.tickets)
_MockTicket = type("Ticket", (), {
    "id": None, "company_id": None, "customer_id": None,
    "channel": "email", "subject": None, "status": "open",
    "category": None, "priority": "medium",
    "first_response_at": None,
    "metadata_json": None,
})
_MockTicketMessage = type("TicketMessage", (), {
    "id": None, "company_id": _AttrChainer(), "ticket_id": _AttrChainer(),
    "role": "customer", "channel": "email",
    "content": None, "metadata_json": None,
    "created_at": _AttrChainer(),
})
setattr(_fake_tickets_models, "Ticket", _MockTicket)
setattr(_fake_tickets_models, "TicketMessage", _MockTicketMessage)

sys.modules.setdefault("database.models.tickets", _fake_tickets_models)

_MockEmailThread = type("EmailThread", (), {
    "id": None, "company_id": _AttrChainer(), "ticket_id": _AttrChainer(),
    "thread_message_id": None, "latest_message_id": None,
    "message_count": 0, "participants_json": "[]",
})
_MockInboundEmail = type("InboundEmail", (), {
    "id": None, "company_id": _AttrChainer(), "ticket_id": _AttrChainer(),
    "sender_email": _AttrChainer(), "sender_name": None,
    "body_html": None, "body_text": None,
    "message_id": None, "created_at": _AttrChainer(),
    "in_reply_to": None, "references": None,
    "is_auto_reply": False, "is_loop": False,
    "is_processed": False, "headers_json": None,
    "raw_size_bytes": 0, "recipient_email": None,
})
_MockOutboundEmail = type("OutboundEmail", (), {
    "id": None, "company_id": _AttrChainer(), "recipient_email": None,
    "subject": None, "delivery_status": None,
    "ticket_id": _AttrChainer(), "brevo_message_id": None,
    "__tablename__": "outbound_emails",
    "to_dict": lambda self: {},
    "bounced_at": None, "delivered_at": None, "error_message": None,
    "created_at": _AttrChainer(), "sent_at": None,
    "reply_to_message_id": None, "references": None,
})

for model_name in ["EmailThread", "InboundEmail"]:
    setattr(_fake_email_channel, model_name,
            _MockEmailThread if model_name == "EmailThread" else _MockInboundEmail)
setattr(_fake_outbound_email, "OutboundEmail", _MockOutboundEmail)

_MockEmailDeliveryEvent = type("EmailDeliveryEvent", (object,), {
    "id": None, "company_id": _AttrChainer(), "event_type": None,
    "recipient_email": None, "recipient_name": None,
    "brevo_message_id": None, "brevo_event_id": None,
    "outbound_email_id": None, "ticket_id": None,
    "reason": None, "bounce_type": None, "ooo_until": None,
    "provider": "brevo", "provider_data": None,
    "is_processed": _AttrChainer(), "processing_error": None,
    "retry_count": 0, "max_retries": 3, "next_retry_at": None,
    "event_at": None, "created_at": _AttrChainer(), "updated_at": None,
    "__tablename__": "email_delivery_events",
})

def _email_delivery_to_dict(self):
    return {"id": getattr(self, 'id', None), "event_type": getattr(self, 'event_type', None)}

_MockEmailDeliveryEvent.to_dict = _email_delivery_to_dict

def _email_delivery_init(self, **kwargs):
    for k, v in kwargs.items():
        setattr(self, k, v)

_MockEmailDeliveryEvent.__init__ = _email_delivery_init

_fake_delivery_event = types.ModuleType("database.models.email_delivery_event")
setattr(_fake_delivery_event, "EmailDeliveryEvent", _MockEmailDeliveryEvent)

sys.modules.setdefault("database.models.email_channel", _fake_email_channel)
sys.modules.setdefault("database.models.outbound_email", _fake_outbound_email)
sys.modules.setdefault("database.models.email_delivery_event", _fake_delivery_event)

# ── database.models.ooo_detection (Week 13 Day 3 — F-122) ──────────
_fake_ooo_models = types.ModuleType("database.models.ooo_detection")

def _mock_model_init(self, **kwargs):
    for k, v in kwargs.items():
        setattr(self, k, v)

def _mock_model_to_dict(self):
    return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

_MockOOODetectionRule = type("OOODetectionRule", (object,), {
    "__tablename__": "ooo_detection_rules",
    "id": None, "company_id": _AttrChainer(), "rule_type": "body",
    "pattern": None, "pattern_type": "regex",
    "classification": "ooo", "active": _AttrChainer(),
    "match_count": 0, "last_matched_at": None,
    "created_at": None, "updated_at": None,
    "__init__": _mock_model_init, "to_dict": _mock_model_to_dict,
})

_MockOOODetectionLog = type("OOODetectionLog", (object,), {
    "__tablename__": "ooo_detection_log",
    "id": None, "company_id": _AttrChainer(), "thread_id": None,
    "sender_email": None, "classification": "ooo",
    "confidence": 0.0, "detected_signals": None,
    "rule_ids_matched": None, "action_taken": "tagged",
    "related_ticket_id": None, "message_id": None,
    "created_at": _AttrChainer(),
    "__init__": _mock_model_init, "to_dict": _mock_model_to_dict,
})

_MockOOOSenderProfile = type("OOOSenderProfile", (object,), {
    "__tablename__": "ooo_sender_profiles",
    "id": None, "company_id": _AttrChainer(), "sender_email": None,
    "ooo_detected_count": 0, "last_ooo_at": None,
    "ooo_until": None, "active_ooo": False,
    "created_at": None, "updated_at": None,
    "__init__": _mock_model_init, "to_dict": _mock_model_to_dict,
})

setattr(_fake_ooo_models, "OOODetectionRule", _MockOOODetectionRule)
setattr(_fake_ooo_models, "OOODetectionLog", _MockOOODetectionLog)
setattr(_fake_ooo_models, "OOOSenderProfile", _MockOOOSenderProfile)
sys.modules.setdefault("database.models.ooo_detection", _fake_ooo_models)

# ── database.models.email_bounces (Week 13 Day 3 — F-124) ─────────
_fake_bounces_models = types.ModuleType("database.models.email_bounces")

_MockEmailBounce = type("EmailBounce", (object,), {
    "__tablename__": "email_bounces",
    "id": None, "company_id": _AttrChainer(), "customer_email": None,
    "bounce_type": "hard", "bounce_reason": None,
    "provider": "gmail", "provider_code": None,
    "event_id": None, "related_ticket_id": None,
    "email_status_before": "active", "email_status_after": "hard_bounced",
    "whitelisted": False, "whitelist_justification": None,
    "whitelisted_by": None, "whitelisted_at": None,
    "created_at": _AttrChainer(),
    "__init__": _mock_model_init, "to_dict": _mock_model_to_dict,
})

_MockCustomerEmailStatus = type("CustomerEmailStatus", (object,), {
    "__tablename__": "customer_email_status",
    "id": None, "company_id": _AttrChainer(), "customer_email": None,
    "email_status": "active", "bounce_count": 0,
    "complaint_count": 0, "last_bounce_at": None,
    "last_complaint_at": None, "suppressed_at": None,
    "whitelisted": False, "updated_at": None,
    "__init__": _mock_model_init, "to_dict": _mock_model_to_dict,
})

_MockEmailDeliverabilityAlert = type("EmailDeliverabilityAlert", (object,), {
    "__tablename__": "email_deliverability_alerts",
    "id": None, "company_id": _AttrChainer(), "alert_type": "bounce_spike",
    "severity": _AttrChainer(), "message": None,
    "metric_value": 0.0, "threshold": 0.0,
    "acknowledged": _AttrChainer(), "acknowledged_by": None,
    "created_at": _AttrChainer(),
    "__init__": _mock_model_init, "to_dict": _mock_model_to_dict,
})

setattr(_fake_bounces_models, "EmailBounce", _MockEmailBounce)
setattr(_fake_bounces_models, "CustomerEmailStatus", _MockCustomerEmailStatus)
setattr(_fake_bounces_models, "EmailDeliverabilityAlert", _MockEmailDeliverabilityAlert)
sys.modules.setdefault("database.models.email_bounces", _fake_bounces_models)

sys.modules.setdefault("database", _fake_database)
sys.modules.setdefault("database.base", _fake_base)
sys.modules.setdefault("database.models", _fake_models)
sys.modules.setdefault("database.models.jarvis", _fake_jarvis_models)
sys.modules.setdefault("database.models.core", _fake_core_models)
sys.modules.setdefault("database.models.onboarding", _fake_onboarding_models)

# ── shared layer (exists on disk but imports database.models.onboarding) ──
_FAKE_SHARED = types.ModuleType("shared")
_FAKE_KB = types.ModuleType("shared.knowledge_base")
_FAKE_KB_MANAGER = types.ModuleType("shared.knowledge_base.manager")
_FAKE_KB_RETRIEVER = types.ModuleType("shared.knowledge_base.retriever")
_FAKE_KB_VECTOR = types.ModuleType("shared.knowledge_base.vector_search")
_FAKE_KB_CHUNKER = types.ModuleType("shared.knowledge_base.chunker")
_FAKE_KB_REINDEX = types.ModuleType("shared.knowledge_base.reindexing")

# Populate vector_search mock with expected exports
_FAKE_KB_VECTOR.EMBEDDING_DIMENSION = 1536
_FAKE_KB_VECTOR.VectorStore = MagicMock()
_FAKE_KB_VECTOR.get_vector_store = MagicMock()
_FAKE_KB_VECTOR.add_documents = MagicMock()

for mod in [_FAKE_SHARED, _FAKE_KB, _FAKE_KB_MANAGER, _FAKE_KB_RETRIEVER,
            _FAKE_KB_VECTOR, _FAKE_KB_CHUNKER, _FAKE_KB_REINDEX]:
    sys.modules.setdefault(mod.__name__, mod)


# ════════════════════════════════════════════════════════════════════════
# Phase 3: Mock app submodules that need special handling
# ════════════════════════════════════════════════════════════════════════

# ── app.logger — mock so structlog doesn't need real config in tests ───
_mock_logger = MagicMock()
sys.modules.setdefault("app.logger", _mock_logger)

# ── app.core.* — ONLY mock submodules that don't exist on disk ──────
_CORE_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "core")

for mod_path, attrs in {
    "app.core.sentiment_engine": {"SentimentAnalyzer": MagicMock()},
    "app.core.graceful_escalation": {
        "GracefulEscalationManager": MagicMock(),
        "EscalationContext": MagicMock(),
        "EscalationTrigger": MagicMock(),
    },
}.items():
    mod_file = mod_path.replace(".", "/") + ".py"
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "..", mod_file)):
        mod = types.ModuleType(mod_path)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules.setdefault(mod_path, mod)

# ── app.services — some tests import from app.services.* ─────────────
# Mock specific service modules that tests reference but may not exist
# or may have cascading import issues.
_SERVICES_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "services")

for mod_path in [
    "app.services.prompt_template_service",
    "app.services.token_budget_service",
    "app.services.response_template_service",
]:
    mod_file = mod_path.replace(".", "/") + ".py"
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "..", mod_file)):
        sys.modules.setdefault(mod_path, MagicMock())

# ── app.core.email_renderer — mock for outbound email tests ────────
_core_dir = os.path.join(os.path.dirname(__file__), "..", "app", "core")
_email_renderer_path = os.path.join(_core_dir, "email_renderer.py")
if os.path.exists(_email_renderer_path):
    # Real file exists — don't mock it
    pass
else:
    _fake_email_renderer = types.ModuleType("app.core.email_renderer")
    _fake_email_renderer.render_email_template = MagicMock(
        return_value="<html><body>Mock Template</body></html>"
    )
    sys.modules.setdefault("app.core.email_renderer", _fake_email_renderer)

# ── app.core.event_emitter — mock for async event tests ─────────────
_event_emitter_path = os.path.join(_core_dir, "event_emitter.py")
if not os.path.exists(_event_emitter_path):
    _fake_event_emitter = types.ModuleType("app.core.event_emitter")
    _fake_event_emitter.emit_ticket_event = MagicMock()
    sys.modules.setdefault("app.core.event_emitter", _fake_event_emitter)


# ════════════════════════════════════════════════════════════════════════
# Phase 4: pytest fixtures
# ════════════════════════════════════════════════════════════════════════

import pytest


@pytest.fixture
def mock_settings():
    """Provide mock settings for tests."""
    from app.config import Settings
    return Settings()


@pytest.fixture
def mock_db_session():
    """Provide a mock database session."""
    return _mock_db


@pytest.fixture
def company_id():
    """Default test company ID."""
    return "test-company-123"
