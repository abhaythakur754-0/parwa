"""
PARWA License Manager Module.
Provides core license management logic — validation, tier checking, expiry handling.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.models.license import License
from backend.models.subscription import Subscription
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


# Tier limits configuration
TIER_LIMITS: Dict[str, Dict[str, Any]] = {
    "mini": {
        "max_calls": 2,
        "max_users": 1,
        "max_tickets_per_month": 100,
        "can_recommend": False,
        "video_support": False,
        "priority_support": False,
        "custom_ai_model": False,
        "api_access": False,
        "analytics_dashboard": False,
        "webhook_integrations": 0,
    },
    "parwa": {
        "max_calls": 3,
        "max_users": 5,
        "max_tickets_per_month": 1000,
        "can_recommend": True,
        "video_support": False,
        "priority_support": True,
        "custom_ai_model": False,
        "api_access": True,
        "analytics_dashboard": True,
        "webhook_integrations": 5,
    },
    "parwa_high": {
        "max_calls": 5,
        "max_users": 20,
        "max_tickets_per_month": 10000,
        "can_recommend": True,
        "video_support": True,
        "priority_support": True,
        "custom_ai_model": True,
        "api_access": True,
        "analytics_dashboard": True,
        "webhook_integrations": -1,  # Unlimited
    },
}

# Feature to tier mapping - which tiers have access to each feature
FEATURE_TIER_ACCESS: Dict[str, List[str]] = {
    "basic_support": ["mini", "parwa", "parwa_high"],
    "product_recommendations": ["parwa", "parwa_high"],
    "video_support": ["parwa_high"],
    "priority_queue": ["parwa", "parwa_high"],
    "custom_ai_model": ["parwa_high"],
    "api_access": ["parwa", "parwa_high"],
    "analytics_dashboard": ["parwa", "parwa_high"],
    "webhook_integrations": ["parwa", "parwa_high"],
    "agent_lightning_training": ["parwa", "parwa_high"],
    "multi_channel_support": ["parwa", "parwa_high"],
    "custom_branding": ["parwa_high"],
    "dedicated_account_manager": ["parwa_high"],
}


@dataclass
class LicenseValidationResult:
    """
    Result of license validation.
    
    Attributes:
        is_valid: Whether the license is valid
        license_id: The UUID of the license if valid
        company_id: The UUID of the company if valid
        tier: The license tier (mini, parwa, parwa_high)
        expires_at: When the license expires
        error_message: Error message if validation failed
    """
    is_valid: bool
    license_id: Optional[UUID] = None
    company_id: Optional[UUID] = None
    tier: Optional[str] = None
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None


def validate_license(license_key: str) -> LicenseValidationResult:
    """
    Validate a license key.
    
    Args:
        license_key: The license key string to validate.
        
    Returns:
        LicenseValidationResult: The validation result containing
            validity status, license info, and any error messages.
            
    Note:
        This function does NOT query the database directly. In production,
        it should be called with a license object retrieved from the database.
        For testing purposes, use validate_license_object() instead.
    """
    if not license_key:
        logger.warning({"event": "license_validation_empty_key"})
        return LicenseValidationResult(
            is_valid=False,
            error_message="License key cannot be empty"
        )
    
    # Basic format validation
    if not isinstance(license_key, str):
        return LicenseValidationResult(
            is_valid=False,
            error_message="License key must be a string"
        )
    
    # License key format: PARWA-XXXX-XXXX-XXXX
    key_parts = license_key.split("-")
    if len(key_parts) != 4 or key_parts[0] != "PARWA":
        return LicenseValidationResult(
            is_valid=False,
            error_message="Invalid license key format"
        )
    
    logger.info({"event": "license_key_format_valid", "key_prefix": key_parts[0]})
    
    # Note: Full validation requires database lookup
    # This returns a partial result - use validate_license_object() for complete validation
    return LicenseValidationResult(
        is_valid=True,  # Format is valid, actual validity requires DB check
        error_message=None
    )


def validate_license_object(license_obj: License) -> LicenseValidationResult:
    """
    Validate a License object from the database.
    
    Args:
        license_obj: The License ORM object to validate.
        
    Returns:
        LicenseValidationResult: Complete validation result.
    """
    if not license_obj:
        return LicenseValidationResult(
            is_valid=False,
            error_message="License not found"
        )
    
    # Check status
    if license_obj.status != "active":
        logger.warning({
            "event": "license_not_active",
            "license_id": str(license_obj.id),
            "status": license_obj.status
        })
        return LicenseValidationResult(
            is_valid=False,
            license_id=license_obj.id,
            company_id=license_obj.company_id,
            tier=license_obj.tier,
            error_message=f"License is {license_obj.status}"
        )
    
    # Check expiration
    if is_license_expired(license_obj):
        logger.warning({
            "event": "license_expired",
            "license_id": str(license_obj.id),
            "expires_at": str(license_obj.expires_at)
        })
        return LicenseValidationResult(
            is_valid=False,
            license_id=license_obj.id,
            company_id=license_obj.company_id,
            tier=license_obj.tier,
            expires_at=license_obj.expires_at,
            error_message="License has expired"
        )
    
    logger.info({
        "event": "license_validated",
        "license_id": str(license_obj.id),
        "tier": license_obj.tier
    })
    
    return LicenseValidationResult(
        is_valid=True,
        license_id=license_obj.id,
        company_id=license_obj.company_id,
        tier=license_obj.tier,
        expires_at=license_obj.expires_at
    )


def get_license_tier(company_id: UUID) -> str:
    """
    Get the license tier for a company.
    
    Args:
        company_id: The UUID of the company.
        
    Returns:
        str: The tier name ("mini", "parwa", "parwa_high").
             Returns "mini" as default if no license found.
             
    Note:
        This function requires database access. In production, pass the
        license object directly. For testing, use mock the database query.
    """
    if not company_id:
        logger.warning({"event": "get_tier_empty_company_id"})
        return "mini"
    
    if not isinstance(company_id, UUID):
        try:
            company_id = UUID(company_id)
        except (ValueError, TypeError):
            logger.warning({"event": "invalid_company_id_format"})
            return "mini"
    
    # Default tier if no license found
    # In production, this would query the database
    logger.warning({
        "event": "no_license_found",
        "company_id": str(company_id),
        "defaulting_to": "mini"
    })
    return "mini"


def get_license_tier_from_license(license_obj: Optional[License]) -> str:
    """
    Get the tier from a License object.
    
    Args:
        license_obj: The License ORM object.
        
    Returns:
        str: The tier name, or "mini" as default.
    """
    if license_obj and license_obj.tier:
        return license_obj.tier
    return "mini"


def check_feature_allowed(company_id: UUID, feature: str) -> bool:
    """
    Check if a feature is allowed for a company based on their license tier.
    
    Args:
        company_id: The UUID of the company.
        feature: The feature name to check.
        
    Returns:
        bool: True if the feature is allowed, False otherwise.
    """
    if not feature:
        return False
    
    # Get the company's tier
    tier = get_license_tier(company_id)
    
    # Check if feature exists in mapping
    if feature not in FEATURE_TIER_ACCESS:
        logger.warning({
            "event": "unknown_feature_check",
            "feature": feature,
            "company_id": str(company_id)
        })
        return False
    
    # Check if tier has access
    allowed = tier in FEATURE_TIER_ACCESS[feature]
    
    logger.info({
        "event": "feature_check",
        "feature": feature,
        "tier": tier,
        "allowed": allowed
    })
    
    return allowed


def check_feature_allowed_for_tier(tier: str, feature: str) -> bool:
    """
    Check if a feature is allowed for a specific tier.
    
    Args:
        tier: The tier name ("mini", "parwa", "parwa_high").
        feature: The feature name to check.
        
    Returns:
        bool: True if the feature is allowed, False otherwise.
    """
    if not feature or not tier:
        return False
    
    if tier not in TIER_LIMITS:
        logger.warning({"event": "invalid_tier", "tier": tier})
        return False
    
    if feature not in FEATURE_TIER_ACCESS:
        return False
    
    return tier in FEATURE_TIER_ACCESS[feature]


def is_license_expired(license_obj: License) -> bool:
    """
    Check if a license has expired.
    
    Args:
        license_obj: The License ORM object.
        
    Returns:
        bool: True if expired, False if valid or no expiration date.
    """
    if not license_obj:
        return True
    
    if license_obj.expires_at is None:
        # No expiration date means license doesn't expire
        return False
    
    now = datetime.now(timezone.utc)
    
    # Ensure expires_at is timezone-aware
    expires_at = license_obj.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    is_expired = expires_at < now
    
    if is_expired:
        logger.info({
            "event": "license_expired_check",
            "license_id": str(license_obj.id),
            "expires_at": str(license_obj.expires_at),
            "now": str(now)
        })
    
    return is_expired


def is_license_expired_by_date(expires_at: Optional[datetime]) -> bool:
    """
    Check if a license has expired based on expiration date.
    
    Args:
        expires_at: The expiration datetime.
        
    Returns:
        bool: True if expired, False if valid or no expiration date.
    """
    if expires_at is None:
        return False
    
    now = datetime.now(timezone.utc)
    
    # Ensure expires_at is timezone-aware
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    return expires_at < now


def get_license_limits(tier: str) -> Dict[str, Any]:
    """
    Get the limits for a license tier.
    
    Args:
        tier: The tier name ("mini", "parwa", "parwa_high").
        
    Returns:
        dict: Dictionary containing max_calls, max_users, and other limits.
              Returns empty dict if tier is invalid.
    """
    if not tier or tier not in TIER_LIMITS:
        logger.warning({"event": "invalid_tier_request", "tier": tier})
        return {}
    
    return TIER_LIMITS[tier].copy()


def get_all_tier_limits() -> Dict[str, Dict[str, Any]]:
    """
    Get limits for all tiers.
    
    Returns:
        dict: Dictionary of tier names to their limits.
    """
    return {tier: limits.copy() for tier, limits in TIER_LIMITS.items()}


def validate_subscription(subscription: Subscription) -> bool:
    """
    Validate that a subscription is active and valid.
    
    Args:
        subscription: The Subscription ORM object.
        
    Returns:
        bool: True if subscription is valid, False otherwise.
    """
    if not subscription:
        return False
    
    if not subscription.is_active_subscription():
        return False
    
    # Check if subscription period is valid
    now = datetime.now(timezone.utc)
    period_start = subscription.current_period_start
    period_end = subscription.current_period_end
    
    # Ensure timezone awareness
    if period_start.tzinfo is None:
        period_start = period_start.replace(tzinfo=timezone.utc)
    if period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=timezone.utc)
    
    return period_start <= now <= period_end


def get_tier_from_subscription(subscription: Optional[Subscription]) -> str:
    """
    Get the tier from a subscription object.
    
    Args:
        subscription: The Subscription ORM object.
        
    Returns:
        str: The tier name, or "mini" as default.
    """
    if subscription and subscription.plan_tier:
        return subscription.plan_tier
    return "mini"


def compare_tiers(tier1: str, tier2: str) -> int:
    """
    Compare two tiers.
    
    Args:
        tier1: First tier name.
        tier2: Second tier name.
        
    Returns:
        int: -1 if tier1 < tier2, 0 if equal, 1 if tier1 > tier2.
    """
    tier_order = {"mini": 0, "parwa": 1, "parwa_high": 2}
    
    if tier1 not in tier_order or tier2 not in tier_order:
        return 0
    
    if tier_order[tier1] < tier_order[tier2]:
        return -1
    elif tier_order[tier1] > tier_order[tier2]:
        return 1
    return 0


def is_upgrade(current_tier: str, new_tier: str) -> bool:
    """
    Check if changing from current_tier to new_tier is an upgrade.
    
    Args:
        current_tier: Current tier name.
        new_tier: New tier name.
        
    Returns:
        bool: True if it's an upgrade, False otherwise.
    """
    return compare_tiers(current_tier, new_tier) < 0


def is_downgrade(current_tier: str, new_tier: str) -> bool:
    """
    Check if changing from current_tier to new_tier is a downgrade.
    
    Args:
        current_tier: Current tier name.
        new_tier: New tier name.
        
    Returns:
        bool: True if it's a downgrade, False otherwise.
    """
    return compare_tiers(current_tier, new_tier) > 0
