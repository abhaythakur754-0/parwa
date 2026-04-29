"""
Tests for Intent × Technique Mapper (F-149) — Week 9 Day 6

Covers: GAP-001 (variant-aware tier filtering), all 12 intents,
T1 fallback, blocked techniques, variant limits, edge cases.
Target: 100+ tests
"""

from unittest.mock import MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════════
# Fixtures — import source modules with mocked logger
# ═══════════════════════════════════════════════════════════════════════

# Runtime-injected by _mock_logger fixture — satisfies flake8 F821
INTENT_TECHNIQUE_MAP = IntentTechniqueMapper = IntentTechniqueMapping = (
    MappingResult
) = TECHNIQUE_TIER1_FALLBACKS = VARIANT_TIER_LIMITS = TechniqueID = TechniqueTier = None


@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("app.logger.get_logger", return_value=MagicMock()):
        from app.core.technique_router import (  # noqa: F811,F401
            TechniqueID,
            TechniqueTier,
        )
        from app.services.intent_technique_mapper import (  # noqa: F811,F401
            INTENT_TECHNIQUE_MAP,
            TECHNIQUE_TIER1_FALLBACKS,
            VARIANT_TIER_LIMITS,
            IntentTechniqueMapper,
            IntentTechniqueMapping,
            MappingResult,
        )

        globals().update(
            {
                "INTENT_TECHNIQUE_MAP": INTENT_TECHNIQUE_MAP,
                "IntentTechniqueMapper": IntentTechniqueMapper,
                "IntentTechniqueMapping": IntentTechniqueMapping,
                "MappingResult": MappingResult,
                "TECHNIQUE_TIER1_FALLBACKS": TECHNIQUE_TIER1_FALLBACKS,
                "VARIANT_TIER_LIMITS": VARIANT_TIER_LIMITS,
                "TechniqueID": TechniqueID,
                "TechniqueTier": TechniqueTier,
            }
        )


# ═══════════════════════════════════════════════════════════════════════
# 1. map_intent for all 12 intents (12 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestMapIntentAll12:
    def setup_method(self):
        self.mapper = IntentTechniqueMapper()

    def test_refund_has_techniques(self):
        result = self.mapper.map_intent("refund", variant_type="parwa_high")
        assert len(result.selected_techniques) > 0
        assert "self_consistency" in [t.value for t in result.selected_techniques]

    def test_technical_has_chain_of_thought(self):
        result = self.mapper.map_intent("technical", variant_type="parwa")
        assert "chain_of_thought" in [t.value for t in result.selected_techniques]

    def test_billing_has_self_consistency(self):
        result = self.mapper.map_intent("billing", variant_type="parwa_high")
        assert "self_consistency" in [t.value for t in result.selected_techniques]

    def test_complaint_has_universe_of_thoughts(self):
        result = self.mapper.map_intent("complaint", variant_type="parwa_high")
        assert "universe_of_thoughts" in [t.value for t in result.selected_techniques]

    def test_feature_request_has_chain_of_thought(self):
        result = self.mapper.map_intent("feature_request", variant_type="parwa")
        assert "chain_of_thought" in [t.value for t in result.selected_techniques]

    def test_general_has_chain_of_thought(self):
        result = self.mapper.map_intent("general", variant_type="parwa")
        assert "chain_of_thought" in [t.value for t in result.selected_techniques]

    def test_cancellation_has_reverse_thinking(self):
        result = self.mapper.map_intent("cancellation", variant_type="parwa")
        assert "reverse_thinking" in [t.value for t in result.selected_techniques]

    def test_shipping_has_react(self):
        result = self.mapper.map_intent("shipping", variant_type="parwa")
        assert "react" in [t.value for t in result.selected_techniques]

    def test_inquiry_has_chain_of_thought(self):
        result = self.mapper.map_intent("inquiry", variant_type="parwa")
        assert "chain_of_thought" in [t.value for t in result.selected_techniques]

    def test_escalation_has_reflexion(self):
        result = self.mapper.map_intent("escalation", variant_type="parwa_high")
        assert "reflexion" in [t.value for t in result.selected_techniques]

    def test_account_has_react(self):
        result = self.mapper.map_intent("account", variant_type="parwa")
        assert "react" in [t.value for t in result.selected_techniques]

    def test_feedback_has_self_consistency(self):
        result = self.mapper.map_intent("feedback", variant_type="parwa_high")
        assert "self_consistency" in [t.value for t in result.selected_techniques]


