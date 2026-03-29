"""
Tests for Performance Tuner Module - Week 52, Builder 2
"""

import pytest
from datetime import datetime, timedelta

from enterprise.scaling.performance_tuner import (
    PerformanceTuner,
    PerformanceProfile,
    PerformanceMetric,
    TuningAction,
    TuningResult,
    TuningStatus,
    OptimizationType,
    CPUPerformanceTuner,
    MemoryPerformanceTuner,
    LatencyOptimizer,
)
from enterprise.scaling.query_optimizer import (
    QueryParser,
    QueryOptimizer,
    QueryRewriter,
    QueryAnalysis,
    QueryType,
    QueryPlan,
    OptimizationSuggestion,
    OptimizationLevel,
)
from enterprise.scaling.resource_tuner import (
    ResourceTuner,
    ResourceMonitor,
    ResourceUsage,
    ResourceLimit,
    ResourceType,
    ResourceStatus,
    TuningStrategy,
    TuningRecommendation,
    ThreadPoolTuner,
    ConnectionPoolTuner,
)


# ============================================================================
# Performance Tuner Tests
# ============================================================================

class TestPerformanceMetric:
    """Tests for PerformanceMetric class"""

    def test_init(self):
        """Test metric initialization"""
        metric = PerformanceMetric(name="cpu", value=50.0)
        assert metric.name == "cpu"
        assert metric.value == 50.0

    def test_improvement(self):
        """Test improvement calculation"""
        metric = PerformanceMetric(name="cpu", value=40, baseline=50)
        assert metric.improvement == 20.0  # 20% improvement

    def test_improvement_no_baseline(self):
        """Test improvement with no baseline"""
        metric = PerformanceMetric(name="cpu", value=50)
        assert metric.improvement is None

    def test_meets_target(self):
        """Test target check"""
        metric = PerformanceMetric(name="latency", value=100, target=200)
        assert metric.meets_target is True

        metric = PerformanceMetric(name="latency", value=300, target=200)
        assert metric.meets_target is False

    def test_meets_target_no_target(self):
        """Test target check with no target"""
        metric = PerformanceMetric(name="cpu", value=50)
        assert metric.meets_target is True


class TestPerformanceProfile:
    """Tests for PerformanceProfile class"""

    def test_init(self):
        """Test profile initialization"""
        profile = PerformanceProfile("test_profile")
        assert profile.name == "test_profile"
        assert len(profile.metrics) == 0

    def test_record_metric(self):
        """Test recording metric"""
        profile = PerformanceProfile("test")
        metric = profile.record_metric("cpu", 50.0, "%")
        assert metric.name == "cpu"
        assert metric.value == 50.0
        assert len(profile.metrics["cpu"]) == 1

    def test_set_baseline(self):
        """Test setting baseline"""
        profile = PerformanceProfile("test")
        profile.set_baseline("cpu", 60)
        assert profile.baselines["cpu"] == 60

    def test_set_target(self):
        """Test setting target"""
        profile = PerformanceProfile("test")
        profile.set_target("latency", 200)
        assert profile.targets["latency"] == 200

    def test_get_current(self):
        """Test getting current value"""
        profile = PerformanceProfile("test")
        assert profile.get_current("cpu") is None
        profile.record_metric("cpu", 50)
        profile.record_metric("cpu", 60)
        assert profile.get_current("cpu") == 60

    def test_get_average(self):
        """Test getting average"""
        profile = PerformanceProfile("test")
        profile.record_metric("cpu", 40)
        profile.record_metric("cpu", 50)
        profile.record_metric("cpu", 60)
        assert profile.get_average("cpu", window=3) == 50

    def test_get_trend(self):
        """Test getting trend"""
        profile = PerformanceProfile("test")
        # Add increasing values
        for i in range(10):
            profile.record_metric("cpu", i * 10)
        assert profile.get_trend("cpu") == "increasing"

        # Add decreasing values
        for i in range(10):
            profile.record_metric("memory", 100 - i * 5)
        assert profile.get_trend("memory") == "decreasing"

    def test_get_trend_insufficient_data(self):
        """Test trend with insufficient data"""
        profile = PerformanceProfile("test")
        profile.record_metric("cpu", 50)
        assert profile.get_trend("cpu") == "unknown"


