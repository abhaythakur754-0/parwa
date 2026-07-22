"""
Variant Engine Pydantic Schemas for Phase 3 AI Engine.

Schemas for:
  - Variant AI Capability Matrix (SG-01)
  - Variant Instance Architecture (SG-37)
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Capability Schemas (SG-01) ─────────────────────────────────

class VariantCapabilityResponse(BaseModel):
    """Full capability record from variant_ai_capabilities."""
    id: str
    company_id: str
    variant_type: str
    instance_id: Optional[str] = None
    feature_id: str
    feature_name: str
    feature_category: Optional[str] = None
    technique_tier: Optional[str] = None
    is_enabled: bool = True
    config_json: str = "{}"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class VariantCapabilityUpdate(BaseModel):
    """Request body for updating a capability config."""
    config_json: dict = Field(
        default_factory=dict,
        description="Per-feature configuration overrides",
    )
    is_enabled: Optional[bool] = Field(
        default=None,
        description="Override enabled status",
    )


# ── Instance Schemas (SG-37) ───────────────────────────────────

class VariantInstanceCreate(BaseModel):
    """Request body for creating a variant instance."""
    instance_name: str = Field(
        min_length=1,
        max_length=255,
        description="Human-readable instance name",
    )
    variant_type: str = Field(
        min_length=1,
        max_length=50,
        description="mini_parwa, parwa, or parwa_high",
    )
    channel_assignment: Optional[list[str]] = Field(
        default=None,
        description="List of channels this instance handles",
    )
    capacity_config: Optional[dict] = Field(
        default=None,
        description="Capacity configuration overrides",
    )


class VariantInstanceResponse(BaseModel):
    """Full instance record from variant_instances."""
    id: str
    company_id: str
    instance_name: str
    variant_type: str
    status: str = "active"
    channel_assignment: str = "[]"
    capacity_config: str = "{}"
    celery_queue_namespace: Optional[str] = None
    redis_partition_key: Optional[str] = None
    active_tickets_count: int = 0
    total_tickets_handled: int = 0
    last_activity_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class VariantInstanceUpdate(BaseModel):
    """Request body for updating a variant instance."""
    status: Optional[str] = Field(
        default=None,
        description="New status value",
    )
    channel_assignment: Optional[list[str]] = Field(
        default=None,
        description="Updated channel list",
    )
    capacity_config: Optional[dict] = Field(
        default=None,
        description="Updated capacity config",
    )


# ── Summary Schemas ─────────────────────────────────────────────

class VariantFeatureSummary(BaseModel):
    """Feature count summary per variant type."""
    variant_type: str
    total_features: int
    enabled_features: int
    disabled_features: int


class VariantCapacitySummary(BaseModel):
    """Aggregate capacity across instances."""
    total_active_instances: int
    total_max_concurrent: int
    total_active_tickets: int
    available_capacity: int
    by_variant_type: dict = Field(
        default_factory=dict,
        description="Breakdown by variant_type",
    )
