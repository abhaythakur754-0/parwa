"""
Unit tests for License Service.
Uses mocked database sessions - no Docker required.
"""
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from backend.services.license_service import (
    LicenseService,
    LicenseTier,
    LicenseStatus,
)


def create_mock_result(return_value=None):
    """Create a properly mocked database result."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=return_value)
    mock_result.scalars = MagicMock()
    mock_result.scalars().all = MagicMock(return_value=[])
    return mock_result


@pytest.fixture
def mock_db():
    """Mock database session with proper async execute."""
    db = AsyncMock()
    # By default, execute returns a result that yields None
    mock_result = create_mock_result(None)
    db.execute = AsyncMock(return_value=mock_result)
    return db


@pytest.fixture
def license_service(mock_db):
    """License service instance with mocked DB."""
    company_id = uuid.uuid4()
    return LicenseService(mock_db, company_id)


class TestLicenseServiceInit:
    """Tests for LicenseService initialization."""
    
    def test_init_stores_db_and_company_id(self, mock_db):
        """Test that init stores db and company_id."""
        company_id = uuid.uuid4()
        service = LicenseService(mock_db, company_id)
        
        assert service.db == mock_db
        assert service.company_id == company_id


class TestLicenseTierEnum:
    """Tests for LicenseTier enum."""
    
    def test_tier_values(self):
        """Test tier enum values."""
        assert LicenseTier.MINI_PARWA.value == "mini"
        assert LicenseTier.PARWA.value == "parwa"
        assert LicenseTier.PARWA_HIGH.value == "parwa_high"
    
    def test_tier_count(self):
        """Test that we have expected number of tiers."""
        assert len(LicenseTier) == 3


class TestLicenseStatusEnum:
    """Tests for LicenseStatus enum."""
    
    def test_status_values(self):
        """Test status enum values."""
        assert LicenseStatus.ACTIVE.value == "active"
        assert LicenseStatus.SUSPENDED.value == "suspended"
        assert LicenseStatus.EXPIRED.value == "expired"
        assert LicenseStatus.CANCELLED.value == "cancelled"


class TestTierLimits:
    """Tests for TIER_LIMITS configuration."""
    
    def test_mini_parwa_limits(self):
        """Test MINI_PARWA tier limits."""
        limits = LicenseService.TIER_LIMITS[LicenseTier.MINI_PARWA]
        
        assert limits["users"] == 5
        assert limits["tickets_per_month"] == 500
        assert "email" in limits["features"]
    
    def test_parwa_limits(self):
        """Test PARWA tier limits."""
        limits = LicenseService.TIER_LIMITS[LicenseTier.PARWA]
        
        assert limits["users"] == 25
        assert limits["tickets_per_month"] == 5000
        assert "voice" in limits["features"]
    
    def test_parwa_high_limits(self):
        """Test PARWA_HIGH tier limits."""
        limits = LicenseService.TIER_LIMITS[LicenseTier.PARWA_HIGH]
        
        assert limits["users"] == 100
        assert limits["tickets_per_month"] == 50000
        assert "video" in limits["features"]
        assert "priority_queue" in limits["features"]


class TestGetLicense:
    """Tests for get_license method."""
    
    @pytest.mark.asyncio
    async def test_get_license_returns_none_when_not_found(self, license_service):
        """Test that get_license returns None when license not found."""
        # Default mock returns None
        result = await license_service.get_license()
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_license_returns_dict_when_found(self, mock_db):
        """Test that get_license returns dict when license found."""
        company_id = uuid.uuid4()
        
        # Create a mock license object
        mock_license = MagicMock()
        mock_license.id = uuid.uuid4()
        mock_license.company_id = company_id
        mock_license.license_key = "TEST-KEY"
        mock_license.tier = "parwa"
        mock_license.status = "active"
        mock_license.issued_at = datetime.now(timezone.utc)
        mock_license.expires_at = datetime.now(timezone.utc) + timedelta(days=365)
        mock_license.max_seats = 25
        
        mock_result = create_mock_result(mock_license)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        service = LicenseService(mock_db, company_id)
        result = await service.get_license()
        
        assert result is not None
        assert result["company_id"] == str(company_id)
        assert result["tier"] == "parwa"
        assert result["status"] == "active"
        assert "limits" in result


class TestValidateLicense:
    """Tests for validate_license method."""
    
    @pytest.mark.asyncio
    async def test_validate_license_returns_false_when_not_found(self, license_service):
        """Test validating when license not found."""
        is_valid = await license_service.validate_license()
        
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_validate_license_returns_true_when_active(self, mock_db):
        """Test validating active license."""
        company_id = uuid.uuid4()
        
        mock_license = MagicMock()
        mock_license.id = uuid.uuid4()
        mock_license.company_id = company_id
        mock_license.license_key = "TEST-KEY"
        mock_license.tier = "parwa"
        mock_license.status = "active"
        mock_license.issued_at = datetime.now(timezone.utc)
        mock_license.expires_at = datetime.now(timezone.utc) + timedelta(days=365)
        mock_license.max_seats = 25
        
        mock_result = create_mock_result(mock_license)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        service = LicenseService(mock_db, company_id)
        is_valid = await service.validate_license()
        
        assert is_valid is True


class TestGetTierLimits:
    """Tests for get_tier_limits method."""
    
    @pytest.mark.asyncio
    async def test_get_tier_limits_mini(self, license_service):
        """Test getting MINI tier limits."""
        limits = await license_service.get_tier_limits(LicenseTier.MINI_PARWA)
        
        assert limits["users"] == 5
        assert limits["sla_response_hours"] == 24
    
    @pytest.mark.asyncio
    async def test_get_tier_limits_parwa(self, license_service):
        """Test getting PARWA tier limits."""
        limits = await license_service.get_tier_limits(LicenseTier.PARWA)
        
        assert limits["users"] == 25
        assert limits["sla_response_hours"] == 4
    
    @pytest.mark.asyncio
    async def test_get_tier_limits_high(self, license_service):
        """Test getting PARWA_HIGH tier limits."""
        limits = await license_service.get_tier_limits(LicenseTier.PARWA_HIGH)
        
        assert limits["users"] == 100
        assert limits["sla_response_hours"] == 1


class TestCheckUsageLimit:
    """Tests for check_usage_limit method."""
    
    @pytest.mark.asyncio
    async def test_check_usage_no_license(self, license_service):
        """Test usage check when no license found."""
        result = await license_service.check_usage_limit("users", 3)
        
        assert result["within_limit"] is False
        assert "reason" in result
    
    @pytest.mark.asyncio
    async def test_check_usage_within_limit(self, mock_db):
        """Test usage within limit."""
        company_id = uuid.uuid4()
        
        mock_license = MagicMock()
        mock_license.id = uuid.uuid4()
        mock_license.company_id = company_id
        mock_license.license_key = "TEST-KEY"
        mock_license.tier = "parwa"
        mock_license.status = "active"
        mock_license.issued_at = datetime.now(timezone.utc)
        mock_license.expires_at = None
        mock_license.max_seats = 25
        
        mock_result = create_mock_result(mock_license)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        service = LicenseService(mock_db, company_id)
        result = await service.check_usage_limit("users", 10)
        
        assert result["within_limit"] is True
        assert result["limit"] == 25
    
    @pytest.mark.asyncio
    async def test_check_usage_exceeds_limit(self, mock_db):
        """Test usage exceeds limit."""
        company_id = uuid.uuid4()
        
        mock_license = MagicMock()
        mock_license.id = uuid.uuid4()
        mock_license.company_id = company_id
        mock_license.license_key = "TEST-KEY"
        mock_license.tier = "parwa"
        mock_license.status = "active"
        mock_license.issued_at = datetime.now(timezone.utc)
        mock_license.expires_at = None
        mock_license.max_seats = 25
        
        mock_result = create_mock_result(mock_license)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        service = LicenseService(mock_db, company_id)
        result = await service.check_usage_limit("users", 50)
        
        assert result["within_limit"] is False


class TestCheckFeatureAccess:
    """Tests for check_feature_access method."""
    
    @pytest.mark.asyncio
    async def test_feature_access_no_license(self, license_service):
        """Test feature access when no license found."""
        has_access = await license_service.check_feature_access("email")
        
        assert has_access is False
    
    @pytest.mark.asyncio
    async def test_feature_access_with_license(self, mock_db):
        """Test feature access with valid license."""
        company_id = uuid.uuid4()
        
        mock_license = MagicMock()
        mock_license.id = uuid.uuid4()
        mock_license.company_id = company_id
        mock_license.license_key = "TEST-KEY"
        mock_license.tier = "parwa"
        mock_license.status = "active"
        mock_license.issued_at = datetime.now(timezone.utc)
        mock_license.expires_at = None
        mock_license.max_seats = 25
        
        mock_result = create_mock_result(mock_license)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        service = LicenseService(mock_db, company_id)
        
        # Email is in PARWA tier
        has_access = await service.check_feature_access("email")
        assert has_access is True
        
        # Video is NOT in PARWA tier (only in PARWA_HIGH)
        has_video = await service.check_feature_access("video")
        assert has_video is False


class TestGetFeatures:
    """Tests for get_features method."""
    
    @pytest.mark.asyncio
    async def test_get_features_no_license(self, license_service):
        """Test that get_features returns empty list when no license."""
        features = await license_service.get_features()
        
        assert features == []
    
    @pytest.mark.asyncio
    async def test_get_features_with_license(self, mock_db):
        """Test that get_features returns list with license."""
        company_id = uuid.uuid4()
        
        mock_license = MagicMock()
        mock_license.id = uuid.uuid4()
        mock_license.company_id = company_id
        mock_license.license_key = "TEST-KEY"
        mock_license.tier = "parwa_high"
        mock_license.status = "active"
        mock_license.issued_at = datetime.now(timezone.utc)
        mock_license.expires_at = None
        mock_license.max_seats = 100
        
        mock_result = create_mock_result(mock_license)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        service = LicenseService(mock_db, company_id)
        features = await service.get_features()
        
        assert isinstance(features, list)
        assert "video" in features
        assert "priority_queue" in features


class TestGetRemainingUsage:
    """Tests for get_remaining_usage method."""
    
    @pytest.mark.asyncio
    async def test_get_remaining_usage(self, license_service):
        """Test getting remaining usage."""
        remaining = await license_service.get_remaining_usage("users", 3)
        
        assert isinstance(remaining, int)


class TestIsUpgradeRequired:
    """Tests for is_upgrade_required method."""
    
    @pytest.mark.asyncio
    async def test_is_upgrade_required_no_license(self, license_service):
        """Test upgrade required when no license."""
        is_required = await license_service.is_upgrade_required("users", 3)
        
        assert is_required is True


class TestSuggestUpgradeTier:
    """Tests for suggest_upgrade_tier method."""
    
    @pytest.mark.asyncio
    async def test_suggest_upgrade_for_features(self, license_service):
        """Test suggesting upgrade for missing features."""
        suggested = await license_service.suggest_upgrade_tier(
            current_tier=LicenseTier.MINI_PARWA,
            required_features=["video", "priority_queue"]
        )
        
        # Should suggest PARWA_HIGH for video feature
        assert suggested == LicenseTier.PARWA_HIGH
    
    @pytest.mark.asyncio
    async def test_no_upgrade_needed(self, license_service):
        """Test no upgrade needed when current tier is sufficient."""
        suggested = await license_service.suggest_upgrade_tier(
            current_tier=LicenseTier.PARWA_HIGH,
            required_features=["email"]
        )
        
        assert suggested is None


class TestActivateLicense:
    """Tests for activate_license method."""
    
    @pytest.mark.asyncio
    async def test_activate_license(self, license_service):
        """Test activating license."""
        result = await license_service.activate_license("TEST-LICENSE-KEY")
        
        assert result["activated"] is True
        assert "activated_at" in result


class TestSuspendLicense:
    """Tests for suspend_license method."""
    
    @pytest.mark.asyncio
    async def test_suspend_license(self, license_service):
        """Test suspending license."""
        result = await license_service.suspend_license("Payment overdue")
        
        assert result["suspended"] is True
        assert result["reason"] == "Payment overdue"
        assert "suspended_at" in result


class TestGetLicenseSummary:
    """Tests for get_license_summary method."""
    
    @pytest.mark.asyncio
    async def test_get_license_summary_no_license(self, license_service):
        """Test getting license summary when no license."""
        result = await license_service.get_license_summary()
        
        assert result["is_valid"] is False
        assert result["features_count"] == 0


class TestCompanyScoping:
    """Tests for company scoping enforcement."""
    
    @pytest.mark.asyncio
    async def test_activate_includes_company_id(self, license_service):
        """Test that activate_license includes company_id."""
        activation = await license_service.activate_license("TEST-KEY")
        assert activation["company_id"] == str(license_service.company_id)
    
    @pytest.mark.asyncio
    async def test_suspend_includes_company_id(self, license_service):
        """Test that suspend_license includes company_id."""
        suspension = await license_service.suspend_license("Test")
        assert suspension["company_id"] == str(license_service.company_id)
