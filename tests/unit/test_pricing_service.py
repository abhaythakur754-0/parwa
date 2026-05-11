"""
Day 6: Pricing Service Tests

Tests for pricing_service.py functions:
- get_variant_by_id
- validate_variant_selection
- calculate_totals
- get_cheapest_variant
- get_popular_variant
"""

import pytest

from backend.app.services.pricing_service import (
    get_variant_by_id,
    validate_variant_selection,
    calculate_totals,
    get_cheapest_variant,
    get_popular_variant,
    VALID_INDUSTRIES,
    INDUSTRY_VARIANTS,
)


# ── get_variant_by_id Tests ───────────────────────────────────────────

class TestGetVariantById:
    """Tests for get_variant_by_id function."""

    def test_returns_variant_for_valid_id(self):
        """Should return variant for valid industry and ID."""
        result = get_variant_by_id("ecommerce", "ecom-order")

        assert result is not None
        assert result["id"] == "ecom-order"
        assert result["name"] == "Order Management"

    def test_returns_none_for_invalid_industry(self):
        """Should return None for invalid industry."""
        result = get_variant_by_id("invalid", "ecom-order")

        assert result is None

    def test_returns_none_for_invalid_variant_id(self):
        """Should return None for invalid variant ID."""
        result = get_variant_by_id("ecommerce", "invalid-id")

        assert result is None

    def test_returns_correct_variant_for_each_industry(self):
        """Should return correct variants for each industry."""
        test_cases = [
            ("ecommerce", "ecom-order"),
            ("saas", "saas-tech"),
            ("logistics", "log-track"),
            ("others", "other-general"),
        ]

        for industry, variant_id in test_cases:
            result = get_variant_by_id(industry, variant_id)
            assert result is not None
            assert result["id"] == variant_id


# ── validate_variant_selection Tests ─────────────────────────────────

class TestValidateVariantSelection:
    """Tests for validate_variant_selection function."""

    def test_valid_selection_returns_valid_true(self):
        """Should return valid=True for valid selection."""
        selections = [
            {"id": "ecom-order", "quantity": 2},
            {"id": "ecom-returns", "quantity": 1},
        ]

        result = validate_variant_selection("ecommerce", selections)

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_invalid_industry_returns_error(self):
        """Should return error for invalid industry."""
        selections = [{"id": "test", "quantity": 1}]

        result = validate_variant_selection("invalid", selections)

        assert result["valid"] is False
        assert "Invalid industry" in result["errors"][0]

    def test_invalid_variant_id_returns_error(self):
        """Should return error for invalid variant ID."""
        selections = [{"id": "invalid-variant", "quantity": 1}]

        result = validate_variant_selection("ecommerce", selections)

        assert result["valid"] is False
        assert "not found" in result["errors"][0]

    def test_negative_quantity_returns_error(self):
        """Should return error for negative quantity."""
        selections = [{"id": "ecom-order", "quantity": -1}]

        result = validate_variant_selection("ecommerce", selections)

        assert result["valid"] is False

    def test_quantity_over_10_returns_error(self):
        """Should return error for quantity over 10."""
        selections = [{"id": "ecom-order", "quantity": 11}]

        result = validate_variant_selection("ecommerce", selections)

        assert result["valid"] is False
        assert "exceeds maximum" in result["errors"][0]

    def test_zero_quantity_is_excluded(self):
        """Zero quantity should be excluded from validated list."""
        selections = [
            {"id": "ecom-order", "quantity": 2},
            {"id": "ecom-returns", "quantity": 0},
        ]

        result = validate_variant_selection("ecommerce", selections)

        assert result["valid"] is True
        assert len(result["validated"]) == 1
        assert result["validated"][0]["id"] == "ecom-order"

    def test_validated_includes_correct_totals(self):
        """Validated selections should include calculated totals."""
        selections = [{"id": "ecom-order", "quantity": 2}]

        result = validate_variant_selection("ecommerce", selections)

        assert result["validated"][0]["tickets_per_month"] == 1000  # 500 * 2
        assert result["validated"][0]["price_per_month"] == 198    # 99 * 2


# ── calculate_totals Tests ───────────────────────────────────────────

