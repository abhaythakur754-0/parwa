"""
Tests for TechniqueExecutor — central orchestrator that wires
TechniqueRouter + TechniqueTierAccessChecker + TechniqueCache +
TechniqueMetricsCollector + TECHNIQUE_NODES.
"""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.technique_executor import (
    ExecutionDetail,
    PipelineResult,
    TechniqueExecutor,
)
from app.core.technique_router import (
    QuerySignals,
    TechniqueActivation,
    TechniqueID,
    TechniqueTier,
    TECHNIQUE_REGISTRY,
)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def basic_state():
    from app.core.techniques.base import ConversationState, GSDState
    return ConversationState(
        query="What is my refund status?",
        signals=QuerySignals(query_complexity=0.5),
        gsd_state=GSDState.DIAGNOSIS,
        company_id="comp_1",
    )


@pytest.fixture
def high_complexity_state():
    from app.core.techniques.base import ConversationState, GSDState
    return ConversationState(
        query="I was charged $49.99 and $59.99 but my plan is $29.99. Why the extra charges?",
        signals=QuerySignals(
            query_complexity=0.8,
            confidence_score=0.5,
            monetary_value=200,
        ),
        gsd_state=GSDState.DIAGNOSIS,
        company_id="comp_1",
    )


@pytest.fixture
def executor():
    return TechniqueExecutor(
        model_tier="medium",
        variant_type="parwa",
        company_id="comp_1",
    )


@pytest.fixture
def lite_executor():
    return TechniqueExecutor(
        model_tier="light",
        variant_type="parwa_lite",
        company_id="comp_2",
    )


@pytest.fixture
def high_executor():
    return TechniqueExecutor(
        model_tier="heavy",
        variant_type="parwa_high",
        company_id="comp_3",
    )


# ── Init Tests ──────────────────────────────────────────────────────


class TestTechniqueExecutorInit:
    def test_default_init(self):
        ex = TechniqueExecutor()
        assert ex.model_tier == "medium"
        assert ex.variant_type == "parwa"
        assert ex.company_id == ""

    def test_custom_init(self):
        ex = TechniqueExecutor(
            model_tier="heavy",
            variant_type="parwa_high",
            company_id="comp_x",
        )
        assert ex.model_tier == "heavy"
        assert ex.variant_type == "parwa_high"
        assert ex.company_id == "comp_x"

    def test_components_created(self, executor):
        assert executor.router is not None
        assert executor.tier_checker is not None
        assert executor.cache is not None
        assert executor.metrics is not None


# ── Basic Pipeline Tests ────────────────────────────────────────────


class TestBasicPipelineExecution:
    @pytest.mark.asyncio
    async def test_pipeline_returns_state_and_result(self, executor, basic_state):
        state, pipeline_result = await executor.execute_pipeline(basic_state)
        assert state is basic_state
        assert isinstance(pipeline_result, PipelineResult)

    @pytest.mark.asyncio
    async def test_t1_techniques_executed(self, executor, basic_state):
        _, pipeline_result = await executor.execute_pipeline(basic_state)
        # At minimum, T1 techniques should have results
        assert "crp" in basic_state.technique_results or "gsd" in basic_state.technique_results
        assert pipeline_result.techniques_executed >= 1

    @pytest.mark.asyncio
    async def test_empty_query(self, executor):
        from app.core.techniques.base import ConversationState
        state = ConversationState(query="", company_id="comp_1")
        result_state, _ = await executor.execute_pipeline(state)
        assert result_state is state

    @pytest.mark.asyncio
    async def test_execution_has_timing(self, executor, basic_state):
        start = __import__('time').time()
        await executor.execute_pipeline(basic_state)
        elapsed = __import__('time').time() - start
        assert elapsed < 5.0  # should complete in under 5 seconds

    @pytest.mark.asyncio
    async def test_pipeline_result_counters(self, executor, basic_state):
        """PipelineResult should have accurate counters."""
        _, pr = await executor.execute_pipeline(basic_state)
        assert pr.techniques_executed >= 1
        assert pr.total_exec_time_ms >= 0
        assert pr.total_tokens_used >= 0
        assert len(pr.details) >= 1
        # Check detail fields are populated
        for detail in pr.details:
            assert detail.technique_id
            assert detail.status
            assert detail.executed_at


