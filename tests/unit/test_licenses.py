"""
Unit tests for License Management API routes.

Tests cover:
- License activation (POST /licenses/activate)
- License validation (GET /licenses/validate)
- License listing (GET /licenses/)
- License update (PUT /licenses/{id})
- Tier limits (GET /licenses/tier-limits/{tier})

Note: These tests mock all database connections to avoid requiring a real database.
"""
import uuid
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import after environment setup from conftest.py
from backend.api.licenses import router, TIER_LIMITS, generate_license_key
from backend.app.dependencies import get_db


# Create test app
app = FastAPI()
app.include_router(router)


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def client(mock_db_session):
    """Create a test client with mocked database."""
    # Override the database dependency
    async def override_get_db():
        yield mock_db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client, mock_db_session
    
    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
def test_company_id() -> uuid.UUID:
    """Return a test company ID."""
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def test_license_id() -> uuid.UUID:
    """Return a test license ID."""
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def mock_license(test_license_id, test_company_id):
    """Create a mock License object."""
    license_obj = MagicMock()
    license_obj.id = test_license_id
    license_obj.company_id = test_company_id
    license_obj.license_key = "TEST-1234-ABCD-5678"
    license_obj.tier = "parwa"
    license_obj.status = "active"
    license_obj.max_seats = 5
    license_obj.issued_at = datetime.datetime.now(datetime.timezone.utc)
    license_obj.expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
    license_obj.created_at = datetime.datetime.now(datetime.timezone.utc)
    license_obj.is_valid = MagicMock(return_value=True)
    return license_obj


class TestTierLimits:
    """Tests for tier limits configuration."""

    def test_tier_limits_mini_exists(self):
        """Verify mini tier limits are defined."""
        assert "mini" in TIER_LIMITS
        assert TIER_LIMITS["mini"]["max_calls"] == 2
        assert TIER_LIMITS["mini"]["can_recommend"] is False

    def test_tier_limits_parwa_exists(self):
        """Verify parwa tier limits are defined."""
        assert "parwa" in TIER_LIMITS
        assert TIER_LIMITS["parwa"]["max_calls"] == 3
        assert TIER_LIMITS["parwa"]["can_recommend"] is True
        assert TIER_LIMITS["parwa"]["agent_lightning"] is True

    def test_tier_limits_parwa_high_exists(self):
        """Verify parwa_high tier limits are defined."""
        assert "parwa_high" in TIER_LIMITS
        assert TIER_LIMITS["parwa_high"]["max_calls"] == 5
        assert TIER_LIMITS["parwa_high"]["video_support"] is True
        assert TIER_LIMITS["parwa_high"]["churn_prediction"] is True


class TestGetTierLimitsEndpoint:
    """Tests for GET /licenses/tier-limits/{tier} endpoint."""

    def test_get_mini_tier_limits(self, client):
        """Test getting mini tier limits."""
        test_client, _ = client
        response = test_client.get("/licenses/tier-limits/mini")
        
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "mini"
        assert "limits" in data
        assert data["limits"]["max_calls"] == 2

    def test_get_parwa_tier_limits(self, client):
        """Test getting parwa tier limits."""
        test_client, _ = client
        response = test_client.get("/licenses/tier-limits/parwa")
        
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "parwa"
        assert data["limits"]["agent_lightning"] is True

    def test_get_parwa_high_tier_limits(self, client):
        """Test getting parwa_high tier limits."""
        test_client, _ = client
        response = test_client.get("/licenses/tier-limits/parwa_high")
        
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "parwa_high"
        assert data["limits"]["strategic_bi"] is True

    def test_get_invalid_tier_limits(self, client):
        """Test getting limits for invalid tier."""
        test_client, _ = client
        response = test_client.get("/licenses/tier-limits/invalid_tier")
        
        assert response.status_code == 400
        assert "Invalid tier" in response.json()["detail"]


