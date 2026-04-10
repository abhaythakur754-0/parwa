"""
Variant Orchestration Layer (SG-38): Celery-based Workload Distribution.

Central orchestrator that distributes tickets across variant instances.
NOT CrewAI-style agent collaboration — this is workload routing via
Celery + Redis.

Components:
  1. Ticket Router — incoming ticket -> instance assignment
  2. Capacity Tracker — real-time load per instance (Redis + DB)
  3. Distribution Strategy Engine — pluggable strategies
  4. Rebalancer — migrate queued tickets between instances
  5. Cross-variant Escalation — escalate to higher variant instance
  6. Billing Per-Instance — track which instance handled which ticket

BC-001: All queries filtered by company_id.
BC-004: Background Jobs (Celery patterns).
BC-007: AI Model Interaction (via strategy engine).
BC-008: Graceful degradation.
"""

import json
import logging
from datetime import datetime
from typing import Any, Callable, Optional

import sqlalchemy as sa

from database.base import SessionLocal
from database.models.variant_engine import (
    VariantInstance,
    VariantWorkloadDistribution,
)
from app.exceptions import ParwaBaseError

logger = logging.getLogger("parwa.orchestration")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

VARIANT_PRIORITY = {
    "mini_parwa": 1,
    "parwa": 2,
    "parwa_high": 3,
}

VALID_STRATEGIES = {
    "round_robin",
    "least_loaded",
    "channel_pinned",
    "variant_priority",
}

VALID_DISTRIBUTION_STATUSES = {
    "assigned",
    "in_progress",
    "completed",
    "escalated",
    "rebalanced",
}

DEFAULT_MAX_CONCURRENT = 50

REBALANCE_THRESHOLD_PCT = 80


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


def _validate_strategy(strategy: str) -> None:
    """Validate distribution strategy name."""
    if strategy not in VALID_STRATEGIES:
        raise ParwaBaseError(
            error_code="INVALID_STRATEGY",
            message=(
                f"Invalid strategy '{strategy}'. "
                f"Must be one of: "
                f"{', '.join(sorted(VALID_STRATEGIES))}"
            ),
            status_code=400,
        )


def _parse_capacity(capacity_config: str) -> dict:
    """Parse capacity_config JSON, return dict with defaults."""
    try:
        cap = json.loads(capacity_config)
        if not isinstance(cap, dict):
            cap = {}
    except (json.JSONDecodeError, TypeError):
        cap = {}
    cap.setdefault("max_concurrent_tickets", DEFAULT_MAX_CONCURRENT)
    return cap


# ══════════════════════════════════════════════════════════════════
# ROUND-ROBIN STATE (in-memory for single-process, Redis for prod)
# ══════════════════════════════════════════════════════════════════

_round_robin_counters: dict[str, int] = {}


def _get_rr_index(company_id: str, total: int) -> int:
    """Get next round-robin index for a company."""
    key = company_id
    current = _round_robin_counters.get(key, 0)
    idx = current % max(total, 1)
    _round_robin_counters[key] = current + 1
    return idx


# ══════════════════════════════════════════════════════════════════
# DISTRIBUTION STRATEGIES
# ══════════════════════════════════════════════════════════════════

class RoundRobinStrategy:
    """Round-robin: cycle through instances sequentially."""

    def select(
        self,
        instances: list[VariantInstance],
        context: dict,
    ) -> VariantInstance | None:
        if not instances:
            return None
        company_id = context.get("company_id", "")
        idx = _get_rr_index(company_id, len(instances))
        return instances[idx]


class LeastLoadedStrategy:
    """Pick instance with lowest active_tickets_count."""

    def select(
        self,
        instances: list[VariantInstance],
        context: dict,
    ) -> VariantInstance | None:
        if not instances:
            return None
        # Sort by active_tickets_count, then by total_tickets_handled
        sorted_instances = sorted(
            instances,
            key=lambda i: (
                i.active_tickets_count,
                i.total_tickets_handled,
            ),
        )
        # Check capacity constraint
        for inst in sorted_instances:
            cap = _parse_capacity(inst.capacity_config)
            max_conc = cap.get("max_concurrent_tickets", DEFAULT_MAX_CONCURRENT)
            if inst.active_tickets_count < max_conc:
                return inst
        # All at capacity — return least loaded anyway (graceful)
        return sorted_instances[0]


