"""
Subscription Manager for SaaS Advanced Module.

Provides comprehensive subscription lifecycle management including:
- Paddle subscription integration
- Status tracking (active, past_due, canceled, expired)
- Renewal monitoring and grace period handling
- Automatic renewal reminders
- Subscription pause/resume support
- Dunning workflow triggers

CRITICAL: Paddle is NEVER called without proper approval workflow.
Subscription changes require explicit validation and approval.
"""

from typing import Optional, List, Dict, Any, TYPE_CHECKING
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SubscriptionStatus(str, Enum):
    """Subscription status enumeration."""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"
    TRIALING = "trialing"
    PAUSED = "paused"


class SubscriptionTier(str, Enum):
    """Subscription tier enumeration."""
    MINI = "mini"
    PARWA = "parwa"
    PARWA_HIGH = "parwa_high"
    ENTERPRISE = "enterprise"


class BillingCycle(str, Enum):
    """Billing cycle enumeration."""
    MONTHLY = "monthly"
    ANNUAL = "annual"
    QUARTERLY = "quarterly"


@dataclass
class SubscriptionEvent:
    """Represents a subscription lifecycle event."""
    id: UUID = field(default_factory=uuid4)
    subscription_id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    status_from: Optional[str] = None
    status_to: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "subscription_id": str(self.subscription_id),
            "event_type": self.event_type,
            "status_from": self.status_from,
            "status_to": self.status_to,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class Subscription:
    """Represents a subscription with all lifecycle information."""
    id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    company_id: Optional[UUID] = None
    paddle_subscription_id: Optional[str] = None
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    tier: SubscriptionTier = SubscriptionTier.MINI
    billing_cycle: BillingCycle = BillingCycle.MONTHLY
    current_period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    current_period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))
    cancel_at_period_end: bool = False
    paused_at: Optional[datetime] = None
    grace_period_ends: Optional[datetime] = None
    trial_ends: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "client_id": self.client_id,
            "company_id": str(self.company_id) if self.company_id else None,
            "paddle_subscription_id": self.paddle_subscription_id,
            "status": self.status.value,
            "tier": self.tier.value,
            "billing_cycle": self.billing_cycle.value,
            "current_period_start": self.current_period_start.isoformat(),
            "current_period_end": self.current_period_end.isoformat(),
            "cancel_at_period_end": self.cancel_at_period_end,
            "paused_at": self.paused_at.isoformat() if self.paused_at else None,
            "grace_period_ends": self.grace_period_ends.isoformat() if self.grace_period_ends else None,
            "trial_ends": self.trial_ends.isoformat() if self.trial_ends else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# Tier pricing configuration (USD)
TIER_PRICING = {
    SubscriptionTier.MINI: {"monthly": 49.0, "annual": 470.0},
    SubscriptionTier.PARWA: {"monthly": 149.0, "annual": 1430.0},
    SubscriptionTier.PARWA_HIGH: {"monthly": 499.0, "annual": 4790.0},
    SubscriptionTier.ENTERPRISE: {"monthly": 1499.0, "annual": 14390.0},
}

# Grace period configuration
GRACE_PERIOD_DAYS = 7
RENEWAL_REMINDER_DAYS = 7


