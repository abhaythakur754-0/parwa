"""
Variant Instance Architecture Service (SG-37).

Manages unlimited variant instances per tenant.
Each instance gets its own Celery queue namespace,
Redis state partition, and workload tracking.

BC-001: All queries filtered by company_id.
BC-004: Instance isolation.
BC-008: Graceful degradation.
"""

import json

from database.base import SessionLocal
from database.models.variant_engine import VariantInstance
from app.exceptions import ParwaBaseError
from app.logger import get_logger

logger = get_logger("variant_instance_service")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

VALID_VARIANT_TYPES = {"mini_parwa", "parwa", "high_parwa"}

VALID_STATUSES = {"active", "inactive", "warming", "suspended"}

VALID_CHANNELS = {
    "email",
    "chat",
    "sms",
    "voice",
    "slack",
    "webchat",
}

VARIANT_PRIORITY = {
    "high_parwa": 3,
    "parwa": 2,
    "mini_parwa": 1,
}


# ══════════════════════════════════════════════════════════════════
# VALIDATION HELPERS
# ══════════════════════════════════════════════════════════════════


def _validate_company_id(company_id: str) -> None:
    """BC-001: company_id is required."""
    if not company_id or not company_id.strip():
        raise ParwaBaseError(
            error_code="INVALID_COMPANY_ID",
            message="company_id is required and cannot be empty",
            status_code=400,
        )


def _validate_variant_type(variant_type: str) -> None:
    """Validate variant_type is a known type."""
    if variant_type not in VALID_VARIANT_TYPES:
        raise ParwaBaseError(
            error_code="INVALID_VARIANT_TYPE",
            message=(
                f"Invalid variant_type '{variant_type}'. "
                "Must be one of: "
                f"{', '.join(sorted(VALID_VARIANT_TYPES))}"
            ),
            status_code=400,
        )


def _validate_instance_name(name: str) -> None:
    """Validate instance name is not empty."""
    if not name or not name.strip():
        raise ParwaBaseError(
            error_code="INVALID_INSTANCE_NAME",
            message="instance_name is required and cannot be empty",
            status_code=400,
        )


def _validate_channels(channels: list[str]) -> None:
    """Validate channel list contains only known channels."""
    invalid = set(channels) - VALID_CHANNELS
    if invalid:
        raise ParwaBaseError(
            error_code="INVALID_CHANNEL",
            message=(
                "Invalid channels: "
                f"{', '.join(sorted(invalid))}. "
                f"Valid: {', '.join(sorted(VALID_CHANNELS))}"
            ),
            status_code=400,
        )


def _validate_json_serializable(value, field_name: str) -> None:
    """BC-008: Verify a value is JSON-serializable before DB write.

    Tests round-trip: json.loads(json.dumps(value)).
    If it fails, raises a clear validation error instead of
    crashing at commit time.
    """
    try:
        json.dumps(value)
    except (TypeError, ValueError, OverflowError) as exc:
        logger.warning(
            "json_serialization_failed",
            field=field_name,
            error=str(exc),
        )
        raise ParwaBaseError(
            error_code="INVALID_JSON",
            message=(
                f"'{field_name}' contains a value that cannot be "
                f"serialized to JSON: {exc}"
            ),
            status_code=400,
        )


def _validate_status(status: str) -> None:
    """Validate status value."""
    if status not in VALID_STATUSES:
        raise ParwaBaseError(
            error_code="INVALID_STATUS",
            message=(
                f"Invalid status '{status}'. "
                "Must be one of: "
                f"{', '.join(sorted(VALID_STATUSES))}"
            ),
            status_code=400,
        )


def _generate_celery_namespace(
    company_id: str,
    variant_type: str,
    count: int,
) -> str:
    """Generate Celery queue namespace."""
    safe_type = variant_type.replace("_", "")
    return f"tenant_{company_id}_{safe_type}_{count}"


def _generate_redis_partition_key(
    company_id: str,
    variant_type: str,
    count: int,
) -> str:
    """Generate Redis state partition key."""
    short_type = (
        variant_type.replace("mini_parwa", "min")
        .replace("high_parwa", "high")
        .replace("parwa", "par")
    )
    return f"parwa:{company_id}:inst:{short_type}_{count}"