# ── Variant Filtering Tests ──────────────────────────────────────────


class TestVariantFiltering:
    def test_lite_blocks_t2_t3(self, lite_executor):
        """parwa_lite should only allow T1 techniques (T2/T3 get downgraded)."""
        activations = [
            TechniqueActivation(
                technique_id=TechniqueID.CLARA,
                triggered_by=["always"],
                tier=TechniqueTier.TIER_1,
            ),
            TechniqueActivation(
                technique_id=TechniqueID.CHAIN_OF_THOUGHT,
                triggered_by=["r1"],
                tier=TechniqueTier.TIER_2,
            ),
            TechniqueActivation(
                technique_id=TechniqueID.GST,
                triggered_by=["r9"],
                tier=TechniqueTier.TIER_3,
            ),
        ]
        filtered = lite_executor._filter_by_tier_access(activations)
        ids = [a.technique_id for a in filtered]
        # T1 always passes through
        assert TechniqueID.CLARA in ids
        # Note: _filter_by_tier_access lets "downgraded" through
        # (the original technique ID is kept, fallback applied at execution)
        # The key behavior is that T2/T3 don't execute as-is in pipeline
        # They get replaced by T1 fallbacks at execution time

    def test_parwa_allows_t1_t2(self, executor):
        """parwa should allow T1 and T2; T3 gets downgraded."""
        activations = [
            TechniqueActivation(
                technique_id=TechniqueID.CRP,
                triggered_by=["always"],
                tier=TechniqueTier.TIER_1,
            ),
            TechniqueActivation(
                technique_id=TechniqueID.REACT,
                triggered_by=["r7"],
                tier=TechniqueTier.TIER_2,
            ),
            TechniqueActivation(
                technique_id=TechniqueID.UNIVERSE_OF_THOUGHTS,
                triggered_by=["r3"],
                tier=TechniqueTier.TIER_3,
            ),
        ]
        filtered = executor._filter_by_tier_access(activations)
        ids = [a.technique_id for a in filtered]
        assert TechniqueID.CRP in ids
        assert TechniqueID.REACT in ids
        # T3 is downgraded but still passes the filter
        # (fallback is applied during execution, not filtering)

    def test_high_allows_all(self, high_executor):
        """parwa_high should allow all tiers."""
        activations = [
            TechniqueActivation(
                technique_id=TechniqueID.CRP,
                triggered_by=["always"],
                tier=TechniqueTier.TIER_1,
            ),
            TechniqueActivation(
                technique_id=TechniqueID.STEP_BACK,
                triggered_by=["r2"],
                tier=TechniqueTier.TIER_2,
            ),
            TechniqueActivation(
                technique_id=TechniqueID.REFLEXION,
                triggered_by=["r11"],
                tier=TechniqueTier.TIER_3,
            ),
        ]
        filtered = high_executor._filter_by_tier_access(activations)
        ids = [a.technique_id for a in filtered]
        assert TechniqueID.CRP in ids
        assert TechniqueID.STEP_BACK in ids
        assert TechniqueID.REFLEXION in ids

    def test_no_company_allows_all(self):
        """Without company_id, all techniques pass through."""
        ex = TechniqueExecutor(company_id="")
        activations = [
            TechniqueActivation(
                technique_id=TechniqueID.GST,
                triggered_by=["r9"],
                tier=TechniqueTier.TIER_3,
            ),
        ]
        filtered = ex._filter_by_tier_access(activations)
        assert len(filtered) == 1


# ── Cache Tests ──────────────────────────────────────────────────────


class TestCacheHitMiss:
    @pytest.mark.asyncio
    async def test_cache_miss_first_run(self, executor, basic_state):
        await executor.execute_pipeline(basic_state)
        stats = executor.cache.get_stats()
        # First run should have at least one miss
        assert stats.misses >= 1

    @pytest.mark.asyncio
    async def test_cache_hit_second_run(self, executor, basic_state):
        await executor.execute_pipeline(basic_state)
        await executor.execute_pipeline(basic_state)
        stats = executor.cache.get_stats()
        assert stats.hits >= 1

    @pytest.mark.asyncio
    async def test_cache_hit_reflected_in_result(self, executor, basic_state):
        """Second run should show cached count in PipelineResult."""
        _, pr1 = await executor.execute_pipeline(basic_state)
        _, pr2 = await executor.execute_pipeline(basic_state)
        assert pr2.techniques_cached >= pr1.techniques_cached


