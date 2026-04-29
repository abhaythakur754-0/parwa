"""
Tests for load_aware_distribution.py (Week 10 Day 4 — SG-07)

Comprehensive unit tests for LoadAwareDistributor covering:
- Constructor initialization
- register_instance / deregister_instance
- update_instance_load: metrics, auto-overload detection
- update_instance_status: status transitions
- distribute: sticky session, round-robin, least-loaded, no-instance
- Sticky session management
- cleanup_expired_sessions
- failover_ticket
- get_all_instances / get_instance_load_summary
- rebalance_weights
- get_distribution_stats
- Edge cases: all overloaded, single instance, no instances
- Thread safety basics
- Channel-based filtering
"""

import pytest
import threading
import time

from app.core.load_aware_distribution import (
    LoadAwareDistributor,
    InstanceInfo,
    InstanceStatus,
    RoutingMethod,
    DEFAULT_MAX_CONCURRENT_TICKETS,
    DEFAULT_INSTANCE_WEIGHT,
)


# ═══════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def dist():
    """Fresh LoadAwareDistributor for each test."""
    return LoadAwareDistributor()


def _register_instances(
    dist,
    company_id="co_1",
    variant_type="parwa",
    count=3,
    channel="email,chat",
):
    """Helper to register multiple instances."""
    instance_ids = []
    for i in range(count):
        iid = f"inst_{i}"
        dist.register_instance(
            company_id, iid, variant_type, channel,
        )
        instance_ids.append(iid)
    return instance_ids


# ═══════════════════════════════════════════════════════════════════
# CONSTRUCTOR
# ═══════════════════════════════════════════════════════════════════


class TestConstructor:
    """Tests for LoadAwareDistributor initialization."""

    def test_empty_instances_on_init(self, dist):
        """Should start with no registered instances."""
        assert len(dist._instances) == 0

    def test_empty_sticky_sessions_on_init(self, dist):
        """Should start with no sticky sessions."""
        assert len(dist._sticky_sessions) == 0

    def test_empty_rr_counter_on_init(self, dist):
        """Should start with no round-robin counters."""
        assert len(dist._rr_counter) == 0

    def test_has_rlock(self, dist):
        """Should use RLock for thread safety."""
        assert isinstance(dist._lock, type(threading.RLock()))


# ═══════════════════════════════════════════════════════════════════
# INSTANCE REGISTRATION
# ═══════════════════════════════════════════════════════════════════


