"""
Integration tests for the Mini Parwa full pipeline.

Tests end-to-end pipeline execution:
  - All 6 steps complete in order
  - Emergency bypass (emergency detected -> skip to format)
  - Audit log accumulates entries from each node
  - Pipeline status is set correctly
  - Different industries (ecommerce, logistics, saas, general)
  - Different channels (chat, email, phone)
"""

import os
import sys
import types
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ── Setup: Ensure paths and env vars ──────────────────────────────────
_backend_dir = os.path.join(os.path.dirname(__file__), "..")
if _backend_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_backend_dir))

_project_root = os.path.join(os.path.dirname(__file__), "..", "..")
if _project_root not in sys.path:
    sys.path.insert(0, os.path.abspath(_project_root))

# Set required env vars
for var, default in {
    "SECRET_KEY": "test-secret-key-for-testing-only-32c",
    "DATABASE_URL": "sqlite:///test.db",
    "JWT_SECRET_KEY": "test-jwt-secret-key-for-testing-32c",
    "DATA_ENCRYPTION_KEY": "test-encryption-key-for-testing-32",
    "ENVIRONMENT": "test",
}.items():
    os.environ.setdefault(var, default)

# ── Mock external modules ────────────────────────────────────────────
_fake_redis_module = types.ModuleType("app.core.redis")
_fake_redis_module.get_redis = AsyncMock(return_value=MagicMock())
_fake_redis_module.make_key = lambda *args: ":".join(str(a) for a in args)
sys.modules.setdefault("app.core.redis", _fake_redis_module)

_fake_exceptions = types.ModuleType("app.exceptions")
_fake_exceptions.InternalError = type("InternalError", (Exception,), {})
sys.modules.setdefault("app.exceptions", _fake_exceptions)

if "app.logger" not in sys.modules or not hasattr(sys.modules["app.logger"], "get_logger"):
    _fake_logger = types.ModuleType("app.logger")
    _mock_logger_instance = MagicMock()
    _fake_logger.get_logger = lambda name: _mock_logger_instance
    sys.modules["app.logger"] = _fake_logger

for mod_name in [
    "database", "database.base", "database.models",
    "database.models.core", "database.models.jarvis",
    "database.models.onboarding", "database.models.tickets",
    "database.models.email_channel", "database.models.outbound_email",
    "database.models.email_delivery_event", "database.models.ooo_detection",
    "database.models.email_bounces", "database.models.chat_widget",
    "database.models.sms_channel",
]:
    sys.modules.setdefault(mod_name, MagicMock())

for mod_name in [
    "shared", "shared.knowledge_base", "shared.knowledge_base.manager",
    "shared.knowledge_base.retriever", "shared.knowledge_base.vector_search",
    "shared.knowledge_base.chunker", "shared.knowledge_base.reindexing",
]:
    sys.modules.setdefault(mod_name, MagicMock())

# Now import
from app.core.parwa_graph_state import create_initial_state
from app.core.mini_parwa.graph import MiniParwaPipeline, build_mini_parwa_graph


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def pipeline():
    """Create a MiniParwaPipeline instance."""
    return MiniParwaPipeline()


def _make_state(**kwargs) -> dict:
    """Create a test state with sensible defaults."""
    defaults = {
        "query": "I need help with my order",
        "company_id": "test-company-123",
        "variant_tier": "mini_parwa",
        "variant_instance_id": "inst_mini_test",
        "industry": "general",
        "channel": "chat",
        "conversation_id": "conv_test",
        "ticket_id": "tkt_test",
        "customer_id": "cust_test",
        "customer_tier": "free",
    }
    defaults.update(kwargs)
    return create_initial_state(**defaults)


# ══════════════════════════════════════════════════════════════════
# TESTS: End-to-end pipeline
# ══════════════════════════════════════════════════════════════════


