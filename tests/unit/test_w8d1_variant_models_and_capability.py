"""
Week 8 Day 1 Part A: Unit tests for Variant Engine Models + Capability Service.

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

from database.base import engine, SessionLocal, Base
from database.models.core import Company
from database.models.variant_engine import (
    VariantAICapability,
    VariantInstance,
    VariantWorkloadDistribution,
    AIAgentAssignment,
    TechniqueCache,
    AITokenBudget,
    PromptInjectionAttempt,
    AIPerformanceVariantMetric,
    PipelineStateSnapshot,
    _uuid,
)
from backend.app.services.variant_capability_service import (
    VARIANT_LEVELS,
    FEATURE_REGISTRY,
    _validate_company_id,
    _validate_variant_type,
    initialize_variant_matrix,
    get_capability,
    check_feature_enabled,
    list_capabilities,
    update_capability_config,
    get_enabled_features,
    get_variant_feature_count,
    batch_update_capabilities,
    get_all_variant_summaries,
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


def _make_instance(db, cid="comp_1", iid="inst_1", vtype="mini_parwa"):
    inst = VariantInstance(
        id=iid, company_id=cid, instance_name=f"{vtype} test",
        variant_type=vtype, status="active",
        channel_assignment="[]", capacity_config="{}",
    )
    db.add(inst)
    db.commit()
    return inst


# ══════════════════════════════════════════════════════════════════
# MODEL TESTS
# ══════════════════════════════════════════════════════════════════

class TestUUIDHelper:
    def test_generates_valid_uuid_string(self):
        u = _uuid()
        assert isinstance(u, str)
        assert len(u) == 36

    def test_unique_on_each_call(self):
        a, b = _uuid(), _uuid()
        assert a != b


class TestVariantAICapability:
    def test_create_minimal(self):
        db = SessionLocal()
        _make_company(db)
        cap = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            feature_id="F-054", feature_name="Smart Router",
        )
        db.add(cap)
        db.commit()
        assert cap.id is not None
        assert cap.is_enabled is True
        assert cap.config_json == "{}"
        assert cap.instance_id is None
        assert cap.technique_tier is None
        assert cap.created_at is not None

    def test_company_id_indexed(self):
        db = SessionLocal()
        _make_company(db)
        for vt in VARIANT_LEVELS:
            cap = VariantAICapability(
                company_id="comp_1", variant_type=vt,
                feature_id="F-054", feature_name="Smart Router",
            )
            db.add(cap)
        db.commit()
        caps = db.query(VariantAICapability).filter_by(
            company_id="comp_1", feature_id="F-054",
        ).all()
        assert len(caps) == 3

    def test_unique_constraint_company_variant_instance_feature(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        cap1 = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            instance_id="inst_1", feature_id="F-054",
            feature_name="Smart Router",
        )
        db.add(cap1)
        db.commit()
        cap2 = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            instance_id="inst_1", feature_id="F-054",
            feature_name="Smart Router",
        )
        db.add(cap2)
        with pytest.raises(Exception):
            db.commit()

    def test_instance_id_nullable(self):
        db = SessionLocal()
        _make_company(db)
        cap = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            feature_id="F-054", feature_name="Smart Router",
            instance_id=None,
        )
        db.add(cap)
        db.commit()
        assert cap.instance_id is None

    def test_config_json_stores_dict(self):
        db = SessionLocal()
        _make_company(db)
        cap = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            feature_id="F-054", feature_name="Smart Router",
            config_json=json.dumps({"threshold": 0.85}),
        )
        db.add(cap)
        db.commit()
        assert json.loads(cap.config_json) == {"threshold": 0.85}

    def test_technique_tier_stored(self):
        db = SessionLocal()
        _make_company(db)
        cap = VariantAICapability(
            company_id="comp_1", variant_type="parwa",
            feature_id="F-143", feature_name="GST",
            technique_tier="tier_2",
        )
        db.add(cap)
        db.commit()
        assert cap.technique_tier == "tier_2"

    def test_tenant_isolation(self):
        db = SessionLocal()
        _make_company(db, cid="comp_1")
        _make_company(db, cid="comp_2")
        db.add(VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            feature_id="F-054", feature_name="Smart Router",
        ))
        db.commit()
        caps = db.query(VariantAICapability).filter_by(
            company_id="comp_2",
        ).all()
        assert len(caps) == 0


class TestVariantInstance:
    def test_create_minimal(self):
        db = SessionLocal()
        _make_company(db)
        inst = VariantInstance(
            company_id="comp_1", instance_name="Mini PARWA 1",
            variant_type="mini_parwa",
        )
        db.add(inst)
        db.commit()
        assert inst.id is not None
        assert inst.status == "active"
        assert inst.active_tickets_count == 0
        assert inst.total_tickets_handled == 0
        assert inst.channel_assignment == "[]"
        assert inst.capacity_config == "{}"

    def test_status_default_active(self):
        db = SessionLocal()
        _make_company(db)
        inst = VariantInstance(
            company_id="comp_1", instance_name="Test",
            variant_type="mini_parwa",
        )
        db.add(inst)
        db.commit()
        assert inst.status == "active"

    def test_valid_statuses(self):
        db = SessionLocal()
        _make_company(db)
        for s in ["active", "inactive", "warming", "suspended"]:
            inst = VariantInstance(
                company_id="comp_1",
                instance_name=f"Inst {s}",
                variant_type="mini_parwa", status=s,
            )
            db.add(inst)
        db.commit()
        count = db.query(VariantInstance).filter_by(
            company_id="comp_1",
        ).count()
        assert count == 4

    def test_check_constraint_active_tickets_nonneg(self):
        db = SessionLocal()
        _make_company(db)
        inst = VariantInstance(
            company_id="comp_1", instance_name="Test",
            variant_type="mini_parwa",
        )
        db.add(inst)
        db.commit()
        from sqlalchemy import text
        with pytest.raises(Exception):
            db.execute(text(
                "UPDATE variant_instances SET active_tickets_count = -1 "
                "WHERE id = :id"
            ), {"id": inst.id})
            db.commit()

    def test_celery_queue_namespace(self):
        db = SessionLocal()
        _make_company(db)
        inst = VariantInstance(
            company_id="comp_1", instance_name="Test",
            variant_type="mini_parwa",
            celery_queue_namespace="tenant_comp1_mini_1",
        )
        db.add(inst)
        db.commit()
        assert inst.celery_queue_namespace == "tenant_comp1_mini_1"

    def test_redis_partition_key(self):
        db = SessionLocal()
        _make_company(db)
        inst = VariantInstance(
            company_id="comp_1", instance_name="Test",
            variant_type="mini_parwa",
            redis_partition_key="parwa:comp1:inst:min_1",
        )
        db.add(inst)
        db.commit()
        assert inst.redis_partition_key == "parwa:comp1:inst:min_1"

    def test_json_fields_parse_correctly(self):
        db = SessionLocal()
        _make_company(db)
        inst = VariantInstance(
            company_id="comp_1", instance_name="Test",
            variant_type="mini_parwa",
            channel_assignment='["email", "chat"]',
            capacity_config='{"max_concurrent_tickets": 100}',
        )
        db.add(inst)
        db.commit()
        assert json.loads(inst.channel_assignment) == ["email", "chat"]
        assert json.loads(inst.capacity_config)["max_concurrent_tickets"] == 100

    def test_tenant_isolation(self):
        db = SessionLocal()
        _make_company(db, cid="comp_1")
        _make_company(db, cid="comp_2")
        db.add(VariantInstance(
            company_id="comp_1", instance_name="C1 Inst",
            variant_type="mini_parwa",
        ))
        db.commit()
        insts = db.query(VariantInstance).filter_by(
            company_id="comp_2",
        ).all()
        assert len(insts) == 0


class TestVariantWorkloadDistribution:
    def test_create_minimal(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        ticket = __import__("database.models.tickets", fromlist=["Ticket"]).Ticket(
            id="tick_1", company_id="comp_1", channel="email",
        )
        db.add(ticket)
        db.commit()
        dist = VariantWorkloadDistribution(
            company_id="comp_1", instance_id="inst_1",
            ticket_id="tick_1", assigned_at=__import__("datetime").datetime.utcnow(),
            status="assigned",
        )
        db.add(dist)
        db.commit()
        assert dist.id is not None
        assert dist.distribution_strategy is None

    def test_default_status_assigned(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        ticket = __import__("database.models.tickets", fromlist=["Ticket"]).Ticket(
            id="tick_1", company_id="comp_1", channel="email",
        )
        db.add(ticket)
        db.commit()
        dist = VariantWorkloadDistribution(
            company_id="comp_1", instance_id="inst_1",
            ticket_id="tick_1", assigned_at=__import__("datetime").datetime.utcnow(),
        )
        db.add(dist)
        db.commit()
        assert dist.status == "assigned"

    def test_escalation_fields_nullable(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _make_instance(db, iid="inst_2")
        ticket = __import__("database.models.tickets", fromlist=["Ticket"]).Ticket(
            id="tick_1", company_id="comp_1", channel="email",
        )
        db.add(ticket)
        db.commit()
        dist = VariantWorkloadDistribution(
            company_id="comp_1", instance_id="inst_1",
            ticket_id="tick_1",
            assigned_at=__import__("datetime").datetime.utcnow(),
            escalation_target_instance_id="inst_2",
            rebalance_from_instance_id="inst_2",
            billing_charged_to_instance="inst_2",
        )
        db.add(dist)
        db.commit()
        assert dist.escalation_target_instance_id == "inst_2"
        assert dist.rebalance_from_instance_id == "inst_2"
        assert dist.billing_charged_to_instance == "inst_2"

    def test_tenant_isolation(self):
        db = SessionLocal()
        _make_company(db, cid="comp_1")
        _make_company(db, cid="comp_2")
        _make_instance(db, cid="comp_1")
        _make_instance(db, cid="comp_2", iid="inst_2")
        ticket = __import__("database.models.tickets", fromlist=["Ticket"]).Ticket(
            id="tick_1", company_id="comp_1", channel="email",
        )
        db.add(ticket)
        db.commit()
        dist = VariantWorkloadDistribution(
            company_id="comp_1", instance_id="inst_1",
            ticket_id="tick_1",
            assigned_at=__import__("datetime").datetime.utcnow(),
        )
        db.add(dist)
        db.commit()
        dists = db.query(VariantWorkloadDistribution).filter_by(
            company_id="comp_2",
        ).all()
        assert len(dists) == 0


class TestAIAgentAssignment:
    def test_create_minimal(self):
        db = SessionLocal()
        _make_company(db)
        a = AIAgentAssignment(
            agent_name="Agent 1",
            agent_role="Infrastructure",
        )
        db.add(a)
        db.commit()
        assert a.id is not None
        assert a.status == "active"

    def test_no_company_id_global_table(self):
        db = SessionLocal()
        a = AIAgentAssignment(agent_name="Agent 2")
        db.add(a)
        db.commit()
        assert a.company_id is None  # No company_id column

    def test_json_fields(self):
        db = SessionLocal()
        a = AIAgentAssignment(
            agent_name="Agent 1",
            feature_ids='["F-054", "F-055"]',
            task_ids='["d1-01"]',
        )
        db.add(a)
        db.commit()
        assert json.loads(a.feature_ids) == ["F-054", "F-055"]


class TestTechniqueCache:
    def test_create_minimal(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        tc = TechniqueCache(
            company_id="comp_1", instance_id="inst_1",
            technique_id="cot", query_hash="abc123",
            cached_result='{"answer": "test"}',
            ttl_expires_at=__import__("datetime").datetime.utcnow(),
        )
        db.add(tc)
        db.commit()
        assert tc.id is not None
        assert tc.hit_count == 0

    def test_unique_constraint(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        exp = __import__("datetime").datetime.utcnow()
        tc1 = TechniqueCache(
            company_id="comp_1", instance_id="inst_1",
            technique_id="cot", query_hash="abc123",
            cached_result="{}", ttl_expires_at=exp,
        )
        db.add(tc1)
        db.commit()
        tc2 = TechniqueCache(
            company_id="comp_1", instance_id="inst_1",
            technique_id="cot", query_hash="abc123",
            cached_result="{}", ttl_expires_at=exp,
        )
        db.add(tc2)
        with pytest.raises(Exception):
            db.commit()

    def test_similarity_score_numeric(self):
        db = SessionLocal()
        _make_company(db)
        tc = TechniqueCache(
            company_id="comp_1", technique_id="cot",
            query_hash="abc", cached_result="{}",
            ttl_expires_at=__import__("datetime").datetime.utcnow(),
            similarity_score=0.9543,
        )
        db.add(tc)
        db.commit()
        assert float(tc.similarity_score) == pytest.approx(0.9543, rel=1e-3)

    def test_instance_id_nullable(self):
        db = SessionLocal()
        _make_company(db)
        tc = TechniqueCache(
            company_id="comp_1", instance_id=None,
            technique_id="cot", query_hash="abc",
            cached_result="{}",
            ttl_expires_at=__import__("datetime").datetime.utcnow(),
        )
        db.add(tc)
        db.commit()
        assert tc.instance_id is None


class TestAITokenBudget:
    def test_create_minimal(self):
        db = SessionLocal()
        _make_company(db)
        tb = AITokenBudget(
            company_id="comp_1", budget_type="daily",
            budget_period="2026-04-08", max_tokens=100000,
        )
        db.add(tb)
        db.commit()
        assert tb.id is not None
        assert tb.used_tokens == 0
        assert tb.alert_threshold_pct == 80
        assert tb.hard_stop is True
        assert tb.status == "active"

    def test_unique_constraint_instance_period(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        tb1 = AITokenBudget(
            company_id="comp_1", instance_id="inst_1",
            budget_type="daily", budget_period="2026-04-08",
            max_tokens=100000,
        )
        db.add(tb1)
        db.commit()
        tb2 = AITokenBudget(
            company_id="comp_1", instance_id="inst_1",
            budget_type="daily", budget_period="2026-04-08",
            max_tokens=100000,
        )
        db.add(tb2)
        with pytest.raises(Exception):
            db.commit()

    def test_different_period_no_conflict(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        for p in ["2026-04-08", "2026-04-09"]:
            tb = AITokenBudget(
                company_id="comp_1", instance_id="inst_1",
                budget_type="daily", budget_period=p,
                max_tokens=100000,
            )
            db.add(tb)
        db.commit()
        assert db.query(AITokenBudget).filter_by(
            company_id="comp_1",
        ).count() == 2

    def test_variant_default_limits_json(self):
        db = SessionLocal()
        _make_company(db)
        tb = AITokenBudget(
            company_id="comp_1", budget_type="daily",
            budget_period="2026-04",
            max_tokens=500000,
            variant_default_limits=json.dumps({
                "mini_parwa": {"daily": 50000},
                "parwa": {"daily": 200000},
            }),
        )
        db.add(tb)
        db.commit()
        limits = json.loads(tb.variant_default_limits)
        assert limits["mini_parwa"]["daily"] == 50000


class TestPromptInjectionAttempt:
    def test_create_minimal(self):
        db = SessionLocal()
        _make_company(db)
        p = PromptInjectionAttempt(
            company_id="comp_1", pattern_type="role_reversal",
            severity="high", query_hash="sha256hash",
        )
        db.add(p)
        db.commit()
        assert p.id is not None
        assert p.action_taken == "logged"

    def test_all_action_types(self):
        db = SessionLocal()
        _make_company(db)
        for action in ["logged", "blocked", "escalated"]:
            p = PromptInjectionAttempt(
                company_id="comp_1",
                pattern_type="role_reversal",
                severity="high", query_hash=f"hash_{action}",
                action_taken=action,
            )
            db.add(p)
        db.commit()
        assert db.query(PromptInjectionAttempt).count() == 3

    def test_severity_values(self):
        db = SessionLocal()
        _make_company(db)
        for sev in ["low", "medium", "high", "critical"]:
            p = PromptInjectionAttempt(
                company_id="comp_1", pattern_type="test",
                severity=sev, query_hash=f"hash_{sev}",
            )
            db.add(p)
        db.commit()
        assert db.query(PromptInjectionAttempt).count() == 4

    def test_detection_methods(self):
        db = SessionLocal()
        _make_company(db)
        for dm in ["regex", "classifier", "heuristic"]:
            p = PromptInjectionAttempt(
                company_id="comp_1", pattern_type="test",
                severity="low", query_hash=f"h_{dm}",
                detection_method=dm,
            )
            db.add(p)
        db.commit()
        assert db.query(PromptInjectionAttempt).count() == 3


class TestAIPerformanceVariantMetric:
    def test_create_minimal(self):
        db = SessionLocal()
        _make_company(db)
        m = AIPerformanceVariantMetric(
            company_id="comp_1", metric_date=__import__("datetime").date.today(),
        )
        db.add(m)
        db.commit()
        assert m.id is not None
        assert m.total_queries == 0
        assert m.successful_queries == 0
        assert m.failed_queries == 0
        assert m.avg_latency_ms == 0
        assert m.p95_latency_ms == 0
        assert m.total_tokens_used == 0

    def test_total_cost_usd_numeric(self):
        db = SessionLocal()
        _make_company(db)
        m = AIPerformanceVariantMetric(
            company_id="comp_1",
            metric_date=__import__("datetime").date.today(),
            total_cost_usd=1.2345,
        )
        db.add(m)
        db.commit()
        assert float(m.total_cost_usd) == pytest.approx(1.2345, rel=1e-3)

    def test_metric_hour_nullable(self):
        db = SessionLocal()
        _make_company(db)
        m = AIPerformanceVariantMetric(
            company_id="comp_1",
            metric_date=__import__("datetime").date.today(),
            metric_hour=None,
        )
        db.add(m)
        db.commit()
        assert m.metric_hour is None

    def test_unique_constraint_date_hour(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        today = __import__("datetime").date.today()
        m1 = AIPerformanceVariantMetric(
            company_id="comp_1", instance_id="inst_1",
            metric_date=today, metric_hour=10,
        )
        db.add(m1)
        db.commit()
        m2 = AIPerformanceVariantMetric(
            company_id="comp_1", instance_id="inst_1",
            metric_date=today, metric_hour=10,
        )
        db.add(m2)
        with pytest.raises(Exception):
            db.commit()


class TestPipelineStateSnapshot:
    def test_create_minimal(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        ticket = __import__("database.models.tickets", fromlist=["Ticket"]).Ticket(
            id="tick_1", company_id="comp_1", channel="email",
        )
        db.add(ticket)
        db.commit()
        snap = PipelineStateSnapshot(
            company_id="comp_1", instance_id="inst_1",
            ticket_id="tick_1", current_node="router",
            state_data='{"step": 1}',
        )
        db.add(snap)
        db.commit()
        assert snap.id is not None
        assert snap.snapshot_type == "auto"
        assert snap.technique_stack == "[]"
        assert snap.token_count == 0

    def test_snapshot_types(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        ticket = __import__("database.models.tickets", fromlist=["Ticket"]).Ticket(
            id="tick_1", company_id="comp_1", channel="email",
        )
        db.add(ticket)
        db.commit()
        for st in ["auto", "manual", "error", "checkpoint"]:
            snap = PipelineStateSnapshot(
                company_id="comp_1", instance_id="inst_1",
                ticket_id="tick_1", current_node="router",
                state_data="{}", snapshot_type=st,
            )
            db.add(snap)
        db.commit()
        assert db.query(PipelineStateSnapshot).count() == 4

    def test_technique_stack_json(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        ticket = __import__("database.models.tickets", fromlist=["Ticket"]).Ticket(
            id="tick_1", company_id="comp_1", channel="email",
        )
        db.add(ticket)
        db.commit()
        snap = PipelineStateSnapshot(
            company_id="comp_1", instance_id="inst_1",
            ticket_id="tick_1", current_node="router",
            state_data="{}",
            technique_stack='["cot", "react", "crp"]',
        )
        db.add(snap)
        db.commit()
        assert json.loads(snap.technique_stack) == ["cot", "react", "crp"]


# ══════════════════════════════════════════════════════════════════
# CAPABILITY SERVICE TESTS
# ══════════════════════════════════════════════════════════════════

class TestValidateCompanyId:
    def test_empty_raises(self):
        with pytest.raises(ParwaBaseError) as exc:
            _validate_company_id("")
        assert exc.value.error_code == "INVALID_COMPANY_ID"
        assert exc.value.status_code == 400

    def test_whitespace_raises(self):
        with pytest.raises(ParwaBaseError):
            _validate_company_id("   ")

    def test_none_raises(self):
        with pytest.raises(ParwaBaseError):
            _validate_company_id(None)

    def test_valid_passes(self):
        _validate_company_id("comp_1")  # Should not raise


class TestValidateVariantType:
    def test_invalid_raises(self):
        with pytest.raises(ParwaBaseError) as exc:
            _validate_variant_type("unknown_type")
        assert exc.value.error_code == "INVALID_VARIANT_TYPE"

    def test_all_valid_pass(self):
        for vt in VARIANT_LEVELS:
            _validate_variant_type(vt)


class TestFeatureRegistry:
    def test_has_170_plus_features(self):
        assert len(FEATURE_REGISTRY) >= 170

    def test_all_features_have_required_fields(self):
        for fid, feat in FEATURE_REGISTRY.items():
            assert "name" in feat, f"{fid} missing name"
            assert "category" in feat, f"{fid} missing category"
            assert "min_level" in feat, f"{fid} missing min_level"
            assert feat["min_level"] in (1, 2, 3)

    def test_all_variant_levels_defined(self):
        assert set(VARIANT_LEVELS.keys()) == {
            "mini_parwa", "parwa", "parwa_high",
        }
        assert VARIANT_LEVELS["mini_parwa"] == 1
        assert VARIANT_LEVELS["parwa"] == 2
        assert VARIANT_LEVELS["parwa_high"] == 3

    def test_known_features_exist(self):
        for fid in ["F-054", "F-060", "F-080", "F-140", "F-150",
                     "F-160", "F-180", "SG-01", "SG-37", "SG-38"]:
            assert fid in FEATURE_REGISTRY, f"{fid} missing from registry"


class TestInitializeVariantMatrix:
    def test_creates_features_for_all_variants(self):
        db = SessionLocal()
        _make_company(db)
        count = initialize_variant_matrix(db, "comp_1")
        assert count > 0
        assert count == len(FEATURE_REGISTRY) * 3
        caps = db.query(VariantAICapability).filter_by(
            company_id="comp_1",
        ).count()
        assert caps == len(FEATURE_REGISTRY) * 3

    def test_idempotent_second_call_returns_zero(self):
        db = SessionLocal()
        _make_company(db)
        count1 = initialize_variant_matrix(db, "comp_1")
        count2 = initialize_variant_matrix(db, "comp_1")
        assert count1 > 0
        assert count2 == 0

    def test_enabled_based_on_min_level(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        # F-054 min_level=1, should be enabled for all
        for vt in VARIANT_LEVELS:
            cap = db.query(VariantAICapability).filter_by(
                company_id="comp_1", variant_type=vt,
                feature_id="F-054", instance_id=None,
            ).first()
            assert cap.is_enabled is True
        # F-143 min_level=2, should be disabled for mini_parwa
        cap = db.query(VariantAICapability).filter_by(
            company_id="comp_1", variant_type="mini_parwa",
            feature_id="F-143", instance_id=None,
        ).first()
        assert cap.is_enabled is False
        # F-150 min_level=3, disabled for mini_parwa and parwa
        for vt in ["mini_parwa", "parwa"]:
            cap = db.query(VariantAICapability).filter_by(
                company_id="comp_1", variant_type=vt,
                feature_id="F-150", instance_id=None,
            ).first()
            assert cap.is_enabled is False
        # Enabled for parwa_high
        cap = db.query(VariantAICapability).filter_by(
            company_id="comp_1", variant_type="parwa_high",
            feature_id="F-150", instance_id=None,
        ).first()
        assert cap.is_enabled is True

    def test_instance_id_null_for_defaults(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        nulls = db.query(VariantAICapability).filter_by(
            company_id="comp_1", instance_id=None,
        ).count()
        assert nulls == len(FEATURE_REGISTRY) * 3

    def test_tenant_isolation(self):
        db = SessionLocal()
        _make_company(db, cid="comp_1")
        _make_company(db, cid="comp_2")
        initialize_variant_matrix(db, "comp_1")
        caps = db.query(VariantAICapability).filter_by(
            company_id="comp_2",
        ).count()
        assert caps == 0

    def test_empty_company_id_raises(self):
        db = SessionLocal()
        with pytest.raises(ParwaBaseError):
            initialize_variant_matrix(db, "")


class TestGetCapability:
    def test_returns_variant_default(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        cap = get_capability(db, "comp_1", "F-054", "mini_parwa")
        assert cap is not None
        assert cap.variant_type == "mini_parwa"
        assert cap.instance_id is None

    def test_instance_override_takes_precedence(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        initialize_variant_matrix(db, "comp_1")
        # Create instance override: disable F-054 for inst_1
        override = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            instance_id="inst_1", feature_id="F-054",
            feature_name="Smart Router", is_enabled=False,
        )
        db.add(override)
        db.commit()
        cap = get_capability(
            db, "comp_1", "F-054", "mini_parwa",
            instance_id="inst_1",
        )
        assert cap is not None
        assert cap.instance_id == "inst_1"
        assert cap.is_enabled is False

    def test_returns_none_when_no_variant_type(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        cap = get_capability(db, "comp_1", "F-054", None)
        assert cap is None

    def test_returns_none_for_unknown_feature(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        cap = get_capability(db, "comp_1", "F-999", "mini_parwa")
        assert cap is None

    def test_tenant_isolation(self):
        db = SessionLocal()
        _make_company(db, cid="comp_1")
        _make_company(db, cid="comp_2")
        initialize_variant_matrix(db, "comp_1")
        cap = get_capability(db, "comp_2", "F-054", "mini_parwa")
        assert cap is None


class TestCheckFeatureEnabled:
    def test_enabled_returns_true(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        assert check_feature_enabled(
            db, "comp_1", "F-054", "mini_parwa",
        ) is True

    def test_disabled_returns_false(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        assert check_feature_enabled(
            db, "comp_1", "F-143", "mini_parwa",
        ) is False

    def test_unknown_feature_returns_false(self):
        db = SessionLocal()
        _make_company(db)
        assert check_feature_enabled(
            db, "comp_1", "F-999", "mini_parwa",
        ) is False

    def test_instance_override_respected(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        initialize_variant_matrix(db, "comp_1")
        override = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            instance_id="inst_1", feature_id="F-054",
            feature_name="Smart Router", is_enabled=False,
        )
        db.add(override)
        db.commit()
        assert check_feature_enabled(
            db, "comp_1", "F-054", "mini_parwa",
            instance_id="inst_1",
        ) is False


class TestListCapabilities:
    def test_list_all_for_company(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        caps = list_capabilities(db, "comp_1")
        assert len(caps) == len(FEATURE_REGISTRY) * 3

    def test_filter_by_variant_type(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        caps = list_capabilities(db, "comp_1", variant_type="parwa_high")
        assert all(c.variant_type == "parwa_high" for c in caps)
        assert len(caps) == len(FEATURE_REGISTRY)

    def test_filter_by_category(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        caps = list_capabilities(db, "comp_1", feature_category="routing")
        assert all(c.feature_category == "routing" for c in caps)
        assert len(caps) > 0

    def test_filter_enabled_only(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        caps = list_capabilities(db, "comp_1", enabled_only=True)
        assert all(c.is_enabled for c in caps)

    def test_filter_by_instance_id(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        initialize_variant_matrix(db, "comp_1")
        override = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            instance_id="inst_1", feature_id="F-054",
            feature_name="Smart Router",
        )
        db.add(override)
        db.commit()
        caps = list_capabilities(db, "comp_1", instance_id="inst_1")
        assert all(c.instance_id == "inst_1" for c in caps)

    def test_ordered_by_feature_id(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        caps = list_capabilities(db, "comp_1", variant_type="mini_parwa")
        ids = [c.feature_id for c in caps]
        assert ids == sorted(ids)

    def test_empty_company_id_raises(self):
        db = SessionLocal()
        with pytest.raises(ParwaBaseError):
            list_capabilities(db, "")


class TestUpdateCapabilityConfig:
    def test_updates_config_json(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        new_cfg = {"threshold": 0.99, "custom": True}
        cap = update_capability_config(
            db, "comp_1", "F-054", "mini_parwa", new_cfg,
        )
        assert json.loads(cap.config_json) == new_cfg

    def test_not_found_raises_404(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        with pytest.raises(ParwaBaseError) as exc:
            update_capability_config(
                db, "comp_1", "F-999", "mini_parwa", {},
            )
        assert exc.value.error_code == "CAPABILITY_NOT_FOUND"
        assert exc.value.status_code == 404

    def test_invalid_variant_raises(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError):
            update_capability_config(
                db, "comp_1", "F-054", "invalid", {},
            )

    def test_instance_specific_override(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        initialize_variant_matrix(db, "comp_1")
        override = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            instance_id="inst_1", feature_id="F-054",
            feature_name="Smart Router",
        )
        db.add(override)
        db.commit()
        new_cfg = {"override": True}
        cap = update_capability_config(
            db, "comp_1", "F-054", "mini_parwa", new_cfg,
            instance_id="inst_1",
        )
        assert json.loads(cap.config_json) == new_cfg
        assert cap.instance_id == "inst_1"


class TestGetEnabledFeatures:
    def test_returns_list_of_ids(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        enabled = get_enabled_features(db, "comp_1", "mini_parwa")
        assert isinstance(enabled, list)
        assert all(isinstance(f, str) for f in enabled)
        assert "F-054" in enabled  # min_level=1
        assert "F-143" not in enabled  # min_level=2

    def test_parwa_high_has_more_features(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        mini = get_enabled_features(db, "comp_1", "mini_parwa")
        high = get_enabled_features(db, "comp_1", "parwa_high")
        assert len(high) > len(mini)

    def test_invalid_variant_raises(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError):
            get_enabled_features(db, "comp_1", "invalid")


class TestGetVariantFeatureCount:
    def test_returns_correct_counts(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        result = get_variant_feature_count(db, "comp_1", "mini_parwa")
        assert result["variant_type"] == "mini_parwa"
        assert result["total_features"] == len(FEATURE_REGISTRY)
        assert result["enabled_features"] + result["disabled_features"] == len(FEATURE_REGISTRY)

    def test_mini_parwa_has_fewer_enabled(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        mini = get_variant_feature_count(db, "comp_1", "mini_parwa")
        high = get_variant_feature_count(db, "comp_1", "parwa_high")
        assert mini["enabled_features"] < high["enabled_features"]

    def test_parwa_high_all_enabled(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        result = get_variant_feature_count(db, "comp_1", "parwa_high")
        assert result["disabled_features"] == 0


class TestBatchUpdateCapabilities:
    def test_enable_disable(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        updates = [
            {"feature_id": "F-054", "variant_type": "mini_parwa",
             "is_enabled": False},
            {"feature_id": "F-143", "variant_type": "parwa",
             "is_enabled": True},
        ]
        result = batch_update_capabilities(db, "comp_1", updates)
        assert result["updated"] == 2
        assert result["errors"] == 0

    def test_missing_fields_counted_as_error(self):
        db = SessionLocal()
        _make_company(db)
        updates = [
            {"feature_id": "", "variant_type": "mini_parwa",
             "is_enabled": True},
            {"variant_type": "parwa", "is_enabled": True},
            {"feature_id": "F-054", "is_enabled": True},
        ]
        result = batch_update_capabilities(db, "comp_1", updates)
        assert result["errors"] == 3

    def test_invalid_variant_counted_as_error(self):
        db = SessionLocal()
        _make_company(db)
        updates = [
            {"feature_id": "F-054", "variant_type": "invalid",
             "is_enabled": True},
        ]
        result = batch_update_capabilities(db, "comp_1", updates)
        assert result["errors"] == 1

    def test_unknown_feature_skipped(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        updates = [
            {"feature_id": "F-999", "variant_type": "mini_parwa",
             "is_enabled": True},
        ]
        result = batch_update_capabilities(db, "comp_1", updates)
        assert result["skipped"] == 1

    def test_empty_list_returns_zeros(self):
        db = SessionLocal()
        _make_company(db)
        result = batch_update_capabilities(db, "comp_1", [])
        assert result == {"updated": 0, "skipped": 0, "errors": 0}

    def test_actual_toggle_persists(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        # F-054 is enabled for mini_parwa by default
        updates = [
            {"feature_id": "F-054", "variant_type": "mini_parwa",
             "is_enabled": False},
        ]
        batch_update_capabilities(db, "comp_1", updates)
        cap = db.query(VariantAICapability).filter_by(
            company_id="comp_1", variant_type="mini_parwa",
            feature_id="F-054", instance_id=None,
        ).first()
        assert cap.is_enabled is False


class TestGetAllVariantSummaries:
    def test_returns_all_three_variants(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        summaries = get_all_variant_summaries(db, "comp_1")
        assert len(summaries) == 3
        types = {s["variant_type"] for s in summaries}
        assert types == {"mini_parwa", "parwa", "parwa_high"}

    def test_each_summary_has_required_keys(self):
        db = SessionLocal()
        _make_company(db)
        initialize_variant_matrix(db, "comp_1")
        summaries = get_all_variant_summaries(db, "comp_1")
        for s in summaries:
            assert "variant_type" in s
            assert "total_features" in s
            assert "enabled_features" in s
            assert "disabled_features" in s
