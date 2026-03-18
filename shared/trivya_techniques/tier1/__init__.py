"""
PARWA TRIVYA Tier 1 Techniques.

Tier 1 is the foundation layer that always fires on every query.
It provides grounded, contextual, and efficient AI responses.
"""

from shared.trivya_techniques.tier1.clara import (
    CLARA,
    CLARAResult,
    CLARAConfig,
)
from shared.trivya_techniques.tier1.crp import (
    CRP,
    CRPResult,
    CRPConfig,
)
from shared.trivya_techniques.tier1.gsd_integration import (
    GSDIntegration,
    GSDIntegrationResult,
    GSDIntegrationConfig,
)

__all__ = [
    "CLARA",
    "CLARAResult",
    "CLARAConfig",
    "CRP",
    "CRPResult",
    "CRPConfig",
    "GSDIntegration",
    "GSDIntegrationResult",
    "GSDIntegrationConfig",
]