class TestActivateLicenseEndpoint:
    """Tests for POST /licenses/activate endpoint."""

    def test_activate_license_invalid_key_format(self, client):
        """Test activation with invalid key format."""
        test_client, _ = client
        with patch("backend.api.licenses.get_current_company_id", 
                   return_value=uuid.UUID("00000000-0000-0000-0000-000000000001")):
            response = test_client.post("/licenses/activate?license_key=short")
            
        assert response.status_code == 400
        assert "Invalid license key format" in response.json()["detail"]

    def test_activate_license_empty_key(self, client):
        """Test activation with empty key."""
        test_client, _ = client
        with patch("backend.api.licenses.get_current_company_id", 
                   return_value=uuid.UUID("00000000-0000-0000-0000-000000000001")):
            response = test_client.post("/licenses/activate?license_key=")
            
        assert response.status_code == 400

    def test_activate_license_success(self, client, mock_license):
        """Test successful license activation."""
        test_client, mock_db = client
        # Set up the license to be unactivated (no company_id)
        mock_license.company_id = None
        
        # Mock the database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_license
        mock_db.execute.return_value = mock_result
        
        with patch("backend.api.licenses.get_current_company_id", 
                   return_value=uuid.UUID("00000000-0000-0000-0000-000000000001")):
            response = test_client.post(
                "/licenses/activate?license_key=TEST-1234-ABCD-5678"
            )
                
        assert response.status_code == 201

    def test_activate_license_not_found(self, client, test_company_id):
        """Test activation with non-existent key."""
        test_client, mock_db = client
        # Mock the database query returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        with patch("backend.api.licenses.get_current_company_id", return_value=test_company_id):
            response = test_client.post(
                "/licenses/activate?license_key=NOTFOUND-1234-ABCD"
            )
                
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_activate_license_already_activated(self, client, mock_license):
        """Test activation of already activated license."""
        test_client, mock_db = client
        # License already has a company_id
        mock_license.company_id = uuid.UUID("99999999-9999-9999-9999-999999999999")
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_license
        mock_db.execute.return_value = mock_result
        
        with patch("backend.api.licenses.get_current_company_id", 
                   return_value=uuid.UUID("00000000-0000-0000-0000-000000000001")):
            response = test_client.post(
                "/licenses/activate?license_key=TEST-1234-ABCD-5678"
            )
                
        assert response.status_code == 409
        assert "already activated" in response.json()["detail"].lower()


class TestValidateLicenseEndpoint:
    """Tests for GET /licenses/validate endpoint."""

    def test_validate_license_success(self, client, mock_license):
        """Test successful license validation."""
        test_client, mock_db = client
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_license
        mock_db.execute.return_value = mock_result
        
        with patch("backend.api.licenses.get_current_company_id", return_value=mock_license.company_id):
            response = test_client.get("/licenses/validate")
                
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["tier"] == "parwa"
        assert "limits" in data

    def test_validate_license_not_found(self, client, test_company_id):
        """Test validation when no license found."""
        test_client, mock_db = client
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        with patch("backend.api.licenses.get_current_company_id", return_value=test_company_id):
            response = test_client.get("/licenses/validate")
                
        assert response.status_code == 404

    def test_validate_license_expired(self, client, mock_license):
        """Test validation of expired license."""
        test_client, mock_db = client
        mock_license.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        mock_license.is_valid.return_value = False
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_license
        mock_db.execute.return_value = mock_result
        
        with patch("backend.api.licenses.get_current_company_id", return_value=mock_license.company_id):
            response = test_client.get("/licenses/validate")
                
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["is_expired"] is True

    def test_validate_license_suspended(self, client, mock_license):
        """Test validation of suspended license."""
        test_client, mock_db = client
        mock_license.status = "suspended"
        mock_license.is_valid.return_value = False
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_license
        mock_db.execute.return_value = mock_result
        
        with patch("backend.api.licenses.get_current_company_id", return_value=mock_license.company_id):
            response = test_client.get("/licenses/validate")
                
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["status"] == "suspended"


