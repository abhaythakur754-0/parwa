"""
Tests for SG-02 Technique Tier Access Check — Week 9 Day 9
"""

import time
from unittest.mock import MagicMock, patch

import pytest


# Module-level stubs
TechniqueTierAccessChecker = None  # type: ignore[assignment,misc]
TierAccessDecision = None  # type: ignore[assignment,misc]
TierAccessResult = None  # type: ignore[assignment,misc]
VariantTierConfig = None  # type: ignore[assignment,misc]
_TECHNIQUE_TO_TIER = None  # type: ignore[assignment,misc]
_TIER_1_TECHNIQUES = None  # type: ignore[assignment,misc]
_TIER_2_TECHNIQUES = None  # type: ignore[assignment,misc]
_TIER_3_TECHNIQUES = None  # type: ignore[assignment,misc]
_DOWNGRADE_FALLBACK = None  # type: ignore[assignment,misc]
_FALLBACK_T3_TO_T1 = None  # type: ignore[assignment,misc]
_FALLBACK_T2_TO_T1 = None  # type: ignore[assignment,misc]
_CACHE_TTL_SECONDS = None  # type: ignore[assignment,misc]


@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("backend.app.logger.get_logger", return_value=MagicMock()):
        from backend.app.core.technique_tier_access import (
            TechniqueTierAccessChecker,
            TierAccessDecision,
            TierAccessResult,
            VariantTierConfig,
            _TECHNIQUE_TO_TIER,
            _TIER_1_TECHNIQUES,
            _TIER_2_TECHNIQUES,
            _TIER_3_TECHNIQUES,
            _DOWNGRADE_FALLBACK,
            _FALLBACK_T3_TO_T1,
            _FALLBACK_T2_TO_T1,
            _CACHE_TTL_SECONDS,
        )
        globals().update({
            "TechniqueTierAccessChecker": TechniqueTierAccessChecker,
            "TierAccessDecision": TierAccessDecision,
            "TierAccessResult": TierAccessResult,
            "VariantTierConfig": VariantTierConfig,
            "_TECHNIQUE_TO_TIER": _TECHNIQUE_TO_TIER,
            "_TIER_1_TECHNIQUES": _TIER_1_TECHNIQUES,
            "_TIER_2_TECHNIQUES": _TIER_2_TECHNIQUES,
            "_TIER_3_TECHNIQUES": _TIER_3_TECHNIQUES,
            "_DOWNGRADE_FALLBACK": _DOWNGRADE_FALLBACK,
            "_FALLBACK_T3_TO_T1": _FALLBACK_T3_TO_T1,
            "_FALLBACK_T2_TO_T1": _FALLBACK_T2_TO_T1,
            "_CACHE_TTL_SECONDS": _CACHE_TTL_SECONDS,
        })


# ═══════════════════════════════════════════════════════════════════
# Module Constants Tests
# ═══════════════════════════════════════════════════════════════════


class TestConstants:
    """Tests for module-level constants and mappings."""

    def test_tier_1_has_3_techniques(self):
        assert len(_TIER_1_TECHNIQUES) == 3

    def test_tier_2_has_5_techniques(self):
        assert len(_TIER_2_TECHNIQUES) == 5

    def test_tier_3_has_6_techniques(self):
        assert len(_TIER_3_TECHNIQUES) == 6

    def test_all_techniques_have_tier_mapping(self):
        all_techniques = _TIER_1_TECHNIQUES + _TIER_2_TECHNIQUES + _TIER_3_TECHNIQUES
        for tid in all_techniques:
            assert tid in _TECHNIQUE_TO_TIER, f"{tid} missing from _TECHNIQUE_TO_TIER"

    def test_fallback_t3_to_t1_has_6_entries(self):
        assert len(_FALLBACK_T3_TO_T1) == 6

    def test_fallback_t2_to_t1_has_5_entries(self):
        assert len(_FALLBACK_T2_TO_T1) == 5

    def test_downgrade_fallback_has_11_entries(self):
        assert len(_DOWNGRADE_FALLBACK) == 11

    def test_cache_ttl_is_60_seconds(self):
        assert _CACHE_TTL_SECONDS == 60

    def test_fallback_targets_are_tier_1(self):
        """Every fallback target must be a Tier 1 technique."""
        tier_1_set = set(_TIER_1_TECHNIQUES)
        for src, dst in _DOWNGRADE_FALLBACK.items():
            assert dst in tier_1_set, f"Fallback {src}→{dst}: {dst} is not Tier 1"

    def test_no_fallback_for_tier_1_techniques(self):
        """Tier 1 techniques should never appear as keys in fallback maps."""
        for tid in _TIER_1_TECHNIQUES:
            assert tid not in _DOWNGRADE_FALLBACK, f"{tid} is Tier 1 but has a fallback"

    def test_technique_to_tier_covers_all_techniques(self):
        all_techniques = _TIER_1_TECHNIQUES + _TIER_2_TECHNIQUES + _TIER_3_TECHNIQUES
        assert len(_TECHNIQUE_TO_TIER) == len(all_techniques)

    def test_fallback_t3_keys_match_tier_3_techniques(self):
        assert set(_FALLBACK_T3_TO_T1.keys()) == set(_TIER_3_TECHNIQUES)

    def test_fallback_t2_keys_match_tier_2_techniques(self):
        assert set(_FALLBACK_T2_TO_T1.keys()) == set(_TIER_2_TECHNIQUES)


# ═══════════════════════════════════════════════════════════════════
# Dataclass Tests
# ═══════════════════════════════════════════════════════════════════


