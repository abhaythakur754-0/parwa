"""
Week 8 Day 1 Part C: Unit tests for Variant Orchestration Service (SG-38).

Tests are SOURCE OF TRUTH. If a test fails, fix the application code.
NEVER modify tests to pass.
"""

import json
import os
import pytest

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only_not_prod"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_not_prod"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

from datetime import datetime

from database.base import engine, SessionLocal, Base
from database.models.core import Company
from database.models.variant_engine import (
    VariantInstance,
    VariantWorkloadDistribution,
)
from backend.app.services.variant_orchestration_service import (
    VARIANT_PRIORITY,
    VALID_STRATEGIES,
    VALID_DISTRIBUTION_STATUSES,
    DEFAULT_MAX_CONCURRENT,
    REBALANCE_THRESHOLD_PCT,
    _validate_company_id,
    _validate_strategy,
    _parse_capacity,
    _round_robin_counters,
    _get_rr_index,
    RoundRobinStrategy,
    LeastLoadedStrategy,
    ChannelPinnedStrategy,
    VariantPriorityStrategy,
    DISTRIBUTION_STRATEGIES,
    select_instance,
    route_ticket,
    get_instance_load,
    get_all_instance_loads,
    rebalance_workload,
    escalate_ticket,
    complete_ticket_assignment,
    get_distribution_history,
    get_orchestration_summary,
)
from backend.app.exceptions import ParwaBaseError


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _setup_db():
    """Create all tables and provide a fresh session."""
    Base.metadata.create_all(bind=engine)
    _round_robin_counters.clear()
    yield
    Base.metadata.drop_all(bind=engine)
    _round_robin_counters.clear()


def _make_company(db, cid="comp_1", name="Test Corp"):
    c = Company(id=cid, name=name, industry="saas",
                subscription_tier="growth", subscription_status="active")
    db.add(c)
    db.commit()
    return c


def _make_instance(db, cid="comp_1", iid="inst_1", vtype="mini_parwa",
                   name=None, status="active", channels=None, cap=None,
                   active_tickets=0, total_tickets=0):
    inst = VariantInstance(
        id=iid, company_id=cid,
        instance_name=name or f"{vtype} test",
        variant_type=vtype, status=status,
        channel_assignment=json.dumps(channels or []),
        capacity_config=json.dumps(cap or {}),
        active_tickets_count=active_tickets,
        total_tickets_handled=total_tickets,
    )
    db.add(inst)
    db.commit()
    return inst


def _make_ticket(db, cid="comp_1", tid="tick_1"):
    ticket = __import__("database.models.tickets", fromlist=["Ticket"]).Ticket(
        id=tid, company_id=cid, channel="email",
    )
    db.add(ticket)
    db.commit()
    return ticket


def _make_distribution(db, cid="comp_1", iid="inst_1", tid="tick_1",
                       strategy="least_loaded", status="assigned"):
    dist = VariantWorkloadDistribution(
        company_id=cid, instance_id=iid, ticket_id=tid,
        distribution_strategy=strategy,
        assigned_at=datetime.utcnow(), status=status,
    )
    db.add(dist)
    db.commit()
    return dist


# ══════════════════════════════════════════════════════════════════
# CONSTANTS TESTS
# ══════════════════════════════════════════════════════════════════

class TestConstants:
    def test_variant_priority_ordering(self):
        assert VARIANT_PRIORITY["mini_parwa"] == 1
        assert VARIANT_PRIORITY["parwa"] == 2
        assert VARIANT_PRIORITY["parwa_high"] == 3

    def test_valid_strategies_has_all_four(self):
        assert "round_robin" in VALID_STRATEGIES
        assert "least_loaded" in VALID_STRATEGIES
        assert "channel_pinned" in VALID_STRATEGIES
        assert "variant_priority" in VALID_STRATEGIES

    def test_valid_distribution_statuses(self):
        for s in ["assigned", "in_progress", "completed", "escalated", "rebalanced"]:
            assert s in VALID_DISTRIBUTION_STATUSES

    def test_default_max_concurrent(self):
        assert DEFAULT_MAX_CONCURRENT == 50

    def test_rebalance_threshold(self):
        assert REBALANCE_THRESHOLD_PCT == 80

    def test_distribution_strategies_registered(self):
        for name in VALID_STRATEGIES:
            assert name in DISTRIBUTION_STRATEGIES


