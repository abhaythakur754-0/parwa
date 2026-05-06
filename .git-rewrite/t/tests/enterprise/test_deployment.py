# Tests for Builder 3 - Deployment Automation
# Week 50: deployment_manager.py, rollback_manager.py, health_checker.py

import pytest
from datetime import datetime, timedelta
import time

from enterprise.ops.deployment_manager import (
    DeploymentManager, Deployment, DeploymentStatus
)
from enterprise.ops.rollback_manager import (
    RollbackManager, Rollback, RollbackPoint, RollbackStatus
)
from enterprise.ops.health_checker import (
    HealthChecker, HealthCheck, HealthCheckResult, HealthStatus, CheckType
)


# =============================================================================
# DEPLOYMENT MANAGER TESTS
# =============================================================================

class TestDeploymentManager:
    """Tests for DeploymentManager class"""

    def test_init(self):
        """Test manager initialization"""
        manager = DeploymentManager()
        assert manager is not None
        metrics = manager.get_metrics()
        assert metrics["total_deployments"] == 0

    def test_create_deployment(self):
        """Test creating a deployment"""
        manager = DeploymentManager()
        deployment = manager.create_deployment(
            tenant_id="tenant_001",
            version="v1.2.0"
        )
        assert deployment.tenant_id == "tenant_001"
        assert deployment.version == "v1.2.0"
        assert deployment.status == DeploymentStatus.PENDING
        assert len(deployment.steps) == 3  # Default steps

    def test_create_deployment_custom_steps(self):
        """Test creating deployment with custom steps"""
        manager = DeploymentManager()
        deployment = manager.create_deployment(
            tenant_id="tenant_001",
            version="v1.2.0",
            steps=["build", "test", "deploy", "verify"]
        )
        assert len(deployment.steps) == 4

    def test_start_deployment(self):
        """Test starting a deployment"""
        manager = DeploymentManager()
        deployment = manager.create_deployment("tenant_001", "v1.0.0")
        result = manager.start_deployment(deployment.id)
        assert result is True
        assert deployment.status == DeploymentStatus.RUNNING
        assert deployment.started_at is not None

    def test_start_nonexistent_deployment(self):
        """Test starting non-existent deployment"""
        manager = DeploymentManager()
        result = manager.start_deployment("nonexistent")
        assert result is False

    def test_start_already_running_deployment(self):
        """Test starting already running deployment"""
        manager = DeploymentManager()
        deployment = manager.create_deployment("tenant_001", "v1.0.0")
        manager.start_deployment(deployment.id)
        result = manager.start_deployment(deployment.id)
        assert result is False

    def test_complete_step(self):
        """Test completing a step"""
        manager = DeploymentManager()
        deployment = manager.create_deployment("tenant_001", "v1.0.0")
        manager.start_deployment(deployment.id)
        result = manager.complete_step(deployment.id)
        assert result is True
        assert deployment.current_step == 1

    def test_complete_all_steps(self):
        """Test completing all steps"""
        manager = DeploymentManager()
        deployment = manager.create_deployment("tenant_001", "v1.0.0")
        manager.start_deployment(deployment.id)
        for _ in deployment.steps:
            manager.complete_step(deployment.id)
        assert deployment.status == DeploymentStatus.COMPLETED
        assert deployment.completed_at is not None

    def test_fail_deployment(self):
        """Test failing a deployment"""
        manager = DeploymentManager()
        deployment = manager.create_deployment("tenant_001", "v1.0.0")
        result = manager.fail_deployment(deployment.id)
        assert result is True
        assert deployment.status == DeploymentStatus.FAILED

    def test_get_deployment(self):
        """Test getting deployment by ID"""
        manager = DeploymentManager()
        deployment = manager.create_deployment("tenant_001", "v1.0.0")
        retrieved = manager.get_deployment(deployment.id)
        assert retrieved is not None
        assert retrieved.id == deployment.id

    def test_get_nonexistent_deployment(self):
        """Test getting non-existent deployment"""
        manager = DeploymentManager()
        deployment = manager.get_deployment("nonexistent")
        assert deployment is None

    def test_metrics_tracking(self):
        """Test metrics tracking"""
        manager = DeploymentManager()
        d1 = manager.create_deployment("tenant_001", "v1.0.0")
        manager.start_deployment(d1.id)
        for _ in d1.steps:
            manager.complete_step(d1.id)

        d2 = manager.create_deployment("tenant_002", "v1.1.0")
        manager.fail_deployment(d2.id)

        metrics = manager.get_metrics()
        assert metrics["total_deployments"] == 2
        assert metrics["successful"] == 1
        assert metrics["failed"] == 1


