"""Compatibility shim.

Many provider modules use ``from .base import ...``. The canonical
implementations live in ``base_provider.py``. This shim re-exports them so
the existing import statements resolve without modifying every file.
"""
from .base_provider import (  # noqa: F401
    BaseProvider,
    ConnectionStatus,
    EmailProvider,
    PaymentProvider,
    ProviderCategory,
    ProviderResult,
    SMSProvider,
)
