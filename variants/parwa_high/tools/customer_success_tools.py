"""
PARWA High Customer Success Tools.

Advanced customer success capabilities for PARWA High variant:
- Health score calculation
- Churn prediction with risk score
- Retention action recommendations
- Engagement tracking

CRITICAL: predict_churn_risk must return {risk_score, factors}

PARWA High Features:
- Heavy AI tier for sophisticated analysis
- Company-isolated customer data
- HIPAA compliance for healthcare clients
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Customer health status levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    AT_RISK = "at_risk"
    CRITICAL = "critical"


class ChurnRiskLevel(Enum):
    """Churn risk levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ChurnPrediction:
    """Churn prediction result."""
    customer_id: str
    risk_score: float  # CRITICAL: 0.0 to 1.0
    risk_level: ChurnRiskLevel
    factors: List[str]  # CRITICAL: List of risk factors
    recommendations: List[str]
    confidence: float
    predicted_churn_date: Optional[str] = None


@dataclass
class HealthScore:
    """Customer health score result."""
    customer_id: str
    score: float  # 0.0 to 100.0
    status: HealthStatus
    components: Dict[str, float] = field(default_factory=dict)
    trend: str = "stable"  # "improving", "declining", "stable"
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CustomerSuccessTools:
    """
    Customer success tools for PARWA High variant.

    Provides advanced customer success capabilities:
    - Calculate customer health scores
    - Predict churn risk with detailed factors
    - Generate retention action recommendations
    - Track customer engagement metrics

    CRITICAL Requirements:
    - predict_churn_risk must return {risk_score, factors}
    - Health scores are company-isolated
    - No PHI stored or logged

    Example:
        tools = CustomerSuccessTools()
        churn = await tools.predict_churn_risk("cust_123")
        # churn["risk_score"] = 0.75
        # churn["factors"] = ["low_engagement", "declining_usage"]
    """

    def __init__(
        self,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize Customer Success Tools.

        Args:
            company_id: Company UUID for data isolation
        """
        self._company_id = company_id
        self._health_scores: Dict[str, HealthScore] = {}
        self._churn_predictions: Dict[str, ChurnPrediction] = {}
        self._engagement_history: Dict[str, List[Dict[str, Any]]] = {}

        logger.info({
            "event": "customer_success_tools_initialized",
            "company_id": str(company_id) if company_id else None,
            "variant": "parwa_high",
            "tier": "heavy",
        })

    async def calculate_health_score(
        self,
        customer_id: str
    ) -> float:
        """
        Calculate customer health score.

        Computes a comprehensive health score based on multiple
        factors including engagement, usage, support interactions,
        and payment history.

        Args:
            customer_id: Customer identifier

        Returns:
            Health score between 0.0 and 100.0
        """
        # Gather customer data (mocked for now)
        customer_data = await self._get_customer_data(customer_id)

        # Calculate component scores
        components: Dict[str, float] = {}

        # Engagement score (0-25)
        engagement_score = self._calculate_engagement_score(customer_data)
        components["engagement"] = engagement_score

        # Usage score (0-25)
        usage_score = self._calculate_usage_score(customer_data)
        components["usage"] = usage_score

        # Support score (0-25)
        support_score = self._calculate_support_score(customer_data)
        components["support"] = support_score

        # Payment score (0-25)
        payment_score = self._calculate_payment_score(customer_data)
        components["payment"] = payment_score

        # Calculate total score
        total_score = sum(components.values())

        # Determine status
        status = self._determine_health_status(total_score)

        # Determine trend
        previous_score = customer_data.get("previous_health_score", total_score)
        if total_score > previous_score + 5:
            trend = "improving"
        elif total_score < previous_score - 5:
            trend = "declining"
        else:
            trend = "stable"

        # Store health score
        health = HealthScore(
            customer_id=customer_id,
            score=total_score,
            status=status,
            components=components,
            trend=trend,
        )
        self._health_scores[customer_id] = health

        logger.info({
            "event": "health_score_calculated",
            "customer_id": customer_id,
            "score": total_score,
            "status": status.value,
            "trend": trend,
        })

        return total_score

    async def predict_churn_risk(
        self,
        customer_id: str
    ) -> Dict[str, Any]:
        """
        Predict churn risk for a customer.

        CRITICAL: This method MUST return a dict with:
        - risk_score: float between 0.0 and 1.0
        - factors: list of risk factor strings

        Uses multiple signals to predict likelihood of churn:
        - Engagement patterns
        - Usage trends
        - Support ticket history
        - Payment behavior
        - Feature adoption

        Args:
            customer_id: Customer identifier

        Returns:
            Dict with:
                - risk_score: float (0.0-1.0)
                - factors: List[str] of risk factors
                - risk_level: str (low/medium/high/critical)
                - recommendations: List[str]
                - confidence: float
        """
        # Get customer data
        customer_data = await self._get_customer_data(customer_id)

        # Calculate risk components
        risk_score = 0.0
        factors: List[str] = []
        recommendations: List[str] = []

        # Check engagement risk
        engagement_risk = self._assess_engagement_risk(customer_data)
        if engagement_risk["score"] > 0:
            risk_score += engagement_risk["score"]
            factors.extend(engagement_risk["factors"])

        # Check usage risk
        usage_risk = self._assess_usage_risk(customer_data)
        if usage_risk["score"] > 0:
            risk_score += usage_risk["score"]
            factors.extend(usage_risk["factors"])

        # Check support risk
        support_risk = self._assess_support_risk(customer_data)
        if support_risk["score"] > 0:
            risk_score += support_risk["score"]
            factors.extend(support_risk["factors"])

        # Check payment risk
        payment_risk = self._assess_payment_risk(customer_data)
        if payment_risk["score"] > 0:
            risk_score += payment_risk["score"]
            factors.extend(payment_risk["factors"])

        # Normalize risk score to 0.0-1.0
        risk_score = min(1.0, risk_score / 4.0)

        # Determine risk level
        if risk_score >= 0.75:
            risk_level = ChurnRiskLevel.CRITICAL
            recommendations.append("Immediate intervention required - schedule executive call")
        elif risk_score >= 0.5:
            risk_level = ChurnRiskLevel.HIGH
            recommendations.append("Schedule retention call within 24 hours")
        elif risk_score >= 0.25:
            risk_level = ChurnRiskLevel.MEDIUM
            recommendations.append("Proactive outreach recommended within 1 week")
        else:
            risk_level = ChurnRiskLevel.LOW
            recommendations.append("Continue regular engagement cadence")

        # Add specific recommendations based on factors
        if "declining_usage" in factors:
            recommendations.append("Review product adoption and offer training")
        if "support_escalations" in factors:
            recommendations.append("Address outstanding support issues")
        if "payment_issues" in factors:
            recommendations.append("Review billing and offer payment flexibility")
        if "low_engagement" in factors:
            recommendations.append("Re-engage with product updates and value props")

        # Calculate confidence
        confidence = self._calculate_prediction_confidence(customer_data)

        # Predict potential churn date
        predicted_date = self._predict_churn_date(risk_score, customer_data)

        # Store prediction
        prediction = ChurnPrediction(
            customer_id=customer_id,
            risk_score=risk_score,
            risk_level=risk_level,
            factors=factors,
            recommendations=recommendations,
            confidence=confidence,
            predicted_churn_date=predicted_date,
        )
        self._churn_predictions[customer_id] = prediction

        logger.info({
            "event": "churn_risk_predicted",
            "customer_id": customer_id,
            "risk_score": risk_score,
            "risk_level": risk_level.value,
            "factor_count": len(factors),
            "confidence": confidence,
        })

        # CRITICAL: Return dict with risk_score and factors
        return {
            "risk_score": risk_score,  # CRITICAL
            "factors": factors,  # CRITICAL
            "risk_level": risk_level.value,
            "recommendations": recommendations,
            "confidence": confidence,
            "predicted_churn_date": predicted_date,
            "metadata": {
                "variant": "parwa_high",
                "tier": "heavy",
                "customer_id": customer_id,
            },
        }

    async def get_retention_actions(
        self,
        customer_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get recommended retention actions for a customer.

        Generates prioritized action items based on customer
        health and churn risk analysis.

        Args:
            customer_id: Customer identifier

        Returns:
            List of action dicts with priority, action, and timing
        """
        # Get health score and churn prediction
        health = self._health_scores.get(customer_id)
        churn = self._churn_predictions.get(customer_id)

        actions: List[Dict[str, Any]] = []

        if not health:
            health_score = await self.calculate_health_score(customer_id)
            health = self._health_scores.get(customer_id)

        if not churn:
            churn = ChurnPrediction(
                customer_id=customer_id,
                risk_score=0.0,
                risk_level=ChurnRiskLevel.LOW,
                factors=[],
                recommendations=[],
                confidence=0.5,
            )

        # Priority 1: Critical risk actions
        if churn.risk_level == ChurnRiskLevel.CRITICAL:
            actions.append({
                "priority": 1,
                "action": "Executive sponsor outreach",
                "description": "Schedule call with customer executive sponsor",
                "timing": "within_24_hours",
                "owner": "customer_success_manager",
            })
            actions.append({
                "priority": 1,
                "action": "Value assessment meeting",
                "description": "Present ROI analysis and value delivered",
                "timing": "within_48_hours",
                "owner": "account_manager",
            })

        # Priority 2: High risk actions
        if churn.risk_level in [ChurnRiskLevel.HIGH, ChurnRiskLevel.CRITICAL]:
            actions.append({
                "priority": 2,
                "action": "Product training session",
                "description": "Offer comprehensive product training",
                "timing": "within_1_week",
                "owner": "customer_success",
            })
            actions.append({
                "priority": 2,
                "action": "Feature adoption review",
                "description": "Review and promote underutilized features",
                "timing": "within_1_week",
                "owner": "customer_success",
            })

        # Priority 3: Medium risk actions
        if churn.risk_level in [ChurnRiskLevel.MEDIUM, ChurnRiskLevel.HIGH, ChurnRiskLevel.CRITICAL]:
            actions.append({
                "priority": 3,
                "action": "Check-in call",
                "description": "Schedule proactive check-in call",
                "timing": "within_2_weeks",
                "owner": "customer_success",
            })

        # Add health-based actions
        if health and health.trend == "declining":
            actions.append({
                "priority": 2,
                "action": "Health trend review",
                "description": "Investigate declining health score trend",
                "timing": "within_1_week",
                "owner": "customer_success_manager",
            })

        # Add factor-specific actions
        for factor in churn.factors:
            if "support" in factor.lower():
                actions.append({
                    "priority": 2,
                    "action": "Support follow-up",
                    "description": "Review and resolve outstanding support issues",
                    "timing": "within_3_days",
                    "owner": "support_team",
                })
            if "payment" in factor.lower():
                actions.append({
                    "priority": 2,
                    "action": "Billing review",
                    "description": "Review billing history and offer assistance",
                    "timing": "within_1_week",
                    "owner": "billing_team",
                })

        # Default actions for healthy customers
        if churn.risk_level == ChurnRiskLevel.LOW and len(actions) < 3:
            actions.append({
                "priority": 4,
                "action": "Quarterly business review",
                "description": "Schedule quarterly business review",
                "timing": "next_quarter",
                "owner": "account_manager",
            })
            actions.append({
                "priority": 5,
                "action": "Expansion opportunity",
                "description": "Identify upsell/cross-sell opportunities",
                "timing": "ongoing",
                "owner": "sales",
            })

        logger.info({
            "event": "retention_actions_generated",
            "customer_id": customer_id,
            "action_count": len(actions),
            "risk_level": churn.risk_level.value,
        })

        return sorted(actions, key=lambda x: x["priority"])

    async def track_engagement(
        self,
        customer_id: str
    ) -> Dict[str, Any]:
        """
        Track customer engagement metrics.

        Monitors and records engagement signals for health
        score calculation and churn prediction.

        Args:
            customer_id: Customer identifier

        Returns:
            Dict with engagement metrics and trends
        """
        customer_data = await self._get_customer_data(customer_id)

        # Track engagement metrics
        engagement_metrics = {
            "customer_id": customer_id,
            "tracked_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "logins_last_30d": customer_data.get("logins_last_30d", 0),
                "feature_usage_pct": customer_data.get("feature_usage_pct", 0),
                "api_calls_last_30d": customer_data.get("api_calls_last_30d", 0),
                "support_tickets_last_30d": customer_data.get("support_tickets_last_30d", 0),
                "nps_score": customer_data.get("nps_score", None),
                "last_active": customer_data.get("last_active", None),
            },
            "trends": {
                "login_trend": self._calculate_trend_direction(
                    customer_data.get("logins_history", [])
                ),
                "usage_trend": self._calculate_trend_direction(
                    customer_data.get("usage_history", [])
                ),
            },
            "engagement_score": self._calculate_engagement_score(customer_data),
            "metadata": {
                "variant": "parwa_high",
                "tier": "heavy",
            },
        }

        # Store in history
        if customer_id not in self._engagement_history:
            self._engagement_history[customer_id] = []
        self._engagement_history[customer_id].append(engagement_metrics)

        logger.info({
            "event": "engagement_tracked",
            "customer_id": customer_id,
            "engagement_score": engagement_metrics["engagement_score"],
        })

        return engagement_metrics

    async def _get_customer_data(
        self,
        customer_id: str
    ) -> Dict[str, Any]:
        """Get customer data for analysis (mocked)."""
        # In production, this would fetch from database
        return {
            "customer_id": customer_id,
            "logins_last_30d": 15,
            "feature_usage_pct": 65,
            "api_calls_last_30d": 500,
            "support_tickets_last_30d": 2,
            "support_escalations": 0,
            "nps_score": 8,
            "last_active": datetime.now(timezone.utc).isoformat(),
            "payment_status": "current",
            "contract_value": 5000,
            "contract_start": (datetime.now(timezone.utc) - timedelta(days=180)).isoformat(),
            "logins_history": [10, 12, 15, 14, 16, 15],
            "usage_history": [60, 62, 65, 63, 67, 65],
            "previous_health_score": 70,
        }

    def _calculate_engagement_score(
        self,
        data: Dict[str, Any]
    ) -> float:
        """Calculate engagement component score (0-25)."""
        score = 0.0

        # Login frequency (0-10)
        logins = data.get("logins_last_30d", 0)
        if logins >= 20:
            score += 10
        elif logins >= 10:
            score += 7
        elif logins >= 5:
            score += 5
        elif logins >= 1:
            score += 2

        # Feature usage (0-10)
        usage = data.get("feature_usage_pct", 0)
        score += min(10, usage / 10)

        # NPS score (0-5)
        nps = data.get("nps_score", 0)
        if nps >= 9:
            score += 5
        elif nps >= 7:
            score += 3
        elif nps >= 5:
            score += 1

        return score

    def _calculate_usage_score(
        self,
        data: Dict[str, Any]
    ) -> float:
        """Calculate usage component score (0-25)."""
        score = 0.0

        # API calls (0-15)
        api_calls = data.get("api_calls_last_30d", 0)
        if api_calls >= 1000:
            score += 15
        elif api_calls >= 500:
            score += 12
        elif api_calls >= 100:
            score += 8
        elif api_calls >= 10:
            score += 4

        # Feature adoption (0-10)
        usage_pct = data.get("feature_usage_pct", 0)
        score += min(10, usage_pct / 10)

        return score

    def _calculate_support_score(
        self,
        data: Dict[str, Any]
    ) -> float:
        """Calculate support component score (0-25)."""
        score = 25.0  # Start with full score

        tickets = data.get("support_tickets_last_30d", 0)
        escalations = data.get("support_escalations", 0)

        # Deduct for tickets
        if tickets > 5:
            score -= 10
        elif tickets > 2:
            score -= 5

        # Deduct for escalations
        score -= escalations * 5

        return max(0, score)

    def _calculate_payment_score(
        self,
        data: Dict[str, Any]
    ) -> float:
        """Calculate payment component score (0-25)."""
        score = 25.0

        status = data.get("payment_status", "current")
        if status == "late":
            score -= 10
        elif status == "overdue":
            score -= 20
        elif status == "defaulted":
            score = 0

        return max(0, score)

    def _determine_health_status(
        self,
        score: float
    ) -> HealthStatus:
        """Determine health status from score."""
        if score >= 85:
            return HealthStatus.EXCELLENT
        elif score >= 70:
            return HealthStatus.GOOD
        elif score >= 50:
            return HealthStatus.FAIR
        elif score >= 30:
            return HealthStatus.AT_RISK
        else:
            return HealthStatus.CRITICAL

    def _assess_engagement_risk(
        self,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess engagement-related churn risk."""
        score = 0.0
        factors: List[str] = []

        logins = data.get("logins_last_30d", 0)
        if logins < 5:
            score += 0.3
            factors.append("low_engagement")
        elif logins < 10:
            score += 0.15
            factors.append("moderate_engagement_decline")

        trend = self._calculate_trend_direction(data.get("logins_history", []))
        if trend == "declining":
            score += 0.2
            factors.append("declining_engagement")

        return {"score": score, "factors": factors}

    def _assess_usage_risk(
        self,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess usage-related churn risk."""
        score = 0.0
        factors: List[str] = []

        usage = data.get("feature_usage_pct", 0)
        if usage < 30:
            score += 0.35
            factors.append("low_feature_adoption")
        elif usage < 50:
            score += 0.2
            factors.append("declining_usage")

        trend = self._calculate_trend_direction(data.get("usage_history", []))
        if trend == "declining":
            score += 0.15
            factors.append("usage_decline_trend")

        return {"score": score, "factors": factors}

    def _assess_support_risk(
        self,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess support-related churn risk."""
        score = 0.0
        factors: List[str] = []

        tickets = data.get("support_tickets_last_30d", 0)
        if tickets > 5:
            score += 0.25
            factors.append("high_support_volume")

        escalations = data.get("support_escalations", 0)
        if escalations > 0:
            score += 0.3
            factors.append("support_escalations")

        return {"score": score, "factors": factors}

    def _assess_payment_risk(
        self,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess payment-related churn risk."""
        score = 0.0
        factors: List[str] = []

        status = data.get("payment_status", "current")
        if status == "late":
            score += 0.2
            factors.append("late_payment")
        elif status == "overdue":
            score += 0.4
            factors.append("payment_issues")
        elif status == "defaulted":
            score += 0.5
            factors.append("payment_default")

        return {"score": score, "factors": factors}

    def _calculate_trend_direction(
        self,
        history: List[Any]
    ) -> str:
        """Calculate trend direction from history."""
        if len(history) < 3:
            return "stable"

        recent = sum(history[-3:]) / 3
        older = sum(history[:3]) / 3

        if recent > older * 1.1:
            return "improving"
        elif recent < older * 0.9:
            return "declining"
        return "stable"

    def _calculate_prediction_confidence(
        self,
        data: Dict[str, Any]
    ) -> float:
        """Calculate confidence in prediction."""
        # More data points = higher confidence
        confidence = 0.5

        if data.get("logins_last_30d") is not None:
            confidence += 0.1
        if data.get("feature_usage_pct") is not None:
            confidence += 0.1
        if data.get("support_tickets_last_30d") is not None:
            confidence += 0.1
        if data.get("nps_score") is not None:
            confidence += 0.1
        if len(data.get("logins_history", [])) >= 3:
            confidence += 0.1

        return min(1.0, confidence)

    def _predict_churn_date(
        self,
        risk_score: float,
        data: Dict[str, Any]
    ) -> Optional[str]:
        """Predict potential churn date."""
        if risk_score < 0.25:
            return None

        # Estimate based on contract and risk
        contract_start = data.get("contract_start")
        contract_value = data.get("contract_value", 0)

        # Higher risk = sooner churn prediction
        if risk_score >= 0.75:
            days_until_churn = 30
        elif risk_score >= 0.5:
            days_until_churn = 60
        else:
            days_until_churn = 90

        churn_date = datetime.now(timezone.utc) + timedelta(days=days_until_churn)
        return churn_date.strftime("%Y-%m-%d")

    def get_variant(self) -> str:
        """Get variant name."""
        return "parwa_high"

    def get_tier(self) -> str:
        """Get AI tier used."""
        return "heavy"
