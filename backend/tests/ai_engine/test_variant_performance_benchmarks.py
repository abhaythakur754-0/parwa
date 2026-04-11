"""
Variant Performance Benchmark Tests

Comprehensive unit tests for the LoadAwareDistributor and variant-specific
performance benchmarking across Mini PARWA ($999/mo), PARWA ($2,499/mo),
and PARWA High ($3,999/mo) tiers.

Covers:
    1.  InstanceInfo properties and derived helpers          (~12 tests)
    2.  StickySession lifecycle and TTL                       (~10 tests)
    3.  DistributionStats aggregation                         (~8 tests)
    4.  LoadAwareDistributor registration                     (~10 tests)
    5.  LoadAwareDistributor deregistration                   (~8 tests)
    6.  Load metrics updates and auto-overload detection      (~10 tests)
    7.  Instance status transitions and recovery              (~8 tests)
    8.  Main distribution routing (sticky, RR, least-loaded)  (~14 tests)
    9.  Load-aware distribution across variant capacities      (~10 tests)
    10. Priority queue management and load shedding            (~8 tests)
    11. Weight rebalancing                                    (~8 tests)
    12. Failover routing                                      (~8 tests)
    13. Performance metric collection and aggregation         (~8 tests)
    14. SLA enforcement per tier                               (~10 tests)
    15. Warm/cold variant scaling                              (~6 tests)
    16. Thread safety and concurrent operations               (~8 tests)
    17. Edge cases (empty, max capacity, timeouts)             (~10 tests)
    18. Dataclass serialisation (to_dict)                     (~6 tests)

Target: 70+ test functions
Uses: pytest, unittest.mock, threading for concurrency
"""

import time
import threading
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Module-level stubs — populated by the autouse fixture below.
LoadAwareDistributor = None  # type: ignore[assignment,misc]
InstanceInfo = None  # type: ignore[assignment,misc]
InstanceStatus = None  # type: ignore[assignment,misc]
RoutingMethod = None  # type: ignore[assignment,misc]
FailoverReason = None  # type: ignore[assignment,misc]
StickySession = None  # type: ignore[assignment,misc]
DistributionResult = None  # type: ignore[assignment,misc]
FailoverEvent = None  # type: ignore[assignment,misc]
DistributionStats = None  # type: ignore[assignment,misc]
DEFAULT_STICKY_TTL_SECONDS = None  # type: ignore[assignment,misc]
DEFAULT_MAX_CONCURRENT_TICKETS = None  # type: ignore[assignment,misc]
DEFAULT_TOKEN_BUDGET_SHARE = None  # type: ignore[assignment,misc]
DEFAULT_INSTANCE_WEIGHT = None  # type: ignore[assignment,misc]
OVERLOAD_THRESHOLD_PCT = None  # type: ignore[assignment,misc]
QUEUE_PRESSURE_WEIGHT_FACTOR = None  # type: ignore[assignment,misc]
REBALANCE_MIN_DIFFERENCE = None  # type: ignore[assignment,misc]


@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("app.logger.get_logger", return_value=MagicMock()):
        from app.core.load_aware_distribution import (
            LoadAwareDistributor as _LoadAwareDistributor,
            InstanceInfo as _InstanceInfo,
            InstanceStatus as _InstanceStatus,
            RoutingMethod as _RoutingMethod,
            FailoverReason as _FailoverReason,
            StickySession as _StickySession,
            DistributionResult as _DistributionResult,
            FailoverEvent as _FailoverEvent,
            DistributionStats as _DistributionStats,
            DEFAULT_STICKY_TTL_SECONDS as _DEFAULT_STICKY_TTL_SECONDS,
            DEFAULT_MAX_CONCURRENT_TICKETS as _DEFAULT_MAX_CONCURRENT_TICKETS,
            DEFAULT_TOKEN_BUDGET_SHARE as _DEFAULT_TOKEN_BUDGET_SHARE,
            DEFAULT_INSTANCE_WEIGHT as _DEFAULT_INSTANCE_WEIGHT,
            OVERLOAD_THRESHOLD_PCT as _OVERLOAD_THRESHOLD_PCT,
            QUEUE_PRESSURE_WEIGHT_FACTOR as _QUEUE_PRESSURE_WEIGHT_FACTOR,
            REBALANCE_MIN_DIFFERENCE as _REBALANCE_MIN_DIFFERENCE,
        )
        globals().update({
            "LoadAwareDistributor": _LoadAwareDistributor,
            "InstanceInfo": _InstanceInfo,
            "InstanceStatus": _InstanceStatus,
            "RoutingMethod": _RoutingMethod,
            "FailoverReason": _FailoverReason,
            "StickySession": _StickySession,
            "DistributionResult": _DistributionResult,
            "FailoverEvent": _FailoverEvent,
            "DistributionStats": _DistributionStats,
            "DEFAULT_STICKY_TTL_SECONDS": _DEFAULT_STICKY_TTL_SECONDS,
            "DEFAULT_MAX_CONCURRENT_TICKETS": _DEFAULT_MAX_CONCURRENT_TICKETS,
            "DEFAULT_TOKEN_BUDGET_SHARE": _DEFAULT_TOKEN_BUDGET_SHARE,
            "DEFAULT_INSTANCE_WEIGHT": _DEFAULT_INSTANCE_WEIGHT,
            "OVERLOAD_THRESHOLD_PCT": _OVERLOAD_THRESHOLD_PCT,
            "QUEUE_PRESSURE_WEIGHT_FACTOR": _QUEUE_PRESSURE_WEIGHT_FACTOR,
            "REBALANCE_MIN_DIFFERENCE": _REBALANCE_MIN_DIFFERENCE,
        })


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

CO = "co_bench"


def _fresh_distributor() -> LoadAwareDistributor:
    d = LoadAwareDistributor()
    d.clear_company_data(CO)
    return d


def _make_instance(
    instance_id: str = "inst_1",
    variant_type: str = "mini_parwa",
    max_concurrent: int = 50,
    weight: float = 1.0,
    status: InstanceStatus = InstanceStatus.ACTIVE,
) -> InstanceInfo:
    return InstanceInfo(
        instance_id=instance_id,
        company_id=CO,
        variant_type=variant_type,
        status=status,
        capacity_config={
            "max_concurrent_tickets": max_concurrent,
            "token_budget_share": DEFAULT_TOKEN_BUDGET_SHARE,
        },
        weight=weight,
    )


# ═══════════════════════════════════════════════════════════════════
# 1. InstanceInfo Properties and Derived Helpers
# ═══════════════════════════════════════════════════════════════════


