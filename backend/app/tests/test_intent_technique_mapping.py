"""
Tests for Intent × Technique Mapper (F-149)

Covers: GAP-001 (variant-aware tier filtering), all 12 intents,
T1 fallback, blocked techniques.
"""

import pytest

from app.core.technique_router import TechniqueID, TechniqueTier
from app.services.intent_technique_mapper import (
    INTENT_TECHNIQUE_MAP,
    IntentTechniqueMapper,
    MappingResult,
    TECHNIQUE_TIER1_FALLBACKS,
    VARIANT_TIER_LIMITS,
)


class TestAllIntentsHaveMappings:
    def test_12_intents(self):
        mapper = IntentTechniqueMapper()
        intents = mapper.get_supported_intents()
        assert len(intents) == 12

    @pytest.mark.parametrize("intent", [
        "refund", "technical", "billing", "complaint", "feature_request",
        "general", "cancellation", "shipping", "inquiry", "escalation",
        "account", "feedback",
    ])
    def test_intent_has_mapping(self, intent):
        mapper = IntentTechniqueMapper()
        mapping = mapper.get_mapping(intent)
        assert mapping is not None
        assert mapping.intent == intent
        assert len(mapping.recommended_techniques) > 0


class TestVariantTierLimits:
    def test_mini_parwa_tier_1(self):
        assert VARIANT_TIER_LIMITS["mini_parwa"] == TechniqueTier.TIER_1

    def test_parwa_tier_2(self):
        assert VARIANT_TIER_LIMITS["parwa"] == TechniqueTier.TIER_2

    def test_parwa_high_tier_3(self):
        assert VARIANT_TIER_LIMITS["parwa_high"] == TechniqueTier.TIER_3


class TestGAP001VariantFiltering:
    """GAP-001: Variant-aware tier filtering."""

    def setup_method(self):
        self.mapper = IntentTechniqueMapper()

    @pytest.mark.parametrize("intent", [
        "refund", "technical", "billing", "complaint", "feature_request",
        "general", "cancellation", "shipping", "inquiry", "escalation",
        "account", "feedback",
    ])
    def test_mini_parwa_only_tier_1(self, intent):
        """GAP-001: Mini PARWA should only get Tier 1 techniques."""
        result = self.mapper.map_intent(intent=intent, variant_type="mini_parwa")
        for tid in result.selected_techniques:
            assert tid in (TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD)

    @pytest.mark.parametrize("intent", [
        "refund", "technical", "billing", "complaint",
    ])
    def test_parwa_gets_tier_1_and_2(self, intent):
        """GAP-001: Parwa gets Tier 1 + 2 techniques."""
        result = self.mapper.map_intent(intent=intent, variant_type="parwa")
        for tid in result.selected_techniques:
            assert tid in (
                TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD,
                TechniqueID.CHAIN_OF_THOUGHT, TechniqueID.REACT,
                TechniqueID.REVERSE_THINKING, TechniqueID.STEP_BACK,
                TechniqueID.THREAD_OF_THOUGHT,
            )

    def test_parwa_high_gets_all(self):
        """GAP-001: Parwa High gets all techniques including Tier 3."""
        result = self.mapper.map_intent(
            intent="refund", variant_type="parwa_high",
        )
        assert TechniqueID.SELF_CONSISTENCY in result.selected_techniques
        assert result.fallback_applied is False

    def test_refund_mini_parwa_fallback(self):
        """GAP-001: Refund maps to T3 Self-Consistency, Mini gets T1 CRP fallback."""
        result = self.mapper.map_intent(
            intent="refund", variant_type="mini_parwa",
        )
        assert result.fallback_applied is True
        assert len(result.blocked_techniques) > 0
        # Blocked should include self_consistency
        blocked_ids = {b["id"] for b in result.blocked_techniques}
        assert "self_consistency" in blocked_ids
        # Fallback should be a T1 technique
        for tid in result.selected_techniques:
            assert tid in (TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD)

    def test_complaint_mini_parwa_fallback(self):
        """GAP-001: Complaint UoT (T3) → CLARA (T1) on Mini."""
        result = self.mapper.map_intent(
            intent="complaint", variant_type="mini_parwa",
        )
        assert result.fallback_applied is True
        blocked_ids = {b["id"] for b in result.blocked_techniques}
        assert "universe_of_thoughts" in blocked_ids

    def test_technical_parwa_no_fallback(self):
        """Technical maps to T2 only, Parwa should get both without fallback."""
        result = self.mapper.map_intent(
            intent="technical", variant_type="parwa",
        )
        assert result.fallback_applied is False
        assert len(result.blocked_techniques) == 0

    def test_unknown_variant_defaults_tier_1(self):
        result = self.mapper.map_intent(
            intent="refund", variant_type="unknown_variant",
        )
        for tid in result.selected_techniques:
            assert tid in (TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD)


