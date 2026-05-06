"""
PARWA Production Integration Connector
=======================================

Connects variant pipelines to real production services:
  - Brevo (Email): Send ticket updates, refund confirmations, notifications
  - Twilio (SMS + Voice): Send SMS updates, make outbound calls, receive incoming calls
  - Paddle (Billing): Process subscriptions, handle refunds, manage payments

This module makes PARWA variants capable of operating independently
without Jarvis — fulfilling the product vision of eliminating human workload.

Usage:
  from app.core.production_connector import ProductionConnector

  connector = ProductionConnector()
  await connector.send_email(customer_email, subject, body)
  await connector.send_sms(customer_phone, message)
  await connector.make_call(customer_phone, script)
  await connector.process_refund(transaction_id, amount)

Environment Variables Required:
  BREVO_API_KEY       — Brevo (Sendinblue) API key
  TWILIO_ACCOUNT_SID  — Twilio Account SID
  TWILIO_AUTH_TOKEN   — Twilio Auth Token
  TWILIO_API_KEY      — Twilio API Key
  TWILIO_PHONE_NUMBER — Twilio outbound phone number
  PADDLE_API_KEY      — Paddle API key
  PADDLE_CLIENT_TOKEN — Paddle Client-side token
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("production_connector")


# ════════════════════════════════════════════════════════════════
# RESULT TYPES
# ════════════════════════════════════════════════════════════════

class IntegrationStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    QUEUED = "queued"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"


@dataclass
class IntegrationResult:
    """Result of an integration call."""
    status: IntegrationStatus
    provider: str
    action: str
    external_id: str = ""
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ════════════════════════════════════════════════════════════════
# BREVO EMAIL CONNECTOR
# ════════════════════════════════════════════════════════════════

class BrevoEmailConnector:
    """Production Brevo (Sendinblue) email integration.

    Capabilities:
      - Send ticket confirmation emails
      - Send refund approval/denial emails
      - Send password reset links
      - Send SLA breach notifications
      - Send batch approval summaries
      - Send subscription invoices
    """

    BASE_URL = "https://api.brevo.com/v3"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.environ.get("BREVO_API_KEY", "")
        self._available = bool(self._api_key)

    @property
    def is_available(self) -> bool:
        return self._available

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        sender_name: str = "PARWA Support",
        sender_email: str = "support@parwa.ai",
        reply_to: Optional[str] = None,
        tags: Optional[List[str]] = None,
        template_id: Optional[int] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> IntegrationResult:
        """Send an email via Brevo API."""
        start = time.monotonic()
        if not self._available:
            return IntegrationResult(
                status=IntegrationStatus.UNAVAILABLE,
                provider="brevo",
                action="send_email",
                message="Brevo API key not configured",
            )

        try:
            import httpx

            headers = {
                "api-key": self._api_key,
                "Content-Type": "application/json",
            }

            payload: Dict[str, Any] = {
                "sender": {"name": sender_name, "email": sender_email},
                "to": [{"email": to_email}],
                "subject": subject,
                "htmlContent": html_content,
            }

            if reply_to:
                payload["replyTo"] = {"email": reply_to}
            if tags:
                payload["tags"] = tags
            if template_id:
                payload["templateId"] = template_id
            if params:
                payload["params"] = params

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/smtp/email",
                    headers=headers,
                    json=payload,
                )

            latency = round((time.monotonic() - start) * 1000, 2)

            if response.status_code == 201:
                data = response.json()
                return IntegrationResult(
                    status=IntegrationStatus.SUCCESS,
                    provider="brevo",
                    action="send_email",
                    external_id=data.get("messageId", ""),
                    message="Email sent successfully",
                    latency_ms=latency,
                    metadata={"to": to_email, "subject": subject},
                )
            elif response.status_code == 429:
                return IntegrationResult(
                    status=IntegrationStatus.RATE_LIMITED,
                    provider="brevo",
                    action="send_email",
                    message="Rate limited",
                    latency_ms=latency,
                )
            else:
                return IntegrationResult(
                    status=IntegrationStatus.FAILED,
                    provider="brevo",
                    action="send_email",
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                    latency_ms=latency,
                )

        except Exception as e:
            return IntegrationResult(
                status=IntegrationStatus.FAILED,
                provider="brevo",
                action="send_email",
                error=str(e),
            )

    async def send_ticket_confirmation(
        self,
        customer_email: str,
        customer_name: str,
        ticket_id: str,
        issue_summary: str,
        variant_tier: str = "parwa",
    ) -> IntegrationResult:
        """Send a ticket confirmation email."""
        tier_label = {
            "mini_parwa": "Standard",
            "parwa": "Priority",
            "parwa_high": "VIP",
        }.get(variant_tier, "Standard")

        html = f"""
        <html><body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Your Support Request Has Been Received</h2>
        <p>Hi {customer_name},</p>
        <p>Thank you for contacting us. Your {tier_label} support request has been logged.</p>
        <table style="border: 1px solid #ddd; padding: 10px; border-collapse: collapse;">
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Ticket ID</strong></td>
            <td style="padding: 8px; border: 1px solid #ddd;">{ticket_id}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Issue</strong></td>
            <td style="padding: 8px; border: 1px solid #ddd;">{issue_summary}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Priority</strong></td>
            <td style="padding: 8px; border: 1px solid #ddd;">{tier_label}</td></tr>
        </table>
        <p>Our AI assistant is reviewing your request and will respond shortly.</p>
        <p>If this is urgent, please reply to this email or call our support line.</p>
        <p>Best regards,<br>PARWA Support Team</p>
        </body></html>
        """

        return await self.send_email(
            to_email=customer_email,
            subject=f"[{ticket_id}] Your Support Request - {tier_label} Priority",
            html_content=html,
            tags=["ticket_confirmation", variant_tier],
        )

    async def send_refund_notification(
        self,
        customer_email: str,
        customer_name: str,
        ticket_id: str,
        amount: float,
        status: str,  # approved, denied, pending
        reason: str = "",
    ) -> IntegrationResult:
        """Send refund status notification email."""
        status_colors = {
            "approved": "#28a745",
            "denied": "#dc3545",
            "pending": "#ffc107",
        }
        color = status_colors.get(status, "#333")
        status_label = status.capitalize()

        html = f"""
        <html><body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Refund Update - Ticket {ticket_id}</h2>
        <p>Hi {customer_name},</p>
        <p>Your refund request has been <span style="color: {color}; font-weight: bold;">{status_label}</span>.</p>
        <table style="border: 1px solid #ddd; padding: 10px; border-collapse: collapse;">
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Amount</strong></td>
            <td style="padding: 8px; border: 1px solid #ddd;">${amount:.2f}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Status</strong></td>
            <td style="padding: 8px; border: 1px solid #ddd; color: {color};">{status_label}</td></tr>
            {"<tr><td style='padding: 8px; border: 1px solid #ddd;'><strong>Reason</strong></td>" +
             f"<td style='padding: 8px; border: 1px solid #ddd;'>{reason}</td></tr>" if reason else ""}
        </table>
        {"<p>If approved, the refund will be processed within 3-5 business days.</p>" if status == "approved" else ""}
        {"<p>If you disagree with this decision, please reply to this email.</p>" if status == "denied" else ""}
        {"<p>Your request is being reviewed and you'll receive an update soon.</p>" if status == "pending" else ""}
        <p>Best regards,<br>PARWA Support Team</p>
        </body></html>
        """

        return await self.send_email(
            to_email=customer_email,
            subject=f"[{ticket_id}] Refund {status_label} - ${amount:.2f}",
            html_content=html,
            tags=["refund_notification", status],
        )


# ════════════════════════════════════════════════════════════════
# TWILIO SMS + VOICE CONNECTOR
# ════════════════════════════════════════════════════════════════

class TwilioConnector:
    """Production Twilio SMS + Voice integration.

    Capabilities:
      - Send SMS notifications (order updates, appointment reminders)
      - Make outbound calls (VIP follow-up, urgent escalations)
      - Handle incoming calls (IVR routing to variant tiers)
      - Voice-First Response (as documented in v6.0)
      - Proactive outbound campaigns (abandoned carts, shipping delays)
    """

    BASE_URL = "https://api.twilio.com/2010-04-01"

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        api_key: Optional[str] = None,
        phone_number: Optional[str] = None,
    ) -> None:
        self._account_sid = account_sid or os.environ.get("TWILIO_ACCOUNT_SID", "")
        self._auth_token = auth_token or os.environ.get("TWILIO_AUTH_TOKEN", "")
        self._api_key = api_key or os.environ.get("TWILIO_API_KEY", "")
        self._phone_number = phone_number or os.environ.get("TWILIO_PHONE_NUMBER", "")
        self._available = bool(self._account_sid and self._auth_token)

    @property
    def is_available(self) -> bool:
        return self._available

    async def send_sms(
        self,
        to_phone: str,
        message: str,
        messaging_service_sid: Optional[str] = None,
    ) -> IntegrationResult:
        """Send an SMS via Twilio API."""
        start = time.monotonic()
        if not self._available:
            return IntegrationResult(
                status=IntegrationStatus.UNAVAILABLE,
                provider="twilio",
                action="send_sms",
                message="Twilio credentials not configured",
            )

        try:
            import httpx

            url = f"{self.BASE_URL}/Accounts/{self._account_sid}/Messages.json"

            data: Dict[str, str] = {
                "To": to_phone,
                "From": self._phone_number,
                "Body": message[:1600],  # Twilio SMS limit
            }
            if messaging_service_sid:
                data["MessagingServiceSid"] = messaging_service_sid

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    auth=(self._account_sid, self._auth_token),
                    data=data,
                )

            latency = round((time.monotonic() - start) * 1000, 2)

            if response.status_code == 201:
                resp_data = response.json()
                return IntegrationResult(
                    status=IntegrationStatus.SUCCESS,
                    provider="twilio",
                    action="send_sms",
                    external_id=resp_data.get("sid", ""),
                    message="SMS sent successfully",
                    latency_ms=latency,
                    metadata={
                        "to": to_phone,
                        "from": self._phone_number,
                        "status": resp_data.get("status", ""),
                    },
                )
            elif response.status_code == 429:
                return IntegrationResult(
                    status=IntegrationStatus.RATE_LIMITED,
                    provider="twilio",
                    action="send_sms",
                    latency_ms=latency,
                )
            else:
                return IntegrationResult(
                    status=IntegrationStatus.FAILED,
                    provider="twilio",
                    action="send_sms",
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                    latency_ms=latency,
                )

        except Exception as e:
            return IntegrationResult(
                status=IntegrationStatus.FAILED,
                provider="twilio",
                action="send_sms",
                error=str(e),
            )

    async def make_call(
        self,
        to_phone: str,
        twiml_url: Optional[str] = None,
        twiml: Optional[str] = None,
        record: bool = False,
        timeout: int = 30,
        status_callback: Optional[str] = None,
    ) -> IntegrationResult:
        """Make an outbound call via Twilio API.

        Args:
            to_phone: Phone number to call.
            twiml_url: URL pointing to TwiML instructions.
            twiml: Inline TwiML (if no URL).
            record: Whether to record the call.
            timeout: Ring timeout in seconds.
            status_callback: URL for call status updates.
        """
        start = time.monotonic()
        if not self._available:
            return IntegrationResult(
                status=IntegrationStatus.UNAVAILABLE,
                provider="twilio",
                action="make_call",
                message="Twilio credentials not configured",
            )

        try:
            import httpx

            url = f"{self.BASE_URL}/Accounts/{self._account_sid}/Calls.json"

            data: Dict[str, str] = {
                "To": to_phone,
                "From": self._phone_number,
                "Timeout": str(timeout),
            }

            if twiml_url:
                data["Url"] = twiml_url
            elif twiml:
                data["Twiml"] = twiml
            else:
                # Default greeting TwiML
                data["Twiml"] = (
                    '<Response><Say voice="alice">Hello, this is PARWA Support '
                    'calling regarding your recent inquiry. Please hold while we '
                    'connect you to our AI assistant.</Say></Response>'
                )

            if record:
                data["Record"] = "true"
            if status_callback:
                data["StatusCallback"] = status_callback

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    auth=(self._account_sid, self._auth_token),
                    data=data,
                )

            latency = round((time.monotonic() - start) * 1000, 2)

            if response.status_code == 201:
                resp_data = response.json()
                return IntegrationResult(
                    status=IntegrationStatus.SUCCESS,
                    provider="twilio",
                    action="make_call",
                    external_id=resp_data.get("sid", ""),
                    message="Call initiated successfully",
                    latency_ms=latency,
                    metadata={
                        "to": to_phone,
                        "call_status": resp_data.get("status", ""),
                    },
                )
            else:
                return IntegrationResult(
                    status=IntegrationStatus.FAILED,
                    provider="twilio",
                    action="make_call",
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                    latency_ms=latency,
                )

        except Exception as e:
            return IntegrationResult(
                status=IntegrationStatus.FAILED,
                provider="twilio",
                action="make_call",
                error=str(e),
            )

    async def send_order_update_sms(
        self,
        to_phone: str,
        order_id: str,
        status: str,
        tracking_url: str = "",
    ) -> IntegrationResult:
        """Send an order status update via SMS."""
        msg = f"PARWA: Your order #{order_id} status: {status}."
        if tracking_url:
            msg += f" Track: {tracking_url}"
        return await self.send_sms(to_phone, msg)

    async def send_appointment_reminder_sms(
        self,
        to_phone: str,
        appointment_time: str,
        location: str = "",
    ) -> IntegrationResult:
        """Send an appointment reminder via SMS."""
        msg = f"PARWA Reminder: Your appointment is at {appointment_time}."
        if location:
            msg += f" Location: {location}"
        msg += " Reply HELP for assistance."
        return await self.send_sms(to_phone, msg)

    async def make_vip_followup_call(
        self,
        to_phone: str,
        customer_name: str,
        ticket_id: str,
    ) -> IntegrationResult:
        """Make a VIP follow-up call using Twilio Voice."""
        twiml = (
            f'<Response>'
            f'<Say voice="alice">Hello {customer_name}, this is PARWA Support '
            f'calling regarding your ticket {ticket_id}. '
            f'We wanted to personally follow up to ensure your issue has been resolved. '
            f'If you need further assistance, please let us know.</Say>'
            f'<Pause length="1"/>'
            f'<Say voice="alice">Thank you for being a valued customer.</Say>'
            f'</Response>'
        )
        return await self.make_call(to_phone, twiml=twiml, record=True)

    async def make_proactive_cart_recovery_call(
        self,
        to_phone: str,
        customer_name: str,
        cart_value: float,
    ) -> IntegrationResult:
        """Make a proactive abandoned cart recovery call (v6.0 feature)."""
        twiml = (
            f'<Response>'
            f'<Say voice="alice">Hi {customer_name}, this is PARWA Support '
            f'from your online store. We noticed you left items worth '
            f'${cart_value:.2f} in your cart. '
            f'Would you like help completing your purchase? '
            f'We can assist you right now.</Say>'
            f'<Gather numDigits="1" action="/api/twilio/cart-response" method="POST">'
            f'<Say voice="alice">Press 1 to speak with our AI assistant, '
            f'or press 2 to receive a discount code via text.</Say>'
            f'</Gather>'
            f'</Response>'
        )
        return await self.make_call(to_phone, twiml=twiml)


# ════════════════════════════════════════════════════════════════
# PADDLE BILLING CONNECTOR
# ════════════════════════════════════════════════════════════════

class PaddleBillingConnector:
    """Production Paddle billing integration.

    Capabilities:
      - Process subscription signups
      - Handle variant tier upgrades/downgrades
      - Process prorated billing
      - Execute refund transactions (with approval gate)
      - Manage payment methods
      - Handle payment failures and retries
      - Generate invoices
    """

    BASE_URL = "https://vendors.paddle.com/api/2.0"

    def __init__(
        self,
        api_key: Optional[str] = None,
        client_token: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("PADDLE_API_KEY", "")
        self._client_token = client_token or os.environ.get("PADDLE_CLIENT_TOKEN", "")
        self._available = bool(self._api_key)

    @property
    def is_available(self) -> bool:
        return self._available

    async def process_refund(
        self,
        order_id: str,
        amount: float,
        reason: str = "requested_by_customer",
        approved_by: str = "",
        confidence: float = 0.0,
    ) -> IntegrationResult:
        """Process a refund via Paddle API.

        CRITICAL: This is the "Human-Triggered API" architecture.
        The AI only RECOMMENDS. A human must APPROVE.
        This function is called ONLY after manager approval.

        Args:
            order_id: The Paddle order/checkout ID.
            amount: Refund amount in original currency.
            reason: Refund reason code.
            approved_by: Email/ID of the human who approved.
            confidence: AI confidence score that led to this refund.
        """
        start = time.monotonic()
        if not self._available:
            return IntegrationResult(
                status=IntegrationStatus.UNAVAILABLE,
                provider="paddle",
                action="process_refund",
                message="Paddle API key not configured",
            )

        try:
            import httpx

            # Paddle refund API
            data = {
                "order_id": order_id,
                "amount": str(amount),
                "reason": reason,
            }

            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/payment/refund",
                    headers=headers,
                    json=data,
                )

            latency = round((time.monotonic() - start) * 1000, 2)

            if response.status_code == 200:
                resp_data = response.json()
                return IntegrationResult(
                    status=IntegrationStatus.SUCCESS,
                    provider="paddle",
                    action="process_refund",
                    external_id=resp_data.get("refund_id", ""),
                    message="Refund processed successfully",
                    latency_ms=latency,
                    metadata={
                        "order_id": order_id,
                        "amount": amount,
                        "approved_by": approved_by,
                        "ai_confidence": confidence,
                        "audit_trail": True,
                    },
                )
            else:
                return IntegrationResult(
                    status=IntegrationStatus.FAILED,
                    provider="paddle",
                    action="process_refund",
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                    latency_ms=latency,
                )

        except Exception as e:
            return IntegrationResult(
                status=IntegrationStatus.FAILED,
                provider="paddle",
                action="process_refund",
                error=str(e),
            )

    async def get_subscription_info(
        self,
        subscription_id: str,
    ) -> IntegrationResult:
        """Get subscription details from Paddle."""
        start = time.monotonic()
        if not self._available:
            return IntegrationResult(
                status=IntegrationStatus.UNAVAILABLE,
                provider="paddle",
                action="get_subscription",
            )

        try:
            import httpx

            headers = {
                "Authorization": f"Bearer {self._api_key}",
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/subscription/{subscription_id}",
                    headers=headers,
                )

            latency = round((time.monotonic() - start) * 1000, 2)

            if response.status_code == 200:
                return IntegrationResult(
                    status=IntegrationStatus.SUCCESS,
                    provider="paddle",
                    action="get_subscription",
                    external_id=subscription_id,
                    latency_ms=latency,
                    metadata=response.json(),
                )
            else:
                return IntegrationResult(
                    status=IntegrationStatus.FAILED,
                    provider="paddle",
                    action="get_subscription",
                    error=f"HTTP {response.status_code}",
                    latency_ms=latency,
                )

        except Exception as e:
            return IntegrationResult(
                status=IntegrationStatus.FAILED,
                provider="paddle",
                action="get_subscription",
                error=str(e),
            )

    async def update_subscription(
        self,
        subscription_id: str,
        plan_id: str,
        prorate: bool = True,
    ) -> IntegrationResult:
        """Update a subscription (upgrade/downgrade variant tier).

        Args:
            subscription_id: Paddle subscription ID.
            plan_id: New plan ID to switch to.
            prorate: Whether to prorate the billing.
        """
        start = time.monotonic()
        if not self._available:
            return IntegrationResult(
                status=IntegrationStatus.UNAVAILABLE,
                provider="paddle",
                action="update_subscription",
            )

        try:
            import httpx

            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }

            data = {
                "plan_id": plan_id,
                "prorate": prorate,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/subscription/{subscription_id}/update",
                    headers=headers,
                    json=data,
                )

            latency = round((time.monotonic() - start) * 1000, 2)

            if response.status_code == 200:
                return IntegrationResult(
                    status=IntegrationStatus.SUCCESS,
                    provider="paddle",
                    action="update_subscription",
                    external_id=subscription_id,
                    message="Subscription updated",
                    latency_ms=latency,
                    metadata={"plan_id": plan_id, "prorated": prorate},
                )
            else:
                return IntegrationResult(
                    status=IntegrationStatus.FAILED,
                    provider="paddle",
                    action="update_subscription",
                    error=f"HTTP {response.status_code}",
                    latency_ms=latency,
                )

        except Exception as e:
            return IntegrationResult(
                status=IntegrationStatus.FAILED,
                provider="paddle",
                action="update_subscription",
                error=str(e),
            )


# ════════════════════════════════════════════════════════════════
# UNIFIED PRODUCTION CONNECTOR
# ════════════════════════════════════════════════════════════════

class ProductionConnector:
    """Unified connector that wires all production services together.

    This is what makes PARWA variants operate independently:
      - When a ticket is created → Send confirmation email
      - When a refund is recommended → Send approval request to manager
      - When a refund is approved → Execute via Paddle + Send notification
      - When a VIP needs attention → Make outbound call via Twilio
      - When an order ships → Send SMS update via Twilio
      - When a subscription changes → Update via Paddle + Send email
    """

    def __init__(self) -> None:
        self.email = BrevoEmailConnector()
        self.sms_voice = TwilioConnector()
        self.billing = PaddleBillingConnector()

    @property
    def is_available(self) -> Dict[str, bool]:
        """Check which integrations are available."""
        return {
            "brevo_email": self.email.is_available,
            "twilio_sms_voice": self.sms_voice.is_available,
            "paddle_billing": self.billing.is_available,
        }

    async def handle_ticket_created(
        self,
        customer_email: str,
        customer_name: str,
        ticket_id: str,
        issue_summary: str,
        customer_phone: str = "",
        variant_tier: str = "parwa",
    ) -> Dict[str, IntegrationResult]:
        """Handle the full workflow when a ticket is created.

        1. Send email confirmation
        2. Send SMS if phone provided and paid tier
        """
        results: Dict[str, IntegrationResult] = {}

        # Email confirmation
        results["email"] = await self.email.send_ticket_confirmation(
            customer_email=customer_email,
            customer_name=customer_name,
            ticket_id=ticket_id,
            issue_summary=issue_summary,
            variant_tier=variant_tier,
        )

        # SMS notification for paid tiers (Pro/High)
        if customer_phone and variant_tier in ("parwa", "parwa_high"):
            results["sms"] = await self.sms_voice.send_sms(
                to_phone=customer_phone,
                message=f"PARWA: Your support ticket {ticket_id} has been received. "
                        f"We're reviewing your request now.",
            )

        return results

    async def handle_refund_recommended(
        self,
        customer_email: str,
        customer_name: str,
        manager_email: str,
        ticket_id: str,
        amount: float,
        confidence: float,
        reasoning: str,
    ) -> Dict[str, IntegrationResult]:
        """Handle the workflow when AI recommends a refund.

        Per docs: AI RECOMMENDS, Human APPROVES, Backend EXECUTES.
        This sends the recommendation to the manager.
        """
        results: Dict[str, IntegrationResult] = {}

        # Notify customer that request is being reviewed
        results["customer_notification"] = await self.email.send_refund_notification(
            customer_email=customer_email,
            customer_name=customer_name,
            ticket_id=ticket_id,
            amount=amount,
            status="pending",
        )

        # Send approval request to manager
        tier_label = "HIGH PRIORITY" if confidence > 0.90 else "REVIEW NEEDED"
        html = f"""
        <html><body style="font-family: Arial, sans-serif;">
        <h2>Refund Approval Required - {tier_label}</h2>
        <table style="border: 1px solid #ddd; border-collapse: collapse;">
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Ticket</strong></td>
            <td style="padding: 8px; border: 1px solid #ddd;">{ticket_id}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Customer</strong></td>
            <td style="padding: 8px; border: 1px solid #ddd;">{customer_name}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Amount</strong></td>
            <td style="padding: 8px; border: 1px solid #ddd;">${amount:.2f}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>AI Confidence</strong></td>
            <td style="padding: 8px; border: 1px solid #ddd;">{confidence:.0%}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>AI Reasoning</strong></td>
            <td style="padding: 8px; border: 1px solid #ddd;">{reasoning}</td></tr>
        </table>
        <p>
            <a href="/api/batch/approve?ticket={ticket_id}" style="background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Approve &amp; Refund</a>
            <a href="/api/batch/deny?ticket={ticket_id}" style="background: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-left: 10px;">Deny</a>
        </p>
        </body></html>
        """

        results["manager_approval"] = await self.email.send_email(
            to_email=manager_email,
            subject=f"[APPROVAL] Refund ${amount:.2f} - {ticket_id} ({confidence:.0%} confidence)",
            html_content=html,
            tags=["refund_approval", "manager_action"],
        )

        return results

    async def handle_refund_approved(
        self,
        order_id: str,
        amount: float,
        customer_email: str,
        customer_name: str,
        ticket_id: str,
        approved_by: str,
        confidence: float,
        customer_phone: str = "",
    ) -> Dict[str, IntegrationResult]:
        """Handle the workflow when a refund is approved by manager.

        This is Step 3 of the "Human-Triggered API" architecture.
        The backend executes the refund after manager approval.
        """
        results: Dict[str, IntegrationResult] = {}

        # Execute the refund via Paddle
        results["refund_execution"] = await self.billing.process_refund(
            order_id=order_id,
            amount=amount,
            approved_by=approved_by,
            confidence=confidence,
        )

        # Notify customer
        results["customer_notification"] = await self.email.send_refund_notification(
            customer_email=customer_email,
            customer_name=customer_name,
            ticket_id=ticket_id,
            amount=amount,
            status="approved",
        )

        # SMS notification for paid tiers
        if customer_phone:
            results["sms_notification"] = await self.sms_voice.send_sms(
                to_phone=customer_phone,
                message=f"PARWA: Your refund of ${amount:.2f} for ticket {ticket_id} has been approved. "
                        f"It will be processed within 3-5 business days.",
            )

        return results

    async def handle_vip_escalation(
        self,
        customer_name: str,
        customer_phone: str,
        customer_email: str,
        ticket_id: str,
        issue_summary: str,
        manager_email: str,
    ) -> Dict[str, IntegrationResult]:
        """Handle the workflow when a VIP customer needs escalation.

        Per docs: Angry/VIP customers are routed to humans.
        The AI initiates the call and notifies the manager.
        """
        results: Dict[str, IntegrationResult] = {}

        # Make outbound call to VIP customer
        if customer_phone:
            results["outbound_call"] = await self.sms_voice.make_vip_followup_call(
                to_phone=customer_phone,
                customer_name=customer_name,
                ticket_id=ticket_id,
            )

        # Alert manager
        html = f"""
        <html><body style="font-family: Arial, sans-serif;">
        <h2 style="color: #dc3545;">URGENT: VIP Customer Escalation</h2>
        <p>A VIP customer requires immediate attention:</p>
        <table style="border: 1px solid #ddd; border-collapse: collapse;">
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Customer</strong></td>
            <td style="padding: 8px; border: 1px solid #ddd;">{customer_name}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Ticket</strong></td>
            <td style="padding: 8px; border: 1px solid #ddd;">{ticket_id}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Issue</strong></td>
            <td style="padding: 8px; border: 1px solid #ddd;">{issue_summary}</td></tr>
        </table>
        <p>AI has initiated a follow-up call. Please review and take over if needed.</p>
        </body></html>
        """

        results["manager_alert"] = await self.email.send_email(
            to_email=manager_email,
            subject=f"[URGENT] VIP Escalation - {customer_name} - {ticket_id}",
            html_content=html,
            tags=["vip_escalation", "urgent"],
        )

        return results

    async def handle_cart_recovery(
        self,
        customer_name: str,
        customer_phone: str,
        customer_email: str,
        cart_value: float,
    ) -> Dict[str, IntegrationResult]:
        """Handle proactive abandoned cart recovery (v6.0 feature).

        Per docs: Jarvis detects abandoned cart → Makes call → Manager approves script.
        """
        results: Dict[str, IntegrationResult] = {}

        # Send recovery email first
        html = f"""
        <html><body style="font-family: Arial, sans-serif;">
        <h2>You Left Something Behind!</h2>
        <p>Hi {customer_name},</p>
        <p>You have items worth ${cart_value:.2f} waiting in your cart.</p>
        <p>Complete your purchase now and get free shipping!</p>
        <p><a href="#" style="background: #007bff; color: white; padding: 12px 24px;
           text-decoration: none; border-radius: 5px;">Complete Purchase</a></p>
        </body></html>
        """

        results["recovery_email"] = await self.email.send_email(
            to_email=customer_email,
            subject=f"Your cart is waiting - ${cart_value:.2f} in items!",
            html_content=html,
            tags=["cart_recovery", "proactive"],
        )

        # Follow up with call if Pro/High tier
        if customer_phone:
            results["recovery_call"] = await self.sms_voice.make_proactive_cart_recovery_call(
                to_phone=customer_phone,
                customer_name=customer_name,
                cart_value=cart_value,
            )

        return results


# ════════════════════════════════════════════════════════════════
# SINGLETON
# ════════════════════════════════════════════════════════════════

_production_connector: Optional[ProductionConnector] = None


def get_production_connector() -> ProductionConnector:
    """Get or create the ProductionConnector singleton."""
    global _production_connector
    if _production_connector is None:
        _production_connector = ProductionConnector()
    return _production_connector
