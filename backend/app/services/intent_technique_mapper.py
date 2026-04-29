"""
Intent × Technique Mapper (F-149)

Maps classified intents to recommended AI techniques with variant-aware
tier filtering.

GAP FIX:
- W9-GAP-001 (CRITICAL): Variant-aware fallback ensures Mini PARWA never
  executes Tier 3 techniques.

Parent: Week 9 Day 6 (Monday)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.technique_router import (
    TechniqueID,
    TechniqueTier,
)
from app.logger import get_logger

logger = get_logger("intent_technique_mapper")


# ── Variant Tier Limits (GAP-001) ────────────────────────────────────

VARIANT_TIER_LIMITS: Dict[str, TechniqueTier] = {
    "mini_parwa": TechniqueTier.TIER_1,
    "parwa": TechniqueTier.TIER_2,
    "high_parwa": TechniqueTier.TIER_3,
}

# ── Tier 1 Fallbacks: when T2/T3 blocked, use T1 equivalent ─────────

TECHNIQUE_TIER1_FALLBACKS: Dict[TechniqueID, TechniqueID] = {
    # Tier 2 → Tier 1
    TechniqueID.CHAIN_OF_THOUGHT: TechniqueID.CRP,
    TechniqueID.REACT: TechniqueID.CRP,
    TechniqueID.REVERSE_THINKING: TechniqueID.CRP,
    TechniqueID.STEP_BACK: TechniqueID.GSD,
    TechniqueID.THREAD_OF_THOUGHT: TechniqueID.GSD,
    # Tier 3 → Tier 1
    TechniqueID.GST: TechniqueID.CLARA,
    TechniqueID.UNIVERSE_OF_THOUGHTS: TechniqueID.CLARA,
    TechniqueID.TREE_OF_THOUGHTS: TechniqueID.CLARA,
    TechniqueID.SELF_CONSISTENCY: TechniqueID.CRP,
    TechniqueID.REFLEXION: TechniqueID.GSD,
    TechniqueID.LEAST_TO_MOST: TechniqueID.CLARA,
}


# ── Data Classes ──────────────────────────────────────────────────────


@dataclass
class IntentTechniqueMapping:
    """Raw intent → technique mapping (before variant filtering)."""

    intent: str
    recommended_techniques: List[str]  # TechniqueID values
    recommended_tiers: List[str]  # TechniqueTier values
    trigger_conditions: str
    variant_override: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class MappingResult:
    """Output of variant-filtered intent → technique mapping."""

    intent: str
    selected_techniques: List[TechniqueID]
    selected_tiers: List[TechniqueTier]
    variant_type: str
    fallback_applied: bool
    blocked_techniques: List[Dict[str, str]]


# ── Intent Technique Mapping Table (F-149) ──────────────────────────

# 12 intent types × technique mappings
INTENT_TECHNIQUE_MAP: Dict[str, Dict[str, Any]] = {
    "refund": {
        "techniques": [TechniqueID.SELF_CONSISTENCY, TechniqueID.STEP_BACK],
        "tiers": [TechniqueTier.TIER_3, TechniqueTier.TIER_2],
        "trigger": "Monetary value involved — accuracy critical for refunds",
    },
    "technical": {
        "techniques": [TechniqueID.CHAIN_OF_THOUGHT, TechniqueID.REACT],
        "tiers": [TechniqueTier.TIER_2, TechniqueTier.TIER_2],
        "trigger": "Technical debugging requires step-by-step reasoning + tool calls",
    },
    "billing": {
        "techniques": [TechniqueID.SELF_CONSISTENCY],
        "tiers": [TechniqueTier.TIER_3],
        "trigger": "Financial accuracy required for billing queries",
    },
    "complaint": {
        "techniques": [TechniqueID.UNIVERSE_OF_THOUGHTS, TechniqueID.STEP_BACK],
        "tiers": [TechniqueTier.TIER_3, TechniqueTier.TIER_2],
        "trigger": "De-escalation + multiple solution paths for complaints",
    },
    "feature_request": {
        "techniques": [TechniqueID.CHAIN_OF_THOUGHT],
        "tiers": [TechniqueTier.TIER_2],
        "trigger": "Clear explanation of feature feasibility",
    },
    "general": {
        "techniques": [TechniqueID.CHAIN_OF_THOUGHT],
        "tiers": [TechniqueTier.TIER_2],
        "trigger": "Standard reasoning for general queries",
    },
    "cancellation": {
        "techniques": [TechniqueID.REVERSE_THINKING, TechniqueID.STEP_BACK],
        "tiers": [TechniqueTier.TIER_2, TechniqueTier.TIER_2],
        "trigger": "Explore alternatives before cancellation",
    },
    "shipping": {
        "techniques": [TechniqueID.REACT, TechniqueID.CHAIN_OF_THOUGHT],
        "tiers": [TechniqueTier.TIER_2, TechniqueTier.TIER_2],
        "trigger": "Track package + debug shipping issues",
    },
    "inquiry": {
        "techniques": [TechniqueID.CHAIN_OF_THOUGHT],
        "tiers": [TechniqueTier.TIER_2],
        "trigger": "Clear explanation needed for inquiries",
    },
    "escalation": {
        "techniques": [TechniqueID.REFLEXION, TechniqueID.UNIVERSE_OF_THOUGHTS],
        "tiers": [TechniqueTier.TIER_3, TechniqueTier.TIER_3],
        "trigger": "Self-check before escalating to human",
    },
    "account": {
        "techniques": [TechniqueID.CHAIN_OF_THOUGHT, TechniqueID.REACT],
        "tiers": [TechniqueTier.TIER_2, TechniqueTier.TIER_2],
        "trigger": "Step-by-step account verification",
    },
    "feedback": {
        "techniques": [TechniqueID.SELF_CONSISTENCY],
        "tiers": [TechniqueTier.TIER_3],
        "trigger": "Verify response quality for feedback",
    },
}


class IntentTechniqueMapper:
    """Maps classified intents to variant-filtered techniques (F-149).

    GAP-001 FIX: Variant-aware tier filtering ensures Mini PARWA
    never executes Tier 3 techniques. Blocked techniques fall back
    to Tier 1 equivalents.
    """

    def __init__(self):
        self._mappings = self._build_mappings()

    def _build_mappings(self) -> Dict[str, IntentTechniqueMapping]:
        """Build internal mapping table."""
        mappings: Dict[str, IntentTechniqueMapping] = {}
        for intent, config in INTENT_TECHNIQUE_MAP.items():
            techniques = config["techniques"]
            tiers = config["tiers"]
            trigger = config["trigger"]

            # Build variant overrides
            variant_override: Dict[str, List[str]] = {}
            for variant, tier_limit in VARIANT_TIER_LIMITS.items():
                filtered = []
                for tech, tier in zip(techniques, tiers):
                    tier_order = {
                        TechniqueTier.TIER_1: 1,
                        TechniqueTier.TIER_2: 2,
                        TechniqueTier.TIER_3: 3,
                    }
                    if tier_order.get(tier, 1) <= tier_order.get(tier_limit, 1):
                        filtered.append(tech.value)
                variant_override[variant] = filtered

            mappings[intent] = IntentTechniqueMapping(
                intent=intent,
                recommended_techniques=[t.value for t in techniques],
                recommended_tiers=[t.value for t in tiers],
                trigger_conditions=trigger,
                variant_override=variant_override,
            )
        return mappings

    def map_intent(
        self,
        intent: str,
        variant_type: str = "parwa",
        company_id: str = "",
    ) -> MappingResult:
        """Map an intent to variant-filtered techniques.

        GAP-001: Filters techniques by variant tier limit.
        Falls back to Tier 1 equivalents when blocked.
        """
        mapping = self._mappings.get(intent)
        if not mapping:
            return MappingResult(
                intent=intent,
                selected_techniques=[],
                selected_tiers=[],
                variant_type=variant_type,
                fallback_applied=False,
                blocked_techniques=[],
            )

        # Resolve techniques and tiers from the mapping
        technique_ids = [
            TechniqueID(t)
            for t in mapping.recommended_techniques
            if t in [tid.value for tid in TechniqueID]
        ]
        technique_tiers = [
            TechniqueTier(t)
            for t in mapping.recommended_tiers
            if t in [tid.value for tid in TechniqueTier]
        ]

        # Apply variant filtering (GAP-001)
        selected, selected_tiers, blocked = self._filter_by_variant(
            technique_ids,
            technique_tiers,
            variant_type,
        )

        logger.info(
            "intent_technique_mapping",
            intent=intent,
            variant=variant_type,
            selected=[t.value for t in selected],
            blocked_count=len(blocked),
            company_id=company_id,
        )

        return MappingResult(
            intent=intent,
            selected_techniques=selected,
            selected_tiers=selected_tiers,
            variant_type=variant_type,
            fallback_applied=len(blocked) > 0,
            blocked_techniques=blocked,
        )

    def _filter_by_variant(
        self,
        techniques: List[TechniqueID],
        tiers: List[TechniqueTier],
        variant_type: str,
    ) -> Tuple[List[TechniqueID], List[TechniqueTier], List[Dict[str, str]]]:
        """GAP-001: Filter techniques based on variant tier limit.

        Blocked techniques get substituted with Tier 1 fallbacks.
        """
        tier_limit = VARIANT_TIER_LIMITS.get(
            variant_type,
            TechniqueTier.TIER_1,
        )
        tier_order = {
            TechniqueTier.TIER_1: 1,
            TechniqueTier.TIER_2: 2,
            TechniqueTier.TIER_3: 3,
        }
        limit_order = tier_order.get(tier_limit, 1)

        selected: List[TechniqueID] = []
        selected_tiers: List[TechniqueTier] = []
        blocked: List[Dict[str, str]] = []
        seen_fallbacks: Set[TechniqueID] = set()

        for tech, tier in zip(techniques, tiers):
            tech_order = tier_order.get(tier, 1)
            if tech_order <= limit_order:
                selected.append(tech)
                selected_tiers.append(tier)
            else:
                # Technique blocked — find T1 fallback
                fallback = TECHNIQUE_TIER1_FALLBACKS.get(tech)
                fallback_reason = f"Tier {tier_order} exceeds variant limit ({
                    tier_limit.value})"
                entry = {
                    "id": tech.value,
                    "reason": fallback_reason,
                    "fallback": fallback.value if fallback else None,
                }
                blocked.append(entry)

                if fallback and fallback not in seen_fallbacks:
                    selected.append(fallback)
                    selected_tiers.append(TechniqueTier.TIER_1)
                    seen_fallbacks.add(fallback)

        return selected, selected_tiers, blocked

    def get_mapping(self, intent: str) -> Optional[IntentTechniqueMapping]:
        """Get raw mapping without variant filtering."""
        return self._mappings.get(intent)

    def get_all_mappings(self) -> Dict[str, IntentTechniqueMapping]:
        """Get all intent→technique mappings."""
        return dict(self._mappings)

    def get_supported_intents(self) -> List[str]:
        """List all supported intent types."""
        return sorted(self._mappings.keys())

    @staticmethod
    def get_variant_tier_limit(variant_type: str) -> TechniqueTier:
        """Get the max technique tier for a variant."""
        return VARIANT_TIER_LIMITS.get(variant_type, TechniqueTier.TIER_1)
