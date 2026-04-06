"""Tests for Technique Celery Tasks (DEP-05).

Covers: ExecuteTechniqueTask, LogTechniqueExecutionTask,
AggregateTechniqueMetricsTask, UpdateTechniqueVersionTask.
"""

import pytest

from backend.app.tasks.technique_tasks import (
    ExecuteTechniqueTask,
    LogTechniqueExecutionTask,
    AggregateTechniqueMetricsTask,
    UpdateTechniqueVersionTask,
    execute_technique,
    log_technique_execution,
    aggregate_technique_metrics,
    update_technique_version,
)


class TestExecuteTechniqueTask:
    def test_task_name(self):
        assert execute_technique.name == "technique.execute"

    def test_task_queue(self):
        assert execute_technique.queue == "ai"

    def test_returns_dict_on_success(self):
        task = ExecuteTechniqueTask()
        result = task.run(
            "company-123",
            "chain_of_thought",
            {"query_complexity": 0.8},
        )
        assert isinstance(result, dict)
        assert "technique_id" in result

    def test_return_has_status(self):
        task = ExecuteTechniqueTask()
        result = task.run("company-123", "cot", {})
        assert "status" in result

    def test_return_has_latency(self):
        task = ExecuteTechniqueTask()
        result = task.run("company-123", "cot", {})
        assert "latency_ms" in result
        assert result["latency_ms"] >= 0

    def test_return_has_tokens_used(self):
        task = ExecuteTechniqueTask()
        result = task.run("company-123", "cot", {})
        assert "tokens_used" in result

    def test_accepts_conversation_id(self):
        task = ExecuteTechniqueTask()
        result = task.run(
            "company-123", "cot", {},
            conversation_id="conv-1",
        )
        assert isinstance(result, dict)

    def test_accepts_ticket_id(self):
        task = ExecuteTechniqueTask()
        result = task.run(
            "company-123", "cot", {},
            ticket_id="ticket-1",
        )
        assert isinstance(result, dict)

    def test_accepts_model_tier(self):
        task = ExecuteTechniqueTask()
        result = task.run(
            "company-123", "cot", {},
            model_tier="heavy",
        )
        assert isinstance(result, dict)

    def test_stub_status(self):
        task = ExecuteTechniqueTask()
        result = task.run("company-123", "cot", {})
        assert result["status"] == "stub"

    def test_is_instance_of_parwa_base_task(self):
        assert isinstance(execute_technique, ExecuteTechniqueTask)

    def test_max_retries(self):
        assert execute_technique.max_retries == 2


class TestLogTechniqueExecutionTask:
    def test_task_name(self):
        assert log_technique_execution.name == "technique.log_execution"

    def test_task_queue(self):
        assert log_technique_execution.queue == "analytics"

    def test_returns_true_on_success(self):
        task = LogTechniqueExecutionTask()
        result = task.run(
            "company-123",
            {"technique_id": "cot", "tokens_overhead": 350, "latency_ms": 200},
        )
        assert result is True

    def test_accepts_execution_data(self):
        task = LogTechniqueExecutionTask()
        result = task.run(
            "company-123",
            {
                "technique_id": "uot",
                "tokens_overhead": 1400,
                "latency_ms": 8000,
                "result_status": "success",
            },
        )
        assert result is True

    def test_max_retries(self):
        assert log_technique_execution.max_retries == 3


class TestAggregateTechniqueMetricsTask:
    def test_task_name(self):
        assert aggregate_technique_metrics.name == "technique.aggregate_metrics"

    def test_task_queue(self):
        assert aggregate_technique_metrics.queue == "analytics"

    def test_returns_dict_on_success(self):
        task = AggregateTechniqueMetricsTask()
        result = task.run("company-123")
        assert isinstance(result, dict)
        assert result["company_id"] == "company-123"

    def test_return_has_window_minutes(self):
        task = AggregateTechniqueMetricsTask()
        result = task.run("company-123", window_minutes=10)
        assert result["window_minutes"] == 10

    def test_return_has_status(self):
        task = AggregateTechniqueMetricsTask()
        result = task.run("company-123")
        assert "status" in result

    def test_default_window_is_5(self):
        task = AggregateTechniqueMetricsTask()
        result = task.run("company-123")
        assert result["window_minutes"] == 5


class TestUpdateTechniqueVersionTask:
    def test_task_name(self):
        assert update_technique_version.name == "technique.update_version_metrics"

    def test_task_queue(self):
        assert update_technique_version.queue == "analytics"

    def test_returns_dict_on_success(self):
        task = UpdateTechniqueVersionTask()
        result = task.run("company-123", "chain_of_thought", "v1")
        assert isinstance(result, dict)

    def test_return_has_technique_id(self):
        task = UpdateTechniqueVersionTask()
        result = task.run("company-123", "cot", "v1")
        assert result["technique_id"] == "cot"

    def test_return_has_version(self):
        task = UpdateTechniqueVersionTask()
        result = task.run("company-123", "cot", "v2")
        assert result["version"] == "v2"

    def test_return_has_status(self):
        task = UpdateTechniqueVersionTask()
        result = task.run("company-123", "cot", "v1")
        assert "status" in result
