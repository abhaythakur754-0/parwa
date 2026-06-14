"""
PARWA Pricing Configuration — SINGLE SOURCE OF TRUTH
═══════════════════════════════════════════════════════════════════════

This module is the **ONLY** place where pricing data, variant names,
and feature limits are defined. Every other module in the codebase
MUST import from here — never hard-code its own copy.

╔══════════════════════════════════════════════════════════════════╗
║  DO NOT duplicate these constants anywhere else.               ║
║  If you need pricing data → import from pricing_config.        ║
╚══════════════════════════════════════════════════════════════════╝

Problems this module fixes (historical bugs found across the codebase):

  1. entitlement_middleware.py — PLAN_PRICING had WRONG prices:
     mini_parwa=$499 (should be $999), parwa_high=$9,999 (should be $3,999)
  2. variant_limit_service.py — _HARDCODED_LIMITS stored prices as
     strings ("999.00") instead of Decimal — precision risk.
  3. pricing_service.py — calculate_totals() gave 2 months free
     on annual (10× monthly) — NO discounts are authorized.
  4. Old variant names (mini_parwa, parwa, parwa_high) were used
     alongside new names (starter, growth, high) with no mapping.
  5. billing_extended.py used key "price_monthly" while billing.py
     used "price" — inconsistent keys across modules.

Correct prices (as of this writing):
  ┌──────────┬──────────────────┬───────────────────┐
  │ Variant  │ Monthly (USD)    │ Annual (USD)      │
  ├──────────┼──────────────────┼───────────────────┤
  │ Starter  │ $999.00          │ $11,988.00        │
  │ Growth   │ $2,499.00        │ $29,988.00        │
  │ High     │ $3,999.00        │ $47,988.00        │
  └──────────┴──────────────────┴───────────────────┘

Annual = 12 × monthly.  NO discounts.  NO free months.

Building Codes:
  BC-002: All money values use Decimal — never float or int.
"""

from decimal import Decimal
from enum import Enum
from typing import Dict, Any


# ══════════════════════════════════════════════════════════════════════════
# VARIANT TYPE ENUM
# ══════════════════════════════════════════════════════════════════════════

class VariantType(str, Enum):
    """
    PARWA subscription variant types.

    Values are the canonical (new) lowercase names used everywhere
    in the codebase: "starter", "growth", "high".

    Old names (mini_parwa, parwa, parwa_high) are deprecated but
    still accepted via normalize_variant_name().
    """
    STARTER = "starter"
    GROWTH = "growth"
    HIGH = "high"


# ══════════════════════════════════════════════════════════════════════════
# OLD NAME → NEW NAME MAPPING
# ══════════════════════════════════════════════════════════════════════════

_VARIANT_NAME_ALIASES: Dict[str, str] = {
    # Old name         → New canonical name
    "mini_parwa":       "starter",
    "parwa":            "growth",
    "parwa_high":       "high",
    # Also accept common variations
    "mini-parwa":       "starter",
    "parwa-high":       "high",
    "starter":          "starter",
    "growth":           "growth",
    "high":             "high",
}


# ══════════════════════════════════════════════════════════════════════════
# PRICES — monthly and annual
# ══════════════════════════════════════════════════════════════════════════

VARIANT_PRICES: Dict[VariantType, Decimal] = {
    VariantType.STARTER: Decimal("999.00"),
    VariantType.GROWTH:  Decimal("2499.00"),
    VariantType.HIGH:    Decimal("3999.00"),
}
"""
Monthly prices per variant (USD).

BC-002: All values are Decimal — never float or int.
"""

VARIANT_ANNUAL_PRICES: Dict[VariantType, Decimal] = {
    variant: price * Decimal("12")
    for variant, price in VARIANT_PRICES.items()
}
"""
Annual prices per variant (USD).

Annual = 12 × monthly.  NO discounts.  NO free months.
"""


# ══════════════════════════════════════════════════════════════════════════
# DISPLAY NAMES — for UI/upgrade nudges
# ══════════════════════════════════════════════════════════════════════════

VARIANT_DISPLAY_NAMES: Dict[VariantType, str] = {
    VariantType.STARTER: "Starter",
    VariantType.GROWTH:  "Growth",
    VariantType.HIGH:    "High",
}


# ══════════════════════════════════════════════════════════════════════════
# VARIANT FEATURE LIMITS
# ══════════════════════════════════════════════════════════════════════════

VARIANT_LIMITS: Dict[VariantType, Dict[str, Any]] = {
    VariantType.STARTER: {
        "monthly_tickets": 2000,
        "ai_agents":       1,
        "team_members":    3,
        "voice_slots":     0,
        "kb_docs":         100,
    },
    VariantType.GROWTH: {
        "monthly_tickets": 5000,
        "ai_agents":       3,
        "team_members":    10,
        "voice_slots":     2,
        "kb_docs":         500,
    },
    VariantType.HIGH: {
        "monthly_tickets": 15000,
        "ai_agents":       5,
        "team_members":    25,
        "voice_slots":     5,
        "kb_docs":         2000,
    },
}
"""
Feature limits per variant.

Keys per variant:
  monthly_tickets : int   — max support tickets per month
  ai_agents       : int   — max AI agents
  team_members    : int   — max team members
  voice_slots     : int   — max concurrent voice/call slots
  kb_docs         : int   — max knowledge-base documents

Prices are NOT included here — use VARIANT_PRICES or get_variant_price().
This separation prevents accidental use of limits when prices are needed
(and vice-versa).
"""

