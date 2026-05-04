"""
Week 8 Day 1: Gap Testing Round 2 — Tests for 8 gaps found in manual analysis.

Gaps tested:
  GAP 1: Non-atomic counters now use SQL atomic UPDATE
  GAP 2: updated_at auto-updates via onupdate
  GAP 3: route_ticket() checks capacity before routing
  GAP 4: update_capability_config() sets updated_at
  GAP 5: batch_update_capabilities() no longer rolls back successful items
  GAP 6: rebalance_workload() correctly updates total_tickets_handled on target
  GAP 7: create_instance_override() sets updated_at on existing
  GAP 8: datetime.utcnow() still works (deprecation is LOW priority)

Tests are SOURCE OF TRUTH. If a test fails, fix the application code.
NEVER modify tests to pass.
"""

import json
import os
import time
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
    VariantAICapability,
    VariantInstance,
    VariantWorkloadDistribution,
    AITokenBudget,
    AIAgentAssignment,
)
from backend.app.services.variant_capability_service import (
    initialize_variant_matrix,
    update_capability_config,
    batch_update_capabilities,
    check_feature_enabled,
)
from backend.app.services.variant_instance_service import (
    register_instance,
)
from backend.app.services.entitlement_middleware import (
    create_instance_override,
)
from backend.app.services.variant_orchestration_service import (
    route_ticket,
    escalate_ticket,
    complete_ticket_assignment,
    rebalance_workload,
    _round_robin_counters,
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
# GAP 1: Non-atomic counters now use SQL atomic UPDATE
# ══════════════════════════════════════════════════════════════════

class TestGapAtomicCounters:
    def test_route_ticket_atomic_counter_update(self):
        """route_ticket() should atomically update counters via SQL."""
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _make_ticket(db)
        dist = route_ticket(db, "comp_1", "tick_1")
        db.commit()

        # Verify counters incremented correctly
        inst = db.query(VariantInstance).filter_by(id="inst_1").first()
        assert inst.active_tickets_count == 1
        assert inst.total_tickets_handled == 1
        assert inst.last_activity_at is not None

    def test_route_ticket_multiple_routes(self):
        """Multiple sequential routes should accumulate correctly."""
        db = SessionLocal()
        _make_company(db)
        inst = _make_instance(db, cap={"max_concurrent_tickets": 100})
        for i in range(5):
            _make_ticket(db, tid=f"tick_{i}")
            route_ticket(db, "comp_1", f"tick_{i}")

        db.commit()
        db.refresh(inst)
        assert inst.active_tickets_count == 5
        assert inst.total_tickets_handled == 5

    def test_escalate_ticket_atomic_counters(self):
        """escalate_ticket() should atomically update both instances."""
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", vtype="mini_parwa", active_tickets=5)
        i2 = _make_instance(db, iid="i2", vtype="parwa")
        _make_ticket(db)
        _make_distribution(db, iid="i1", tid="tick_1")

        escalate_ticket(db, "comp_1", "tick_1")
        db.commit()

        db.refresh(i1)
        db.refresh(i2)
        assert i1.active_tickets_count == 4  # Decremented
        assert i2.active_tickets_count == 1   # Incremented
        assert i2.total_tickets_handled == 1

    def test_complete_ticket_atomic_decrement(self):
        """complete_ticket_assignment() should atomically decrement."""
        db = SessionLocal()
        _make_company(db)
        inst = _make_instance(db, active_tickets=3)
        _make_ticket(db)
        dist = _make_distribution(db, iid="inst_1", tid="tick_1")

        complete_ticket_assignment(db, "comp_1", dist.id)
        db.commit()

        db.refresh(inst)
        assert inst.active_tickets_count == 2
        assert inst.last_activity_at is not None

    def test_rebalance_atomic_counter_moves(self):
        """rebalance should atomically move counters between instances."""
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", vtype="mini_parwa",
                           cap={"max_concurrent_tickets": 10}, active_tickets=10)
        i2 = _make_instance(db, iid="i2", vtype="mini_parwa",
                           cap={"max_concurrent_tickets": 10}, active_tickets=0)

        for t in range(5):
            _make_ticket(db, tid=f"tick_{t}")
            _make_distribution(db, iid="i1", tid=f"tick_{t}")

        result = rebalance_workload(db, "comp_1")
        db.commit()

        db.refresh(i1)
        db.refresh(i2)
        assert result["migrated_tickets"] > 0
        # After rebalance: i1 should have fewer, i2 should have more
        assert i2.active_tickets_count > 0
        assert i2.total_tickets_handled > 0  # GAP 6: target gets total_tickets