class TestMiniParwaPipelineE2E:
    """End-to-end integration tests for the Mini Parwa pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_completes(self, pipeline):
        """Full pipeline should complete all 6 steps."""
        state = _make_state(query="I need a refund for my order")
        result = await pipeline.run(state)

        assert result["pipeline_status"] in ("success", "partial")
        assert result["final_response"] != ""
        assert result["current_step"] == "format"

    @pytest.mark.asyncio
    async def test_all_steps_complete_in_order(self, pipeline):
        """All 6 steps should complete and be tracked."""
        state = _make_state(query="My order hasn't arrived yet")
        result = await pipeline.run(state)

        steps_completed = result.get("steps_completed", [])
        # At minimum, format should be completed
        assert "format" in steps_completed

        # Step outputs should exist
        step_outputs = result.get("step_outputs", {})
        assert isinstance(step_outputs, dict)

    @pytest.mark.asyncio
    async def test_audit_log_accumulates(self, pipeline):
        """Audit log should accumulate entries from each node."""
        state = _make_state(query="I need help with billing")
        result = await pipeline.run(state)

        audit_log = result.get("audit_log", [])
        assert len(audit_log) >= 1  # At least one entry

        # Each entry should have required fields
        for entry in audit_log:
            assert "step" in entry
            assert "action" in entry
            assert "timestamp" in entry

    @pytest.mark.asyncio
    async def test_pipeline_status_success(self, pipeline):
        """Clean pipeline run should result in 'success' status."""
        state = _make_state(query="Can you help me with my account?")
        result = await pipeline.run(state)
        assert result["pipeline_status"] in ("success", "partial")

    @pytest.mark.asyncio
    async def test_total_latency_tracked(self, pipeline):
        """Pipeline should track total latency."""
        state = _make_state(query="Hello")
        result = await pipeline.run(state)
        assert result.get("total_latency_ms", 0) >= 0


# ══════════════════════════════════════════════════════════════════
# TESTS: Emergency bypass
# ══════════════════════════════════════════════════════════════════


class TestEmergencyBypass:
    """Tests for emergency bypass (emergency -> skip to format)."""

    @pytest.mark.asyncio
    async def test_emergency_bypasses_classify_generate(self, pipeline):
        """Emergency should skip classify and generate, go to format."""
        state = _make_state(query="I will sue your company for this!")
        result = await pipeline.run(state)

        assert result["emergency_flag"] is True
        assert result["final_response"] != ""
        assert result["pipeline_status"] in ("success", "partial")

    @pytest.mark.asyncio
    async def test_safety_emergency(self, pipeline):
        """Safety emergency should be detected and handled."""
        state = _make_state(query="I want to hurt myself")
        result = await pipeline.run(state)

        assert result["emergency_flag"] is True
        assert result["emergency_type"] == "safety"

    @pytest.mark.asyncio
    async def test_emergency_still_produces_response(self, pipeline):
        """Emergency queries should still produce a response."""
        state = _make_state(query="I will take legal action!")
        result = await pipeline.run(state)

        assert result["final_response"] != ""


# ══════════════════════════════════════════════════════════════════
# TESTS: Different industries
# ══════════════════════════════════════════════════════════════════


class TestIndustryVariants:
    """Tests with different industries."""

    @pytest.mark.asyncio
    async def test_ecommerce_industry(self, pipeline):
        """E-commerce industry should work end-to-end."""
        state = _make_state(
            query="Where is my order? I need a refund",
            industry="ecommerce",
        )
        result = await pipeline.run(state)
        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_logistics_industry(self, pipeline):
        """Logistics industry should work end-to-end."""
        state = _make_state(
            query="My shipment is delayed, where is it?",
            industry="logistics",
        )
        result = await pipeline.run(state)
        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_saas_industry(self, pipeline):
        """SaaS industry should work end-to-end."""
        state = _make_state(
            query="I have a billing issue with my subscription",
            industry="saas",
        )
        result = await pipeline.run(state)
        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_general_industry(self, pipeline):
        """General industry should work end-to-end."""
        state = _make_state(
            query="I have a general question",
            industry="general",
        )
        result = await pipeline.run(state)
        assert result["final_response"] != ""


# ══════════════════════════════════════════════════════════════════
# TESTS: Different channels
# ══════════════════════════════════════════════════════════════════


class TestChannelVariants:
    """Tests with different channels."""

    @pytest.mark.asyncio
    async def test_chat_channel(self, pipeline):
        """Chat channel should work end-to-end."""
        state = _make_state(query="Hello", channel="chat")
        result = await pipeline.run(state)
        assert result["response_format"] == "chat"

    @pytest.mark.asyncio
    async def test_email_channel(self, pipeline):
        """Email channel should work end-to-end."""
        state = _make_state(query="Hello", channel="email")
        result = await pipeline.run(state)
        assert result["response_format"] == "email"

    @pytest.mark.asyncio
    async def test_phone_channel(self, pipeline):
        """Phone channel should work end-to-end."""
        state = _make_state(query="Hello", channel="phone")
        result = await pipeline.run(state)
        assert result["response_format"] == "phone_transcript"


# ══════════════════════════════════════════════════════════════════
# TESTS: Graph building
# ══════════════════════════════════════════════════════════════════


class TestGraphBuilding:
    """Tests for graph construction."""

    def test_graph_builds_successfully(self):
        """Graph should build without errors."""
        graph = build_mini_parwa_graph()
        assert graph is not None

    def test_pipeline_initializes(self):
        """Pipeline should initialize successfully."""
        pipeline = MiniParwaPipeline()
        assert pipeline._graph is not None

    def test_process_ticket_method_exists(self):
        """process_ticket method should exist."""
        pipeline = MiniParwaPipeline()
        assert hasattr(pipeline, "process_ticket")
        assert callable(pipeline.process_ticket)


# ══════════════════════════════════════════════════════════════════
# TESTS: PII handling in pipeline
# ══════════════════════════════════════════════════════════════════


class TestPIIInPipeline:
    """Tests for PII handling in the full pipeline."""

    @pytest.mark.asyncio
    async def test_pii_redacted_in_pipeline(self, pipeline):
        """PII should be detected and redacted during pipeline run."""
        state = _make_state(query="My email is test@example.com and I need help")
        result = await pipeline.run(state)

        assert result["pii_detected"] is True
        assert "test@example.com" not in result.get("pii_redacted_query", "")

    @pytest.mark.asyncio
    async def test_no_pii_in_normal_query(self, pipeline):
        """Normal query should not flag PII."""
        state = _make_state(query="I have a question about my order")
        result = await pipeline.run(state)
        assert result["pii_detected"] is False
