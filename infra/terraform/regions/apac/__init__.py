"""
APAC Region Infrastructure Module.

Asia-Pacific compliant infrastructure for APAC clients.
Region: ap-southeast-1 (Singapore)
"""

from .main import APACRegionConfig
from .database import APACDatabaseConfig
from .redis import APACRedisConfig
from .variables import APACVariables

__all__ = [
    "APACRegionConfig",
    "APACDatabaseConfig",
    "APACRedisConfig",
    "APACVariables",
]

__version__ = "1.0.0"
