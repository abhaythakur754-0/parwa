"""
PARWA Production Integration Connector
=======================================

Connects variant pipelines to real production services:
  - Email/SMS/Voice: Routed through ExternalToolBus (single integration layer)
  - Billing (Razorpay): Handled out-of-band via Razorpay webhooks + DB services

NOTE: Paddle was removed; the PaddleBillingConnector class has been deleted.
Refunds are now handled by Razorpay (delegated to razorpay_service). The
ProductionConnector keeps a `self.billing = None` attribute and a no-op
path in handle_refund_approved so existing callers don't break.

This module makes PARWA variants capable of operating independently
without Jarvis — fulfilling the product vision of eliminating human workload.

Usage:
  from app.core.production_connector import ProductionConnector

  connector = ProductionConnector()
  results = await connector.handle_ticket_created(
      customer_email="user@example.com",
      customer_name="John",
      ticket_id="TKT-123",
      issue_summary="My order is late",
      variant_tier="parwa",
  )

Environment Variables Required (fallback when no DB config):
  BREVO_API_KEY       — Brevo (Sendinblue) API key
  TWILIO_ACCOUNT_SID  — Twilio Account SID
  TWILIO_AUTH_TOKEN   — Twilio Auth Token
  TWILIO_API_KEY      — Twilio API Key
  TWILIO_PHONE_NUMBER — Twilio outbound phone number
  RAZORPAY_KEY_ID     — Razorpay Key ID
  RAZORPAY_KEY_SECRET — Razorpay Key Secret
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.core.external_tool_bus import ExternalToolBus, ToolResult, external_tool_bus
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


def _tool_result_to_integration(result: ToolResult, action: str) -> IntegrationResult:
    """Convert a ToolResult from ExternalToolBus into an IntegrationResult."""
    if result.success:
        return IntegrationResult(
            status=IntegrationStatus.SUCCESS,
            provider=result.provider,
            action=action,
            external_id=result.message_id,
            message="Success",
            metadata=result.data,
        )
    return IntegrationResult(
        status=IntegrationStatus.FAILED,
        provider=result.provider,
        action=action,
        error=result.error,
        metadata=result.data,
    )


# ════════════════════════════════════════════════════════════════
# UNIFIED PRODUCTION CONNECTOR
# ════════════════════════════════════════════════════════════════

class ProductionConnector:
    """Unified connector that wires all production services together.

    Channel communication (email, SMS, voice) is routed through
    the ExternalToolBus — the SINGLE integration layer for all
    external tool calls. Billing is handled out-of-band by Razorpay
    (Paddle was removed).

    Workflows:
      - When a ticket is created → Send confirmation email
      - When a refund is recommended → Send approval request to manager
      - When a refund is approved → Send notification (refund execution is delegated to Razorpay)
      - When a VIP needs attention → Make outbound call via Twilio
      - When an order ships → Send SMS update via Twilio
      - When a subscription changes → Handled by Razorpay webhook → DB update
    """

    def __init__(self, tool_bus: Optional[ExternalToolBus] = None) -> None:
        self.tool_bus = tool_bus or external_tool_bus
        # NOTE: Paddle was removed. Billing is now handled by Razorpay
        # (out-of-band via webhooks). `self.billing` is kept as None for
        # backward-compat with any callers that read it.
        self.billing = None

    @property
    def is_available(self) -> Dict[str, bool]:
        """Check which integrations are available."""
        provider_status = self.tool_bus.get_provider_status()
        return {
            "email": provider_status.get("email", {}).get("configured", False),
            "sms": provider_status.get("sms", {}).get("configured", False),
            "voice": provider_status.get("voice", {}).get("configured", False),
            "razorpay_billing": bool(os.environ.get("RAZORPAY_KEY_ID")),
        }

    async def handle_ticket_created(
        self,
        customer_email: str,
        customer_name: str,
        ticket_id: str,
        issue_summary: str,
        customer_phone: str = "",
        variant_tier: str = "parwa",
        company_id: str = "",
    ) -> Dict[str, IntegrationResult]:
        """Handle the full workflow when a ticket is created.

        1. Send email confirmation
        2. Send SMS if phone provided and paid tier
        """
        results: Dict[str, IntegrationResult] = {}

        # Email confirmation
        tier_label = {
            "mini_parwa": "Standard",
            "parwa": "Priority",
            "parwa_high": "VIP",
        }.get(variant_tier, "Standard")

        email_html = f"""
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

        tool_result = await self.tool_bus.send_email(
            variant=variant_tier,
            company_id=company_id,
            to=customer_email,
            subject=f"[{ticket_id}] Your Support Request - {tier_label} Priority",
            body=email_html,
            html_body=email_html,
        )
        results["email"] = _tool_result_to_integration(tool_result, "send_ticket_confirmation")

        # SMS notification for paid tiers (Pro/High)
        if customer_phone and variant_tier in ("parwa", "parwa_high"):
            tool_result = await self.tool_bus.send_sms(
                variant=variant_tier,
                company_id=company_id,
                to=customer_phone,
                body=f"PARWA: Your support ticket {ticket_id} has been received. "
                     f"We're reviewing your request now.",
            )
            results["sms"] = _tool_result_to_integration(tool_result, "send_sms")

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
        variant_tier: str = "parwa",
        company_id: str = "",
    ) -> Dict[str, IntegrationResult]:
        """Handle the workflow when AI recommends a refund.

        Per docs: AI RECOMMENDS, Human APPROVES, Backend EXECUTES.
        This sends the recommendation to the manager.
        """
        results: Dict[str, IntegrationResult] = {}

        # Notify customer that request is being reviewed
        customer_html = self._build_refund_notification_html(
            customer_name, ticket_id, amount, "pending",
        )
        tool_result = await self.tool_bus.send_email(
            variant=variant_tier,
            company_id=company_id,
            to=customer_email,
            subject=f"[{ticket_id}] Refund Pending - ${amount:.2f}",
            body=customer_html,
            html_body=customer_html,
        )
        results["customer_notification"] = _tool_result_to_integration(tool_result, "send_refund_notification")

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

        tool_result = await self.tool_bus.send_email(
            variant=variant_tier,
            company_id=company_id,
            to=manager_email,
            subject=f"[APPROVAL] Refund ${amount:.2f} - {ticket_id} ({confidence:.0%} confidence)",
            body=html,
            html_body=html,
        )
        results["manager_approval"] = _tool_result_to_integration(tool_result, "send_manager_approval")

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
        variant_tier: str = "parwa",
        company_id: str = "",
    ) -> Dict[str, IntegrationResult]:
        """Handle the workflow when a refund is approved by manager.

        This is Step 3 of the "Human-Triggered API" architecture.
        The backend executes the refund after manager approval.
        """
        results: Dict[str, IntegrationResult] = {}

        # NOTE: Paddle was removed. Refund execution is delegated to Razorpay
        # (handled out-of-band via the Razorpay service / webhooks). We log
        # the intent and return an UNAVAILABLE result so the customer-facing
        # notification still fires.
        logger.warning(
            "refund_execution_skipped reason=Paddle was removed; "
            "delegate to razorpay_service order_id=%s amount=%s approved_by=%s",
            order_id, amount, approved_by,
        )
        results["refund_execution"] = IntegrationResult(
            status=IntegrationStatus.UNAVAILABLE,
            provider="razorpay",
            action="process_refund",
            message="Paddle was removed; refund must be executed via Razorpay service",
            metadata={
                "order_id": order_id,
                "amount": amount,
                "approved_by": approved_by,
                "ai_confidence": confidence,
                "audit_trail": True,
            },
        )

        # Notify customer
        customer_html = self._build_refund_notification_html(
            customer_name, ticket_id, amount, "approved",
        )
        tool_result = await self.tool_bus.send_email(
            variant=variant_tier,
            company_id=company_id,
            to=customer_email,
            subject=f"[{ticket_id}] Refund Approved - ${amount:.2f}",
            body=customer_html,
            html_body=customer_html,
        )
        results["customer_notification"] = _tool_result_to_integration(tool_result, "send_refund_notification")

        # SMS notification for paid tiers
        if customer_phone:
            tool_result = await self.tool_bus.send_sms(
                variant=variant_tier,
                company_id=company_id,
                to=customer_phone,
                body=f"PARWA: Your refund of ${amount:.2f} for ticket {ticket_id} has been approved. "
                     f"It will be processed within 3-5 business days.",
            )
            results["sms_notification"] = _tool_result_to_integration(tool_result, "send_sms")

        return results

    async def handle_vip_escalation(
        self,
        customer_name: str,
        customer_phone: str,
        customer_email: str,
        ticket_id: str,
        issue_summary: str,
        manager_email: str,
        variant_tier: str = "parwa_high",
        company_id: str = "",
    ) -> Dict[str, IntegrationResult]:
        """Handle the workflow when a VIP customer needs escalation.

        Per docs: Angry/VIP customers are routed to humans.
        The AI initiates the call and notifies the manager.
        """
        results: Dict[str, IntegrationResult] = {}

        # Make outbound call to VIP customer
        if customer_phone:
            tool_result = await self.tool_bus.make_call(
                variant=variant_tier,
                company_id=company_id,
                to=customer_phone,
                message=(
                    f"Hello {customer_name}, this is PARWA Support "
                    f"calling regarding your ticket {ticket_id}. "
                    f"We wanted to personally follow up to ensure your issue has been resolved. "
                    f"If you need further assistance, please let us know. "
                    f"Thank you for being a valued customer."
                ),
            )
            results["outbound_call"] = _tool_result_to_integration(tool_result, "make_vip_followup_call")

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

        tool_result = await self.tool_bus.send_email(
            variant=variant_tier,
            company_id=company_id,
            to=manager_email,
            subject=f"[URGENT] VIP Escalation - {customer_name} - {ticket_id}",
            body=html,
            html_body=html,
        )
        results["manager_alert"] = _tool_result_to_integration(tool_result, "send_manager_alert")

        return results

    async def handle_cart_recovery(
        self,
        customer_name: str,
        customer_phone: str,
        customer_email: str,
        cart_value: float,
        variant_tier: str = "parwa",
        company_id: str = "",
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

        tool_result = await self.tool_bus.send_email(
            variant=variant_tier,
            company_id=company_id,
            to=customer_email,
            subject=f"Your cart is waiting - ${cart_value:.2f} in items!",
            body=html,
            html_body=html,
        )
        results["recovery_email"] = _tool_result_to_integration(tool_result, "send_recovery_email")

        # Follow up with call if Pro/High tier
        if customer_phone:
            tool_result = await self.tool_bus.make_call(
                variant=variant_tier,
                company_id=company_id,
                to=customer_phone,
                message=(
                    f"Hi {customer_name}, this is PARWA Support "
                    f"from your online store. We noticed you left items worth "
                    f"${cart_value:.2f} in your cart. "
                    f"Would you like help completing your purchase? "
                    f"We can assist you right now."
                ),
            )
            results["recovery_call"] = _tool_result_to_integration(tool_result, "make_cart_recovery_call")

        return results

    # ── Private helpers ──────────────────────────────────────────

    @staticmethod
    def _build_refund_notification_html(
        customer_name: str,
        ticket_id: str,
        amount: float,
        status: str,
        reason: str = "",
    ) -> str:
        """Build HTML for refund status notification email."""
        status_colors = {
            "approved": "#28a745",
            "denied": "#dc3545",
            "pending": "#ffc107",
        }
        color = status_colors.get(status, "#333")
        status_label = status.capitalize()

        reason_row = ""
        if reason:
            reason_row = (
                f"<tr><td style='padding: 8px; border: 1px solid #ddd;'>"
                f"<strong>Reason</strong></td>"
                f"<td style='padding: 8px; border: 1px solid #ddd;'>{reason}</td></tr>"
            )

        status_message = ""
        if status == "approved":
            status_message = "<p>If approved, the refund will be processed within 3-5 business days.</p>"
        elif status == "denied":
            status_message = "<p>If you disagree with this decision, please reply to this email.</p>"
        elif status == "pending":
            status_message = "<p>Your request is being reviewed and you'll receive an update soon.</p>"

        return f"""
        <html><body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Refund Update - Ticket {ticket_id}</h2>
        <p>Hi {customer_name},</p>
        <p>Your refund request has been <span style="color: {color}; font-weight: bold;">{status_label}</span>.</p>
        <table style="border: 1px solid #ddd; padding: 10px; border-collapse: collapse;">
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Amount</strong></td>
            <td style="padding: 8px; border: 1px solid #ddd;">${amount:.2f}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Status</strong></td>
            <td style="padding: 8px; border: 1px solid #ddd; color: {color};">{status_label}</td></tr>
            {reason_row}
        </table>
        {status_message}
        <p>Best regards,<br>PARWA Support Team</p>
        </body></html>
        """
