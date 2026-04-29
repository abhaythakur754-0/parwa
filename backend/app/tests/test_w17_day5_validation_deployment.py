"""
Tests for Week 17 Day 5 — F-104 (Model Validation) and F-105 (Auto-rollback Deployment)

Tests:
- ModelValidationService: Evaluation suite, quality gates
- ModelDeploymentService: Canary releases, auto-rollback
- Deployment strategies: Canary, Blue-green, Rolling
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4

# ══════════════════════════════════════════════════════════════════════════
# F-104: Model Validation Service Tests
# ══════════════════════════════════════════════════════════════════════════


class TestModelValidationService:
    """Tests for ModelValidationService (F-104)."""

    @pytest.fixture
    def mock_db(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.model_validation_service import ModelValidationService

        return ModelValidationService(mock_db)

    def test_create_validation_run(self, service):
        """Test creating a validation run."""
        result = service.create_validation_run(
            company_id=str(uuid4()),
            training_run_id=str(uuid4()),
            model_path="/models/test/model.pkl",
        )
        assert result["status"] == "pending"
        assert "id" in result

    def test_run_validation_success(self, service):
        """Test successful validation run."""
        result = service.run_validation(
            company_id=str(uuid4()),
            training_run_id=str(uuid4()),
            model_path="/models/test/model.pkl",
        )
        assert result["status"] in ["passed", "failed", "error"]
        assert "metrics" in result
        assert "quality_gates" in result

    def test_quality_gates_check_pass(self, service):
        """Test quality gates passing."""
        metrics = {
            "accuracy": 0.90,
            "f1_score": 0.85,
            "latency_p95_ms": 500,
            "hallucination_rate": 0.02,
            "safety_score": 0.98,
        }
        gates = service._check_quality_gates(metrics)
        assert gates["accuracy"]["passed"]
        assert gates["f1_score"]["passed"]

    def test_quality_gates_check_fail(self, service):
        """Test quality gates failing."""
        metrics = {
            "accuracy": 0.50,
            "f1_score": 0.40,
            "latency_p95_ms": 5000,
            "hallucination_rate": 0.10,
            "safety_score": 0.80,
        }
        gates = service._check_quality_gates(metrics)
        assert gates["accuracy"]["passed"] is False
        assert gates["latency_p95"]["passed"] is False

    def test_is_model_deployable(self, service):
        """Test deployability check."""
        passed_result = {
            "status": "passed",
            "quality_gates": {
                "accuracy": {"passed": True},
                "f1_score": {"passed": True},
            },
        }
        assert service.is_model_deployable(passed_result)

        failed_result = {
            "status": "failed",
            "quality_gates": {"accuracy": {"passed": False}},
        }
        assert service.is_model_deployable(failed_result) is False

    def test_regression_tests(self, service):
        """Test regression test suite."""
        result = service.run_regression_tests(
            company_id=str(uuid4()),
            model_path="/models/test/model.pkl",
        )
        assert "total_tests" in result
        assert "passed" in result
        assert "pass_rate" in result


# ══════════════════════════════════════════════════════════════════════════
# F-105: Model Deployment Service Tests
# ══════════════════════════════════════════════════════════════════════════


class TestModelDeploymentService:
    """Tests for ModelDeploymentService (F-105)."""

    @pytest.fixture
    def mock_db(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.model_deployment_service import ModelDeploymentService

        return ModelDeploymentService(mock_db)

    @pytest.fixture
    def deployment(self, service):
        return service.create_deployment(
            company_id=str(uuid4()),
            agent_id=str(uuid4()),
            model_path="/models/new/model.pkl",
            validation_id=str(uuid4()),
            baseline_model_path="/models/baseline/model.pkl",
        )

    def test_create_deployment(self, service):
        """Test creating a deployment."""
        result = service.create_deployment(
            company_id=str(uuid4()),
            agent_id=str(uuid4()),
            model_path="/models/test/model.pkl",
            validation_id=str(uuid4()),
        )
        assert result["status"] == "pending"
        assert result["strategy"] == "canary"

    def test_start_canary_deployment(self, service, deployment):
        """Test starting canary deployment."""
        result = service.start_deployment(deployment, canary_percentage=5)
        assert result["status"] == "canary"
        assert result["current_percentage"] == 5

    def test_advance_canary(self, service, deployment):
        """Test advancing canary rollout."""
        deployment = service.start_deployment(deployment, canary_percentage=5)
        result = service.advance_canary(deployment, increment=10)
        assert result["current_percentage"] == 15

    def test_advance_canary_to_completion(self, service, deployment):
        """Test advancing canary to 100%."""
        deployment = service.start_deployment(deployment, canary_percentage=50)
        result = service.advance_canary(deployment, increment=60)
        assert result["status"] == "active"
        assert result["current_percentage"] == 100

    def test_check_canary_health(self, service, deployment):
        """Test canary health check."""
        deployment = service.start_deployment(deployment, canary_percentage=5)
        health = service.check_canary_health(deployment)
        assert "healthy" in health
        assert "metrics" in health

    def test_trigger_rollback(self, service, deployment):
        """Test manual rollback."""
        deployment = service.start_deployment(deployment, canary_percentage=10)
        result = service.trigger_rollback(
            deployment=deployment,
            reason="Test rollback",
            trigger_type="manual",
        )
        assert result["status"] == "rolled_back"

    def test_auto_rollback_on_high_error_rate(self, service, deployment):
        """Test auto-rollback on high error rate."""
        deployment = service.start_deployment(deployment, canary_percentage=5)

        with patch.object(service, "_collect_deployment_metrics") as mock_metrics:
            mock_metrics.return_value = {
                "error_rate": 0.10,
                "latency_p95_ms": 500,
            }
            result = service.check_and_auto_rollback(deployment)

        assert result["action"] == "rollback"

    def test_no_rollback_when_healthy(self, service, deployment):
        """Test no rollback when deployment is healthy."""
        deployment = service.start_deployment(deployment, canary_percentage=5)

        with patch.object(service, "_collect_deployment_metrics") as mock_metrics:
            mock_metrics.return_value = {
                "error_rate": 0.01,
                "latency_p95_ms": 500,
            }
            result = service.check_and_auto_rollback(deployment)

        assert result["action"] == "continue"

    def test_pause_and_resume_deployment(self, service, deployment):
        """Test pausing and resuming deployment."""
        deployment = service.start_deployment(deployment, canary_percentage=5)

        paused = service.pause_deployment(deployment)
        assert paused["status"] == "paused"

        resumed = service.resume_deployment(paused)
        assert resumed["status"] == "rolling_out"


# ══════════════════════════════════════════════════════════════════════════
# Integration Tests
# ══════════════════════════════════════════════════════════════════════════


class TestValidationDeploymentIntegration:
    """Integration tests for validation and deployment pipeline."""

    def test_full_pipeline_success(self):
        """Test successful validation to deployment pipeline."""
        from app.services.model_validation_service import ModelValidationService
        from app.services.model_deployment_service import ModelDeploymentService

        mock_db = Mock()
        validation_service = ModelValidationService(mock_db)
        deployment_service = ModelDeploymentService(mock_db)

        # Run validation
        validation = validation_service.run_validation(
            company_id=str(uuid4()),
            training_run_id=str(uuid4()),
            model_path="/models/new/model.pkl",
        )

        # Check deployable
        is_deployable = validation_service.is_model_deployable(validation)

        if is_deployable:
            deployment = deployment_service.create_deployment(
                company_id=str(uuid4()),
                agent_id=str(uuid4()),
                model_path="/models/new/model.pkl",
                validation_id=validation.get("id"),
            )
            assert deployment["status"] == "pending"

    def test_validation_failure_blocks_deployment(self):
        """Test that failed validation blocks deployment."""
        from app.services.model_validation_service import ModelValidationService

        service = ModelValidationService(Mock())

        failed_validation = {
            "status": "failed",
            "quality_gates": {
                "accuracy": {"passed": False},
            },
        }

        assert service.is_model_deployable(failed_validation) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
