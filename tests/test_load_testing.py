"""
Week 59 - Builder 4 Tests: Load Testing Module
Unit tests for Load Generator, Stress Tester, and Capacity Tester
"""

import pytest
import time
from parwa_testing_qa.load_testing import (
    LoadGenerator, VirtualUser, LoadTestResult, LoadPattern, TestState,
    StressTester, StressTestResult,
    CapacityTester
)


class TestLoadGenerator:
    """Tests for LoadGenerator class"""

    @pytest.fixture
    def generator(self):
        """Create load generator"""
        return LoadGenerator()

    def test_create_virtual_users(self, generator):
        """Test virtual user creation"""
        users = generator.create_virtual_users(10)
        assert len(users) == 10
        assert len(generator.virtual_users) == 10

    def test_set_load_pattern(self, generator):
        """Test load pattern setting"""
        generator.set_load_pattern(
            LoadPattern.RAMP_UP,
            duration_seconds=60,
            max_users=100
        )

        assert generator.pattern == LoadPattern.RAMP_UP

    def test_run_test(self, generator):
        """Test load test execution"""
        result = generator.run_test(
            test_func=lambda: time.sleep(0.001),
            duration_seconds=2,
            target_rps=10
        )

        assert result.state == TestState.COMPLETED
        assert result.total_requests > 0

    def test_stop_test(self, generator):
        """Test stopping test"""
        generator.stop_flag = False
        generator.stop_test()
        assert generator.stop_flag is True

    def test_get_result(self, generator):
        """Test get result"""
        result = generator.run_test(
            test_func=lambda: None,
            duration_seconds=1,
            target_rps=5
        )

        retrieved = generator.get_result(result.test_id)
        assert retrieved.test_id == result.test_id


class TestStressTester:
    """Tests for StressTester class"""

    @pytest.fixture
    def tester(self):
        """Create stress tester"""
        return StressTester()

    def test_run_stress_test(self, tester):
        """Test stress test execution"""
        result = tester.run_stress_test(
            test_func=lambda: time.sleep(0.001),
            initial_load=5,
            increment=5,
            max_load=20,
            duration_per_step=1
        )

        assert result.state == TestState.COMPLETED
        assert result.max_concurrent >= 0

    def test_get_result(self, tester):
        """Test get stress test result"""
        result = tester.run_stress_test(
            test_func=lambda: None,
            initial_load=5,
            max_load=10,
            duration_per_step=1
        )

        retrieved = tester.get_result(result.test_id)
        assert retrieved.test_id == result.test_id


class TestCapacityTester:
    """Tests for CapacityTester class"""

    @pytest.fixture
    def tester(self):
        """Create capacity tester"""
        return CapacityTester()

    def test_test_capacity(self, tester):
        """Test capacity test"""
        result = tester.test_capacity(
            test_func=lambda: time.sleep(0.001),
            target_rps=10,
            duration_seconds=2,
            sla_latency_ms=500,
            sla_error_rate=0.01
        )

        assert "test_id" in result
        assert "actual_rps" in result
        assert "sla_met" in result

    def test_find_max_capacity(self, tester):
        """Test finding max capacity"""
        result = tester.find_max_capacity(
            test_func=lambda: time.sleep(0.001),
            start_rps=5,
            max_rps=20,
            step=10,
            sla_latency_ms=500,
            sla_error_rate=0.1
        )

        assert "max_capacity_rps" in result
        assert result["max_capacity_rps"] >= 0

    def test_get_result(self, tester):
        """Test get capacity test result"""
        result = tester.test_capacity(
            test_func=lambda: None,
            target_rps=5,
            duration_seconds=1
        )

        retrieved = tester.get_result(result["test_id"])
        assert retrieved is not None