# =============================================================================
# ROLLBACK MANAGER TESTS
# =============================================================================

class TestRollbackManager:
    """Tests for RollbackManager class"""

    def test_init(self):
        """Test manager initialization"""
        manager = RollbackManager()
        assert manager is not None
        metrics = manager.get_metrics()
        assert metrics["total_rollbacks"] == 0

    def test_create_rollback_point(self):
        """Test creating a rollback point"""
        manager = RollbackManager()
        point = manager.create_rollback_point(
            deployment_id="deploy_001",
            version="v1.0.0",
            snapshot_data={"config": {"key": "value"}}
        )
        assert point.deployment_id == "deploy_001"
        assert point.version == "v1.0.0"
        assert point.snapshot_data["config"]["key"] == "value"

    def test_initiate_rollback(self):
        """Test initiating a rollback"""
        manager = RollbackManager()
        point = manager.create_rollback_point("deploy_001", "v1.0.0")
        rollback = manager.initiate_rollback(
            deployment_id="deploy_001",
            rollback_point_id=point.id,
            reason="Deployment failed health check"
        )
        assert rollback is not None
        assert rollback.deployment_id == "deploy_001"
        assert rollback.rollback_point_id == point.id
        assert rollback.status == RollbackStatus.PENDING

    def test_initiate_rollback_invalid_point(self):
        """Test rollback with invalid point"""
        manager = RollbackManager()
        rollback = manager.initiate_rollback("deploy_001", "invalid_point")
        assert rollback is None

    def test_start_rollback(self):
        """Test starting a rollback"""
        manager = RollbackManager()
        point = manager.create_rollback_point("deploy_001", "v1.0.0")
        rollback = manager.initiate_rollback("deploy_001", point.id)
        result = manager.start_rollback(rollback.id)
        assert result is True
        assert rollback.status == RollbackStatus.IN_PROGRESS

    def test_complete_rollback_step(self):
        """Test completing rollback step"""
        manager = RollbackManager()
        point = manager.create_rollback_point("deploy_001", "v1.0.0")
        rollback = manager.initiate_rollback("deploy_001", point.id)
        manager.start_rollback(rollback.id)
        result = manager.complete_rollback_step(rollback.id)
        assert result is True
        assert rollback.steps_completed == 1

    def test_complete_all_rollback_steps(self):
        """Test completing all rollback steps"""
        manager = RollbackManager()
        point = manager.create_rollback_point("deploy_001", "v1.0.0")
        rollback = manager.initiate_rollback("deploy_001", point.id)
        manager.start_rollback(rollback.id)
        for _ in range(rollback.total_steps):
            manager.complete_rollback_step(rollback.id)
        assert rollback.status == RollbackStatus.COMPLETED
        assert rollback.completed_at is not None

    def test_fail_rollback(self):
        """Test failing a rollback"""
        manager = RollbackManager()
        point = manager.create_rollback_point("deploy_001", "v1.0.0")
        rollback = manager.initiate_rollback("deploy_001", point.id)
        result = manager.fail_rollback(rollback.id)
        assert result is True
        assert rollback.status == RollbackStatus.FAILED

    def test_get_rollback_point(self):
        """Test getting rollback point"""
        manager = RollbackManager()
        point = manager.create_rollback_point("deploy_001", "v1.0.0")
        retrieved = manager.get_rollback_point(point.id)
        assert retrieved is not None
        assert retrieved.id == point.id

    def test_get_rollback(self):
        """Test getting rollback by ID"""
        manager = RollbackManager()
        point = manager.create_rollback_point("deploy_001", "v1.0.0")
        rollback = manager.initiate_rollback("deploy_001", point.id)
        retrieved = manager.get_rollback(rollback.id)
        assert retrieved is not None
        assert retrieved.id == rollback.id

    def test_get_rollback_points_for_deployment(self):
        """Test getting rollback points for deployment"""
        manager = RollbackManager()
        manager.create_rollback_point("deploy_001", "v1.0.0")
        manager.create_rollback_point("deploy_001", "v1.1.0")
        manager.create_rollback_point("deploy_002", "v1.0.0")
        points = manager.get_rollback_points_for_deployment("deploy_001")
        assert len(points) == 2

    def test_get_latest_rollback_point(self):
        """Test getting latest rollback point"""
        manager = RollbackManager()
        manager.create_rollback_point("deploy_001", "v1.0.0")
        time.sleep(0.01)
        latest = manager.create_rollback_point("deploy_001", "v1.1.0")
        retrieved = manager.get_latest_rollback_point("deploy_001")
        assert retrieved.id == latest.id

    def test_get_latest_rollback_point_no_points(self):
        """Test getting latest point when none exist"""
        manager = RollbackManager()
        point = manager.get_latest_rollback_point("deploy_001")
        assert point is None

    def test_metrics_tracking(self):
        """Test metrics tracking"""
        manager = RollbackManager()
        point = manager.create_rollback_point("deploy_001", "v1.0.0")
        rollback = manager.initiate_rollback("deploy_001", point.id)
        manager.start_rollback(rollback.id)
        for _ in range(rollback.total_steps):
            manager.complete_rollback_step(rollback.id)

        metrics = manager.get_metrics()
        assert metrics["rollback_points_created"] == 1
        assert metrics["total_rollbacks"] == 1
        assert metrics["successful"] == 1


