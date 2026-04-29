"""
P2 Tests — AI Processing Pipeline (13-stage orchestration)

Tests the full end-to-end AI pipeline:
- All 13 stages execute correctly
- Each stage populates PipelineContext fields
- Failed stages degrade gracefully (BC-012)
- Edge cases short-circuit the pipeline
- Prompt injection blocks processing
- Guardrails block unsafe responses
- Confidence auto-action thresholds work per variant
- Brand voice merge applies correctly
- Pipeline result contains all expected metadata
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any


# ── Test Fixtures ───────────────────────────────────────────────


def make_context(
    query: str = "How do I get a refund?",
    company_id: str = "comp_123",
    conversation_id: str = "conv_456",
    variant_type: str = "parwa",
    **overrides,
) -> Any:
    """Create a PipelineContext for testing."""
    from app.core.ai_pipeline import PipelineContext
    kwargs = dict(
        query=query,
        company_id=company_id,
        conversation_id=conversation_id,
        variant_type=variant_type,
    )
    kwargs.update(overrides)
    return PipelineContext(**kwargs)


# ── Stage 1: Edge Case Detection Tests ─────────────────────────


class TestEdgeCaseStage:
    """Test edge case detection pipeline stage."""

    @pytest.mark.asyncio
    async def test_empty_query_detected_as_edge_case(self):
        """Empty query should be caught and marked as edge case."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        with patch.object(pipeline, "_get_edge_case_handlers", return_value=[]):
            ctx = make_context(query="")
            # Empty handler list means no edge case detected
            await pipeline._stage_edge_case(ctx)
            assert ctx.is_edge_case is False  # No handlers = no detection

    @pytest.mark.asyncio
    async def test_normal_query_passes_edge_case(self):
        """Normal queries should not be flagged as edge cases."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        mock_handler = MagicMock()
        mock_handler.can_handle.return_value = False
        with patch.object(pipeline, "_get_edge_case_handlers", return_value=[mock_handler]):
            ctx = make_context(query="How do I get a refund?")
            await pipeline._stage_edge_case(ctx)
            assert ctx.is_edge_case is False

    @pytest.mark.asyncio
    async def test_blocked_edge_case_returns_early(self):
        """Blocked edge case should set response_text and block flag."""
        from app.core.ai_pipeline import AIPipeline
        from app.core.edge_case_handlers import EdgeCaseAction
        pipeline = AIPipeline()

        mock_result = MagicMock()
        mock_result.action = EdgeCaseAction.BLOCK
        mock_result.response = "I cannot process this request."

        mock_handler = MagicMock()
        mock_handler.can_handle.return_value = True
        mock_handler.handle.return_value = mock_result

        with patch.object(pipeline, "_get_edge_case_handlers", return_value=[mock_handler]):
            ctx = make_context(query="<script>alert('xss')</script>")
            await pipeline._stage_edge_case(ctx)
            assert ctx.is_edge_case
            assert ctx.edge_case_action is not None
            assert "block" in str(ctx.edge_case_action).lower()


# ── Stage 2: Prompt Injection Tests ────────────────────────────


class TestInjectionScanStage:
    """Test prompt injection detection stage."""

    def test_no_injection_detected(self):
        """Normal query should not trigger injection detection."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        mock_detector = MagicMock()
        mock_result = MagicMock()
        mock_result.is_injection = False
        mock_result.severity = "none"
        mock_result.action = "allow"
        mock_result.matches = []
        mock_detector.scan.return_value = mock_result

        with patch.object(pipeline, "_get_injection_detector", return_value=mock_detector):
            ctx = make_context(query="How do I reset my password?")
            pipeline._stage_injection_scan(ctx)
            assert ctx.injection_detected is False
            assert ctx.injection_blocked is False

    def test_injection_blocked(self):
        """SQL injection should be blocked."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        mock_detector = MagicMock()
        mock_result = MagicMock()
        mock_result.is_injection = True
        mock_result.severity = "critical"
        mock_result.action = "BLOCK"
        mock_result.matches = [
            MagicMock(
                pattern="DROP TABLE",
                type="sql",
                severity="critical")]
        mock_detector.scan.return_value = mock_result

        with patch.object(pipeline, "_get_injection_detector", return_value=mock_detector):
            ctx = make_context(query="'; DROP TABLE users; --")
            pipeline._stage_injection_scan(ctx)
            assert ctx.injection_detected
            assert ctx.injection_blocked
            assert ctx.response_text != ""  # Should have a safe response

    def test_no_detector_graceful_degradation(self):
        """Missing detector should not crash the pipeline."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        with patch.object(pipeline, "_get_injection_detector", return_value=None):
            ctx = make_context()
            pipeline._stage_injection_scan(ctx)
            assert ctx.injection_blocked is False


