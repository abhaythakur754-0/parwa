"""
Health Score for SaaS Advanced Module.

Provides account health scoring including:
- Account health calculation
- Usage health component
- Engagement health component
- Financial health component
- Support health component
- Overall health dashboard
- Trend analysis
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class HealthLevel(str, Enum):
    """Health score levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class HealthComponent(str, Enum):
    """Health score components."""
    USAGE = "usage"
    ENGAGEMENT = "engagement"
    FINANCIAL = "financial"
    SUPPORT = "support"
    PRODUCT = "product"


@dataclass
class ComponentScore:
    """Represents a health component score."""
    component: HealthComponent = HealthComponent.USAGE
    score: float = 0.0
    weight: float = 0.0
    max_score: float = 100.0
    indicators: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "component": self.component.value,
            "score": round(self.score, 2),
            "weight": self.weight,
            "max_score": self.max_score,
            "weighted_score": round(self.score * self.weight, 2),
            "indicators": self.indicators,
            "warnings": self.warnings,
        }


@dataclass
class HealthScore:
    """Represents an overall health score."""
    id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    overall_score: float = 0.0
    health_level: HealthLevel = HealthLevel.GOOD
    component_scores: Dict[str, ComponentScore] = field(default_factory=dict)
    trend: str = "stable"
    trend_direction: str = "none"
    previous_score: Optional[float] = None
    score_change: Optional[float] = None
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "client_id": self.client_id,
            "calculated_at": self.calculated_at.isoformat(),
            "overall_score": round(self.overall_score, 2),
            "health_level": self.health_level.value,
            "component_scores": {
                k: v.to_dict() for k, v in self.component_scores.items()
            },
            "trend": self.trend,
            "trend_direction": self.trend_direction,
            "previous_score": self.previous_score,
            "score_change": self.score_change,
            "recommendations": self.recommendations,
        }


# Component weights
COMPONENT_WEIGHTS = {
    HealthComponent.USAGE: 0.30,
    HealthComponent.ENGAGEMENT: 0.25,
    HealthComponent.FINANCIAL: 0.25,
    HealthComponent.SUPPORT: 0.20,
}

# Health level thresholds
HEALTH_THRESHOLDS = {
    HealthLevel.EXCELLENT: 90,
    HealthLevel.GOOD: 75,
    HealthLevel.FAIR: 60,
    HealthLevel.POOR: 40,
    HealthLevel.CRITICAL: 0,
}


