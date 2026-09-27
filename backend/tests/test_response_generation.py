"""
Comprehensive tests for ResponseGenerator (F-065).

Tests cover the full auto-response generation pipeline:
- Request validation & empty-query handling
- Draft-in-progress guard (GAP-028)
- Rate-limit enforcement (GAP-020)
- Sentiment analysis integration
- RAG retrieval, reranking, and context assembly
- Token budget checks (GAP-006)
- Brand voice integration
- LLM response generation via SmartRouter
- CLARA quality gate
- Template fallback
- Response formatting
- Final brand voice validation & merge
- System prompt construction
- Message building
- Utility methods (batch, draft, rate-limit status)

All lazy imports inside ``ResponseGenerator.__init__`` are mocked at the
source module path so that no real service dependencies are needed.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Environment bootstrap (must precede any app imports) ──────────
import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test_secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt")
os.environ.setdefault("DATA_ENCRYPTION_KEY", "12345678901234567890123456789012")

from app.core.response_generator import (
    RATE_LIMIT_DAILY_MAX,
    RATE_LIMIT_HOURLY_MAX,
    RateLimitCheck,
    ResponseGenerationRequest,
    ResponseGenerationResult,
    ResponseGenerator,
)


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def _make_request(
    query: str = "How do I reset my password?",
    company_id: str = "company-001",
    conversation_id: str = "conv-001",
    variant_type: str = "parwa",
    customer_id: Optional[str] = "cust-001",
    **overrides: Any,
) -> ResponseGenerationRequest:
    """Factory for creating test requests."""
    return ResponseGenerationRequest(
        query=query,
        company_id=company_id,
        conversation_id=conversation_id,
        variant_type=variant_type,
        customer_id=customer_id,
        **overrides,
    )


def _make_sentiment_result(
    sentiment_score: float = 0.7,
    frustration_score: float = 10,
    emotion: str = "neutral",
    conversation_trend: str = "stable",
    tone_recommendation: str = "standard",
    empathy_signals: Optional[List[str]] = None,
) -> MagicMock:
    """Create a mock sentiment analysis result."""
    result = MagicMock()
    result.sentiment_score = sentiment_score
    result.frustration_score = frustration_score
    result.emotion = emotion
    result.conversation_trend = conversation_trend
    result.tone_recommendation = tone_recommendation
    result.empathy_signals = empathy_signals or []
    result.to_dict.return_value = {
        "sentiment_score": sentiment_score,
        "frustration_score": frustration_score,
        "emotion": emotion,
        "conversation_trend": conversation_trend,
        "tone_recommendation": tone_recommendation,
        "empathy_signals": empathy_signals or [],
        "urgency_level": "low",
    }
    return result


def _make_rag_result(
    chunks: Optional[List[ MagicMock]] = None,
    total_found: int = 5,
) -> MagicMock:
    """Create a mock RAG result."""
    if chunks is None:
        chunk = MagicMock()
        chunk.content = "Knowledge base entry about password resets."
        chunk.to_dict.return_value = {"content": chunk.content}
        chunks = [chunk]
    result = MagicMock()
    result.chunks = chunks
    result.total_found = total_found
    return result


def _make_clara_result(
    overall_pass: bool = True,
    overall_score: float = 0.85,
    final_response: str = "",
    pipeline_timed_out: bool = False,
) -> MagicMock:
    """Create a mock CLARA quality gate result."""
    stage = MagicMock()
    stage.result.value = "pass"
    stage.issues = []
    result = MagicMock()
    result.overall_pass = overall_pass
    result.overall_score = overall_score
    result.final_response = final_response
    result.pipeline_timed_out = pipeline_timed_out
    result.stages = [stage]
    return result


def _make_brand_config(
    brand_name: str = "Acme Corp",
    tone: str = "professional",
    formality_level: float = 0.5,
    response_length_preference: str = "standard",
    max_response_sentences: int = 6,
    min_response_sentences: int = 2,
    prohibited_words: Optional[List[str]] = None,
    custom_instructions: str = "",
) -> MagicMock:
    """Create a mock brand voice config."""
    config = MagicMock()
    config.brand_name = brand_name
    config.tone = tone
    config.formality_level = formality_level
    config.response_length_preference = response_length_preference
    config.max_response_sentences = max_response_sentences
    config.min_response_sentences = min_response_sentences
    config.prohibited_words = prohibited_words or []
    config.custom_instructions = custom_instructions
    return config


@dataclass
class _MockOverflowResult:
    can_fit: bool = True
    overflow_amount: int = 0


@dataclass
class _MockReserveResult:
    success: bool = True
    remaining_after_reserve: int = 10000


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_redis():
    """Async mock for Redis client."""
    redis = AsyncMock()
    redis.get.return_value = None
    redis.set.return_value = True
    redis.delete.return_value = True
    redis.incr.return_value = 1
    redis.expire.return_value = True
    return redis


@pytest.fixture
def gen(mock_redis):
    """Create a ResponseGenerator with all dependencies mocked."""
    with (
        patch("app.core.sentiment_engine.SentimentAnalyzer") as MockSentiment,
        patch("app.core.rag_retrieval.RAGRetriever") as MockRAG,
        patch("app.core.rag_reranking.CrossEncoderReranker") as MockReranker,
        patch("app.core.rag_reranking.ContextWindowAssembler") as MockAssembler,
        patch("app.core.clara_quality_gate.CLARAQualityGate") as MockCLARA,
        patch("app.core.smart_router.SmartRouter") as MockRouter,
        patch("app.services.brand_voice_service.BrandVoiceService") as MockBrand,
        patch("app.services.token_budget_service.TokenBudgetService") as MockBudget,
        patch("app.services.response_template_service.ResponseTemplateService") as MockTemplate,
    ):
        generator = ResponseGenerator(redis_client=mock_redis)

        # Replace smart_router and template_service with plain objects so
        # AsyncMock attributes are not swallowed by MagicMock's child-mock
        # auto-generation.  MagicMock() instances produced by the patched
        # constructors can silently eat attribute assignments.
        _router = SimpleNamespace()
        _router.route = MagicMock(return_value=MagicMock())
        _router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Default mock response."}
        )
        generator.smart_router = _router

        _tpl = SimpleNamespace()
        _tpl.find_best_template = AsyncMock(return_value=None)
        _tpl.render_template = AsyncMock(return_value=None)
        generator.template_service = _tpl

        # Ensure all await-able mock methods have AsyncMock defaults so
        # that any code path which reaches them does not try to await a
        # plain MagicMock (which raises "object MagicMock can't be used
        # in 'await' expression").
        _budget = SimpleNamespace()
        _budget.initialize_budget = AsyncMock()
        _budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult(),
        )
        _budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult(),
        )
        _budget.finalize_tokens = AsyncMock()
        _budget.get_budget_status = AsyncMock(
            return_value=MagicMock(
                max_tokens=10000, used_tokens=500, reserved_tokens=1000,
                available_tokens=8500, percentage_used=5.0, warning_level="normal",
            ),
        )
        generator.token_budget = _budget

        # Attach mock classes to the fixture for easy access in tests
        generator._mock_classes = {
            "SentimentAnalyzer": MockSentiment,
            "RAGRetriever": MockRAG,
            "CrossEncoderReranker": MockReranker,
            "ContextWindowAssembler": MockAssembler,
            "CLARAQualityGate": MockCLARA,
            "SmartRouter": MockRouter,
            "BrandVoiceService": MockBrand,
            "TokenBudgetService": MockBudget,
            "ResponseTemplateService": MockTemplate,
        }
        yield generator


# ══════════════════════════════════════════════════════════════════
# 1. INITIALIZATION TESTS
# ══════════════════════════════════════════════════════════════════


class TestResponseGeneratorInit:
    """Test ResponseGenerator initialization and dependency wiring."""

    def test_init_with_no_redis(self):
        """Generator initializes with None redis_client."""
        with patch("app.core.sentiment_engine.SentimentAnalyzer"), \
             patch("app.core.rag_retrieval.RAGRetriever"), \
             patch("app.core.rag_reranking.CrossEncoderReranker"), \
             patch("app.core.rag_reranking.ContextWindowAssembler"), \
             patch("app.core.clara_quality_gate.CLARAQualityGate"), \
             patch("app.core.smart_router.SmartRouter"), \
             patch("app.services.brand_voice_service.BrandVoiceService"), \
             patch("app.services.token_budget_service.TokenBudgetService"), \
             patch("app.services.response_template_service.ResponseTemplateService"):
            g = ResponseGenerator()
            assert g.redis_client is None

    def test_init_with_redis(self, mock_redis):
        """Generator stores the provided redis_client."""
        with patch("app.core.sentiment_engine.SentimentAnalyzer"), \
             patch("app.core.rag_retrieval.RAGRetriever"), \
             patch("app.core.rag_reranking.CrossEncoderReranker"), \
             patch("app.core.rag_reranking.ContextWindowAssembler"), \
             patch("app.core.clara_quality_gate.CLARAQualityGate"), \
             patch("app.core.smart_router.SmartRouter"), \
             patch("app.services.brand_voice_service.BrandVoiceService"), \
             patch("app.services.token_budget_service.TokenBudgetService"), \
             patch("app.services.response_template_service.ResponseTemplateService"):
            g = ResponseGenerator(redis_client=mock_redis)
            assert g.redis_client is mock_redis

    def test_init_creates_sentiment_analyzer(self, gen):
        """SentimentAnalyzer is instantiated on init."""
        assert gen.sentiment_analyzer is not None

    def test_init_creates_rag_retriever(self, gen):
        """RAGRetriever is instantiated on init."""
        assert gen.rag_retriever is not None

    def test_init_creates_reranker(self, gen):
        """CrossEncoderReranker is instantiated on init."""
        assert gen.reranker is not None

    def test_init_creates_assembler(self, gen):
        """ContextWindowAssembler is instantiated on init."""
        assert gen.assembler is not None

    def test_init_creates_clara_gate(self, gen):
        """CLARAQualityGate is instantiated on init."""
        assert gen.clara_gate is not None

    def test_init_creates_smart_router(self, gen):
        """SmartRouter is instantiated on init."""
        assert gen.smart_router is not None

    def test_init_creates_brand_voice(self, gen):
        """BrandVoiceService is instantiated on init."""
        assert gen.brand_voice is not None

    def test_init_creates_token_budget(self, gen):
        """TokenBudgetService is instantiated on init."""
        assert gen.token_budget is not None

    def test_init_creates_template_service(self, gen):
        """ResponseTemplateService is instantiated on init."""
        assert gen.template_service is not None


# ══════════════════════════════════════════════════════════════════
# 2. EMPTY QUERY / VALIDATION TESTS
# ══════════════════════════════════════════════════════════════════


class TestEmptyQueryHandling:
    """Test that empty or whitespace-only queries are handled gracefully."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty_result(self, gen):
        """Empty string query returns an empty response result."""
        req = _make_request(query="")
        result = await gen.generate(req)
        assert isinstance(result, ResponseGenerationResult)
        assert result.response_text == ""
        assert result.confidence_score == 0.0
        assert not result.clara_passed
        assert not result.template_used

    @pytest.mark.asyncio
    async def test_whitespace_only_query_returns_empty_result(self, gen):
        """Whitespace-only query is treated as empty."""
        req = _make_request(query="   \t\n  ")
        result = await gen.generate(req)
        assert result.response_text == ""
        assert result.confidence_score == 0.0

    @pytest.mark.asyncio
    async def test_empty_query_reason(self, gen):
        """Empty query result includes 'empty_query' in quality issues."""
        req = _make_request(query="")
        result = await gen.generate(req)
        assert any("empty_query" in issue for issue in result.quality_issues)

    @pytest.mark.asyncio
    async def test_empty_query_has_generation_time(self, gen):
        """Empty query result has a non-negative generation_time_ms."""
        req = _make_request(query="")
        result = await gen.generate(req)
        assert result.generation_time_ms >= 0

    @pytest.mark.asyncio
    async def test_empty_query_sentiment_analysis_is_default(self, gen):
        """Empty query returns a default sentiment analysis dict."""
        req = _make_request(query="")
        result = await gen.generate(req)
        assert isinstance(result.sentiment_analysis, dict)
        assert result.sentiment_analysis.get("degraded") is True

    @pytest.mark.asyncio
    async def test_empty_query_rag_not_used(self, gen):
        """Empty query should not trigger RAG retrieval."""
        req = _make_request(query="")
        result = await gen.generate(req)
        assert not result.rag_context_used
        assert result.citations == []


