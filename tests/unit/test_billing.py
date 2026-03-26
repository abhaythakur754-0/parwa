"""
Unit tests for PARWA Billing API.
Tests cover subscription management, invoices, payment methods, and usage endpoints.
Uses FastAPI dependency injection for mocking database and services.
"""
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set environment before imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-characters-for-testing!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "development")


# --- Fixtures ---

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_user_dict():
    """Create mock user data."""
    return {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "password_hash": "$2b$12$test_hash",
        "role": "manager",
        "company_id": uuid.uuid4(),
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def mock_subscription_dict():
    """Create mock subscription data."""
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "company_id": uuid.uuid4(),
        "plan_tier": "parwa",
        "status": "active",
        "current_period_start": now,
        "current_period_end": now + timedelta(days=30),
        "amount_cents": 250000,
        "currency": "usd",
        "stripe_subscription_id": "sub_test123456",
    }


# --- Tests ---

class TestBillingEndpointsAuthRequired:
    """Test billing endpoints require authentication."""

    def test_subscription_missing_auth(self):
        """Test subscription endpoint without auth returns 401 or 403."""
        app = FastAPI()
        
        # Import router dynamically
        from backend.api.billing import router
        app.include_router(router)
        
        # Override get_db to avoid database connection
        async def override_get_db():
            yield AsyncMock()
        
        from backend.app.dependencies import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        with TestClient(app) as client:
            response = client.get("/billing/subscription")
            assert response.status_code in (401, 403)

    def test_update_subscription_missing_auth(self):
        """Test update subscription endpoint without auth returns 401 or 403."""
        app = FastAPI()
        
        from backend.api.billing import router
        app.include_router(router)
        
        async def override_get_db():
            yield AsyncMock()
        
        from backend.app.dependencies import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        with TestClient(app) as client:
            response = client.put("/billing/subscription", json={"plan_tier": "parwa_high"})
            assert response.status_code in (401, 403)

    def test_invoices_missing_auth(self):
        """Test invoices endpoint without auth returns 401 or 403."""
        app = FastAPI()
        
        from backend.api.billing import router
        app.include_router(router)
        
        async def override_get_db():
            yield AsyncMock()
        
        from backend.app.dependencies import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        with TestClient(app) as client:
            response = client.get("/billing/invoices")
            assert response.status_code in (401, 403)

    def test_invoice_detail_missing_auth(self):
        """Test invoice detail endpoint without auth returns 401 or 403."""
        app = FastAPI()
        
        from backend.api.billing import router
        app.include_router(router)
        
        async def override_get_db():
            yield AsyncMock()
        
        from backend.app.dependencies import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        with TestClient(app) as client:
            response = client.get(f"/billing/invoices/{uuid.uuid4()}")
            assert response.status_code in (401, 403)

    def test_payment_method_missing_auth(self):
        """Test payment method endpoint without auth returns 401 or 403."""
        app = FastAPI()
        
        from backend.api.billing import router
        app.include_router(router)
        
        async def override_get_db():
            yield AsyncMock()
        
        from backend.app.dependencies import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        with TestClient(app) as client:
            response = client.post("/billing/payment-method", json={"token": "tok_test"})
            assert response.status_code in (401, 403)

    def test_usage_missing_auth(self):
        """Test usage endpoint without auth returns 401 or 403."""
        app = FastAPI()
        
        from backend.api.billing import router
        app.include_router(router)
        
        async def override_get_db():
            yield AsyncMock()
        
        from backend.app.dependencies import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        with TestClient(app) as client:
            response = client.get("/billing/usage")
            assert response.status_code in (401, 403)


# --- Helper Function Tests ---

