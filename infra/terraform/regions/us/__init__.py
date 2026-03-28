"""
US Region Infrastructure Module.

CCPA-compliant infrastructure for United States clients.
Region: us-east-1 (N. Virginia)
"""

from .main import USRegionConfig
from .database import USDatabaseConfig
from .redis import USRedisConfig
from .variables import USVariables

__all__ = [
    "USRegionConfig",
    "USDatabaseConfig",
    "USRedisConfig",
    "USVariables",
]

__version__ = "1.0.0"