class TestDataclasses:
    """Tests for TierAccessDecision, TierAccessResult, VariantTierConfig."""

    def test_tier_access_decision_values(self):
        assert TierAccessDecision.ALLOWED.value == "allowed"
        assert TierAccessDecision.BLOCKED.value == "blocked"
        assert TierAccessDecision.DOWNGRADED.value == "downgraded"
        assert len(TierAccessDecision) == 3

    def test_tier_access_decision_is_str_enum(self):
        assert isinstance(TierAccessDecision.ALLOWED, str)
        assert TierAccessDecision.ALLOWED == "allowed"

    def test_tier_access_result_defaults(self):
        result = TierAccessResult(
            technique="clara",
            requested_tier="tier_1",
            decision=TierAccessDecision.ALLOWED,
            variant_type="parwa",
        )
        assert result.technique == "clara"
        assert result.requested_tier == "tier_1"
        assert result.decision == TierAccessDecision.ALLOWED
        assert result.variant_type == "parwa"
        assert result.effective_tier is None
        assert result.fallback_technique is None
        assert result.reason == ""
        assert result.max_allowed_tier == ""

    def test_tier_access_result_custom_values(self):
        result = TierAccessResult(
            technique="gst",
            requested_tier="tier_3",
            decision=TierAccessDecision.DOWNGRADED,
            variant_type="parwa",
            effective_tier="tier_1",
            fallback_technique="clara",
            reason="downgrade_applied",
            max_allowed_tier="tier_2",
        )
        assert result.technique == "gst"
        assert result.requested_tier == "tier_3"
        assert result.decision == TierAccessDecision.DOWNGRADED
        assert result.effective_tier == "tier_1"
        assert result.fallback_technique == "clara"
        assert result.reason == "downgrade_applied"
        assert result.max_allowed_tier == "tier_2"

    def test_tier_access_result_is_dataclass(self):
        from dataclasses import fields
        result = TierAccessResult(
            technique="clara",
            requested_tier="tier_1",
            decision=TierAccessDecision.ALLOWED,
            variant_type="parwa",
        )
        field_names = {f.name for f in fields(result)}
        expected = {
            "technique", "requested_tier", "decision", "variant_type",
            "effective_tier", "fallback_technique", "reason", "max_allowed_tier",
        }
        assert field_names == expected

    def test_variant_tier_config_defaults(self):
        config = VariantTierConfig(variant_type="parwa", max_tier=2)
        assert config.variant_type == "parwa"
        assert config.max_tier == 2
        assert config.allowed_techniques == []
        assert config.blocked_techniques == []
        assert config.fallback_map == {}

    def test_variant_tier_config_custom(self):
        config = VariantTierConfig(
            variant_type="parwa_high",
            max_tier=3,
            allowed_techniques=["clara", "gst"],
            blocked_techniques=[],
            fallback_map={"gst": "clara"},
        )
        assert config.max_tier == 3
        assert len(config.allowed_techniques) == 2
        assert config.fallback_map["gst"] == "clara"

    def test_variant_tier_config_default_factory_isolation(self):
        config_a = VariantTierConfig(variant_type="a", max_tier=1)
        config_b = VariantTierConfig(variant_type="b", max_tier=1)
        config_a.allowed_techniques.append("clara")
        assert "clara" not in config_b.allowed_techniques


# ═══════════════════════════════════════════════════════════════════
# Initialization Tests
# ═══════════════════════════════════════════════════════════════════


class TestTechniqueTierAccessCheckerInit:
    """Tests for TechniqueTierAccessChecker.__init__."""

    def test_creates_configs_for_all_3_variants(self):
        checker = TechniqueTierAccessChecker()
        assert len(checker._configs) == 3

    def test_parwa_lite_max_tier_1(self):
        checker = TechniqueTierAccessChecker()
        assert checker._configs["parwa_lite"].max_tier == 1

    def test_parwa_max_tier_2(self):
        checker = TechniqueTierAccessChecker()
        assert checker._configs["parwa"].max_tier == 2

    def test_parwa_high_max_tier_3(self):
        checker = TechniqueTierAccessChecker()
        assert checker._configs["parwa_high"].max_tier == 3

    def test_cache_empty_on_init(self):
        checker = TechniqueTierAccessChecker()
        assert len(checker._cache) == 0
        assert len(checker._cache_timestamps) == 0

    def test_parwa_lite_allowed_3_techniques(self):
        checker = TechniqueTierAccessChecker()
        assert len(checker._configs["parwa_lite"].allowed_techniques) == 3

    def test_parwa_allowed_8_techniques(self):
        checker = TechniqueTierAccessChecker()
        assert len(checker._configs["parwa"].allowed_techniques) == 8

    def test_parwa_high_allowed_14_techniques(self):
        checker = TechniqueTierAccessChecker()
        assert len(checker._configs["parwa_high"].allowed_techniques) == 14

    def test_parwa_lite_blocked_11_techniques(self):
        checker = TechniqueTierAccessChecker()
        assert len(checker._configs["parwa_lite"].blocked_techniques) == 11

    def test_parwa_blocked_6_techniques(self):
        checker = TechniqueTierAccessChecker()
        assert len(checker._configs["parwa"].blocked_techniques) == 6

    def test_parwa_high_blocked_0_techniques(self):
        checker = TechniqueTierAccessChecker()
        assert len(checker._configs["parwa_high"].blocked_techniques) == 0

    def test_parwa_lite_fallback_map_has_11_entries(self):
        checker = TechniqueTierAccessChecker()
        assert len(checker._configs["parwa_lite"].fallback_map) == 11

    def test_parwa_fallback_map_has_6_entries(self):
        checker = TechniqueTierAccessChecker()
        assert len(checker._configs["parwa"].fallback_map) == 6

    def test_parwa_high_fallback_map_is_empty(self):
        checker = TechniqueTierAccessChecker()
        assert len(checker._configs["parwa_high"].fallback_map) == 0

    def test_parwa_lite_allowed_contains_tier_1(self):
        checker = TechniqueTierAccessChecker()
        for tid in _TIER_1_TECHNIQUES:
            assert tid in checker._configs["parwa_lite"].allowed_techniques

    def test_parwa_allowed_contains_tier_1_and_tier_2(self):
        checker = TechniqueTierAccessChecker()
        for tid in _TIER_1_TECHNIQUES + _TIER_2_TECHNIQUES:
            assert tid in checker._configs["parwa"].allowed_techniques