class TestTuningAction:
    """Tests for TuningAction class"""

    def test_init(self):
        """Test action initialization"""
        action = TuningAction(
            name="test_action",
            optimization_type=OptimizationType.CPU,
            description="Test action",
        )
        assert action.name == "test_action"
        assert action.applied is False


class TestPerformanceTuner:
    """Tests for PerformanceTuner class"""

    def test_init(self):
        """Test tuner initialization"""
        tuner = PerformanceTuner()
        assert tuner.status == TuningStatus.IDLE
        assert len(tuner.profiles) == 0

    def test_create_profile(self):
        """Test creating profile"""
        tuner = PerformanceTuner()
        profile = tuner.create_profile("test_profile")
        assert profile is not None
        assert "test_profile" in tuner.profiles

    def test_get_profile(self):
        """Test getting profile"""
        tuner = PerformanceTuner()
        tuner.create_profile("test_profile")
        assert tuner.get_profile("test_profile") is not None
        assert tuner.get_profile("nonexistent") is None

    def test_register_handler(self):
        """Test registering handler"""
        tuner = PerformanceTuner()
        handler = lambda action: True
        tuner.register_handler(OptimizationType.CPU, handler)
        assert "cpu" in tuner._handlers

    def test_apply_tuning_with_handler(self):
        """Test applying tuning with handler"""
        tuner = PerformanceTuner()
        calls = []
        tuner.register_handler(OptimizationType.CPU, lambda a: calls.append(a) or True)

        action = TuningAction(
            name="test",
            optimization_type=OptimizationType.CPU,
            description="test",
        )
        result = tuner.apply_tuning(action)
        assert result.success is True
        assert len(calls) == 1

    def test_apply_tuning_no_handler(self):
        """Test applying tuning without handler"""
        tuner = PerformanceTuner()
        action = TuningAction(
            name="test",
            optimization_type=OptimizationType.CPU,
            description="test",
        )
        result = tuner.apply_tuning(action)
        assert result.success is False
        assert result.error is not None

    def test_get_statistics(self):
        """Test getting statistics"""
        tuner = PerformanceTuner()
        stats = tuner.get_statistics()
        assert stats["status"] == "idle"
        assert stats["profiles_count"] == 0


class TestCPUPerformanceTuner:
    """Tests for CPUPerformanceTuner class"""

    def test_init(self):
        """Test CPU tuner initialization"""
        tuner = CPUPerformanceTuner()
        assert len(tuner._optimization_rules) > 0

    def test_high_cpu_rule(self):
        """Test high CPU rule triggers"""
        tuner = CPUPerformanceTuner()
        profile = tuner.create_profile("test")
        profile.record_metric("cpu_usage", 90)

        actions = tuner.analyze("test")
        assert len(actions) > 0
        assert any(a.name == "reduce_cpu_load" for a in actions)


class TestMemoryPerformanceTuner:
    """Tests for MemoryPerformanceTuner class"""

    def test_init(self):
        """Test memory tuner initialization"""
        tuner = MemoryPerformanceTuner()
        assert len(tuner._optimization_rules) > 0

    def test_high_memory_rule(self):
        """Test high memory rule triggers"""
        tuner = MemoryPerformanceTuner()
        profile = tuner.create_profile("test")
        profile.record_metric("memory_usage", 90)

        actions = tuner.analyze("test")
        assert len(actions) > 0


class TestLatencyOptimizer:
    """Tests for LatencyOptimizer class"""

    def test_init(self):
        """Test latency optimizer initialization"""
        optimizer = LatencyOptimizer()
        assert len(optimizer._optimization_rules) > 0

    def test_high_latency_rule(self):
        """Test high latency rule triggers"""
        optimizer = LatencyOptimizer()
        profile = optimizer.create_profile("test")
        profile.record_metric("latency_p95", 600)

        actions = optimizer.analyze("test")
        assert len(actions) > 0


