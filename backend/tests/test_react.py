"""
Comprehensive tests for PARWA ReAct Technique (react.py).

Tests cover:
- ReActConfig, ReActStep, ReActResult dataclasses
- ActionType enum
- ReActNode: should_activate, execute
- ReActProcessor: thought generation, tool selection, observation processing
- ReAct loop execution with mocked ToolRegistry
- Final answer synthesis
- Max iterations enforcement
- Company isolation (BC-001)
- Error fallback (BC-008)
- Edge cases
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.core.technique_router import (
    QuerySignals,
    TechniqueID,
)
from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
)
from app.core.techniques.react import (
    ActionType,
    ReActConfig,
    ReActNode,
    ReActProcessor,
    ReActResult,
    ReActStep,
)
from app.core.techniques.react_tools import ToolRegistry

# ── Environment bootstrap ─────────────────────────────────────────
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test_secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt")
os.environ.setdefault("DATA_ENCRYPTION_KEY", "12345678901234567890123456789012")


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

COMPANY_ID = "co-test-001"
OTHER_COMPANY = "co-test-002"


def _make_state(
    query: str = "Where is my order ORD-123?",
    external_data_required: bool = True,
    company_id: str = COMPANY_ID,
    **signal_overrides,
) -> ConversationState:
    """Create a ConversationState with sensible defaults for testing."""
    signals = QuerySignals(
        external_data_required=external_data_required,
        **signal_overrides,
    )
    return ConversationState(
        query=query,
        signals=signals,
        company_id=company_id,
    )


def _make_tool_result(
    success: bool = True,
    tool: str = "knowledge_base_search",
    data: Any = None,
    error: str = "",
) -> dict:
    """Create a mock tool result dict."""
    result: dict = {"success": success, "tool": tool}
    if data is not None:
        result["data"] = data
    if error:
        result["error"] = error
    if data is None and success:
        result["data"] = {
            "query": "test",
            "results": [],
            "total": 0,
            "message": "Placeholder",
        }
    return result


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def default_config():
    return ReActConfig(company_id=COMPANY_ID)


@pytest.fixture
def custom_config():
    return ReActConfig(
        company_id=COMPANY_ID,
        max_iterations=2,
        tool_timeout=10.0,
    )


@pytest.fixture
def mock_registry():
    """Create a ToolRegistry with mocked execute_tool."""
    registry = ToolRegistry()
    registry.execute_tool = AsyncMock(return_value=_make_tool_result())
    return registry


@pytest.fixture
def processor(default_config, mock_registry):
    return ReActProcessor(
        config=default_config,
        tool_registry=mock_registry,
    )


@pytest.fixture
def node(default_config, mock_registry):
    return ReActNode(
        config=default_config,
        tool_registry=mock_registry,
    )


# ══════════════════════════════════════════════════════════════════
# 1. ACTION TYPE ENUM
# ══════════════════════════════════════════════════════════════════


class TestActionType:
    """Test ActionType enum values."""

    def test_tool_call_value(self):
        assert ActionType.TOOL_CALL.value == "tool_call"

    def test_wait_value(self):
        assert ActionType.WAIT.value == "wait"

    def test_delegate_value(self):
        assert ActionType.DELEGATE.value == "delegate"

    def test_respond_value(self):
        assert ActionType.RESPOND.value == "respond"

    def test_all_values_unique(self):
        values = [e.value for e in ActionType]
        assert len(values) == len(set(values))

    def test_enum_members_count(self):
        assert len(ActionType) == 4

    def test_enum_is_str(self):
        assert isinstance(ActionType.TOOL_CALL, str)


# ══════════════════════════════════════════════════════════════════
# 2. REACT CONFIG
# ══════════════════════════════════════════════════════════════════


class TestReActConfig:
    """Test ReActConfig frozen dataclass."""

    def test_default_values(self):
        config = ReActConfig()
        assert config.company_id == ""
        assert config.max_iterations == 3
        assert config.tool_timeout == 30.0

    def test_custom_values(self):
        config = ReActConfig(
            company_id="co-1",
            max_iterations=5,
            tool_timeout=60.0,
        )
        assert config.company_id == "co-1"
        assert config.max_iterations == 5
        assert config.tool_timeout == 60.0

    def test_frozen_immutability(self):
        config = ReActConfig()
        with pytest.raises(AttributeError):
            config.company_id = "changed"  # type: ignore[misc]

    def test_frozen_max_iterations(self):
        config = ReActConfig()
        with pytest.raises(AttributeError):
            config.max_iterations = 99  # type: ignore[misc]

    def test_frozen_tool_timeout(self):
        config = ReActConfig()
        with pytest.raises(AttributeError):
            config.tool_timeout = 1.0  # type: ignore[misc]

    def test_partial_custom(self):
        config = ReActConfig(company_id="co-partial")
        assert config.company_id == "co-partial"
        assert config.max_iterations == 3  # default


# ══════════════════════════════════════════════════════════════════
# 3. REACT STEP DATACLASS
# ══════════════════════════════════════════════════════════════════


class TestReActStep:
    """Test ReActStep dataclass."""

    def test_default_values(self):
        step = ReActStep()
        assert step.step_number == 0
        assert step.step_type == "thought"
        assert step.content == ""
        assert step.tool_name == ""
        assert step.tool_params == {}
        assert step.tool_result == {}
        assert step.reasoning == ""

    def test_custom_thought_step(self):
        step = ReActStep(
            step_number=1,
            step_type="thought",
            content="Need to find order info",
            reasoning="Categories: order_reference",
        )
        assert step.step_number == 1
        assert step.step_type == "thought"
        assert step.content == "Need to find order info"

    def test_custom_action_step(self):
        step = ReActStep(
            step_number=2,
            step_type="action",
            content="Calling order_status_check",
            tool_name="order_status_check",
            tool_params={"order_id": "ORD-123"},
        )
        assert step.tool_name == "order_status_check"
        assert step.tool_params == {"order_id": "ORD-123"}

    def test_custom_observation_step(self):
        step = ReActStep(
            step_number=3,
            step_type="observation",
            content="Order found: shipped",
            tool_name="order_status_check",
            tool_result={"success": True, "data": {"status": "shipped"}},
        )
        assert step.tool_result["success"] is True

    def test_to_dict(self):
        step = ReActStep(
            step_number=1,
            step_type="thought",
            content="Analyze query",
            tool_name="",
            tool_params={"key": "val"},
            tool_result={"success": True},
            reasoning="test",
        )
        d = step.to_dict()
        assert d["step_number"] == 1
        assert d["step_type"] == "thought"
        assert d["content"] == "Analyze query"
        assert d["tool_params"] == {"key": "val"}
        assert d["tool_result"] == {"success": True}
        assert d["reasoning"] == "test"
        assert d["tool_name"] == ""

    def test_to_dict_empty(self):
        step = ReActStep()
        d = step.to_dict()
        assert d["step_number"] == 0
        assert d["content"] == ""
        assert d["tool_params"] == {}
        assert d["tool_result"] == {}

    def test_mutable_step_number(self):
        step = ReActStep()
        step.step_number = 5
        assert step.step_number == 5

    def test_mutable_content(self):
        step = ReActStep()
        step.content = "updated"
        assert step.content == "updated"


# ══════════════════════════════════════════════════════════════════
# 4. REACT RESULT DATACLASS
# ══════════════════════════════════════════════════════════════════


class TestReActResult:
    """Test ReActResult dataclass."""

    def test_default_values(self):
        result = ReActResult()
        assert result.thought_chain == []
        assert result.actions_taken == []
        assert result.observations == []
        assert result.final_answer == ""
        assert result.iterations_used == 0
        assert result.steps_applied == []
        assert result.tools_used == []

    def test_custom_values(self):
        result = ReActResult(
            thought_chain=["Need info", "Got info"],
            actions_taken=["tool_call"],
            observations=["Order shipped"],
            final_answer="Your order is shipped.",
            iterations_used=1,
            steps_applied=["thought_analysis", "action_tool_call"],
            tools_used=["order_status_check"],
        )
        assert len(result.thought_chain) == 2
        assert result.final_answer == "Your order is shipped."
        assert result.iterations_used == 1
        assert len(result.tools_used) == 1

    def test_to_dict(self):
        result = ReActResult(
            thought_chain=["t1"],
            actions_taken=["a1"],
            observations=["o1"],
            final_answer="ans",
            iterations_used=1,
            steps_applied=["s1"],
            tools_used=["tool1"],
        )
        d = result.to_dict()
        assert d["thought_chain"] == ["t1"]
        assert d["actions_taken"] == ["a1"]
        assert d["observations"] == ["o1"]
        assert d["final_answer"] == "ans"
        assert d["iterations_used"] == 1
        assert d["steps_applied"] == ["s1"]
        assert d["tools_used"] == ["tool1"]

    def test_to_dict_defaults(self):
        result = ReActResult()
        d = result.to_dict()
        assert d["thought_chain"] == []
        assert d["final_answer"] == ""
        assert d["iterations_used"] == 0

    def test_mutable_fields(self):
        result = ReActResult()
        result.thought_chain.append("new thought")
        result.tools_used.append("new_tool")
        assert len(result.thought_chain) == 1
        assert len(result.tools_used) == 1


# ══════════════════════════════════════════════════════════════════
# 5. QUERY CATEGORY DETECTION
# ══════════════════════════════════════════════════════════════════


class TestQueryCategoryDetection:
    """Test query category detection logic."""

    def test_order_reference_ord_prefix(self, processor):
        cats = processor._detect_query_categories("Where is my order ORD-123?")
        assert "order_reference" in cats

    def test_order_reference_ord_no_dash(self, processor):
        cats = processor._detect_query_categories("ORD123 status")
        assert "order_reference" in cats

    def test_order_reference_hash(self, processor):
        cats = processor._detect_query_categories("Status of #12345")
        assert "order_reference" in cats

    def test_order_reference_word_order(self, processor):
        cats = processor._detect_query_categories("What is my order number 456?")
        assert "order_reference" in cats

    def test_customer_reference(self, processor):
        cats = processor._detect_query_categories("Check customer CUST-001")
        assert "account_reference" in cats

    def test_account_reference(self, processor):
        cats = processor._detect_query_categories("My account #ACCT-99")
        assert "account_reference" in cats

    def test_user_reference(self, processor):
        cats = processor._detect_query_categories("User #123 profile")
        assert "account_reference" in cats

    def test_billing_query(self, processor):
        cats = processor._detect_query_categories("Why was I charged $50?")
        assert "billing_query" in cats

    def test_subscription_query(self, processor):
        cats = processor._detect_query_categories("How do I upgrade my plan?")
        assert "billing_query" in cats

    def test_refund_query(self, processor):
        cats = processor._detect_query_categories("I want a refund")
        assert "billing_query" in cats

    def test_technical_issue(self, processor):
        cats = processor._detect_query_categories("The app keeps crashing")
        assert "technical_issue" in cats

    def test_technical_issue_login(self, processor):
        cats = processor._detect_query_categories("Cannot login to my account")
        assert "technical_issue" in cats

    def test_technical_issue_api(self, processor):
        cats = processor._detect_query_categories("API webhook not working")
        assert "technical_issue" in cats

    def test_policy_faq(self, processor):
        cats = processor._detect_query_categories("What is your return policy?")
        assert "policy_faq" in cats

    def test_policy_how_to(self, processor):
        cats = processor._detect_query_categories("How to reset my password?")
        assert "policy_faq" in cats

    def test_past_issue(self, processor):
        cats = processor._detect_query_categories("This happened before")
        assert "past_issue" in cats

    def test_past_issue_ticket(self, processor):
        cats = processor._detect_query_categories("Ticket #456 was not resolved")
        assert "past_issue" in cats

    def test_multiple_categories(self, processor):
        cats = processor._detect_query_categories(
            "My order ORD-123 was charged incorrectly, and this happened before"
        )
        assert "order_reference" in cats
        assert "billing_query" in cats
        assert "past_issue" in cats

    def test_no_categories(self, processor):
        cats = processor._detect_query_categories("Hello there")
        assert cats == []

    def test_empty_query(self, processor):
        cats = processor._detect_query_categories("")
        assert cats == []

    def test_none_query(self, processor):
        cats = processor._detect_query_categories("")  # None becomes empty handled
        assert cats == []


# ══════════════════════════════════════════════════════════════════
# 6. THOUGHT GENERATION
# ══════════════════════════════════════════════════════════════════


class TestThoughtGeneration:
    """Test thought generation per query type."""

    @pytest.mark.asyncio
    async def test_order_thought(self, processor):
        thought = await processor.generate_thought("Where is ORD-456?")
        assert "order" in thought.lower()
        assert "ORD" in thought or "order_status" in thought

    @pytest.mark.asyncio
    async def test_billing_thought(self, processor):
        thought = await processor.generate_thought("Why was I charged?")
        assert "billing" in thought.lower() or "payment" in thought.lower()

    @pytest.mark.asyncio
    async def test_technical_thought(self, processor):
        thought = await processor.generate_thought("The app is crashing")
        assert "technical" in thought.lower() or "troubleshoot" in thought.lower()

    @pytest.mark.asyncio
    async def test_policy_thought(self, processor):
        thought = await processor.generate_thought("What is your return policy?")
        assert "knowledge" in thought.lower() or "policy" in thought.lower()

    @pytest.mark.asyncio
    async def test_customer_thought(self, processor):
        thought = await processor.generate_thought("Look up customer CUST-001")
        assert "customer" in thought.lower() or "account" in thought.lower()

    @pytest.mark.asyncio
    async def test_past_issue_thought(self, processor):
        thought = await processor.generate_thought(
            "This happened before with ticket #123"
        )
        assert "past" in thought.lower() or "ticket" in thought.lower()

    @pytest.mark.asyncio
    async def test_generic_thought(self, processor):
        thought = await processor.generate_thought("Hello world")
        assert "no specific" in thought.lower() or "knowledge" in thought.lower()

    @pytest.mark.asyncio
    async def test_thought_includes_tools(self, processor):
        thought = await processor.generate_thought("Where is ORD-456?")
        assert "tool" in thought.lower()

    @pytest.mark.asyncio
    async def test_thought_includes_query(self, processor):
        thought = await processor.generate_thought("My special query")
        assert "My special query" in thought


# ══════════════════════════════════════════════════════════════════
# 7. TOOL SELECTION
# ══════════════════════════════════════════════════════════════════


class TestToolSelection:
    """Test tool selection logic."""

    @pytest.mark.asyncio
    async def test_order_selects_order_tool(self, processor):
        processor._last_query = "Where is ORD-123?"
        action = await processor.select_action(
            "Where is ORD-123?",
            ["order_reference"],
        )
        assert action["action_type"] == "tool_call"
        assert action["tool_name"] == "order_status_check"
        assert "order_id" in action["params"]

    @pytest.mark.asyncio
    async def test_customer_selects_customer_tool(self, processor):
        processor._last_query = "Look up customer CUST-001"
        action = await processor.select_action(
            "Look up customer CUST-001",
            ["account_reference"],
        )
        assert action["tool_name"] == "customer_lookup"
        assert "customer_id" in action["params"]

    @pytest.mark.asyncio
    async def test_billing_selects_kb_tool(self, processor):
        processor._last_query = "Why was I charged?"
        action = await processor.select_action(
            "Why was I charged?",
            ["billing_query"],
        )
        assert action["tool_name"] == "knowledge_base_search"
        assert "query" in action["params"]

    @pytest.mark.asyncio
    async def test_technical_selects_kb_tool(self, processor):
        processor._last_query = "App keeps crashing"
        action = await processor.select_action(
            "App keeps crashing",
            ["technical_issue"],
        )
        assert action["tool_name"] == "knowledge_base_search"

    @pytest.mark.asyncio
    async def test_policy_selects_kb_tool(self, processor):
        processor._last_query = "What is the refund policy?"
        action = await processor.select_action(
            "What is the refund policy?",
            ["policy_faq"],
        )
        assert action["tool_name"] == "knowledge_base_search"

    @pytest.mark.asyncio
    async def test_past_issue_selects_ticket_tool(self, processor):
        processor._last_query = "This happened before"
        action = await processor.select_action(
            "This happened before",
            ["past_issue"],
        )
        assert action["tool_name"] == "ticket_history_search"

    @pytest.mark.asyncio
    async def test_empty_categories_defaults_to_kb(self, processor):
        processor._last_query = "Hello"
        action = await processor.select_action("Hello", [])
        assert action["action_type"] == "tool_call"
        assert action["tool_name"] == "knowledge_base_search"

    @pytest.mark.asyncio
    async def test_primary_tool_from_multiple(self, processor):
        processor._last_query = "Order ORD-1 was overcharged"
        action = await processor.select_action(
            "Order ORD-1 was overcharged",
            ["order_reference", "billing_query"],
        )
        assert action["action_type"] == "tool_call"
        # Should select one of the tools for order or billing
        assert action["tool_name"] in (
            "order_status_check",
            "knowledge_base_search",
        )


# ══════════════════════════════════════════════════════════════════
# 8. OBSERVATION PROCESSING
# ══════════════════════════════════════════════════════════════════


class TestObservationProcessing:
    """Test observation processing from tool results."""

    @pytest.mark.asyncio
    async def test_kb_search_with_results(self, processor):
        result = _make_tool_result(
            tool="knowledge_base_search",
            data={
                "query": "refund policy",
                "results": [{"title": "Refund Policy"}],
                "total": 1,
                "message": "",
            },
        )
        obs = await processor.process_observation("knowledge_base_search", result)
        assert "1 result" in obs

    @pytest.mark.asyncio
    async def test_kb_search_no_results(self, processor):
        result = _make_tool_result(
            tool="knowledge_base_search",
            data={
                "query": "xyz",
                "results": [],
                "total": 0,
                "message": "No matches",
            },
        )
        obs = await processor.process_observation("knowledge_base_search", result)
        assert "0 results" in obs

    @pytest.mark.asyncio
    async def test_customer_lookup_with_data(self, processor):
        result = _make_tool_result(
            tool="customer_lookup",
            data={
                "customer_id": "CUST-001",
                "name": "John Doe",
                "tier": "pro",
                "status": "active",
                "message": "",
            },
        )
        obs = await processor.process_observation("customer_lookup", result)
        assert "CUST-001" in obs
        assert "John Doe" in obs

    @pytest.mark.asyncio
    async def test_ticket_history_with_results(self, processor):
        result = _make_tool_result(
            tool="ticket_history_search",
            data={
                "query": "login issue",
                "tickets": [{"id": "T-1"}],
                "total": 1,
                "message": "",
            },
        )
        obs = await processor.process_observation("ticket_history_search", result)
        assert "1 result" in obs
        assert "past tickets" in obs.lower() or "relevant" in obs.lower()

    @pytest.mark.asyncio
    async def test_order_status_with_data(self, processor):
        result = _make_tool_result(
            tool="order_status_check",
            data={
                "order_id": "ORD-123",
                "status": "shipped",
                "tracking_number": "1Z999",
                "estimated_delivery": "2024-03-01",
                "message": "",
            },
        )
        obs = await processor.process_observation("order_status_check", result)
        assert "ORD-123" in obs
        assert "shipped" in obs

    @pytest.mark.asyncio
    async def test_error_result(self, processor):
        result = {"success": False, "error": "Tool timeout"}
        obs = await processor.process_observation("some_tool", result)
        assert "error" in obs.lower()
        assert "Tool timeout" in obs

    @pytest.mark.asyncio
    async def test_empty_result(self, processor):
        obs = await processor.process_observation("some_tool", {})
        assert "no results" in obs.lower()

    @pytest.mark.asyncio
    async def test_unknown_tool_type(self, processor):
        result = _make_tool_result(
            tool="unknown_tool",
            data={"message": "Custom result"},
        )
        obs = await processor.process_observation("unknown_tool", result)
        assert "unknown_tool" in obs

    @pytest.mark.asyncio
    async def test_kb_search_with_message(self, processor):
        result = _make_tool_result(
            tool="knowledge_base_search",
            data={
                "query": "test",
                "results": [],
                "total": 0,
                "message": "RAG retrieval placeholder",
            },
        )
        obs = await processor.process_observation("knowledge_base_search", result)
        assert "0 results" in obs


# ══════════════════════════════════════════════════════════════════
# 9. REASONING ABOUT OBSERVATIONS
# ══════════════════════════════════════════════════════════════════


class TestReasoningAboutObservations:
    """Test thought reasoning about observation context."""

    @pytest.mark.asyncio
    async def test_error_observation_continues(self, processor):
        thought = await processor.reason_about_observation(
            "query",
            "Tool reported an error.",
            ["billing"],
            0,
        )
        assert "alternative" in thought.lower() or "different" in thought.lower()

    @pytest.mark.asyncio
    async def test_error_observation_final_iteration(self, processor):
        thought = await processor.reason_about_observation(
            "query",
            "Tool reported an error.",
            ["billing"],
            processor.config.max_iterations - 1,
        )
        assert "synthesize" in thought.lower() or "best possible" in thought.lower()

    @pytest.mark.asyncio
    async def test_no_results_continues(self, processor):
        thought = await processor.reason_about_observation(
            "query",
            "returned 0 results.",
            ["policy_faq"],
            0,
        )
        assert "broaden" in thought.lower() or "different" in thought.lower()

    @pytest.mark.asyncio
    async def test_useful_data_more_categories(self, processor):
        thought = await processor.reason_about_observation(
            "query",
            "Knowledge base returned 5 results.",
            ["policy_faq", "billing_query"],
            0,
        )
        assert (
            "additional categories" in thought.lower() or "more data" in thought.lower()
        )

    @pytest.mark.asyncio
    async def test_sufficient_data_ready(self, processor):
        thought = await processor.reason_about_observation(
            "query",
            "Order found: shipped via FedEx.",
            ["order_reference"],
            1,
        )
        assert "sufficient" in thought.lower() or "synthesize" in thought.lower()

    @pytest.mark.asyncio
    async def test_empty_observation(self, processor):
        thought = await processor.reason_about_observation(
            "query",
            "",
            ["billing"],
            0,
        )
        assert "error" in thought.lower() or "limited" in thought.lower()


# ══════════════════════════════════════════════════════════════════
# 10. FINAL ANSWER SYNTHESIS
# ══════════════════════════════════════════════════════════════════


class TestFinalAnswerSynthesis:
    """Test final answer synthesis from observations."""

    @pytest.mark.asyncio
    async def test_order_answer(self, processor):
        answer = await processor.synthesize_final_answer(
            "Where is ORD-123?",
            [],
            ["Order ORD-123 is shipped"],
            ["order_reference"],
        )
        assert "order" in answer.lower()

    @pytest.mark.asyncio
    async def test_billing_answer(self, processor):
        answer = await processor.synthesize_final_answer(
            "Why was I charged?",
            [],
            ["Billing info retrieved"],
            ["billing_query"],
        )
        assert "billing" in answer.lower()

    @pytest.mark.asyncio
    async def test_technical_answer(self, processor):
        answer = await processor.synthesize_final_answer(
            "App is crashing",
            [],
            ["Troubleshooting steps found"],
            ["technical_issue"],
        )
        assert "troubleshooting" in answer.lower()

    @pytest.mark.asyncio
    async def test_account_answer(self, processor):
        answer = await processor.synthesize_final_answer(
            "Check my account",
            [],
            ["Customer info found"],
            ["account_reference"],
        )
        assert "account" in answer.lower()

    @pytest.mark.asyncio
    async def test_past_issue_answer(self, processor):
        answer = await processor.synthesize_final_answer(
            "This happened before",
            [],
            ["Past tickets found"],
            ["past_issue"],
        )
        assert "past" in answer.lower() or "ticket" in answer.lower()

    @pytest.mark.asyncio
    async def test_generic_answer(self, processor):
        answer = await processor.synthesize_final_answer(
            "Hello",
            [],
            ["Some info"],
            [],
        )
        assert "information" in answer.lower()

    @pytest.mark.asyncio
    async def test_no_observations(self, processor):
        answer = await processor.synthesize_final_answer(
            "Some query",
            [],
            [],
            [],
        )
        assert "help" in answer.lower() or "search" in answer.lower()

    @pytest.mark.asyncio
    async def test_multiple_observations(self, processor):
        answer = await processor.synthesize_final_answer(
            "Query",
            [],
            ["Obs1: order shipped", "Obs2: billing info"],
            ["order_reference", "billing_query"],
        )
        assert "key findings" in answer.lower() or "|" in answer

    @pytest.mark.asyncio
    async def test_answer_includes_query_reference(self, processor):
        answer = await processor.synthesize_final_answer(
            "My special question",
            [],
            ["Info found"],
            ["policy_faq"],
        )
        assert "clarify" in answer.lower()


# ══════════════════════════════════════════════════════════════════
# 11. ID EXTRACTION
# ══════════════════════════════════════════════════════════════════


class TestIdExtraction:
    """Test order ID and customer ID extraction."""

    def test_extract_order_id_ord_dash(self):
        result = ReActProcessor._extract_order_id("Where is ORD-123?")
        assert result == "123"

    def test_extract_order_id_ord_underscore(self):
        result = ReActProcessor._extract_order_id("ORD_456 status")
        assert result == "456"

    def test_extract_order_id_hash(self):
        result = ReActProcessor._extract_order_id("Status of #7890")
        assert result == "7890"

    def test_extract_order_id_none(self):
        result = ReActProcessor._extract_order_id("Hello there")
        assert result is None

    def test_extract_order_id_empty(self):
        result = ReActProcessor._extract_order_id("")
        assert result is None

    def test_extract_customer_id_cust_dash(self):
        result = ReActProcessor._extract_customer_id("Look up CUST-001")
        assert result == "001"

    def test_extract_customer_id_account(self):
        result = ReActProcessor._extract_customer_id("Account #ACCT-99")
        assert result is not None
        assert "ACCT" in result

    def test_extract_customer_id_none(self):
        result = ReActProcessor._extract_customer_id("No ID here")
        assert result is None

    def test_extract_customer_id_empty(self):
        result = ReActProcessor._extract_customer_id("")
        assert result is None


# ══════════════════════════════════════════════════════════════════
# 12. REACT LOOP CONTINUATION
# ══════════════════════════════════════════════════════════════════


class TestLoopContinuation:
    """Test _should_continue logic."""

    def test_max_iterations_reached(self, processor):
        thought = "Need more info"
        assert (
            processor._should_continue(
                thought,
                3,
                ["billing"],
                set(),
            )
            is False
        )

    def test_max_iterations_custom(self, custom_config, mock_registry):
        proc = ReActProcessor(config=custom_config, tool_registry=mock_registry)
        assert (
            proc._should_continue(
                "Need more info",
                2,
                ["billing"],
                set(),
            )
            is False
        )

    def test_sufficient_thought_continues(self, processor):
        thought = "Sufficient information gathered. Ready to synthesize."
        assert (
            processor._should_continue(
                thought,
                0,
                ["billing"],
                {"knowledge_base_search"},
            )
            is True
        )

    def test_remaining_tools_continues(self, processor):
        thought = "Need more context"
        assert (
            processor._should_continue(
                thought,
                0,
                ["billing", "past_issue"],
                {"knowledge_base_search"},
            )
            is True
        )

    def test_no_remaining_tools_stops(self, processor):
        thought = "Need more context"
        assert (
            processor._should_continue(
                thought,
                0,
                ["billing"],
                {"knowledge_base_search"},
            )
            is False
        )

    def test_within_max_iterations_with_tools(self, processor):
        thought = "Need more data"
        assert (
            processor._should_continue(
                thought,
                0,
                ["billing", "order_reference"],
                set(),
            )
            is True
        )


# ══════════════════════════════════════════════════════════════════
# 13. FULL REACT LOOP EXECUTION
# ══════════════════════════════════════════════════════════════════


class TestReActLoopExecution:
    """Test full ReAct loop with mocked ToolRegistry."""

    @pytest.mark.asyncio
    async def test_basic_order_query(self, processor):
        result = await processor.process("Where is my order ORD-123?")
        assert result.iterations_used >= 1
        assert "thought_analysis" in result.steps_applied
        assert "final_answer_synthesis" in result.steps_applied
        assert len(result.thought_chain) >= 1
        assert len(result.actions_taken) >= 1

    @pytest.mark.asyncio
    async def test_billing_query(self, processor):
        result = await processor.process("Why was I charged $50?")
        assert result.iterations_used >= 1
        assert "knowledge_base_search" in result.tools_used

    @pytest.mark.asyncio
    async def test_technical_query(self, processor):
        result = await processor.process("The app keeps crashing on login")
        assert result.iterations_used >= 1
        assert "final_answer_synthesis" in result.steps_applied

    @pytest.mark.asyncio
    async def test_generic_query(self, processor):
        result = await processor.process("Hello, I need help")
        assert result.iterations_used >= 1
        assert result.final_answer != ""

    @pytest.mark.asyncio
    async def test_empty_query(self, processor):
        result = await processor.process("")
        assert result.steps_applied == ["empty_input"]
        assert result.final_answer == ""
        assert result.iterations_used == 0

    @pytest.mark.asyncio
    async def test_whitespace_query(self, processor):
        result = await processor.process("   ")
        assert result.steps_applied == ["empty_input"]

    @pytest.mark.asyncio
    async def test_result_has_tools_used(self, processor):
        result = await processor.process("Check order ORD-999")
        assert isinstance(result.tools_used, list)

    @pytest.mark.asyncio
    async def test_result_has_observations(self, processor):
        result = await processor.process("Check order ORD-999")
        assert isinstance(result.observations, list)

    @pytest.mark.asyncio
    async def test_result_to_dict(self, processor):
        result = await processor.process("Order ORD-123?")
        d = result.to_dict()
        assert "thought_chain" in d
        assert "actions_taken" in d
        assert "observations" in d
        assert "final_answer" in d
        assert "iterations_used" in d
        assert "steps_applied" in d
        assert "tools_used" in d

    @pytest.mark.asyncio
    async def test_tool_called_with_company_id(self, processor):
        await processor.process("Where is ORD-123?")
        # The mock registry should have been called
        processor.tool_registry.execute_tool.assert_called()
        # Check company_id was passed
        call_args = processor.tool_registry.execute_tool.call_args
        assert call_args[1]["company_id"] == COMPANY_ID

    @pytest.mark.asyncio
    async def test_tool_called_with_timeout(self, processor):
        await processor.process("Where is ORD-123?")
        call_args = processor.tool_registry.execute_tool.call_args
        assert "timeout" in call_args[1]


# ══════════════════════════════════════════════════════════════════
# 14. MAX ITERATIONS ENFORCEMENT
# ══════════════════════════════════════════════════════════════════


class TestMaxIterations:
    """Test max iterations enforcement."""

    @pytest.mark.asyncio
    async def test_default_max_iterations(self, processor):
        result = await processor.process(
            "Complex multi-faceted query with orders billing and past issues"
        )
        assert result.iterations_used <= 3

    @pytest.mark.asyncio
    async def test_custom_max_iterations(self, custom_config, mock_registry):
        proc = ReActProcessor(config=custom_config, tool_registry=mock_registry)
        result = await proc.process("Order ORD-1 and billing question")
        assert result.iterations_used <= 2

    @pytest.mark.asyncio
    async def test_max_iterations_one(self, mock_registry):
        config = ReActConfig(company_id=COMPANY_ID, max_iterations=1)
        proc = ReActProcessor(config=config, tool_registry=mock_registry)
        result = await proc.process("Order ORD-1 billing question past issue")
        assert result.iterations_used <= 1

    @pytest.mark.asyncio
    async def test_max_iterations_respected_multiple_tools(self, processor):
        """Even with many categories, iterations don't exceed max."""
        result = await processor.process(
            "Order ORD-123 customer CUST-456 billing charge "
            "happened before with ticket T-789 app crash"
        )
        assert result.iterations_used <= 3


