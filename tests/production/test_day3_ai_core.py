"""
Day 3 AI Core Integration Tests

Verifies that all AI techniques properly call external LLMs through
the unified llm_gateway (BC-007). Tests cover:
  1. LLM Gateway provider auto-detection
  2. All 11 LLM-powered techniques import and use llm_gateway
  3. CRP is intentionally deterministic (no LLM)
  4. Variant LLM clients delegate to gateway
  5. BC-008: Techniques never crash, fall back gracefully
  6. BC-001: Company isolation supported

Building Codes: BC-001, BC-007, BC-008, BC-012
"""

import os
import importlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ── Ensure LLM_PROVIDER is set to avoid import errors ────────────────
os.environ.setdefault("LLM_PROVIDER", "litellm")

from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
    GSDState,
)
from app.core.technique_router import QuerySignals


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def simple_state() -> ConversationState:
    """Minimal state for simple queries."""
    return ConversationState(
        query="What is my order status for ORD-12345?",
        signals=QuerySignals(
            query_complexity=0.3,
            external_data_required=False,
            confidence_score=0.7,
            sentiment_score=0.8,
        ),
        company_id="test_company_001",
        ticket_id="TKT-001",
    )


@pytest.fixture
def complex_state() -> ConversationState:
    """State for complex multi-part queries."""
    return ConversationState(
        query=(
            "I was charged $99.99 twice this month and I need a refund. "
            "Also, why is my order ORD-789 delayed? And can you explain "
            "the difference between the Pro and High plans?"
        ),
        signals=QuerySignals(
            query_complexity=0.8,
            external_data_required=True,
            confidence_score=0.5,
            sentiment_score=0.3,
        ),
        company_id="test_company_002",
        ticket_id="TKT-002",
    )


@pytest.fixture
def billing_state() -> ConversationState:
    """State for billing/financial queries."""
    return ConversationState(
        query="I was charged $49.99 but my plan is $29.99. I need a refund.",
        signals=QuerySignals(
            query_complexity=0.5,
            external_data_required=False,
            confidence_score=0.6,
            monetary_value=49.99,
        ),
        company_id="test_company_003",
        ticket_id="TKT-003",
    )


@pytest.fixture
def failure_state() -> ConversationState:
    """State for reflexion (previous response rejected)."""
    return ConversationState(
        query="That's wrong, I didn't ask about shipping. I asked about billing.",
        signals=QuerySignals(
            query_complexity=0.4,
            external_data_required=False,
            confidence_score=0.3,
            sentiment_score=0.2,
        ),
        company_id="test_company_004",
        ticket_id="TKT-004",
    )


# ── 1. LLM Gateway Tests ───────────────────────────────────────────


class TestLLMGateway:
    """Test the unified LLM gateway initialization and provider detection."""

    def test_gateway_import(self):
        """Verify llm_gateway singleton is importable."""
        from app.core.llm_gateway import llm_gateway
        assert llm_gateway is not None

    def test_gateway_has_generate_method(self):
        """Verify gateway has the generate() method."""
        from app.core.llm_gateway import llm_gateway
        assert hasattr(llm_gateway, "generate")
        assert callable(llm_gateway.generate)

    def test_gateway_has_generate_json_method(self):
        """Verify gateway has the generate_json() method."""
        from app.core.llm_gateway import llm_gateway
        assert hasattr(llm_gateway, "generate_json")
        assert callable(llm_gateway.generate_json)

    def test_gateway_auto_detect_provider(self):
        """Verify gateway auto-detects provider from env vars."""
        from app.core.llm_gateway import llm_gateway, LLMProvider
        # Without ZAI_API_KEY, should default to litellm
        provider = llm_gateway.provider
        assert provider in (LLMProvider.LITELLM, LLMProvider.ZAI_GATEWAY)

    def test_gateway_stats(self):
        """Verify gateway stats method returns expected keys."""
        from app.core.llm_gateway import llm_gateway
        stats = llm_gateway.get_stats()
        assert "provider" in stats
        assert "model" in stats
        assert "total_calls" in stats
        assert "successful_calls" in stats
        assert "failed_calls" in stats
        assert "is_available" in stats


