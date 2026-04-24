"""
Week 8 Day 1 Part B: Unit tests for Variant Instance Service + Entitlement Middleware.

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
    VariantInstance,
    VariantAICapability,
)
from backend.app.services.variant_instance_service import (
    VALID_VARIANT_TYPES,
    VALID_STATUSES,
    VALID_CHANNELS,
    VARIANT_PRIORITY,
    _validate_company_id,
    _validate_variant_type,
    _validate_instance_name,
    _validate_channels,
    _validate_status,
    _generate_celery_namespace,
    _generate_redis_partition_key,
    register_instance,
    deactivate_instance,
    activate_instance,
    suspend_instance,
    list_instances,
    get_instance,
    get_highest_active_variant,
    get_total_capacity,
    update_channel_assignment,
    update_capacity_config,
    increment_active_tickets,
    decrement_active_tickets,
    get_least_loaded_instance,
    get_instance_for_channel,
)
from backend.app.services.entitlement_middleware import (
    PLAN_DISPLAY_NAMES,
    PLAN_PRICING,
    EntitlementResult,
    _get_required_variant_type,
    _build_upgrade_suggestion,
    check_entitlement,
    enforce_entitlement,
    get_upgrade_nudge,
    batch_check_entitlements,
    create_instance_override,
    remove_instance_override,
    get_entitlement_summary,
)
from backend.app.services.variant_capability_service import (
    initialize_variant_matrix,
    VARIANT_LEVELS,
    FEATURE_REGISTRY,
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
                   name=None, status="active", channels=None, cap=None):
    inst = VariantInstance(
        id=iid, company_id=cid,
        instance_name=name or f"{vtype} test",
        variant_type=vtype, status=status,
        channel_assignment=json.dumps(channels or []),
        capacity_config=json.dumps(cap or {}),
    )
    db.add(inst)
    db.commit()
    return inst


def _init_matrix(db, cid="comp_1"):
    initialize_variant_matrix(db, cid)


# ══════════════════════════════════════════════════════════════════
# INSTANCE SERVICE — VALIDATION HELPERS
# ══════════════════════════════════════════════════════════════════

class TestInstanceValidateCompanyId:
    def test_empty_raises(self):
        with pytest.raises(ParwaBaseError) as exc:
            _validate_company_id("")
        assert exc.value.error_code == "INVALID_COMPANY_ID"

    def test_whitespace_raises(self):
        with pytest.raises(ParwaBaseError):
            _validate_company_id("   ")

    def test_valid_passes(self):
        _validate_company_id("comp_1")


class TestInstanceValidateVariantType:
    def test_invalid_raises(self):
        with pytest.raises(ParwaBaseError) as exc:
            _validate_variant_type("free_tier")
        assert exc.value.error_code == "INVALID_VARIANT_TYPE"

    def test_all_valid_pass(self):
        for vt in VALID_VARIANT_TYPES:
            _validate_variant_type(vt)


class TestValidateInstanceName:
    def test_empty_raises(self):
        with pytest.raises(ParwaBaseError) as exc:
            _validate_instance_name("")
        assert exc.value.error_code == "INVALID_INSTANCE_NAME"

    def test_whitespace_raises(self):
        with pytest.raises(ParwaBaseError):
            _validate_instance_name("   ")

    def test_valid_passes(self):
        _validate_instance_name("Mini PARWA Chat")


class TestValidateChannels:
    def test_valid_channels_pass(self):
        _validate_channels(["email", "chat", "sms"])

    def test_empty_list_passes(self):
        _validate_channels([])

    def test_invalid_channel_raises(self):
        with pytest.raises(ParwaBaseError) as exc:
            _validate_channels(["email", "telepathy"])
        assert exc.value.error_code == "INVALID_CHANNEL"

    def test_all_known_channels(self):
        _validate_channels(list(VALID_CHANNELS))


class TestValidateStatus:
    def test_valid_passes(self):
        for s in VALID_STATUSES:
            _validate_status(s)

    def test_invalid_raises(self):
        with pytest.raises(ParwaBaseError) as exc:
            _validate_status("destroyed")
        assert exc.value.error_code == "INVALID_STATUS"


class TestGenerateCeleryNamespace:
    def test_mini_parwa_format(self):
        ns = _generate_celery_namespace("comp_1", "mini_parwa", 1)
        assert ns == "tenant_comp_1_miniparwa_1"

    def test_parwa_format(self):
        ns = _generate_celery_namespace("comp_1", "parwa", 2)
        assert ns == "tenant_comp_1_parwa_2"

    def test_parwa_high_format(self):
        ns = _generate_celery_namespace("comp_1", "parwa_high", 1)
        assert ns == "tenant_comp_1_parwahigh_1"

    def test_incremental_number(self):
        ns1 = _generate_celery_namespace("c1", "parwa", 1)
        ns2 = _generate_celery_namespace("c1", "parwa", 2)
        assert ns1 != ns2


class TestGenerateRedisPartitionKey:
    def test_mini_parwa_format(self):
        key = _generate_redis_partition_key("comp_1", "mini_parwa", 1)
        assert key == "parwa:comp_1:inst:min_1"

    def test_parwa_format(self):
        key = _generate_redis_partition_key("comp_1", "parwa", 2)
        assert key == "parwa:comp_1:inst:par_2"

    def test_parwa_high_format(self):
        key = _generate_redis_partition_key("comp_1", "parwa_high", 1)
        assert key == "parwa:comp_1:inst:high_1"


class TestVariantPriority:
    def test_correct_ordering(self):
        assert VARIANT_PRIORITY["mini_parwa"] == 1
        assert VARIANT_PRIORITY["parwa"] == 2
        assert VARIANT_PRIORITY["parwa_high"] == 3


# ══════════════════════════════════════════════════════════════════
# INSTANCE SERVICE — MAIN FUNCTIONS
# ══════════════════════════════════════════════════════════════════

class TestRegisterInstance:
    def test_creates_instance(self):
        db = SessionLocal()
        _make_company(db)
        inst = register_instance(
            db, "comp_1", "Mini PARWA Chat", "mini_parwa",
        )
        assert inst.id is not None
        assert inst.status == "active"
        assert inst.variant_type == "mini_parwa"
        assert inst.active_tickets_count == 0
        assert inst.total_tickets_handled == 0

    def test_strips_name_whitespace(self):
        db = SessionLocal()
        _make_company(db)
        inst = register_instance(
            db, "comp_1", "  Mini PARWA Chat  ", "mini_parwa",
        )
        assert inst.instance_name == "Mini PARWA Chat"

    def test_generates_celery_namespace(self):
        db = SessionLocal()
        _make_company(db)
        inst = register_instance(
            db, "comp_1", "Test", "mini_parwa",
        )
        assert inst.celery_queue_namespace is not None
        assert "tenant_comp_1" in inst.celery_queue_namespace

    def test_generates_redis_key(self):
        db = SessionLocal()
        _make_company(db)
        inst = register_instance(
            db, "comp_1", "Test", "mini_parwa",
        )
        assert inst.redis_partition_key is not None
        assert "parwa:" in inst.redis_partition_key

    def test_channel_assignment_stored(self):
        db = SessionLocal()
        _make_company(db)
        inst = register_instance(
            db, "comp_1", "Test", "mini_parwa",
            channel_assignment=["email", "chat"],
        )
        assert json.loads(inst.channel_assignment) == ["email", "chat"]

    def test_invalid_channel_raises(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError):
            register_instance(
                db, "comp_1", "Test", "mini_parwa",
                channel_assignment=["email", "telepathy"],
            )

    def test_capacity_config_stored(self):
        db = SessionLocal()
        _make_company(db)
        inst = register_instance(
            db, "comp_1", "Test", "mini_parwa",
            capacity_config={"max_concurrent_tickets": 100},
        )
        assert json.loads(inst.capacity_config) == {
            "max_concurrent_tickets": 100,
        }

    def test_incremental_namespace(self):
        db = SessionLocal()
        _make_company(db)
        i1 = register_instance(db, "comp_1", "Test 1", "mini_parwa")
        i2 = register_instance(db, "comp_1", "Test 2", "mini_parwa")
        assert i1.celery_queue_namespace != i2.celery_queue_namespace

    def test_empty_company_id_raises(self):
        db = SessionLocal()
        with pytest.raises(ParwaBaseError):
            register_instance(db, "", "Test", "mini_parwa")

    def test_empty_name_raises(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError):
            register_instance(db, "comp_1", "", "mini_parwa")


class TestDeactivateInstance:
    def test_sets_inactive(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        inst = deactivate_instance(db, "comp_1", "inst_1")
        assert inst.status == "inactive"

    def test_not_found_raises_404(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError) as exc:
            deactivate_instance(db, "comp_1", "nonexistent")
        assert exc.value.status_code == 404


class TestActivateInstance:
    def test_sets_active(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, status="inactive")
        inst = activate_instance(db, "comp_1", "inst_1")
        assert inst.status == "active"

    def test_not_found_raises_404(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError) as exc:
            activate_instance(db, "comp_1", "nonexistent")
        assert exc.value.status_code == 404


class TestSuspendInstance:
    def test_sets_suspended(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        inst = suspend_instance(db, "comp_1", "inst_1")
        assert inst.status == "suspended"

    def test_not_found_raises_404(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError) as exc:
            suspend_instance(db, "comp_1", "nonexistent")
        assert exc.value.status_code == 404


class TestListInstances:
    def test_lists_all(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="inst_1")
        _make_instance(db, iid="inst_2")
        insts = list_instances(db, "comp_1")
        assert len(insts) == 2

    def test_filter_by_variant_type(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa")
        _make_instance(db, iid="i2", vtype="parwa")
        insts = list_instances(db, "comp_1", variant_type="mini_parwa")
        assert len(insts) == 1
        assert insts[0].variant_type == "mini_parwa"

    def test_filter_by_status(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", status="active")
        _make_instance(db, iid="i2", status="inactive")
        insts = list_instances(db, "comp_1", status="inactive")
        assert len(insts) == 1

    def test_tenant_isolation(self):
        db = SessionLocal()
        _make_company(db, cid="comp_1")
        _make_company(db, cid="comp_2")
        _make_instance(db, cid="comp_1")
        insts = list_instances(db, "comp_2")
        assert len(insts) == 0


class TestGetInstance:
    def test_returns_instance(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        inst = get_instance(db, "comp_1", "inst_1")
        assert inst is not None
        assert inst.id == "inst_1"

    def test_returns_none_if_not_found(self):
        db = SessionLocal()
        _make_company(db)
        inst = get_instance(db, "comp_1", "nonexistent")
        assert inst is None


class TestGetHighestActiveVariant:
    def test_returns_highest(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa")
        _make_instance(db, iid="i2", vtype="parwa")
        _make_instance(db, iid="i3", vtype="parwa_high")
        result = get_highest_active_variant(db, "comp_1")
        assert result == "parwa_high"

    def test_returns_parwa_if_no_high(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa")
        _make_instance(db, iid="i2", vtype="parwa")
        result = get_highest_active_variant(db, "comp_1")
        assert result == "parwa"

    def test_returns_none_if_no_active(self):
        db = SessionLocal()
        _make_company(db)
        result = get_highest_active_variant(db, "comp_1")
        assert result is None

    def test_ignores_inactive_instances(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="parwa_high", status="inactive")
        _make_instance(db, iid="i2", vtype="mini_parwa")
        result = get_highest_active_variant(db, "comp_1")
        assert result == "mini_parwa"


class TestGetTotalCapacity:
    def test_aggregates_active_instances(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa",
                       cap={"max_concurrent_tickets": 50})
        _make_instance(db, iid="i2", vtype="parwa",
                       cap={"max_concurrent_tickets": 100})
        result = get_total_capacity(db, "comp_1")
        assert result["total_active_instances"] == 2
        assert result["total_max_concurrent"] == 150

    def test_ignores_inactive(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa", status="inactive",
                       cap={"max_concurrent_tickets": 100})
        result = get_total_capacity(db, "comp_1")
        assert result["total_active_instances"] == 0

    def test_includes_active_ticket_count(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa",
                       cap={"max_concurrent_tickets": 100})
        db.execute(__import__("sqlalchemy").text(
            "UPDATE variant_instances SET active_tickets_count = 30 "
            "WHERE id = 'i1'"
        ))
        db.commit()
        result = get_total_capacity(db, "comp_1")
        assert result["total_active_tickets"] == 30
        assert result["available_capacity"] == 70

    def test_handles_malformed_json_gracefully(self):
        db = SessionLocal()
        _make_company(db)
        inst = _make_instance(db, iid="i1")
        inst.capacity_config = "not json"
        db.commit()
        result = get_total_capacity(db, "comp_1")
        assert result["total_max_concurrent"] == 50  # default

    def test_by_variant_type_breakdown(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa",
                       cap={"max_concurrent_tickets": 50})
        _make_instance(db, iid="i2", vtype="parwa",
                       cap={"max_concurrent_tickets": 100})
        result = get_total_capacity(db, "comp_1")
        assert "mini_parwa" in result["by_variant_type"]
        assert "parwa" in result["by_variant_type"]

    def test_empty_company_raises(self):
        db = SessionLocal()
        with pytest.raises(ParwaBaseError):
            get_total_capacity(db, "")


class TestUpdateChannelAssignment:
    def test_updates_channels(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        inst = update_channel_assignment(
            db, "comp_1", "inst_1", ["email", "chat", "sms"],
        )
        assert json.loads(inst.channel_assignment) == [
            "email", "chat", "sms",
        ]

    def test_invalid_channel_raises(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        with pytest.raises(ParwaBaseError):
            update_channel_assignment(
                db, "comp_1", "inst_1", ["telepathy"],
            )

    def test_not_found_raises_404(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError):
            update_channel_assignment(
                db, "comp_1", "nope", ["email"],
            )


class TestUpdateCapacityConfig:
    def test_updates_config(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        inst = update_capacity_config(
            db, "comp_1", "inst_1",
            {"max_concurrent_tickets": 200, "priority_weight": 5},
        )
        cfg = json.loads(inst.capacity_config)
        assert cfg["max_concurrent_tickets"] == 200

    def test_non_dict_raises(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        with pytest.raises(ParwaBaseError):
            update_capacity_config(db, "comp_1", "inst_1", "not a dict")

    def test_not_found_raises_404(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError):
            update_capacity_config(
                db, "comp_1", "nope", {"max": 100},
            )


class TestIncrementActiveTickets:
    def test_increments(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, cap={"max_concurrent_tickets": 50})
        inst = increment_active_tickets(db, "comp_1", "inst_1")
        assert inst.active_tickets_count == 1
        assert inst.total_tickets_handled == 1

    def test_not_found_raises_404(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError) as exc:
            increment_active_tickets(db, "comp_1", "nope")
        assert exc.value.status_code == 404

    def test_inactive_raises_409(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, status="inactive")
        with pytest.raises(ParwaBaseError) as exc:
            increment_active_tickets(db, "comp_1", "inst_1")
        assert exc.value.error_code == "INSTANCE_NOT_ACTIVE"
        assert exc.value.status_code == 409

    def test_suspended_raises_409(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, status="suspended")
        with pytest.raises(ParwaBaseError):
            increment_active_tickets(db, "comp_1", "inst_1")

    def test_capacity_exceeded_raises_429(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, cap={"max_concurrent_tickets": 2})
        increment_active_tickets(db, "comp_1", "inst_1")
        increment_active_tickets(db, "comp_1", "inst_1")
        with pytest.raises(ParwaBaseError) as exc:
            increment_active_tickets(db, "comp_1", "inst_1")
        assert exc.value.error_code == "CAPACITY_EXCEEDED"
        assert exc.value.status_code == 429

    def test_uses_default_capacity_50(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, cap={})  # No max set
        for _ in range(50):
            increment_active_tickets(db, "comp_1", "inst_1")
        with pytest.raises(ParwaBaseError):
            increment_active_tickets(db, "comp_1", "inst_1")


class TestDecrementActiveTickets:
    def test_decrements(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        # Set active_tickets to 5 via raw SQL
        db.execute(__import__("sqlalchemy").text(
            "UPDATE variant_instances SET active_tickets_count = 5 "
            "WHERE id = 'inst_1'"
        ))
        db.commit()
        inst = decrement_active_tickets(db, "comp_1", "inst_1")
        assert inst.active_tickets_count == 4

    def test_never_goes_below_zero(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        # active_tickets_count is 0 by default
        inst = decrement_active_tickets(db, "comp_1", "inst_1")
        assert inst.active_tickets_count == 0

    def test_not_found_raises_404(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError):
            decrement_active_tickets(db, "comp_1", "nope")


class TestGetLeastLoadedInstance:
    def test_returns_lowest(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa")
        _make_instance(db, iid="i2", vtype="mini_parwa")
        db.execute(__import__("sqlalchemy").text(
            "UPDATE variant_instances SET active_tickets_count = 10 "
            "WHERE id = 'i1'"
        ))
        db.commit()
        inst = get_least_loaded_instance(db, "comp_1")
        assert inst.id == "i2"

    def test_filter_by_variant_type(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", vtype="mini_parwa")
        _make_instance(db, iid="i2", vtype="parwa")
        inst = get_least_loaded_instance(
            db, "comp_1", variant_type="parwa",
        )
        assert inst.id == "i2"

    def test_returns_none_if_no_active(self):
        db = SessionLocal()
        _make_company(db)
        inst = get_least_loaded_instance(db, "comp_1")
        assert inst is None


class TestGetInstanceForChannel:
    def test_returns_matching_instance(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, iid="i1", channels=["email", "chat"])
        inst = get_instance_for_channel(db, "comp_1", "email")
        assert inst is not None
        assert inst.id == "i1"

    def test_returns_none_for_no_channel(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        inst = get_instance_for_channel(db, "comp_1", "")
        assert inst is None

    def test_handles_malformed_json(self):
        db = SessionLocal()
        _make_company(db)
        inst_obj = _make_instance(db)
        inst_obj.channel_assignment = "not json"
        db.commit()
        inst = get_instance_for_channel(db, "comp_1", "email")
        assert inst is None

    def test_returns_none_if_no_match(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db, channels=["email"])
        inst = get_instance_for_channel(db, "comp_1", "voice")
        assert inst is None


# ══════════════════════════════════════════════════════════════════
# ENTITLEMENT MIDDLEWARE TESTS
# ══════════════════════════════════════════════════════════════════

class TestGetRequiredVariantType:
    def test_level1_feature_mini_parwa(self):
        # F-054 min_level=1
        vt = _get_required_variant_type("F-054")
        assert vt == "mini_parwa"

    def test_level2_feature_parwa(self):
        # F-143 min_level=2
        vt = _get_required_variant_type("F-143")
        assert vt == "parwa"

    def test_level3_feature_parwa_high(self):
        # F-150 min_level=3
        vt = _get_required_variant_type("F-150")
        assert vt == "parwa_high"

    def test_unknown_feature_returns_none(self):
        vt = _get_required_variant_type("F-999")
        assert vt is None


class TestBuildUpgradeSuggestion:
    def test_mini_to_parwa_for_level2(self):
        # F-143 min_level=2, user on mini_parwa
        sug = _build_upgrade_suggestion("F-143", "mini_parwa")
        assert sug is not None
        assert "PARWA" in sug
        assert "$2,499/mo" in sug

    def test_already_entitled_returns_none(self):
        # F-054 min_level=1, user on mini_parwa
        sug = _build_upgrade_suggestion("F-054", "mini_parwa")
        assert sug is None

    def test_unknown_feature_returns_none(self):
        sug = _build_upgrade_suggestion("F-999", "mini_parwa")
        assert sug is None

    def test_mini_to_high_for_level3(self):
        sug = _build_upgrade_suggestion("F-150", "mini_parwa")
        assert sug is not None
        assert "PARWA High" in sug


class TestCheckEntitlement:
    def test_enabled_feature_entitled(self):
        db = SessionLocal()
        _make_company(db)
        _init_matrix(db)
        result = check_entitlement(
            db, "comp_1", "F-054", "mini_parwa",
        )
        assert result.is_entitled is True
        assert result.reason == "enabled"

    def test_disabled_for_variant_not_entitled(self):
        db = SessionLocal()
        _make_company(db)
        _init_matrix(db)
        # F-143 min_level=2, mini_parwa is level 1
        result = check_entitlement(
            db, "comp_1", "F-143", "mini_parwa",
        )
        assert result.is_entitled is False
        assert result.reason == "disabled_for_variant"
        assert result.upgrade_suggestion is not None

    def test_unknown_feature_disabled_globally(self):
        db = SessionLocal()
        _make_company(db)
        result = check_entitlement(
            db, "comp_1", "F-999", "mini_parwa",
        )
        assert result.is_entitled is False
        assert result.reason == "disabled_globally"
        assert result.upgrade_suggestion is None

    def test_instance_override_enabled(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _init_matrix(db)
        # F-143 disabled for mini_parwa globally, enable for inst_1
        override = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            instance_id="inst_1", feature_id="F-143",
            feature_name="GST", is_enabled=True,
        )
        db.add(override)
        db.commit()
        result = check_entitlement(
            db, "comp_1", "F-143", "mini_parwa",
            instance_id="inst_1",
        )
        assert result.is_entitled is True
        assert result.reason == "enabled"

    def test_instance_override_disabled(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _init_matrix(db)
        # F-054 enabled for mini_parwa globally, disable for inst_1
        override = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            instance_id="inst_1", feature_id="F-054",
            feature_name="Smart Router", is_enabled=False,
        )
        db.add(override)
        db.commit()
        result = check_entitlement(
            db, "comp_1", "F-054", "mini_parwa",
            instance_id="inst_1",
        )
        assert result.is_entitled is False
        assert result.reason == "instance_override_disabled"

    def test_result_is_dataclass(self):
        db = SessionLocal()
        _make_company(db)
        _init_matrix(db)
        result = check_entitlement(
            db, "comp_1", "F-054", "mini_parwa",
        )
        assert isinstance(result, EntitlementResult)
        assert hasattr(result, "is_entitled")
        assert hasattr(result, "upgrade_suggestion")


class TestEnforceEntitlement:
    def test_passes_when_entitled(self):
        db = SessionLocal()
        _make_company(db)
        _init_matrix(db)
        # Should not raise
        enforce_entitlement(db, "comp_1", "F-054", "mini_parwa")

    def test_raises_403_when_not_entitled(self):
        db = SessionLocal()
        _make_company(db)
        _init_matrix(db)
        with pytest.raises(ParwaBaseError) as exc:
            enforce_entitlement(db, "comp_1", "F-143", "mini_parwa")
        assert exc.value.status_code == 403
        assert exc.value.error_code == "FEATURE_NOT_ENTITLED"

    def test_raises_403_instance_disabled(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _init_matrix(db)
        override = VariantAICapability(
            company_id="comp_1", variant_type="mini_parwa",
            instance_id="inst_1", feature_id="F-054",
            feature_name="Smart Router", is_enabled=False,
        )
        db.add(override)
        db.commit()
        with pytest.raises(ParwaBaseError) as exc:
            enforce_entitlement(
                db, "comp_1", "F-054", "mini_parwa",
                instance_id="inst_1",
            )
        assert exc.value.error_code == "INSTANCE_FEATURE_DISABLED"
        assert exc.value.status_code == 403


class TestGetUpgradeNudge:
    def test_upgrade_required(self):
        db = SessionLocal()
        _make_company(db)
        _init_matrix(db)
        nudge = get_upgrade_nudge(db, "comp_1", "F-143", "mini_parwa")
        assert nudge["upgrade_available"] is True
        assert nudge["required_plan"] is not None
        assert nudge["pricing"] is not None

    def test_already_entitled(self):
        db = SessionLocal()
        _make_company(db)
        _init_matrix(db)
        nudge = get_upgrade_nudge(db, "comp_1", "F-054", "mini_parwa")
        assert nudge["upgrade_available"] is False
        assert nudge["reason"] == "Feature available at current plan"

    def test_unknown_feature(self):
        db = SessionLocal()
        _make_company(db)
        nudge = get_upgrade_nudge(db, "comp_1", "F-999", "mini_parwa")
        assert nudge["upgrade_available"] is False
        assert nudge["reason"] == "Feature not found in registry"

    def test_has_required_fields(self):
        db = SessionLocal()
        _make_company(db)
        _init_matrix(db)
        nudge = get_upgrade_nudge(db, "comp_1", "F-150", "parwa")
        for key in ["feature_id", "feature_name", "current_plan",
                     "required_plan", "upgrade_suggestion"]:
            assert key in nudge


class TestBatchCheckEntitlements:
    def test_mixed_results(self):
        db = SessionLocal()
        _make_company(db)
        _init_matrix(db)
        result = batch_check_entitlements(
            db, "comp_1",
            ["F-054", "F-143", "F-999"],
            "mini_parwa",
        )
        assert result["summary"]["total"] == 3
        assert result["summary"]["entitled_count"] == 1
        assert result["summary"]["denied_count"] == 2
        assert "F-054" in result["entitled"]
        assert "F-143" in result["denied"]

    def test_empty_list(self):
        db = SessionLocal()
        _make_company(db)
        result = batch_check_entitlements(
            db, "comp_1", [], "mini_parwa",
        )
        assert result["summary"]["total"] == 0

    def test_non_list_raises(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError):
            batch_check_entitlements(
                db, "comp_1", "F-054", "mini_parwa",
            )


class TestCreateInstanceOverride:
    def test_creates_new_override(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _init_matrix(db)
        override = create_instance_override(
            db, "comp_1", "F-054", "mini_parwa",
            "inst_1", False,
        )
        assert override.is_enabled is False
        assert override.instance_id == "inst_1"

    def test_updates_existing_override(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _init_matrix(db)
        create_instance_override(
            db, "comp_1", "F-054", "mini_parwa",
            "inst_1", True,
        )
        override = create_instance_override(
            db, "comp_1", "F-054", "mini_parwa",
            "inst_1", False,
        )
        assert override.is_enabled is False

    def test_empty_instance_id_raises(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError):
            create_instance_override(
                db, "comp_1", "F-054", "mini_parwa", "", True,
            )

    def test_empty_feature_id_raises(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError):
            create_instance_override(
                db, "comp_1", "", "mini_parwa", "inst_1", True,
            )

    def test_with_config_json(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _init_matrix(db)
        override = create_instance_override(
            db, "comp_1", "F-054", "mini_parwa",
            "inst_1", True, {"custom": True},
        )
        assert json.loads(override.config_json) == {"custom": True}


class TestRemoveInstanceOverride:
    def test_removes_existing(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _init_matrix(db)
        create_instance_override(
            db, "comp_1", "F-054", "mini_parwa",
            "inst_1", True,
        )
        result = remove_instance_override(
            db, "comp_1", "F-054", "mini_parwa", "inst_1",
        )
        assert result is True
        # Verify gone
        cap = db.query(VariantAICapability).filter_by(
            company_id="comp_1", instance_id="inst_1",
            feature_id="F-054",
        ).first()
        assert cap is None

    def test_nonexistent_returns_false(self):
        db = SessionLocal()
        _make_company(db)
        result = remove_instance_override(
            db, "comp_1", "F-054", "mini_parwa", "inst_1",
        )
        assert result is False

    def test_empty_instance_id_raises(self):
        db = SessionLocal()
        _make_company(db)
        with pytest.raises(ParwaBaseError):
            remove_instance_override(
                db, "comp_1", "F-054", "mini_parwa", "",
            )


class TestGetEntitlementSummary:
    def test_returns_correct_counts(self):
        db = SessionLocal()
        _make_company(db)
        _init_matrix(db)
        summary = get_entitlement_summary(
            db, "comp_1", "mini_parwa",
        )
        assert summary["variant_type"] == "mini_parwa"
        assert summary["total_features"] == len(FEATURE_REGISTRY)
        assert summary["enabled_features"] > 0
        assert summary["disabled_features"] > 0

    def test_by_category_breakdown(self):
        db = SessionLocal()
        _make_company(db)
        _init_matrix(db)
        summary = get_entitlement_summary(
            db, "comp_1", "parwa",
        )
        assert "by_category" in summary
        assert "routing" in summary["by_category"]
        assert "technique" in summary["by_category"]

    def test_instance_specific(self):
        db = SessionLocal()
        _make_company(db)
        _make_instance(db)
        _init_matrix(db)
        create_instance_override(
            db, "comp_1", "F-054", "mini_parwa",
            "inst_1", True,
        )
        summary = get_entitlement_summary(
            db, "comp_1", "mini_parwa",
            instance_id="inst_1",
        )
        assert summary["instance_id"] == "inst_1"
        assert summary["total_features"] == 1
        assert summary["enabled_features"] == 1

    def test_sorted_feature_lists(self):
        db = SessionLocal()
        _make_company(db)
        _init_matrix(db)
        summary = get_entitlement_summary(
            db, "comp_1", "mini_parwa",
        )
        assert summary["enabled_feature_ids"] == sorted(
            summary["enabled_feature_ids"],
        )