# ══════════════════════════════════════════════════════════════════
# 15. COMPANY ISOLATION (BC-001)
# ══════════════════════════════════════════════════════════════════


class TestCompanyIsolation:
    """Test BC-001 company isolation."""

    @pytest.mark.asyncio
    async def test_processor_uses_config_company_id(self, mock_registry):
        config = ReActConfig(company_id=OTHER_COMPANY)
        proc = ReActProcessor(config=config, tool_registry=mock_registry)
        await proc.process("Where is ORD-123?")
        call_args = proc.tool_registry.execute_tool.call_args
        assert call_args[1]["company_id"] == OTHER_COMPANY

    @pytest.mark.asyncio
    async def test_node_uses_state_company_id(self, mock_registry):
        state = _make_state(
            query="Order ORD-123?",
            external_data_required=True,
            company_id=OTHER_COMPANY,
        )
        node = ReActNode(
            config=ReActConfig(company_id="default-co"),
            tool_registry=mock_registry,
        )
        await node.execute(state)
        call_args = mock_registry.execute_tool.call_args
        assert call_args[1]["company_id"] == OTHER_COMPANY

    @pytest.mark.asyncio
    async def test_node_falls_back_to_config_company_id(self, mock_registry):
        state = _make_state(
            query="Order ORD-123?",
            external_data_required=True,
            company_id="",  # No state company_id
        )
        node = ReActNode(
            config=ReActConfig(company_id=COMPANY_ID),
            tool_registry=mock_registry,
        )
        await node.execute(state)
        call_args = mock_registry.execute_tool.call_args
        assert call_args[1]["company_id"] == COMPANY_ID


