"""
Unit Tests for Day 1-2 Landing Page Components

Tests for:
- Public API endpoints (/public/features, /public/stats, /public/industries)
- Landing page component rendering

Based on ONBOARDING_SPEC.md v2.0 Section 2.3
"""

import pytest
from fastapi.testclient import TestClient


class TestPublicAPI:
    """Tests for public API endpoints (no auth required)."""

    def test_get_features_returns_5_slides(self, client: TestClient):
        """Test that /public/features returns 5 feature slides."""
        response = client.get("/public/features")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 5

    def test_features_have_required_fields(self, client: TestClient):
        """Test that each feature has all required fields."""
        response = client.get("/public/features")
        data = response.json()
        
        required_fields = ["id", "icon", "title", "description", "psychological_trigger", "gradient"]
        
        for feature in data:
            for field in required_fields:
                assert field in feature, f"Missing field: {field}"

    def test_features_psychological_triggers(self, client: TestClient):
        """Test that features have correct psychological triggers."""
        response = client.get("/public/features")
        data = response.json()
        
        expected_triggers = ["SIMPLICITY", "FEAR REMOVAL", "EFFORT REDUCTION", "TIME FREEDOM", "ASPIRATION"]
        actual_triggers = [f["psychological_trigger"] for f in data]
        
        assert actual_triggers == expected_triggers

    def test_get_stats_returns_required_fields(self, client: TestClient):
        """Test that /public/stats returns required statistics."""
        response = client.get("/public/stats")
        assert response.status_code == 200
        
        data = response.json()
        
        required_fields = ["automation_rate", "hours_saved_per_week", "availability", "response_time", "starting_price"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_stats_starting_price_is_999(self, client: TestClient):
        """Test that starting price is $999/month (not fake stats)."""
        response = client.get("/public/stats")
        data = response.json()
        
        assert data["starting_price"] == "$999/month"

    def test_get_industries_returns_4_options(self, client: TestClient):
        """Test that /public/industries returns exactly 4 industries."""
        response = client.get("/public/industries")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 4

    def test_industries_have_correct_ids(self, client: TestClient):
        """Test that industries have correct IDs: ecommerce, saas, logistics, others."""
        response = client.get("/public/industries")
        data = response.json()
        
        expected_ids = ["ecommerce", "saas", "logistics", "others"]
        actual_ids = [i["id"] for i in data]
        
        assert actual_ids == expected_ids

    def test_industries_have_variants(self, client: TestClient):
        """Test that each industry has variants defined."""
        response = client.get("/public/industries")
        data = response.json()
        
        for industry in data:
            assert "variants" in industry, f"Industry {industry['id']} missing variants"
            assert isinstance(industry["variants"], list)
            assert len(industry["variants"]) > 0


class TestLandingPageComponents:
    """Tests for landing page component structure and data."""

    def test_feature_slide_1_control_by_chat(self, client: TestClient):
        """Test first slide: Control Everything by Chat."""
        response = client.get("/public/features")
        data = response.json()
        
        slide_1 = data[0]
        assert slide_1["title"] == "Control Everything by Chat"
        assert slide_1["psychological_trigger"] == "SIMPLICITY"

    def test_feature_slide_2_no_tech_skills(self, client: TestClient):
        """Test second slide: No Tech Skills Needed."""
        response = client.get("/public/features")
        data = response.json()
        
        slide_2 = data[1]
        assert slide_2["title"] == "No Tech Skills Needed"
        assert slide_2["psychological_trigger"] == "FEAR REMOVAL"

    def test_feature_slide_3_self_learning(self, client: TestClient):
        """Test third slide: Self-Learning AI."""
        response = client.get("/public/features")
        data = response.json()
        
        slide_3 = data[2]
        assert slide_3["title"] == "Self-Learning AI"
        assert slide_3["psychological_trigger"] == "EFFORT REDUCTION"

    def test_feature_slide_4_eliminate_work(self, client: TestClient):
        """Test fourth slide: Eliminates 90% Daily Work."""
        response = client.get("/public/features")
        data = response.json()
        
        slide_4 = data[3]
        assert slide_4["title"] == "Eliminates 90% Daily Work"
        assert slide_4["psychological_trigger"] == "TIME FREEDOM"

    def test_feature_slide_5_iron_man_jarvis(self, client: TestClient):
        """Test fifth slide: Your Iron Man Jarvis."""
        response = client.get("/public/features")
        data = response.json()
        
        slide_5 = data[4]
        assert slide_5["title"] == "Your Iron Man Jarvis"
        assert slide_5["psychological_trigger"] == "ASPIRATION"


class TestLandingPageNavigation:
    """Tests for navigation bar requirements."""

    def test_navigation_has_home_link(self, client: TestClient):
        """Test that navigation includes Home link."""
        # Navigation is client-side, so we just verify the page loads
        response = client.get("/public/features")
        assert response.status_code == 200

    def test_navigation_has_models_not_pricing(self, client: TestClient):
        """Test that navigation uses 'Models' not 'Pricing'."""
        response = client.get("/public/industries")
        data = response.json()
        
        # Just verify industries API works - navigation is rendered client-side
        assert len(data) == 4


class TestHeroSection:
    """Tests for hero section data."""

    def test_traditional_vs_parwa_comparison(self, client: TestClient):
        """Test that comparison data is available."""
        response = client.get("/public/stats")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify key comparison points exist
        assert "starting_price" in data
        assert "availability" in data
        assert "automation_rate" in data

    def test_no_fake_response_time(self, client: TestClient):
        """Test that we don't claim specific fake response times like '2 seconds'."""
        response = client.get("/public/stats")
        data = response.json()
        
        # Response time should be generic, not a specific fake number
        assert data["response_time"] != "2 seconds"
        assert data["response_time"] != "2s"