def _get_instance_count(
    db: SessionLocal,
    company_id: str,
    variant_type: str,
) -> int:
    """Count existing instances of this type for tenant."""
    return (
        db.query(VariantInstance)
        .filter_by(
            company_id=company_id,
            variant_type=variant_type,
        )
        .count()
    )


# ══════════════════════════════════════════════════════════════════
# SERVICE FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def register_instance(
    db: SessionLocal,
    company_id: str,
    instance_name: str,
    variant_type: str,
    channel_assignment: list[str] | None = None,
    capacity_config: dict | None = None,
) -> VariantInstance:
    """
    Register a new variant instance.

    Auto-generates celery_queue_namespace and
    redis_partition_key based on count of existing
    instances of same type for this tenant.
    """
    _validate_company_id(company_id)
    _validate_instance_name(instance_name)
    _validate_variant_type(variant_type)

    if channel_assignment is not None:
        _validate_channels(channel_assignment)

    # Gap 2: Validate JSON serializability before DB write (BC-008)
    safe_channels = channel_assignment if channel_assignment else []
    safe_config = capacity_config if capacity_config else {}
    _validate_json_serializable(safe_channels, "channel_assignment")
    _validate_json_serializable(safe_config, "capacity_config")

    count = _get_instance_count(db, company_id, variant_type)
    next_num = count + 1

    celery_ns = _generate_celery_namespace(
        company_id,
        variant_type,
        next_num,
    )
    redis_key = _generate_redis_partition_key(
        company_id,
        variant_type,
        next_num,
    )

    channels_json = json.dumps(safe_channels)
    capacity_json = json.dumps(safe_config)

    instance = VariantInstance(
        company_id=company_id,
        instance_name=instance_name.strip(),
        variant_type=variant_type,
        status="active",
        channel_assignment=channels_json,
        capacity_config=capacity_json,
        celery_queue_namespace=celery_ns,
        redis_partition_key=redis_key,
        active_tickets_count=0,
        total_tickets_handled=0,
    )

    db.add(instance)
    db.commit()
    db.refresh(instance)
    return instance


def deactivate_instance(
    db: SessionLocal,
    company_id: str,
    instance_id: str,
) -> VariantInstance:
    """Set instance status to 'inactive'."""
    _validate_company_id(company_id)

    inst = (
        db.query(VariantInstance)
        .filter_by(
            company_id=company_id,
            id=instance_id,
        )
        .first()
    )

    if inst is None:
        raise ParwaBaseError(
            error_code="INSTANCE_NOT_FOUND",
            message=(
                f"Instance '{instance_id}' not found " f"for company '{company_id}'"
            ),
            status_code=404,
        )

    inst.status = "inactive"
    db.commit()
    db.refresh(inst)
    return inst


def activate_instance(
    db: SessionLocal,
    company_id: str,
    instance_id: str,
) -> VariantInstance:
    """Set instance status to 'active'."""
    _validate_company_id(company_id)

    inst = (
        db.query(VariantInstance)
        .filter_by(
            company_id=company_id,
            id=instance_id,
        )
        .first()
    )

    if inst is None:
        raise ParwaBaseError(
            error_code="INSTANCE_NOT_FOUND",
            message=(
                f"Instance '{instance_id}' not found " f"for company '{company_id}'"
            ),
            status_code=404,
        )

    inst.status = "active"
    db.commit()
    db.refresh(inst)
    return inst


def suspend_instance(
    db: SessionLocal,
    company_id: str,
    instance_id: str,
    reason: str | None = None,
) -> VariantInstance:
    """Set instance status to 'suspended'."""
    _validate_company_id(company_id)

    inst = (
        db.query(VariantInstance)
        .filter_by(
            company_id=company_id,
            id=instance_id,
        )
        .first()
    )

    if inst is None:
        raise ParwaBaseError(
            error_code="INSTANCE_NOT_FOUND",
            message=(
                f"Instance '{instance_id}' not found " f"for company '{company_id}'"
            ),
            status_code=404,
        )

    inst.status = "suspended"
    db.commit()
    db.refresh(inst)
    return inst


