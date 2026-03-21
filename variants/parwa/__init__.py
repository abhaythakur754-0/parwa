"""
PARWA Junior Variant.

PARWA Junior is the medium-tier variant of the PARWA support system.
It provides enhanced capabilities over Mini PARWA while maintaining
cost-effectiveness for small to medium businesses.

Key Features:
- Up to 5 concurrent voice calls
- Support for FAQ, Email, Chat, SMS, Voice, and Video channels
- Refund recommendations up to $500 with APPROVE/REVIEW/DENY reasoning
- Learning agent for feedback collection and improvement
- Safety agent for competitor mention blocking and hallucination detection
- 60% escalation threshold (lower than Mini's 70%)
- Medium AI tier support

PARWA Junior is designed for businesses that need more than basic
support but don't require full enterprise capabilities.

This package contains:
- config: PARWA Junior configuration
- agents: PARWA-specific agents including Learning and Safety agents
- tools: PARWA-specific tools including knowledge update and refund tools
"""
from variants.parwa.config import ParwaConfig, get_parwa_config
from variants.parwa.anti_arbitrage_config import (
    ParwaAntiArbitrageConfig,
    get_parwa_anti_arbitrage_config,
)
from variants.parwa.agents import ParwaLearningAgent, ParwaSafetyAgent
from variants.parwa.tools import (
    KnowledgeUpdateTool,
    RefundRecommendationTool,
    SafetyTools,
)

__all__ = [
    # Config
    "ParwaConfig",
    "get_parwa_config",
    "ParwaAntiArbitrageConfig",
    "get_parwa_anti_arbitrage_config",
    # Agents
    "ParwaLearningAgent",
    "ParwaSafetyAgent",
    # Tools
    "KnowledgeUpdateTool",
    "RefundRecommendationTool",
    "SafetyTools",
]
