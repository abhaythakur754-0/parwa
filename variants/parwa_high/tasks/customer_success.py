"""
PARWA High Customer Success Task.

Task for customer success operations in PARWA High.
Provides health scoring, churn prediction, and retention recommendations.

CRITICAL: Returns {health_score, churn_risk, recommendations}
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone

from variants.parwa_high.config import ParwaHighConfig, get_parwa_high_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ChurnRisk:
    """Churn risk assessment data."""
    risk_score: float
    risk_level: str  # low, medium, high
    risk_factors: List[str] = field(default_factory=list)


@dataclass
class CustomerSuccessResult:
    """Result from customer success task."""
    success: bool
    customer_id: str = ""
    health_score: float = 0.0
    churn_risk: Optional[ChurnRisk] = None
    recommendations: List[str] = field(default_factory=list)
    engagement_score: float = 0.0
    message: str = ""
    generated_at: str = ""


class CustomerSuccessTask:
    """
    Task for customer success operations.

    CRITICAL: Returns {health_score, churn_risk, recommendations}

    Provides:
    - Customer health scoring
    - Churn prediction with risk factors
    - Retention recommendations
    - Engagement tracking

    Example:
        task = CustomerSuccessTask()
        result = await task.execute("cust_123")
        # result.health_score = 0.85
        # result.churn_risk.risk_score = 0.15
        # result.recommendations = ["Schedule check-in call"]
    """

    def __init__(
        self,
        parwa_high_config: Optional[ParwaHighConfig] = None
    ) -> None:
        """
        Initialize customer success task.

        Args:
            parwa_high_config: PARWA High configuration
        """
        self._config = parwa_high_config or get_parwa_high_config()
        self._customer_data: Dict[str, Dict[str, Any]] = {}

    async def execute(self, customer_id: str) -> CustomerSuccessResult:
        """
        Execute customer success analysis.

        CRITICAL: Returns {health_score, churn_risk, recommendations}

        Args:
            customer_id: Customer identifier

        Returns:
            CustomerSuccessResult with health score and churn risk
        """
        logger.info({
            "event": "customer_success_task_started",
            "customer_id": customer_id,
            "variant": "parwa_high",
        })

        if not customer_id:
            return CustomerSuccessResult(
                success=False,
                message="Customer ID is required",
                generated_at=datetime.now(timezone.utc).isoformat(),
            )

        # Get customer health score
        health_score = await self._calculate_health_score(customer_id)

        # Predict churn risk
        churn_risk = await self._predict_churn_risk(customer_id, health_score)

        # Generate recommendations
        recommendations = self._generate_recommendations(health_score, churn_risk)

        # Calculate engagement score
        engagement_score = await self._calculate_engagement_score(customer_id)

        logger.info({
            "event": "customer_success_task_completed",
            "customer_id": customer_id,
            "health_score": health_score,
            "churn_risk_score": churn_risk.risk_score,
            "recommendation_count": len(recommendations),
        })

        return CustomerSuccessResult(
            success=True,
            customer_id=customer_id,
            health_score=health_score,
            churn_risk=churn_risk,
            recommendations=recommendations,
            engagement_score=engagement_score,
            message=f"Customer success analysis completed for {customer_id}",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    async def _calculate_health_score(self, customer_id: str) -> float:
        """
        Calculate customer health score.

        Args:
            customer_id: Customer identifier

        Returns:
            Health score between 0.0 (poor) and 1.0 (excellent)
        """
        # Get or generate customer data
        data = self._customer_data.get(customer_id, self._generate_customer_data(customer_id))
        self._customer_data[customer_id] = data

        score = 0.0

        # Activity score (40% weight)
        if data.get("last_activity_days", 30) <= 7:
            score += 0.4
        elif data.get("last_activity_days", 30) <= 14:
            score += 0.3
        elif data.get("last_activity_days", 30) <= 30:
            score += 0.2

        # Support satisfaction (30% weight)
        satisfaction = data.get("satisfaction_score", 3.5)
        score += (satisfaction / 5.0) * 0.3

        # Resolution rate (20% weight)
        resolution_rate = data.get("resolution_rate", 0.8)
        score += resolution_rate * 0.2

        # Tenure bonus (10% weight)
        tenure_months = data.get("tenure_months", 6)
        if tenure_months >= 12:
            score += 0.1
        elif tenure_months >= 6:
            score += 0.05

        return min(1.0, score)

    async def _predict_churn_risk(
        self,
        customer_id: str,
        health_score: float
    ) -> ChurnRisk:
        """
        Predict churn risk for customer.

        CRITICAL: Returns risk_score and risk_factors

        Args:
            customer_id: Customer identifier
            health_score: Pre-calculated health score

        Returns:
            ChurnRisk with risk assessment
        """
        data = self._customer_data.get(customer_id, {})
        risk_factors: List[str] = []

        # Calculate risk score (inverse of health, with additional factors)
        base_risk = 1.0 - health_score

        # Check for risk indicators
        last_activity = data.get("last_activity_days", 30)
        if last_activity > 21:
            risk_factors.append("Low recent activity")
            base_risk += 0.1

        satisfaction = data.get("satisfaction_score", 3.5)
        if satisfaction < 3.5:
            risk_factors.append("Low satisfaction score")
            base_risk += 0.15

        ticket_count = data.get("open_tickets", 0)
        if ticket_count > 3:
            risk_factors.append("Multiple open tickets")
            base_risk += 0.1

        escalation_count = data.get("escalations", 0)
        if escalation_count > 1:
            risk_factors.append("Recent escalations")
            base_risk += 0.1

        # Cap risk at 1.0
        risk_score = min(1.0, base_risk)

        # Determine risk level
        if risk_score < 0.3:
            risk_level = "low"
        elif risk_score < 0.6:
            risk_level = "medium"
        else:
            risk_level = "high"

        return ChurnRisk(
            risk_score=risk_score,
            risk_level=risk_level,
            risk_factors=risk_factors,
        )

    def _generate_recommendations(
        self,
        health_score: float,
        churn_risk: ChurnRisk
    ) -> List[str]:
        """
        Generate retention recommendations.

        Args:
            health_score: Customer health score
            churn_risk: Churn risk assessment

        Returns:
            List of recommendation strings
        """
        recommendations: List[str] = []

        # Based on health score
        if health_score < 0.5:
            recommendations.append("Schedule immediate check-in call with account manager")
            recommendations.append("Review recent support interactions for issues")
        elif health_score < 0.7:
            recommendations.append("Send proactive engagement email")
            recommendations.append("Offer training or product demo")

        # Based on churn risk
        if churn_risk.risk_level == "high":
            recommendations.append("Escalate to customer success manager")
            recommendations.append("Prepare retention offer")
        elif churn_risk.risk_level == "medium":
            recommendations.append("Schedule follow-up within 7 days")

        # Based on specific risk factors
        for factor in churn_risk.risk_factors:
            if "activity" in factor.lower():
                recommendations.append("Send re-engagement campaign")
            if "satisfaction" in factor.lower():
                recommendations.append("Conduct satisfaction survey")
            if "ticket" in factor.lower():
                recommendations.append("Review and prioritize open tickets")

        # Default positive engagement
        if health_score >= 0.8 and churn_risk.risk_level == "low":
            recommendations.append("Consider for case study or testimonial")
            recommendations.append("Explore upsell opportunities")

        return recommendations[:5]  # Limit to top 5 recommendations

    async def _calculate_engagement_score(self, customer_id: str) -> float:
        """
        Calculate engagement score.

        Args:
            customer_id: Customer identifier

        Returns:
            Engagement score between 0.0 and 1.0
        """
        data = self._customer_data.get(customer_id, {})

        score = 0.0

        # Login frequency (40% weight)
        logins_per_month = data.get("logins_per_month", 4)
        if logins_per_month >= 20:
            score += 0.4
        elif logins_per_month >= 10:
            score += 0.3
        elif logins_per_month >= 5:
            score += 0.2

        # Feature usage (30% weight)
        features_used = data.get("features_used_pct", 50)
        score += (features_used / 100) * 0.3

        # API usage (20% weight)
        api_calls = data.get("api_calls_per_month", 100)
        if api_calls >= 1000:
            score += 0.2
        elif api_calls >= 500:
            score += 0.15
        elif api_calls >= 100:
            score += 0.1

        # Support interaction quality (10% weight)
        satisfaction = data.get("satisfaction_score", 3.5)
        score += (satisfaction / 5.0) * 0.1

        return min(1.0, score)

    def _generate_customer_data(self, customer_id: str) -> Dict[str, Any]:
        """Generate sample customer data for testing."""
        return {
            "last_activity_days": 5,
            "satisfaction_score": 4.2,
            "resolution_rate": 0.92,
            "tenure_months": 12,
            "open_tickets": 1,
            "escalations": 0,
            "logins_per_month": 15,
            "features_used_pct": 75,
            "api_calls_per_month": 500,
        }

    def get_task_name(self) -> str:
        """Get task name."""
        return "customer_success"

    def get_variant(self) -> str:
        """Get variant name."""
        return "parwa_high"

    def get_tier(self) -> str:
        """Get tier used."""
        return "heavy"
