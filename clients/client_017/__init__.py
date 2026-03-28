"""Client 017 - QuickBite Delivery

Food & Beverage Delivery client with Mini PARWA variant.
DoorDash API, Stripe, SMS integrations for fast delivery support.
"""

from .config import get_client_config, ClientConfig

__all__ = ["get_client_config", "ClientConfig"]
