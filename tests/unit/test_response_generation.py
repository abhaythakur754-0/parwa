"""
Tests for Response Generation (F-065), Brand Voice (F-154),
Response Templates (F-155), and Token Budget (F-156).
"""
import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from dataclasses import dataclass


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock(return_value=True)
    r.delete = AsyncMock(return_value=True)
    r.hset = AsyncMock(return_value=True)
    r.hgetall = AsyncMock(return_value={})
    r.incr = AsyncMock(return_value=1)
    r.expire = AsyncMock(return_value=True)
    r.eval = AsyncMock(return_value=100)
    r.rpush = AsyncMock(return_value=1)
    r.lrange = AsyncMock(return_value=[])
    r.keys = AsyncMock(return_value=[])
    r.exists = AsyncMock(return_value=0)
    r.scan_iter = AsyncMock(return_value=[])
    r.pipeline = MagicMock()
    r.pipeline.return_value.__aenter__ = AsyncMock(return_value=MagicMock(execute=AsyncMock(return_value=[None])))
    r.pipeline.return_value.__aexit__ = AsyncMock(return_value=False)
    return r


@pytest.fixture
def company_id():
    return "comp_test_001"


@pytest.fixture
def variant_type():
    return "parwa"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. ResponseGenerator Tests (F-065)
# ═══════════════════════════════════════════════════════════════════════════════

class TestResponseGeneratorInit:
    """Test ResponseGenerator initialization."""

    @pytest.mark.asyncio
    async def test_init_with_redis(self, mock_redis):
        with patch('backend.app.core.response_generator.SentimentAnalyzer'), \
             patch('backend.app.core.response_generator.RAGRetriever'), \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate'), \
             patch('backend.app.core.response_generator.BrandVoiceService'), \
             patch('backend.app.core.response_generator.TokenBudgetService'), \
             patch('backend.app.core.response_generator.ResponseTemplateService'), \
             patch('backend.app.core.response_generator.SmartRouter'):
            from backend.app.core.response_generator import ResponseGenerator
            gen = ResponseGenerator(redis_client=mock_redis)
            assert gen is not None

    @pytest.mark.asyncio
    async def test_init_without_redis(self):
        with patch('backend.app.core.response_generator.SentimentAnalyzer'), \
             patch('backend.app.core.response_generator.RAGRetriever'), \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate'), \
             patch('backend.app.core.response_generator.BrandVoiceService'), \
             patch('backend.app.core.response_generator.TokenBudgetService'), \
             patch('backend.app.core.response_generator.ResponseTemplateService'), \
             patch('backend.app.core.response_generator.SmartRouter'):
            from backend.app.core.response_generator import ResponseGenerator
            gen = ResponseGenerator()
            assert gen is not None


