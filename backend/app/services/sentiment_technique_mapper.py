"""
Sentiment × Technique Trigger Mapping (F-151)

Maps sentiment ranges to recommended AI reasoning techniques.

Rules:
- Frustration < 30 → UoT + Step-Back (explore solutions broadly)
- Frustration 30-60 → Step-Back only (pause and reconsider)
- Frustration 60-80 → Reflexion (self-check) + Step-Back
- Frustration 80+ → CLARA enhanced + human escalation flag
- Positive sentiment (>0.7) → standard CoT (no heavy techniques)
- Urgency critical → bypass technique selection, direct routing
- VIP + high frustration → UoT + Reflexion + Step-Back

Per-variant filtering:
- mini_parwa cannot access Tier 3 techniques (GAP-001 pattern)

Parent: Week 9 Day 7 (Sunday)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.app.core.technique_router import (
    TechniqueID,
    TechniqueTier,
)
from backend.app.logger import get_logger

logger = get_logger("sentiment_technique_mapper")


# ── Variant Tier Limits (same as intent_technique_mapper GAP-001) ────

VARIANT_TIER_LIMITS: Dict[str, TechniqueTier] = {
    "mini_parwa": TechniqueTier.TIER_1,
    "parwa": TechniqueTier.TIER_2,
    "parwa_high": TechniqueTier.TIER_3,
}

# ── Tier → Technique Info ───────────────────────────────────────────

TECHNIQUE_TIERS: Dict[TechniqueID, TechniqueTier] = {
    TechniqueID.CLARA: TechniqueTier.TIER_1,
    TechniqueID.CRP: TechniqueTier.TIER_1,
    TechniqueID.GSD: TechniqueTier.TIER_1,
    TechniqueID.CHAIN_OF_THOUGHT: TechniqueTier.TIER_2,
    TechniqueID.REVERSE_THINKING: TechniqueTier.TIER_2,
    TechniqueID.REACT: TechniqueTier.TIER_2,
    TechniqueID.STEP_BACK: TechniqueTier.TIER_2,
    TechniqueID.THREAD_OF_THOUGHT: TechniqueTier.TIER_2,
    TechniqueID.GST: TechniqueTier.TIER_3,
    TechniqueID.UNIVERSE_OF_THOUGHTS: TechniqueTier.TIER_3,
    TechniqueID.TREE_OF_THOUGHTS: TechniqueTier.TIER_3,
    TechniqueID.SELF_CONSISTENCY: TechniqueTier.TIER_3,
    TechniqueID.REFLEXION: TechniqueTier.TIER_3,
    TechniqueID.LEAST_TO_MOST: TechniqueTier.TIER_3,
}

TIER_ORDER = {
    TechniqueTier.TIER_1: 1,
    TechniqueTier.TIER_2: 2,
    TechniqueTier.TIER_3: 3,
}

# ── Tier 1 Fallbacks (same as intent_technique_mapper) ──────────────

TECHNIQUE_TIER1_FALLBACKS: Dict[TechniqueID, TechniqueID] = {
    TechniqueID.CHAIN_OF_THOUGHT: TechniqueID.CRP,
    TechniqueID.REACT: TechniqueID.CRP,
    TechniqueID.REVERSE_THINKING: TechniqueID.CRP,
    TechniqueID.STEP_BACK: TechniqueID.GSD,
    TechniqueID.THREAD_OF_THOUGHT: TechniqueID.GSD,
    TechniqueID.GST: TechniqueID.CLARA,
    TechniqueID.UNIVERSE_OF_THOUGHTS: TechniqueID.CLARA,
    TechniqueID.TREE_OF_THOUGHTS: TechniqueID.CLARA,
    TechniqueID.SELF_CONSISTENCY: TechniqueID.CRP,
    TechniqueID.REFLEXION: TechniqueID.GSD,
    TechniqueID.LEAST_TO_MOST: TechniqueID.CLARA,
}


# ── Data Classes ─────────────────────────────────────────────────────


@dataclass
class SentimentMappingResult:
    """Output of sentiment × technique mapping (F-151)."""

    recommended_techniques: List[TechniqueID]
    technique_reasons: Dict[str, str]  # technique_id.value → reason
    priority_override: bool
    escalation_recommended: bool
    tone_adjustments: List[str]
    variant_type: str = "parwa"
    blocked_techniques: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "recommended_techniques": [t.value for t in self.recommended_techniques],
            "technique_reasons": self.technique_reasons,
            "priority_override": self.priority_override,
            "escalation_recommended": self.escalation_recommended,
            "tone_adjustments": self.tone_adjustments,
            "variant_type": self.variant_type,
            "blocked_techniques": self.blocked_techniques,
        }


# ── Sentiment Technique Mapper ──────────────────────────────────────


class SentimentTechniqueMapper:
    """Maps sentiment ranges to recommended AI techniques (F-151).

    Rules:
    - Frustration < 30 + positive → UoT + Step-Back (explore broadly)
    - Frustration 30-60 → Step-Back only
    - Frustration 60-80 → Reflexion + Step-Back
    - Frustration 80+ → CLARA enhanced + escalation flag
    - Positive (>0.7) → CoT (no heavy techniques)
    - Critical urgency → bypass, direct routing
    - VIP + high frustration → UoT + Reflexion + Step-Back

    Per-variant: mini_parwa cannot access Tier 3 techniques.
    """

    def map(
        self,
        frustration_score: float,
        sentiment_score: float,
        urgency_level: str,
        customer_tier: str = "free",
        emotion: str = "neutral",
        is_vip: bool = False,
        variant_type: str = "parwa",
        company_id: str = "",
    ) -> SentimentMappingResult:
        """Map sentiment signals to recommended techniques.

        Args:
            frustration_score: 0-100 frustration score.
            sentiment_score: 0.0-1.0 sentiment (from signal_extraction.py).
            urgency_level: low, medium, high, critical.
            customer_tier: free, pro, enterprise, vip.
            emotion: Primary emotion classification.
            is_vip: Whether customer is VIP.
            variant_type: mini_parwa, parwa, parwa_high.
            company_id: Tenant identifier (BC-001).

        Returns:
            SentimentMappingResult with techniques, reasons, and flags.
        """
        recommended: List[TechniqueID] = []
        reasons: Dict[str, str] = {}
        tone_adjustments: List[str] = []
        priority_override = False
        escalation_recommended = False
        blocked: List[Dict[str, Any]] = []

        # ── Rule 1: Critical urgency → bypass technique selection ──
        if urgency_level == "critical":
            priority_override = True
            escalation_recommended = True
            tone_adjustments.append("immediate_acknowledgment_required")
            tone_adjustments.append("escalation_protocol_active")
            # For critical, still recommend some techniques but flag override
            recommended.append(TechniqueID.CHAIN_OF_THOUGHT)
            reasons[TechniqueID.CHAIN_OF_THOUGHT.value] = (
                "Critical urgency — ensure clear step-by-step response"
            )
            recommended.append(TechniqueID.STEP_BACK)
            reasons[TechniqueID.STEP_BACK.value] = (
                "Critical urgency — reassess full situation before responding"
            )
        # ── Rule 2: Very high frustration (80+) → escalation ──────
        elif frustration_score >= 80:
            escalation_recommended = True
            recommended.append(TechniqueID.CLARA)
            reasons[TechniqueID.CLARA.value] = (
                "High frustration — enhanced quality gate for de-escalation"
            )
            recommended.append(TechniqueID.STEP_BACK)
            reasons[TechniqueID.STEP_BACK.value] = (
                "High frustration — pause and reassess before response"
            )
            tone_adjustments.append("extreme_empathy_required")
            tone_adjustments.append("de_escalation_priority")

            # VIP + high frustration → additional techniques
            if is_vip or customer_tier == "vip":
                recommended.append(TechniqueID.UNIVERSE_OF_THOUGHTS)
                reasons[TechniqueID.UNIVERSE_OF_THOUGHTS.value] = (
                    "VIP + high frustration — explore all solution paths"
                )
                recommended.append(TechniqueID.REFLEXION)
                reasons[TechniqueID.REFLEXION.value] = (
                    "VIP + high frustration — self-check before response"
                )
                tone_adjustments.append("vip_escalation_protocol")

        # ── Rule 3: High frustration (60-80) ──────────────────────
        elif frustration_score >= 60:
            recommended.append(TechniqueID.REFLEXION)
            reasons[TechniqueID.REFLEXION.value] = (
                "Elevated frustration — self-correction before responding"
            )
            recommended.append(TechniqueID.STEP_BACK)
            reasons[TechniqueID.STEP_BACK.value] = (
                "Elevated frustration — broader context assessment"
            )
            tone_adjustments.append("empathetic_tone_required")

            if is_vip or customer_tier == "vip":
                recommended.append(TechniqueID.UNIVERSE_OF_THOUGHTS)
                reasons[TechniqueID.UNIVERSE_OF_THOUGHTS.value] = (
                    "VIP + elevated frustration — comprehensive solution exploration"
                )

        # ── Rule 4: Moderate frustration (30-60) ──────────────────
        elif frustration_score >= 30:
            recommended.append(TechniqueID.STEP_BACK)
            reasons[TechniqueID.STEP_BACK.value] = (
                "Moderate frustration — pause and reconsider approach"
            )
            if emotion in ("angry", "frustrated"):
                tone_adjustments.append("cautious_tone_advised")

        # ── Rule 5: Low frustration (<30) + positive ──────────────
        elif sentiment_score > 0.7:
            # Positive sentiment → standard CoT, no heavy techniques
            recommended.append(TechniqueID.CHAIN_OF_THOUGHT)
            reasons[TechniqueID.CHAIN_OF_THOUGHT.value] = (
                "Positive sentiment — standard reasoning sufficient"
            )
            if sentiment_score > 0.9:
                recommended.append(TechniqueID.UNIVERSE_OF_THOUGHTS)
                reasons[TechniqueID.UNIVERSE_OF_THOUGHTS.value] = (
                    "Very positive — explore solutions broadly to delight customer"
                )
                tone_adjustments.append("warm_friendly_tone")

        # ── Rule 6: Low frustration (<30) + neutral/negative ──────
        else:
            # G9-GAP-04 FIX: Use Tier 2 techniques (Step-Back + CoT) instead
            # of Tier 3 (UoT) to avoid unnecessary Tier blocking on mini_parwa
            recommended.append(TechniqueID.CHAIN_OF_THOUGHT)
            reasons[TechniqueID.CHAIN_OF_THOUGHT.value] = (
                "Low frustration — standard reasoning with structured approach"
            )
            recommended.append(TechniqueID.STEP_BACK)
            reasons[TechniqueID.STEP_BACK.value] = (
                "Low frustration — consider multiple approaches"
            )

        # ── VIP special handling (not already covered above) ──────
        if (is_vip or customer_tier == "vip") and frustration_score < 60:
            # Add Reflexion for VIP even at lower frustration
            if TechniqueID.REFLEXION not in recommended:
                recommended.append(TechniqueID.REFLEXION)
                reasons[TechniqueID.REFLEXION.value] = (
                    "VIP customer — enhanced self-check for quality"
                )

        # ── Deduplicate ───────────────────────────────────────────
        seen = set()
        deduped = []
        for t in recommended:
            if t not in seen:
                seen.add(t)
                deduped.append(t)
        recommended = deduped

        # ── Apply variant filtering (GAP-001) ────────────────────
        tier_limit = VARIANT_TIER_LIMITS.get(variant_type, TechniqueTier.TIER_1)
        limit_order = TIER_ORDER.get(tier_limit, 1)

        filtered: List[TechniqueID] = []
        seen_fallbacks: set = set()

        for tech in recommended:
            tech_tier = TECHNIQUE_TIERS.get(tech, TechniqueTier.TIER_3)
            tech_order = TIER_ORDER.get(tech_tier, 3)

            if tech_order <= limit_order:
                filtered.append(tech)
            else:
                # Blocked — find T1 fallback
                fallback = TECHNIQUE_TIER1_FALLBACKS.get(tech)
                entry = {
                    "id": tech.value,
                    "reason": f"Tier {tech_order} exceeds variant limit ({tier_limit.value})",
                    "fallback": fallback.value if fallback else None,
                }
                blocked.append(entry)

                if fallback and fallback not in seen_fallbacks:
                    filtered.append(fallback)
                    seen_fallbacks.add(fallback)
                    if fallback.value not in reasons:
                        reasons[fallback.value] = f"Fallback for blocked {tech.value}"

        logger.info(
            "sentiment_technique_mapping",
            company_id=company_id,
            frustration=frustration_score,
            sentiment=sentiment_score,
            urgency=urgency_level,
            vip=is_vip,
            variant=variant_type,
            selected=[t.value for t in filtered],
            blocked_count=len(blocked),
            escalation=escalation_recommended,
            priority_override=priority_override,
        )

        return SentimentMappingResult(
            recommended_techniques=filtered,
            technique_reasons=reasons,
            priority_override=priority_override,
            escalation_recommended=escalation_recommended,
            tone_adjustments=tone_adjustments,
            variant_type=variant_type,
            blocked_techniques=blocked,
        )
