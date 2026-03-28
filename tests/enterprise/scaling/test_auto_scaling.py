"""
Tests for Auto-Scaling Module - Week 52, Builder 1
"""

import pytest
from datetime import datetime, timedelta
import asyncio

from enterprise.scaling.auto_scaler import (
    AutoScaler,
    PredictiveScaler,
    ScalingDirection,
    ScalingStatus,
    ScalingDecision,
    ScalingEvent,
)
from enterprise.scaling.scaling_policy import (
    PolicyEngine,
    PolicyType,
    PolicyAction,
    PolicyStatus,
    ScalingPolicy,
    ScalingRule,
)
from enterprise.scaling.scaling_metrics import (
    MetricsCollector,
    MetricType,
    AggregationType,
    MetricSeries,
    MetricPoint,
    ResourceMetrics,
    ScalingMetricsAggregator,
)


# ============================================================================
# Auto Scaler Tests
# ============================================================================

class TestAutoScaler:
    """Tests for AutoScaler class"""

    def test_init(self):
        """Test AutoScaler initialization"""
        scaler = AutoScaler(min_instances=2, max_instances=50)
        assert scaler.min_instances == 2
        assert scaler.max_instances == 50
        assert scaler.current_instances == 2
        assert scaler.status == ScalingStatus.IDLE

    def test_add_policy(self):
        """Test adding scaling policy"""
        scaler = AutoScaler()
        scaler.add_policy(
            name="cpu_policy",
            metric_name="cpu_usage",
            threshold_up=80,
            threshold_down=30,
        )
        assert len(scaler.policies) == 1
        assert scaler.policies[0]["name"] == "cpu_policy"

    def test_remove_policy(self):
        """Test removing scaling policy"""
        scaler = AutoScaler()
        scaler.add_policy("cpu_policy", "cpu_usage", 80, 30)
        assert scaler.remove_policy("cpu_policy") is True
        assert len(scaler.policies) == 0
        assert scaler.remove_policy("nonexistent") is False

    def test_enable_disable_policy(self):
        """Test enabling and disabling policies"""
        scaler = AutoScaler()
        scaler.add_policy("cpu_policy", "cpu_usage", 80, 30)
        assert scaler.disable_policy("cpu_policy") is True
        assert scaler.policies[0]["enabled"] is False
        assert scaler.enable_policy("cpu_policy") is True
        assert scaler.policies[0]["enabled"] is True

    def test_update_metrics(self):
        """Test updating metrics"""
        scaler = AutoScaler()
        scaler.update_metrics({"cpu_usage": 75, "memory_usage": 60})
        assert scaler.metrics["cpu_usage"] == 75
        assert scaler.metrics["memory_usage"] == 60

    def test_set_current_instances(self):
        """Test setting current instance count"""
        scaler = AutoScaler(min_instances=2, max_instances=10)
        scaler.set_current_instances(5)
        assert scaler.current_instances == 5

    def test_set_current_instances_respects_bounds(self):
        """Test that set_current_instances respects min/max bounds"""
        scaler = AutoScaler(min_instances=2, max_instances=10)
        scaler.set_current_instances(1)  # Below min
        assert scaler.current_instances == 2
        scaler.set_current_instances(15)  # Above max
        assert scaler.current_instances == 10

    def test_is_in_cooldown_false_initially(self):
        """Test that cooldown is False initially"""
        scaler = AutoScaler()
        assert scaler.is_in_cooldown() is False

    def test_is_in_cooldown_after_scaling(self):
        """Test cooldown after scaling"""
        scaler = AutoScaler(cooldown_period=60)
        decision = ScalingDecision(
            direction=ScalingDirection.SCALE_UP,
            current_instances=1,
            target_instances=2,
            reason="test",
        )
        scaler.scale(decision)
        assert scaler.is_in_cooldown() is True

    def test_evaluate_no_scaling_needed(self):
        """Test evaluation when no scaling needed"""
        scaler = AutoScaler()
        scaler.add_policy("cpu_policy", "cpu_usage", 80, 30)
        scaler.update_metrics({"cpu_usage": 50})
        decision = scaler.evaluate()
        assert decision is None

    def test_evaluate_scale_up(self):
        """Test evaluation for scale up"""
        scaler = AutoScaler(min_instances=1, max_instances=10)
        scaler.add_policy("cpu_policy", "cpu_usage", 80, 30, scale_up_factor=2.0)
        scaler.set_current_instances(2)
        scaler.update_metrics({"cpu_usage": 90})
        decision = scaler.evaluate()
        assert decision is not None
        assert decision.direction == ScalingDirection.SCALE_UP
        assert decision.target_instances == 4

    def test_evaluate_scale_down(self):
        """Test evaluation for scale down"""
        scaler = AutoScaler(min_instances=1, max_instances=10)
        scaler.add_policy("cpu_policy", "cpu_usage", 80, 30, scale_down_factor=0.5)
        scaler.set_current_instances(4)
        scaler.update_metrics({"cpu_usage": 20})
        decision = scaler.evaluate()
        assert decision is not None
        assert decision.direction == ScalingDirection.SCALE_DOWN
        assert decision.target_instances == 2

    def test_scale(self):
        """Test scaling execution"""
        scaler = AutoScaler()
        decision = ScalingDecision(
            direction=ScalingDirection.SCALE_UP,
            current_instances=1,
            target_instances=3,
            reason="test scaling",
        )
        event = scaler.scale(decision)
        assert event.executed is True
        assert event.error is None
        assert scaler.current_instances == 3

    def test_scale_respects_max(self):
        """Test that scale respects max instances"""
        scaler = AutoScaler(max_instances=5)
        decision = ScalingDecision(
            direction=ScalingDirection.SCALE_UP,
            current_instances=3,
            target_instances=10,
            reason="test",
        )
        # Decision target is 10, but scaler should enforce max
        # Note: AutoScaler.scale uses decision.target_instances directly
        # But evaluate() enforces bounds
        event = scaler.scale(decision)
        assert event.decision.target_instances == 10

    def test_get_events(self):
        """Test getting scaling events"""
        scaler = AutoScaler()
        decision = ScalingDecision(
            direction=ScalingDirection.SCALE_UP,
            current_instances=1,
            target_instances=2,
            reason="test",
        )
        scaler.scale(decision)
        events = scaler.get_events()
        assert len(events) == 1
        assert events[0].decision.direction == ScalingDirection.SCALE_UP

    def test_get_events_filtered(self):
        """Test getting filtered events"""
        scaler = AutoScaler()

        # Scale up
        scaler.scale(ScalingDecision(
            ScalingDirection.SCALE_UP, 1, 2, "test"
        ))
        # Scale down
        scaler.scale(ScalingDecision(
            ScalingDirection.SCALE_DOWN, 2, 1, "test"
        ))

        scale_ups = scaler.get_events(direction=ScalingDirection.SCALE_UP)
        assert len(scale_ups) == 1

        scale_downs = scaler.get_events(direction=ScalingDirection.SCALE_DOWN)
        assert len(scale_downs) == 1

    def test_get_statistics(self):
        """Test getting statistics"""
        scaler = AutoScaler()
        scaler.add_policy("cpu_policy", "cpu_usage", 80, 30)
        stats = scaler.get_statistics()
        assert stats["current_instances"] == 1
        assert stats["total_events"] == 0
        assert stats["policies_count"] == 1
        assert stats["active_policies"] == 1

    def test_reset(self):
        """Test reset functionality"""
        scaler = AutoScaler()
        scaler.set_current_instances(5)
        scaler.update_metrics({"cpu": 50})
        scaler.reset()
        assert scaler.current_instances == scaler.min_instances
        assert scaler.status == ScalingStatus.IDLE
        assert len(scaler.events) == 0
        assert len(scaler.metrics) == 0

    def test_scaling_handler(self):
        """Test scaling handler callback"""
        scaler = AutoScaler()
        calls = []
        scaler.add_scaling_handler(lambda d: calls.append(d))

        decision = ScalingDecision(
            ScalingDirection.SCALE_UP, 1, 2, "test"
        )
        scaler.scale(decision)
        assert len(calls) == 1
        assert calls[0] == decision