# ══════════════════════════════════════════════════════════════════
# VALIDATION TESTS
# ══════════════════════════════════════════════════════════════════

class TestValidateCompanyIdOrch:
    def test_empty_raises(self):
        with pytest.raises(ParwaBaseError) as exc:
            _validate_company_id("")
        assert exc.value.error_code == "INVALID_COMPANY_ID"

    def test_whitespace_raises(self):
        with pytest.raises(ParwaBaseError):
            _validate_company_id("   ")

    def test_none_raises(self):
        with pytest.raises(ParwaBaseError):
            _validate_company_id(None)

    def test_valid_passes(self):
        _validate_company_id("comp_1")


class TestValidateStrategy:
    def test_invalid_raises(self):
        with pytest.raises(ParwaBaseError) as exc:
            _validate_strategy("random")
        assert exc.value.error_code == "INVALID_STRATEGY"

    def test_all_valid_pass(self):
        for s in VALID_STRATEGIES:
            _validate_strategy(s)


class TestParseCapacity:
    def test_valid_json(self):
        result = _parse_capacity('{"max_concurrent_tickets": 100}')
        assert result["max_concurrent_tickets"] == 100

    def test_empty_json(self):
        result = _parse_capacity("{}")
        assert result["max_concurrent_tickets"] == DEFAULT_MAX_CONCURRENT

    def test_malformed_json(self):
        result = _parse_capacity("not json")
        assert result["max_concurrent_tickets"] == DEFAULT_MAX_CONCURRENT

    def test_none_input(self):
        result = _parse_capacity(None)
        assert result["max_concurrent_tickets"] == DEFAULT_MAX_CONCURRENT

    def test_non_dict_json(self):
        result = _parse_capacity('"string"')
        assert result["max_concurrent_tickets"] == DEFAULT_MAX_CONCURRENT

    def test_missing_max_concurrent_uses_default(self):
        result = _parse_capacity('{"priority_weight": 5}')
        assert result["max_concurrent_tickets"] == DEFAULT_MAX_CONCURRENT


# ══════════════════════════════════════════════════════════════════
# ROUND ROBIN TESTS
# ══════════════════════════════════════════════════════════════════

class TestRoundRobin:
    def test_cycles_through_instances(self):
        i1 = _make_instance.__wrapped__(None) if False else None
        # Test the _get_rr_index directly
        idx0 = _get_rr_index("comp_1", 3)
        idx1 = _get_rr_index("comp_1", 3)
        idx2 = _get_rr_index("comp_1", 3)
        idx3 = _get_rr_index("comp_1", 3)
        assert idx0 == 0
        assert idx1 == 1
        assert idx2 == 2
        assert idx3 == 0  # Wraps around

    def test_separate_companies_separate_counters(self):
        idx_a = _get_rr_index("comp_a", 2)
        idx_b = _get_rr_index("comp_b", 2)
        assert idx_a == 0
        assert idx_b == 0

    def test_empty_list_returns_none(self):
        strat = RoundRobinStrategy()
        result = strat.select([], {"company_id": "comp_1"})
        assert result is None

    def test_single_instance(self):
        db = SessionLocal()
        _make_company(db)
        inst = _make_instance(db)
        strat = RoundRobinStrategy()
        result = strat.select([inst], {"company_id": "comp_1"})
        assert result.id == "inst_1"


# ══════════════════════════════════════════════════════════════════
# LEAST LOADED STRATEGY TESTS
# ══════════════════════════════════════════════════════════════════

