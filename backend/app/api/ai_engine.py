"""
PARWA AI Engine API Router (Week 8).

REST endpoints for all Day 1+2 AI Engine services including:
- Variant Capability Management (SG-01)
- Variant Instance Management (SG-37)
- Variant Orchestration (SG-38)
- Entitlement Checks (SG-05)
- Cost Protection (SG-35)
- Smart Router (F-054)
- Cold Start (SG-30)
- Model Failover (F-055)

All endpoints follow BC-001 (company_id scoping), BC-011 (JWT auth),
and BC-012 (structured JSON responses).

Import patterns:
  - Lazy service imports inside endpoint functions to avoid circular imports.
  - Dependencies: require_roles, get_company_id, get_current_user, get_db.
"""

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    require_roles,
    get_company_id,
    get_current_user,
)
from app.exceptions import NotFoundError, ValidationError
from database.base import get_db
from database.models.core import User

router = APIRouter(prefix="/api/ai", tags=["ai-engine"])


# ═══════════════════════════════════════════════════════════════════
# REQUEST SCHEMAS (M-14: Replace raw body:dict with Pydantic models)
# ═══════════════════════════════════════════════════════════════════


class UpdateCapabilityRequest(BaseModel):
    """Request to update a capability configuration."""
    variant_type: str = Field(..., description="Variant type (e.g. mini_parwa, parwa, parwa_high)")
    config: Dict[str, Any] = Field(default_factory=dict, description="Configuration key-value pairs")
    instance_id: Optional[str] = Field(None, description="Optional instance-level override")


class BatchCapabilityUpdateItem(BaseModel):
    """Single item in a batch capability update."""
    feature_id: str = Field(..., description="Feature ID to update")
    variant_type: str = Field(..., description="Variant type")
    is_enabled: bool = Field(..., description="Enable or disable the feature")
    instance_id: Optional[str] = Field(None, description="Optional instance override")


class BatchCapabilityUpdateRequest(BaseModel):
    """Request to batch update multiple capabilities."""
    updates: List[BatchCapabilityUpdateItem] = Field(..., description="List of capability updates")


class CreateInstanceRequest(BaseModel):
    """Request to create a new variant instance."""
    instance_name: str = Field(..., min_length=1, max_length=255, description="Instance name")
    variant_type: str = Field(..., description="Variant type (mini_parwa, parwa, parwa_high)")
    channel_assignment: Optional[List[str]] = Field(None, description="Channels assigned to this instance")
    capacity_config: Optional[Dict[str, Any]] = Field(None, description="Capacity configuration dict")


class UpdateInstanceRequest(BaseModel):
    """Request to update an instance's configuration."""
    channel_assignment: Optional[List[str]] = Field(None, description="Channels assigned to this instance")
    capacity_config: Optional[Dict[str, Any]] = Field(None, description="Capacity configuration dict")


class RouteTicketRequest(BaseModel):
    """Request to route a ticket to the best available instance."""
    ticket_id: str = Field(..., description="Ticket ID to route")
    channel: Optional[str] = Field(None, description="Channel of the ticket")
    strategy: Optional[str] = Field("least_loaded", description="Routing strategy")
    variant_type: Optional[str] = Field(None, description="Preferred variant type")


class TriggerWarmupRequest(BaseModel):
    """Request to trigger manual warmup for AI models."""
    variant_type: str = Field(..., description="Variant type to warm up")


class BatchEntitlementCheckRequest(BaseModel):
    """Request to batch check feature entitlements."""
    feature_ids: List[str] = Field(..., min_length=1, description="Feature IDs to check")
    variant_type: str = Field(..., description="Variant type")
    instance_id: Optional[str] = Field(None, description="Optional instance ID")


class InstanceOverrideRequest(BaseModel):
    """Request to create/update a per-instance feature override."""
    feature_id: str = Field(..., description="Feature ID")
    variant_type: str = Field(..., description="Variant type")
    instance_id: str = Field(..., description="Instance ID")
    is_enabled: bool = Field(..., description="Enable or disable")
    config_json: Optional[Dict[str, Any]] = Field(None, description="Optional configuration override")


