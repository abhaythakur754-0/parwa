"""
Week 59 - Builder 1: Test Automation Module
Test runner, orchestrator, and fixtures management
"""

import time
import threading
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging
import traceback

logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """Test execution status"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestPriority(Enum):
    """Test priority levels"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class TestCase:
    """Test case definition"""
    id: str
    name: str
    module: str
    function: str
    priority: TestPriority = TestPriority.MEDIUM
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    timeout: int = 60


@dataclass
class TestResult:
    """Test execution result"""
    test_id: str
    status: TestStatus
    duration_ms: float = 0
    message: str = ""
    error: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


class TestRunner:
    """
    Test runner with discovery, execution, and parallelization
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.tests: Dict[str, TestCase] = {}
        self.results: Dict[str, TestResult] = {}
        self.running = False
        self.lock = threading.Lock()
        self.stats: Dict[str, int] = defaultdict(int)

    def register_test(self, test: TestCase) -> None:
        """Register a test case"""
        with self.lock:
            self.tests[test.id] = test

    def register_tests(self, tests: List[TestCase]) -> None:
        """Register multiple test cases"""
        for test in tests:
            self.register_test(test)

    def discover_tests(self, module_pattern: str = "test_") -> List[TestCase]:
        """Discover tests matching pattern"""
        return [
            test for test in self.tests.values()
            if module_pattern in test.module
        ]

    def run_test(self, test_id: str, test_func: Callable = None) -> TestResult:
        """Run a single test"""
        test = self.tests.get(test_id)
        if not test:
            return TestResult(
                test_id=test_id,
                status=TestStatus.ERROR,
                message="Test not found"
            )

        result = TestResult(test_id=test_id, status=TestStatus.RUNNING)
        start_time = time.time()

        try:
            if test_func:
                test_func()
            result.status = TestStatus.PASSED
            result.message = "Test passed"

        except AssertionError as e:
            result.status = TestStatus.FAILED
            result.message = str(e)
            result.error = traceback.format_exc()

        except Exception as e:
            result.status = TestStatus.ERROR
            result.message = f"Test error: {str(e)}"
            result.error = traceback.format_exc()

        result.duration_ms = (time.time() - start_time) * 1000
        result.completed_at = time.time()

        with self.lock:
            self.results[test_id] = result
            self.stats[result.status.value] += 1

        return result

    def run_tests_parallel(self, test_ids: List[str] = None) -> Dict[str, TestResult]:
        """Run tests in parallel"""
        if test_ids is None:
            test_ids = list(self.tests.keys())

        results = {}
        threads = []

        def run_single(test_id: str):
            results[test_id] = self.run_test(test_id)

        for test_id in test_ids:
            thread = threading.Thread(target=run_single, args=(test_id,))
            threads.append(thread)
            thread.start()

            if len(threads) >= self.max_workers:
                for t in threads:
                    t.join()
                threads = []

        for t in threads:
            t.join()

        return results

    def get_result(self, test_id: str) -> Optional[TestResult]:
        """Get test result by ID"""
        return self.results.get(test_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get test statistics"""
        with self.lock:
            total = sum(self.stats.values())
            return {
                "total_tests": len(self.tests),
                "total_run": total,
                "passed": self.stats.get("passed", 0),
                "failed": self.stats.get("failed", 0),
                "errors": self.stats.get("error", 0),
                "skipped": self.stats.get("skipped", 0)
            }


