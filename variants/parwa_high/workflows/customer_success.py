"""
PARWA High Customer Success Workflow.

End-to-end workflow for customer success operations:
- Get customer health score
- Predict churn risk with risk score
- Suggest retention actions
- Track engagement metrics

CRITICAL: This workflow MUST return churn_risk with risk_score

PARWA High Features:
- Heavy AI tier for sophisticated analysis
- Customer success with churn prediction
- Company-isolated customer data
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum

from variants.parwa_high.tools.customer_success_tools import CustomerSuccessTools
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class CustomerSuccessStatus(Enum):
    """Customer success workflow status."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    PREDICTING = "predicting"
    RECOMMENDING = "recommending"
    TRACKING = "tracking"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class CustomerSuccessResult:
    """Result from customer success workflow."""
    workflow_id: str
    customer_id: str
    status: CustomerSuccessStatus
    health_score: float = 0.0
    churn_risk: Optional[Dict[str, Any]] = None
    actions: List[Dict[str, Any]] = field(default_factory=list)
    engagement: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CustomerSuccessWorkflow:
    """
    Customer success workflow for PARWA High variant.

    Manages the complete customer success process:
    1. Get customer health score
    2. Predict churn risk with risk_score
    3. Suggest retention actions
    4. Track engagement metrics

    CRITICAL Requirements:
    - Must return churn_risk with risk_score
    - Must return churn_risk with factors list
    - Health scores are company-isolated

    Example:
        workflow = CustomerSuccessWorkflow()
        result = await workflow.execute("cust_123")
        # result["churn_risk"]["risk_score"] = 0.75
        # result["churn_risk"]["factors"] = ["low_engagement", ...]
    """

    def __init__(
        self,
        company_id: Optional[UUID] = None,
        success_tools: Optional[CustomerSuccessTools] = None
    ) -> None:
        """
        Initialize Customer Success Workflow.

        Args:
            company_id: Company UUID for data isolation
            success_tools: Optional customer success tools instance
        """
        self._company_id = company_id
        self._success_tools = success_tools or CustomerSuccessTools(company_id=company_id)
        self._workflows: Dict[str, CustomerSuccessResult] = {}

        logger.info({
            "event": "customer_success_workflow_initialized",
            "company_id": str(company_id) if company_id else None,
            "variant": "parwa_high",
            "tier": "heavy",
        })

    async def execute(
        self,
        customer_id: str
    ) -> Dict[str, Any]:
        """
        Execute the complete customer success workflow.

        Runs through all steps of customer success analysis:
        1. Get health score
        2. Predict churn risk
        3. Suggest retention actions
        4. Track engagement

        CRITICAL: Returns churn_risk with risk_score and factors

        Args:
            customer_id: Customer identifier

        Returns:
            Dict with:
                - health_score: float (0-100)
                - churn_risk: Dict with risk_score and factors
                - actions: List of recommended actions
                - engagement: Engagement metrics
        """
        workflow_id = f"cs_{customer_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        start_time = datetime.now(timezone.utc)

        logger.info({
            "event": "customer_success_workflow_started",
            "workflow_id": workflow_id,
            "customer_id": customer_id,
        })

        # Initialize result
        result = CustomerSuccessResult(
            workflow_id=workflow_id,
            customer_id=customer_id,
            status=CustomerSuccessStatus.PENDING,
        )
        self._workflows[workflow_id] = result

        try:
            # Step 1: Get health score
            result.status = CustomerSuccessStatus.ANALYZING
            health_score = await self._success_tools.calculate_health_score(customer_id)
            result.health_score = health_score

            # Step 2: Predict churn risk (CRITICAL)
            result.status = CustomerSuccessStatus.PREDICTING
            churn_risk = await self._success_tools.predict_churn_risk(customer_id)
            result.churn_risk = churn_risk  # CRITICAL: contains risk_score and factors

            # Step 3: Suggest retention actions
            result.status = CustomerSuccessStatus.RECOMMENDING
            actions = await self._success_tools.get_retention_actions(customer_id)
            result.actions = actions

            # Step 4: Track engagement
            result.status = CustomerSuccessStatus.TRACKING
            engagement = await self._success_tools.track_engagement(customer_id)
            result.engagement = engagement

            result.status = CustomerSuccessStatus.COMPLETED
            result.completed_at = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            result.status = CustomerSuccessStatus.ERROR
            logger.error({
                "event": "customer_success_workflow_error",
                "workflow_id": workflow_id,
                "error": str(e),
            })

        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        logger.info({
            "event": "customer_success_workflow_completed",
            "workflow_id": workflow_id,
            "customer_id": customer_id,
            "health_score": result.health_score,
            "churn_risk_score": result.churn_risk.get("risk_score") if result.churn_risk else None,
            "action_count": len(result.actions),
            "execution_time_ms": execution_time,
        })

        return {
            "success": result.status == CustomerSuccessStatus.COMPLETED,
            "workflow_id": workflow_id,
            "customer_id": customer_id,
            "health_score": result.health_score,
            "churn_risk": result.churn_risk,  # CRITICAL: contains risk_score and factors
            "actions": result.actions,
            "engagement": result.engagement,
            "execution_time_ms": execution_time,
            "metadata": {
                "variant": "parwa_high",
                "tier": "heavy",
                "status": result.status.value,
            },
        }

    async def get_churn_prediction(
        self,
        customer_id: str
    ) -> Dict[str, Any]:
        """
        Get churn prediction for a specific customer.

        Convenience method that only runs churn prediction.

        CRITICAL: Returns dict with risk_score and factors

        Args:
            customer_id: Customer identifier

        Returns:
            Dict with risk_score, factors, risk_level, recommendations
        """
        return await self._success_tools.predict_churn_risk(customer_id)

    async def get_health_assessment(
        self,
        customer_id: str
    ) -> Dict[str, Any]:
        """
        Get health assessment for a specific customer.

        Args:
            customer_id: Customer identifier

        Returns:
            Dict with health_score and status
        """
        score = await self._success_tools.calculate_health_score(customer_id)
        return {
            "customer_id": customer_id,
            "health_score": score,
            "status": "healthy" if score >= 70 else "at_risk",
            "metadata": {
                "variant": "parwa_high",
                "tier": "heavy",
            },
        }

    async def get_retention_plan(
        self,
        customer_id: str
    ) -> Dict[str, Any]:
        """
        Get retention plan for a customer.

        Generates a comprehensive retention plan including
        health score, churn risk, and recommended actions.

        Args:
            customer_id: Customer identifier

        Returns:
            Dict with full retention plan
        """
        # Run full workflow
        result = await self.execute(customer_id)

        # Generate plan summary
        plan = {
            "customer_id": customer_id,
            "health_score": result.get("health_score", 0),
            "churn_risk": result.get("churn_risk", {}),
            "priority_actions": result.get("actions", [])[:3],
            "all_actions": result.get("actions", []),
            "engagement_summary": self._summarize_engagement(result.get("engagement")),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "variant": "parwa_high",
                "tier": "heavy",
            },
        }

        logger.info({
            "event": "retention_plan_generated",
            "customer_id": customer_id,
            "health_score": plan["health_score"],
            "churn_risk_score": plan["churn_risk"].get("risk_score") if plan["churn_risk"] else None,
        })

        return plan

    def _summarize_engagement(
        self,
        engagement: Optional[Dict[str, Any]]
    ) -> str:
        """Summarize engagement metrics into a brief summary."""
        if not engagement:
            return "No engagement data available"

        metrics = engagement.get("metrics", {})
        trends = engagement.get("trends", {})

        parts = []

        logins = metrics.get("logins_last_30d", 0)
        if logins >= 20:
            parts.append("High engagement")
        elif logins >= 10:
            parts.append("Moderate engagement")
        else:
            parts.append("Low engagement")

        login_trend = trends.get("login_trend", "stable")
        if login_trend == "improving":
            parts.append("with improving trend")
        elif login_trend == "declining":
            parts.append("with declining trend")

        return " ".join(parts)

    def get_variant(self) -> str:
        """Get variant name."""
        return "parwa_high"

    def get_tier(self) -> str:
        """Get AI tier used."""
        return "heavy"

    def get_workflow_name(self) -> str:
        """Get workflow name."""
        return "CustomerSuccessWorkflow"