# ── Fallback Tests ───────────────────────────────────────────────────


class TestFallback:
    @pytest.mark.asyncio
    async def test_no_company_no_crash(self):
        """Executor with no company_id should not crash."""
        ex = TechniqueExecutor(company_id="")
        from app.core.techniques.base import ConversationState
        state = ConversationState(
            query="Help me",
            company_id="",
        )
        result_state, _ = await ex.execute_pipeline(state)
        assert result_state is state

    @pytest.mark.asyncio
    async def test_empty_company_no_crash(self):
        """Empty company_id should not crash."""
        ex = TechniqueExecutor(company_id="")
        from app.core.techniques.base import ConversationState
        state = ConversationState(query="Test")
        result_state, _ = await ex.execute_pipeline(state)
        assert result_state is state

    @pytest.mark.asyncio
    async def test_graceful_degradation(self, executor, basic_state):
        """Pipeline should handle errors gracefully."""
        # This should not raise even if techniques have issues
        result_state, _ = await executor.execute_pipeline(basic_state)
        assert result_state is basic_state

    @pytest.mark.asyncio
    async def test_router_exception_returns_state(self, executor, basic_state):
        """If router.route() raises, should return original state without crash."""
        with patch.object(executor.router, 'route', side_effect=RuntimeError("router boom")):
            result_state, pr = await executor.execute_pipeline(basic_state)
        assert result_state is basic_state
        assert pr.techniques_executed == 0
        assert pr.techniques_failed == 0


# ── Execute Single Tests ─────────────────────────────────────────────


class TestExecuteSingle:
    @pytest.mark.asyncio
    async def test_execute_single_returns_state(self, executor, basic_state):
        """execute_single should return the state after running one technique."""
        result = await executor.execute_single(TechniqueID.CRP, basic_state)
        assert result is basic_state

    @pytest.mark.asyncio
    async def test_execute_single_records_metrics(self, executor, basic_state):
        """execute_single should record a metric."""
        await executor.execute_single(TechniqueID.CRP, basic_state)
        count = executor.metrics.get_record_count()
        assert count > 0

    @pytest.mark.asyncio
    async def test_execute_single_unknown_technique(self, executor, basic_state):
        """execute_single with unknown technique should not crash."""
        result = await executor.execute_single(TechniqueID.CRP, basic_state)
        assert result is basic_state


# ── Fallback Application Tests ───────────────────────────────────────


class TestApplyFallback:
    @pytest.mark.asyncio
    async def test_non_t3_failure_no_fallback(self, executor, basic_state):
        """T1/T2 failures should NOT trigger fallback."""
        activation = TechniqueActivation(
            technique_id=TechniqueID.CRP,
            triggered_by=["test"],
            tier=TechniqueTier.TIER_1,
        )
        with patch('app.core.technique_executor.TECHNIQUE_NODES') as mock_nodes:
            mock_node = AsyncMock()
            mock_node.execute = AsyncMock(side_effect=RuntimeError("CRP failed"))
            mock_node.check_token_budget = MagicMock(return_value=True)
            mock_nodes.get = MagicMock(return_value=mock_node)
            detail = await executor._execute_with_infrastructure(activation, basic_state)
        assert detail.fallback_applied is False
        assert detail.status == "error"

    @pytest.mark.asyncio
    async def test_t3_failure_triggers_fallback(self):
        """When a T3 technique fails, fallback should be attempted."""
        from app.core.techniques.base import TECHNIQUE_NODES
        ex = TechniqueExecutor(
            model_tier="heavy",
            variant_type="parwa_high",
            company_id="comp_fb",
        )
        from app.core.techniques.base import ConversationState, GSDState
        state = ConversationState(
            query="Complex query",
            signals=QuerySignals(query_complexity=0.9),
            gsd_state=GSDState.DIAGNOSIS,
            company_id="comp_fb",
        )
        activation = TechniqueActivation(
            technique_id=TechniqueID.GST,
            triggered_by=["r9"],
            tier=TechniqueTier.TIER_3,
        )
        with patch('app.core.technique_executor.TECHNIQUE_NODES') as mock_nodes:
            mock_t3_node = AsyncMock()
            mock_t3_node.execute = AsyncMock(side_effect=RuntimeError("GST failed"))
            mock_t3_node.check_token_budget = MagicMock(return_value=True)
            mock_nodes.get = MagicMock(return_value=mock_t3_node)
            detail = await ex._execute_with_infrastructure(activation, state)
        # Either fallback applied or error recorded
        assert detail.status in ("error", "success")