# =============================================================================
# HEALTH CHECKER TESTS
# =============================================================================

class TestHealthChecker:
    """Tests for HealthChecker class"""

    def test_init(self):
        """Test checker initialization"""
        checker = HealthChecker()
        assert checker is not None
        metrics = checker.get_metrics()
        assert metrics["total_checks"] == 0

    def test_register_check(self):
        """Test registering a health check"""
        checker = HealthChecker()
        check = checker.register_check(
            name="api_health",
            check_type=CheckType.HTTP,
            target="https://api.example.com/health"
        )
        assert check.name == "api_health"
        assert check.check_type == CheckType.HTTP
        assert check.target == "https://api.example.com/health"
        assert check.enabled is True

    def test_register_check_with_options(self):
        """Test registering check with custom options"""
        checker = HealthChecker()
        check = checker.register_check(
            name="db_health",
            check_type=CheckType.DATABASE,
            target="postgres://localhost:5432/db",
            timeout_seconds=60,
            interval_seconds=120
        )
        assert check.timeout_seconds == 60
        assert check.interval_seconds == 120

    def test_execute_check_healthy(self):
        """Test executing a healthy check"""
        checker = HealthChecker()
        check = checker.register_check("api", CheckType.HTTP, "https://api.example.com")
        result = checker.execute_check(
            check_id=check.id,
            status=HealthStatus.HEALTHY,
            response_time_ms=150.5,
            message="OK"
        )
        assert result is not None
        assert result.status == HealthStatus.HEALTHY
        assert result.response_time_ms == 150.5

    def test_execute_check_unhealthy(self):
        """Test executing an unhealthy check"""
        checker = HealthChecker()
        check = checker.register_check("api", CheckType.HTTP, "https://api.example.com")
        result = checker.execute_check(
            check_id=check.id,
            status=HealthStatus.UNHEALTHY,
            message="Connection refused"
        )
        assert result.status == HealthStatus.UNHEALTHY

    def test_execute_check_degraded(self):
        """Test executing a degraded check"""
        checker = HealthChecker()
        check = checker.register_check("api", CheckType.HTTP, "https://api.example.com")
        result = checker.execute_check(
            check_id=check.id,
            status=HealthStatus.DEGRADED,
            message="High latency detected"
        )
        assert result.status == HealthStatus.DEGRADED

    def test_execute_disabled_check(self):
        """Test executing a disabled check"""
        checker = HealthChecker()
        check = checker.register_check("api", CheckType.HTTP, "https://api.example.com")
        checker.disable_check(check.id)
        result = checker.execute_check(
            check_id=check.id,
            status=HealthStatus.HEALTHY
        )
        assert result is None

    def test_get_check(self):
        """Test getting check by ID"""
        checker = HealthChecker()
        check = checker.register_check("api", CheckType.HTTP, "https://api.example.com")
        retrieved = checker.get_check(check.id)
        assert retrieved is not None
        assert retrieved.id == check.id

    def test_get_check_by_name(self):
        """Test getting check by name"""
        checker = HealthChecker()
        check = checker.register_check("api_health", CheckType.HTTP, "https://api.example.com")
        retrieved = checker.get_check_by_name("api_health")
        assert retrieved is not None
        assert retrieved.name == "api_health"

    def test_get_current_status(self):
        """Test getting current cached status"""
        checker = HealthChecker()
        check = checker.register_check("api", CheckType.HTTP, "https://api.example.com")
        checker.execute_check(check.id, HealthStatus.HEALTHY)
        status = checker.get_current_status(check.id)
        assert status == HealthStatus.HEALTHY

    def test_get_all_statuses(self):
        """Test getting all statuses"""
        checker = HealthChecker()
        check1 = checker.register_check("api1", CheckType.HTTP, "https://api1.example.com")
        check2 = checker.register_check("api2", CheckType.HTTP, "https://api2.example.com")
        checker.execute_check(check1.id, HealthStatus.HEALTHY)
        checker.execute_check(check2.id, HealthStatus.DEGRADED)
        statuses = checker.get_all_statuses()
        assert len(statuses) == 2

    def test_get_results(self):
        """Test getting check results"""
        checker = HealthChecker()
        check = checker.register_check("api", CheckType.HTTP, "https://api.example.com")
        checker.execute_check(check.id, HealthStatus.HEALTHY)
        checker.execute_check(check.id, HealthStatus.DEGRADED)
        results = checker.get_results(check.id)
        assert len(results) == 2

    def test_get_results_with_limit(self):
        """Test getting results with limit"""
        checker = HealthChecker()
        check = checker.register_check("api", CheckType.HTTP, "https://api.example.com")
        for i in range(10):
            checker.execute_check(check.id, HealthStatus.HEALTHY)
        results = checker.get_results(limit=5)
        assert len(results) == 5

    def test_enable_disable_check(self):
        """Test enabling and disabling check"""
        checker = HealthChecker()
        check = checker.register_check("api", CheckType.HTTP, "https://api.example.com")
        checker.disable_check(check.id)
        assert check.enabled is False
        checker.enable_check(check.id)
        assert check.enabled is True

    def test_get_overall_health_healthy(self):
        """Test overall health when all healthy"""
        checker = HealthChecker()
        check1 = checker.register_check("api1", CheckType.HTTP, "https://api1.example.com")
        check2 = checker.register_check("api2", CheckType.HTTP, "https://api2.example.com")
        checker.execute_check(check1.id, HealthStatus.HEALTHY)
        checker.execute_check(check2.id, HealthStatus.HEALTHY)
        overall = checker.get_overall_health()
        assert overall == HealthStatus.HEALTHY

    def test_get_overall_health_unhealthy(self):
        """Test overall health when one unhealthy"""
        checker = HealthChecker()
        check1 = checker.register_check("api1", CheckType.HTTP, "https://api1.example.com")
        check2 = checker.register_check("api2", CheckType.HTTP, "https://api2.example.com")
        checker.execute_check(check1.id, HealthStatus.HEALTHY)
        checker.execute_check(check2.id, HealthStatus.UNHEALTHY)
        overall = checker.get_overall_health()
        assert overall == HealthStatus.UNHEALTHY

    def test_get_overall_health_degraded(self):
        """Test overall health when degraded"""
        checker = HealthChecker()
        check1 = checker.register_check("api1", CheckType.HTTP, "https://api1.example.com")
        check2 = checker.register_check("api2", CheckType.HTTP, "https://api2.example.com")
        checker.execute_check(check1.id, HealthStatus.HEALTHY)
        checker.execute_check(check2.id, HealthStatus.DEGRADED)
        overall = checker.get_overall_health()
        assert overall == HealthStatus.DEGRADED

    def test_get_overall_health_unknown(self):
        """Test overall health when no checks"""
        checker = HealthChecker()
        overall = checker.get_overall_health()
        assert overall == HealthStatus.UNKNOWN

    def test_metrics_tracking(self):
        """Test metrics tracking"""
        checker = HealthChecker()
        check = checker.register_check("api", CheckType.HTTP, "https://api.example.com")
        checker.execute_check(check.id, HealthStatus.HEALTHY)
        checker.execute_check(check.id, HealthStatus.UNHEALTHY)
        checker.execute_check(check.id, HealthStatus.DEGRADED)
        metrics = checker.get_metrics()
        assert metrics["total_checks"] == 1
        assert metrics["total_executions"] == 3
        assert metrics["healthy"] == 1
        assert metrics["unhealthy"] == 1
        assert metrics["degraded"] == 1