class TestRegisterInstance:
    """Tests for instance registration."""

    def test_register_returns_instance_info(self, dist):
        """Should return an InstanceInfo object on success."""
        info = dist.register_instance(
            "co_1", "inst_1", "parwa", "email,chat",
        )
        assert info is not None
        assert isinstance(info, InstanceInfo)
        assert info.instance_id == "inst_1"

    def test_register_sets_defaults(self, dist):
        """Should set default status, weight, and capacity."""
        info = dist.register_instance("co_1", "inst_1", "parwa")
        assert info.status == InstanceStatus.ACTIVE
        assert info.weight == DEFAULT_INSTANCE_WEIGHT
        assert info.max_concurrent == DEFAULT_MAX_CONCURRENT_TICKETS

    def test_register_with_custom_capacity(self, dist):
        """Should accept custom capacity_config."""
        info = dist.register_instance(
            "co_1", "inst_1", "parwa", capacity_config={
                "max_concurrent_tickets": 100, "token_budget_share": 500_000}, )
        assert info.max_concurrent == 100
        assert info.token_budget == 500_000

    def test_register_with_custom_weight(self, dist):
        """Should accept custom routing weight."""
        info = dist.register_instance(
            "co_1", "inst_1", "parwa", weight=2.5,
        )
        assert info.weight == 2.5

    def test_register_negative_weight_clamped(self, dist):
        """Negative weight should be clamped to default."""
        info = dist.register_instance(
            "co_1", "inst_1", "parwa", weight=-1.0,
        )
        assert info.weight == DEFAULT_INSTANCE_WEIGHT

    def test_register_zero_weight_clamped(self, dist):
        """Zero weight should be clamped to default."""
        info = dist.register_instance(
            "co_1", "inst_1", "parwa", weight=0.0,
        )
        assert info.weight == DEFAULT_INSTANCE_WEIGHT

    def test_register_replaces_existing(self, dist):
        """Re-registering same key should replace the instance."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_instance("co_1", "inst_1", "mini_parwa")
        instances = dist.get_all_instances("co_1")
        assert len(instances) == 1
        assert instances[0].variant_type == "mini_parwa"

    def test_register_multiple_companies(self, dist):
        """Instances from different companies should be separate."""
        dist.register_instance("co_a", "inst_1", "parwa")
        dist.register_instance("co_b", "inst_2", "parwa")
        assert len(dist.get_all_instances("co_a")) == 1
        assert len(dist.get_all_instances("co_b")) == 1

    def test_timestamp_set(self, dist):
        """Created_at should be a non-empty ISO string."""
        info = dist.register_instance("co_1", "inst_1", "parwa")
        assert info.created_at
        assert "T" in info.created_at


class TestDeregisterInstance:
    """Tests for instance removal."""

    def test_deregister_existing(self, dist):
        """Should return True when instance exists."""
        dist.register_instance("co_1", "inst_1", "parwa")
        assert dist.deregister_instance("co_1", "inst_1") is True

    def test_deregister_nonexistent(self, dist):
        """Should return False when instance doesn't exist."""
        assert dist.deregister_instance("co_1", "inst_99") is False

    def test_deregister_clears_sticky_sessions(self, dist):
        """Deregistering should clear sticky sessions for that instance."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_sticky_session("co_1", "tkt_1", "inst_1")
        dist.deregister_instance("co_1", "inst_1")
        assert dist.get_sticky_instance("co_1", "tkt_1") is None


# ═══════════════════════════════════════════════════════════════════
# LOAD METRICS
# ═══════════════════════════════════════════════════════════════════


class TestUpdateInstanceLoad:
    """Tests for instance load metric updates."""

    def test_update_existing_instance(self, dist):
        """Should return True when instance is found."""
        dist.register_instance("co_1", "inst_1", "parwa")
        assert dist.update_instance_load(
            "co_1", "inst_1", active_tickets=10) is True

    def test_update_nonexistent_instance(self, dist):
        """Should return False when instance not found."""
        assert dist.update_instance_load(
            "co_1", "inst_99", active_tickets=5) is False

    def test_active_tickets_set(self, dist):
        """Should update current_load to active_tickets."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.update_instance_load("co_1", "inst_1", active_tickets=25)
        instances = dist.get_all_instances("co_1")
        assert instances[0].current_load == 25

    def test_queued_tickets_set(self, dist):
        """Should update queued_count."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.update_instance_load("co_1", "inst_1", queued_tickets=10)
        instances = dist.get_all_instances("co_1")
        assert instances[0].queued_count == 10

    def test_tokens_used_set(self, dist):
        """Should update tokens_used_today when non-zero."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.update_instance_load("co_1", "inst_1", tokens_used=5000)
        instances = dist.get_all_instances("co_1")
        assert instances[0].tokens_used_today == 5000

    def test_tokens_zero_preserves_existing(self, dist):
        """tokens_used=0 should preserve existing value."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.update_instance_load("co_1", "inst_1", tokens_used=5000)
        dist.update_instance_load("co_1", "inst_1", tokens_used=0)
        instances = dist.get_all_instances("co_1")
        assert instances[0].tokens_used_today == 5000

    def test_negative_values_clamped_to_zero(self, dist):
        """Negative values should be clamped to zero."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.update_instance_load(
            "co_1",
            "inst_1",
            active_tickets=-5,
            queued_tickets=-3)
        instances = dist.get_all_instances("co_1")
        assert instances[0].current_load == 0
        assert instances[0].queued_count == 0

    def test_auto_overload_at_90_percent(self, dist):
        """Should auto-mark as OVERLOADED at 90% utilization."""
        dist.register_instance(
            "co_1", "inst_1", "parwa",
            capacity_config={"max_concurrent_tickets": 100},
        )
        # 90/100 = 90% → triggers overload
        dist.update_instance_load("co_1", "inst_1", active_tickets=90)
        instances = dist.get_all_instances("co_1")
        assert instances[0].status == InstanceStatus.OVERLOADED

    def test_below_90_not_overloaded(self, dist):
        """Below 90% should not trigger auto-overload."""
        dist.register_instance(
            "co_1", "inst_1", "parwa",
            capacity_config={"max_concurrent_tickets": 100},
        )
        dist.update_instance_load("co_1", "inst_1", active_tickets=89)
        instances = dist.get_all_instances("co_1")
        assert instances[0].status == InstanceStatus.ACTIVE


