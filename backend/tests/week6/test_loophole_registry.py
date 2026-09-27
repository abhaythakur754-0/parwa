"""
Tests for the Loophole Registry (25-category detection system).

Validates that all 25 categories are properly defined, accessible,
and have valid metadata (detection patterns, severity, group).
"""

import pytest

from app.core.loophole_registry import (
    LOOPHOLE_REGISTRY,
    LoopholeCategory,
    get_all_loopholes,
    get_loophole,
    get_loopholes_by_group,
    get_loopholes_by_severity,
)


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def all_loopholes():
    """Return all 25 registered loophole categories."""
    return get_all_loopholes()


# ── Registry Structure Tests ───────────────────────────────────────


class TestLoopholeRegistryStructure:
    """Validate the structural integrity of the loophole registry."""

    def test_all_25_categories_loaded(self):
        """Exactly 25 loophole categories must be registered."""
        assert len(LOOPHOLE_REGISTRY) == 25

    def test_get_all_loopholes_returns_25(self):
        """get_all_loopholes() should return exactly 25 categories."""
        assert len(get_all_loopholes()) == 25

    def test_all_categories_have_ids_lh_prefix(self, all_loopholes):
        """Every category ID must start with 'LH-'."""
        for cat in all_loopholes:
            assert cat.id.startswith("LH-"), f"{cat.id} does not start with LH-"

    def test_all_categories_have_sequential_ids(self, all_loopholes):
        """Category IDs should be LH-001 through LH-025."""
        ids = {cat.id for cat in all_loopholes}
        for i in range(1, 26):
            expected = f"LH-{i:03d}"
            assert expected in ids, f"Missing category: {expected}"

    def test_registry_keys_match_category_ids(self, all_loopholes):
        """Every registry key must equal the category's id field."""
        for key, cat in LOOPHOLE_REGISTRY.items():
            assert key == cat.id, f"Registry key '{key}' != category.id '{cat.id}'"


# ── Lookup Tests ────────────────────────────────────────────────────


class TestLoopholeLookups:
    """Test registry lookup functions."""

    def test_get_loophole_returns_correct_category(self):
        """get_loophole('LH-001') should return the Hallucination category."""
        cat = get_loophole("LH-001")
        assert cat is not None
        assert cat.id == "LH-001"
        assert cat.name == "Hallucination"
        assert cat.severity == "critical"

    def test_get_loophole_returns_correct_category_last(self):
        """get_loophole('LH-025') should return Numerical Precision Fraud."""
        cat = get_loophole("LH-025")
        assert cat is not None
        assert cat.id == "LH-025"
        assert cat.name == "Numerical Precision Fraud"
        assert cat.severity == "medium"

    def test_get_loophole_nonexistent_returns_none(self):
        """get_loophole() with unknown ID returns None."""
        assert get_loophole("LH-999") is None
        assert get_loophole("") is None
        assert get_loophole("INVALID") is None

    def test_get_loophole_returns_frozen_dataclass(self):
        """Each LoopholeCategory should be a frozen dataclass."""
        cat = get_loophole("LH-001")
        # frozen=True dataclasses raise FrozenInstanceError on mutation
        with pytest.raises(AttributeError):
            cat.id = "MUTATED"  # type: ignore[misc]

    def test_get_loopholes_by_severity_critical(self):
        """Filtering by 'critical' severity returns the right categories."""
        result = get_loopholes_by_severity("critical")
        assert len(result) > 0
        for cat in result:
            assert cat.severity == "critical"
        # Expected critical categories: LH-001, LH-002, LH-003, LH-009, LH-015, LH-021
        critical_ids = {cat.id for cat in result}
        assert "LH-001" in critical_ids
        assert "LH-002" in critical_ids
        assert "LH-003" in critical_ids
        assert "LH-009" in critical_ids
        assert "LH-015" in critical_ids
        assert "LH-021" in critical_ids

    def test_get_loopholes_by_severity_high(self):
        """Filtering by 'high' severity returns only high categories."""
        result = get_loopholes_by_severity("high")
        assert len(result) > 0
        for cat in result:
            assert cat.severity == "high"

    def test_get_loopholes_by_severity_medium(self):
        """Filtering by 'medium' severity returns only medium categories."""
        result = get_loopholes_by_severity("medium")
        assert len(result) > 0
        for cat in result:
            assert cat.severity == "medium"

    def test_get_loopholes_by_severity_low(self):
        """Filtering by 'low' severity returns only low categories."""
        result = get_loopholes_by_severity("low")
        assert len(result) > 0
        for cat in result:
            assert cat.severity == "low"
        # LH-022 Timeout Exploitation is the only low severity
        assert "LH-022" in {cat.id for cat in result}

    def test_get_loopholes_by_severity_case_insensitive(self):
        """Severity filter should be case-insensitive."""
        lower_result = get_loopholes_by_severity("critical")
        upper_result = get_loopholes_by_severity("CRITICAL")
        mixed_result = get_loopholes_by_severity("Critical")
        assert len(lower_result) == len(upper_result) == len(mixed_result)

    def test_get_loopholes_by_severity_unknown_returns_empty(self):
        """Unknown severity level returns empty list."""
        assert get_loopholes_by_severity("nonexistent") == []

    def test_get_loopholes_by_group(self):
        """Filtering by group returns categories in that group."""
        security = get_loopholes_by_group("security")
        assert len(security) > 0
        for cat in security:
            assert cat.category_group == "security"
        security_ids = {cat.id for cat in security}
        assert "LH-002" in security_ids  # PII Leakage
        assert "LH-003" in security_ids  # Unauthorized Access

    def test_get_loopholes_by_group_accuracy(self):
        """Accuracy group should contain hallucination, overconfident, etc."""
        accuracy = get_loopholes_by_group("accuracy")
        assert len(accuracy) > 0
        accuracy_ids = {cat.id for cat in accuracy}
        assert "LH-001" in accuracy_ids  # Hallucination
        assert "LH-011" in accuracy_ids  # Overconfident Claims

    def test_get_loopholes_by_group_case_insensitive(self):
        """Group filter should be case-insensitive."""
        lower = get_loopholes_by_group("security")
        upper = get_loopholes_by_group("SECURITY")
        assert len(lower) == len(upper)

    def test_get_loopholes_by_group_unknown_returns_empty(self):
        """Unknown group returns empty list."""
        assert get_loopholes_by_group("nonexistent") == []

    def test_severity_counts_add_up(self, all_loopholes):
        """The sum of categories across all severities should equal 25."""
        valid_severities = ["critical", "high", "medium", "low"]
        total = sum(len(get_loopholes_by_severity(s)) for s in valid_severities)
        assert total == 25

    def test_group_counts_add_up(self, all_loopholes):
        """The sum of categories across all groups should equal 25."""
        valid_groups = ["accuracy", "security", "compliance", "ethics", "reliability", "brand"]
        total = sum(len(get_loopholes_by_group(g)) for g in valid_groups)
        assert total == 25