class HealthScoreCalculator:
    """
    Calculates account health scores for SaaS customers.

    Features:
    - Multi-component health scoring
    - Usage health analysis
    - Engagement health analysis
    - Financial health analysis
    - Support health analysis
    - Trend analysis
    """

    def __init__(self, client_id: str = ""):
        """
        Initialize health score calculator.

        Args:
            client_id: Client identifier
        """
        self.client_id = client_id
        self._scores: Dict[str, HealthScore] = {}
        self._score_history: Dict[str, List[HealthScore]] = {}

    async def calculate_health_score(
        self,
        usage_data: Dict[str, Any],
        engagement_data: Dict[str, Any],
        financial_data: Dict[str, Any],
        support_data: Dict[str, Any],
        product_data: Optional[Dict[str, Any]] = None
    ) -> HealthScore:
        """
        Calculate comprehensive health score.

        Args:
            usage_data: Usage metrics
            engagement_data: Engagement metrics
            financial_data: Financial metrics
            support_data: Support metrics
            product_data: Optional product metrics

        Returns:
            HealthScore with all components
        """
        component_scores = {}

        # Calculate each component
        usage_score = await self._calculate_usage_health(usage_data)
        component_scores[HealthComponent.USAGE.value] = usage_score

        engagement_score = await self._calculate_engagement_health(engagement_data)
        component_scores[HealthComponent.ENGAGEMENT.value] = engagement_score

        financial_score = await self._calculate_financial_health(financial_data)
        component_scores[HealthComponent.FINANCIAL.value] = financial_score

        support_score = await self._calculate_support_health(support_data)
        component_scores[HealthComponent.SUPPORT.value] = support_score

        # Calculate overall score
        overall = sum(
            cs.score * COMPONENT_WEIGHTS.get(HealthComponent(k), 0.25)
            for k, cs in component_scores.items()
        )

        # Determine health level
        health_level = self._determine_health_level(overall)

        # Calculate trend
        trend, direction = await self._calculate_trend(overall)

        # Get previous score
        previous = None
        change = None
        history = self._score_history.get(self.client_id, [])
        if history:
            previous = history[-1].overall_score
            change = overall - previous

        # Generate recommendations
        recommendations = await self._generate_recommendations(
            component_scores, health_level
        )

        score = HealthScore(
            client_id=self.client_id,
            overall_score=round(overall, 2),
            health_level=health_level,
            component_scores=component_scores,
            trend=trend,
            trend_direction=direction,
            previous_score=round(previous, 2) if previous else None,
            score_change=round(change, 2) if change else None,
            recommendations=recommendations,
        )

        self._scores[self.client_id] = score

        # Add to history
        if self.client_id not in self._score_history:
            self._score_history[self.client_id] = []
        self._score_history[self.client_id].append(score)

        logger.info(
            "Health score calculated",
            extra={
                "client_id": self.client_id,
                "overall_score": overall,
                "health_level": health_level.value,
            }
        )

        return score

    async def get_usage_health(self) -> ComponentScore:
        """
        Get usage health component.

        Returns:
            ComponentScore for usage
        """
        score = self._scores.get(self.client_id)
        if score:
            return score.component_scores.get(HealthComponent.USAGE.value)
        return None

    async def get_engagement_health(self) -> ComponentScore:
        """
        Get engagement health component.

        Returns:
            ComponentScore for engagement
        """
        score = self._scores.get(self.client_id)
        if score:
            return score.component_scores.get(HealthComponent.ENGAGEMENT.value)
        return None

    async def get_financial_health(self) -> ComponentScore:
        """
        Get financial health component.

        Returns:
            ComponentScore for financial
        """
        score = self._scores.get(self.client_id)
        if score:
            return score.component_scores.get(HealthComponent.FINANCIAL.value)
        return None

    async def get_support_health(self) -> ComponentScore:
        """
        Get support health component.

        Returns:
            ComponentScore for support
        """
        score = self._scores.get(self.client_id)
        if score:
            return score.component_scores.get(HealthComponent.SUPPORT.value)
        return None

    async def get_health_dashboard(self) -> Dict[str, Any]:
        """
        Get complete health dashboard.

        Returns:
            Dict with dashboard data
        """
        score = self._scores.get(self.client_id)
        if not score:
            return {"error": "No health score calculated"}

        history = self._score_history.get(self.client_id, [])

        # Calculate trends over time
        trends = {
            "7_day": self._calculate_period_trend(history, 7),
            "30_day": self._calculate_period_trend(history, 30),
            "90_day": self._calculate_period_trend(history, 90),
        }

        return {
            "current_score": score.to_dict(),
            "trends": trends,
            "history_count": len(history),
            "improvement_areas": [
                k for k, v in score.component_scores.items()
                if v.score < 70
            ],
            "strengths": [
                k for k, v in score.component_scores.items()
                if v.score >= 80
            ],
        }

    async def analyze_trends(self, days: int = 30) -> Dict[str, Any]:
        """
        Analyze health score trends.

        Args:
            days: Number of days to analyze

        Returns:
            Dict with trend analysis
        """
        history = self._score_history.get(self.client_id, [])
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        recent = [s for s in history if s.calculated_at >= cutoff]

        if len(recent) < 2:
            return {
                "analyzed": False,
                "reason": "insufficient_data",
                "data_points": len(recent),
            }

        scores = [s.overall_score for s in recent]

        # Calculate statistics
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)
        score_range = max_score - min_score

        # Determine trend direction
        if recent[-1].overall_score > recent[0].overall_score:
            direction = "improving"
        elif recent[-1].overall_score < recent[0].overall_score:
            direction = "declining"
        else:
            direction = "stable"

        # Calculate velocity (score change per day)
        if len(scores) >= 2:
            days_covered = (recent[-1].calculated_at - recent[0].calculated_at).days or 1
            velocity = (scores[-1] - scores[0]) / days_covered
        else:
            velocity = 0

        return {
            "analyzed": True,
            "period_days": days,
            "data_points": len(recent),
            "average_score": round(avg_score, 2),
            "min_score": round(min_score, 2),
            "max_score": round(max_score, 2),
            "score_range": round(score_range, 2),
            "direction": direction,
            "velocity": round(velocity, 4),
            "volatility": round(score_range / avg_score * 100, 2) if avg_score > 0 else 0,
        }

    async def get_score(self, client_id: Optional[str] = None) -> Optional[HealthScore]:
        """
        Get cached health score.

        Args:
            client_id: Optional client ID override

        Returns:
            HealthScore if exists
        """
        key = client_id or self.client_id
        return self._scores.get(key)

    async def _calculate_usage_health(
        self,
        data: Dict[str, Any]
    ) -> ComponentScore:
        """Calculate usage health component."""
        score = 100.0
        indicators = []
        warnings = []

        # Active usage
        active_users = data.get("active_users", 0)
        total_users = data.get("total_users", 1)
        active_rate = active_users / total_users if total_users > 0 else 0

        if active_rate >= 0.8:
            indicators.append("high_active_user_rate")
        elif active_rate < 0.5:
            score -= 20
            warnings.append("low_active_user_rate")

        # Feature utilization
        feature_util = data.get("feature_utilization", 0.5)
        if feature_util >= 0.7:
            indicators.append("good_feature_utilization")
        elif feature_util < 0.3:
            score -= 15
            warnings.append("low_feature_utilization")

        # Usage growth
        growth = data.get("usage_growth", 0)
        if growth > 0.1:
            indicators.append("usage_growing")
            score += 5
        elif growth < -0.2:
            score -= 10
            warnings.append("usage_declining")

        # API usage
        api_calls = data.get("api_calls_30d", 0)
        if api_calls >= 1000:
            indicators.append("high_api_usage")
        elif api_calls < 100:
            score -= 10
            warnings.append("low_api_usage")

        return ComponentScore(
            component=HealthComponent.USAGE,
            score=min(100, max(0, score)),
            weight=COMPONENT_WEIGHTS[HealthComponent.USAGE],
            indicators=indicators,
            warnings=warnings,
        )

    async def _calculate_engagement_health(
        self,
        data: Dict[str, Any]
    ) -> ComponentScore:
        """Calculate engagement health component."""
        score = 100.0
        indicators = []
        warnings = []

        # Login frequency
        logins_30d = data.get("logins_30d", 0)
        daily_avg = logins_30d / 30

        if daily_avg >= 1:
            indicators.append("daily_login_pattern")
        elif daily_avg < 0.2:
            score -= 25
            warnings.append("infrequent_logins")

        # Feature adoption
        adoption_rate = data.get("feature_adoption_rate", 0.5)
        if adoption_rate >= 0.7:
            indicators.append("high_feature_adoption")
        elif adoption_rate < 0.3:
            score -= 20
            warnings.append("low_feature_adoption")

        # Session duration
        avg_session = data.get("avg_session_minutes", 5)
        if avg_session >= 10:
            indicators.append("engaged_sessions")
        elif avg_session < 3:
            score -= 15
            warnings.append("short_sessions")

        # Team engagement
        team_engagement = data.get("team_engagement_rate", 0.5)
        if team_engagement >= 0.8:
            indicators.append("high_team_engagement")
        elif team_engagement < 0.4:
            score -= 10
            warnings.append("low_team_engagement")

        return ComponentScore(
            component=HealthComponent.ENGAGEMENT,
            score=min(100, max(0, score)),
            weight=COMPONENT_WEIGHTS[HealthComponent.ENGAGEMENT],
            indicators=indicators,
            warnings=warnings,
        )

    async def _calculate_financial_health(
        self,
        data: Dict[str, Any]
    ) -> ComponentScore:
        """Calculate financial health component."""
        score = 100.0
        indicators = []
        warnings = []

        # Payment history
        payment_failures = data.get("payment_failures_90d", 0)
        if payment_failures == 0:
            indicators.append("clean_payment_history")
        elif payment_failures >= 2:
            score -= 30
            warnings.append("payment_issues")
        elif payment_failures >= 1:
            score -= 15
            warnings.append("recent_payment_failure")

        # Overdue status
        overdue_days = data.get("overdue_days", 0)
        if overdue_days == 0:
            indicators.append("current_payments")
        elif overdue_days > 30:
            score -= 25
            warnings.append("significantly_overdue")
        elif overdue_days > 0:
            score -= 10
            warnings.append("payment_overdue")

        # Contract value
        is_annual = data.get("is_annual_contract", False)
        if is_annual:
            indicators.append("annual_commitment")
            score += 5

        # Expansion potential
        has_expansion = data.get("expansion_opportunity", False)
        if has_expansion:
            indicators.append("expansion_potential")

        # Downgrade risk
        downgrade_requests = data.get("downgrade_requests_90d", 0)
        if downgrade_requests > 0:
            score -= 20
            warnings.append("downgrade_intent")

        return ComponentScore(
            component=HealthComponent.FINANCIAL,
            score=min(100, max(0, score)),
            weight=COMPONENT_WEIGHTS[HealthComponent.FINANCIAL],
            indicators=indicators,
            warnings=warnings,
        )

    async def _calculate_support_health(
        self,
        data: Dict[str, Any]
    ) -> ComponentScore:
        """Calculate support health component."""
        score = 100.0
        indicators = []
        warnings = []

        # Ticket volume
        tickets_30d = data.get("tickets_30d", 0)
        if tickets_30d == 0:
            indicators.append("no_support_issues")
        elif tickets_30d <= 2:
            indicators.append("minimal_support_needed")
        elif tickets_30d > 5:
            score -= 20
            warnings.append("high_support_volume")
        elif tickets_30d > 3:
            score -= 10
            warnings.append("elevated_support_volume")

        # Resolution time
        avg_resolution = data.get("avg_resolution_hours", 0)
        if avg_resolution > 0:
            if avg_resolution <= 4:
                indicators.append("fast_resolution")
            elif avg_resolution > 48:
                score -= 15
                warnings.append("slow_resolution")

        # Sentiment
        sentiment = data.get("avg_sentiment", 0.5)
        if sentiment >= 0.7:
            indicators.append("positive_sentiment")
        elif sentiment < 0.4:
            score -= 20
            warnings.append("negative_sentiment")

        # Escalations
        escalations = data.get("escalations_30d", 0)
        if escalations == 0:
            indicators.append("no_escalations")
        elif escalations >= 2:
            score -= 25
            warnings.append("multiple_escalations")
        elif escalations >= 1:
            score -= 10
            warnings.append("recent_escalation")

        return ComponentScore(
            component=HealthComponent.SUPPORT,
            score=min(100, max(0, score)),
            weight=COMPONENT_WEIGHTS[HealthComponent.SUPPORT],
            indicators=indicators,
            warnings=warnings,
        )

    def _determine_health_level(self, score: float) -> HealthLevel:
        """Determine health level from score."""
        if score >= HEALTH_THRESHOLDS[HealthLevel.EXCELLENT]:
            return HealthLevel.EXCELLENT
        elif score >= HEALTH_THRESHOLDS[HealthLevel.GOOD]:
            return HealthLevel.GOOD
        elif score >= HEALTH_THRESHOLDS[HealthLevel.FAIR]:
            return HealthLevel.FAIR
        elif score >= HEALTH_THRESHOLDS[HealthLevel.POOR]:
            return HealthLevel.POOR
        else:
            return HealthLevel.CRITICAL

    async def _calculate_trend(self, current_score: float) -> tuple:
        """Calculate trend from history."""
        history = self._score_history.get(self.client_id, [])
        if len(history) < 2:
            return "stable", "none"

        previous = history[-1].overall_score
        change = current_score - previous

        if abs(change) < 2:
            return "stable", "none"
        elif change > 0:
            return "improving", "up"
        else:
            return "declining", "down"

    def _calculate_period_trend(
        self,
        history: List[HealthScore],
        days: int
    ) -> Dict[str, Any]:
        """Calculate trend for a period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent = [s for s in history if s.calculated_at >= cutoff]

        if len(recent) < 2:
            return {"available": False, "reason": "insufficient_data"}

        scores = [s.overall_score for s in recent]
        return {
            "available": True,
            "average": round(sum(scores) / len(scores), 2),
            "min": round(min(scores), 2),
            "max": round(max(scores), 2),
            "data_points": len(recent),
        }

    async def _generate_recommendations(
        self,
        component_scores: Dict[str, ComponentScore],
        health_level: HealthLevel
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        for name, component in component_scores.items():
            if component.score < 60:
                recommendations.extend(
                    f"Address {name}: {w}" for w in component.warnings[:2]
                )

        if health_level in [HealthLevel.POOR, HealthLevel.CRITICAL]:
            recommendations.insert(0, "Schedule immediate success review")

        return recommendations[:5]


# Export for testing
__all__ = [
    "HealthScoreCalculator",
    "HealthScore",
    "ComponentScore",
    "HealthLevel",
    "HealthComponent",
    "COMPONENT_WEIGHTS",
    "HEALTH_THRESHOLDS",
]
