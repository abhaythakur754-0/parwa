"""
Risk Scorer for SaaS Advanced Module.

Provides risk scoring including:
- Multi-factor risk assessment
- Usage decline detection
- Login frequency tracking
- Feature adoption scoring
- Support sentiment analysis
- Payment failure tracking
- Composite risk score calculation
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RiskFactor(str, Enum):
    """Risk factor categories."""
    USAGE = "usage"
    ENGAGEMENT = "engagement"
    FINANCIAL = "financial"
    SUPPORT = "support"
    PRODUCT = "product"


class RiskWeight(str, Enum):
    """Risk weights for different factors."""
    CRITICAL = 3.0
    HIGH = 2.0
    MEDIUM = 1.0
    LOW = 0.5


@dataclass
class RiskScore:
    """Represents a risk score."""
    id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    score_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    overall_score: float = 0.0
    factor_scores: Dict[str, float] = field(default_factory=dict)
    risk_factors: List[str] = field(default_factory=list)
    protective_factors: List[str] = field(default_factory=list)
    trend: str = "stable"
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "client_id": self.client_id,
            "score_date": self.score_date.isoformat(),
            "overall_score": round(self.overall_score, 2),
            "factor_scores": self.factor_scores,
            "risk_factors": self.risk_factors,
            "protective_factors": self.protective_factors,
            "trend": self.trend,
            "last_updated": self.last_updated.isoformat(),
        }


# Factor configurations
USAGE_RISK_CONFIG = {
    "usage_decline_threshold": -0.20,  # 20% decline
    "usage_decline_weight": 2.0,
    "zero_usage_days_threshold": 7,
    "zero_usage_weight": 3.0,
}

ENGAGEMENT_RISK_CONFIG = {
    "low_login_threshold": 3,  # Logins per week
    "low_login_weight": 1.5,
    "feature_adoption_threshold": 0.3,  # 30% adoption
    "feature_adoption_weight": 1.0,
}

FINANCIAL_RISK_CONFIG = {
    "payment_failure_weight": 3.0,
    "overdue_days_threshold": 30,
    "overdue_weight": 2.5,
    "downgrade_request_weight": 2.0,
}

SUPPORT_RISK_CONFIG = {
    "high_ticket_threshold": 5,  # Tickets in 30 days
    "high_ticket_weight": 1.5,
    "negative_sentiment_threshold": 0.3,
    "negative_sentiment_weight": 2.0,
}


class RiskScorer:
    """
    Calculates risk scores for SaaS customers.

    Features:
    - Multi-factor risk assessment
    - Usage decline detection
    - Engagement tracking
    - Payment failure tracking
    - Composite scoring
    """

    def __init__(self, client_id: str = ""):
        """
        Initialize risk scorer.

        Args:
            client_id: Client identifier
        """
        self.client_id = client_id
        self._scores: Dict[str, RiskScore] = {}
        self._score_history: Dict[str, List[RiskScore]] = {}

    async def calculate_score(
        self,
        usage_data: Dict[str, Any],
        engagement_data: Dict[str, Any],
        financial_data: Dict[str, Any],
        support_data: Dict[str, Any]
    ) -> RiskScore:
        """
        Calculate comprehensive risk score.

        Args:
            usage_data: Usage metrics
            engagement_data: Engagement metrics
            financial_data: Financial metrics
            support_data: Support metrics

        Returns:
            RiskScore with all components
        """
        factor_scores = {}

        # Calculate usage risk
        usage_score, usage_factors = await self._calculate_usage_risk(usage_data)
        factor_scores["usage"] = usage_score

        # Calculate engagement risk
        engagement_score, engagement_factors = await self._calculate_engagement_risk(engagement_data)
        factor_scores["engagement"] = engagement_score

        # Calculate financial risk
        financial_score, financial_factors = await self._calculate_financial_risk(financial_data)
        factor_scores["financial"] = financial_score

        # Calculate support risk
        support_score, support_factors = await self._calculate_support_risk(support_data)
        factor_scores["support"] = support_score

        # Calculate overall score (weighted average)
        weights = {
            "usage": 0.30,
            "engagement": 0.25,
            "financial": 0.25,
            "support": 0.20,
        }

        overall = sum(
            factor_scores.get(k, 0) * w
            for k, w in weights.items()
        )

        # Identify risk and protective factors
        risk_factors = usage_factors["risk"] + engagement_factors["risk"] + \
                      financial_factors["risk"] + support_factors["risk"]

        protective_factors = usage_factors["protective"] + engagement_factors["protective"] + \
                            financial_factors["protective"] + support_factors["protective"]

        # Determine trend
        trend = await self._calculate_trend(overall)

        score = RiskScore(
            client_id=self.client_id,
            overall_score=round(overall, 2),
            factor_scores={k: round(v, 2) for k, v in factor_scores.items()},
            risk_factors=risk_factors,
            protective_factors=protective_factors,
            trend=trend,
        )

        self._scores[self.client_id] = score

        # Add to history
        if self.client_id not in self._score_history:
            self._score_history[self.client_id] = []
        self._score_history[self.client_id].append(score)

        logger.info(
            "Risk score calculated",
            extra={
                "client_id": self.client_id,
                "overall_score": overall,
                "trend": trend,
            }
        )

        return score

    async def detect_usage_decline(
        self,
        current_usage: float,
        previous_usage: float,
        threshold: float = 0.20
    ) -> Dict[str, Any]:
        """
        Detect usage decline.

        Args:
            current_usage: Current period usage
            previous_usage: Previous period usage
            threshold: Decline threshold

        Returns:
            Dict with decline analysis
        """
        if previous_usage == 0:
            return {
                "decline_detected": False,
                "decline_percentage": 0.0,
                "severity": "none",
            }

        decline = (previous_usage - current_usage) / previous_usage

        if decline <= 0:
            return {
                "decline_detected": False,
                "decline_percentage": abs(decline) * 100,
                "change_type": "increase",
                "severity": "none",
            }

        severity = "low"
        if decline > 0.50:
            severity = "critical"
        elif decline > 0.30:
            severity = "high"
        elif decline > threshold:
            severity = "medium"

        return {
            "decline_detected": decline > threshold,
            "decline_percentage": round(decline * 100, 2),
            "previous_usage": previous_usage,
            "current_usage": current_usage,
            "change_type": "decline",
            "severity": severity,
            "threshold": threshold * 100,
        }

    async def track_login_frequency(
        self,
        logins_7d: int,
        logins_30d: int
    ) -> Dict[str, Any]:
        """
        Track and analyze login frequency.

        Args:
            logins_7d: Logins in last 7 days
            logins_30d: Logins in last 30 days

        Returns:
            Dict with login analysis
        """
        weekly_avg = logins_7d
        daily_avg_30d = logins_30d / 30

        # Determine engagement level
        if weekly_avg >= 5:
            level = "high"
        elif weekly_avg >= 3:
            level = "moderate"
        elif weekly_avg >= 1:
            level = "low"
        else:
            level = "inactive"

        # Calculate trend
        expected_weekly = daily_avg_30d * 7
        if expected_weekly > 0:
            trend_pct = (weekly_avg - expected_weekly) / expected_weekly * 100
        else:
            trend_pct = 0

        return {
            "logins_7d": logins_7d,
            "logins_30d": logins_30d,
            "daily_average": round(daily_avg_30d, 2),
            "weekly_average": weekly_avg,
            "engagement_level": level,
            "trend_percentage": round(trend_pct, 2),
            "trend_direction": "up" if trend_pct > 10 else "down" if trend_pct < -10 else "stable",
        }

    async def score_feature_adoption(
        self,
        available_features: int,
        used_features: int,
        feature_depth: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Score feature adoption.

        Args:
            available_features: Total available features
            used_features: Features used at least once
            feature_depth: Usage depth per feature

        Returns:
            Dict with adoption analysis
        """
        if available_features == 0:
            adoption_rate = 1.0
        else:
            adoption_rate = used_features / available_features

        # Calculate depth score (how deeply features are used)
        depth_scores = []
        for feature, count in feature_depth.items():
            if count > 10:
                depth_scores.append(1.0)  # Heavy user
            elif count > 5:
                depth_scores.append(0.7)  # Moderate user
            elif count > 1:
                depth_scores.append(0.4)  # Light user
            else:
                depth_scores.append(0.1)  # Trial user

        avg_depth = sum(depth_scores) / len(depth_scores) if depth_scores else 0

        # Combined adoption score
        combined_score = (adoption_rate * 0.6) + (avg_depth * 0.4)

        return {
            "available_features": available_features,
            "used_features": used_features,
            "adoption_rate": round(adoption_rate, 2),
            "depth_score": round(avg_depth, 2),
            "combined_score": round(combined_score, 2),
            "level": "high" if combined_score > 0.7 else "moderate" if combined_score > 0.4 else "low",
        }

    async def analyze_payment_failures(
        self,
        failures_90d: int,
        last_failure_days: int,
        payment_method_age: int
    ) -> Dict[str, Any]:
        """
        Analyze payment failures.

        Args:
            failures_90d: Payment failures in 90 days
            last_failure_days: Days since last failure
            payment_method_age: Days since payment method added

        Returns:
            Dict with payment analysis
        """
        risk_level = "low"
        risk_factors = []

        if failures_90d >= 3:
            risk_level = "critical"
            risk_factors.append("multiple_recent_failures")
        elif failures_90d >= 2:
            risk_level = "high"
            risk_factors.append("recurring_failures")
        elif failures_90d >= 1:
            risk_level = "medium"
            risk_factors.append("recent_failure")

        # Recent failure increases risk
        if last_failure_days <= 7 and failures_90d > 0:
            risk_factors.append("very_recent_failure")

        # Old payment method is protective
        if payment_method_age > 365:
            risk_factors.append("stable_payment_method")

        return {
            "failures_90d": failures_90d,
            "last_failure_days": last_failure_days,
            "payment_method_age": payment_method_age,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
        }

    async def get_score(self, client_id: Optional[str] = None) -> Optional[RiskScore]:
        """
        Get cached risk score.

        Args:
            client_id: Optional client ID override

        Returns:
            RiskScore if exists
        """
        key = client_id or self.client_id
        return self._scores.get(key)

    async def get_score_history(
        self,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get score history for trend analysis.

        Args:
            limit: Maximum history items

        Returns:
            List of historical scores
        """
        history = self._score_history.get(self.client_id, [])
        return [s.to_dict() for s in history[-limit:]]

    async def _calculate_usage_risk(
        self,
        usage_data: Dict[str, Any]
    ) -> tuple:
        """Calculate usage risk score and factors."""
        score = 0.0
        risk_factors = []
        protective_factors = []

        # Check usage decline
        current = usage_data.get("current_usage", 0)
        previous = usage_data.get("previous_usage", 0)

        decline = await self.detect_usage_decline(current, previous)
        if decline["decline_detected"]:
            score += decline["decline_percentage"] * USAGE_RISK_CONFIG["usage_decline_weight"] / 100
            risk_factors.append(f"usage_decline_{decline['severity']}")

        # Check zero usage
        last_usage_days = usage_data.get("last_usage_days", 0)
        if last_usage_days > USAGE_RISK_CONFIG["zero_usage_days_threshold"]:
            score += USAGE_RISK_CONFIG["zero_usage_weight"]
            risk_factors.append("extended_inactive")

        # Positive indicators
        if decline.get("change_type") == "increase":
            protective_factors.append("usage_growing")

        return min(score, 10), {"risk": risk_factors, "protective": protective_factors}

    async def _calculate_engagement_risk(
        self,
        engagement_data: Dict[str, Any]
    ) -> tuple:
        """Calculate engagement risk score and factors."""
        score = 0.0
        risk_factors = []
        protective_factors = []

        # Login frequency
        logins_7d = engagement_data.get("logins_7d", 0)
        if logins_7d < ENGAGEMENT_RISK_CONFIG["low_login_threshold"]:
            score += (ENGAGEMENT_RISK_CONFIG["low_login_threshold"] - logins_7d) * \
                    ENGAGEMENT_RISK_CONFIG["low_login_weight"]
            risk_factors.append("low_login_frequency")
        else:
            protective_factors.append("active_login_pattern")

        # Feature adoption
        adoption = engagement_data.get("feature_adoption", 0)
        if adoption < ENGAGEMENT_RISK_CONFIG["feature_adoption_threshold"]:
            score += (1 - adoption) * ENGAGEMENT_RISK_CONFIG["feature_adoption_weight"]
            risk_factors.append("low_feature_adoption")
        else:
            protective_factors.append("good_feature_adoption")

        return min(score, 10), {"risk": risk_factors, "protective": protective_factors}

    async def _calculate_financial_risk(
        self,
        financial_data: Dict[str, Any]
    ) -> tuple:
        """Calculate financial risk score and factors."""
        score = 0.0
        risk_factors = []
        protective_factors = []

        # Payment failures
        failures = financial_data.get("payment_failures_90d", 0)
        if failures > 0:
            score += failures * FINANCIAL_RISK_CONFIG["payment_failure_weight"]
            risk_factors.append(f"payment_failures_{failures}")

        # Overdue days
        overdue = financial_data.get("overdue_days", 0)
        if overdue > FINANCIAL_RISK_CONFIG["overdue_days_threshold"]:
            score += (overdue / 30) * FINANCIAL_RISK_CONFIG["overdue_weight"]
            risk_factors.append("payment_overdue")

        # Downgrade requests
        downgrades = financial_data.get("downgrade_requests_90d", 0)
        if downgrades > 0:
            score += downgrades * FINANCIAL_RISK_CONFIG["downgrade_request_weight"]
            risk_factors.append("downgrade_intent")

        # Protective factors
        if failures == 0:
            protective_factors.append("no_payment_issues")

        if financial_data.get("is_annual", False):
            protective_factors.append("annual_commitment")

        return min(score, 10), {"risk": risk_factors, "protective": protective_factors}

    async def _calculate_support_risk(
        self,
        support_data: Dict[str, Any]
    ) -> tuple:
        """Calculate support risk score and factors."""
        score = 0.0
        risk_factors = []
        protective_factors = []

        # High ticket volume
        tickets_30d = support_data.get("tickets_30d", 0)
        if tickets_30d > SUPPORT_RISK_CONFIG["high_ticket_threshold"]:
            score += (tickets_30d - SUPPORT_RISK_CONFIG["high_ticket_threshold"]) * \
                    SUPPORT_RISK_CONFIG["high_ticket_weight"] / 5
            risk_factors.append("high_support_volume")

        # Negative sentiment
        sentiment = support_data.get("avg_sentiment", 0.5)
        if sentiment < SUPPORT_RISK_CONFIG["negative_sentiment_threshold"]:
            score += (1 - sentiment) * SUPPORT_RISK_CONFIG["negative_sentiment_weight"]
            risk_factors.append("negative_sentiment")
        else:
            protective_factors.append("positive_sentiment")

        # Escalations
        escalations = support_data.get("escalations_30d", 0)
        if escalations > 0:
            score += escalations
            risk_factors.append("support_escalations")

        return min(score, 10), {"risk": risk_factors, "protective": protective_factors}

    async def _calculate_trend(self, current_score: float) -> str:
        """Calculate score trend."""
        history = self._score_history.get(self.client_id, [])
        if len(history) < 2:
            return "stable"

        previous = history[-1].overall_score if history else current_score
        change = current_score - previous

        if change > 1:
            return "increasing"
        elif change < -1:
            return "decreasing"
        else:
            return "stable"


# Export for testing
__all__ = [
    "RiskScorer",
    "RiskScore",
    "RiskFactor",
    "RiskWeight",
    "USAGE_RISK_CONFIG",
    "ENGAGEMENT_RISK_CONFIG",
    "FINANCIAL_RISK_CONFIG",
    "SUPPORT_RISK_CONFIG",
]