class ChannelPinnedStrategy:
    """Route to the instance assigned to the ticket's channel."""

    def select(
        self,
        instances: list[VariantInstance],
        context: dict,
    ) -> VariantInstance | None:
        if not instances:
            return None
        channel = context.get("channel")
        if not channel:
            # Fall back to least-loaded if no channel
            return LeastLoadedStrategy().select(instances, context)

        for inst in instances:
            try:
                channels = json.loads(inst.channel_assignment)
                if channel in channels:
                    # Check capacity
                    cap = _parse_capacity(inst.capacity_config)
                    max_conc = cap.get(
                        "max_concurrent_tickets",
                        DEFAULT_MAX_CONCURRENT,
                    )
                    if inst.active_tickets_count < max_conc:
                        return inst
            except (json.JSONDecodeError, TypeError):
                continue

        # No instance pinned to this channel — fall back
        return LeastLoadedStrategy().select(instances, context)


class VariantPriorityStrategy:
    """Prefer higher variant instances, then least-loaded within tier."""

    def select(
        self,
        instances: list[VariantInstance],
        context: dict,
    ) -> VariantInstance | None:
        if not instances:
            return None
        variant_type = context.get("variant_type")

        # If specific variant_type requested, filter to that
        if variant_type:
            filtered = [
                i for i in instances
                if i.variant_type == variant_type
            ]
            if filtered:
                return LeastLoadedStrategy().select(
                    filtered, context,
                )
            # Requested type not available — fall through

        # Sort by variant priority (highest first), then least loaded
        sorted_instances = sorted(
            instances,
            key=lambda i: (
                -VARIANT_PRIORITY.get(i.variant_type, 0),
                i.active_tickets_count,
            ),
        )
        return sorted_instances[0]


DISTRIBUTION_STRATEGIES: dict[str, Any] = {
    "round_robin": RoundRobinStrategy,
    "least_loaded": LeastLoadedStrategy,
    "channel_pinned": ChannelPinnedStrategy,
    "variant_priority": VariantPriorityStrategy,
}


# ══════════════════════════════════════════════════════════════════
# MAIN SERVICE FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def select_instance(
    db: SessionLocal,
    company_id: str,
    strategy: str = "least_loaded",
    channel: str | None = None,
    variant_type: str | None = None,
) -> VariantInstance | None:
    """
    Pick the best variant instance for a new ticket.

    Strategy determines how instances are ranked:
      - round_robin: sequential cycling
      - least_loaded: lowest active_tickets_count
      - channel_pinned: instance assigned to channel
      - variant_priority: highest variant type first

    Only considers active instances.
    Returns None if no active instances exist.
    """
    _validate_company_id(company_id)
    _validate_strategy(strategy)

    instances = db.query(VariantInstance).filter_by(
        company_id=company_id,
        status="active",
    ).all()

    if not instances:
        return None

    strategy_cls = DISTRIBUTION_STRATEGIES.get(strategy)
    if strategy_cls is None:
        raise ParwaBaseError(
            error_code="STRATEGY_NOT_FOUND",
            message=f"Strategy '{strategy}' not registered",
            status_code=500,
        )

    selector = strategy_cls()
    context = {
        "company_id": company_id,
        "channel": channel,
        "variant_type": variant_type,
    }
    return selector.select(instances, context)