# ============================================================================
# Query Optimizer Tests
# ============================================================================

class TestQueryParser:
    """Tests for QueryParser class"""

    def test_parse_select(self):
        """Test parsing SELECT query"""
        parser = QueryParser()
        query = "SELECT id, name FROM users WHERE active = 1"
        analysis = parser.parse(query)
        assert analysis.query_type == QueryType.SELECT
        assert "users" in analysis.tables
        assert len(analysis.where_clauses) > 0

    def test_parse_select_wildcard(self):
        """Test parsing SELECT * query"""
        parser = QueryParser()
        query = "SELECT * FROM users"
        analysis = parser.parse(query)
        assert analysis.has_wildcard is True

    def test_parse_join(self):
        """Test parsing JOIN query"""
        parser = QueryParser()
        query = "SELECT u.name, o.id FROM users u JOIN orders o ON u.id = o.user_id"
        analysis = parser.parse(query)
        assert analysis.query_type == QueryType.JOIN
        assert "users" in analysis.tables
        assert "orders" in analysis.tables

    def test_parse_insert(self):
        """Test parsing INSERT query"""
        parser = QueryParser()
        query = "INSERT INTO users (name, email) VALUES ('John', 'john@test.com')"
        analysis = parser.parse(query)
        assert analysis.query_type == QueryType.INSERT
        assert "users" in analysis.tables

    def test_parse_update(self):
        """Test parsing UPDATE query"""
        parser = QueryParser()
        query = "UPDATE users SET name = 'Jane' WHERE id = 1"
        analysis = parser.parse(query)
        assert analysis.query_type == QueryType.UPDATE
        assert "users" in analysis.tables

    def test_parse_delete(self):
        """Test parsing DELETE query"""
        parser = QueryParser()
        query = "DELETE FROM users WHERE id = 1"
        analysis = parser.parse(query)
        assert analysis.query_type == QueryType.DELETE

    def test_parse_order_by(self):
        """Test parsing ORDER BY"""
        parser = QueryParser()
        query = "SELECT * FROM users ORDER BY created_at DESC"
        analysis = parser.parse(query)
        assert len(analysis.order_by) > 0

    def test_parse_group_by(self):
        """Test parsing GROUP BY"""
        parser = QueryParser()
        query = "SELECT COUNT(*) FROM users GROUP BY status"
        analysis = parser.parse(query)
        assert len(analysis.group_by) > 0

    def test_parse_limit(self):
        """Test parsing LIMIT"""
        parser = QueryParser()
        query = "SELECT * FROM users LIMIT 10"
        analysis = parser.parse(query)
        assert analysis.has_limit is True

    def test_parse_subquery(self):
        """Test parsing subquery"""
        parser = QueryParser()
        query = "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"
        analysis = parser.parse(query)
        assert analysis.has_subquery is True

    def test_parse_distinct(self):
        """Test parsing DISTINCT"""
        parser = QueryParser()
        query = "SELECT DISTINCT name FROM users"
        analysis = parser.parse(query)
        assert analysis.has_distinct is True