def list_instances(
    db: SessionLocal,
    company_id: str,
    variant_type: str | None = None,
    status: str | None = None,
) -> list[VariantInstance]:
    """List instances with optional filters."""
    _validate_company_id(company_id)

    query = db.query(VariantInstance).filter_by(
        company_id=company_id,
    )

    if variant_type is not None:
        _validate_variant_type(variant_type)
        query = query.filter_by(variant_type=variant_type)

    if status is not None:
        _validate_status(status)
        query = query.filter_by(status=status)

    return query.order_by(
        VariantInstance.created_at,
    ).all()


def get_instance(
    db: SessionLocal,
    company_id: str,
    instance_id: str,
) -> VariantInstance | None:
    """Get single instance by ID."""
    _validate_company_id(company_id)

    return (
        db.query(VariantInstance)
        .filter_by(
            company_id=company_id,
            id=instance_id,
        )
        .first()
    )


def get_highest_active_variant(
    db: SessionLocal,
    company_id: str,
) -> str | None:
    """
    Returns highest variant_type with at least one
    active instance.

    Priority: high_parwa > parwa > mini_parwa.
    Returns None if no active instances.
    """
    _validate_company_id(company_id)

    active = (
        db.query(
            VariantInstance.variant_type,
        )
        .filter_by(
            company_id=company_id,
            status="active",
        )
        .distinct()
        .all()
    )

    if not active:
        return None

    active_types = {row[0] for row in active}
    best = None
    best_priority = -1

    for vt in active_types:
        pri = VARIANT_PRIORITY.get(vt, 0)
        if pri > best_priority:
            best_priority = pri
            best = vt

    return best


def get_total_capacity(
    db: SessionLocal,
    company_id: str,
) -> dict:
    """
    Returns aggregate capacity across all active
    instances.
    """
    _validate_company_id(company_id)

    instances = (
        db.query(VariantInstance)
        .filter_by(
            company_id=company_id,
            status="active",
        )
        .all()
    )

    total_max = 0
    total_active = 0
    by_type: dict = {}

    for inst in instances:
        try:
            cap = json.loads(inst.capacity_config)
        except (json.JSONDecodeError, TypeError):
            cap = {}
        max_conc = cap.get(
            "max_concurrent_tickets",
            50,
        )

        total_max += max_conc
        total_active += inst.active_tickets_count

        if inst.variant_type not in by_type:
            by_type[inst.variant_type] = {
                "instances": 0,
                "max_concurrent": 0,
                "active_tickets": 0,
            }
        by_type[inst.variant_type]["instances"] += 1
        by_type[inst.variant_type]["max_concurrent"] += max_conc
        by_type[inst.variant_type]["active_tickets"] += inst.active_tickets_count

    return {
        "total_active_instances": len(instances),
        "total_max_concurrent": total_max,
        "total_active_tickets": total_active,
        "available_capacity": max(0, total_max - total_active),
        "by_variant_type": by_type,
    }


def update_channel_assignment(
    db: SessionLocal,
    company_id: str,
    instance_id: str,
    channels: list[str] | str,
) -> VariantInstance:
    """Update which channels this instance handles.

    Gap 5: Accepts both list[str] and JSON-encoded string.
    Wraps JSON parsing in try/except (BC-008) to avoid
    crashes on malformed input.
    """
    _validate_company_id(company_id)

    # Gap 5: If channels is a string, parse it safely
    if isinstance(channels, str):
        try:
            parsed = json.loads(channels)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning(
                "channel_assignment_json_parse_failed",
                instance_id=instance_id,
                error=str(exc),
            )
            raise ParwaBaseError(
                error_code="INVALID_JSON",
                message=(
                    "channel_assignment must be a valid JSON "
                    f"array or a list of strings. Parse error: {exc}"
                ),
                status_code=400,
            )
        if not isinstance(parsed, list):
            raise ParwaBaseError(
                error_code="INVALID_CHANNEL_FORMAT",
                message=(
                    "channel_assignment must resolve to a list, "
                    f"got {type(parsed).__name__}"
                ),
                status_code=400,
            )
        channels = parsed

    _validate_channels(channels)

    # Gap 2: Validate JSON serializability (BC-008)
    _validate_json_serializable(channels, "channel_assignment")

    inst = (
        db.query(VariantInstance)
        .filter_by(
            company_id=company_id,
            id=instance_id,
        )
        .first()
    )

    if inst is None:
        raise ParwaBaseError(
            error_code="INSTANCE_NOT_FOUND",
            message=(
                f"Instance '{instance_id}' not found " f"for company '{company_id}'"
            ),
            status_code=404,
        )

    inst.channel_assignment = json.dumps(channels)
    db.commit()
    db.refresh(inst)
    return inst