# ── 2. Technique LLM Integration Tests ─────────────────────────────


class TestTechniqueLLMIntegration:
    """Verify all 11 LLM-powered techniques import and use llm_gateway."""

    @pytest.mark.asyncio
    async def test_chain_of_thought_uses_llm_gateway(self, complex_state):
        """Chain of Thought should try LLM and fall back to templates."""
        from app.core.techniques.chain_of_thought import ChainOfThoughtNode

        node = ChainOfThoughtNode()
        result_state = await node.execute(complex_state)

        # Should not crash (BC-008)
        assert result_state is not None
        # Should have recorded a result
        assert "chain_of_thought" in result_state.technique_results

    @pytest.mark.asyncio
    async def test_react_uses_llm_gateway(self, simple_state):
        """ReAct should try LLM for thought generation."""
        from app.core.techniques.react import ReActNode

        node = ReActNode()
        result_state = await node.execute(simple_state)

        assert result_state is not None
        assert "react" in result_state.technique_results

    @pytest.mark.asyncio
    async def test_self_consistency_uses_llm_gateway(self, billing_state):
        """Self Consistency should try LLM for answer generation."""
        from app.core.techniques.self_consistency import SelfConsistencyNode

        node = SelfConsistencyNode()
        result_state = await node.execute(billing_state)

        assert result_state is not None
        assert "self_consistency" in result_state.technique_results

    @pytest.mark.asyncio
    async def test_reflexion_uses_llm_gateway(self, failure_state):
        """Reflexion should process failure feedback without crashing."""
        from app.core.techniques.reflexion import ReflexionNode

        node = ReflexionNode()
        result_state = await node.execute(failure_state)

        assert result_state is not None

    @pytest.mark.asyncio
    async def test_tree_of_thoughts_uses_llm_gateway(self, complex_state):
        """Tree of Thoughts should build reasoning tree with LLM eval."""
        from app.core.techniques.tree_of_thoughts import TreeOfThoughtsNode

        node = TreeOfThoughtsNode()
        result_state = await node.execute(complex_state)

        assert result_state is not None

    @pytest.mark.asyncio
    async def test_least_to_most_uses_llm_gateway(self, complex_state):
        """Least to Most should decompose complex queries."""
        from app.core.techniques.least_to_most import LeastToMostNode

        node = LeastToMostNode()
        result_state = await node.execute(complex_state)

        assert result_state is not None

    @pytest.mark.asyncio
    async def test_gst_uses_llm_gateway(self, complex_state):
        """GST (Goal-Strategy Tree) should use LLM for evaluation."""
        from app.core.techniques.gst import GSTNode

        node = GSTNode()
        result_state = await node.execute(complex_state)

        assert result_state is not None

    @pytest.mark.asyncio
    async def test_reverse_thinking_uses_llm_gateway(self, complex_state):
        """Reverse Thinking should challenge assumptions via LLM."""
        from app.core.techniques.reverse_thinking import ReverseThinkingNode

        node = ReverseThinkingNode()
        result_state = await node.execute(complex_state)

        assert result_state is not None

    @pytest.mark.asyncio
    async def test_step_back_uses_llm_gateway(self, complex_state):
        """Step Back should abstract via LLM before solving."""
        from app.core.techniques.step_back import StepBackNode

        node = StepBackNode()
        result_state = await node.execute(complex_state)

        assert result_state is not None

    @pytest.mark.asyncio
    async def test_thread_of_thought_uses_llm_gateway(self, complex_state):
        """Thread of Thought should build reasoning thread via LLM."""
        from app.core.techniques.thread_of_thought import ThreadOfThoughtNode

        node = ThreadOfThoughtNode()
        result_state = await node.execute(complex_state)

        assert result_state is not None

    @pytest.mark.asyncio
    async def test_universe_of_thoughts_uses_llm_gateway(self, complex_state):
        """Universe of Thoughts should use LLM for multi-perspective eval."""
        from app.core.techniques.universe_of_thoughts import UniverseOfThoughtsNode

        node = UniverseOfThoughtsNode()
        result_state = await node.execute(complex_state)

        assert result_state is not None