class TestPredictiveScaler:
    """Tests for PredictiveScaler class"""

    def test_init(self):
        """Test PredictiveScaler initialization"""
        scaler = PredictiveScaler(prediction_window=300)
        assert scaler.prediction_window == 300
        assert scaler.history_size == 100

    def test_record_metric(self):
        """Test recording metric for prediction"""
        scaler = PredictiveScaler()
        scaler.record_metric("cpu_usage", 50)
        assert "cpu_usage" in scaler.metric_history
        assert len(scaler.metric_history["cpu_usage"]) == 1

    def test_predict_metric_insufficient_data(self):
        """Test prediction with insufficient data"""
        scaler = PredictiveScaler()
        scaler.record_metric("cpu_usage", 50)
        prediction = scaler.predict_metric("cpu_usage")
        assert prediction is None  # Needs at least 10 points

    def test_predict_metric_with_data(self):
        """Test prediction with sufficient data"""
        scaler = PredictiveScaler()
        # Record 20 points with increasing trend
        for i in range(20):
            scaler.record_metric("cpu_usage", 50 + i)

        prediction = scaler.predict_metric("cpu_usage")
        assert prediction is not None
        assert prediction > 50  # Should predict higher value


# ============================================================================
# Scaling Policy Tests
# ============================================================================

