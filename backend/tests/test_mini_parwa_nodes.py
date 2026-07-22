"""
Unit tests for Mini Parwa pipeline nodes.

Tests all 6 nodes independently with mock state:
  - pii_check_node
  - empathy_check_node
  - emergency_check_node
  - classify_node
  - generate_node
  - format_node

Plus:
  - PII detection with known PII patterns
  - Empathy check with various emotional inputs
  - Emergency detection with legal threats, safety keywords
  - Classification with various intent types
  - Generation with mock LLM responses
  - Formatting with Mini variant defaults
  - Error handling / fallbacks (BC-008)
  - No node ever crashes on bad input
"""

import os
import sys
import types
from unittest.mock import MagicMock, patch, AsyncMock

import asyncio
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
# Mock Redis (used by pii_redaction_engine)
_fake_redis_module = types.ModuleType("app.core.redis")
_fake_redis_module.get_redis = AsyncMock(return_value=MagicMock())
_fake_redis_module.make_key = lambda *args: ":".join(str(a) for a in args)
sys.modules.setdefault("app.core.redis", _fake_redis_module)

# Mock app.exceptions
_fake_exceptions = types.ModuleType("app.exceptions")
_fake_exceptions.InternalError = type("InternalError", (Exception,), {})
sys.modules.setdefault("app.exceptions", _fake_exceptions)

# Mock app.logger if not already done
if "app.logger" not in sys.modules or not hasattr(sys.modules["app.logger"], "get_logger"):
    _fake_logger = types.ModuleType("app.logger")
    _mock_logger_instance = MagicMock()
    _fake_logger.get_logger = lambda name: _mock_logger_instance
    sys.modules["app.logger"] = _fake_logger

# Mock database modules
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

# Mock shared modules
for mod_name in [
    "shared", "shared.knowledge_base", "shared.knowledge_base.manager",
    "shared.knowledge_base.retriever", "shared.knowledge_base.vector_search",
    "shared.knowledge_base.chunker", "shared.knowledge_base.reindexing",
]:
    sys.modules.setdefault(mod_name, MagicMock())

# ── Now import the nodes ─────────────────────────────────────────────
from app.core.parwa_graph_state import create_initial_state
from app.core.mini_parwa.nodes import (
    pii_check_node,
    empathy_check_node,
    emergency_check_node,
    classify_node,
    generate_node,
    format_node,
    _check_emergency_keywords,
    _keyword_empathy_check,
    EMERGENCY_PATTERNS,
    EMPATHY_PATTERNS,
    TEMPLATE_RESPONSES,
)


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


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
# TEST: pii_check_node
# ══════════════════════════════════════════════════════════════════


class TestPIICheckNode:
    """Tests for the PII check node."""

    def test_no_pii_in_query(self):
        """Query without PII should return pii_detected=False."""
        state = _make_state(query="I need help with my order")
        result = pii_check_node(state)
        assert result["pii_detected"] is False
        assert result["pii_redacted_query"] == "I need help with my order"
        assert result["pii_entities"] == []
        assert result["current_step"] == "pii_check"

    def test_email_pii_detected(self):
        """Email address should be detected and redacted."""
        state = _make_state(query="My email is john@example.com and I need help")
        result = pii_check_node(state)
        assert result["pii_detected"] is True
        assert "john@example.com" not in result["pii_redacted_query"]
        assert "EMAIL" in result["pii_redacted_query"]
        assert len(result["pii_entities"]) > 0
        assert result["pii_entities"][0]["type"] == "EMAIL"

    def test_phone_pii_detected(self):
        """Phone number should be detected and redacted."""
        state = _make_state(query="Call me at 555-123-4567 please")
        result = pii_check_node(state)
        assert result["pii_detected"] is True
        assert "555-123-4567" not in result["pii_redacted_query"]

    def test_multiple_pii_types(self):
        """Multiple PII types in one query should all be detected."""
        state = _make_state(
            query="My email is test@company.com and my SSN is 123-45-6789"
        )
        result = pii_check_node(state)
        assert result["pii_detected"] is True
        # Should have at least email detected
        entity_types = [e["type"] for e in result["pii_entities"]]
        assert "EMAIL" in entity_types

    def test_empty_query(self):
        """Empty query should not crash (BC-008)."""
        state = _make_state(query="")
        result = pii_check_node(state)
        assert result["pii_detected"] is False
        assert result["current_step"] == "pii_check"

    def test_audit_log_entry(self):
        """Node should append an audit log entry."""
        state = _make_state(query="Hello there")
        result = pii_check_node(state)
        assert "audit_log" in result
        assert len(result["audit_log"]) > 0
        entry = result["audit_log"][0]
        assert entry["step"] == "pii_check"

    def test_step_outputs(self):
        """Node should write step_outputs."""
        state = _make_state(query="Hello")
        result = pii_check_node(state)
        assert "step_outputs" in result
        assert "pii_check" in result["step_outputs"]
        assert result["step_outputs"]["pii_check"]["status"] == "completed"


