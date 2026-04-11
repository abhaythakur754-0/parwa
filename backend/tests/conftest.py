"""
PARWA Test Configuration — Mock database layer for unit tests.
Only mocks modules that don't exist on disk (database, app.config, app.core.*, app.logger).
"""
import sys
import types
from unittest.mock import MagicMock


_mock_db = MagicMock()

# ── database layer (doesn't exist as real package) ──────────────────
_fake_database = types.ModuleType("database")
_fake_base = types.ModuleType("database.base")
_fake_models = types.ModuleType("database.models")
_fake_jarvis_models = types.ModuleType("database.models.jarvis")
_fake_core_models = types.ModuleType("database.models.core")

_fake_base.Base = MagicMock()
_fake_base.engine = MagicMock()
_fake_base.SessionLocal = MagicMock(return_value=_mock_db)
_fake_core_models.__all__ = []

for model_name in [
    "JarvisSession", "JarvisMessage", "JarvisKnowledgeUsed",
    "JarvisActionTicket", "Ticket", "TicketMessage",
    "TicketIntent", "ClassificationCorrection", "TicketPriority",
    "TicketStatusChange", "TicketMerge", "Customer",
    "CustomerChannel", "OnboardingSession", "Company",
    "User", "RefreshToken", "AITokenBudget", "Subscription",
    "OverageCharge", "OverageRecord", "Invoice",
    "AuditEntry", "Webhook", "WebhookDelivery",
]:
    setattr(_fake_jarvis_models, model_name, MagicMock(name=model_name))

sys.modules.setdefault("database", _fake_database)
sys.modules.setdefault("database.base", _fake_base)
sys.modules.setdefault("database.models", _fake_models)
sys.modules.setdefault("database.models.jarvis", _fake_jarvis_models)
sys.modules.setdefault("database.models.core", _fake_core_models)

# ── app.config (mock settings so no real DB URL needed) ────────────
_fake_config = types.ModuleType("app.config")
_mock_settings = MagicMock()
_mock_settings.CEREBRAS_API_KEY = None
_mock_settings.GROQ_API_KEY = None
_mock_settings.GOOGLE_AI_API_KEY = None
_fake_config.get_settings = MagicMock(return_value=_mock_settings)
sys.modules.setdefault("app.config", _fake_config)

# ── app.core.* (sentiment, escalation, technique_router) ───────────
for mod_path, attrs in {
    "app.core.sentiment_engine": {"SentimentAnalyzer": MagicMock()},
    "app.core.graceful_escalation": {
        "GracefulEscalationManager": MagicMock(),
        "EscalationContext": MagicMock(),
        "EscalationTrigger": MagicMock(),
    },
    "app.core.technique_router": {
        "TechniqueID": type("TechniqueID", (), {}),
        "TechniqueTier": type("TechniqueTier", (), {}),
    },
}.items():
    mod = types.ModuleType(mod_path)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules.setdefault(mod_path, mod)

sys.modules.setdefault("app.core", types.ModuleType("app.core"))
sys.modules.setdefault("app.logger", MagicMock(name="app.logger"))
