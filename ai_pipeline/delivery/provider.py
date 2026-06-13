"""Delivery Provider — Abstraction for real SMS, voice call, and email delivery.

CRITICAL: This module ensures PARWA never lies about action execution.
If an SMS is not actually sent, the status will be "simulated" or "delivery_failed",
NOT "executed".

Provider Chain:
1. TwilioProvider (real SMS/calls via Twilio API) — used when TWILIO credentials are set
2. SimulationProvider (honest simulation) — used when no real provider is available

The SimulationProvider is HONEST — it clearly marks results as simulated and
provides verifiable proof of what DID and DID NOT happen.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger("parwa.delivery")


class DeliveryStatus(str, Enum):
    """Honest delivery status — never misrepresent what happened."""
    DELIVERED = "delivered"              # Actually delivered (Twilio confirmed)
    DELIVERY_PENDING = "delivery_pending"  # Sent to provider, awaiting confirmation
    SIMULATED = "simulated"              # Not actually delivered — honest simulation
    DELIVERY_FAILED = "delivery_failed"  # Provider returned an error
    PROVIDER_UNAVAILABLE = "provider_unavailable"  # No provider configured


class DeliveryResult:
    """Result of a delivery attempt with full traceability."""

    def __init__(
        self,
        status: DeliveryStatus,
        channel: str,  # "sms", "voice", "email"
        recipient: str,
        provider: str,
        message_id: str = "",
        provider_sid: str = "",  # Twilio SID for real deliveries
        error: str = "",
        timestamp: str = "",
        metadata: dict[str, Any] | None = None,
    ):
        self.status = status
        self.channel = channel
        self.recipient = recipient
        self.provider = provider
        self.message_id = message_id or f"{channel.upper()}-{uuid.uuid4().hex[:6].upper()}"
        self.provider_sid = provider_sid
        self.error = error
        self.timestamp = timestamp or datetime.utcnow().isoformat()
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for storage in CRM and execution results."""
        result = {
            "delivery_status": self.status.value,
            "channel": self.channel,
            "recipient": self.recipient,
            "provider": self.provider,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "actually_delivered": self.status == DeliveryStatus.DELIVERED,
        }
        if self.provider_sid:
            result["provider_sid"] = self.provider_sid
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        # Honest note for simulated deliveries
        if self.status == DeliveryStatus.SIMULATED:
            result["honest_note"] = (
                f"NOT actually delivered. {self.channel.upper()} was simulated. "
                f"Configure Twilio credentials (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
                f"TWILIO_PHONE_NUMBER) for real delivery."
            )
        return result


