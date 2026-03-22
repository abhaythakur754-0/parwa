"""
PARWA TRIVYA Tier 3 Trigger Detector.

Analyzes queries and context to determine if Tier 3 advanced reasoning
techniques should be activated. T3 only fires on HIGH-STAKES scenarios.

Trigger Conditions (ALL must be met):
1. VIP Customer - High-value customer requiring premium handling
2. Transaction Amount > $100 - Significant financial impact
3. Anger Level > 80% - High emotional intensity detected

This conservative triggering ensures expensive T3 techniques are only
used when truly necessary for customer retention and satisfaction.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class T3TriggerType(str, Enum):
    """Types of T3 technique triggers."""
    GST = "gst"  # Generated Step-by-step Thought
    UNIVERSE_OF_THOUGHTS = "universe_of_thoughts"
    TREE_OF_THOUGHTS = "tree_of_thoughts"
    SELF_CONSISTENCY = "self_consistency"
    REFLEXION = "reflexion"
    LEAST_TO_MOST = "least_to_most"
    NONE = "none"


class HighStakesIndicator(str, Enum):
    """Indicators that contribute to high-stakes determination."""
    VIP_CUSTOMER = "vip_customer"
    HIGH_AMOUNT = "high_amount"
    HIGH_ANGER = "high_anger"
    ESCALATION_RISK = "escalation_risk"
    COMPLAINT_HISTORY = "complaint_history"
    SOCIAL_MEDIA_THREAT = "social_media_threat"
    LEGAL_MENTION = "legal_mention"


class T3TriggerResult(BaseModel):
    """Result from T3 trigger detection."""
    query: str
    should_fire_t3: bool = False
    triggered_techniques: List[T3TriggerType] = Field(default_factory=list)
    primary_technique: T3TriggerType = T3TriggerType.NONE
    high_stakes_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Individual trigger conditions
    is_vip: bool = False
    amount_exceeds_threshold: bool = False
    anger_exceeds_threshold: bool = False

    # Detailed indicators
    indicators: Dict[str, Any] = Field(default_factory=dict)
    risk_factors: List[str] = Field(default_factory=list)

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = ""
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class T3TriggerConfig(BaseModel):
    """Configuration for T3 trigger detection."""
    # Trigger thresholds
    vip_required: bool = Field(default=True)
    amount_threshold: float = Field(default=100.0)  # $100
    anger_threshold: float = Field(default=0.80)  # 80%

    # Require ALL conditions (AND logic) vs ANY condition (OR logic)
    require_all_conditions: bool = Field(default=True)

    # Additional risk factor weights
    escalation_risk_weight: float = Field(default=0.3)
    complaint_history_weight: float = Field(default=0.2)
    social_threat_weight: float = Field(default=0.25)
    legal_mention_weight: float = Field(default=0.4)

    # High stakes score threshold for fallback triggering
    high_stakes_score_threshold: float = Field(default=0.7)

    model_config = ConfigDict()


class T3TriggerDetector:
    """
    Tier 3 Trigger Detector for TRIVYA.

    Determines when advanced reasoning techniques should be activated.
    T3 is EXPENSIVE and should only fire in high-stakes scenarios.

    Trigger Logic (conservative):
    - ALL conditions must be met: VIP + Amount>$100 + Anger>80%
    - OR high_stakes_score > threshold with multiple risk factors

    Techniques are selected based on query characteristics:
    - Complex multi-step -> GST + Least-to-Most
    - Multiple solutions possible -> Universe of Thoughts + Tree of Thoughts
    - High uncertainty -> Self-Consistency + Reflexion
    """

    def __init__(self, config: Optional[T3TriggerConfig] = None) -> None:
        """
        Initialize T3 Trigger Detector.

        Args:
            config: Optional configuration override
        """
        self.config = config or T3TriggerConfig()

        # Performance tracking
        self._queries_analyzed = 0
        self._t3_activations = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "t3_trigger_detector_initialized",
            "amount_threshold": self.config.amount_threshold,
            "anger_threshold": self.config.anger_threshold,
            "require_all_conditions": self.config.require_all_conditions,
        })

    def detect(
        self,
        query: str,
        is_vip: bool = False,
        transaction_amount: Optional[float] = None,
        anger_level: Optional[float] = None,
        customer_history: Optional[Dict[str, Any]] = None,
        sentiment_result: Optional[Dict[str, Any]] = None,
        context: Optional[str] = None
    ) -> T3TriggerResult:
        """
        Detect if T3 should fire for this query.

        Args:
            query: User query text
            is_vip: Whether customer is VIP status
            transaction_amount: Transaction amount in dollars
            anger_level: Anger/emotion level (0.0-1.0)
            customer_history: Customer history data
            sentiment_result: Result from sentiment analysis
            context: Additional context from T1/T2

        Returns:
            T3TriggerResult with trigger decision and techniques

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()
        query_lower = query.lower().strip()

        # Initialize result
        result = T3TriggerResult(
            query=query,
            is_vip=is_vip,
            amount_exceeds_threshold=(
                transaction_amount is not None and
                transaction_amount > self.config.amount_threshold
            ),
            anger_exceeds_threshold=(
                anger_level is not None and
                anger_level >= self.config.anger_threshold
            )
        )

        # Analyze risk factors
        risk_factors = self._analyze_risk_factors(
            query_lower,
            customer_history,
            sentiment_result,
            context
        )
        result.risk_factors = risk_factors

        # Calculate high-stakes score
        high_stakes_score = self._calculate_high_stakes_score(
            is_vip=is_vip,
            amount=transaction_amount,
            anger=anger_level,
            risk_factors=risk_factors
        )
        result.high_stakes_score = high_stakes_score

        # Determine if T3 should fire
        should_fire = self._should_fire_t3(
            is_vip=is_vip,
            amount=transaction_amount,
            anger=anger_level,
            high_stakes_score=high_stakes_score,
            risk_factors=risk_factors
        )
        result.should_fire_t3 = should_fire

        # If T3 fires, determine which techniques
        if should_fire:
            techniques = self._select_techniques(query_lower, risk_factors)
            result.triggered_techniques = techniques
            result.primary_technique = techniques[0] if techniques else T3TriggerType.NONE
            result.confidence = min(1.0, high_stakes_score + 0.1)
            self._t3_activations += 1

        # Build reasoning
        result.reasoning = self._build_reasoning(result, query_lower)
        result.indicators = {
            "is_vip": is_vip,
            "transaction_amount": transaction_amount,
            "anger_level": anger_level,
            "risk_factor_count": len(risk_factors),
            "high_stakes_score": high_stakes_score,
        }

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._queries_analyzed += 1
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "t3_trigger_detection_complete",
            "should_fire": should_fire,
            "high_stakes_score": high_stakes_score,
            "techniques": [t.value for t in result.triggered_techniques],
            "processing_time_ms": result.processing_time_ms,
        })

        return result

    def should_fire_t3(
        self,
        query: str,
        is_vip: bool = False,
        transaction_amount: Optional[float] = None,
        anger_level: Optional[float] = None
    ) -> bool:
        """
        Quick check if T3 should fire.

        Args:
            query: User query text
            is_vip: VIP status
            transaction_amount: Transaction amount
            anger_level: Anger level (0.0-1.0)

        Returns:
            True if T3 should fire
        """
        if not query or not query.strip():
            return False

        # Check core conditions
        amount_ok = (
            transaction_amount is not None and
            transaction_amount > self.config.amount_threshold
        )
        anger_ok = (
            anger_level is not None and
            anger_level >= self.config.anger_threshold
        )

        if self.config.require_all_conditions:
            # ALL conditions must be met (AND logic)
            return is_vip and amount_ok and anger_ok
        else:
            # ANY condition triggers (OR logic)
            return is_vip or amount_ok or anger_ok

    def get_stats(self) -> Dict[str, Any]:
        """
        Get trigger detector statistics.

        Returns:
            Dict with stats
        """
        return {
            "queries_analyzed": self._queries_analyzed,
            "t3_activations": self._t3_activations,
            "activation_rate": (
                self._t3_activations / self._queries_analyzed
                if self._queries_analyzed > 0 else 0
            ),
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._queries_analyzed
                if self._queries_analyzed > 0 else 0
            ),
        }

    def _analyze_risk_factors(
        self,
        query: str,
        customer_history: Optional[Dict[str, Any]],
        sentiment_result: Optional[Dict[str, Any]],
        context: Optional[str]
    ) -> List[str]:
        """
        Analyze additional risk factors.

        Args:
            query: Lowercase query
            customer_history: Customer history data
            sentiment_result: Sentiment analysis result
            context: Additional context

        Returns:
            List of detected risk factors
        """
        risk_factors = []

        # Check for escalation language
        escalation_patterns = [
            "speak to manager", "supervisor", "escalate", "complaint",
            "report you", "better business bureau", "bbb",
            "never buying again", "cancel my subscription",
            "tell everyone", "review", "social media",
        ]
        if any(p in query for p in escalation_patterns):
            risk_factors.append(HighStakesIndicator.ESCALATION_RISK.value)

        # Check for legal mentions
        legal_patterns = [
            "lawyer", "attorney", "legal action", "lawsuit",
            "sue", "court", "illegal", "fraud", "scam",
        ]
        if any(p in query for p in legal_patterns):
            risk_factors.append(HighStakesIndicator.LEGAL_MENTION.value)

        # Check for social media threats
        social_patterns = [
            "twitter", "facebook", "instagram", "tiktok",
            "post about", "share this", "viral", "go public",
        ]
        if any(p in query for p in social_patterns):
            risk_factors.append(HighStakesIndicator.SOCIAL_MEDIA_THREAT.value)

        # Check customer history
        if customer_history:
            complaint_count = customer_history.get("complaint_count", 0)
            if complaint_count >= 3:
                risk_factors.append(HighStakesIndicator.COMPLAINT_HISTORY.value)

            # Check for previous escalations
            if customer_history.get("previous_escalations", 0) > 0:
                risk_factors.append(HighStakesIndicator.ESCALATION_RISK.value)

        # Check sentiment result
        if sentiment_result:
            if sentiment_result.get("urgency") == "high":
                risk_factors.append("high_urgency")
            if sentiment_result.get("frustration_level", 0) > 0.7:
                risk_factors.append("high_frustration")

        return risk_factors

    def _calculate_high_stakes_score(
        self,
        is_vip: bool,
        amount: Optional[float],
        anger: Optional[float],
        risk_factors: List[str]
    ) -> float:
        """
        Calculate overall high-stakes score.

        Args:
            is_vip: VIP status
            amount: Transaction amount
            anger: Anger level
            risk_factors: List of risk factors

        Returns:
            High-stakes score (0.0-1.0)
        """
        score = 0.0

        # Core conditions
        if is_vip:
            score += 0.35  # VIP contributes 35%

        if amount is not None and amount > self.config.amount_threshold:
            # Scale amount contribution
            amount_factor = min(1.0, amount / 500)  # Max at $500
            score += 0.30 * amount_factor  # Amount contributes up to 30%

        if anger is not None and anger >= self.config.anger_threshold:
            # Scale anger contribution
            anger_factor = min(1.0, anger / 0.95)  # Max at 95%
            score += 0.35 * anger_factor  # Anger contributes up to 35%

        # Risk factors add to score
        for factor in risk_factors:
            if factor == HighStakesIndicator.LEGAL_MENTION.value:
                score += self.config.legal_mention_weight
            elif factor == HighStakesIndicator.SOCIAL_MEDIA_THREAT.value:
                score += self.config.social_threat_weight
            elif factor == HighStakesIndicator.ESCALATION_RISK.value:
                score += self.config.escalation_risk_weight
            elif factor == HighStakesIndicator.COMPLAINT_HISTORY.value:
                score += self.config.complaint_history_weight
            else:
                score += 0.1  # Default weight for other factors

        return min(1.0, score)

    def _should_fire_t3(
        self,
        is_vip: bool,
        amount: Optional[float],
        anger: Optional[float],
        high_stakes_score: float,
        risk_factors: List[str]
    ) -> bool:
        """
        Determine if T3 should fire.

        Args:
            is_vip: VIP status
            amount: Transaction amount
            anger: Anger level
            high_stakes_score: Calculated high-stakes score
            risk_factors: List of risk factors

        Returns:
            True if T3 should fire
        """
        # Check primary trigger conditions
        amount_ok = (
            amount is not None and
            amount > self.config.amount_threshold
        )
        anger_ok = (
            anger is not None and
            anger >= self.config.anger_threshold
        )

        # Primary path: ALL conditions met (AND logic)
        if self.config.require_all_conditions:
            if is_vip and amount_ok and anger_ok:
                return True

        # Secondary path: High stakes score with multiple risk factors
        if high_stakes_score >= self.config.high_stakes_score_threshold:
            if len(risk_factors) >= 2:  # Multiple risk factors present
                return True

        # Tertiary path: Legal mention always triggers T3
        if HighStakesIndicator.LEGAL_MENTION.value in risk_factors:
            return True

        return False

    def _select_techniques(
        self,
        query: str,
        risk_factors: List[str]
    ) -> List[T3TriggerType]:
        """
        Select which T3 techniques to use.

        Args:
            query: Lowercase query
            risk_factors: List of risk factors

        Returns:
            List of techniques to apply
        """
        techniques = []

        # Always include GST for structured reasoning
        techniques.append(T3TriggerType.GST)

        # Complex problem-solving -> Least-to-Most
        complex_patterns = [
            "how do i", "steps", "process", "complicated",
            "multiple issues", "several problems",
        ]
        if any(p in query for p in complex_patterns):
            techniques.append(T3TriggerType.LEAST_TO_MOST)

        # Decision-making or comparison -> Universe of Thoughts + Self-Consistency
        decision_patterns = [
            "should i", "which", "choose", "decide",
            "better", "best option", "compare",
        ]
        if any(p in query for p in decision_patterns):
            techniques.append(T3TriggerType.UNIVERSE_OF_THOUGHTS)
            techniques.append(T3TriggerType.SELF_CONSISTENCY)

        # Multiple solutions needed -> Tree of Thoughts
        if len(risk_factors) >= 2:
            techniques.append(T3TriggerType.TREE_OF_THOUGHTS)

        # High uncertainty or previous failures -> Reflexion
        if HighStakesIndicator.COMPLAINT_HISTORY.value in risk_factors:
            techniques.append(T3TriggerType.REFLEXION)

        # Legal mentions -> All techniques for thoroughness
        if HighStakesIndicator.LEGAL_MENTION.value in risk_factors:
            for t in T3TriggerType:
                if t not in techniques and t != T3TriggerType.NONE:
                    techniques.append(t)

        # Deduplicate while preserving order
        seen = set()
        unique_techniques = []
        for t in techniques:
            if t not in seen:
                seen.add(t)
                unique_techniques.append(t)

        return unique_techniques

    def _build_reasoning(
        self,
        result: T3TriggerResult,
        query: str
    ) -> str:
        """
        Build reasoning explanation.

        Args:
            result: Trigger result
            query: Lowercase query

        Returns:
            Reasoning string
        """
        if not result.should_fire_t3:
            reasons = []
            if not result.is_vip:
                reasons.append("not VIP")
            if not result.amount_exceeds_threshold:
                reasons.append("amount below threshold")
            if not result.anger_exceeds_threshold:
                reasons.append("anger below threshold")

            return f"T3 not triggered: {', '.join(reasons)}"

        reasons = []
        if result.is_vip:
            reasons.append("VIP customer")
        if result.amount_exceeds_threshold:
            reasons.append("high-value transaction")
        if result.anger_exceeds_threshold:
            reasons.append("high anger detected")

        if result.risk_factors:
            reasons.append(f"risk factors: {', '.join(result.risk_factors[:3])}")

        techniques = [t.value for t in result.triggered_techniques]

        return (
            f"T3 triggered: {', '.join(reasons)}. "
            f"Techniques: {', '.join(techniques)}"
        )