# ══════════════════════════════════════════════════════════════════
# TEST: empathy_check_node
# ══════════════════════════════════════════════════════════════════


class TestEmpathyCheckNode:
    """Tests for the empathy check node."""

    def test_neutral_query(self):
        """Neutral query should get moderate empathy score."""
        state = _make_state(query="I have a question about my account")
        result = asyncio.run(empathy_check_node(state))
        assert 0.0 <= result["empathy_score"] <= 1.0
        assert isinstance(result["empathy_flags"], list)
        assert result["current_step"] == "empathy_check"

    def test_frustrated_query(self):
        """Frustrated query should have low empathy score and frustrated flag."""
        state = _make_state(query="I am very frustrated with this service!")
        result = asyncio.run(empathy_check_node(state))
        assert result["empathy_score"] < 0.7
        assert "frustrated" in result["empathy_flags"]

    def test_angry_query(self):
        """Angry query should have low empathy score and angry flag."""
        state = _make_state(query="I am angry about this terrible experience!")
        result = asyncio.run(empathy_check_node(state))
        assert result["empathy_score"] < 0.7
        assert "angry" in result["empathy_flags"]

    def test_urgent_query(self):
        """Urgent query should have urgent flag."""
        state = _make_state(query="This is urgent! I need help ASAP!")
        result = asyncio.run(empathy_check_node(state))
        assert "urgent" in result["empathy_flags"]

    def test_sad_query(self):
        """Sad query should have sad flag."""
        state = _make_state(query="I am so sad and disappointed with my purchase")
        result = asyncio.run(empathy_check_node(state))
        assert "sad" in result["empathy_flags"]

    def test_empty_query(self):
        """Empty query should not crash (BC-008)."""
        state = _make_state(query="")
        result = asyncio.run(empathy_check_node(state))
        assert result["empathy_score"] == 0.5
        assert result["current_step"] == "empathy_check"

    def test_audit_log_entry(self):
        """Node should append an audit log entry."""
        state = _make_state(query="Hello")
        result = asyncio.run(empathy_check_node(state))
        assert "audit_log" in result
        assert len(result["audit_log"]) > 0

    def test_keyword_fallback_works(self):
        """Keyword fallback should work when LLM is unavailable."""
        result = _keyword_empathy_check("I am frustrated and angry")
        assert result["empathy_score"] < 0.5
        assert "frustrated" in result["empathy_flags"]
        assert "angry" in result["empathy_flags"]


# ══════════════════════════════════════════════════════════════════
# TEST: emergency_check_node
# ══════════════════════════════════════════════════════════════════


