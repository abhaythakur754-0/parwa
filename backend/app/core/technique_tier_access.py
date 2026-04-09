"""
SG-02: Technique Tier Access Check (W9-GAP-029, W9-GAP-030)

Validates whether a given reasoning technique is accessible for a
specific variant (subscription tier) before the Technique Router
selects it.  Used by intent/sentiment × technique mappings built
on Days 6-7.

Architecture:
  parwa_lite  (starter)  → Tier 1 only
  parwa       (growth)   → Tier 1 + Tier 2
  parwa_high  (high)     → Tier 1 + Tier 2 + Tier 3

GAP Fixes:
  W9-GAP-029 (HIGH): Cache tier access decisions for 60s
  W9-GAP-030 (MEDIUM): Log every blocked/downgraded access
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from backend.app.logger import get_logger
from backend.app.core.technique_router import (
    TechniqueID,
    TechniqueTier,
)

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────

_CACHE_TTL_SECONDS: int = 60

# Fallback: Tier 3 → Tier 1
_FALLBACK_T3_TO_T1: Dict[str, str] = {
    TechniqueID.GST.value: TechniqueID.CLARA.value,
    TechniqueID.UNIVERSE_OF_THOUGHTS.value: (
        TechniqueID.CLARA.value
    ),
    TechniqueID.TREE_OF_THOUGHTS.value: TechniqueID.CLARA.value,
    TechniqueID.SELF_CONSISTENCY.value: TechniqueID.CRP.value,
    TechniqueID.REFLEXION.value: TechniqueID.GSD.value,
    TechniqueID.LEAST_TO_MOST.value: TechniqueID.CLARA.value,
}

# Fallback: Tier 2 → Tier 1
_FALLBACK_T2_TO_T1: Dict[str, str] = {
    TechniqueID.CHAIN_OF_THOUGHT.value: TechniqueID.CRP.value,
    TechniqueID.REACT.value: TechniqueID.CRP.value,
    TechniqueID.REVERSE_THINKING.value: TechniqueID.CRP.value,
    TechniqueID.STEP_BACK.value: TechniqueID.GSD.value,
    TechniqueID.THREAD_OF_THOUGHT.value: TechniqueID.GSD.value,
}

# Combined fallback map (any technique → safe substitute)
_DOWNGRADE_FALLBACK: Dict[str, str] = {
    **_FALLBACK_T3_TO_T1,
    **_FALLBACK_T2_TO_T1,
}

# Known variant types
VALID_VARIANTS = ("parwa_lite", "parwa", "parwa_high")

# Technique → tier mapping
_TECHNIQUE_TO_TIER: Dict[str, str] = {
    # Tier 1
    TechniqueID.CLARA.value: TechniqueTier.TIER_1.value,
    TechniqueID.CRP.value: TechniqueTier.TIER_1.value,
    TechniqueID.GSD.value: TechniqueTier.TIER_1.value,
    # Tier 2
    TechniqueID.CHAIN_OF_THOUGHT.value: (
        TechniqueTier.TIER_2.value
    ),
    TechniqueID.REVERSE_THINKING.value: (
        TechniqueTier.TIER_2.value
    ),
    TechniqueID.REACT.value: TechniqueTier.TIER_2.value,
    TechniqueID.STEP_BACK.value: TechniqueTier.TIER_2.value,
    TechniqueID.THREAD_OF_THOUGHT.value: (
        TechniqueTier.TIER_2.value
    ),
    # Tier 3
    TechniqueID.GST.value: TechniqueTier.TIER_3.value,
    TechniqueID.UNIVERSE_OF_THOUGHTS.value: (
        TechniqueTier.TIER_3.value
    ),
    TechniqueID.TREE_OF_THOUGHTS.value: (
        TechniqueTier.TIER_3.value
    ),
    TechniqueID.SELF_CONSISTENCY.value: (
        TechniqueTier.TIER_3.value
    ),
    TechniqueID.REFLEXION.value: TechniqueTier.TIER_3.value,
    TechniqueID.LEAST_TO_MOST.value: (
        TechniqueTier.TIER_3.value
    ),
}

_TIER_1_TECHNIQUES = [
    TechniqueID.CLARA.value,
    TechniqueID.CRP.value,
    TechniqueID.GSD.value,
]

_TIER_2_TECHNIQUES = [
    TechniqueID.CHAIN_OF_THOUGHT.value,
    TechniqueID.REVERSE_THINKING.value,
    TechniqueID.REACT.value,
    TechniqueID.STEP_BACK.value,
    TechniqueID.THREAD_OF_THOUGHT.value,
]

_TIER_3_TECHNIQUES = [
    TechniqueID.GST.value,
    TechniqueID.UNIVERSE_OF_THOUGHTS.value,
    TechniqueID.TREE_OF_THOUGHTS.value,
    TechniqueID.SELF_CONSISTENCY.value,
    TechniqueID.REFLEXION.value,
    TechniqueID.LEAST_TO_MOST.value,
]


# ── TierAccessDecision Enum ───────────────────────────────────────


class TierAccessDecision(str, Enum):
    """Result of a tier access check."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    DOWNGRADED = "downgraded"