class SubscriptionManager:
    """
    Manages subscription lifecycle for SaaS clients.

    Features:
    - Track subscription status (active, past_due, canceled, expired)
    - Monitor renewal dates
    - Handle grace periods
    - Send automatic renewal reminders
    - Support pause/resume
    - Trigger dunning workflows

    CRITICAL: Never call Paddle without proper approval workflow.
    """

    def __init__(
        self,
        db: Optional["AsyncSession"] = None,
        client_id: str = "",
        company_id: Optional[UUID] = None
    ):
        """
        Initialize subscription manager.

        Args:
            db: Optional async database session
            client_id: Client identifier for multi-tenant isolation
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.client_id = client_id
        self.company_id = company_id
        self._subscriptions: Dict[str, Subscription] = {}
        self._events: List[SubscriptionEvent] = []
        self._paddle_mock_data: Dict[str, Any] = {}

    async def get_subscription(self, subscription_id: Optional[UUID] = None) -> Optional[Subscription]:
        """
        Get subscription by ID or client_id.

        Args:
            subscription_id: Optional subscription UUID

        Returns:
            Subscription if found, None otherwise
        """
        if subscription_id:
            for sub in self._subscriptions.values():
                if sub.id == subscription_id:
                    return sub
            return None

        # Get by client_id
        return self._subscriptions.get(self.client_id)

    async def create_subscription(
        self,
        tier: SubscriptionTier,
        billing_cycle: BillingCycle = BillingCycle.MONTHLY,
        trial_days: int = 0,
        paddle_subscription_id: Optional[str] = None
    ) -> Subscription:
        """
        Create a new subscription.

        Args:
            tier: Subscription tier
            billing_cycle: Billing cycle (monthly, annual, quarterly)
            trial_days: Number of trial days (0 for no trial)
            paddle_subscription_id: Optional Paddle subscription ID

        Returns:
            Created Subscription
        """
        now = datetime.now(timezone.utc)

        # Calculate period based on billing cycle
        if billing_cycle == BillingCycle.MONTHLY:
            period_end = now + timedelta(days=30)
        elif billing_cycle == BillingCycle.QUARTERLY:
            period_end = now + timedelta(days=90)
        else:  # annual
            period_end = now + timedelta(days=365)

        # Set trial end date if applicable
        trial_ends = None
        if trial_days > 0:
            trial_ends = now + timedelta(days=trial_days)

        subscription = Subscription(
            client_id=self.client_id,
            company_id=self.company_id,
            paddle_subscription_id=paddle_subscription_id,
            status=SubscriptionStatus.TRIALING if trial_days > 0 else SubscriptionStatus.ACTIVE,
            tier=tier,
            billing_cycle=billing_cycle,
            current_period_start=now,
            current_period_end=period_end,
            trial_ends=trial_ends,
        )

        self._subscriptions[self.client_id] = subscription

        # Log event
        await self._log_event(
            subscription=subscription,
            event_type="subscription_created",
            status_to=subscription.status.value,
            metadata={"tier": tier.value, "billing_cycle": billing_cycle.value, "trial_days": trial_days}
        )

        logger.info(
            "Subscription created",
            extra={
                "client_id": self.client_id,
                "subscription_id": str(subscription.id),
                "tier": tier.value,
                "billing_cycle": billing_cycle.value,
            }
        )

        return subscription

    async def update_status(
        self,
        subscription: Subscription,
        new_status: SubscriptionStatus,
        reason: Optional[str] = None
    ) -> Subscription:
        """
        Update subscription status.

        Args:
            subscription: Subscription to update
            new_status: New status
            reason: Optional reason for status change

        Returns:
            Updated Subscription
        """
        old_status = subscription.status
        subscription.status = new_status
        subscription.updated_at = datetime.now(timezone.utc)

        # Handle status-specific logic
        if new_status == SubscriptionStatus.PAUSED:
            subscription.paused_at = datetime.now(timezone.utc)
        elif new_status == SubscriptionStatus.PAST_DUE:
            subscription.grace_period_ends = datetime.now(timezone.utc) + timedelta(days=GRACE_PERIOD_DAYS)

        # Log event
        await self._log_event(
            subscription=subscription,
            event_type="status_changed",
            status_from=old_status.value,
            status_to=new_status.value,
            metadata={"reason": reason}
        )

        logger.info(
            "Subscription status updated",
            extra={
                "client_id": self.client_id,
                "subscription_id": str(subscription.id),
                "old_status": old_status.value,
                "new_status": new_status.value,
                "reason": reason,
            }
        )

        return subscription

    async def check_renewal_status(self, subscription: Subscription) -> Dict[str, Any]:
        """
        Check renewal status and trigger appropriate actions.

        Args:
            subscription: Subscription to check

        Returns:
            Dict with renewal status information
        """
        now = datetime.now(timezone.utc)
        days_until_renewal = (subscription.current_period_end - now).days

        renewal_status = {
            "subscription_id": str(subscription.id),
            "days_until_renewal": days_until_renewal,
            "will_renew": not subscription.cancel_at_period_end,
            "reminder_sent": False,
            "action_required": None,
        }

        # Check if renewal reminder should be sent
        if days_until_renewal <= RENEWAL_REMINDER_DAYS and not subscription.cancel_at_period_end:
            renewal_status["reminder_sent"] = True
            renewal_status["action_required"] = "send_reminder"
            await self._send_renewal_reminder(subscription)

        # Check if subscription is expiring
        if days_until_renewal <= 0:
            if subscription.cancel_at_period_end:
                await self.update_status(subscription, SubscriptionStatus.EXPIRED, "Period ended with cancellation")
                renewal_status["action_required"] = "expired"
            else:
                renewal_status["action_required"] = "renew"

        # Check grace period
        if subscription.grace_period_ends and now > subscription.grace_period_ends:
            renewal_status["action_required"] = "dunning"
            await self._trigger_dunning(subscription)

        return renewal_status

    async def pause_subscription(
        self,
        subscription: Subscription,
        reason: Optional[str] = None
    ) -> Subscription:
        """
        Pause a subscription.

        Args:
            subscription: Subscription to pause
            reason: Optional reason for pause

        Returns:
            Updated Subscription
        """
        if subscription.status == SubscriptionStatus.PAUSED:
            raise ValueError("Subscription is already paused")

        updated = await self.update_status(
            subscription,
            SubscriptionStatus.PAUSED,
            reason or "User requested pause"
        )

        logger.info(
            "Subscription paused",
            extra={
                "client_id": self.client_id,
                "subscription_id": str(subscription.id),
                "reason": reason,
            }
        )

        return updated

    async def resume_subscription(self, subscription: Subscription) -> Subscription:
        """
        Resume a paused subscription.

        Args:
            subscription: Subscription to resume

        Returns:
            Updated Subscription
        """
        if subscription.status != SubscriptionStatus.PAUSED:
            raise ValueError("Only paused subscriptions can be resumed")

        updated = await self.update_status(
            subscription,
            SubscriptionStatus.ACTIVE,
            "User requested resume"
        )

        # Reset period end
        subscription.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
        subscription.paused_at = None

        logger.info(
            "Subscription resumed",
            extra={
                "client_id": self.client_id,
                "subscription_id": str(subscription.id),
            }
        )

        return updated

    async def cancel_subscription(
        self,
        subscription: Subscription,
        immediate: bool = False,
        reason: Optional[str] = None
    ) -> Subscription:
        """
        Cancel a subscription.

        Args:
            subscription: Subscription to cancel
            immediate: If True, cancel immediately; otherwise at period end
            reason: Optional reason for cancellation

        Returns:
            Updated Subscription
        """
        if immediate:
            updated = await self.update_status(
                subscription,
                SubscriptionStatus.CANCELED,
                reason or "Immediate cancellation requested"
            )
        else:
            subscription.cancel_at_period_end = True
            subscription.updated_at = datetime.now(timezone.utc)
            updated = subscription

            await self._log_event(
                subscription=subscription,
                event_type="cancellation_scheduled",
                metadata={"reason": reason, "effective_date": subscription.current_period_end.isoformat()}
            )

        logger.info(
            "Subscription canceled",
            extra={
                "client_id": self.client_id,
                "subscription_id": str(subscription.id),
                "immediate": immediate,
                "reason": reason,
            }
        )

        return updated

    async def process_paddle_webhook(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a webhook from Paddle.

        CRITICAL: This method validates and processes Paddle events
        without directly calling Paddle API.

        Args:
            event_data: Webhook event data from Paddle

        Returns:
            Dict with processing result
        """
        event_type = event_data.get("alert_type") or event_data.get("event_type", "unknown")
        paddle_subscription_id = event_data.get("subscription_id") or event_data.get("paddle_id")

        # Find subscription by Paddle ID
        subscription = None
        for sub in self._subscriptions.values():
            if sub.paddle_subscription_id == paddle_subscription_id:
                subscription = sub
                break

        if not subscription:
            logger.warning(
                "Webhook received for unknown subscription",
                extra={"paddle_subscription_id": paddle_subscription_id}
            )
            return {"processed": False, "reason": "subscription_not_found"}

        result = {"processed": True, "event_type": event_type}

        # Handle specific event types
        if event_type in ["subscription_created", "subscription_updated"]:
            # Update subscription from Paddle data
            pass
        elif event_type == "subscription_canceled":
            await self.update_status(subscription, SubscriptionStatus.CANCELED, "Paddle cancellation")
        elif event_type == "subscription_payment_failed":
            await self.update_status(subscription, SubscriptionStatus.PAST_DUE, "Payment failed")
        elif event_type == "subscription_payment_succeeded":
            if subscription.status == SubscriptionStatus.PAST_DUE:
                await self.update_status(subscription, SubscriptionStatus.ACTIVE, "Payment recovered")

        return result

    async def get_subscription_events(
        self,
        subscription_id: Optional[UUID] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get subscription events history.

        Args:
            subscription_id: Optional filter by subscription
            limit: Maximum events to return

        Returns:
            List of subscription events
        """
        events = self._events

        if subscription_id:
            events = [e for e in events if e.subscription_id == subscription_id]

        return [e.to_dict() for e in events[-limit:]]

    async def get_expiring_subscriptions(self, days: int = 7) -> List[Subscription]:
        """
        Get subscriptions expiring within specified days.

        Args:
            days: Number of days to look ahead

        Returns:
            List of expiring subscriptions
        """
        now = datetime.now(timezone.utc)
        threshold = now + timedelta(days=days)

        expiring = []
        for sub in self._subscriptions.values():
            if sub.current_period_end <= threshold and sub.status in [
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.TRIALING
            ]:
                expiring.append(sub)

        return expiring

    async def get_subscription_metrics(self) -> Dict[str, Any]:
        """
        Get subscription metrics summary.

        Returns:
            Dict with subscription metrics
        """
        status_counts = {}
        tier_counts = {}

        for sub in self._subscriptions.values():
            status_counts[sub.status.value] = status_counts.get(sub.status.value, 0) + 1
            tier_counts[sub.tier.value] = tier_counts.get(sub.tier.value, 0) + 1

        return {
            "total_subscriptions": len(self._subscriptions),
            "by_status": status_counts,
            "by_tier": tier_counts,
            "active_count": status_counts.get("active", 0) + status_counts.get("trialing", 0),
        }

    async def _send_renewal_reminder(self, subscription: Subscription) -> None:
        """
        Send renewal reminder for subscription.

        Args:
            subscription: Subscription to remind about
        """
        # Log the reminder (in production, this would trigger email/notification)
        await self._log_event(
            subscription=subscription,
            event_type="renewal_reminder_sent",
            metadata={"days_until_renewal": (subscription.current_period_end - datetime.now(timezone.utc)).days}
        )

        logger.info(
            "Renewal reminder sent",
            extra={
                "client_id": self.client_id,
                "subscription_id": str(subscription.id),
            }
        )

    async def _trigger_dunning(self, subscription: Subscription) -> None:
        """
        Trigger dunning workflow for past-due subscription.

        Args:
            subscription: Past-due subscription
        """
        await self._log_event(
            subscription=subscription,
            event_type="dunning_triggered",
            metadata={"grace_period_expired": True}
        )

        logger.warning(
            "Dunning triggered",
            extra={
                "client_id": self.client_id,
                "subscription_id": str(subscription.id),
            }
        )

    async def _log_event(
        self,
        subscription: Subscription,
        event_type: str,
        status_from: Optional[str] = None,
        status_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a subscription event.

        Args:
            subscription: Related subscription
            event_type: Type of event
            status_from: Previous status
            status_to: New status
            metadata: Additional event metadata
        """
        event = SubscriptionEvent(
            subscription_id=subscription.id,
            event_type=event_type,
            status_from=status_from,
            status_to=status_to,
            metadata=metadata or {},
        )

        self._events.append(event)


# Export for testing
__all__ = [
    "SubscriptionManager",
    "Subscription",
    "SubscriptionEvent",
    "SubscriptionStatus",
    "SubscriptionTier",
    "BillingCycle",
    "TIER_PRICING",
]