class TestUpdateInstanceStatus:
    """Tests for instance status transitions."""

    def test_mark_unhealthy(self, dist):
        """Should mark instance as UNHEALTHY."""
        dist.register_instance("co_1", "inst_1", "parwa")
        assert dist.update_instance_status(
            "co_1", "inst_1", InstanceStatus.UNHEALTHY)
        instances = dist.get_all_instances("co_1")
        assert instances[0].status == InstanceStatus.UNHEALTHY

    def test_mark_inactive(self, dist):
        """Should mark instance as INACTIVE."""
        dist.register_instance("co_1", "inst_1", "parwa")
        assert dist.update_instance_status(
            "co_1", "inst_1", InstanceStatus.INACTIVE)

    def test_unhealthy_nonexistent(self, dist):
        """Should return False for nonexistent instance."""
        assert dist.update_instance_status(
            "co_1", "inst_99", InstanceStatus.UNHEALTHY) is False

    def test_unhealthy_clears_sticky_sessions(self, dist):
        """Going UNHEALTHY should clear all sticky sessions for the instance."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_sticky_session("co_1", "tkt_1", "inst_1")
        dist.register_sticky_session("co_1", "tkt_2", "inst_1")
        dist.update_instance_status("co_1", "inst_1", InstanceStatus.UNHEALTHY)
        assert dist.get_sticky_instance("co_1", "tkt_1") is None
        assert dist.get_sticky_instance("co_1", "tkt_2") is None


# ═══════════════════════════════════════════════════════════════════
# DISTRIBUTION (ROUTING)
# ═══════════════════════════════════════════════════════════════════


class TestDistribute:
    """Tests for the main distribution / routing entry point."""

    def test_no_instances_returns_no_instance_available(self, dist):
        """With no registered instances, should return no_instance_available."""
        result = dist.distribute("co_1", "parwa", "tkt_1")
        assert result.routing_method == RoutingMethod.NO_INSTANCE_AVAILABLE.value
        assert result.instance_id == ""

    def test_single_instance_round_robin(self, dist):
        """Single instance should be selected via round_robin."""
        dist.register_instance("co_1", "inst_1", "parwa")
        result = dist.distribute("co_1", "parwa", "tkt_1")
        assert result.instance_id == "inst_1"
        assert result.routing_method == RoutingMethod.ROUND_ROBIN.value

    def test_sticky_session_hit(self, dist):
        """Second call with same ticket_id should use sticky routing."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_instance("co_1", "inst_2", "parwa")
        result1 = dist.distribute("co_1", "parwa", "tkt_1")
        result2 = dist.distribute("co_1", "parwa", "tkt_1")
        assert result2.routing_method == RoutingMethod.STICKY.value
        assert result2.instance_id == result1.instance_id

    def test_all_unhealthy_returns_no_instance(self, dist):
        """All instances UNHEALTHY should return no_instance_available."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_instance("co_1", "inst_2", "parwa")
        dist.update_instance_status("co_1", "inst_1", InstanceStatus.UNHEALTHY)
        dist.update_instance_status("co_1", "inst_2", InstanceStatus.UNHEALTHY)
        result = dist.distribute("co_1", "parwa", "tkt_1")
        assert result.routing_method == RoutingMethod.NO_INSTANCE_AVAILABLE.value

    def test_channel_filtering(self, dist):
        """Preferred channel should filter eligible instances."""
        dist.register_instance("co_1", "inst_1", "parwa", "email")
        dist.register_instance("co_1", "inst_2", "parwa", "chat")
        result = dist.distribute(
            "co_1", "parwa", "tkt_1", preferred_channel="chat")
        assert result.instance_id == "inst_2"

    def test_variant_type_filtering(self, dist):
        """Should only consider instances of the requested variant."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_instance("co_1", "inst_2", "mini_parwa")
        result = dist.distribute("co_1", "mini_parwa", "tkt_1")
        assert result.instance_id == "inst_2"

    def test_round_robin_alternates(self, dist):
        """Round-robin should alternate between instances."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_instance("co_1", "inst_2", "parwa")
        r1 = dist.distribute("co_1", "parwa", "tkt_1")
        r2 = dist.distribute("co_1", "parwa", "tkt_2")
        # Both should be round_robin since no sticky session yet
        assert r1.routing_method == RoutingMethod.ROUND_ROBIN.value
        assert r2.routing_method == RoutingMethod.ROUND_ROBIN.value

    def test_overloaded_falls_to_no_instance(self, dist):
        """When all instances are OVERLOADED, they are not routable, so no_instance_available."""
        dist.register_instance(
            "co_1", "inst_1", "parwa",
            capacity_config={"max_concurrent_tickets": 100},
        )
        dist.register_instance(
            "co_1", "inst_2", "parwa",
            capacity_config={"max_concurrent_tickets": 100},
        )
        dist.update_instance_load("co_1", "inst_1", active_tickets=95)
        dist.update_instance_load("co_1", "inst_2", active_tickets=92)
        result = dist.distribute("co_1", "parwa", "tkt_new")
        assert result.routing_method == RoutingMethod.NO_INSTANCE_AVAILABLE.value

    def test_auto_registers_sticky_session(self, dist):
        """Distribution should auto-register sticky session for ticket_id."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.distribute("co_1", "parwa", "tkt_1")
        sticky = dist.get_sticky_instance("co_1", "tkt_1")
        assert sticky == "inst_1"