# Tier ordering for upgrade/downgrade logic
VARIANT_TIER_ORDER: Dict[VariantType, int] = {
    VariantType.STARTER: 1,
    VariantType.GROWTH:  2,
    VariantType.HIGH:    3,
}


# ══════════════════════════════════════════════════════════════════════════
# PUBLIC API FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════

def get_variant_price(
    variant: VariantType | str,
    billing_cycle: str = "monthly",
) -> Decimal:
    """
    Get the price for a variant and billing cycle.

    Args:
        variant:       VariantType enum or string name (old or new).
        billing_cycle: "monthly" or "annual".

    Returns:
        Decimal price in USD.

    Raises:
        ValueError: If variant or billing_cycle is invalid.

    Examples:
        >>> get_variant_price("starter")
        Decimal('999.00')
        >>> get_variant_price(VariantType.GROWTH, "annual")
        Decimal('29988.00')
        >>> get_variant_price("mini_parwa")          # old name
        Decimal('999.00')
        >>> get_variant_price("parwa_high", "annual")
        Decimal('47988.00')
    """
    # Normalize string to VariantType if needed
    if isinstance(variant, str):
        normalized = normalize_variant_name(variant)
        variant = VariantType(normalized)

    cycle = billing_cycle.lower().strip()
    if cycle == "monthly":
        return VARIANT_PRICES[variant]
    elif cycle == "annual":
        return VARIANT_ANNUAL_PRICES[variant]
    else:
        raise ValueError(
            f"Invalid billing_cycle '{billing_cycle}'. "
            f"Must be 'monthly' or 'annual'."
        )


def normalize_variant_name(name: str) -> str:
    """
    Normalize a variant name to its canonical form.

    Maps old names to new:
      mini_parwa  → starter
      parwa       → growth
      parwa_high  → high

    Also handles common variations (hyphens, case differences).

    Args:
        name: Variant name string (old or new).

    Returns:
        Canonical lowercase variant name string.

    Raises:
        ValueError: If the name is not recognized.

    Examples:
        >>> normalize_variant_name("mini_parwa")
        'starter'
        >>> normalize_variant_name("parwa_high")
        'high'
        >>> normalize_variant_name("growth")
        'growth'
        >>> normalize_variant_name("STARTER")
        'starter'
    """
    if not name or not isinstance(name, str):
        raise ValueError("Variant name must be a non-empty string.")

    key = name.lower().strip()
    canonical = _VARIANT_NAME_ALIASES.get(key)

    if canonical is None:
        raise ValueError(
            f"Unknown variant name '{name}'. "
            f"Valid names: starter, growth, high. "
            f"Legacy aliases: mini_parwa, parwa, parwa_high."
        )

    return canonical


def get_variant_limits(variant: VariantType | str) -> Dict[str, Any]:
    """
    Get the feature limits for a variant.

    Args:
        variant: VariantType enum or string name (old or new).

    Returns:
        Dict with keys: monthly_tickets, ai_agents, team_members,
        voice_slots, kb_docs.

    Raises:
        ValueError: If the variant is invalid.

    Examples:
        >>> get_variant_limits("starter")
        {'monthly_tickets': 2000, 'ai_agents': 1, 'team_members': 3, 'voice_slots': 0, 'kb_docs': 100}
        >>> get_variant_limits("parwa_high")["voice_slots"]
        5
    """
    if isinstance(variant, str):
        normalized = normalize_variant_name(variant)
        variant = VariantType(normalized)

    return dict(VARIANT_LIMITS[variant])  # return a copy to prevent mutation


def is_upgrade(old_variant: str, new_variant: str) -> bool:
    """
    Check whether moving from old_variant to new_variant is an upgrade.

    Args:
        old_variant: Current variant name (old or new format).
        new_variant: Target variant name (old or new format).

    Returns:
        True if new_variant is a higher tier than old_variant.

    Raises:
        ValueError: If either variant name is invalid.
    """
    old_norm = VariantType(normalize_variant_name(old_variant))
    new_norm = VariantType(normalize_variant_name(new_variant))
    return VARIANT_TIER_ORDER[new_norm] > VARIANT_TIER_ORDER[old_norm]


def get_all_variant_info(variant: VariantType | str) -> Dict[str, Any]:
    """
    Get comprehensive info for a variant: price, limits, and display name.

    Convenience function that combines get_variant_price and get_variant_limits.

    Args:
        variant: VariantType enum or string name (old or new).

    Returns:
        Dict with: variant, display_name, monthly_price, annual_price,
        monthly_tickets, ai_agents, team_members, voice_slots, kb_docs.
    """
    if isinstance(variant, str):
        normalized = normalize_variant_name(variant)
        variant = VariantType(normalized)

    return {
        "variant":        variant.value,
        "display_name":   VARIANT_DISPLAY_NAMES[variant],
        "monthly_price":  VARIANT_PRICES[variant],
        "annual_price":   VARIANT_ANNUAL_PRICES[variant],
        **VARIANT_LIMITS[variant],
    }
