"""
PARWA Sentiment Routing Rules.

Routes queries to appropriate AI pathways based on sentiment analysis.
Integrates with Smart Router for tier selection and failover.
"""
from typing import Optional, Dict, Any, Tuple, List
from uuid import UUID
from enum import Enum
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger
from shared.smart_router.tier_config import AITier
from shared.sentiment.analyzer import (
    SentimentAnalyzer,
    SentimentResult,
    SentimentType,
    SentimentIntensity,
)

logger = get_logger(__name__)


# Self-contained thresholds (since confidence/thresholds.py may not exist yet)
class RoutingThresholds:
    """
    Thresholds for sentiment-based routing.
    
    These define when to escalate or route differently
    based on sentiment analysis results.
    """
    # Sentiment score thresholds
    ANGER_ESCALATION_THRESHOLD = 75.0      # Anger score >= 75 → escalation
    FRUSTRATION_HIGH_THRESHOLD = 60.0      # Frustration >= 60 → high pathway
    URGENCY_PRIORITY_THRESHOLD = 50.0      # Urgency >= 50 → priority handling
    
    # Intensity thresholds
    CRITICAL_INTENSITY_THRESHOLD = 80.0    # Intensity >= 80 → critical
    HIGH_INTENSITY_THRESHOLD = 60.0        # Intensity >= 60 → high
    MODERATE_INTENSITY_THRESHOLD = 40.0    # Intensity >= 40 → moderate
    
    # Combined emotion thresholds
    ESCALATION_COMBINED_THRESHOLD = 120.0  # Combined negative >= 120 → escalate


class RoutingPathway(str, Enum):
    """Routing pathway options."""
    STANDARD = "standard"       # Normal processing
    GUIDED = "guided"          # Extra guidance for confused users
    PRIORITY = "priority"      # Fast-track for urgent issues
    ELEVATED = "elevated"      # Higher tier for frustrated users
    HIGH = "high"              # High attention for angry users
    ESCALATION = "escalation"  # Human escalation


class RoutingDecision(BaseModel):
    """
    Routing decision result.
    """
    pathway: str = RoutingPathway.STANDARD.value
    tier: str = AITier.MEDIUM.value
    requires_human: bool = False
    priority: int = Field(default=5, ge=1, le=10)
    sentiment_result: Optional[SentimentResult] = None
    routing_reasons: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class SentimentRoutingConfig(BaseModel):
    """
    Configuration for Sentiment Routing.
    """
    enable_sentiment_routing: bool = Field(default=True)
    escalate_on_anger: bool = Field(default=True)
    anger_threshold: float = Field(default=RoutingThresholds.ANGER_ESCALATION_THRESHOLD)
    priority_on_urgency: bool = Field(default=True)
    urgency_threshold: float = Field(default=RoutingThresholds.URGENCY_PRIORITY_THRESHOLD)
    log_all_routing_decisions: bool = Field(default=True)

    model_config = ConfigDict(use_enum_values=True)