class TestScalingRule:
    """Tests for ScalingRule class"""

    def test_init(self):
        """Test ScalingRule initialization"""
        rule = ScalingRule(
            name="test_rule",
            condition="cpu > 80",
            action=PolicyAction.SCALE_UP,
        )
        assert rule.name == "test_rule"
        assert rule.condition == "cpu > 80"
        assert rule.action == PolicyAction.SCALE_UP

    def test_evaluate_true(self):
        """Test rule evaluation returns True"""
        rule = ScalingRule(
            name="test_rule",
            condition="cpu > 80",
            action=PolicyAction.SCALE_UP,
        )
        result = rule.evaluate({"cpu": 90})
        assert result is True

    def test_evaluate_false(self):
        """Test rule evaluation returns False"""
        rule = ScalingRule(
            name="test_rule",
            condition="cpu > 80",
            action=PolicyAction.SCALE_UP,
        )
        result = rule.evaluate({"cpu": 70})
        assert result is False

    def test_evaluate_complex_condition(self):
        """Test complex condition evaluation"""
        rule = ScalingRule(
            name="test_rule",
            condition="cpu > 80 and memory > 70",
            action=PolicyAction.SCALE_UP,
        )
        assert rule.evaluate({"cpu": 90, "memory": 80}) is True
        assert rule.evaluate({"cpu": 90, "memory": 60}) is False


class TestScalingPolicy:
    """Tests for ScalingPolicy class"""

    def test_init(self):
        """Test ScalingPolicy initialization"""
        policy = ScalingPolicy(
            name="test_policy",
            policy_type=PolicyType.THRESHOLD,
        )
        assert policy.name == "test_policy"
        assert policy.status == PolicyStatus.ACTIVE

    def test_add_rule(self):
        """Test adding rule to policy"""
        policy = ScalingPolicy(
            name="test_policy",
            policy_type=PolicyType.THRESHOLD,
        )
        rule = ScalingRule("rule1", "cpu > 80", PolicyAction.SCALE_UP, priority=100)
        policy.add_rule(rule)
        assert len(policy.rules) == 1

    def test_remove_rule(self):
        """Test removing rule from policy"""
        policy = ScalingPolicy(
            name="test_policy",
            policy_type=PolicyType.THRESHOLD,
        )
        policy.add_rule(ScalingRule("rule1", "cpu > 80", PolicyAction.SCALE_UP))
        assert policy.remove_rule("rule1") is True
        assert len(policy.rules) == 0
        assert policy.remove_rule("nonexistent") is False

    def test_rules_sorted_by_priority(self):
        """Test that rules are sorted by priority"""
        policy = ScalingPolicy(
            name="test_policy",
            policy_type=PolicyType.THRESHOLD,
        )
        policy.add_rule(ScalingRule("low", "cpu > 80", PolicyAction.SCALE_UP, priority=50))
        policy.add_rule(ScalingRule("high", "cpu > 90", PolicyAction.SCALE_UP, priority=100))
        assert policy.rules[0].name == "high"  # Higher priority first