# ═══════════════════════════════════════════════════════════════════════
# 2. Variant Filtering GAP-001 (15 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestVariantFilteringGAP001:
    def setup_method(self):
        self.mapper = IntentTechniqueMapper()

    def test_mini_parwa_blocks_t2(self):
        """GAP-001: Mini PARWA blocks all T2 techniques."""
        result = self.mapper.map_intent("technical", variant_type="mini_parwa")
        for tid in result.selected_techniques:
            assert tid in (TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD)

    def test_mini_parwa_blocks_t3(self):
        """GAP-001: Mini PARWA blocks all T3 techniques."""
        result = self.mapper.map_intent("refund", variant_type="mini_parwa")
        for tid in result.selected_techniques:
            assert tid in (TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD)

    def test_parwa_blocks_t3(self):
        """GAP-001: Parwa blocks T3 techniques."""
        result = self.mapper.map_intent("refund", variant_type="parwa")
        t3_ids = {
            TechniqueID.GST,
            TechniqueID.UNIVERSE_OF_THOUGHTS,
            TechniqueID.TREE_OF_THOUGHTS,
            TechniqueID.SELF_CONSISTENCY,
            TechniqueID.REFLEXION,
            TechniqueID.LEAST_TO_MOST,
        }
        for tid in result.selected_techniques:
            assert tid not in t3_ids

    def test_parwa_high_allows_all(self):
        """GAP-001: Parwa High allows all tiers."""
        result = self.mapper.map_intent("refund", variant_type="parwa_high")
        assert len(result.selected_techniques) > 0
        assert result.fallback_applied is False
        assert len(result.blocked_techniques) == 0

    def test_mini_parwa_refund_fallback(self):
        """GAP-001: Refund's T3 Self-Consistency → T1 CRP on Mini."""
        result = self.mapper.map_intent("refund", variant_type="mini_parwa")
        assert result.fallback_applied is True
        blocked_ids = {b["id"] for b in result.blocked_techniques}
        assert "self_consistency" in blocked_ids
        for tid in result.selected_techniques:
            assert tid in (TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD)

    def test_mini_parwa_complaint_fallback(self):
        """GAP-001: Complaint's UoT (T3) → CLARA (T1) on Mini."""
        result = self.mapper.map_intent("complaint", variant_type="mini_parwa")
        assert result.fallback_applied is True
        blocked_ids = {b["id"] for b in result.blocked_techniques}
        assert "universe_of_thoughts" in blocked_ids

    def test_mini_parwa_billing_fallback(self):
        result = self.mapper.map_intent("billing", variant_type="mini_parwa")
        assert result.fallback_applied is True
        blocked_ids = {b["id"] for b in result.blocked_techniques}
        assert "self_consistency" in blocked_ids

    def test_mini_parwa_escalation_fallback(self):
        result = self.mapper.map_intent("escalation", variant_type="mini_parwa")
        assert result.fallback_applied is True

    def test_parwa_technical_no_fallback(self):
        """Technical maps to T2 only, Parwa should get both without fallback."""
        result = self.mapper.map_intent("technical", variant_type="parwa")
        assert result.fallback_applied is False
        assert len(result.blocked_techniques) == 0

    def test_parwa_general_no_fallback(self):
        result = self.mapper.map_intent("general", variant_type="parwa")
        assert result.fallback_applied is False

    def test_mini_parwa_technical_fallback(self):
        """Technical's T2 CoT+ReAct → T1 CRP on Mini."""
        result = self.mapper.map_intent("technical", variant_type="mini_parwa")
        assert result.fallback_applied is True
        blocked_ids = {b["id"] for b in result.blocked_techniques}
        assert "chain_of_thought" in blocked_ids
        assert "react" in blocked_ids

    def test_parwa_refund_blocks_t3(self):
        """Parwa allows T2 but blocks T3."""
        result = self.mapper.map_intent("refund", variant_type="parwa")
        # step_back is T2, self_consistency is T3
        blocked_ids = {b["id"] for b in result.blocked_techniques}
        assert "self_consistency" in blocked_ids
        # step_back should NOT be blocked
        assert "step_back" not in blocked_ids

    def test_mini_parwa_shipping_fallback(self):
        result = self.mapper.map_intent("shipping", variant_type="mini_parwa")
        assert result.fallback_applied is True
        for tid in result.selected_techniques:
            assert tid in (TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD)

    def test_parwa_high_nothing_blocked(self):
        for intent in ["refund", "billing", "complaint", "escalation", "feedback"]:
            result = self.mapper.map_intent(intent, variant_type="parwa_high")
            assert (
                len(result.blocked_techniques) == 0
            ), f"{intent} should have no blocked on parwa_high"

    def test_unknown_variant_defaults_t1(self):
        result = self.mapper.map_intent("refund", variant_type="unknown_variant")
        for tid in result.selected_techniques:
            assert tid in (TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD)