class TestQueryOptimizer:
    """Tests for QueryOptimizer class"""

    def test_init(self):
        """Test optimizer initialization"""
        optimizer = QueryOptimizer()
        assert optimizer.slow_query_threshold_ms == 1000.0

    def test_analyze(self):
        """Test query analysis"""
        optimizer = QueryOptimizer()
        analysis = optimizer.analyze("SELECT * FROM users")
        assert analysis.query_type == QueryType.SELECT

    def test_suggest_optimizations_wildcard(self):
        """Test suggestion for SELECT *"""
        optimizer = QueryOptimizer()
        suggestions = optimizer.suggest_optimizations("SELECT * FROM users")
        assert any("SELECT *" in s.suggestion for s in suggestions)

    def test_suggest_optimizations_no_limit(self):
        """Test suggestion for missing LIMIT"""
        optimizer = QueryOptimizer()
        suggestions = optimizer.suggest_optimizations("SELECT id FROM users")
        assert any("LIMIT" in s.suggestion for s in suggestions)

    def test_suggest_optimizations_subquery(self):
        """Test suggestion for subquery"""
        optimizer = QueryOptimizer()
        query = "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"
        suggestions = optimizer.suggest_optimizations(query)
        assert any("subquery" in s.suggestion.lower() for s in suggestions)

    def test_suggest_optimizations_slow_query(self):
        """Test suggestion for slow query"""
        optimizer = QueryOptimizer()
        plan = QueryPlan(
            query="SELECT * FROM users",
            estimated_cost=100,
            estimated_rows=1000,
            execution_time_ms=1500,
        )
        suggestions = optimizer.suggest_optimizations("SELECT * FROM users", plan)
        assert any(s.level == OptimizationLevel.CRITICAL for s in suggestions)

    def test_suggest_optimizations_full_scan(self):
        """Test suggestion for full table scan"""
        optimizer = QueryOptimizer()
        plan = QueryPlan(
            query="SELECT * FROM users WHERE name = 'John'",
            estimated_cost=100,
            estimated_rows=1000,
            scan_type="full",
        )
        suggestions = optimizer.suggest_optimizations(
            "SELECT * FROM users WHERE name = 'John'", plan
        )
        assert any("full table scan" in s.reason.lower() for s in suggestions)

    def test_record_plan(self):
        """Test recording query plan"""
        optimizer = QueryOptimizer()
        plan = QueryPlan(
            query="SELECT * FROM users",
            estimated_cost=100,
            estimated_rows=1000,
        )
        optimizer.record_plan("SELECT * FROM users", plan)
        assert len(optimizer.query_history) == 1

    def test_get_slow_queries(self):
        """Test getting slow queries"""
        optimizer = QueryOptimizer()
        plan = QueryPlan(
            query="SELECT * FROM large_table",
            estimated_cost=100,
            estimated_rows=1000000,
            execution_time_ms=2000,
        )
        optimizer.record_plan("SELECT * FROM large_table", plan)
        slow = optimizer.get_slow_queries()
        assert len(slow) == 1

    def test_get_statistics(self):
        """Test getting statistics"""
        optimizer = QueryOptimizer()
        stats = optimizer.get_statistics()
        assert "total_unique_queries" in stats
        assert "slow_queries_count" in stats


class TestQueryRewriter:
    """Tests for QueryRewriter class"""

    def test_init(self):
        """Test rewriter initialization"""
        rewriter = QueryRewriter()
        assert rewriter.parser is not None

    def test_rewrite_whitespace(self):
        """Test whitespace normalization"""
        rewriter = QueryRewriter()
        query = "SELECT   *   FROM   users"
        rewritten, changes = rewriter.rewrite(query)
        assert "  " not in rewritten

    def test_rewrite_no_changes(self):
        """Test no changes needed"""
        rewriter = QueryRewriter()
        query = "SELECT id FROM users"
        rewritten, changes = rewriter.rewrite(query)
        # Should normalize whitespace at minimum
        assert rewritten is not None


# ============================================================================
# Resource Tuner Tests
# ============================================================================

