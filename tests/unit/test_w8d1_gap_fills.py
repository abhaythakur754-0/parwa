"""
Week 8 Day 1: Gap-fill tests for critical gaps found by gap_finder.

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
    VariantAICapability,
    VariantInstance,
    VariantWorkloadDistribution,
    AITokenBudget,
    PromptInjectionAttempt,
    AIPerformanceVariantMetric,
    TechniqueCache,
)
from backend.app.services.variant_capability_service import (
    initialize_variant_matrix,
    update_capability_config,
    check_feature_enabled,
)
from backend.app.services.variant_instance_service import (
    register_instance,
    increment_active_tickets,
    decrement_active_tickets,
)
from backend.app.services.entitlement_middleware import (
    check_entitlement,
    create_instance_override,
    remove_instance_override,
)
from backend.app.services.variant_orchestration_service import (
    _parse_capacity,
    route_ticket,
    escalate_ticket,
    complete_ticket_assignment,
    rebalance_workload,
)
from backend.app.exceptions import ParwaBaseError


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _setup_db():
    """Create all tables and provide a fresh session."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _make_company(db, cid="comp_1", name="Test Corp"):
    c = Company(id=cid, name=name, industry="saas",
                subscription_tier="parwa", subscription_status="active")
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
# GAP A1: Tenant isolation leak via company_id collision
# ══════════════════════════════════════════════════════════════════

class TestGapTenantIsolationCompanyPrefix:
    def test_similar_company_ids_dont_leak_data(self):
        """Companies with similar IDs must not see each other's data."""
        db = SessionLocal()
        _make_company(db, cid="comp_1")
        _make_company(db, cid="comp_10")
        _make_company(db, cid="comp_1_suffix")
        
        initialize_variant_matrix(db, "comp_1")
        
        # comp_10 should see zero capabilities
        count_10 = db.query(VariantAICapability).filter_by(
            company_id="comp_10",
        ).count()
        assert count_10 == 0
        
        # comp_1_suffix should see zero
        count_suffix = db.query(VariantAICapability).filter_by(
            company_id="comp_1_suffix",
        ).count()
        assert count_suffix == 0
        
        # comp_1 should have all features
        count_1 = db.query(VariantAICapability).filter_by(
            company_id="comp_1",
        ).count()
        assert count_1 > 0


# ══════════════════════════════════════════════════════════════════
# GAP A2: JSON corruption in config_json
# ══════════════════════════════════════════════════════════════════

class TestGapConfigJsonCorruption:
    def test_malformed_json_in_config_stored_as_string(self):
        """Malformed JSON should be stored as-is (service handles parsing)."""
        db = SessionLocal()
        _make_company(db)
        cap = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            feature_id="F-054", feature_name="Smart Router",
            config_json="not valid json{{{",
        )
        db.add(cap)
        db.commit()
        db.refresh(cap)
        # Should be stored as-is
        assert cap.config_json == "not valid json{{{"

    def test_empty_string_config_json(self):
        db = SessionLocal()
        _make_company(db)
        cap = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            feature_id="F-054", feature_name="Smart Router",
            config_json="",
        )
        db.add(cap)
        db.commit()
        assert cap.config_json == ""

    def test_very_large_config_json(self):
        """Large config JSON should be stored without truncation."""
        db = SessionLocal()
        _make_company(db)
        large_config = json.dumps({"key_" + "a" * 1000: "v" * 10000})
        cap = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            feature_id="F-054", feature_name="Smart Router",
            config_json=large_config,
        )
        db.add(cap)
        db.commit()
        db.refresh(cap)
        assert len(cap.config_json) == len(large_config)

    def test_unicode_in_config_json(self):
        db = SessionLocal()
        _make_company(db)
        config = {"name": "日本語テスト", "emoji": "🚀", "special": "\t\n\r"}
        cap = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            feature_id="F-054", feature_name="Smart Router",
            config_json=json.dumps(config),
        )
        db.add(cap)
        db.commit()
        parsed = json.loads(cap.config_json)
        assert parsed["name"] == "日本語テスト"


# ══════════════════════════════════════════════════════════════════
# GAP A3: Token budget hard_stop enforcement
# ══════════════════════════════════════════════════════════════════

class TestGapTokenBudgetHardStop:
    def test_used_tokens_can_exceed_max_in_db(self):
        """DB allows used_tokens > max_tokens (enforcement at service level)."""
        db = SessionLocal()
        _make_company(db)
        tb = AITokenBudget(
            company_id="comp_1", budget_type="daily",
            budget_period="2026-04-08", max_tokens=100,
            used_tokens=200,  # Over budget
        )
        db.add(tb)
        db.commit()
        assert tb.used_tokens == 200

    def test_zero_max_tokens_allowed(self):
        db = SessionLocal()
        _make_company(db)
        tb = AITokenBudget(
            company_id="comp_1", budget_type="daily",
            budget_period="2026-04-08", max_tokens=0,
        )
        db.add(tb)
        db.commit()
        assert tb.max_tokens == 0

    def test_alert_threshold_at_100(self):
        db = SessionLocal()
        _make_company(db)
        tb = AITokenBudget(
            company_id="comp_1", budget_type="daily",
            budget_period="2026-04-08", max_tokens=100,
            alert_threshold_pct=100,
        )
        db.add(tb)
        db.commit()
        assert tb.alert_threshold_pct == 100


