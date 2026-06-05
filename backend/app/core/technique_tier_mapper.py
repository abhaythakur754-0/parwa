"""
Technique Tier Mapper (Day 5 — AI-16)

Maps technique selection to variant tiers. Controls which AI reasoning
techniques are available per product tier, maximum LLM calls, and
timeouts.

Tier Definitions:
  - Mini PARWA ($999/mo):  1 technique, 1-2 LLM calls, 3s timeout
  - PARWA ($2,499/mo):     Best single technique, 2-4 LLM calls, 8s timeout
  - PARWA High ($3,999/mo): Multi-technique + MAKER + FAKE, 6-24 LLM calls, no hard limit

BC-001: All operations scoped to company_id.
BC-008: Always returns a valid technique, never crashes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("technique_tier_mapper")

# ── Intent Types ────────────────────────────────────────────────────

INTENT_TYPES = [
    "refund",
    "technical",
    "billing",
    "complaint",
    "faq",
    "cancellation",
    "shipping",
    "account",
    "general",
]

# ── Technique Names ─────────────────────────────────────────────────

TECHNIQUE_CHAIN_OF_THOUGHT = "chain_of_thought"
TECHNIQUE_REACT = "react"
TECHNIQUE_SELF_CONSISTENCY = "self_consistency"
TECHNIQUE_TREE_OF_THOUGHT = "tree_of_thought"
TECHNIQUE_REFLEXION = "reflexion"
TECHNIQUE_STEP_BACK = "step_back"
TECHNIQUE_LEAST_TO_MOST = "least_to_most"
TECHNIQUE_REVERSE_THINKING = "reverse_thinking"

# ── Intent → Technique Mapping per Tier ─────────────────────────────

INTENT_TECHNIQUE_MAP: Dict[str, Dict[str, str]] = {
    "mini_parwa": {
        # All intents use CoT — fastest, simplest
        "refund": TECHNIQUE_CHAIN_OF_THOUGHT,
        "technical": TECHNIQUE_CHAIN_OF_THOUGHT,
        "billing": TECHNIQUE_CHAIN_OF_THOUGHT,
        "complaint": TECHNIQUE_CHAIN_OF_THOUGHT,
        "faq": TECHNIQUE_CHAIN_OF_THOUGHT,
        "cancellation": TECHNIQUE_CHAIN_OF_THOUGHT,
        "shipping": TECHNIQUE_CHAIN_OF_THOUGHT,
        "account": TECHNIQUE_CHAIN_OF_THOUGHT,
        "general": TECHNIQUE_CHAIN_OF_THOUGHT,
    },
    "parwa": {
        # Best single technique per intent
        "refund": TECHNIQUE_SELF_CONSISTENCY,
        "technical": TECHNIQUE_REACT,
        "billing": TECHNIQUE_CHAIN_OF_THOUGHT,
        "complaint": TECHNIQUE_REFLEXION,
        "faq": TECHNIQUE_CHAIN_OF_THOUGHT,
        "cancellation": TECHNIQUE_STEP_BACK,
        "shipping": TECHNIQUE_REACT,
        "account": TECHNIQUE_CHAIN_OF_THOUGHT,
        "general": TECHNIQUE_CHAIN_OF_THOUGHT,
    },
    "parwa_high": {
        # Full multi-technique composition — MAKER handles technique selection
        "refund": TECHNIQUE_SELF_CONSISTENCY,
        "technical": TECHNIQUE_REACT,
        "billing": TECHNIQUE_LEAST_TO_MOST,
        "complaint": TECHNIQUE_REFLEXION,
        "faq": TECHNIQUE_CHAIN_OF_THOUGHT,
        "cancellation": TECHNIQUE_STEP_BACK,
        "shipping": TECHNIQUE_REACT,
        "account": TECHNIQUE_REVERSE_THINKING,
        "general": TECHNIQUE_TREE_OF_THOUGHT,
    },
}

# ── Tier Configuration ──────────────────────────────────────────────

TIER_CONFIG: Dict[str, Dict[str, Any]] = {
    "mini_parwa": {
        "primary_technique": TECHNIQUE_CHAIN_OF_THOUGHT,
        "available_techniques": [TECHNIQUE_CHAIN_OF_THOUGHT],
        "max_llm_calls": 2,
        "timeout_ms": 3000,
        "maker_enabled": False,
        "fake_voting_enabled": False,
        "compression_enabled": False,
        "hyde_enabled": False,
        "multi_query_enabled": False,
    },
    "parwa": {
        "primary_technique": TECHNIQUE_CHAIN_OF_THOUGHT,
        "available_techniques": [
            TECHNIQUE_CHAIN_OF_THOUGHT,
            TECHNIQUE_REACT,
            TECHNIQUE_SELF_CONSISTENCY,
            TECHNIQUE_REFLEXION,
            TECHNIQUE_STEP_BACK,
        ],
        "max_llm_calls": 4,
        "timeout_ms": 8000,
        "maker_enabled": True,
        "maker_k": 3,
        "fake_voting_enabled": False,
        "compression_enabled": True,
        "hyde_enabled": False,
        "multi_query_enabled": True,
    },
    "parwa_high": {
        "primary_technique": TECHNIQUE_TREE_OF_THOUGHT,
        "available_techniques": [
            TECHNIQUE_CHAIN_OF_THOUGHT,
            TECHNIQUE_REACT,
            TECHNIQUE_SELF_CONSISTENCY,
            TECHNIQUE_TREE_OF_THOUGHT,
            TECHNIQUE_REFLEXION,
            TECHNIQUE_STEP_BACK,
            TECHNIQUE_LEAST_TO_MOST,
            TECHNIQUE_REVERSE_THINKING,
        ],
        "max_llm_calls": 24,
        "timeout_ms": 0,  # No hard limit — quality over speed
        "maker_enabled": True,
        "maker_k": 7,
        "fake_voting_enabled": True,
        "compression_enabled": True,
        "hyde_enabled": True,
        "multi_query_enabled": True,
    },
}


@dataclass
class TierTechniqueConfig:
    """Resolved technique configuration for a specific tier + intent."""

    variant_tier: str
    intent: str
    primary_technique: str
    available_techniques: List[str]
    max_llm_calls: int
    timeout_ms: int
    maker_enabled: bool
    fake_voting_enabled: bool
    compression_enabled: bool
    hyde_enabled: bool
    multi_query_enabled: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_tier": self.variant_tier,
            "intent": self.intent,
            "primary_technique": self.primary_technique,
            "available_techniques": self.available_techniques,
            "max_llm_calls": self.max_llm_calls,
            "timeout_ms": self.timeout_ms,
            "maker_enabled": self.maker_enabled,
            "fake_voting_enabled": self.fake_voting_enabled,
            "compression_enabled": self.compression_enabled,
            "hyde_enabled": self.hyde_enabled,
            "multi_query_enabled": self.multi_query_enabled,
        }


def get_technique_for_tier(
    intent: str, variant_tier: str = "parwa"
) -> str:
    """Get the recommended technique for an intent at a given tier.

    BC-008: Always returns a valid technique name, never crashes.

    Args:
        intent: Customer intent type (e.g. 'refund', 'technical').
        variant_tier: Product tier (mini_parwa, parwa, parwa_high).

    Returns:
        Technique name string.
    """
    tier_map = INTENT_TECHNIQUE_MAP.get(variant_tier)
    if tier_map is None:
        logger.warning(
            "tier_mapper_unknown_tier_defaulting_to_parwa",
            variant_tier=variant_tier,
        )
        tier_map = INTENT_TECHNIQUE_MAP["parwa"]

    technique = tier_map.get(intent)
    if technique is None:
        logger.debug(
            "tier_mapper_unknown_intent_defaulting_to_cot",
            intent=intent,
            variant_tier=variant_tier,
        )
        technique = TECHNIQUE_CHAIN_OF_THOUGHT

    return technique


def get_max_llm_calls(variant_tier: str) -> int:
    """Get maximum LLM calls allowed for a tier.

    BC-008: Returns conservative default for unknown tiers.
    """
    config = TIER_CONFIG.get(variant_tier)
    if config is None:
        return 2
    return config["max_llm_calls"]


def get_timeout_ms(variant_tier: str) -> int:
    """Get maximum timeout in milliseconds for a tier.

    Returns 0 for no hard limit (parwa_high).
    BC-008: Returns 3000ms for unknown tiers.
    """
    config = TIER_CONFIG.get(variant_tier)
    if config is None:
        return 3000
    return config["timeout_ms"]


def get_tier_config(variant_tier: str) -> Dict[str, Any]:
    """Get full tier configuration.

    BC-008: Returns parwa config for unknown tiers.
    """
    return TIER_CONFIG.get(variant_tier, TIER_CONFIG["parwa"])


def resolve_technique_config(
    intent: str, variant_tier: str = "parwa"
) -> TierTechniqueConfig:
    """Resolve full technique configuration for tier + intent.

    BC-008: Always returns a valid config, never crashes.

    Args:
        intent: Customer intent type.
        variant_tier: Product tier.

    Returns:
        TierTechniqueConfig with all resolved settings.
    """
    config = get_tier_config(variant_tier)
    technique = get_technique_for_tier(intent, variant_tier)

    return TierTechniqueConfig(
        variant_tier=variant_tier,
        intent=intent,
        primary_technique=technique,
        available_techniques=config["available_techniques"],
        max_llm_calls=config["max_llm_calls"],
        timeout_ms=config["timeout_ms"],
        maker_enabled=config["maker_enabled"],
        fake_voting_enabled=config["fake_voting_enabled"],
        compression_enabled=config["compression_enabled"],
        hyde_enabled=config["hyde_enabled"],
        multi_query_enabled=config["multi_query_enabled"],
    )