# ═══════════════════════════════════════════════════════════════════════
# 3. Tier 1 Fallbacks (10 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestTier1Fallbacks:
    def test_chain_of_thought_to_crp(self):
        assert (
            TECHNIQUE_TIER1_FALLBACKS[TechniqueID.CHAIN_OF_THOUGHT] == TechniqueID.CRP
        )

    def test_react_to_crp(self):
        assert TECHNIQUE_TIER1_FALLBACKS[TechniqueID.REACT] == TechniqueID.CRP

    def test_step_back_to_gsd(self):
        assert TECHNIQUE_TIER1_FALLBACKS[TechniqueID.STEP_BACK] == TechniqueID.GSD

    def test_reverse_thinking_to_crp(self):
        assert (
            TECHNIQUE_TIER1_FALLBACKS[TechniqueID.REVERSE_THINKING] == TechniqueID.CRP
        )

    def test_thread_of_thought_to_gsd(self):
        assert (
            TECHNIQUE_TIER1_FALLBACKS[TechniqueID.THREAD_OF_THOUGHT] == TechniqueID.GSD
        )

    def test_gst_to_clara(self):
        assert TECHNIQUE_TIER1_FALLBACKS[TechniqueID.GST] == TechniqueID.CLARA

    def test_universe_of_thoughts_to_clara(self):
        assert (
            TECHNIQUE_TIER1_FALLBACKS[TechniqueID.UNIVERSE_OF_THOUGHTS]
            == TechniqueID.CLARA
        )

    def test_tree_of_thoughts_to_clara(self):
        assert (
            TECHNIQUE_TIER1_FALLBACKS[TechniqueID.TREE_OF_THOUGHTS] == TechniqueID.CLARA
        )

    def test_self_consistency_to_crp(self):
        assert (
            TECHNIQUE_TIER1_FALLBACKS[TechniqueID.SELF_CONSISTENCY] == TechniqueID.CRP
        )

    def test_reflexion_to_gsd(self):
        assert TECHNIQUE_TIER1_FALLBACKS[TechniqueID.REFLEXION] == TechniqueID.GSD

    def test_least_to_most_to_clara(self):
        assert TECHNIQUE_TIER1_FALLBACKS[TechniqueID.LEAST_TO_MOST] == TechniqueID.CLARA

    def test_all_fallbacks_are_t1(self):
        t1 = {TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD}
        for tid, fallback in TECHNIQUE_TIER1_FALLBACKS.items():
            assert fallback in t1, f"{tid} fallback should be T1"