class TestResourceUsage:
    """Tests for ResourceUsage class"""

    def test_init(self):
        """Test usage initialization"""
        usage = ResourceUsage(
            resource_type=ResourceType.CPU,
            current=50,
            limit=100,
        )
        assert usage.current == 50
        assert usage.limit == 100

    def test_utilization_percent(self):
        """Test utilization calculation"""
        usage = ResourceUsage(
            resource_type=ResourceType.CPU,
            current=75,
            limit=100,
        )
        assert usage.utilization_percent == 75.0

    def test_utilization_zero_limit(self):
        """Test utilization with zero limit"""
        usage = ResourceUsage(
            resource_type=ResourceType.CPU,
            current=50,
            limit=0,
        )
        assert usage.utilization_percent == 0.0

    def test_available(self):
        """Test available calculation"""
        usage = ResourceUsage(
            resource_type=ResourceType.CPU,
            current=30,
            limit=100,
        )
        assert usage.available == 70

    def test_status_optimal(self):
        """Test optimal status"""
        usage = ResourceUsage(
            resource_type=ResourceType.CPU,
            current=50,
            limit=100,
        )
        assert usage.status == ResourceStatus.OPTIMAL

    def test_status_critical(self):
        """Test critical status"""
        usage = ResourceUsage(
            resource_type=ResourceType.CPU,
            current=96,
            limit=100,
        )
        assert usage.status == ResourceStatus.CRITICAL

    def test_status_over_utilized(self):
        """Test over-utilized status"""
        usage = ResourceUsage(
            resource_type=ResourceType.CPU,
            current=85,
            limit=100,
        )
        assert usage.status == ResourceStatus.OVER_UTILIZED

    def test_status_under_utilized(self):
        """Test under-utilized status"""
        usage = ResourceUsage(
            resource_type=ResourceType.CPU,
            current=10,
            limit=100,
        )
        assert usage.status == ResourceStatus.UNDER_UTILIZED


class TestResourceMonitor:
    """Tests for ResourceMonitor class"""

    def test_init(self):
        """Test monitor initialization"""
        monitor = ResourceMonitor()
        assert len(monitor.usage_history) == 0

    def test_set_limit(self):
        """Test setting limit"""
        monitor = ResourceMonitor()
        monitor.set_limit(ResourceType.CPU, 80, 100)
        assert ResourceType.CPU in monitor.limits
        assert monitor.limits[ResourceType.CPU].soft_limit == 80

    def test_record_usage(self):
        """Test recording usage"""
        monitor = ResourceMonitor()
        monitor.set_limit(ResourceType.CPU, 80, 100)
        usage = monitor.record_usage(ResourceType.CPU, 50)
        assert usage.current == 50
        assert ResourceType.CPU in monitor.usage_history

    def test_get_current_usage(self):
        """Test getting current usage"""
        monitor = ResourceMonitor()
        monitor.set_limit(ResourceType.CPU, 80, 100)
        monitor.record_usage(ResourceType.CPU, 50)
        usage = monitor.get_current_usage(ResourceType.CPU)
        assert usage.current == 50

    def test_get_average_usage(self):
        """Test getting average usage"""
        monitor = ResourceMonitor()
        monitor.set_limit(ResourceType.CPU, 80, 100)
        monitor.record_usage(ResourceType.CPU, 40)
        monitor.record_usage(ResourceType.CPU, 50)
        monitor.record_usage(ResourceType.CPU, 60)
        avg = monitor.get_average_usage(ResourceType.CPU)
        assert avg == 50

    def test_get_peak_usage(self):
        """Test getting peak usage"""
        monitor = ResourceMonitor()
        monitor.set_limit(ResourceType.CPU, 80, 100)
        monitor.record_usage(ResourceType.CPU, 40)
        monitor.record_usage(ResourceType.CPU, 90)
        monitor.record_usage(ResourceType.CPU, 60)
        peak = monitor.get_peak_usage(ResourceType.CPU)
        assert peak == 90

    def test_register_collector(self):
        """Test registering collector"""
        monitor = ResourceMonitor()
        monitor.register_collector(ResourceType.CPU, lambda: 50)
        assert ResourceType.CPU in monitor._collectors

    def test_collect(self):
        """Test collecting from collectors"""
        monitor = ResourceMonitor()
        monitor.set_limit(ResourceType.CPU, 80, 100)
        monitor.register_collector(ResourceType.CPU, lambda: 50)
        results = monitor.collect()
        assert ResourceType.CPU in results
        assert results[ResourceType.CPU].current == 50