# ── Category Metadata Tests ─────────────────────────────────────────


class TestCategoryMetadata:
    """Validate that every category has proper metadata."""

    def test_each_category_has_non_empty_detection_patterns(self, all_loopholes):
        """Every category must have at least one detection pattern."""
        for cat in all_loopholes:
            assert len(cat.detection_patterns) > 0, (
                f"{cat.id} {cat.name} has no detection_patterns"
            )

    def test_each_category_has_valid_severity(self, all_loopholes):
        """Every category severity must be one of: critical, high, medium, low."""
        valid = {"critical", "high", "medium", "low"}
        for cat in all_loopholes:
            assert cat.severity in valid, (
                f"{cat.id} has invalid severity: '{cat.severity}'"
            )

    def test_each_category_has_valid_group(self, all_loopholes):
        """Every category group must be one of the 6 valid groups."""
        valid = {"accuracy", "security", "compliance", "ethics", "reliability", "brand"}
        for cat in all_loopholes:
            assert cat.category_group in valid, (
                f"{cat.id} has invalid group: '{cat.category_group}'"
            )

    def test_each_category_has_non_empty_description(self, all_loopholes):
        """Every category should have a description."""
        for cat in all_loopholes:
            assert len(cat.description) > 10, (
                f"{cat.id} has empty or too-short description"
            )

    def test_each_category_has_non_empty_countermeasure(self, all_loopholes):
        """Every category should have a countermeasure."""
        for cat in all_loopholes:
            assert len(cat.countermeasure) > 10, (
                f"{cat.id} has empty or too-short countermeasure"
            )

    def test_each_category_has_affected_components(self, all_loopholes):
        """Every category should list affected components."""
        for cat in all_loopholes:
            assert len(cat.affected_components) > 0, (
                f"{cat.id} has no affected_components"
            )

    def test_detection_patterns_are_strings(self, all_loopholes):
        """Every detection pattern should be a string."""
        for cat in all_loopholes:
            for pattern in cat.detection_patterns:
                assert isinstance(pattern, str), (
                    f"{cat.id} has non-string pattern: {pattern}"
                )