class TestLeastLoadedStrategy:
    def test_picks_lowest_active_tickets(self):
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", active_tickets=10)
        i2 = _make_instance(db, iid="i2", active_tickets=2)
        strat = LeastLoadedStrategy()
        result = strat.select([i1, i2], {"company_id": "comp_1"})
        assert result.id == "i2"

    def test_empty_list_returns_none(self):
        strat = LeastLoadedStrategy()
        result = strat.select([], {})
        assert result is None

    def test_respects_capacity_limit(self):
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", cap={"max_concurrent_tickets": 5},
                           active_tickets=3)
        i2 = _make_instance(db, iid="i2", cap={"max_concurrent_tickets": 5},
                           active_tickets=4)
        strat = LeastLoadedStrategy()
        result = strat.select([i1, i2], {"company_id": "comp_1"})
        assert result.id == "i1"

    def test_all_at_capacity_returns_least_loaded(self):
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", cap={"max_concurrent_tickets": 2},
                           active_tickets=2)
        i2 = _make_instance(db, iid="i2", cap={"max_concurrent_tickets": 2},
                           active_tickets=2)
        strat = LeastLoadedStrategy()
        result = strat.select([i1, i2], {"company_id": "comp_1"})
        # Graceful degradation — returns least loaded even at capacity
        assert result is not None

    def test_tiebreaker_by_total_tickets_handled(self):
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", active_tickets=5, total_tickets=100)
        i2 = _make_instance(db, iid="i2", active_tickets=5, total_tickets=50)
        strat = LeastLoadedStrategy()
        result = strat.select([i1, i2], {"company_id": "comp_1"})
        assert result.id == "i2"


# ══════════════════════════════════════════════════════════════════
# CHANNEL PINNED STRATEGY TESTS
# ══════════════════════════════════════════════════════════════════

class TestChannelPinnedStrategy:
    def test_returns_channel_matched_instance(self):
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", channels=["email"])
        i2 = _make_instance(db, iid="i2", channels=["chat"])
        strat = ChannelPinnedStrategy()
        result = strat.select([i1, i2], {"company_id": "comp_1", "channel": "email"})
        assert result.id == "i1"

    def test_falls_back_to_least_loaded_when_no_channel_match(self):
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", channels=["email"], active_tickets=10)
        i2 = _make_instance(db, iid="i2", channels=["chat"], active_tickets=2)
        strat = ChannelPinnedStrategy()
        result = strat.select([i1, i2], {"company_id": "comp_1", "channel": "voice"})
        assert result.id == "i2"  # Falls back to least loaded

    def test_falls_back_when_no_channel_in_context(self):
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", active_tickets=10)
        i2 = _make_instance(db, iid="i2", active_tickets=2)
        strat = ChannelPinnedStrategy()
        result = strat.select([i1, i2], {"company_id": "comp_1"})
        assert result.id == "i2"

    def test_empty_list_returns_none(self):
        strat = ChannelPinnedStrategy()
        result = strat.select([], {})
        assert result is None

    def test_handles_malformed_channel_json(self):
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1")
        i1.channel_assignment = "not json"
        db.commit()
        i2 = _make_instance(db, iid="i2", channels=["email"])
        strat = ChannelPinnedStrategy()
        result = strat.select([i1, i2], {"company_id": "comp_1", "channel": "email"})
        assert result.id == "i2"

    def test_respects_capacity_on_channel_match(self):
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", channels=["email"],
                           cap={"max_concurrent_tickets": 1}, active_tickets=1)
        i2 = _make_instance(db, iid="i2", channels=["email"],
                           cap={"max_concurrent_tickets": 5}, active_tickets=0)
        strat = ChannelPinnedStrategy()
        result = strat.select([i1, i2], {"company_id": "comp_1", "channel": "email"})
        assert result.id == "i2"


# ══════════════════════════════════════════════════════════════════
# VARIANT PRIORITY STRATEGY TESTS
# ══════════════════════════════════════════════════════════════════

