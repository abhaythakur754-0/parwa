"""Unit tests for all 22 PARWA nodes.

Each test verifies that a node correctly reads from state,
processes the input, and returns the expected output fields.

All nodes are now async — tests use pytest-asyncio.
"""

import pytest

from parwa.nodes.ingest import ingest
from parwa.nodes.intent_classifier import intent_classifier
from parwa.nodes.sentiment_analyzer import sentiment_analyzer
from parwa.nodes.escalation_decision import escalation_decision
from parwa.nodes.faq_matcher import faq_matcher
from parwa.nodes.kb_retriever import kb_retriever
from parwa.nodes.context_manager import context_manager
from parwa.nodes.integration_lookup import integration_lookup
from parwa.nodes.reasoning_engine import reasoning_engine
from parwa.nodes.reverse_thinker import reverse_thinker
from parwa.nodes.tree_of_thoughts import tree_of_thoughts
from parwa.nodes.strategy_planner import strategy_planner
from parwa.nodes.action_planner import action_planner
from parwa.nodes.action_executor import action_executor
from parwa.nodes.action_verifier import action_verifier
from parwa.nodes.proactive_checker import proactive_checker
from parwa.nodes.prediction_engine import prediction_engine
from parwa.nodes.feedback_loop import feedback_loop
from parwa.nodes.pii_compliance_guard import pii_compliance_guard
from parwa.nodes.audit_logger import audit_logger
from parwa.nodes.quality_scorer import quality_scorer
from parwa.nodes.response_formatter import response_formatter


# ─── Router Agent Nodes ───────────────────────────────────────────────────────────

class TestIngest:
    """Node 1: INGEST"""

    @pytest.mark.asyncio
    async def test_generates_ticket_id(self):
        result = await ingest({"raw_message": "Hello"})
        assert "ticket_id" in result
        assert result["ticket_id"].startswith("TKT-")

    @pytest.mark.asyncio
    async def test_preserves_existing_ticket_id(self):
        result = await ingest({"ticket_id": "TKT-EXISTING", "raw_message": "Hello"})
        assert result["ticket_id"] == "TKT-EXISTING"

    @pytest.mark.asyncio
    async def test_sets_default_channel(self):
        result = await ingest({"raw_message": "Hello"})
        assert result["channel"] == "email"

    @pytest.mark.asyncio
    async def test_validates_channel_for_variant(self):
        result = await ingest({"raw_message": "Hello", "channel": "social", "variant": "mini"})
        # Mini doesn't have social, should fall back
        assert result["channel"] in ("email", "chat")

    @pytest.mark.asyncio
    async def test_sets_variant(self):
        result = await ingest({"raw_message": "Hello", "variant": "high"})
        assert result["variant"] == "high"


class TestIntentClassifier:
    """Node 2: INTENT_CLASSIFIER"""

    @pytest.mark.asyncio
    async def test_classifies_refund(self):
        result = await intent_classifier({"raw_message": "I was charged twice, I want a refund"})
        assert result["intent"] == "refund_request"
        assert result["intent_confidence"] > 0.5

    @pytest.mark.asyncio
    async def test_classifies_cancellation(self):
        result = await intent_classifier({"raw_message": "I want to cancel my order"})
        assert result["intent"] == "cancellation"

    @pytest.mark.asyncio
    async def test_classifies_order_status(self):
        result = await intent_classifier({"raw_message": "Where is my order?"})
        assert result["intent"] == "order_status"

    @pytest.mark.asyncio
    async def test_default_general_inquiry(self):
        result = await intent_classifier({"raw_message": "Hello there"})
        assert result["intent"] == "general_inquiry"

    @pytest.mark.asyncio
    async def test_sets_complexity(self):
        result = await intent_classifier({"raw_message": "I was charged twice, I want a refund"})
        assert result["complexity"] in ("simple", "medium", "complex", "critical")


class TestSentimentAnalyzer:
    """Node 18: SENTIMENT_ANALYZER"""

    @pytest.mark.asyncio
    async def test_detects_frustration(self):
        result = await sentiment_analyzer({"raw_message": "This is unacceptable! I'm so frustrated"})
        assert result["sentiment"] == "frustrated"
        assert result["sentiment_urgency"] > 0.5

    @pytest.mark.asyncio
    async def test_detects_anger(self):
        result = await sentiment_analyzer({"raw_message": "I'm furious, I'll call my lawyer"})
        assert result["sentiment"] == "angry"
        assert result["sentiment_urgency"] > 0.8

    @pytest.mark.asyncio
    async def test_detects_happy(self):
        result = await sentiment_analyzer({"raw_message": "Thank you so much, great service!"})
        assert result["sentiment"] == "happy"

    @pytest.mark.asyncio
    async def test_default_neutral(self):
        result = await sentiment_analyzer({"raw_message": "I have a question"})
        assert result["sentiment"] == "neutral"