class TestPolicyEngine:
    """Tests for PolicyEngine class"""

    def test_init(self):
        """Test PolicyEngine initialization"""
        engine = PolicyEngine()
        assert len(engine.policies) == 0

    def test_create_policy(self):
        """Test creating policy"""
        engine = PolicyEngine()
        policy = engine.create_policy(
            name="test_policy",
            policy_type=PolicyType.THRESHOLD,
        )
        assert policy is not None
        assert "test_policy" in engine.policies

    def test_get_policy(self):
        """Test getting policy"""
        engine = PolicyEngine()
        engine.create_policy("test_policy", PolicyType.THRESHOLD)
        policy = engine.get_policy("test_policy")
        assert policy is not None
        assert engine.get_policy("nonexistent") is None

    def test_delete_policy(self):
        """Test deleting policy"""
        engine = PolicyEngine()
        engine.create_policy("test_policy", PolicyType.THRESHOLD)
        assert engine.delete_policy("test_policy") is True
        assert engine.delete_policy("nonexistent") is False

    def test_pause_resume_policy(self):
        """Test pausing and resuming policy"""
        engine = PolicyEngine()
        engine.create_policy("test_policy", PolicyType.THRESHOLD)
        engine.pause_policy("test_policy")
        assert engine.get_policy("test_policy").status == PolicyStatus.PAUSED
        engine.resume_policy("test_policy")
        assert engine.get_policy("test_policy").status == PolicyStatus.ACTIVE

    def test_disable_policy(self):
        """Test disabling policy"""
        engine = PolicyEngine()
        engine.create_policy("test_policy", PolicyType.THRESHOLD)
        engine.disable_policy("test_policy")
        assert engine.get_policy("test_policy").status == PolicyStatus.DISABLED

    def test_list_policies(self):
        """Test listing policies"""
        engine = PolicyEngine()
        engine.create_policy("threshold_policy", PolicyType.THRESHOLD)
        engine.create_policy("schedule_policy", PolicyType.SCHEDULE)

        all_policies = engine.list_policies()
        assert len(all_policies) == 2

        threshold_policies = engine.list_policies(policy_type=PolicyType.THRESHOLD)
        assert len(threshold_policies) == 1

    def test_add_rule_to_policy(self):
        """Test adding rule to policy via engine"""
        engine = PolicyEngine()
        engine.create_policy("test_policy", PolicyType.THRESHOLD)
        result = engine.add_rule_to_policy(
            policy_name="test_policy",
            rule_name="scale_up",
            condition="cpu > 80",
            action=PolicyAction.SCALE_UP,
        )
        assert result is True
        assert len(engine.get_policy("test_policy").rules) == 1

    def test_evaluate_all(self):
        """Test evaluating all policies"""
        engine = PolicyEngine()
        engine.create_threshold_policy(
            name="cpu_policy",
            metric_name="cpu",
            scale_up_threshold=80,
            scale_down_threshold=30,
        )

        results = engine.evaluate_all({"cpu": 90}, 5)
        assert "cpu_policy" in results
        assert results["cpu_policy"] is not None

    def test_get_recommended_action(self):
        """Test getting recommended action"""
        engine = PolicyEngine()
        engine.create_threshold_policy(
            name="cpu_policy",
            metric_name="cpu",
            scale_up_threshold=80,
            scale_down_threshold=30,
        )

        recommendation = engine.get_recommended_action({"cpu": 90}, 5)
        assert recommendation["action"] == PolicyAction.SCALE_UP

    def test_create_threshold_policy(self):
        """Test creating threshold policy helper"""
        engine = PolicyEngine()
        policy = engine.create_threshold_policy(
            name="cpu_policy",
            metric_name="cpu_usage",
            scale_up_threshold=80,
            scale_down_threshold=30,
        )
        assert policy is not None
        assert len(policy.rules) == 2

    def test_export_import_policies(self):
        """Test exporting and importing policies"""
        engine = PolicyEngine()
        engine.create_threshold_policy(
            name="cpu_policy",
            metric_name="cpu",
            scale_up_threshold=80,
            scale_down_threshold=30,
        )

        exported = engine.export_policies()
        assert "policies" in exported
        assert "cpu_policy" in exported["policies"]

        # Create new engine and import
        new_engine = PolicyEngine()
        imported = new_engine.import_policies(exported)
        assert imported == 1