# ══════════════════════════════════════════════════════════════════
# 16. SHOULD ACTIVATE
# ══════════════════════════════════════════════════════════════════


class TestShouldActivate:
    """Test ReActNode.should_activate."""

    @pytest.mark.asyncio
    async def test_activates_when_external_data_required(self, node):
        state = _make_state(external_data_required=True)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_not_activates_when_no_external_data(self, node):
        state = _make_state(external_data_required=False)
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_activates_with_default_signals(self, node):
        """Default QuerySignals has external_data_required=False."""
        state = ConversationState(query="test")
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_activates_regardless_of_other_signals(self, node):
        state = _make_state(
            external_data_required=True,
            confidence_score=0.9,
            sentiment_score=0.9,
            query_complexity=0.1,
        )
        assert await node.should_activate(state) is True


# ══════════════════════════════════════════════════════════════════
# 17. NODE EXECUTION
# ══════════════════════════════════════════════════════════════════


class TestNodeExecution:
    """Test ReActNode.execute."""

    @pytest.mark.asyncio
    async def test_execute_updates_response_parts(self, node):
        state = _make_state(query="Where is ORD-123?")
        result_state = await node.execute(state)
        assert len(result_state.response_parts) >= 1

    @pytest.mark.asyncio
    async def test_execute_records_result(self, node):
        state = _make_state(query="Where is ORD-123?")
        result_state = await node.execute(state)
        assert TechniqueID.REACT.value in result_state.technique_results

    @pytest.mark.asyncio
    async def test_execute_result_has_status(self, node):
        state = _make_state(query="Where is ORD-123?")
        result_state = await node.execute(state)
        react_result = result_state.technique_results[TechniqueID.REACT.value]
        assert react_result["status"] == "success"

    @pytest.mark.asyncio
    async def test_technique_id_property(self, node):
        assert node.technique_id == TechniqueID.REACT

    @pytest.mark.asyncio
    async def test_extends_base_node(self, node):
        assert isinstance(node, BaseTechniqueNode)