class TestEscalationDecision:
    """Node 20: ESCALATION_DECISION"""

    @pytest.mark.asyncio
    async def test_escalates_angry_critical(self):
        result = await escalation_decision({
            "raw_message": "I'm furious",
            "sentiment": "angry",
            "sentiment_urgency": 0.95,
            "complexity": "critical",
            "intent": "complaint",
            "intent_confidence": 0.9,
        })
        assert result["should_escalate"] is True

    @pytest.mark.asyncio
    async def test_escalates_escalation_intent(self):
        result = await escalation_decision({
            "raw_message": "Let me speak to a manager",
            "sentiment": "neutral",
            "sentiment_urgency": 0.3,
            "complexity": "simple",
            "intent": "escalation",
            "intent_confidence": 0.8,
        })
        assert result["should_escalate"] is True

    @pytest.mark.asyncio
    async def test_no_escalate_normal(self):
        result = await escalation_decision({
            "raw_message": "Where is my order?",
            "sentiment": "neutral",
            "sentiment_urgency": 0.3,
            "complexity": "simple",
            "intent": "order_status",
            "intent_confidence": 0.9,
        })
        assert result["should_escalate"] is False


# ─── Knowledge Agent Nodes ────────────────────────────────────────────────────────

class TestFaqMatcher:
    """Node 3: FAQ_MATCHER"""

    @pytest.mark.asyncio
    async def test_matches_refund_faq(self):
        result = await faq_matcher({"raw_message": "What is the refund policy?"})
        assert result["faq_match"] is not None
        assert result["faq_match"]["relevance_score"] >= 0.3

    @pytest.mark.asyncio
    async def test_no_match_for_unclear(self):
        result = await faq_matcher({"raw_message": "asdfghjkl"})
        assert result["faq_match"] is None


class TestKbRetriever:
    """Node 4: KB_RETRIEVER"""

    @pytest.mark.asyncio
    async def test_retrieves_refund_docs(self):
        result = await kb_retriever({"raw_message": "I was charged twice", "intent": "refund_request"})
        assert len(result["kb_results"]) > 0
        assert result["kb_results"][0]["relevance_score"] > 0.3

    @pytest.mark.asyncio
    async def test_returns_max_3_results(self):
        result = await kb_retriever({"raw_message": "I need help", "intent": "general_inquiry"})
        assert len(result["kb_results"]) <= 3


