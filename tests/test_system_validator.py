"""
Week 60 - Builder 5 Tests: System Validator Module
Unit tests for System Validator, Dependency Checker, and Readiness Checker
"""

import pytest
from parwa_final_release.system_validator import (
    SystemValidator, SystemCheck, CheckStatus,
    DependencyChecker, Dependency,
    ReadinessChecker, ReadinessCheck, ReadinessCategory
)


class TestSystemValidator:
    """Tests for SystemValidator class"""

    @pytest.fixture
    def validator(self):
        """Create system validator"""
        return SystemValidator()

    def test_register_check(self, validator):
        """Test check registration"""
        validator.register_check(
            name="health_check",
            category="health",
            check_func=lambda: (CheckStatus.PASS, "OK", {})
        )

        assert "health_check" in validator.check_registry

    def test_run_check(self, validator):
        """Test running a check"""
        validator.register_check(
            "test_check",
            "test",
            lambda: (CheckStatus.PASS, "Test passed", {})
        )

        check = validator.run_check("test_check")

        assert check.status == CheckStatus.PASS
        assert check.message == "Test passed"

    def test_run_failing_check(self, validator):
        """Test running a failing check"""
        validator.register_check(
            "fail_check",
            "test",
            lambda: (CheckStatus.FAIL, "Test failed", {})
        )

        check = validator.run_check("fail_check")

        assert check.status == CheckStatus.FAIL

    def test_run_all_checks(self, validator):
        """Test running all checks"""
        validator.register_check("check1", "cat1", lambda: (CheckStatus.PASS, "OK", {}))
        validator.register_check("check2", "cat2", lambda: (CheckStatus.PASS, "OK", {}))

        results = validator.run_all_checks()

        assert results["total"] == 2
        assert results["passed"] == 2

    def test_get_results(self, validator):
        """Test getting results"""
        validator.register_check("test", "cat", lambda: (CheckStatus.PASS, "OK", {}))
        validator.run_check("test")

        results = validator.get_results("test")
        assert len(results) == 1

    def test_get_summary(self, validator):
        """Test getting summary"""
        validator.register_check("check1", "cat1", lambda: (CheckStatus.PASS, "OK", {}))
        validator.register_check("check2", "cat1", lambda: (CheckStatus.FAIL, "Fail", {}))
        validator.run_all_checks()

        summary = validator.get_summary()

        assert "cat1" in summary
        assert summary["cat1"]["pass"] == 1
        assert summary["cat1"]["fail"] == 1


class TestDependencyChecker:
    """Tests for DependencyChecker class"""

    @pytest.fixture
    def checker(self):
        """Create dependency checker"""
        return DependencyChecker()

    def test_register_dependency(self, checker):
        """Test registering dependency"""
        dep = checker.register_dependency(
            name="requests",
            current_version="2.25.0",
            required_version=">=2.20.0",
            latest_version="2.28.0"
        )

        assert dep.name == "requests"
        assert dep.current_version == "2.25.0"

    def test_check_versions(self, checker):
        """Test version checking"""
        checker.register_dependency("pkg1", "1.0.0", latest_version="2.0.0")
        checker.register_dependency("pkg2", "1.0.0", latest_version="1.0.0")

        results = checker.check_versions()

        assert results["total"] == 2
        assert results["outdated"] == 1
        assert results["up_to_date"] == 1

    def test_check_vulnerabilities(self, checker):
        """Test vulnerability checking"""
        checker.register_dependency("pkg1", "1.0.0")
        checker.add_vulnerability("pkg1", "1.0.0", "CVE-2023-001", "high")

        results = checker.check_vulnerabilities()

        assert results["vulnerable"] == 1
        assert results["secure"] == 0

    def test_add_vulnerability(self, checker):
        """Test adding vulnerability"""
        checker.add_vulnerability("pkg", "1.0.0", "CVE-001", "critical", "RCE")

        assert "pkg@1.0.0" in checker.vulnerability_db

    def test_get_dependency(self, checker):
        """Test getting dependency"""
        checker.register_dependency("requests", "2.25.0")

        dep = checker.get_dependency("requests")
        assert dep.current_version == "2.25.0"

    def test_list_dependencies(self, checker):
        """Test listing dependencies"""
        checker.register_dependency("pkg1", "1.0.0")
        checker.register_dependency("pkg2", "2.0.0")

        deps = checker.list_dependencies()
        assert len(deps) == 2


class TestReadinessChecker:
    """Tests for ReadinessChecker class"""

    @pytest.fixture
    def checker(self):
        """Create readiness checker"""
        return ReadinessChecker()

    def test_add_check(self, checker):
        """Test adding readiness check"""
        checker.add_check(
            category=ReadinessCategory.INFRASTRUCTURE,
            name="database_ready",
            description="Database is accessible",
            required=True
        )

        assert len(checker.checklist) == 1

    def test_run_checklist(self, checker):
        """Test running checklist"""
        checker.add_check(ReadinessCategory.INFRASTRUCTURE, "check1", "Test", True)
        checker.add_check(ReadinessCategory.SECURITY, "check2", "Test", True)

        results = checker.run_checklist()

        assert results["ready"] is True
        assert len(results["checks"]) == 2

    def test_get_results(self, checker):
        """Test getting results"""
        checker.add_check(ReadinessCategory.INFRASTRUCTURE, "test", "Test")
        checker.run_checklist()

        results = checker.get_results()
        assert results is not None

    def test_get_category_status(self, checker):
        """Test getting category status"""
        checker.add_check(ReadinessCategory.INFRASTRUCTURE, "check1", "Test")
        checker.add_check(ReadinessCategory.INFRASTRUCTURE, "check2", "Test")
        checker.run_checklist()

        status = checker.get_category_status(ReadinessCategory.INFRASTRUCTURE)

        assert status["total"] == 2
        assert status["passed"] == 2

    def test_is_ready(self, checker):
        """Test readiness check"""
        checker.add_check(ReadinessCategory.INFRASTRUCTURE, "check", "Test")
        checker.run_checklist()

        assert checker.is_ready() is True

    def test_clear_checklist(self, checker):
        """Test clearing checklist"""
        checker.add_check(ReadinessCategory.INFRASTRUCTURE, "check", "Test")
        checker.clear_checklist()

        assert len(checker.checklist) == 0