class TestHelperFunctions:
    """Test helper functions."""

    def test_mask_stripe_id_with_valid_id(self):
        """Test Stripe ID masking."""
        from backend.api.billing import mask_stripe_id

        result = mask_stripe_id("sub_1234567890abcdef")
        assert result == "***cdef"
        assert "sub_" not in result

    def test_mask_stripe_id_with_none(self):
        """Test Stripe ID masking with None."""
        from backend.api.billing import mask_stripe_id

        result = mask_stripe_id(None)
        assert result is None

    def test_mask_stripe_id_with_short_id(self):
        """Test Stripe ID masking with short ID."""
        from backend.api.billing import mask_stripe_id

        result = mask_stripe_id("abc")
        assert result == "***"

    def test_validate_plan_tier_valid(self):
        """Test plan tier validation with valid tiers."""
        from backend.api.billing import validate_plan_tier

        assert validate_plan_tier("mini") == "mini"
        assert validate_plan_tier("parwa") == "parwa"
        assert validate_plan_tier("parwa_high") == "parwa_high"

    def test_validate_plan_tier_invalid(self):
        """Test plan tier validation with invalid tier."""
        from backend.api.billing import validate_plan_tier
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_plan_tier("enterprise")

        assert exc_info.value.status_code == 400

    def test_plan_pricing_config(self):
        """Test plan pricing configuration exists."""
        from backend.api.billing import PLAN_PRICING

        assert "mini" in PLAN_PRICING
        assert "parwa" in PLAN_PRICING
        assert "parwa_high" in PLAN_PRICING
        
        assert PLAN_PRICING["mini"]["monthly_cents"] == 100000
        assert PLAN_PRICING["parwa"]["monthly_cents"] == 250000
        assert PLAN_PRICING["parwa_high"]["monthly_cents"] == 450000