# ══════════════════════════════════════════════════════════════════
# 3. DRAFT-IN-PROGRESS TESTS (GAP-028)
# ══════════════════════════════════════════════════════════════════


class TestDraftInProgress:
    """Test GAP-028 draft-in-progress guard."""

    @pytest.mark.asyncio
    async def test_draft_active_returns_empty(self, gen, mock_redis):
        """If a draft is in progress, returns an empty result."""
        mock_redis.get.return_value = "agent-123"
        req = _make_request(ticket_id="tkt-001")
        result = await gen.generate(req)
        assert result.response_text == ""

    @pytest.mark.asyncio
    async def test_draft_active_quality_issues(self, gen, mock_redis):
        """Draft-in-progress result reports the reason."""
        mock_redis.get.return_value = "agent-123"
        req = _make_request(ticket_id="tkt-001")
        result = await gen.generate(req)
        assert any("draft_in_progress" in issue for issue in result.quality_issues)

    @pytest.mark.asyncio
    async def test_no_draft_allows_generation(self, gen, mock_redis):
        """When no draft is active, generation proceeds."""
        mock_redis.get.return_value = None
        # Setup mocks so the pipeline runs through
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Here is your answer."}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="Here is your answer."
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request(ticket_id="tkt-001")
                result = await gen.generate(req)
                assert result.response_text != ""

    @pytest.mark.asyncio
    async def test_draft_check_redis_error_continues(self, gen, mock_redis):
        """Redis error during draft check does not block generation."""
        mock_redis.get.side_effect = Exception("Redis down")
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Response despite Redis error."}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="Response despite Redis error."
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request(ticket_id="tkt-001")
                result = await gen.generate(req)
                # Should not crash — BC-008
                assert isinstance(result, ResponseGenerationResult)

    @pytest.mark.asyncio
    async def test_no_ticket_id_skips_draft_check(self, gen):
        """When ticket_id is None, draft check is skipped entirely."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "No draft check needed."}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="No draft check needed."
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request(ticket_id=None)
                result = await gen.generate(req)
                assert isinstance(result, ResponseGenerationResult)


# ══════════════════════════════════════════════════════════════════
# 4. RATE-LIMIT TESTS (GAP-020)
# ══════════════════════════════════════════════════════════════════


class TestRateLimiting:
    """Test GAP-020 per-customer rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limit_within_bounds(self, gen, mock_redis):
        """When within limits, rate check is allowed."""
        mock_redis.incr.return_value = 5
        result = await gen._check_rate_limit("co-1", "cust-1")
        assert result.allowed is True
        assert result.hourly_count == 5
        assert result.daily_count == 5

    @pytest.mark.asyncio
    async def test_rate_limit_hourly_exceeded(self, gen, mock_redis):
        """Hourly limit exceeded returns not allowed."""
        mock_redis.incr.side_effect = [25, 50]
        result = await gen._check_rate_limit("co-1", "cust-1")
        assert result.allowed is False
        assert "Hourly limit exceeded" in result.reason

    @pytest.mark.asyncio
    async def test_rate_limit_daily_exceeded(self, gen, mock_redis):
        """Daily limit exceeded returns not allowed."""
        mock_redis.incr.side_effect = [10, 105]
        result = await gen._check_rate_limit("co-1", "cust-1")
        assert result.allowed is False
        assert "Daily limit exceeded" in result.reason

    @pytest.mark.asyncio
    async def test_rate_limit_no_redis(self, gen):
        """No redis client always allows (fail open)."""
        gen.redis_client = None
        result = await gen._check_rate_limit("co-1", "cust-1")
        assert result.allowed is True
        assert result.reason == "no_redis"

    @pytest.mark.asyncio
    async def test_rate_limit_redis_error_fail_open(self, gen, mock_redis):
        """Redis exception returns allowed=True (BC-008/BC-012)."""
        mock_redis.incr.side_effect = Exception("Connection refused")
        result = await gen._check_rate_limit("co-1", "cust-1")
        assert result.allowed is True
        assert "redis_error" in result.reason

    @pytest.mark.asyncio
    async def test_rate_limit_sets_expire_on_first_incr(self, gen, mock_redis):
        """First increment for each counter sets TTL on the key."""
        call_count = 0

        async def _incr_side_effect(key):
            nonlocal call_count
            call_count += 1
            return call_count

        mock_redis.incr.side_effect = _incr_side_effect
        # First call returns 1 → hourly expire; second returns 2 → no daily expire
        await gen._check_rate_limit("co-1", "cust-1")
        assert mock_redis.expire.call_count == 1

    @pytest.mark.asyncio
    async def test_rate_limit_both_expire_on_first(self, gen, mock_redis):
        """When both counters are at 1, both keys get TTL."""
        mock_redis.incr.return_value = 1
        await gen._check_rate_limit("co-1", "cust-1")
        assert mock_redis.expire.call_count == 2  # hour + day

    @pytest.mark.asyncio
    async def test_rate_limit_constants(self):
        """Verify rate limit constants."""
        assert RATE_LIMIT_HOURLY_MAX == 20
        assert RATE_LIMIT_DAILY_MAX == 100

    @pytest.mark.asyncio
    async def test_rate_limit_returns_correct_limits(self, gen, mock_redis):
        """RateLimitCheck always carries the configured limits."""
        mock_redis.incr.return_value = 1
        result = await gen._check_rate_limit("co-1", "cust-1")
        assert result.hourly_limit == RATE_LIMIT_HOURLY_MAX
        assert result.daily_limit == RATE_LIMIT_DAILY_MAX

    @pytest.mark.asyncio
    async def test_rate_limited_falls_to_template(self, gen, mock_redis):
        """Rate-limited request falls back to template."""
        mock_redis.incr.side_effect = [25, 50]
        mock_template = MagicMock()
        mock_template.id = "tpl-1"
        mock_template.name = "rate_limit_template"
        gen.template_service.find_best_template = AsyncMock(
            return_value=mock_template
        )
        gen.template_service.render_template = AsyncMock(
            return_value="We've received your message. An agent will respond shortly."
        )
        with patch("app.core.response_formatters.create_default_registry"):
            req = _make_request(customer_id="cust-1")
            result = await gen.generate(req)
            assert result.template_used is True


