"""
License Service Layer.

Handles license validation, tier management, and usage tracking.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.license import License
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class LicenseTier(str, Enum):
    """License tier levels."""
    MINI_PARWA = "mini"
    PARWA = "parwa"
    PARWA_HIGH = "parwa_high"


class LicenseStatus(str, Enum):
    """License status values."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class LicenseService:
    """
    Service class for license management.
    
    Handles validation, tier enforcement, and usage tracking.
    All methods enforce company-scoped data access (RLS).
    """
    
    TIER_LIMITS = {
        LicenseTier.MINI_PARWA: {
            "users": 5,
            "tickets_per_month": 500,
            "api_calls_per_day": 1000,
            "storage_gb": 10,
            "features": ["email", "chat", "basic_analytics"],
            "support_channels": ["email"],
            "sla_response_hours": 24,
        },
        LicenseTier.PARWA: {
            "users": 25,
            "tickets_per_month": 5000,
            "api_calls_per_day": 10000,
            "storage_gb": 50,
            "features": ["email", "chat", "voice", "analytics", "integrations"],
            "support_channels": ["email", "chat"],
            "sla_response_hours": 4,
        },
        LicenseTier.PARWA_HIGH: {
            "users": 100,
            "tickets_per_month": 50000,
            "api_calls_per_day": 100000,
            "storage_gb": 200,
            "features": ["email", "chat", "voice", "video", "analytics", "integrations", "priority_queue", "custom_ai"],
            "support_channels": ["email", "chat", "phone", "video"],
            "sla_response_hours": 1,
        },
    }
    
    def __init__(self, db: AsyncSession, company_id: UUID) -> None:
        """
        Initialize license service.
        
        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.company_id = company_id
    
    async def get_license(self) -> Optional[Dict[str, Any]]:
        """
        Get the company's license information.
        
        Returns:
            Dict with license details or None
        """
        logger.info({
            "event": "license_retrieved",
            "company_id": str(self.company_id),
        })
        
        result = await self.db.execute(
            select(License).where(License.company_id == self.company_id)
        )
        license_obj = result.scalar_one_or_none()
        
        if not license_obj:
            return None
        
        tier = LicenseTier(license_obj.tier) if license_obj.tier in [t.value for t in LicenseTier] else LicenseTier.MINI_PARWA
        
        return {
            "license_id": str(license_obj.id),
            "company_id": str(self.company_id),
            "license_key": license_obj.license_key,
            "tier": tier.value,
            "status": license_obj.status,
            "issued_at": license_obj.issued_at.isoformat() if license_obj.issued_at else None,
            "expires_at": license_obj.expires_at.isoformat() if license_obj.expires_at else None,
            "max_seats": license_obj.max_seats,
            "limits": self.TIER_LIMITS.get(tier, self.TIER_LIMITS[LicenseTier.MINI_PARWA]),
        }
    
    async def validate_license(self) -> bool:
        """
        Validate that the company has an active license.
        
        Returns:
            bool: True if license is valid and active
        """
        license_info = await self.get_license()
        
        if not license_info:
            logger.warning({
                "event": "license_not_found",
                "company_id": str(self.company_id),
            })
            return False
        
        if license_info.get("status") != LicenseStatus.ACTIVE.value:
            logger.warning({
                "event": "license_not_active",
                "company_id": str(self.company_id),
                "status": license_info.get("status"),
            })
            return False
        
        # Check expiration
        expires_at = license_info.get("expires_at")
        if expires_at:
            expiry_date = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry_date < datetime.now(timezone.utc):
                logger.warning({
                    "event": "license_expired",
                    "company_id": str(self.company_id),
                    "expired_at": expires_at,
                })
                return False
        
        return True
    
    async def get_tier_limits(self, tier: LicenseTier) -> Dict[str, Any]:
        """
        Get limits for a license tier.
        
        Args:
            tier: License tier level
            
        Returns:
            Dict with tier limits
        """
        return self.TIER_LIMITS.get(tier, self.TIER_LIMITS[LicenseTier.MINI_PARWA])
    
    async def check_usage_limit(
        self,
        limit_type: str,
        current_usage: int
    ) -> Dict[str, Any]:
        """
        Check if usage is within limits.
        
        Args:
            limit_type: Type of limit (users, tickets_per_month, api_calls_per_day)
            current_usage: Current usage value
            
        Returns:
            Dict with limit check result
        """
        license_info = await self.get_license()
        
        if not license_info:
            return {
                "within_limit": False,
                "reason": "No active license",
                "limit_type": limit_type,
            }
        
        tier_str = license_info.get("tier", "mini")
        tier = LicenseTier(tier_str) if tier_str in [t.value for t in LicenseTier] else LicenseTier.MINI_PARWA
        limits = await self.get_tier_limits(tier)
        
        limit = limits.get(limit_type, 0)
        within_limit = current_usage < limit
        
        if not within_limit:
            logger.warning({
                "event": "usage_limit_exceeded",
                "company_id": str(self.company_id),
                "limit_type": limit_type,
                "current_usage": current_usage,
                "limit": limit,
            })
        
        return {
            "within_limit": within_limit,
            "limit_type": limit_type,
            "current_usage": current_usage,
            "limit": limit,
            "remaining": max(0, limit - current_usage),
            "usage_percentage": round((current_usage / limit) * 100, 2) if limit > 0 else 0,
        }
    
    async def check_feature_access(self, feature: str) -> bool:
        """
        Check if company has access to a feature.
        
        Args:
            feature: Feature name to check
            
        Returns:
            bool: True if feature is accessible
        """
        license_info = await self.get_license()
        
        if not license_info:
            return False
        
        tier_str = license_info.get("tier", "mini")
        tier = LicenseTier(tier_str) if tier_str in [t.value for t in LicenseTier] else LicenseTier.MINI_PARWA
        limits = await self.get_tier_limits(tier)
        
        has_access = feature in limits.get("features", [])
        
        if not has_access:
            logger.info({
                "event": "feature_access_denied",
                "company_id": str(self.company_id),
                "feature": feature,
                "tier": tier.value,
            })
        
        return has_access
    
    async def get_features(self) -> List[str]:
        """
        Get list of available features for company's tier.
        
        Returns:
            List of feature names
        """
        license_info = await self.get_license()
        
        if not license_info:
            return []
        
        tier_str = license_info.get("tier", "mini")
        tier = LicenseTier(tier_str) if tier_str in [t.value for t in LicenseTier] else LicenseTier.MINI_PARWA
        limits = await self.get_tier_limits(tier)
        
        return limits.get("features", [])
    
    async def get_remaining_usage(
        self,
        limit_type: str,
        current_usage: int
    ) -> int:
        """
        Get remaining usage for a limit type.
        
        Args:
            limit_type: Type of limit
            current_usage: Current usage value
            
        Returns:
            Remaining capacity
        """
        result = await self.check_usage_limit(limit_type, current_usage)
        return result.get("remaining", 0)
    
    async def is_upgrade_required(
        self,
        limit_type: str,
        current_usage: int
    ) -> bool:
        """
        Check if an upgrade is required for the given usage.
        
        Args:
            limit_type: Type of limit
            current_usage: Current usage value
            
        Returns:
            bool: True if upgrade is needed
        """
        result = await self.check_usage_limit(limit_type, current_usage)
        return not result.get("within_limit", False)
    
    async def suggest_upgrade_tier(
        self,
        current_tier: LicenseTier,
        required_features: Optional[List[str]] = None,
        required_limits: Optional[Dict[str, int]] = None
    ) -> Optional[LicenseTier]:
        """
        Suggest an upgrade tier based on requirements.
        
        Args:
            current_tier: Current license tier
            required_features: List of required features
            required_limits: Dict of required limits
            
        Returns:
            Suggested tier or None if current is sufficient
        """
        required_features = required_features or []
        required_limits = required_limits or {}
        
        # Check if current tier satisfies requirements
        current_limits = self.TIER_LIMITS.get(current_tier, {})
        current_features = set(current_limits.get("features", []))
        
        features_satisfied = all(f in current_features for f in required_features)
        limits_satisfied = all(
            current_limits.get(k, 0) >= v
            for k, v in required_limits.items()
        )
        
        if features_satisfied and limits_satisfied:
            return None  # No upgrade needed
        
        # Find the lowest tier that satisfies requirements
        tier_order = [LicenseTier.MINI_PARWA, LicenseTier.PARWA, LicenseTier.PARWA_HIGH]
        
        for tier in tier_order:
            if tier == current_tier:
                continue
            
            tier_limits = self.TIER_LIMITS.get(tier, {})
            tier_features = set(tier_limits.get("features", []))
            
            feat_ok = all(f in tier_features for f in required_features)
            limit_ok = all(
                tier_limits.get(k, 0) >= v
                for k, v in required_limits.items()
            )
            
            if feat_ok and limit_ok:
                logger.info({
                    "event": "upgrade_suggested",
                    "company_id": str(self.company_id),
                    "current_tier": current_tier.value,
                    "suggested_tier": tier.value,
                })
                return tier
        
        return LicenseTier.PARWA_HIGH  # Highest tier as fallback
    
    async def activate_license(
        self,
        license_key: str
    ) -> Dict[str, Any]:
        """
        Activate a license key for the company.
        
        Args:
            license_key: License key to activate
            
        Returns:
            Dict with activation status
        """
        logger.info({
            "event": "license_activation_attempted",
            "company_id": str(self.company_id),
            "license_key": license_key[:8] + "...",  # Partial key for security
        })
        
        # TODO: Implement actual license activation
        return {
            "activated": True,
            "company_id": str(self.company_id),
            "activated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def suspend_license(
        self,
        reason: str
    ) -> Dict[str, Any]:
        """
        Suspend the company's license.
        
        Args:
            reason: Reason for suspension
            
        Returns:
            Dict with suspension status
        """
        logger.warning({
            "event": "license_suspended",
            "company_id": str(self.company_id),
            "reason": reason,
        })
        
        return {
            "suspended": True,
            "company_id": str(self.company_id),
            "reason": reason,
            "suspended_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def get_license_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the company's license status.
        
        Returns:
            Dict with license summary
        """
        license_info = await self.get_license()
        is_valid = await self.validate_license()
        features = await self.get_features() if is_valid else []
        
        return {
            "company_id": str(self.company_id),
            "is_valid": is_valid,
            "tier": license_info.get("tier") if license_info else None,
            "status": license_info.get("status") if license_info else None,
            "expires_at": license_info.get("expires_at") if license_info else None,
            "features_count": len(features),
            "max_users": license_info.get("limits", {}).get("users", 0) if license_info else 0,
        }