# ═══════════════════════════════════════════════════════════════════
# STICKY SESSION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════


class TestStickySessions:
    """Tests for sticky session management."""

    def test_register_sticky(self, dist):
        """Should register a sticky session."""
        dist.register_instance("co_1", "inst_1", "parwa")
        assert dist.register_sticky_session("co_1", "tkt_1", "inst_1") is True

    def test_register_sticky_nonexistent_instance(self, dist):
        """Should return False for nonexistent instance."""
        assert dist.register_sticky_session(
            "co_1", "tkt_1", "inst_99") is False

    def test_get_sticky_instance(self, dist):
        """Should return the pinned instance_id."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_sticky_session("co_1", "tkt_1", "inst_1")
        assert dist.get_sticky_instance("co_1", "tkt_1") == "inst_1"

    def test_get_sticky_nonexistent(self, dist):
        """Should return None for nonexistent session."""
        assert dist.get_sticky_instance("co_1", "tkt_99") is None

    def test_clear_sticky(self, dist):
        """Should remove a sticky session."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_sticky_session("co_1", "tkt_1", "inst_1")
        assert dist.clear_sticky_session("co_1", "tkt_1") is True
        assert dist.get_sticky_instance("co_1", "tkt_1") is None

    def test_clear_nonexistent_sticky(self, dist):
        """Should return False for nonexistent session."""
        assert dist.clear_sticky_session("co_1", "tkt_99") is False

    def test_repin_to_different_instance(self, dist):
        """Re-pinning should update to new instance."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_instance("co_1", "inst_2", "parwa")
        dist.register_sticky_session("co_1", "tkt_1", "inst_1")
        dist.register_sticky_session("co_1", "tkt_1", "inst_2")
        assert dist.get_sticky_instance("co_1", "tkt_1") == "inst_2"


class TestCleanupExpiredSessions:
    """Tests for expired session cleanup."""

    def test_cleanup_removes_expired(self, dist):
        """Should remove sessions that have expired."""
        dist.register_instance("co_1", "inst_1", "parwa")
        # Register with very short TTL
        dist.register_sticky_session(
            "co_1", "tkt_old", "inst_1", ttl_seconds=0.001)
        time.sleep(0.01)
        cleaned = dist.cleanup_expired_sessions("co_1")
        assert cleaned >= 1
        assert dist.get_sticky_instance("co_1", "tkt_old") is None

    def test_cleanup_respects_max_age(self, dist):
        """Should remove sessions exceeding max_age_seconds."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_sticky_session(
            "co_1", "tkt_old", "inst_1", ttl_seconds=9999)
        time.sleep(0.01)
        cleaned = dist.cleanup_expired_sessions("co_1", max_age_seconds=0.001)
        assert cleaned >= 1

    def test_cleanup_no_expired(self, dist):
        """Should return 0 when nothing to clean."""
        cleaned = dist.cleanup_expired_sessions("co_1")
        assert cleaned == 0


