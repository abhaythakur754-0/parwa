"""Regression tests for onboarding variant resolution and display metadata."""

from app.core.variant_tier_mapper import resolve_tier_from_context, variant_instance_name


def test_selected_variant_list_ranks_each_internal_tier():
    assert resolve_tier_from_context(selected_variants=[{"variant_id": "starter"}]) == "mini_parwa"
    assert resolve_tier_from_context(selected_variants=[{"variant_id": "growth"}]) == "parwa"
    assert resolve_tier_from_context(selected_variants=[{"variant_id": "high"}]) == "parwa_high"


def test_selected_variant_list_chooses_highest_tier():
    assert resolve_tier_from_context(
        selected_variants=[{"variant_id": "starter"}, {"variant_id": "growth"}]
    ) == "parwa"
    assert resolve_tier_from_context(
        selected_variants=[{"variant_id": "growth"}, {"variant_id": "high"}]
    ) == "parwa_high"


def test_unrecognized_selected_variants_keep_safe_default():
    assert resolve_tier_from_context(selected_variants=[{"variant_id": "unknown"}]) == "parwa"


def test_direct_variant_id_keeps_priority_over_selected_variants():
    assert resolve_tier_from_context(
        variant_id="high",
        selected_variants=[{"variant_id": "starter"}],
    ) == "parwa_high"


def test_instance_display_name_uses_canonical_variant():
    assert variant_instance_name("starter") == "Mini Parwa"
    assert variant_instance_name("mini_parwa") == "Mini Parwa"
    assert variant_instance_name("growth") == "Parwa"
    assert variant_instance_name("parwa") == "Parwa"
    assert variant_instance_name("high") == "High Parwa"
    assert variant_instance_name("parwa_high") == "High Parwa"