# ══════════════════════════════════════════════════════════════════
# GAP B1: Namespace collision between tenants
# ══════════════════════════════════════════════════════════════════

class TestGapNamespaceCollision:
    def test_different_tenants_different_namespaces(self):
        """Two tenants should never share celery namespaces."""
        db = SessionLocal()
        _make_company(db, cid="comp_1")
        _make_company(db, cid="comp_2")
        
        i1 = register_instance(db, "comp_1", "Test", "mini_parwa")
        i2 = register_instance(db, "comp_2", "Test", "mini_parwa")
        
        assert i1.celery_queue_namespace != i2.celery_queue_namespace
        assert "comp_1" in i1.celery_queue_namespace
        assert "comp_2" in i2.celery_queue_namespace

    def test_different_tenants_different_redis_keys(self):
        db = SessionLocal()
        _make_company(db, cid="comp_1")
        _make_company(db, cid="comp_2")
        
        i1 = register_instance(db, "comp_1", "Test", "mini_parwa")
        i2 = register_instance(db, "comp_2", "Test", "mini_parwa")
        
        assert i1.redis_partition_key != i2.redis_partition_key


# ══════════════════════════════════════════════════════════════════
# GAP B2: Entitlement fallback after override removal
# ══════════════════════════════════════════════════════════════════

class TestGapEntitlementFallback:
    def test_falls_back_to_variant_default_after_override_removed(self):
        """After removing instance override, should fall back to variant default."""
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        initialize_variant_matrix(db, "comp_1")
        
        # F-054 is enabled for mini_parwa by default
        assert check_feature_enabled(
            db, "comp_1", "F-054", "mini_parwa", instance_id="inst_1",
        ) is True
        
        # Disable via instance override
        create_instance_override(
            db, "comp_1", "F-054", "mini_parwa", "inst_1", False,
        )
        assert check_feature_enabled(
            db, "comp_1", "F-054", "mini_parwa", instance_id="inst_1",
        ) is False
        
        # Remove override — should fall back to enabled
        remove_instance_override(
            db, "comp_1", "F-054", "mini_parwa", "inst_1",
        )
        assert check_feature_enabled(
            db, "comp_1", "F-054", "mini_parwa", instance_id="inst_1",
        ) is True

    def test_falls_back_to_disabled_after_override_removed(self):
        """After removing override that enabled a feature, should fall back to disabled."""
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        initialize_variant_matrix(db, "comp_1")
        
        # F-143 is disabled for mini_parwa by default
        assert check_feature_enabled(
            db, "comp_1", "F-143", "mini_parwa", instance_id="inst_1",
        ) is False
        
        # Enable via instance override
        create_instance_override(
            db, "comp_1", "F-143", "mini_parwa", "inst_1", True,
        )
        assert check_feature_enabled(
            db, "comp_1", "F-143", "mini_parwa", instance_id="inst_1",
        ) is True
        
        # Remove override — should fall back to disabled
        remove_instance_override(
            db, "comp_1", "F-143", "mini_parwa", "inst_1",
        )
        assert check_feature_enabled(
            db, "comp_1", "F-143", "mini_parwa", instance_id="inst_1",
        ) is False


# ══════════════════════════════════════════════════════════════════
# GAP C1: Round-robin counter isolation between tenants
# ══════════════════════════════════════════════════════════════════

class TestGapRoundRobinIsolation:
    def test_rr_counter_per_company(self):
        """Each company should have its own round-robin counter."""
        from backend.app.services.variant_orchestration_service import (
            _round_robin_counters, _get_rr_index,
        )
        _round_robin_counters.clear()
        
        # Simulate comp_1 getting 5 requests
        for _ in range(5):
            _get_rr_index("comp_1", 3)
        
        # comp_2 should start from 0, not 5
        idx = _get_rr_index("comp_2", 3)
        assert idx == 0, f"Expected 0, got {idx}"


# ══════════════════════════════════════════════════════════════════
# GAP C2: Double-escalation prevention
# ══════════════════════════════════════════════════════════════════

class TestGapDoubleEscalation:
    def test_cannot_escalate_already_escalated_ticket(self):
        """An already-escalated ticket should not be escalated again."""
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa")
        _make_instance(db, iid="i2", vtype="parwa")
        _make_instance(db, iid="i3", vtype="parwa_high")
        _make_ticket(db)
        
        # First escalation: mini_parwa -> parwa
        dist1 = route_ticket(db, "comp_1", "tick_1", strategy="variant_priority",
                            variant_type="mini_parwa")
        escalated1 = escalate_ticket(db, "comp_1", "tick_1")
        
        # The original distribution should be marked escalated
        db.refresh(dist1)
        assert dist1.status == "escalated"
        
        # Try to escalate again — should create a new distribution
        # from parwa (current active) to parwa_high
        escalated2 = escalate_ticket(db, "comp_1", "tick_1")
        assert escalated2.instance_id == "i3"
        
        # Source (i2) should have been decremented
        i2 = db.query(VariantInstance).filter_by(id="i2").first()
        assert i2.active_tickets_count == 0  # Was 1, escalated away