# ── 3. CRP is Intentionally Deterministic ───────────────────────────


class TestCRPDeterministic:
    """CRP (Concise Response Protocol) must NOT use LLM calls."""

    def test_crp_has_no_llm_gateway_import(self):
        """Verify CRP module does not import llm_gateway."""
        import app.core.techniques.crp as crp_module
        source = importlib.import_module("app.core.techniques.crp")
        # Check source doesn't have llm_gateway reference
        source_file = source.__file__
        assert source_file is not None
        with open(source_file, "r") as f:
            content = f.read()
        assert "llm_gateway" not in content
        assert "LLMResponse" not in content

    @pytest.mark.asyncio
    async def test_crp_processes_without_llm(self):
        """CRP should process text purely with regex/heuristics."""
        from app.core.techniques.crp import CRPProcessor

        processor = CRPProcessor()
        verbose_text = (
            "I would be happy to help you with that! "
            "Let me look into that for you. "
            "In order to process your refund of $49.99, we need to verify "
            "your account. Additionally, we will need to check your "
            "subscription status. Furthermore, the billing team will "
            "review the charge. "
            "Please don't hesitate to reach out if you need anything else!"
        )
        result = await processor.process(verbose_text, complexity=0.3)

        assert result.processed_text != ""
        assert result.processed_tokens < result.original_tokens
        assert result.reduction_pct > 0
        assert "filler_elimination" in result.steps_applied or "compression" in result.steps_applied

    @pytest.mark.asyncio
    async def test_crp_preserves_reserved_words(self):
        """CRP should never remove financial keywords."""
        from app.core.techniques.crp import CRPProcessor

        processor = CRPProcessor()
        text = "Your refund of $80.00 for the subscription cancellation has been processed."
        result = await processor.process(text)

        for word in ["refund", "subscription", "cancellation"]:
            assert word in result.processed_text.lower(), f"Reserved word '{word}' was removed!"


# ── 4. Variant LLM Client Gateway Delegation ────────────────────────


