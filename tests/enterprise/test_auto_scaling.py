# Tests for Builder 1 - Auto Scaling Engine
# Week 52: auto_scaler.py, scaling_policy.py, scaling_metrics.py

import pytest
from datetime import datetime, timedelta
import time

from enterprise.scaling.auto_scaler import (
    AutoScaler, ScalingTarget, ScalingEvent, ScalingAction, ScalingStatus
)
from enterprise.scaling.scaling_policy import (
    ScalingPolicyManager, ScalingPolicy, ScalingRule,
    PolicyType, PolicyStatus, ComparisonOperator
)
from enterprise.scaling.scaling_metrics import (
    ScalingMetrics, MetricDefinition, MetricDataPoint,
    MetricAggregation, MetricPriority
)


# =============================================================================
# AUTO SCALER TESTS
# =============================================================================

class TestAutoScaler:
    """Tests for AutoScaler class"""

    def test_init(self):
        """Test scaler initialization"""
        scaler = AutoScaler()
        assert scaler is not None
        metrics = scaler.get_metrics()
        assert metrics["total_scale_events"] == 0

    def test_register_target(self):
        """Test registering a scaling target"""
        scaler = AutoScaler()
        target = scaler.register_target(
            name="web-servers",
            resource_type="ec2",
            min_capacity=2,
            max_capacity=20,
            initial_capacity=5
        )
        assert target.name == "web-servers"
        assert target.resource_type == "ec2"
        assert target.min_capacity == 2
        assert target.max_capacity == 20
        assert target.current_capacity == 5

    def test_deregister_target(self):
        """Test deregistering a target"""
        scaler = AutoScaler()
        target = scaler.register_target("web", "ec2")
        result = scaler.deregister_target(target.id)
        assert result is True
        assert scaler.get_target(target.id) is None

    def test_evaluate_scaling_scale_up(self):
        """Test evaluating scale up"""
        scaler = AutoScaler()
        target = scaler.register_target("web", "ec2", min_capacity=1, max_capacity=10)
        policies = [
            {
                "metric": "cpu",
                "threshold": 80,
                "comparison": "greater",
                "action": ScalingAction.SCALE_UP,
                "scale_by": 2,
                "reason": "High CPU"
            }
        ]

        event = scaler.evaluate_scaling(target.id, {"cpu": 90}, policies)
        assert event is not None
        assert event.action == ScalingAction.SCALE_UP
        assert event.target_capacity == 3  # 1 + 2

    def test_evaluate_scaling_scale_down(self):
        """Test evaluating scale down"""
        scaler = AutoScaler()
        target = scaler.register_target("web", "ec2", min_capacity=1, max_capacity=10, initial_capacity=5)
        policies = [
            {
                "metric": "cpu",
                "threshold": 20,
                "comparison": "less",
                "action": ScalingAction.SCALE_DOWN,
                "scale_by": 2,
                "reason": "Low CPU"
            }
        ]

        event = scaler.evaluate_scaling(target.id, {"cpu": 15}, policies)
        assert event is not None
        assert event.action == ScalingAction.SCALE_DOWN
        assert event.target_capacity == 3  # 5 - 2

    def test_evaluate_scaling_no_action(self):
        """Test when no scaling needed"""
        scaler = AutoScaler()
        target = scaler.register_target("web", "ec2")
        policies = [
            {
                "metric": "cpu",
                "threshold": 80,
                "comparison": "greater",
                "action": ScalingAction.SCALE_UP,
                "scale_by": 1
            }
        ]

        event = scaler.evaluate_scaling(target.id, {"cpu": 50}, policies)
        assert event is None

    def test_evaluate_scaling_respects_min(self):
        """Test scaling respects minimum"""
        scaler = AutoScaler()
        target = scaler.register_target("web", "ec2", min_capacity=2, initial_capacity=2)
        policies = [
            {
                "metric": "cpu",
                "threshold": 20,
                "comparison": "less",
                "action": ScalingAction.SCALE_DOWN,
                "scale_by": 3,
                "reason": "Low CPU"
            }
        ]

        event = scaler.evaluate_scaling(target.id, {"cpu": 10}, policies)
        assert event.target_capacity == 2  # Can't go below min

    def test_evaluate_scaling_respects_max(self):
        """Test scaling respects maximum"""
        scaler = AutoScaler()
        target = scaler.register_target("web", "ec2", max_capacity=5, initial_capacity=4)
        policies = [
            {
                "metric": "cpu",
                "threshold": 80,
                "comparison": "greater",
                "action": ScalingAction.SCALE_UP,
                "scale_by": 5,
                "reason": "High CPU"
            }
        ]

        event = scaler.evaluate_scaling(target.id, {"cpu": 95}, policies)
        assert event.target_capacity == 5  # Can't exceed max

    def test_complete_scaling(self):
        """Test completing scaling event"""
        scaler = AutoScaler()
        target = scaler.register_target("web", "ec2", initial_capacity=2)
        policies = [{"metric": "cpu", "threshold": 80, "comparison": "greater",
                     "action": ScalingAction.SCALE_UP, "scale_by": 2}]

        event = scaler.evaluate_scaling(target.id, {"cpu": 90}, policies)
        result = scaler.complete_scaling(target.id, event.id, success=True, cooldown_seconds=60)

        assert result is True
        assert event.status == "completed"
        assert target.current_capacity == 4
        assert target.status == ScalingStatus.COOLDOWN

    def test_get_target_by_name(self):
        """Test getting target by name"""
        scaler = AutoScaler()
        scaler.register_target("web-servers", "ec2")
        target = scaler.get_target_by_name("web-servers")
        assert target is not None

    def test_get_targets_by_type(self):
        """Test getting targets by type"""
        scaler = AutoScaler()
        scaler.register_target("web1", "ec2")
        scaler.register_target("web2", "ec2")
        scaler.register_target("db1", "rds")

        targets = scaler.get_targets_by_type("ec2")
        assert len(targets) == 2

    def test_force_scale(self):
        """Test forced scaling"""
        scaler = AutoScaler()
        target = scaler.register_target("web", "ec2", initial_capacity=5)

        event = scaler.force_scale(target.id, ScalingAction.SCALE_UP, 3, "Manual")
        assert event is not None
        assert event.target_capacity == 8

    def test_enable_disable_target(self):
        """Test enabling and disabling target"""
        scaler = AutoScaler()
        target = scaler.register_target("web", "ec2")

        scaler.disable_target(target.id)
        assert target.status == ScalingStatus.DISABLED

        scaler.enable_target(target.id)
        assert target.status == ScalingStatus.IDLE

    def test_get_metrics(self):
        """Test getting scaler metrics"""
        scaler = AutoScaler()
        scaler.register_target("web", "ec2")

        metrics = scaler.get_metrics()
        assert metrics["total_scale_events"] == 0