def update_capacity_config(
    db: SessionLocal,
    company_id: str,
    instance_id: str,
    config: dict,
) -> VariantInstance:
    """Update capacity configuration.

    Gap 2: Validates JSON serializability before writing (BC-008).
    """
    _validate_company_id(company_id)

    if not isinstance(config, dict):
        raise ParwaBaseError(
            error_code="INVALID_CONFIG",
            message="capacity_config must be a dict",
            status_code=400,
        )

    # Gap 2: Validate JSON serializability before DB write
    _validate_json_serializable(config, "capacity_config")

    inst = (
        db.query(VariantInstance)
        .filter_by(
            company_id=company_id,
            id=instance_id,
        )
        .first()
    )

    if inst is None:
        raise ParwaBaseError(
            error_code="INSTANCE_NOT_FOUND",
            message=(
                f"Instance '{instance_id}' not found " f"for company '{company_id}'"
            ),
            status_code=404,
        )

    inst.capacity_config = json.dumps(config)
    db.commit()
    db.refresh(inst)
    return inst


def increment_active_tickets(
    db: SessionLocal,
    company_id: str,
    instance_id: str,
) -> VariantInstance:
    """Atomically increment active_tickets_count.

    Uses SQL UPDATE for atomicity to prevent race conditions
    where concurrent requests cause lost increments.
    Also checks capacity limit before incrementing.

    Gap 8: Atomic capacity guard via WHERE clause prevents
    overflow even under concurrent load.
    """
    _validate_company_id(company_id)

    inst = (
        db.query(VariantInstance)
        .filter_by(
            company_id=company_id,
            id=instance_id,
        )
        .first()
    )

    if inst is None:
        raise ParwaBaseError(
            error_code="INSTANCE_NOT_FOUND",
            message=(
                f"Instance '{instance_id}' not found " f"for company '{company_id}'"
            ),
            status_code=404,
        )

    if inst.status != "active":
        raise ParwaBaseError(
            error_code="INSTANCE_NOT_ACTIVE",
            message=(
                f"Instance '{instance_id}' is not active "
                f"(current status: '{inst.status}')"
            ),
            status_code=409,
        )

    # Check capacity limit before incrementing
    try:
        cap = json.loads(inst.capacity_config)
    except (json.JSONDecodeError, TypeError):
        cap = {}
    max_conc = cap.get("max_concurrent_tickets", 50)

    if inst.active_tickets_count >= max_conc:
        raise ParwaBaseError(
            error_code="CAPACITY_EXCEEDED",
            message=(
                f"Instance '{instance_id}' has reached " f"max capacity ({max_conc})"
            ),
            status_code=429,
        )

    # Gap 8: Atomic SQL UPDATE with capacity guard.
    # The WHERE clause ensures that even under concurrent load,
    # we never exceed max capacity at the DB level.
    import sqlalchemy as sa
    from datetime import datetime, timezone

    result = db.execute(
        sa.text(
            "UPDATE variant_instances SET "
            "active_tickets_count = active_tickets_count + 1, "
            "total_tickets_handled = total_tickets_handled + 1, "
            "updated_at = :now_ts "
            "WHERE id = :inst_id "
            "AND company_id = :comp_id "
            "AND active_tickets_count < :max_cap"
        ),
        {
            "inst_id": instance_id,
            "comp_id": company_id,
            "max_cap": max_conc,
            "now_ts": datetime.now(timezone.utc),
        },
    )
    db.commit()
    db.refresh(inst)

    # If the atomic UPDATE matched zero rows, capacity was
    # exceeded between our read-check and the write.
    if result.rowcount == 0:
        logger.warning(
            "capacity_overflow_race_condition",
            instance_id=instance_id,
            company_id=company_id,
            max_capacity=max_conc,
        )
        raise ParwaBaseError(
            error_code="CAPACITY_EXCEEDED",
            message=(
                f"Instance '{instance_id}' reached max capacity "
                f"({max_conc}) concurrently. Please retry."
            ),
            status_code=429,
        )

    return inst