# ═══════════════════════════════════════════════════════════════════════
# 4. MappingResult Structure (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestMappingResult:
    def setup_method(self):
        self.mapper = IntentTechniqueMapper()

    def test_all_fields_populated(self):
        result = self.mapper.map_intent("refund", variant_type="parwa")
        assert isinstance(result, MappingResult)
        assert result.intent == "refund"
        assert isinstance(result.selected_techniques, list)
        assert isinstance(result.selected_tiers, list)
        assert isinstance(result.variant_type, str)
        assert isinstance(result.fallback_applied, bool)
        assert isinstance(result.blocked_techniques, list)

    def test_fallback_applied_flag_true(self):
        result = self.mapper.map_intent("refund", variant_type="mini_parwa")
        assert result.fallback_applied is True

    def test_fallback_applied_flag_false(self):
        result = self.mapper.map_intent("refund", variant_type="parwa_high")
        assert result.fallback_applied is False

    def test_blocked_techniques_format(self):
        result = self.mapper.map_intent("refund", variant_type="mini_parwa")
        for blocked in result.blocked_techniques:
            assert "id" in blocked
            assert "reason" in blocked
            assert "fallback" in blocked

    def test_selected_techniques_are_technique_id(self):
        result = self.mapper.map_intent("technical", variant_type="parwa")
        for tid in result.selected_techniques:
            assert isinstance(tid, TechniqueID)


# ═══════════════════════════════════════════════════════════════════════
# 5. Unknown Intent (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestUnknownIntent:
    def setup_method(self):
        self.mapper = IntentTechniqueMapper()

    def test_returns_empty_techniques(self):
        result = self.mapper.map_intent("nonexistent_intent", variant_type="parwa")
        assert result.selected_techniques == []
        assert result.selected_tiers == []

    def test_returns_empty_blocked(self):
        result = self.mapper.map_intent("nonexistent_intent", variant_type="parwa")
        assert result.blocked_techniques == []

    def test_returns_no_fallback(self):
        result = self.mapper.map_intent("nonexistent_intent", variant_type="parwa")
        assert result.fallback_applied is False


# ═══════════════════════════════════════════════════════════════════════
# 6. get_mapping (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGetMapping:
    def setup_method(self):
        self.mapper = IntentTechniqueMapper()

    def test_returns_raw_mapping(self):
        mapping = self.mapper.get_mapping("refund")
        assert mapping is not None
        assert mapping.intent == "refund"
        assert len(mapping.recommended_techniques) > 0

    def test_returns_none_for_unknown(self):
        mapping = self.mapper.get_mapping("nonexistent")
        assert mapping is None

    def test_mapping_has_trigger_conditions(self):
        mapping = self.mapper.get_mapping("refund")
        assert mapping.trigger_conditions != ""
        assert len(mapping.trigger_conditions) > 0


# ═══════════════════════════════════════════════════════════════════════
# 7. get_all_mappings (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGetAllMappings:
    def setup_method(self):
        self.mapper = IntentTechniqueMapper()

    def test_returns_all_12_intents(self):
        all_mappings = self.mapper.get_all_mappings()
        assert len(all_mappings) == 12

    def test_all_intents_have_techniques(self):
        all_mappings = self.mapper.get_all_mappings()
        for intent, mapping in all_mappings.items():
            assert (
                len(mapping.recommended_techniques) > 0
            ), f"{intent} has no techniques"

    def test_returns_dict(self):
        all_mappings = self.mapper.get_all_mappings()
        assert isinstance(all_mappings, dict)


# ═══════════════════════════════════════════════════════════════════════
# 8. get_supported_intents (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGetSupportedIntents:
    def setup_method(self):
        self.mapper = IntentTechniqueMapper()

    def test_returns_sorted_list(self):
        intents = self.mapper.get_supported_intents()
        assert intents == sorted(intents)

    def test_returns_12_intents(self):
        intents = self.mapper.get_supported_intents()
        assert len(intents) == 12

    def test_all_expected_intents_present(self):
        intents = self.mapper.get_supported_intents()
        expected = {
            "refund",
            "technical",
            "billing",
            "complaint",
            "feature_request",
            "general",
            "cancellation",
            "shipping",
            "inquiry",
            "escalation",
            "account",
            "feedback",
        }
        assert set(intents) == expected


