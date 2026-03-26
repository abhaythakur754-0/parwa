"""
Unit tests for backend/core/license_manager.py - License management module.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4, UUID

from backend.core.license_manager import (
    LicenseValidationResult,
    TIER_LIMITS,
    FEATURE_TIER_ACCESS,
    validate_license,
    validate_license_object,
    get_license_tier,
    get_license_tier_from_license,
    check_feature_allowed,
    check_feature_allowed_for_tier,
    is_license_expired,
    is_license_expired_by_date,
    get_license_limits,
    get_all_tier_limits,
    validate_subscription,
    get_tier_from_subscription,
    compare_tiers,
    is_upgrade,
    is_downgrade,
)


class TestValidateLicense:
    """Tests for validate_license function."""

    def test_valid_format(self):
        """Test validating a license key with valid format."""
        result = validate_license("PARWA-ABCD-EFGH-IJKL")
        assert result.is_valid is True
        assert result.error_message is None

    def test_empty_string(self):
        """Test that empty string returns invalid."""
        result = validate_license("")
        assert result.is_valid is False
        assert result.error_message == "License key cannot be empty"

    def test_none_key(self):
        """Test that None key returns invalid."""
        result = validate_license(None)
        assert result.is_valid is False
        assert result.error_message == "License key cannot be empty"

    def test_invalid_format_no_prefix(self):
        """Test that invalid format without PARWA prefix returns invalid."""
        result = validate_license("ABCD-EFGH-IJKL-MNOP")
        assert result.is_valid is False
        assert "Invalid license key format" in result.error_message

    def test_invalid_format_wrong_parts(self):
        """Test that invalid format with wrong parts returns invalid."""
        result = validate_license("PARWA-ABCD-EFGH")
        assert result.is_valid is False
        assert "Invalid license key format" in result.error_message

    def test_non_string_key(self):
        """Test that non-string key returns invalid."""
        result = validate_license(12345)
        assert result.is_valid is False
        assert result.error_message == "License key must be a string"


class TestValidateLicenseObject:
    """Tests for validate_license_object function."""

    def test_valid_license(self):
        """Test validating a valid license object."""
        license_obj = MagicMock()
        license_obj.id = uuid4()
        license_obj.company_id = uuid4()
        license_obj.tier = "parwa"
        license_obj.status = "active"
        license_obj.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        result = validate_license_object(license_obj)

        assert result.is_valid is True
        assert result.license_id == license_obj.id
        assert result.company_id == license_obj.company_id
        assert result.tier == "parwa"

    def test_license_not_found(self):
        """Test that None license returns invalid."""
        result = validate_license_object(None)

        assert result.is_valid is False
        assert result.error_message == "License not found"

    def test_suspended_license(self):
        """Test that suspended license returns invalid."""
        license_obj = MagicMock()
        license_obj.id = uuid4()
        license_obj.company_id = uuid4()
        license_obj.tier = "parwa"
        license_obj.status = "suspended"
        license_obj.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        result = validate_license_object(license_obj)

        assert result.is_valid is False
        assert "suspended" in result.error_message.lower()

    def test_expired_license(self):
        """Test that expired license returns invalid."""
        license_obj = MagicMock()
        license_obj.id = uuid4()
        license_obj.company_id = uuid4()
        license_obj.tier = "parwa"
        license_obj.status = "active"
        license_obj.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

        result = validate_license_object(license_obj)

        assert result.is_valid is False
        assert "expired" in result.error_message.lower()


class TestGetLicenseTier:
    """Tests for get_license_tier function."""

    def test_empty_company_id(self):
        """Test that empty company_id returns default tier."""
        result = get_license_tier(None)
        assert result == "mini"

    def test_invalid_uuid_format(self):
        """Test that invalid UUID format returns default tier."""
        result = get_license_tier("not-a-uuid")
        assert result == "mini"

    def test_valid_uuid_no_license(self):
        """Test that valid UUID with no license returns default tier."""
        company_id = uuid4()
        result = get_license_tier(company_id)
        assert result == "mini"


class TestGetLicenseTierFromLicense:
    """Tests for get_license_tier_from_license function."""

    def test_valid_license(self):
        """Test getting tier from valid license."""
        license_obj = MagicMock()
        license_obj.tier = "parwa_high"

        result = get_license_tier_from_license(license_obj)
        assert result == "parwa_high"

    def test_none_license(self):
        """Test that None license returns default tier."""
        result = get_license_tier_from_license(None)
        assert result == "mini"

    def test_license_no_tier(self):
        """Test license without tier returns default."""
        license_obj = MagicMock()
        license_obj.tier = None

        result = get_license_tier_from_license(license_obj)
        assert result == "mini"


class TestCheckFeatureAllowed:
    """Tests for check_feature_allowed function."""

    def test_allowed_feature_parwa(self):
        """Test that parwa tier can access allowed features."""
        company_id = uuid4()
        
        with patch("backend.core.license_manager.get_license_tier", return_value="parwa"):
            # parwa tier should have api_access
            result = check_feature_allowed(company_id, "api_access")
            assert result is True

    def test_denied_feature_mini(self):
        """Test that mini tier cannot access premium features."""
        company_id = uuid4()
        
        with patch("backend.core.license_manager.get_license_tier", return_value="mini"):
            # mini tier should NOT have api_access
            result = check_feature_allowed(company_id, "api_access")
            assert result is False

    def test_unknown_feature(self):
        """Test that unknown feature returns False."""
        company_id = uuid4()
        
        with patch("backend.core.license_manager.get_license_tier", return_value="parwa"):
            result = check_feature_allowed(company_id, "unknown_feature")
            assert result is False

    def test_empty_feature(self):
        """Test that empty feature returns False."""
        company_id = uuid4()
        result = check_feature_allowed(company_id, "")
        assert result is False


class TestCheckFeatureAllowedForTier:
    """Tests for check_feature_allowed_for_tier function."""

    def test_mini_basic_support(self):
        """Test mini tier has basic_support."""
        result = check_feature_allowed_for_tier("mini", "basic_support")
        assert result is True

    def test_mini_no_video_support(self):
        """Test mini tier has no video_support."""
        result = check_feature_allowed_for_tier("mini", "video_support")
        assert result is False

    def test_parwa_high_video_support(self):
        """Test parwa_high has video_support."""
        result = check_feature_allowed_for_tier("parwa_high", "video_support")
        assert result is True

    def test_invalid_tier(self):
        """Test invalid tier returns False."""
        result = check_feature_allowed_for_tier("invalid", "basic_support")
        assert result is False

    def test_empty_feature(self):
        """Test empty feature returns False."""
        result = check_feature_allowed_for_tier("parwa", "")
        assert result is False


class TestIsLicenseExpired:
    """Tests for is_license_expired function."""

    def test_not_expired(self):
        """Test that license not yet expired returns False."""
        license_obj = MagicMock()
        license_obj.id = uuid4()
        license_obj.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        result = is_license_expired(license_obj)
        assert result is False

    def test_expired(self):
        """Test that expired license returns True."""
        license_obj = MagicMock()
        license_obj.id = uuid4()
        license_obj.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

        result = is_license_expired(license_obj)
        assert result is True

    def test_no_expiration(self):
        """Test that license with no expiration returns False."""
        license_obj = MagicMock()
        license_obj.id = uuid4()
        license_obj.expires_at = None

        result = is_license_expired(license_obj)
        assert result is False

    def test_none_license(self):
        """Test that None license returns True (expired)."""
        result = is_license_expired(None)
        assert result is True


class TestIsLicenseExpiredByDate:
    """Tests for is_license_expired_by_date function."""

    def test_future_date(self):
        """Test future expiration date returns False."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        result = is_license_expired_by_date(future_date)
        assert result is False

    def test_past_date(self):
        """Test past expiration date returns True."""
        past_date = datetime.now(timezone.utc) - timedelta(days=1)
        result = is_license_expired_by_date(past_date)
        assert result is True

    def test_none_date(self):
        """Test None expiration date returns False."""
        result = is_license_expired_by_date(None)
        assert result is False