# ══════════════════════════════════════════════════════════════════
# 18. ERROR FALLBACK (BC-008)
# ══════════════════════════════════════════════════════════════════


class TestErrorFallback:
    """Test BC-008 never crash behavior."""

    @pytest.mark.asyncio
    async def test_processor_never_crashes_on_tool_error(self, default_config):
        """Processor handles tool errors gracefully."""
        registry = ToolRegistry()
        registry.execute_tool = AsyncMock(
            return_value={"success": False, "error": "Tool crashed"},
        )
        proc = ReActProcessor(config=default_config, tool_registry=registry)
        result = await proc.process("Where is ORD-123?")
        assert "error_fallback" not in result.steps_applied
        # Should still produce a result
        assert result.iterations_used >= 1

    @pytest.mark.asyncio
    async def test_processor_handles_exception_in_process(self, default_config):
        """Processor catches internal exceptions."""
        registry = ToolRegistry()
        registry.execute_tool = AsyncMock(
            side_effect=RuntimeError("Unexpected crash"),
        )
        proc = ReActProcessor(config=default_config, tool_registry=registry)
        result = await proc.process("Where is ORD-123?")
        assert "error_fallback" in result.steps_applied

    @pytest.mark.asyncio
    async def test_node_never_crashes(self, mock_registry):
        """Node execute never crashes even on tool errors."""
        mock_registry.execute_tool = AsyncMock(
            side_effect=RuntimeError("Tool exploded"),
        )
        node = ReActNode(
            config=ReActConfig(company_id=COMPANY_ID),
            tool_registry=mock_registry,
        )
        state = _make_state(query="Where is ORD-123?")
        result_state = await node.execute(state)
        # Should return state (possibly original or with skip recorded)
        assert result_state is not None
        assert isinstance(result_state, ConversationState)

    @pytest.mark.asyncio
    async def test_node_records_skip_on_error(self, mock_registry):
        """Node records skip when execution fails."""
        mock_registry.execute_tool = AsyncMock(
            side_effect=RuntimeError("Tool exploded"),
        )
        node = ReActNode(
            config=ReActConfig(company_id=COMPANY_ID),
            tool_registry=mock_registry,
        )
        state = _make_state(query="Where is ORD-123?")
        result_state = await node.execute(state)
        react_result = result_state.technique_results.get(TechniqueID.REACT.value)
        # Either error recording or skip recording
        assert react_result is not None


