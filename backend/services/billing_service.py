"""
Billing Service Layer

Business logic for subscriptions, billing, and usage tracking.
All methods are company-scoped for RLS compliance.

CRITICAL: Stripe is NEVER called without a pending_approval record.
Payment processing requires explicit approval workflow.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func

from backend.models.subscription import Subscription
from backend.models.company import Company, PlanTierEnum
from backend.models.user import User
from backend.models.usage_log import UsageLog, AITier
from backend.models.audit_trail import AuditTrail


class SubscriptionTier(str, Enum):
    """Subscription tier enumeration."""
    MINI = "mini"
    PARWA = "parwa"
    PARWA_HIGH = "parwa_high"


class SubscriptionStatus(str, Enum):
    """Subscription status enumeration."""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    TRIALING = "trialing"


class ApprovalType(str, Enum):
    """Types of approval workflows."""
    SUBSCRIPTION_CHANGE = "subscription_change"
    REFUND = "refund"
    PAYMENT_METHOD = "payment_method"
    PLAN_UPGRADE = "plan_upgrade"


# Tier pricing configuration (USD per month)
TIER_PRICING = {
    SubscriptionTier.MINI: 1000.0,
    SubscriptionTier.PARWA: 2500.0,
    SubscriptionTier.PARWA_HIGH: 4500.0,
}

# Tier pricing in cents for consistency with billing API
TIER_PRICING_CENTS = {
    SubscriptionTier.MINI: 100000,
    SubscriptionTier.PARWA: 250000,
    SubscriptionTier.PARWA_HIGH: 450000,
}

# Tier usage limits
TIER_LIMITS = {
    SubscriptionTier.MINI: {
        "tickets_per_month": 500,
        "voice_minutes_per_month": 100,
        "ai_interactions_per_month": 1000,
        "max_calls": 2,
        "sms": False,
        "refund_execution": False,
    },
    SubscriptionTier.PARWA: {
        "tickets_per_month": 2000,
        "voice_minutes_per_month": 500,
        "ai_interactions_per_month": 5000,
        "max_calls": 3,
        "sms": True,
        "refund_execution": True,
    },
    SubscriptionTier.PARWA_HIGH: {
        "tickets_per_month": 10000,
        "voice_minutes_per_month": 2000,
        "ai_interactions_per_month": 25000,
        "max_calls": 5,
        "sms": True,
        "refund_execution": True,
    },
}


class PendingApproval:
    """
    Mock class for pending approval records.
    In production, this would be a database model.
    """
    def __init__(
        self,
        approval_type: str,
        amount: float,
        requested_by: UUID,
        company_id: UUID,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.id = uuid4()
        self.approval_type = approval_type
        self.amount = amount
        self.requested_by = requested_by
        self.company_id = company_id
        self.metadata = metadata or {}
        self.status = "pending"
        self.created_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "approval_type": self.approval_type,
            "amount": self.amount,
            "requested_by": str(self.requested_by),
            "company_id": str(self.company_id),
            "metadata": self.metadata,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class BillingService:
    """
    Service class for billing business logic.

    Provides subscription management, usage tracking, and billing calculations.
    All methods enforce company-scoped data access (RLS).

    CRITICAL: Never call Stripe without pending_approval record.
    """

    def __init__(self, db: AsyncSession, company_id: UUID):
        """
        Initialize billing service.

        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.company_id = company_id
        self._pending_approvals: List[PendingApproval] = []

    async def get_subscription(self) -> Optional[Subscription]:
        """
        Get current subscription for company.

        Returns:
            Subscription if found, None otherwise
        """
        result = await self.db.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.company_id == self.company_id,
                    Subscription.status == SubscriptionStatus.ACTIVE.value
                )
            )
            .order_by(desc(Subscription.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_subscription_tier(
        self,
        new_tier: SubscriptionTier,
        requested_by: UUID
    ) -> Dict[str, Any]:
        """
        Update subscription tier (upgrade or downgrade).

        Creates pending_approval record for payment processing.
        Does NOT call Stripe directly.

        Args:
            new_tier: Target tier
            requested_by: User UUID requesting change

        Returns:
            Dict with:
            - subscription: Updated Subscription
            - pending_approval_id: UUID for approval workflow
            - price_change: float (monthly difference)
        """
        # Get current subscription
        subscription = await self.get_subscription()
        if not subscription:
            raise ValueError("No active subscription found for company")

        # Convert current tier to enum
        current_tier_str = subscription.plan_tier
        current_tier = SubscriptionTier(current_tier_str)

        # Validate tier change
        validation = await self.validate_tier_change(current_tier, new_tier)
        if not validation["valid"]:
            raise ValueError(validation["message"])

        # Calculate price change
        current_price = TIER_PRICING.get(current_tier, 0.0)
        new_price = TIER_PRICING.get(new_tier, 0.0)
        price_change = new_price - current_price

        is_upgrade = new_price > current_price

        # Create pending approval for payment processing
        pending_approval = PendingApproval(
            approval_type=ApprovalType.SUBSCRIPTION_CHANGE.value,
            amount=abs(price_change),
            requested_by=requested_by,
            company_id=self.company_id,
            metadata={
                "old_tier": current_tier.value,
                "new_tier": new_tier.value,
                "is_upgrade": is_upgrade,
            }
        )
        self._pending_approvals.append(pending_approval)

        # For downgrades, update immediately (takes effect at period end in real impl)
        # For upgrades, require payment approval first
        if not is_upgrade:
            subscription.plan_tier = new_tier.value
            subscription.amount_cents = TIER_PRICING_CENTS.get(new_tier, 0)
            await self.db.flush()

        # Log audit trail
        await self._log_audit(
            action="subscription_tier_change_requested",
            entity_type="subscription",
            entity_id=subscription.id,
            changes={
                "old_tier": current_tier.value,
                "new_tier": new_tier.value,
                "price_change": price_change,
                "pending_approval_id": str(pending_approval.id),
            }
        )

        return {
            "subscription": subscription,
            "pending_approval_id": pending_approval.id,
            "price_change": price_change,
            "is_upgrade": is_upgrade,
        }

    async def get_invoices(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List invoices for company.

        Args:
            limit: Max results
            offset: Pagination offset

        Returns:
            List of invoice dicts
        """
        subscription = await self.get_subscription()
        if not subscription:
            return []

        # Generate mock invoices for demonstration
        # In production, these would come from an invoices table
        invoices = []
        for i in range(3):
            invoice_id = uuid4()
            invoices.append({
                "id": str(invoice_id),
                "company_id": str(self.company_id),
                "subscription_id": str(subscription.id),
                "amount_cents": subscription.amount_cents,
                "currency": subscription.currency,
                "status": "paid" if i > 0 else "open",
                "due_date": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
                "paid_at": subscription.current_period_end.isoformat() if i > 0 and subscription.current_period_end else None,
                "items": [
                    {
                        "description": f"PARWA {subscription.plan_tier} subscription",
                        "amount_cents": subscription.amount_cents,
                        "quantity": 1,
                    }
                ],
                "created_at": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
            })

        return invoices[offset:offset + limit]

    async def get_invoice_by_id(self, invoice_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get specific invoice details.

        Args:
            invoice_id: Invoice UUID

        Returns:
            Invoice dict if found, None otherwise
        """
        invoices = await self.get_invoices()
        for invoice in invoices:
            if invoice["id"] == str(invoice_id):
                return invoice
        return None

    async def get_usage(self) -> Dict[str, Any]:
        """
        Get current usage vs tier limits.

        Returns:
            Dict with:
            - tier: SubscriptionTier
            - usage: Dict of usage metrics
            - limits: Dict of tier limits
            - percentages: Dict of usage percentages
        """
        subscription = await self.get_subscription()
        if not subscription:
            raise ValueError("No active subscription found")

        tier = SubscriptionTier(subscription.plan_tier)
        limits = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.MINI])

        # Fetch usage logs for current billing period
        usage_result = await self.db.execute(
            select(
                UsageLog.ai_tier,
                func.sum(UsageLog.request_count).label("total_requests"),
                func.sum(UsageLog.token_count).label("total_tokens"),
                func.sum(UsageLog.error_count).label("total_errors"),
                func.avg(UsageLog.avg_latency_ms).label("avg_latency"),
            )
            .where(
                and_(
                    UsageLog.company_id == self.company_id,
                    UsageLog.log_date >= subscription.current_period_start.date(),
                    UsageLog.log_date <= subscription.current_period_end.date(),
                )
            )
            .group_by(UsageLog.ai_tier)
        )
        usage_rows = usage_result.all()

        # Aggregate usage
        total_requests = 0
        total_tokens = 0
        total_errors = 0
        avg_latency = None

        tier_usage = {tier.value: {"requests": 0, "tokens": 0} for tier in AITier}

        for row in usage_rows:
            tier_name = row.ai_tier.value if row.ai_tier else "light"
            tier_usage[tier_name]["requests"] = row.total_requests or 0
            tier_usage[tier_name]["tokens"] = row.total_tokens or 0
            total_requests += row.total_requests or 0
            total_tokens += row.total_tokens or 0
            total_errors += row.total_errors or 0
            if row.avg_latency:
                avg_latency = row.avg_latency

        # Calculate percentages
        baseline_tokens = limits["ai_interactions_per_month"]
        tokens_percentage = (total_tokens / baseline_tokens * 100) if baseline_tokens > 0 else 0.0

        return {
            "tier": tier.value,
            "usage": {
                "total_requests": total_requests,
                "total_tokens": total_tokens,
                "total_errors": total_errors,
                "avg_latency_ms": round(avg_latency, 2) if avg_latency else None,
                "by_ai_tier": tier_usage,
            },
            "limits": limits,
            "percentages": {
                "ai_interactions": round(tokens_percentage, 2),
            },
        }

    async def check_usage_limits(
        self,
        action: str
    ) -> Dict[str, Any]:
        """
        Check if an action is within usage limits.

        Args:
            action: Action type (ticket, voice_minute, ai_interaction)

        Returns:
            Dict with:
            - allowed: bool
            - current_usage: int
            - limit: int
            - percentage: float
        """
        subscription = await self.get_subscription()
        if not subscription:
            return {
                "allowed": False,
                "current_usage": 0,
                "limit": 0,
                "percentage": 0.0,
                "reason": "No active subscription",
            }

        tier = SubscriptionTier(subscription.plan_tier)
        limits = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.MINI])

        # Map action to limit key
        action_mapping = {
            "ticket": "tickets_per_month",
            "voice_minute": "voice_minutes_per_month",
            "ai_interaction": "ai_interactions_per_month",
        }

        if action not in action_mapping:
            return {
                "allowed": False,
                "current_usage": 0,
                "limit": 0,
                "percentage": 0.0,
                "reason": f"Unknown action: {action}",
            }

        limit_key = action_mapping[action]
        limit = limits.get(limit_key, 0)

        # Get current usage from usage logs
        usage_data = await self.get_usage()

        # Estimate current usage based on requests
        current_usage = usage_data["usage"]["total_requests"]

        # Calculate percentage
        percentage = (current_usage / limit * 100) if limit > 0 else 100.0

        return {
            "allowed": current_usage < limit,
            "current_usage": current_usage,
            "limit": limit,
            "percentage": round(percentage, 2),
        }

    async def calculate_billing(
        self,
        tier: SubscriptionTier,
        period_months: int = 1
    ) -> Dict[str, Any]:
        """
        Calculate billing amount for tier and period.

        Args:
            tier: Subscription tier
            period_months: Billing period in months

        Returns:
            Dict with:
            - base_amount: float
            - period_months: int
            - total: float
            - currency: str
        """
        base_amount = TIER_PRICING.get(tier, 0.0)
        total = base_amount * period_months

        return {
            "base_amount": base_amount,
            "period_months": period_months,
            "total": total,
            "currency": "USD",
        }

    async def create_pending_approval(
        self,
        approval_type: str,
        amount: float,
        requested_by: UUID,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create pending approval record for payment action.

        CRITICAL: This MUST be called BEFORE any Stripe interaction.
        The approval workflow handles the actual payment processing.

        Args:
            approval_type: Type (subscription_change, refund, etc.)
            amount: Amount in USD
            requested_by: User UUID requesting
            metadata: Optional additional data

        Returns:
            Dict with pending_approval details
        """
        pending_approval = PendingApproval(
            approval_type=approval_type,
            amount=amount,
            requested_by=requested_by,
            company_id=self.company_id,
            metadata=metadata,
        )
        self._pending_approvals.append(pending_approval)

        # Log audit trail
        await self._log_audit(
            action="pending_approval_created",
            entity_type="pending_approval",
            entity_id=pending_approval.id,
            changes={
                "approval_type": approval_type,
                "amount": amount,
                "requested_by": str(requested_by),
            }
        )

        return pending_approval.to_dict()

    async def get_tier_pricing(self) -> Dict[str, Any]:
        """
        Get pricing for all tiers.

        Returns:
            Dict mapping tier to monthly price
        """
        return {
            tier.value: {
                "monthly_price": price,
                "monthly_cents": int(price * 100),
            }
            for tier, price in TIER_PRICING.items()
        }

    async def validate_tier_change(
        self,
        current_tier: SubscriptionTier,
        new_tier: SubscriptionTier
    ) -> Dict[str, Any]:
        """
        Validate if tier change is allowed.

        Args:
            current_tier: Current subscription tier
            new_tier: Target tier

        Returns:
            Dict with:
            - valid: bool
            - is_upgrade: bool
            - message: str
        """
        if current_tier == new_tier:
            return {
                "valid": False,
                "is_upgrade": False,
                "message": "Cannot change to the same tier",
            }

        current_price = TIER_PRICING.get(current_tier, 0.0)
        new_price = TIER_PRICING.get(new_tier, 0.0)
        is_upgrade = new_price > current_price

        return {
            "valid": True,
            "is_upgrade": is_upgrade,
            "message": f"{'Upgrade' if is_upgrade else 'Downgrade'} from {current_tier.value} to {new_tier.value}",
        }

    async def get_company(self) -> Optional[Company]:
        """
        Get company details.

        Returns:
            Company if found, None otherwise
        """
        result = await self.db.execute(
            select(Company).where(Company.id == self.company_id)
        )
        return result.scalar_one_or_none()

    async def _log_audit(
        self,
        action: str,
        entity_type: str,
        entity_id: UUID,
        changes: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log audit trail entry.

        Args:
            action: Action performed (create, update, escalate, etc.)
            entity_type: Entity type (ticket, message, etc.)
            entity_id: Entity UUID
            changes: Optional dict of changes
        """
        audit_entry = AuditTrail(
            company_id=self.company_id,
            actor="billing_service",
            action=action,
            details={
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "changes": changes or {},
            },
        )
        audit_entry.entry_hash = audit_entry.compute_hash()
        self.db.add(audit_entry)
        await self.db.flush()


# Export for testing
__all__ = [
    "BillingService",
    "SubscriptionTier",
    "SubscriptionStatus",
    "ApprovalType",
    "PendingApproval",
    "TIER_PRICING",
    "TIER_PRICING_CENTS",
    "TIER_LIMITS",
]