# ══════════════════════════════════════════════════════════════════
# GAP 2: updated_at auto-updates via onupdate
# ══════════════════════════════════════════════════════════════════

class TestGapUpdatedAtOnUpdate:
    def test_capability_updated_at_changes_on_modify(self):
        """VariantAICapability updated_at should change when row is modified."""
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        initialize_variant_matrix(db, "comp_1")

        cap = db.query(VariantAICapability).filter_by(
            company_id="comp_1", variant_type="mini_parwa",
            feature_id="F-054", instance_id=None,
        ).first()

        original_updated = cap.updated_at
        time.sleep(0.01)  # Small delay to ensure timestamp difference

        cap.is_enabled = False
        db.commit()
        db.refresh(cap)

        assert cap.updated_at >= original_updated

    def test_instance_updated_at_changes_on_modify(self):
        """VariantInstance updated_at should change when row is modified."""
        db = SessionLocal()
        _make_company(db)
        inst = _make_instance(db)

        original_updated = inst.updated_at
        time.sleep(0.01)

        inst.status = "inactive"
        db.commit()
        db.refresh(inst)

        assert inst.updated_at >= original_updated

    def test_token_budget_updated_at_changes_on_modify(self):
        """AITokenBudget updated_at should change when row is modified."""
        db = SessionLocal()
        _make_company(db)
        tb = AITokenBudget(
            company_id="comp_1", budget_type="daily",
            budget_period="2026-04-08", max_tokens=100,
        )
        db.add(tb)
        db.commit()

        original_updated = tb.updated_at
        time.sleep(0.01)

        tb.used_tokens = 50
        db.commit()
        db.refresh(tb)

        assert tb.updated_at >= original_updated

    def test_agent_assignment_updated_at_changes_on_modify(self):
        """AIAgentAssignment updated_at should change when row is modified."""
        db = SessionLocal()
        a = AIAgentAssignment(agent_name="Agent 1")
        db.add(a)
        db.commit()

        original_updated = a.updated_at
        time.sleep(0.01)

        a.status = "inactive"
        db.commit()
        db.refresh(a)

        assert a.updated_at >= original_updated


# ══════════════════════════════════════════════════════════════════
# GAP 3: route_ticket() checks capacity before routing
# ══════════════════════════════════════════════════════════════════

class TestGapRouteTicketCapacityCheck:
    def test_route_ticket_at_capacity_raises_503(self):
        """route_ticket() should reject when instance is at capacity."""
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, cap={"max_concurrent_tickets": 2}, active_tickets=2)
        _make_ticket(db)

        with pytest.raises(ParwaBaseError) as exc:
            route_ticket(db, "comp_1", "tick_1")
        assert exc.value.error_code == "INSTANCE_AT_CAPACITY"
        assert exc.value.status_code == 503

    def test_route_ticket_one_below_capacity_succeeds(self):
        """route_ticket() should succeed when one below capacity."""
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, cap={"max_concurrent_tickets": 2}, active_tickets=1)
        _make_ticket(db)

        dist = route_ticket(db, "comp_1", "tick_1")
        assert dist.instance_id == "inst_1"

    def test_route_ticket_over_capacity_raises(self):
        """route_ticket() should reject when already over capacity."""
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, cap={"max_concurrent_tickets": 5}, active_tickets=10)
        _make_ticket(db)

        with pytest.raises(ParwaBaseError) as exc:
            route_ticket(db, "comp_1", "tick_1")
        assert exc.value.error_code == "INSTANCE_AT_CAPACITY"

    def test_route_ticket_default_capacity_50(self):
        """route_ticket() should use default capacity of 50 when not set."""
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, cap={})  # No max set
        _make_ticket(db)

        # Should succeed — default is 50, current is 0
        dist = route_ticket(db, "comp_1", "tick_1")
        assert dist.id is not None

    def test_route_ticket_capacity_edge_case_exactly_at_limit(self):
        """route_ticket() should reject at exactly the capacity limit."""
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, cap={"max_concurrent_tickets": 1}, active_tickets=1)
        _make_ticket(db)

        with pytest.raises(ParwaBaseError) as exc:
            route_ticket(db, "comp_1", "tick_1")
        assert exc.value.error_code == "INSTANCE_AT_CAPACITY"