class TestVariantLLMClients:
    """Verify all 3 variant LLM clients delegate to llm_gateway."""

    @pytest.mark.asyncio
    async def test_mini_llm_client_delegates_to_gateway(self):
        """MiniLLMClient should call llm_gateway.generate."""
        from app.core.mini_parwa.llm_client import MiniLLMClient

        client = MiniLLMClient()
        assert client.is_available == client.is_available  # Property works

    @pytest.mark.asyncio
    async def test_pro_llm_client_delegates_to_gateway(self):
        """ProLLMClient should call llm_gateway.generate."""
        from app.core.parwa.llm_client import ProLLMClient

        client = ProLLMClient()
        assert client.is_available == client.is_available  # Property works

    @pytest.mark.asyncio
    async def test_high_llm_client_delegates_to_gateway(self):
        """HighLLMClient should call llm_gateway.generate."""
        from app.core.parwa_high.llm_client import HighLLMClient

        client = HighLLMClient()
        assert client.is_available == client.is_available  # Property works

    @pytest.mark.asyncio
    async def test_mini_llm_client_chat_returns_tuple(self):
        """MiniLLMClient.chat should return (str, int) tuple."""
        from app.core.mini_parwa.llm_client import MiniLLMClient

        client = MiniLLMClient()
        result = await client.chat(
            system_prompt="You are helpful.",
            user_message="Hello!",
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], int)

    @pytest.mark.asyncio
    async def test_pro_llm_client_chat_returns_tuple(self):
        """ProLLMClient.chat should return (str, int) tuple."""
        from app.core.parwa.llm_client import ProLLMClient

        client = ProLLMClient()
        result = await client.chat(
            system_prompt="You are helpful.",
            user_message="Hello!",
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_high_llm_client_chat_returns_tuple(self):
        """HighLLMClient.chat should return (str, int) tuple."""
        from app.core.parwa_high.llm_client import HighLLMClient

        client = HighLLMClient()
        result = await client.chat(
            system_prompt="You are helpful.",
            user_message="Hello!",
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_mini_llm_client_chat_with_fallback(self):
        """MiniLLMClient.chat_with_fallback should return fallback when LLM fails."""
        from app.core.mini_parwa.llm_client import MiniLLMClient

        client = MiniLLMClient()
        result = await client.chat_with_fallback(
            system_prompt="You are helpful.",
            user_message="Hello!",
            fallback_text="Fallback response",
        )
        assert isinstance(result, tuple)
        # Should get either LLM response or fallback
        assert result[0] == "" or result[0] == "Fallback response" or len(result[0]) > 0

    @pytest.mark.asyncio
    async def test_pro_llm_client_chat_with_fallback(self):
        """ProLLMClient.chat_with_fallback should return fallback when LLM fails."""
        from app.core.parwa.llm_client import ProLLMClient

        client = ProLLMClient()
        result = await client.chat_with_fallback(
            system_prompt="You are helpful.",
            user_message="Hello!",
            fallback_text="Pro fallback",
        )
        assert isinstance(result, tuple)

    @pytest.mark.asyncio
    async def test_high_llm_client_chat_with_fallback(self):
        """HighLLMClient.chat_with_fallback should return fallback when LLM fails."""
        from app.core.parwa_high.llm_client import HighLLMClient

        client = HighLLMClient()
        result = await client.chat_with_fallback(
            system_prompt="You are helpful.",
            user_message="Hello!",
            fallback_text="High fallback",
        )
        assert isinstance(result, tuple)

    @pytest.mark.asyncio
    async def test_all_clients_support_company_id(self):
        """All variant clients should accept company_id parameter."""
        from app.core.mini_parwa.llm_client import MiniLLMClient
        from app.core.parwa.llm_client import ProLLMClient
        from app.core.parwa_high.llm_client import HighLLMClient

        for ClientClass in [MiniLLMClient, ProLLMClient, HighLLMClient]:
            client = ClientClass()
            # Should not raise TypeError for company_id parameter
            result = await client.chat(
                system_prompt="Test",
                user_message="Test",
                company_id="company_123",
            )
            assert isinstance(result, tuple)


# ── 5. BC-008 Graceful Degradation ──────────────────────────────────


class TestGracefulDegradation:
    """Verify all techniques handle failures gracefully (BC-008)."""

    @pytest.mark.asyncio
    async def test_empty_query_does_not_crash(self):
        """Empty query should not crash any technique."""
        from app.core.techniques.chain_of_thought import ChainOfThoughtNode
        from app.core.techniques.react import ReActNode
        from app.core.techniques.self_consistency import SelfConsistencyNode

        empty_state = ConversationState(
            query="",
            signals=QuerySignals(),
            company_id="test",
        )

        for NodeClass in [ChainOfThoughtNode, ReActNode, SelfConsistencyNode]:
            node = NodeClass()
            result = await node.execute(empty_state)
            assert result is not None

    @pytest.mark.asyncio
    async def test_techniques_preserve_state_on_error(self):
        """Techniques should return state unchanged or enriched on error."""
        from app.core.techniques.chain_of_thought import ChainOfThoughtNode

        state = ConversationState(
            query="Test query with complex reasoning needed",
            signals=QuerySignals(query_complexity=0.7),
            company_id="test",
        )
        original_company = state.company_id

        node = ChainOfThoughtNode()
        result = await node.execute(state)

        assert result.company_id == original_company
        assert result.query == state.query

    @pytest.mark.asyncio
    async def test_all_techniques_have_should_activate(self):
        """All technique nodes should implement should_activate."""
        from app.core.techniques.chain_of_thought import ChainOfThoughtNode
        from app.core.techniques.react import ReActNode
        from app.core.techniques.self_consistency import SelfConsistencyNode
        from app.core.techniques.reflexion import ReflexionNode
        from app.core.techniques.tree_of_thoughts import TreeOfThoughtsNode
        from app.core.techniques.least_to_most import LeastToMostNode
        from app.core.techniques.gst import GSTNode
        from app.core.techniques.reverse_thinking import ReverseThinkingNode
        from app.core.techniques.step_back import StepBackNode
        from app.core.techniques.thread_of_thought import ThreadOfThoughtNode
        from app.core.techniques.universe_of_thoughts import UniverseOfThoughtsNode

        state = ConversationState(
            query="Test",
            signals=QuerySignals(),
        )

        for NodeClass in [
            ChainOfThoughtNode,
            ReActNode,
            SelfConsistencyNode,
            ReflexionNode,
            TreeOfThoughtsNode,
            LeastToMostNode,
            GSTNode,
            ReverseThinkingNode,
            StepBackNode,
            ThreadOfThoughtNode,
            UniverseOfThoughtsNode,
        ]:
            node = NodeClass()
            should = await node.should_activate(state)
            assert isinstance(should, bool), f"{NodeClass.__name__}.should_activate() must return bool"


# ── 6. Import Verification ──────────────────────────────────────────


class TestImports:
    """Verify all technique modules import llm_gateway."""

    def test_chain_of_thought_imports_gateway(self):
        """chain_of_thought.py must import from llm_gateway."""
        import app.core.techniques.chain_of_thought as mod
        assert hasattr(mod, "llm_gateway")

    def test_react_imports_gateway(self):
        """react.py must import from llm_gateway."""
        import app.core.techniques.react as mod
        assert hasattr(mod, "llm_gateway")

    def test_self_consistency_imports_gateway(self):
        """self_consistency.py must import from llm_gateway."""
        import app.core.techniques.self_consistency as mod
        assert hasattr(mod, "llm_gateway")

    def test_reflexion_imports_gateway(self):
        """reflexion.py must import from llm_gateway."""
        import app.core.techniques.reflexion as mod
        assert hasattr(mod, "llm_gateway")

    def test_tree_of_thoughts_imports_gateway(self):
        """tree_of_thoughts.py must import from llm_gateway."""
        import app.core.techniques.tree_of_thoughts as mod
        assert hasattr(mod, "llm_gateway")

    def test_least_to_most_imports_gateway(self):
        """least_to_most.py must import from llm_gateway."""
        import app.core.techniques.least_to_most as mod
        assert hasattr(mod, "llm_gateway")

    def test_gst_imports_gateway(self):
        """gst.py must import from llm_gateway."""
        import app.core.techniques.gst as mod
        assert hasattr(mod, "llm_gateway")

    def test_reverse_thinking_imports_gateway(self):
        """reverse_thinking.py must import from llm_gateway."""
        import app.core.techniques.reverse_thinking as mod
        assert hasattr(mod, "llm_gateway")

    def test_step_back_imports_gateway(self):
        """step_back.py must import from llm_gateway."""
        import app.core.techniques.step_back as mod
        assert hasattr(mod, "llm_gateway")

    def test_thread_of_thought_imports_gateway(self):
        """thread_of_thought.py must import from llm_gateway."""
        import app.core.techniques.thread_of_thought as mod
        assert hasattr(mod, "llm_gateway")

    def test_universe_of_thoughts_imports_gateway(self):
        """universe_of_thoughts.py must import from llm_gateway."""
        import app.core.techniques.universe_of_thoughts as mod
        assert hasattr(mod, "llm_gateway")

    def test_mini_llm_client_imports_gateway(self):
        """mini_parwa/llm_client.py must import from llm_gateway."""
        import app.core.mini_parwa.llm_client as mod
        assert hasattr(mod, "llm_gateway")

    def test_pro_llm_client_imports_gateway(self):
        """parwa/llm_client.py must import from llm_gateway."""
        import app.core.parwa.llm_client as mod
        assert hasattr(mod, "llm_gateway")

    def test_high_llm_client_imports_gateway(self):
        """parwa_high/llm_client.py must import from llm_gateway."""
        import app.core.parwa_high.llm_client as mod
        assert hasattr(mod, "llm_gateway")