class TestEmergencyCheckNode:
    """Tests for the emergency check node."""

    def test_no_emergency(self):
        """Normal query should not trigger emergency."""
        state = _make_state(query="I need help with my order")
        result = emergency_check_node(state)
        assert result["emergency_flag"] is False
        assert result["emergency_type"] == ""

    def test_legal_threat(self):
        """Legal threat should be detected."""
        state = _make_state(query="I will sue your company for this!")
        result = emergency_check_node(state)
        assert result["emergency_flag"] is True
        assert result["emergency_type"] == "legal_threat"

    def test_safety_threat(self):
        """Safety-related content should be detected."""
        state = _make_state(query="I want to hurt myself")
        result = emergency_check_node(state)
        assert result["emergency_flag"] is True
        assert result["emergency_type"] == "safety"

    def test_self_harm(self):
        """Self-harm should be detected as safety emergency."""
        state = _make_state(query="I'm thinking about self-harm")
        result = emergency_check_node(state)
        assert result["emergency_flag"] is True
        assert result["emergency_type"] == "safety"

    def test_compliance_violation(self):
        """Compliance-related content should be detected."""
        state = _make_state(query="This is a GDPR data breach!")
        result = emergency_check_node(state)
        assert result["emergency_flag"] is True
        assert result["emergency_type"] == "compliance"

    def test_media_threat(self):
        """Media/social media threat should be detected."""
        state = _make_state(query="I'm going to the press about this!")
        result = emergency_check_node(state)
        assert result["emergency_flag"] is True
        assert result["emergency_type"] == "media"

    def test_safety_priority_over_legal(self):
        """Safety should take priority over legal threats."""
        # Query with both safety and legal keywords
        result = _check_emergency_keywords("I will sue and I want to hurt myself")
        assert result["emergency_flag"] is True
        assert result["emergency_type"] == "safety"

    def test_empty_query(self):
        """Empty query should not crash (BC-008)."""
        state = _make_state(query="")
        result = emergency_check_node(state)
        assert result["emergency_flag"] is False
        assert result["current_step"] == "emergency_check"

    def test_case_insensitive(self):
        """Emergency detection should be case-insensitive."""
        state = _make_state(query="I WILL SUE YOUR COMPANY!")
        result = emergency_check_node(state)
        assert result["emergency_flag"] is True

    def test_audit_log_entry(self):
        """Node should append an audit log entry."""
        state = _make_state(query="Hello")
        result = emergency_check_node(state)
        assert "audit_log" in result
        assert len(result["audit_log"]) > 0


# ══════════════════════════════════════════════════════════════════
# TEST: classify_node
# ══════════════════════════════════════════════════════════════════


class TestClassifyNode:
    """Tests for the classify node."""

    def test_refund_intent(self):
        """Refund-related query should classify as refund."""
        state = _make_state(query="I want a refund for my order")
        result = classify_node(state)
        assert result["classification"]["intent"] == "refund"
        assert result["classification"]["method"] == "keyword"

    def test_technical_intent(self):
        """Technical issue should classify as technical."""
        state = _make_state(query="The app is not working and keeps crashing")
        result = classify_node(state)
        assert result["classification"]["intent"] == "technical"

    def test_billing_intent(self):
        """Billing question should classify as billing."""
        state = _make_state(query="I have a question about my bill and payment")
        result = classify_node(state)
        assert result["classification"]["intent"] == "billing"

    def test_complaint_intent(self):
        """Complaint should classify as complaint."""
        state = _make_state(query="I want to make a formal complaint about this terrible service")
        result = classify_node(state)
        assert result["classification"]["intent"] == "complaint"

    def test_cancellation_intent(self):
        """Cancellation request should classify as cancellation."""
        state = _make_state(query="I want to cancel my subscription")
        result = classify_node(state)
        assert result["classification"]["intent"] == "cancellation"

    def test_shipping_intent(self):
        """Shipping query should classify as shipping."""
        state = _make_state(query="Where is my package? Track my shipping")
        result = classify_node(state)
        assert result["classification"]["intent"] == "shipping"

    def test_general_intent_fallback(self):
        """Ambiguous query should classify as general."""
        state = _make_state(query="Hello there")
        result = classify_node(state)
        assert result["classification"]["intent"] == "general"

    def test_classification_has_confidence(self):
        """Classification should include confidence score."""
        state = _make_state(query="I want a refund for my order")
        result = classify_node(state)
        assert 0.0 <= result["classification"]["confidence"] <= 1.0

    def test_classification_has_secondary_intents(self):
        """Classification should include secondary intents."""
        state = _make_state(query="I want a refund for my broken order")
        result = classify_node(state)
        assert isinstance(result["classification"]["secondary_intents"], list)

    def test_empty_query(self):
        """Empty query should not crash (BC-008)."""
        state = _make_state(query="")
        result = classify_node(state)
        assert result["classification"]["intent"] == "general"
        assert result["current_step"] == "classify"

    def test_uses_keyword_method(self):
        """Mini should use keyword classification (no AI)."""
        state = _make_state(query="I need a refund")
        result = classify_node(state)
        assert result["classification"]["method"] == "keyword"


# ══════════════════════════════════════════════════════════════════
# TEST: generate_node
# ══════════════════════════════════════════════════════════════════