# =============================================================================
# SCALING POLICY TESTS
# =============================================================================

class TestScalingPolicy:
    """Tests for ScalingPolicyManager class"""

    def test_init(self):
        """Test policy manager initialization"""
        manager = ScalingPolicyManager()
        assert manager is not None
        metrics = manager.get_metrics()
        assert metrics["total_policies"] == 0

    def test_create_policy(self):
        """Test creating a policy"""
        manager = ScalingPolicyManager()
        policy = manager.create_policy(
            name="web-scale-policy",
            policy_type=PolicyType.THRESHOLD,
            target_id="target-1",
            min_capacity=2,
            max_capacity=20
        )
        assert policy.name == "web-scale-policy"
        assert policy.policy_type == PolicyType.THRESHOLD
        assert policy.status == PolicyStatus.ACTIVE

    def test_add_rule(self):
        """Test adding a rule"""
        manager = ScalingPolicyManager()
        policy = manager.create_policy("test", PolicyType.THRESHOLD, "target-1")

        rule = manager.add_rule(
            policy_id=policy.id,
            name="high-cpu",
            metric_name="cpu_percent",
            operator=ComparisonOperator.GREATER_THAN,
            threshold=80.0,
            action="scale_up",
            scale_by=2
        )
        assert rule is not None
        assert rule.name == "high-cpu"
        assert len(policy.rules) == 1

    def test_remove_rule(self):
        """Test removing a rule"""
        manager = ScalingPolicyManager()
        policy = manager.create_policy("test", PolicyType.THRESHOLD, "target-1")
        rule = manager.add_rule(policy.id, "rule1", "cpu", ComparisonOperator.GREATER_THAN, 80)

        result = manager.remove_rule(policy.id, rule.id)
        assert result is True
        assert len(policy.rules) == 0

    def test_update_policy(self):
        """Test updating policy"""
        manager = ScalingPolicyManager()
        policy = manager.create_policy("test", PolicyType.THRESHOLD, "target-1")

        result = manager.update_policy(policy.id, min_capacity=5, max_capacity=50)
        assert result is True
        assert policy.min_capacity == 5
        assert policy.max_capacity == 50

    def test_activate_deactivate_policy(self):
        """Test activating and deactivating policy"""
        manager = ScalingPolicyManager()
        policy = manager.create_policy("test", PolicyType.THRESHOLD, "target-1")

        manager.deactivate_policy(policy.id)
        assert policy.status == PolicyStatus.INACTIVE

        manager.activate_policy(policy.id)
        assert policy.status == PolicyStatus.ACTIVE

    def test_get_policies_by_target(self):
        """Test getting policies by target"""
        manager = ScalingPolicyManager()
        manager.create_policy("policy1", PolicyType.THRESHOLD, "target-1")
        manager.create_policy("policy2", PolicyType.THRESHOLD, "target-1")
        manager.create_policy("policy3", PolicyType.THRESHOLD, "target-2")

        policies = manager.get_policies_by_target("target-1")
        assert len(policies) == 2

    def test_get_active_policies(self):
        """Test getting active policies"""
        manager = ScalingPolicyManager()
        p1 = manager.create_policy("policy1", PolicyType.THRESHOLD, "target-1")
        manager.create_policy("policy2", PolicyType.THRESHOLD, "target-1")
        manager.deactivate_policy(p1.id)

        active = manager.get_active_policies()
        assert len(active) == 1

    def test_evaluate_rules_triggered(self):
        """Test evaluating rules when triggered"""
        manager = ScalingPolicyManager()
        policy = manager.create_policy("test", PolicyType.THRESHOLD, "target-1")
        manager.add_rule(policy.id, "high-cpu", "cpu", ComparisonOperator.GREATER_THAN, 80, "scale_up")

        results = manager.evaluate_rules(policy.id, {"cpu": 90})
        assert len(results) == 1
        assert results[0]["triggered"] is True

    def test_evaluate_rules_not_triggered(self):
        """Test evaluating rules when not triggered"""
        manager = ScalingPolicyManager()
        policy = manager.create_policy("test", PolicyType.THRESHOLD, "target-1")
        manager.add_rule(policy.id, "high-cpu", "cpu", ComparisonOperator.GREATER_THAN, 80, "scale_up")

        results = manager.evaluate_rules(policy.id, {"cpu": 50})
        assert len(results) == 1
        assert results[0]["triggered"] is False

    def test_delete_policy(self):
        """Test deleting a policy"""
        manager = ScalingPolicyManager()
        policy = manager.create_policy("test", PolicyType.THRESHOLD, "target-1")
        manager.add_rule(policy.id, "rule1", "cpu", ComparisonOperator.GREATER_THAN, 80)

        result = manager.delete_policy(policy.id)
        assert result is True
        assert manager.get_policy(policy.id) is None

    def test_get_metrics(self):
        """Test getting metrics"""
        manager = ScalingPolicyManager()
        manager.create_policy("test", PolicyType.THRESHOLD, "target-1")

        metrics = manager.get_metrics()
        assert metrics["total_policies"] == 1