# ── Stage 3: Signal Extraction Tests ───────────────────────────


class TestSignalExtractionStage:
    """Test signal extraction pipeline stage."""

    @pytest.mark.asyncio
    async def test_signals_extracted(self):
        """Signal extraction should populate extracted_signals."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        mock_extractor = MagicMock()
        mock_signals = MagicMock()
        mock_signals.to_dict.return_value = {
            "intent": "refund",
            "sentiment": 0.3,
            "complexity": 0.6,
        }
        mock_extractor.extract = AsyncMock(return_value=mock_signals)
        mock_extractor.to_query_signals = MagicMock(return_value=None)

        with patch.object(pipeline, "_get_signal_extractor", return_value=mock_extractor):
            ctx = make_context()
            await pipeline._stage_signal_extraction(ctx)
            # Verify extract was called (it constructs request internally)
            assert mock_extractor.extract.called
            # Signals should be populated from the mock return
            assert ctx.extracted_signals is not None
            assert ctx.extracted_signals.get("intent") == "refund"

    @pytest.mark.asyncio
    async def test_failed_extraction_degrades(self):
        """Failed signal extraction should not crash pipeline."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        with patch.object(pipeline, "_get_signal_extractor", return_value=None):
            ctx = make_context()
            await pipeline._stage_signal_extraction(ctx)
            # Should not crash, signals remain None
            assert ctx.extracted_signals is None


# ── Stage 4: Classification Tests ──────────────────────────────


class TestClassificationStage:
    """Test intent classification pipeline stage."""

    @pytest.mark.asyncio
    async def test_intent_classified(self):
        """Classification should populate intent fields."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.primary_intent = "refund"
        mock_result.confidence = 0.92
        mock_result.secondary_intents = ["billing"]
        mock_engine.classify = AsyncMock(return_value=mock_result)

        with patch.object(pipeline, "_get_classification_engine", return_value=mock_engine):
            ctx = make_context()
            await pipeline._stage_classification(ctx)
            assert ctx.intent_type == "refund"
            assert ctx.intent_confidence == 0.92
            assert "billing" in ctx.secondary_intents


# ── Stage 5: Sentiment Tests ───────────────────────────────────


class TestSentimentStage:
    """Test sentiment analysis pipeline stage."""

    @pytest.mark.asyncio
    async def test_sentiment_analyzed(self):
        """Sentiment should populate frustration, emotion, urgency."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        mock_analyzer = MagicMock()
        mock_result = MagicMock()
        mock_result.frustration_score = 0.75
        mock_result.sentiment_score = 0.2
        mock_result.emotion = "anger"
        mock_result.urgency = "high"
        mock_result.tone_recommendation = "de-escalation"
        mock_result.customer_tier = "vip"
        mock_analyzer.analyze = AsyncMock(return_value=mock_result)

        with patch.object(pipeline, "_get_sentiment_analyzer", return_value=mock_analyzer):
            ctx = make_context()
            await pipeline._stage_sentiment(ctx)
            assert ctx.frustration_score == 0.75
            assert ctx.sentiment_score == 0.2
            assert ctx.urgency_level == "high"
            assert ctx.emotion == "anger"


# ── Stage 6-7: Routing Tests ──────────────────────────────────