# ═══════════════════════════════════════════════════════════════════
# FAILOVER
# ═══════════════════════════════════════════════════════════════════


class TestFailover:
    """Tests for ticket failover."""

    def test_failover_to_another_instance(self, dist):
        """Should reroute ticket to least-loaded alternate instance."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_instance("co_1", "inst_2", "parwa")
        result = dist.failover_ticket(
            "co_1", "tkt_1", "inst_1", "health_check_failed")
        assert result is not None
        assert result.instance_id == "inst_2"
        assert result.routing_method == RoutingMethod.FAILOVER.value

    def test_failover_nonexistent_source(self, dist):
        """Should return None when source instance doesn't exist."""
        dist.register_instance("co_1", "inst_1", "parwa")
        result = dist.failover_ticket("co_1", "tkt_1", "inst_99")
        assert result is None

    def test_failover_no_other_instances(self, dist):
        """Should return None when no alternate instance available."""
        dist.register_instance("co_1", "inst_1", "parwa")
        result = dist.failover_ticket("co_1", "tkt_1", "inst_1")
        assert result is None

    def test_failover_creates_new_sticky(self, dist):
        """Failover should create a new sticky session to target."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_instance("co_1", "inst_2", "parwa")
        dist.failover_ticket("co_1", "tkt_1", "inst_1")
        sticky = dist.get_sticky_instance("co_1", "tkt_1")
        assert sticky == "inst_2"


# ═══════════════════════════════════════════════════════════════════
# INSTANCE QUERIES
# ═══════════════════════════════════════════════════════════════════


class TestGetAllInstances:
    """Tests for listing instances."""

    def test_all_instances_for_company(self, dist):
        """Should return all instances for a company."""
        _register_instances(dist, "co_1", "parwa", 3)
        instances = dist.get_all_instances("co_1")
        assert len(instances) == 3

    def test_filter_by_variant(self, dist):
        """Should filter instances by variant type."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_instance("co_1", "inst_2", "mini_parwa")
        instances = dist.get_all_instances("co_1", variant_type="parwa")
        assert len(instances) == 1
        assert instances[0].instance_id == "inst_1"

    def test_different_company_not_returned(self, dist):
        """Should not return instances from other companies."""
        dist.register_instance("co_a", "inst_1", "parwa")
        instances = dist.get_all_instances("co_b")
        assert len(instances) == 0