class TestResourceTuner:
    """Tests for ResourceTuner class"""

    def test_init(self):
        """Test tuner initialization"""
        tuner = ResourceTuner()
        assert tuner.strategy == TuningStrategy.BALANCED
        assert len(tuner.recommendations) == 0

    def test_set_strategy(self):
        """Test setting strategy"""
        tuner = ResourceTuner()
        tuner.set_strategy(TuningStrategy.AGGRESSIVE)
        assert tuner.strategy == TuningStrategy.AGGRESSIVE

    def test_analyze_critical(self):
        """Test analyzing critical resource"""
        tuner = ResourceTuner()
        tuner.monitor.set_limit(ResourceType.CPU, 80, 100)
        tuner.monitor.record_usage(ResourceType.CPU, 96)  # Critical
        recommendations = tuner.analyze()
        assert len(recommendations) > 0
        assert any(r.priority == 100 for r in recommendations)

    def test_analyze_over_utilized(self):
        """Test analyzing over-utilized resource"""
        tuner = ResourceTuner()
        tuner.monitor.set_limit(ResourceType.CPU, 80, 100)
        tuner.monitor.record_usage(ResourceType.CPU, 85)  # Over-utilized
        recommendations = tuner.analyze()
        assert len(recommendations) > 0

    def test_analyze_under_utilized(self):
        """Test analyzing under-utilized resource"""
        tuner = ResourceTuner()
        tuner.monitor.set_limit(ResourceType.CPU, 80, 100)
        tuner.monitor.record_usage(ResourceType.CPU, 10)  # Under-utilized
        recommendations = tuner.analyze()
        assert len(recommendations) > 0

    def test_apply_recommendation(self):
        """Test applying recommendation"""
        tuner = ResourceTuner()
        tuner.monitor.set_limit(ResourceType.CPU, 80, 100, auto_adjust=True)
        tuner.monitor.record_usage(ResourceType.CPU, 96)

        recommendations = tuner.analyze()
        applied = tuner.apply_recommendation(recommendations[0])
        assert applied is True

    def test_get_tuning_summary(self):
        """Test getting tuning summary"""
        tuner = ResourceTuner()
        tuner.monitor.set_limit(ResourceType.CPU, 80, 100)
        tuner.monitor.record_usage(ResourceType.CPU, 50)
        summary = tuner.get_tuning_summary()
        assert "strategy" in summary
        assert "resources" in summary


class TestThreadPoolTuner:
    """Tests for ThreadPoolTuner class"""

    def test_init(self):
        """Test thread pool tuner initialization"""
        tuner = ThreadPoolTuner()
        assert tuner.min_threads == 1
        assert tuner.max_threads == 100

    def test_calculate_optimal_threads_high_util(self):
        """Test calculating optimal threads with high utilization"""
        tuner = ThreadPoolTuner()
        optimal = tuner.calculate_optimal_threads(
            current_threads=10,
            current_utilization=0.9,
            avg_task_time_ms=100,
        )
        assert optimal > 10  # Should increase

    def test_calculate_optimal_threads_low_util(self):
        """Test calculating optimal threads with low utilization"""
        tuner = ThreadPoolTuner()
        optimal = tuner.calculate_optimal_threads(
            current_threads=10,
            current_utilization=0.05,
            avg_task_time_ms=100,
        )
        assert optimal < 10  # Should decrease


class TestConnectionPoolTuner:
    """Tests for ConnectionPoolTuner class"""

    def test_init(self):
        """Test connection pool tuner initialization"""
        tuner = ConnectionPoolTuner()
        assert tuner.min_connections == 5
        assert tuner.max_connections == 100

    def test_calculate_optimal_connections_with_wait(self):
        """Test calculating optimal connections with wait queue"""
        tuner = ConnectionPoolTuner()
        optimal = tuner.calculate_optimal_connections(
            current_connections=10,
            active_connections=10,
            wait_queue_size=5,
            avg_query_time_ms=50,
        )
        assert optimal > 10  # Should increase

    def test_calculate_optimal_connections_low_util(self):
        """Test calculating optimal connections with low utilization"""
        tuner = ConnectionPoolTuner()
        optimal = tuner.calculate_optimal_connections(
            current_connections=20,
            active_connections=4,  # 20% utilization
            wait_queue_size=0,
            avg_query_time_ms=50,
        )
        assert optimal < 20  # Should decrease