# ═══════════════════════════════════════════════════════════════════════
# 9. get_variant_tier_limit (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGetVariantTierLimit:
    def test_mini_parwa_tier_1(self):
        assert (
            IntentTechniqueMapper.get_variant_tier_limit("mini_parwa")
            == TechniqueTier.TIER_1
        )

    def test_parwa_tier_2(self):
        assert (
            IntentTechniqueMapper.get_variant_tier_limit("parwa")
            == TechniqueTier.TIER_2
        )

    def test_parwa_high_tier_3(self):
        assert (
            IntentTechniqueMapper.get_variant_tier_limit("parwa_high")
            == TechniqueTier.TIER_3
        )

    def test_unknown_defaults_tier_1(self):
        assert (
            IntentTechniqueMapper.get_variant_tier_limit("unknown")
            == TechniqueTier.TIER_1
        )

    def test_empty_string_defaults_tier_1(self):
        assert IntentTechniqueMapper.get_variant_tier_limit("") == TechniqueTier.TIER_1


# ═══════════════════════════════════════════════════════════════════════
# 10. IntentTechniqueMapping Dataclass (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestIntentTechniqueMappingDataclass:
    def setup_method(self):
        self.mapper = IntentTechniqueMapper()

    def test_variant_override_per_variant(self):
        mapping = self.mapper.get_mapping("refund")
        assert "mini_parwa" in mapping.variant_override
        assert "parwa" in mapping.variant_override
        assert "parwa_high" in mapping.variant_override

    def test_variant_override_has_technique_lists(self):
        mapping = self.mapper.get_mapping("refund")
        for variant, techniques in mapping.variant_override.items():
            assert isinstance(techniques, list)

    def test_parwa_high_override_equals_recommended(self):
        """Parwa High has all techniques, no filtering."""
        mapping = self.mapper.get_mapping("refund")
        assert mapping.variant_override["parwa_high"] == mapping.recommended_techniques

    def test_mini_parwa_override_smaller(self):
        """Mini PARWA should have fewer or equal techniques."""
        mapping = self.mapper.get_mapping("refund")
        assert len(mapping.variant_override["mini_parwa"]) <= len(
            mapping.recommended_techniques
        )

    def test_recommended_tiers_populated(self):
        mapping = self.mapper.get_mapping("technical")
        assert len(mapping.recommended_tiers) > 0
        for tier in mapping.recommended_tiers:
            assert tier in ("tier_1", "tier_2", "tier_3")


# ═══════════════════════════════════════════════════════════════════════
# 11. Blocked Techniques Format (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestBlockedTechniquesFormat:
    def setup_method(self):
        self.mapper = IntentTechniqueMapper()

    def test_blocked_has_id(self):
        result = self.mapper.map_intent("refund", variant_type="mini_parwa")
        for blocked in result.blocked_techniques:
            assert "id" in blocked
            assert isinstance(blocked["id"], str)

    def test_blocked_has_reason(self):
        result = self.mapper.map_intent("refund", variant_type="mini_parwa")
        for blocked in result.blocked_techniques:
            assert "reason" in blocked
            assert isinstance(blocked["reason"], str)
            assert (
                "exceeds" in blocked["reason"].lower()
                or "tier" in blocked["reason"].lower()
            )

    def test_blocked_has_fallback(self):
        result = self.mapper.map_intent("refund", variant_type="mini_parwa")
        for blocked in result.blocked_techniques:
            assert "fallback" in blocked
            assert blocked["fallback"] is not None

    def test_no_blocked_for_parwa_high(self):
        result = self.mapper.map_intent("refund", variant_type="parwa_high")
        assert len(result.blocked_techniques) == 0

    def test_blocked_ids_match_source_techniques(self):
        """Blocked technique IDs should match original technique values."""
        result = self.mapper.map_intent("refund", variant_type="mini_parwa")
        mapping = self.mapper.get_mapping("refund")
        blocked_ids = {b["id"] for b in result.blocked_techniques}
        for bid in blocked_ids:
            assert bid in mapping.recommended_techniques