def route_ticket(
    db: SessionLocal,
    company_id: str,
    ticket_id: str,
    channel: str | None = None,
    strategy: str = "least_loaded",
    variant_type: str | None = None,
) -> VariantWorkloadDistribution:
    """
    Main routing function: assign a ticket to the best instance.

    Steps:
    1. Select instance via strategy
    2. Create VariantWorkloadDistribution record
    3. Increment instance active_tickets_count

    Raises if no instance available or company_id invalid.
    """
    _validate_company_id(company_id)
    _validate_strategy(strategy)

    if not ticket_id or not ticket_id.strip():
        raise ParwaBaseError(
            error_code="INVALID_TICKET_ID",
            message="ticket_id is required and cannot be empty",
            status_code=400,
        )

    instance = select_instance(
        db, company_id, strategy, channel, variant_type,
    )

    if instance is None:
        raise ParwaBaseError(
            error_code="NO_AVAILABLE_INSTANCE",
            message=(
                f"No active instances available for "
                f"company '{company_id}'"
            ),
            status_code=503,
        )

    # Check capacity before routing (GAP 3 fix)
    cap = _parse_capacity(instance.capacity_config)
    max_conc = cap.get("max_concurrent_tickets", DEFAULT_MAX_CONCURRENT)
    if instance.active_tickets_count >= max_conc:
        raise ParwaBaseError(
            error_code="INSTANCE_AT_CAPACITY",
            message=(
                f"Selected instance '{instance.id}' has reached "
                f"max capacity ({max_conc})"
            ),
            status_code=503,
        )

    # Create distribution record
    distribution = VariantWorkloadDistribution(
        company_id=company_id,
        instance_id=instance.id,
        ticket_id=ticket_id.strip(),
        distribution_strategy=strategy,
        assigned_at=datetime.utcnow(),
        status="assigned",
    )
    db.add(distribution)

    # Atomic SQL UPDATE for counters (GAP 1 fix)
    db.execute(
        sa.text(
            "UPDATE variant_instances SET "
            "active_tickets_count = active_tickets_count + 1, "
            "total_tickets_handled = total_tickets_handled + 1, "
            "last_activity_at = :now_ts, "
            "updated_at = :now_ts "
            "WHERE id = :inst_id AND company_id = :comp_id"
        ),
        {
            "inst_id": instance.id,
            "comp_id": company_id,
            "now_ts": datetime.utcnow(),
        },
    )
    db.commit()
    db.refresh(distribution)
    return distribution


def get_instance_load(
    db: SessionLocal,
    company_id: str,
    instance_id: str,
) -> dict:
    """
    Get current load for a specific instance.

    Returns dict with:
      - instance_id, variant_type, status
      - active_tickets_count, total_tickets_handled
      - max_concurrent_tickets, available_capacity
      - utilization_pct
    """
    _validate_company_id(company_id)

    inst = db.query(VariantInstance).filter_by(
        company_id=company_id,
        id=instance_id,
    ).first()

    if inst is None:
        raise ParwaBaseError(
            error_code="INSTANCE_NOT_FOUND",
            message=(
                f"Instance '{instance_id}' not found for "
                f"company '{company_id}'"
            ),
            status_code=404,
        )

    cap = _parse_capacity(inst.capacity_config)
    max_conc = cap.get("max_concurrent_tickets", DEFAULT_MAX_CONCURRENT)
    available = max(0, max_conc - inst.active_tickets_count)
    utilization = round(
        (inst.active_tickets_count / max(max_conc, 1)) * 100, 2,
    )

    return {
        "instance_id": inst.id,
        "instance_name": inst.instance_name,
        "variant_type": inst.variant_type,
        "status": inst.status,
        "active_tickets_count": inst.active_tickets_count,
        "total_tickets_handled": inst.total_tickets_handled,
        "max_concurrent_tickets": max_conc,
        "available_capacity": available,
        "utilization_pct": utilization,
        "last_activity_at": (
            inst.last_activity_at.isoformat()
            if inst.last_activity_at else None
        ),
    }


def get_all_instance_loads(
    db: SessionLocal,
    company_id: str,
) -> list[dict]:
    """Get current load for all instances of a company."""
    _validate_company_id(company_id)

    instances = db.query(VariantInstance).filter_by(
        company_id=company_id,
    ).order_by(VariantInstance.variant_type).all()

    loads = []
    for inst in instances:
        try:
            loads.append(
                get_instance_load(
                    db, company_id, inst.id,
                ),
            )
        except ParwaBaseError:
            continue
    return loads