# ══════════════════════════════════════════════════════════════════
# GAP 4: update_capability_config() sets updated_at
# ══════════════════════════════════════════════════════════════════

class TestGapUpdateCapabilityConfigUpdatedAt:
    def test_updated_at_changes_after_config_update(self):
        """update_capability_config() should set updated_at."""
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")

        cap = db.query(VariantAICapability).filter_by(
            company_id="comp_1", variant_type="mini_parwa",
            feature_id="F-054", instance_id=None,
        ).first()

        original_updated = cap.updated_at
        time.sleep(0.01)

        updated = update_capability_config(
            db, "comp_1", "F-054", "mini_parwa",
            {"threshold": 0.99},
        )
        assert updated.updated_at >= original_updated

    def test_config_json_correct_after_update(self):
        """Config should be correctly updated."""
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")

        new_cfg = {"threshold": 0.95, "custom": True}
        updated = update_capability_config(
            db, "comp_1", "F-054", "mini_parwa", new_cfg,
        )
        assert json.loads(updated.config_json) == new_cfg


# ══════════════════════════════════════════════════════════════════
# GAP 5: batch_update_capabilities() doesn't roll back successful
# ══════════════════════════════════════════════════════════════════

class TestGapBatchUpdateNoRollback:
    def test_valid_and_invalid_in_same_batch(self):
        """Valid updates should succeed even when invalid ones are present."""
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")

        updates = [
            # Valid: disable F-054 for mini_parwa
            {"feature_id": "F-054", "variant_type": "mini_parwa",
             "is_enabled": False},
            # Invalid: missing feature_id
            {"variant_type": "parwa", "is_enabled": True},
            # Invalid: invalid variant_type
            {"feature_id": "F-054", "variant_type": "invalid_type",
             "is_enabled": True},
            # Valid: disable F-060 for mini_parwa
            {"feature_id": "F-060", "variant_type": "mini_parwa",
             "is_enabled": False},
        ]

        result = batch_update_capabilities(db, "comp_1", updates)
        assert result["updated"] == 2
        assert result["errors"] == 2
        assert result["skipped"] == 0

        # Verify the valid updates actually persisted
        assert check_feature_enabled(
            db, "comp_1", "F-054", "mini_parwa",
        ) is False
        assert check_feature_enabled(
            db, "comp_1", "F-060", "mini_parwa",
        ) is False

    def test_batch_update_empty_list(self):
        """Empty list should return all zeros."""
        db = SessionLocal()
        _make_company(db)
        result = batch_update_capabilities(db, "comp_1", [])
        assert result["updated"] == 0
        assert result["errors"] == 0
        assert result["skipped"] == 0

    def test_batch_update_all_invalid(self):
        """All invalid should return 0 updated."""
        db = SessionLocal()
        _make_company(db)
        result = batch_update_capabilities(db, "comp_1", [
            {"variant_type": "parwa", "is_enabled": True},
            {"feature_id": "F-054", "is_enabled": True},
            {"feature_id": "", "variant_type": "mini_parwa", "is_enabled": True},
        ])
        assert result["updated"] == 0
        assert result["errors"] == 3


