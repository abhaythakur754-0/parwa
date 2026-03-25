"""
Risk Scorer Service

Calculates churn risk levels (LOW/MEDIUM/HIGH/CRITICAL) using
weighted risk factors with trend analysis.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RiskCategory(str, Enum):
    """Categories of risk."""
    USAGE = "usage"
    QUALITY = "quality"
    SUPPORT = "support"
    FINANCIAL = "financial"
    ENGAGEMENT = "engagement"


class RiskTrend(str, Enum):
    """Trend direction for risk."""
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"


@dataclass
class RiskComponent:
    """Individual risk component score."""
    category: RiskCategory
    score: float  # 0-100
    weight: float  # 0.0-1.0
    trend: RiskTrend
    details: Dict[str, Any] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RiskScoreResult:
    """Complete risk score result for a client."""
    client_id: str
    overall_score: float  # 0-100
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    components: List[RiskComponent]
    trend: RiskTrend
    trend_description: str
    primary_risk_factor: str
    calculated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class RiskScorer:
    """
    Calculate churn risk scores for clients.

    Risk factors and weights:
    - Declining usage: 25%
    - Low accuracy: 25%
    - Support tickets: 20%
    - Payment issues: 15%
    - Low engagement: 15%
    """

    # Component weights (must sum to 1.0)
    COMPONENT_WEIGHTS = {
        RiskCategory.USAGE: 0.25,
        RiskCategory.QUALITY: 0.25,
        RiskCategory.SUPPORT: 0.20,
        RiskCategory.FINANCIAL: 0.15,
        RiskCategory.ENGAGEMENT: 0.15,
    }

    # Risk level thresholds
    RISK_THRESHOLDS = {
        "LOW": (0, 25),
        "MEDIUM": (25, 50),
        "HIGH": (50, 75),
        "CRITICAL": (75, 100),
    }

    # Supported clients
    SUPPORTED_CLIENTS = [
        "client_001", "client_002", "client_003", "client_004", "client_005",
        "client_006", "client_007", "client_008", "client_009", "client_010"
    ]

    def __init__(self):
        """Initialize risk scorer."""
        self._scores: Dict[str, List[RiskScoreResult]] = {
            client: [] for client in self.SUPPORTED_CLIENTS
        }

    def calculate_score(
        self,
        client_id: str,
        usage_metrics: Optional[Dict[str, Any]] = None,
        quality_metrics: Optional[Dict[str, Any]] = None,
        support_metrics: Optional[Dict[str, Any]] = None,
        financial_metrics: Optional[Dict[str, Any]] = None,
        engagement_metrics: Optional[Dict[str, Any]] = None
    ) -> RiskScoreResult:
        """
        Calculate risk score for a client.

        Args:
            client_id: Client identifier
            usage_metrics: Usage-related metrics
            quality_metrics: Quality/accuracy metrics
            support_metrics: Support ticket metrics
            financial_metrics: Payment/financial metrics
            engagement_metrics: Engagement metrics

        Returns:
            RiskScoreResult with complete breakdown
        """
        if client_id not in self.SUPPORTED_CLIENTS:
            raise ValueError(f"Unsupported client: {client_id}")

        # Calculate individual components
        components = []

        # Usage component
        usage_component = self._calculate_usage_risk(usage_metrics or {})
        components.append(usage_component)

        # Quality component
        quality_component = self._calculate_quality_risk(quality_metrics or {})
        components.append(quality_component)

        # Support component
        support_component = self._calculate_support_risk(support_metrics or {})
        components.append(support_component)

        # Financial component
        financial_component = self._calculate_financial_risk(financial_metrics or {})
        components.append(financial_component)

        # Engagement component
        engagement_component = self._calculate_engagement_risk(engagement_metrics or {})
        components.append(engagement_component)

        # Calculate weighted overall score
        overall_score = sum(
            c.score * self.COMPONENT_WEIGHTS[c.category]
            for c in components
        )

        # Determine risk level
        risk_level = self._determine_risk_level(overall_score)

        # Analyze trend
        trend, trend_desc = self._analyze_trend(client_id, overall_score)

        # Find primary risk factor
        primary = max(components, key=lambda c: c.score * self.COMPONENT_WEIGHTS[c.category])

        result = RiskScoreResult(
            client_id=client_id,
            overall_score=round(overall_score, 1),
            risk_level=risk_level,
            components=components,
            trend=trend,
            trend_description=trend_desc,
            primary_risk_factor=primary.category.value,
            metadata={
                "weights": {k.value: v for k, v in self.COMPONENT_WEIGHTS.items()},
            }
        )

        # Store result
        self._scores[client_id].append(result)
        logger.info(f"Risk score for {client_id}: {overall_score:.1f} ({risk_level})")

        return result

    def _calculate_usage_risk(self, metrics: Dict[str, Any]) -> RiskComponent:
        """Calculate usage risk component."""
        # Extract metrics
        trend = metrics.get("usage_trend", 0.0)
        active_users = metrics.get("active_users", 100)
        total_users = metrics.get("total_users", 100)
        sessions_per_user = metrics.get("sessions_per_user", 10)

        # Calculate score
        score = 0.0

        # Declining usage adds risk
        if trend < 0:
            score += min(50, abs(trend))

        # Low active user ratio adds risk
        active_ratio = active_users / total_users if total_users > 0 else 1.0
        if active_ratio < 0.5:
            score += (1.0 - active_ratio) * 50

        # Low session count adds risk
        if sessions_per_user < 5:
            score += (5 - sessions_per_user) * 5

        score = min(100, score)

        # Determine trend
        risk_trend = RiskTrend.STABLE
        if trend < -10:
            risk_trend = RiskTrend.INCREASING
        elif trend > 5:
            risk_trend = RiskTrend.DECREASING

        return RiskComponent(
            category=RiskCategory.USAGE,
            score=round(score, 1),
            weight=self.COMPONENT_WEIGHTS[RiskCategory.USAGE],
            trend=risk_trend,
            details={
                "usage_trend": trend,
                "active_ratio": round(active_ratio, 2),
                "sessions_per_user": sessions_per_user,
            }
        )

    def _calculate_quality_risk(self, metrics: Dict[str, Any]) -> RiskComponent:
        """Calculate quality/accuracy risk component."""
        accuracy = metrics.get("accuracy_rate", 85.0)
        resolution_rate = metrics.get("resolution_rate", 80.0)
        avg_response_time = metrics.get("avg_response_time", 3.0)

        score = 0.0

        # Low accuracy adds risk
        if accuracy < 80:
            score += (80 - accuracy) * 2.5

        # Low resolution rate adds risk
        if resolution_rate < 70:
            score += (70 - resolution_rate) * 1.5

        # High response time adds risk
        if avg_response_time > 4:
            score += (avg_response_time - 4) * 10

        score = min(100, score)

        # Determine trend
        risk_trend = RiskTrend.STABLE
        if accuracy < 70:
            risk_trend = RiskTrend.INCREASING
        elif accuracy > 85:
            risk_trend = RiskTrend.DECREASING

        return RiskComponent(
            category=RiskCategory.QUALITY,
            score=round(score, 1),
            weight=self.COMPONENT_WEIGHTS[RiskCategory.QUALITY],
            trend=risk_trend,
            details={
                "accuracy_rate": accuracy,
                "resolution_rate": resolution_rate,
                "avg_response_time": avg_response_time,
            }
        )

    def _calculate_support_risk(self, metrics: Dict[str, Any]) -> RiskComponent:
        """Calculate support-related risk component."""
        tickets_30d = metrics.get("tickets_30d", 0)
        escalations_30d = metrics.get("escalations_30d", 0)
        unresolved_tickets = metrics.get("unresolved_tickets", 0)

        score = 0.0

        # High ticket volume adds risk
        if tickets_30d > 5:
            score += (tickets_30d - 5) * 8

        # Escalations add significant risk
        score += escalations_30d * 15

        # Unresolved tickets add risk
        score += unresolved_tickets * 5

        score = min(100, score)

        # Determine trend
        risk_trend = RiskTrend.STABLE
        if tickets_30d > 10 or escalations_30d > 3:
            risk_trend = RiskTrend.INCREASING
        elif tickets_30d < 3:
            risk_trend = RiskTrend.DECREASING

        return RiskComponent(
            category=RiskCategory.SUPPORT,
            score=round(score, 1),
            weight=self.COMPONENT_WEIGHTS[RiskCategory.SUPPORT],
            trend=risk_trend,
            details={
                "tickets_30d": tickets_30d,
                "escalations_30d": escalations_30d,
                "unresolved_tickets": unresolved_tickets,
            }
        )

    def _calculate_financial_risk(self, metrics: Dict[str, Any]) -> RiskComponent:
        """Calculate financial/payment risk component."""
        payment_issues = metrics.get("payment_issues", 0)
        overdue_amount = metrics.get("overdue_amount", 0)
        contract_value = metrics.get("contract_value", 1000)
        days_to_renewal = metrics.get("days_to_renewal", 180)

        score = 0.0

        # Payment issues add significant risk
        score += payment_issues * 30

        # Overdue amount proportional to contract value
        if overdue_amount > 0:
            overdue_ratio = overdue_amount / contract_value if contract_value > 0 else 0
            score += overdue_ratio * 50

        # Near renewal with other issues compounds risk
        if days_to_renewal < 30 and payment_issues > 0:
            score += 20

        score = min(100, score)

        # Determine trend
        risk_trend = RiskTrend.STABLE
        if payment_issues > 2:
            risk_trend = RiskTrend.INCREASING
        elif payment_issues == 0 and overdue_amount == 0:
            risk_trend = RiskTrend.DECREASING

        return RiskComponent(
            category=RiskCategory.FINANCIAL,
            score=round(score, 1),
            weight=self.COMPONENT_WEIGHTS[RiskCategory.FINANCIAL],
            trend=risk_trend,
            details={
                "payment_issues": payment_issues,
                "overdue_amount": overdue_amount,
                "days_to_renewal": days_to_renewal,
            }
        )

    def _calculate_engagement_risk(self, metrics: Dict[str, Any]) -> RiskComponent:
        """Calculate engagement risk component."""
        engagement_score = metrics.get("engagement_score", 75.0)
        last_login_days = metrics.get("last_login_days", 1)
        feature_adoption = metrics.get("feature_adoption", 0.5)

        score = 0.0

        # Low engagement score adds risk
        if engagement_score < 60:
            score += (60 - engagement_score) * 1.5

        # Long time since last login
        if last_login_days > 7:
            score += min(30, (last_login_days - 7) * 3)

        # Low feature adoption
        if feature_adoption < 0.3:
            score += (0.3 - feature_adoption) * 100

        score = min(100, score)

        # Determine trend
        risk_trend = RiskTrend.STABLE
        if engagement_score < 40 or last_login_days > 14:
            risk_trend = RiskTrend.INCREASING
        elif engagement_score > 70 and last_login_days < 3:
            risk_trend = RiskTrend.DECREASING

        return RiskComponent(
            category=RiskCategory.ENGAGEMENT,
            score=round(score, 1),
            weight=self.COMPONENT_WEIGHTS[RiskCategory.ENGAGEMENT],
            trend=risk_trend,
            details={
                "engagement_score": engagement_score,
                "last_login_days": last_login_days,
                "feature_adoption": feature_adoption,
            }
        )

    def _determine_risk_level(self, score: float) -> str:
        """Determine risk level from score."""
        for level, (low, high) in self.RISK_THRESHOLDS.items():
            if low <= score < high:
                return level
        return "CRITICAL"

    def _analyze_trend(
        self,
        client_id: str,
        current_score: float
    ) -> tuple:
        """Analyze risk trend over time."""
        history = self._scores.get(client_id, [])

        if len(history) < 2:
            return RiskTrend.STABLE, "Insufficient data for trend analysis"

        # Compare with last 3 scores
        recent_scores = [h.overall_score for h in history[-3:]]
        avg_recent = sum(recent_scores) / len(recent_scores)

        diff = current_score - avg_recent

        if diff > 10:
            return RiskTrend.INCREASING, f"Risk increasing (+{diff:.1f} points)"
        elif diff < -10:
            return RiskTrend.DECREASING, f"Risk decreasing ({diff:.1f} points)"
        else:
            return RiskTrend.STABLE, "Risk stable"

    def get_client_scores(
        self,
        client_id: str,
        limit: int = 10
    ) -> List[RiskScoreResult]:
        """Get historical risk scores for a client."""
        history = self._scores.get(client_id, [])
        return history[-limit:] if history else []

    def get_risk_distribution(self) -> Dict[str, int]:
        """Get distribution of clients by risk level."""
        distribution = {level: 0 for level in self.RISK_THRESHOLDS.keys()}

        for client_id in self.SUPPORTED_CLIENTS:
            history = self._scores.get(client_id, [])
            if history:
                latest = history[-1]
                distribution[latest.risk_level] += 1

        return distribution

    def get_high_risk_clients(self) -> List[RiskScoreResult]:
        """Get list of high-risk clients."""
        high_risk = []

        for client_id in self.SUPPORTED_CLIENTS:
            history = self._scores.get(client_id, [])
            if history:
                latest = history[-1]
                if latest.risk_level in ["HIGH", "CRITICAL"]:
                    high_risk.append(latest)

        # Sort by score (highest first)
        high_risk.sort(key=lambda r: r.overall_score, reverse=True)
        return high_risk

    def get_summary(self) -> Dict[str, Any]:
        """Get overall risk summary."""
        distribution = self.get_risk_distribution()
        high_risk = self.get_high_risk_clients()

        total_scored = sum(distribution.values())
        avg_score = 0.0

        if total_scored > 0:
            total = 0
            count = 0
            for client_id in self.SUPPORTED_CLIENTS:
                history = self._scores.get(client_id, [])
                if history:
                    total += history[-1].overall_score
                    count += 1
            avg_score = total / count if count > 0 else 0

        return {
            "clients_scored": total_scored,
            "average_risk_score": round(avg_score, 1),
            "distribution": distribution,
            "high_risk_count": len(high_risk),
            "critical_clients": [r.client_id for r in high_risk if r.risk_level == "CRITICAL"],
        }
