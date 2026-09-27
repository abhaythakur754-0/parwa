"""
Day 6: Pricing API Tests

Tests for:
- GET /api/pricing/industries
- GET /api/pricing/variants/{industry}
- POST /api/pricing/calculate
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def valid_industry():
    return "ecommerce"


@pytest.fixture
def invalid_industry():
    return "invalid_industry"


@pytest.fixture
def valid_calculate_request():
    return {
        "industry": "ecommerce",
        "variants": [
            {"id": "ecom-order", "quantity": 2},
            {"id": "ecom-returns", "quantity": 1},
        ],
    }


# ── GET /api/pricing/industries Tests ────────────────────────────────

class TestGetIndustries:
    """Tests for GET /api/pricing/industries endpoint."""

    def test_returns_all_industries(self):
        """Should return all 4 industries."""
        response = client.get("/api/pricing/industries")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4

    def test_industries_have_required_fields(self):
        """Each industry should have id, name, description, color."""
        response = client.get("/api/pricing/industries")
        data = response.json()

        for industry in data:
            assert "id" in industry
            assert "name" in industry
            assert "description" in industry
            assert "color" in industry

    def test_industries_have_correct_ids(self):
        """Should have ecommerce, saas, logistics, others."""
        response = client.get("/api/pricing/industries")
        data = response.json()
        ids = [i["id"] for i in data]

        assert "ecommerce" in ids
        assert "saas" in ids
        assert "logistics" in ids
        assert "others" in ids


# ── GET /api/pricing/variants/{industry} Tests ───────────────────────

class TestGetVariants:
    """Tests for GET /api/pricing/variants/{industry} endpoint."""

    def test_returns_variants_for_valid_industry(self, valid_industry):
        """Should return variants for a valid industry."""
        response = client.get(f"/api/pricing/variants/{valid_industry}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

    def test_variants_have_required_fields(self, valid_industry):
        """Each variant should have required fields."""
        response = client.get(f"/api/pricing/variants/{valid_industry}")
        data = response.json()

        for variant in data:
            assert "id" in variant
            assert "name" in variant
            assert "description" in variant
            assert "tickets_per_month" in variant
            assert "price_per_month" in variant
            assert "features" in variant
            assert "popular" in variant

    def test_returns_404_for_invalid_industry(self, invalid_industry):
        """Should return 404 for invalid industry."""
        response = client.get(f"/api/pricing/variants/{invalid_industry}")

        assert response.status_code == 404

    def test_ecommerce_has_5_variants(self):
        """E-commerce should have 5 variants."""
        response = client.get("/api/pricing/variants/ecommerce")
        data = response.json()

        assert len(data) == 5

    def test_saas_has_5_variants(self):
        """SaaS should have 5 variants."""
        response = client.get("/api/pricing/variants/saas")
        data = response.json()

        assert len(data) == 5

    def test_logistics_has_5_variants(self):
        """Logistics should have 5 variants."""
        response = client.get("/api/pricing/variants/logistics")
        data = response.json()

        assert len(data) == 5

    def test_others_has_4_variants(self):
        """Others should have 4 variants."""
        response = client.get("/api/pricing/variants/others")
        data = response.json()

        assert len(data) == 4

    def test_each_industry_has_one_popular_variant(self):
        """Each industry should have exactly one popular variant."""
        for industry in ["ecommerce", "saas", "logistics", "others"]:
            response = client.get(f"/api/pricing/variants/{industry}")
            data = response.json()

            popular_count = sum(1 for v in data if v["popular"])
            assert popular_count == 1, f"{industry} should have 1 popular variant"


# ── POST /api/pricing/calculate Tests ────────────────────────────────

class TestCalculatePricing:
    """Tests for POST /api/pricing/calculate endpoint."""

    def test_calculate_valid_request(self, valid_calculate_request):
        """Should calculate pricing for valid request."""
        response = client.post(
            "/api/pricing/calculate",
            json=valid_calculate_request,
        )

        assert response.status_code == 200
        data = response.json()

        assert "industry" in data
        assert "variants" in data
        assert "total_tickets" in data
        assert "total_monthly" in data
        assert "annual_cost" in data
        assert "annual_savings" in data

    def test_calculate_total_tickets(self, valid_calculate_request):
        """Should calculate total tickets correctly."""
        response = client.post(
            "/api/pricing/calculate",
            json=valid_calculate_request,
        )
        data = response.json()

        # ecom-order: 500 * 2 = 1000
        # ecom-returns: 200 * 1 = 200
        # Total: 1200
        assert data["total_tickets"] == 1200

    def test_calculate_total_monthly(self, valid_calculate_request):
        """Should calculate total monthly cost correctly."""
        response = client.post(
            "/api/pricing/calculate",
            json=valid_calculate_request,
        )
        data = response.json()

        # ecom-order: 99 * 2 = 198
        # ecom-returns: 49 * 1 = 49
        # Total: 247
        assert data["total_monthly"] == 247

    def test_calculate_annual_cost(self, valid_calculate_request):
        """Should calculate annual cost (10 months)."""
        response = client.post(
            "/api/pricing/calculate",
            json=valid_calculate_request,
        )
        data = response.json()

        # Monthly: 247
        # Annual: 247 * 10 = 2470
        assert data["annual_cost"] == 2470

    def test_calculate_annual_savings(self, valid_calculate_request):
        """Should calculate annual savings (2 months free)."""
        response = client.post(
            "/api/pricing/calculate",
            json=valid_calculate_request,
        )
        data = response.json()

        # Monthly: 247
        # Savings: 247 * 2 = 494
        assert data["annual_savings"] == 494

    def test_invalid_industry_returns_400(self):
        """Should return 400 for invalid industry."""
        request = {
            "industry": "invalid",
            "variants": [{"id": "test", "quantity": 1}],
        }

        response = client.post(
            "/api/pricing/calculate",
            json=request,
        )

        assert response.status_code == 422  # Validation error

    def test_invalid_variant_id_returns_400(self):
        """Should return 400 for variant not in industry."""
        request = {
            "industry": "ecommerce",
            "variants": [{"id": "saas-tech", "quantity": 1}],  # SaaS variant
        }

        response = client.post(
            "/api/pricing/calculate",
            json=request,
        )

        assert response.status_code == 400

    def test_zero_quantity_is_ignored(self):
        """Variants with zero quantity should be ignored."""
        request = {
            "industry": "ecommerce",
            "variants": [
                {"id": "ecom-order", "quantity": 2},
                {"id": "ecom-returns", "quantity": 0},
            ],
        }

        response = client.post(
            "/api/pricing/calculate",
            json=request,
        )
        data = response.json()

        # Only ecom-order with quantity 2 should be counted
        assert len(data["variants"]) == 1
        assert data["variants"][0]["id"] == "ecom-order"

    def test_negative_quantity_returns_422(self):
        """Should return 422 for negative quantity."""
        request = {
            "industry": "ecommerce",
            "variants": [{"id": "ecom-order", "quantity": -1}],
        }

        response = client.post(
            "/api/pricing/calculate",
            json=request,
        )

        assert response.status_code == 422

    def test_quantity_over_10_returns_422(self):
        """Should return 422 for quantity over 10."""
        request = {
            "industry": "ecommerce",
            "variants": [{"id": "ecom-order", "quantity": 11}],
        }

        response = client.post(
            "/api/pricing/calculate",
            json=request,
        )

        assert response.status_code == 422

    def test_empty_variants_returns_422(self):
        """Should return 422 for empty variants list."""
        request = {
            "industry": "ecommerce",
            "variants": [],
        }

        response = client.post(
            "/api/pricing/calculate",
            json=request,
        )

        assert response.status_code == 422


# ── Edge Cases ───────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge case tests for pricing API."""

    def test_all_industries_work(self):
        """All industries should return valid variants."""
        for industry in ["ecommerce", "saas", "logistics", "others"]:
            response = client.get(f"/api/pricing/variants/{industry}")
            assert response.status_code == 200, f"{industry} failed"

    def test_variant_has_features_list(self):
        """Each variant should have a non-empty features list."""
        response = client.get("/api/pricing/variants/ecommerce")
        data = response.json()

        for variant in data:
            assert len(variant["features"]) > 0

    def test_tickets_per_month_is_positive(self):
        """All variants should have positive tickets per month."""
        for industry in ["ecommerce", "saas", "logistics", "others"]:
            response = client.get(f"/api/pricing/variants/{industry}")
            data = response.json()

            for variant in data:
                assert variant["tickets_per_month"] > 0

    def test_price_per_month_is_positive(self):
        """All variants should have positive price per month."""
        for industry in ["ecommerce", "saas", "logistics", "others"]:
            response = client.get(f"/api/pricing/variants/{industry}")
            data = response.json()

            for variant in data:
                assert variant["price_per_month"] > 0

    def test_single_variant_calculation(self):
        """Should correctly calculate for a single variant."""
        request = {
            "industry": "ecommerce",
            "variants": [{"id": "ecom-order", "quantity": 1}],
        }

        response = client.post(
            "/api/pricing/calculate",
            json=request,
        )
        data = response.json()

        assert data["total_tickets"] == 500
        assert data["total_monthly"] == 99
        assert data["annual_cost"] == 990
        assert data["annual_savings"] == 198

    def test_max_quantity_calculation(self):
        """Should correctly calculate with max quantity (10)."""
        request = {
            "industry": "ecommerce",
            "variants": [{"id": "ecom-order", "quantity": 10}],
        }

        response = client.post(
            "/api/pricing/calculate",
            json=request,
        )
        data = response.json()

        assert data["total_tickets"] == 5000  # 500 * 10
        assert data["total_monthly"] == 990   # 99 * 10
