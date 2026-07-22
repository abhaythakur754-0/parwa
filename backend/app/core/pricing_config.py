"""
PARWA Pricing Configuration — SINGLE SOURCE OF TRUTH
═════════════════════════════════════════════════════════════════════════

This module is the **ONLY** place where pricing data, variant names,
and feature limits are defined. Every other module in the codebase
MUST import from here — never hard-code its own copy.

╔══════════════════════════════════════════════════════════════════╗
║  DO NOT duplicate these constants anywhere else.               ║
║  If you need pricing data → import from pricing_config.        ║
╚══════════════════════════════════════════════════════════════════╝

Pricing model: $1 = 1 ticket. What you pay is how many tickets you get.
All variants have the SAME AI capabilities. The only difference
is the ticket volume restriction.

Correct prices (as of this writing):
  ┌──────────┬──────────────────┬───────────────────┬──────────────┐
  │ Variant  │ Monthly (USD)    │ Annual (USD)      │ Tickets/mo   │
  ├──────────┼──────────────────┼───────────────────┼──────────────┤
  │ Mini     │ $999.00          │ $11,988.00        │ 999          │
  │ Parwa    │ $2,499.00        │ $29,988.00        │ 2,499        │
  │ High     │ $3,999.00        │ $47,988.00        │ 3,999        │
  └──────────┴──────────────────┴───────────────────┴──────────────┘

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

    Values are the canonical lowercase names: "mini", "parwa", "high".

    Old names (starter, growth, mini_parwa, parwa, parwa_high) are
    deprecated but still accepted via normalize_variant_name().
    """
    MINI = "mini"
    PARWA = "parwa"
    HIGH = "high"


# ══════════════════════════════════════════════════════════════════════════
# OLD NAME → CANONICAL NAME MAPPING
# ══════════════════════════════════════════════════════════════════════════

_VARIANT_NAME_ALIASES: Dict[str, str] = {
    # Old name              → Canonical name
    "mini_parwa":           "mini",
    "parwa":                "parwa",
    "parwa_high":           "high",
    # Also accept common variations
    "mini-parwa":           "mini",
    "parwa-high":           "high",
    "starter":              "mini",
    "growth":               "parwa",
    "mini":                 "mini",
    "high":                 "high",
}


# ══════════════════════════════════════════════════════════════════════════
# PRICES — monthly and annual
# ══════════════════════════════════════════════════════════════════════════

VARIANT_PRICES: Dict[VariantType, Decimal] = {
    VariantType.MINI:  Decimal("999.00"),
    VariantType.PARWA: Decimal("2499.00"),
    VariantType.HIGH:  Decimal("3999.00"),
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
    VariantType.MINI:  "Mini PARWA",
    VariantType.PARWA: "PARWA",
    VariantType.HIGH:  "PARWA High",
}


# ══════════════════════════════════════════════════════════════════════════
# VARIANT FEATURE LIMITS
# ══════════════════════════════════════════════════════════════════════════
#
# Pricing model: $1 = 1 ticket.
# All variants have the SAME AI capabilities.
# The only difference is the ticket volume ($1 = 1 ticket).
# Other limits (agents, team members, etc.) also differ by tier.

VARIANT_LIMITS: Dict[VariantType, Dict[str, Any]] = {
    VariantType.MINI: {
        "monthly_tickets": 999,
        "ai_agents":       0,
        "team_members":    3,
        "voice_slots":     0,
        "kb_docs":         100,
    },
    VariantType.PARWA: {
        "monthly_tickets": 2499,
        "ai_agents":       5,
        "team_members":    10,
        "voice_slots":     2,
        "kb_docs":         500,
    },
    VariantType.HIGH: {
        "monthly_tickets": 3999,
        "ai_agents":       8,  # 8 base, +$3/agent overage beyond this
        "team_members":    25,
        "voice_slots":     5,
        "kb_docs":         2000,
    },
}
"""
Feature limits per variant.

Keys per variant:
  monthly_tickets : int   — max support tickets per month ($1 = 1 ticket)
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
    VariantType.MINI:  1,
    VariantType.PARWA: 2,
    VariantType.HIGH:  3,
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
        >>> get_variant_price("mini")
        Decimal('999.00')
        >>> get_variant_price(VariantType.PARWA, "annual")
        Decimal('29988.00')
        >>> get_variant_price("starter")            # old name
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
      starter     → mini
      growth      → parwa
      mini_parwa  → mini
      parwa_high  → high

    Also handles common variations (hyphens, case differences).

    Args:
        name: Variant name string (old or new).

    Returns:
        Canonical lowercase variant name string.

    Raises:
        ValueError: If the name is not recognized.

    Examples:
        >>> normalize_variant_name("starter")
        'mini'
        >>> normalize_variant_name("parwa_high")
        'high'
        >>> normalize_variant_name("parwa")
        'parwa'
        >>> normalize_variant_name("MINI")
        'mini'
    """
    if not name or not isinstance(name, str):
        raise ValueError("Variant name must be a non-empty string.")

    key = name.lower().strip()
    canonical = _VARIANT_NAME_ALIASES.get(key)

    if canonical is None:
        raise ValueError(
            f"Unknown variant name '{name}'. "
            f"Valid names: mini, parwa, high. "
            f"Legacy aliases: starter, growth, mini_parwa, parwa, parwa_high."
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
        >>> get_variant_limits("mini")
        {'monthly_tickets': 999, 'ai_agents': 5, 'team_members': 3, 'voice_slots': 0, 'kb_docs': 100}
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