def decrement_active_tickets(
    db: SessionLocal,
    company_id: str,
    instance_id: str,
) -> VariantInstance:
    """
    Atomically decrement active_tickets_count.
    Never goes below 0 — uses SQL GREATEST for safety.
    """
    _validate_company_id(company_id)

    inst = (
        db.query(VariantInstance)
        .filter_by(
            company_id=company_id,
            id=instance_id,
        )
        .first()
    )

    if inst is None:
        raise ParwaBaseError(
            error_code="INSTANCE_NOT_FOUND",
            message=(
                f"Instance '{instance_id}' not found " f"for company '{company_id}'"
            ),
            status_code=404,
        )

    # Gap 1: Atomic SQL UPDATE using GREATEST to prevent
    # counter underflow (DB CheckConstraint is the safety net)
    import sqlalchemy as sa
    from datetime import datetime, timezone

    db.execute(
        sa.text(
            "UPDATE variant_instances SET "
            "active_tickets_count = GREATEST("
            "active_tickets_count - 1, 0), "
            "updated_at = :now_ts "
            "WHERE id = :inst_id AND company_id = :comp_id"
        ),
        {
            "inst_id": instance_id,
            "comp_id": company_id,
            "now_ts": datetime.now(timezone.utc),
        },
    )
    db.commit()
    db.refresh(inst)
    return inst


def set_instance_status(
    db: SessionLocal,
    company_id: str,
    instance_id: str,
    status: str,
) -> VariantInstance:
    """Gap 4: Generic status setter with validation.

    Validates that status is one of VALID_STATUSES before
    setting it. Rejects invalid values with a clear error.
    """
    _validate_company_id(company_id)
    _validate_status(status)

    inst = (
        db.query(VariantInstance)
        .filter_by(
            company_id=company_id,
            id=instance_id,
        )
        .first()
    )

    if inst is None:
        raise ParwaBaseError(
            error_code="INSTANCE_NOT_FOUND",
            message=(
                f"Instance '{instance_id}' not found " f"for company '{company_id}'"
            ),
            status_code=404,
        )

    inst.status = status
    db.commit()
    db.refresh(inst)
    return inst


def get_least_loaded_instance(
    db: SessionLocal,
    company_id: str,
    variant_type: str | None = None,
) -> VariantInstance | None:
    """
    Find instance with lowest active_tickets_count.
    For workload distribution.
    """
    _validate_company_id(company_id)

    query = db.query(VariantInstance).filter_by(
        company_id=company_id,
        status="active",
    )

    if variant_type is not None:
        _validate_variant_type(variant_type)
        query = query.filter_by(variant_type=variant_type)

    return query.order_by(
        VariantInstance.active_tickets_count,
    ).first()


def get_instance_for_channel(
    db: SessionLocal,
    company_id: str,
    channel: str,
) -> VariantInstance | None:
    """
    Find active instance assigned to a specific channel.
    """
    _validate_company_id(company_id)

    if not channel:
        return None

    instances = (
        db.query(VariantInstance)
        .filter_by(
            company_id=company_id,
            status="active",
        )
        .all()
    )

    for inst in instances:
        try:
            channels = json.loads(inst.channel_assignment)
            if channel in channels:
                return inst
        except (json.JSONDecodeError, TypeError):
            continue

    return None
