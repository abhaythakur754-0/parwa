"""
Webhook Provider Handler Registry (BC-003, GAP 1.5)

Central registry for webhook provider handlers.
Each provider handler:
- Validates event payload structure
- Extracts business-relevant data
- Dispatches to appropriate service layer
- All handlers are idempotent (duplicate event_id ignored)
- All handlers are async-safe (non-blocking)
"""

import logging
from typing import Callable, Dict, Optional

logger = logging.getLogger("parwa.webhooks")

# Handler registry: provider_name -> handler_function
_HANDLER_REGISTRY: Dict[str, Callable] = {}

# Supported event types per provider
PROVIDER_EVENT_TYPES = {
    "paddle": [
        "subscription.created",
        "subscription.updated",
        "subscription.cancelled",
        "payment.succeeded",
        "payment.failed",
    ],
    "brevo": [
        "inbound_email",
        "bounce",
        "complaint",
        "delivered",
    ],
    "twilio": [
        "sms.incoming",
        "voice.call.started",
        "voice.call.ended",
    ],
    "shopify": [
        "orders.create",
        "customers.create",
    ],
}


def register_handler(provider: str):
    """Decorator to register a webhook handler for a provider.

    Usage:
        @register_handler("paddle")
        def handle_paddle(event: dict) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        if provider in _HANDLER_REGISTRY:
            logger.warning(
                "webhook_handler_overridden provider=%s",
                provider,
            )
        _HANDLER_REGISTRY[provider] = func
        return func
    return decorator


def get_handler(provider: str) -> Optional[Callable]:
    """Get the registered handler for a provider.

    Args:
        provider: Provider name (e.g. 'paddle', 'twilio').

    Returns:
        Handler function or None if not registered.
    """
    return _HANDLER_REGISTRY.get(provider)


def dispatch_event(provider: str, event: dict) -> dict:
    """Dispatch a webhook event to the appropriate provider handler.

    Args:
        provider: Provider name.
        event: Full event dict from webhook_tasks.

    Returns:
        Dict with processing result.

    Raises:
        ValueError: If provider has no registered handler.
    """
    handler = get_handler(provider)
    if not handler:
        raise ValueError(
            f"No handler registered for provider: {provider}"
        )
    return handler(event)


def validate_event_type(
    provider: str, event_type: str,
) -> bool:
    """Check if an event type is supported for a provider.

    Args:
        provider: Provider name.
        event_type: Event type string.

    Returns:
        True if event type is in the provider's supported list.
    """
    supported = PROVIDER_EVENT_TYPES.get(provider, [])
    return event_type in supported


def get_supported_event_types(provider: str) -> list:
    """Get supported event types for a provider.

    Args:
        provider: Provider name.

    Returns:
        List of supported event type strings.
    """
    return list(PROVIDER_EVENT_TYPES.get(provider, []))


def get_registered_providers() -> list:
    """Get all providers with registered handlers.

    Returns:
        List of provider names.
    """
    return list(_HANDLER_REGISTRY.keys())