# ══════════════════════════════════════════════════════════════════
# 5. SENTIMENT ANALYSIS TESTS
# ══════════════════════════════════════════════════════════════════


class TestSentimentAnalysis:
    """Test sentiment analysis step and graceful degradation."""

    @pytest.mark.asyncio
    async def test_sentiment_called_with_correct_args(self, gen):
        """Sentiment analyzer receives the right parameters."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Response"}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="Response"
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                history = [{"role": "user", "content": "Hello"}]
                req = _make_request(
                    query="How do I reset?",
                    conversation_history=history,
                )
                await gen.generate(req)
                gen.sentiment_analyzer.analyze.assert_called_once()
                call_kwargs = gen.sentiment_analyzer.analyze.call_args
                assert call_kwargs.kwargs["query"] == "How do I reset?"
                assert call_kwargs.kwargs["company_id"] == "company-001"

    @pytest.mark.asyncio
    async def test_sentiment_failure_uses_defaults(self, gen):
        """If sentiment analysis fails, defaults are used."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            side_effect=RuntimeError("Sentiment service down")
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Default sentiment response"}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="Default sentiment response"
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request()
                result = await gen.generate(req)
                assert result.sentiment_analysis.get("degraded") is True
                assert result.sentiment_analysis.get("sentiment_score") == 0.5

    @pytest.mark.asyncio
    async def test_sentiment_history_texts_extraction(self, gen):
        """Conversation history messages are extracted as strings."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "OK"}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(return_value="OK")
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                history = [
                    {"role": "user", "content": "First message"},
                    {"role": "assistant", "content": "Reply"},
                    {"role": "user", "content": "Second message"},
                    {"not_a_dict": True},  # should be skipped
                    {"role": "user", "content": ""},  # empty content skipped
                ]
                req = _make_request(conversation_history=history)
                await gen.generate(req)
                call_kwargs = gen.sentiment_analyzer.analyze.call_args.kwargs
                # Should extract 3 non-empty content messages
                assert len(call_kwargs["conversation_history"]) == 3


# ══════════════════════════════════════════════════════════════════
# 6. RAG RETRIEVAL TESTS
# ══════════════════════════════════════════════════════════════════


class TestRAGRetrieval:
    """Test RAG retrieval, reranking, and context assembly."""

    @pytest.mark.asyncio
    async def test_rag_success(self, gen):
        """Successful RAG retrieval sets rag_context_used=True."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        chunk = MagicMock()
        chunk.content = "KB content here."
        chunk.to_dict.return_value = {"content": chunk.content}
        gen.rag_retriever.retrieve = AsyncMock(
            return_value=_make_rag_result(chunks=[chunk])
        )
        gen.reranker.rerank = AsyncMock(
            return_value=_make_rag_result(chunks=[chunk])
        )
        assembled = MagicMock()
        assembled.context_string = "Assembled context."
        assembled.citations = []
        gen.assembler.assemble.return_value = assembled
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "RAG-based response"}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="RAG-based response"
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request()
                result = await gen.generate(req)
                assert result.rag_context_used is True

    @pytest.mark.asyncio
    async def test_rag_failure_continues(self, gen):
        """RAG failure does not crash the pipeline."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(
            side_effect=RuntimeError("RAG service down")
        )
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Response without RAG"}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="Response without RAG"
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request()
                result = await gen.generate(req)
                assert result.rag_context_used is False
                assert isinstance(result, ResponseGenerationResult)

    @pytest.mark.asyncio
    async def test_rerank_failure_uses_original(self, gen):
        """Reranking failure falls back to unranked chunks."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        chunk = MagicMock()
        chunk.content = "Unranked content."
        chunk.to_dict.return_value = {"content": chunk.content}
        gen.rag_retriever.retrieve = AsyncMock(
            return_value=_make_rag_result(chunks=[chunk])
        )
        gen.reranker.rerank = AsyncMock(
            side_effect=RuntimeError("Reranker down")
        )
        assembled = MagicMock()
        assembled.context_string = "Assembled from original."
        assembled.citations = []
        gen.assembler.assemble.return_value = assembled
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Response with unranked RAG"}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="Response with unranked RAG"
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request()
                result = await gen.generate(req)
                assert result.rag_context_used is True

    @pytest.mark.asyncio
    async def test_context_assembly_failure_uses_raw_chunks(self, gen):
        """If context assembly fails, raw chunks are concatenated."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        chunk = MagicMock()
        chunk.content = "Raw chunk text."
        gen.rag_retriever.retrieve = AsyncMock(
            return_value=_make_rag_result(chunks=[chunk])
        )
        gen.reranker.rerank = AsyncMock(
            return_value=_make_rag_result(chunks=[chunk])
        )
        gen.assembler.assemble.side_effect = RuntimeError("Assembly failed")
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Response with raw chunks"}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="Response with raw chunks"
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request()
                result = await gen.generate(req)
                assert result.rag_context_used is True

    @pytest.mark.asyncio
    async def test_no_rag_results_context_not_used(self, gen):
        """When RAG returns None or no chunks, rag_context_used is False."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "No RAG needed."}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="No RAG needed."
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request()
                result = await gen.generate(req)
                assert result.rag_context_used is False


