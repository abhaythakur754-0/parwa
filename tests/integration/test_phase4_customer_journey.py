"""
Phase 4: Integration Tests — Customer Journey BFF API Routes
Tests that the BFF (Next.js API routes) properly handle:
1. GET /api/onboarding/state (with fallback)
2. POST /api/onboarding/industry-variant
3. POST /api/onboarding/checkout
4. GET /api/onboarding/prerequisites
5. GET /api/onboarding/cost-breakdown
6. Industry catalog endpoint
"""

import json
import os
import pytest
import httpx

# Frontend BFF (may be unavailable in sandbox environments)
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:3000")
# Backend (more stable)
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")


def _frontend_available():
    """Check if frontend BFF is running."""
    try:
        resp = httpx.get(f"{FRONTEND_URL}/api/onboarding/state", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture
def frontend_client():
    return httpx.Client(base_url=FRONTEND_URL, timeout=15.0, follow_redirects=True)


@pytest.fixture
def backend_client():
    return httpx.Client(base_url=BACKEND_URL, timeout=15.0)


# Skip frontend tests if BFF is not running
pytestmark = pytest.mark.skipif(
    not _frontend_available(),
    reason="Frontend BFF not running on {FRONTEND_URL}"
)


class TestOnboardingStateAPI:
    """Test the onboarding state BFF endpoint."""

    def test_get_onboarding_state_returns_200(self, frontend_client):
        """GET /api/onboarding/state should return state (or mock fallback)."""
        resp = frontend_client.get("/api/onboarding/state")
        assert resp.status_code == 200
        data = resp.json()
        assert "current_step" in data or "status" in data

    def test_onboarding_state_has_required_fields(self, frontend_client):
        """Onboarding state should include core fields."""
        resp = frontend_client.get("/api/onboarding/state")
        data = resp.json()
        # Mock fallback includes these fields
        assert "status" in data


class TestIndustryVariantAPI:
    """Test the industry-variant selection BFF endpoint."""

    def test_post_industry_variant_returns_ok(self, frontend_client):
        """POST /api/onboarding/industry-variant should accept industry + variant."""
        resp = frontend_client.post(
            "/api/onboarding/industry-variant",
            json={"industry": "saas", "variant": "parwa"},
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"

    def test_post_industry_variant_ecommerce(self, frontend_client):
        """Test e-commerce industry selection."""
        resp = frontend_client.post(
            "/api/onboarding/industry-variant",
            json={"industry": "ecommerce", "variant": "mini_parwa"},
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200

    def test_post_industry_variant_logistics(self, frontend_client):
        """Test logistics industry selection."""
        resp = frontend_client.post(
            "/api/onboarding/industry-variant",
            json={"industry": "logistics", "variant": "parwa_high"},
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200

    def test_post_industry_variant_other(self, frontend_client):
        """Test 'Other' industry selection."""
        resp = frontend_client.post(
            "/api/onboarding/industry-variant",
            json={"industry": "other", "variant": "parwa"},
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200


class TestCheckoutAPI:
    """Test the checkout BFF endpoint."""

    def test_post_checkout_returns_ok(self, frontend_client):
        """POST /api/onboarding/checkout should accept checkout data."""
        resp = frontend_client.post(
            "/api/onboarding/checkout",
            json={
                "variant": "parwa",
                "addOns": {"voice": True, "customApi": False},
                "totalMonthly": 2698,
            },
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"

    def test_post_checkout_mini_parwa(self, frontend_client):
        """Test checkout with Mini PARWA variant."""
        resp = frontend_client.post(
            "/api/onboarding/checkout",
            json={
                "variant": "mini_parwa",
                "addOns": {"voice": False, "customApi": False},
                "totalMonthly": 999,
            },
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200


class TestPrerequisitesAPI:
    """Test the prerequisites BFF endpoint."""

    def test_get_prerequisites_returns_200(self, frontend_client):
        """GET /api/onboarding/prerequisites should return can_activate flag."""
        resp = frontend_client.get("/api/onboarding/prerequisites")
        assert resp.status_code == 200
        data = resp.json()
        assert "can_activate" in data
        assert "missing" in data


class TestCostBreakdownAPI:
    """Test the cost-breakdown BFF endpoint."""

    def test_get_cost_breakdown_returns_200(self, frontend_client):
        """GET /api/onboarding/cost-breakdown should return breakdown data."""
        resp = frontend_client.get("/api/onboarding/cost-breakdown")
        assert resp.status_code == 200


class TestIndustryCatalogAPI:
    """Test the integration catalog filtering by industry."""

    def test_get_integration_catalog(self, frontend_client):
        """GET /api/integrations/catalog should return catalog."""
        resp = frontend_client.get("/api/integrations/catalog")
        assert resp.status_code == 200

    def test_get_available_integrations(self, frontend_client):
        """GET /api/integrations/available should return available integrations."""
        resp = frontend_client.get("/api/integrations/available")
        # May return 200 or 401/403 depending on auth
        assert resp.status_code in [200, 401, 403]


class TestOnboardingCompleteStepAPI:
    """Test the complete-step BFF endpoint."""

    def test_post_complete_step_1(self, frontend_client):
        """POST /api/onboarding/complete-step?step=1 should work."""
        resp = frontend_client.post("/api/onboarding/complete-step?step=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"

    def test_post_complete_step_6(self, frontend_client):
        """Step 6 (cost breakdown review) should be completable."""
        resp = frontend_client.post("/api/onboarding/complete-step?step=6")
        assert resp.status_code == 200

    def test_post_legal_consent(self, frontend_client):
        """POST /api/onboarding/legal-consent should accept consents."""
        resp = frontend_client.post(
            "/api/onboarding/legal-consent",
            json={
                "accept_terms": True,
                "accept_privacy": True,
                "accept_ai_data": True,
            },
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"

    def test_post_activate(self, frontend_client):
        """POST /api/onboarding/activate should activate."""
        resp = frontend_client.post(
            "/api/onboarding/activate",
            json={
                "ai_name": "Jarvis",
                "ai_tone": "professional",
                "ai_response_style": "concise",
            },
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok" or data.get("activated") == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