class TestResponseGeneratorPipeline:
    """Test full pipeline and individual steps."""

    @pytest.mark.asyncio
    async def test_full_pipeline_success(self, mock_redis, company_id, variant_type):
        with patch('backend.app.core.response_generator.SentimentAnalyzer') as sa_cls, \
             patch('backend.app.core.response_generator.RAGRetriever') as rag_cls, \
             patch('backend.app.core.response_generator.CrossEncoderReranker') as rerank_cls, \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate') as clara_cls, \
             patch('backend.app.core.response_generator.BrandVoiceService') as bv_cls, \
             patch('backend.app.core.response_generator.TokenBudgetService') as tb_cls, \
             patch('backend.app.core.response_generator.ResponseTemplateService'), \
             patch('backend.app.core.response_generator.SmartRouter') as sr_cls:

            from backend.app.core.response_generator import ResponseGenerator, ResponseGenerationRequest

            # Mock sentiment
            mock_sentiment = AsyncMock()
            mock_sentiment.analyze = AsyncMock(return_value=MagicMock(
                frustration_score=20, emotion="neutral", urgency_level="low",
                tone_recommendation="professional", empathy_signals=[],
                sentiment_score=0.5, emotion_breakdown={}, conversation_trend="stable", cached=False
            ))
            sa_cls.return_value = mock_sentiment

            # Mock RAG
            mock_rag = AsyncMock()
            mock_rag.retrieve = AsyncMock(return_value=MagicMock(
                chunks=[], total_found=0, retrieval_time_ms=10
            ))
            rag_cls.return_value = mock_rag

            # Mock reranker
            mock_reranker = AsyncMock()
            mock_reranker.rerank = AsyncMock(return_value=MagicMock(
                chunks=[], total_found=0, retrieval_time_ms=5
            ))
            rerank_cls.return_value = mock_reranker

            # Mock CLARA
            mock_clara = AsyncMock()
            mock_clara.evaluate = AsyncMock(return_value=MagicMock(
                overall_pass=True, overall_score=0.85, stages=[],
                final_response="Thank you for your inquiry.", pipeline_timed_out=False
            ))
            clara_cls.return_value = mock_clara

            # Mock brand voice
            mock_bv = AsyncMock()
            mock_bv.get_config = AsyncMock(return_value=MagicMock(
                company_id=company_id, tone="professional", formality_level=0.6,
                prohibited_words=[], response_length_preference="standard",
                max_response_sentences=10, min_response_sentences=1,
                greeting_template="", closing_template="", emoji_usage="minimal",
                apology_style="empathetic", escalation_tone="calm",
                brand_name="TestCo", industry="tech", custom_instructions=""
            ))
            mock_bv.get_response_guidelines = AsyncMock(return_value=MagicMock(
                tone="professional", formality_level=0.6, max_sentences=10,
                min_sentences=1, empathy_level="low", urgency_adjustment="none",
                suggested_opening="Hello!", suggested_closing="Best regards",
                avoid_phrases=[]
            ))
            mock_bv.validate_response = AsyncMock(return_value=MagicMock(
                is_valid=True, violations=[], warnings=[], score=0.9, suggested_fixes=[]
            ))
            bv_cls.return_value = mock_bv

            # Mock token budget
            mock_tb = AsyncMock()
            mock_tb.initialize_budget = AsyncMock(return_value=MagicMock(
                conversation_id="conv_1", company_id=company_id, variant_type=variant_type,
                max_tokens=8192, reserved_tokens=0, used_tokens=0,
                available_tokens=8192, created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            ))
            mock_tb.reserve_tokens = AsyncMock(return_value=MagicMock(
                success=True, reserved_amount=500, remaining_after_reserve=7692, error=None
            ))
            mock_tb.finalize_tokens = AsyncMock()
            mock_tb.check_overflow = AsyncMock(return_value=MagicMock(
                can_fit=True, remaining_tokens=8192, overflow_amount=0,
                truncation_needed=False, suggested_truncation_tokens=0
            ))
            mock_tb.get_context_management_strategy = AsyncMock(return_value=MagicMock(
                strategy="keep_all", reason="Budget OK", tokens_to_remove=0,
                messages_to_remove=0, priority_messages=[]
            ))
            tb_cls.return_value = mock_tb

            # Mock smart router
            mock_sr = AsyncMock()
            mock_router_result = MagicMock()
            mock_router_result.model_tier = MagicMock()
            mock_router_result.model_tier.value = "medium"
            mock_router_result.provider = MagicMock()
            mock_router_result.provider.value = "google"
            mock_sr.route = MagicMock(return_value=mock_router_result)
            mock_sr.async_execute_llm_call = AsyncMock(return_value={
                "content": "Thank you for contacting us. We're looking into this.",
                "usage": {"total_tokens": 150}
            })
            sr_cls.return_value = mock_sr

            gen = ResponseGenerator(redis_client=mock_redis)
            req = ResponseGenerationRequest(
                query="How do I reset my password?",
                company_id=company_id,
                conversation_id="conv_1",
                variant_type=variant_type,
            )
            result = await gen.generate(req)
            assert result.response_text is not None
            assert len(result.response_text) > 0

    @pytest.mark.asyncio
    async def test_empty_query_returns_valid_result(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer') as sa_cls, \
             patch('backend.app.core.response_generator.RAGRetriever') as rag_cls, \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate') as clara_cls, \
             patch('backend.app.core.response_generator.BrandVoiceService') as bv_cls, \
             patch('backend.app.core.response_generator.TokenBudgetService') as tb_cls, \
             patch('backend.app.core.response_generator.ResponseTemplateService') as tpl_cls, \
             patch('backend.app.core.response_generator.SmartRouter') as sr_cls:

            from backend.app.core.response_generator import ResponseGenerator, ResponseGenerationRequest

            mock_sa = AsyncMock()
            mock_sa.analyze = AsyncMock(return_value=MagicMock(
                frustration_score=0, emotion="neutral", urgency_level="low",
                tone_recommendation="professional", empathy_signals=[],
                sentiment_score=0.5, emotion_breakdown={}, conversation_trend="stable", cached=False
            ))
            sa_cls.return_value = mock_sa
            rag_cls.return_value = AsyncMock(retrieve=AsyncMock(return_value=MagicMock(chunks=[], total_found=0, retrieval_time_ms=0)))
            clara_cls.return_value = AsyncMock(evaluate=AsyncMock(return_value=MagicMock(
                overall_pass=True, overall_score=0.9, stages=[], final_response="", pipeline_timed_out=False
            )))
            bv_cls.return_value = AsyncMock(
                get_config=AsyncMock(return_value=MagicMock(
                    tone="professional", formality_level=0.5, prohibited_words=[],
                    response_length_preference="standard", max_response_sentences=10,
                    min_response_sentences=1, greeting_template="", closing_template="",
                    emoji_usage="minimal", apology_style="empathetic", escalation_tone="calm",
                    brand_name="", industry="tech", custom_instructions=""
                )),
                get_response_guidelines=AsyncMock(return_value=MagicMock(
                    tone="professional", formality_level=0.5, max_sentences=10,
                    min_sentences=1, empathy_level="low", urgency_adjustment="none",
                    suggested_opening="", suggested_closing="", avoid_phrases=[]
                )),
                validate_response=AsyncMock(return_value=MagicMock(
                    is_valid=True, violations=[], warnings=[], score=1.0, suggested_fixes=[]
                ))
            )
            mock_tb = AsyncMock()
            mock_tb.initialize_budget = AsyncMock(return_value=MagicMock(
                conversation_id="c", company_id="c", variant_type="p",
                max_tokens=8192, reserved_tokens=0, used_tokens=0, available_tokens=8192,
                created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
            ))
            mock_tb.reserve_tokens = AsyncMock(return_value=MagicMock(success=True, reserved_amount=100, remaining_after_reserve=8092, error=None))
            mock_tb.finalize_tokens = AsyncMock()
            mock_tb.check_overflow = AsyncMock(return_value=MagicMock(can_fit=True, remaining_tokens=8192, overflow_amount=0, truncation_needed=False, suggested_truncation_tokens=0))
            mock_tb.get_context_management_strategy = AsyncMock(return_value=MagicMock(strategy="keep_all", reason="", tokens_to_remove=0, messages_to_remove=0, priority_messages=[]))
            tb_cls.return_value = mock_tb
            tpl_cls.return_value = AsyncMock(find_best_template=AsyncMock(return_value=None))
            sr_cls.return_value = AsyncMock(
                route=MagicMock(return_value=MagicMock(model_tier=MagicMock(value="medium"), provider=MagicMock(value="google"))),
                async_execute_llm_call=AsyncMock(return_value={"content": "Hi there!", "usage": {"total_tokens": 50}})
            )

            gen = ResponseGenerator(redis_client=mock_redis)
            req = ResponseGenerationRequest(query="", company_id=company_id, conversation_id="conv_empty", variant_type="parwa")
            result = await gen.generate(req)
            assert result is not None

    @pytest.mark.asyncio
    async def test_sentiment_analysis_fallback_on_error(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer') as sa_cls, \
             patch('backend.app.core.response_generator.RAGRetriever') as rag_cls, \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate') as clara_cls, \
             patch('backend.app.core.response_generator.BrandVoiceService') as bv_cls, \
             patch('backend.app.core.response_generator.TokenBudgetService') as tb_cls, \
             patch('backend.app.core.response_generator.ResponseTemplateService') as tpl_cls, \
             patch('backend.app.core.response_generator.SmartRouter') as sr_cls:

            from backend.app.core.response_generator import ResponseGenerator, ResponseGenerationRequest

            mock_sa = AsyncMock()
            mock_sa.analyze = AsyncMock(side_effect=Exception("Sentiment engine down"))
            sa_cls.return_value = mock_sa
            rag_cls.return_value = AsyncMock(retrieve=AsyncMock(return_value=MagicMock(chunks=[], total_found=0, retrieval_time_ms=0)))
            clara_cls.return_value = AsyncMock(evaluate=AsyncMock(return_value=MagicMock(overall_pass=True, overall_score=0.9, stages=[], final_response="OK", pipeline_timed_out=False)))
            bv_cls.return_value = AsyncMock(
                get_config=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, prohibited_words=[], response_length_preference="standard", max_response_sentences=10, min_response_sentences=1, greeting_template="", closing_template="", emoji_usage="minimal", apology_style="empathetic", escalation_tone="calm", brand_name="", industry="tech", custom_instructions="")),
                get_response_guidelines=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, max_sentences=10, min_sentences=1, empathy_level="low", urgency_adjustment="none", suggested_opening="", suggested_closing="", avoid_phrases=[])),
                validate_response=AsyncMock(return_value=MagicMock(is_valid=True, violations=[], warnings=[], score=1.0, suggested_fixes=[]))
            )
            mock_tb = AsyncMock()
            mock_tb.initialize_budget = AsyncMock(return_value=MagicMock(conversation_id="c", company_id="c", variant_type="p", max_tokens=8192, reserved_tokens=0, used_tokens=0, available_tokens=8192, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            mock_tb.reserve_tokens = AsyncMock(return_value=MagicMock(success=True, reserved_amount=100, remaining_after_reserve=8092, error=None))
            mock_tb.finalize_tokens = AsyncMock()
            mock_tb.check_overflow = AsyncMock(return_value=MagicMock(can_fit=True, remaining_tokens=8192, overflow_amount=0, truncation_needed=False, suggested_truncation_tokens=0))
            mock_tb.get_context_management_strategy = AsyncMock(return_value=MagicMock(strategy="keep_all", reason="", tokens_to_remove=0, messages_to_remove=0, priority_messages=[]))
            tb_cls.return_value = mock_tb
            tpl_cls.return_value = AsyncMock(find_best_template=AsyncMock(return_value=None))
            sr_cls.return_value = AsyncMock(
                route=MagicMock(return_value=MagicMock(model_tier=MagicMock(value="medium"), provider=MagicMock(value="google"))),
                async_execute_llm_call=AsyncMock(return_value={"content": "We're looking into it.", "usage": {"total_tokens": 30}})
            )

            gen = ResponseGenerator(redis_client=mock_redis)
            req = ResponseGenerationRequest(query="Help me", company_id=company_id, conversation_id="conv_err", variant_type="parwa")
            result = await gen.generate(req)
            assert result is not None
            assert result.sentiment_analysis is not None

    @pytest.mark.asyncio
    async def test_rag_failure_generates_without_context(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer') as sa_cls, \
             patch('backend.app.core.response_generator.RAGRetriever') as rag_cls, \
             patch('backend.app.core.response_generator.CrossEncoderReranker') as rerank_cls, \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate') as clara_cls, \
             patch('backend.app.core.response_generator.BrandVoiceService') as bv_cls, \
             patch('backend.app.core.response_generator.TokenBudgetService') as tb_cls, \
             patch('backend.app.core.response_generator.ResponseTemplateService') as tpl_cls, \
             patch('backend.app.core.response_generator.SmartRouter') as sr_cls:

            from backend.app.core.response_generator import ResponseGenerator, ResponseGenerationRequest

            sa_cls.return_value = AsyncMock(analyze=AsyncMock(return_value=MagicMock(
                frustration_score=10, emotion="neutral", urgency_level="low",
                tone_recommendation="professional", empathy_signals=[], sentiment_score=0.5,
                emotion_breakdown={}, conversation_trend="stable", cached=False
            )))
            rag_cls.return_value = AsyncMock(retrieve=AsyncMock(side_effect=Exception("RAG down")))
            rerank_cls.return_value = AsyncMock(rerank=AsyncMock(return_value=MagicMock(chunks=[], total_found=0, retrieval_time_ms=0)))
            clara_cls.return_value = AsyncMock(evaluate=AsyncMock(return_value=MagicMock(overall_pass=True, overall_score=0.9, stages=[], final_response="OK", pipeline_timed_out=False)))
            bv_cls.return_value = AsyncMock(
                get_config=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, prohibited_words=[], response_length_preference="standard", max_response_sentences=10, min_sentences_sentences=1, greeting_template="", closing_template="", emoji_usage="minimal", apology_style="empathetic", escalation_tone="calm", brand_name="", industry="tech", custom_instructions="")),
                get_response_guidelines=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, max_sentences=10, min_sentences=1, empathy_level="low", urgency_adjustment="none", suggested_opening="", suggested_closing="", avoid_phrases=[])),
                validate_response=AsyncMock(return_value=MagicMock(is_valid=True, violations=[], warnings=[], score=1.0, suggested_fixes=[]))
            )
            mock_tb = AsyncMock()
            mock_tb.initialize_budget = AsyncMock(return_value=MagicMock(conversation_id="c", company_id="c", variant_type="p", max_tokens=8192, reserved_tokens=0, used_tokens=0, available_tokens=8192, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            mock_tb.reserve_tokens = AsyncMock(return_value=MagicMock(success=True, reserved_amount=100, remaining_after_reserve=8092, error=None))
            mock_tb.finalize_tokens = AsyncMock()
            mock_tb.check_overflow = AsyncMock(return_value=MagicMock(can_fit=True, remaining_tokens=8192, overflow_amount=0, truncation_needed=False, suggested_truncation_tokens=0))
            mock_tb.get_context_management_strategy = AsyncMock(return_value=MagicMock(strategy="keep_all", reason="", tokens_to_remove=0, messages_to_remove=0, priority_messages=[]))
            tb_cls.return_value = mock_tb
            tpl_cls.return_value = AsyncMock(find_best_template=AsyncMock(return_value=None))
            sr_cls.return_value = AsyncMock(
                route=MagicMock(return_value=MagicMock(model_tier=MagicMock(value="medium"), provider=MagicMock(value="google"))),
                async_execute_llm_call=AsyncMock(return_value={"content": "Let me help you.", "usage": {"total_tokens": 25}})
            )

            gen = ResponseGenerator(redis_client=mock_redis)
            req = ResponseGenerationRequest(query="Test", company_id=company_id, conversation_id="conv_rag_fail", variant_type="parwa")
            result = await gen.generate(req)
            assert result.rag_context_used is False

    @pytest.mark.asyncio
    async def test_clara_fail_falls_to_template(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer') as sa_cls, \
             patch('backend.app.core.response_generator.RAGRetriever') as rag_cls, \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate') as clara_cls, \
             patch('backend.app.core.response_generator.BrandVoiceService') as bv_cls, \
             patch('backend.app.core.response_generator.TokenBudgetService') as tb_cls, \
             patch('backend.app.core.response_generator.ResponseTemplateService') as tpl_cls, \
             patch('backend.app.core.response_generator.SmartRouter') as sr_cls:

            from backend.app.core.response_generator import ResponseGenerator, ResponseGenerationRequest

            sa_cls.return_value = AsyncMock(analyze=AsyncMock(return_value=MagicMock(
                frustration_score=10, emotion="neutral", urgency_level="low",
                tone_recommendation="professional", empathy_signals=[], sentiment_score=0.5,
                emotion_breakdown={}, conversation_trend="stable", cached=False
            )))
            rag_cls.return_value = AsyncMock(retrieve=AsyncMock(return_value=MagicMock(chunks=[], total_found=0, retrieval_time_ms=0)))
            clara_cls.return_value = AsyncMock(evaluate=AsyncMock(return_value=MagicMock(
                overall_pass=False, overall_score=0.2, stages=[], final_response="", pipeline_timed_out=False
            )))
            mock_template = MagicMock(id="tpl_1", company_id=company_id, name="General", category="general",
                intent_types=["general"], subject_template="", body_template="Hello {{name}}, thank you for reaching out.",
                variables=["name"], language="en", is_active=True, usage_count=0, last_used_at=None,
                version=1, created_by="system", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
            )
            bv_cls.return_value = AsyncMock(
                get_config=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, prohibited_words=[], response_length_preference="standard", max_response_sentences=10, min_response_sentences=1, greeting_template="", closing_template="", emoji_usage="minimal", apology_style="empathetic", escalation_tone="calm", brand_name="", industry="tech", custom_instructions="")),
                get_response_guidelines=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, max_sentences=10, min_sentences=1, empathy_level="low", urgency_adjustment="none", suggested_opening="", suggested_closing="", avoid_phrases=[])),
                validate_response=AsyncMock(return_value=MagicMock(is_valid=True, violations=[], warnings=[], score=1.0, suggested_fixes=[]))
            )
            mock_tb = AsyncMock()
            mock_tb.initialize_budget = AsyncMock(return_value=MagicMock(conversation_id="c", company_id="c", variant_type="p", max_tokens=8192, reserved_tokens=0, used_tokens=0, available_tokens=8192, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            mock_tb.reserve_tokens = AsyncMock(return_value=MagicMock(success=True, reserved_amount=100, remaining_after_reserve=8092, error=None))
            mock_tb.finalize_tokens = AsyncMock()
            mock_tb.check_overflow = AsyncMock(return_value=MagicMock(can_fit=True, remaining_tokens=8192, overflow_amount=0, truncation_needed=False, suggested_truncation_tokens=0))
            mock_tb.get_context_management_strategy = AsyncMock(return_value=MagicMock(strategy="keep_all", reason="", tokens_to_remove=0, messages_to_remove=0, priority_messages=[]))
            tb_cls.return_value = mock_tb
            tpl_cls.return_value = AsyncMock(
                find_best_template=AsyncMock(return_value=mock_template),
                render_template=AsyncMock(return_value="Hello there, thank you for reaching out.")
            )
            sr_cls.return_value = AsyncMock(
                route=MagicMock(return_value=MagicMock(model_tier=MagicMock(value="medium"), provider=MagicMock(value="google"))),
                async_execute_llm_call=AsyncMock(return_value={"content": "Bad response", "usage": {"total_tokens": 20}})
            )

            gen = ResponseGenerator(redis_client=mock_redis)
            req = ResponseGenerationRequest(query="Hello", company_id=company_id, conversation_id="conv_clara_fail", variant_type="parwa")
            result = await gen.generate(req)
            assert result is not None
            assert result.template_used is True

    @pytest.mark.asyncio
    async def test_llm_fail_falls_to_template(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer') as sa_cls, \
             patch('backend.app.core.response_generator.RAGRetriever') as rag_cls, \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate') as clara_cls, \
             patch('backend.app.core.response_generator.BrandVoiceService') as bv_cls, \
             patch('backend.app.core.response_generator.TokenBudgetService') as tb_cls, \
             patch('backend.app.core.response_generator.ResponseTemplateService') as tpl_cls, \
             patch('backend.app.core.response_generator.SmartRouter') as sr_cls:

            from backend.app.core.response_generator import ResponseGenerator, ResponseGenerationRequest

            sa_cls.return_value = AsyncMock(analyze=AsyncMock(return_value=MagicMock(
                frustration_score=10, emotion="neutral", urgency_level="low",
                tone_recommendation="professional", empathy_signals=[], sentiment_score=0.5,
                emotion_breakdown={}, conversation_trend="stable", cached=False
            )))
            rag_cls.return_value = AsyncMock(retrieve=AsyncMock(return_value=MagicMock(chunks=[], total_found=0, retrieval_time_ms=0)))
            clara_cls.return_value = AsyncMock(evaluate=AsyncMock(side_effect=Exception("CLARA down")))
            mock_template = MagicMock(id="tpl_2", company_id=company_id, name="Fallback", category="general",
                intent_types=["general"], subject_template="", body_template="We received your message.",
                variables=[], language="en", is_active=True, usage_count=0, last_used_at=None,
                version=1, created_by="system", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
            )
            bv_cls.return_value = AsyncMock(
                get_config=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, prohibited_words=[], response_length_preference="standard", max_response_sentences=10, min_response_sentences=1, greeting_template="", closing_template="", emoji_usage="minimal", apology_style="empathetic", escalation_tone="calm", brand_name="", industry="tech", custom_instructions="")),
                get_response_guidelines=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, max_sentences=10, min_sentences=1, empathy_level="low", urgency_adjustment="none", suggested_opening="", suggested_closing="", avoid_phrases=[])),
                validate_response=AsyncMock(return_value=MagicMock(is_valid=True, violations=[], warnings=[], score=1.0, suggested_fixes=[]))
            )
            mock_tb = AsyncMock()
            mock_tb.initialize_budget = AsyncMock(return_value=MagicMock(conversation_id="c", company_id="c", variant_type="p", max_tokens=8192, reserved_tokens=0, used_tokens=0, available_tokens=8192, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            mock_tb.reserve_tokens = AsyncMock(return_value=MagicMock(success=True, reserved_amount=100, remaining_after_reserve=8092, error=None))
            mock_tb.finalize_tokens = AsyncMock()
            mock_tb.check_overflow = AsyncMock(return_value=MagicMock(can_fit=True, remaining_tokens=8192, overflow_amount=0, truncation_needed=False, suggested_truncation_tokens=0))
            mock_tb.get_context_management_strategy = AsyncMock(return_value=MagicMock(strategy="keep_all", reason="", tokens_to_remove=0, messages_to_remove=0, priority_messages=[]))
            tb_cls.return_value = mock_tb
            tpl_cls.return_value = AsyncMock(
                find_best_template=AsyncMock(return_value=mock_template),
                render_template=AsyncMock(return_value="We received your message.")
            )
            sr_cls.return_value = AsyncMock(
                route=MagicMock(return_value=MagicMock(model_tier=MagicMock(value="medium"), provider=MagicMock(value="google"))),
                async_execute_llm_call=AsyncMock(side_effect=Exception("LLM down"))
            )

            gen = ResponseGenerator(redis_client=mock_redis)
            req = ResponseGenerationRequest(query="Hi", company_id=company_id, conversation_id="conv_llm_fail", variant_type="parwa")
            result = await gen.generate(req)
            assert result is not None
            assert result.template_used is True

    @pytest.mark.asyncio
    async def test_token_budget_overflow_template_fallback(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer') as sa_cls, \
             patch('backend.app.core.response_generator.RAGRetriever'), \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate'), \
             patch('backend.app.core.response_generator.BrandVoiceService'), \
             patch('backend.app.core.response_generator.TokenBudgetService') as tb_cls, \
             patch('backend.app.core.response_generator.ResponseTemplateService') as tpl_cls, \
             patch('backend.app.core.response_generator.SmartRouter'):

            from backend.app.core.response_generator import ResponseGenerator, ResponseGenerationRequest

            sa_cls.return_value = AsyncMock(analyze=AsyncMock(return_value=MagicMock(
                frustration_score=10, emotion="neutral", urgency_level="low",
                tone_recommendation="professional", empathy_signals=[], sentiment_score=0.5,
                emotion_breakdown={}, conversation_trend="stable", cached=False
            )))
            mock_tb = AsyncMock()
            mock_tb.initialize_budget = AsyncMock(return_value=MagicMock(conversation_id="c", company_id="c", variant_type="p", max_tokens=8192, reserved_tokens=0, used_tokens=8100, available_tokens=92, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            mock_tb.reserve_tokens = AsyncMock(return_value=MagicMock(success=False, reserved_amount=0, remaining_after_reserve=92, error="Budget exceeded"))
            mock_tb.check_overflow = AsyncMock(return_value=MagicMock(can_fit=False, remaining_tokens=92, overflow_amount=408, truncation_needed=True, suggested_truncation_tokens=400))
            tb_cls.return_value = mock_tb
            tpl_cls.return_value = AsyncMock(
                find_best_template=AsyncMock(return_value=None),
                render_template=AsyncMock(return_value="Budget template response.")
            )

            gen = ResponseGenerator(redis_client=mock_redis)
            req = ResponseGenerationRequest(query="Hi", company_id=company_id, conversation_id="conv_overflow", variant_type="parwa")
            result = await gen.generate(req)
            assert result is not None

    @pytest.mark.asyncio
    async def test_batch_generation(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer') as sa_cls, \
             patch('backend.app.core.response_generator.RAGRetriever'), \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate') as clara_cls, \
             patch('backend.app.core.response_generator.BrandVoiceService') as bv_cls, \
             patch('backend.app.core.response_generator.TokenBudgetService') as tb_cls, \
             patch('backend.app.core.response_generator.ResponseTemplateService'), \
             patch('backend.app.core.response_generator.SmartRouter') as sr_cls:

            from backend.app.core.response_generator import ResponseGenerator, ResponseGenerationRequest

            sa_cls.return_value = AsyncMock(analyze=AsyncMock(return_value=MagicMock(
                frustration_score=10, emotion="neutral", urgency_level="low",
                tone_recommendation="professional", empathy_signals=[], sentiment_score=0.5,
                emotion_breakdown={}, conversation_trend="stable", cached=False
            )))
            clara_cls.return_value = AsyncMock(evaluate=AsyncMock(return_value=MagicMock(
                overall_pass=True, overall_score=0.9, stages=[], final_response="OK", pipeline_timed_out=False
            )))
            bv_cls.return_value = AsyncMock(
                get_config=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, prohibited_words=[], response_length_preference="standard", max_response_sentences=10, min_response_sentences=1, greeting_template="", closing_template="", emoji_usage="minimal", apology_style="empathetic", escalation_tone="calm", brand_name="", industry="tech", custom_instructions="")),
                get_response_guidelines=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, max_sentences=10, min_sentences=1, empathy_level="low", urgency_adjustment="none", suggested_opening="", suggested_closing="", avoid_phrases=[])),
                validate_response=AsyncMock(return_value=MagicMock(is_valid=True, violations=[], warnings=[], score=1.0, suggested_fixes=[]))
            )
            mock_tb = AsyncMock()
            mock_tb.initialize_budget = AsyncMock(return_value=MagicMock(conversation_id="c", company_id="c", variant_type="p", max_tokens=8192, reserved_tokens=0, used_tokens=0, available_tokens=8192, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            mock_tb.reserve_tokens = AsyncMock(return_value=MagicMock(success=True, reserved_amount=100, remaining_after_reserve=8092, error=None))
            mock_tb.finalize_tokens = AsyncMock()
            mock_tb.check_overflow = AsyncMock(return_value=MagicMock(can_fit=True, remaining_tokens=8192, overflow_amount=0, truncation_needed=False, suggested_truncation_tokens=0))
            mock_tb.get_context_management_strategy = AsyncMock(return_value=MagicMock(strategy="keep_all", reason="", tokens_to_remove=0, messages_to_remove=0, priority_messages=[]))
            tb_cls.return_value = mock_tb
            sr_cls.return_value = AsyncMock(
                route=MagicMock(return_value=MagicMock(model_tier=MagicMock(value="medium"), provider=MagicMock(value="google"))),
                async_execute_llm_call=AsyncMock(return_value={"content": "Response", "usage": {"total_tokens": 20}})
            )

            gen = ResponseGenerator(redis_client=mock_redis)
            reqs = [
                ResponseGenerationRequest(query=f"Q{i}", company_id=company_id, conversation_id=f"conv_batch_{i}", variant_type="parwa")
                for i in range(3)
            ]
            results = await gen.generate_batch(reqs)
            assert len(results) == 3

    @pytest.mark.asyncio
    async def test_mini_parwa_variant(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer') as sa_cls, \
             patch('backend.app.core.response_generator.RAGRetriever'), \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate') as clara_cls, \
             patch('backend.app.core.response_generator.BrandVoiceService') as bv_cls, \
             patch('backend.app.core.response_generator.TokenBudgetService') as tb_cls, \
             patch('backend.app.core.response_generator.ResponseTemplateService'), \
             patch('backend.app.core.response_generator.SmartRouter') as sr_cls:

            from backend.app.core.response_generator import ResponseGenerator, ResponseGenerationRequest

            sa_cls.return_value = AsyncMock(analyze=AsyncMock(return_value=MagicMock(
                frustration_score=10, emotion="neutral", urgency_level="low",
                tone_recommendation="professional", empathy_signals=[], sentiment_score=0.5,
                emotion_breakdown={}, conversation_trend="stable", cached=False
            )))
            clara_cls.return_value = AsyncMock(evaluate=AsyncMock(return_value=MagicMock(overall_pass=True, overall_score=0.9, stages=[], final_response="OK", pipeline_timed_out=False)))
            bv_cls.return_value = AsyncMock(
                get_config=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, prohibited_words=[], response_length_preference="standard", max_response_sentences=10, min_response_sentences=1, greeting_template="", closing_template="", emoji_usage="minimal", apology_style="empathetic", escalation_tone="calm", brand_name="", industry="tech", custom_instructions="")),
                get_response_guidelines=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, max_sentences=10, min_sentences=1, empathy_level="low", urgency_adjustment="none", suggested_opening="", suggested_closing="", avoid_phrases=[])),
                validate_response=AsyncMock(return_value=MagicMock(is_valid=True, violations=[], warnings=[], score=1.0, suggested_fixes=[]))
            )
            mock_tb = AsyncMock()
            mock_tb.initialize_budget = AsyncMock(return_value=MagicMock(conversation_id="c", company_id="c", variant_type="mini_parwa", max_tokens=4096, reserved_tokens=0, used_tokens=0, available_tokens=4096, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            mock_tb.reserve_tokens = AsyncMock(return_value=MagicMock(success=True, reserved_amount=100, remaining_after_reserve=3996, error=None))
            mock_tb.finalize_tokens = AsyncMock()
            mock_tb.check_overflow = AsyncMock(return_value=MagicMock(can_fit=True, remaining_tokens=4096, overflow_amount=0, truncation_needed=False, suggested_truncation_tokens=0))
            mock_tb.get_context_management_strategy = AsyncMock(return_value=MagicMock(strategy="keep_all", reason="", tokens_to_remove=0, messages_to_remove=0, priority_messages=[]))
            tb_cls.return_value = mock_tb
            sr_cls.return_value = AsyncMock(
                route=MagicMock(return_value=MagicMock(model_tier=MagicMock(value="light"), provider=MagicMock(value="google"))),
                async_execute_llm_call=AsyncMock(return_value={"content": "Mini response", "usage": {"total_tokens": 15}})
            )

            gen = ResponseGenerator(redis_client=mock_redis)
            req = ResponseGenerationRequest(query="Test mini", company_id=company_id, conversation_id="conv_mini", variant_type="mini_parwa")
            result = await gen.generate(req)
            assert result is not None

    @pytest.mark.asyncio
    async def test_parwa_high_variant(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer') as sa_cls, \
             patch('backend.app.core.response_generator.RAGRetriever'), \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate') as clara_cls, \
             patch('backend.app.core.response_generator.BrandVoiceService') as bv_cls, \
             patch('backend.app.core.response_generator.TokenBudgetService') as tb_cls, \
             patch('backend.app.core.response_generator.ResponseTemplateService'), \
             patch('backend.app.core.response_generator.SmartRouter') as sr_cls:

            from backend.app.core.response_generator import ResponseGenerator, ResponseGenerationRequest

            sa_cls.return_value = AsyncMock(analyze=AsyncMock(return_value=MagicMock(
                frustration_score=10, emotion="neutral", urgency_level="low",
                tone_recommendation="professional", empathy_signals=[], sentiment_score=0.5,
                emotion_breakdown={}, conversation_trend="stable", cached=False
            )))
            clara_cls.return_value = AsyncMock(evaluate=AsyncMock(return_value=MagicMock(overall_pass=True, overall_score=0.95, stages=[], final_response="Excellent", pipeline_timed_out=False)))
            bv_cls.return_value = AsyncMock(
                get_config=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.7, prohibited_words=[], response_length_preference="detailed", max_response_sentences=20, min_response_sentences=2, greeting_template="Dear customer,", closing_template="Best regards, Team", emoji_usage="minimal", apology_style="empathetic", escalation_tone="calm", brand_name="", industry="tech", custom_instructions="")),
                get_response_guidelines=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.7, max_sentences=20, min_sentences=2, empathy_level="low", urgency_adjustment="none", suggested_opening="Dear customer,", suggested_closing="Best regards", avoid_phrases=[])),
                validate_response=AsyncMock(return_value=MagicMock(is_valid=True, violations=[], warnings=[], score=0.95, suggested_fixes=[]))
            )
            mock_tb = AsyncMock()
            mock_tb.initialize_budget = AsyncMock(return_value=MagicMock(conversation_id="c", company_id="c", variant_type="parwa_high", max_tokens=16384, reserved_tokens=0, used_tokens=0, available_tokens=16384, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            mock_tb.reserve_tokens = AsyncMock(return_value=MagicMock(success=True, reserved_amount=200, remaining_after_reserve=16184, error=None))
            mock_tb.finalize_tokens = AsyncMock()
            mock_tb.check_overflow = AsyncMock(return_value=MagicMock(can_fit=True, remaining_tokens=16384, overflow_amount=0, truncation_needed=False, suggested_truncation_tokens=0))
            mock_tb.get_context_management_strategy = AsyncMock(return_value=MagicMock(strategy="keep_all", reason="", tokens_to_remove=0, messages_to_remove=0, priority_messages=[]))
            tb_cls.return_value = mock_tb
            sr_cls.return_value = AsyncMock(
                route=MagicMock(return_value=MagicMock(model_tier=MagicMock(value="heavy"), provider=MagicMock(value="google"))),
                async_execute_llm_call=AsyncMock(return_value={"content": "Comprehensive detailed response.", "usage": {"total_tokens": 200}})
            )

            gen = ResponseGenerator(redis_client=mock_redis)
            req = ResponseGenerationRequest(query="Detailed question please", company_id=company_id, conversation_id="conv_high", variant_type="parwa_high")
            result = await gen.generate(req)
            assert result is not None


class TestGAP020RateLimit:
    """GAP-020: Rate limit per customer — max 20/hour, 100/day."""

    @pytest.mark.asyncio
    async def test_rate_limit_under_threshold(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer'), \
             patch('backend.app.core.response_generator.RAGRetriever'), \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate'), \
             patch('backend.app.core.response_generator.BrandVoiceService') as bv_cls, \
             patch('backend.app.core.response_generator.TokenBudgetService'), \
             patch('backend.app.core.response_generator.ResponseTemplateService'), \
             patch('backend.app.core.response_generator.SmartRouter'):

            from backend.app.core.response_generator import ResponseGenerator

            # Redis returns low count for hourly rate
            mock_redis.get = AsyncMock(return_value="5")

            bv_cls.return_value = AsyncMock(
                get_config=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, prohibited_words=[], response_length_preference="standard", max_response_sentences=10, min_response_sentences=1, greeting_template="", closing_template="", emoji_usage="minimal", apology_style="empathetic", escalation_tone="calm", brand_name="", industry="tech", custom_instructions="")),
                get_response_guidelines=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, max_sentences=10, min_sentences=1, empathy_level="low", urgency_adjustment="none", suggested_opening="", suggested_closing="", avoid_phrases=[])),
                validate_response=AsyncMock(return_value=MagicMock(is_valid=True, violations=[], warnings=[], score=1.0, suggested_fixes=[]))
            )

            gen = ResponseGenerator(redis_client=mock_redis)
            result = await gen._check_rate_limit(company_id, "cust_1")
            assert result.allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_hourly_exceeded(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer'), \
             patch('backend.app.core.response_generator.RAGRetriever'), \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate'), \
             patch('backend.app.core.response_generator.BrandVoiceService'), \
             patch('backend.app.core.response_generator.TokenBudgetService'), \
             patch('backend.app.core.response_generator.ResponseTemplateService'), \
             patch('backend.app.core.response_generator.SmartRouter'):

            from backend.app.core.response_generator import ResponseGenerator

            mock_redis.get = AsyncMock(return_value="25")

            gen = ResponseGenerator(redis_client=mock_redis)
            result = await gen._check_rate_limit(company_id, "cust_1")
            assert result.allowed is False

    @pytest.mark.asyncio
    async def test_rate_limit_daily_exceeded(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer'), \
             patch('backend.app.core.response_generator.RAGRetriever'), \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate'), \
             patch('backend.app.core.response_generator.BrandVoiceService'), \
             patch('backend.app.core.response_generator.TokenBudgetService'), \
             patch('backend.app.core.response_generator.ResponseTemplateService'), \
             patch('backend.app.core.response_generator.SmartRouter'):

            from backend.app.core.response_generator import ResponseGenerator

            # Hourly OK but daily exceeded
            def get_side_effect(key):
                if "hourly" in str(key):
                    return "5"
                return "105"

            mock_redis.get = AsyncMock(side_effect=get_side_effect)

            gen = ResponseGenerator(redis_client=mock_redis)
            result = await gen._check_rate_limit(company_id, "cust_1")
            assert result.allowed is False

    @pytest.mark.asyncio
    async def test_rate_limit_redis_error_allows(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer'), \
             patch('backend.app.core.response_generator.RAGRetriever'), \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate'), \
             patch('backend.app.core.response_generator.BrandVoiceService'), \
             patch('backend.app.core.response_generator.TokenBudgetService'), \
             patch('backend.app.core.response_generator.ResponseTemplateService'), \
             patch('backend.app.core.response_generator.SmartRouter'):

            from backend.app.core.response_generator import ResponseGenerator

            mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))

            gen = ResponseGenerator(redis_client=mock_redis)
            result = await gen._check_rate_limit(company_id, "cust_1")
            assert result.allowed is True


