"""
PARWA Refund Recommendation Tools.

Tool for analyzing refund requests and generating APPROVE/REVIEW/DENY
recommendations with detailed reasoning.

CRITICAL: This tool NEVER calls Paddle directly. All recommendations
create a pending_approval record for human review.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class RefundDecision(str, Enum):
    """Refund decision values."""
    APPROVE = "APPROVE"
    REVIEW = "REVIEW"
    DENY = "DENY"


class RefundRecommendationTool:
    """
    Tool for generating refund recommendations.

    Analyzes refund requests and provides APPROVE/REVIEW/DENY
    recommendations with detailed reasoning.

    CRITICAL: This tool NEVER calls Paddle directly. It only
    creates recommendations and pending_approval records.

    Features:
    - Fraud indicator detection
    - Customer history analysis
    - Amount-based thresholds
    - Detailed reasoning generation
    """

    # Thresholds for recommendations
    AUTO_APPROVE_THRESHOLD = 100.0  # Auto-approve under $100
    REVIEW_THRESHOLD = 500.0       # Review required over $500
    PARWA_LIMIT = 500.0            # PARWA max refund limit

    def __init__(
        self,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize Refund Recommendation Tool.

        Args:
            company_id: Company UUID for data isolation
        """
        self._company_id = company_id
        self._analyses: Dict[str, Dict[str, Any]] = {}

    async def analyze(
        self,
        refund_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze a refund request.

        Performs comprehensive analysis including:
        - Fraud indicator detection
        - Customer history review
        - Order validation
        - Amount thresholds

        Args:
            refund_data: Dict with order_id, amount, customer_id, etc.

        Returns:
            Analysis dict with indicators and risk score
        """
        order_id = refund_data.get("order_id", "unknown")
        amount = float(refund_data.get("amount", 0))
        customer_id = refund_data.get("customer_id")
        reason = refund_data.get("reason", "")

        analysis_id = f"analysis_{order_id}"
        risk_score = 0.0
        indicators: List[Dict[str, Any]] = []

        # Check amount thresholds
        if amount > self.REVIEW_THRESHOLD:
            risk_score += 0.3
            indicators.append({
                "type": "high_amount",
                "detail": f"Amount ${amount:.2f} exceeds review threshold ${self.REVIEW_THRESHOLD}",
                "risk_contribution": 0.3,
            })

        # Check for fraud indicators
        fraud_check = self._check_fraud_indicators(refund_data)
        if fraud_check["detected"]:
            risk_score += 0.5
            indicators.append({
                "type": "fraud_indicators",
                "detail": fraud_check["indicators"],
                "risk_contribution": 0.5,
            })

        # Check customer history
        history_check = self._check_customer_history(refund_data)
        if history_check["risk_increase"] > 0:
            risk_score += history_check["risk_increase"]
            indicators.append({
                "type": "customer_history",
                "detail": history_check["detail"],
                "risk_contribution": history_check["risk_increase"],
            })

        # Check reason quality
        reason_check = self._check_reason_quality(reason)
        if reason_check["risk_increase"] > 0:
            risk_score += reason_check["risk_increase"]
            indicators.append({
                "type": "reason_quality",
                "detail": reason_check["detail"],
                "risk_contribution": reason_check["risk_increase"],
            })

        # Cap risk score at 1.0
        risk_score = min(1.0, risk_score)

        analysis = {
            "analysis_id": analysis_id,
            "order_id": order_id,
            "amount": amount,
            "customer_id": customer_id,
            "risk_score": risk_score,
            "indicators": indicators,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

        self._analyses[analysis_id] = analysis

        logger.info({
            "event": "refund_analyzed",
            "analysis_id": analysis_id,
            "order_id": order_id,
            "amount": amount,
            "risk_score": risk_score,
            "indicator_count": len(indicators),
        })

        return analysis

    def get_recommendation(
        self,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate refund recommendation from analysis.

        CRITICAL: This creates a recommendation only. It does NOT
        call Paddle or process any refund.

        Args:
            analysis: Analysis dict from analyze()

        Returns:
            Dict with recommendation, reasoning, and confidence
        """
        risk_score = analysis.get("risk_score", 0.0)
        amount = analysis.get("amount", 0.0)
        indicators = analysis.get("indicators", [])

        # Determine recommendation
        if risk_score >= 0.7:
            recommendation = RefundDecision.DENY.value
            confidence = 0.85
        elif risk_score >= 0.3:
            recommendation = RefundDecision.REVIEW.value
            confidence = 0.65
        else:
            recommendation = RefundDecision.APPROVE.value
            confidence = 0.90

        # Generate reasoning
        reasoning = self._generate_reasoning(
            recommendation, risk_score, amount, indicators
        )

        # Check PARWA limit
        if amount > self.PARWA_LIMIT:
            # Must escalate - exceeds PARWA's authority
            recommendation = RefundDecision.REVIEW.value
            reasoning += f" Amount ${amount:.2f} exceeds PARWA limit of ${self.PARWA_LIMIT:.2f}. Requires manager approval."
            confidence = 0.95

        result = {
            "recommendation": recommendation,
            "reasoning": reasoning,
            "confidence": confidence,
            "risk_score": risk_score,
            "amount": amount,
            "indicators_count": len(indicators),
            # CRITICAL: Never call Paddle directly
            "payment_processor_called": False,
            "requires_pending_approval": True,
        }

        logger.info({
            "event": "refund_recommendation_generated",
            "recommendation": recommendation,
            "amount": amount,
            "confidence": confidence,
            "payment_processor_called": False,
        })

        return result

    def _check_fraud_indicators(
        self,
        refund_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check for fraud indicators."""
        indicators: List[str] = []

        # Check for suspicious patterns
        if refund_data.get("multiple_refund_attempts"):
            indicators.append("Multiple refund attempts detected")

        if refund_data.get("account_age_days", 365) < 7:
            indicators.append("Very new account")

        if refund_data.get("different_payment_method"):
            indicators.append("Different payment method than original")

        return {
            "detected": len(indicators) > 0,
            "indicators": indicators,
        }

    def _check_customer_history(
        self,
        refund_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check customer history for risk factors."""
        risk_increase = 0.0
        details: List[str] = []

        previous_refunds = refund_data.get("previous_refunds", 0)
        if previous_refunds > 3:
            risk_increase += 0.2
            details.append(f"High refund count: {previous_refunds}")

        if refund_data.get("previous_disputes", 0) > 0:
            risk_increase += 0.15
            details.append("Previous disputes on record")

        return {
            "risk_increase": min(risk_increase, 0.4),
            "detail": details,
        }

    def _check_reason_quality(self, reason: str) -> Dict[str, Any]:
        """Check quality of refund reason."""
        risk_increase = 0.0
        detail = ""

        if not reason or len(reason) < 5:
            risk_increase += 0.1
            detail = "Very short or missing reason"
        elif reason.lower() in ["don't want", "changed mind", "just because"]:
            risk_increase += 0.05
            detail = f"Generic reason: '{reason}'"

        return {
            "risk_increase": risk_increase,
            "detail": detail,
        }

    def _generate_reasoning(
        self,
        recommendation: str,
        risk_score: float,
        amount: float,
        indicators: List[Dict[str, Any]]
    ) -> str:
        """Generate human-readable reasoning."""
        parts: List[str] = []

        if recommendation == RefundDecision.APPROVE.value:
            parts.append(f"Refund of ${amount:.2f} meets approval criteria.")
            parts.append(f"Risk score is low ({risk_score:.2f}).")
        elif recommendation == RefundDecision.REVIEW.value:
            parts.append(f"Refund of ${amount:.2f} requires manual review.")
            parts.append(f"Risk score is moderate ({risk_score:.2f}).")
        else:
            parts.append(f"Refund of ${amount:.2f} is not recommended.")
            parts.append(f"Risk score is high ({risk_score:.2f}).")

        # Add indicator details
        if indicators:
            parts.append("Factors considered:")
            for ind in indicators[:3]:
                if isinstance(ind.get("detail"), list):
                    parts.append(f"  - {ind['type']}: {', '.join(ind['detail'])}")
                else:
                    parts.append(f"  - {ind.get('detail', ind.get('type', 'Unknown'))}")

        return " ".join(parts)

    async def execute(
        self,
        action: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Execute a refund recommendation action.

        Args:
            action: Action (analyze, recommend)
            **kwargs: Action-specific arguments

        Returns:
            Result dict
        """
        if action == "analyze":
            return await self.analyze(kwargs.get("refund_data", {}))
        elif action == "recommend":
            analysis = kwargs.get("analysis", {})
            if not analysis:
                # Run analysis first
                analysis = await self.analyze(kwargs.get("refund_data", {}))
            return self.get_recommendation(analysis)
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}