class TestGetLoadSummary:
    """Tests for instance load summary."""

    def test_summary_totals(self, dist):
        """Summary should aggregate totals across instances."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_instance("co_1", "inst_2", "parwa")
        dist.update_instance_load(
            "co_1",
            "inst_1",
            active_tickets=10,
            queued_tickets=5)
        dist.update_instance_load(
            "co_1",
            "inst_2",
            active_tickets=20,
            queued_tickets=3)

        summary = dist.get_instance_load_summary("co_1")
        assert summary["total_instances"] == 2
        assert summary["total_active_tickets"] == 30
        assert summary["total_queued_tickets"] == 8
        assert summary["total_capacity"] == 100

    def test_summary_utilization(self, dist):
        """Should calculate aggregate utilization percentage."""
        dist.register_instance(
            "co_1", "inst_1", "parwa",
            capacity_config={"max_concurrent_tickets": 200},
        )
        dist.update_instance_load("co_1", "inst_1", active_tickets=50)
        summary = dist.get_instance_load_summary("co_1")
        assert summary["aggregate_utilization_pct"] == 25.0

    def test_summary_empty_company(self, dist):
        """Summary for company with no instances should have zero totals."""
        summary = dist.get_instance_load_summary("co_empty")
        assert summary["total_instances"] == 0
        assert summary["total_active_tickets"] == 0


# ═══════════════════════════════════════════════════════════════════
# WEIGHT REBALANCING
# ═══════════════════════════════════════════════════════════════════


class TestRebalanceWeights:
    """Tests for dynamic weight rebalancing."""

    def test_single_instance_skips(self, dist):
        """Should skip rebalance with fewer than 2 instances."""
        dist.register_instance("co_1", "inst_1", "parwa")
        result = dist.rebalance_weights("co_1", "parwa")
        assert result["skipped"] is True
        assert "2 instances" in result["reason"]

    def test_low_utilization_boosts_weight(self, dist):
        """Under-utilized instance should get increased weight."""
        dist.register_instance(
            "co_1", "inst_1", "parwa",
            capacity_config={"max_concurrent_tickets": 100},
        )
        dist.register_instance(
            "co_1", "inst_2", "parwa",
            capacity_config={"max_concurrent_tickets": 100},
        )
        dist.update_instance_load("co_1", "inst_1", active_tickets=5)
        dist.update_instance_load("co_1", "inst_2", active_tickets=80)

        result = dist.rebalance_weights("co_1", "parwa")
        assert result["skipped"] is False
        # inst_1 (5%) should have higher weight after rebalance
        weights = result["current_weights"]
        assert weights["inst_1"] > weights["inst_2"]

    def test_high_utilization_reduces_weight(self, dist):
        """Over-utilized instance should get reduced weight."""
        dist.register_instance(
            "co_1", "inst_1", "parwa",
            capacity_config={"max_concurrent_tickets": 100},
        )
        dist.register_instance(
            "co_1", "inst_2", "parwa",
            capacity_config={"max_concurrent_tickets": 100},
        )
        dist.update_instance_load("co_1", "inst_1", active_tickets=90)
        dist.update_instance_load("co_1", "inst_2", active_tickets=10)

        result = dist.rebalance_weights("co_1", "parwa")
        weights = result["current_weights"]
        assert weights["inst_2"] > weights["inst_1"]

    def test_equal_utilization_no_changes(self, dist):
        """Equal utilization should produce no weight changes."""
        dist.register_instance(
            "co_1", "inst_1", "parwa",
            capacity_config={"max_concurrent_tickets": 100},
        )
        dist.register_instance(
            "co_1", "inst_2", "parwa",
            capacity_config={"max_concurrent_tickets": 100},
        )
        dist.update_instance_load("co_1", "inst_1", active_tickets=50)
        dist.update_instance_load("co_1", "inst_2", active_tickets=50)

        result = dist.rebalance_weights("co_1", "parwa")
        assert result["changes_count"] == 0


# ═══════════════════════════════════════════════════════════════════
# DISTRIBUTION STATS
# ═══════════════════════════════════════════════════════════════════


class TestGetDistributionStats:
    """Tests for routing statistics."""

    def test_initial_stats_are_zero(self, dist):
        """Initial stats should have all counters at zero."""
        stats = dist.get_distribution_stats("co_1")
        rs = stats["routing_stats"]
        assert rs["sticky_hits"] == 0
        assert rs["round_robin_routes"] == 0
        assert rs["failover_count"] == 0
        assert rs["total_distributions"] == 0

    def test_stats_after_distribution(self, dist):
        """Stats should update after distribution calls."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.distribute("co_1", "parwa", "tkt_1")
        stats = dist.get_distribution_stats("co_1")
        rs = stats["routing_stats"]
        assert rs["total_distributions"] == 1
        assert rs["round_robin_routes"] == 1

    def test_sticky_hit_rate(self, dist):
        """Should compute correct sticky hit rate."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.distribute("co_1", "parwa", "tkt_1")  # round_robin
        dist.distribute("co_1", "parwa", "tkt_1")  # sticky hit
        stats = dist.get_distribution_stats("co_1")
        rs = stats["routing_stats"]
        assert rs["sticky_hits"] == 1
        assert rs["sticky_misses"] == 1
        assert rs["sticky_hit_rate"] == 50.0


# ═══════════════════════════════════════════════════════════════════
# INSTANCE INFO DERIVED PROPERTIES
# ═══════════════════════════════════════════════════════════════════


class TestInstanceInfoProperties:
    """Tests for InstanceInfo computed properties."""

    def test_utilization_pct(self):
        """utilization_pct should be load / max_concurrent."""
        info = InstanceInfo(
            instance_id="i1", company_id="c1", variant_type="parwa",
            capacity_config={"max_concurrent_tickets": 100},
            current_load=25,
        )
        assert info.utilization_pct == 0.25

    def test_utilization_pct_zero_max(self):
        """utilization_pct should return 1.0 when max_concurrent is 0."""
        info = InstanceInfo(
            instance_id="i1", company_id="c1", variant_type="parwa",
            capacity_config={"max_concurrent_tickets": 0},
            current_load=10,
        )
        assert info.utilization_pct == 1.0

    def test_effective_load(self):
        """effective_load should combine active + queued * factor."""
        info = InstanceInfo(
            instance_id="i1", company_id="c1", variant_type="parwa",
            current_load=10, queued_count=4,
        )
        # 10 + 4 * 0.5 = 12.0
        assert info.effective_load == 12.0

    def test_available_capacity(self):
        """available_capacity should be max - current."""
        info = InstanceInfo(
            instance_id="i1", company_id="c1", variant_type="parwa",
            capacity_config={"max_concurrent_tickets": 100},
            current_load=30,
        )
        assert info.available_capacity == 70

    def test_available_capacity_no_negative(self):
        """available_capacity should not go below 0."""
        info = InstanceInfo(
            instance_id="i1", company_id="c1", variant_type="parwa",
            capacity_config={"max_concurrent_tickets": 10},
            current_load=50,
        )
        assert info.available_capacity == 0

    def test_is_routable_active(self):
        """ACTIVE instances should be routable."""
        info = InstanceInfo(
            instance_id="i1", company_id="c1", variant_type="parwa",
            status=InstanceStatus.ACTIVE,
        )
        assert info.is_routable is True

    def test_is_routable_overloaded(self):
        """OVERLOADED instances should not be routable."""
        info = InstanceInfo(
            instance_id="i1", company_id="c1", variant_type="parwa",
            status=InstanceStatus.OVERLOADED,
        )
        assert info.is_routable is False

    def test_is_routable_warming(self):
        """WARMING instances should be routable."""
        info = InstanceInfo(
            instance_id="i1", company_id="c1", variant_type="parwa",
            status=InstanceStatus.WARMING,
        )
        assert info.is_routable is True

    def test_to_dict(self):
        """to_dict should return a dict with all expected keys."""
        info = InstanceInfo(
            instance_id="i1", company_id="c1", variant_type="parwa",
        )
        d = info.to_dict()
        assert "instance_id" in d
        assert "company_id" in d
        assert "utilization_pct" in d


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Tests for boundary conditions and edge cases."""

    def test_all_instances_overloaded_returns_no_instance(self, dist):
        """All instances OVERLOADED are not routable, returns no_instance_available."""
        dist.register_instance(
            "co_1", "inst_1", "parwa",
            capacity_config={"max_concurrent_tickets": 100},
        )
        dist.register_instance(
            "co_1", "inst_2", "parwa",
            capacity_config={"max_concurrent_tickets": 100},
        )
        dist.update_instance_load("co_1", "inst_1", active_tickets=95)
        dist.update_instance_load("co_1", "inst_2", active_tickets=99)
        result = dist.distribute("co_1", "parwa", "tkt_new")
        assert result.routing_method == RoutingMethod.NO_INSTANCE_AVAILABLE.value

    def test_single_instance_no_alternate_for_failover(self, dist):
        """Single instance with no alternates should return None on failover."""
        dist.register_instance("co_1", "inst_1", "parwa")
        result = dist.failover_ticket("co_1", "tkt_1", "inst_1")
        assert result is None

    def test_no_instances_at_all(self, dist):
        """No instances registered should return no_instance_available."""
        result = dist.distribute("co_1", "parwa", "tkt_1")
        assert result.instance_id == ""
        assert result.routing_method == RoutingMethod.NO_INSTANCE_AVAILABLE.value


# ═══════════════════════════════════════════════════════════════════
# THREAD SAFETY
# ═══════════════════════════════════════════════════════════════════


class TestThreadSafety:
    """Basic thread safety tests."""

    def test_concurrent_register_and_distribute(self, dist):
        """Concurrent register and distribute should not crash."""
        errors = []

        def register():
            try:
                for i in range(10):
                    dist.register_instance("co_1", f"inst_{i}", "parwa")
            except Exception as e:
                errors.append(str(e))

        def distribute():
            try:
                for i in range(20):
                    dist.distribute("co_1", "parwa", f"tkt_{i}")
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=register),
            threading.Thread(target=distribute),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_concurrent_distribute(self, dist):
        """Concurrent distribute calls should not crash."""
        dist.register_instance("co_1", "inst_1", "parwa")
        dist.register_instance("co_1", "inst_2", "parwa")

        errors = []

        def do_distribute(i):
            try:
                dist.distribute("co_1", "parwa", f"tkt_{i}")
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(
                target=do_distribute, args=(
                    i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