def rebalance_workload(
    db: SessionLocal,
    company_id: str,
) -> dict:
    """
    Rebalance tickets across instances.

    Checks if any instance is overloaded (>threshold% capacity).
    Migrates completed/rebalanced tickets to free up capacity.
    Marks overloaded instances for rebalancing.

    Returns summary dict with rebalanced instances and ticket count.
    """
    _validate_company_id(company_id)

    active_instances = db.query(VariantInstance).filter_by(
        company_id=company_id,
        status="active",
    ).all()

    if not active_instances:
        return {
            "rebalanced_instances": 0,
            "migrated_tickets": 0,
            "details": [],
        }

    overloaded = []
    underloaded = []

    for inst in active_instances:
        cap = _parse_capacity(inst.capacity_config)
        max_conc = cap.get(
            "max_concurrent_tickets", DEFAULT_MAX_CONCURRENT,
        )
        util_pct = (
            inst.active_tickets_count / max(max_conc, 1)
        ) * 100

        if util_pct >= REBALANCE_THRESHOLD_PCT:
            overloaded.append(inst)
        elif util_pct < (REBALANCE_THRESHOLD_PCT / 2):
            underloaded.append(inst)

    if not overloaded or not underloaded:
        return {
            "rebalanced_instances": 0,
            "migrated_tickets": 0,
            "details": [],
        }

    migrated = 0
    details = []

    # For each overloaded instance, find tickets that can be
    # moved to underloaded instances
    for over_inst in overloaded:
        # Find assigned/in_progress distributions on
        # this overloaded instance
        dists = db.query(VariantWorkloadDistribution).filter_by(
            company_id=company_id,
            instance_id=over_inst.id,
            status="assigned",
        ).order_by(
            VariantWorkloadDistribution.assigned_at,
        ).limit(5).all()

        for under_inst in underloaded:
            if not dists:
                break

            cap = _parse_capacity(under_inst.capacity_config)
            max_conc = cap.get(
                "max_concurrent_tickets", DEFAULT_MAX_CONCURRENT,
            )
            available = max_conc - under_inst.active_tickets_count

            if available <= 0:
                continue

            # Migrate up to available capacity
            to_migrate = min(available, len(dists))
            for i in range(to_migrate):
                dist = dists.pop(0)

                # Create new distribution on underloaded
                new_dist = VariantWorkloadDistribution(
                    company_id=company_id,
                    instance_id=under_inst.id,
                    ticket_id=dist.ticket_id,
                    distribution_strategy="rebalanced",
                    assigned_at=dist.assigned_at,
                    status="rebalanced",
                    rebalance_from_instance_id=over_inst.id,
                )
                db.add(new_dist)

                # Mark original as rebalanced
                dist.status = "rebalanced"
                dist.escalation_target_instance_id = (
                    under_inst.id
                )

                # Atomic SQL: decrement overloaded, increment underloaded
                # (GAP 1 fix — non-atomic counters)
                # Note: total_tickets_handled stays on overloaded instance
                # since that instance originally handled the ticket (GAP 6)
                db.execute(
                    sa.text(
                        "UPDATE variant_instances SET "
                        "active_tickets_count = CASE "
                        "WHEN active_tickets_count > 0 "
                        "THEN active_tickets_count - 1 ELSE 0 END, "
                        "updated_at = :now_ts "
                        "WHERE id = :inst_id"
                    ),
                    {"inst_id": over_inst.id, "now_ts": datetime.utcnow()},
                )
                db.execute(
                    sa.text(
                        "UPDATE variant_instances SET "
                        "active_tickets_count = active_tickets_count + 1, "
                        "total_tickets_handled = total_tickets_handled + 1, "
                        "updated_at = :now_ts "
                        "WHERE id = :inst_id"
                    ),
                    {"inst_id": under_inst.id, "now_ts": datetime.utcnow()},
                )
                migrated += 1

        if over_inst.active_tickets_count > 0:
            details.append({
                "overloaded_instance_id": over_inst.id,
                "overloaded_type": over_inst.variant_type,
                "remaining_active": (
                    over_inst.active_tickets_count
                ),
            })

    db.commit()

    return {
        "rebalanced_instances": len(overloaded),
        "migrated_tickets": migrated,
        "details": details,
    }