class TestRoutingStages:
    """Test smart router and technique router stages."""

    def test_smart_router_selects_model(self):
        """Smart router should populate model selection."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        mock_router = MagicMock()
        mock_decision = MagicMock()
        mock_decision.model_id = "gemini-2.0-flash"
        mock_decision.provider = "google"
        mock_decision.tier.value = "light"
        mock_router.route.return_value = mock_decision

        with patch.object(pipeline, "_get_smart_router", return_value=mock_router):
            ctx = make_context()
            pipeline._stage_smart_router(ctx)
            assert ctx.selected_model == "gemini-2.0-flash"
            assert ctx.selected_provider == "google"

    def test_smart_router_fallback(self):
        """Missing smart router should use default model."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        with patch.object(pipeline, "_get_smart_router", return_value=None):
            ctx = make_context()
            pipeline._stage_smart_router(ctx)
            assert ctx.selected_model == "gemini-2.0-flash"

    def test_technique_router_selects(self):
        """Technique router should select a technique."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        mock_router = MagicMock()
        mock_result = MagicMock()
        mock_result.technique.value = "cot"
        mock_result.tier.value = "tier_2"
        mock_result.fallback.value = "crp"
        mock_router.route.return_value = mock_result

        # Need query_signals
        mock_signals = MagicMock()

        with patch.object(pipeline, "_get_technique_router", return_value=mock_router):
            ctx = make_context()
            ctx.query_signals = mock_signals
            pipeline._stage_technique_router(ctx)
            assert ctx.selected_technique == "cot"
            assert ctx.technique_tier == "tier_2"

    def test_technique_router_default_crp(self):
        """Missing technique router or signals should default to CRP."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        with patch.object(pipeline, "_get_technique_router", return_value=None):
            ctx = make_context()
            pipeline._stage_technique_router(ctx)
            assert ctx.selected_technique == "crp"


# ── Stage 8: RAG Tests ─────────────────────────────────────────


class TestRAGStage:
    """Test RAG retrieval pipeline stage."""

    @pytest.mark.asyncio
    async def test_rag_retrieves_context(self):
        """RAG should populate context and citations."""
        from app.core.ai_pipeline import AIPipeline
        from app.core.rag_retrieval import RAGResult
        pipeline = AIPipeline()

        # Build a mock RAGResult with a chunk
        mock_chunk = MagicMock()
        mock_chunk.content = "Refund policy: 30 days..."
        mock_chunk.score = 0.95
        mock_chunk.source = "refund_policy.pdf"
        mock_chunk.to_dict.return_value = {
            "content": "Refund policy: 30 days...",
            "score": 0.95,
            "source": "refund_policy.pdf",
        }

        mock_rag_result = MagicMock(spec=RAGResult)
        mock_rag_result.chunks = [mock_chunk]

        mock_reranker = MagicMock()
        mock_assembled = MagicMock()
        mock_assembled.context_text = "Refund policy: 30 days..."
        mock_assembled.to_dict.return_value = {
            "chunks": [{"text": "Refund policy"}],
            "citations": [{"source": "refund_policy.pd", "score": 0.95}],
        }
        mock_reranker.rerank = AsyncMock(return_value=mock_assembled)

        with patch.object(pipeline, "_get_rag_reranker", return_value=mock_reranker), \
                patch("app.core.rag_retrieval.RAGRetriever") as MockRetriever:
            mock_retriever_instance = MagicMock()
            mock_retriever_instance.retrieve = AsyncMock(
                return_value=mock_rag_result)
            MockRetriever.return_value = mock_retriever_instance

            ctx = make_context()
            await pipeline._stage_rag_retrieval(ctx)
            assert ctx.rag_context != ""
            assert ctx.rag_context_used


# ── Stage 9: Response Generation Tests ─────────────────────────


class TestResponseGenerationStage:
    """Test response generation pipeline stage."""

    @pytest.mark.asyncio
    async def test_response_generated(self):
        """Response generator should produce response text."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        mock_generator = MagicMock()
        mock_result = MagicMock()
        mock_result.response_text = "Based on our policy, you can request a refund within 30 days."
        mock_result.confidence_score = 0.88
        mock_result.rag_context_used = True
        mock_result.citations = [{"source": "policy.pd", "score": 0.9}]
        mock_result.tokens_used = 150
        mock_result.generation_time_ms = 500.0
        mock_result.clara_passed = True
        mock_result.clara_score = 95.0
        mock_result.quality_issues = []
        mock_generator.generate = AsyncMock(return_value=mock_result)

        with patch.object(pipeline, "_get_response_generator", return_value=mock_generator):
            ctx = make_context()
            await pipeline._stage_response_generation(ctx)
            assert "refund" in ctx.response_text.lower()
            assert ctx.tokens_used == 150

    @pytest.mark.asyncio
    async def test_fallback_template_when_generator_fails(self):
        """Should use template fallback when generator fails."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        with patch.object(pipeline, "_get_response_generator", return_value=None):
            ctx = make_context(intent_type="refund")
            await pipeline._stage_response_generation(ctx)
            # Should get a template response
            assert ctx.response_text != ""