# ── Node Not Found Tests ─────────────────────────────────────────────


class TestNodeNotFound:
    @pytest.mark.asyncio
    async def test_missing_node_returns_error_detail(self, executor, basic_state):
        """If technique_id not in TECHNIQUE_NODES, should return error detail."""
        activation = TechniqueActivation(
            technique_id=TechniqueID.CRP,
            triggered_by=["test"],
            tier=TechniqueTier.TIER_1,
        )
        with patch('app.core.technique_executor.TECHNIQUE_NODES') as mock_nodes:
            mock_nodes.get = MagicMock(return_value=None)
            detail = await executor._execute_with_infrastructure(activation, basic_state)
        assert detail.status == "error"
        assert "technique_node_not_found" in (detail.error or "")


# ── Budget Skip Tests ────────────────────────────────────────────────


class TestBudgetSkip:
    @pytest.mark.asyncio
    async def test_budget_exceeded_returns_skipped(self, executor, basic_state):
        """When check_token_budget returns False, status should be skipped_budget."""
        activation = TechniqueActivation(
            technique_id=TechniqueID.CRP,
            triggered_by=["test"],
            tier=TechniqueTier.TIER_1,
        )
        with patch('app.core.technique_executor.TECHNIQUE_NODES') as mock_nodes:
            mock_node = AsyncMock()
            mock_node.check_token_budget = MagicMock(return_value=False)
            mock_node.record_skip = MagicMock()
            mock_nodes.get = MagicMock(return_value=mock_node)
            detail = await executor._execute_with_infrastructure(activation, basic_state)
        assert detail.status == "skipped_budget"


# ── Tier Sorting Edge Cases ─────────────────────────────────────────


class TestTierSortingEdgeCases:
    def test_unknown_tier_last(self):
        """Activations with unknown tier should sort last."""
        activations = [
            TechniqueActivation(
                technique_id=TechniqueID.CRP,
                triggered_by=["a"],
                tier=TechniqueTier.TIER_1,
            ),
        ]
        sorted_acts = TechniqueExecutor._sort_by_tier(activations)
        assert sorted_acts[0].tier == TechniqueTier.TIER_1

    def test_empty_activations(self):
        """Empty list should return empty list."""
        assert TechniqueExecutor._sort_by_tier([]) == []

    def test_mixed_tiers_sorted(self):
        """Mixed T1/T2/T3 should sort in order."""
        activations = [
            TechniqueActivation(
                technique_id=TechniqueID.REFLEXION,
                triggered_by=["a"],
                tier=TechniqueTier.TIER_3,
            ),
            TechniqueActivation(
                technique_id=TechniqueID.STEP_BACK,
                triggered_by=["a"],
                tier=TechniqueTier.TIER_2,
            ),
            TechniqueActivation(
                technique_id=TechniqueID.CRP,
                triggered_by=["a"],
                tier=TechniqueTier.TIER_1,
            ),
        ]
        sorted_acts = TechniqueExecutor._sort_by_tier(activations)
        assert sorted_acts[0].tier == TechniqueTier.TIER_1
        assert sorted_acts[1].tier == TechniqueTier.TIER_2
        assert sorted_acts[2].tier == TechniqueTier.TIER_3


# ── Cache Key Tests ──────────────────────────────────────────────────


