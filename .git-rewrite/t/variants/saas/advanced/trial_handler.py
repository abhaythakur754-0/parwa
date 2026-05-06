"""
Trial Handler for SaaS Advanced Module.

Provides trial management including:
- Trial period management
- Trial expiration alerts
- Trial-to-paid conversion workflow
- Trial extension logic
- Feature limitations during trial
- Trial analytics tracking
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

from variants.saas.advanced.plan_manager import PlanTier, PLANS

logger = logging.getLogger(__name__)


class TrialStatus(str, Enum):
    """Trial status enumeration."""
    ACTIVE = "active"
    EXPIRED = "expired"
    CONVERTED = "converted"
    EXTENDED = "extended"
    CANCELED = "canceled"


class AlertType(str, Enum):
    """Trial alert type enumeration."""
    STARTED = "started"
    HALFWAY = "halfway"
    ENDING_SOON = "ending_soon"
    EXPIRED = "expired"
    CONVERTED = "converted"


@dataclass
class Trial:
    """Represents a subscription trial."""
    id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    subscription_id: Optional[UUID] = None
    tier: str = "mini"
    status: TrialStatus = TrialStatus.ACTIVE
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ends_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=14))
    extended_days: int = 0
    feature_usage: Dict[str, int] = field(default_factory=dict)
    conversion_attempts: int = 0
    converted_at: Optional[datetime] = None
    alerts_sent: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "client_id": self.client_id,
            "subscription_id": str(self.subscription_id) if self.subscription_id else None,
            "tier": self.tier,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "ends_at": self.ends_at.isoformat(),
            "extended_days": self.extended_days,
            "days_remaining": max(0, (self.ends_at - datetime.now(timezone.utc)).days),
            "feature_usage": self.feature_usage,
            "conversion_attempts": self.conversion_attempts,
            "converted_at": self.converted_at.isoformat() if self.converted_at else None,
            "alerts_sent": self.alerts_sent,
        }


# Default trial configuration
DEFAULT_TRIAL_DAYS = 14
MAX_EXTENSION_DAYS = 7
TRIAL_FEATURE_LIMITS = {
    "mini": {
        "tickets": 50,
        "ai_interactions": 100,
        "voice_minutes": 20,
        "team_members": 2,
    },
    "parwa": {
        "tickets": 200,
        "ai_interactions": 500,
        "voice_minutes": 50,
        "team_members": 5,
    },
    "parwa_high": {
        "tickets": 500,
        "ai_interactions": 1000,
        "voice_minutes": 100,
        "team_members": 10,
    },
}


class TrialHandler:
    """
    Handles subscription trial management.

    Features:
    - Trial period management
    - Expiration alerts
    - Trial-to-paid conversion
    - Trial extensions
    - Feature limitations
    - Analytics tracking
    """

    def __init__(self, client_id: str = ""):
        """
        Initialize trial handler.

        Args:
            client_id: Client identifier for multi-tenant isolation
        """
        self.client_id = client_id
        self._trials: Dict[str, Trial] = {}
        self._trial_analytics: Dict[str, Dict[str, Any]] = {}

    async def start_trial(
        self,
        tier: str = "mini",
        days: int = DEFAULT_TRIAL_DAYS,
        subscription_id: Optional[UUID] = None
    ) -> Trial:
        """
        Start a new trial period.

        Args:
            tier: Plan tier to trial
            days: Trial duration in days
            subscription_id: Optional associated subscription

        Returns:
            Created Trial
        """
        now = datetime.now(timezone.utc)

        trial = Trial(
            client_id=self.client_id,
            subscription_id=subscription_id,
            tier=tier,
            status=TrialStatus.ACTIVE,
            started_at=now,
            ends_at=now + timedelta(days=days),
            feature_usage={},
        )

        self._trials[self.client_id] = trial

        # Initialize analytics
        self._trial_analytics[self.client_id] = {
            "tier": tier,
            "started_at": now.isoformat(),
            "daily_active_days": 0,
            "features_used": [],
            "conversion_funnel": ["trial_started"],
        }

        # Send started alert
        await self._send_alert(trial, AlertType.STARTED)

        logger.info(
            "Trial started",
            extra={
                "client_id": self.client_id,
                "trial_id": str(trial.id),
                "tier": tier,
                "days": days,
            }
        )

        return trial

    async def get_trial(self) -> Optional[Trial]:
        """
        Get current trial for client.

        Returns:
            Trial if exists, None otherwise
        """
        return self._trials.get(self.client_id)

    async def check_trial_status(self) -> Dict[str, Any]:
        """
        Check trial status and trigger alerts if needed.

        Returns:
            Dict with trial status details
        """
        trial = await self.get_trial()
        if not trial:
            return {"has_trial": False}

        now = datetime.now(timezone.utc)
        days_remaining = (trial.ends_at - now).days

        status = {
            "has_trial": True,
            "trial_id": str(trial.id),
            "status": trial.status.value,
            "tier": trial.tier,
            "days_remaining": max(0, days_remaining),
            "is_expired": now > trial.ends_at,
            "feature_usage": trial.feature_usage,
            "limits": TRIAL_FEATURE_LIMITS.get(trial.tier, {}),
        }

        # Check if expired
        if status["is_expired"] and trial.status == TrialStatus.ACTIVE:
            trial.status = TrialStatus.EXPIRED
            await self._send_alert(trial, AlertType.EXPIRED)
            status["status"] = TrialStatus.EXPIRED.value

        # Check for alerts
        elif trial.status == TrialStatus.ACTIVE:
            await self._check_and_send_alerts(trial, days_remaining)

        return status

    async def extend_trial(
        self,
        days: int,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extend trial period.

        Args:
            days: Number of days to extend
            reason: Optional reason for extension

        Returns:
            Dict with extension result
        """
        trial = await self.get_trial()
        if not trial:
            raise ValueError("No active trial to extend")

        if trial.status not in [TrialStatus.ACTIVE, TrialStatus.EXTENDED]:
            raise ValueError(f"Cannot extend trial in {trial.status.value} status")

        # Cap extension
        actual_extension = min(days, MAX_EXTENSION_DAYS)

        # Check total extension doesn't exceed max
        if trial.extended_days + actual_extension > MAX_EXTENSION_DAYS:
            actual_extension = MAX_EXTENSION_DAYS - trial.extended_days

        if actual_extension <= 0:
            return {
                "extended": False,
                "reason": "Maximum extension already applied",
            }

        # Extend trial
        trial.ends_at = trial.ends_at + timedelta(days=actual_extension)
        trial.extended_days += actual_extension
        trial.status = TrialStatus.EXTENDED

        logger.info(
            "Trial extended",
            extra={
                "client_id": self.client_id,
                "trial_id": str(trial.id),
                "days_extended": actual_extension,
                "reason": reason,
            }
        )

        return {
            "extended": True,
            "days_extended": actual_extension,
            "new_end_date": trial.ends_at.isoformat(),
            "total_extended_days": trial.extended_days,
        }

    async def convert_to_paid(
        self,
        tier: str,
        billing_frequency: str = "monthly"
    ) -> Dict[str, Any]:
        """
        Convert trial to paid subscription.

        Args:
            tier: Plan tier to subscribe to
            billing_frequency: Billing frequency

        Returns:
            Dict with conversion result
        """
        trial = await self.get_trial()
        if not trial:
            raise ValueError("No trial to convert")

        if trial.status not in [TrialStatus.ACTIVE, TrialStatus.EXTENDED]:
            raise ValueError(f"Cannot convert trial in {trial.status.value} status")

        # Update trial status
        trial.status = TrialStatus.CONVERTED
        trial.converted_at = datetime.now(timezone.utc)
        trial.conversion_attempts += 1

        # Send conversion alert
        await self._send_alert(trial, AlertType.CONVERTED)

        # Update analytics
        analytics = self._trial_analytics.get(self.client_id, {})
        funnel = analytics.get("conversion_funnel", [])
        funnel.append("converted")
        analytics["conversion_funnel"] = funnel
        analytics["converted_at"] = trial.converted_at.isoformat()
        analytics["converted_tier"] = tier

        logger.info(
            "Trial converted to paid",
            extra={
                "client_id": self.client_id,
                "trial_id": str(trial.id),
                "tier": tier,
                "billing_frequency": billing_frequency,
            }
        )

        return {
            "converted": True,
            "trial_id": str(trial.id),
            "tier": tier,
            "billing_frequency": billing_frequency,
            "converted_at": trial.converted_at.isoformat(),
        }

    async def cancel_trial(self, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel an active trial.

        Args:
            reason: Optional cancellation reason

        Returns:
            Dict with cancellation result
        """
        trial = await self.get_trial()
        if not trial:
            raise ValueError("No trial to cancel")

        if trial.status not in [TrialStatus.ACTIVE, TrialStatus.EXTENDED]:
            raise ValueError(f"Cannot cancel trial in {trial.status.value} status")

        trial.status = TrialStatus.CANCELED

        logger.info(
            "Trial canceled",
            extra={
                "client_id": self.client_id,
                "trial_id": str(trial.id),
                "reason": reason,
            }
        )

        return {
            "canceled": True,
            "trial_id": str(trial.id),
            "reason": reason,
        }

    async def track_feature_usage(
        self,
        feature: str,
        amount: int = 1
    ) -> Dict[str, Any]:
        """
        Track feature usage during trial.

        Args:
            feature: Feature name
            amount: Usage amount

        Returns:
            Dict with usage status
        """
        trial = await self.get_trial()
        if not trial or trial.status not in [TrialStatus.ACTIVE, TrialStatus.EXTENDED]:
            return {"tracked": False, "reason": "No active trial"}

        # Update usage
        current = trial.feature_usage.get(feature, 0)
        trial.feature_usage[feature] = current + amount

        # Check limits
        limits = TRIAL_FEATURE_LIMITS.get(trial.tier, {})
        limit = limits.get(feature)
        usage = trial.feature_usage[feature]

        # Update analytics
        analytics = self._trial_analytics.get(self.client_id, {})
        if feature not in analytics.get("features_used", []):
            features = analytics.get("features_used", [])
            features.append(feature)
            analytics["features_used"] = features

        return {
            "tracked": True,
            "feature": feature,
            "current_usage": usage,
            "limit": limit,
            "percentage": round((usage / limit * 100), 2) if limit else 0,
            "at_limit": limit is not None and usage >= limit,
        }

    async def check_feature_limit(self, feature: str) -> Dict[str, Any]:
        """
        Check if a feature is within trial limits.

        Args:
            feature: Feature to check

        Returns:
            Dict with limit status
        """
        trial = await self.get_trial()
        if not trial or trial.status not in [TrialStatus.ACTIVE, TrialStatus.EXTENDED]:
            return {"allowed": False, "reason": "No active trial"}

        limits = TRIAL_FEATURE_LIMITS.get(trial.tier, {})
        limit = limits.get(feature)
        usage = trial.feature_usage.get(feature, 0)

        if limit is None:
            return {"allowed": True, "unlimited": True}

        return {
            "allowed": usage < limit,
            "current_usage": usage,
            "limit": limit,
            "remaining": max(0, limit - usage),
            "percentage": round((usage / limit * 100), 2),
        }

    async def get_trial_analytics(self) -> Dict[str, Any]:
        """
        Get analytics for the trial.

        Returns:
            Dict with trial analytics
        """
        trial = await self.get_trial()
        if not trial:
            return {"has_trial": False}

        analytics = self._trial_analytics.get(self.client_id, {})

        now = datetime.now(timezone.utc)
        trial_duration = (trial.ends_at - trial.started_at).days
        days_elapsed = (now - trial.started_at).days
        days_remaining = max(0, (trial.ends_at - now).days)

        # Calculate engagement score
        features_used_count = len(trial.feature_usage)
        total_features = len(TRIAL_FEATURE_LIMITS.get(trial.tier, {}))
        feature_adoption = features_used_count / total_features if total_features > 0 else 0

        # Calculate usage percentage across all features
        limits = TRIAL_FEATURE_LIMITS.get(trial.tier, {})
        total_usage_pct = 0
        for feature, limit in limits.items():
            usage = trial.feature_usage.get(feature, 0)
            if limit > 0:
                total_usage_pct += (usage / limit)

        avg_usage_pct = total_usage_pct / len(limits) if limits else 0

        return {
            "has_trial": True,
            "trial_id": str(trial.id),
            "tier": trial.tier,
            "status": trial.status.value,
            "duration": {
                "total_days": trial_duration,
                "days_elapsed": days_elapsed,
                "days_remaining": days_remaining,
                "percentage_complete": round((days_elapsed / trial_duration * 100), 2) if trial_duration > 0 else 0,
            },
            "feature_usage": trial.feature_usage,
            "limits": limits,
            "engagement": {
                "features_used": features_used_count,
                "total_features": total_features,
                "feature_adoption": round(feature_adoption, 2),
                "average_usage_pct": round(avg_usage_pct * 100, 2),
            },
            "conversion_funnel": analytics.get("conversion_funnel", []),
            "extended": trial.extended_days > 0,
            "extended_days": trial.extended_days,
        }

    async def get_conversion_suggestions(self) -> Dict[str, Any]:
        """
        Get personalized conversion suggestions.

        Returns:
            Dict with conversion suggestions
        """
        trial = await self.get_trial()
        if not trial:
            return {"suggestions": [], "reason": "No active trial"}

        analytics = await self.get_trial_analytics()
        suggestions = []

        # Based on usage patterns
        engagement = analytics.get("engagement", {})
        feature_adoption = engagement.get("feature_adoption", 0)
        avg_usage = engagement.get("average_usage_pct", 0)

        # High engagement - recommend upgrade
        if feature_adoption > 0.7 and avg_usage > 50:
            suggestions.append({
                "type": "upgrade",
                "tier": "parwa" if trial.tier == "mini" else "parwa_high",
                "reason": "Your usage suggests you'd benefit from a higher tier",
                "confidence": "high",
            })

        # Approaching limits
        for feature, usage in trial.feature_usage.items():
            limits = TRIAL_FEATURE_LIMITS.get(trial.tier, {})
            limit = limits.get(feature, 0)
            if limit > 0 and usage >= limit * 0.8:
                suggestions.append({
                    "type": "limit_warning",
                    "feature": feature,
                    "reason": f"You've used {round(usage/limit*100)}% of your {feature} limit",
                    "upgrade_benefit": "Higher limits with paid plan",
                })

        # Time-based suggestion
        days_remaining = analytics.get("duration", {}).get("days_remaining", 0)
        if days_remaining <= 3:
            suggestions.append({
                "type": "urgent",
                "reason": f"Only {days_remaining} days left in trial",
                "action": "Convert now to maintain access",
            })

        # Discount incentive
        if days_remaining > 7 and avg_usage > 30:
            suggestions.append({
                "type": "discount",
                "offer": "15% off first month",
                "reason": "Early conversion bonus",
                "code": "EARLY15",
            })

        return {
            "trial_id": str(trial.id),
            "suggestions": suggestions,
            "engagement_score": round((feature_adoption + avg_usage/100) / 2 * 100, 2),
        }

    async def _check_and_send_alerts(
        self,
        trial: Trial,
        days_remaining: int
    ) -> None:
        """Check and send appropriate alerts."""
        # Halfway alert
        if days_remaining <= 7 and days_remaining > 3 and "halfway" not in trial.alerts_sent:
            await self._send_alert(trial, AlertType.HALFWAY)
            trial.alerts_sent.append("halfway")

        # Ending soon alert
        if days_remaining <= 3 and days_remaining > 0 and "ending_soon" not in trial.alerts_sent:
            await self._send_alert(trial, AlertType.ENDING_SOON)
            trial.alerts_sent.append("ending_soon")

    async def _send_alert(self, trial: Trial, alert_type: AlertType) -> None:
        """Send a trial alert."""
        logger.info(
            "Trial alert sent",
            extra={
                "client_id": self.client_id,
                "trial_id": str(trial.id),
                "alert_type": alert_type.value,
            }
        )

        # Update analytics
        analytics = self._trial_analytics.get(self.client_id, {})
        funnel = analytics.get("conversion_funnel", [])
        funnel.append(f"alert_{alert_type.value}")
        analytics["conversion_funnel"] = funnel


# Export for testing
__all__ = [
    "TrialHandler",
    "Trial",
    "TrialStatus",
    "AlertType",
    "DEFAULT_TRIAL_DAYS",
    "MAX_EXTENSION_DAYS",
    "TRIAL_FEATURE_LIMITS",
]