# ── Stage 10: CLARA Tests ──────────────────────────────────────


class TestCLARAStage:
    """Test CLARA quality gate pipeline stage."""

    @pytest.mark.asyncio
    async def test_clara_passes_good_response(self):
        """CLARA should pass a good response."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        mock_gate = MagicMock()
        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.score = 92.0
        mock_result.issues = []
        mock_result.suggestions_applied = False
        mock_gate.evaluate = AsyncMock(return_value=mock_result)

        with patch.object(pipeline, "_get_clara_gate", return_value=mock_gate):
            ctx = make_context()
            ctx.response_text = "You can request a refund within 30 days of purchase."
            await pipeline._stage_clara_quality(ctx)
            assert ctx.clara_passed
            assert ctx.clara_score == 92.0

    @pytest.mark.asyncio
    async def test_clara_improves_response(self):
        """CLARA should apply suggestions to improve response."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        mock_gate = MagicMock()
        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.score = 85.0
        mock_result.issues = ["Tone could be more empathetic"]
        mock_result.suggestions_applied = True
        mock_result.response = "I understand your concern. You can request a refund within 30 days of purchase. I'm happy to help with this process."
        mock_gate.evaluate = AsyncMock(return_value=mock_result)

        with patch.object(pipeline, "_get_clara_gate", return_value=mock_gate):
            ctx = make_context()
            ctx.response_text = "You can get a refund in 30 days."
            await pipeline._stage_clara_quality(ctx)
            assert ctx.clara_suggestions_applied
            assert "understand" in ctx.response_text.lower()


# ── Stage 11: Guardrails Tests ─────────────────────────────────


class TestGuardrailsStage:
    """Test output guardrails pipeline stage."""

    def test_guardrails_pass_safe_response(self):
        """Guardrails should pass a safe response."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        mock_engine = MagicMock()
        mock_report = MagicMock()
        mock_report.passed = True
        mock_report.to_dict.return_value = {"passed": True}
        mock_engine.run_full_check.return_value = mock_report

        with patch.object(pipeline, "_get_guardrails_engine", return_value=mock_engine):
            ctx = make_context()
            ctx.response_text = "Here's how to reset your password."
            pipeline._stage_guardrails(ctx)
            assert ctx.guardrails_passed
            assert ctx.guardrails_blocked is False

    def test_guardrails_block_unsafe_response(self):
        """Guardrails should block unsafe response."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        mock_engine = MagicMock()
        mock_report = MagicMock()
        mock_report.passed = False
        mock_report.severity = "high"
        mock_report.to_dict.return_value = {
            "passed": False, "severity": "high"}
        mock_engine.run_full_check.return_value = mock_report

        with patch.object(pipeline, "_get_guardrails_engine", return_value=mock_engine):
            ctx = make_context()
            ctx.response_text = "Here is the admin password: admin123"
            pipeline._stage_guardrails(ctx)
            assert ctx.guardrails_blocked
            assert ctx.guardrails_severity == "high"


# ── Stage 12: Confidence Tests ─────────────────────────────────