class TestGetLicenseLimits:
    """Tests for get_license_limits function."""

    def test_mini_tier(self):
        """Test getting mini tier limits."""
        limits = get_license_limits("mini")

        assert limits["max_calls"] == 2
        assert limits["max_users"] == 1
        assert limits["can_recommend"] is False
        assert limits["video_support"] is False

    def test_parwa_tier(self):
        """Test getting parwa tier limits."""
        limits = get_license_limits("parwa")

        assert limits["max_calls"] == 3
        assert limits["max_users"] == 5
        assert limits["can_recommend"] is True
        assert limits["video_support"] is False

    def test_parwa_high_tier(self):
        """Test getting parwa_high tier limits."""
        limits = get_license_limits("parwa_high")

        assert limits["max_calls"] == 5
        assert limits["max_users"] == 20
        assert limits["can_recommend"] is True
        assert limits["video_support"] is True

    def test_invalid_tier(self):
        """Test that invalid tier returns empty dict."""
        limits = get_license_limits("invalid_tier")
        assert limits == {}

    def test_empty_tier(self):
        """Test that empty tier returns empty dict."""
        limits = get_license_limits("")
        assert limits == {}


class TestGetAllTierLimits:
    """Tests for get_all_tier_limits function."""

    def test_returns_all_tiers(self):
        """Test that all tiers are returned."""
        limits = get_all_tier_limits()

        assert "mini" in limits
        assert "parwa" in limits
        assert "parwa_high" in limits

    def test_returns_copies(self):
        """Test that returned dicts are copies."""
        limits1 = get_all_tier_limits()
        limits2 = get_all_tier_limits()

        limits1["mini"]["max_users"] = 999

        assert limits2["mini"]["max_users"] != 999


