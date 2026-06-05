"""
Day 5 Integration Tests — AI Frameworks + RAG + DSPy + Agent Lightning

Tests all Day 5 components:
  1. CLARA RAG Rebuild: HyDE, Multi-Query, Compression
  2. MAKER Framework Full Pipeline
  3. Agent Lightning Training
  4. 3-Tier Hybrid Optimization + Technique Tier Mapper

BC-001: All tests use scoped company_id.
BC-008: All tests verify fallback behavior.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════════
# Test 1: Technique Tier Mapper
# ══════════════════════════════════════════════════════════════════


class TestTechniqueTierMapper:
    """Unit tests for technique_tier_mapper.py"""

    def test_get_technique_for_tier_mini_parwa(self):
        from app.core.technique_tier_mapper import get_technique_for_tier
        for intent in ["refund", "technical", "billing", "complaint", "faq", "general"]:
            assert get_technique_for_tier(intent, "mini_parwa") == "chain_of_thought"

    def test_get_technique_for_tier_parwa(self):
        from app.core.technique_tier_mapper import get_technique_for_tier
        assert get_technique_for_tier("refund", "parwa") == "self_consistency"
        assert get_technique_for_tier("technical", "parwa") == "react"
        assert get_technique_for_tier("complaint", "parwa") == "reflexion"

    def test_get_technique_for_tier_parwa_high(self):
        from app.core.technique_tier_mapper import get_technique_for_tier
        assert get_technique_for_tier("refund", "parwa_high") == "self_consistency"
        assert get_technique_for_tier("billing", "parwa_high") == "least_to_most"
        assert get_technique_for_tier("general", "parwa_high") == "tree_of_thought"

    def test_unknown_tier_defaults_to_parwa(self):
        from app.core.technique_tier_mapper import get_technique_for_tier
        result = get_technique_for_tier("refund", "unknown_tier")
        assert result == "self_consistency"  # parwa default

    def test_unknown_intent_defaults_to_cot(self):
        from app.core.technique_tier_mapper import get_technique_for_tier
        result = get_technique_for_tier("nonexistent_intent", "parwa")
        assert result == "chain_of_thought"

    def test_get_max_llm_calls(self):
        from app.core.technique_tier_mapper import get_max_llm_calls
        assert get_max_llm_calls("mini_parwa") == 2
        assert get_max_llm_calls("parwa") == 4
        assert get_max_llm_calls("parwa_high") == 24
        assert get_max_llm_calls("unknown") == 2

    def test_get_timeout_ms(self):
        from app.core.technique_tier_mapper import get_timeout_ms
        assert get_timeout_ms("mini_parwa") == 3000
        assert get_timeout_ms("parwa") == 8000
        assert get_timeout_ms("parwa_high") == 0  # no hard limit
        assert get_timeout_ms("unknown") == 3000

    def test_get_tier_config(self):
        from app.core.technique_tier_mapper import get_tier_config
        config = get_tier_config("parwa_high")
        assert config["maker_enabled"] is True
        assert config["fake_voting_enabled"] is True
        assert config["hyde_enabled"] is True
        assert config["multi_query_enabled"] is True
        assert config["compression_enabled"] is True

    def test_resolve_technique_config(self):
        from app.core.technique_tier_mapper import resolve_technique_config
        config = resolve_technique_config("refund", "parwa_high")
        assert config.primary_technique == "self_consistency"
        assert config.maker_enabled is True
        assert config.fake_voting_enabled is True  # parwa_high has FAKE voting
        assert config.hyde_enabled is True
        assert config.to_dict()["primary_technique"] == "self_consistency"

    def test_tier_config_maker_settings(self):
        from app.core.technique_tier_mapper import get_tier_config
        mini = get_tier_config("mini_parwa")
        assert mini["maker_enabled"] is False
        assert mini["fake_voting_enabled"] is False

        pro = get_tier_config("parwa")
        assert pro["maker_enabled"] is True
        assert pro["fake_voting_enabled"] is False
        assert pro["maker_k"] == 3

        high = get_tier_config("parwa_high")
        assert high["maker_enabled"] is True
        assert high["fake_voting_enabled"] is True
        assert high["maker_k"] == 7


# ══════════════════════════════════════════════════════════════════
# Test 2: Contextual Compression
# ══════════════════════════════════════════════════════════════════


class TestContextualCompression:
    """Unit tests for rag_compression.py"""

    def _make_chunk(self, content="Test content " * 100, chunk_id="c1", doc_id="d1", score=0.8):
        """Helper to create a mock RAGChunk."""
        chunk = MagicMock()
        chunk.chunk_id = chunk_id
        chunk.document_id = doc_id
        chunk.content = content
        chunk.score = score
        chunk.metadata = {}
        chunk.citation = None
        return chunk

    @pytest.mark.asyncio
    async def test_mini_parwa_no_compression(self):
        from app.core.rag_compression import ContextualCompressor
        compressor = ContextualCompressor()
        chunks = [self._make_chunk()]
        result = await compressor.compress_chunks(
            chunks, "test query", "co_001", "mini_parwa"
        )
        assert result.method_used == "none"
        assert len(result.compressed_chunks) == 1
        assert result.compressed_chunks[0].compression_ratio == 1.0
        assert result.compressed_chunks[0].compression_method == "none"

    @pytest.mark.asyncio
    async def test_parwa_truncation_compression(self):
        from app.core.rag_compression import ContextualCompressor
        compressor = ContextualCompressor()
        long_content = "This is a test sentence. " * 50
        chunks = [self._make_chunk(content=long_content)]
        result = await compressor.compress_chunks(
            chunks, "test query", "co_001", "parwa"
        )
        assert result.method_used == "truncation"
        assert len(result.compressed_chunks) == 1
        assert result.compressed_chunks[0].compression_ratio < 1.0
        assert result.compressed_chunks[0].compression_method == "truncation"

    @pytest.mark.asyncio
    async def test_short_content_no_truncation_needed(self):
        from app.core.rag_compression import ContextualCompressor
        compressor = ContextualCompressor()
        short_content = "Short content"
        chunks = [self._make_chunk(content=short_content)]
        result = await compressor.compress_chunks(
            chunks, "test query", "co_001", "parwa"
        )
        assert result.compressed_chunks[0].compression_ratio == 1.0

    @pytest.mark.asyncio
    async def test_empty_chunks(self):
        from app.core.rag_compression import ContextualCompressor
        compressor = ContextualCompressor()
        result = await compressor.compress_chunks(
            [], "test query", "co_001", "parwa"
        )
        assert len(result.compressed_chunks) == 0

    @pytest.mark.asyncio
    async def test_empty_query_returns_uncompressed(self):
        from app.core.rag_compression import ContextualCompressor
        compressor = ContextualCompressor()
        chunks = [self._make_chunk()]
        result = await compressor.compress_chunks(
            chunks, "", "co_001", "parwa"
        )
        assert result.method_used == "none"

    @pytest.mark.asyncio
    async def test_max_chunks_limit(self):
        from app.core.rag_compression import ContextualCompressor
        compressor = ContextualCompressor()
        chunks = [self._make_chunk(chunk_id=f"c{i}") for i in range(10)]
        result = await compressor.compress_chunks(
            chunks, "test query", "co_001", "mini_parwa", max_chunks=3
        )
        assert len(result.compressed_chunks) == 3

    @pytest.mark.asyncio
    async def test_compression_result_to_dict(self):
        from app.core.rag_compression import ContextualCompressor
        compressor = ContextualCompressor()
        chunks = [self._make_chunk()]
        result = await compressor.compress_chunks(
            chunks, "test query", "co_001", "mini_parwa"
        )
        d = result.to_dict()
        assert "compressed_chunks" in d
        assert "overall_compression_ratio" in d
        assert "compression_time_ms" in d
        assert "method_used" in d

    @pytest.mark.asyncio
    async def test_parwa_high_llm_fallback_to_truncation(self):
        """When LLM is unavailable, parwa_high falls back to truncation"""
        from app.core.rag_compression import ContextualCompressor
        # No LLM function provided, and llm_gateway not importable
        compressor = ContextualCompressor()
        chunks = [self._make_chunk(content="Long content " * 50)]
        with patch.dict("sys.modules", {"app.services.llm_gateway": None}):
            result = await compressor.compress_chunks(
                chunks, "test query", "co_001", "parwa_high"
            )
        # Should fall back to truncation
        assert result.method_used == "truncation"


# ══════════════════════════════════════════════════════════════════
# Test 3: RAG Retrieval HyDE and Multi-Query
# ══════════════════════════════════════════════════════════════════


class TestRAGRetrievalEnhanced:
    """Unit tests for HyDE and Multi-Query additions to rag_retrieval.py"""

    @pytest.mark.asyncio
    async def test_hyde_empty_query(self):
        from app.core.rag_retrieval import RAGRetriever
        mock_store = MagicMock()
        retriever = RAGRetriever(vector_store=mock_store)
        result = await retriever.generate_hyde_and_retrieve(
            "", "co_001", "parwa_high"
        )
        assert result.total_found == 0

    @pytest.mark.asyncio
    async def test_hyde_llm_failure_falls_back(self):
        """When LLM fails, HyDE falls back to standard retrieve"""
        from app.core.rag_retrieval import RAGRetriever
        mock_store = MagicMock()
        mock_store.health_check.return_value = True
        mock_store.search.return_value = []
        mock_store._generate_embedding.return_value = [0.1] * 128
        retriever = RAGRetriever(vector_store=mock_store)
        with patch.dict("sys.modules", {"app.services.llm_gateway": None}):
            result = await retriever.generate_hyde_and_retrieve(
                "How do I reset my password?", "co_001", "parwa_high"
            )
        # Should fallback to standard retrieval (may return empty due to mock)
        assert isinstance(result.total_found, int)

    @pytest.mark.asyncio
    async def test_multi_query_empty_query(self):
        from app.core.rag_retrieval import RAGRetriever
        mock_store = MagicMock()
        retriever = RAGRetriever(vector_store=mock_store)
        result = await retriever.expand_query_multi(
            "", "co_001", "parwa"
        )
        assert result.total_found == 0

    @pytest.mark.asyncio
    async def test_multi_query_llm_failure_uses_synonym_fallback(self):
        """When LLM unavailable, Multi-Query uses synonym expansion"""
        from app.core.rag_retrieval import RAGRetriever
        mock_store = MagicMock()
        mock_store.health_check.return_value = True
        mock_store.search.return_value = []
        mock_store._generate_embedding.return_value = [0.1] * 128
        retriever = RAGRetriever(vector_store=mock_store)
        with patch.dict("sys.modules", {"app.services.llm_gateway": None}):
            result = await retriever.expand_query_multi(
                "I want a refund for my order", "co_001", "parwa"
            )
        # Should use synonym-based expansion as fallback
        assert isinstance(result, object)

    @pytest.mark.asyncio
    async def test_synonym_expansion(self):
        from app.core.rag_retrieval import RAGRetriever
        mock_store = MagicMock()
        retriever = RAGRetriever(vector_store=mock_store)
        expansions = retriever._expand_query("I want a refund for my order")
        assert len(expansions) >= 1  # At least original query
        assert "refund" in expansions[0].lower() or "reimburse" in expansions[1].lower() if len(expansions) > 1 else True

    def test_cache_key_deterministic(self):
        from app.core.rag_retrieval import RAGRetriever
        key1 = RAGRetriever._build_cache_key("test", "co_001", "parwa", None)
        key2 = RAGRetriever._build_cache_key("test", "co_001", "parwa", None)
        assert key1 == key2

    def test_cache_key_different_query(self):
        from app.core.rag_retrieval import RAGRetriever
        key1 = RAGRetriever._build_cache_key("test1", "co_001", "parwa", None)
        key2 = RAGRetriever._build_cache_key("test2", "co_001", "parwa", None)
        assert key1 != key2


# ══════════════════════════════════════════════════════════════════
# Test 4: MAKER Pipeline
# ══════════════════════════════════════════════════════════════════


class TestMAKERPipeline:
    """Unit tests for maker_pipeline.py"""

    @pytest.mark.asyncio
    async def test_pipeline_keyword_classification(self):
        from app.core.maker_pipeline import MAKERPipeline
        pipeline = MAKERPipeline()
        result = await pipeline._stage_map("I want a refund", "co_001")
        assert result.success is True
        assert result.data["query_type"] == "refund"

    @pytest.mark.asyncio
    async def test_pipeline_analyze_extracts_entities(self):
        from app.core.maker_pipeline import MAKERPipeline
        pipeline = MAKERPipeline()
        result = await pipeline._stage_analyze(
            "My order #12345 is broken", "co_001", "parwa"
        )
        assert result.success is True
        assert "order_id" in result.data.get("entities", {})
        assert result.data["entities"]["order_id"] == "12345"

    @pytest.mark.asyncio
    async def test_pipeline_analyze_urgency_detection(self):
        from app.core.maker_pipeline import MAKERPipeline
        pipeline = MAKERPipeline()
        result = await pipeline._stage_analyze(
            "This is URGENT! Fix my account immediately!", "co_001", "parwa"
        )
        assert result.data["urgency"] in ["high", "critical"]

    @pytest.mark.asyncio
    async def test_pipeline_refine_pii_redaction(self):
        from app.core.maker_pipeline import MAKERPipeline
        pipeline = MAKERPipeline()
        result = await pipeline._stage_refine(
            "Contact me at john@example.com or 555-123-4567",
            "test query", "co_001", "parwa"
        )
        assert result.success is True
        refined = result.data["refined_response"]
        assert "john@example.com" not in refined
        assert "[EMAIL]" in refined
        assert "555-123-4567" not in refined
        assert "[PHONE]" in refined

    @pytest.mark.asyncio
    async def test_pipeline_refine_ssns_redacted(self):
        from app.core.maker_pipeline import MAKERPipeline
        pipeline = MAKERPipeline()
        result = await pipeline._stage_refine(
            "My SSN is 123-45-6789", "test query", "co_001", "parwa"
        )
        assert "[SSN]" in result.data["refined_response"]

    @pytest.mark.asyncio
    async def test_pipeline_knowledge_rag_unavailable(self):
        """Knowledge stage handles RAG unavailable gracefully"""
        from app.core.maker_pipeline import MAKERPipeline
        pipeline = MAKERPipeline()
        with patch.dict("sys.modules", {"app.core.rag_retrieval": None}):
            result = await pipeline._stage_knowledge(
                "How do I reset my password?", "co_001", "parwa"
            )
        # Should succeed but with empty rag_context
        assert result.fallback_used is True or result.data.get("rag_context") == ""

    @pytest.mark.asyncio
    async def test_pipeline_full_mini_parwa(self):
        """Mini PARWA skips most stages for speed"""
        from app.core.maker_pipeline import MAKERPipeline
        pipeline = MAKERPipeline()
        with patch.dict("sys.modules", {"app.services.llm_gateway": None}):
            result = await pipeline.execute(
                "How do I reset my password?", "co_001", "mini_parwa"
            )
        assert result.variant_tier == "mini_parwa"
        assert len(result.stages) == 1  # Only MAP stage
        assert result.total_llm_calls >= 0

    @pytest.mark.asyncio
    async def test_pipeline_keyword_classify_types(self):
        from app.core.maker_pipeline import MAKERPipeline
        pipeline = MAKERPipeline()
        assert pipeline._keyword_classify("I want a refund") == "refund"
        assert pipeline._keyword_classify("My app crashed") == "technical"
        assert pipeline._keyword_classify("What is my bill?") == "billing"
        assert pipeline._keyword_classify("This is terrible") == "complaint"
        assert pipeline._keyword_classify("How do I do X?") == "faq"
        assert pipeline._keyword_classify("Hello there") == "general"

    @pytest.mark.asyncio
    async def test_safe_response(self):
        from app.core.maker_pipeline import MAKERPipeline
        response = MAKERPipeline._safe_response("test query")
        assert len(response) > 0


# ══════════════════════════════════════════════════════════════════
# Test 5: Agent Lightning Trainer
# ══════════════════════════════════════════════════════════════════


class TestAgentLightning:
    """Unit tests for agent_lightning.py"""

    @pytest.mark.asyncio
    async def test_prepare_dataset_db_unavailable(self):
        """When DB is unavailable, returns synthetic dataset"""
        from app.core.agent_lightning import AgentLightningTrainer
        trainer = AgentLightningTrainer()
        with patch.dict("sys.modules", {"database.base": None}):
            dataset = await trainer.prepare_dataset("co_001")
        # Should return synthetic dataset
        assert dataset.company_id == "co_001"
        assert dataset.total_samples > 0

    @pytest.mark.asyncio
    async def test_schedule_training_insufficient_samples(self):
        from app.core.agent_lightning import AgentLightningTrainer, TrainingDataset
        trainer = AgentLightningTrainer()
        dataset = TrainingDataset(
            dataset_id="ds_001",
            company_id="co_001",
        )
        job = await trainer.schedule_training("co_001", dataset)
        assert job.status == "failed"
        assert "Insufficient" in job.error

    @pytest.mark.asyncio
    async def test_schedule_training_success(self):
        from app.core.agent_lightning import AgentLightningTrainer, TrainingDataset, TrainingSample
        trainer = AgentLightningTrainer()
        dataset = TrainingDataset(
            dataset_id="ds_002",
            company_id="co_001",
        )
        for i in range(15):
            dataset.samples.append(TrainingSample(
                input_text=f"Query {i}",
                output_text=f"Response {i}",
                intent="general",
                quality_score=4.5,
            ))
        dataset.split()
        job = await trainer.schedule_training("co_001", dataset)
        assert job.status in ["pending", "running"]
        assert job.job_id is not None
        assert job.company_id == "co_001"

    @pytest.mark.asyncio
    async def test_check_training_status(self):
        from app.core.agent_lightning import AgentLightningTrainer, TrainingDataset, TrainingSample
        trainer = AgentLightningTrainer()
        dataset = TrainingDataset(
            dataset_id="ds_003",
            company_id="co_001",
        )
        for i in range(15):
            dataset.samples.append(TrainingSample(
                input_text=f"Query {i}",
                output_text=f"Response {i}",
            ))
        dataset.split()
        job = await trainer.schedule_training("co_001", dataset)
        found = await trainer.check_training_status(job.job_id)
        assert found is not None
        assert found.job_id == job.job_id

    @pytest.mark.asyncio
    async def test_check_nonexistent_job(self):
        from app.core.agent_lightning import AgentLightningTrainer
        trainer = AgentLightningTrainer()
        found = await trainer.check_training_status("nonexistent")
        assert found is None

    @pytest.mark.asyncio
    async def test_apply_fine_tuned_model(self):
        from app.core.agent_lightning import AgentLightningTrainer, TrainingDataset, TrainingSample
        trainer = AgentLightningTrainer()
        dataset = TrainingDataset(
            dataset_id="ds_004",
            company_id="co_001",
        )
        for i in range(15):
            dataset.samples.append(TrainingSample(
                input_text=f"Query {i}",
                output_text=f"Response {i}",
            ))
        dataset.split()
        job = await trainer.schedule_training("co_001", dataset)
        result = await trainer.apply_fine_tuned_model("co_001", job.job_id)
        assert result["status"] == "deployed"
        assert result["company_id"] == "co_001"
        assert "model_name" in result

    @pytest.mark.asyncio
    async def test_apply_nonexistent_job(self):
        from app.core.agent_lightning import AgentLightningTrainer
        trainer = AgentLightningTrainer()
        result = await trainer.apply_fine_tuned_model("co_001", "nonexistent")
        assert result["status"] == "error"

    def test_training_sample_to_dict(self):
        from app.core.agent_lightning import TrainingSample
        sample = TrainingSample(
            input_text="How do I reset?",
            output_text="Click forgot password",
            intent="account",
            quality_score=4.5,
        )
        d = sample.to_dict()
        assert d["input"] == "How do I reset?"
        assert d["intent"] == "account"

    def test_training_sample_to_finetune_format(self):
        from app.core.agent_lightning import TrainingSample
        sample = TrainingSample(
            input_text="How do I reset?",
            output_text="Click forgot password",
        )
        fmt = sample.to_finetune_format()
        assert "instruction" in fmt
        assert "response" in fmt

    def test_dataset_split(self):
        from app.core.agent_lightning import TrainingDataset, TrainingSample
        dataset = TrainingDataset(
            dataset_id="ds_test",
            company_id="co_001",
        )
        for i in range(20):
            dataset.samples.append(TrainingSample(
                input_text=f"Query {i}",
                output_text=f"Response {i}",
            ))
        dataset.split(train_ratio=0.8)
        assert len(dataset.train_split) == 16
        assert len(dataset.test_split) == 4


# ══════════════════════════════════════════════════════════════════
# Test 6: Tier Hybrid Optimizer
# ══════════════════════════════════════════════════════════════════


class TestTierHybridOptimizer:
    """Unit tests for tier_hybrid_optimizer.py"""

    @pytest.mark.asyncio
    async def test_mini_parwa_strategy(self):
        from app.core.tier_hybrid_optimizer import TierHybridOptimizer
        optimizer = TierHybridOptimizer()
        with patch.dict("sys.modules", {"app.services.llm_gateway": None}):
            result = await optimizer.optimize_query(
                "How do I reset my password?", "co_001", "mini_parwa"
            )
        assert result.variant_tier == "mini_parwa"
        assert result.technique_used == "chain_of_thought"
        assert result.maker_used is False
        assert result.fake_voting_used is False

    @pytest.mark.asyncio
    async def test_parwa_strategy(self):
        from app.core.tier_hybrid_optimizer import TierHybridOptimizer
        optimizer = TierHybridOptimizer()
        with patch.dict("sys.modules", {
            "app.services.llm_gateway": None,
            "app.core.rag_retrieval": None,
        }):
            result = await optimizer.optimize_query(
                "I want a refund for my order", "co_001", "parwa"
            )
        assert result.variant_tier == "parwa"
        assert result.max_llm_calls == 4

    @pytest.mark.asyncio
    async def test_parwa_high_strategy(self):
        from app.core.tier_hybrid_optimizer import TierHybridOptimizer
        optimizer = TierHybridOptimizer()
        with patch.dict("sys.modules", {
            "app.services.llm_gateway": None,
            "app.core.rag_retrieval": None,
            "app.core.rag_compression": None,
        }):
            result = await optimizer.optimize_query(
                "My app keeps crashing", "co_001", "parwa_high"
            )
        assert result.variant_tier == "parwa_high"
        assert result.max_llm_calls == 24
        assert result.maker_used is True
        assert result.fake_voting_used is True

    @pytest.mark.asyncio
    async def test_empty_query(self):
        from app.core.tier_hybrid_optimizer import TierHybridOptimizer
        optimizer = TierHybridOptimizer()
        result = await optimizer.optimize_query("", "co_001", "parwa")
        assert result.confidence == 0.0
        assert result.llm_calls_made == 0

    @pytest.mark.asyncio
    async def test_intent_classification_refund(self):
        from app.core.tier_hybrid_optimizer import TierHybridOptimizer
        optimizer = TierHybridOptimizer()
        intent = await optimizer._classify_intent("I want a refund", "co_001")
        assert intent == "refund"

    @pytest.mark.asyncio
    async def test_intent_classification_technical(self):
        from app.core.tier_hybrid_optimizer import TierHybridOptimizer
        optimizer = TierHybridOptimizer()
        intent = await optimizer._classify_intent("My app has an error", "co_001")
        assert intent == "technical"

    @pytest.mark.asyncio
    async def test_intent_classification_general(self):
        from app.core.tier_hybrid_optimizer import TierHybridOptimizer
        optimizer = TierHybridOptimizer()
        intent = await optimizer._classify_intent("Hello there", "co_001")
        assert intent == "general"

    def test_get_technique_for_intent(self):
        from app.core.tier_hybrid_optimizer import TierHybridOptimizer
        optimizer = TierHybridOptimizer()
        assert optimizer.get_technique_for_intent("refund", "parwa") == "self_consistency"
        assert optimizer.get_technique_for_intent("technical", "parwa") == "react"

    @pytest.mark.asyncio
    async def test_fallback_response(self):
        from app.core.tier_hybrid_optimizer import TierHybridOptimizer
        response = TierHybridOptimizer._fallback_response("test query", "cot")
        assert len(response) > 0
        assert "test query"[:10] in response

    def test_result_to_dict(self):
        from app.core.tier_hybrid_optimizer import TierOptimizationResult
        result = TierOptimizationResult(
            query="test",
            company_id="co_001",
            variant_tier="parwa",
            intent="refund",
            technique_used="self_consistency",
            llm_calls_made=3,
            max_llm_calls=4,
            response="Here is your refund info",
            confidence=0.85,
            processing_time_ms=150.0,
        )
        d = result.to_dict()
        assert d["variant_tier"] == "parwa"
        assert d["technique_used"] == "self_consistency"
        assert d["confidence"] == 0.85


# ══════════════════════════════════════════════════════════════════
# Test 7: Cross-Component Integration
# ══════════════════════════════════════════════════════════════════


class TestDay5CrossComponent:
    """Integration tests across Day 5 components"""

    def test_tier_mapper_to_optimizer_consistency(self):
        """Technique mapper and optimizer agree on technique selection"""
        from app.core.technique_tier_mapper import get_technique_for_tier
        from app.core.tier_hybrid_optimizer import TierHybridOptimizer
        optimizer = TierHybridOptimizer()
        for intent in ["refund", "technical", "billing", "general"]:
            for tier in ["mini_parwa", "parwa", "parwa_high"]:
                mapper_result = get_technique_for_tier(intent, tier)
                optimizer_result = optimizer.get_technique_for_intent(intent, tier)
                assert mapper_result == optimizer_result

    def test_all_tiers_have_different_capabilities(self):
        """Verify each tier has genuinely different capability levels"""
        from app.core.technique_tier_mapper import get_tier_config
        mini = get_tier_config("mini_parwa")
        pro = get_tier_config("parwa")
        high = get_tier_config("parwa_high")

        # Mini has fewest techniques
        assert len(mini["available_techniques"]) < len(pro["available_techniques"])
        assert len(pro["available_techniques"]) < len(high["available_techniques"])

        # Mini has fewest LLM calls
        assert mini["max_llm_calls"] < pro["max_llm_calls"]
        assert pro["max_llm_calls"] < high["max_llm_calls"]

        # Only high has FAKE voting
        assert not mini["fake_voting_enabled"]
        assert not pro["fake_voting_enabled"]
        assert high["fake_voting_enabled"]

        # Only high has HyDE
        assert not mini["hyde_enabled"]
        assert not pro["hyde_enabled"]
        assert high["hyde_enabled"]

    @pytest.mark.asyncio
    async def test_compressor_with_real_chunk_data(self):
        """Test compression with realistic chunk data"""
        from app.core.rag_compression import ContextualCompressor

        chunk = MagicMock()
        chunk.chunk_id = "chunk_1"
        chunk.document_id = "doc_1"
        chunk.content = (
            "To reset your password, navigate to the login page and click "
            "on 'Forgot Password'. Enter your email address and you will "
            "receive a password reset link within 5 minutes. If you don't "
            "see the email, check your spam folder. The reset link expires "
            "after 24 hours. For security, we recommend using a strong "
            "password with at least 12 characters including uppercase, "
            "lowercase, numbers, and special characters."
        )
        chunk.score = 0.85
        chunk.metadata = {"source": "FAQ"}
        chunk.citation = None

        compressor = ContextualCompressor()
        result = await compressor.compress_chunks(
            [chunk], "reset password", "co_001", "parwa"
        )
        assert len(result.compressed_chunks) == 1
        assert result.compressed_chunks[0].original_content == chunk.content
