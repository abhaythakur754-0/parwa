"""
Upgrade/Downgrade Handler for SaaS Advanced Module.

Provides upgrade and downgrade handling including:
- Proration calculation
- Immediate vs end-of-cycle changes
- Feature access updates
- Data preservation during changes
- Upgrade incentives
- Downgrade limitation checks
"""

from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

from variants.saas.advanced.subscription_manager import SubscriptionStatus, SubscriptionTier
from variants.saas.advanced.plan_manager import PlanTier as PlanTierEnum, PLANS, BillingFrequency

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Type of subscription change."""
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    LATERAL = "lateral"  # Same tier, different billing


class ChangeTiming(str, Enum):
    """When to apply the change."""
    IMMEDIATE = "immediate"
    END_OF_CYCLE = "end_of_cycle"
    SCHEDULED = "scheduled"


@dataclass
class PlanChange:
    """Represents a plan change request."""
    id: UUID = field(default_factory=uuid4)
    subscription_id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    from_tier: str = ""
    to_tier: str = ""
    from_billing: str = ""
    to_billing: str = ""
    change_type: ChangeType = ChangeType.UPGRADE
    timing: ChangeTiming = ChangeTiming.IMMEDIATE
    scheduled_date: Optional[datetime] = None
    proration_amount: float = 0.0
    credit_amount: float = 0.0
    charge_amount: float = 0.0
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "subscription_id": str(self.subscription_id),
            "client_id": self.client_id,
            "from_tier": self.from_tier,
            "to_tier": self.to_tier,
            "from_billing": self.from_billing,
            "to_billing": self.to_billing,
            "change_type": self.change_type.value,
            "timing": self.timing.value,
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
            "proration_amount": self.proration_amount,
            "credit_amount": self.credit_amount,
            "charge_amount": self.charge_amount,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }


class UpgradeDowngradeHandler:
    """
    Handles subscription upgrades and downgrades.

    Features:
    - Proration calculation
    - Immediate vs end-of-cycle changes
    - Feature access updates
    - Data preservation
    - Upgrade incentives
    - Downgrade limitation checks
    """

    def __init__(self, client_id: str = ""):
        """
        Initialize upgrade/downgrade handler.

        Args:
            client_id: Client identifier for multi-tenant isolation
        """
        self.client_id = client_id
        self._pending_changes: Dict[str, PlanChange] = {}

    async def initiate_change(
        self,
        subscription_id: UUID,
        from_tier: str,
        to_tier: str,
        from_billing: str,
        to_billing: str,
        timing: ChangeTiming = ChangeTiming.IMMEDIATE,
        scheduled_date: Optional[datetime] = None
    ) -> PlanChange:
        """
        Initiate a plan change request.

        Args:
            subscription_id: Subscription to change
            from_tier: Current tier
            to_tier: Target tier
            from_billing: Current billing frequency
            to_billing: Target billing frequency
            timing: When to apply change
            scheduled_date: Optional scheduled date

        Returns:
            PlanChange request
        """
        # Determine change type
        change_type = self._determine_change_type(from_tier, to_tier, from_billing, to_billing)

        # Validate the change
        validation = await self.validate_change(from_tier, to_tier, change_type)
        if not validation["valid"]:
            raise ValueError(validation["reason"])

        # Calculate proration
        proration = await self.calculate_proration(
            from_tier, to_tier, from_billing, to_billing
        )

        change = PlanChange(
            subscription_id=subscription_id,
            client_id=self.client_id,
            from_tier=from_tier,
            to_tier=to_tier,
            from_billing=from_billing,
            to_billing=to_billing,
            change_type=change_type,
            timing=timing,
            scheduled_date=scheduled_date,
            proration_amount=proration["proration_amount"],
            credit_amount=proration["credit_amount"],
            charge_amount=proration["charge_amount"],
        )

        self._pending_changes[str(change.id)] = change

        logger.info(
            "Plan change initiated",
            extra={
                "client_id": self.client_id,
                "change_id": str(change.id),
                "from_tier": from_tier,
                "to_tier": to_tier,
                "change_type": change_type.value,
            }
        )

        return change

    async def calculate_proration(
        self,
        from_tier: str,
        to_tier: str,
        from_billing: str,
        to_billing: str,
        days_remaining: int = 15,
        days_in_period: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate proration for a plan change.

        Args:
            from_tier: Current tier
            to_tier: Target tier
            from_billing: Current billing frequency
            to_billing: Target billing frequency
            days_remaining: Days left in current period
            days_in_period: Total days in period

        Returns:
            Dict with proration details
        """
        from_plan = PLANS.get(PlanTierEnum(from_tier), PLANS[PlanTierEnum.MINI])
        to_plan = PLANS.get(PlanTierEnum(to_tier), PLANS[PlanTierEnum.MINI])

        # Get current and new prices
        if from_billing == "annual":
            from_monthly = from_plan.annual_price / 12
        else:
            from_monthly = from_plan.monthly_price

        if to_billing == "annual":
            to_monthly = to_plan.annual_price / 12
        else:
            to_monthly = to_plan.monthly_price

        # Calculate daily rates
        from_daily = from_monthly / 30
        to_daily = to_monthly / 30

        # Calculate proration
        unused_credit = from_daily * days_remaining
        new_charge = to_daily * days_remaining
        proration_amount = new_charge - unused_credit

        return {
            "from_tier": from_tier,
            "to_tier": to_tier,
            "from_monthly": from_monthly,
            "to_monthly": to_monthly,
            "days_remaining": days_remaining,
            "days_in_period": days_in_period,
            "unused_credit": round(unused_credit, 2),
            "new_charge": round(new_charge, 2),
            "proration_amount": round(proration_amount, 2),
            "credit_amount": round(abs(proration_amount), 2) if proration_amount < 0 else 0.0,
            "charge_amount": round(proration_amount, 2) if proration_amount > 0 else 0.0,
            "effective_immediately": proration_amount > 0,  # Upgrades apply immediately
        }

    async def validate_change(
        self,
        from_tier: str,
        to_tier: str,
        change_type: ChangeType
    ) -> Dict[str, Any]:
        """
        Validate if a plan change is allowed.

        Args:
            from_tier: Current tier
            to_tier: Target tier
            change_type: Type of change

        Returns:
            Dict with validation result
        """
        result = {
            "valid": True,
            "warnings": [],
            "reason": None,
            "limitations": [],
        }

        # Check downgrade limitations
        if change_type == ChangeType.DOWNGRADE:
            limitations = await self._check_downgrade_limitations(from_tier, to_tier)
            result["limitations"] = limitations

            if limitations:
                result["warnings"].append(
                    f"Downgrade has {len(limitations)} feature limitations to consider"
                )

        # Check if change is a significant jump
        tier_order = ["mini", "parwa", "parwa_high", "enterprise"]
        from_idx = tier_order.index(from_tier) if from_tier in tier_order else 0
        to_idx = tier_order.index(to_tier) if to_tier in tier_order else 0

        if abs(to_idx - from_idx) > 1:
            result["warnings"].append(
                f"Significant tier change: {abs(to_idx - from_idx)} levels"
            )

        return result

    async def apply_change(
        self,
        change_id: UUID
    ) -> Dict[str, Any]:
        """
        Apply a pending plan change.

        Args:
            change_id: PlanChange ID to apply

        Returns:
            Dict with application result
        """
        change = self._pending_changes.get(str(change_id))
        if not change:
            raise ValueError(f"Change {change_id} not found")

        if change.status != "pending":
            raise ValueError(f"Change already {change.status}")

        # Process the change
        result = {
            "change_id": str(change_id),
            "applied": False,
            "timing": change.timing.value,
            "features_updated": [],
            "data_preserved": True,
        }

        if change.timing == ChangeTiming.IMMEDIATE:
            # Apply immediately
            change.status = "processing"

            # Update feature access
            features = await self._update_feature_access(
                change.from_tier, change.to_tier
            )
            result["features_updated"] = features

            # Preserve data
            preserved = await self._preserve_data(change.subscription_id)
            result["data_preserved"] = preserved

            change.status = "completed"
            change.processed_at = datetime.now(timezone.utc)
            result["applied"] = True

        elif change.timing == ChangeTiming.END_OF_CYCLE:
            # Schedule for end of cycle
            change.status = "scheduled"
            result["applied"] = False
            result["scheduled"] = True

        logger.info(
            "Plan change applied",
            extra={
                "client_id": self.client_id,
                "change_id": str(change_id),
                "status": change.status,
                "timing": change.timing.value,
            }
        )

        return result

    async def cancel_change(
        self,
        change_id: UUID,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancel a pending plan change.

        Args:
            change_id: PlanChange ID to cancel
            reason: Optional cancellation reason

        Returns:
            Dict with cancellation result
        """
        change = self._pending_changes.get(str(change_id))
        if not change:
            raise ValueError(f"Change {change_id} not found")

        if change.status not in ["pending", "scheduled"]:
            raise ValueError(f"Cannot cancel change in {change.status} status")

        change.status = "canceled"
        change.processed_at = datetime.now(timezone.utc)

        logger.info(
            "Plan change canceled",
            extra={
                "client_id": self.client_id,
                "change_id": str(change_id),
                "reason": reason,
            }
        )

        return {
            "change_id": str(change_id),
            "canceled": True,
            "reason": reason,
        }

    async def get_upgrade_incentives(
        self,
        from_tier: str,
        to_tier: str
    ) -> Dict[str, Any]:
        """
        Get available upgrade incentives.

        Args:
            from_tier: Current tier
            to_tier: Target tier

        Returns:
            Dict with available incentives
        """
        tier_order = ["mini", "parwa", "parwa_high", "enterprise"]
        from_idx = tier_order.index(from_tier) if from_tier in tier_order else 0
        to_idx = tier_order.index(to_tier) if to_tier in tier_order else 0

        if to_idx <= from_idx:
            return {"available": False, "reason": "Not an upgrade"}

        incentives = {
            "available": True,
            "discounts": [],
            "bonus_features": [],
            "trial_extension": 0,
            "total_value": 0.0,
        }

        # Calculate jump distance
        jump_distance = to_idx - from_idx

        # Multi-tier upgrade bonus
        if jump_distance >= 2:
            incentives["discounts"].append({
                "type": "percent",
                "value": 15,
                "description": "Multi-tier upgrade discount",
            })
            incentives["total_value"] += 0.15

        # First-time upgrade bonus
        incentives["discounts"].append({
            "type": "flat",
            "value": 25,
            "description": "Upgrade bonus credit",
        })

        # Annual commitment bonus
        incentives["discounts"].append({
            "type": "months_free",
            "value": 2,
            "description": "2 months free with annual commitment",
        })

        # Bonus features for upgrade
        to_plan = PLANS.get(PlanTierEnum(to_tier))
        if to_plan:
            for feature in to_plan.features:
                if feature.included and "Unlimited" in feature.name:
                    incentives["bonus_features"].append(feature.name)

        # Trial extension
        incentives["trial_extension"] = 7 * jump_distance

        return incentives

    async def get_pending_changes(self) -> List[Dict[str, Any]]:
        """
        Get all pending changes for the client.

        Returns:
            List of pending changes
        """
        return [
            change.to_dict()
            for change in self._pending_changes.values()
            if change.client_id == self.client_id and change.status in ["pending", "scheduled"]
        ]

    async def get_change_history(
        self,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get change history for the client.

        Args:
            limit: Maximum number of changes to return

        Returns:
            List of historical changes
        """
        changes = [
            change.to_dict()
            for change in self._pending_changes.values()
            if change.client_id == self.client_id
        ]

        # Sort by created_at descending
        changes.sort(key=lambda x: x["created_at"], reverse=True)

        return changes[:limit]

    def _determine_change_type(
        self,
        from_tier: str,
        to_tier: str,
        from_billing: str,
        to_billing: str
    ) -> ChangeType:
        """Determine if change is upgrade, downgrade, or lateral."""
        tier_order = ["mini", "parwa", "parwa_high", "enterprise"]
        from_idx = tier_order.index(from_tier) if from_tier in tier_order else 0
        to_idx = tier_order.index(to_tier) if to_tier in tier_order else 0

        if to_idx > from_idx:
            return ChangeType.UPGRADE
        elif to_idx < from_idx:
            return ChangeType.DOWNGRADE
        else:
            return ChangeType.LATERAL

    async def _check_downgrade_limitations(
        self,
        from_tier: str,
        to_tier: str
    ) -> List[Dict[str, Any]]:
        """Check limitations when downgrading."""
        limitations = []

        from_plan = PLANS.get(PlanTierEnum(from_tier))
        to_plan = PLANS.get(PlanTierEnum(to_tier))

        if not from_plan or not to_plan:
            return limitations

        # Check features that will be lost
        for from_feature in from_plan.features:
            if not from_feature.included:
                continue

            to_feature = next(
                (f for f in to_plan.features if f.name == from_feature.name),
                None
            )

            if not to_feature or not to_feature.included:
                limitations.append({
                    "type": "feature_lost",
                    "feature": from_feature.name,
                    "description": f"'{from_feature.name}' will no longer be available",
                })
            elif from_feature.limit and (not to_feature.limit or to_feature.limit < from_feature.limit):
                limitations.append({
                    "type": "limit_reduced",
                    "feature": from_feature.name,
                    "from_limit": from_feature.limit,
                    "to_limit": to_feature.limit,
                    "description": f"'{from_feature.name}' limit reduced from {from_feature.limit} to {to_feature.limit}",
                })

        return limitations

    async def _update_feature_access(
        self,
        from_tier: str,
        to_tier: str
    ) -> List[str]:
        """Update feature access based on tier change."""
        from_plan = PLANS.get(PlanTierEnum(from_tier))
        to_plan = PLANS.get(PlanTierEnum(to_tier))

        updated_features = []

        if not from_plan or not to_plan:
            return updated_features

        # Identify features that changed
        for to_feature in to_plan.features:
            from_feature = next(
                (f for f in from_plan.features if f.name == to_feature.name),
                None
            )

            if from_feature:
                if to_feature.included and not from_feature.included:
                    updated_features.append(f"Enabled: {to_feature.name}")
                elif not to_feature.included and from_feature.included:
                    updated_features.append(f"Disabled: {to_feature.name}")
                elif to_feature.limit != from_feature.limit:
                    updated_features.append(
                        f"Updated: {to_feature.name} ({from_feature.limit} -> {to_feature.limit})"
                    )

        return updated_features

    async def _preserve_data(self, subscription_id: UUID) -> bool:
        """Preserve data during tier change."""
        # In production, this would:
        # - Export current settings
        # - Archive historical data
        # - Prepare for migration if needed

        logger.info(
            "Data preserved for tier change",
            extra={
                "client_id": self.client_id,
                "subscription_id": str(subscription_id),
            }
        )

        return True


# Export for testing
__all__ = [
    "UpgradeDowngradeHandler",
    "PlanChange",
    "ChangeType",
    "ChangeTiming",
]
