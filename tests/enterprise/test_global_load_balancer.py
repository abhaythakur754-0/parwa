# Tests for Builder 1 - Global Load Balancer
# Week 51: global_load_balancer.py, traffic_router.py, latency_optimizer.py

import pytest
from datetime import datetime, timedelta
import time

from enterprise.global_infra.global_load_balancer import (
    GlobalLoadBalancer, BackendServer, LoadBalancerConfig,
    BalancingStrategy, RegionHealth
)
from enterprise.global_infra.traffic_router import (
    TrafficRouter, RoutingRule, RoutingDecision, RoutingRuleType
)
from enterprise.global_infra.latency_optimizer import (
    LatencyOptimizer, LatencyMeasurement, RegionLatency, OptimizationStrategy
)


# =============================================================================
# GLOBAL LOAD BALANCER TESTS
# =============================================================================

class TestGlobalLoadBalancer:
    """Tests for GlobalLoadBalancer class"""

    def test_init(self):
        """Test load balancer initialization"""
        lb = GlobalLoadBalancer()
        assert lb is not None
        metrics = lb.get_metrics()
        assert metrics["total_requests"] == 0

    def test_create_config(self):
        """Test creating a configuration"""
        lb = GlobalLoadBalancer()
        config = lb.create_config(
            name="main-lb",
            strategy=BalancingStrategy.ROUND_ROBIN,
            health_check_interval=30
        )
        assert config.name == "main-lb"
        assert config.strategy == BalancingStrategy.ROUND_ROBIN

    def test_add_server(self):
        """Test adding a server"""
        lb = GlobalLoadBalancer()
        server = lb.add_server(
            region="us-east-1",
            host="10.0.1.1",
            port=443,
            weight=2
        )
        assert server.region == "us-east-1"
        assert server.host == "10.0.1.1"
        assert server.weight == 2
        assert server.enabled is True

    def test_remove_server(self):
        """Test removing a server"""
        lb = GlobalLoadBalancer()
        server = lb.add_server("us-east-1", "10.0.1.1")
        result = lb.remove_server(server.id)
        assert result is True
        assert lb.get_server(server.id) is None

    def test_get_next_server_round_robin(self):
        """Test round robin server selection"""
        lb = GlobalLoadBalancer()
        lb.add_server("us-east-1", "10.0.1.1")
        lb.add_server("us-west-1", "10.0.2.1")

        server1 = lb.get_next_server(BalancingStrategy.ROUND_ROBIN)
        server2 = lb.get_next_server(BalancingStrategy.ROUND_ROBIN)

        # Should alternate
        assert server1.id != server2.id

    def test_get_next_server_least_connections(self):
        """Test least connections selection"""
        lb = GlobalLoadBalancer()
        s1 = lb.add_server("us-east-1", "10.0.1.1")
        s2 = lb.add_server("us-west-1", "10.0.2.1")

        lb.increment_connections(s1.id)
        lb.increment_connections(s1.id)

        server = lb.get_next_server(BalancingStrategy.LEAST_CONNECTIONS)
        assert server.id == s2.id

    def test_get_next_server_latency_based(self):
        """Test latency-based selection"""
        lb = GlobalLoadBalancer()
        s1 = lb.add_server("us-east-1", "10.0.1.1")
        s2 = lb.add_server("us-west-1", "10.0.2.1")

        lb.record_request(s1.id, latency_ms=100.0, region="us-east-1")
        lb.record_request(s2.id, latency_ms=50.0, region="us-west-1")

        server = lb.get_next_server(BalancingStrategy.LATENCY_BASED)
        assert server.id == s2.id

    def test_get_next_server_no_healthy(self):
        """Test selection with no healthy servers"""
        lb = GlobalLoadBalancer()
        server = lb.get_next_server()
        assert server is None

    def test_record_request(self):
        """Test recording a request"""
        lb = GlobalLoadBalancer()
        server = lb.add_server("us-east-1", "10.0.1.1")
        result = lb.record_request(server.id, latency_ms=50.0, region="us-east-1")
        assert result is True

        metrics = lb.get_metrics()
        assert metrics["total_requests"] == 1
        assert metrics["requests_by_region"]["us-east-1"] == 1

    def test_increment_decrement_connections(self):
        """Test connection tracking"""
        lb = GlobalLoadBalancer()
        server = lb.add_server("us-east-1", "10.0.1.1")

        lb.increment_connections(server.id)
        lb.increment_connections(server.id)
        assert server.current_connections == 2

        lb.decrement_connections(server.id)
        assert server.current_connections == 1

    def test_update_server_health(self):
        """Test updating server health"""
        lb = GlobalLoadBalancer()
        server = lb.add_server("us-east-1", "10.0.1.1")
        result = lb.update_server_health(server.id, RegionHealth.UNHEALTHY)
        assert result is True
        assert server.health == RegionHealth.UNHEALTHY

    def test_enable_disable_server(self):
        """Test enabling and disabling servers"""
        lb = GlobalLoadBalancer()
        server = lb.add_server("us-east-1", "10.0.1.1")
        lb.disable_server(server.id)
        assert server.enabled is False

        lb.enable_server(server.id)
        assert server.enabled is True

    def test_get_servers_by_region(self):
        """Test getting servers by region"""
        lb = GlobalLoadBalancer()
        lb.add_server("us-east-1", "10.0.1.1")
        lb.add_server("us-east-1", "10.0.1.2")
        lb.add_server("eu-west-1", "10.0.2.1")

        servers = lb.get_servers_by_region("us-east-1")
        assert len(servers) == 2

    def test_get_healthy_servers(self):
        """Test getting healthy servers"""
        lb = GlobalLoadBalancer()
        s1 = lb.add_server("us-east-1", "10.0.1.1")
        s2 = lb.add_server("us-west-1", "10.0.2.1")
        lb.update_server_health(s2.id, RegionHealth.UNHEALTHY)

        healthy = lb.get_healthy_servers()
        assert len(healthy) == 1
        assert healthy[0].id == s1.id

    def test_get_metrics(self):
        """Test getting metrics"""
        lb = GlobalLoadBalancer()
        lb.add_server("us-east-1", "10.0.1.1")
        lb.add_server("us-west-1", "10.0.2.1")

        metrics = lb.get_metrics()
        assert metrics["total_servers"] == 2
        assert metrics["healthy_servers"] == 2