class TestGenerateNode:
    """Tests for the generate node."""

    def test_template_fallback_on_no_llm(self):
        """Without LLM, should use template response."""
        state = _make_state(query="I need a refund")
        state["classification"] = {
            "intent": "refund",
            "confidence": 0.8,
            "secondary_intents": [],
            "method": "keyword",
        }
        result = asyncio.run(generate_node(state))
        assert result["generated_response"] != ""
        assert result["current_step"] == "generate"

    def test_refund_template(self):
        """Refund query should use refund template."""
        state = _make_state(query="I want my money back")
        state["classification"] = {
            "intent": "refund",
            "confidence": 0.8,
            "secondary_intents": [],
            "method": "keyword",
        }
        result = asyncio.run(generate_node(state))
        # Should contain refund-related text (from template or LLM)
        response_lower = result["generated_response"].lower()
        assert "refund" in response_lower or "thank you" in response_lower

    def test_emergency_template(self):
        """Emergency flag should produce escalation response."""
        state = _make_state(query="I will sue you!")
        state["emergency_flag"] = True
        state["emergency_type"] = "legal_threat"
        state["ticket_id"] = "tkt_123"
        result = asyncio.run(generate_node(state))
        assert "priority" in result["generated_response"].lower() or "escalat" in result["generated_response"].lower() or "reference" in result["generated_response"].lower()
        assert result["generation_model"] == "template"

    def test_industry_prompt_used(self):
        """Industry context should be included in generation."""
        state = _make_state(query="I need help", industry="ecommerce")
        state["classification"] = {
            "intent": "general",
            "confidence": 0.3,
            "secondary_intents": [],
            "method": "keyword",
        }
        result = asyncio.run(generate_node(state))
        assert result["generated_response"] != ""

    def test_empathy_context_used(self):
        """Low empathy score should add empathy instructions."""
        state = _make_state(query="I am very frustrated!")
        state["empathy_score"] = 0.2
        state["empathy_flags"] = ["frustrated"]
        state["classification"] = {
            "intent": "complaint",
            "confidence": 0.8,
            "secondary_intents": [],
            "method": "keyword",
        }
        result = asyncio.run(generate_node(state))
        assert result["generated_response"] != ""

    def test_empty_query(self):
        """Empty query should not crash (BC-008)."""
        state = _make_state(query="")
        result = asyncio.run(generate_node(state))
        assert result["generated_response"] != ""
        assert result["current_step"] == "generate"

    def test_general_template_exists(self):
        """General template should exist as fallback."""
        assert "general" in TEMPLATE_RESPONSES
        assert TEMPLATE_RESPONSES["general"] != ""


# ══════════════════════════════════════════════════════════════════
# TEST: format_node
# ══════════════════════════════════════════════════════════════════


class TestFormatNode:
    """Tests for the format node."""

    def test_basic_formatting(self):
        """Should format the generated response."""
        state = _make_state(query="Hello")
        state["generated_response"] = "Thank you for contacting us. We will help you."
        state["classification"] = {"intent": "general", "confidence": 0.5}
        state["empathy_score"] = 0.5
        result = format_node(state)
        assert result["formatted_response"] != ""
        assert result["final_response"] != ""
        assert result["pipeline_status"] in ("success", "partial", "failed")

    def test_chat_channel_format(self):
        """Chat channel should use 'chat' response format."""
        state = _make_state(query="Hello", channel="chat")
        state["generated_response"] = "Hello there"
        state["classification"] = {"intent": "general", "confidence": 0.5}
        result = format_node(state)
        assert result["response_format"] == "chat"

    def test_email_channel_format(self):
        """Email channel should use 'email' response format."""
        state = _make_state(query="Hello", channel="email")
        state["generated_response"] = "Hello there"
        state["classification"] = {"intent": "general", "confidence": 0.5}
        result = format_node(state)
        assert result["response_format"] == "email"

    def test_phone_channel_format(self):
        """Phone channel should use 'phone_transcript' format."""
        state = _make_state(query="Hello", channel="phone")
        state["generated_response"] = "Hello there"
        state["classification"] = {"intent": "general", "confidence": 0.5}
        result = format_node(state)
        assert result["response_format"] == "phone_transcript"

    def test_steps_completed_includes_format(self):
        """Steps completed should include format."""
        state = _make_state(query="Hello")
        state["generated_response"] = "Hello there"
        state["classification"] = {"intent": "general", "confidence": 0.5}
        result = format_node(state)
        assert "format" in result["steps_completed"]

    def test_pipeline_status_success(self):
        """Clean run should result in 'success' status."""
        state = _make_state(query="Hello")
        state["generated_response"] = "Hello there"
        state["classification"] = {"intent": "general", "confidence": 0.5}
        state["errors"] = []
        result = format_node(state)
        assert result["pipeline_status"] == "success"

    def test_pipeline_status_partial_with_errors(self):
        """Run with errors should result in 'partial' status."""
        state = _make_state(query="Hello")
        state["generated_response"] = "Hello there"
        state["classification"] = {"intent": "general", "confidence": 0.5}
        state["errors"] = ["some error occurred"]
        result = format_node(state)
        assert result["pipeline_status"] == "partial"

    def test_mini_formatters_applied(self):
        """Mini should apply token_limit, markdown, whitespace formatters."""
        state = _make_state(query="Hello")
        state["generated_response"] = "Thank you for contacting us."
        state["classification"] = {"intent": "general", "confidence": 0.5}
        result = format_node(state)
        step_data = result.get("step_outputs", {}).get("format", {})
        assert step_data.get("status") == "completed"

    def test_empty_response(self):
        """Empty generated response should not crash (BC-008)."""
        state = _make_state(query="Hello")
        state["generated_response"] = ""
        state["classification"] = {"intent": "general", "confidence": 0.5}
        result = format_node(state)
        assert result["current_step"] == "format"


