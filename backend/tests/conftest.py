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

# ── database.models.email_channel and outbound_email (Week 13) ────
_fake_email_channel = types.ModuleType("database.models.email_channel")
_fake_outbound_email = types.ModuleType("database.models.outbound_email")

_MockEmailThread = type("EmailThread", (), {
    "id": None, "company_id": None, "ticket_id": None,
    "thread_message_id": None, "latest_message_id": None,
    "message_count": 0, "participants_json": "[]",
})
_MockInboundEmail = type("InboundEmail", (), {
    "id": None, "company_id": None, "ticket_id": None,
    "sender_email": None, "sender_name": None,
    "body_html": None, "body_text": None,
    "message_id": None, "created_at": None,
})
_MockOutboundEmail = type("OutboundEmail", (), {
    "id": None, "company_id": None, "recipient_email": None,
    "subject": None, "delivery_status": None,
    "ticket_id": None, "brevo_message_id": None,
    "__tablename__": "outbound_emails",
    "to_dict": lambda self: {},
})

for model_name in ["EmailThread", "InboundEmail"]:
    setattr(_fake_email_channel, model_name,
            _MockEmailThread if model_name == "EmailThread" else _MockInboundEmail)
setattr(_fake_outbound_email, "OutboundEmail", _MockOutboundEmail)

sys.modules.setdefault("database.models.email_channel", _fake_email_channel)
sys.modules.setdefault("database.models.outbound_email", _fake_outbound_email)

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
