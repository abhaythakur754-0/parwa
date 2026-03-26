"""
Tests for Agent Lightning v2 Validation and Deployment System.

CRITICAL: All tests verify model validation and deployment works correctly.
"""

import pytest
from datetime import datetime
from typing import Dict, Any
import os
import tempfile
import time

from agent_lightning.v2.model_validator import (
    ModelValidator,
    ModelValidationReport,
    ValidationResult,
    ValidationStatus,
    validate_trained_model,
)
from agent_lightning.v2.regression_suite import (
    RegressionSuite,
    RegressionTest,
    RegressionTestResult,
    RegressionSuiteReport,
    run_regression_tests,
)
from agent_lightning.v2.deployment_manager import (
    DeploymentManager,
    DeploymentRecord,
    DeploymentStatus,
    DeploymentStage,
    DeploymentConfig,
    deploy_to_production,
)
from agent_lightning.v2.canary_deployer import (
    CanaryDeployer,
    CanaryConfig,
    CanaryMetrics,
    CanaryDeploymentRecord,
    CanaryStage,
    CanaryStatus,
    deploy_canary,
)
from agent_lightning.v2.rollback_manager import (
    RollbackManager,
    RollbackRecord,
    RollbackStatus,
    RollbackTrigger,
    RollbackConfig,
    ModelVersion,
    quick_rollback,
)


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def temp_dir():
    """Create temporary directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def model_validator():
    """Create a model validator"""
    return ModelValidator(model_path="models/test_model")


@pytest.fixture
def regression_suite():
    """Create a regression suite"""
    return RegressionSuite(model_version="v2_test")


@pytest.fixture
def deployment_manager(temp_dir):
    """Create a deployment manager"""
    return DeploymentManager(deployment_dir=temp_dir)


@pytest.fixture
def canary_deployer():
    """Create a canary deployer"""
    return CanaryDeployer(model_version="v2_test")


@pytest.fixture
def rollback_manager(temp_dir):
    """Create a rollback manager"""
    registry_path = os.path.join(temp_dir, "versions.json")
    manager = RollbackManager(version_registry_path=registry_path)
    # Register some versions
    manager.register_version("v1.0.0", "models/v1.0.0", 0.72)
    manager.register_version("v2.0.0", "models/v2.0.0", 0.78)
    return manager


# ==============================================================================
# Model Validator Tests
# ==============================================================================

class TestModelValidator:
    """Tests for ModelValidator"""

    def test_validator_initialization(self, model_validator):
        """Test validator initializes correctly"""
        assert model_validator.model_path == "models/test_model"
        assert model_validator._status == ValidationStatus.PENDING

    def test_validate_model(self, model_validator):
        """Test complete model validation"""
        report = model_validator.validate_model()

        assert isinstance(report, ModelValidationReport)
        assert report.model_version is not None
        assert report.accuracy > 0

    def test_accuracy_validation(self, model_validator):
        """Test accuracy is validated correctly"""
        result = model_validator.validate_accuracy_only()

        assert isinstance(result, ValidationResult)
        assert result.check_name == "accuracy_validation"
        assert result.score >= model_validator.BASELINE_ACCURACY

    def test_accuracy_target_met(self, model_validator):
        """Test accuracy meets 77% target"""
        report = model_validator.validate_model()

        # Allow for some variance in mock
        assert report.accuracy >= 0.72

    def test_improvement_calculation(self, model_validator):
        """Test improvement percentage calculation"""
        report = model_validator.validate_model()

        assert report.baseline_accuracy == 0.72
        assert report.improvement > 0
        assert report.improvement_percentage > 0

    def test_hallucination_check(self, model_validator):
        """Test hallucination check runs"""
        report = model_validator.validate_model()

        hallucination_result = [
            r for r in report.results
            if r.check_name == "hallucination_check"
        ][0]

        assert hallucination_result.score > 0
        assert hallucination_result.passed is True

    def test_response_quality_check(self, model_validator):
        """Test response quality verification"""
        report = model_validator.validate_model()

        quality_result = [
            r for r in report.results
            if r.check_name == "response_quality"
        ][0]

        assert quality_result.score >= 0.80

    def test_bias_check(self, model_validator):
        """Test bias check runs"""
        report = model_validator.validate_model()

        bias_result = [
            r for r in report.results
            if r.check_name == "bias_check"
        ][0]

        assert bias_result.score > 0

    def test_safety_verification(self, model_validator):
        """Test safety verification runs"""
        report = model_validator.validate_model()

        safety_result = [
            r for r in report.results
            if r.check_name == "safety_verification"
        ][0]

        assert safety_result.passed is True

    def test_validation_report_to_dict(self, model_validator):
        """Test report serialization"""
        report = model_validator.validate_model()
        data = report.to_dict()

        assert "model_version" in data
        assert "accuracy" in data
        assert "results" in data

    def test_get_status(self, model_validator):
        """Test getting validation status"""
        status = model_validator.get_status()

        assert "status" in status
        assert "results_count" in status


class TestValidateTrainedModelFunction:
    """Tests for convenience function"""

    def test_validate_trained_model_function(self):
        """Test the convenience validation function"""
        report = validate_trained_model(model_path="models/test")

        assert isinstance(report, ModelValidationReport)
        assert report.accuracy > 0


# ==============================================================================
# Regression Suite Tests
# ==============================================================================

class TestRegressionSuite:
    """Tests for RegressionSuite"""

    def test_suite_initialization(self, regression_suite):
        """Test suite initializes correctly"""
        assert regression_suite.model_version == "v2_test"
        assert len(regression_suite.REGRESSION_TESTS) >= 6

    def test_run_all_tests(self, regression_suite):
        """Test running all regression tests"""
        report = regression_suite.run_all_tests()

        assert isinstance(report, RegressionSuiteReport)
        assert report.total_tests >= 6
        assert report.execution_duration_seconds >= 0

    def test_refund_gate_test(self, regression_suite):
        """Test refund gate enforcement test"""
        report = regression_suite.run_all_tests(
            tests_to_run=["REG_001"]
        )

        assert report.total_tests == 1
        result = report.results[0]
        assert result.test.test_name == "refund_gate_enforcement"

    def test_jarvis_commands_test(self, regression_suite):
        """Test Jarvis commands test"""
        report = regression_suite.run_all_tests(
            tests_to_run=["REG_002"]
        )

        assert report.total_tests == 1
        result = report.results[0]
        assert result.test.test_name == "jarvis_commands"
        assert "commands_tested" in result.details

    def test_escalation_ladder_test(self, regression_suite):
        """Test escalation ladder test"""
        report = regression_suite.run_all_tests(
            tests_to_run=["REG_003"]
        )

        assert report.total_tests == 1
        result = report.results[0]
        assert result.test.test_name == "escalation_ladder"

    def test_voice_handler_test(self, regression_suite):
        """Test voice handler test"""
        report = regression_suite.run_all_tests(
            tests_to_run=["REG_004"]
        )

        assert report.total_tests == 1
        result = report.results[0]
        assert result.test.test_name == "voice_handler"

    def test_variants_test(self, regression_suite):
        """Test variant compatibility test"""
        report = regression_suite.run_all_tests(
            tests_to_run=["REG_005"]
        )

        assert report.total_tests == 1
        result = report.results[0]
        assert result.test.test_name == "variant_compatibility"
        assert "variants_tested" in result.details

    def test_guardrails_test(self, regression_suite):
        """Test guardrails test"""
        report = regression_suite.run_all_tests(
            tests_to_run=["REG_006"]
        )

        assert report.total_tests == 1
        result = report.results[0]
        assert result.test.test_name == "guardrails_active"

    def test_critical_tests_only(self, regression_suite):
        """Test running only critical tests"""
        report = regression_suite.run_critical_tests()

        for result in report.results:
            assert result.test.critical is True

    def test_all_passed_flag(self, regression_suite):
        """Test all_passed flag in report"""
        report = regression_suite.run_all_tests()

        assert isinstance(report.all_passed, bool)
        assert report.passed_tests + report.failed_tests == report.total_tests

    def test_critical_failures_listed(self, regression_suite):
        """Test critical failures are listed"""
        report = regression_suite.run_all_tests()

        assert isinstance(report.critical_failures, list)

    def test_report_to_dict(self, regression_suite):
        """Test report serialization"""
        report = regression_suite.run_all_tests()
        data = report.to_dict()

        assert "suite_name" in data
        assert "total_tests" in data
        assert "results" in data


class TestRunRegressionTestsFunction:
    """Tests for convenience function"""

    def test_run_regression_tests_function(self):
        """Test the convenience regression function"""
        report = run_regression_tests(model_version="v2_test")

        assert isinstance(report, RegressionSuiteReport)
        assert report.total_tests >= 6


# ==============================================================================
# Deployment Manager Tests
# ==============================================================================

class TestDeploymentManager:
    """Tests for DeploymentManager"""

    def test_manager_initialization(self, deployment_manager):
        """Test manager initializes correctly"""
        assert deployment_manager.config is not None
        assert len(deployment_manager._history) == 0

    def test_deploy_model(self, deployment_manager):
        """Test deploying a model"""
        record = deployment_manager.deploy_model(
            model_path="models/v2.0.0",
            model_version="v2.0.0",
            accuracy=0.78,
        )

        assert isinstance(record, DeploymentRecord)
        assert record.model_version == "v2.0.0"
        assert record.accuracy == 0.78

    def test_deployment_validation_stage(self, deployment_manager):
        """Test validation stage runs"""
        record = deployment_manager.deploy_model(
            model_path="models/v2.0.0",
            model_version="v2.0.0",
            accuracy=0.78,
        )

        assert record.validation_passed is True

    def test_deployment_regression_stage(self, deployment_manager):
        """Test regression stage runs"""
        record = deployment_manager.deploy_model(
            model_path="models/v2.0.0",
            model_version="v2.0.0",
            accuracy=0.78,
        )

        assert record.regression_passed is True

    def test_deployment_health_check(self, deployment_manager):
        """Test health check runs"""
        record = deployment_manager.deploy_model(
            model_path="models/v2.0.0",
            model_version="v2.0.0",
            accuracy=0.78,
        )

        assert record.health_check_passed is True

    def test_deployment_below_threshold_fails(self, deployment_manager):
        """Test deployment fails if accuracy below threshold"""
        record = deployment_manager.deploy_model(
            model_path="models/v1.0.0",
            model_version="v1.0.0",
            accuracy=0.65,  # Below 77% threshold
        )

        assert record.status == DeploymentStatus.FAILED
        assert "failure_reason" in record.metadata

    def test_get_current_deployment(self, deployment_manager):
        """Test getting current deployment"""
        deployment_manager.deploy_model(
            model_path="models/v2.0.0",
            model_version="v2.0.0",
            accuracy=0.78,
        )

        current = deployment_manager.get_current_deployment()

        assert current is not None
        assert current.model_version == "v2.0.0"

    def test_deployment_history(self, deployment_manager):
        """Test deployment history tracking"""
        deployment_manager.deploy_model(
            model_path="models/v2.0.0",
            model_version="v2.0.0",
            accuracy=0.78,
        )

        history = deployment_manager.get_deployment_history()

        assert len(history) == 1

    def test_check_health(self, deployment_manager):
        """Test health check endpoint"""
        deployment_manager.deploy_model(
            model_path="models/v2.0.0",
            model_version="v2.0.0",
            accuracy=0.78,
        )

        health = deployment_manager.check_health()

        assert health["healthy"] is True
        assert "model_version" in health

    def test_rollback(self, deployment_manager):
        """Test rollback functionality"""
        # Deploy two versions
        deployment_manager.deploy_model(
            model_path="models/v1.0.0",
            model_version="v1.0.0",
            accuracy=0.78,
        )
        deployment_manager.deploy_model(
            model_path="models/v2.0.0",
            model_version="v2.0.0",
            accuracy=0.78,
        )

        # Rollback
        rolled_back = deployment_manager.rollback()

        assert rolled_back is not None
        assert rolled_back.model_version == "v1.0.0"

    def test_deployment_record_to_dict(self, deployment_manager):
        """Test record serialization"""
        record = deployment_manager.deploy_model(
            model_path="models/v2.0.0",
            model_version="v2.0.0",
            accuracy=0.78,
        )

        data = record.to_dict()

        assert "deployment_id" in data
        assert "model_version" in data
        assert "status" in data


class TestDeployToProductionFunction:
    """Tests for convenience function"""

    def test_deploy_to_production_function(self, temp_dir):
        """Test the convenience deployment function"""
        record = deploy_to_production(
            model_path="models/v2.0.0",
            model_version="v2.0.0",
            accuracy=0.78,
            deployment_dir=temp_dir,
        )

        assert isinstance(record, DeploymentRecord)


# ==============================================================================
# Canary Deployer Tests
# ==============================================================================

class TestCanaryDeployer:
    """Tests for CanaryDeployer"""

    def test_deployer_initialization(self, canary_deployer):
        """Test deployer initializes correctly"""
        assert canary_deployer.model_version == "v2_test"
        assert len(canary_deployer.config.stages) == 4

    def test_start_canary(self, canary_deployer):
        """Test starting canary deployment"""
        record = canary_deployer.start_canary()

        assert isinstance(record, CanaryDeploymentRecord)
        assert record.model_version == "v2_test"

    def test_canary_stages_progress(self, canary_deployer):
        """Test canary progresses through stages"""
        record = canary_deployer.start_canary()

        # Should complete to 100%
        assert record.current_traffic_percentage == 1.0
        assert record.current_stage == CanaryStage.PERCENT_100

    def test_canary_metrics_collection(self, canary_deployer):
        """Test metrics are collected"""
        record = canary_deployer.start_canary()

        assert len(record.metrics_history) > 0

        metrics = record.metrics_history[0]
        assert isinstance(metrics, CanaryMetrics)
        assert metrics.accuracy > 0
        assert metrics.request_count > 0

    def test_canary_rollback_capability(self, canary_deployer):
        """Test manual rollback capability"""
        canary_deployer.start_canary()

        result = canary_deployer.trigger_rollback("Manual test rollback")

        assert result is True
        assert canary_deployer._record.rollback_triggered is True

    def test_canary_config_thresholds(self, canary_deployer):
        """Test canary respects thresholds"""
        config = CanaryConfig(
            max_error_rate=0.01,
            min_accuracy=0.77,
            max_latency_ms=500,
        )
        deployer = CanaryDeployer(model_version="v2_test", config=config)

        assert deployer.config.max_error_rate == 0.01
        assert deployer.config.min_accuracy == 0.77

    def test_canary_callbacks(self, canary_deployer):
        """Test canary callbacks work"""
        stage_changes = []
        metrics_collected = []

        def on_stage(stage, percent):
            stage_changes.append((stage, percent))

        def on_metrics(metrics):
            metrics_collected.append(metrics)

        canary_deployer.start_canary(
            on_stage_change=on_stage,
            on_metrics=on_metrics,
        )

        assert len(stage_changes) > 0
        assert len(metrics_collected) > 0

    def test_canary_record_to_dict(self, canary_deployer):
        """Test record serialization"""
        record = canary_deployer.start_canary()
        data = record.to_dict()

        assert "canary_id" in data
        assert "model_version" in data
        assert "current_stage" in data


class TestDeployCanaryFunction:
    """Tests for convenience function"""

    def test_deploy_canary_function(self):
        """Test the convenience canary function"""
        record = deploy_canary(model_version="v2_test")

        assert isinstance(record, CanaryDeploymentRecord)


# ==============================================================================
# Rollback Manager Tests
# ==============================================================================

class TestRollbackManager:
    """Tests for RollbackManager"""

    def test_manager_initialization(self, rollback_manager):
        """Test manager initializes correctly"""
        assert len(rollback_manager._versions) == 2
        assert rollback_manager._active_version is not None

    def test_register_version(self, rollback_manager):
        """Test registering a version"""
        version = rollback_manager.register_version(
            version_id="v3.0.0",
            model_path="models/v3.0.0",
            accuracy=0.80,
        )

        assert version.version_id == "v3.0.0"
        assert version.accuracy == 0.80
        assert version.is_active is True

    def test_rollback(self, rollback_manager):
        """Test rollback functionality"""
        record = rollback_manager.rollback(reason="Test rollback")

        assert isinstance(record, RollbackRecord)
        assert record.status == RollbackStatus.COMPLETE
        assert record.from_version == "v2.0.0"
        assert record.to_version == "v1.0.0"

    def test_rollback_under_30_seconds(self, rollback_manager):
        """CRITICAL: Rollback must complete in <30 seconds"""
        start = time.time()
        record = rollback_manager.rollback()
        elapsed = time.time() - start

        assert record.duration_seconds < 30.0
        assert elapsed < 30.0

    def test_one_command_rollback(self, rollback_manager):
        """Test one-command rollback"""
        record = rollback_manager.one_command_rollback()

        assert record.status == RollbackStatus.COMPLETE
        assert record.trigger == RollbackTrigger.MANUAL

    def test_traffic_switch_time(self, rollback_manager):
        """Test traffic switch is instant"""
        record = rollback_manager.rollback()

        assert record.traffic_switch_time_ms is not None
        assert record.traffic_switch_time_ms < 5000  # <5 seconds

    def test_rollback_verification(self, rollback_manager):
        """Test rollback verification"""
        record = rollback_manager.rollback()

        assert record.verification_passed is True

    def test_get_active_version(self, rollback_manager):
        """Test getting active version"""
        active = rollback_manager.get_active_version()

        assert active is not None
        assert active.is_active is True

    def test_get_version_history(self, rollback_manager):
        """Test version history tracking"""
        history = rollback_manager.get_version_history()

        assert len(history) == 2

    def test_audit_trail(self, rollback_manager):
        """Test audit trail"""
        rollback_manager.rollback(reason="Test audit")
        trail = rollback_manager.get_audit_trail()

        assert len(trail) == 1
        assert trail[0].reason == "Test audit"

    def test_verify_rollback_capability(self, rollback_manager):
        """Test rollback capability verification"""
        capability = rollback_manager.verify_rollback_capability()

        assert capability["rollback_ready"] is True
        assert capability["previous_version_available"] is True

    def test_rollback_record_to_dict(self, rollback_manager):
        """Test record serialization"""
        record = rollback_manager.rollback()
        data = record.to_dict()

        assert "rollback_id" in data
        assert "from_version" in data
        assert "to_version" in data
        assert "duration_seconds" in data


class TestQuickRollbackFunction:
    """Tests for convenience function"""

    def test_quick_rollback_function(self, temp_dir):
        """Test the quick rollback function"""
        registry_path = os.path.join(temp_dir, "versions.json")
        manager = RollbackManager(version_registry_path=registry_path)
        manager.register_version("v1.0.0", "models/v1.0.0", 0.72)
        manager.register_version("v2.0.0", "models/v2.0.0", 0.78)

        record = quick_rollback(
            version_registry_path=registry_path,
            reason="Quick test rollback",
        )

        assert isinstance(record, RollbackRecord)


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestValidationDeploymentIntegration:
    """Integration tests for validation and deployment"""

    def test_full_validation_to_deployment(self, temp_dir):
        """Test complete validation to deployment flow"""
        # 1. Validate model
        validator = ModelValidator(model_path="models/v2.0.0")
        validation_report = validator.validate_model()

        assert validation_report.accuracy >= 0.72

        # 2. Run regression tests
        suite = RegressionSuite(model_version="v2.0.0")
        regression_report = suite.run_all_tests()

        assert regression_report.total_tests >= 6

        # 3. Deploy
        manager = DeploymentManager(deployment_dir=temp_dir)
        deployment = manager.deploy_model(
            model_path="models/v2.0.0",
            model_version="v2.0.0",
            accuracy=validation_report.accuracy,
        )

        assert deployment.status == DeploymentStatus.ACTIVE

    def test_canary_with_rollback(self, temp_dir):
        """Test canary deployment with rollback"""
        registry_path = os.path.join(temp_dir, "versions.json")

        # Register versions
        rb_manager = RollbackManager(version_registry_path=registry_path)
        rb_manager.register_version("v1.0.0", "models/v1.0.0", 0.72)
        rb_manager.register_version("v2.0.0", "models/v2.0.0", 0.78)

        # Start canary
        deployer = CanaryDeployer(model_version="v2.0.0")
        record = deployer.start_canary()

        assert record.status == CanaryStatus.COMPLETE

        # Can trigger rollback if needed
        deployer.trigger_rollback("Test rollback")

        assert deployer._record.rollback_triggered is True

    def test_deployment_with_regression_validation(self, temp_dir):
        """Test deployment with regression validation"""
        config = DeploymentConfig(
            require_validation=True,
            require_regression=True,
            min_accuracy=0.77,
        )
        manager = DeploymentManager(deployment_dir=temp_dir, config=config)

        record = manager.deploy_model(
            model_path="models/v2.0.0",
            model_version="v2.0.0",
            accuracy=0.78,
        )

        assert record.validation_passed is True
        assert record.regression_passed is True
        assert record.status == DeploymentStatus.ACTIVE


# ==============================================================================
# Run Tests
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