# ── TierAccessResult Dataclass ────────────────────────────────────


@dataclass
class TierAccessResult:
    """Detailed result of a single technique access check."""

    technique: str
    requested_tier: str
    decision: TierAccessDecision
    variant_type: str
    effective_tier: Optional[str] = None
    fallback_technique: Optional[str] = None
    reason: str = ""
    max_allowed_tier: str = ""


# ── VariantTierConfig Dataclass ───────────────────────────────────


@dataclass
class VariantTierConfig:
    """Configuration for a single variant's tier access."""

    variant_type: str
    max_tier: int  # 1, 2, or 3
    allowed_techniques: List[str] = field(
        default_factory=list,
    )
    blocked_techniques: List[str] = field(
        default_factory=list,
    )
    fallback_map: Dict[str, str] = field(
        default_factory=dict,
    )


# ── TechniqueTierAccessChecker ────────────────────────────────────


class TechniqueTierAccessChecker:
    """
    Checks whether a reasoning technique is accessible for a given
    variant tier.  Caches decisions for 60s (W9-GAP-029) and logs
    every blocked/downgraded access (W9-GAP-030).

    The Technique Router must call this *before* technique selection
    so that intent/sentiment mappings are variant-aware.
    """

    def __init__(self) -> None:
        """Load tier configurations for all 3 variants."""
        self._configs: Dict[str, VariantTierConfig] = {}
        self._cache: Dict[str, TierAccessResult] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._build_variant_configs()

    # ── Config Builder ────────────────────────────────────────────

    def _build_variant_configs(self) -> None:
        """Build tier configurations for all 3 variants."""
        all_techniques = (
            _TIER_1_TECHNIQUES
            + _TIER_2_TECHNIQUES
            + _TIER_3_TECHNIQUES
        )

        # parwa_lite: Tier 1 only
        t1_blocked = list(_TIER_2_TECHNIQUES + _TIER_3_TECHNIQUES)
        t1_fallback = {
            **_FALLBACK_T2_TO_T1,
            **_FALLBACK_T3_TO_T1,
        }
        self._configs["parwa_lite"] = VariantTierConfig(
            variant_type="parwa_lite",
            max_tier=1,
            allowed_techniques=list(_TIER_1_TECHNIQUES),
            blocked_techniques=t1_blocked,
            fallback_map=t1_fallback,
        )

        # parwa: Tier 1 + Tier 2
        t2_blocked = list(_TIER_3_TECHNIQUES)
        t2_fallback = dict(_FALLBACK_T3_TO_T1)
        self._configs["parwa"] = VariantTierConfig(
            variant_type="parwa",
            max_tier=2,
            allowed_techniques=(
                _TIER_1_TECHNIQUES + _TIER_2_TECHNIQUES
            ),
            blocked_techniques=t2_blocked,
            fallback_map=t2_fallback,
        )

        # parwa_high: Tier 1 + Tier 2 + Tier 3 (all)
        self._configs["parwa_high"] = VariantTierConfig(
            variant_type="parwa_high",
            max_tier=3,
            allowed_techniques=all_techniques,
            blocked_techniques=[],
            fallback_map={},
        )

    # ── Cache Helpers (W9-GAP-029) ────────────────────────────────

    def _cache_key(
        self, technique_id: str, variant_type: str,
    ) -> str:
        """Build a deterministic cache key."""
        return f"{technique_id}:{variant_type}"

    def _get_cached(
        self, technique_id: str, variant_type: str,
    ) -> Optional[TierAccessResult]:
        """Return cached result if still valid (60s TTL)."""
        key = self._cache_key(technique_id, variant_type)
        ts = self._cache_timestamps.get(key, 0)
        if time.time() - ts < _CACHE_TTL_SECONDS:
            return self._cache.get(key)
        # Expired — evict
        self._cache.pop(key, None)
        self._cache_timestamps.pop(key, None)
        return None

    def _set_cached(
        self, technique_id: str, variant_type: str,
        result: TierAccessResult,
    ) -> None:
        """Store result in cache with timestamp."""
        key = self._cache_key(technique_id, variant_type)
        self._cache[key] = result
        self._cache_timestamps[key] = time.time()

    def clear_cache(self) -> None:
        """Clear all cached tier access decisions."""
        self._cache.clear()
        self._cache_timestamps.clear()

    # ── Core Access Check ─────────────────────────────────────────

    def check_access(
        self,
        technique_id: str,
        variant_type: str,
        company_id: str = "",
    ) -> TierAccessResult:
        """
        Check if a technique is allowed for the given variant.

        Returns ALLOWED, BLOCKED, or DOWNGRADED with fallback.
        Caches results for 60s (W9-GAP-029).
        """
        # Validate inputs — graceful degradation (BC-008)
        if not technique_id or not variant_type:
            return TierAccessResult(
                technique=technique_id or "",
                requested_tier="",
                decision=TierAccessDecision.BLOCKED,
                variant_type=variant_type or "",
                reason="empty_technique_or_variant",
                max_allowed_tier="",
            )

        technique_id = technique_id.strip().lower()
        variant_type = variant_type.strip().lower()

        # Check cache first
        cached = self._get_cached(technique_id, variant_type)
        if cached is not None:
            return cached

        result = self._evaluate_access(
            technique_id, variant_type, company_id,
        )

        # Store in cache
        self._set_cached(technique_id, variant_type, result)

        return result

    def _evaluate_access(
        self,
        technique_id: str,
        variant_type: str,
        company_id: str,
    ) -> TierAccessResult:
        """Evaluate access without caching."""
        config = self._configs.get(variant_type)

        # Unknown variant — treat as most restrictive (BC-008)
        if config is None:
            logger.warning(
                "tier_access_unknown_variant",
                company_id=company_id,
                technique=technique_id,
                variant=variant_type,
            )
            return TierAccessResult(
                technique=technique_id,
                requested_tier=_TECHNIQUE_TO_TIER.get(
                    technique_id, "",
                ),
                decision=TierAccessDecision.BLOCKED,
                variant_type=variant_type,
                reason=(
                    "unknown_variant_treated_as_restricted"
                ),
                max_allowed_tier="",
            )

        technique_tier = _TECHNIQUE_TO_TIER.get(
            technique_id, "",
        )
        max_allowed = f"tier_{config.max_tier}"

        # Unknown technique — allow Tier 1 fallback (BC-008)
        if not technique_tier:
            logger.warning(
                "tier_access_unknown_technique",
                company_id=company_id,
                technique=technique_id,
                variant=variant_type,
            )
            fallback = _DOWNGRADE_FALLBACK.get(technique_id)
            return TierAccessResult(
                technique=technique_id,
                requested_tier="",
                decision=TierAccessDecision.BLOCKED,
                variant_type=variant_type,
                fallback_technique=fallback,
                reason="unknown_technique_id",
                max_allowed_tier=max_allowed,
            )

        # Allowed — technique tier ≤ variant max tier
        if technique_id in config.allowed_techniques:
            return TierAccessResult(
                technique=technique_id,
                requested_tier=technique_tier,
                decision=TierAccessDecision.ALLOWED,
                variant_type=variant_type,
                effective_tier=technique_tier,
                reason="technique_within_variant_tier",
                max_allowed_tier=max_allowed,
            )

        # Blocked / Downgraded — technique tier > variant max
        fallback = config.fallback_map.get(technique_id)

        if fallback:
            decision = TierAccessDecision.DOWNGRADED
            effective_tier = _TECHNIQUE_TO_TIER.get(
                fallback, "tier_1",
            )
            reason = (
                f"technique_{technique_tier}_exceeds_"
                f"variant_max_{max_allowed}_"
                f"downgraded_to_{fallback}"
            )
            log_level = "info"
        else:
            decision = TierAccessDecision.BLOCKED
            effective_tier = None
            reason = (
                f"technique_{technique_tier}_exceeds_"
                f"variant_max_{max_allowed}_"
                f"no_fallback_available"
            )
            log_level = "warning"

        # W9-GAP-030: Log every blocked/downgraded attempt
        log_fn = (
            logger.info if log_level == "info"
            else logger.warning
        )
        log_fn(
            "tier_access_denied",
            company_id=company_id,
            technique=technique_id,
            technique_tier=technique_tier,
            variant=variant_type,
            max_allowed=max_allowed,
            decision=decision.value,
            fallback=fallback,
            reason=reason,
        )

        return TierAccessResult(
            technique=technique_id,
            requested_tier=technique_tier,
            decision=decision,
            variant_type=variant_type,
            effective_tier=effective_tier,
            fallback_technique=fallback,
            reason=reason,
            max_allowed_tier=max_allowed,
        )

    # ── Batch Operations ──────────────────────────────────────────

    def check_batch_access(
        self,
        technique_ids: List[str],
        variant_type: str,
        company_id: str = "",
    ) -> List[TierAccessResult]:
        """Check multiple techniques at once."""
        results: List[TierAccessResult] = []
        for tid in technique_ids:
            results.append(
                self.check_access(tid, variant_type, company_id)
            )
        return results

    def filter_techniques(
        self,
        technique_ids: List[str],
        variant_type: str,
    ) -> List[str]:
        """
        Return only allowed techniques for the variant.

        Blocked techniques get replaced with their fallbacks.
        Deduplication is applied to avoid duplicates when
        multiple blocked techniques share the same fallback.
        """
        seen: set = set()
        result: List[str] = []

        for tid in technique_ids:
            tid_clean = tid.strip().lower() if tid else ""
            if not tid_clean:
                continue

            access = self.check_access(tid_clean, variant_type)

            if access.decision == TierAccessDecision.ALLOWED:
                if tid_clean not in seen:
                    seen.add(tid_clean)
                    result.append(tid_clean)
            elif (
                access.decision == TierAccessDecision.DOWNGRADED
                and access.fallback_technique
            ):
                fb = access.fallback_technique
                if fb not in seen:
                    seen.add(fb)
                    result.append(fb)
            # BLOCKED with no fallback → silently dropped

        return result

    # ── Query Methods ─────────────────────────────────────────────

    def get_allowed_techniques(
        self, variant_type: str,
    ) -> List[str]:
        """Get all techniques a variant can use."""
        config = self._configs.get(variant_type)
        if config is None:
            return []
        return list(config.allowed_techniques)

    def get_blocked_techniques(
        self, variant_type: str,
    ) -> List[str]:
        """Get all techniques blocked for a variant."""
        config = self._configs.get(variant_type)
        if config is None:
            return list(
                _TIER_2_TECHNIQUES + _TIER_3_TECHNIQUES
            )
        return list(config.blocked_techniques)

    def get_tier_for_technique(self, technique_id: str) -> str:
        """Return the tier a technique belongs to."""
        tid = technique_id.strip().lower() if technique_id else ""
        return _TECHNIQUE_TO_TIER.get(tid, "")

    # ── Upgrade / Escalation ──────────────────────────────────────

    def upgrade_technique(
        self,
        technique_id: str,
        from_variant: str,
        to_variant: str,
        company_id: str = "",
    ) -> TierAccessResult:
        """
        Check what happens when escalating a technique
        across variants (e.g., parwa → parwa_high).

        Returns the access result from the *target* variant
        perspective so callers know whether the upgrade
        unlocks, keeps, or still blocks the technique.
        """
        technique_id = (
            technique_id.strip().lower()
            if technique_id else ""
        )
        from_variant = (
            from_variant.strip().lower()
            if from_variant else ""
        )
        to_variant = (
            to_variant.strip().lower()
            if to_variant else ""
        )

        # Check original access
        original = self.check_access(
            technique_id, from_variant, company_id,
        )
        # Check target access
        target = self.check_access(
            technique_id, to_variant, company_id,
        )

        # Build an enriched result showing the upgrade path
        upgraded = target
        if (
            original.decision != TierAccessDecision.ALLOWED
            and target.decision == TierAccessDecision.ALLOWED
        ):
            logger.info(
                "tier_access_upgraded",
                company_id=company_id,
                technique=technique_id,
                from_variant=from_variant,
                to_variant=to_variant,
                previous_decision=original.decision.value,
                new_decision=target.decision.value,
            )

        return upgraded

    # ── Pipeline Validation ───────────────────────────────────────

    def validate_pipeline(
        self,
        techniques: List[str],
        variant_type: str,
    ) -> Dict:
        """
        Validate an entire technique pipeline for variant
        compliance.

        Returns:
            {
                "valid": bool,
                "allowed": [...],
                "blocked": [...],
                "downgraded": [...],
                "details": [...],
            }
        """
        allowed: List[str] = []
        blocked: List[str] = []
        downgraded: List[str] = []
        details: List[Dict] = []

        for tid in techniques:
            tid_clean = (
                tid.strip().lower() if tid else ""
            )
            if not tid_clean:
                continue

            result = self.check_access(tid_clean, variant_type)
            detail = {
                "technique": tid_clean,
                "decision": result.decision.value,
                "requested_tier": result.requested_tier,
                "fallback": result.fallback_technique,
                "reason": result.reason,
            }

            if result.decision == TierAccessDecision.ALLOWED:
                allowed.append(tid_clean)
            elif (
                result.decision
                == TierAccessDecision.DOWNGRADED
            ):
                downgraded.append(tid_clean)
                if result.fallback_technique:
                    allowed.append(
                        result.fallback_technique
                    )
            else:
                blocked.append(tid_clean)

            details.append(detail)

        is_valid = len(blocked) == 0

        return {
            "valid": is_valid,
            "allowed": allowed,
            "blocked": blocked,
            "downgraded": downgraded,
            "details": details,
        }

    # ── Config Access ─────────────────────────────────────────────

    def get_variant_config(
        self, variant_type: str,
    ) -> Optional[VariantTierConfig]:
        """Get full config for a variant.

        Returns None for unknown variants (BC-008).
        """
        return self._configs.get(variant_type)

    # ── Utility Methods ───────────────────────────────────────────

    def get_all_variant_types(self) -> List[str]:
        """Return all known variant type names."""
        return list(self._configs.keys())

    def get_max_tier(self, variant_type: str) -> int:
        """Return the max tier number for a variant."""
        config = self._configs.get(variant_type)
        if config is None:
            return 0
        return config.max_tier

    def is_variant_valid(self, variant_type: str) -> bool:
        """Check if a variant type is recognized."""
        return variant_type in self._configs

    def get_technique_count_for_variant(
        self, variant_type: str,
    ) -> Dict[str, int]:
        """Return count of allowed/blocked techniques."""
        config = self._configs.get(variant_type)
        if config is None:
            return {"allowed": 0, "blocked": 0, "total": 0}
        return {
            "allowed": len(config.allowed_techniques),
            "blocked": len(config.blocked_techniques),
            "total": (
                len(config.allowed_techniques)
                + len(config.blocked_techniques)
            ),
        }

    def get_fallback_for_technique(
        self, technique_id: str, variant_type: str,
    ) -> Optional[str]:
        """Get the fallback technique for a blocked
        technique on a specific variant."""
        config = self._configs.get(variant_type)
        if config is None:
            return _DOWNGRADE_FALLBACK.get(
                technique_id.strip().lower(),
            )
        return config.fallback_map.get(
            technique_id.strip().lower(),
        )

    def compare_variants(
        self,
        variant_a: str,
        variant_b: str,
    ) -> Dict:
        """Compare two variants' tier access side by side."""
        config_a = self._configs.get(variant_a)
        config_b = self._configs.get(variant_b)
        if config_a is None or config_b is None:
            return {"error": "unknown_variant"}

        a_set = set(config_a.allowed_techniques)
        b_set = set(config_b.allowed_techniques)

        return {
            "variant_a": variant_a,
            "variant_b": variant_b,
            "variant_a_max_tier": config_a.max_tier,
            "variant_b_max_tier": config_b.max_tier,
            "common": sorted(a_set & b_set),
            "only_in_a": sorted(a_set - b_set),
            "only_in_b": sorted(b_set - a_set),
            "a_has_more": len(a_set) > len(b_set),
        }
