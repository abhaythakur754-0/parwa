"""Client 007 - EduLearn Academy

Education client for PARWA multi-tenant support.
Industry: Education
Variant: PARWA Junior
Compliance: FERPA enabled
"""

from .config import get_client_config, ClientConfig

__all__ = ['get_client_config', 'ClientConfig']
