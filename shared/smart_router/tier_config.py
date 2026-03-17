"""
PARWA Tier Configuration.

Defines AI tier configurations for OpenRouter models.
Maps tiers (Light/Medium/Heavy) to specific models.
"""
from typing import Dict, Any, Optional
from enum import Enum

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class AITier(str, Enum):
    """AI tier levels."""
    LIGHT = "light"      # Fast, cheap - for simple queries
    MEDIUM = "medium"    # Balanced - for moderate queries
    HEAVY = "heavy"      # Powerful - for complex queries


# Model configurations per tier
TIER_MODELS: Dict[str, Dict[str, str]] = {
    "google": {
        AITier.LIGHT.value: "gemma-2-9b-it",
        AITier.MEDIUM.value: "gemma-2-27b-it",
        AITier.HEAVY.value: "gemini-1.5-pro",
    },
    "cerebras": {
        AITier.LIGHT.value: "llama-3.1-8b",
        AITier.MEDIUM.value: "llama-3.1-70b",
        AITier.HEAVY.value: "llama-3.1-405b",
    },
    "groq": {
        AITier.LIGHT.value: "llama-3.1-8b-instant",
        AITier.MEDIUM.value: "llama-3.1-70b-versatile",
        AITier.HEAVY.value: "llama-3.1-405b-reasoning",
    },
}

# Cost per 1M tokens (approximate)
TIER_COSTS: Dict[str, float] = {
    AITier.LIGHT.value: 0.10,
    AITier.MEDIUM.value: 0.50,
    AITier.HEAVY.value: 2.00,
}

# Token limits per tier
TIER_TOKEN_LIMITS: Dict[str, int] = {
    AITier.LIGHT.value: 4096,
    AITier.MEDIUM.value: 8192,
    AITier.HEAVY.value: 32768,
}


class TierConfig:
    """
    Tier Configuration Manager.

    Manages AI tier configurations for OpenRouter.
    """

    def __init__(self, provider: Optional[str] = None) -> None:
        """
        Initialize Tier Config.

        Args:
            provider: LLM provider (google, cerebras, groq)
        """
        self.provider = provider or settings.llm_primary_provider

    def get_model(self, tier: AITier) -> str:
        """
        Get model name for tier.

        Args:
            tier: AI tier

        Returns:
            Model name string
        """
        provider_models = TIER_MODELS.get(self.provider, TIER_MODELS["google"])
        return provider_models.get(tier.value, provider_models[AITier.MEDIUM.value])

    def get_cost(self, tier: AITier) -> float:
        """
        Get cost per 1M tokens for tier.

        Args:
            tier: AI tier

        Returns:
            Cost in USD
        """
        return TIER_COSTS.get(tier.value, 0.50)

    def get_token_limit(self, tier: AITier) -> int:
        """
        Get token limit for tier.

        Args:
            tier: AI tier

        Returns:
            Token limit
        """
        return TIER_TOKEN_LIMITS.get(tier.value, 4096)

    def get_tier_config(self, tier: AITier) -> Dict[str, Any]:
        """
        Get full configuration for tier.

        Args:
            tier: AI tier

        Returns:
            Dict with model, cost, token_limit
        """
        return {
            "tier": tier.value,
            "provider": self.provider,
            "model": self.get_model(tier),
            "cost_per_1m_tokens": self.get_cost(tier),
            "token_limit": self.get_token_limit(tier),
        }

    def validate_tier_id(self, tier_id: str) -> bool:
        """
        Validate tier ID is in OpenRouter format.

        Args:
            tier_id: Tier identifier

        Returns:
            True if valid
        """
        return tier_id in [t.value for t in AITier]