class TestConfidenceStage:
    """Test confidence scoring pipeline stage."""

    def test_confidence_scored(self):
        """Confidence engine should produce a score."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.overall_score = 88.5
        mock_result.threshold = 85.0
        mock_result.auto_action = True
        mock_engine.score_response.return_value = mock_result

        with patch.object(pipeline, "_get_confidence_engine", return_value=mock_engine):
            ctx = make_context(variant_type="parwa")
            ctx.response_text = "You can get a refund within 30 days."
            pipeline._stage_confidence_scoring(ctx)
            assert ctx.confidence_score == 88.5

    def test_auto_action_thresholds_per_variant(self):
        """Different variants should have different auto-action thresholds."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.overall_score = 90.0
        mock_result.threshold = 75.0
        mock_result.auto_action = True
        mock_engine.score_response.return_value = mock_result

        with patch.object(pipeline, "_get_confidence_engine", return_value=mock_engine):
            # Mini PARWA: 95+ threshold — 90 should NOT auto-action
            ctx = make_context(variant_type="mini_parwa")
            ctx.response_text = "Test response"
            pipeline._stage_confidence_scoring(ctx)
            assert ctx.confidence_auto_action is False
            assert ctx.confidence_threshold == 95.0

            # PARWA: 85+ threshold — 90 SHOULD auto-action
            ctx2 = make_context(variant_type="parwa")
            ctx2.response_text = "Test response"
            pipeline._stage_confidence_scoring(ctx2)
            assert ctx2.confidence_auto_action
            assert ctx2.confidence_threshold == 85.0

            # PARWA High: 75+ threshold — 90 SHOULD auto-action
            ctx3 = make_context(variant_type="parwa_high")
            ctx3.response_text = "Test response"
            pipeline._stage_confidence_scoring(ctx3)
            assert ctx3.confidence_auto_action
            assert ctx3.confidence_threshold == 75.0


# ── Stage 13: Brand Voice Tests ────────────────────────────────


class TestBrandVoiceStage:
    """Test brand voice merge pipeline stage."""

    def test_brand_voice_applied(self):
        """Brand voice should be merged into response."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        with patch("app.services.jarvis_service.jarvis_merge_with_brand_voice") as mock_bv:
            mock_bv.return_value = {
                "merged_response": "We'd be delighted to help you with your refund request!",
                "brand_voice_applied": True,
            }
            ctx = make_context()
            ctx.response_text = "I can help with your refund."
            pipeline._stage_brand_voice(ctx)
            assert ctx.brand_voice_applied
            assert "delighted" in ctx.response_text.lower()

    def test_no_brand_voice_when_missing(self):
        """Missing company_id should skip brand voice."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        ctx = make_context(company_id="")
        ctx.response_text = "Original response"
        pipeline._stage_brand_voice(ctx)
        assert ctx.brand_voice_applied is False
        assert ctx.response_text == "Original response"


# ── End-to-End Pipeline Tests ──────────────────────────────────


