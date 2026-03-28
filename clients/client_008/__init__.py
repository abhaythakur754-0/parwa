"""Client 008 - TravelEase

Travel client for PARWA multi-tenant support.
Industry: Travel
Variant: PARWA High
Business Hours: 24/7 (Global)
"""

from .config import get_client_config, ClientConfig

__all__ = ['get_client_config', 'ClientConfig']
