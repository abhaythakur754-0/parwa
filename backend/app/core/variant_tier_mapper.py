"""
Variant Tier Mapper: Maps onboarding variant selections to pipeline tiers.

The Models page shows 3 variant cards (Starter, Growth, High) per industry.
The Variant Engine has 3 pipeline tiers (mini_parwa, parwa, parwa_high).

This module bridges the two worlds:
  - Frontend/Onboarding: starter, growth, high
  - Backend/Pipeline: mini_parwa, parwa, parwa_high

Also maps industry labels from the frontend (E-commerce, SaaS, etc.)
to the enum values used by the Variant Engine (ecommerce, saas, etc.).

BC-001: company_id first parameter on public methods.
BC-008: Every function wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("variant_tier_mapper")


# ══════════════════════════════════════════════════════════════════
# MAPPING CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Frontend variant_id → Backend pipeline tier
VARIANT_ID_TO_TIER: Dict[str, str] = {
    "starter": "mini_parwa",
    "growth": "parwa",
    "high": "parwa_high",
}

# Backend pipeline tier → Frontend variant_id (reverse map)
TIER_TO_VARIANT_ID: Dict[str, str] = {
    "mini_parwa": "starter",
    "parwa": "growth",
    "parwa_high": "high",
}

# Frontend variant name → Backend pipeline tier
VARIANT_NAME_TO_TIER: Dict[str, str] = {
    "parwa starter": "mini_parwa",
    "parwa growth": "parwa",
    "parwa high": "parwa_high",
    "starter": "mini_parwa",
    "growth": "parwa",
    "high": "parwa_high",
}

# Frontend industry label → Backend enum value
INDUSTRY_LABEL_TO_ENUM: Dict[str, str] = {
    "e-commerce": "ecommerce",
    "ecommerce": "ecommerce",
    "e_commerce": "ecommerce",
    "saas": "saas",
    "logistics": "logistics",
    "others": "general",
    "other": "general",
    "general": "general",
}

# Pipeline tier metadata for display/context
TIER_METADATA: Dict[str, Dict[str, str]] = {
    "mini_parwa": {
        "display_name": "PARWA Starter",
        "tagline": "The 24/7 Trainee",
        "pipeline_nodes": "10",
        "techniques": "CLARA + CRP + GSD",
        "cost_per_query": "$0.003",
    },
    "parwa": {
        "display_name": "PARWA Growth",
        "tagline": "The Junior Agent",
        "pipeline_nodes": "15",
        "techniques": "CLARA + CRP + GSD + CoT + ReAct + Reverse Thinking",
        "cost_per_query": "$0.008",
    },
    "parwa_high": {
        "display_name": "PARWA High",
        "tagline": "The Senior Agent",
        "pipeline_nodes": "20",
        "techniques": "All 14 techniques",
        "cost_per_query": "$0.015",
    },
}


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════


def variant_id_to_tier(variant_id: str) -> str:
    """Map a frontend variant_id to a backend pipeline tier.

    Args:
        variant_id: Frontend variant identifier (starter, growth, high).

    Returns:
        Backend pipeline tier (mini_parwa, parwa, parwa_high).
        Defaults to 'mini_parwa' if unknown.
    """
    try:
        tier = VARIANT_ID_TO_TIER.get(variant_id.lower().strip(), "mini_parwa")
        logger.debug(
            "variant_id_to_tier: %s → %s",
            variant_id, tier,
        )
        return tier
    except Exception:
        logger.warning(
            "variant_id_to_tier failed for '%s' — defaulting to mini_parwa",
            variant_id,
        )
        return "mini_parwa"


def variant_name_to_tier(variant_name: str) -> str:
    """Map a frontend variant display name to a backend pipeline tier.

    Handles names like "PARWA Starter", "PARWA Growth", "PARWA High",
    as well as just "Starter", "Growth", "High".

    Args:
        variant_name: Frontend display name.

    Returns:
        Backend pipeline tier. Defaults to 'mini_parwa' if unknown.
    """
    try:
        key = variant_name.lower().strip()
        tier = VARIANT_NAME_TO_TIER.get(key, "mini_parwa")
        logger.debug(
            "variant_name_to_tier: %s → %s",
            variant_name, tier,
        )
        return tier
    except Exception:
        return "mini_parwa"


def industry_label_to_enum(industry_label: str) -> str:
    """Map a frontend industry label to the backend enum value.

    Handles various casings and formats:
      "E-commerce" → "ecommerce"
      "SaaS" → "saas"
      "Others" → "general"

    Args:
        industry_label: Frontend industry display string.

    Returns:
        Backend industry enum value. Defaults to 'general' if unknown.
    """
    try:
        key = industry_label.lower().strip().replace(" ", "_")
        enum_val = INDUSTRY_LABEL_TO_ENUM.get(key, "general")
        logger.debug(
            "industry_label_to_enum: %s → %s",
            industry_label, enum_val,
        )
        return enum_val
    except Exception:
        return "general"


def tier_to_variant_id(tier: str) -> str:
    """Map a backend pipeline tier to a frontend variant_id.

    Args:
        tier: Backend pipeline tier (mini_parwa, parwa, parwa_high).

    Returns:
        Frontend variant_id (starter, growth, high).
    """
    try:
        return TIER_TO_VARIANT_ID.get(tier, "starter")
    except Exception:
        return "starter"


def resolve_tier_from_context(
    variant_id: Optional[str] = None,
    variant_name: Optional[str] = None,
    selected_variants: Optional[List[Dict]] = None,
) -> str:
    """Resolve the highest variant tier from onboarding context data.

    Priority:
      1. Direct variant_id mapping
      2. Variant name mapping
      3. Highest tier from selected_variants list
      4. Default: mini_parwa

    This is the main entry point when processing onboarding context
    during the handoff from Onboarding Jarvis to Customer Care Jarvis.

    Args:
        variant_id: Frontend variant identifier.
        variant_name: Frontend variant display name.
        selected_variants: List of selected variant dicts from pricing page.

    Returns:
        Backend pipeline tier string.
    """
    try:
        # Priority 1: Direct variant_id
        if variant_id:
            tier = variant_id_to_tier(variant_id)
            if tier:
                logger.info(
                    "resolve_tier_from_context: variant_id=%s → tier=%s",
                    variant_id, tier,
                )
                return tier

        # Priority 2: Variant name
        if variant_name:
            tier = variant_name_to_tier(variant_name)
            if tier:
                logger.info(
                    "resolve_tier_from_context: variant_name=%s → tier=%s",
                    variant_name, tier,
                )
                return tier

        # Priority 3: Highest from selected_variants list
        if selected_variants and isinstance(selected_variants, list):
            highest_tier = "mini_parwa"
            tier_priority = {"mini_parwa": 1, "parwa": 2, "parwa_high": 3}

            for sel in selected_variants:
                if not isinstance(sel, dict):
                    continue
                # Try variant_id key
                vid = sel.get("variant_id") or sel.get("id") or sel.get("plan", "")
                if vid:
                    t = variant_id_to_tier(str(vid))
                    if tier_priority.get(t, 0) > tier_priority.get(highest_tier, 0):
                        highest_tier = t

            if highest_tier != "mini_parwa" or len(selected_variants) > 0:
                logger.info(
                    "resolve_tier_from_context: selected_variants → tier=%s",
                    highest_tier,
                )
                return highest_tier

        # Priority 4: Default
        logger.info(
            "resolve_tier_from_context: no context found → default=mini_parwa",
        )
        return "mini_parwa"

    except Exception:
        logger.exception(
            "resolve_tier_from_context failed — defaulting to mini_parwa",
        )
        return "mini_parwa"


def resolve_industry_from_context(
    industry: Optional[str] = None,
    entry_params: Optional[Dict] = None,
) -> str:
    """Resolve the industry enum value from onboarding context data.

    Handles various formats from the frontend:
      - "E-commerce" (display label)
      - "ecommerce" (already enum value)
      - entry_params.industry

    Args:
        industry: Industry string from session context.
        entry_params: Entry params dict that may contain industry.

    Returns:
        Backend industry enum value.
    """
    try:
        # Try direct industry value
        if industry:
            # Already an enum value?
            if industry.lower() in ("ecommerce", "logistics", "saas", "general"):
                return industry.lower()
            # Try label mapping
            mapped = industry_label_to_enum(industry)
            if mapped != "general" or industry.lower() == "general":
                return mapped

        # Try entry_params
        if entry_params and isinstance(entry_params, dict):
            ep_industry = entry_params.get("industry", "")
            if ep_industry:
                return resolve_industry_from_context(industry=ep_industry)

        return "general"

    except Exception:
        return "general"


def get_tier_metadata(tier: str) -> Dict[str, str]:
    """Get display metadata for a pipeline tier.

    Args:
        tier: Backend pipeline tier.

    Returns:
        Dict with display_name, tagline, pipeline_nodes, techniques, cost.
    """
    try:
        return TIER_METADATA.get(tier, TIER_METADATA["mini_parwa"])
    except Exception:
        return TIER_METADATA["mini_parwa"]