class TestInstanceInfoProperties:
    """InstanceInfo derived property calculations."""

    def test_max_concurrent_returns_from_config(self):
        inst = _make_instance(max_concurrent=100)
        assert inst.max_concurrent == 100

    def test_max_concurrent_defaults_when_missing(self):
        inst = InstanceInfo(
            instance_id="i1", company_id=CO, variant_type="parwa",
            capacity_config={},
        )
        assert inst.max_concurrent == DEFAULT_MAX_CONCURRENT_TICKETS

    def test_token_budget_returns_from_config(self):
        inst = InstanceInfo(
            instance_id="i1", company_id=CO, variant_type="parwa",
            capacity_config={"token_budget_share": 500_000},
        )
        assert inst.token_budget == 500_000

    def test_utilization_pct_zero_load(self):
        inst = _make_instance(max_concurrent=50)
        assert inst.utilization_pct == 0.0

    def test_utilization_pct_half_load(self):
        inst = _make_instance(max_concurrent=50)
        inst.current_load = 25
        assert inst.utilization_pct == 0.5

    def test_utilization_pct_full_load(self):
        inst = _make_instance(max_concurrent=50)
        inst.current_load = 50
        assert inst.utilization_pct == 1.0

    def test_utilization_pct_zero_capacity_returns_one(self):
        inst = InstanceInfo(
            instance_id="i1", company_id=CO, variant_type="parwa",
            capacity_config={"max_concurrent_tickets": 0},
        )
        assert inst.utilization_pct == 1.0

    def test_effective_load_includes_queue(self):
        inst = _make_instance(max_concurrent=50)
        inst.current_load = 10
        inst.queued_count = 20
        # effective = 10 + 20 * 0.5 = 20
        assert inst.effective_load == 20.0

    def test_available_capacity_at_zero(self):
        inst = _make_instance(max_concurrent=50)
        assert inst.available_capacity == 50

    def test_available_capacity_clamped_to_zero(self):
        inst = _make_instance(max_concurrent=50)
        inst.current_load = 60
        assert inst.available_capacity == 0

    def test_is_routable_active(self):
        inst = _make_instance(status=InstanceStatus.ACTIVE)
        assert inst.is_routable is True

    def test_is_routable_warming(self):
        inst = _make_instance(status=InstanceStatus.WARMING)
        assert inst.is_routable is True

    def test_is_routable_overloaded(self):
        inst = _make_instance(status=InstanceStatus.OVERLOADED)
        assert inst.is_routable is False

    def test_is_routable_unhealthy(self):
        inst = _make_instance(status=InstanceStatus.UNHEALTHY)
        assert inst.is_routable is False

    def test_is_routable_inactive(self):
        inst = _make_instance(status=InstanceStatus.INACTIVE)
        assert inst.is_routable is False

    def test_is_overloaded_at_threshold(self):
        inst = _make_instance(max_concurrent=100)
        inst.current_load = 90
        assert inst.is_overloaded is True

    def test_is_overloaded_below_threshold(self):
        inst = _make_instance(max_concurrent=100)
        inst.current_load = 89
        assert inst.is_overloaded is False


# ═══════════════════════════════════════════════════════════════════
# 2. StickySession Lifecycle and TTL
# ═══════════════════════════════════════════════════════════════════


class TestStickySessionLifecycle:
    """StickySession TTL, expiration, and touch refresh."""

    def test_fresh_session_not_expired(self):
        session = StickySession(session_key="tkt_1", instance_id="inst_1")
        assert session.is_expired is False

    def test_expired_session_when_ttl_exceeded(self):
        session = StickySession(
            session_key="tkt_1", instance_id="inst_1", ttl_seconds=0.001,
        )
        time.sleep(0.01)
        assert session.is_expired is True

    def test_touch_refreshes_last_used(self):
        session = StickySession(session_key="tkt_1", instance_id="inst_1")
        old_last_used = session.last_used
        time.sleep(0.005)
        session.touch()
        assert session.last_used > old_last_used

    def test_age_seconds_non_negative(self):
        session = StickySession(session_key="tkt_1", instance_id="inst_1")
        assert session.age_seconds >= 0

    def test_touch_prevents_expiry(self):
        session = StickySession(
            session_key="tkt_1", instance_id="inst_1", ttl_seconds=1.0,
        )
        time.sleep(0.5)
        session.touch()
        time.sleep(0.5)
        assert session.is_expired is False

    def test_default_ttl_is_one_hour(self):
        session = StickySession(session_key="tkt_1", instance_id="inst_1")
        assert session.ttl_seconds == 3600.0

    def test_custom_ttl_accepted(self):
        session = StickySession(
            session_key="tkt_1", instance_id="inst_1", ttl_seconds=7200.0,
        )
        assert session.ttl_seconds == 7200.0


# ═══════════════════════════════════════════════════════════════════
# 3. DistributionStats Aggregation
# ═══════════════════════════════════════════════════════════════════


class TestDistributionStats:
    """DistributionStats properties and to_dict."""

    def test_sticky_hit_rate_zero_when_no_lookups(self):
        stats = DistributionStats()
        assert stats.sticky_hit_rate == 0.0

    def test_sticky_hit_rate_100_percent(self):
        stats = DistributionStats(sticky_hits=10, sticky_misses=0)
        assert stats.sticky_hit_rate == 100.0

    def test_sticky_hit_rate_50_percent(self):
        stats = DistributionStats(sticky_hits=5, sticky_misses=5)
        assert stats.sticky_hit_rate == 50.0

    def test_sticky_hit_rate_rounded(self):
        stats = DistributionStats(sticky_hits=1, sticky_misses=3)
        assert stats.sticky_hit_rate == 25.0

    def test_to_dict_has_all_keys(self):
        stats = DistributionStats(
            sticky_hits=1, sticky_misses=2, round_robin_routes=3,
            failover_count=4, total_distributions=10,
        )
        d = stats.to_dict()
        assert d["sticky_hits"] == 1
        assert d["sticky_misses"] == 2
        assert d["round_robin_routes"] == 3
        assert d["failover_count"] == 4
        assert d["total_distributions"] == 10
        assert "sticky_hit_rate" in d

    def test_defaults_all_zero(self):
        stats = DistributionStats()
        assert stats.total_distributions == 0
        assert stats.failover_count == 0
        assert stats.no_instance_available == 0


# ═══════════════════════════════════════════════════════════════════
# 4. LoadAwareDistributor — Instance Registration
# ═══════════════════════════════════════════════════════════════════


class TestInstanceRegistration:
    """Register instances with different configs, weights, channels."""

    def setup_method(self):
        self.dist = _fresh_distributor()

    def test_register_basic_instance(self):
        inst = self.dist.register_instance(CO, "inst_1", "mini_parwa")
        assert inst is not None
        assert inst.instance_id == "inst_1"
        assert inst.variant_type == "mini_parwa"
        assert inst.company_id == CO

    def test_register_with_custom_capacity(self):
        inst = self.dist.register_instance(
            CO, "inst_2", "parwa",
            capacity_config={"max_concurrent_tickets": 200, "token_budget_share": 5_000_000},
        )
        assert inst.max_concurrent == 200
        assert inst.token_budget == 5_000_000

    def test_register_with_custom_weight(self):
        inst = self.dist.register_instance(CO, "inst_3", "parwa_high", weight=2.5)
        assert inst.weight == 2.5

    def test_register_with_custom_channels(self):
        inst = self.dist.register_instance(CO, "inst_4", "mini_parwa", channel_assignment="chat,email")
        assert inst.channel_assignment == "chat,email"

    def test_register_replaces_existing(self):
        self.dist.register_instance(CO, "inst_5", "mini_parwa", weight=1.0)
        inst = self.dist.register_instance(CO, "inst_5", "mini_parwa", weight=3.0)
        assert inst.weight == 3.0

    def test_register_with_negative_weight_uses_default(self):
        inst = self.dist.register_instance(CO, "inst_neg", "mini_parwa", weight=-1.0)
        assert inst.weight == DEFAULT_INSTANCE_WEIGHT

    def test_register_with_zero_weight_uses_default(self):
        inst = self.dist.register_instance(CO, "inst_zero", "mini_parwa", weight=0.0)
        assert inst.weight == DEFAULT_INSTANCE_WEIGHT

    def test_register_with_invalid_max_concurrent_uses_default(self):
        inst = self.dist.register_instance(
            CO, "inst_inv", "mini_parwa",
            capacity_config={"max_concurrent_tickets": -5},
        )
        assert inst.max_concurrent == DEFAULT_MAX_CONCURRENT_TICKETS

    def test_register_with_string_max_concurrent_uses_default(self):
        inst = self.dist.register_instance(
            CO, "inst_str", "mini_parwa",
            capacity_config={"max_concurrent_tickets": "bad"},
        )
        assert inst.max_concurrent == DEFAULT_MAX_CONCURRENT_TICKETS

    def test_register_returns_instance_info(self):
        inst = self.dist.register_instance(CO, "inst_ret", "parwa_high")
        assert isinstance(inst, InstanceInfo)

    def test_register_sets_created_at(self):
        inst = self.dist.register_instance(CO, "inst_ts", "mini_parwa")
        assert inst.created_at is not None
        # Should be a valid ISO-8601 string
        datetime.fromisoformat(inst.created_at)