class TestVariantPriorityStrategy:
    def test_prefers_highest_variant(self):
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", vtype="mini_parwa")
        i2 = _make_instance(db, iid="i2", vtype="parwa")
        i3 = _make_instance(db, iid="i3", vtype="parwa_high")
        strat = VariantPriorityStrategy()
        result = strat.select([i1, i2, i3], {"company_id": "comp_1"})
        assert result.id == "i3"

    def test_filters_by_requested_variant_type(self):
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", vtype="mini_parwa")
        i2 = _make_instance(db, iid="i2", vtype="parwa")
        strat = VariantPriorityStrategy()
        result = strat.select(
            [i1, i2], {"company_id": "comp_1", "variant_type": "mini_parwa"},
        )
        assert result.id == "i1"

    def test_falls_through_if_requested_type_unavailable(self):
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", vtype="mini_parwa")
        i2 = _make_instance(db, iid="i2", vtype="parwa")
        strat = VariantPriorityStrategy()
        result = strat.select(
            [i1, i2], {"company_id": "comp_1", "variant_type": "parwa_high"},
        )
        # Falls through to highest available
        assert result.id == "i2"

    def test_empty_list_returns_none(self):
        strat = VariantPriorityStrategy()
        result = strat.select([], {})
        assert result is None

    def test_least_loaded_within_same_variant(self):
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", vtype="parwa", active_tickets=10)
        i2 = _make_instance(db, iid="i2", vtype="parwa", active_tickets=2)
        strat = VariantPriorityStrategy()
        result = strat.select([i1, i2], {"company_id": "comp_1"})
        assert result.id == "i2"


# ══════════════════════════════════════════════════════════════════
# SELECT_INSTANCE TESTS
# ══════════════════════════════════════════════════════════════════

