"""
Overage Handler for SaaS Advanced Module.

Provides overage handling including:
- Overage detection
- Overage rate application
- Soft vs hard limits
- Grace period for overages
- Automatic upgrade suggestions
- Overage notification workflows
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LimitType(str, Enum):
    """Types of limits."""
    SOFT = "soft"  # Warning only, usage continues
    HARD = "hard"  # Usage blocked when exceeded


class OverageStatus(str, Enum):
    """Overage status."""
    NONE = "none"
    WARNING = "warning"
    OVER_LIMIT = "over_limit"
    GRACE_PERIOD = "grace_period"
    BLOCKED = "blocked"


@dataclass
class OverageRecord:
    """Represents an overage event."""
    id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    usage_type: str = ""
    limit: float = 0.0
    actual: float = 0.0
    overage: float = 0.0
    overage_cost: float = 0.0
    status: OverageStatus = OverageStatus.NONE
    grace_period_ends: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "client_id": self.client_id,
            "usage_type": self.usage_type,
            "limit": self.limit,
            "actual": self.actual,
            "overage": self.overage,
            "overage_cost": self.overage_cost,
            "status": self.status.value,
            "grace_period_ends": self.grace_period_ends.isoformat() if self.grace_period_ends else None,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


# Grace period configuration
DEFAULT_GRACE_PERIOD_DAYS = 3
OVERAGE_RATES = {
    "api_calls": 0.002,  # $0.002 per call over limit
    "ai_interactions": 0.03,  # $0.03 per interaction over limit
    "voice_minutes": 0.15,  # $0.15 per minute over limit
    "tickets": 0.50,  # $0.50 per ticket over limit
    "storage_gb": 1.00,  # $1.00 per GB over limit
    "sms_messages": 0.08,  # $0.08 per SMS over limit
}

# Soft vs hard limit configuration by tier
LIMIT_CONFIG = {
    "mini": {
        "api_calls": {"type": LimitType.HARD, "grace": False},
        "ai_interactions": {"type": LimitType.HARD, "grace": False},
        "tickets": {"type": LimitType.SOFT, "grace": True},
        "voice_minutes": {"type": LimitType.HARD, "grace": False},
        "storage_gb": {"type": LimitType.SOFT, "grace": True},
        "sms_messages": {"type": LimitType.HARD, "grace": False},
    },
    "parwa": {
        "api_calls": {"type": LimitType.SOFT, "grace": True},
        "ai_interactions": {"type": LimitType.SOFT, "grace": True},
        "tickets": {"type": LimitType.SOFT, "grace": True},
        "voice_minutes": {"type": LimitType.SOFT, "grace": True},
        "storage_gb": {"type": LimitType.SOFT, "grace": True},
        "sms_messages": {"type": LimitType.SOFT, "grace": True},
    },
    "parwa_high": {
        "api_calls": {"type": LimitType.SOFT, "grace": True},
        "ai_interactions": {"type": LimitType.SOFT, "grace": True},
        "tickets": {"type": LimitType.SOFT, "grace": True},
        "voice_minutes": {"type": LimitType.SOFT, "grace": True},
        "storage_gb": {"type": LimitType.SOFT, "grace": True},
        "sms_messages": {"type": LimitType.SOFT, "grace": True},
    },
}


class OverageHandler:
    """
    Handles usage overages for SaaS subscriptions.

    Features:
    - Detect overages
    - Apply overage rates
    - Manage soft vs hard limits
    - Grace periods
    - Upgrade suggestions
    - Notifications
    """

    def __init__(
        self,
        client_id: str = "",
        tier: str = "mini"
    ):
        """
        Initialize overage handler.

        Args:
            client_id: Client identifier
            tier: Subscription tier
        """
        self.client_id = client_id
        self.tier = tier
        self._overages: Dict[str, OverageRecord] = {}
        self._limit_config = LIMIT_CONFIG.get(tier, LIMIT_CONFIG["mini"])

    async def check_overage(
        self,
        usage_type: str,
        limit: float,
        actual: float
    ) -> OverageRecord:
        """
        Check for overage and create record if applicable.

        Args:
            usage_type: Type of usage
            limit: Usage limit
            actual: Actual usage

        Returns:
            OverageRecord
        """
        config = self._limit_config.get(usage_type, {"type": LimitType.HARD, "grace": False})

        if actual <= limit:
            # No overage
            return OverageRecord(
                client_id=self.client_id,
                usage_type=usage_type,
                limit=limit,
                actual=actual,
                overage=0,
                status=OverageStatus.NONE,
            )

        # Calculate overage
        overage = actual - limit
        overage_rate = OVERAGE_RATES.get(usage_type, 0.01)
        overage_cost = overage * overage_rate

        # Determine status
        if config["type"] == LimitType.SOFT:
            status = OverageStatus.WARNING
        else:
            status = OverageStatus.OVER_LIMIT

        # Apply grace period if applicable
        grace_period_ends = None
        if config["grace"] and overage > 0:
            status = OverageStatus.GRACE_PERIOD
            grace_period_ends = datetime.now(timezone.utc) + timedelta(days=DEFAULT_GRACE_PERIOD_DAYS)

        record = OverageRecord(
            client_id=self.client_id,
            usage_type=usage_type,
            limit=limit,
            actual=actual,
            overage=overage,
            overage_cost=overage_cost,
            status=status,
            grace_period_ends=grace_period_ends,
        )

        # Store record
        key = f"{self.client_id}_{usage_type}"
        self._overages[key] = record

        logger.warning(
            "Overage detected",
            extra={
                "client_id": self.client_id,
                "usage_type": usage_type,
                "limit": limit,
                "actual": actual,
                "overage": overage,
                "status": status.value,
            }
        )

        return record

    async def apply_overage_rate(
        self,
        usage_type: str,
        overage: float,
        custom_rate: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate overage charges.

        Args:
            usage_type: Type of usage
            overage: Overage amount
            custom_rate: Optional custom rate

        Returns:
            Dict with overage charges
        """
        rate = custom_rate or OVERAGE_RATES.get(usage_type, 0.01)
        cost = overage * rate

        return {
            "usage_type": usage_type,
            "overage": overage,
            "rate": rate,
            "cost": round(cost, 2),
            "currency": "USD",
        }

    async def is_usage_allowed(
        self,
        usage_type: str,
        current: float,
        limit: float
    ) -> Dict[str, Any]:
        """
        Check if additional usage is allowed.

        Args:
            usage_type: Type of usage
            current: Current usage
            limit: Usage limit

        Returns:
            Dict with allowance status
        """
        config = self._limit_config.get(usage_type, {"type": LimitType.HARD, "grace": False})

        if current < limit:
            return {
                "allowed": True,
                "reason": "within_limit",
                "remaining": limit - current,
            }

        if config["type"] == LimitType.SOFT:
            # Check grace period
            key = f"{self.client_id}_{usage_type}"
            overage = self._overages.get(key)

            if overage and overage.grace_period_ends:
                if datetime.now(timezone.utc) < overage.grace_period_ends:
                    return {
                        "allowed": True,
                        "reason": "grace_period",
                        "grace_period_ends": overage.grace_period_ends.isoformat(),
                    }

            return {
                "allowed": True,
                "reason": "soft_limit",
                "overage_charges_apply": True,
            }

        # Hard limit
        return {
            "allowed": False,
            "reason": "hard_limit_exceeded",
            "current": current,
            "limit": limit,
        }

    async def suggest_upgrade(
        self,
        overages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Suggest upgrade based on overage patterns.

        Args:
            overages: List of overage records

        Returns:
            Dict with upgrade suggestion
        """
        if not overages:
            return {
                "suggested": False,
                "reason": "no_overages",
            }

        # Calculate total overage cost
        total_overage_cost = sum(o.get("overage_cost", 0) for o in overages)

        # Find most problematic usage types
        sorted_overages = sorted(
            overages,
            key=lambda x: x.get("overage_cost", 0),
            reverse=True
        )

        # Determine suggested tier
        tier_order = ["mini", "parwa", "parwa_high", "enterprise"]
        current_idx = tier_order.index(self.tier) if self.tier in tier_order else 0

        suggested_tier = self.tier
        if total_overage_cost > 100:
            suggested_tier = tier_order[min(current_idx + 2, len(tier_order) - 1)]
        elif total_overage_cost > 30:
            suggested_tier = tier_order[min(current_idx + 1, len(tier_order) - 1)]

        # Calculate savings
        potential_savings = total_overage_cost * 0.8  # Assume 80% savings with upgrade

        return {
            "suggested": suggested_tier != self.tier,
            "current_tier": self.tier,
            "suggested_tier": suggested_tier,
            "total_overage_cost": round(total_overage_cost, 2),
            "potential_savings": round(potential_savings, 2),
            "top_overage_types": [o.get("usage_type") for o in sorted_overages[:3]],
            "overages": sorted_overages,
        }

    async def get_overage_history(
        self,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get overage history for client.

        Args:
            limit: Maximum records to return

        Returns:
            List of overage records
        """
        records = [
            record.to_dict()
            for record in self._overages.values()
            if record.client_id == self.client_id
        ]

        records.sort(key=lambda x: x["created_at"], reverse=True)

        return records[:limit]

    async def resolve_overage(
        self,
        usage_type: str,
        resolution: str
    ) -> Dict[str, Any]:
        """
        Resolve an overage.

        Args:
            usage_type: Type of usage to resolve
            resolution: Resolution type (upgraded, paid, reset)

        Returns:
            Dict with resolution result
        """
        key = f"{self.client_id}_{usage_type}"
        record = self._overages.get(key)

        if not record:
            return {
                "resolved": False,
                "reason": "no_overage_found",
            }

        record.resolved_at = datetime.now(timezone.utc)
        record.status = OverageStatus.NONE

        logger.info(
            "Overage resolved",
            extra={
                "client_id": self.client_id,
                "usage_type": usage_type,
                "resolution": resolution,
            }
        )

        return {
            "resolved": True,
            "usage_type": usage_type,
            "resolution": resolution,
            "resolved_at": record.resolved_at.isoformat(),
        }

    def update_tier(self, new_tier: str) -> None:
        """
        Update the subscription tier.

        Args:
            new_tier: New tier value
        """
        self.tier = new_tier
        self._limit_config = LIMIT_CONFIG.get(new_tier, LIMIT_CONFIG["mini"])

        logger.info(
            "Overage handler tier updated",
            extra={"client_id": self.client_id, "new_tier": new_tier}
        )


# Export for testing
__all__ = [
    "OverageHandler",
    "OverageRecord",
    "OverageStatus",
    "LimitType",
    "OVERAGE_RATES",
    "LIMIT_CONFIG",
]
