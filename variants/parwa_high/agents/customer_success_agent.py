"""
PARWA High Customer Success Agent.

Customer success agent with churn prediction capabilities.
CRITICAL: predict_churn() returns {churn_risk: float, risk_factors: list, recommendations: list}
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

from variants.base_agents.base_agent import BaseAgent, AgentResponse
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ChurnRiskLevel(str, Enum):
    """Churn risk level enumeration."""
    LOW = "low"  # 0-0.3
    MEDIUM = "medium"  # 0.3-0.6
    HIGH = "high"  # 0.6-0.8
    CRITICAL = "critical"  # 0.8-1.0


class CustomerHealthStatus(str, Enum):
    """Customer health status."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


@dataclass
class ChurnPrediction:
    """Churn prediction result."""
    churn_risk: float
    risk_level: ChurnRiskLevel
    risk_factors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.8
    customer_id: str = ""
    prediction_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ParwaHighCustomerSuccessAgent(BaseAgent):
    """
    PARWA High Customer Success Agent.

    Provides customer success capabilities including:
    - Churn prediction with risk score
    - Customer health scoring
    - Retention action recommendations
    - Engagement tracking

    CRITICAL: predict_churn() must return:
    - churn_risk: float (0.0-1.0)
    - risk_factors: list of risk factor strings
    - recommendations: list of action recommendations
    """

    # PARWA High specific settings
    PARWA_HIGH_ESCALATION_THRESHOLD = 0.50
    PARWA_HIGH_MAX_CONCURRENT_CUSTOMERS = 100

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize PARWA High Customer Success Agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Agent configuration dictionary
            company_id: UUID of the company
        """
        super().__init__(agent_id, config, company_id)

        # Customer tracking
        self._customer_health_scores: Dict[str, float] = {}
        self._churn_predictions: Dict[str, ChurnPrediction] = {}
        self._engagement_history: Dict[str, List[Dict[str, Any]]] = {}

        # Risk factor weights for churn prediction
        self._risk_weights = {
            "low_engagement": 0.25,
            "declining_usage": 0.20,
            "support_tickets": 0.15,
            "payment_issues": 0.15,
            "feature_underutilization": 0.10,
            "negative_sentiment": 0.10,
            "contract_renewal_near": 0.05,
        }

        logger.info({
            "event": "parwa_high_customer_success_initialized",
            "agent_id": agent_id,
            "tier": self.get_tier(),
            "variant": self.get_variant(),
        })

    def get_tier(self) -> str:
        """Get the AI tier for this agent. PARWA High uses 'heavy'."""
        return "heavy"

    def get_variant(self) -> str:
        """Get the PARWA High variant for this agent."""
        return "parwa_high"

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process customer success request.

        Args:
            input_data: Must contain 'action' key
                - 'predict_churn': Predict churn for a customer
                - 'get_health_score': Get customer health score
                - 'suggest_retention': Suggest retention actions
                - 'track_engagement': Track customer engagement

        Returns:
            AgentResponse with processing result
        """
        action = input_data.get("action")

        if not action:
            return AgentResponse(
                success=False,
                message="Missing required field: action",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        self.log_action("parwa_high_customer_success_process", {
            "action": action,
            "tier": self.get_tier(),
        })

        if action == "predict_churn":
            return await self._handle_predict_churn(input_data)
        elif action == "get_health_score":
            return await self._handle_get_health_score(input_data)
        elif action == "suggest_retention":
            return await self._handle_suggest_retention(input_data)
        elif action == "track_engagement":
            return await self._handle_track_engagement(input_data)
        elif action == "get_stats":
            return await self._handle_get_stats()
        else:
            return AgentResponse(
                success=False,
                message=f"Unknown action: {action}",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

    async def predict_churn(self, customer_id: str) -> Dict[str, Any]:
        """
        CRITICAL: Predict churn for a customer.

        Returns:
            Dict with:
            - churn_risk: float (0.0-1.0)
            - risk_factors: list of risk factor strings
            - recommendations: list of action recommendations
        """
        # Calculate risk factors
        risk_factors = self._identify_risk_factors(customer_id)
        
        # Calculate churn risk
        churn_risk = self._calculate_churn_risk(risk_factors)
        
        # Determine risk level
        risk_level = self._get_risk_level(churn_risk)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(risk_factors, churn_risk)

        prediction = ChurnPrediction(
            churn_risk=churn_risk,
            risk_level=risk_level,
            risk_factors=risk_factors,
            recommendations=recommendations,
            customer_id=customer_id,
        )

        # Store prediction
        self._churn_predictions[customer_id] = prediction

        self.log_action("parwa_high_churn_prediction", {
            "customer_id": customer_id,
            "churn_risk": churn_risk,
            "risk_level": risk_level.value,
            "risk_factor_count": len(risk_factors),
        })

        return {
            "churn_risk": round(churn_risk, 4),
            "risk_level": risk_level.value,
            "risk_factors": risk_factors,
            "recommendations": recommendations,
            "customer_id": customer_id,
        }

    async def get_health_score(self, customer_id: str) -> Dict[str, Any]:
        """
        Get customer health score.

        Args:
            customer_id: Customer identifier

        Returns:
            Dict with health score and status
        """
        # Calculate health score (inverse of churn risk with adjustments)
        churn_prediction = await self.predict_churn(customer_id)
        churn_risk = churn_prediction["churn_risk"]

        # Health score is inverse of churn risk
        health_score = round((1.0 - churn_risk) * 100, 2)

        # Determine health status
        if health_score >= 80:
            status = CustomerHealthStatus.EXCELLENT
        elif health_score >= 60:
            status = CustomerHealthStatus.GOOD
        elif health_score >= 40:
            status = CustomerHealthStatus.FAIR
        elif health_score >= 20:
            status = CustomerHealthStatus.POOR
        else:
            status = CustomerHealthStatus.CRITICAL

        # Store health score
        self._customer_health_scores[customer_id] = health_score

        return {
            "customer_id": customer_id,
            "health_score": health_score,
            "status": status.value,
            "churn_risk": churn_risk,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    async def suggest_retention_actions(self, customer_id: str) -> Dict[str, Any]:
        """
        Suggest retention actions for a customer.

        Args:
            customer_id: Customer identifier

        Returns:
            Dict with retention actions
        """
        prediction = await self.predict_churn(customer_id)

        actions = []

        # High-priority actions for high-risk customers
        if prediction["churn_risk"] > 0.7:
            actions.extend([
                {
                    "priority": "critical",
                    "action": "Schedule executive outreach call",
                    "reason": "High churn risk requires personal attention",
                    "expected_impact": "Reduce churn risk by 20-30%",
                },
                {
                    "priority": "critical",
                    "action": "Offer loyalty discount or contract extension",
                    "reason": "Economic incentive to retain",
                    "expected_impact": "Improve retention likelihood by 25%",
                },
            ])

        # Address specific risk factors
        for factor in prediction["risk_factors"]:
            if "engagement" in factor.lower():
                actions.append({
                    "priority": "high",
                    "action": "Schedule product training session",
                    "reason": factor,
                    "expected_impact": "Increase engagement by 40%",
                })
            elif "support" in factor.lower():
                actions.append({
                    "priority": "high",
                    "action": "Proactive support check-in",
                    "reason": factor,
                    "expected_impact": "Resolve issues before escalation",
                })
            elif "payment" in factor.lower():
                actions.append({
                    "priority": "medium",
                    "action": "Review billing and payment options",
                    "reason": factor,
                    "expected_impact": "Resolve payment friction",
                })

        return {
            "customer_id": customer_id,
            "churn_risk": prediction["churn_risk"],
            "actions": actions,
            "total_actions": len(actions),
        }

    async def _handle_predict_churn(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle predict_churn action."""
        customer_id = input_data.get("customer_id")

        if not customer_id:
            return AgentResponse(
                success=False,
                message="Missing required field: customer_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.predict_churn(customer_id)

        return AgentResponse(
            success=True,
            message=f"Churn prediction for {customer_id}: {result['churn_risk']:.2%} risk",
            data=result,
            confidence=0.85,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_get_health_score(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle get_health_score action."""
        customer_id = input_data.get("customer_id")

        if not customer_id:
            return AgentResponse(
                success=False,
                message="Missing required field: customer_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.get_health_score(customer_id)

        return AgentResponse(
            success=True,
            message=f"Health score for {customer_id}: {result['health_score']}",
            data=result,
            confidence=0.85,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_suggest_retention(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle suggest_retention action."""
        customer_id = input_data.get("customer_id")

        if not customer_id:
            return AgentResponse(
                success=False,
                message="Missing required field: customer_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.suggest_retention_actions(customer_id)

        return AgentResponse(
            success=True,
            message=f"Generated {result['total_actions']} retention actions",
            data=result,
            confidence=0.80,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_track_engagement(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle track_engagement action."""
        customer_id = input_data.get("customer_id")
        engagement_data = input_data.get("engagement_data", {})

        if not customer_id:
            return AgentResponse(
                success=False,
                message="Missing required field: customer_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        # Record engagement
        if customer_id not in self._engagement_history:
            self._engagement_history[customer_id] = []

        engagement_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **engagement_data,
        }
        self._engagement_history[customer_id].append(engagement_record)

        return AgentResponse(
            success=True,
            message=f"Engagement tracked for {customer_id}",
            data={
                "customer_id": customer_id,
                "engagement_count": len(self._engagement_history[customer_id]),
                "last_engagement": engagement_record,
            },
            confidence=0.95,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_get_stats(self) -> AgentResponse:
        """Handle get_stats action."""
        return AgentResponse(
            success=True,
            message="Customer success statistics",
            data={
                "customers_tracked": len(self._customer_health_scores),
                "predictions_made": len(self._churn_predictions),
                "total_engagement_records": sum(
                    len(h) for h in self._engagement_history.values()
                ),
                "variant": self.get_variant(),
                "tier": self.get_tier(),
            },
            confidence=1.0,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    def _identify_risk_factors(self, customer_id: str) -> List[str]:
        """Identify risk factors for a customer."""
        risk_factors = []

        # Simulated risk factor detection
        # In production, this would analyze actual customer data
        import random
        random.seed(hash(customer_id))

        possible_factors = [
            "Low engagement in last 30 days",
            "Declining usage trend",
            "Multiple support tickets open",
            "Payment issues detected",
            "Feature underutilization",
            "Negative sentiment in recent interactions",
            "Contract renewal approaching",
        ]

        # Randomly select risk factors based on customer
        num_factors = random.randint(0, 4)
        risk_factors = random.sample(possible_factors, min(num_factors, len(possible_factors)))

        return risk_factors

    def _calculate_churn_risk(self, risk_factors: List[str]) -> float:
        """Calculate churn risk from risk factors."""
        if not risk_factors:
            return 0.1  # Base risk for customers with no risk factors

        risk_score = 0.0

        for factor in risk_factors:
            factor_lower = factor.lower()
            for key, weight in self._risk_weights.items():
                if key.replace("_", " ") in factor_lower:
                    risk_score += weight
                    break

        # Normalize to 0-1 range
        return min(1.0, max(0.0, risk_score))

    def _get_risk_level(self, churn_risk: float) -> ChurnRiskLevel:
        """Get risk level from churn risk score."""
        if churn_risk >= 0.8:
            return ChurnRiskLevel.CRITICAL
        elif churn_risk >= 0.6:
            return ChurnRiskLevel.HIGH
        elif churn_risk >= 0.3:
            return ChurnRiskLevel.MEDIUM
        else:
            return ChurnRiskLevel.LOW

    def _generate_recommendations(
        self,
        risk_factors: List[str],
        churn_risk: float
    ) -> List[str]:
        """Generate recommendations based on risk factors."""
        recommendations = []

        if churn_risk > 0.7:
            recommendations.append("URGENT: Schedule immediate retention call")

        for factor in risk_factors:
            if "engagement" in factor.lower():
                recommendations.append("Schedule product training to boost engagement")
            elif "support" in factor.lower():
                recommendations.append("Proactive support outreach to resolve issues")
            elif "payment" in factor.lower():
                recommendations.append("Review payment options and billing schedule")
            elif "usage" in factor.lower():
                recommendations.append("Analyze usage patterns and suggest additional features")
            elif "sentiment" in factor.lower():
                recommendations.append("Escalate to customer success manager")
            elif "renewal" in factor.lower():
                recommendations.append("Initiate early renewal discussion")

        if not recommendations:
            recommendations.append("Continue regular engagement cadence")

        return recommendations
