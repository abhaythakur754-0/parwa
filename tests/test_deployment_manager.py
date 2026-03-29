"""
Week 60 - Builder 2 Tests: Deployment Manager Module
Unit tests for Deployment Manager, Environment Manager, and Deployment Validator
"""

import pytest
import time
from parwa_final_release.deployment_manager import (
    DeploymentManager, Deployment, DeploymentStatus,
    EnvironmentManager, Environment, EnvironmentType,
    DeploymentValidator
)


class TestDeploymentManager:
    """Tests for DeploymentManager class"""

    @pytest.fixture
    def manager(self):
        """Create deployment manager"""
        return DeploymentManager()

    def test_create_deployment(self, manager):
        """Test deployment creation"""
        deployment = manager.create_deployment(
            environment="production",
            version="1.0.0"
        )

        assert deployment.environment == "production"
        assert deployment.version == "1.0.0"
        assert deployment.status == DeploymentStatus.PENDING

    def test_start_deployment(self, manager):
        """Test starting deployment"""
        deployment = manager.create_deployment("prod", "1.0.0")
        result = manager.start_deployment(deployment.id)

        assert result is True
        assert manager.get_deployment(deployment.id).status == DeploymentStatus.IN_PROGRESS

    def test_complete_deployment(self, manager):
        """Test completing deployment"""
        deployment = manager.create_deployment("prod", "1.0.0")
        manager.start_deployment(deployment.id)
        result = manager.complete_deployment(deployment.id)

        assert result is True
        assert manager.get_deployment(deployment.id).status == DeploymentStatus.COMPLETED
        assert manager.get_current_version("prod") == "1.0.0"

    def test_fail_deployment(self, manager):
        """Test failing deployment"""
        deployment = manager.create_deployment("prod", "1.0.0")
        manager.start_deployment(deployment.id)
        result = manager.fail_deployment(deployment.id, "Connection failed")

        assert result is True
        assert manager.get_deployment(deployment.id).status == DeploymentStatus.FAILED

    def test_rollback(self, manager):
        """Test deployment rollback"""
        # Deploy first version
        dep1 = manager.create_deployment("prod", "1.0.0")
        manager.start_deployment(dep1.id)
        manager.complete_deployment(dep1.id)

        # Deploy second version
        dep2 = manager.create_deployment("prod", "2.0.0")
        manager.start_deployment(dep2.id)
        manager.complete_deployment(dep2.id)

        # Rollback
        rollback = manager.rollback(dep2.id)

        assert rollback is not None
        assert rollback.version == "1.0.0"
        assert manager.get_deployment(dep2.id).status == DeploymentStatus.ROLLED_BACK

    def test_get_deployment(self, manager):
        """Test get deployment"""
        deployment = manager.create_deployment("prod", "1.0.0")
        retrieved = manager.get_deployment(deployment.id)

        assert retrieved.version == "1.0.0"

    def test_list_deployments(self, manager):
        """Test list deployments"""
        manager.create_deployment("prod", "1.0.0")
        manager.create_deployment("staging", "1.0.0")

        all_deployments = manager.list_deployments()
        assert len(all_deployments) == 2

        prod_deployments = manager.list_deployments(environment="prod")
        assert len(prod_deployments) == 1


class TestEnvironmentManager:
    """Tests for EnvironmentManager class"""

    @pytest.fixture
    def manager(self):
        """Create environment manager"""
        return EnvironmentManager()

    def test_create_environment(self, manager):
        """Test environment creation"""
        env = manager.create_environment(
            name="production",
            env_type=EnvironmentType.PRODUCTION,
            config={"region": "us-east-1"}
        )

        assert env.name == "production"
        assert env.env_type == EnvironmentType.PRODUCTION

    def test_get_environment(self, manager):
        """Test get environment"""
        manager.create_environment("staging", EnvironmentType.STAGING)
        env = manager.get_environment("staging")

        assert env.name == "staging"

    def test_update_config(self, manager):
        """Test config update"""
        manager.create_environment("prod", EnvironmentType.PRODUCTION)
        result = manager.update_config("prod", "region", "eu-west-1")

        assert result is True
        assert manager.get_config("prod", "region") == "eu-west-1"

    def test_get_config(self, manager):
        """Test get config"""
        manager.create_environment("prod", EnvironmentType.PRODUCTION, {"key": "value"})

        config = manager.get_config("prod")
        assert config["key"] == "value"

        value = manager.get_config("prod", "key")
        assert value == "value"

    def test_add_secret_ref(self, manager):
        """Test adding secret reference"""
        manager.create_environment("prod", EnvironmentType.PRODUCTION)
        result = manager.add_secret_ref("prod", "DATABASE_PASSWORD")

        assert result is True
        assert "DATABASE_PASSWORD" in manager.get_environment("prod").secrets

    def test_add_endpoint(self, manager):
        """Test adding endpoint"""
        manager.create_environment("prod", EnvironmentType.PRODUCTION)
        result = manager.add_endpoint("prod", "api", "https://api.example.com")

        assert result is True
        assert manager.get_endpoint("prod", "api") == "https://api.example.com"

    def test_list_environments(self, manager):
        """Test list environments"""
        manager.create_environment("prod", EnvironmentType.PRODUCTION)
        manager.create_environment("staging", EnvironmentType.STAGING)

        envs = manager.list_environments()
        assert len(envs) == 2

    def test_delete_environment(self, manager):
        """Test delete environment"""
        manager.create_environment("test", EnvironmentType.DEVELOPMENT)
        result = manager.delete_environment("test")

        assert result is True
        assert manager.get_environment("test") is None


class TestDeploymentValidator:
    """Tests for DeploymentValidator class"""

    @pytest.fixture
    def validator(self):
        """Create deployment validator"""
        return DeploymentValidator()

    def test_register_check(self, validator):
        """Test check registration"""
        validator.register_check(
            category="preflight",
            name="health_check",
            check_func=lambda env: True
        )

        assert "preflight" in validator.checks

    def test_run_preflight_checks(self, validator):
        """Test preflight checks"""
        validator.register_check("preflight", "test_check", lambda e: True)
        results = validator.run_preflight_checks("production")

        assert results["check_type"] == "preflight"
        assert results["passed"] is True

    def test_run_postdeploy_checks(self, validator):
        """Test postdeploy checks"""
        validator.register_check("postdeploy", "smoke_test", lambda e: True)
        results = validator.run_postdeploy_checks("production")

        assert results["check_type"] == "postdeploy"
        assert results["passed"] is True

    def test_failed_check(self, validator):
        """Test failed check"""
        validator.register_check("preflight", "failing", lambda e: False, required=True)
        results = validator.run_preflight_checks("prod")

        assert results["passed"] is False

    def test_get_result(self, validator):
        """Test get validation result"""
        validator.register_check("preflight", "test", lambda e: True)
        results = validator.run_preflight_checks("prod")
        result_id = list(validator.results.keys())[0]

        retrieved = validator.get_result(result_id)
        assert retrieved["check_type"] == "preflight"

    def test_clear_checks(self, validator):
        """Test clearing checks"""
        validator.register_check("preflight", "test", lambda e: True)
        validator.clear_checks("preflight")

        assert len(validator.checks.get("preflight", [])) == 0
