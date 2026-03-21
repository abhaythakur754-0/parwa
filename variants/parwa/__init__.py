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
"""
from variants.parwa.config import ParwaConfig, get_parwa_config
from variants.parwa.anti_arbitrage_config import (
    ParwaAntiArbitrageConfig,
    get_parwa_anti_arbitrage_config,
)

__all__ = [
    "ParwaConfig",
    "get_parwa_config",
    "ParwaAntiArbitrageConfig",
    "get_parwa_anti_arbitrage_config",
]