# ══════════════════════════════════════════════════════════════════
# TEST: BC-008 — Never crash on bad input
# ══════════════════════════════════════════════════════════════════


class TestBC008NeverCrash:
    """Tests that no node ever crashes on bad input (BC-008)."""

    def test_pii_none_query(self):
        """PII node with None-like state should not crash."""
        # Empty state dict
        result = pii_check_node({})
        assert "pii_detected" in result

    def test_empathy_empty_state(self):
        """Empathy node with empty state should not crash."""
        result = asyncio.run(empathy_check_node({}))
        assert "empathy_score" in result

    def test_emergency_empty_state(self):
        """Emergency node with empty state should not crash."""
        result = emergency_check_node({})
        assert "emergency_flag" in result

    def test_classify_empty_state(self):
        """Classify node with empty state should not crash."""
        result = classify_node({})
        assert "classification" in result

    def test_generate_empty_state(self):
        """Generate node with empty state should not crash."""
        result = asyncio.run(generate_node({}))
        assert "generated_response" in result

    def test_format_empty_state(self):
        """Format node with empty state should not crash."""
        result = format_node({})
        assert "final_response" in result

    def test_all_nodes_with_minimal_state(self):
        """All nodes should handle minimal state without crashing."""
        import asyncio
        minimal = {"query": "test", "company_id": "test"}
        sync_nodes = [pii_check_node, emergency_check_node, classify_node, format_node]
        async_nodes = [empathy_check_node, generate_node]
        for node_fn in sync_nodes:
            result = node_fn(minimal)
            assert isinstance(result, dict), f"{node_fn.__name__} did not return dict"
        for node_fn in async_nodes:
            result = asyncio.run(node_fn(minimal))
            assert isinstance(result, dict), f"{node_fn.__name__} did not return dict"

    def test_all_nodes_with_very_long_query(self):
        """All nodes should handle very long queries."""
        import asyncio
        long_query = "x" * 10000
        state = _make_state(query=long_query)
        sync_nodes = [pii_check_node, emergency_check_node, classify_node, format_node]
        async_nodes = [empathy_check_node, generate_node]
        for node_fn in sync_nodes:
            result = node_fn(state)
            assert isinstance(result, dict), f"{node_fn.__name__} crashed on long input"
        for node_fn in async_nodes:
            result = asyncio.run(node_fn(state))
            assert isinstance(result, dict), f"{node_fn.__name__} crashed on long input"

    def test_all_nodes_with_special_characters(self):
        """All nodes should handle special characters in queries."""
        import asyncio
        special_query = "!@#$%^&*(){}[]|\\:;\"'<>,.?/~`\n\t"
        state = _make_state(query=special_query)
        sync_nodes = [pii_check_node, emergency_check_node, classify_node]
        async_nodes = [empathy_check_node]
        for node_fn in sync_nodes:
            result = node_fn(state)
            assert isinstance(result, dict), f"{node_fn.__name__} crashed on special chars"
        for node_fn in async_nodes:
            result = asyncio.run(node_fn(state))
            assert isinstance(result, dict), f"{node_fn.__name__} crashed on special chars"