# ═══════════════════════════════════════════════════════════════════════
# 12. Integration (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestIntegration:
    def setup_method(self):
        self.mapper = IntentTechniqueMapper()

    def test_mini_parwa_all_intents_t1_only(self):
        """GAP-001: All intents on Mini PARWA only use T1 techniques."""
        for intent in self.mapper.get_supported_intents():
            result = self.mapper.map_intent(intent=intent, variant_type="mini_parwa")
            for tid in result.selected_techniques:
                assert tid in (
                    TechniqueID.CLARA,
                    TechniqueID.CRP,
                    TechniqueID.GSD,
                ), f"{intent} has non-T1 technique {tid} on mini_parwa"

    def test_parwa_no_t3_techniques(self):
        """Parwa should never return T3 techniques."""
        t3_ids = {
            TechniqueID.GST,
            TechniqueID.UNIVERSE_OF_THOUGHTS,
            TechniqueID.TREE_OF_THOUGHTS,
            TechniqueID.SELF_CONSISTENCY,
            TechniqueID.REFLEXION,
            TechniqueID.LEAST_TO_MOST,
        }
        for intent in self.mapper.get_supported_intents():
            result = self.mapper.map_intent(intent=intent, variant_type="parwa")
            for tid in result.selected_techniques:
                assert tid not in t3_ids, f"{intent} has T3 technique {tid} on parwa"

    def test_parwa_high_has_original_techniques(self):
        """Parwa High should have all original techniques."""
        for intent in self.mapper.get_supported_intents():
            result = self.mapper.map_intent(intent=intent, variant_type="parwa_high")
            mapping = self.mapper.get_mapping(intent)
            original_ids = set(mapping.recommended_techniques)
            selected_ids = {t.value for t in result.selected_techniques}
            assert (
                original_ids == selected_ids
            ), f"{intent}: parwa_high selected {selected_ids} != original {original_ids}"

    def test_fallback_applied_only_when_needed(self):
        result_t3 = self.mapper.map_intent("refund", variant_type="parwa")
        # refund has self_consistency (T3) and step_back (T2), parwa blocks T3
        assert result_t3.fallback_applied is True

        result_t2 = self.mapper.map_intent("technical", variant_type="parwa")
        # technical only has T2 techniques, parwa allows them
        assert result_t2.fallback_applied is False

    def test_selected_tiers_match_techniques(self):
        """Each selected technique should have a matching tier."""
        result = self.mapper.map_intent("technical", variant_type="parwa_high")
        assert len(result.selected_techniques) == len(result.selected_tiers)

    def test_variant_type_in_result(self):
        result = self.mapper.map_intent("refund", variant_type="parwa", company_id="c1")
        assert result.variant_type == "parwa"

    def test_intent_in_result(self):
        result = self.mapper.map_intent("billing", variant_type="parwa")
        assert result.intent == "billing"

    def test_no_duplicate_selected_techniques(self):
        """Fallback deduplication: no duplicate techniques in selected."""
        for intent in self.mapper.get_supported_intents():
            result = self.mapper.map_intent(intent=intent, variant_type="mini_parwa")
            selected_ids = [t.value for t in result.selected_techniques]
            assert len(selected_ids) == len(
                set(selected_ids)
            ), f"{intent} has duplicate techniques on mini_parwa"


# ═══════════════════════════════════════════════════════════════════════
# 13. Edge Cases (5+ tests)
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def setup_method(self):
        self.mapper = IntentTechniqueMapper()

    def test_empty_intent(self):
        result = self.mapper.map_intent("", variant_type="parwa")
        assert result.selected_techniques == []
        assert result.fallback_applied is False

    def test_whitespace_intent(self):
        result = self.mapper.map_intent("   ", variant_type="parwa")
        assert result.selected_techniques == []

    def test_very_long_intent_string(self):
        result = self.mapper.map_intent("a" * 10000, variant_type="parwa")
        assert result.selected_techniques == []

    def test_none_intent_handled(self):
        """None should not crash."""
        result = self.mapper.map_intent(None, variant_type="parwa")
        assert result.selected_techniques == []

    def test_case_sensitive_intent(self):
        result = self.mapper.map_intent("REFUND", variant_type="parwa")
        # Intent lookup is case-sensitive
        assert result.selected_techniques == []

    def test_numeric_intent(self):
        result = self.mapper.map_intent(123, variant_type="parwa")
        assert result.selected_techniques == []


