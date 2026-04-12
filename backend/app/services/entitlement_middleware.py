"""
SG-05 AI Feature Entitlement Enforcement Middleware.

Intercepts every AI API call and checks variant_ai_capabilities
against the tenant's variant instance. Checks at instance level
(not just variant type). Returns 403 with upgrade nudge if
feature not in plan. Supports per-instance feature overrides.

Building Codes:
- BC-001: Multi-Tenant Isolation (every query filtered by
  company_id)
- BC-007: AI Model Interaction (feature gating per variant tier)
- BC-011: Authentication & Security

Uses:
- database.models.variant_engine.VariantAICapability
- backend.app.services.variant_capability_service
  .check_feature_enabled
- backend.app.exceptions.ParwaBaseError
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from database.models.variant_engine import VariantAICapability
from app.services.variant_capability_service import (
    VARIANT_LEVELS,
    FEATURE_REGISTRY,
    check_feature_enabled,
    _validate_company_id,
    _validate_variant_type,
)
from app.exceptions import ParwaBaseError


# ══════════════════════════════════════════════════════════════════
# PLAN DISPLAY NAMES FOR UPGRADE NUDGES
# ══════════════════════════════════════════════════════════════════

PLAN_DISPLAY_NAMES = {
    "mini_parwa": "Mini PARWA",
    "parwa": "PARWA",
    "parwa_high": "PARWA High",
}

PLAN_PRICING = {
    "mini_parwa": "$499/mo",
    "parwa": "$2,499/mo",
    "parwa_high": "$9,999/mo",
}

# Minimum variant type required for upgrade suggestion
# ordered by level
ORDERED_VARIANT_TYPES = [
    "mini_parwa",
    "parwa",
    "parwa_high",
]


# ══════════════════════════════════════════════════════════════════
# DATA CLASS
# ══════════════════════════════════════════════════════════════════

@dataclass
class EntitlementResult:
    """Result of an entitlement check."""
    is_entitled: bool
    feature_id: str
    variant_type: str
    reason: str
    # "enabled", "disabled_for_variant",
    # "disabled_globally", "instance_override_disabled",
    # "unknown_feature"
    upgrade_suggestion: str | None = None


# ══════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════

def _get_required_variant_type(
    feature_id: str,
) -> str | None:
    """
    Get the minimum variant type that supports a feature
    from the registry. Returns None if feature is not in
    the registry.
    """
    feat = FEATURE_REGISTRY.get(feature_id)
    if feat is None:
        return None
    min_level = feat["min_level"]
    for vt in ORDERED_VARIANT_TYPES:
        if VARIANT_LEVELS[vt] >= min_level:
            return vt
    return None


def _build_upgrade_suggestion(
    feature_id: str,
    current_variant_type: str,
) -> str | None:
    """
    Build an upgrade suggestion string.
    Returns None if the feature is unknown.
    """
    feat = FEATURE_REGISTRY.get(feature_id)
    if feat is None:
        return None

    min_level = feat["min_level"]
    current_level = VARIANT_LEVELS.get(current_variant_type, 0)

    # Already entitled at current level
    if current_level >= min_level:
        return None

    # Find the minimum variant that supports it
    for vt in ORDERED_VARIANT_TYPES:
        if VARIANT_LEVELS[vt] >= min_level:
            plan_name = PLAN_DISPLAY_NAMES[vt]
            price = PLAN_PRICING[vt]
            return (
                f"Upgrade to {plan_name} ({price}) "
                f"for {feature_id}"
            )

    return None


def _check_instance_override(
    db,
    company_id: str,
    feature_id: str,
    variant_type: str,
    instance_id: str,
) -> EntitlementResult:
    """
    Check if there is an instance-level override for
    the feature. Returns EntitlementResult based on
    the override.
    """
    from app.services.variant_capability_service import (
        get_capability,
    )

    cap = get_capability(
        db, company_id, feature_id, variant_type,
        instance_id=instance_id,
    )

    if cap is not None and cap.instance_id is not None:
        if cap.is_enabled:
            return EntitlementResult(
                is_entitled=True,
                feature_id=feature_id,
                variant_type=variant_type,
                reason="enabled",
                upgrade_suggestion=None,
            )
        else:
            return EntitlementResult(
                is_entitled=False,
                feature_id=feature_id,
                variant_type=variant_type,
                reason="instance_override_disabled",
                upgrade_suggestion=_build_upgrade_suggestion(
                    feature_id, variant_type,
                ),
            )

    return None


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════

def check_entitlement(
    db,
    company_id: str,
    feature_id: str,
    variant_type: str,
    instance_id: str | None = None,
) -> EntitlementResult:
    """
    Main entitlement check function.

    Checks if a feature is enabled for a given company,
    variant type, and optionally a specific instance.

    Returns EntitlementResult with is_entitled, reason,
    and optional upgrade_suggestion.
    """
    _validate_company_id(company_id)
    _validate_variant_type(variant_type)

    # Check if feature exists in the registry
    feat = FEATURE_REGISTRY.get(feature_id)

    # Step 1: If instance_id provided, check instance
    #         override first
    if instance_id is not None:
        override_result = _check_instance_override(
            db, company_id, feature_id,
            variant_type, instance_id,
        )
        if override_result is not None:
            return override_result

    # Step 2: Check feature_enabled via capability service
    is_enabled = check_feature_enabled(
        db, company_id, feature_id, variant_type,
        instance_id=instance_id,
    )

    if is_enabled:
        return EntitlementResult(
            is_entitled=True,
            feature_id=feature_id,
            variant_type=variant_type,
            reason="enabled",
            upgrade_suggestion=None,
        )

    # Step 3: Feature is not enabled — determine why
    if feat is None:
        return EntitlementResult(
            is_entitled=False,
            feature_id=feature_id,
            variant_type=variant_type,
            reason="disabled_globally",
            upgrade_suggestion=None,
        )

    min_level = feat["min_level"]
    current_level = VARIANT_LEVELS.get(variant_type, 0)

    if current_level < min_level:
        return EntitlementResult(
            is_entitled=False,
            feature_id=feature_id,
            variant_type=variant_type,
            reason="disabled_for_variant",
            upgrade_suggestion=_build_upgrade_suggestion(
                feature_id, variant_type,
            ),
        )

    # Feature is in registry and variant level is sufficient,
    # but it's disabled (e.g., manually disabled or global
    # override)
    return EntitlementResult(
        is_entitled=False,
        feature_id=feature_id,
        variant_type=variant_type,
        reason="disabled_globally",
        upgrade_suggestion=None,
    )


def enforce_entitlement(
    db,
    company_id: str,
    feature_id: str,
    variant_type: str,
    instance_id: str | None = None,
) -> None:
    """
    Enforce entitlement. Raises ParwaBaseError(403) if
    the feature is not entitled.

    Error codes:
    - FEATURE_NOT_ENTITLED (403): feature not available
      for variant
    - INSTANCE_FEATURE_DISABLED (403): feature disabled
      at instance level
    """
    result = check_entitlement(
        db, company_id, feature_id, variant_type, instance_id,
    )

    if result.is_entitled:
        return

    if result.reason == "instance_override_disabled":
        raise ParwaBaseError(
            message=(
                f"Feature '{feature_id}' is disabled for "
                f"instance '{instance_id}'. "
                f"{result.upgrade_suggestion or ''}"
            ),
            error_code="INSTANCE_FEATURE_DISABLED",
            status_code=403,
            details={
                "feature_id": feature_id,
                "variant_type": variant_type,
                "instance_id": instance_id,
                "reason": result.reason,
                "upgrade_suggestion": (
                    result.upgrade_suggestion
                ),
            },
        )

    raise ParwaBaseError(
        message=(
            f"Feature '{feature_id}' is not available for "
            f"variant '{variant_type}'. "
            f"{result.upgrade_suggestion or ''}"
        ),
        error_code="FEATURE_NOT_ENTITLED",
        status_code=403,
        details={
            "feature_id": feature_id,
            "variant_type": variant_type,
            "instance_id": instance_id,
            "reason": result.reason,
            "upgrade_suggestion": (
                result.upgrade_suggestion
            ),
        },
    )


def get_upgrade_nudge(
    db,
    company_id: str,
    feature_id: str,
    variant_type: str,
) -> dict:
    """
    Returns upgrade suggestion info for a feature.

    Includes current plan, required plan, feature name,
    and pricing info.
    """
    _validate_company_id(company_id)
    _validate_variant_type(variant_type)

    feat = FEATURE_REGISTRY.get(feature_id)

    if feat is None:
        return {
            "feature_id": feature_id,
            "feature_name": feature_id,
            "current_variant": variant_type,
            "current_plan": PLAN_DISPLAY_NAMES.get(
                variant_type, variant_type,
            ),
            "required_variant": None,
            "required_plan": None,
            "upgrade_available": False,
            "upgrade_suggestion": None,
            "pricing": None,
            "reason": "Feature not found in registry",
        }

    min_level = feat["min_level"]
    current_level = VARIANT_LEVELS.get(variant_type, 0)

    required_variant = None
    upgrade_available = current_level < min_level
    upgrade_suggestion = None
    pricing = None

    if upgrade_available:
        for vt in ORDERED_VARIANT_TYPES:
            if VARIANT_LEVELS[vt] >= min_level:
                required_variant = vt
                upgrade_suggestion = (
                    _build_upgrade_suggestion(
                        feature_id, variant_type,
                    )
                )
                pricing = PLAN_PRICING[vt]
                break
    else:
        # Already entitled at this level
        required_variant = variant_type

    return {
        "feature_id": feature_id,
        "feature_name": feat["name"],
        "current_variant": variant_type,
        "current_plan": PLAN_DISPLAY_NAMES.get(
            variant_type, variant_type,
        ),
        "required_variant": required_variant,
        "required_plan": (
            PLAN_DISPLAY_NAMES[required_variant]
            if required_variant
            else None
        ),
        "upgrade_available": upgrade_available,
        "upgrade_suggestion": upgrade_suggestion,
        "pricing": pricing,
        "reason": (
            "Feature available at current plan"
            if not upgrade_available
            else "Upgrade required"
        ),
    }


def batch_check_entitlements(
    db,
    company_id: str,
    feature_ids: list[str],
    variant_type: str,
    instance_id: str | None = None,
) -> dict:
    """
    Check multiple features at once.

    Returns:
    {
        "entitled": [feature_id, ...],
        "denied": [feature_id, ...],
        "results": {feature_id: EntitlementResult_dict, ...},
        "summary": {
            "total": int,
            "entitled_count": int,
            "denied_count": int,
        }
    }
    """
    _validate_company_id(company_id)
    _validate_variant_type(variant_type)

    if not isinstance(feature_ids, list):
        raise ParwaBaseError(
            message="feature_ids must be a list",
            error_code="VALIDATION_ERROR",
            status_code=400,
        )

    entitled = []
    denied = []
    results = {}

    for fid in feature_ids:
        result = check_entitlement(
            db, company_id, fid, variant_type,
            instance_id=instance_id,
        )
        results[fid] = {
            "is_entitled": result.is_entitled,
            "feature_id": result.feature_id,
            "variant_type": result.variant_type,
            "reason": result.reason,
            "upgrade_suggestion": (
                result.upgrade_suggestion
            ),
        }

        if result.is_entitled:
            entitled.append(fid)
        else:
            denied.append(fid)

    return {
        "entitled": entitled,
        "denied": denied,
        "results": results,
        "summary": {
            "total": len(feature_ids),
            "entitled_count": len(entitled),
            "denied_count": len(denied),
        },
    }


def create_instance_override(
    db,
    company_id: str,
    feature_id: str,
    variant_type: str,
    instance_id: str,
    is_enabled: bool,
    config_json: dict | None = None,
) -> VariantAICapability:
    """
    Create or update a per-instance feature override.

    If an override already exists for this
    company/feature/variant/instance combination,
    it updates the existing record.

    BC-001: All queries filtered by company_id.
    """
    _validate_company_id(company_id)
    _validate_variant_type(variant_type)

    if not instance_id or not instance_id.strip():
        raise ParwaBaseError(
            message="instance_id is required and cannot be empty",
            error_code="INVALID_INSTANCE_ID",
            status_code=400,
        )

    if not feature_id or not feature_id.strip():
        raise ParwaBaseError(
            message=(
                "feature_id is required and cannot be empty"
            ),
            error_code="INVALID_FEATURE_ID",
            status_code=400,
        )

    # Verify instance belongs to this company (BC-001)
    from database.models.variant_engine import VariantInstance
    instance = db.query(VariantInstance).filter(
        VariantInstance.id == instance_id,
        VariantInstance.company_id == company_id,
    ).first()
    if not instance:
        raise ParwaBaseError(
            status_code=404,
            error_code="INSTANCE_NOT_FOUND",
            detail="Instance not found",
        )

    # Check if override already exists
    existing = db.query(VariantAICapability).filter_by(
        company_id=company_id,
        feature_id=feature_id,
        variant_type=variant_type,
        instance_id=instance_id,
    ).first()

    if existing is not None:
        # Update existing override
        existing.is_enabled = is_enabled
        if config_json is not None:
            existing.config_json = json.dumps(config_json)
        existing.updated_at = datetime.now(timezone.utc)  # GAP 7 fix
        db.commit()
        db.refresh(existing)
        return existing

    # Look up the feature info from the base variant record
    # or from the registry
    feat = FEATURE_REGISTRY.get(feature_id)
    feat_name = (
        feat["name"] if feat else feature_id
    )
    feat_category = (
        feat["category"] if feat else None
    )
    technique_tier = (
        feat.get("technique_tier") if feat else None
    )

    # Get config from base variant record if available
    base_cap = db.query(VariantAICapability).filter_by(
        company_id=company_id,
        feature_id=feature_id,
        variant_type=variant_type,
        instance_id=None,
    ).first()

    if config_json is None and base_cap is not None:
        config = base_cap.config_json
    else:
        config = json.dumps(
            config_json if config_json else {}
        )

    override = VariantAICapability(
        company_id=company_id,
        variant_type=variant_type,
        instance_id=instance_id,
        feature_id=feature_id,
        feature_name=feat_name,
        feature_category=feat_category,
        technique_tier=technique_tier,
        is_enabled=is_enabled,
        config_json=config,
    )

    db.add(override)
    db.commit()
    db.refresh(override)
    return override


def remove_instance_override(
    db,
    company_id: str,
    feature_id: str,
    variant_type: str,
    instance_id: str,
) -> bool:
    """
    Remove a per-instance feature override.

    Returns True if the override was found and removed,
    False if no override existed.

    After removal, the feature falls back to the
    variant-type default setting.
    """
    _validate_company_id(company_id)
    _validate_variant_type(variant_type)

    if not instance_id or not instance_id.strip():
        raise ParwaBaseError(
            message="instance_id is required and cannot be empty",
            error_code="INVALID_INSTANCE_ID",
            status_code=400,
        )

    # Verify instance belongs to this company (BC-001)
    from database.models.variant_engine import VariantInstance
    instance = db.query(VariantInstance).filter(
        VariantInstance.id == instance_id,
        VariantInstance.company_id == company_id,
    ).first()
    if not instance:
        raise ParwaBaseError(
            status_code=404,
            error_code="INSTANCE_NOT_FOUND",
            detail="Instance not found",
        )

    override = db.query(VariantAICapability).filter_by(
        company_id=company_id,
        feature_id=feature_id,
        variant_type=variant_type,
        instance_id=instance_id,
    ).first()

    if override is None:
        return False

    db.delete(override)
    db.commit()
    return True


def get_entitlement_summary(
    db,
    company_id: str,
    variant_type: str,
    instance_id: str | None = None,
) -> dict:
    """
    Summary of what's enabled/disabled for a variant.

    Returns:
    {
        "variant_type": str,
        "instance_id": str | None,
        "total_features": int,
        "enabled_features": int,
        "disabled_features": int,
        "enabled_feature_ids": [str, ...],
        "disabled_feature_ids": [str, ...],
        "by_category": {
            category_name: {
                "enabled": int,
                "disabled": int,
            }
        }
    }
    """
    _validate_company_id(company_id)
    _validate_variant_type(variant_type)

    query = db.query(VariantAICapability).filter_by(
        company_id=company_id,
        variant_type=variant_type,
    )

    if instance_id is not None:
        query = query.filter_by(instance_id=instance_id)
    else:
        query = query.filter(
            VariantAICapability.instance_id.is_(None),
        )

    caps = query.all()

    enabled_ids = []
    disabled_ids = []
    by_category: dict = {}

    for cap in caps:
        cat = cap.feature_category or "unknown"
        if cat not in by_category:
            by_category[cat] = {
                "enabled": 0,
                "disabled": 0,
            }

        if cap.is_enabled:
            enabled_ids.append(cap.feature_id)
            by_category[cat]["enabled"] += 1
        else:
            disabled_ids.append(cap.feature_id)
            by_category[cat]["disabled"] += 1

    return {
        "variant_type": variant_type,
        "instance_id": instance_id,
        "total_features": len(caps),
        "enabled_features": len(enabled_ids),
        "disabled_features": len(disabled_ids),
        "enabled_feature_ids": sorted(enabled_ids),
        "disabled_feature_ids": sorted(disabled_ids),
        "by_category": by_category,
    }