class TestSubscriptionEndpoints:
    """Test subscription endpoints with authentication."""

    def test_get_subscription_not_found(self, mock_db, mock_user_dict):
        """Test subscription endpoint returns 404 when no subscription found."""
        app = FastAPI()
        from backend.api.billing import router
        from backend.app.dependencies import get_db

        app.include_router(router)
        
        # Mock the decode and blacklist check
        with patch("backend.api.billing.decode_access_token") as mock_decode, \
             patch("backend.api.billing.is_token_blacklisted", new_callable=AsyncMock) as mock_blacklist:
            
            valid_payload = {
                "sub": str(mock_user_dict["id"]),
                "email": mock_user_dict["email"],
                "role": mock_user_dict["role"],
                "company_id": str(mock_user_dict["company_id"]),
            }
            mock_decode.return_value = valid_payload
            mock_blacklist.return_value = False

            # Create mock user
            mock_user = MagicMock()
            mock_user.id = mock_user_dict["id"]
            mock_user.company_id = mock_user_dict["company_id"]
            mock_user.is_active = True
            mock_user.role = mock_user_dict["role"]

            # First call: user lookup, Second call: subscription lookup (returns None)
            mock_user_result = MagicMock()
            mock_user_result.scalar_one_or_none.return_value = mock_user
            
            mock_sub_result = MagicMock()
            mock_sub_result.scalar_one_or_none.return_value = None
            
            mock_db.execute = AsyncMock(side_effect=[mock_user_result, mock_sub_result])
            
            async def override_get_db():
                yield mock_db
            
            app.dependency_overrides[get_db] = override_get_db

            with TestClient(app) as client:
                response = client.get(
                    "/billing/subscription",
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 404
            assert "No active subscription" in response.json()["detail"]

    def test_get_subscription_success(self, mock_db, mock_user_dict, mock_subscription_dict):
        """Test subscription endpoint returns subscription data."""
        app = FastAPI()
        from backend.api.billing import router
        from backend.app.dependencies import get_db

        app.include_router(router)
        
        with patch("backend.api.billing.decode_access_token") as mock_decode, \
             patch("backend.api.billing.is_token_blacklisted", new_callable=AsyncMock) as mock_blacklist:
            
            valid_payload = {
                "sub": str(mock_user_dict["id"]),
                "email": mock_user_dict["email"],
                "role": mock_user_dict["role"],
                "company_id": str(mock_user_dict["company_id"]),
            }
            mock_decode.return_value = valid_payload
            mock_blacklist.return_value = False

            # Create mock user
            mock_user = MagicMock()
            mock_user.id = mock_user_dict["id"]
            mock_user.company_id = mock_user_dict["company_id"]
            mock_user.is_active = True
            mock_user.role = mock_user_dict["role"]

            # Create mock subscription
            mock_subscription = MagicMock()
            mock_subscription.id = mock_subscription_dict["id"]
            mock_subscription.company_id = mock_subscription_dict["company_id"]
            mock_subscription.plan_tier = mock_subscription_dict["plan_tier"]
            mock_subscription.status = mock_subscription_dict["status"]
            mock_subscription.current_period_start = mock_subscription_dict["current_period_start"]
            mock_subscription.current_period_end = mock_subscription_dict["current_period_end"]
            mock_subscription.amount_cents = mock_subscription_dict["amount_cents"]
            mock_subscription.currency = mock_subscription_dict["currency"]
            mock_subscription.stripe_subscription_id = mock_subscription_dict["stripe_subscription_id"]

            mock_user_result = MagicMock()
            mock_user_result.scalar_one_or_none.return_value = mock_user
            
            mock_sub_result = MagicMock()
            mock_sub_result.scalar_one_or_none.return_value = mock_subscription
            
            mock_db.execute = AsyncMock(side_effect=[mock_user_result, mock_sub_result])
            
            async def override_get_db():
                yield mock_db
            
            app.dependency_overrides[get_db] = override_get_db

            with TestClient(app) as client:
                response = client.get(
                    "/billing/subscription",
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["plan_tier"] == "parwa"
            assert data["status"] == "active"


class TestSubscriptionUpdate:
    """Test subscription update endpoint."""

    def test_update_subscription_viewer_forbidden(self, mock_db, mock_user_dict):
        """Test that viewers cannot update subscription."""
        app = FastAPI()
        from backend.api.billing import router
        from backend.app.dependencies import get_db

        app.include_router(router)
        
        # Set role to viewer (not manager/admin)
        mock_user_dict["role"] = "viewer"

        with patch("backend.api.billing.decode_access_token") as mock_decode, \
             patch("backend.api.billing.is_token_blacklisted", new_callable=AsyncMock) as mock_blacklist:
            
            valid_payload = {
                "sub": str(mock_user_dict["id"]),
                "email": mock_user_dict["email"],
                "role": "viewer",
                "company_id": str(mock_user_dict["company_id"]),
            }
            mock_decode.return_value = valid_payload
            mock_blacklist.return_value = False

            # Create mock user with viewer role
            mock_user = MagicMock()
            mock_user.id = mock_user_dict["id"]
            mock_user.company_id = mock_user_dict["company_id"]
            mock_user.is_active = True
            mock_user.role = "viewer"

            mock_user_result = MagicMock()
            mock_user_result.scalar_one_or_none.return_value = mock_user
            
            mock_db.execute = AsyncMock(side_effect=[mock_user_result])
            
            async def override_get_db():
                yield mock_db
            
            app.dependency_overrides[get_db] = override_get_db

            with TestClient(app) as client:
                response = client.put(
                    "/billing/subscription",
                    json={"plan_tier": "parwa_high"},
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 403

    def test_update_subscription_invalid_tier(self, mock_db, mock_user_dict):
        """Test that invalid tier is rejected."""
        app = FastAPI()
        from backend.api.billing import router
        from backend.app.dependencies import get_db

        app.include_router(router)
        
        with patch("backend.api.billing.decode_access_token") as mock_decode, \
             patch("backend.api.billing.is_token_blacklisted", new_callable=AsyncMock) as mock_blacklist:
            
            valid_payload = {
                "sub": str(mock_user_dict["id"]),
                "email": mock_user_dict["email"],
                "role": "manager",
                "company_id": str(mock_user_dict["company_id"]),
            }
            mock_decode.return_value = valid_payload
            mock_blacklist.return_value = False

            # Create mock user with manager role
            mock_user = MagicMock()
            mock_user.id = mock_user_dict["id"]
            mock_user.company_id = mock_user_dict["company_id"]
            mock_user.is_active = True
            mock_user.role = "manager"

            mock_user_result = MagicMock()
            mock_user_result.scalar_one_or_none.return_value = mock_user
            
            mock_db.execute = AsyncMock(side_effect=[mock_user_result])
            
            async def override_get_db():
                yield mock_db
            
            app.dependency_overrides[get_db] = override_get_db

            with TestClient(app) as client:
                response = client.put(
                    "/billing/subscription",
                    json={"plan_tier": "invalid_tier"},
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 400


class TestPaymentMethodEndpoint:
    """Test payment method endpoint."""

    def test_add_payment_method_viewer_forbidden(self, mock_db, mock_user_dict):
        """Test that viewers cannot add payment methods."""
        app = FastAPI()
        from backend.api.billing import router
        from backend.app.dependencies import get_db

        app.include_router(router)
        
        with patch("backend.api.billing.decode_access_token") as mock_decode, \
             patch("backend.api.billing.is_token_blacklisted", new_callable=AsyncMock) as mock_blacklist:
            
            valid_payload = {
                "sub": str(mock_user_dict["id"]),
                "email": mock_user_dict["email"],
                "role": "viewer",
                "company_id": str(mock_user_dict["company_id"]),
            }
            mock_decode.return_value = valid_payload
            mock_blacklist.return_value = False

            # Create mock user with viewer role
            mock_user = MagicMock()
            mock_user.id = mock_user_dict["id"]
            mock_user.company_id = mock_user_dict["company_id"]
            mock_user.is_active = True
            mock_user.role = "viewer"

            mock_user_result = MagicMock()
            mock_user_result.scalar_one_or_none.return_value = mock_user
            
            mock_db.execute = AsyncMock(side_effect=[mock_user_result])
            
            async def override_get_db():
                yield mock_db
            
            app.dependency_overrides[get_db] = override_get_db

            with TestClient(app) as client:
                response = client.post(
                    "/billing/payment-method",
                    json={"token": "tok_test", "is_default": True},
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 403

    def test_add_payment_method_success(self, mock_db, mock_user_dict):
        """Test adding payment method successfully."""
        app = FastAPI()
        from backend.api.billing import router
        from backend.app.dependencies import get_db

        app.include_router(router)
        
        with patch("backend.api.billing.decode_access_token") as mock_decode, \
             patch("backend.api.billing.is_token_blacklisted", new_callable=AsyncMock) as mock_blacklist:
            
            valid_payload = {
                "sub": str(mock_user_dict["id"]),
                "email": mock_user_dict["email"],
                "role": "manager",
                "company_id": str(mock_user_dict["company_id"]),
            }
            mock_decode.return_value = valid_payload
            mock_blacklist.return_value = False

            # Create mock user with manager role
            mock_user = MagicMock()
            mock_user.id = mock_user_dict["id"]
            mock_user.company_id = mock_user_dict["company_id"]
            mock_user.is_active = True
            mock_user.role = "manager"

            mock_user_result = MagicMock()
            mock_user_result.scalar_one_or_none.return_value = mock_user
            
            mock_db.execute = AsyncMock(side_effect=[mock_user_result])
            
            async def override_get_db():
                yield mock_db
            
            app.dependency_overrides[get_db] = override_get_db

            with TestClient(app) as client:
                response = client.post(
                    "/billing/payment-method",
                    json={"token": "tok_test", "is_default": True},
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["type"] == "card"
            assert data["is_default"] is True


class TestUsageEndpoint:
    """Test usage endpoint."""

    def test_get_usage_no_subscription(self, mock_db, mock_user_dict):
        """Test usage endpoint returns 404 when no subscription."""
        app = FastAPI()
        from backend.api.billing import router
        from backend.app.dependencies import get_db

        app.include_router(router)
        
        with patch("backend.api.billing.decode_access_token") as mock_decode, \
             patch("backend.api.billing.is_token_blacklisted", new_callable=AsyncMock) as mock_blacklist:
            
            valid_payload = {
                "sub": str(mock_user_dict["id"]),
                "email": mock_user_dict["email"],
                "role": mock_user_dict["role"],
                "company_id": str(mock_user_dict["company_id"]),
            }
            mock_decode.return_value = valid_payload
            mock_blacklist.return_value = False

            # Create mock user
            mock_user = MagicMock()
            mock_user.id = mock_user_dict["id"]
            mock_user.company_id = mock_user_dict["company_id"]
            mock_user.is_active = True

            mock_user_result = MagicMock()
            mock_user_result.scalar_one_or_none.return_value = mock_user
            
            mock_sub_result = MagicMock()
            mock_sub_result.scalar_one_or_none.return_value = None
            
            mock_db.execute = AsyncMock(side_effect=[mock_user_result, mock_sub_result])
            
            async def override_get_db():
                yield mock_db
            
            app.dependency_overrides[get_db] = override_get_db

            with TestClient(app) as client:
                response = client.get(
                    "/billing/usage",
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 404

    def test_get_usage_success(self, mock_db, mock_user_dict, mock_subscription_dict):
        """Test usage endpoint returns usage data."""
        app = FastAPI()
        from backend.api.billing import router
        from backend.app.dependencies import get_db

        app.include_router(router)
        
        with patch("backend.api.billing.decode_access_token") as mock_decode, \
             patch("backend.api.billing.is_token_blacklisted", new_callable=AsyncMock) as mock_blacklist:
            
            valid_payload = {
                "sub": str(mock_user_dict["id"]),
                "email": mock_user_dict["email"],
                "role": mock_user_dict["role"],
                "company_id": str(mock_user_dict["company_id"]),
            }
            mock_decode.return_value = valid_payload
            mock_blacklist.return_value = False

            # Create mock user
            mock_user = MagicMock()
            mock_user.id = mock_user_dict["id"]
            mock_user.company_id = mock_user_dict["company_id"]
            mock_user.is_active = True

            # Create mock subscription
            mock_subscription = MagicMock()
            mock_subscription.id = mock_subscription_dict["id"]
            mock_subscription.company_id = mock_subscription_dict["company_id"]
            mock_subscription.plan_tier = mock_subscription_dict["plan_tier"]
            mock_subscription.status = mock_subscription_dict["status"]
            mock_subscription.current_period_start = mock_subscription_dict["current_period_start"]
            mock_subscription.current_period_end = mock_subscription_dict["current_period_end"]
            mock_subscription.amount_cents = mock_subscription_dict["amount_cents"]
            mock_subscription.currency = mock_subscription_dict["currency"]

            mock_user_result = MagicMock()
            mock_user_result.scalar_one_or_none.return_value = mock_user
            
            mock_sub_result = MagicMock()
            mock_sub_result.scalar_one_or_none.return_value = mock_subscription
            
            # Empty usage logs
            mock_usage_result = MagicMock()
            mock_usage_result.all.return_value = []
            
            mock_db.execute = AsyncMock(side_effect=[mock_user_result, mock_sub_result, mock_usage_result])
            
            async def override_get_db():
                yield mock_db
            
            app.dependency_overrides[get_db] = override_get_db

            with TestClient(app) as client:
                response = client.get(
                    "/billing/usage",
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["company_id"] == str(mock_user_dict["company_id"])
            assert data["limits"]["tier"] == "parwa"


# --- Async Helper Tests ---

@pytest.mark.asyncio
async def test_is_token_blacklisted():
    """Test is_token_blacklisted helper function."""
    with patch("backend.api.billing.Cache") as mock_cache_class:
        mock_cache = AsyncMock()
        mock_cache.exists.return_value = True
        mock_cache.close = AsyncMock()
        mock_cache_class.return_value = mock_cache

        from backend.api.billing import is_token_blacklisted
        result = await is_token_blacklisted("blacklisted.token")

        assert result is True
        mock_cache.exists.assert_called_once()


@pytest.mark.asyncio
async def test_is_token_blacklisted_error():
    """Test is_token_blacklisted handles errors gracefully."""
    with patch("backend.api.billing.Cache") as mock_cache_class:
        mock_cache = AsyncMock()
        mock_cache.exists.side_effect = Exception("Redis error")
        mock_cache.close = AsyncMock()
        mock_cache_class.return_value = mock_cache

        from backend.api.billing import is_token_blacklisted
        result = await is_token_blacklisted("any.token")

        # Should return False on error (fail open)
        assert result is False