# ═══════════════════════════════════════════════════════════════════════
# Additional tests for coverage
# ═══════════════════════════════════════════════════════════════════════


class TestVARIANT_TIER_LIMITS:
    def test_3_variants(self):
        assert len(VARIANT_TIER_LIMITS) == 3

    def test_keys(self):
        assert set(VARIANT_TIER_LIMITS.keys()) == {"mini_parwa", "parwa", "parwa_high"}


class TestINTENT_TECHNIQUE_MAP:
    def test_12_intents(self):
        assert len(INTENT_TECHNIQUE_MAP) == 12

    def test_each_intent_has_required_keys(self):
        for intent, config in INTENT_TECHNIQUE_MAP.items():
            assert "techniques" in config
            assert "tiers" in config
            assert "trigger" in config

    def test_techniques_and_tiers_same_length(self):
        for intent, config in INTENT_TECHNIQUE_MAP.items():
            assert len(config["techniques"]) == len(
                config["tiers"]
            ), f"{intent}: {len(config['techniques'])} techniques != {len(config['tiers'])} tiers"


class TestTECHNIQUE_TIER1_FALLBACKS:
    def test_all_t2_and_t3_have_fallbacks(self):
        """All T2 and T3 techniques should have T1 fallbacks."""
        t2_t3 = [
            TechniqueID.CHAIN_OF_THOUGHT,
            TechniqueID.REVERSE_THINKING,
            TechniqueID.REACT,
            TechniqueID.STEP_BACK,
            TechniqueID.THREAD_OF_THOUGHT,
            TechniqueID.GST,
            TechniqueID.UNIVERSE_OF_THOUGHTS,
            TechniqueID.TREE_OF_THOUGHTS,
            TechniqueID.SELF_CONSISTENCY,
            TechniqueID.REFLEXION,
            TechniqueID.LEAST_TO_MOST,
        ]
        for tid in t2_t3:
            assert tid in TECHNIQUE_TIER1_FALLBACKS, f"{tid} missing from fallback map"


class TestFallbackDeduplication:
    def test_no_duplicate_fallbacks_for_refund(self):
        """Refund: Step-Back (T2) → GSD, Self-Consistency (T3) → CRP on Mini."""
        mapper = IntentTechniqueMapper()
        result = mapper.map_intent(intent="refund", variant_type="mini_parwa")
        selected_ids = [t.value for t in result.selected_techniques]
        assert len(selected_ids) == len(set(selected_ids))

    def test_no_duplicate_fallbacks_for_complaint(self):
        """Complaint: UoT (T3) → CLARA, Step-Back (T2) → GSD on Mini."""
        mapper = IntentTechniqueMapper()
        result = mapper.map_intent(intent="complaint", variant_type="mini_parwa")
        selected_ids = [t.value for t in result.selected_techniques]
        assert len(selected_ids) == len(set(selected_ids))

    def test_no_duplicate_fallbacks_for_escalation(self):
        """Escalation: Reflexion (T3) → GSD, UoT (T3) → CLARA on Mini."""
        mapper = IntentTechniqueMapper()
        result = mapper.map_intent(intent="escalation", variant_type="mini_parwa")
        selected_ids = [t.value for t in result.selected_techniques]
        assert len(selected_ids) == len(set(selected_ids))


class TestMappingTriggerConditions:
    def test_all_intents_have_trigger(self):
        mapper = IntentTechniqueMapper()
        for intent in mapper.get_supported_intents():
            mapping = mapper.get_mapping(intent)
            assert mapping.trigger_conditions != ""
            assert len(mapping.trigger_conditions) > 5

    def test_trigger_is_string(self):
        mapper = IntentTechniqueMapper()
        mapping = mapper.get_mapping("refund")
        assert isinstance(mapping.trigger_conditions, str)
