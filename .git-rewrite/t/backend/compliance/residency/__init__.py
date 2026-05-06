"""
Data Residency Module.

Enforces data residency requirements:
- Cross-region access blocking
- Region routing
- Sovereignty checking
- GDPR export
"""

from .residency_enforcer import ResidencyEnforcer
from .region_router import RegionRouter
from .sovereignty_checker import SovereigntyChecker
from .gdpr_export import GDPrexport

__all__ = [
    "ResidencyEnforcer",
    "RegionRouter",
    "SovereigntyChecker",
    "GDPrexport",
]

__version__ = "1.0.0"