# ══════════════════════════════════════════════════════════════════
# 19. EDGE CASES
# ══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test various edge cases."""

    @pytest.mark.asyncio
    async def test_very_long_query(self, processor):
        long_query = "Where is " + "my order ORD-123 " * 100
        result = await processor.process(long_query)
        assert result.iterations_used >= 1

    @pytest.mark.asyncio
    async def test_special_characters_in_query(self, processor):
        result = await processor.process("Order <script>alert(1)</script> status?")
        assert result.iterations_used >= 1

    @pytest.mark.asyncio
    async def test_unicode_query(self, processor):
        result = await processor.process("Comment puis-je annuler? 😊")
        assert result.iterations_used >= 1

    @pytest.mark.asyncio
    async def test_single_word_query(self, processor):
        result = await processor.process("help")
        assert result.iterations_used >= 1

    @pytest.mark.asyncio
    async def test_null_state_company_id(self, mock_registry):
        """Node handles None company_id in state."""
        state = _make_state(company_id="")
        node = ReActNode(
            config=ReActConfig(company_id=COMPANY_ID),
            tool_registry=mock_registry,
        )
        result_state = await node.execute(state)
        assert result_state is not None

    @pytest.mark.asyncio
    async def test_no_tools_in_registry(self, default_config):
        """Processor handles empty tool registry."""
        empty_registry = ToolRegistry()
        proc = ReActProcessor(config=default_config, tool_registry=empty_registry)
        result = await proc.process("Where is ORD-123?")
        assert result.iterations_used >= 1

    @pytest.mark.asyncio
    async def test_unknown_tool_in_registry(self, default_config):
        """Processor handles when registry returns unknown tool error."""
        registry = ToolRegistry()
        registry.execute_tool = AsyncMock(
            return_value={"success": False, "error": "Unknown tool: xyz"},
        )
        proc = ReActProcessor(config=default_config, tool_registry=registry)
        result = await proc.process("Where is ORD-123?")
        assert result.iterations_used >= 1

    @pytest.mark.asyncio
    async def test_tool_timeout(self, default_config):
        """Processor handles tool timeout."""
        import asyncio

        registry = ToolRegistry()
        registry.execute_tool = AsyncMock(
            side_effect=asyncio.TimeoutError(),
        )
        proc = ReActProcessor(config=default_config, tool_registry=registry)
        result = await proc.process("Where is ORD-123?")
        # Should handle gracefully
        assert "error_fallback" in result.steps_applied

    @pytest.mark.asyncio
    async def test_multiple_calls_independent(self, processor):
        """Multiple process calls don't interfere."""
        r1 = await processor.process("Where is ORD-1?")
        r2 = await processor.process("Why was I charged?")
        assert r1.tools_used != r2.tools_used or len(r1.tools_used) == len(
            r2.tools_used
        )