class RemoveOverrideRequest(BaseModel):
    """Request to remove a per-instance feature override."""
    feature_id: str = Field(..., description="Feature ID")
    variant_type: str = Field(..., description="Variant type")
    instance_id: str = Field(..., description="Instance ID")


class ResetBudgetRequest(BaseModel):
    """Request to reset budget counters."""
    budget_type: str = Field("daily", description="Budget type: 'daily' or 'monthly'")


# ═══════════════════════════════════════════════════════════════════
# SERIALIZATION HELPERS
# ═══════════════════════════════════════════════════════════════════


def _serialize_capability(cap) -> dict:
    """Serialize a VariantAICapability ORM object to response dict."""
    config = {}
    if cap.config_json:
        try:
            config = json.loads(cap.config_json)
        except (json.JSONDecodeError, TypeError):
            config = {}
    return {
        "id": cap.id,
        "company_id": cap.company_id,
        "variant_type": cap.variant_type,
        "instance_id": cap.instance_id,
        "feature_id": cap.feature_id,
        "feature_name": cap.feature_name,
        "feature_category": cap.feature_category,
        "technique_tier": cap.technique_tier,
        "is_enabled": cap.is_enabled,
        "config": config,
        "created_at": (
            cap.created_at.isoformat() if cap.created_at else None
        ),
        "updated_at": (
            cap.updated_at.isoformat() if cap.updated_at else None
        ),
    }


def _serialize_instance(inst) -> dict:
    """Serialize a VariantInstance ORM object to response dict."""
    channels = []
    if inst.channel_assignment:
        try:
            channels = json.loads(inst.channel_assignment)
        except (json.JSONDecodeError, TypeError):
            channels = []
    capacity = {}
    if inst.capacity_config:
        try:
            capacity = json.loads(inst.capacity_config)
        except (json.JSONDecodeError, TypeError):
            capacity = {}
    return {
        "id": inst.id,
        "company_id": inst.company_id,
        "instance_name": inst.instance_name,
        "variant_type": inst.variant_type,
        "status": inst.status,
        "channel_assignment": channels,
        "capacity_config": capacity,
        "celery_queue_namespace": inst.celery_queue_namespace,
        "redis_partition_key": inst.redis_partition_key,
        "active_tickets_count": inst.active_tickets_count,
        "total_tickets_handled": inst.total_tickets_handled,
        "last_activity_at": (
            inst.last_activity_at.isoformat()
            if inst.last_activity_at else None
        ),
        "created_at": (
            inst.created_at.isoformat() if inst.created_at else None
        ),
        "updated_at": (
            inst.updated_at.isoformat() if inst.updated_at else None
        ),
    }


def _serialize_distribution(dist) -> dict:
    """Serialize a VariantWorkloadDistribution ORM object."""
    return {
        "id": dist.id,
        "company_id": dist.company_id,
        "instance_id": dist.instance_id,
        "ticket_id": dist.ticket_id,
        "strategy": dist.distribution_strategy,
        "status": dist.status,
        "assigned_at": (
            dist.assigned_at.isoformat() if dist.assigned_at else None
        ),
        "completed_at": (
            dist.completed_at.isoformat() if dist.completed_at else None
        ),
        "escalation_target": dist.escalation_target_instance_id,
        "rebalance_from": dist.rebalance_from_instance_id,
        "billing_charged_to": dist.billing_charged_to_instance,
    }


def _serialize_warmup_state(state) -> dict:
    """Serialize a TenantWarmupState dataclass to response dict."""
    if state is None:
        return {"status": "cold", "message": "No warmup data"}

    models = {}
    for key, ms in state.models_warmed.items():
        models[key] = {
            "provider": ms.provider,
            "model_id": ms.model_id,
            "tier": ms.tier,
            "status": ms.status.value,
            "warmup_success": ms.warmup_success,
            "warmup_latency_ms": ms.warmup_latency_ms,
            "last_warmed_at": ms.last_warmed_at,
            "error_message": ms.error_message,
        }

    return {
        "company_id": state.company_id,
        "variant_type": state.variant_type,
        "overall_status": state.overall_status.value,
        "models_warmed": models,
        "time_to_warm_ms": state.time_to_warm_ms,
        "fallback_used": state.fallback_used,
        "started_at": state.started_at,
        "completed_at": state.completed_at,
    }


