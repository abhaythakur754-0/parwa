"""
EU Region Infrastructure Module.

GDPR-compliant infrastructure for European Union clients.
Region: eu-west-1 (Ireland)
"""

from .main import EURegionConfig
from .database import EUDatabaseConfig
from .redis import EURedisConfig
from .variables import EUVariables

__all__ = [
    "EURegionConfig",
    "EUDatabaseConfig",
    "EURedisConfig",
    "EUVariables",
]

__version__ = "1.0.0"