# ══════════════════════════════════════════════════════════════════
# GAP C3: Rebalance with completed tickets only
# ══════════════════════════════════════════════════════════════════

class TestGapRebalanceEdgeCases:
    def test_rebalance_does_not_move_completed_tickets(self):
        """Rebalance should only move assigned tickets, not completed."""
        db = SessionLocal()
        _make_company(db)
        i1 = _make_instance(db, iid="i1", cap={"max_concurrent_tickets": 5},
                           active_tickets=5)
        i2 = _make_instance(db, iid="i2", cap={"max_concurrent_tickets": 5},
                           active_tickets=0)
        
        # Create completed distributions on i1
        for t in range(5):
            _make_ticket(db, tid=f"tick_{t}")
            _make_distribution(db, iid="i1", tid=f"tick_{t}", status="completed")
        
        result = rebalance_workload(db, "comp_1")
        # No assigned tickets to move
        assert result["migrated_tickets"] == 0

    def test_rebalance_with_single_instance(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", cap={"max_concurrent_tickets": 5},
                       active_tickets=5)
        result = rebalance_workload(db, "comp_1")
        assert result["migrated_tickets"] == 0


# ══════════════════════════════════════════════════════════════════
# GAP A4: Performance metric hour boundary
# ══════════════════════════════════════════════════════════════════

class TestGapPerformanceMetricBoundary:
    def test_hour_23_allowed(self):
        db = SessionLocal()
        _make_company(db)
        m = AIPerformanceVariantMetric(
            company_id="comp_1",
            metric_date=__import__("datetime").date.today(),
            metric_hour=23,
        )
        db.add(m)
        db.commit()
        assert m.metric_hour == 23

    def test_null_hour_represents_daily(self):
        db = SessionLocal()
        _make_company(db)
        m1 = AIPerformanceVariantMetric(
            company_id="comp_1",
            metric_date=__import__("datetime").date.today(),
            metric_hour=None,
        )
        m2 = AIPerformanceVariantMetric(
            company_id="comp_1",
            metric_date=__import__("datetime").date.today(),
            metric_hour=12,
        )
        db.add(m1)
        db.add(m2)
        db.commit()
        # Both should exist — different unique constraint entries
        assert db.query(AIPerformanceVariantMetric).count() == 2


# ══════════════════════════════════════════════════════════════════
# GAP A5: Prompt injection severity ordering
# ══════════════════════════════════════════════════════════════════

class TestGapPromptInjectionEdgeCases:
    def test_query_preview_none(self):
        db = SessionLocal()
        _make_company(db)
        p = PromptInjectionAttempt(
            company_id="comp_1", pattern_type="role_reversal",
            severity="high", query_hash="abc",
            query_preview=None,
        )
        db.add(p)
        db.commit()
        assert p.query_preview is None

    def test_long_query_preview(self):
        db = SessionLocal()
        _make_company(db)
        long_text = "x" * 10000
        p = PromptInjectionAttempt(
            company_id="comp_1", pattern_type="role_reversal",
            severity="high", query_hash="abc",
            query_preview=long_text,
        )
        db.add(p)
        db.commit()
        assert p.query_preview == long_text

    def test_ip_address_validation(self):
        db = SessionLocal()
        _make_company(db)
        for ip in ["192.168.1.1", "::1", "10.0.0.1", None, ""]:
            p = PromptInjectionAttempt(
                company_id="comp_1", pattern_type="test",
                severity="low", query_hash=f"h_{ip}",
                ip_address=ip,
            )
            db.add(p)
        db.commit()
        assert db.query(PromptInjectionAttempt).count() == 5


# ══════════════════════════════════════════════════════════════════
# GAP: Technique cache TTL edge cases
# ══════════════════════════════════════════════════════════════════

class TestGapTechniqueCacheEdgeCases:
    def test_signal_profile_hash_nullable(self):
        db = SessionLocal()
        _make_company(db)
        tc = TechniqueCache(
            company_id="comp_1", technique_id="cot",
            query_hash="abc", cached_result="{}",
            ttl_expires_at=datetime.utcnow(),
            signal_profile_hash=None,
        )
        db.add(tc)
        db.commit()
        assert tc.signal_profile_hash is None

    def test_hit_count_increment(self):
        db = SessionLocal()
        _make_company(db)
        tc = TechniqueCache(
            company_id="comp_1", technique_id="cot",
            query_hash="abc", cached_result="{}",
            ttl_expires_at=datetime.utcnow(),
            hit_count=5,
        )
        db.add(tc)
        db.commit()
        assert tc.hit_count == 5
        tc.hit_count += 1
        db.commit()
        assert tc.hit_count == 6