def escalate_ticket(
    db: SessionLocal,
    company_id: str,
    ticket_id: str,
    reason: str = "capability_exceeded",
) -> VariantWorkloadDistribution:
    """
    Escalate a ticket to a higher-variant instance.

    Finds the current active distribution for this ticket,
    determines the current instance's variant type, finds
    the least-loaded instance of a higher variant type,
    and creates a new distribution record.

    Returns the new distribution record.
    """
    _validate_company_id(company_id)

    if not ticket_id or not ticket_id.strip():
        raise ParwaBaseError(
            error_code="INVALID_TICKET_ID",
            message="ticket_id is required and cannot be empty",
            status_code=400,
        )

    # Find current active distribution for this ticket
    current = db.query(VariantWorkloadDistribution).filter_by(
        company_id=company_id,
        ticket_id=ticket_id.strip(),
    ).filter(
        VariantWorkloadDistribution.status.in_([
            "assigned", "in_progress",
        ]),
    ).order_by(
        VariantWorkloadDistribution.assigned_at.desc(),
    ).first()

    if current is None:
        raise ParwaBaseError(
            error_code="NO_ACTIVE_DISTRIBUTION",
            message=(
                f"No active distribution found for "
                f"ticket '{ticket_id}'"
            ),
            status_code=404,
        )

    # Find current instance and its variant type
    current_inst = db.query(VariantInstance).filter_by(
        company_id=company_id,
        id=current.instance_id,
    ).first()

    if current_inst is None:
        raise ParwaBaseError(
            error_code="INSTANCE_NOT_FOUND",
            message=(
                f"Current instance '{current.instance_id}' "
                f"not found"
            ),
            status_code=404,
        )

    current_priority = VARIANT_PRIORITY.get(
        current_inst.variant_type, 0,
    )

    # Find least-loaded instance with higher priority
    higher_instances = db.query(VariantInstance).filter_by(
        company_id=company_id,
        status="active",
    ).all()

    candidates = []
    for inst in higher_instances:
        pri = VARIANT_PRIORITY.get(inst.variant_type, 0)
        if pri > current_priority:
            candidates.append(inst)

    if not candidates:
        raise ParwaBaseError(
            error_code="NO_HIGHER_INSTANCE",
            message=(
                f"No higher-variant instance available for "
                f"escalation from '{current_inst.variant_type}'"
            ),
            status_code=503,
        )

    # Pick least loaded among higher instances
    target = min(
        candidates,
        key=lambda i: i.active_tickets_count,
    )

    # Mark current distribution as escalated
    current.status = "escalated"
    current.escalation_target_instance_id = target.id

    # Create new distribution on higher instance
    new_dist = VariantWorkloadDistribution(
        company_id=company_id,
        instance_id=target.id,
        ticket_id=ticket_id.strip(),
        distribution_strategy="escalated",
        assigned_at=datetime.utcnow(),
        status="assigned",
        rebalance_from_instance_id=current_inst.id,
    )
    db.add(new_dist)

    # Atomic SQL UPDATE: decrement source, increment target (GAP 1 fix)
    now_ts = datetime.utcnow()
    db.execute(
        sa.text(
            "UPDATE variant_instances SET "
            "active_tickets_count = CASE "
            "WHEN active_tickets_count > 0 "
            "THEN active_tickets_count - 1 ELSE 0 END, "
            "updated_at = :now_ts "
            "WHERE id = :inst_id AND company_id = :comp_id"
        ),
        {"inst_id": current_inst.id, "comp_id": company_id, "now_ts": now_ts},
    )
    db.execute(
        sa.text(
            "UPDATE variant_instances SET "
            "active_tickets_count = active_tickets_count + 1, "
            "total_tickets_handled = total_tickets_handled + 1, "
            "last_activity_at = :now_ts, "
            "updated_at = :now_ts "
            "WHERE id = :inst_id AND company_id = :comp_id"
        ),
        {"inst_id": target.id, "comp_id": company_id, "now_ts": now_ts},
    )

    db.commit()
    db.refresh(new_dist)
    return new_dist


def complete_ticket_assignment(
    db: SessionLocal,
    company_id: str,
    distribution_id: str,
) -> VariantWorkloadDistribution:
    """
    Mark a ticket assignment as completed.

    Sets completed_at, status='completed', decrements instance
    active_tickets_count, and sets billing_charged_to_instance.
    """
    _validate_company_id(company_id)

    if not distribution_id or not distribution_id.strip():
        raise ParwaBaseError(
            error_code="INVALID_DISTRIBUTION_ID",
            message=(
                "distribution_id is required and cannot be empty"
            ),
            status_code=400,
        )

    dist = db.query(VariantWorkloadDistribution).filter_by(
        company_id=company_id,
        id=distribution_id.strip(),
    ).first()

    if dist is None:
        raise ParwaBaseError(
            error_code="DISTRIBUTION_NOT_FOUND",
            message=(
                f"Distribution '{distribution_id}' not found "
                f"for company '{company_id}'"
            ),
            status_code=404,
        )

    if dist.status == "completed":
        return dist

    dist.status = "completed"
    dist.completed_at = datetime.utcnow()
    dist.billing_charged_to_instance = dist.instance_id

    # Atomic SQL UPDATE: decrement active count (GAP 1 fix)
    db.execute(
        sa.text(
            "UPDATE variant_instances SET "
            "active_tickets_count = CASE "
            "WHEN active_tickets_count > 0 "
            "THEN active_tickets_count - 1 ELSE 0 END, "
            "last_activity_at = :now_ts, "
            "updated_at = :now_ts "
            "WHERE id = :inst_id AND company_id = :comp_id"
        ),
        {"inst_id": dist.instance_id, "comp_id": company_id, "now_ts": datetime.utcnow()},
    )

    db.commit()
    db.refresh(dist)
    return dist