# =============================================================================
# TRAFFIC ROUTER TESTS
# =============================================================================

class TestTrafficRouter:
    """Tests for TrafficRouter class"""

    def test_init(self):
        """Test router initialization"""
        router = TrafficRouter()
        assert router is not None
        metrics = router.get_metrics()
        assert metrics["total_routed"] == 0

    def test_add_rule(self):
        """Test adding a routing rule"""
        router = TrafficRouter()
        rule = router.add_rule(
            name="eu-traffic",
            rule_type=RoutingRuleType.GEOGRAPHIC,
            condition="EU",
            target_region="eu-west-1"
        )
        assert rule.name == "eu-traffic"
        assert rule.rule_type == RoutingRuleType.GEOGRAPHIC
        assert rule.target_region == "eu-west-1"

    def test_remove_rule(self):
        """Test removing a routing rule"""
        router = TrafficRouter()
        rule = router.add_rule("test", RoutingRuleType.PATH_BASED, "/api", "us-east-1")
        result = router.remove_rule(rule.id)
        assert result is True
        assert router.get_rule(rule.id) is None

    def test_route_request_geographic(self):
        """Test geographic routing"""
        router = TrafficRouter()
        router.add_rule(
            name="eu-rule",
            rule_type=RoutingRuleType.GEOGRAPHIC,
            condition="EU",
            target_region="eu-west-1"
        )

        decision = router.route_request(source_ip="10.0.2.1")
        assert decision.target_region == "eu-west-1"
        assert decision.matched_rule == "eu-rule"

    def test_route_request_path_based(self):
        """Test path-based routing"""
        router = TrafficRouter()
        router.add_rule(
            name="api-rule",
            rule_type=RoutingRuleType.PATH_BASED,
            condition="/api",
            target_region="us-west-1"
        )

        decision = router.route_request(source_ip="10.0.1.1", path="/api/users")
        assert decision.target_region == "us-west-1"

    def test_route_request_header_based(self):
        """Test header-based routing"""
        router = TrafficRouter()
        router.add_rule(
            name="header-rule",
            rule_type=RoutingRuleType.HEADER_BASED,
            condition="X-Region:eu",
            target_region="eu-west-1"
        )

        decision = router.route_request(
            source_ip="10.0.1.1",
            headers={"X-Region": "eu"}
        )
        assert decision.target_region == "eu-west-1"

    def test_route_request_default(self):
        """Test default routing when no rule matches"""
        router = TrafficRouter()
        decision = router.route_request(source_ip="10.0.1.1")
        assert decision.target_region == "us-east-1"
        assert decision.matched_rule == "default"

    def test_enable_disable_rule(self):
        """Test enabling and disabling rules"""
        router = TrafficRouter()
        rule = router.add_rule("test", RoutingRuleType.PATH_BASED, "/api", "us-east-1")
        router.disable_rule(rule.id)
        assert rule.enabled is False

        router.enable_rule(rule.id)
        assert rule.enabled is True

    def test_rule_priority(self):
        """Test rule priority ordering"""
        router = TrafficRouter()
        router.add_rule("low", RoutingRuleType.GEOGRAPHIC, "US", "us-east-1", priority=1)
        router.add_rule("high", RoutingRuleType.GEOGRAPHIC, "US", "us-west-1", priority=10)

        decision = router.route_request(source_ip="10.0.1.1")
        # Higher priority rule should win
        assert decision.target_region == "us-west-1"

    def test_get_rules_by_type(self):
        """Test getting rules by type"""
        router = TrafficRouter()
        router.add_rule("geo1", RoutingRuleType.GEOGRAPHIC, "EU", "eu-west-1")
        router.add_rule("path1", RoutingRuleType.PATH_BASED, "/api", "us-east-1")
        router.add_rule("geo2", RoutingRuleType.GEOGRAPHIC, "APAC", "ap-southeast-1")

        geo_rules = router.get_rules_by_type(RoutingRuleType.GEOGRAPHIC)
        assert len(geo_rules) == 2

    def test_get_decisions(self):
        """Test getting routing decisions"""
        router = TrafficRouter()
        router.route_request(source_ip="10.0.1.1")
        router.route_request(source_ip="10.0.2.1")

        decisions = router.get_decisions()
        assert len(decisions) == 2

    def test_set_region_mapping(self):
        """Test setting region mapping"""
        router = TrafficRouter()
        router.set_region_mapping("LATAM", "sa-east-1")
        mapping = router.get_region_mapping()
        assert mapping["LATAM"] == "sa-east-1"

    def test_clear_decisions(self):
        """Test clearing decisions"""
        router = TrafficRouter()
        router.route_request(source_ip="10.0.1.1")
        count = router.clear_decisions()
        assert count == 1

    def test_metrics_tracking(self):
        """Test metrics tracking"""
        router = TrafficRouter()
        router.add_rule("eu", RoutingRuleType.GEOGRAPHIC, "EU", "eu-west-1")
        router.route_request(source_ip="10.0.2.1")
        router.route_request(source_ip="10.0.1.1")

        metrics = router.get_metrics()
        assert metrics["total_routed"] == 2


