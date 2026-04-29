"""
Tests for LangGraph Workflow Engine — Week 10 Day 12
Feature: F-200
Target: 65+ tests
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Runtime-injected by _mock_logger fixture — satisfies flake8 F821
# type: ignore[assignment,misc]
LangGraphWorkflow = WorkflowConfig = WorkflowStep = WorkflowStepResult = (
    WorkflowResult
) = WorkflowError = WORKFLOW_STEP_DEFINITIONS = VARIANT_PIPELINE_CONFIG = None


@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("app.logger.get_logger", return_value=MagicMock()):
        from app.core.langgraph_workflow import (  # noqa: F811,F401
            VARIANT_PIPELINE_CONFIG,
            WORKFLOW_STEP_DEFINITIONS,
            LangGraphWorkflow,
            WorkflowConfig,
            WorkflowError,
            WorkflowResult,
            WorkflowStep,
            WorkflowStepResult,
        )

        globals().update(
            {
                "LangGraphWorkflow": LangGraphWorkflow,
                "WorkflowConfig": WorkflowConfig,
                "WorkflowStep": WorkflowStep,
                "WorkflowStepResult": WorkflowStepResult,
                "WorkflowResult": WorkflowResult,
                "WorkflowError": WorkflowError,
                "WORKFLOW_STEP_DEFINITIONS": WORKFLOW_STEP_DEFINITIONS,
                "VARIANT_PIPELINE_CONFIG": VARIANT_PIPELINE_CONFIG,
            }
        )


# ═══════════════════════════════════════════════════════════════════════
# 1. WorkflowConfig (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestWorkflowConfig:
    def test_default_company_id_empty(self):
        cfg = WorkflowConfig()
        assert cfg.company_id == ""

    def test_default_variant_type_parwa(self):
        cfg = WorkflowConfig()
        assert cfg.variant_type == "parwa"

    def test_default_context_compression_false(self):
        cfg = WorkflowConfig()
        assert cfg.enable_context_compression is False

    def test_default_context_health_check_false(self):
        cfg = WorkflowConfig()
        assert cfg.enable_context_health_check is False

    def test_default_max_pipeline_time(self):
        cfg = WorkflowConfig()
        assert cfg.max_pipeline_time_seconds == 30.0

    def test_default_max_tokens(self):
        cfg = WorkflowConfig()
        assert cfg.max_tokens == 1500

    def test_custom_values(self):
        cfg = WorkflowConfig(
            company_id="corp-1",
            variant_type="parwa_high",
            enable_context_compression=True,
            enable_context_health_check=True,
            max_pipeline_time_seconds=60.0,
            max_tokens=3000,
        )
        assert cfg.company_id == "corp-1"
        assert cfg.variant_type == "parwa_high"
        assert cfg.enable_context_compression is True
        assert cfg.enable_context_health_check is True
        assert cfg.max_pipeline_time_seconds == 60.0
        assert cfg.max_tokens == 3000

    def test_per_variant_defaults(self):
        mini_cfg = WorkflowConfig(variant_type="mini_parwa")
        assert mini_cfg.variant_type == "mini_parwa"
        high_cfg = WorkflowConfig(variant_type="parwa_high")
        assert high_cfg.variant_type == "parwa_high"


# ═══════════════════════════════════════════════════════════════════════
# 2. WorkflowStep (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestWorkflowStep:
    def test_creation_with_required_fields(self):
        step = WorkflowStep(
            step_id="classify",
            step_name="Intent Classification",
            step_type="preprocessing",
        )
        assert step.step_id == "classify"
        assert step.step_name == "Intent Classification"
        assert step.step_type == "preprocessing"

    def test_default_estimated_tokens_zero(self):
        step = WorkflowStep(step_id="x", step_name="X", step_type="core")
        assert step.estimated_tokens == 0

    def test_default_timeout_seconds(self):
        step = WorkflowStep(step_id="x", step_name="X", step_type="core")
        assert step.timeout_seconds == 5.0

    def test_default_enabled_true(self):
        step = WorkflowStep(step_id="x", step_name="X", step_type="core")
        assert step.enabled is True

    def test_step_types_valid(self):
        for stype in ("preprocessing", "core", "postprocessing"):
            step = WorkflowStep(step_id="x", step_name="X", step_type=stype)
            assert step.step_type == stype

    def test_equality_same_values(self):
        s1 = WorkflowStep(
            step_id="a", step_name="A", step_type="core", estimated_tokens=10
        )
        s2 = WorkflowStep(
            step_id="a", step_name="A", step_type="core", estimated_tokens=10
        )
        assert s1 == s2


# ═══════════════════════════════════════════════════════════════════════
# 3. WorkflowStepResult (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestWorkflowStepResult:
    def test_success_status(self):
        r = WorkflowStepResult(step_id="classify", status="success", tokens_used=50)
        assert r.status == "success"
        assert r.tokens_used == 50

    def test_skipped_status(self):
        r = WorkflowStepResult(step_id="x", status="skipped")
        assert r.status == "skipped"

    def test_error_status_with_message(self):
        r = WorkflowStepResult(
            step_id="x", status="error", error="Something went wrong"
        )
        assert r.status == "error"
        assert r.error == "Something went wrong"

    def test_timeout_status(self):
        r = WorkflowStepResult(step_id="x", status="timeout")
        assert r.status == "timeout"

    def test_default_tokens_and_duration(self):
        r = WorkflowStepResult(step_id="x", status="success")
        assert r.tokens_used == 0
        assert r.duration_ms == 0.0

    def test_output_dict(self):
        r = WorkflowStepResult(
            step_id="gen",
            status="success",
            output={"response": "hello"},
        )
        assert r.output == {"response": "hello"}


# ═══════════════════════════════════════════════════════════════════════
# 4. WorkflowResult (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestWorkflowResult:
    def test_creation_with_required_fields(self):
        r = WorkflowResult(workflow_id="w1", variant_type="parwa", status="success")
        assert r.workflow_id == "w1"
        assert r.variant_type == "parwa"
        assert r.status == "success"

    def test_default_steps_completed_empty(self):
        r = WorkflowResult(workflow_id="w1", variant_type="parwa", status="success")
        assert r.steps_completed == []

    def test_default_step_results_empty(self):
        r = WorkflowResult(workflow_id="w1", variant_type="parwa", status="success")
        assert r.step_results == {}

    def test_default_final_response_empty(self):
        r = WorkflowResult(workflow_id="w1", variant_type="parwa", status="success")
        assert r.final_response == ""

    def test_default_total_tokens_zero(self):
        r = WorkflowResult(workflow_id="w1", variant_type="parwa", status="success")
        assert r.total_tokens_used == 0

    def test_default_total_duration_zero(self):
        r = WorkflowResult(workflow_id="w1", variant_type="parwa", status="success")
        assert r.total_duration_ms == 0.0

    def test_default_compression_applied_false(self):
        r = WorkflowResult(workflow_id="w1", variant_type="parwa", status="success")
        assert r.context_compression_applied is False

    def test_default_health_score_one(self):
        r = WorkflowResult(workflow_id="w1", variant_type="parwa", status="success")
        assert r.context_health_score == 1.0

    def test_status_values(self):
        for s in ("success", "partial", "failed", "timeout"):
            r = WorkflowResult(workflow_id="w1", variant_type="parwa", status=s)
            assert r.status == s


# ═══════════════════════════════════════════════════════════════════════
# 5. MiniParwa Pipeline (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestMiniParwaPipeline:
    def setup_method(self):
        self.engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="mini_parwa"),
        )
        self.engine.build_graph()

    def test_three_steps(self):
        assert len(self.engine._steps) == 3

    def test_step_ids_correct(self):
        ids = [s.step_id for s in self.engine._steps]
        assert ids == ["classify", "generate", "format"]

    def test_step_names_match_definitions(self):
        for step in self.engine._steps:
            defn = WORKFLOW_STEP_DEFINITIONS[step.step_id]
            assert step.step_name == defn["step_name"]

    def test_step_order_is_correct(self):
        assert self.engine._steps[0].step_id == "classify"
        assert self.engine._steps[1].step_id == "generate"
        assert self.engine._steps[2].step_id == "format"

    @pytest.mark.asyncio
    async def test_execution_produces_result(self):
        result = await self.engine.execute("c1", "Hello world")
        assert isinstance(result, WorkflowResult)
        assert result.status == "success"
        assert len(result.steps_completed) == 3


# ═══════════════════════════════════════════════════════════════════════
# 6. Parwa Pipeline (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestParwaPipeline:
    def setup_method(self):
        self.engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="parwa"),
        )
        self.engine.build_graph()

    def test_six_steps(self):
        assert len(self.engine._steps) == 6

    def test_correct_node_names(self):
        ids = [s.step_id for s in self.engine._steps]
        expected = [
            "classify",
            "extract_signals",
            "technique_select",
            "generate",
            "quality_gate",
            "format",
        ]
        assert ids == expected

    def test_first_step_is_classify(self):
        assert self.engine._steps[0].step_id == "classify"

    def test_last_step_is_format(self):
        assert self.engine._steps[-1].step_id == "format"

    @pytest.mark.asyncio
    async def test_execution_succeeds(self):
        result = await self.engine.execute("c1", "refund my order")
        assert isinstance(result, WorkflowResult)
        assert result.status == "success"
        assert len(result.steps_completed) == 6


# ═══════════════════════════════════════════════════════════════════════
# 7. ParwaHigh Pipeline (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestParwaHighPipeline:
    def setup_method(self):
        self.engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="parwa_high"),
        )
        self.engine.build_graph()

    def test_nine_steps(self):
        assert len(self.engine._steps) == 9

    def test_correct_node_names(self):
        ids = [s.step_id for s in self.engine._steps]
        expected = [
            "classify",
            "extract_signals",
            "technique_select",
            "context_compress",
            "generate",
            "quality_gate",
            "context_health",
            "dedup",
            "format",
        ]
        assert ids == expected

    def test_includes_context_compress(self):
        ids = [s.step_id for s in self.engine._steps]
        assert "context_compress" in ids

    def test_includes_context_health_and_dedup(self):
        ids = [s.step_id for s in self.engine._steps]
        assert "context_health" in ids
        assert "dedup" in ids

    @pytest.mark.asyncio
    async def test_execution_succeeds(self):
        result = await self.engine.execute("c1", "How do I track my order?")
        assert isinstance(result, WorkflowResult)
        assert result.status == "success"
        assert len(result.steps_completed) == 9


# ═══════════════════════════════════════════════════════════════════════
# 8. BuildGraph (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestBuildGraph:
    def test_build_mini_parwa_graph(self):
        engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="mini_parwa"),
        )
        engine.build_graph()
        assert len(engine._steps) == 3

    def test_build_parwa_graph(self):
        engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="parwa"),
        )
        engine.build_graph()
        assert len(engine._steps) == 6

    def test_build_parwa_high_graph(self):
        engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="parwa_high"),
        )
        engine.build_graph()
        assert len(engine._steps) == 9

    def test_idempotent_build(self):
        engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="parwa"),
        )
        engine.build_graph()
        first_len = len(engine._steps)
        engine.build_graph()
        assert len(engine._steps) == first_len

    def test_unknown_variant_falls_to_parwa(self):
        engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="unknown_variant_xyz"),
        )
        engine.build_graph()
        assert len(engine._steps) == 6


# ═══════════════════════════════════════════════════════════════════════
# 9. WorkflowExecution (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestWorkflowExecution:
    @pytest.mark.asyncio
    async def test_end_to_end_execute(self):
        engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="parwa"),
        )
        result = await engine.execute("c1", "I need a refund")
        assert result.status == "success"
        assert result.workflow_id
        assert result.variant_type == "parwa"
        assert result.total_tokens_used > 0
        assert result.total_duration_ms >= 0

    @pytest.mark.asyncio
    async def test_empty_query(self):
        engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="mini_parwa"),
        )
        result = await engine.execute("c1", "")
        assert isinstance(result, WorkflowResult)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_returns_workflow_result_type(self):
        engine = LangGraphWorkflow()
        result = await engine.execute("c1", "test query")
        assert isinstance(result, WorkflowResult)

    @pytest.mark.asyncio
    async def test_final_response_populated(self):
        engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="parwa"),
        )
        result = await engine.execute("c1", "order status")
        assert len(result.final_response) > 0

    @pytest.mark.asyncio
    async def test_all_steps_completed(self):
        engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="parwa"),
        )
        result = await engine.execute("c1", "test")
        assert len(result.steps_completed) == 6
        assert set(result.steps_completed) == set(
            VARIANT_PIPELINE_CONFIG["parwa"]["steps"],
        )

    @pytest.mark.asyncio
    async def test_error_handling_graceful(self):
        engine = LangGraphWorkflow()
        # Force an error by making _execute_step raise
        with patch.object(
            engine,
            "_execute_step",
            new_callable=AsyncMock,
            side_effect=RuntimeError("forced error"),
        ):
            result = await engine.execute("c1", "test")
        # BC-008: should not crash, returns a valid result
        assert isinstance(result, WorkflowResult)


# ═══════════════════════════════════════════════════════════════════════
# 10. GetStep (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGetStep:
    def test_get_existing_step(self):
        engine = LangGraphWorkflow()
        engine.build_graph()
        step = engine.get_step("classify")
        assert step is not None
        assert step.step_id == "classify"

    def test_get_non_existing_step(self):
        engine = LangGraphWorkflow()
        engine.build_graph()
        step = engine.get_step("nonexistent_step_xyz")
        assert step is None

    def test_get_after_build_returns_correct_step(self):
        engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="parwa_high"),
        )
        engine.build_graph()
        step = engine.get_step("context_compress")
        assert step is not None
        assert step.step_name == "Context Compression"


# ═══════════════════════════════════════════════════════════════════════
# 11. PipelineTopology (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineTopology:
    def test_returns_dict_structure(self):
        engine = LangGraphWorkflow()
        topo = engine.get_pipeline_topology("c1")
        assert isinstance(topo, dict)
        assert "variant_type" in topo
        assert "total_steps" in topo
        assert "steps" in topo

    def test_contains_steps_list(self):
        engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="parwa"),
        )
        topo = engine.get_pipeline_topology("c1")
        assert len(topo["steps"]) == 6
        for step in topo["steps"]:
            assert "step_id" in step
            assert "step_type" in step
            assert "next" in step
            assert "prev" in step

    def test_variant_differences(self):
        mini_engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="mini_parwa"),
        )
        high_engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="parwa_high"),
        )
        mini_topo = mini_engine.get_pipeline_topology("c1")
        high_topo = high_engine.get_pipeline_topology("c1")
        assert mini_topo["total_steps"] == 3
        assert high_topo["total_steps"] == 9


# ═══════════════════════════════════════════════════════════════════════
# 12. WorkflowError (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestWorkflowError:
    def test_default_message(self):
        err = WorkflowError()
        assert err.message == "Workflow execution failed"
        assert err.workflow_id == ""
        assert err.step_id == ""

    def test_inheritance_from_exception(self):
        err = WorkflowError("test error")
        assert isinstance(err, Exception)

    def test_custom_fields(self):
        err = WorkflowError(
            message="Pipeline failed at generate",
            workflow_id="wf-123",
            step_id="generate",
        )
        assert err.message == "Pipeline failed at generate"
        assert err.workflow_id == "wf-123"
        assert err.step_id == "generate"
        assert str(err) == "Pipeline failed at generate"


# ═══════════════════════════════════════════════════════════════════════
# 13. WORKFLOW_STEP_DEFINITIONS constants (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestStepDefinitions:
    def test_nine_steps_defined(self):
        assert len(WORKFLOW_STEP_DEFINITIONS) == 9

    def test_all_have_required_keys(self):
        required = {
            "step_id",
            "step_name",
            "step_type",
            "estimated_tokens",
            "timeout_seconds",
        }
        for step_id, defn in WORKFLOW_STEP_DEFINITIONS.items():
            assert required.issubset(defn.keys()), f"Missing keys in {step_id}"

    def test_variant_pipeline_configs(self):
        assert "mini_parwa" in VARIANT_PIPELINE_CONFIG
        assert "parwa" in VARIANT_PIPELINE_CONFIG
        assert "parwa_high" in VARIANT_PIPELINE_CONFIG
        assert VARIANT_PIPELINE_CONFIG["mini_parwa"]["steps"] == [
            "classify",
            "generate",
            "format",
        ]
        assert len(VARIANT_PIPELINE_CONFIG["parwa_high"]["steps"]) == 9


# ═══════════════════════════════════════════════════════════════════════
# 14. Engine init and helpers (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestEngineInit:
    def test_default_config_used_when_none(self):
        engine = LangGraphWorkflow()
        assert engine.get_config().variant_type == "parwa"

    def test_custom_config_passed(self):
        cfg = WorkflowConfig(variant_type="parwa_high", company_id="c1")
        engine = LangGraphWorkflow(config=cfg)
        assert engine.get_config().variant_type == "parwa_high"
        assert engine.get_config().company_id == "c1"

    def test_reset_clears_state(self):
        engine = LangGraphWorkflow()
        engine.build_graph()
        assert len(engine._steps) > 0
        engine.reset()
        assert engine._steps == []
        assert engine._graph is None

    def test_lazy_build_on_execute(self):
        engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="mini_parwa"),
        )
        assert len(engine._steps) == 0  # not yet built
        # execute should trigger lazy build
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            engine.execute("c1", "test"),
        )
        assert len(engine._steps) == 3


# ═══════════════════════════════════════════════════════════════════════
# 15. Simulation Step Outputs (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestSimulationOutputs:
    @pytest.mark.asyncio
    async def test_classify_step_output(self):
        engine = LangGraphWorkflow()
        result = await engine.execute("c1", "I want a refund")
        classify_result = result.step_results.get("classify")
        assert classify_result is not None
        assert classify_result.status == "success"
        assert classify_result.output.get("intent") == "refund_request"

    @pytest.mark.asyncio
    async def test_generate_step_output(self):
        engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="parwa"),
        )
        result = await engine.execute("c1", "Hello")
        gen_result = result.step_results.get("generate")
        assert gen_result is not None
        assert gen_result.status == "success"
        assert "response" in gen_result.output

    @pytest.mark.asyncio
    async def test_quality_gate_passes(self):
        engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="parwa"),
        )
        result = await engine.execute("c1", "test")
        qg_result = result.step_results.get("quality_gate")
        assert qg_result is not None
        assert qg_result.output.get("passed") is True

    @pytest.mark.asyncio
    async def test_parwa_high_compression_step(self):
        engine = LangGraphWorkflow(
            WorkflowConfig(variant_type="parwa_high"),
        )
        result = await engine.execute("c1", "test query")
        comp_result = result.step_results.get("context_compress")
        assert comp_result is not None
        assert comp_result.output.get("compressed") is True
        assert result.context_compression_applied is True