# ══════════════════════════════════════════════════════════════════
# 20. TOOL SELECTION CATEGORIES MAPPING
# ══════════════════════════════════════════════════════════════════


class TestToolSelectionMapping:
    """Test _select_tools_for_categories internal method."""

    def test_order_category_maps_to_order_tool(self, processor):
        processor._last_query = "ORD-123"
        calls = processor._select_tools_for_categories(["order_reference"])
        assert len(calls) >= 1
        assert calls[0]["tool_name"] == "order_status_check"

    def test_customer_category_maps_to_customer_tool(self, processor):
        processor._last_query = "CUST-001"
        calls = processor._select_tools_for_categories(["account_reference"])
        assert calls[0]["tool_name"] == "customer_lookup"

    def test_billing_category_maps_to_kb(self, processor):
        processor._last_query = "billing question"
        calls = processor._select_tools_for_categories(["billing_query"])
        assert calls[0]["tool_name"] == "knowledge_base_search"

    def test_technical_category_maps_to_kb(self, processor):
        processor._last_query = "app crash"
        calls = processor._select_tools_for_categories(["technical_issue"])
        assert calls[0]["tool_name"] == "knowledge_base_search"

    def test_policy_category_maps_to_kb(self, processor):
        processor._last_query = "refund policy"
        calls = processor._select_tools_for_categories(["policy_faq"])
        assert calls[0]["tool_name"] == "knowledge_base_search"

    def test_past_issue_category_maps_to_ticket(self, processor):
        processor._last_query = "happened before"
        calls = processor._select_tools_for_categories(["past_issue"])
        assert calls[0]["tool_name"] == "ticket_history_search"

    def test_empty_categories_defaults_to_kb(self, processor):
        processor._last_query = "hello"
        calls = processor._select_tools_for_categories([])
        assert len(calls) == 1
        assert calls[0]["tool_name"] == "knowledge_base_search"

    def test_multiple_categories_multiple_tools(self, processor):
        processor._last_query = "ORD-1 CUST-1"
        calls = processor._select_tools_for_categories(
            ["order_reference", "account_reference"],
        )
        tool_names = [c["tool_name"] for c in calls]
        assert "order_status_check" in tool_names
        assert "customer_lookup" in tool_names

    def test_duplicate_categories_not_repeated(self, processor):
        processor._last_query = "billing"
        calls = processor._select_tools_for_categories(
            ["billing_query", "technical_issue"],
        )
        # Both map to knowledge_base_search, should only appear once
        kb_count = sum(1 for c in calls if c["tool_name"] == "knowledge_base_search")
        assert kb_count == 1

    def test_order_params_have_order_id(self, processor):
        processor._last_query = "Where is ORD-456?"
        calls = processor._select_tools_for_categories(["order_reference"])
        assert "order_id" in calls[0]["params"]

    def test_customer_params_have_customer_id(self, processor):
        processor._last_query = "Look up CUST-789"
        calls = processor._select_tools_for_categories(["account_reference"])
        assert "customer_id" in calls[0]["params"]

    def test_kb_params_have_query(self, processor):
        processor._last_query = "What is the return policy?"
        calls = processor._select_tools_for_categories(["policy_faq"])
        assert "query" in calls[0]["params"]