class TestSelectInstance:
    def test_returns_active_instance(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        result = select_instance(db, "comp_1")
        assert result is not None
        assert result.id == "inst_1"

    def test_returns_none_if_no_active_instances(self):
        db = SessionLocal()
        _make_company(db)
        result = select_instance(db, "comp_1")
        assert result is None

    def test_ignores_inactive_instances(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", status="inactive")
        result = select_instance(db, "comp_1")
        assert result is None

    def test_tenant_isolation(self):
        db = SessionLocal()
        _make_company(db, cid="comp_1")
        _make_company(db, cid="comp_2")
        _make_instance(db, cid="comp_1")
        result = select_instance(db, "comp_2")
        assert result is None

    def test_invalid_strategy_raises(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError):
            select_instance(db, "comp_1", strategy="invalid")

    def test_empty_company_id_raises(self):
        db = SessionLocal()
        with pytest.raises(ParwaBaseError):
            select_instance(db, "")

    def test_least_loaded_strategy(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", active_tickets=10)
        _make_instance(db, iid="i2", active_tickets=2)
        result = select_instance(db, "comp_1", strategy="least_loaded")
        assert result.id == "i2"

    def test_variant_priority_strategy(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa")
        _make_instance(db, iid="i2", vtype="parwa_high")
        result = select_instance(db, "comp_1", strategy="variant_priority")
        assert result.id == "i2"

    def test_channel_pinned_strategy(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", channels=["email"])
        _make_instance(db, iid="i2", channels=["chat"])
        result = select_instance(
            db, "comp_1", strategy="channel_pinned", channel="chat",
        )
        assert result.id == "i2"


# ══════════════════════════════════════════════════════════════════
# ROUTE_TICKET TESTS
# ══════════════════════════════════════════════════════════════════

class TestRouteTicket:
    def test_routes_to_instance(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _make_ticket(db)
        dist = route_ticket(db, "comp_1", "tick_1")
        assert dist.id is not None
        assert dist.instance_id == "inst_1"
        assert dist.ticket_id == "tick_1"
        assert dist.status == "assigned"
        assert dist.distribution_strategy == "least_loaded"

    def test_increments_instance_counters(self):
        db = SessionLocal()
        _make_company(db)
        inst = _make_instance(db)
        route_ticket(db, "comp_1", "tick_1")
        db.refresh(inst)
        assert inst.active_tickets_count == 1
        assert inst.total_tickets_handled == 1

    def test_empty_company_id_raises(self):
        db = SessionLocal()
        with pytest.raises(ParwaBaseError):
            route_ticket(db, "", "tick_1")

    def test_empty_ticket_id_raises(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError) as exc:
            route_ticket(db, "comp_1", "")
        assert exc.value.error_code == "INVALID_TICKET_ID"

    def test_no_available_instance_raises_503(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError) as exc:
            route_ticket(db, "comp_1", "tick_1")
        assert exc.value.error_code == "NO_AVAILABLE_INSTANCE"
        assert exc.value.status_code == 503

    def test_whitespace_ticket_id_raises(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError):
            route_ticket(db, "comp_1", "   ")

    def test_strategy_used(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _make_ticket(db)
        dist = route_ticket(db, "comp_1", "tick_1", strategy="round_robin")
        assert dist.distribution_strategy == "round_robin"

    def test_invalid_strategy_raises(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError):
            route_ticket(db, "comp_1", "tick_1", strategy="bad")

    def test_tenant_isolation(self):
        db = SessionLocal()
        _make_company(db, cid="comp_1")
        _make_company(db, cid="comp_2")
        _make_instance(db, cid="comp_1")
        _make_ticket(db, cid="comp_1")
        _make_ticket(db, cid="comp_2", tid="tick_2")
        # Instance for comp_1 should not be available for comp_2
        with pytest.raises(ParwaBaseError):
            route_ticket(db, "comp_2", "tick_2")

    def test_sets_last_activity_at(self):
        db = SessionLocal()
        _make_company(db)
        inst = _make_instance(db)
        _make_ticket(db)
        route_ticket(db, "comp_1", "tick_1")
        db.refresh(inst)
        assert inst.last_activity_at is not None


# ══════════════════════════════════════════════════════════════════
# GET_INSTANCE_LOAD TESTS
# ══════════════════════════════════════════════════════════════════

class TestGetInstanceLoad:
    def test_returns_load_dict(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, cap={"max_concurrent_tickets": 100}, active_tickets=30)
        load = get_instance_load(db, "comp_1", "inst_1")
        assert load["instance_id"] == "inst_1"
        assert load["active_tickets_count"] == 30
        assert load["max_concurrent_tickets"] == 100
        assert load["available_capacity"] == 70
        assert load["utilization_pct"] == 30.0

    def test_instance_not_found_raises_404(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError) as exc:
            get_instance_load(db, "comp_1", "nonexistent")
        assert exc.value.status_code == 404

    def test_empty_company_id_raises(self):
        db = SessionLocal()
        with pytest.raises(ParwaBaseError):
            get_instance_load(db, "", "inst_1")

    def test_default_capacity_when_no_config(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, cap={})
        load = get_instance_load(db, "comp_1", "inst_1")
        assert load["max_concurrent_tickets"] == DEFAULT_MAX_CONCURRENT

    def test_utilization_pct_calculation(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, cap={"max_concurrent_tickets": 4}, active_tickets=3)
        load = get_instance_load(db, "comp_1", "inst_1")
        assert load["utilization_pct"] == 75.0

    def test_zero_max_concurrent_returns_zero_available(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, cap={"max_concurrent_tickets": 0})
        load = get_instance_load(db, "comp_1", "inst_1")
        assert load["available_capacity"] == 0

    def test_has_required_fields(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        load = get_instance_load(db, "comp_1", "inst_1")
        for key in ["instance_id", "instance_name", "variant_type", "status",
                     "active_tickets_count", "total_tickets_handled",
                     "max_concurrent_tickets", "available_capacity",
                     "utilization_pct", "last_activity_at"]:
            assert key in load


# ══════════════════════════════════════════════════════════════════
# GET_ALL_INSTANCE_LOADS TESTS
# ══════════════════════════════════════════════════════════════════

class TestGetAllInstanceLoads:
    def test_returns_all_instances(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1")
        _make_instance(db, iid="i2")
        loads = get_all_instance_loads(db, "comp_1")
        assert len(loads) == 2

    def test_empty_company_returns_empty_list(self):
        db = SessionLocal()
        _make_company(db)
        loads = get_all_instance_loads(db, "comp_1")
        assert loads == []

    def test_empty_company_id_raises(self):
        db = SessionLocal()
        with pytest.raises(ParwaBaseError):
            get_all_instance_loads(db, "")

    def test_tenant_isolation(self):
        db = SessionLocal()
        _make_company(db, cid="comp_1")
        _make_company(db, cid="comp_2")
        _make_instance(db, cid="comp_1")
        loads = get_all_instance_loads(db, "comp_2")
        assert loads == []


# ══════════════════════════════════════════════════════════════════
# REBALANCE_WORKLOAD TESTS
# ══════════════════════════════════════════════════════════════════

class TestRebalanceWorkload:
    def test_no_active_instances_returns_empty(self):
        db = SessionLocal()
        _make_company(db)
        result = rebalance_workload(db, "comp_1")
        assert result["rebalanced_instances"] == 0
        assert result["migrated_tickets"] == 0

    def test_no_overloaded_returns_empty(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", cap={"max_concurrent_tickets": 100},
                       active_tickets=10)
        _make_instance(db, iid="i2", cap={"max_concurrent_tickets": 100},
                       active_tickets=5)
        result = rebalance_workload(db, "comp_1")
        assert result["migrated_tickets"] == 0

    def test_migrates_tickets_from_overloaded(self):
        db = SessionLocal()
        _make_company(db)
        # Overloaded instance (100%)
        i1 = _make_instance(db, iid="i1", vtype="mini_parwa",
                           cap={"max_concurrent_tickets": 10}, active_tickets=10)
        # Underloaded instance (10%)
        i2 = _make_instance(db, iid="i2", vtype="mini_parwa",
                           cap={"max_concurrent_tickets": 10}, active_tickets=1)
        # Create distributions on i1
        for t in range(5):
            _make_ticket(db, tid=f"tick_{t}")
            _make_distribution(db, iid="i1", tid=f"tick_{t}")
        result = rebalance_workload(db, "comp_1")
        assert result["migrated_tickets"] > 0

    def test_empty_company_id_raises(self):
        db = SessionLocal()
        with pytest.raises(ParwaBaseError):
            rebalance_workload(db, "")

    def test_returns_details_dict(self):
        db = SessionLocal()
        _make_company(db)
        result = rebalance_workload(db, "comp_1")
        assert "rebalanced_instances" in result
        assert "migrated_tickets" in result
        assert "details" in result


# ══════════════════════════════════════════════════════════════════
# ESCALATE_TICKET TESTS
# ══════════════════════════════════════════════════════════════════

class TestEscalateTicket:
    def test_escalates_to_higher_variant(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa")
        _make_instance(db, iid="i2", vtype="parwa")
        _make_ticket(db)
        _make_distribution(db, iid="i1", tid="tick_1")
        new_dist = escalate_ticket(db, "comp_1", "tick_1")
        assert new_dist.instance_id == "i2"
        assert new_dist.status == "assigned"
        assert new_dist.distribution_strategy == "escalated"

    def test_marks_original_as_escalated(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa")
        _make_instance(db, iid="i2", vtype="parwa")
        _make_ticket(db)
        dist = _make_distribution(db, iid="i1", tid="tick_1")
        escalate_ticket(db, "comp_1", "tick_1")
        db.refresh(dist)
        assert dist.status == "escalated"
        assert dist.escalation_target_instance_id == "i2"

    def test_decrements_source_instance(self):
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", vtype="mini_parwa", active_tickets=5)
        _make_instance(db, iid="i2", vtype="parwa")
        _make_ticket(db)
        _make_distribution(db, iid="i1", tid="tick_1")
        escalate_ticket(db, "comp_1", "tick_1")
        db.refresh(i1)
        assert i1.active_tickets_count == 4

    def test_increments_target_instance(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa")
        i2 = _make_instance(db, iid="i2", vtype="parwa")
        _make_ticket(db)
        _make_distribution(db, iid="i1", tid="tick_1")
        escalate_ticket(db, "comp_1", "tick_1")
        db.refresh(i2)
        assert i2.active_tickets_count == 1
        assert i2.total_tickets_handled == 1

    def test_no_active_distribution_raises_404(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError) as exc:
            escalate_ticket(db, "comp_1", "nonexistent_ticket")
        assert exc.value.error_code == "NO_ACTIVE_DISTRIBUTION"
        assert exc.value.status_code == 404

    def test_no_higher_instance_raises_503(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="parwa_high")  # Already highest
        _make_ticket(db)
        _make_distribution(db, iid="i1", tid="tick_1")
        with pytest.raises(ParwaBaseError) as exc:
            escalate_ticket(db, "comp_1", "tick_1")
        assert exc.value.error_code == "NO_HIGHER_INSTANCE"
        assert exc.value.status_code == 503

    def test_empty_ticket_id_raises(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError) as exc:
            escalate_ticket(db, "comp_1", "")
        assert exc.value.error_code == "INVALID_TICKET_ID"

    def test_empty_company_id_raises(self):
        db = SessionLocal()
        with pytest.raises(ParwaBaseError):
            escalate_ticket(db, "", "tick_1")

    def test_rebalance_from_set(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa")
        _make_instance(db, iid="i2", vtype="parwa")
        _make_ticket(db)
        _make_distribution(db, iid="i1", tid="tick_1")
        new_dist = escalate_ticket(db, "comp_1", "tick_1")
        assert new_dist.rebalance_from_instance_id == "i1"


# ══════════════════════════════════════════════════════════════════
# COMPLETE_TICKET_ASSIGNMENT TESTS
# ══════════════════════════════════════════════════════════════════

class TestCompleteTicketAssignment:
    def test_completes_assignment(self):
        db = SessionLocal()
        _make_company(db)
        inst = _make_instance(db, active_tickets=5)
        _make_ticket(db)
        dist = _make_distribution(db, iid="inst_1", tid="tick_1")
        result = complete_ticket_assignment(db, "comp_1", dist.id)
        assert result.status == "completed"
        assert result.completed_at is not None
        assert result.billing_charged_to_instance == "inst_1"

    def test_decrements_instance_counter(self):
        db = SessionLocal()
        _make_company(db)
        inst = _make_instance(db, active_tickets=5)
        _make_ticket(db)
        dist = _make_distribution(db, iid="inst_1", tid="tick_1")
        complete_ticket_assignment(db, "comp_1", dist.id)
        db.refresh(inst)
        assert inst.active_tickets_count == 4

    def test_idempotent_double_complete(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, active_tickets=1)
        _make_ticket(db)
        dist = _make_distribution(db, iid="inst_1", tid="tick_1")
        result1 = complete_ticket_assignment(db, "comp_1", dist.id)
        result2 = complete_ticket_assignment(db, "comp_1", dist.id)
        assert result1.status == "completed"
        assert result2.status == "completed"

    def test_not_found_raises_404(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError) as exc:
            complete_ticket_assignment(db, "comp_1", "nonexistent")
        assert exc.value.error_code == "DISTRIBUTION_NOT_FOUND"
        assert exc.value.status_code == 404

    def test_empty_distribution_id_raises(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError) as exc:
            complete_ticket_assignment(db, "comp_1", "")
        assert exc.value.error_code == "INVALID_DISTRIBUTION_ID"

    def test_empty_company_id_raises(self):
        db = SessionLocal()
        with pytest.raises(ParwaBaseError):
            complete_ticket_assignment(db, "", "dist_1")

    def test_sets_last_activity_at(self):
        db = SessionLocal()
        _make_company(db)
        inst = _make_instance(db)
        _make_ticket(db)
        dist = _make_distribution(db, iid="inst_1", tid="tick_1")
        complete_ticket_assignment(db, "comp_1", dist.id)
        db.refresh(inst)
        assert inst.last_activity_at is not None


# ══════════════════════════════════════════════════════════════════
# GET_DISTRIBUTION_HISTORY TESTS
# ══════════════════════════════════════════════════════════════════

class TestGetDistributionHistory:
    def test_returns_history(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _make_ticket(db)
        _make_distribution(db, iid="inst_1", tid="tick_1")
        history = get_distribution_history(db, "comp_1")
        assert len(history) == 1
        assert history[0]["ticket_id"] == "tick_1"

    def test_filter_by_ticket_id(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _make_ticket(db, tid="t1")
        _make_ticket(db, tid="t2")
        _make_distribution(db, iid="inst_1", tid="t1")
        _make_distribution(db, iid="inst_1", tid="t2")
        history = get_distribution_history(db, "comp_1", ticket_id="t1")
        assert len(history) == 1
        assert history[0]["ticket_id"] == "t1"

    def test_filter_by_instance_id(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1")
        _make_instance(db, iid="i2")
        _make_ticket(db)
        _make_distribution(db, iid="i1", tid="tick_1")
        _make_distribution(db, iid="i2", tid="tick_1")
        history = get_distribution_history(db, "comp_1", instance_id="i1")
        assert len(history) == 1
        assert history[0]["instance_id"] == "i1"

    def test_filter_by_status(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _make_ticket(db, tid="t1")
        _make_ticket(db, tid="t2")
        _make_distribution(db, iid="inst_1", tid="t1", status="assigned")
        _make_distribution(db, iid="inst_1", tid="t2", status="completed")
        history = get_distribution_history(db, "comp_1", status="assigned")
        assert len(history) == 1

    def test_empty_company_id_raises(self):
        db = SessionLocal()
        with pytest.raises(ParwaBaseError):
            get_distribution_history(db, "")

    def test_returns_dicts_with_required_fields(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _make_ticket(db)
        _make_distribution(db)
        history = get_distribution_history(db, "comp_1")
        for h in history:
            for key in ["id", "instance_id", "ticket_id", "strategy",
                        "status", "assigned_at"]:
                assert key in h

    def test_ordered_by_assigned_at_desc(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _make_ticket(db, tid="t1")
        _make_ticket(db, tid="t2")
        _make_distribution(db, iid="inst_1", tid="t1")
        _make_distribution(db, iid="inst_1", tid="t2")
        history = get_distribution_history(db, "comp_1")
        assert len(history) == 2
        # Most recent first
        assert history[0]["ticket_id"] == "t2"


# ══════════════════════════════════════════════════════════════════
# GET_ORCHESTRATION_SUMMARY TESTS
# ══════════════════════════════════════════════════════════════════

class TestGetOrchestrationSummary:
    def test_returns_summary_dict(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa")
        _make_instance(db, iid="i2", vtype="parwa", status="inactive")
        summary = get_orchestration_summary(db, "comp_1")
        assert summary["instances"]["total"] == 2
        assert "active" in summary["instances"]["by_status"]
        assert "inactive" in summary["instances"]["by_status"]

    def test_capacity_summary(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, cap={"max_concurrent_tickets": 100}, active_tickets=30)
        summary = get_orchestration_summary(db, "comp_1")
        assert summary["capacity"]["total_max_concurrent"] == 100
        assert summary["capacity"]["total_active_tickets"] == 30
        assert summary["capacity"]["available_capacity"] == 70

    def test_distribution_stats(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _make_ticket(db, tid="t1")
        _make_ticket(db, tid="t2")
        _make_distribution(db, iid="inst_1", tid="t1", strategy="least_loaded")
        _make_distribution(db, iid="inst_1", tid="t2", strategy="round_robin")
        summary = get_orchestration_summary(db, "comp_1")
        assert summary["distributions"]["total"] == 2
        assert summary["distributions"]["by_strategy"]["least_loaded"] == 1
        assert summary["distributions"]["by_strategy"]["round_robin"] == 1

    def test_empty_company_returns_empty_summary(self):
        db = SessionLocal()
        _make_company(db)
        summary = get_orchestration_summary(db, "comp_1")
        assert summary["instances"]["total"] == 0
        assert summary["capacity"]["total_max_concurrent"] == 0

    def test_empty_company_id_raises(self):
        db = SessionLocal()
        with pytest.raises(ParwaBaseError):
            get_orchestration_summary(db, "")

    def test_by_variant_type_in_summary(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa")
        _make_instance(db, iid="i2", vtype="parwa")
        _make_instance(db, iid="i3", vtype="parwa_high")
        summary = get_orchestration_summary(db, "comp_1")
        assert summary["instances"]["by_variant_type"]["mini_parwa"] == 1
        assert summary["instances"]["by_variant_type"]["parwa"] == 1
        assert summary["instances"]["by_variant_type"]["parwa_high"] == 1

    def test_utilization_pct_in_capacity(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, cap={"max_concurrent_tickets": 100}, active_tickets=25)
        summary = get_orchestration_summary(db, "comp_1")
        assert summary["capacity"]["utilization_pct"] == 25.0

    def test_total_tickets_handled(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", total_tickets=100)
        _make_instance(db, iid="i2", total_tickets=200)
        summary = get_orchestration_summary(db, "comp_1")
        assert summary["total_tickets_handled"] == 300

    def test_ignores_inactive_in_capacity(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", status="inactive",
                       cap={"max_concurrent_tickets": 100})
        summary = get_orchestration_summary(db, "comp_1")
        assert summary["capacity"]["total_max_concurrent"] == 0