# ══════════════════════════════════════════════════════════════════
# 7. TOKEN BUDGET TESTS (GAP-006)
# ══════════════════════════════════════════════════════════════════


class TestTokenBudget:
    """Test token budget enforcement."""

    @pytest.mark.asyncio
    async def test_budget_overflow_falls_to_template(self, gen):
        """Token budget overflow triggers template fallback."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult(can_fit=False, overflow_amount=500)
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult(success=True)
        )
        mock_template = MagicMock()
        mock_template.id = "tpl-budget"
        mock_template.name = "budget_template"
        gen.template_service.find_best_template = AsyncMock(
            return_value=mock_template
        )
        gen.template_service.render_template = AsyncMock(
            return_value="Budget exhausted. Template response."
        )
        with patch("app.core.response_formatters.create_default_registry"):
            req = _make_request()
            result = await gen.generate(req)
            assert result.template_used is True

    @pytest.mark.asyncio
    async def test_budget_reserve_failure_falls_to_template(self, gen):
        """Failed token reserve triggers template fallback."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult(success=False, remaining_after_reserve=0)
        )
        mock_template = MagicMock()
        mock_template.id = "tpl-reserve"
        gen.template_service.find_best_template = AsyncMock(
            return_value=mock_template
        )
        gen.template_service.render_template = AsyncMock(
            return_value="Reserve failed template."
        )
        with patch("app.core.response_formatters.create_default_registry"):
            req = _make_request()
            result = await gen.generate(req)
            assert result.template_used is True

    @pytest.mark.asyncio
    async def test_force_template_response(self, gen):
        """force_template_response=True bypasses AI pipeline."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        mock_template = MagicMock()
        mock_template.id = "tpl-force"
        gen.template_service.find_best_template = AsyncMock(
            return_value=mock_template
        )
        gen.template_service.render_template = AsyncMock(
            return_value="Forced template response."
        )
        with patch("app.core.response_formatters.create_default_registry"):
            req = _make_request(force_template_response=True)
            result = await gen.generate(req)
            assert result.template_used is True

    @pytest.mark.asyncio
    async def test_budget_error_does_not_crash(self, gen):
        """Token budget exceptions are caught and pipeline continues."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock(
            side_effect=RuntimeError("Budget service down")
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Despite budget error"}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="Despite budget error"
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request()
                result = await gen.generate(req)
                assert isinstance(result, ResponseGenerationResult)