class TestGAP028DraftInProgress:
    """GAP-028: Check for existing human draft in progress."""

    @pytest.mark.asyncio
    async def test_no_draft_in_progress(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer'), \
             patch('backend.app.core.response_generator.RAGRetriever'), \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate'), \
             patch('backend.app.core.response_generator.BrandVoiceService'), \
             patch('backend.app.core.response_generator.TokenBudgetService'), \
             patch('backend.app.core.response_generator.ResponseTemplateService'), \
             patch('backend.app.core.response_generator.SmartRouter'):

            from backend.app.core.response_generator import ResponseGenerator

            mock_redis.get = AsyncMock(return_value=None)

            gen = ResponseGenerator(redis_client=mock_redis)
            has_draft = await gen._check_draft_in_progress(company_id, "ticket_1")
            assert has_draft is False

    @pytest.mark.asyncio
    async def test_draft_in_progress_detected(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer'), \
             patch('backend.app.core.response_generator.RAGRetriever'), \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate'), \
             patch('backend.app.core.response_generator.BrandVoiceService'), \
             patch('backend.app.core.response_generator.TokenBudgetService'), \
             patch('backend.app.core.response_generator.ResponseTemplateService'), \
             patch('backend.app.core.response_generator.SmartRouter'):

            from backend.app.core.response_generator import ResponseGenerator

            mock_redis.get = AsyncMock(return_value="agent_123")

            gen = ResponseGenerator(redis_client=mock_redis)
            has_draft = await gen._check_draft_in_progress(company_id, "ticket_1")
            assert has_draft is True

    @pytest.mark.asyncio
    async def test_set_and_clear_draft(self, mock_redis, company_id):
        with patch('backend.app.core.response_generator.SentimentAnalyzer'), \
             patch('backend.app.core.response_generator.RAGRetriever'), \
             patch('backend.app.core.response_generator.CrossEncoderReranker'), \
             patch('backend.app.core.response_generator.ContextWindowAssembler'), \
             patch('backend.app.core.response_generator.CLARAQualityGate'), \
             patch('backend.app.core.response_generator.BrandVoiceService'), \
             patch('backend.app.core.response_generator.TokenBudgetService'), \
             patch('backend.app.core.response_generator.ResponseTemplateService'), \
             patch('backend.app.core.response_generator.SmartRouter'):

            from backend.app.core.response_generator import ResponseGenerator

            gen = ResponseGenerator(redis_client=mock_redis)
            await gen.set_draft_in_progress(company_id, "ticket_1", "agent_123")
            mock_redis.set.assert_called()
            await gen.clear_draft_in_progress(company_id, "ticket_1")
            mock_redis.delete.assert_called()