# ═══════════════════════════════════════════════════════════════════
# Variant Capability Management (SG-01)
# ═══════════════════════════════════════════════════════════════════


@router.get("/capabilities")
def list_capabilities(
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    variant_type: Optional[str] = Query(None),
    instance_id: Optional[str] = Query(None),
    feature_category: Optional[str] = Query(None),
    enabled_only: bool = Query(False),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """List all AI capabilities for the company.

    Filter by variant_type, instance_id, feature_category, or
    enabled_only. Returns paginated-style list with total count.
    """
    from app.services.variant_capability_service import (
        list_capabilities as svc_list_capabilities,
    )

    items = svc_list_capabilities(
        db,
        company_id=company_id,
        variant_type=variant_type,
        feature_category=feature_category,
        instance_id=instance_id,
        enabled_only=enabled_only,
    )

    return {
        "items": [_serialize_capability(c) for c in items],
        "total": len(items),
    }


@router.get("/capabilities/{feature_id}")
def get_capability(
    feature_id: str,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    variant_type: Optional[str] = Query(None),
    instance_id: Optional[str] = Query(None),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Get single capability detail by feature_id."""
    from app.services.variant_capability_service import (
        get_capability as svc_get_capability,
    )

    cap = svc_get_capability(
        db,
        company_id=company_id,
        feature_id=feature_id,
        variant_type=variant_type,
        instance_id=instance_id,
    )

    if cap is None:
        raise NotFoundError(
            message=f"Capability '{feature_id}' not found",
            details={"feature_id": feature_id},
        )

    return {"status": "ok", "data": _serialize_capability(cap)}


@router.put("/capabilities/{feature_id}")
def update_capability(
    feature_id: str,
    body: UpdateCapabilityRequest,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Update capability configuration for a feature.

    Body must include 'variant_type' and 'config' keys.
    Optionally include 'instance_id' for instance-level override.
    """
    from app.services.variant_capability_service import (
        update_capability_config,
    )

    updated = update_capability_config(
        db,
        company_id=company_id,
        feature_id=feature_id,
        variant_type=body.variant_type,
        config_json=body.config,
        instance_id=body.instance_id,
    )

    return {"status": "ok", "data": _serialize_capability(updated)}


@router.post("/capabilities/batch")
def batch_update_capabilities(
    body: BatchCapabilityUpdateRequest,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Batch enable/disable multiple capabilities.

    Body must include 'updates' key: a list of dicts with
    feature_id, variant_type, is_enabled, and optional instance_id.
    """
    from app.services.variant_capability_service import (
        batch_update_capabilities,
    )

    updates = [item.model_dump() for item in body.updates]

    result = batch_update_capabilities(
        db,
        company_id=company_id,
        updates=updates,
    )

    return {
        "status": "ok",
        "data": result,
    }


# ═══════════════════════════════════════════════════════════════════
# Variant Instance Management (SG-37)
# ═══════════════════════════════════════════════════════════════════


@router.get("/instances")
def list_instances(
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    variant_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """List all variant instances for the company.

    Filter by variant_type or status.
    """
    from app.services.variant_instance_service import (
        list_instances as svc_list_instances,
    )

    items = svc_list_instances(
        db,
        company_id=company_id,
        variant_type=variant_type,
        status=status,
    )

    return {
        "items": [_serialize_instance(i) for i in items],
        "total": len(items),
    }


@router.post("/instances")
def create_instance(
    body: CreateInstanceRequest,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Register a new variant instance.

    Body must include 'instance_name' and 'variant_type'.
    Optionally include 'channel_assignment' (list of strings)
    and 'capacity_config' (dict).
    """
    from app.services.variant_instance_service import (
        register_instance,
    )

    instance = register_instance(
        db,
        company_id=company_id,
        instance_name=body.instance_name,
        variant_type=body.variant_type,
        channel_assignment=body.channel_assignment,
        capacity_config=body.capacity_config,
    )

    return {"status": "ok", "data": _serialize_instance(instance)}


@router.get("/instances/{instance_id}")
def get_instance(
    instance_id: str,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Get single instance detail by ID."""
    from app.services.variant_instance_service import (
        get_instance as svc_get_instance,
    )

    instance = svc_get_instance(
        db,
        company_id=company_id,
        instance_id=instance_id,
    )

    if instance is None:
        raise NotFoundError(
            message=f"Instance '{instance_id}' not found",
            details={"instance_id": instance_id},
        )

    return {"status": "ok", "data": _serialize_instance(instance)}


@router.put("/instances/{instance_id}")
def update_instance(
    instance_id: str,
    body: UpdateInstanceRequest,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Update an instance's configuration.

    Supports updating 'channel_assignment' (list) and/or
    'capacity_config' (dict).
    """
    from app.services.variant_instance_service import (
        update_channel_assignment,
        update_capacity_config,
    )

    if body.channel_assignment is None and body.capacity_config is None:
        raise ValidationError(
            message=(
                "At least one of channel_assignment or "
                "capacity_config must be provided"
            ),
        )

    if body.channel_assignment is not None:
        instance = update_channel_assignment(
            db,
            company_id=company_id,
            instance_id=instance_id,
            channels=body.channel_assignment,
        )
    else:
        instance = update_capacity_config(
            db,
            company_id=company_id,
            instance_id=instance_id,
            config=body.capacity_config,
        )

    if body.channel_assignment is not None and body.capacity_config is not None:
        instance = update_capacity_config(
            db,
            company_id=company_id,
            instance_id=instance_id,
            config=body.capacity_config,
        )

    return {"status": "ok", "data": _serialize_instance(instance)}


@router.delete("/instances/{instance_id}")
def deactivate_instance(
    instance_id: str,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Deactivate an instance (set status to 'inactive')."""
    from app.services.variant_instance_service import (
        deactivate_instance,
    )

    instance = deactivate_instance(
        db,
        company_id=company_id,
        instance_id=instance_id,
    )

    return {
        "status": "ok",
        "data": _serialize_instance(instance),
    }


@router.get("/instances/highest")
def get_highest_active_variant(
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Get the highest active variant type for the company.

    Returns the variant type with the highest tier that has
    at least one active instance. Priority: parwa_high > parwa > mini_parwa.
    """
    from app.services.variant_instance_service import (
        get_highest_active_variant,
    )

    variant = get_highest_active_variant(db, company_id=company_id)

    return {
        "status": "ok",
        "data": {
            "company_id": company_id,
            "highest_active_variant": variant,
        },
    }


# ═══════════════════════════════════════════════════════════════════
# Variant Orchestration (SG-38)
# ═══════════════════════════════════════════════════════════════════


@router.post("/orchestrate/route-ticket")
def route_ticket(
    body: RouteTicketRequest,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Route a ticket to the best available instance.

    Body must include 'ticket_id'. Optionally include 'channel',
    'strategy' (default: 'least_loaded'), and 'variant_type'.
    """
    from app.services.variant_orchestration_service import (
        route_ticket as svc_route_ticket,
    )

    distribution = svc_route_ticket(
        db,
        company_id=company_id,
        ticket_id=body.ticket_id,
        channel=body.channel,
        strategy=body.strategy,
        variant_type=body.variant_type,
    )

    return {"status": "ok", "data": _serialize_distribution(distribution)}


@router.get("/orchestrate/workload")
def get_workload_status(
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Get workload distribution status across all instances."""
    from app.services.variant_orchestration_service import (
        get_all_instance_loads,
        get_orchestration_summary,
    )

    loads = get_all_instance_loads(db, company_id=company_id)
    summary = get_orchestration_summary(db, company_id=company_id)

    return {
        "status": "ok",
        "data": {
            "instance_loads": loads,
            "summary": summary,
        },
    }


@router.post("/orchestrate/rebalance")
def rebalance_workload(
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Trigger manual workload rebalance across instances.

    Checks for overloaded instances and migrates tickets to
    underloaded instances.
    """
    from app.services.variant_orchestration_service import (
        rebalance_workload as svc_rebalance,
    )

    result = svc_rebalance(db, company_id=company_id)

    return {"status": "ok", "data": result}


# ═══════════════════════════════════════════════════════════════════
# Entitlement Checks (SG-05)
# ═══════════════════════════════════════════════════════════════════


@router.get("/entitlement/check")
def check_entitlement(
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    feature_id: str = Query(..., description="Feature ID to check"),
    variant_type: str = Query(..., description="Variant type"),
    instance_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
) -> dict:
    """Check if a feature is entitled for the given variant/instance.

    Returns EntitlementResult with is_entitled, reason, and
    optional upgrade_suggestion.
    """
    from app.services.entitlement_middleware import (
        check_entitlement as svc_check_entitlement,
    )

    result = svc_check_entitlement(
        db,
        company_id=company_id,
        feature_id=feature_id,
        variant_type=variant_type,
        instance_id=instance_id,
    )

    return {
        "status": "ok",
        "data": {
            "is_entitled": result.is_entitled,
            "feature_id": result.feature_id,
            "variant_type": result.variant_type,
            "reason": result.reason,
            "upgrade_suggestion": result.upgrade_suggestion,
        },
    }


@router.post("/entitlement/batch-check")
def batch_check_entitlements(
    body: BatchEntitlementCheckRequest,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Batch check multiple features for entitlement.

    Body must include 'feature_ids' (list of strings) and
    'variant_type'. Optionally include 'instance_id'.
    """
    from app.services.entitlement_middleware import (
        batch_check_entitlements as svc_batch_check,
    )

    result = svc_batch_check(
        db,
        company_id=company_id,
        feature_ids=body.feature_ids,
        variant_type=body.variant_type,
        instance_id=body.instance_id,
    )

    return {"status": "ok", "data": result}


@router.get("/entitlement/summary")
def get_entitlement_summary(
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    variant_type: str = Query(..., description="Variant type"),
    instance_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
) -> dict:
    """Get entitlement summary for a variant type.

    Returns counts of enabled/disabled features, lists of
    feature IDs, and breakdown by category.
    """
    from app.services.entitlement_middleware import (
        get_entitlement_summary as svc_get_summary,
    )

    summary = svc_get_summary(
        db,
        company_id=company_id,
        variant_type=variant_type,
        instance_id=instance_id,
    )

    return {"status": "ok", "data": summary}


@router.get("/entitlement/upgrade-nudge")
def get_upgrade_nudge(
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    feature_id: str = Query(..., description="Feature ID"),
    variant_type: str = Query(..., description="Current variant type"),
    user: User = Depends(get_current_user),
) -> dict:
    """Get upgrade suggestion for a feature not in current plan.

    Includes current plan, required plan, pricing, and
    feature details.
    """
    from app.services.entitlement_middleware import (
        get_upgrade_nudge as svc_get_upgrade_nudge,
    )

    nudge = svc_get_upgrade_nudge(
        db,
        company_id=company_id,
        feature_id=feature_id,
        variant_type=variant_type,
    )

    return {"status": "ok", "data": nudge}


@router.post("/entitlement/instance-override")
def create_instance_override(
    body: InstanceOverrideRequest,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Create or update a per-instance feature override.

    Body must include 'feature_id', 'variant_type', 'instance_id',
    and 'is_enabled'. Optionally include 'config_json'.
    """
    from app.services.entitlement_middleware import (
        create_instance_override as svc_create_override,
    )

    override = svc_create_override(
        db,
        company_id=company_id,
        feature_id=body.feature_id,
        variant_type=body.variant_type,
        instance_id=body.instance_id,
        is_enabled=body.is_enabled,
        config_json=body.config_json,
    )

    return {"status": "ok", "data": _serialize_capability(override)}


@router.delete("/entitlement/instance-override")
def remove_instance_override(
    body: RemoveOverrideRequest,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Remove a per-instance feature override.

    Body must include 'feature_id', 'variant_type', and 'instance_id'.
    After removal, the feature falls back to variant-type default.
    """
    from app.services.entitlement_middleware import (
        remove_instance_override as svc_remove_override,
    )

    removed = svc_remove_override(
        db,
        company_id=company_id,
        feature_id=body.feature_id,
        variant_type=body.variant_type,
        instance_id=body.instance_id,
    )

    return {
        "status": "ok",
        "data": {
            "removed": removed,
            "feature_id": body.feature_id,
            "instance_id": body.instance_id,
            "message": (
                "Override removed successfully"
                if removed
                else "No override found to remove"
            ),
        },
    }


# ═══════════════════════════════════════════════════════════════════
# Cost Protection (SG-35)
# ═══════════════════════════════════════════════════════════════════


@router.get("/cost/budget")
def get_budget_status(
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    budget_type: str = Query("daily", description="daily or monthly"),
    instance_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
) -> dict:
    """Get current token budget status for the company.

    Returns usage stats including used/max tokens, remaining,
    usage percentage, alert level, and status.
    """
    from app.services.cost_protection_service import (
        CostProtectionService,
    )

    service = CostProtectionService(db)
    usage = service.get_usage(
        company_id=company_id,
        budget_type=budget_type,
        instance_id=instance_id,
    )

    return {"status": "ok", "data": usage}


@router.post("/cost/budget/reset")
def reset_budget(
    body: ResetBudgetRequest,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Reset daily/monthly budget counters.

    Body should include 'budget_type' ('daily' or 'monthly').
    Resets used_tokens to 0, status to 'active', and clears alert_sent.
    """
    from app.services.cost_protection_service import (
        CostProtectionService,
    )

    budget_type = body.budget_type

    service = CostProtectionService(db)

    if budget_type == "monthly":
        # Reset monthly budgets by resetting all daily budgets
        # and the monthly budget for current period
        result = service.reset_daily_budgets(company_id)
        # Also try to get and reset monthly usage
        monthly_usage = service.get_usage(
            company_id=company_id, budget_type="monthly",
        )
        result["monthly_reset"] = True
        result["monthly_status"] = monthly_usage.get("status")
    else:
        result = service.reset_daily_budgets(company_id)

    return {"status": "ok", "data": result}


# ═══════════════════════════════════════════════════════════════════
# Smart Router (F-054)
# ═══════════════════════════════════════════════════════════════════


@router.get("/router/status")
def get_router_status(
    user: User = Depends(get_current_user),
) -> dict:
    """Get Smart Router health and overall provider status.

    Returns health overview for all tracked provider+model
    combinations including availability, daily usage, and errors.
    """
    from app.core.smart_router import SmartRouter

    router = SmartRouter()
    status = router.get_provider_status()

    # Summary counts
    total_models = len(status)
    healthy = sum(1 for s in status.values() if s.get("is_healthy"))
    unhealthy = total_models - healthy

    return {
        "status": "ok",
        "data": {
            "total_models": total_models,
            "healthy_models": healthy,
            "unhealthy_models": unhealthy,
            "providers": status,
        },
    }


@router.get("/router/providers")
def get_router_providers(
    user: User = Depends(get_current_user),
) -> dict:
    """List available providers with health and model details.

    Returns structured list grouped by provider and tier.
    """
    from app.core.smart_router import (
        MODEL_REGISTRY,
        VARIANT_MODEL_ACCESS,
        ModelTier,
        ModelProvider,
    )

    # Group models by provider
    providers = {}
    for key, config in MODEL_REGISTRY.items():
        provider = config.provider.value
        tier = config.tier.value

        if provider not in providers:
            providers[provider] = {
                "provider": provider,
                "tiers": {},
                "total_models": 0,
            }

        if tier not in providers[provider]["tiers"]:
            providers[provider]["tiers"][tier] = []

        providers[provider]["tiers"][tier].append({
            "registry_key": key,
            "model_id": config.model_id,
            "display_name": config.display_name,
            "priority": config.priority,
            "context_window": config.context_window,
            "max_requests_per_day": config.max_requests_per_day,
            "is_openai_compatible": config.is_openai_compatible,
        })
        providers[provider]["total_models"] += 1

    # Add variant access info
    variant_access = {}
    for vt, tiers in VARIANT_MODEL_ACCESS.items():
        variant_access[vt] = sorted(t.value for t in tiers)

    return {
        "status": "ok",
        "data": {
            "providers": providers,
            "variant_model_access": variant_access,
            "total_providers": len(providers),
            "total_models": len(MODEL_REGISTRY),
        },
    }


# ═══════════════════════════════════════════════════════════════════
# Cold Start (SG-30)
# ═══════════════════════════════════════════════════════════════════


@router.post("/cold-start/warmup")
def trigger_warmup(
    body: TriggerWarmupRequest,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Trigger manual warmup for the company's AI models.

    Body must include 'variant_type'. Warms up all model
    combos relevant to that variant tier.
    """
    from app.core.cold_start_service import get_cold_start_service

    service = get_cold_start_service()
    state = service.warmup_tenant(company_id, body.variant_type)

    return {"status": "ok", "data": _serialize_warmup_state(state)}


@router.get("/cold-start/status")
def get_warmup_status(
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Get warmup status for the company.

    Returns the current warmup state including which models
    have been warmed and their status.
    """
    from app.core.cold_start_service import get_cold_start_service

    service = get_cold_start_service()
    state = service.get_tenant_status(company_id)

    return {"status": "ok", "data": _serialize_warmup_state(state)}


# ═══════════════════════════════════════════════════════════════════
# Model Failover (F-055)
# ═══════════════════════════════════════════════════════════════════


@router.get("/failover/status")
def get_failover_status(
    user: User = Depends(get_current_user),
) -> dict:
    """Get failover chain status for all provider+model circuits.

    Returns circuit breaker states, failure counts, and
    availability info.
    """
    from app.core.model_failover import FailoverManager

    manager = FailoverManager()
    states = manager.get_all_circuit_states()

    # Summary
    total = len(states)
    healthy = sum(
        1 for s in states.values()
        if s.get("state") == "healthy"
    )
    degraded = sum(
        1 for s in states.values()
        if s.get("state") == "degraded"
    )
    circuit_open = sum(
        1 for s in states.values()
        if s.get("state") == "circuit_open"
    )

    return {
        "status": "ok",
        "data": {
            "total_circuits": total,
            "healthy": healthy,
            "degraded": degraded,
            "circuit_open": circuit_open,
            "circuits": states,
        },
    }


@router.get("/failover/history")
def get_failover_history(
    company_id: str = Depends(get_company_id),
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    user: User = Depends(get_current_user),
) -> dict:
    """Get recent failover events for the company.

    Returns aggregate failover stats by provider including
    failure reasons and circuit states.
    """
    from app.core.model_failover import FailoverManager

    manager = FailoverManager()
    stats = manager.get_failover_stats(
        company_id=company_id,
        hours=hours,
    )

    return {"status": "ok", "data": stats}


# ═══════════════════════════════════════════════════════════════════
# AI Monitoring Dashboard (SG-19)
# ═══════════════════════════════════════════════════════════════════


@router.get("/monitoring/dashboard")
def get_monitoring_dashboard(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> dict:
    """Get AI performance monitoring dashboard data.

    Returns aggregated metrics including latency percentiles,
    confidence distribution, guardrail pass rates, error rates,
    provider comparisons, and active alerts.
    """
    from app.core.ai_monitoring_service import AIMonitoringService

    monitor = AIMonitoringService()
    dashboard = monitor.get_dashboard_data(company_id=company_id)

    return {"status": "ok", "data": dashboard}


@router.get("/monitoring/alerts")
def get_monitoring_alerts(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> dict:
    """Get active alert conditions for the company.

    Returns list of alert conditions that have been triggered,
    including error rate, confidence, latency, and guardrail alerts.
    """
    from app.core.ai_monitoring_service import AIMonitoringService

    monitor = AIMonitoringService()
    alerts = monitor.get_alert_conditions(company_id=company_id)

    return {
        "status": "ok",
        "data": {
            "alerts": alerts,
            "total": len(alerts),
        },
    }


@router.get("/monitoring/metrics")
def get_monitoring_metrics(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> dict:
    """Get detailed AI execution metrics.

    Returns execution count, success rate, average latency,
    fallback rate, error rate, and per-task-type breakdown.
    """
    from app.core.ai_monitoring_service import AIMonitoringService

    monitor = AIMonitoringService()
    metrics = monitor.get_metrics_summary(company_id=company_id)

    return {"status": "ok", "data": metrics}