# ══════════════════════════════════════════════════════════════════
# 8. CLARA QUALITY GATE TESTS
# ══════════════════════════════════════════════════════════════════


class TestCLARAQualityGate:
    """Test CLARA quality gate integration."""

    @pytest.mark.asyncio
    async def test_clara_passes(self, gen):
        """When CLARA passes, the response goes through."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "CLARA approved response"}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result(overall_pass=True, overall_score=0.9)
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="CLARA approved response"
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request()
                result = await gen.generate(req)
                assert result.clara_passed is True
                assert result.clara_score == 0.9

    @pytest.mark.asyncio
    async def test_clara_failure_falls_to_template(self, gen):
        """CLARA failure falls back to template."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Bad response"}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result(
                overall_pass=False, overall_score=0.2
            )
        )
        mock_template = MagicMock()
        mock_template.id = "tpl-clara-fail"
        gen.template_service.find_best_template = AsyncMock(
            return_value=mock_template
        )
        gen.template_service.render_template = AsyncMock(
            return_value="CLARA failed template."
        )
        with patch("app.core.response_formatters.create_default_registry"):
            req = _make_request()
            result = await gen.generate(req)
            assert result.template_used is True
            assert result.clara_passed is False

    @pytest.mark.asyncio
    async def test_clara_uses_final_response(self, gen):
        """CLARA's final_response replaces generated response."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Original response"}
        )
        clara_improved = "CLARA improved response."
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result(
                overall_pass=True,
                overall_score=0.85,
                final_response=clara_improved,
            )
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value=clara_improved
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request()
                result = await gen.generate(req)
                assert result.response_text == clara_improved

    @pytest.mark.asyncio
    async def test_clara_error_continues(self, gen):
        """CLARA exception doesn't crash the pipeline."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Despite CLARA error"}
        )
        gen.clara_gate.evaluate = AsyncMock(
            side_effect=RuntimeError("CLARA service down")
        )
        # CLARA fails -> template fallback
        mock_template = MagicMock()
        mock_template.id = "tpl-clara-err"
        gen.template_service.find_best_template = AsyncMock(
            return_value=mock_template
        )
        gen.template_service.render_template = AsyncMock(
            return_value="CLARA error template."
        )
        with patch("app.core.response_formatters.create_default_registry"):
            req = _make_request()
            result = await gen.generate(req)
            assert isinstance(result, ResponseGenerationResult)
            assert any("CLARA" in i for i in result.quality_issues)


# ══════════════════════════════════════════════════════════════════
# 9. BRAND VOICE TESTS
# ══════════════════════════════════════════════════════════════════


