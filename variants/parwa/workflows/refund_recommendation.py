"""
PARWA Junior Refund Recommendation Workflow.

Handles refund request processing with full APPROVE/REVIEW/DENY reasoning.
CRITICAL: This workflow NEVER calls Paddle directly.
It creates pending_approval records for human review with full reasoning.

PARWA Junior Features:
- Refund limit: $500
- Returns APPROVE/REVIEW/DENY with detailed reasoning
- Uses Medium AI tier for sophisticated analysis
- Escalation threshold: 60% confidence
- Creates pending_approval for ALL refunds
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, field

from variants.parwa.config import ParwaConfig, get_parwa_config
from variants.parwa.anti_arbitrage_config import ParwaAntiArbitrageConfig
from variants.base_agents.base_refund_agent import RefundRecommendation
from shared.core_functions.logger import get_logger
from shared.core_functions.config import get_settings
from shared.integrations.paddle_client import PaddleClient

logger = get_logger(__name__)


class RefundDecision(Enum):
    """Refund decision types for PARWA."""
    APPROVE = "APPROVE"  # Recommend approval
    REVIEW = "REVIEW"    # Needs manual review
    DENY = "DENY"        # Deny with reason


@dataclass
class RefundReasoning:
    """Detailed reasoning for refund recommendation."""
    decision: RefundDecision
    confidence: float
    primary_reason: str
    supporting_factors: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    policy_references: List[str] = field(default_factory=list)
    recommendation_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RefundRecommendationResult:
    """Result from refund recommendation workflow."""
    success: bool
    approval_id: Optional[str] = None
    decision: RefundDecision = RefundDecision.REVIEW
    reasoning: Optional[RefundReasoning] = None
    amount: Decimal = Decimal("0.00")
    within_parwa_limit: bool = True
    requires_escalation: bool = False
    paddle_called: bool = False  # CRITICAL: Always False
    estimated_processing_days: int = 3
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class RefundRecommendationWorkflow:
    """
    Workflow for processing refund recommendations with full reasoning.

    PARWA Junior-specific logic:
    - Maximum refund: $500
    - Auto-approve threshold: $100 (still creates pending_approval)
    - Review threshold: $250
    - Returns APPROVE/REVIEW/DENY with FULL REASONING
    - Escalation threshold: 60% confidence

    CRITICAL: This workflow NEVER calls Paddle directly.
    All refunds require pending_approval creation.

    Example:
        workflow = RefundRecommendationWorkflow()
        result = await workflow.execute({
            "order_id": "ord_123",
            "amount": 150.00,
            "customer_id": "cust_456",
            "reason": "Product not as described"
        })
        # result.decision = RefundDecision.REVIEW
        # result.reasoning.primary_reason = "Amount requires verification..."
    """

    # PARWA Junior refund limits
    PARWA_REFUND_LIMIT = Decimal("500.00")
    AUTO_APPROVE_THRESHOLD = Decimal("100.00")
    REVIEW_THRESHOLD = Decimal("250.00")

    # Time windows
    REFUND_WINDOW_DAYS = 30
    EXTENDED_WINDOW_DAYS = 60  # VIP customers

    def __init__(
        self,
        parwa_config: Optional[ParwaConfig] = None,
        anti_arbitrage_config: Optional[ParwaAntiArbitrageConfig] = None,
    ) -> None:
        """
        Initialize refund recommendation workflow.

        Args:
            parwa_config: PARWA Junior configuration
            anti_arbitrage_config: Anti-arbitrage configuration
        """
        self._config = parwa_config or get_parwa_config()
        self._anti_arbitrage = anti_arbitrage_config or ParwaAntiArbitrageConfig()
        self._paddle_client = PaddleClient()  # For lookup only, NOT for refunds
        self._pending_approvals: Dict[str, Dict[str, Any]] = {}

    async def execute(self, refund_data: Dict[str, Any]) -> RefundRecommendationResult:
        """
        Execute the refund recommendation workflow.

        CRITICAL: This creates pending_approval and NEVER
        calls Paddle directly for refunds.

        Args:
            refund_data: Dict with:
                - order_id: Order identifier
                - amount: Refund amount
                - reason: Refund reason
                - customer_id: Customer identifier
                - customer_email: Customer email
                - customer_history: Optional customer history info
                - order_age_days: Optional order age in days

        Returns:
            RefundRecommendationResult with full reasoning
        """
        order_id = refund_data.get("order_id", "")
        amount = Decimal(str(refund_data.get("amount", 0)))
        reason = refund_data.get("reason", "Customer request")
        customer_id = refund_data.get("customer_id", "")
        customer_email = refund_data.get("customer_email", "")
        customer_history = refund_data.get("customer_history", {})
        order_age_days = refund_data.get("order_age_days", 0)

        logger.info({
            "event": "refund_recommendation_workflow_started",
            "order_id": order_id,
            "amount": str(amount),
            "customer_id": customer_id,
            "variant": "parwa",
        })

        # Step 1: Validate amount against PARWA limit
        if amount > self.PARWA_REFUND_LIMIT:
            return self._create_over_limit_result(order_id, amount)

        # Step 2: Gather context for decision
        context = await self._gather_decision_context(
            order_id, amount, customer_id, customer_history, refund_data
        )

        # Step 3: Generate recommendation with full reasoning
        recommendation = self._generate_recommendation(
            amount=amount,
            order_age_days=order_age_days,
            customer_history=customer_history,
            context=context,
            refund_data=refund_data,
        )

        # Step 4: Create pending approval (CRITICAL: never calls Paddle)
        approval = await self._create_pending_approval(
            order_id=order_id,
            amount=amount,
            reason=reason,
            customer_id=customer_id,
            customer_email=customer_email,
            recommendation=recommendation,
        )

        # Step 5: Determine if escalation needed
        needs_escalation = self._should_escalate(
            recommendation.decision,
            recommendation.confidence,
            amount,
        )

        # Log CRITICAL verification
        logger.info({
            "event": "refund_recommendation_complete",
            "approval_id": approval["approval_id"],
            "order_id": order_id,
            "amount": str(amount),
            "decision": recommendation.decision.value,
            "confidence": recommendation.confidence,
            "within_parwa_limit": amount <= self.PARWA_REFUND_LIMIT,
            # CRITICAL: Explicitly log no processor call
            "paddle_called": False,
            "payment_processor_called": False,
        })

        return RefundRecommendationResult(
            success=True,
            approval_id=approval["approval_id"],
            decision=recommendation.decision,
            reasoning=recommendation,
            amount=amount,
            within_parwa_limit=amount <= self.PARWA_REFUND_LIMIT,
            requires_escalation=needs_escalation,
            paddle_called=False,  # CRITICAL: Always False
            estimated_processing_days=self._get_processing_days(recommendation.decision),
            message=self._format_message(recommendation, amount),
            metadata={
                "variant": "parwa",
                "tier": "medium",
                "config_limit": float(self.PARWA_REFUND_LIMIT),
                "escalation_threshold": self._config.escalation_threshold,
            },
        )

    async def _gather_decision_context(
        self,
        order_id: str,
        amount: Decimal,
        customer_id: str,
        customer_history: Dict[str, Any],
        refund_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Gather context for decision making.

        Args:
            order_id: Order identifier
            amount: Refund amount
            customer_id: Customer identifier
            customer_history: Customer history data
            refund_data: Full refund request data

        Returns:
            Dict with decision context
        """
        context = {
            "order_id": order_id,
            "amount": float(amount),
            "customer_id": customer_id,
            "is_first_refund": customer_history.get("total_refunds", 0) == 0,
            "total_refunds": customer_history.get("total_refunds", 0),
            "customer_tier": customer_history.get("tier", "standard"),
            "fraud_indicators": refund_data.get("fraud_indicators", False),
            "order_verified": refund_data.get("order_verified", True),
            "has_previous_disputes": customer_history.get("dispute_count", 0) > 0,
        }

        # Check for VIP status
        if context["customer_tier"] == "vip":
            context["extended_window"] = True
            context["refund_window_days"] = self.EXTENDED_WINDOW_DAYS
        else:
            context["extended_window"] = False
            context["refund_window_days"] = self.REFUND_WINDOW_DAYS

        # Calculate risk score
        context["risk_score"] = self._calculate_risk_score(context)

        return context

    def _calculate_risk_score(self, context: Dict[str, Any]) -> float:
        """
        Calculate risk score for the refund request.

        Args:
            context: Decision context

        Returns:
            Risk score between 0.0 (low risk) and 1.0 (high risk)
        """
        risk = 0.0

        # High refund count increases risk
        total_refunds = context.get("total_refunds", 0)
        if total_refunds > 5:
            risk += 0.3
        elif total_refunds > 3:
            risk += 0.2
        elif total_refunds > 1:
            risk += 0.1

        # Previous disputes increase risk
        if context.get("has_previous_disputes", False):
            risk += 0.25

        # Fraud indicators significantly increase risk
        if context.get("fraud_indicators", False):
            risk += 0.5

        # First-time customer with high amount
        if context.get("is_first_refund", True) and context.get("amount", 0) > 300:
            risk += 0.15

        return min(1.0, risk)

    def _generate_recommendation(
        self,
        amount: Decimal,
        order_age_days: int,
        customer_history: Dict[str, Any],
        context: Dict[str, Any],
        refund_data: Dict[str, Any],
    ) -> RefundReasoning:
        """
        Generate refund recommendation with full reasoning.

        Args:
            amount: Refund amount
            order_age_days: Order age in days
            customer_history: Customer history
            context: Decision context
            refund_data: Full refund data

        Returns:
            RefundReasoning with decision and reasoning
        """
        supporting_factors: List[str] = []
        risk_factors: List[str] = []
        policy_references: List[str] = []

        # Check for fraud indicators - always DENY
        if context.get("fraud_indicators", False):
            risk_factors.append("Fraud indicators detected in request")
            policy_references.append("Anti-Fraud Policy Section 4.2")
            return RefundReasoning(
                decision=RefundDecision.DENY,
                confidence=0.95,
                primary_reason="Transaction flagged for security review due to fraud indicators",
                supporting_factors=["Security system detected suspicious patterns"],
                risk_factors=risk_factors,
                policy_references=policy_references,
                recommendation_details={"fraud_check": "failed"},
            )

        # Check order age
        refund_window = context.get("refund_window_days", self.REFUND_WINDOW_DAYS)
        if order_age_days > refund_window:
            risk_factors.append(f"Order age ({order_age_days} days) exceeds refund window ({refund_window} days)")
            policy_references.append(f"Refund Policy: {refund_window}-day window")
            return RefundReasoning(
                decision=RefundDecision.REVIEW,
                confidence=0.7,
                primary_reason=f"Order exceeds standard {refund_window}-day refund window",
                supporting_factors=["Requires manager approval for policy exception"],
                risk_factors=risk_factors,
                policy_references=policy_references,
                recommendation_details={"window_exceeded": True, "days_over": order_age_days - refund_window},
            )

        # Check risk score
        risk_score = context.get("risk_score", 0)
        if risk_score > 0.5:
            risk_factors.append(f"Elevated risk score: {risk_score:.2f}")
            return RefundReasoning(
                decision=RefundDecision.REVIEW,
                confidence=0.65,
                primary_reason="Elevated risk factors detected requiring manual review",
                supporting_factors=["Multiple risk indicators present"],
                risk_factors=risk_factors,
                policy_references=["Risk Assessment Policy Section 2.1"],
                recommendation_details={"risk_score": risk_score, "manual_review_required": True},
            )

        # First refund, small amount - APPROVE territory
        if context.get("is_first_refund", True) and amount <= self.AUTO_APPROVE_THRESHOLD:
            supporting_factors.append("First-time refund request from customer")
            supporting_factors.append(f"Amount ${amount:.2f} within auto-approve threshold")
            supporting_factors.append("Customer has no prior refund history")
            policy_references.append("First-Time Customer Policy Section 1.3")
            return RefundReasoning(
                decision=RefundDecision.APPROVE,
                confidence=0.90,
                primary_reason="First-time refund within auto-approve threshold meets all criteria",
                supporting_factors=supporting_factors,
                risk_factors=risk_factors,
                policy_references=policy_references,
                recommendation_details={"auto_approve_eligible": True, "first_refund": True},
            )

        # VIP customer - prioritize
        if context.get("customer_tier") == "vip":
            supporting_factors.append("VIP customer status")
            if amount <= self.REVIEW_THRESHOLD:
                supporting_factors.append(f"Amount ${amount:.2f} within VIP expedited threshold")
                policy_references.append("VIP Customer Policy Section 3.1")
                return RefundReasoning(
                    decision=RefundDecision.APPROVE,
                    confidence=0.85,
                    primary_reason="VIP customer eligible for expedited refund processing",
                    supporting_factors=supporting_factors,
                    risk_factors=risk_factors,
                    policy_references=policy_references,
                    recommendation_details={"vip_expedited": True},
                )

        # Medium amount, first refund - REVIEW with good confidence
        if context.get("is_first_refund", True) and amount <= self.REVIEW_THRESHOLD:
            supporting_factors.append("First-time refund request")
            supporting_factors.append(f"Amount ${amount:.2f} within review threshold")
            supporting_factors.append("Standard verification process recommended")
            policy_references.append("Standard Refund Process Section 2.4")
            return RefundReasoning(
                decision=RefundDecision.REVIEW,
                confidence=0.75,
                primary_reason="First-time refund requiring standard verification process",
                supporting_factors=supporting_factors,
                risk_factors=risk_factors,
                policy_references=policy_references,
                recommendation_details={"standard_review": True, "verification_required": True},
            )

        # High-value refund (>$250)
        if amount > self.REVIEW_THRESHOLD:
            supporting_factors.append(f"High-value refund request: ${amount:.2f}")
            supporting_factors.append("Enhanced verification process required")
            if context.get("customer_tier") == "vip":
                supporting_factors.append("VIP customer - priority review")
            policy_references.append("High-Value Refund Policy Section 5.1")
            return RefundReasoning(
                decision=RefundDecision.REVIEW,
                confidence=0.70,
                primary_reason="High-value refund requiring enhanced verification and approval",
                supporting_factors=supporting_factors,
                risk_factors=risk_factors,
                policy_references=policy_references,
                recommendation_details={"high_value": True, "enhanced_verification": True},
            )

        # Default case - standard review
        supporting_factors.append("Standard refund request")
        supporting_factors.append("Requires verification process")
        return RefundReasoning(
            decision=RefundDecision.REVIEW,
            confidence=0.70,
            primary_reason="Standard refund request requiring verification",
            supporting_factors=supporting_factors,
            risk_factors=risk_factors,
            policy_references=["Standard Refund Policy Section 2.1"],
            recommendation_details={"standard_review": True},
        )

    async def _create_pending_approval(
        self,
        order_id: str,
        amount: Decimal,
        reason: str,
        customer_id: str,
        customer_email: str,
        recommendation: RefundReasoning,
    ) -> Dict[str, Any]:
        """
        Create a pending approval record.

        CRITICAL: This method ONLY creates a pending_approval record.
        It does NOT and MUST NOT call Paddle directly.

        Args:
            order_id: Order identifier
            amount: Refund amount
            reason: Refund reason
            customer_id: Customer identifier
            customer_email: Customer email
            recommendation: Refund recommendation with reasoning

        Returns:
            Dict with approval_id and status
        """
        approval_id = f"parwa_appr_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{order_id}"

        approval_record = {
            "approval_id": approval_id,
            "order_id": order_id,
            "amount": float(amount),
            "reason": reason,
            "customer_id": customer_id,
            "customer_email": customer_email,
            "decision": recommendation.decision.value,
            "confidence": recommendation.confidence,
            "primary_reason": recommendation.primary_reason,
            "supporting_factors": recommendation.supporting_factors,
            "risk_factors": recommendation.risk_factors,
            "policy_references": recommendation.policy_references,
            "variant": "parwa",
            "tier": "medium",
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            # CRITICAL: Explicitly track no Paddle call
            "paddle_called": False,
            "payment_processor_called": False,
        }

        # Store in memory (in production, this would go to database)
        self._pending_approvals[approval_id] = approval_record

        logger.info({
            "event": "parwa_pending_approval_created",
            "approval_id": approval_id,
            "order_id": order_id,
            "amount": str(amount),
            "decision": recommendation.decision.value,
            # CRITICAL: Log no processor call
            "paddle_called": False,
        })

        return {
            "approval_id": approval_id,
            "status": "pending",
            "decision": recommendation.decision.value,
            "parwa_limit": float(self.PARWA_REFUND_LIMIT),
            "within_limit": amount <= self.PARWA_REFUND_LIMIT,
        }

    def _should_escalate(
        self,
        decision: RefundDecision,
        confidence: float,
        amount: Decimal,
    ) -> bool:
        """
        Determine if escalation is needed.

        Args:
            decision: Refund decision
            confidence: Confidence score
            amount: Refund amount

        Returns:
            True if escalation needed
        """
        # Low confidence triggers escalation
        if confidence < self._config.escalation_threshold:
            return True

        # Amount over limit (shouldn't happen, but safety check)
        if amount > self.PARWA_REFUND_LIMIT:
            return True

        # Deny decisions may need escalation for appeals
        if decision == RefundDecision.DENY:
            return True

        return False

    def _create_over_limit_result(
        self,
        order_id: str,
        amount: Decimal,
    ) -> RefundRecommendationResult:
        """Create result for over-limit refund."""
        return RefundRecommendationResult(
            success=True,
            decision=RefundDecision.REVIEW,
            reasoning=RefundReasoning(
                decision=RefundDecision.REVIEW,
                confidence=0.5,
                primary_reason=f"Amount ${amount:.2f} exceeds PARWA Junior limit of ${self.PARWA_REFUND_LIMIT:.2f}",
                supporting_factors=["Requires escalation to PARWA High or manual review"],
                risk_factors=[],
                policy_references=["Tier Limit Policy Section 4.1"],
                recommendation_details={"exceeds_limit": True},
            ),
            amount=amount,
            within_parwa_limit=False,
            requires_escalation=True,
            paddle_called=False,
            message=f"Refund amount ${amount:.2f} exceeds PARWA Junior limit. Escalating for review.",
            metadata={"escalation_target": "parwa_high"},
        )

    def _get_processing_days(self, decision: RefundDecision) -> int:
        """Get estimated processing days based on decision."""
        if decision == RefundDecision.APPROVE:
            return 2  # Faster for approved
        elif decision == RefundDecision.DENY:
            return 5  # Slower for denied (appeal window)
        return 3  # Standard for review

    def _format_message(
        self,
        recommendation: RefundReasoning,
        amount: Decimal,
    ) -> str:
        """Format user-facing message."""
        if recommendation.decision == RefundDecision.APPROVE:
            return f"Refund request for ${amount:.2f} has been recommended for approval. {recommendation.primary_reason}"
        elif recommendation.decision == RefundDecision.DENY:
            return f"Refund request cannot be processed. {recommendation.primary_reason}"
        return f"Refund request for ${amount:.2f} is pending review. {recommendation.primary_reason}"

    async def check_approval_status(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """
        Check status of a pending approval.

        Args:
            approval_id: Approval identifier

        Returns:
            Approval status or None if not found
        """
        return self._pending_approvals.get(approval_id)

    def get_workflow_name(self) -> str:
        """Get workflow name."""
        return "RefundRecommendationWorkflow"

    def get_variant(self) -> str:
        """Get variant name."""
        return "parwa"

    def get_tier(self) -> str:
        """Get AI tier used."""
        return "medium"