class TestValidateSubscription:
    """Tests for validate_subscription function."""

    def test_valid_subscription(self):
        """Test validating a valid subscription."""
        subscription = MagicMock()
        subscription.status = "active"
        subscription.current_period_start = datetime.now(timezone.utc) - timedelta(days=15)
        subscription.current_period_end = datetime.now(timezone.utc) + timedelta(days=15)
        subscription.is_active_subscription.return_value = True

        result = validate_subscription(subscription)
        assert result is True

    def test_inactive_subscription(self):
        """Test that inactive subscription returns False."""
        subscription = MagicMock()
        subscription.status = "canceled"
        subscription.is_active_subscription.return_value = False

        result = validate_subscription(subscription)
        assert result is False

    def test_none_subscription(self):
        """Test that None subscription returns False."""
        result = validate_subscription(None)
        assert result is False

    def test_outside_period(self):
        """Test subscription outside current period returns False."""
        subscription = MagicMock()
        subscription.status = "active"
        subscription.current_period_start = datetime.now(timezone.utc) - timedelta(days=30)
        subscription.current_period_end = datetime.now(timezone.utc) - timedelta(days=1)
        subscription.is_active_subscription.return_value = True

        result = validate_subscription(subscription)
        assert result is False


class TestGetTierFromSubscription:
    """Tests for get_tier_from_subscription function."""

    def test_valid_subscription(self):
        """Test getting tier from valid subscription."""
        subscription = MagicMock()
        subscription.plan_tier = "parwa_high"

        result = get_tier_from_subscription(subscription)
        assert result == "parwa_high"

    def test_none_subscription(self):
        """Test that None subscription returns default tier."""
        result = get_tier_from_subscription(None)
        assert result == "mini"

    def test_subscription_no_tier(self):
        """Test subscription without tier returns default."""
        subscription = MagicMock()
        subscription.plan_tier = None

        result = get_tier_from_subscription(subscription)
        assert result == "mini"


class TestCompareTiers:
    """Tests for compare_tiers function."""

    def test_equal_tiers(self):
        """Test comparing equal tiers."""
        assert compare_tiers("mini", "mini") == 0
        assert compare_tiers("parwa", "parwa") == 0
        assert compare_tiers("parwa_high", "parwa_high") == 0

    def test_ascending_order(self):
        """Test comparing tiers in ascending order."""
        assert compare_tiers("mini", "parwa") == -1
        assert compare_tiers("mini", "parwa_high") == -1
        assert compare_tiers("parwa", "parwa_high") == -1

    def test_descending_order(self):
        """Test comparing tiers in descending order."""
        assert compare_tiers("parwa", "mini") == 1
        assert compare_tiers("parwa_high", "mini") == 1
        assert compare_tiers("parwa_high", "parwa") == 1

    def test_invalid_tier(self):
        """Test comparing with invalid tier."""
        assert compare_tiers("invalid", "mini") == 0
        assert compare_tiers("parwa", "invalid") == 0


class TestIsUpgrade:
    """Tests for is_upgrade function."""

    def test_mini_to_parwa(self):
        """Test upgrade from mini to parwa."""
        assert is_upgrade("mini", "parwa") is True

    def test_parwa_to_parwa_high(self):
        """Test upgrade from parwa to parwa_high."""
        assert is_upgrade("parwa", "parwa_high") is True

    def test_same_tier(self):
        """Test same tier is not upgrade."""
        assert is_upgrade("parwa", "parwa") is False

    def test_downgrade(self):
        """Test downgrade is not upgrade."""
        assert is_upgrade("parwa_high", "parwa") is False


class TestIsDowngrade:
    """Tests for is_downgrade function."""

    def test_parwa_to_mini(self):
        """Test downgrade from parwa to mini."""
        assert is_downgrade("parwa", "mini") is True

    def test_parwa_high_to_parwa(self):
        """Test downgrade from parwa_high to parwa."""
        assert is_downgrade("parwa_high", "parwa") is True

    def test_same_tier(self):
        """Test same tier is not downgrade."""
        assert is_downgrade("parwa", "parwa") is False

    def test_upgrade(self):
        """Test upgrade is not downgrade."""
        assert is_downgrade("mini", "parwa") is False


class TestLicenseValidationResult:
    """Tests for LicenseValidationResult dataclass."""

    def test_valid_result(self):
        """Test creating valid result."""
        license_id = uuid4()
        company_id = uuid4()

        result = LicenseValidationResult(
            is_valid=True,
            license_id=license_id,
            company_id=company_id,
            tier="parwa",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30)
        )

        assert result.is_valid is True
        assert result.license_id == license_id
        assert result.company_id == company_id
        assert result.tier == "parwa"
        assert result.error_message is None

    def test_invalid_result(self):
        """Test creating invalid result."""
        result = LicenseValidationResult(
            is_valid=False,
            error_message="License expired"
        )

        assert result.is_valid is False
        assert result.error_message == "License expired"
        assert result.license_id is None