class TestBrandVoice:
    """Test brand voice integration."""

    def test_system_prompt_includes_brand_name(self, gen):
        """System prompt includes brand name from config."""
        config = _make_brand_config(brand_name="TestBrand")
        req = _make_request()
        prompt = gen._build_system_prompt(
            brand_config=config,
            response_guidelines=None,
            sentiment_result=None,
            rag_context="",
            request=req,
        )
        assert "TestBrand" in prompt

    def test_system_prompt_formality_high(self, gen):
        """High formality level produces 'high formality' in prompt."""
        config = _make_brand_config(formality_level=0.9)
        req = _make_request()
        prompt = gen._build_system_prompt(
            brand_config=config,
            response_guidelines=None,
            sentiment_result=None,
            rag_context="",
            request=req,
        )
        assert "high formality" in prompt

    def test_system_prompt_formality_low(self, gen):
        """Low formality level produces 'low formality' in prompt."""
        config = _make_brand_config(formality_level=0.2)
        req = _make_request()
        prompt = gen._build_system_prompt(
            brand_config=config,
            response_guidelines=None,
            sentiment_result=None,
            rag_context="",
            request=req,
        )
        assert "low formality" in prompt

    def test_system_prompt_prohibited_words(self, gen):
        """Prohibited words are listed in system prompt."""
        config = _make_brand_config(prohibited_words=["sorry", "um", "uh"])
        req = _make_request()
        prompt = gen._build_system_prompt(
            brand_config=config,
            response_guidelines=None,
            sentiment_result=None,
            rag_context="",
            request=req,
        )
        assert "sorry" in prompt
        assert "PROHIBITED" in prompt

    def test_system_prompt_custom_instructions(self, gen):
        """Custom instructions appear in system prompt."""
        config = _make_brand_config(
            custom_instructions="Always use bullet points."
        )
        req = _make_request()
        prompt = gen._build_system_prompt(
            brand_config=config,
            response_guidelines=None,
            sentiment_result=None,
            rag_context="",
            request=req,
        )
        assert "bullet points" in prompt

    def test_system_prompt_no_brand_config(self, gen):
        """Without brand config, default values are used."""
        req = _make_request()
        prompt = gen._build_system_prompt(
            brand_config=None,
            response_guidelines=None,
            sentiment_result=None,
            rag_context="",
            request=req,
        )
        assert "our company" in prompt
        assert "professional" in prompt

    def test_system_prompt_high_frustration(self, gen):
        """High frustration score triggers empathetic instructions."""
        sentiment = _make_sentiment_result(frustration_score=80)
        req = _make_request()
        prompt = gen._build_system_prompt(
            brand_config=None,
            response_guidelines=None,
            sentiment_result=sentiment,
            rag_context="",
            request=req,
        )
        assert "highly frustrated" in prompt
        assert "80" in prompt

    def test_system_prompt_moderate_frustration(self, gen):
        """Moderate frustration shows appropriate note."""
        sentiment = _make_sentiment_result(frustration_score=50)
        req = _make_request()
        prompt = gen._build_system_prompt(
            brand_config=None,
            response_guidelines=None,
            sentiment_result=sentiment,
            rag_context="",
            request=req,
        )
        assert "moderate frustration" in prompt

    def test_system_prompt_happy_emotion(self, gen):
        """Happy emotion triggers warm tone instruction."""
        sentiment = _make_sentiment_result(emotion="happy")
        req = _make_request()
        prompt = gen._build_system_prompt(
            brand_config=None,
            response_guidelines=None,
            sentiment_result=sentiment,
            rag_context="",
            request=req,
        )
        assert "positive mood" in prompt

    def test_system_prompt_rag_context(self, gen):
        """RAG context triggers citation instructions."""
        req = _make_request()
        prompt = gen._build_system_prompt(
            brand_config=None,
            response_guidelines=None,
            sentiment_result=None,
            rag_context="Some context about the product.",
            request=req,
        )
        assert "Knowledge base context" in prompt

    def test_system_prompt_citation_parwa_high(self, gen):
        """parwa_high variant includes citation format instructions."""
        req = _make_request(variant_type="parwa_high")
        prompt = gen._build_system_prompt(
            brand_config=None,
            response_guidelines=None,
            sentiment_result=None,
            rag_context="",
            request=req,
        )
        assert "Citation format" in prompt

    def test_system_prompt_language(self, gen):
        """Non-English language instruction is included."""
        req = _make_request(language="es")
        prompt = gen._build_system_prompt(
            brand_config=None,
            response_guidelines=None,
            sentiment_result=None,
            rag_context="",
            request=req,
        )
        assert "es" in prompt

    def test_system_prompt_empathy_signals(self, gen):
        """Empathy signals trigger specific handling instructions."""
        sentiment = _make_sentiment_result(
            empathy_signals=["financial_impact", "apology_expectation"]
        )
        req = _make_request()
        prompt = gen._build_system_prompt(
            brand_config=None,
            response_guidelines=None,
            sentiment_result=sentiment,
            rag_context="",
            request=req,
        )
        assert "Financial impact" in prompt
        assert "apology" in prompt

    @pytest.mark.asyncio
    async def test_brand_voice_failure_continues(self, gen):
        """Brand voice service failure does not block generation."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(
            side_effect=RuntimeError("Brand service down")
        )
        gen.brand_voice.get_response_guidelines = AsyncMock(
            side_effect=RuntimeError("Brand service down")
        )
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Despite brand failure"}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="Despite brand failure"
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request()
                result = await gen.generate(req)
                assert isinstance(result, ResponseGenerationResult)


# ══════════════════════════════════════════════════════════════════
# 10. MESSAGE BUILDING TESTS
# ══════════════════════════════════════════════════════════════════


class TestMessageBuilding:
    """Test _build_messages method."""

    def test_messages_includes_system_prompt(self, gen):
        """First message is always the system prompt."""
        messages = gen._build_messages(
            system_prompt="Be helpful.",
            conversation_history=[],
            query="Hello",
            rag_context="",
        )
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "Be helpful."

    def test_messages_includes_user_query(self, gen):
        """Last message before RAG context is the user query."""
        messages = gen._build_messages(
            system_prompt="Be helpful.",
            conversation_history=[],
            query="How to reset?",
            rag_context="",
        )
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "How to reset?"

    def test_messages_includes_rag_context(self, gen):
        """RAG context is appended as a system message."""
        messages = gen._build_messages(
            system_prompt="Be helpful.",
            conversation_history=[],
            query="Hello",
            rag_context="KB context here",
        )
        assert any(
            m["role"] == "system" and "KB context" in m["content"]
            for m in messages
        )

    def test_messages_no_rag_context(self, gen):
        """Without RAG context, no extra system message is added."""
        messages = gen._build_messages(
            system_prompt="Be helpful.",
            conversation_history=[],
            query="Hello",
            rag_context="",
        )
        # System prompt + user query = 2 messages
        assert len(messages) == 2

    def test_messages_history_limited_to_10(self, gen):
        """Conversation history is limited to last 10 messages."""
        history = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(20)
        ]
        messages = gen._build_messages(
            system_prompt="Be helpful.",
            conversation_history=history,
            query="Latest question",
            rag_context="",
        )
        user_assistant_msgs = [
            m for m in messages if m["role"] in ("user", "assistant")
        ]
        # 10 from history + 1 current query = 11
        assert len(user_assistant_msgs) == 11

    def test_messages_skips_invalid_history(self, gen):
        """Non-dict and invalid entries in history are skipped."""
        history = [
            "not a dict",
            {"no_content": True},
            {"role": "user", "content": ""},  # empty
            {"role": "user", "content": "Valid"},
        ]
        messages = gen._build_messages(
            system_prompt="Be helpful.",
            conversation_history=history,
            query="Latest",
            rag_context="",
        )
        user_assistant = [
            m for m in messages if m["role"] in ("user", "assistant")
        ]
        # Only "Valid" from history + current query = 2
        assert len(user_assistant) == 2


# ══════════════════════════════════════════════════════════════════
# 11. LLM GENERATION TESTS
# ══════════════════════════════════════════════════════════════════


class TestLLMGeneration:
    """Test LLM response generation and error handling."""

    @pytest.mark.asyncio
    async def test_llm_success_returns_response(self, gen):
        """Successful LLM call produces a response."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "LLM generated response."}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="LLM generated response."
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request()
                result = await gen.generate(req)
                assert "LLM generated response" in result.response_text
                assert result.confidence_score == 0.8

    @pytest.mark.asyncio
    async def test_llm_empty_response_falls_to_template(self, gen):
        """Empty LLM response falls back to template."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": ""}
        )
        mock_template = MagicMock()
        mock_template.id = "tpl-empty"
        gen.template_service.find_best_template = AsyncMock(
            return_value=mock_template
        )
        gen.template_service.render_template = AsyncMock(
            return_value="Empty LLM template."
        )
        with patch("app.core.response_formatters.create_default_registry"):
            req = _make_request()
            result = await gen.generate(req)
            assert result.template_used is True

    @pytest.mark.asyncio
    async def test_llm_error_falls_to_template(self, gen):
        """LLM exception falls back to template."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            side_effect=RuntimeError("LLM provider down")
        )
        mock_template = MagicMock()
        mock_template.id = "tpl-llm-err"
        gen.template_service.find_best_template = AsyncMock(
            return_value=mock_template
        )
        gen.template_service.render_template = AsyncMock(
            return_value="LLM error template."
        )
        with patch("app.core.response_formatters.create_default_registry"):
            req = _make_request()
            result = await gen.generate(req)
            assert result.template_used is True