class TestListLicensesEndpoint:
    """Tests for GET /licenses/ endpoint."""

    def test_list_licenses_empty(self, client, test_company_id):
        """Test listing licenses when company has none."""
        test_client, mock_db = client
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result
        
        with patch("backend.api.licenses.get_current_company_id", return_value=test_company_id):
            response = test_client.get("/licenses/")
                
        assert response.status_code == 200
        assert response.json() == []

    def test_list_licenses_success(self, client, mock_license, test_company_id):
        """Test successful listing of licenses."""
        test_client, mock_db = client
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_license]
        mock_db.execute.return_value = mock_result
        
        with patch("backend.api.licenses.get_current_company_id", return_value=test_company_id):
            response = test_client.get("/licenses/")
                
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["tier"] == "parwa"

    def test_list_licenses_multiple(self, client, test_company_id):
        """Test listing multiple licenses."""
        test_client, mock_db = client
        licenses = []
        for i in range(3):
            lic = MagicMock()
            lic.id = uuid.uuid4()
            lic.company_id = test_company_id
            lic.license_key = f"TEST-{i}-ABCD-5678"
            lic.tier = ["mini", "parwa", "parwa_high"][i]
            lic.status = "active"
            lic.max_seats = i + 1
            lic.issued_at = datetime.datetime.now(datetime.timezone.utc)
            lic.expires_at = None
            lic.created_at = datetime.datetime.now(datetime.timezone.utc)
            licenses.append(lic)
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = licenses
        mock_db.execute.return_value = mock_result
        
        with patch("backend.api.licenses.get_current_company_id", return_value=test_company_id):
            response = test_client.get("/licenses/")
                
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3


class TestUpdateLicenseEndpoint:
    """Tests for PUT /licenses/{id} endpoint."""

    def test_update_license_not_found(self, client, test_company_id, test_license_id):
        """Test updating non-existent license."""
        test_client, mock_db = client
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        with patch("backend.api.licenses.get_current_company_id", return_value=test_company_id):
            response = test_client.put(
                f"/licenses/{test_license_id}",
                json={"status": "suspended"}
            )
                
        assert response.status_code == 404

    def test_update_license_status_success(self, client, mock_license, test_company_id):
        """Test successful status update."""
        test_client, mock_db = client
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_license
        mock_db.execute.return_value = mock_result
        
        with patch("backend.api.licenses.get_current_company_id", return_value=test_company_id):
            response = test_client.put(
                f"/licenses/{mock_license.id}",
                json={"status": "suspended"}
            )
                
        assert response.status_code == 200

    def test_update_license_max_seats(self, client, mock_license, test_company_id):
        """Test updating max seats."""
        test_client, mock_db = client
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_license
        mock_db.execute.return_value = mock_result
        
        with patch("backend.api.licenses.get_current_company_id", return_value=test_company_id):
            response = test_client.put(
                f"/licenses/{mock_license.id}",
                json={"max_seats": 10}
            )
                
        assert response.status_code == 200

    def test_update_license_tier_with_active_subscription(
        self, client, mock_license, test_company_id
    ):
        """Test tier change with active subscription fails."""
        test_client, mock_db = client
        mock_subscription = MagicMock()
        mock_subscription.status = "active"
        
        # Track call count for different queries
        call_count = [0]
        async def mock_execute(*args, **kwargs):
            result = MagicMock()
            if call_count[0] == 0:
                # First call returns license
                result.scalar_one_or_none.return_value = mock_license
            else:
                # Second call returns subscription
                result.scalar_one_or_none.return_value = mock_subscription
            call_count[0] += 1
            return result
        
        mock_db.execute = mock_execute
        
        with patch("backend.api.licenses.get_current_company_id", return_value=test_company_id):
            response = test_client.put(
                f"/licenses/{mock_license.id}",
                json={"tier": "mini"}
            )
                
        assert response.status_code == 400
        assert "active subscription" in response.json()["detail"].lower()


class TestGenerateLicenseKey:
    """Tests for license key generation."""

    def test_generate_license_key_format(self):
        """Test that generated key has correct format."""
        key = generate_license_key()
        
        # Should be in format XXXX-XXXX-XXXX-XXXX
        parts = key.split("-")
        assert len(parts) == 4
        for part in parts:
            assert len(part) == 4
            assert part.isalnum()

    def test_generate_license_key_uniqueness(self):
        """Test that generated keys are unique."""
        keys = set()
        for _ in range(100):
            key = generate_license_key()
            assert key not in keys
            keys.add(key)
