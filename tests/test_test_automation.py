"""
Week 59 - Builder 1 Tests: Test Automation Module
Unit tests for Test Runner, Orchestrator, and Fixtures
"""

import pytest
import time
from parwa_testing_qa.test_runner import (
    TestRunner, TestCase, TestResult, TestStatus, TestPriority,
    TestOrchestrator, TestFixtures
)


class TestTestRunner:
    """Tests for TestRunner class"""

    @pytest.fixture
    def runner(self):
        """Create test runner"""
        return TestRunner()

    @pytest.fixture
    def sample_test(self):
        """Create sample test case"""
        return TestCase(
            id="test-001",
            name="sample_test",
            module="test_module",
            function="test_function"
        )

    def test_runner_creation(self, runner):
        """Test runner creation"""
        assert runner.max_workers == 4
        assert len(runner.tests) == 0

    def test_register_test(self, runner, sample_test):
        """Test test registration"""
        runner.register_test(sample_test)
        assert "test-001" in runner.tests

    def test_register_tests(self, runner):
        """Test multiple test registration"""
        tests = [
            TestCase(id="t1", name="test1", module="m1", function="f1"),
            TestCase(id="t2", name="test2", module="m2", function="f2")
        ]
        runner.register_tests(tests)
        assert len(runner.tests) == 2

    def test_discover_tests(self, runner):
        """Test test discovery"""
        runner.register_test(TestCase(id="t1", name="test1", module="test_api", function="f"))
        runner.register_test(TestCase(id="t2", name="test2", module="main", function="f"))

        discovered = runner.discover_tests("test_")
        assert len(discovered) == 1

    def test_run_test_pass(self, runner, sample_test):
        """Test running passing test"""
        runner.register_test(sample_test)
        result = runner.run_test("test-001", test_func=lambda: None)

        assert result.status == TestStatus.PASSED

    def test_run_test_fail(self, runner, sample_test):
        """Test running failing test"""
        runner.register_test(sample_test)
        result = runner.run_test("test-001", test_func=lambda: 1/0)

        assert result.status == TestStatus.ERROR

    def test_run_nonexistent_test(self, runner):
        """Test running nonexistent test"""
        result = runner.run_test("nonexistent")
        assert result.status == TestStatus.ERROR

    def test_run_tests_parallel(self, runner):
        """Test parallel test execution"""
        tests = [
            TestCase(id=f"t{i}", name=f"test{i}", module="m", function="f")
            for i in range(5)
        ]
        runner.register_tests(tests)

        results = runner.run_tests_parallel()
        assert len(results) == 5

    def test_get_result(self, runner, sample_test):
        """Test get test result"""
        runner.register_test(sample_test)
        runner.run_test("test-001")

        result = runner.get_result("test-001")
        assert result is not None

    def test_get_stats(self, runner, sample_test):
        """Test get statistics"""
        runner.register_test(sample_test)
        runner.run_test("test-001")

        stats = runner.get_stats()
        assert stats["total_tests"] == 1


class TestTestOrchestrator:
    """Tests for TestOrchestrator class"""

    @pytest.fixture
    def orchestrator(self):
        """Create test orchestrator"""
        runner = TestRunner()
        return TestOrchestrator(runner)

    def test_create_suite(self, orchestrator):
        """Test suite creation"""
        orchestrator.create_suite("smoke", ["t1", "t2", "t3"])
        assert "smoke" in orchestrator.suites

    def test_get_suite(self, orchestrator):
        """Test get suite"""
        orchestrator.create_suite("smoke", ["t1", "t2"])
        tests = orchestrator.get_suite("smoke")
        assert len(tests) == 2

    def test_list_suites(self, orchestrator):
        """Test list suites"""
        orchestrator.create_suite("s1", [])
        orchestrator.create_suite("s2", [])

        suites = orchestrator.list_suites()
        assert len(suites) == 2

    def test_resolve_dependencies(self, orchestrator):
        """Test dependency resolution"""
        t1 = TestCase(id="t1", name="test1", module="m", function="f", dependencies=[])
        t2 = TestCase(id="t2", name="test2", module="m", function="f", dependencies=["t1"])

        orchestrator.runner.register_tests([t2, t1])  # Register in reverse order
        order = orchestrator.resolve_dependencies(["t1", "t2"])

        assert order.index("t1") < order.index("t2")

    def test_get_execution_order(self, orchestrator):
        """Test get execution order"""
        orchestrator.runner.register_test(TestCase(id="t1", name="t", module="m", function="f"))
        orchestrator.resolve_dependencies()

        order = orchestrator.get_execution_order()
        assert "t1" in order


class TestTestFixtures:
    """Tests for TestFixtures class"""

    @pytest.fixture
    def fixtures(self):
        """Create test fixtures"""
        return TestFixtures()

    def test_register_fixture(self, fixtures):
        """Test fixture registration"""
        fixtures.register_fixture("db_url", "postgresql://localhost")
        assert fixtures.get_fixture("db_url") == "postgresql://localhost"

    def test_register_factory(self, fixtures):
        """Test factory registration"""
        fixtures.register_factory("counter", lambda: 42)
        assert fixtures.get_fixture("counter") == 42

    def test_register_setup(self, fixtures):
        """Test setup hook registration"""
        called = []
        fixtures.register_setup("setup1", lambda: called.append(1))

        result = fixtures.run_setup("setup1")
        assert result is True
        assert len(called) == 1

    def test_register_teardown(self, fixtures):
        """Test teardown hook registration"""
        called = []
        fixtures.register_teardown("teardown1", lambda: called.append(1))

        result = fixtures.run_teardown("teardown1")
        assert result is True
        assert len(called) == 1

    def test_create_mock(self, fixtures):
        """Test mock creation"""
        mock = fixtures.create_mock(dict)
        mock.set_return("method", "value")

        result = mock.method()
        assert result == "value"

    def test_clear_fixtures(self, fixtures):
        """Test clear fixtures"""
        fixtures.register_fixture("f1", 1)
        fixtures.clear_fixtures()

        assert len(fixtures.fixtures) == 0

    def test_get_fixture_stats(self, fixtures):
        """Test fixture statistics"""
        fixtures.register_fixture("f1", 1)
        fixtures.get_fixture("f1")
        fixtures.get_fixture("f1")

        stats = fixtures.get_fixture_stats()
        assert stats["f1"] == 2