# =============================================================================
# LATENCY OPTIMIZER TESTS
# =============================================================================

class TestLatencyOptimizer:
    """Tests for LatencyOptimizer class"""

    def test_init(self):
        """Test optimizer initialization"""
        optimizer = LatencyOptimizer()
        assert optimizer is not None
        metrics = optimizer.get_metrics()
        assert metrics["total_measurements"] == 0

    def test_record_latency(self):
        """Test recording latency"""
        optimizer = LatencyOptimizer()
        measurement = optimizer.record_latency(
            source_region="us-east-1",
            target_region="eu-west-1",
            latency_ms=100.0
        )
        assert measurement.source_region == "us-east-1"
        assert measurement.latency_ms == 100.0

    def test_get_optimal_region_single(self):
        """Test optimal region with single option"""
        optimizer = LatencyOptimizer()
        region = optimizer.get_optimal_region("us-east-1", ["eu-west-1"])
        assert region == "eu-west-1"

    def test_get_optimal_region_multiple(self):
        """Test optimal region selection"""
        optimizer = LatencyOptimizer()
        optimizer.record_latency("us-east-1", "us-west-1", 50.0)
        optimizer.record_latency("us-east-1", "eu-west-1", 150.0)

        optimal = optimizer.get_optimal_region("us-east-1", ["us-west-1", "eu-west-1"])
        assert optimal == "us-west-1"

    def test_should_reroute_false(self):
        """Test re-route decision when no improvement"""
        optimizer = LatencyOptimizer()
        optimizer.set_latency_threshold(100.0)
        optimizer.record_latency("us-east-1", "us-west-1", 50.0)
        optimizer.record_latency("us-east-1", "eu-west-1", 60.0)

        should_reroute = optimizer.should_reroute(
            "us-west-1", "us-east-1", ["us-west-1", "eu-west-1"]
        )
        assert should_reroute is False

    def test_should_reroute_true(self):
        """Test re-route decision when improvement is significant"""
        optimizer = LatencyOptimizer()
        optimizer.set_latency_threshold(10.0)
        optimizer.record_latency("us-east-1", "us-west-1", 200.0)
        optimizer.record_latency("us-east-1", "eu-west-1", 50.0)

        should_reroute = optimizer.should_reroute(
            "us-west-1", "us-east-1", ["us-west-1", "eu-west-1"]
        )
        assert should_reroute is True

    def test_set_strategy(self):
        """Test setting optimization strategy"""
        optimizer = LatencyOptimizer()
        optimizer.set_strategy(OptimizationStrategy.PERCENTILE_BASED)
        assert optimizer.get_strategy() == OptimizationStrategy.PERCENTILE_BASED

    def test_set_latency_threshold(self):
        """Test setting latency threshold"""
        optimizer = LatencyOptimizer()
        optimizer.set_latency_threshold(200.0)
        assert optimizer.get_latency_threshold() == 200.0

    def test_get_region_latency(self):
        """Test getting region latency stats"""
        optimizer = LatencyOptimizer()
        optimizer.record_latency("us-east-1", "eu-west-1", 100.0)
        optimizer.record_latency("us-east-1", "eu-west-1", 200.0)

        latency = optimizer.get_region_latency("us-east-1", "eu-west-1")
        assert latency is not None
        assert latency.sample_count == 2

    def test_get_measurements(self):
        """Test getting latency measurements"""
        optimizer = LatencyOptimizer()
        optimizer.record_latency("us-east-1", "eu-west-1", 100.0)
        optimizer.record_latency("us-east-1", "us-west-1", 50.0)

        measurements = optimizer.get_measurements()
        assert len(measurements) == 2

    def test_get_measurements_filtered(self):
        """Test getting filtered measurements"""
        optimizer = LatencyOptimizer()
        optimizer.record_latency("us-east-1", "eu-west-1", 100.0)
        optimizer.record_latency("us-east-1", "us-west-1", 50.0)

        measurements = optimizer.get_measurements(target_region="eu-west-1")
        assert len(measurements) == 1

    def test_cleanup_old_measurements(self):
        """Test cleaning up old measurements"""
        optimizer = LatencyOptimizer()
        optimizer.record_latency("us-east-1", "eu-west-1", 100.0)
        removed = optimizer.cleanup_old_measurements(hours=0)
        assert removed >= 1

    def test_get_metrics(self):
        """Test getting optimizer metrics"""
        optimizer = LatencyOptimizer()
        optimizer.record_latency("us-east-1", "eu-west-1", 100.0)

        metrics = optimizer.get_metrics()
        assert metrics["total_measurements"] == 1
        assert metrics["strategy"] == "lowest_latency"

    def test_percentile_based_strategy(self):
        """Test percentile-based optimization strategy"""
        optimizer = LatencyOptimizer()
        optimizer.set_strategy(OptimizationStrategy.PERCENTILE_BASED)

        # Add multiple measurements
        for i in range(20):
            optimizer.record_latency("us-east-1", "region-a", float(i * 10))
            optimizer.record_latency("us-east-1", "region-b", float(i * 5))

        optimal = optimizer.get_optimal_region("us-east-1", ["region-a", "region-b"])
        assert optimal == "region-b"  # Lower latency overall