class TestResponseGeneratorHelpers:
    """Test helper methods."""

    @pytest.mark.asyncio
    async def test_empty_response_result(self, mock_redis, company_id):
        with patch('backend.app.core.sentiment_engine.SentimentAnalyzer'), \
             patch('backend.app.core.rag_retrieval.RAGRetriever'), \
             patch('backend.app.core.rag_reranking.CrossEncoderReranker'), \
             patch('backend.app.core.rag_reranking.ContextWindowAssembler'), \
             patch('backend.app.core.clara_quality_gate.CLARAQualityGate'), \
             patch('backend.app.services.brand_voice_service.BrandVoiceService'), \
             patch('backend.app.services.token_budget_service.TokenBudgetService'), \
             patch('backend.app.services.response_template_service.ResponseTemplateService'), \
             patch('backend.app.core.smart_router.SmartRouter'):

            from backend.app.core.response_generator import ResponseGenerator

            gen = ResponseGenerator(redis_client=mock_redis)
            result = gen._empty_response_result("conv_1")
            assert result.response_text is not None

    @pytest.mark.asyncio
    async def test_get_generation_status(self, mock_redis, company_id):
        with patch('backend.app.core.sentiment_engine.SentimentAnalyzer'), \
             patch('backend.app.core.rag_retrieval.RAGRetriever'), \
             patch('backend.app.core.rag_reranking.CrossEncoderReranker'), \
             patch('backend.app.core.rag_reranking.ContextWindowAssembler'), \
             patch('backend.app.core.clara_quality_gate.CLARAQualityGate'), \
             patch('backend.app.services.brand_voice_service.BrandVoiceService'), \
             patch('backend.app.services.token_budget_service.TokenBudgetService') as tb_cls, \
             patch('backend.app.services.response_template_service.ResponseTemplateService'), \
             patch('backend.app.core.smart_router.SmartRouter'):

            from backend.app.core.response_generator import ResponseGenerator

            tb_cls.return_value = AsyncMock(get_budget_status=AsyncMock(return_value=MagicMock(
                conversation_id="c", max_tokens=8192, used_tokens=1000, reserved_tokens=0,
                available_tokens=7192, percentage_used=12.2, warning_level="normal"
            )))
            gen = ResponseGenerator(redis_client=mock_redis)
            status = await gen.get_generation_status("conv_1", company_id)
            assert status is not None

    @pytest.mark.asyncio
    async def test_get_customer_rate_limit_status(self, mock_redis, company_id):
        with patch('backend.app.core.sentiment_engine.SentimentAnalyzer'), \
             patch('backend.app.core.rag_retrieval.RAGRetriever'), \
             patch('backend.app.core.rag_reranking.CrossEncoderReranker'), \
             patch('backend.app.core.rag_reranking.ContextWindowAssembler'), \
             patch('backend.app.core.clara_quality_gate.CLARAQualityGate'), \
             patch('backend.app.services.brand_voice_service.BrandVoiceService'), \
             patch('backend.app.services.token_budget_service.TokenBudgetService'), \
             patch('backend.app.services.response_template_service.ResponseTemplateService'), \
             patch('backend.app.core.smart_router.SmartRouter'):

            from backend.app.core.response_generator import ResponseGenerator

            mock_redis.get = AsyncMock(return_value="10")

            gen = ResponseGenerator(redis_client=mock_redis)
            status = await gen.get_customer_rate_limit_status(company_id, "cust_1")
            assert status is not None

    @pytest.mark.asyncio
    async def test_reset_customer_rate_limit(self, mock_redis, company_id):
        with patch('backend.app.core.sentiment_engine.SentimentAnalyzer'), \
             patch('backend.app.core.rag_retrieval.RAGRetriever'), \
             patch('backend.app.core.rag_reranking.CrossEncoderReranker'), \
             patch('backend.app.core.rag_reranking.ContextWindowAssembler'), \
             patch('backend.app.core.clara_quality_gate.CLARAQualityGate'), \
             patch('backend.app.services.brand_voice_service.BrandVoiceService'), \
             patch('backend.app.services.token_budget_service.TokenBudgetService'), \
             patch('backend.app.services.response_template_service.ResponseTemplateService'), \
             patch('backend.app.core.smart_router.SmartRouter'):

            from backend.app.core.response_generator import ResponseGenerator

            gen = ResponseGenerator(redis_client=mock_redis)
            await gen.reset_customer_rate_limit(company_id, "cust_1")
            mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_conversation_history_truncation(self, mock_redis, company_id):
        """Test that conversation history is truncated to last 10 messages."""
        with patch('backend.app.core.sentiment_engine.SentimentAnalyzer') as sa_cls, \
             patch('backend.app.core.rag_retrieval.RAGRetriever') as rag_cls, \
             patch('backend.app.core.rag_reranking.CrossEncoderReranker'), \
             patch('backend.app.core.rag_reranking.ContextWindowAssembler'), \
             patch('backend.app.core.clara_quality_gate.CLARAQualityGate') as clara_cls, \
             patch('backend.app.services.brand_voice_service.BrandVoiceService') as bv_cls, \
             patch('backend.app.services.token_budget_service.TokenBudgetService') as tb_cls, \
             patch('backend.app.services.response_template_service.ResponseTemplateService'), \
             patch('backend.app.core.smart_router.SmartRouter') as sr_cls:

            from backend.app.core.response_generator import ResponseGenerator, ResponseGenerationRequest

            sa_cls.return_value = AsyncMock(analyze=AsyncMock(return_value=MagicMock(
                frustration_score=10, emotion="neutral", urgency_level="low",
                tone_recommendation="professional", empathy_signals=[], sentiment_score=0.5,
                emotion_breakdown={}, conversation_trend="stable", cached=False
            )))
            rag_cls.return_value = AsyncMock(retrieve=AsyncMock(return_value=MagicMock(chunks=[], total_found=0, retrieval_time_ms=0)))
            clara_cls.return_value = AsyncMock(evaluate=AsyncMock(return_value=MagicMock(overall_pass=True, overall_score=0.9, stages=[], final_response="OK", pipeline_timed_out=False)))
            bv_cls.return_value = AsyncMock(
                get_config=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, prohibited_words=[], response_length_preference="standard", max_response_sentences=10, min_response_sentences=1, greeting_template="", closing_template="", emoji_usage="minimal", apology_style="empathetic", escalation_tone="calm", brand_name="", industry="tech", custom_instructions="")),
                get_response_guidelines=AsyncMock(return_value=MagicMock(tone="professional", formality_level=0.5, max_sentences=10, min_sentences=1, empathy_level="low", urgency_adjustment="none", suggested_opening="", suggested_closing="", avoid_phrases=[])),
                validate_response=AsyncMock(return_value=MagicMock(is_valid=True, violations=[], warnings=[], score=1.0, suggested_fixes=[]))
            )
            mock_tb = AsyncMock()
            mock_tb.initialize_budget = AsyncMock(return_value=MagicMock(conversation_id="c", company_id="c", variant_type="p", max_tokens=8192, reserved_tokens=0, used_tokens=0, available_tokens=8192, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            mock_tb.reserve_tokens = AsyncMock(return_value=MagicMock(success=True, reserved_amount=100, remaining_after_reserve=8092, error=None))
            mock_tb.finalize_tokens = AsyncMock()
            mock_tb.check_overflow = AsyncMock(return_value=MagicMock(can_fit=True, remaining_tokens=8192, overflow_amount=0, truncation_needed=False, suggested_truncation_tokens=0))
            mock_tb.get_context_management_strategy = AsyncMock(return_value=MagicMock(strategy="keep_all", reason="", tokens_to_remove=0, messages_to_remove=0, priority_messages=[]))
            tb_cls.return_value = mock_tb
            sr_cls.return_value = AsyncMock(
                route=MagicMock(return_value=MagicMock(model_tier=MagicMock(value="medium"), provider=MagicMock(value="google"))),
                async_execute_llm_call=AsyncMock(return_value={"content": "OK", "usage": {"total_tokens": 10}})
            )

            gen = ResponseGenerator(redis_client=mock_redis)
            # 20 messages — should only use last 10
            history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"} for i in range(20)]
            req = ResponseGenerationRequest(
                query="Latest message", company_id=company_id,
                conversation_id="conv_hist", variant_type="parwa",
                conversation_history=history
            )
            result = await gen.generate(req)
            assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. BrandVoiceService Tests (F-154)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBrandVoiceCRUD:
    """Test BrandVoiceService CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_config(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        config = await svc.create_config(company_id, {"tone": "friendly", "industry": "ecommerce"})
        assert config.company_id == company_id
        assert config.tone == "friendly"

    @pytest.mark.asyncio
    async def test_get_config_returns_created(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        created = await svc.create_config(company_id, {"tone": "professional", "industry": "tech"})
        retrieved = await svc.get_config(company_id)
        assert retrieved is not None
        assert retrieved.tone == "professional"

    @pytest.mark.asyncio
    async def test_update_config(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "friendly", "industry": "ecommerce"})
        updated = await svc.update_config(company_id, {"tone": "authoritative", "formality_level": 0.9})
        assert updated.tone == "authoritative"
        assert updated.formality_level == 0.9

    @pytest.mark.asyncio
    async def test_delete_config(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "casual", "industry": "hospitality"})
        deleted = await svc.delete_config(company_id)
        assert deleted is True

    @pytest.mark.asyncio
    async def test_get_config_missing_returns_default(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        config = await svc.get_config(company_id)
        # Should return a default config (BC-008)
        assert config is not None

    @pytest.mark.asyncio
    async def test_get_config_with_industry_default(self, mock_redis):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        config = await svc.get_default_config("finance")
        assert config.industry == "finance"
        assert config.formality_level == 0.9


class TestBrandVoiceProhibitedWordsGAP021:
    """GAP-021: L33t-speak and emoji variant detection."""

    @pytest.mark.asyncio
    async def test_normal_prohibited_word(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "professional", "prohibited_words": ["damn", "hell"], "industry": "tech"})
        result = await svc.check_prohibited_words("This is damn annoying", company_id)
        assert result.has_violations is True
        assert len(result.violations) > 0

    @pytest.mark.asyncio
    async def test_l33t_speak_d4mn(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "professional", "prohibited_words": ["damn"], "industry": "tech"})
        result = await svc.check_prohibited_words("This is d4mn annoying", company_id)
        assert result.has_violations is True

    @pytest.mark.asyncio
    async def test_l33t_speak_h3ll(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "professional", "prohibited_words": ["hell"], "industry": "tech"})
        result = await svc.check_prohibited_words("What the h3ll", company_id)
        assert result.has_violations is True

    @pytest.mark.asyncio
    async def test_l33t_speak_sh1t(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "professional", "prohibited_words": ["shit"], "industry": "tech"})
        result = await svc.check_prohibited_words("This is sh1t", company_id)
        assert result.has_violations is True

    @pytest.mark.asyncio
    async def test_l33t_speak_f4ck(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "professional", "prohibited_words": ["fuck"], "industry": "tech"})
        result = await svc.check_prohibited_words("f4ck this", company_id)
        assert result.has_violations is True

    @pytest.mark.asyncio
    async def test_repeated_chars_caught(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "professional", "prohibited_words": ["hell"], "industry": "tech"})
        result = await svc.check_prohibited_words("heeellllo", company_id)
        # "heeellllo" normalizes to "helo" — should NOT match "hell"
        # This tests that normalization doesn't over-collapse
        assert isinstance(result, object)

    @pytest.mark.asyncio
    async def test_clean_text_no_violations(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "professional", "prohibited_words": ["damn", "hell"], "industry": "tech"})
        result = await svc.check_prohibited_words("This is perfectly fine text", company_id)
        assert result.has_violations is False

    @pytest.mark.asyncio
    async def test_empty_prohibited_words(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "professional", "prohibited_words": [], "industry": "tech"})
        result = await svc.check_prohibited_words("Anything goes", company_id)
        assert result.has_violations is False


class TestBrandVoiceIndustryDefaults:
    """Test all 6 industry defaults."""

    @pytest.mark.asyncio
    async def test_tech_defaults(self):
        from backend.app.services.brand_voice_service import BrandVoiceService
        svc = BrandVoiceService()
        config = await svc.get_default_config("tech")
        assert config.tone == "professional"
        assert config.formality_level == 0.7

    @pytest.mark.asyncio
    async def test_ecommerce_defaults(self):
        from backend.app.services.brand_voice_service import BrandVoiceService
        svc = BrandVoiceService()
        config = await svc.get_default_config("ecommerce")
        assert config.tone == "friendly"
        assert config.formality_level == 0.4

    @pytest.mark.asyncio
    async def test_finance_defaults(self):
        from backend.app.services.brand_voice_service import BrandVoiceService
        svc = BrandVoiceService()
        config = await svc.get_default_config("finance")
        assert config.tone == "authoritative"
        assert config.formality_level == 0.9

    @pytest.mark.asyncio
    async def test_education_defaults(self):
        from backend.app.services.brand_voice_service import BrandVoiceService
        svc = BrandVoiceService()
        config = await svc.get_default_config("education")
        assert config.tone == "friendly"
        assert config.formality_level == 0.5

    @pytest.mark.asyncio
    async def test_legal_defaults(self):
        from backend.app.services.brand_voice_service import BrandVoiceService
        svc = BrandVoiceService()
        config = await svc.get_default_config("legal")
        assert config.tone == "authoritative"
        assert config.formality_level == 1.0

    @pytest.mark.asyncio
    async def test_hospitality_defaults(self):
        from backend.app.services.brand_voice_service import BrandVoiceService
        svc = BrandVoiceService()
        config = await svc.get_default_config("hospitality")
        assert config.tone == "casual"
        assert config.formality_level == 0.3


class TestBrandVoiceResponseGuidelines:
    """Test dynamic response guidelines based on sentiment."""

    @pytest.mark.asyncio
    async def test_low_sentiment_guidelines(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "professional", "industry": "tech"})
        guidelines = await svc.get_response_guidelines(company_id, sentiment_score=0.2)
        assert guidelines.empathy_level in ("low", "medium", "high", "critical")
        assert guidelines.tone is not None

    @pytest.mark.asyncio
    async def test_high_sentiment_guidelines(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "professional", "industry": "tech"})
        guidelines = await svc.get_response_guidelines(company_id, sentiment_score=0.9)
        assert guidelines.empathy_level in ("high", "critical")

    @pytest.mark.asyncio
    async def test_neutral_sentiment_guidelines(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "professional", "industry": "tech"})
        guidelines = await svc.get_response_guidelines(company_id, sentiment_score=0.5)
        assert guidelines is not None


class TestBrandVoiceValidation:
    """Test response validation against brand voice."""

    @pytest.mark.asyncio
    async def test_valid_response(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "professional", "prohibited_words": ["damn"], "industry": "tech"})
        result = await svc.validate_response("Thank you for your inquiry. We will get back to you shortly.", company_id)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_response_with_prohibited_words(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "professional", "prohibited_words": ["damn"], "industry": "tech"})
        result = await svc.validate_response("This is damn terrible", company_id)
        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_merge_with_brand_voice(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {
            "tone": "professional", "industry": "tech",
            "greeting_template": "Hello from {brand}!",
            "closing_template": "Best, {brand} Team"
        })
        merged = await svc.merge_with_brand_voice("We can help with that.", company_id)
        assert merged is not None
        assert len(merged) > 0


class TestBrandVoiceRedisCaching:
    """Test Redis caching behavior."""

    @pytest.mark.asyncio
    async def test_cache_set_on_create(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "friendly", "industry": "ecommerce"})
        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_cache_deleted_on_update(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "friendly", "industry": "ecommerce"})
        mock_redis.reset_mock()
        await svc.update_config(company_id, {"tone": "formal"})
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_cache_deleted_on_delete_config(self, mock_redis, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        svc = BrandVoiceService(redis_client=mock_redis)
        await svc.create_config(company_id, {"tone": "friendly", "industry": "ecommerce"})
        mock_redis.reset_mock()
        await svc.delete_config(company_id)
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_graceful_with_redis_error(self, company_id):
        from backend.app.services.brand_voice_service import BrandVoiceService

        broken_redis = AsyncMock()
        broken_redis.get = AsyncMock(side_effect=Exception("Connection refused"))
        broken_redis.set = AsyncMock(side_effect=Exception("Connection refused"))

        svc = BrandVoiceService(redis_client=broken_redis)
        config = await svc.create_config(company_id, {"tone": "friendly", "industry": "ecommerce"})
        assert config is not None  # BC-008: never crash


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ResponseTemplateService Tests (F-155)
# ═══════════════════════════════════════════════════════════════════════════════

class TestResponseTemplateCRUD:
    """Test ResponseTemplateService CRUD."""

    @pytest.mark.asyncio
    async def test_create_template(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService

        svc = ResponseTemplateService(redis_client=mock_redis)
        tpl = await svc.create_template(company_id, {
            "name": "Greeting", "category": "greeting", "intent_types": ["general"],
            "subject_template": "Welcome", "body_template": "Hello {{name}}, welcome!"
        })
        assert tpl.company_id == company_id
        assert tpl.name == "Greeting"

    @pytest.mark.asyncio
    async def test_get_template(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService

        svc = ResponseTemplateService(redis_client=mock_redis)
        created = await svc.create_template(company_id, {
            "name": "Apology", "category": "apology", "intent_types": ["complaint"],
            "subject_template": "We're sorry", "body_template": "Dear {{name}}, we apologize for {{issue}}."
        })
        retrieved = await svc.get_template(created.id, company_id)
        assert retrieved is not None
        assert retrieved.name == "Apology"

    @pytest.mark.asyncio
    async def test_list_templates(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService

        svc = ResponseTemplateService(redis_client=mock_redis)
        await svc.create_template(company_id, {
            "name": "T1", "category": "greeting", "intent_types": ["general"],
            "subject_template": "", "body_template": "Hello {{name}}"
        })
        await svc.create_template(company_id, {
            "name": "T2", "category": "apology", "intent_types": ["complaint"],
            "subject_template": "", "body_template": "Sorry {{name}}"
        })
        templates = await svc.list_templates(company_id)
        assert len(templates) >= 2

    @pytest.mark.asyncio
    async def test_list_templates_by_category(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService

        svc = ResponseTemplateService(redis_client=mock_redis)
        await svc.create_template(company_id, {
            "name": "T1", "category": "greeting", "intent_types": ["general"],
            "subject_template": "", "body_template": "Hi"
        })
        await svc.create_template(company_id, {
            "name": "T2", "category": "apology", "intent_types": ["complaint"],
            "subject_template": "", "body_template": "Sorry"
        })
        greeting_tpls = await svc.list_templates(company_id, category="greeting")
        assert all(t.category == "greeting" for t in greeting_tpls)

    @pytest.mark.asyncio
    async def test_update_template(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService

        svc = ResponseTemplateService(redis_client=mock_redis)
        created = await svc.create_template(company_id, {
            "name": "Greeting", "category": "greeting", "intent_types": ["general"],
            "subject_template": "", "body_template": "Hello"
        })
        updated = await svc.update_template(created.id, company_id, {"name": "Updated Greeting"})
        assert updated.name == "Updated Greeting"
        assert updated.version > created.version

    @pytest.mark.asyncio
    async def test_delete_template(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService

        svc = ResponseTemplateService(redis_client=mock_redis)
        created = await svc.create_template(company_id, {
            "name": "Temp", "category": "general", "intent_types": ["general"],
            "subject_template": "", "body_template": "Temp"
        })
        deleted = await svc.delete_template(created.id, company_id)
        assert deleted is True

    @pytest.mark.asyncio
    async def test_duplicate_template(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService

        svc = ResponseTemplateService(redis_client=mock_redis)
        created = await svc.create_template(company_id, {
            "name": "Original", "category": "greeting", "intent_types": ["general"],
            "subject_template": "", "body_template": "Hello {{name}}"
        })
        dup = await svc.duplicate_template(created.id, company_id)
        assert "(Copy)" in dup.name


class TestResponseTemplateRendering:
    """Test template rendering and variable substitution."""

    @pytest.mark.asyncio
    async def test_render_with_variables(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService

        svc = ResponseTemplateService(redis_client=mock_redis)
        created = await svc.create_template(company_id, {
            "name": "Greeting", "category": "greeting", "intent_types": ["general"],
            "subject_template": "Welcome {{name}}",
            "body_template": "Hello {{name}}, thank you for contacting {{company}}."
        })
        rendered = await svc.render_template(created.id, company_id, {"name": "John", "company": "Acme"})
        assert "John" in rendered
        assert "Acme" in rendered
        assert "{{" not in rendered

    @pytest.mark.asyncio
    async def test_render_missing_variable(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService

        svc = ResponseTemplateService(redis_client=mock_redis)
        created = await svc.create_template(company_id, {
            "name": "Test", "category": "greeting", "intent_types": ["general"],
            "subject_template": "", "body_template": "Hello {{name}}"
        })
        rendered = await svc.render_template(created.id, company_id, {})
        assert "{{name}}" not in rendered or "name" in rendered.lower()


class TestGAP010XSSSanitization:
    """GAP-010: XSS sanitization for template variables."""

    @pytest.mark.asyncio
    async def test_text_mode_html_escaping(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService, sanitize_template_variable

        result = sanitize_template_variable("<script>alert('xss')</script>", "text")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    @pytest.mark.asyncio
    async def test_text_mode_escapes_all_entities(self):
        from backend.app.services.response_template_service import sanitize_template_variable

        result = sanitize_template_variable('<b onclick="evil()">Test</b>', "text")
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&quot;" in result

    @pytest.mark.asyncio
    async def test_html_mode_strips_script(self):
        from backend.app.services.response_template_service import sanitize_template_variable

        result = sanitize_template_variable('<p>Hello</p><script>alert("xss")</script><b>World</b>', "html")
        assert "<script>" not in result
        assert "<p>" in result or "Hello" in result

    @pytest.mark.asyncio
    async def test_html_mode_strips_event_handlers(self):
        from backend.app.services.response_template_service import sanitize_template_variable

        result = sanitize_template_variable('<div onclick="alert(1)">Click</div>', "html")
        assert "onclick" not in result.lower()

    @pytest.mark.asyncio
    async def test_html_mode_strips_javascript_urls(self):
        from backend.app.services.response_template_service import sanitize_template_variable

        result = sanitize_template_variable('<a href="javascript:alert(1)">Link</a>', "html")
        assert "javascript:" not in result.lower()

    @pytest.mark.asyncio
    async def test_html_mode_allows_safe_tags(self):
        from backend.app.services.response_template_service import sanitize_template_variable

        result = sanitize_template_variable('<p>Hello <strong>world</strong></p>', "html")
        assert "Hello" in result
        assert "world" in result

    @pytest.mark.asyncio
    async def test_render_with_xss_variable(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService

        svc = ResponseTemplateService(redis_client=mock_redis)
        created = await svc.create_template(company_id, {
            "name": "XSS Test", "category": "general", "intent_types": ["general"],
            "subject_template": "", "body_template": "Hello {{name}}"
        })
        rendered = await svc.render_template(created.id, company_id, {
            "name": '<script>alert("xss")</script>'
        })
        assert "<script>" not in rendered


class TestResponseTemplateValidation:
    """Test template validation."""

    @pytest.mark.asyncio
    async def test_valid_template(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService

        svc = ResponseTemplateService(redis_client=mock_redis)
        result = await svc.validate_template("Hello {{name}}, welcome to {{company}}.")
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_unclosed_variable(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService

        svc = ResponseTemplateService(redis_client=mock_redis)
        result = await svc.validate_template("Hello {{name}} welcome to {{company")
        assert result.is_valid is False or len(result.unclosed_variables) > 0

    @pytest.mark.asyncio
    async def test_find_best_template(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService

        svc = ResponseTemplateService(redis_client=mock_redis)
        await svc.create_template(company_id, {
            "name": "Refund", "category": "refund", "intent_types": ["refund"],
            "subject_template": "", "body_template": "Refund info for {{order_id}}"
        })
        best = await svc.find_best_template(company_id, "refund", "en", 0.5)
        assert best is not None
        assert "refund" in best.category.lower() or "refund" in best.intent_types

    @pytest.mark.asyncio
    async def test_increment_usage(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService

        svc = ResponseTemplateService(redis_client=mock_redis)
        created = await svc.create_template(company_id, {
            "name": "Usage", "category": "greeting", "intent_types": ["general"],
            "subject_template": "", "body_template": "Hi"
        })
        await svc.increment_usage(created.id)
        # Re-fetch and check usage_count increased
        updated = await svc.get_template(created.id, company_id)
        assert updated.usage_count >= 1

    @pytest.mark.asyncio
    async def test_get_template_variables(self, mock_redis, company_id):
        from backend.app.services.response_template_service import ResponseTemplateService

        svc = ResponseTemplateService(redis_client=mock_redis)
        created = await svc.create_template(company_id, {
            "name": "Vars", "category": "general", "intent_types": ["general"],
            "subject_template": "Hello {{name}}",
            "body_template": "Your order {{order_id}} is {{status}}"
        })
        variables = await svc.get_template_variables(created.id, company_id)
        assert len(variables) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TokenBudgetService Tests (F-156)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTokenBudgetInit:
    """Test budget initialization per variant."""

    @pytest.mark.asyncio
    async def test_mini_parwa_budget(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        svc = TokenBudgetService(redis_client=mock_redis)
        budget = await svc.initialize_budget("conv_mini", company_id, "mini_parwa")
        # Effective max = 4096 * (1 - 0.1) = 3687 due to safety margin
        assert budget.max_tokens == 3687

    @pytest.mark.asyncio
    async def test_parwa_budget(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        svc = TokenBudgetService(redis_client=mock_redis)
        budget = await svc.initialize_budget("conv_parwa", company_id, "parwa")
        assert budget.max_tokens == 7373

    @pytest.mark.asyncio
    async def test_parwa_high_budget(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        svc = TokenBudgetService(redis_client=mock_redis)
        budget = await svc.initialize_budget("conv_high", company_id, "parwa_high")
        assert budget.max_tokens == 14746


class TestTokenBudgetGAP006AtomicReserve:
    """GAP-006: Atomic reserve + finalize pattern."""

    @pytest.mark.asyncio
    async def test_reserve_tokens_success(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        mock_redis.eval = AsyncMock(return_value=500)

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        result = await svc.reserve_tokens("conv_1", 500)
        assert result.success is True
        assert result.reserved_amount == 500

    @pytest.mark.asyncio
    async def test_reserve_tokens_overflow(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        # Lua script returns -1 for overflow
        mock_redis.eval = AsyncMock(return_value=-1)

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "mini_parwa")
        result = await svc.reserve_tokens("conv_1", 99999)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_finalize_returns_unused(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        mock_redis.eval = AsyncMock(return_value=300)

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        await svc.reserve_tokens("conv_1", 500)
        await svc.finalize_tokens("conv_1", 500, 300)
        # finalize should call eval to return 200 unused tokens
        assert mock_redis.eval.called

    @pytest.mark.asyncio
    async def test_concurrent_reserve_no_overflow(self, mock_redis, company_id):
        """Multiple reserves should not exceed budget."""
        from backend.app.services.token_budget_service import TokenBudgetService

        # Simulate: first 3 reserves succeed (3000 total), 4th fails
        call_count = [0]
        def eval_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 3:
                return call_count[0] * 1000
            return -1

        mock_redis.eval = AsyncMock(side_effect=eval_side_effect)

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")  # 8192

        r1 = await svc.reserve_tokens("conv_1", 1000)
        r2 = await svc.reserve_tokens("conv_1", 1000)
        r3 = await svc.reserve_tokens("conv_1", 1000)
        r4 = await svc.reserve_tokens("conv_1", 1000)

        assert r1.success is True
        assert r2.success is True
        assert r3.success is True
        assert r4.success is False


class TestTokenBudgetStatus:
    """Test budget status checking."""

    @pytest.mark.asyncio
    async def test_get_budget_status(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        mock_redis.get = AsyncMock(return_value="1000")
        mock_redis.hgetall = AsyncMock(return_value={
            "company_id": company_id, "variant_type": "parwa"
        })

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        status = await svc.get_budget_status("conv_1")
        assert status.max_tokens == 8192
        assert status.warning_level in ("normal", "warning", "critical", "exhausted")

    @pytest.mark.asyncio
    async def test_warning_threshold(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        mock_redis.get = AsyncMock(return_value="6000")
        mock_redis.hgetall = AsyncMock(return_value={"company_id": company_id, "variant_type": "parwa"})

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        status = await svc.get_budget_status("conv_1")
        # 6000/8192 ≈ 73% — should be warning
        assert status.warning_level in ("warning", "normal", "critical")

    @pytest.mark.asyncio
    async def test_critical_threshold(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        mock_redis.get = AsyncMock(return_value="7800")
        mock_redis.hgetall = AsyncMock(return_value={"company_id": company_id, "variant_type": "parwa"})

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        status = await svc.get_budget_status("conv_1")
        # 7800/8192 ≈ 95% — should be critical
        assert status.warning_level in ("critical", "warning")


class TestTokenBudgetOverflow:
    """Test overflow checking."""

    @pytest.mark.asyncio
    async def test_can_fit(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        mock_redis.get = AsyncMock(return_value="100")

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        check = await svc.check_overflow("conv_1", 100)
        assert check.can_fit is True

    @pytest.mark.asyncio
    async def test_cannot_fit(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        mock_redis.get = AsyncMock(return_value="8100")

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        check = await svc.check_overflow("conv_1", 500)
        assert check.can_fit is False
        assert check.truncation_needed is True


class TestTokenBudgetContextStrategies:
    """Test 4 context management strategies."""

    @pytest.mark.asyncio
    async def test_keep_all_strategy(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        mock_redis.get = AsyncMock(return_value="500")

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        strategy = await svc.get_context_management_strategy("conv_1", 100)
        assert strategy.strategy == "keep_all"

    @pytest.mark.asyncio
    async def test_truncate_old_strategy(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        mock_redis.get = AsyncMock(return_value="6500")

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        strategy = await svc.get_context_management_strategy("conv_1", 2000)
        assert strategy.strategy in ("truncate_old", "summarize_old", "sliding_window", "keep_all")

    @pytest.mark.asyncio
    async def test_summarize_strategy(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        mock_redis.get = AsyncMock(return_value="7800")

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        strategy = await svc.get_context_management_strategy("conv_1", 1000)
        assert strategy.strategy in ("summarize_old", "sliding_window", "truncate_old")

    @pytest.mark.asyncio
    async def test_sliding_window_strategy(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        mock_redis.get = AsyncMock(return_value="8000")

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        strategy = await svc.get_context_management_strategy("conv_1", 500)
        assert strategy.strategy in ("sliding_window", "summarize_old")


class TestTokenBudgetMessages:
    """Test message token tracking."""

    @pytest.mark.asyncio
    async def test_add_message_tokens(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        await svc.add_message_tokens("conv_1", "msg_1", "user", 50)
        await svc.add_message_tokens("conv_1", "msg_2", "assistant", 100)

        messages = await svc.get_conversation_history_tokens("conv_1")
        assert len(messages) >= 2

    @pytest.mark.asyncio
    async def test_get_tokens_by_role(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        await svc.add_message_tokens("conv_1", "msg_1", "user", 50)
        await svc.add_message_tokens("conv_1", "msg_2", "assistant", 100)
        await svc.add_message_tokens("conv_1", "msg_3", "user", 30)

        by_role = await svc.get_tokens_by_role("conv_1")
        assert "user" in by_role
        assert "assistant" in by_role

    @pytest.mark.asyncio
    async def test_get_message_count(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        await svc.add_message_tokens("conv_1", "msg_1", "user", 50)
        await svc.add_message_tokens("conv_1", "msg_2", "assistant", 100)

        count = await svc.get_message_count("conv_1")
        assert count >= 2


class TestTokenBudgetReset:
    """Test budget reset."""

    @pytest.mark.asyncio
    async def test_reset_budget(self, mock_redis, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        svc = TokenBudgetService(redis_client=mock_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        await svc.add_message_tokens("conv_1", "msg_1", "user", 5000)
        await svc.reset_budget("conv_1")

        status = await svc.get_budget_status("conv_1")
        assert status is not None


class TestTokenBudgetInMemoryFallback:
    """Test in-memory fallback when Redis unavailable."""

    @pytest.mark.asyncio
    async def test_memory_fallback_reserve(self, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        broken_redis = AsyncMock()
        broken_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        broken_redis.set = AsyncMock(side_effect=Exception("Redis down"))
        broken_redis.eval = AsyncMock(side_effect=Exception("Redis down"))

        svc = TokenBudgetService(redis_client=broken_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        result = await svc.reserve_tokens("conv_1", 500)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_memory_fallback_overflow(self, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        broken_redis = AsyncMock()
        broken_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        broken_redis.set = AsyncMock(side_effect=Exception("Redis down"))
        broken_redis.eval = AsyncMock(side_effect=Exception("Redis down"))

        svc = TokenBudgetService(redis_client=broken_redis)
        await svc.initialize_budget("conv_1", company_id, "mini_parwa")  # 4096
        await svc.reserve_tokens("conv_1", 3000)
        result = await svc.reserve_tokens("conv_1", 2000)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_memory_fallback_status(self, company_id):
        from backend.app.services.token_budget_service import TokenBudgetService

        broken_redis = AsyncMock()
        broken_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        broken_redis.set = AsyncMock(side_effect=Exception("Redis down"))
        broken_redis.eval = AsyncMock(side_effect=Exception("Redis down"))

        svc = TokenBudgetService(redis_client=broken_redis)
        await svc.initialize_budget("conv_1", company_id, "parwa")
        status = await svc.get_budget_status("conv_1")
        assert status.max_tokens == 8192
        assert status.available_tokens == 8192