def get_distribution_history(
    db: SessionLocal,
    company_id: str,
    ticket_id: str | None = None,
    instance_id: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """
    Query distribution records.

    Can filter by ticket_id, instance_id, and/or status.
    Returns list of dicts with distribution details.
    """
    _validate_company_id(company_id)

    query = db.query(VariantWorkloadDistribution).filter_by(
        company_id=company_id,
    )

    if ticket_id is not None:
        query = query.filter_by(ticket_id=ticket_id)

    if instance_id is not None:
        query = query.filter_by(instance_id=instance_id)

    if status is not None:
        query = query.filter_by(status=status)

    records = query.order_by(
        VariantWorkloadDistribution.assigned_at.desc(),
    ).limit(100).all()

    return [
        {
            "id": r.id,
            "instance_id": r.instance_id,
            "ticket_id": r.ticket_id,
            "strategy": r.distribution_strategy,
            "status": r.status,
            "assigned_at": (
                r.assigned_at.isoformat()
                if r.assigned_at else None
            ),
            "completed_at": (
                r.completed_at.isoformat()
                if r.completed_at else None
            ),
            "escalation_target": (
                r.escalation_target_instance_id
            ),
            "rebalance_from": (
                r.rebalance_from_instance_id
            ),
            "billing_charged_to": (
                r.billing_charged_to_instance
            ),
        }
        for r in records
    ]


def get_orchestration_summary(
    db: SessionLocal,
    company_id: str,
) -> dict:
    """
    Overall orchestration metrics for a company.

    Returns:
      - total_instances (by status)
      - total_distributions (by status, by strategy)
      - capacity summary
      - recent activity
    """
    _validate_company_id(company_id)

    instances = db.query(VariantInstance).filter_by(
        company_id=company_id,
    ).all()

    by_status = {}
    by_variant = {}
    total_active_tickets = 0
    total_handled = 0

    for inst in instances:
        by_status[inst.status] = (
            by_status.get(inst.status, 0) + 1
        )
        by_variant[inst.variant_type] = (
            by_variant.get(inst.variant_type, 0) + 1
        )
        total_active_tickets += inst.active_tickets_count
        total_handled += inst.total_tickets_handled

    # Distribution stats
    distributions = db.query(VariantWorkloadDistribution).filter_by(
        company_id=company_id,
    ).all()

    dist_by_status = {}
    dist_by_strategy = {}
    for d in distributions:
        dist_by_status[d.status] = (
            dist_by_status.get(d.status, 0) + 1
        )
        strat = d.distribution_strategy or "unknown"
        dist_by_strategy[strat] = (
            dist_by_strategy.get(strat, 0) + 1
        )

    # Active capacity
    active_instances = [
        i for i in instances if i.status == "active"
    ]
    total_max_conc = 0
    for inst in active_instances:
        cap = _parse_capacity(inst.capacity_config)
        total_max_conc += cap.get(
            "max_concurrent_tickets", DEFAULT_MAX_CONCURRENT,
        )

    return {
        "instances": {
            "total": len(instances),
            "by_status": by_status,
            "by_variant_type": by_variant,
        },
        "capacity": {
            "total_max_concurrent": total_max_conc,
            "total_active_tickets": total_active_tickets,
            "available_capacity": max(
                0, total_max_conc - total_active_tickets,
            ),
            "utilization_pct": round(
                (
                    total_active_tickets
                    / max(total_max_conc, 1)
                ) * 100, 2,
            ),
        },
        "distributions": {
            "total": len(distributions),
            "by_status": dist_by_status,
            "by_strategy": dist_by_strategy,
        },
        "total_tickets_handled": total_handled,
    }