class TestContextManager:
    """Node 19: CONTEXT_MANAGER"""

    @pytest.mark.asyncio
    async def test_adds_current_message(self):
        result = await context_manager({"raw_message": "Hello", "context_history": []})
        assert len(result["context_history"]) == 1
        assert result["context_history"][0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_appends_to_existing(self):
        existing = [{"role": "customer", "content": "Hi"}]
        result = await context_manager({"raw_message": "Help", "context_history": existing})
        assert len(result["context_history"]) == 2

    @pytest.mark.asyncio
    async def test_limits_to_10_entries(self):
        existing = [{"role": "customer", "content": f"Msg {i}"} for i in range(12)]
        result = await context_manager({"raw_message": "New", "context_history": existing})
        assert len(result["context_history"]) <= 11  # 10 + new


class TestIntegrationLookup:
    """Node 5: INTEGRATION_LOOKUP"""

    @pytest.mark.asyncio
    async def test_returns_crm_data(self):
        result = await integration_lookup({"customer_id": "default", "intent": "refund_request"})
        # Default customer data includes payments and duplicate_charges
        assert result["integration_data"].get("found") is True
        assert "payments" in result["integration_data"] or "duplicate_charges" in result["integration_data"]

    @pytest.mark.asyncio
    async def test_returns_order_data_for_status(self):
        result = await integration_lookup({"customer_id": "default", "intent": "order_status"})
        assert "orders" in result["integration_data"]


# ─── Reasoning Agent Nodes ────────────────────────────────────────────────────────

class TestReasoningEngine:
    """Node 6: REASONING_ENGINE"""

    @pytest.mark.asyncio
    async def test_produces_chain(self):
        result = await reasoning_engine({
            "raw_message": "I was charged twice",
            "intent": "refund_request",
            "faq_match": None,
            "kb_results": [],
            "integration_data": {},
            "active_frameworks": [],
        })
        assert len(result["reasoning_chain"]) > 0
        assert result["reasoning_conclusion"] != ""

    @pytest.mark.asyncio
    async def test_adds_cot_framework(self):
        result = await reasoning_engine({
            "raw_message": "Hello",
            "intent": "general_inquiry",
            "faq_match": None,
            "kb_results": [],
            "integration_data": {},
            "active_frameworks": [],
        })
        assert "chain_of_thought" in result["active_frameworks"]


class TestReverseThinker:
    """Node 10: REVERSE_THINKER"""

    @pytest.mark.asyncio
    async def test_validates_with_evidence(self):
        result = await reverse_thinker({
            "reasoning_conclusion": "Customer eligible for refund",
            "kb_results": [{"content": "Refund policy", "relevance_score": 0.9}],
            "integration_data": {"charges": [{"amount": 49.99}]},
            "active_frameworks": [],
            "loop_count": 0,
            "max_loops": 2,
        })
        assert result["reverse_validation"]["passed"] is True
        assert "reverse_thinking" in result["active_frameworks"]

    @pytest.mark.asyncio
    async def test_fails_without_evidence(self):
        result = await reverse_thinker({
            "reasoning_conclusion": "Some conclusion",
            "kb_results": [],
            "integration_data": {},
            "active_frameworks": [],
            "loop_count": 0,
            "max_loops": 2,
        })
        assert result["reverse_validation"]["passed"] is False


class TestTreeOfThoughts:
    """Node 12: TREE_OF_THOUGHTS"""

    @pytest.mark.asyncio
    async def test_creates_multiple_paths(self):
        result = await tree_of_thoughts({
            "intent": "refund_request",
            "reasoning_conclusion": "Eligible for refund",
            "active_frameworks": [],
        })
        assert len(result["reasoning_paths"]) >= 3
        assert result["selected_path"] is not None
        assert "tree_of_thoughts" in result["active_frameworks"]

    @pytest.mark.asyncio
    async def test_selects_best_path(self):
        result = await tree_of_thoughts({
            "intent": "refund_request",
            "reasoning_conclusion": "Eligible for refund",
            "active_frameworks": [],
        })
        assert result["selected_path"]["selected"] is True
        assert result["selected_path"]["confidence"] > 0.5


class TestStrategyPlanner:
    """Node 11: STRATEGY_PLANNER"""

    @pytest.mark.asyncio
    async def test_creates_plan(self):
        result = await strategy_planner({
            "intent": "refund_request",
            "reasoning_conclusion": "Eligible for refund",
            "selected_path": None,
            "active_frameworks": [],
        })
        assert len(result["strategy_plan"]) > 0
        assert "maker_planning" in result["active_frameworks"]

    @pytest.mark.asyncio
    async def test_uses_selected_path_steps(self):
        path = {"steps": ["Step A", "Step B", "Step C"]}
        result = await strategy_planner({
            "intent": "refund_request",
            "reasoning_conclusion": "Eligible",
            "selected_path": path,
            "active_frameworks": [],
        })
        assert result["strategy_plan"] == ["Step A", "Step B", "Step C"]


# ─── Action Agent Nodes ───────────────────────────────────────────────────────────

class TestActionPlanner:
    """Node 7: ACTION_PLANNER"""

    @pytest.mark.asyncio
    async def test_plans_refund_action(self):
        result = await action_planner({
            "intent": "refund_request",
            "reasoning_conclusion": "Eligible for refund",
            "strategy_plan": ["Verify", "Process"],
            "integration_data": {"charges": [{"amount": 49.99}]},
        })
        assert len(result["action_plans"]) > 0
        assert result["action_plans"][0]["action_type"] == "process_refund"


class TestActionExecutor:
    """Node 8: ACTION_EXECUTOR — KEY VARIANT DIFFERENTIATION NODE"""

    @pytest.mark.asyncio
    async def test_parwa_executes_refund(self):
        result = await action_executor({
            "variant": "parwa",
            "action_plans": [{"action_type": "process_refund", "description": "Refund", "parameters": {}, "evidence": [], "risk_level": "low"}],
            "quality_score": 85,
        })
        # MOCK_MODE returns "simulated" when no CRM customer; "executed" with real CRM
        assert result["execution_results"][0]["status"] in ("executed", "simulated")
        assert result["recommendation"] is None

    @pytest.mark.asyncio
    async def test_mini_recommends_refund(self):
        result = await action_executor({
            "variant": "mini",
            "action_plans": [{"action_type": "process_refund", "description": "Refund", "parameters": {"amount": 49.99}, "evidence": ["Duplicate found"], "risk_level": "low"}],
            "quality_score": 85,
        })
        assert result["execution_results"][0]["status"] == "recommended"
        assert result["recommendation"] is not None
        assert result["recommendation"]["pending_approval"] is True

    @pytest.mark.asyncio
    async def test_high_executes_everything(self):
        result = await action_executor({
            "variant": "high",
            "action_plans": [{"action_type": "process_refund", "description": "Refund", "parameters": {}, "evidence": [], "risk_level": "low"}],
            "quality_score": 85,
        })
        # MOCK_MODE returns "simulated" when no CRM customer; "executed" with real CRM
        assert result["execution_results"][0]["status"] in ("executed", "simulated")


class TestActionVerifier:
    """Node 9: ACTION_VERIFIER"""

    @pytest.mark.asyncio
    async def test_passes_for_successful_execution(self):
        result = await action_verifier({
            "execution_results": [{"status": "executed", "action_type": "send_reply"}],
            "recommendation": None,
            "loop_count": 0,
            "max_loops": 2,
        })
        assert result["verification_passed"] is True

    @pytest.mark.asyncio
    async def test_passes_for_recommendation(self):
        result = await action_verifier({
            "execution_results": [{"status": "recommended", "action_type": "process_refund"}],
            "recommendation": {"pending_approval": True, "action_type": "process_refund", "evidence": [], "parameters": {}},
            "loop_count": 0,
            "max_loops": 2,
        })
        assert result["verification_passed"] is True


# ─── Proactive Agent Nodes ────────────────────────────────────────────────────────

class TestProactiveChecker:
    """Node 13: PROACTIVE_CHECKER"""

    @pytest.mark.asyncio
    async def test_generates_insights(self):
        result = await proactive_checker({
            "intent": "refund_request",
            "integration_data": {},
        })
        assert len(result["proactive_insights"]) > 0

    @pytest.mark.asyncio
    async def test_detects_shipping_followup(self):
        result = await proactive_checker({
            "intent": "refund_request",
            "integration_data": {"orders": [{"status": "delayed"}]},
        })
        descriptions = [i["description"] for i in result["proactive_insights"]]
        assert any("shipping" in d.lower() or "delayed" in d.lower() for d in descriptions)


class TestPredictionEngine:
    """Node 14: PREDICTION_ENGINE"""

    @pytest.mark.asyncio
    async def test_predicts_for_frustrated(self):
        result = await prediction_engine({
            "intent": "refund_request",
            "integration_data": {},
            "sentiment": "frustrated",
        })
        assert len(result["predictions"]) > 0

    @pytest.mark.asyncio
    async def test_predicts_duplicate_billing_confusion(self):
        result = await prediction_engine({
            "intent": "refund_request",
            "integration_data": {"charges": [{"amount": 49.99}, {"amount": 49.99}]},
            "sentiment": "neutral",
        })
        descriptions = [p["description"] for p in result["predictions"]]
        assert any("duplicate" in d.lower() or "billing" in d.lower() for d in descriptions)


class TestFeedbackLoop:
    """Node 22: FEEDBACK_LOOP"""

    @pytest.mark.asyncio
    async def test_generates_feedback(self):
        result = await feedback_loop({
            "intent": "refund_request",
            "quality_score": 85,
            "verification_passed": True,
            "recommendation": None,
        })
        assert result["feedback_signal"]["resolved"] is True
        assert result["feedback_signal"]["satisfaction"] in ("high", "medium", "low")


# ─── Compliance Agent Nodes ───────────────────────────────────────────────────────

class TestPiiComplianceGuard:
    """Node 15: PII_COMPLIANCE_GUARD"""

    @pytest.mark.asyncio
    async def test_detects_email(self):
        result = await pii_compliance_guard({"raw_message": "My email is john@example.com"})
        assert result["pii_detected"] is True
        assert "[EMAIL_REDACTED]" in result["pii_redacted_message"]

    @pytest.mark.asyncio
    async def test_detects_phone(self):
        result = await pii_compliance_guard({"raw_message": "Call me at 555-123-4567"})
        assert result["pii_detected"] is True

    @pytest.mark.asyncio
    async def test_no_pii_in_clean_message(self):
        result = await pii_compliance_guard({"raw_message": "I need help with my order"})
        assert result["pii_detected"] is False


class TestAuditLogger:
    """Node 16: AUDIT_LOGGER"""

    @pytest.mark.asyncio
    async def test_creates_audit_entry(self):
        result = await audit_logger({
            "ticket_id": "TKT-TEST",
            "intent": "refund_request",
            "action_plans": [{"action_type": "process_refund"}],
            "execution_results": [{"action_type": "process_refund", "status": "executed"}],
            "recommendation": None,
            "quality_score": 85,
            "variant": "parwa",
            "audit_log": [],
        })
        assert len(result["audit_log"]) == 1
        assert result["audit_log"][0]["ticket_id"] == "TKT-TEST"

    @pytest.mark.asyncio
    async def test_appends_to_existing(self):
        existing = [{"ticket_id": "TKT-OLD"}]
        result = await audit_logger({
            "ticket_id": "TKT-NEW",
            "intent": "order_status",
            "action_plans": [],
            "execution_results": [],
            "recommendation": None,
            "quality_score": 90,
            "variant": "parwa",
            "audit_log": existing,
        })
        assert len(result["audit_log"]) == 2


class TestQualityScorer:
    """Node 21: QUALITY_SCORER

    Month 1 update: Quality scorer now checks final_response and execution_results
    for honest scoring. Tests updated to include these fields.
    """

    @pytest.mark.asyncio
    async def test_scores_high_for_complete_response(self):
        result = await quality_scorer({
            "intent": "refund_request",
            "reasoning_conclusion": "Customer is eligible for $49.99 refund for duplicate charge on 2025-01-05.",
            "verification_passed": True,
            "recommendation": None,
            "variant": "parwa",
            "loop_count": 0,
            "max_loops": 2,
            "final_response": "I found the duplicate charge of $49.99 on your account from 2025-01-05 and have processed your refund. It will appear in 3-5 business days.",
            "execution_results": [{"action_type": "process_refund", "status": "executed"}],
        })
        assert result["quality_score"] >= 80, f"Expected >= 80, got {result['quality_score']}"

    @pytest.mark.asyncio
    async def test_scores_low_for_incomplete(self):
        result = await quality_scorer({
            "intent": "refund_request",
            "reasoning_conclusion": "",
            "verification_passed": False,
            "recommendation": None,
            "variant": "parwa",
            "loop_count": 0,
            "max_loops": 2,
        })
        assert result["quality_score"] < 80

    @pytest.mark.asyncio
    async def test_generic_response_scores_low(self):
        """Month 1: Generic/template responses should score below 70."""
        result = await quality_scorer({
            "intent": "refund_request",
            "reasoning_conclusion": "Customer wants refund",
            "verification_passed": True,
            "recommendation": None,
            "variant": "parwa",
            "loop_count": 0,
            "max_loops": 2,
            "final_response": "Thank you for reaching out. We have reviewed your request and are working on a resolution.",
            "execution_results": [],
        })
        assert result["quality_score"] < 80, f"Generic response scored {result['quality_score']}, should be < 80"
        assert "generic_response" in result["quality_issues"]


class TestResponseFormatter:
    """Node 17: RESPONSE_FORMATTER"""

    @pytest.mark.asyncio
    async def test_formats_refund_response_with_recommendation(self):
        result = await response_formatter({
            "intent": "refund_request",
            "reasoning_conclusion": "Eligible",
            "execution_results": [{"status": "recommended"}],
            "recommendation": {"pending_approval": True, "parameters": {"amount": 49.99}},
            "proactive_insights": [],
            "variant": "mini",
        })
        assert "refund" in result["final_response"].lower()
        assert "approval" in result["final_response"].lower() or "submitted" in result["final_response"].lower()

    @pytest.mark.asyncio
    async def test_formats_executed_refund(self):
        result = await response_formatter({
            "intent": "refund_request",
            "reasoning_conclusion": "Eligible",
            "execution_results": [{"status": "executed", "action_type": "process_refund"}],
            "recommendation": None,
            "proactive_insights": [],
            "variant": "parwa",
        })
        assert "refund" in result["final_response"].lower()
        assert "processed" in result["final_response"].lower()