class TestOrchestrator:
    """
    Test orchestrator for suites, dependencies, and ordering
    """

    def __init__(self, runner: TestRunner):
        self.runner = runner
        self.suites: Dict[str, List[str]] = {}
        self.execution_order: List[str] = []
        self.lock = threading.Lock()

    def create_suite(self, name: str, test_ids: List[str]) -> None:
        """Create a test suite"""
        with self.lock:
            self.suites[name] = test_ids

    def get_suite(self, name: str) -> List[str]:
        """Get test IDs in a suite"""
        return self.suites.get(name, [])

    def list_suites(self) -> List[str]:
        """List all suites"""
        return list(self.suites.keys())

    def resolve_dependencies(self, test_ids: List[str] = None) -> List[str]:
        """Resolve test dependencies and return execution order"""
        if test_ids is None:
            test_ids = list(self.runner.tests.keys())

        # Build dependency graph
        graph = {}
        for test_id in test_ids:
            test = self.runner.tests.get(test_id)
            if test:
                deps = [d for d in test.dependencies if d in test_ids]
                graph[test_id] = deps

        # Topological sort
        visited = set()
        order = []

        def visit(test_id: str):
            if test_id in visited:
                return
            visited.add(test_id)
            for dep in graph.get(test_id, []):
                visit(dep)
            order.append(test_id)

        for test_id in test_ids:
            visit(test_id)

        with self.lock:
            self.execution_order = order

        return order

    def run_suite(self, name: str, parallel: bool = False) -> Dict[str, TestResult]:
        """Run a test suite"""
        test_ids = self.get_suite(name)
        if not test_ids:
            return {}

        if parallel:
            return self.runner.run_tests_parallel(test_ids)

        order = self.resolve_dependencies(test_ids)
        results = {}
        for test_id in order:
            results[test_id] = self.runner.run_test(test_id)
        return results

    def get_execution_order(self) -> List[str]:
        """Get current execution order"""
        return list(self.execution_order)


class TestFixtures:
    """
    Test fixtures manager for data, mocks, and setup/teardown
    """

    def __init__(self):
        self.fixtures: Dict[str, Any] = {}
        self.setup_hooks: Dict[str, Callable] = {}
        self.teardown_hooks: Dict[str, Callable] = {}
        self.fixture_counts: Dict[str, int] = defaultdict(int)
        self.lock = threading.Lock()

    def register_fixture(self, name: str, value: Any) -> None:
        """Register a fixture value"""
        with self.lock:
            self.fixtures[name] = value

    def register_factory(self, name: str, factory: Callable) -> None:
        """Register a fixture factory function"""
        with self.lock:
            self.fixtures[name] = factory

    def get_fixture(self, name: str) -> Any:
        """Get a fixture value"""
        fixture = self.fixtures.get(name)
        if callable(fixture) and not isinstance(fixture, type):
            result = fixture()
            with self.lock:
                self.fixture_counts[name] += 1
            return result

        with self.lock:
            self.fixture_counts[name] += 1
        return fixture

    def register_setup(self, name: str, hook: Callable) -> None:
        """Register setup hook"""
        with self.lock:
            self.setup_hooks[name] = hook

    def register_teardown(self, name: str, hook: Callable) -> None:
        """Register teardown hook"""
        with self.lock:
            self.teardown_hooks[name] = hook

    def run_setup(self, name: str = None) -> bool:
        """Run setup hooks"""
        hooks = self.setup_hooks
        if name:
            hooks = {name: hooks.get(name)} if name in hooks else {}

        for hook_name, hook in hooks.items():
            try:
                hook()
            except Exception as e:
                logger.error(f"Setup hook {hook_name} failed: {e}")
                return False
        return True

    def run_teardown(self, name: str = None) -> bool:
        """Run teardown hooks"""
        hooks = self.teardown_hooks
        if name:
            hooks = {name: hooks.get(name)} if name in hooks else {}

        for hook_name, hook in hooks.items():
            try:
                hook()
            except Exception as e:
                logger.error(f"Teardown hook {hook_name} failed: {e}")
                return False
        return True

    def create_mock(self, spec: Any) -> Any:
        """Create a mock object"""
        class MockObject:
            def __init__(self):
                self._calls = defaultdict(list)
                self._returns = {}

            def __getattr__(self, name):
                def mock_method(*args, **kwargs):
                    self._calls[name].append((args, kwargs))
                    return self._returns.get(name)
                return mock_method

            def set_return(self, method: str, value: Any):
                self._returns[method] = value

            def get_calls(self, method: str) -> List:
                return self._calls.get(method, [])

        return MockObject()

    def clear_fixtures(self) -> None:
        """Clear all fixtures"""
        with self.lock:
            self.fixtures.clear()
            self.fixture_counts.clear()

    def get_fixture_stats(self) -> Dict[str, int]:
        """Get fixture usage statistics"""
        return dict(self.fixture_counts)
