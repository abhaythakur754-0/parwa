"""
PARWA Smart Router.

Routes customer queries to appropriate AI tier based on complexity,
sentiment, and company settings. Implements cost-optimized AI routing.
"""
from typing import Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timezone

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger
from shared.smart_router.tier_config import AITier, TierConfig
from shared.smart_router.failover import FailoverManager
from shared.smart_router.complexity_scorer import ComplexityScorer

logger = get_logger(__name__)
settings = get_settings()


class SmartRouter:
    """
    Smart Router for AI tier selection.

    Routes queries to appropriate AI tier based on:
    - Query complexity analysis
    - Sentiment detection
    - Customer tier/subscription level
    - Company AI settings and budget
    - Provider health and failover
    """

    def __init__(
        self,
        company_id: Optional[UUID] = None,
        company_settings: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize Smart Router.

        Args:
            company_id: Company UUID for settings lookup
            company_settings: Company-specific routing settings
        """
        self.company_id = company_id
        self.company_settings = company_settings or {}
        self.tier_config = TierConfig()
        self.failover = FailoverManager()
        self.complexity_scorer = ComplexityScorer()

    def route(
        self,
        query: str,
        customer_tier: Optional[str] = None,
        budget_remaining: Optional[float] = None
    ) -> Tuple[AITier, Dict[str, Any]]:
        """
        Route query to appropriate AI tier.

        Args:
            query: Customer query text
            customer_tier: Customer subscription tier
            budget_remaining: Remaining AI budget

        Returns:
            Tuple of (AITier, routing_metadata dict)
        """
        # Score complexity
        complexity_score = self.complexity_scorer.score(query)
        recommended_tier = self.complexity_scorer.get_tier_for_score(complexity_score)

        # Get provider with failover
        provider = self.failover.get_provider()

        routing_metadata = {
            "complexity_score": complexity_score,
            "recommended_tier": recommended_tier.value,
            "provider": provider,
            "model": self.tier_config.get_model(recommended_tier),
            "customer_tier": customer_tier,
            "budget_remaining": budget_remaining,
            "routed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Budget check - downgrade if necessary
        selected_tier = recommended_tier
        if budget_remaining is not None and budget_remaining < 1.0:
            # Critical budget - use light tier
            selected_tier = AITier.LIGHT
            routing_metadata["budget_downgrade"] = True
            routing_metadata["downgrade_reason"] = "critical_budget"
        elif budget_remaining is not None and budget_remaining < 10.0:
            # Low budget - downgrade heavy to medium
            if selected_tier == AITier.HEAVY:
                selected_tier = AITier.MEDIUM
                routing_metadata["budget_downgrade"] = True
                routing_metadata["downgrade_reason"] = "low_budget"

        routing_metadata["selected_tier"] = selected_tier.value
        routing_metadata["estimated_cost"] = self.tier_config.get_cost(selected_tier)

        logger.info({
            "event": "query_routed",
            "company_id": str(self.company_id) if self.company_id else None,
            "complexity_score": complexity_score,
            "selected_tier": selected_tier.value,
            "provider": provider,
        })

        return selected_tier, routing_metadata

    def get_model_for_tier(self, tier: AITier, provider: Optional[str] = None) -> str:
        """
        Get model name for tier.

        Args:
            tier: AI tier
            provider: Provider override

        Returns:
            Model name string
        """
        if provider:
            config = TierConfig(provider=provider)
            return config.get_model(tier)
        return self.tier_config.get_model(tier)

    def estimate_cost(self, query: str) -> float:
        """
        Estimate cost for processing query.

        Args:
            query: Customer query text

        Returns:
            Estimated cost in USD
        """
        tier, _ = self.route(query)
        base_cost = self.tier_config.get_cost(tier)

        # Adjust for query length
        token_estimate = len(query.split()) / 4
        length_multiplier = max(1.0, token_estimate / 500)

        return (base_cost / 1_000_000) * token_estimate * length_multiplier

    def record_success(self, provider: str) -> None:
        """Record successful provider request."""
        self.failover.record_success(provider)

    def record_error(self, provider: str, error_type: str = "unknown") -> None:
        """Record provider error."""
        self.failover.record_error(provider, error_type)

    def get_routing_stats(self) -> Dict[str, Any]:
        """
        Get routing statistics.

        Returns:
            Dict with routing statistics
        """
        return {
            "company_id": str(self.company_id) if self.company_id else None,
            "provider_status": self.failover.get_status(),
        }
