"""
PARWA Mini Variant Package.

Mini PARWA is the entry-level variant designed for basic tasks:
- Handles FAQs and simple queries
- Manages ticket intake and basic support
- Supports up to 2 concurrent calls
- Escalates when confidence < 70%
- Refund recommendations up to $50

This package contains:
- config: Mini PARWA configuration
- anti_arbitrage_config: Anti-arbitrage pricing configuration
- agents: Mini-specific agent implementations
"""
from variants.mini.config import MiniConfig, get_mini_config
from variants.mini.anti_arbitrage_config import (
    AntiArbitrageConfig,
    get_anti_arbitrage_config,
    calculate_mini_roi,
)

__all__ = [
    "MiniConfig",
    "get_mini_config",
    "AntiArbitrageConfig",
    "get_anti_arbitrage_config",
    "calculate_mini_roi",
]