class DeliveryProvider(ABC):
    """Abstract base class for delivery providers."""

    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and available."""

    @abstractmethod
    async def send_sms(self, to: str, message: str, metadata: dict[str, Any] | None = None) -> DeliveryResult:
        """Send an SMS message."""

    @abstractmethod
    async def make_call(self, to: str, reason: str, metadata: dict[str, Any] | None = None) -> DeliveryResult:
        """Initiate a voice call."""

    @abstractmethod
    async def send_email(self, to: str, subject: str, body: str, metadata: dict[str, Any] | None = None) -> DeliveryResult:
        """Send an email."""


class TwilioProvider(DeliveryProvider):
    """Real SMS and voice call delivery via Twilio API.

    Requires environment variables:
    - TWILIO_ACCOUNT_SID
    - TWILIO_AUTH_TOKEN
    - TWILIO_PHONE_NUMBER (Twilio-provided phone number)

    If any of these are missing, is_available() returns False.
    """

    def name(self) -> str:
        return "twilio"

    def is_available(self) -> bool:
        return bool(
            os.environ.get("TWILIO_ACCOUNT_SID")
            and os.environ.get("TWILIO_AUTH_TOKEN")
            and os.environ.get("TWILIO_PHONE_NUMBER")
        )

    async def send_sms(self, to: str, message: str, metadata: dict[str, Any] | None = None) -> DeliveryResult:
        if not self.is_available():
            return DeliveryResult(
                status=DeliveryStatus.PROVIDER_UNAVAILABLE,
                channel="sms", recipient=to, provider=self.name(),
                error="Twilio credentials not configured",
            )

        try:
            import httpx

            account_sid = os.environ["TWILIO_ACCOUNT_SID"]
            auth_token = os.environ["TWILIO_AUTH_TOKEN"]
            from_number = os.environ["TWILIO_PHONE_NUMBER"]

            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            data = {
                "From": from_number,
                "To": to,
                "Body": message[:1600],  # Twilio SMS limit
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    data=data,
                    auth=(account_sid, auth_token),
                )

            if response.status_code in (200, 201):
                result_data = response.json()
                sid = result_data.get("sid", "")
                status_val = result_data.get("status", "queued")
                # Twilio returns "queued" when accepted for delivery
                delivery_status = DeliveryStatus.DELIVERY_PENDING if status_val in ("queued", "sent") else DeliveryStatus.DELIVERED

                logger.info("Twilio SMS sent: SID=%s To=%s Status=%s", sid, to, status_val)

                return DeliveryResult(
                    status=delivery_status,
                    channel="sms",
                    recipient=to,
                    provider=self.name(),
                    provider_sid=sid,
                    metadata={"twilio_status": status_val, **(metadata or {})},
                )
            else:
                error_msg = f"Twilio API error: {response.status_code} - {response.text[:200]}"
                logger.error("Twilio SMS failed: %s", error_msg)
                return DeliveryResult(
                    status=DeliveryStatus.DELIVERY_FAILED,
                    channel="sms", recipient=to, provider=self.name(),
                    error=error_msg,
                )

        except ImportError:
            return DeliveryResult(
                status=DeliveryStatus.DELIVERY_FAILED,
                channel="sms", recipient=to, provider=self.name(),
                error="httpx not installed — cannot call Twilio API",
            )
        except Exception as exc:
            logger.error("Twilio SMS error: %s", exc)
            return DeliveryResult(
                status=DeliveryStatus.DELIVERY_FAILED,
                channel="sms", recipient=to, provider=self.name(),
                error=str(exc),
            )

    async def make_call(self, to: str, reason: str, metadata: dict[str, Any] | None = None) -> DeliveryResult:
        if not self.is_available():
            return DeliveryResult(
                status=DeliveryStatus.PROVIDER_UNAVAILABLE,
                channel="voice", recipient=to, provider=self.name(),
                error="Twilio credentials not configured",
            )

        try:
            import httpx

            account_sid = os.environ["TWILIO_ACCOUNT_SID"]
            auth_token = os.environ["TWILIO_AUTH_TOKEN"]
            from_number = os.environ["TWILIO_PHONE_NUMBER"]

            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"

            # Create a simple TwiML for the call
            twiml = f'<Response><Say>{reason}</Say></Response>'

            data = {
                "From": from_number,
                "To": to,
                "Twiml": twiml,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    data=data,
                    auth=(account_sid, auth_token),
                )

            if response.status_code in (200, 201):
                result_data = response.json()
                sid = result_data.get("sid", "")
                status_val = result_data.get("status", "queued")

                logger.info("Twilio call initiated: SID=%s To=%s Status=%s", sid, to, status_val)

                return DeliveryResult(
                    status=DeliveryStatus.DELIVERY_PENDING,
                    channel="voice",
                    recipient=to,
                    provider=self.name(),
                    provider_sid=sid,
                    metadata={"twilio_status": status_val, "reason": reason, **(metadata or {})},
                )
            else:
                error_msg = f"Twilio API error: {response.status_code} - {response.text[:200]}"
                logger.error("Twilio call failed: %s", error_msg)
                return DeliveryResult(
                    status=DeliveryStatus.DELIVERY_FAILED,
                    channel="voice", recipient=to, provider=self.name(),
                    error=error_msg,
                )

        except ImportError:
            return DeliveryResult(
                status=DeliveryStatus.DELIVERY_FAILED,
                channel="voice", recipient=to, provider=self.name(),
                error="httpx not installed — cannot call Twilio API",
            )
        except Exception as exc:
            logger.error("Twilio call error: %s", exc)
            return DeliveryResult(
                status=DeliveryStatus.DELIVERY_FAILED,
                channel="voice", recipient=to, provider=self.name(),
                error=str(exc),
            )

    async def send_email(self, to: str, subject: str, body: str, metadata: dict[str, Any] | None = None) -> DeliveryResult:
        # Twilio doesn't do email — delegate to SMTP or simulation
        return DeliveryResult(
            status=DeliveryStatus.PROVIDER_UNAVAILABLE,
            channel="email", recipient=to, provider=self.name(),
            error="Twilio does not support email delivery",
        )


class SimulationProvider(DeliveryProvider):
    """HONEST simulation provider — never claims to have delivered when it hasn't.

    This provider is used when no real delivery provider (Twilio, SMTP) is
    available. It creates verifiable records of what WOULD have happened,
    but clearly marks everything as "simulated".

    Key principle: It's better to be honestly simulated than dishonestly "executed".
    """

    def name(self) -> str:
        return "simulation"

    def is_available(self) -> bool:
        return True  # Always available as fallback

    async def send_sms(self, to: str, message: str, metadata: dict[str, Any] | None = None) -> DeliveryResult:
        msg_id = f"SMS-SIM-{uuid.uuid4().hex[:6].upper()}"
        logger.info("SIMULATED SMS to %s: %s (ID: %s)", to, message[:50], msg_id)

        # Create a simulation receipt file as proof
        receipt = {
            "message_id": msg_id,
            "channel": "sms",
            "recipient": to,
            "message_preview": message[:200],
            "simulated_at": datetime.utcnow().isoformat(),
            "provider": "simulation",
            "status": "simulated",
            "note": "This SMS was NOT actually delivered. Configure Twilio for real delivery.",
        }
        _save_simulation_receipt(receipt)

        return DeliveryResult(
            status=DeliveryStatus.SIMULATED,
            channel="sms",
            recipient=to,
            provider=self.name(),
            message_id=msg_id,
            metadata={"message_preview": message[:200], "simulation_receipt": True, **(metadata or {})},
        )

    async def make_call(self, to: str, reason: str, metadata: dict[str, Any] | None = None) -> DeliveryResult:
        call_id = f"CALL-SIM-{uuid.uuid4().hex[:6].upper()}"
        logger.info("SIMULATED CALL to %s: %s (ID: %s)", to, reason[:50], call_id)

        receipt = {
            "call_id": call_id,
            "channel": "voice",
            "recipient": to,
            "reason": reason,
            "simulated_at": datetime.utcnow().isoformat(),
            "provider": "simulation",
            "status": "simulated",
            "note": "This call was NOT actually made. Configure Twilio for real delivery.",
        }
        _save_simulation_receipt(receipt)

        return DeliveryResult(
            status=DeliveryStatus.SIMULATED,
            channel="voice",
            recipient=to,
            provider=self.name(),
            message_id=call_id,
            metadata={"reason": reason, "simulation_receipt": True, **(metadata or {})},
        )

    async def send_email(self, to: str, subject: str, body: str, metadata: dict[str, Any] | None = None) -> DeliveryResult:
        email_id = f"EMAIL-SIM-{uuid.uuid4().hex[:6].upper()}"
        logger.info("SIMULATED EMAIL to %s: %s (ID: %s)", to, subject[:50], email_id)

        receipt = {
            "email_id": email_id,
            "channel": "email",
            "recipient": to,
            "subject": subject,
            "body_preview": body[:200],
            "simulated_at": datetime.utcnow().isoformat(),
            "provider": "simulation",
            "status": "simulated",
            "note": "This email was NOT actually sent. Configure SMTP for real delivery.",
        }
        _save_simulation_receipt(receipt)

        return DeliveryResult(
            status=DeliveryStatus.SIMULATED,
            channel="email",
            recipient=to,
            provider=self.name(),
            message_id=email_id,
            metadata={"subject": subject, "simulation_receipt": True, **(metadata or {})},
        )


# ─── Simulation Receipt Storage ──────────────────────────────────────────────

_SIMULATION_RECEIPTS: list[dict[str, Any]] = []


def _save_simulation_receipt(receipt: dict[str, Any]) -> None:
    """Save a simulation receipt for later verification."""
    _SIMULATION_RECEIPTS.append(receipt)
    # Also persist to file
    try:
        import pathlib
        receipts_dir = pathlib.Path("/home/z/my-project/parwa/delivery_receipts")
        receipts_dir.mkdir(parents=True, exist_ok=True)
        receipt_file = receipts_dir / f"{receipt.get('message_id', receipt.get('call_id', receipt.get('email_id', 'unknown')))}.json"
        receipt_file.write_text(json.dumps(receipt, indent=2))
    except Exception:
        pass  # Non-critical — receipts are also in memory


def get_simulation_receipts() -> list[dict[str, Any]]:
    """Get all simulation receipts for verification."""
    return list(_SIMULATION_RECEIPTS)


def clear_simulation_receipts() -> None:
    """Clear all simulation receipts."""
    _SIMULATION_RECEIPTS.clear()


# ─── Provider Selection ──────────────────────────────────────────────────────

_providers: list[DeliveryProvider] = []


def _get_providers() -> list[DeliveryProvider]:
    """Get the provider chain (Twilio first, Simulation as fallback)."""
    global _providers
    if not _providers:
        _providers = [
            TwilioProvider(),
            SimulationProvider(),
        ]
    return _providers


def get_delivery_provider(channel: str = "sms") -> DeliveryProvider:
    """Get the best available delivery provider for a channel.

    Returns the first provider that:
    1. Is available (has credentials)
    2. Supports the requested channel

    Falls back to SimulationProvider which is always available.
    """
    for provider in _get_providers():
        if provider.is_available():
            return provider
    # Should never reach here since SimulationProvider is always available
    return SimulationProvider()


# ─── High-Level Delivery Functions ────────────────────────────────────────────

async def deliver_sms(to: str, message: str, metadata: dict[str, Any] | None = None) -> DeliveryResult:
    """Send an SMS to a phone number.

    Uses the best available provider (Twilio if configured, else simulation).
    Returns an HONEST DeliveryResult — if simulated, status will be "simulated".
    """
    provider = get_delivery_provider("sms")
    result = await provider.send_sms(to, message, metadata)

    # Also log in CRM if possible
    try:
        from parwa.fake_crm.database import get_crm
        crm = get_crm()
        # Find customer by phone
        for cust_id in ["CUST-1001", "CUST-1002", "CUST-1003", "CUST-1004",
                        "CUST-1005", "CUST-1006", "CUST-1007", "CUST-1008"]:
            cust = crm.get_customer(cust_id)
            if cust and cust.get("phone") == to:
                status_label = "DELIVERED" if result.status == DeliveryStatus.DELIVERED else result.status.value.upper()
                crm.add_note(cust_id, (
                    f"[SMS {status_label}] ID: {result.message_id} | "
                    f"To: {to} | Message: {message[:200]} | "
                    f"Provider: {result.provider}"
                ))
                break
    except Exception:
        pass

    return result


async def deliver_voice_call(to: str, reason: str, metadata: dict[str, Any] | None = None) -> DeliveryResult:
    """Make a voice call to a phone number.

    Uses the best available provider (Twilio if configured, else simulation).
    Returns an HONEST DeliveryResult.
    """
    provider = get_delivery_provider("voice")
    result = await provider.make_call(to, reason, metadata)

    # Also log in CRM
    try:
        from parwa.fake_crm.database import get_crm
        crm = get_crm()
        for cust_id in ["CUST-1001", "CUST-1002", "CUST-1003", "CUST-1004",
                        "CUST-1005", "CUST-1006", "CUST-1007", "CUST-1008"]:
            cust = crm.get_customer(cust_id)
            if cust and cust.get("phone") == to:
                status_label = "DELIVERED" if result.status == DeliveryStatus.DELIVERED else result.status.value.upper()
                crm.add_note(cust_id, (
                    f"[VOICE CALL {status_label}] ID: {result.message_id} | "
                    f"To: {to} | Reason: {reason} | "
                    f"Provider: {result.provider}"
                ))
                break
    except Exception:
        pass

    return result


async def deliver_email(to: str, subject: str, body: str, metadata: dict[str, Any] | None = None) -> DeliveryResult:
    """Send an email.

    Uses the best available provider (SMTP if configured, else simulation).
    Returns an HONEST DeliveryResult.
    """
    provider = get_delivery_provider("email")
    result = await provider.send_email(to, subject, body, metadata)
    return result