class SentimentRouter:
    """
    Sentiment-based Routing Rules Engine.

    Determines routing pathway based on sentiment analysis:
    - High anger → Escalation/High pathway
    - High urgency → Priority handling
    - Confusion → Guided assistance
    - Positive sentiment → Standard pathway

    Features:
    - Sentiment-aware routing
    - Integration with Smart Router
    - Threshold-based escalation
    - Action recommendations
    """

    # Priority mappings
    PATHWAY_PRIORITIES: Dict[str, int] = {
        RoutingPathway.ESCALATION.value: 10,
        RoutingPathway.HIGH.value: 8,
        RoutingPathway.ELEVATED.value: 7,
        RoutingPathway.PRIORITY.value: 6,
        RoutingPathway.GUIDED.value: 5,
        RoutingPathway.STANDARD.value: 4,
    }

    # Tier mappings
    PATHWAY_TIERS: Dict[str, str] = {
        RoutingPathway.ESCALATION.value: AITier.HEAVY.value,
        RoutingPathway.HIGH.value: AITier.HEAVY.value,
        RoutingPathway.ELEVATED.value: AITier.MEDIUM.value,
        RoutingPathway.PRIORITY.value: AITier.MEDIUM.value,
        RoutingPathway.GUIDED.value: AITier.MEDIUM.value,
        RoutingPathway.STANDARD.value: AITier.LIGHT.value,
    }

    def __init__(
        self,
        analyzer: Optional[SentimentAnalyzer] = None,
        config: Optional[SentimentRoutingConfig] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize Sentiment Router.

        Args:
            analyzer: SentimentAnalyzer instance
            config: Router configuration
            company_id: Company UUID for scoping
        """
        self.analyzer = analyzer or SentimentAnalyzer()
        self.config = config or SentimentRoutingConfig()
        self.company_id = company_id

        # Statistics tracking
        self._routing_decisions = 0
        self._escalations = 0
        self._pathway_counts: Dict[str, int] = {}

        logger.info({
            "event": "sentiment_router_initialized",
            "company_id": str(company_id) if company_id else None,
            "enable_sentiment_routing": self.config.enable_sentiment_routing,
        })

    def route(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        complexity_score: Optional[int] = None,
        budget_remaining: Optional[float] = None
    ) -> RoutingDecision:
        """
        Route query based on sentiment analysis.

        Args:
            query: Customer query text
            context: Additional context
            complexity_score: Pre-calculated complexity score
            budget_remaining: Remaining AI budget

        Returns:
            RoutingDecision with pathway and tier

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        # Analyze sentiment
        sentiment_result = self.analyzer.analyze(query, context)

        # Determine pathway
        pathway = self._determine_pathway(
            sentiment_result,
            complexity_score,
            budget_remaining
        )

        # Determine tier
        tier = self._determine_tier(pathway, sentiment_result, budget_remaining)

        # Check if human escalation needed
        requires_human = self._check_human_escalation(
            pathway,
            sentiment_result
        )

        # Get routing reasons
        routing_reasons = self._get_routing_reasons(sentiment_result, pathway)

        # Get recommended actions
        recommended_actions = self._get_recommended_actions(
            sentiment_result,
            pathway
        )

        # Determine priority
        priority = self.PATHWAY_PRIORITIES.get(pathway, 5)

        decision = RoutingDecision(
            pathway=pathway,
            tier=tier,
            requires_human=requires_human,
            priority=priority,
            sentiment_result=sentiment_result,
            routing_reasons=routing_reasons,
            recommended_actions=recommended_actions,
            metadata={
                "company_id": str(self.company_id) if self.company_id else None,
                "complexity_score": complexity_score,
                "budget_remaining": budget_remaining,
                "routed_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Update stats
        self._routing_decisions += 1
        self._pathway_counts[pathway] = self._pathway_counts.get(pathway, 0) + 1
        if requires_human:
            self._escalations += 1

        if self.config.log_all_routing_decisions:
            log_level = "warning" if requires_human else "info"
            getattr(logger, log_level)({
                "event": "sentiment_routing_decision",
                "pathway": pathway,
                "tier": tier,
                "requires_human": requires_human,
                "primary_sentiment": sentiment_result.primary_sentiment,
                "intensity_score": sentiment_result.intensity_score,
            })

        return decision

    def route_with_sentiment(
        self,
        sentiment_result: SentimentResult,
        complexity_score: Optional[int] = None,
        budget_remaining: Optional[float] = None
    ) -> RoutingDecision:
        """
        Route based on pre-computed sentiment result.

        Args:
            sentiment_result: Pre-computed sentiment analysis
            complexity_score: Pre-calculated complexity score
            budget_remaining: Remaining AI budget

        Returns:
            RoutingDecision with pathway and tier
        """
        pathway = self._determine_pathway(
            sentiment_result,
            complexity_score,
            budget_remaining
        )

        tier = self._determine_tier(pathway, sentiment_result, budget_remaining)

        requires_human = self._check_human_escalation(pathway, sentiment_result)

        routing_reasons = self._get_routing_reasons(sentiment_result, pathway)

        recommended_actions = self._get_recommended_actions(
            sentiment_result,
            pathway
        )

        priority = self.PATHWAY_PRIORITIES.get(pathway, 5)

        return RoutingDecision(
            pathway=pathway,
            tier=tier,
            requires_human=requires_human,
            priority=priority,
            sentiment_result=sentiment_result,
            routing_reasons=routing_reasons,
            recommended_actions=recommended_actions,
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get routing statistics.

        Returns:
            Dict with routing stats
        """
        return {
            "routing_decisions": self._routing_decisions,
            "escalations": self._escalations,
            "escalation_rate": (
                self._escalations / self._routing_decisions
                if self._routing_decisions > 0 else 0
            ),
            "pathway_distribution": dict(self._pathway_counts),
            "analyzer_stats": self.analyzer.get_stats(),
            "config": self.config.model_dump(),
        }

    def _determine_pathway(
        self,
        sentiment: SentimentResult,
        complexity_score: Optional[int],
        budget_remaining: Optional[float]
    ) -> str:
        """
        Determine routing pathway.

        Args:
            sentiment: Sentiment analysis result
            complexity_score: Query complexity score
            budget_remaining: Budget remaining

        Returns:
            Pathway string
        """
        primary = sentiment.primary_sentiment
        intensity = sentiment.intensity_score
        scores = sentiment.sentiment_scores

        # Check for escalation conditions
        if self.config.escalate_on_anger:
            anger_score = scores.get(SentimentType.ANGER.value, 0)
            if anger_score >= self.config.anger_threshold:
                return RoutingPathway.ESCALATION.value

        # Critical intensity
        if intensity >= RoutingThresholds.CRITICAL_INTENSITY_THRESHOLD:
            return RoutingPathway.ESCALATION.value

        # High intensity negative emotions
        if intensity >= RoutingThresholds.HIGH_INTENSITY_THRESHOLD:
            if primary == SentimentType.ANGER.value:
                return RoutingPathway.HIGH.value
            elif primary in [SentimentType.FRUSTRATION.value, SentimentType.SADNESS.value]:
                return RoutingPathway.ELEVATED.value

        # Urgency check
        if self.config.priority_on_urgency:
            urgency_score = scores.get(SentimentType.URGENCY.value, 0)
            if urgency_score >= self.config.urgency_threshold:
                return RoutingPathway.PRIORITY.value

        # Confusion → guided
        if primary == SentimentType.CONFUSION.value:
            return RoutingPathway.GUIDED.value

        # Frustration at moderate level
        if primary == SentimentType.FRUSTRATION.value:
            if intensity >= RoutingThresholds.MODERATE_INTENSITY_THRESHOLD:
                return RoutingPathway.ELEVATED.value

        # Attention flag → elevated
        if sentiment.requires_attention:
            return RoutingPathway.ELEVATED.value

        # Positive sentiment → standard
        if primary in [SentimentType.HAPPINESS.value, SentimentType.GRATITUDE.value]:
            return RoutingPathway.STANDARD.value

        # Budget constraints
        if budget_remaining is not None and budget_remaining < 5.0:
            # Low budget → use lighter pathway
            return RoutingPathway.STANDARD.value

        # High complexity
        if complexity_score is not None and complexity_score >= 7:
            return RoutingPathway.PRIORITY.value

        return RoutingPathway.STANDARD.value

    def _determine_tier(
        self,
        pathway: str,
        sentiment: SentimentResult,
        budget_remaining: Optional[float]
    ) -> str:
        """
        Determine AI tier based on pathway and constraints.

        Args:
            pathway: Routing pathway
            sentiment: Sentiment result
            budget_remaining: Budget remaining

        Returns:
            Tier string
        """
        # Get base tier from pathway
        base_tier = self.PATHWAY_TIERS.get(pathway, AITier.MEDIUM.value)

        # Budget downgrade
        if budget_remaining is not None:
            if budget_remaining < 1.0:
                # Critical budget - use light tier
                return AITier.LIGHT.value
            elif budget_remaining < 10.0 and base_tier == AITier.HEAVY.value:
                # Low budget - downgrade heavy to medium
                return AITier.MEDIUM.value

        return base_tier

    def _check_human_escalation(
        self,
        pathway: str,
        sentiment: SentimentResult
    ) -> bool:
        """
        Check if human escalation is required.

        Args:
            pathway: Routing pathway
            sentiment: Sentiment result

        Returns:
            True if human escalation needed
        """
        # Escalation pathway always requires human
        if pathway == RoutingPathway.ESCALATION.value:
            return True

        # Critical intensity
        if sentiment.intensity_score >= RoutingThresholds.CRITICAL_INTENSITY_THRESHOLD:
            return True

        # Very high anger
        anger_score = sentiment.sentiment_scores.get(SentimentType.ANGER.value, 0)
        if anger_score >= 90:
            return True

        # Combined negative emotions above threshold
        frustration = sentiment.sentiment_scores.get(SentimentType.FRUSTRATION.value, 0)
        sadness = sentiment.sentiment_scores.get(SentimentType.SADNESS.value, 0)

        if (anger_score + frustration + sadness) >= RoutingThresholds.ESCALATION_COMBINED_THRESHOLD:
            return True

        return False

    def _get_routing_reasons(
        self,
        sentiment: SentimentResult,
        pathway: str
    ) -> List[str]:
        """
        Get reasons for routing decision.

        Args:
            sentiment: Sentiment result
            pathway: Chosen pathway

        Returns:
            List of reason strings
        """
        reasons = []

        primary = sentiment.primary_sentiment
        intensity = sentiment.intensity_score
        scores = sentiment.sentiment_scores

        if primary != SentimentType.NEUTRAL.value:
            reasons.append(f"Primary sentiment: {primary}")

        if intensity >= RoutingThresholds.HIGH_INTENSITY_THRESHOLD:
            reasons.append(f"High intensity score: {intensity:.1f}")

        anger = scores.get(SentimentType.ANGER.value, 0)
        if anger >= self.config.anger_threshold:
            reasons.append(f"High anger score: {anger:.1f}")

        urgency = scores.get(SentimentType.URGENCY.value, 0)
        if urgency >= self.config.urgency_threshold:
            reasons.append(f"Urgency detected: {urgency:.1f}")

        if sentiment.requires_attention:
            reasons.append("Attention flag triggered")

        if not reasons:
            reasons.append("Standard routing - no special conditions")

        return reasons

    def _get_recommended_actions(
        self,
        sentiment: SentimentResult,
        pathway: str
    ) -> List[str]:
        """
        Get recommended actions for the routing.

        Args:
            sentiment: Sentiment result
            pathway: Chosen pathway

        Returns:
            List of action recommendations
        """
        actions = []

        primary = sentiment.primary_sentiment

        if pathway == RoutingPathway.ESCALATION.value:
            actions.append("Immediate human agent notification")
            actions.append("Prepare conversation summary")
            actions.append("Flag for supervisor review")

        elif pathway == RoutingPathway.HIGH.value:
            actions.append("Use empathetic response tone")
            actions.append("Acknowledge customer frustration")
            actions.append("Offer concrete resolution steps")

        elif pathway == RoutingPathway.PRIORITY.value:
            actions.append("Fast-track response")
            actions.append("Provide clear timeline")
            actions.append("Confirm understanding of urgency")

        elif pathway == RoutingPathway.GUIDED.value:
            actions.append("Provide step-by-step guidance")
            actions.append("Offer examples and clarifications")
            actions.append("Ask confirming questions")

        elif primary == SentimentType.GRATITUDE.value:
            actions.append("Express appreciation")
            actions.append("Offer additional assistance")

        elif primary == SentimentType.SADNESS.value:
            actions.append("Use supportive tone")
            actions.append("Show understanding and empathy")

        return actions


def create_sentiment_router(
    company_id: Optional[UUID] = None,
    config: Optional[SentimentRoutingConfig] = None
) -> SentimentRouter:
    """
    Factory function to create a SentimentRouter.

    Args:
        company_id: Company UUID
        config: Router configuration

    Returns:
        Configured SentimentRouter instance
    """
    return SentimentRouter(
        analyzer=SentimentAnalyzer(),
        config=config,
        company_id=company_id
    )
