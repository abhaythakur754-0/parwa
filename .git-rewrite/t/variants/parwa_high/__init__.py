"""
PARWA High Variant Package.

This package contains the PARWA High variant - the premium tier with:
- 10 concurrent voice calls
- All channels including video support
- $2000 refund limit (can execute with approval)
- Heavy AI tier
- Customer success with churn prediction
- Team coordination (5 teams)
- Analytics and insights
- HIPAA compliance support

PARWA High is designed for enterprise customers requiring:
- Video support capabilities
- Advanced analytics and insights
- Multi-team coordination
- Customer success management
- Healthcare compliance (HIPAA)
"""
from variants.parwa_high.config import ParwaHighConfig, get_parwa_high_config
from variants.parwa_high.anti_arbitrage_config import (
    ParwaHighAntiArbitrageConfig,
    get_parwa_high_anti_arbitrage_config,
)

__all__ = [
    "ParwaHighConfig",
    "get_parwa_high_config",
    "ParwaHighAntiArbitrageConfig",
    "get_parwa_high_anti_arbitrage_config",
]

__version__ = "1.0.0"
__variant_name__ = "PARWA High"
__variant_tier__ = "heavy"