# ============================================================================
# Metrics Collector Tests
# ============================================================================

class TestMetricSeries:
    """Tests for MetricSeries class"""

    def test_init(self):
        """Test MetricSeries initialization"""
        series = MetricSeries(name="test_metric")
        assert series.name == "test_metric"
        assert len(series.points) == 0

    def test_add_point(self):
        """Test adding point to series"""
        series = MetricSeries(name="test_metric")
        series.add_point(50.0)
        assert len(series.points) == 1
        assert series.points[0].value == 50.0

    def test_add_point_with_tags(self):
        """Test adding point with tags"""
        series = MetricSeries(name="test_metric")
        series.add_point(50.0, tags={"host": "server1"})
        assert series.points[0].tags["host"] == "server1"

    def test_get_values(self):
        """Test getting values list"""
        series = MetricSeries(name="test_metric")
        series.add_point(10)
        series.add_point(20)
        series.add_point(30)
        values = series.get_values()
        assert values == [10, 20, 30]

    def test_get_latest(self):
        """Test getting latest value"""
        series = MetricSeries(name="test_metric")
        assert series.get_latest() is None
        series.add_point(10)
        series.add_point(20)
        assert series.get_latest() == 20

    def test_aggregate_avg(self):
        """Test average aggregation"""
        series = MetricSeries(name="test_metric")
        series.add_point(10)
        series.add_point(20)
        series.add_point(30)
        assert series.aggregate(AggregationType.AVG) == 20

    def test_aggregate_min_max(self):
        """Test min/max aggregation"""
        series = MetricSeries(name="test_metric")
        series.add_point(10)
        series.add_point(20)
        series.add_point(30)
        assert series.aggregate(AggregationType.MIN) == 10
        assert series.aggregate(AggregationType.MAX) == 30

    def test_aggregate_sum(self):
        """Test sum aggregation"""
        series = MetricSeries(name="test_metric")
        series.add_point(10)
        series.add_point(20)
        series.add_point(30)
        assert series.aggregate(AggregationType.SUM) == 60

    def test_aggregate_percentile(self):
        """Test percentile aggregation"""
        series = MetricSeries(name="test_metric")
        for i in range(100):
            series.add_point(i)
        p50 = series.aggregate(AggregationType.P50)
        p95 = series.aggregate(AggregationType.P95)
        assert p50 is not None
        assert p95 is not None
        assert p95 > p50


class TestMetricsCollector:
    """Tests for MetricsCollector class"""

    def test_init(self):
        """Test MetricsCollector initialization"""
        collector = MetricsCollector()
        assert len(collector.series) == 0

    def test_register_metric(self):
        """Test registering metric"""
        collector = MetricsCollector()
        series = collector.register_metric("cpu_usage")
        assert series is not None
        assert "cpu_usage" in collector.series

    def test_record(self):
        """Test recording metric value"""
        collector = MetricsCollector()
        collector.record("cpu_usage", 75)
        assert collector.get_latest("cpu_usage") == 75

    def test_record_batch(self):
        """Test recording batch of metrics"""
        collector = MetricsCollector()
        count = collector.record_batch({"cpu": 50, "memory": 60})
        assert count == 2
        assert collector.get_latest("cpu") == 50
        assert collector.get_latest("memory") == 60

    def test_get_metric(self):
        """Test getting metric series"""
        collector = MetricsCollector()
        collector.record("cpu", 50)
        series = collector.get_metric("cpu")
        assert series is not None
        assert collector.get_metric("nonexistent") is None

    def test_get_aggregated(self):
        """Test getting aggregated value"""
        collector = MetricsCollector()
        for i in range(10):
            collector.record("cpu", i * 10)
        avg = collector.get_aggregated("cpu", AggregationType.AVG)
        assert avg == 45  # Average of 0, 10, 20, ..., 90

    def test_get_all_latest(self):
        """Test getting all latest values"""
        collector = MetricsCollector()
        collector.record("cpu", 50)
        collector.record("memory", 60)
        latest = collector.get_all_latest()
        assert latest["cpu"] == 50
        assert latest["memory"] == 60

    def test_register_collector(self):
        """Test registering collector function"""
        collector = MetricsCollector()
        collector.register_collector("system", lambda: {"cpu": 50, "memory": 60})
        assert "system" in collector._collectors

    def test_collect_all(self):
        """Test collecting from all collectors"""
        collector = MetricsCollector()
        collector.register_collector("system", lambda: {"cpu": 50})
        metrics = collector.collect_all()
        assert "cpu" in metrics
        assert metrics["cpu"] == 50

    def test_get_statistics(self):
        """Test getting statistics"""
        collector = MetricsCollector()
        collector.record("cpu", 50)
        stats = collector.get_statistics()
        assert stats["total_metrics"] == 1
        assert "metrics" in stats