# ═══════════════════════════════════════════════════════════════════
# 5. LoadAwareDistributor — Instance Deregistration
# ═══════════════════════════════════════════════════════════════════


class TestInstanceDeregistration:
    """Deregister instances, cleanup sticky sessions and state."""

    def setup_method(self):
        self.dist = _fresh_distributor()

    def test_deregister_existing_instance(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        assert self.dist.deregister_instance(CO, "inst_1") is True

    def test_deregister_nonexistent_instance(self):
        assert self.dist.deregister_instance(CO, "ghost") is False

    def test_deregister_clears_sticky_sessions(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.register_sticky_session(CO, "tkt_1", "inst_1")
        self.dist.deregister_instance(CO, "inst_1")
        assert self.dist.get_sticky_instance(CO, "tkt_1") is None

    def test_deregister_different_company_isolation(self):
        self.dist.register_instance("co_other", "inst_1", "mini_parwa")
        assert self.dist.deregister_instance(CO, "inst_1") is False

    def test_deregister_cleans_rr_counter(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.distribute(CO, "mini_parwa", "tkt_1")
        self.dist.deregister_instance(CO, "inst_1")
        # No more instances → RR counter should be cleaned
        assert self.dist.get_all_instances(CO, "mini_parwa") == []

    def test_deregister_with_sticky_fails_gracefully(self):
        """BC-008: deregister never raises."""
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.register_sticky_session(CO, "tkt_1", "inst_1")
        # Deregister should clean everything without error
        result = self.dist.deregister_instance(CO, "inst_1")
        assert result is True


# ═══════════════════════════════════════════════════════════════════
# 6. Load Metrics and Auto-Overload Detection
# ═══════════════════════════════════════════════════════════════════


class TestLoadMetricsAndOverload:
    """Update load, auto-overload detection, token tracking."""

    def setup_method(self):
        self.dist = _fresh_distributor()
        self.dist.register_instance(CO, "inst_1", "mini_parwa", max_concurrent=100)

    def test_update_load_basic(self):
        assert self.dist.update_instance_load(CO, "inst_1", active_tickets=30) is True

    def test_update_load_nonexistent_returns_false(self):
        assert self.dist.update_instance_load(CO, "ghost", active_tickets=10) is False

    def test_auto_overload_at_90_percent(self):
        self.dist.update_instance_load(CO, "inst_1", active_tickets=90)
        inst = self.dist.get_instance_info(CO, "inst_1")
        assert inst.status == InstanceStatus.OVERLOADED

    def test_no_auto_overload_below_90_percent(self):
        self.dist.update_instance_load(CO, "inst_1", active_tickets=89)
        inst = self.dist.get_instance_info(CO, "inst_1")
        assert inst.status == InstanceStatus.ACTIVE

    def test_negative_tickets_clamped_to_zero(self):
        self.dist.update_instance_load(CO, "inst_1", active_tickets=-5, queued_tickets=-3)
        inst = self.dist.get_instance_info(CO, "inst_1")
        assert inst.current_load == 0
        assert inst.queued_count == 0

    def test_tokens_used_updated(self):
        self.dist.update_instance_load(CO, "inst_1", tokens_used=50000)
        inst = self.dist.get_instance_info(CO, "inst_1")
        assert inst.tokens_used_today == 50000

    def test_tokens_zero_does_not_overwrite(self):
        self.dist.update_instance_load(CO, "inst_1", tokens_used=50000)
        self.dist.update_instance_load(CO, "inst_1", tokens_used=0)
        inst = self.dist.get_instance_info(CO, "inst_1")
        assert inst.tokens_used_today == 50000

    def test_queued_tickets_tracked(self):
        self.dist.update_instance_load(CO, "inst_1", queued_tickets=15)
        inst = self.dist.get_instance_info(CO, "inst_1")
        assert inst.queued_count == 15

    def test_auto_overload_with_queued_tickets(self):
        # 45 active + 90 queued: effective_load = 45 + 90*0.5 = 90
        # But overload is based on utilization_pct (current_load/max_concurrent)
        # 90/100 = 0.9 >= OVERLOAD_THRESHOLD
        self.dist.update_instance_load(CO, "inst_1", active_tickets=90, queued_tickets=10)
        inst = self.dist.get_instance_info(CO, "inst_1")
        assert inst.status == InstanceStatus.OVERLOADED


# ═══════════════════════════════════════════════════════════════════
# 7. Instance Status Transitions and Recovery
# ═══════════════════════════════════════════════════════════════════


class TestInstanceStatusTransitions:
    """Mark instances unhealthy, overloaded, recovery."""

    def setup_method(self):
        self.dist = _fresh_distributor()
        self.dist.register_instance(CO, "inst_1", "mini_parwa", max_concurrent=100)

    def test_mark_unhealthy(self):
        assert self.dist.update_instance_status(CO, "inst_1", InstanceStatus.UNHEALTHY) is True
        inst = self.dist.get_instance_info(CO, "inst_1")
        assert inst.status == InstanceStatus.UNHEALTHY

    def test_mark_inactive(self):
        self.dist.update_instance_status(CO, "inst_1", InstanceStatus.INACTIVE)
        inst = self.dist.get_instance_info(CO, "inst_1")
        assert inst.status == InstanceStatus.INACTIVE

    def test_mark_warming(self):
        self.dist.update_instance_status(CO, "inst_1", InstanceStatus.WARMING)
        inst = self.dist.get_instance_info(CO, "inst_1")
        assert inst.status == InstanceStatus.WARMING

    def test_nonexistent_instance_returns_false(self):
        assert self.dist.update_instance_status(CO, "ghost", InstanceStatus.ACTIVE) is False

    def test_unhealthy_invalidates_sticky_sessions(self):
        self.dist.register_sticky_session(CO, "tkt_1", "inst_1")
        self.dist.update_instance_status(CO, "inst_1", InstanceStatus.UNHEALTHY)
        stats = self.dist.get_distribution_stats(CO)
        assert stats["routing_stats"]["sticky_expired"] >= 1

    def test_overloaded_instance_not_auto_marked_overloaded_twice(self):
        """Setting OVERLOADED on instance that is already OVERLOADED
        but below threshold should auto-recover to ACTIVE."""
        self.dist.update_instance_load(CO, "inst_1", active_tickets=95)
        assert self.dist.get_instance_info(CO, "inst_1").status == InstanceStatus.OVERLOADED
        # Load drops below threshold
        self.dist.update_instance_load(CO, "inst_1", active_tickets=50)
        self.dist.update_instance_status(CO, "inst_1", InstanceStatus.OVERLOADED)
        inst = self.dist.get_instance_info(CO, "inst_1")
        assert inst.status == InstanceStatus.ACTIVE

    def test_recover_from_unhealthy(self):
        self.dist.update_instance_status(CO, "inst_1", InstanceStatus.UNHEALTHY)
        self.dist.update_instance_status(CO, "inst_1", InstanceStatus.ACTIVE)
        inst = self.dist.get_instance_info(CO, "inst_1")
        assert inst.status == InstanceStatus.ACTIVE


# ═══════════════════════════════════════════════════════════════════
# 8. Main Distribution Routing
# ═══════════════════════════════════════════════════════════════════


class TestDistributionRouting:
    """Main distribute() — sticky, round-robin, least-loaded."""

    def setup_method(self):
        self.dist = _fresh_distributor()

    def test_distribute_single_instance(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        assert result.instance_id == "inst_1"
        assert result.routing_method in (
            RoutingMethod.ROUND_ROBIN.value,
            RoutingMethod.LEAST_LOADED.value,
        )

    def test_distribute_creates_sticky_session(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.distribute(CO, "mini_parwa", "tkt_1")
        # Second call should use sticky
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        assert result.routing_method == RoutingMethod.STICKY.value

    def test_distribute_no_instances_returns_empty(self):
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        assert result.instance_id == ""
        assert result.routing_method == RoutingMethod.NO_INSTANCE_AVAILABLE.value

    def test_distribute_channel_filtering(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", channel_assignment="email")
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1", preferred_channel="chat")
        assert result.instance_id == ""

    def test_distribute_channel_match(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", channel_assignment="chat,email")
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1", preferred_channel="chat")
        assert result.instance_id == "inst_1"

    def test_distribute_all_unhealthy_returns_empty(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.update_instance_status(CO, "inst_1", InstanceStatus.UNHEALTHY)
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        assert result.instance_id == ""

    def test_distribute_all_inactive_returns_empty(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.update_instance_status(CO, "inst_1", InstanceStatus.INACTIVE)
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        assert result.instance_id == ""

    def test_round_robin_cycles_instances(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", weight=1.0)
        self.dist.register_instance(CO, "inst_2", "mini_parwa", weight=1.0)
        ids = set()
        for i in range(20):
            result = self.dist.distribute(CO, "mini_parwa", f"tkt_rr_{i}")
            ids.add(result.instance_id)
        assert "inst_1" in ids
        assert "inst_2" in ids

    def test_weighted_round_robin_prefers_higher_weight(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", weight=5.0)
        self.dist.register_instance(CO, "inst_2", "mini_parwa", weight=1.0)
        inst_1_count = 0
        for i in range(60):
            result = self.dist.distribute(CO, "mini_parwa", f"tkt_w_{i}")
            if result.instance_id == "inst_1":
                inst_1_count += 1
        # inst_1 should get roughly 5/6 of traffic
        assert inst_1_count > 30

    def test_least_loaded_fallback_when_all_overloaded(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", max_concurrent=100)
        self.dist.register_instance(CO, "inst_2", "mini_parwa", max_concurrent=100)
        self.dist.update_instance_load(CO, "inst_1", active_tickets=95)
        self.dist.update_instance_load(CO, "inst_2", active_tickets=92)
        result = self.dist.distribute(CO, "mini_parwa", "tkt_ll_1")
        # Should pick inst_2 (less loaded)
        assert result.routing_method == RoutingMethod.LEAST_LOADED.value
        assert result.instance_id == "inst_2"

    def test_customer_id_sticky_routing(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        # First ticket establishes sticky via customer_id
        self.dist.distribute(CO, "mini_parwa", "tkt_a", customer_id="cust_1")
        # Second ticket with same customer_id should be sticky
        result = self.dist.distribute(CO, "mini_parwa", "tkt_b", customer_id="cust_1")
        assert result.routing_method == RoutingMethod.STICKY.value

    def test_distribute_result_has_company_id(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        assert result.company_id == CO

    def test_distribute_result_variant_type(self):
        self.dist.register_instance(CO, "inst_1", "parwa_high")
        result = self.dist.distribute(CO, "parwa_high", "tkt_1")
        assert result.variant_type == "parwa_high"


# ═══════════════════════════════════════════════════════════════════
# 9. Load-Aware Distribution Across Variant Capacities
# ═══════════════════════════════════════════════════════════════════


class TestLoadAwareVariantDistribution:
    """Distribution across Mini, PARWA, and PARWA High variant pools."""

    def setup_method(self):
        self.dist = _fresh_distributor()

    def test_mini_parwa_low_capacity_default(self):
        inst = self.dist.register_instance(CO, "mini_1", "mini_parwa", max_concurrent=20)
        assert inst.max_concurrent == 20

    def test_parwa_medium_capacity(self):
        inst = self.dist.register_instance(CO, "parwa_1", "parwa", max_concurrent=100)
        assert inst.max_concurrent == 100

    def test_parwa_high_high_capacity(self):
        inst = self.dist.register_instance(CO, "high_1", "parwa_high", max_concurrent=500)
        assert inst.max_concurrent == 500

    def test_distribute_within_variant_pool(self):
        self.dist.register_instance(CO, "mini_1", "mini_parwa")
        self.dist.register_instance(CO, "parwa_1", "parwa")
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        assert result.instance_id == "mini_1"
        assert result.variant_type == "mini_parwa"

    def test_separate_rr_counters_per_variant(self):
        self.dist.register_instance(CO, "mini_1", "mini_parwa")
        self.dist.register_instance(CO, "mini_2", "mini_parwa")
        self.dist.register_instance(CO, "parwa_1", "parwa")
        self.dist.register_instance(CO, "parwa_2", "parwa")

        # Distribute across mini_parwa
        self.dist.distribute(CO, "mini_parwa", "tkt_a")
        # Distribute across parwa
        self.dist.distribute(CO, "parwa", "tkt_b")

        # Both should get sticky on second call
        r1 = self.dist.distribute(CO, "mini_parwa", "tkt_a")
        r2 = self.dist.distribute(CO, "parwa", "tkt_b")
        assert r1.routing_method == RoutingMethod.STICKY.value
        assert r2.routing_method == RoutingMethod.STICKY.value

    def test_parwa_high_receives_all_14_techniques(self):
        """PARWA High gets full technique pipeline with higher capacity."""
        inst = self.dist.register_instance(
            CO, "high_1", "parwa_high",
            max_concurrent=500,
            capacity_config={"token_budget_share": 10_000_000},
        )
        assert inst.max_concurrent == 500
        assert inst.token_budget == 10_000_000

    def test_mini_parwa_token_budget_enforcement(self):
        """Mini PARWA has lower token budget."""
        inst = self.dist.register_instance(
            CO, "mini_1", "mini_parwa",
            capacity_config={"token_budget_share": 200_000},
        )
        assert inst.token_budget == 200_000

    def test_load_summary_across_variants(self):
        self.dist.register_instance(CO, "mini_1", "mini_parwa", max_concurrent=20)
        self.dist.register_instance(CO, "parwa_1", "parwa", max_concurrent=100)
        self.dist.register_instance(CO, "high_1", "parwa_high", max_concurrent=500)

        summary = self.dist.get_instance_load_summary(CO)
        assert summary["total_instances"] == 3
        assert summary["total_capacity"] == 620  # 20 + 100 + 500

    def test_load_summary_filtered_by_variant(self):
        self.dist.register_instance(CO, "mini_1", "mini_parwa", max_concurrent=20)
        self.dist.register_instance(CO, "parwa_1", "parwa", max_concurrent=100)

        summary = self.dist.get_instance_load_summary(CO, variant_type="parwa")
        assert summary["total_instances"] == 1
        assert summary["total_capacity"] == 100

    def test_company_isolation_across_variants(self):
        self.dist.register_instance(CO, "mini_1", "mini_parwa")
        self.dist.register_instance("co_other", "mini_2", "mini_parwa")

        r1 = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        assert r1.instance_id == "mini_1"

        r2 = self.dist.distribute("co_other", "mini_parwa", "tkt_2")
        assert r2.instance_id == "mini_2"


# ═══════════════════════════════════════════════════════════════════
# 10. Priority Queue Management and Load Shedding
# ═══════════════════════════════════════════════════════════════════


class TestPriorityQueueAndLoadShedding:
    """Load shedding under pressure, overloaded handling."""

    def setup_method(self):
        self.dist = _fresh_distributor()

    def test_all_overloaded_still_routes_least_loaded(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", max_concurrent=100)
        self.dist.register_instance(CO, "inst_2", "mini_parwa", max_concurrent=100)
        self.dist.update_instance_load(CO, "inst_1", active_tickets=95)
        self.dist.update_instance_load(CO, "inst_2", active_tickets=91)

        result = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        assert result.instance_id == "inst_2"  # less loaded
        assert result.routing_method == RoutingMethod.LEAST_LOADED.value

    def test_no_instance_available_when_none_routable(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.update_instance_status(CO, "inst_1", InstanceStatus.UNHEALTHY)
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        assert result.routing_method == RoutingMethod.NO_INSTANCE_AVAILABLE.value

    def test_stats_track_no_instance_available(self):
        self.dist.distribute(CO, "mini_parwa", "tkt_1")
        stats = self.dist.get_distribution_stats(CO)
        assert stats["routing_stats"]["no_instance_available"] == 1

    def test_overloaded_instance_auto_transitions(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", max_concurrent=100)
        self.dist.update_instance_load(CO, "inst_1", active_tickets=95)
        inst = self.dist.get_instance_info(CO, "inst_1")
        assert inst.status == InstanceStatus.OVERLOADED

    def test_overload_with_channel_filter_load_sheds(self):
        """When all instances matching channel are overloaded, no instance available."""
        self.dist.register_instance(
            CO, "inst_1", "mini_parwa", max_concurrent=10,
            channel_assignment="chat",
        )
        self.dist.update_instance_load(CO, "inst_1", active_tickets=10)
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1", preferred_channel="chat")
        # All capacity used, least_loaded still picks it
        assert result.instance_id == "inst_1"
        assert result.routing_method == RoutingMethod.LEAST_LOADED.value

    def test_warming_instance_receives_traffic(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", status=InstanceStatus.WARMING)
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        assert result.instance_id == "inst_1"

    def test_load_shedding_multiple_companies(self):
        """Load shedding for one company doesn't affect another."""
        self.dist.register_instance(CO, "inst_1", "mini_parwa", max_concurrent=10)
        self.dist.register_instance("co_other", "inst_2", "mini_parwa", max_concurrent=10)
        self.dist.update_instance_load(CO, "inst_1", active_tickets=10)

        r1 = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        r2 = self.dist.distribute("co_other", "mini_parwa", "tkt_2")

        # co_other should still route normally
        assert r2.instance_id == "inst_2"
        assert r2.routing_method != RoutingMethod.NO_INSTANCE_AVAILABLE.value


# ═══════════════════════════════════════════════════════════════════
# 11. Weight Rebalancing
# ═══════════════════════════════════════════════════════════════════


class TestWeightRebalancing:
    """Dynamic weight adjustment based on load."""

    def setup_method(self):
        self.dist = _fresh_distributor()

    def test_rebalance_needs_at_least_two_instances(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        result = self.dist.rebalance_weights(CO, "mini_parwa")
        assert result["skipped"] is True

    def test_rebalance_boosts_underloaded(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", max_concurrent=100, weight=1.0)
        self.dist.register_instance(CO, "inst_2", "mini_parwa", max_concurrent=100, weight=1.0)
        self.dist.update_instance_load(CO, "inst_1", active_tickets=5)   # 5% util
        self.dist.update_instance_load(CO, "inst_2", active_tickets=80)  # 80% util

        result = self.dist.rebalance_weights(CO, "mini_parwa")
        assert result["skipped"] is False
        assert result["changes_count"] >= 1

    def test_rebalance_reduces_overloaded(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", max_concurrent=100, weight=1.0)
        self.dist.register_instance(CO, "inst_2", "mini_parwa", max_concurrent=100, weight=1.0)
        self.dist.update_instance_load(CO, "inst_1", active_tickets=95)
        self.dist.update_instance_load(CO, "inst_2", active_tickets=10)

        result = self.dist.rebalance_weights(CO, "mini_parwa")
        assert result["skipped"] is False
        # inst_1 weight should decrease
        inst_1 = self.dist.get_instance_info(CO, "inst_1")
        assert inst_1.weight < 1.0

    def test_rebalance_no_change_when_balanced(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", max_concurrent=100, weight=1.0)
        self.dist.register_instance(CO, "inst_2", "mini_parwa", max_concurrent=100, weight=1.0)
        self.dist.update_instance_load(CO, "inst_1", active_tickets=50)
        self.dist.update_instance_load(CO, "inst_2", active_tickets=50)

        result = self.dist.rebalance_weights(CO, "mini_parwa")
        # 50% utilization is in the moderate range (0.3-0.7) → no change
        assert result["changes_count"] == 0

    def test_rebalance_clamps_weight_range(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", max_concurrent=100, weight=1.0)
        self.dist.register_instance(CO, "inst_2", "mini_parwa", max_concurrent=100, weight=1.0)
        # 99% util → big reduction
        self.dist.update_instance_load(CO, "inst_1", active_tickets=99)
        self.dist.update_instance_load(CO, "inst_2", active_tickets=1)

        result = self.dist.rebalance_weights(CO, "mini_parwa")
        inst_1 = self.dist.get_instance_info(CO, "inst_1")
        assert 0.05 <= inst_1.weight <= 10.0

    def test_rebalance_returns_current_weights(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", weight=2.0)
        self.dist.register_instance(CO, "inst_2", "mini_parwa", weight=3.0)
        result = self.dist.rebalance_weights(CO, "mini_parwa")
        assert "current_weights" in result
        assert "inst_1" in result["current_weights"]
        assert "inst_2" in result["current_weights"]

    def test_rebalance_includes_timestamp(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", weight=2.0)
        self.dist.register_instance(CO, "inst_2", "mini_parwa", weight=3.0)
        result = self.dist.rebalance_weights(CO, "mini_parwa")
        assert "rebalanced_at_utc" in result


# ═══════════════════════════════════════════════════════════════════
# 12. Failover Routing
# ═══════════════════════════════════════════════════════════════════


class TestFailoverRouting:
    """Failover when instances go unhealthy."""

    def setup_method(self):
        self.dist = _fresh_distributor()

    def test_failover_to_healthy_instance(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.register_instance(CO, "inst_2", "mini_parwa")
        # Pin ticket to inst_1
        self.dist.register_sticky_session(CO, "tkt_1", "inst_1")
        # Mark inst_1 unhealthy
        self.dist.update_instance_status(CO, "inst_1", InstanceStatus.UNHEALTHY)

        # Distribution should failover to inst_2
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        assert result.instance_id == "inst_2"
        assert result.routing_method != RoutingMethod.NO_INSTANCE_AVAILABLE.value

    def test_failover_records_event(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.register_instance(CO, "inst_2", "mini_parwa")
        self.dist.register_sticky_session(CO, "tkt_1", "inst_1")

        result = self.dist.failover_ticket(CO, "tkt_1", "inst_1", "overloaded")
        assert result is not None
        assert result.instance_id == "inst_2"

    def test_failover_no_available_returns_none(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        result = self.dist.failover_ticket(CO, "tkt_1", "inst_1", "overloaded")
        # No other instance available
        assert result is None

    def test_failover_history_tracked(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.register_instance(CO, "inst_2", "mini_parwa")
        self.dist.failover_ticket(CO, "tkt_1", "inst_1", "unhealthy")

        history = self.dist.get_failover_history(CO)
        assert len(history) >= 1
        assert history[0]["from_instance_id"] == "inst_1"
        assert history[0]["to_instance_id"] == "inst_2"

    def test_failover_from_nonexistent_instance_returns_none(self):
        result = self.dist.failover_ticket(CO, "tkt_1", "ghost", "unhealthy")
        assert result is None

    def test_failover_clears_sticky_session(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.register_instance(CO, "inst_2", "mini_parwa")
        self.dist.register_sticky_session(CO, "tkt_1", "inst_1")
        self.dist.failover_ticket(CO, "tkt_1", "inst_1", "unhealthy")
        # Old sticky should be cleared, new one set on inst_2
        pinned = self.dist.get_sticky_instance(CO, "tkt_1")
        assert pinned == "inst_2"

    def test_multiple_failovers_tracked(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.register_instance(CO, "inst_2", "mini_parwa")
        self.dist.failover_ticket(CO, "tkt_1", "inst_1", "unhealthy")
        self.dist.failover_ticket(CO, "tkt_2", "inst_1", "overloaded")

        history = self.dist.get_failover_history(CO)
        assert len(history) == 2


# ═══════════════════════════════════════════════════════════════════
# 13. Performance Metric Collection and Aggregation
# ═══════════════════════════════════════════════════════════════════


class TestPerformanceMetricCollection:
    """Stats, failover history, load summaries."""

    def setup_method(self):
        self.dist = _fresh_distributor()

    def test_stats_initial_state(self):
        stats = self.dist.get_distribution_stats(CO)
        assert stats["routing_stats"]["total_distributions"] == 0
        assert stats["active_sticky_sessions"] == 0
        assert stats["total_failover_events"] == 0

    def test_stats_tracks_distributions(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.distribute(CO, "mini_parwa", "tkt_1")
        stats = self.dist.get_distribution_stats(CO)
        assert stats["routing_stats"]["total_distributions"] == 1

    def test_stats_tracks_sticky_hits(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.distribute(CO, "mini_parwa", "tkt_1")
        self.dist.distribute(CO, "mini_parwa", "tkt_1")  # sticky hit
        stats = self.dist.get_distribution_stats(CO)
        assert stats["routing_stats"]["sticky_hits"] == 1

    def test_stats_tracks_round_robin(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.distribute(CO, "mini_parwa", "tkt_1")
        stats = self.dist.get_distribution_stats(CO)
        assert stats["routing_stats"]["round_robin_routes"] == 1

    def test_load_summary_aggregate_utilization(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", max_concurrent=100)
        self.dist.update_instance_load(CO, "inst_1", active_tickets=50)
        summary = self.dist.get_instance_load_summary(CO)
        assert summary["aggregate_utilization_pct"] == 50.0

    def test_load_summary_zero_capacity(self):
        summary = self.dist.get_instance_load_summary(CO)
        assert summary["aggregate_utilization_pct"] == 0.0

    def test_failover_history_limited(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.register_instance(CO, "inst_2", "mini_parwa")
        for i in range(5):
            self.dist.failover_ticket(CO, f"tkt_{i}", "inst_1", "unhealthy")

        history = self.dist.get_failover_history(CO, limit=2)
        assert len(history) == 2

    def test_stats_instance_status_counts(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.register_instance(CO, "inst_2", "mini_parwa")
        self.dist.update_instance_status(CO, "inst_1", InstanceStatus.UNHEALTHY)

        stats = self.dist.get_distribution_stats(CO)
        assert stats["instance_status_counts"]["unhealthy"] == 1
        assert stats["instance_status_counts"]["active"] == 1


# ═══════════════════════════════════════════════════════════════════
# 14. SLA Enforcement Per Tier
# ═══════════════════════════════════════════════════════════════════


class TestSLAEnforcementPerTier:
    """Response time and capacity SLA enforcement for each tier."""

    def setup_method(self):
        self.dist = _fresh_distributor()

    def test_mini_parwa_faq_throughput(self):
        """Mini PARWA should handle FAQ-style tickets with fast routing."""
        self.dist.register_instance(CO, "mini_1", "mini_parwa", max_concurrent=50)
        start = time.perf_counter()
        for i in range(100):
            self.dist.distribute(CO, "mini_parwa", f"faq_tkt_{i}")
        elapsed = time.perf_counter() - start
        # 100 distributions should complete in under 2 seconds
        assert elapsed < 2.0

    def test_parwa_medium_llm_routing(self):
        """PARWA tier should route with medium-weight round-robin."""
        self.dist.register_instance(CO, "parwa_1", "parwa", max_concurrent=100, weight=2.0)
        self.dist.register_instance(CO, "parwa_2", "parwa", max_concurrent=100, weight=1.0)
        results = [self.dist.distribute(CO, "parwa", f"tkt_{i}") for i in range(30)]
        parwa_1_count = sum(1 for r in results if r.instance_id == "parwa_1")
        parwa_2_count = sum(1 for r in results if r.instance_id == "parwa_2")
        # parwa_1 should get roughly 2x traffic
        assert parwa_1_count > parwa_2_count

    def test_parwa_high_concurrent_handling(self):
        """PARWA High should handle concurrent high-load scenarios."""
        self.dist.register_instance(CO, "high_1", "parwa_high", max_concurrent=500)
        errors = []
        results = []

        def worker(tid):
            try:
                r = self.dist.distribute(CO, "parwa_high", f"high_tkt_{tid}")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        assert len(results) == 50

    def test_mini_parwa_token_budget_enforcement(self):
        """Mini PARWA has low token budget, verify tracking."""
        self.dist.register_instance(
            CO, "mini_1", "mini_parwa",
            capacity_config={"token_budget_share": 200_000},
        )
        self.dist.update_instance_load(CO, "mini_1", tokens_used=180_000)
        inst = self.dist.get_instance_info(CO, "mini_1")
        assert inst.tokens_used_today == 180_000

    def test_resolution_rate_tracking(self):
        """Track distribution as proxy for resolution capability."""
        self.dist.register_instance(CO, "parwa_1", "parwa", max_concurrent=100)
        for i in range(100):
            self.dist.distribute(CO, "parwa", f"tkt_{i}")
        stats = self.dist.get_distribution_stats(CO)
        assert stats["routing_stats"]["total_distributions"] == 100

    def test_multi_turn_conversation_sticky(self):
        """Multi-turn conversation stays on same instance."""
        self.dist.register_instance(CO, "inst_1", "parwa")
        # Turn 1
        r1 = self.dist.distribute(CO, "parwa", "conv_tkt", customer_id="cust_1")
        # Turn 2
        r2 = self.dist.distribute(CO, "parwa", "conv_tkt", customer_id="cust_1")
        # Turn 3
        r3 = self.dist.distribute(CO, "parwa", "conv_tkt", customer_id="cust_1")
        assert r1.instance_id == r2.instance_id == r3.instance_id
        assert r2.routing_method == RoutingMethod.STICKY.value
        assert r3.routing_method == RoutingMethod.STICKY.value

    def test_context_window_management_via_capacity(self):
        """Higher tier has more capacity for context windows."""
        mini = self.dist.register_instance(CO, "mini_1", "mini_parwa", max_concurrent=20)
        high = self.dist.register_instance(CO, "high_1", "parwa_high", max_concurrent=500)
        assert high.max_concurrent > mini.max_concurrent

    def test_sla_response_time_round_robin(self):
        """Round-robin distribution should complete in sub-10ms per call."""
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        times = []
        for i in range(50):
            start = time.perf_counter()
            self.dist.distribute(CO, "mini_parwa", f"sla_tkt_{i}")
            times.append((time.perf_counter() - start) * 1000)
        avg_ms = sum(times) / len(times)
        assert avg_ms < 10.0

    def test_overloaded_instance_sla_degradation(self):
        """When instance is overloaded, routing degrades to least-loaded."""
        self.dist.register_instance(CO, "inst_1", "mini_parwa", max_concurrent=100)
        self.dist.register_instance(CO, "inst_2", "mini_parwa", max_concurrent=100)
        self.dist.update_instance_load(CO, "inst_1", active_tickets=95)
        self.dist.update_instance_load(CO, "inst_2", active_tickets=5)

        result = self.dist.distribute(CO, "mini_parwa", "sla_tkt")
        assert result.routing_method == RoutingMethod.ROUND_ROBIN.value
        # Should prefer inst_2 (not overloaded)
        assert result.instance_id == "inst_2"


# ═══════════════════════════════════════════════════════════════════
# 15. Warm/Cold Variant Scaling
# ═══════════════════════════════════════════════════════════════════


class TestWarmColdVariantScaling:
    """Warming instances, inactive instances, scaling behavior."""

    def setup_method(self):
        self.dist = _fresh_distributor()

    def test_warming_instance_receives_limited_traffic(self):
        """WARMING instances should still receive traffic."""
        self.dist.register_instance(CO, "inst_1", "mini_parwa", status=InstanceStatus.WARMING)
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        assert result.instance_id == "inst_1"

    def test_inactive_instance_excluded(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", status=InstanceStatus.INACTIVE)
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        assert result.instance_id == ""

    def test_scale_up_register_new_instance(self):
        """Scale up by registering new instance."""
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.register_instance(CO, "inst_2", "mini_parwa")
        summary = self.dist.get_instance_load_summary(CO, variant_type="mini_parwa")
        assert summary["total_instances"] == 2

    def test_scale_down_deregister_instance(self):
        """Scale down by deregistering instance."""
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.register_instance(CO, "inst_2", "mini_parwa")
        self.dist.deregister_instance(CO, "inst_2")
        summary = self.dist.get_instance_load_summary(CO, variant_type="mini_parwa")
        assert summary["total_instances"] == 1

    def test_warming_to_active_transition(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", status=InstanceStatus.WARMING)
        self.dist.update_instance_status(CO, "inst_1", InstanceStatus.ACTIVE)
        inst = self.dist.get_instance_info(CO, "inst_1")
        assert inst.status == InstanceStatus.ACTIVE

    def test_active_to_inactive_drain(self):
        """Active → Inactive: instance drains and stops receiving traffic."""
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.distribute(CO, "mini_parwa", "tkt_1")
        self.dist.update_instance_status(CO, "inst_1", InstanceStatus.INACTIVE)
        result = self.dist.distribute(CO, "mini_parwa", "tkt_2")
        assert result.instance_id == ""


# ═══════════════════════════════════════════════════════════════════
# 16. Thread Safety and Concurrent Operations
# ═══════════════════════════════════════════════════════════════════


class TestThreadSafety:
    """Concurrent registration, distribution, load updates."""

    def setup_method(self):
        self.dist = _fresh_distributor()

    def test_concurrent_registrations_no_crash(self):
        errors = []

        def worker(i):
            try:
                self.dist.register_instance(CO, f"inst_{i}", "mini_parwa")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert len(errors) == 0

    def test_concurrent_distributions_no_crash(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", max_concurrent=200)
        errors = []
        results = []

        def worker(i):
            try:
                r = self.dist.distribute(CO, "mini_parwa", f"tkt_{i}")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert len(errors) == 0
        assert len(results) == 100

    def test_concurrent_load_updates_no_corruption(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", max_concurrent=100)
        errors = []

        def updater():
            try:
                for i in range(100):
                    self.dist.update_instance_load(CO, "inst_1", active_tickets=i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=updater) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert len(errors) == 0

    def test_concurrent_sticky_and_deregister(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        errors = []

        def sticky_worker(i):
            try:
                self.dist.register_sticky_session(CO, f"tkt_{i}", "inst_1")
                self.dist.get_sticky_instance(CO, f"tkt_{i}")
            except Exception as e:
                errors.append(e)

        def deregister_worker():
            try:
                time.sleep(0.01)
                self.dist.deregister_instance(CO, "inst_1")
            except Exception as e:
                errors.append(e)

        threads = (
            [threading.Thread(target=sticky_worker, args=(i,)) for i in range(20)]
            + [threading.Thread(target=deregister_worker)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert len(errors) == 0

    def test_concurrent_failover_no_duplicates(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.register_instance(CO, "inst_2", "mini_parwa")
        errors = []

        def worker(i):
            try:
                self.dist.failover_ticket(CO, f"tkt_{i}", "inst_1", "unhealthy")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════
# 17. Edge Cases
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Empty loads, max capacity, timeout scenarios."""

    def setup_method(self):
        self.dist = _fresh_distributor()

    def test_empty_company_no_crash(self):
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1")
        assert result.instance_id == ""

    def test_max_capacity_distribution(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa", max_concurrent=1)
        self.dist.update_instance_load(CO, "inst_1", active_tickets=1)
        result = self.dist.distribute(CO, "mini_parwa", "tkt_full")
        # Instance is overloaded (1/1 = 100% >= 90%)
        # Should still route via least_loaded since there's one eligible instance
        assert result.instance_id == "inst_1"

    def test_clear_nonexistent_sticky_returns_false(self):
        assert self.dist.clear_sticky_session(CO, "ghost_session") is False

    def test_get_sticky_nonexistent_returns_none(self):
        assert self.dist.get_sticky_instance(CO, "ghost") is None

    def test_register_sticky_nonexistent_instance_returns_false(self):
        assert self.dist.register_sticky_session(CO, "tkt_1", "ghost") is False

    def test_clear_company_data_removes_everything(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        self.dist.register_instance(CO, "inst_2", "parwa")
        self.dist.distribute(CO, "mini_parwa", "tkt_1")
        self.dist.distribute(CO, "parwa", "tkt_2")

        self.dist.clear_company_data(CO)

        assert self.dist.get_all_instances(CO) == []
        assert self.dist.get_distribution_stats(CO)["routing_stats"]["total_distributions"] == 0

    def test_distribute_with_empty_ticket_id(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        result = self.dist.distribute(CO, "mini_parwa", "")
        assert result.instance_id == "inst_1"

    def test_distribute_with_empty_customer_id(self):
        self.dist.register_instance(CO, "inst_1", "mini_parwa")
        result = self.dist.distribute(CO, "mini_parwa", "tkt_1", customer_id="")
        assert result.instance_id == "inst_1"

    def test_reset_round_robin_nonexistent_returns_false(self):
        assert self.dist.reset_round_robin_counter(CO, "mini_parwa") is False

    def test_get_instance_info_nonexistent_returns_none(self):
        assert self.dist.get_instance_info(CO, "ghost") is None


# ═══════════════════════════════════════════════════════════════════
# 18. Dataclass Serialisation (to_dict)
# ═══════════════════════════════════════════════════════════════════


class TestDataclassSerialisation:
    """to_dict methods for API responses."""

    def test_instance_info_to_dict(self):
        inst = _make_instance(instance_id="inst_1", variant_type="mini_parwa")
        d = inst.to_dict()
        assert d["instance_id"] == "inst_1"
        assert d["company_id"] == CO
        assert d["variant_type"] == "mini_parwa"
        assert d["status"] == "active"
        assert "utilization_pct" in d
        assert "effective_load" in d
        assert "available_capacity" in d
        assert "created_at" in d

    def test_distribution_result_to_dict(self):
        result = DistributionResult(
            instance_id="inst_1", company_id=CO, variant_type="mini_parwa",
            routing_method="round_robin", load_at_routing=10, capacity=50,
            reason="test",
        )
        d = result.to_dict()
        assert d["instance_id"] == "inst_1"
        assert d["routing_method"] == "round_robin"
        assert d["load_at_routing"] == 10
        assert d["capacity"] == 50

    def test_failover_event_to_dict(self):
        evt = FailoverEvent(
            ticket_id="tkt_1", company_id=CO,
            from_instance_id="inst_1", to_instance_id="inst_2",
            reason="unhealthy",
        )
        d = evt.to_dict()
        assert d["ticket_id"] == "tkt_1"
        assert d["from_instance_id"] == "inst_1"
        assert d["to_instance_id"] == "inst_2"
        assert d["timestamp"] is not None

    def test_distribution_stats_to_dict(self):
        stats = DistributionStats(
            sticky_hits=10, sticky_misses=5, round_robin_routes=20,
            total_distributions=35,
        )
        d = stats.to_dict()
        assert d["sticky_hits"] == 10
        assert d["sticky_hit_rate"] > 0


# ═══════════════════════════════════════════════════════════════════
# 19. Constants Validation
# ═══════════════════════════════════════════════════════════════════


class TestConstantsValidation:
    """Verify module-level constants have expected values."""

    def test_overload_threshold_is_90_percent(self):
        assert OVERLOAD_THRESHOLD_PCT == 0.90

    def test_default_sticky_ttl_is_one_hour(self):
        assert DEFAULT_STICKY_TTL_SECONDS == 3600.0

    def test_default_max_concurrent_is_50(self):
        assert DEFAULT_MAX_CONCURRENT_TICKETS == 50

    def test_default_token_budget_is_1m(self):
        assert DEFAULT_TOKEN_BUDGET_SHARE == 1_000_000

    def test_default_instance_weight_is_1(self):
        assert DEFAULT_INSTANCE_WEIGHT == 1.0

    def test_queue_pressure_factor(self):
        assert QUEUE_PRESSURE_WEIGHT_FACTOR == 0.5

    def test_rebalance_min_difference(self):
        assert REBALANCE_MIN_DIFFERENCE == 0.1

    def test_instance_status_has_five_members(self):
        assert len(InstanceStatus) == 5

    def test_routing_method_has_five_members(self):
        assert len(RoutingMethod) == 5

    def test_failover_reason_has_five_members(self):
        assert len(FailoverReason) == 5

    def test_instance_status_values(self):
        assert InstanceStatus.ACTIVE.value == "active"
        assert InstanceStatus.WARMING.value == "warming"
        assert InstanceStatus.OVERLOADED.value == "overloaded"
        assert InstanceStatus.UNHEALTHY.value == "unhealthy"
        assert InstanceStatus.INACTIVE.value == "inactive"


# ═══════════════════════════════════════════════════════════════════
# 20. Sticky Session Management API
# ═══════════════════════════════════════════════════════════════════


class TestStickySessionManagement:
    """Register, get, clear sticky sessions."""

    def setup_method(self):
        self.dist = _fresh_distributor()
        self.dist.register_instance(CO, "inst_1", "mini_parwa")

    def test_register_and_retrieve_sticky(self):
        assert self.dist.register_sticky_session(CO, "tkt_1", "inst_1") is True
        assert self.dist.get_sticky_instance(CO, "tkt_1") == "inst_1"

    def test_clear_sticky_session(self):
        self.dist.register_sticky_session(CO, "tkt_1", "inst_1")
        assert self.dist.clear_sticky_session(CO, "tkt_1") is True
        assert self.dist.get_sticky_instance(CO, "tkt_1") is None

    def test_repin_to_different_instance(self):
        self.dist.register_instance(CO, "inst_2", "mini_parwa")
        self.dist.register_sticky_session(CO, "tkt_1", "inst_1")
        self.dist.register_sticky_session(CO, "tkt_1", "inst_2")
        assert self.dist.get_sticky_instance(CO, "tkt_1") == "inst_2"

    def test_get_instance_sticky_sessions(self):
        self.dist.register_sticky_session(CO, "tkt_1", "inst_1")
        self.dist.register_sticky_session(CO, "tkt_2", "inst_1")
        sessions = self.dist.get_instance_sticky_sessions(CO, "inst_1")
        assert len(sessions) == 2
        keys = {s["session_key"] for s in sessions}
        assert keys == {"tkt_1", "tkt_2"}

    def test_expired_sticky_returns_none(self):
        self.dist.register_sticky_session(CO, "tkt_exp", "inst_1", ttl_seconds=0.001)
        time.sleep(0.01)
        assert self.dist.get_sticky_instance(CO, "tkt_exp") is None

    def test_custom_ttl_sticky(self):
        self.dist.register_sticky_session(CO, "tkt_custom", "inst_1", ttl_seconds=7200.0)
        time.sleep(0.01)
        assert self.dist.get_sticky_instance(CO, "tkt_custom") == "inst_1"

    def test_get_instance_sticky_sessions_empty(self):
        sessions = self.dist.get_instance_sticky_sessions(CO, "inst_1")
        assert sessions == []