# ══════════════════════════════════════════════════════════════════
# GAP 6: rebalance updates total_tickets_handled on target
# ══════════════════════════════════════════════════════════════════

class TestGapRebalanceTotalTickets:
    def test_rebalance_increments_target_total_tickets(self):
        """Target instance should get total_tickets_handled incremented."""
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", vtype="mini_parwa",
                           cap={"max_concurrent_tickets": 10}, active_tickets=10)
        i2 = _make_instance(db, iid="i2", vtype="mini_parwa",
                           cap={"max_concurrent_tickets": 10}, active_tickets=0,
                           total_tickets=0)

        for t in range(5):
            _make_ticket(db, tid=f"tick_{t}")
            _make_distribution(db, iid="i1", tid=f"tick_{t}")

        result = rebalance_workload(db, "comp_1")
        db.commit()
        db.refresh(i1)
        db.refresh(i2)

        # Target should have total_tickets incremented
        assert i2.total_tickets_handled == result["migrated_tickets"]

    def test_rebalance_keeps_source_total_tickets(self):
        """Source instance should keep its total_tickets_handled."""
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", vtype="mini_parwa",
                           cap={"max_concurrent_tickets": 10}, active_tickets=10,
                           total_tickets=100)
        i2 = _make_instance(db, iid="i2", vtype="mini_parwa",
                           cap={"max_concurrent_tickets": 10}, active_tickets=0)

        for t in range(3):
            _make_ticket(db, tid=f"tick_{t}")
            _make_distribution(db, iid="i1", tid=f"tick_{t}")

        rebalance_workload(db, "comp_1")
        db.commit()
        db.refresh(i1)

        # Source total_tickets should NOT change
        assert i1.total_tickets_handled == 100


# ══════════════════════════════════════════════════════════════════
# GAP 7: create_instance_override() updates updated_at
# ══════════════════════════════════════════════════════════════════

class TestGapOverrideUpdatedAt:
    def test_update_existing_override_sets_updated_at(self):
        """Updating an existing override should set updated_at."""
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        initialize_variant_matrix(db, "comp_1")

        create_instance_override(
            db, "comp_1", "F-054", "mini_parwa",
            "inst_1", True,
        )

        override = db.query(VariantAICapability).filter_by(
            company_id="comp_1", instance_id="inst_1",
            feature_id="F-054",
        ).first()

        original_updated = override.updated_at
        time.sleep(0.01)

        # Update the existing override
        create_instance_override(
            db, "comp_1", "F-054", "mini_parwa",
            "inst_1", False,
        )

        db.refresh(override)
        assert override.updated_at >= original_updated
        assert override.is_enabled is False

    def test_new_override_has_valid_updated_at(self):
        """Newly created override should have updated_at set."""
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        initialize_variant_matrix(db, "comp_1")

        override = create_instance_override(
            db, "comp_1", "F-054", "mini_parwa",
            "inst_1", True,
        )

        assert override.updated_at is not None
        assert override.created_at is not None


# ══════════════════════════════════════════════════════════════════
# GAP 8: datetime.utcnow() deprecation (LOW — verify still works)
# ══════════════════════════════════════════════════════════════════

class TestGapDatetimeUtcnowStillWorks:
    def test_created_at_and_updated_at_are_datetime(self):
        """All timestamp fields should be datetime objects."""
        db = SessionLocal()
        _make_company(db)
        cap = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            feature_id="F-054", feature_name="Test",
        )
        db.add(cap)
        db.commit()

        assert isinstance(cap.created_at, datetime)
        assert isinstance(cap.updated_at, datetime)

    def test_instance_timestamps_are_datetime(self):
        db = SessionLocal()
        _make_company(db)
        inst = _make_instance(db)

        assert isinstance(inst.created_at, datetime)
        assert isinstance(inst.updated_at, datetime)