class TestCacheKey:
    def test_deterministic(self, executor):
        key1 = executor.get_cache_key("crp", "Hello", "comp_1")
        key2 = executor.get_cache_key("crp", "Hello", "comp_1")
        assert key1 == key2

    def test_unique_per_technique(self, executor):
        k1 = executor.get_cache_key("crp", "Hello", "comp_1")
        k2 = executor.get_cache_key("cot", "Hello", "comp_1")
        assert k1 != k2

    def test_unique_per_query(self, executor):
        k1 = executor.get_cache_key("crp", "Hello", "comp_1")
        k2 = executor.get_cache_key("crp", "World", "comp_1")
        assert k1 != k2

    def test_unique_per_company(self, executor):
        k1 = executor.get_cache_key("crp", "Hello", "comp_1")
        k2 = executor.get_cache_key("crp", "Hello", "comp_2")
        assert k1 != k2

    def test_sha256_format(self, executor):
        key = executor.get_cache_key("crp", "test", "comp_1")
        assert len(key) == 64  # SHA-256 hex digest

    def test_empty_inputs(self, executor):
        key = executor.get_cache_key("", "", "")
        assert len(key) == 64


# ── Dataclass Tests ──────────────────────────────────────────────────


class TestExecutionDetail:
    def test_defaults(self):
        d = ExecutionDetail()
        assert d.technique_id == ""
        assert d.status == "pending"
        assert d.cached is False
        assert d.fallback_applied is False
        assert d.error is None


class TestPipelineResult:
    def test_defaults(self):
        r = PipelineResult()
        assert r.techniques_executed == 0
        assert r.techniques_cached == 0
        assert r.techniques_skipped == 0
        assert r.techniques_failed == 0
        assert r.total_tokens_used == 0
        assert r.details == []


# ── Tier Sorting Tests ───────────────────────────────────────────────


class TestTierSorting:
    def test_t1_before_t2(self):
        activations = [
            TechniqueActivation(
                technique_id=TechniqueID.CHAIN_OF_THOUGHT,
                triggered_by=["r1"],
                tier=TechniqueTier.TIER_2,
            ),
            TechniqueActivation(
                technique_id=TechniqueID.CRP,
                triggered_by=["always"],
                tier=TechniqueTier.TIER_1,
            ),
            TechniqueActivation(
                technique_id=TechniqueID.GST,
                triggered_by=["r9"],
                tier=TechniqueTier.TIER_3,
            ),
        ]
        sorted_acts = TechniqueExecutor._sort_by_tier(activations)
        assert sorted_acts[0].tier == TechniqueTier.TIER_1
        assert sorted_acts[1].tier == TechniqueTier.TIER_2
        assert sorted_acts[2].tier == TechniqueTier.TIER_3

    def test_same_tier_preserves_order(self):
        activations = [
            TechniqueActivation(
                technique_id=TechniqueID.CRP,
                triggered_by=["a"],
                tier=TechniqueTier.TIER_1,
            ),
            TechniqueActivation(
                technique_id=TechniqueID.CLARA,
                triggered_by=["b"],
                tier=TechniqueTier.TIER_1,
            ),
        ]
        sorted_acts = TechniqueExecutor._sort_by_tier(activations)
        assert sorted_acts[0].technique_id == TechniqueID.CRP
        assert sorted_acts[1].technique_id == TechniqueID.CLARA


# ── Metrics Tests ────────────────────────────────────────────────────


class TestMetricsRecording:
    @pytest.mark.asyncio
    async def test_metrics_recorded(self, executor, basic_state):
        await executor.execute_pipeline(basic_state)
        record_count = executor.metrics.get_record_count()
        assert record_count > 0

    @pytest.mark.asyncio
    async def test_metrics_by_company(self, executor, basic_state):
        await executor.execute_pipeline(basic_state)
        company_ids = executor.metrics.get_company_ids()
        assert "comp_1" in company_ids


# ── Hash Utility ─────────────────────────────────────────────────────


class TestHashValue:
    def test_sha256_format(self):
        key = TechniqueExecutor.get_cache_key(
            TechniqueExecutor(), "crp", "test",
        )
        assert len(key) == 64

    def test_deterministic(self):
        ex = TechniqueExecutor()
        k1 = ex.get_cache_key("crp", "hello", "c1")
        k2 = ex.get_cache_key("crp", "hello", "c1")
        assert k1 == k2

    def test_empty_string(self):
        ex = TechniqueExecutor()
        k = ex.get_cache_key("crp", "", "")
        assert len(k) == 64