class TestBlockedTechniques:
    def test_blocked_has_reason(self):
        mapper = IntentTechniqueMapper()
        result = mapper.map_intent(intent="refund", variant_type="mini_parwa")
        for blocked in result.blocked_techniques:
            assert "id" in blocked
            assert "reason" in blocked
            assert "fallback" in blocked

    def test_blocked_has_fallback(self):
        mapper = IntentTechniqueMapper()
        result = mapper.map_intent(intent="refund", variant_type="mini_parwa")
        for blocked in result.blocked_techniques:
            assert blocked["fallback"] is not None

    def test_no_blocked_for_parwa_high(self):
        mapper = IntentTechniqueMapper()
        result = mapper.map_intent(
            intent="refund", variant_type="parwa_high",
        )
        assert len(result.blocked_techniques) == 0


class TestFallbackDeduplication:
    def test_no_duplicate_fallbacks(self):
        """If two blocked techniques share the same T1 fallback, only one is added."""
        mapper = IntentTechniqueMapper()
        result = mapper.map_intent(
            intent="refund", variant_type="mini_parwa",
        )
        # Step-Back (T2) → GSD (T1), Self-Consistency (T3) → CRP (T1)
        selected_ids = [t.value for t in result.selected_techniques]
        assert len(selected_ids) == len(set(selected_ids))


class TestTier1FallbackMap:
    def test_all_techniques_have_fallbacks(self):
        for tid, fallback in TECHNIQUE_TIER1_FALLBACKS.items():
            assert fallback in (TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD)

    def test_fallback_is_tier_1(self):
        for tid, fallback in TECHNIQUE_TIER1_FALLBACKS.items():
            assert fallback in (TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD)


class TestMappingResult:
    def test_result_fields(self):
        mapper = IntentTechniqueMapper()
        result = mapper.map_intent(intent="refund", variant_type="parwa")
        assert isinstance(result, MappingResult)
        assert result.intent == "refund"
        assert isinstance(result.selected_techniques, list)
        assert isinstance(result.selected_tiers, list)
        assert isinstance(result.variant_type, str)
        assert isinstance(result.fallback_applied, bool)
        assert isinstance(result.blocked_techniques, list)

    def test_invalid_intent(self):
        mapper = IntentTechniqueMapper()
        result = mapper.map_intent(intent="nonexistent", variant_type="parwa")
        assert result.selected_techniques == []
        assert result.fallback_applied is False

    def test_get_all_mappings(self):
        mapper = IntentTechniqueMapper()
        all_mappings = mapper.get_all_mappings()
        assert len(all_mappings) == 12

    def test_get_variant_tier_limit(self):
        assert IntentTechniqueMapper.get_variant_tier_limit("mini_parwa") == TechniqueTier.TIER_1
        assert IntentTechniqueMapper.get_variant_tier_limit("parwa") == TechniqueTier.TIER_2
        assert IntentTechniqueMapper.get_variant_tier_limit("parwa_high") == TechniqueTier.TIER_3


class TestSpecificMappings:
    def test_refund_has_self_consistency(self):
        mapper = IntentTechniqueMapper()
        mapping = mapper.get_mapping("refund")
        assert "self_consistency" in mapping.recommended_techniques

    def test_technical_has_chain_of_thought(self):
        mapper = IntentTechniqueMapper()
        mapping = mapper.get_mapping("technical")
        assert "chain_of_thought" in mapping.recommended_techniques

    def test_complaint_has_universe_of_thoughts(self):
        mapper = IntentTechniqueMapper()
        mapping = mapper.get_mapping("complaint")
        assert "universe_of_thoughts" in mapping.recommended_techniques

    def test_shipping_has_react(self):
        mapper = IntentTechniqueMapper()
        mapping = mapper.get_mapping("shipping")
        assert "react" in mapping.recommended_techniques