class TestCalculateTotals:
    """Tests for calculate_totals function."""

    def test_calculates_single_variant(self):
        """Should calculate totals for single variant."""
        selections = [
            {
                "id": "ecom-order",
                "name": "Order Management",
                "quantity": 1,
                "tickets_per_month": 500,
                "price_per_month": 99,
            }
        ]

        result = calculate_totals(selections)

        assert result["total_tickets"] == 500
        assert result["total_monthly"] == 99
        assert result["annual_cost"] == 990  # 99 * 10
        assert result["annual_savings"] == 198  # 99 * 2

    def test_calculates_multiple_variants(self):
        """Should calculate totals for multiple variants."""
        selections = [
            {
                "id": "ecom-order",
                "name": "Order Management",
                "quantity": 2,
                "tickets_per_month": 1000,
                "price_per_month": 198,
            },
            {
                "id": "ecom-returns",
                "name": "Returns & Refunds",
                "quantity": 1,
                "tickets_per_month": 200,
                "price_per_month": 49,
            },
        ]

        result = calculate_totals(selections)

        assert result["total_tickets"] == 1200
        assert result["total_monthly"] == 247
        assert result["annual_cost"] == 2470
        assert result["annual_savings"] == 494

    def test_empty_selection_returns_zeros(self):
        """Should return zeros for empty selection."""
        result = calculate_totals([])

        assert result["total_tickets"] == 0
        assert result["total_monthly"] == 0
        assert result["annual_cost"] == 0
        assert result["annual_savings"] == 0


# ── get_cheapest_variant Tests ───────────────────────────────────────

class TestGetCheapestVariant:
    """Tests for get_cheapest_variant function."""

    def test_returns_cheapest_for_ecommerce(self):
        """Should return cheapest variant for ecommerce."""
        result = get_cheapest_variant("ecommerce")

        assert result is not None
        assert result["price_per_month"] == 39  # Payment Issues

    def test_returns_cheapest_for_saas(self):
        """Should return cheapest variant for saas."""
        result = get_cheapest_variant("saas")

        assert result is not None
        assert result["price_per_month"] == 69  # Billing Support

    def test_returns_none_for_invalid_industry(self):
        """Should return None for invalid industry."""
        result = get_cheapest_variant("invalid")

        assert result is None


# ── get_popular_variant Tests ────────────────────────────────────────

class TestGetPopularVariant:
    """Tests for get_popular_variant function."""

    def test_returns_popular_for_ecommerce(self):
        """Should return popular variant for ecommerce."""
        result = get_popular_variant("ecommerce")

        assert result is not None
        assert result["popular"] is True
        assert result["id"] == "ecom-order"

    def test_returns_popular_for_saas(self):
        """Should return popular variant for saas."""
        result = get_popular_variant("saas")

        assert result is not None
        assert result["popular"] is True
        assert result["id"] == "saas-tech"

    def test_returns_none_for_invalid_industry(self):
        """Should return None for invalid industry."""
        result = get_popular_variant("invalid")

        assert result is None


# ── Constants Tests ──────────────────────────────────────────────────

class TestConstants:
    """Tests for module constants."""

    def test_valid_industries_count(self):
        """Should have 4 valid industries."""
        assert len(VALID_INDUSTRIES) == 4

    def test_valid_industries_values(self):
        """Should have correct industry values."""
        assert "ecommerce" in VALID_INDUSTRIES
        assert "saas" in VALID_INDUSTRIES
        assert "logistics" in VALID_INDUSTRIES
        assert "others" in VALID_INDUSTRIES

    def test_industry_variants_count(self):
        """Each industry should have variants defined."""
        for industry in VALID_INDUSTRIES:
            assert industry in INDUSTRY_VARIANTS
            assert len(INDUSTRY_VARIANTS[industry]) > 0

    def test_each_variant_has_required_fields(self):
        """Each variant should have required fields."""
        required_fields = ["id", "name", "tickets_per_month", "price_per_month"]

        for industry, variants in INDUSTRY_VARIANTS.items():
            for variant in variants:
                for field in required_fields:
                    assert field in variant, f"{industry}/{variant.get('id')} missing {field}"
