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
- agents: Mini-specific agent implementations
"""
from variants.mini.config import MiniConfig, get_mini_config

__all__ = ["MiniConfig", "get_mini_config"]