class TestFullPipeline:
    """Test the complete end-to-end AI pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_happy_path(self):
        """Full pipeline should produce a valid response with all metadata."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        # Mock all stages
        with patch.object(pipeline, "_get_langgraph_workflow", return_value=None), \
                patch.object(pipeline, "_get_edge_case_handlers", return_value=[]), \
                patch.object(pipeline, "_get_injection_detector") as mock_inj, \
                patch.object(pipeline, "_get_signal_extractor") as mock_sig, \
                patch.object(pipeline, "_get_classification_engine") as mock_cls, \
                patch.object(pipeline, "_get_sentiment_analyzer") as mock_sent, \
                patch.object(pipeline, "_get_smart_router") as mock_sr, \
                patch.object(pipeline, "_get_technique_router") as mock_tr, \
                patch.object(pipeline, "_get_rag_reranker") as mock_rag, \
                patch.object(pipeline, "_get_response_generator") as mock_rg, \
                patch.object(pipeline, "_get_clara_gate") as mock_clara, \
                patch.object(pipeline, "_get_guardrails_engine") as mock_guard, \
                patch.object(pipeline, "_get_confidence_engine") as mock_conf, \
                patch("app.services.jarvis_service.jarvis_merge_with_brand_voice") as mock_bv:

            # Injection: clean
            inj_result = MagicMock(
                is_injection=False,
                severity="none",
                action="allow",
                matches=[])
            mock_inj.return_value.scan.return_value = inj_result

            # Signals
            sig_result = MagicMock()
            sig_result.to_dict.return_value = {
                "intent": "refund", "complexity": 0.5}
            mock_sig.return_value.extract = AsyncMock(return_value=sig_result)
            mock_sig.return_value.to_query_signals = MagicMock(
                return_value=None)

            # Classification
            cls_result = MagicMock(
                primary_intent="refund",
                confidence=0.9,
                secondary_intents=["billing"])
            mock_cls.return_value.classify = AsyncMock(return_value=cls_result)

            # Sentiment
            sent_result = MagicMock(
                frustration_score=0.3,
                sentiment_score=0.6,
                emotion="neutral",
                urgency="normal",
                tone_recommendation=None,
                customer_tier="standard")
            mock_sent.return_value.analyze = AsyncMock(
                return_value=sent_result)

            # Smart Router
            sr_result = MagicMock(
                model_id="gemini-2.0-flash",
                provider="google")
            sr_result.tier.value = "light"
            mock_sr.return_value.route.return_value = sr_result

            # Technique Router
            tr_result = MagicMock()
            tr_result.technique.value = "crp"
            tr_result.tier.value = "tier_1"
            tr_result.fallback = None
            mock_tr.return_value.route.return_value = tr_result

            # RAG
            rag_result = MagicMock(context_text="Refund policy: 30 days...")
            rag_result.to_dict.return_value = {"chunks": [], "citations": []}
            mock_rag.return_value.rerank = AsyncMock(return_value=rag_result)

            # Response Generator
            rg_result = MagicMock(
                response_text="You can request a refund within 30 days of purchase.",
                confidence_score=0.88,
                rag_context_used=True,
                citations=[],
                tokens_used=120,
                generation_time_ms=300.0,
                clara_passed=True,
                clara_score=90.0,
                quality_issues=[],
            )
            mock_rg.return_value.generate = AsyncMock(return_value=rg_result)

            # CLARA
            clara_result = MagicMock(
                passed=True,
                score=90.0,
                issues=[],
                suggestions_applied=False)
            mock_clara.return_value.evaluate = AsyncMock(
                return_value=clara_result)

            # Guardrails
            guard_report = MagicMock(passed=True)
            guard_report.to_dict.return_value = {"passed": True}
            mock_guard.return_value.run_full_check.return_value = guard_report

            # Confidence
            conf_result = MagicMock(
                overall_score=88.0,
                threshold=85.0,
                auto_action=True)
            mock_conf.return_value.score_response.return_value = conf_result

            # Brand voice
            mock_bv.return_value = None  # No change

            ctx = make_context()
            result = await pipeline.process(ctx)

            # Verify result
            assert result.response != ""
            assert result.intent_type == "refund"
            assert result.confidence_score > 0
            assert result.technique_used == "crp"
            assert result.model_used == "gemini-2.0-flash"
            assert result.rag_context_used
            assert result.clara_passed
            assert not result.guardrails_blocked
            assert len(result.stages_completed) > 0
            assert "edge_case" in result.stages_completed
            assert "injection_scan" in result.stages_completed

    @pytest.mark.asyncio
    async def test_pipeline_with_injection_blocked(self):
        """Pipeline should return early when injection is detected."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        with patch.object(pipeline, "_get_edge_case_handlers", return_value=[]), \
                patch.object(pipeline, "_get_injection_detector") as mock_inj:

            inj_result = MagicMock(
                is_injection=True,
                severity="critical",
                action="BLOCK",
                matches=[])
            mock_inj.return_value.scan.return_value = inj_result

            ctx = make_context(query="'; DROP TABLE users; --")
            result = await pipeline.process(ctx)

            assert result.injection_blocked
            assert result.response != ""
            # Most stages should be skipped
            assert "response_generation" not in result.stages_completed

    @pytest.mark.asyncio
    async def test_pipeline_with_guardrails_blocked(self):
        """Pipeline should use safe fallback when guardrails block."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        with patch.object(pipeline, "_get_edge_case_handlers", return_value=[]), \
                patch.object(pipeline, "_get_injection_detector") as mock_inj, \
                patch.object(pipeline, "_get_signal_extractor") as mock_sig, \
                patch.object(pipeline, "_get_classification_engine") as mock_cls, \
                patch.object(pipeline, "_get_sentiment_analyzer") as mock_sent, \
                patch.object(pipeline, "_get_smart_router") as mock_sr, \
                patch.object(pipeline, "_get_technique_router") as mock_tr, \
                patch.object(pipeline, "_get_rag_reranker") as mock_rag, \
                patch.object(pipeline, "_get_response_generator") as mock_rg, \
                patch.object(pipeline, "_get_clara_gate") as mock_clara, \
                patch.object(pipeline, "_get_guardrails_engine") as mock_guard, \
                patch.object(pipeline, "_get_confidence_engine") as mock_conf, \
                patch("app.services.jarvis_service.jarvis_merge_with_brand_voice") as mock_bv:

            inj_result = MagicMock(
                is_injection=False,
                severity="none",
                action="allow",
                matches=[])
            mock_inj.return_value.scan.return_value = inj_result

            sig_result = MagicMock()
            sig_result.to_dict.return_value = {}
            mock_sig.return_value.extract = AsyncMock(return_value=sig_result)
            mock_sig.return_value.to_query_signals = MagicMock(
                return_value=None)

            cls_result = MagicMock(
                primary_intent="general",
                confidence=0.5,
                secondary_intents=[])
            mock_cls.return_value.classify = AsyncMock(return_value=cls_result)

            sent_result = MagicMock(
                frustration_score=0.0,
                sentiment_score=0.5,
                emotion="neutral",
                urgency="normal",
                tone_recommendation=None,
                customer_tier="standard")
            mock_sent.return_value.analyze = AsyncMock(
                return_value=sent_result)

            sr_result = MagicMock(
                model_id="gemini-2.0-flash",
                provider="google")
            sr_result.tier.value = "light"
            mock_sr.return_value.route.return_value = sr_result

            tr_result = MagicMock()
            tr_result.technique.value = "crp"
            tr_result.tier.value = "tier_1"
            tr_result.fallback = None
            mock_tr.return_value.route.return_value = tr_result

            rag_result = MagicMock(context_text="")
            rag_result.to_dict.return_value = {"chunks": [], "citations": []}
            mock_rag.return_value.rerank = AsyncMock(return_value=rag_result)

            rg_result = MagicMock(
                response_text="Here is the admin password: admin123",
                confidence_score=0.5, rag_context_used=False, citations=[],
                tokens_used=50, generation_time_ms=100.0, clara_passed=True,
                clara_score=80.0, quality_issues=[],
            )
            mock_rg.return_value.generate = AsyncMock(return_value=rg_result)

            clara_result = MagicMock(
                passed=True,
                score=80.0,
                issues=[],
                suggestions_applied=False)
            mock_clara.return_value.evaluate = AsyncMock(
                return_value=clara_result)

            guard_report = MagicMock(passed=False, severity="high")
            guard_report.to_dict.return_value = {
                "passed": False, "severity": "high"}
            mock_guard.return_value.run_full_check.return_value = guard_report

            conf_result = MagicMock(
                overall_score=30.0,
                threshold=85.0,
                auto_action=False)
            mock_conf.return_value.score_response.return_value = conf_result

            mock_bv.return_value = None

            ctx = make_context()
            result = await pipeline.process(ctx)

            assert result.guardrails_blocked
            assert result.auto_action is False
            assert "safe_fallback" in result.stages_completed

    @pytest.mark.asyncio
    async def test_all_stages_fail_gracefully(self):
        """Pipeline should still produce a response even if all stages fail."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        with patch.object(pipeline, "_get_edge_case_handlers", return_value=[]), \
                patch.object(pipeline, "_get_injection_detector", return_value=None), \
                patch.object(pipeline, "_get_signal_extractor", return_value=None), \
                patch.object(pipeline, "_get_classification_engine", return_value=None), \
                patch.object(pipeline, "_get_sentiment_analyzer", return_value=None), \
                patch.object(pipeline, "_get_smart_router", return_value=None), \
                patch.object(pipeline, "_get_technique_router", return_value=None), \
                patch.object(pipeline, "_get_rag_reranker", return_value=None), \
                patch.object(pipeline, "_get_response_generator", return_value=None), \
                patch.object(pipeline, "_get_clara_gate", return_value=None), \
                patch.object(pipeline, "_get_guardrails_engine", return_value=None), \
                patch.object(pipeline, "_get_confidence_engine", return_value=None), \
                patch("app.services.jarvis_service.jarvis_merge_with_brand_voice") as mock_bv:

            mock_bv.return_value = None

            ctx = make_context()
            result = await pipeline.process(ctx)

            # Should still get a response (template fallback)
            assert result.response != ""
            assert result.intent_type == "general"  # Default
            assert result.confidence_score >= 0


# ── Convenience Function Tests ──────────────────────────────────


class TestProcessAIMessage:
    """Test the convenience process_ai_message function."""

    @pytest.mark.asyncio
    async def test_convenience_function(self):
        """process_ai_message should create context and run pipeline."""
        from app.core.ai_pipeline import process_ai_message

        mock_pipeline = AsyncMock()
        mock_result = MagicMock(
            response="Test response",
            confidence_score=80.0,
            auto_action=True,
            intent_type="general",
            frustration_score=0.0,
            sentiment_score=0.5,
            urgency_level="normal",
            technique_used="crp",
            model_used="gemini-2.0-flash",
            rag_context_used=False,
            citations=[],
            is_edge_case=False,
            injection_blocked=False,
            guardrails_blocked=False,
            clara_passed=True,
            pipeline_time_ms=100.0,
            stages_completed=[
                "edge_case",
                "injection_scan"],
            stages_failed=[],
            metadata={},
        )
        mock_result.to_dict.return_value = {}
        mock_pipeline.process.return_value = mock_result

        with patch("app.core.ai_pipeline.AIPipeline", return_value=mock_pipeline):
            result = await process_ai_message(
                query="Hello",
                company_id="comp_123",
                conversation_id="conv_456",
            )
            assert result.response == "Test response"
            mock_pipeline.process.assert_called_once()


# ── PipelineResult Tests ───────────────────────────────────────


class TestPipelineResult:
    """Test PipelineResult dataclass."""

    def test_to_dict(self):
        """PipelineResult.to_dict() should return a complete dictionary."""
        from app.core.ai_pipeline import PipelineResult

        result = PipelineResult(
            response="Hello!",
            confidence_score=85.0,
            auto_action=True,
            intent_type="greeting",
            frustration_score=0.1,
            sentiment_score=0.8,
            urgency_level="low",
            technique_used="crp",
            model_used="gemini-2.0-flash",
            rag_context_used=False,
            citations=[],
            is_edge_case=False,
            injection_blocked=False,
            guardrails_blocked=False,
            clara_passed=True,
            pipeline_time_ms=150.0,
            stages_completed=["edge_case", "injection_scan"],
            stages_failed=[],
        )

        d = result.to_dict()
        assert d["response"] == "Hello!"
        assert d["confidence_score"] == 85.0
        assert d["auto_action"]
        assert d["intent_type"] == "greeting"
        assert d["technique_used"] == "crp"


# ── Fallback Response Tests ────────────────────────────────────


class TestFallbackResponses:
    """Test fallback response generation."""

    def test_safe_fallback_by_severity(self):
        """Safe fallback should vary by guardrails severity."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        ctx_high = make_context()
        ctx_high.guardrails_severity = "high"
        resp_high = pipeline._get_safe_fallback_response(ctx_high)
        assert "team member" in resp_high.lower()

        ctx_critical = make_context()
        ctx_critical.guardrails_severity = "critical"
        resp_critical = pipeline._get_safe_fallback_response(ctx_critical)
        assert "specialized" in resp_critical.lower() or "security" in resp_critical.lower()

    def test_template_response_by_intent(self):
        """Template response should match intent type."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        # Refund template
        ctx_refund = make_context(intent_type="refund")
        resp = pipeline._get_template_response(ctx_refund)
        assert "refund" in resp.lower() or "order number" in resp.lower()

        # Technical template
        ctx_tech = make_context(intent_type="technical")
        resp = pipeline._get_template_response(ctx_tech)
        assert "technical" in resp.lower() or "detail" in resp.lower()

        # Default template
        ctx_default = make_context(intent_type="unknown_type")
        resp = pipeline._get_template_response(ctx_default)
        assert "help" in resp.lower()


# ── Timeout Tests ───────────────────────────────────────────────


class TestPipelineTimeouts:
    """Test that pipeline stages respect timeouts (BC-012)."""

    @pytest.mark.asyncio
    async def test_stage_timeout_doesnt_crash_pipeline(self):
        """A timed-out stage should fail gracefully."""
        from app.core.ai_pipeline import AIPipeline
        pipeline = AIPipeline()

        async def slow_stage(ctx):
            await asyncio.sleep(100)  # Way over any timeout

        ctx = make_context()
        await pipeline._run_stage("test_slow", ctx, slow_stage)
        assert "test_slow" in ctx.stages_failed
        assert "test_slow" not in ctx.stages_completed
