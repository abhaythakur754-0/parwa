"""Delivery Provider System — Actually delivers SMS, voice calls, and emails.

This module provides REAL delivery of communications, not just CRM logging.
It uses a provider abstraction so different backends (Twilio, SMTP, etc.)
can be plugged in.

Provider Hierarchy:
1. TwilioProvider — Real SMS and voice calls via Twilio API
2. SMTPProvider — Real email delivery via SMTP
3. SimulationProvider — Honest simulation that marks itself as "simulated"

The key principle: We NEVER claim "executed" when nothing was actually delivered.
If a provider fails or is unavailable, we report "delivery_pending" or "delivery_failed",
not "executed".
"""

from parwa.delivery.provider import (
    DeliveryProvider,
    DeliveryResult,
    DeliveryStatus,
    get_delivery_provider,
    deliver_sms,
    deliver_voice_call,
    deliver_email,
)

__all__ = [
    "DeliveryProvider",
    "DeliveryResult",
    "DeliveryStatus",
    "get_delivery_provider",
    "deliver_sms",
    "deliver_voice_call",
    "deliver_email",
]
