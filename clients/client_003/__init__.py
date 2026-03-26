"""Client 003 - MediCare Health Module (Healthcare/HIPAA)"""

from .config import ClientConfig, get_client_config
from .hipaa_compliance import HIPAACompliance, PHIHandler

__all__ = ["ClientConfig", "get_client_config", "HIPAACompliance", "PHIHandler"]