# ══════════════════════════════════════════════════════════════════
# 12. TEMPLATE FALLBACK TESTS
# ══════════════════════════════════════════════════════════════════


class TestTemplateFallback:
    """Test template fallback mechanism."""

    @pytest.mark.asyncio
    async def test_no_template_returns_none(self, gen):
        """When no template found, fallback returns None."""
        gen.template_service.find_best_template = AsyncMock(return_value=None)
        result = await gen._fallback_to_template(
            request=_make_request(),
            sentiment_score=0.5,
            pipeline_start=time.monotonic(),
            reason="test",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_template_success(self, gen):
        """Successful template render returns a result."""
        mock_template = MagicMock()
        mock_template.id = "tpl-ok"
        mock_template.name = "general_template"
        gen.template_service.find_best_template = AsyncMock(
            return_value=mock_template
        )
        gen.template_service.render_template = AsyncMock(
            return_value="Template rendered text."
        )
        with patch("app.core.response_formatters.create_default_registry"):
            result = await gen._fallback_to_template(
                request=_make_request(),
                sentiment_score=0.5,
                pipeline_start=time.monotonic(),
                reason="test",
            )
        assert result is not None
        assert result.template_used is True
        assert result.clara_passed is True
        assert result.confidence_score == 0.5

    @pytest.mark.asyncio
    async def test_template_empty_render_returns_none(self, gen):
        """Empty rendered template returns None."""
        mock_template = MagicMock()
        mock_template.id = "tpl-empty-render"
        gen.template_service.find_best_template = AsyncMock(
            return_value=mock_template
        )
        gen.template_service.render_template = AsyncMock(return_value="")
        result = await gen._fallback_to_template(
            request=_make_request(),
            sentiment_score=0.5,
            pipeline_start=time.monotonic(),
            reason="test",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_template_error_returns_none(self, gen):
        """Template service exception returns None."""
        gen.template_service.find_best_template = AsyncMock(
            side_effect=RuntimeError("Template service error")
        )
        result = await gen._fallback_to_template(
            request=_make_request(),
            sentiment_score=0.5,
            pipeline_start=time.monotonic(),
            reason="test",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_template_uses_customer_name(self, gen):
        """Template variables include customer name from metadata."""
        mock_template = MagicMock()
        mock_template.id = "tpl-cust"
        gen.template_service.find_best_template = AsyncMock(
            return_value=mock_template
        )
        gen.template_service.render_template = AsyncMock(
            return_value="Hello Alice!"
        )
        with patch("app.core.response_formatters.create_default_registry"):
            result = await gen._fallback_to_template(
                request=_make_request(
                    customer_metadata={"name": "Alice"}
                ),
                sentiment_score=0.5,
                pipeline_start=time.monotonic(),
                reason="test",
            )
        assert result is not None
        call_kwargs = gen.template_service.render_template.call_args.kwargs
        assert call_kwargs["variables"]["customer_name"] == "Alice"


# ══════════════════════════════════════════════════════════════════
# 13. EMPTY RESPONSE RESULT TESTS
# ══════════════════════════════════════════════════════════════════


class TestEmptyResponseResult:
    """Test _empty_response_result method."""

    def test_empty_query_reason(self, gen):
        result = gen._empty_response_result(time.monotonic(), "empty_query")
        assert result.response_text == ""
        assert result.confidence_score == 0.0

    def test_draft_in_progress_reason(self, gen):
        result = gen._empty_response_result(
            time.monotonic(), "draft_in_progress"
        )
        assert result.response_text == ""

    def test_other_reasons_give_generic_response(self, gen):
        result = gen._empty_response_result(
            time.monotonic(), "all_generation_failed"
        )
        assert "support agent" in result.response_text

    def test_empty_result_has_quality_issues(self, gen):
        result = gen._empty_response_result(
            time.monotonic(), "test_reason"
        )
        assert len(result.quality_issues) > 0
        assert "test_reason" in result.quality_issues[0]

    def test_empty_result_not_template(self, gen):
        result = gen._empty_response_result(
            time.monotonic(), "any"
        )
        assert result.template_used is False


# ══════════════════════════════════════════════════════════════════
# 14. UTILITY METHODS
# ══════════════════════════════════════════════════════════════════


class TestUtilityMethods:
    """Test batch generation, draft management, and rate-limit status."""

    @pytest.mark.asyncio
    async def test_generate_batch_empty_list(self, gen):
        """Empty batch returns empty list."""
        result = await gen.generate_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_batch_returns_correct_count(self, gen):
        """Batch returns one result per request."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Batch response"}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="Batch response"
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                reqs = [_make_request(conversation_id=f"conv-{i}") for i in range(3)]
                results = await gen.generate_batch(reqs)
                assert len(results) == 3

    @pytest.mark.asyncio
    async def test_set_draft_in_progress(self, gen, mock_redis):
        """Setting draft-in-progress flag succeeds."""
        result = await gen.set_draft_in_progress("co-1", "tkt-1", "agent-1")
        assert result is True
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_draft_no_redis(self, gen):
        """Setting draft without Redis returns False."""
        gen.redis_client = None
        result = await gen.set_draft_in_progress("co-1", "tkt-1", "agent-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_clear_draft_in_progress(self, gen, mock_redis):
        """Clearing draft-in-progress flag succeeds."""
        result = await gen.clear_draft_in_progress("co-1", "tkt-1")
        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_draft_no_redis(self, gen):
        """Clearing draft without Redis returns False."""
        gen.redis_client = None
        result = await gen.clear_draft_in_progress("co-1", "tkt-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_customer_rate_limit_status(self, gen, mock_redis):
        """Rate limit status is returned correctly."""
        mock_redis.get.side_effect = [None, None]
        status = await gen.get_customer_rate_limit_status("co-1", "cust-1")
        assert status["hourly_count"] == 0
        assert status["daily_count"] == 0
        assert status["hourly_remaining"] == RATE_LIMIT_HOURLY_MAX
        assert status["daily_remaining"] == RATE_LIMIT_DAILY_MAX

    @pytest.mark.asyncio
    async def test_get_customer_rate_limit_status_with_counts(self, gen, mock_redis):
        """Rate limit status reflects actual Redis counts."""
        mock_redis.get.side_effect = ["5", "30"]
        status = await gen.get_customer_rate_limit_status("co-1", "cust-1")
        assert status["hourly_count"] == 5
        assert status["daily_count"] == 30

    @pytest.mark.asyncio
    async def test_reset_customer_rate_limit(self, gen, mock_redis):
        """Resetting rate limit deletes Redis keys."""
        result = await gen.reset_customer_rate_limit("co-1", "cust-1")
        assert result is True
        assert mock_redis.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_reset_rate_limit_no_redis(self, gen):
        """Resetting rate limit without Redis returns False."""
        gen.redis_client = None
        result = await gen.reset_customer_rate_limit("co-1", "cust-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_generation_status(self, gen):
        """Generation status returns budget info."""
        mock_status = MagicMock()
        mock_status.max_tokens = 10000
        mock_status.used_tokens = 500
        mock_status.reserved_tokens = 1000
        mock_status.available_tokens = 8500
        mock_status.percentage_used = 5.0
        mock_status.warning_level = "normal"
        gen.token_budget.get_budget_status = AsyncMock(return_value=mock_status)
        status = await gen.get_generation_status("conv-1", "co-1")
        assert status["max_tokens"] == 10000
        assert status["warning_level"] == "normal"

    @pytest.mark.asyncio
    async def test_get_generation_status_error(self, gen):
        """Generation status error returns graceful fallback."""
        gen.token_budget.get_budget_status = AsyncMock(
            side_effect=RuntimeError("Budget service down")
        )
        status = await gen.get_generation_status("conv-1", "co-1")
        assert "error" in status
        assert status["warning_level"] == "unknown"

    @pytest.mark.asyncio
    async def test_set_draft_empty_args(self, gen):
        """set_draft_in_progress with empty args returns False."""
        result = await gen.set_draft_in_progress("", "", "agent-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_clear_draft_empty_args(self, gen):
        """clear_draft_in_progress with empty args returns False."""
        result = await gen.clear_draft_in_progress("", "")
        assert result is False


# ══════════════════════════════════════════════════════════════════
# 15. FULL PIPELINE TESTS
# ══════════════════════════════════════════════════════════════════


class TestFullPipeline:
    """End-to-end pipeline tests with all mocks configured."""

    @pytest.mark.asyncio
    async def test_full_pipeline_all_steps(self, gen):
        """Full pipeline runs through all steps successfully."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result(
                sentiment_score=0.8,
                frustration_score=5,
                emotion="happy",
            )
        )
        chunk = MagicMock()
        chunk.content = "KB: password reset instructions."
        chunk.to_dict.return_value = {"content": chunk.content}
        gen.rag_retriever.retrieve = AsyncMock(
            return_value=_make_rag_result(chunks=[chunk])
        )
        gen.reranker.rerank = AsyncMock(
            return_value=_make_rag_result(chunks=[chunk])
        )
        assembled = MagicMock()
        assembled.context_string = "Assembled KB context."
        assembled.citations = [MagicMock(to_dict=MagicMock(return_value={"source": "kb"}))]
        gen.assembler.assemble.return_value = assembled
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.token_budget.finalize_tokens = AsyncMock()
        brand_config = _make_brand_config()
        gen.brand_voice.get_config = AsyncMock(return_value=brand_config)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={
                "content": "To reset your password, go to Settings > Security.",
                "model": "gpt-4",
                "provider": "openai",
                "tier": "medium",
            }
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result(
                overall_pass=True, overall_score=0.92
            )
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="To reset your password, go to Settings > Security."
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request(
                    query="How do I reset my password?",
                    variant_type="parwa",
                    conversation_history=[
                        {"role": "user", "content": "I forgot my password"}
                    ],
                    customer_metadata={"name": "Alice", "tier": "pro"},
                    intent_type="password_reset",
                )
                result = await gen.generate(req)

        assert isinstance(result, ResponseGenerationResult)
        assert result.clara_passed is True
        assert result.clara_score == 0.92
        assert result.rag_context_used is True
        assert result.confidence_score == 0.8
        assert result.template_used is False
        assert result.generation_time_ms >= 0

    @pytest.mark.asyncio
    async def test_full_pipeline_with_validation_issues(self, gen):
        """Brand validation violations are collected in quality_issues."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        brand_config = _make_brand_config()
        gen.brand_voice.get_config = AsyncMock(return_value=brand_config)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Response with issues"}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        validation = MagicMock()
        validation.is_valid = False
        validation.violations = ["Used prohibited word: 'sorry'"]
        validation.warnings = ["Tone could be warmer"]
        validation.suggested_fixes = ["Replace 'sorry' with 'apologize'"]
        gen.brand_voice.validate_response = AsyncMock(return_value=validation)
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="Response with issues"
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request()
                result = await gen.generate(req)
                assert any("prohibited" in i for i in result.quality_issues)
                assert any("Brand warning" in i for i in result.quality_issues)

    @pytest.mark.asyncio
    async def test_mini_parwa_variant(self, gen):
        """mini_parwa variant uses smaller token budgets."""
        gen.sentiment_analyzer.analyze = AsyncMock(
            return_value=_make_sentiment_result()
        )
        gen.rag_retriever.retrieve = AsyncMock(return_value=None)
        gen.token_budget.initialize_budget = AsyncMock()
        gen.token_budget.check_overflow = AsyncMock(
            return_value=_MockOverflowResult()
        )
        gen.token_budget.reserve_tokens = AsyncMock(
            return_value=_MockReserveResult()
        )
        gen.brand_voice.get_config = AsyncMock(return_value=None)
        gen.brand_voice.get_response_guidelines = AsyncMock(return_value=None)
        gen.smart_router.route = MagicMock(return_value=MagicMock())
        gen.smart_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "Mini response"}
        )
        gen.clara_gate.evaluate = AsyncMock(
            return_value=_make_clara_result()
        )
        gen.brand_voice.validate_response = AsyncMock(
            return_value=MagicMock(is_valid=True, violations=[], warnings=[])
        )
        gen.brand_voice.merge_with_brand_voice = AsyncMock(
            return_value="Mini response"
        )
        with patch("app.core.response_formatters.create_default_registry"):
            with patch("app.core.smart_router.AtomicStepType", MagicMock()):
                req = _make_request(variant_type="mini_parwa")
                result = await gen.generate(req)
                assert isinstance(result, ResponseGenerationResult)