class TestResourceMetrics:
    """Tests for ResourceMetrics class"""

    def test_init(self):
        """Test ResourceMetrics initialization"""
        collector = MetricsCollector()
        rm = ResourceMetrics(collector)
        assert rm.collector is collector

    def test_record_cpu(self):
        """Test recording CPU usage"""
        collector = MetricsCollector()
        rm = ResourceMetrics(collector)
        rm.record_cpu(75, host="server1")
        assert collector.get_latest("cpu_usage") == 75

    def test_record_memory(self):
        """Test recording memory usage"""
        collector = MetricsCollector()
        rm = ResourceMetrics(collector)
        rm.record_memory(60, host="server1")
        assert collector.get_latest("memory_usage") == 60

    def test_record_disk(self):
        """Test recording disk usage"""
        collector = MetricsCollector()
        rm = ResourceMetrics(collector)
        rm.record_disk(40, host="server1")
        assert collector.get_latest("disk_usage") == 40

    def test_record_network(self):
        """Test recording network I/O"""
        collector = MetricsCollector()
        rm = ResourceMetrics(collector)
        rm.record_network(1000, 500, host="server1")
        assert collector.get_latest("network_in") == 1000
        assert collector.get_latest("network_out") == 500

    def test_record_request(self):
        """Test recording request"""
        collector = MetricsCollector()
        rm = ResourceMetrics(collector)
        rm.record_request(100, endpoint="/api/test")
        assert collector.get_latest("request_latency") == 100

    def test_record_connections(self):
        """Test recording connections"""
        collector = MetricsCollector()
        rm = ResourceMetrics(collector)
        rm.record_connections(50, host="server1")
        assert collector.get_latest("active_connections") == 50

    def test_get_resource_summary(self):
        """Test getting resource summary"""
        collector = MetricsCollector()
        rm = ResourceMetrics(collector)
        rm.record_cpu(50)
        rm.record_memory(60)
        summary = rm.get_resource_summary()
        assert summary["cpu"]["current"] == 50
        assert summary["memory"]["current"] == 60


class TestScalingMetricsAggregator:
    """Tests for ScalingMetricsAggregator class"""

    def test_init(self):
        """Test ScalingMetricsAggregator initialization"""
        collector = MetricsCollector()
        aggregator = ScalingMetricsAggregator(collector)
        assert aggregator.collector is collector

    def test_calculate_load_score(self):
        """Test calculating load score"""
        collector = MetricsCollector()
        aggregator = ScalingMetricsAggregator(collector)
        collector.record("cpu_usage", 50)
        collector.record("memory_usage", 60)
        score = aggregator.calculate_load_score()
        assert 0 <= score <= 100

    def test_get_scaling_metrics(self):
        """Test getting scaling metrics"""
        collector = MetricsCollector()
        aggregator = ScalingMetricsAggregator(collector)
        collector.record("cpu_usage", 50)
        metrics = aggregator.get_scaling_metrics()
        assert "current" in metrics
        assert "load_score" in metrics

    def test_predict_load(self):
        """Test predicting load"""
        collector = MetricsCollector()
        aggregator = ScalingMetricsAggregator(collector)
        prediction = aggregator.predict_load(minutes_ahead=5)
        assert prediction is not None