# ═══════════════════════════════════════════════════════════════════
# check_access Tests
# ═══════════════════════════════════════════════════════════════════


class TestCheckAccess:
    """Tests for TechniqueTierAccessChecker.check_access."""

    def test_parwa_lite_allows_clara(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("clara", "parwa_lite")
        assert result.decision == TierAccessDecision.ALLOWED

    def test_parwa_lite_allows_crp(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("crp", "parwa_lite")
        assert result.decision == TierAccessDecision.ALLOWED

    def test_parwa_lite_allows_gsd(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("gsd", "parwa_lite")
        assert result.decision == TierAccessDecision.ALLOWED

    def test_parwa_lite_blocks_chain_of_thought(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("chain_of_thought", "parwa_lite")
        assert result.decision == TierAccessDecision.DOWNGRADED

    def test_parwa_lite_blocks_gst(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("gst", "parwa_lite")
        assert result.decision == TierAccessDecision.DOWNGRADED

    def test_parwa_lite_downgrade_has_fallback(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("gst", "parwa_lite")
        assert result.fallback_technique == "clara"
        assert result.effective_tier == "tier_1"

    def test_parwa_lite_chain_of_thought_fallback(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("chain_of_thought", "parwa_lite")
        assert result.fallback_technique == "crp"

    def test_parwa_allows_chain_of_thought(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("chain_of_thought", "parwa")
        assert result.decision == TierAccessDecision.ALLOWED

    def test_parwa_blocks_gst(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("gst", "parwa")
        assert result.decision == TierAccessDecision.DOWNGRADED

    def test_parwa_gst_fallback_to_clara(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("gst", "parwa")
        assert result.fallback_technique == "clara"

    def test_parwa_high_allows_gst(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("gst", "parwa_high")
        assert result.decision == TierAccessDecision.ALLOWED

    def test_parwa_high_allows_all_techniques(self):
        checker = TechniqueTierAccessChecker()
        all_techniques = _TIER_1_TECHNIQUES + _TIER_2_TECHNIQUES + _TIER_3_TECHNIQUES
        for tid in all_techniques:
            result = checker.check_access(tid, "parwa_high")
            assert result.decision == TierAccessDecision.ALLOWED, (
                f"{tid} should be ALLOWED on parwa_high"
            )

    def test_empty_technique_returns_blocked(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("", "parwa")
        assert result.decision == TierAccessDecision.BLOCKED
        assert result.reason == "empty_technique_or_variant"

    def test_empty_variant_returns_blocked(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("clara", "")
        assert result.decision == TierAccessDecision.BLOCKED
        assert result.reason == "empty_technique_or_variant"

    def test_unknown_variant_returns_blocked(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("clara", "unknown_variant")
        assert result.decision == TierAccessDecision.BLOCKED
        assert "unknown_variant" in result.reason

    def test_unknown_technique_returns_blocked(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("nonexistent_tech", "parwa")
        assert result.decision == TierAccessDecision.BLOCKED
        assert "unknown_technique" in result.reason

    def test_case_insensitive_technique(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("CLARA", "parwa_lite")
        assert result.decision == TierAccessDecision.ALLOWED
        assert result.technique == "clara"

    def test_whitespace_trimmed_technique(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("  clara  ", "parwa_lite")
        assert result.decision == TierAccessDecision.ALLOWED
        assert result.technique == "clara"

    def test_case_insensitive_variant(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("clara", "PARWA_LITE")
        assert result.decision == TierAccessDecision.ALLOWED
        assert result.variant_type == "parwa_lite"

    def test_company_id_in_result(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("clara", "parwa", company_id="comp_123")
        assert result.variant_type == "parwa"

    def test_max_allowed_tier_populated(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("clara", "parwa_lite")
        assert result.max_allowed_tier == "tier_1"

    def test_effective_tier_matches_for_allowed(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("clara", "parwa")
        assert result.effective_tier == "tier_1"

    def test_reflexion_blocked_on_parwa(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("reflexion", "parwa")
        assert result.decision == TierAccessDecision.DOWNGRADED
        assert result.fallback_technique == "gsd"

    def test_self_consistency_blocked_on_parwa(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("self_consistency", "parwa")
        assert result.decision == TierAccessDecision.DOWNGRADED
        assert result.fallback_technique == "crp"

    def test_step_back_blocked_on_parwa_lite(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("step_back", "parwa_lite")
        assert result.decision == TierAccessDecision.DOWNGRADED
        assert result.fallback_technique == "gsd"

    def test_thread_of_thought_blocked_on_parwa_lite(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("thread_of_thought", "parwa_lite")
        assert result.decision == TierAccessDecision.DOWNGRADED
        assert result.fallback_technique == "gsd"

    def test_universe_of_thoughts_blocked_on_parwa_lite(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("universe_of_thoughts", "parwa_lite")
        assert result.decision == TierAccessDecision.DOWNGRADED
        assert result.fallback_technique == "clara"

    def test_tree_of_thoughts_blocked_on_parwa_lite(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("tree_of_thoughts", "parwa_lite")
        assert result.decision == TierAccessDecision.DOWNGRADED
        assert result.fallback_technique == "clara"

    def test_least_to_most_blocked_on_parwa_lite(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("least_to_most", "parwa_lite")
        assert result.decision == TierAccessDecision.DOWNGRADED
        assert result.fallback_technique == "clara"

    def test_allowed_result_has_reason(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("clara", "parwa")
        assert "within_variant" in result.reason


# ═══════════════════════════════════════════════════════════════════
# Cache Behavior Tests
# ═══════════════════════════════════════════════════════════════════


class TestCacheBehavior:
    """Tests for the 60-second TTL cache (W9-GAP-029)."""

    def test_first_call_miss_second_hit(self):
        checker = TechniqueTierAccessChecker()
        # First call populates cache
        checker.check_access("clara", "parwa")
        # Cache should now have an entry
        assert len(checker._cache) == 1
        assert len(checker._cache_timestamps) == 1

    def test_cache_returns_same_result(self):
        checker = TechniqueTierAccessChecker()
        result1 = checker.check_access("clara", "parwa")
        result2 = checker.check_access("clara", "parwa")
        assert result1 is result2  # Same object reference

    def test_cache_expires_after_60s(self):
        checker = TechniqueTierAccessChecker()
        # Populate cache
        checker.check_access("clara", "parwa")
        # Fast-forward time past TTL
        original_time = time.time

        with patch("backend.app.core.technique_tier_access.time.time") as mock_time:
            # First call at t=0
            mock_time.return_value = original_time()
            result1 = checker.check_access("clara", "parwa")
            # Advance past 60s
            mock_time.return_value = original_time() + 61
            # This should bypass cache and create new result
            result2 = checker.check_access("clara", "parwa")
            # Results should be different objects (new evaluation)
            assert result1 is not result2

    def test_clear_cache(self):
        checker = TechniqueTierAccessChecker()
        checker.check_access("clara", "parwa")
        checker.check_access("gst", "parwa_high")
        assert len(checker._cache) == 2
        checker.clear_cache()
        assert len(checker._cache) == 0
        assert len(checker._cache_timestamps) == 0

    def test_different_variants_separate_cache(self):
        checker = TechniqueTierAccessChecker()
        checker.check_access("clara", "parwa_lite")
        checker.check_access("clara", "parwa")
        assert len(checker._cache) == 2

    def test_different_techniques_separate_cache(self):
        checker = TechniqueTierAccessChecker()
        checker.check_access("clara", "parwa")
        checker.check_access("crp", "parwa")
        assert len(checker._cache) == 2

    def test_cache_key_format(self):
        checker = TechniqueTierAccessChecker()
        key = checker._cache_key("clara", "parwa")
        assert key == "clara:parwa"

    def test_clear_cache_idempotent(self):
        checker = TechniqueTierAccessChecker()
        checker.clear_cache()  # Should not raise
        checker.clear_cache()
        assert len(checker._cache) == 0


# ═══════════════════════════════════════════════════════════════════
# Batch Operations Tests
# ═══════════════════════════════════════════════════════════════════


class TestBatchOperations:
    """Tests for check_batch_access and filter_techniques."""

    def test_check_batch_access_returns_list(self):
        checker = TechniqueTierAccessChecker()
        results = checker.check_batch_access(["clara", "crp"], "parwa_lite")
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, TierAccessResult) for r in results)

    def test_batch_mixed_allowed_blocked(self):
        checker = TechniqueTierAccessChecker()
        results = checker.check_batch_access(
            ["clara", "chain_of_thought", "gst"],
            "parwa",
        )
        assert results[0].decision == TierAccessDecision.ALLOWED
        assert results[1].decision == TierAccessDecision.ALLOWED
        assert results[2].decision == TierAccessDecision.DOWNGRADED

    def test_batch_empty_list_returns_empty(self):
        checker = TechniqueTierAccessChecker()
        results = checker.check_batch_access([], "parwa")
        assert results == []

    def test_batch_all_allowed(self):
        checker = TechniqueTierAccessChecker()
        results = checker.check_batch_access(
            ["clara", "crp", "gsd"],
            "parwa_lite",
        )
        assert all(r.decision == TierAccessDecision.ALLOWED for r in results)

    def test_batch_all_blocked(self):
        checker = TechniqueTierAccessChecker()
        results = checker.check_batch_access(
            ["gst", "tree_of_thoughts", "reflexion"],
            "parwa",
        )
        assert all(
            r.decision == TierAccessDecision.DOWNGRADED for r in results
        )

    def test_filter_techniques_keeps_allowed(self):
        checker = TechniqueTierAccessChecker()
        filtered = checker.filter_techniques(
            ["clara", "crp", "gsd"],
            "parwa_lite",
        )
        assert set(filtered) == {"clara", "crp", "gsd"}

    def test_filter_techniques_replaces_blocked_with_fallback(self):
        checker = TechniqueTierAccessChecker()
        filtered = checker.filter_techniques(
            ["chain_of_thought"],
            "parwa_lite",
        )
        assert "crp" in filtered
        assert "chain_of_thought" not in filtered

    def test_filter_techniques_dedupes_fallbacks(self):
        checker = TechniqueTierAccessChecker()
        # chain_of_thought→crp, react→crp — should only appear once
        filtered = checker.filter_techniques(
            ["chain_of_thought", "react"],
            "parwa_lite",
        )
        assert filtered.count("crp") == 1

    def test_filter_techniques_dedupes_allowed_and_fallback(self):
        checker = TechniqueTierAccessChecker()
        # clara is allowed AND is fallback for gst
        filtered = checker.filter_techniques(
            ["clara", "gst"],
            "parwa_lite",
        )
        assert filtered.count("clara") == 1

    def test_filter_techniques_drops_blocked_no_fallback(self):
        checker = TechniqueTierAccessChecker()
        filtered = checker.filter_techniques(
            ["unknown_technique_xyz"],
            "parwa",
        )
        assert filtered == []

    def test_filter_techniques_skips_empty_strings(self):
        checker = TechniqueTierAccessChecker()
        filtered = checker.filter_techniques(
            ["", "  ", "clara", ""],
            "parwa_lite",
        )
        assert filtered == ["clara"]

    def test_filter_techniques_preserves_order(self):
        checker = TechniqueTierAccessChecker()
        filtered = checker.filter_techniques(
            ["gsd", "clara", "crp"],
            "parwa_lite",
        )
        assert filtered == ["gsd", "clara", "crp"]


# ═══════════════════════════════════════════════════════════════════
# Query Methods Tests
# ═══════════════════════════════════════════════════════════════════


class TestQueryMethods:
    """Tests for get_allowed_techniques, get_blocked_techniques, etc."""

    def test_get_allowed_techniques_parwa_lite(self):
        checker = TechniqueTierAccessChecker()
        allowed = checker.get_allowed_techniques("parwa_lite")
        assert set(allowed) == set(_TIER_1_TECHNIQUES)

    def test_get_allowed_techniques_parwa(self):
        checker = TechniqueTierAccessChecker()
        allowed = checker.get_allowed_techniques("parwa")
        assert set(allowed) == set(_TIER_1_TECHNIQUES + _TIER_2_TECHNIQUES)

    def test_get_allowed_techniques_parwa_high(self):
        checker = TechniqueTierAccessChecker()
        allowed = checker.get_allowed_techniques("parwa_high")
        all_techs = _TIER_1_TECHNIQUES + _TIER_2_TECHNIQUES + _TIER_3_TECHNIQUES
        assert set(allowed) == set(all_techs)

    def test_get_allowed_techniques_unknown_returns_empty(self):
        checker = TechniqueTierAccessChecker()
        assert checker.get_allowed_techniques("nonexistent") == []

    def test_get_blocked_techniques_parwa_lite(self):
        checker = TechniqueTierAccessChecker()
        blocked = checker.get_blocked_techniques("parwa_lite")
        assert set(blocked) == set(_TIER_2_TECHNIQUES + _TIER_3_TECHNIQUES)

    def test_get_blocked_techniques_parwa_high_empty(self):
        checker = TechniqueTierAccessChecker()
        assert checker.get_blocked_techniques("parwa_high") == []

    def test_get_blocked_techniques_unknown_returns_restrictive(self):
        checker = TechniqueTierAccessChecker()
        blocked = checker.get_blocked_techniques("unknown")
        # Unknown variant returns all T2+T3 as blocked (most restrictive)
        assert set(blocked) == set(_TIER_2_TECHNIQUES + _TIER_3_TECHNIQUES)

    def test_get_tier_for_technique_clara(self):
        checker = TechniqueTierAccessChecker()
        assert checker.get_tier_for_technique("clara") == "tier_1"

    def test_get_tier_for_technique_crp(self):
        checker = TechniqueTierAccessChecker()
        assert checker.get_tier_for_technique("crp") == "tier_1"

    def test_get_tier_for_technique_gsd(self):
        checker = TechniqueTierAccessChecker()
        assert checker.get_tier_for_technique("gsd") == "tier_1"

    def test_get_tier_for_technique_chain_of_thought(self):
        checker = TechniqueTierAccessChecker()
        assert checker.get_tier_for_technique("chain_of_thought") == "tier_2"

    def test_get_tier_for_technique_gst(self):
        checker = TechniqueTierAccessChecker()
        assert checker.get_tier_for_technique("gst") == "tier_3"

    def test_get_tier_for_technique_unknown_empty(self):
        checker = TechniqueTierAccessChecker()
        assert checker.get_tier_for_technique("nonexistent") == ""

    def test_get_tier_for_technique_empty_string(self):
        checker = TechniqueTierAccessChecker()
        assert checker.get_tier_for_technique("") == ""

    def test_get_all_variant_types(self):
        checker = TechniqueTierAccessChecker()
        variants = checker.get_all_variant_types()
        assert set(variants) == {"parwa_lite", "parwa", "parwa_high"}

    def test_get_max_tier_parwa_lite(self):
        checker = TechniqueTierAccessChecker()
        assert checker.get_max_tier("parwa_lite") == 1

    def test_get_max_tier_parwa(self):
        checker = TechniqueTierAccessChecker()
        assert checker.get_max_tier("parwa") == 2

    def test_get_max_tier_parwa_high(self):
        checker = TechniqueTierAccessChecker()
        assert checker.get_max_tier("parwa_high") == 3

    def test_get_max_tier_unknown_returns_0(self):
        checker = TechniqueTierAccessChecker()
        assert checker.get_max_tier("unknown") == 0

    def test_is_variant_valid_true(self):
        checker = TechniqueTierAccessChecker()
        assert checker.is_variant_valid("parwa") is True
        assert checker.is_variant_valid("parwa_lite") is True
        assert checker.is_variant_valid("parwa_high") is True

    def test_is_variant_valid_false(self):
        checker = TechniqueTierAccessChecker()
        assert checker.is_variant_valid("unknown") is False
        assert checker.is_variant_valid("") is False

    def test_get_variant_config_returns_config(self):
        checker = TechniqueTierAccessChecker()
        config = checker.get_variant_config("parwa")
        assert config is not None
        assert isinstance(config, VariantTierConfig)
        assert config.variant_type == "parwa"

    def test_get_variant_config_unknown_returns_none(self):
        checker = TechniqueTierAccessChecker()
        assert checker.get_variant_config("unknown") is None


# ═══════════════════════════════════════════════════════════════════
# Technique Counts Tests
# ═══════════════════════════════════════════════════════════════════


class TestTechniqueCounts:
    """Tests for get_technique_count_for_variant."""

    def test_parwa_lite_counts(self):
        checker = TechniqueTierAccessChecker()
        counts = checker.get_technique_count_for_variant("parwa_lite")
        assert counts["allowed"] == 3
        assert counts["blocked"] == 11
        assert counts["total"] == 14

    def test_parwa_counts(self):
        checker = TechniqueTierAccessChecker()
        counts = checker.get_technique_count_for_variant("parwa")
        assert counts["allowed"] == 8
        assert counts["blocked"] == 6
        assert counts["total"] == 14

    def test_parwa_high_counts(self):
        checker = TechniqueTierAccessChecker()
        counts = checker.get_technique_count_for_variant("parwa_high")
        assert counts["allowed"] == 14
        assert counts["blocked"] == 0
        assert counts["total"] == 14

    def test_unknown_counts_zero(self):
        checker = TechniqueTierAccessChecker()
        counts = checker.get_technique_count_for_variant("unknown")
        assert counts["allowed"] == 0
        assert counts["blocked"] == 0
        assert counts["total"] == 0


# ═══════════════════════════════════════════════════════════════════
# Fallback Lookup Tests
# ═══════════════════════════════════════════════════════════════════


class TestFallbackLookup:
    """Tests for get_fallback_for_technique."""

    def test_fallback_for_gst_on_parwa_lite(self):
        checker = TechniqueTierAccessChecker()
        fb = checker.get_fallback_for_technique("gst", "parwa_lite")
        assert fb == "clara"

    def test_fallback_for_chain_of_thought_on_parwa_lite(self):
        checker = TechniqueTierAccessChecker()
        fb = checker.get_fallback_for_technique("chain_of_thought", "parwa_lite")
        assert fb == "crp"

    def test_fallback_for_gst_on_parwa(self):
        checker = TechniqueTierAccessChecker()
        fb = checker.get_fallback_for_technique("gst", "parwa")
        assert fb == "clara"

    def test_fallback_for_reflexion_on_parwa(self):
        checker = TechniqueTierAccessChecker()
        fb = checker.get_fallback_for_technique("reflexion", "parwa")
        assert fb == "gsd"

    def test_fallback_for_allowed_technique_returns_none(self):
        checker = TechniqueTierAccessChecker()
        fb = checker.get_fallback_for_technique("clara", "parwa_lite")
        assert fb is None

    def test_fallback_on_unknown_variant_uses_global_map(self):
        checker = TechniqueTierAccessChecker()
        fb = checker.get_fallback_for_technique("gst", "unknown")
        assert fb == "clara"

    def test_fallback_on_unknown_technique_returns_none(self):
        checker = TechniqueTierAccessChecker()
        fb = checker.get_fallback_for_technique("nonexistent", "parwa")
        assert fb is None

    def test_fallback_for_all_tier_3_on_parwa(self):
        checker = TechniqueTierAccessChecker()
        for tid in _TIER_3_TECHNIQUES:
            fb = checker.get_fallback_for_technique(tid, "parwa")
            assert fb is not None, f"{tid} should have fallback on parwa"

    def test_fallback_for_all_tier_2_on_parwa_lite(self):
        checker = TechniqueTierAccessChecker()
        for tid in _TIER_2_TECHNIQUES:
            fb = checker.get_fallback_for_technique(tid, "parwa_lite")
            assert fb is not None, f"{tid} should have fallback on parwa_lite"


# ═══════════════════════════════════════════════════════════════════
# Upgrade Technique Tests
# ═══════════════════════════════════════════════════════════════════


class TestUpgradeTechnique:
    """Tests for upgrade_technique."""

    def test_upgrade_parwa_lite_to_parwa_unlocks_t2(self):
        checker = TechniqueTierAccessChecker()
        result = checker.upgrade_technique(
            "chain_of_thought", "parwa_lite", "parwa",
        )
        assert result.decision == TierAccessDecision.ALLOWED

    def test_upgrade_parwa_lite_to_parwa_high_unlocks_all(self):
        checker = TechniqueTierAccessChecker()
        result = checker.upgrade_technique(
            "gst", "parwa_lite", "parwa_high",
        )
        assert result.decision == TierAccessDecision.ALLOWED

    def test_upgrade_parwa_to_parwa_high_unlocks_t3(self):
        checker = TechniqueTierAccessChecker()
        result = checker.upgrade_technique(
            "gst", "parwa", "parwa_high",
        )
        assert result.decision == TierAccessDecision.ALLOWED

    def test_upgrade_same_variant_no_change(self):
        checker = TechniqueTierAccessChecker()
        result = checker.upgrade_technique(
            "clara", "parwa_lite", "parwa_lite",
        )
        assert result.decision == TierAccessDecision.ALLOWED

    def test_upgrade_unknown_variant_from_but_valid_target(self):
        """upgrade_technique returns the TARGET variant's access result."""
        checker = TechniqueTierAccessChecker()
        result = checker.upgrade_technique(
            "clara", "unknown", "parwa",
        )
        # Target parwa allows clara, so result is ALLOWED
        assert result.decision == TierAccessDecision.ALLOWED

    def test_upgrade_to_unknown_variant_returns_blocked(self):
        checker = TechniqueTierAccessChecker()
        result = checker.upgrade_technique(
            "clara", "parwa", "unknown",
        )
        assert result.decision == TierAccessDecision.BLOCKED

    def test_upgrade_t3_still_downgraded_on_parwa(self):
        checker = TechniqueTierAccessChecker()
        result = checker.upgrade_technique(
            "gst", "parwa_lite", "parwa",
        )
        # gst is Tier 3, parwa max is Tier 2 → still downgraded
        assert result.decision == TierAccessDecision.DOWNGRADED
        assert result.fallback_technique == "clara"

    def test_upgrade_case_insensitive(self):
        checker = TechniqueTierAccessChecker()
        result = checker.upgrade_technique(
            "CHAIN_OF_THOUGHT", "PARWA_LITE", "PARWA",
        )
        assert result.decision == TierAccessDecision.ALLOWED


# ═══════════════════════════════════════════════════════════════════
# Validate Pipeline Tests
# ═══════════════════════════════════════════════════════════════════


class TestValidatePipeline:
    """Tests for validate_pipeline."""

    def test_valid_pipeline_all_allowed(self):
        checker = TechniqueTierAccessChecker()
        result = checker.validate_pipeline(
            ["clara", "crp", "gsd"],
            "parwa_lite",
        )
        assert result["valid"] is True
        assert len(result["blocked"]) == 0
        assert set(result["allowed"]) == {"clara", "crp", "gsd"}

    def test_pipeline_with_blocked_techniques(self):
        checker = TechniqueTierAccessChecker()
        result = checker.validate_pipeline(
            ["clara", "unknown_xyz"],
            "parwa",
        )
        assert result["valid"] is False
        assert "unknown_xyz" in result["blocked"]

    def test_pipeline_with_downgraded_techniques(self):
        checker = TechniqueTierAccessChecker()
        result = checker.validate_pipeline(
            ["clara", "chain_of_thought"],
            "parwa_lite",
        )
        # chain_of_thought is downgraded with fallback crp
        assert "chain_of_thought" in result["downgraded"]
        # The fallback crp should be in allowed
        assert "crp" in result["allowed"]
        # No blocked (has fallback)
        assert len(result["blocked"]) == 0
        # Valid because no pure blocks
        assert result["valid"] is True

    def test_empty_pipeline_returns_valid(self):
        checker = TechniqueTierAccessChecker()
        result = checker.validate_pipeline([], "parwa")
        assert result["valid"] is True
        assert result["allowed"] == []
        assert result["blocked"] == []
        assert result["downgraded"] == []
        assert result["details"] == []

    def test_pipeline_with_unknown_techniques(self):
        checker = TechniqueTierAccessChecker()
        result = checker.validate_pipeline(
            ["clara", "unknown_tech"],
            "parwa",
        )
        assert result["valid"] is False
        assert "unknown_tech" in result["blocked"]

    def test_pipeline_result_structure(self):
        checker = TechniqueTierAccessChecker()
        result = checker.validate_pipeline(["clara"], "parwa")
        assert "valid" in result
        assert "allowed" in result
        assert "blocked" in result
        assert "downgraded" in result
        assert "details" in result

    def test_pipeline_details_contain_decision(self):
        checker = TechniqueTierAccessChecker()
        result = checker.validate_pipeline(["clara", "gst"], "parwa")
        assert len(result["details"]) == 2
        assert result["details"][0]["decision"] == "allowed"
        assert result["details"][1]["decision"] == "downgraded"
        assert result["details"][1]["fallback"] == "clara"

    def test_pipeline_ignores_empty_strings(self):
        checker = TechniqueTierAccessChecker()
        result = checker.validate_pipeline(["", "  ", "clara"], "parwa")
        assert result["valid"] is True
        assert len(result["details"]) == 1

    def test_pipeline_mixed_decisions(self):
        checker = TechniqueTierAccessChecker()
        result = checker.validate_pipeline(
            ["clara", "chain_of_thought", "gst", "unknown"],
            "parwa",
        )
        assert len(result["allowed"]) >= 2  # clara, chain_of_thought + fallbacks
        assert "gst" in result["downgraded"]
        assert "unknown" in result["blocked"]
        assert result["valid"] is False


# ═══════════════════════════════════════════════════════════════════
# Compare Variants Tests
# ═══════════════════════════════════════════════════════════════════


class TestCompareVariants:
    """Tests for compare_variants."""

    def test_compare_parwa_lite_vs_parwa_high(self):
        checker = TechniqueTierAccessChecker()
        result = checker.compare_variants("parwa_lite", "parwa_high")
        assert result["variant_a"] == "parwa_lite"
        assert result["variant_b"] == "parwa_high"
        assert result["variant_a_max_tier"] == 1
        assert result["variant_b_max_tier"] == 3
        assert len(result["common"]) == 3  # Tier 1
        assert len(result["only_in_b"]) == 11  # Tier 2 + Tier 3
        assert result["a_has_more"] is False

    def test_compare_parwa_vs_parwa_high(self):
        checker = TechniqueTierAccessChecker()
        result = checker.compare_variants("parwa", "parwa_high")
        assert result["variant_a_max_tier"] == 2
        assert result["variant_b_max_tier"] == 3
        assert len(result["common"]) == 8  # Tier 1 + Tier 2
        assert len(result["only_in_b"]) == 6  # Tier 3
        assert result["a_has_more"] is False

    def test_compare_same_variant(self):
        checker = TechniqueTierAccessChecker()
        result = checker.compare_variants("parwa", "parwa")
        assert len(result["common"]) == 8
        assert len(result["only_in_a"]) == 0
        assert len(result["only_in_b"]) == 0
        assert result["a_has_more"] is False

    def test_compare_unknown_variant_returns_error(self):
        checker = TechniqueTierAccessChecker()
        result = checker.compare_variants("parwa", "unknown")
        assert "error" in result
        assert result["error"] == "unknown_variant"

    def test_compare_both_unknown_returns_error(self):
        checker = TechniqueTierAccessChecker()
        result = checker.compare_variants("unknown_a", "unknown_b")
        assert result["error"] == "unknown_variant"

    def test_compare_parwa_lite_vs_parwa(self):
        checker = TechniqueTierAccessChecker()
        result = checker.compare_variants("parwa_lite", "parwa")
        assert len(result["common"]) == 3  # Tier 1
        assert len(result["only_in_b"]) == 5  # Tier 2
        assert result["a_has_more"] is False

    def test_compare_reversed_order(self):
        checker = TechniqueTierAccessChecker()
        result_ab = checker.compare_variants("parwa_lite", "parwa")
        result_ba = checker.compare_variants("parwa", "parwa_lite")
        # only_in_a and only_in_b should be swapped
        assert result_ab["only_in_a"] == result_ba["only_in_b"]
        assert result_ab["only_in_b"] == result_ba["only_in_a"]


# ═══════════════════════════════════════════════════════════════════
# Edge Cases Tests
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge case and robustness tests."""

    def test_none_technique_id_blocked(self):
        checker = TechniqueTierAccessChecker()
        # None is falsy → treated as empty → blocked
        result = checker.check_access(None, "parwa")  # type: ignore[arg-type]
        assert result.decision == TierAccessDecision.BLOCKED

    def test_none_variant_blocked(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("clara", None)  # type: ignore[arg-type]
        assert result.decision == TierAccessDecision.BLOCKED

    def test_very_long_technique_string(self):
        checker = TechniqueTierAccessChecker()
        long_name = "a" * 500
        result = checker.check_access(long_name, "parwa")
        assert result.decision == TierAccessDecision.BLOCKED
        assert "unknown" in result.reason

    def test_special_characters_in_technique_id(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("clara<script>", "parwa")
        assert result.decision == TierAccessDecision.BLOCKED

    def test_concurrent_access_same_technique(self):
        """Multiple accesses to the same technique+variant should be safe."""
        checker = TechniqueTierAccessChecker()
        results = []
        for _ in range(100):
            result = checker.check_access("clara", "parwa")
            results.append(result)
        # All should be ALLOWED
        assert all(r.decision == TierAccessDecision.ALLOWED for r in results)
        # Cache should still have exactly one entry
        assert len(checker._cache) == 1

    def test_whitespace_only_technique(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("   ", "parwa")
        assert result.decision == TierAccessDecision.BLOCKED

    def test_whitespace_only_variant(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("clara", "   ")
        assert result.decision == TierAccessDecision.BLOCKED

    def test_unicode_technique_name(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("clará", "parwa")
        assert result.decision == TierAccessDecision.BLOCKED

    def test_batch_with_none_in_list(self):
        checker = TechniqueTierAccessChecker()
        # None will be treated as empty string → blocked
        results = checker.check_batch_access(
            [None, "clara"],  # type: ignore[list-item]
            "parwa",
        )
        assert results[0].decision == TierAccessDecision.BLOCKED
        assert results[1].decision == TierAccessDecision.ALLOWED

    def test_filter_with_duplicates(self):
        checker = TechniqueTierAccessChecker()
        filtered = checker.filter_techniques(
            ["clara", "clara", "clara"],
            "parwa_lite",
        )
        assert filtered == ["clara"]

    def test_validate_pipeline_skips_empty_strings(self):
        checker = TechniqueTierAccessChecker()
        result = checker.validate_pipeline(
            ["", "clara", ""],
            "parwa",
        )
        assert len(result["details"]) == 1
        assert result["details"][0]["technique"] == "clara"


# ═══════════════════════════════════════════════════════════════════
# BC-008 Graceful Degradation Tests
# ═══════════════════════════════════════════════════════════════════


class TestBC008GracefulDegradation:
    """Tests for BC-008 graceful degradation requirements."""

    def test_no_crash_on_empty_inputs(self):
        checker = TechniqueTierAccessChecker()
        # Should not raise any exception
        r1 = checker.check_access("", "")
        assert r1.decision == TierAccessDecision.BLOCKED

    def test_no_crash_on_unknown_variant(self):
        checker = TechniqueTierAccessChecker()
        r1 = checker.check_access("clara", "totally_unknown_variant")
        assert r1.decision == TierAccessDecision.BLOCKED

    def test_no_crash_on_unknown_technique(self):
        checker = TechniqueTierAccessChecker()
        r1 = checker.check_access("made_up_technique", "parwa")
        assert r1.decision == TierAccessDecision.BLOCKED

    def test_no_crash_on_none_company_id(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_access("clara", "parwa", company_id=None)  # type: ignore[arg-type]
        assert result.decision == TierAccessDecision.ALLOWED

    def test_no_crash_on_batch_with_empty_list(self):
        checker = TechniqueTierAccessChecker()
        result = checker.check_batch_access([], "parwa")
        assert result == []

    def test_no_crash_on_filter_empty_list(self):
        checker = TechniqueTierAccessChecker()
        result = checker.filter_techniques([], "parwa")
        assert result == []

    def test_no_crash_on_validate_empty_list(self):
        checker = TechniqueTierAccessChecker()
        result = checker.validate_pipeline([], "parwa")
        assert result["valid"] is True
        assert result["allowed"] == []

    def test_no_crash_on_get_tier_empty_string(self):
        checker = TechniqueTierAccessChecker()
        tier = checker.get_tier_for_technique("")
        assert tier == ""

    def test_no_crash_on_compare_unknown_variants(self):
        checker = TechniqueTierAccessChecker()
        result = checker.compare_variants("x", "y")
        assert "error" in result

    def test_no_crash_on_upgrade_empty_variant(self):
        checker = TechniqueTierAccessChecker()
        # Empty from_variant → blocked source, but target parwa allows clara
        result = checker.upgrade_technique("clara", "", "parwa")
        # upgrade_technique returns the TARGET (parwa) result
        assert result.decision == TierAccessDecision.ALLOWED

    def test_no_crash_on_upgrade_empty_technique(self):
        checker = TechniqueTierAccessChecker()
        result = checker.upgrade_technique("", "parwa_lite", "parwa")
        assert result.decision == TierAccessDecision.BLOCKED

    def test_unknown_variant_returns_restrictive_blocked_list(self):
        """BC-008: Unknown variant treated as most restrictive."""
        checker = TechniqueTierAccessChecker()
        blocked = checker.get_blocked_techniques("ghost_variant")
        assert len(blocked) == 11  # All T2 + T3

    def test_unknown_variant_returns_empty_allowed_list(self):
        """BC-008: Unknown variant has no allowed techniques."""
        checker = TechniqueTierAccessChecker()
        allowed = checker.get_allowed_techniques("ghost_variant")
        assert allowed == []

    def test_unknown_variant_max_tier_zero(self):
        """BC-008: Unknown variant returns 0 for max tier."""
        checker = TechniqueTierAccessChecker()
        assert checker.get_max_tier("ghost") == 0

    def test_unknown_variant_not_valid(self):
        checker = TechniqueTierAccessChecker()
        assert checker.is_variant_valid("ghost") is False