# =============================================================================
# SCALING METRICS TESTS
# =============================================================================

class TestScalingMetrics:
    """Tests for ScalingMetrics class"""

    def test_init(self):
        """Test metrics initialization"""
        metrics = ScalingMetrics()
        assert metrics is not None
        stats = metrics.get_metrics()
        assert stats["total_definitions"] == 0

    def test_register_metric(self):
        """Test registering a metric"""
        sm = ScalingMetrics()
        definition = sm.register_metric(
            name="cpu_percent",
            display_name="CPU Percentage",
            unit="percent",
            aggregation=MetricAggregation.AVERAGE,
            priority=MetricPriority.HIGH
        )
        assert definition.name == "cpu_percent"
        assert definition.unit == "percent"
        assert definition.aggregation == MetricAggregation.AVERAGE

    def test_record_metric(self):
        """Test recording a metric"""
        sm = ScalingMetrics()
        sm.register_metric("cpu_percent")
        point = sm.record_metric("cpu_percent", 75.5, "percent")

        assert point is not None
        assert point.value == 75.5

    def test_record_nonexistent_metric(self):
        """Test recording non-existent metric"""
        sm = ScalingMetrics()
        point = sm.record_metric("nonexistent", 50.0)
        assert point is None

    def test_get_aggregated_value_average(self):
        """Test getting average value"""
        sm = ScalingMetrics()
        sm.register_metric("cpu", aggregation=MetricAggregation.AVERAGE)
        sm.record_metric("cpu", 50)
        sm.record_metric("cpu", 60)
        sm.record_metric("cpu", 70)

        avg = sm.get_aggregated_value("cpu")
        assert avg == 60.0

    def test_get_aggregated_value_maximum(self):
        """Test getting maximum value"""
        sm = ScalingMetrics()
        sm.register_metric("cpu", aggregation=MetricAggregation.MAXIMUM)
        sm.record_metric("cpu", 50)
        sm.record_metric("cpu", 90)
        sm.record_metric("cpu", 70)

        max_val = sm.get_aggregated_value("cpu")
        assert max_val == 90.0

    def test_get_statistics(self):
        """Test getting statistics"""
        sm = ScalingMetrics()
        sm.register_metric("cpu")
        for i in range(10):
            sm.record_metric("cpu", float(i * 10))

        stats = sm.get_statistics("cpu")
        assert stats["count"] == 10
        assert stats["minimum"] == 0.0
        assert stats["maximum"] == 90.0
        assert stats["average"] == 45.0

    def test_get_percentile(self):
        """Test getting percentile"""
        sm = ScalingMetrics()
        sm.register_metric("cpu")
        for i in range(100):
            sm.record_metric("cpu", float(i))

        p95 = sm.get_percentile("cpu", 95)
        assert p95 >= 90.0

    def test_get_rate(self):
        """Test getting rate of change"""
        sm = ScalingMetrics()
        sm.register_metric("requests")
        sm.record_metric("requests", 100)
        time.sleep(0.1)
        sm.record_metric("requests", 200)

        rate = sm.get_rate("requests", minutes=5)
        assert rate > 0

    def test_get_data_points_since(self):
        """Test getting data points since time"""
        sm = ScalingMetrics()
        sm.register_metric("cpu")
        sm.record_metric("cpu", 50)
        sm.record_metric("cpu", 60)

        points = sm.get_data_points("cpu", since=datetime.utcnow() - timedelta(minutes=5))
        assert len(points) == 2

    def test_get_metrics_by_priority(self):
        """Test getting metrics by priority"""
        sm = ScalingMetrics()
        sm.register_metric("cpu", priority=MetricPriority.HIGH)
        sm.register_metric("memory", priority=MetricPriority.HIGH)
        sm.register_metric("disk", priority=MetricPriority.NORMAL)

        high_priority = sm.get_metrics_by_priority(MetricPriority.HIGH)
        assert len(high_priority) == 2

    def test_cleanup_old_data(self):
        """Test cleanup of old data"""
        sm = ScalingMetrics()
        sm.register_metric("cpu")
        sm.record_metric("cpu", 50)
        removed = sm.cleanup_old_data(hours=0)
        assert removed >= 1

    def test_delete_metric(self):
        """Test deleting a metric"""
        sm = ScalingMetrics()
        sm.register_metric("cpu")
        sm.record_metric("cpu", 50)

        result = sm.delete_metric("cpu")
        assert result is True

    def test_get_metrics(self):
        """Test getting metrics stats"""
        sm = ScalingMetrics()
        sm.register_metric("cpu")
        sm.record_metric("cpu", 50)
        sm.record_metric("cpu", 60)

        metrics = sm.get_metrics()
        assert metrics["total_definitions"] == 1
        assert metrics["total_data_points"] == 2
