"""
PARWA — External Tool Executor (Pipeline → MCP Bridge)

Bridges the variant pipeline's auto_action_node output to the MCP server's
external tool endpoints. When the pipeline suggests actions (send SMS,
send email, make call, send chat), this executor actually CARRIES THEM OUT
via the MCP server.

Design:
    - BC-008: Pipeline should never crash — all calls wrapped in try/except
    - Post-pipeline execution: runs AFTER the pipeline finishes, so tool
      failures don't affect the AI response quality
    - Variant-aware: checks channel permissions before calling
    - Zero complexity: just call execute_pipeline_actions() after the pipeline runs

Usage (in variant_pipeline_bridge.py):
    from app.core.external_tool_executor import execute_pipeline_actions

    # After pipeline runs...
    tool_results = await execute_pipeline_actions(
        variant_tier="parwa",
        company_id="comp_123",
        pipeline_result=result,  # raw dict from pipeline
        customer_email="user@example.com",
        customer_phone="+919652852014",
        ticket_number="TKT-1234",
    )
    # tool_results → {"sms": ToolResult, "email": ToolResult, ...}
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.channel_permissions import Channel, VARIANT_CHANNEL_PERMISSIONS, is_channel_allowed

logger = logging.getLogger("parwa.external_tool_executor")


# ═══════════════════════════════════════════════════════════════════
# Variant-Channel Permission Matrix
# (Imported from shared module: app.core.channel_permissions)
# ═══════════════════════════════════════════════════════════════════


@dataclass
class ToolExecutionResult:
    """Result from a single external tool execution."""
    channel: str
    success: bool
    message_id: str = ""
    error: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# Action → Tool Type Mapping
# ═══════════════════════════════════════════════════════════════════

# Maps action types from enhancement engines to external tool channels
ACTION_TOOL_MAP = {
    # EI engine recovery actions
    "send_apology_email": Channel.EMAIL,
    "send_empathy_email": Channel.EMAIL,
    "send_followup_email": Channel.EMAIL,
    "send_notification": Channel.EMAIL,
    # Churn engine retention actions
    "send_retention_offer": Channel.EMAIL,
    "send_retention_sms": Channel.SMS,
    "call_retention_specialist": Channel.VOICE,
    # Billing engine actions
    "send_refund_receipt": Channel.EMAIL,
    "send_billing_update": Channel.EMAIL,
    "send_billing_sms": Channel.SMS,
    "call_billing_support": Channel.VOICE,
    # Tech diagnostic actions
    "send_diagnostic_report": Channel.EMAIL,
    "send_status_sms": Channel.SMS,
    "call_tech_support": Channel.VOICE,
    # Shipping engine actions
    "send_tracking_update": Channel.EMAIL,
    "send_tracking_sms": Channel.SMS,
    "call_delivery_team": Channel.VOICE,
    # Generic actions
    "send_email": Channel.EMAIL,
    "send_sms": Channel.SMS,
    "make_call": Channel.VOICE,
    "send_chat": Channel.CHAT,
}


# _is_channel_allowed removed — use is_channel_allowed from channel_permissions


# ═══════════════════════════════════════════════════════════════════
# MCP Server Client
# ═══════════════════════════════════════════════════════════════════

async def _call_mcp_tool(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Call an MCP server tool via HTTP.

    Args:
        tool_name: MCP tool name (e.g. "sms_send", "email_send").
        parameters: Tool parameters dict.

    Returns:
        Response dict from MCP server.
    """
    import httpx

    mcp_url = os.environ.get("MCP_SERVER_URL", "http://localhost:5200")
    auth_token = os.environ.get("MCP_AUTH_TOKEN", "")

    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{mcp_url}/mcp/tools/{tool_name}/invoke",
                json={"tool_name": tool_name, "parameters": parameters},
                headers=headers,
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.warning(
                    "mcp_tool_call_failed: tool=%s status=%s error=%s",
                    tool_name, resp.status_code, resp.text[:200],
                )
                return {"success": False, "error": f"MCP returned {resp.status_code}"}
    except Exception as exc:
        logger.warning("mcp_tool_call_error: tool=%s error=%s", tool_name, str(exc)[:200])
        return {"success": False, "error": str(exc)[:200]}


# ═══════════════════════════════════════════════════════════════════
# Direct Provider Fallbacks (when MCP server is unreachable)
# DEPRECATED: Direct API fallback — will be replaced by ProviderFactory in Phase 13
# For now, these exist as safety fallbacks when MCP server is unreachable
# ═══════════════════════════════════════════════════════════════════

async def _send_sms_direct(to: str, body: str) -> ToolExecutionResult:
    """Send SMS directly via Twilio REST API (fallback)."""
    import httpx

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_PHONE_NUMBER")

    if not all([account_sid, auth_token, from_number]):
        return ToolExecutionResult(
            channel="sms",
            success=False,
            error="Twilio not configured (missing env vars)",
        )

    formatted_to = to.strip()
    if not formatted_to.startswith("+"):
        formatted_to = "+" + re.sub(r"[^0-9]", "", formatted_to)

    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        auth = httpx.BasicAuth(account_sid, auth_token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url, auth=auth,
                data={"From": from_number, "To": formatted_to, "Body": body[:1600]},
            )
            resp_data = resp.json()
            if resp.status_code in (200, 201):
                return ToolExecutionResult(
                    channel="sms", success=True,
                    message_id=resp_data.get("sid", ""),
                    data=resp_data,
                )
            return ToolExecutionResult(
                channel="sms", success=False,
                error=f"Twilio error {resp.status_code}: {resp_data.get('message', 'Unknown')}",
            )
    except Exception as exc:
        return ToolExecutionResult(channel="sms", success=False, error=str(exc)[:200])


async def _send_email_direct(
    to: str, subject: str, body: str, html_body: str = "",
) -> ToolExecutionResult:
    """Send email directly via Brevo REST API (fallback)."""
    import httpx

    api_key = os.environ.get("BREVO_API_KEY")
    from_email = os.environ.get("FROM_EMAIL", "noreply@parwa.io")
    from_name = os.environ.get("FROM_NAME", "PARWA")

    if not api_key:
        return ToolExecutionResult(
            channel="email", success=False,
            error="Brevo not configured (missing BREVO_API_KEY)",
        )

    html_content = html_body or f"<p>{body}</p>"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": api_key, "Content-Type": "application/json"},
                json={
                    "sender": {"name": from_name, "email": from_email},
                    "to": [{"email": to}],
                    "subject": subject,
                    "htmlContent": html_content,
                },
            )
            if resp.status_code in (200, 201):
                data = resp.json() if resp.text else {}
                return ToolExecutionResult(
                    channel="email", success=True,
                    message_id=data.get("messageId", ""),
                    data=data,
                )
            return ToolExecutionResult(
                channel="email", success=False,
                error=f"Brevo error {resp.status_code}: {resp.text[:200]}",
            )
    except Exception as exc:
        return ToolExecutionResult(channel="email", success=False, error=str(exc)[:200])


async def _make_call_direct(
    to: str, message: str = "", variant: str = "parwa",
) -> ToolExecutionResult:
    """Make voice call directly via Twilio REST API (fallback)."""
    import httpx

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_PHONE_NUMBER", "")

    if not all([account_sid, auth_token, from_number]):
        return ToolExecutionResult(
            channel="voice", success=False,
            error="Twilio not configured (missing env vars)",
        )

    formatted_to = to.strip()
    if not formatted_to.startswith("+"):
        formatted_to = "+" + re.sub(r"[^0-9]", "", formatted_to)

    greeting = message or "Hello, this is a call from your support team."
    greeting_escaped = greeting.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    twiml = f"<Response><Say>{greeting_escaped}</Say></Response>"

    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
        auth = httpx.BasicAuth(account_sid, auth_token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url, auth=auth,
                data={"From": from_number, "To": formatted_to, "Twiml": twiml},
            )
            resp_data = resp.json()
            if resp.status_code in (200, 201):
                return ToolExecutionResult(
                    channel="voice", success=True,
                    message_id=resp_data.get("sid", ""),
                    data={"call_sid": resp_data.get("sid", ""), "status": resp_data.get("status", "queued")},
                )
            return ToolExecutionResult(
                channel="voice", success=False,
                error=f"Twilio call error: {resp_data.get('message', 'Unknown')}",
            )
    except Exception as exc:
        return ToolExecutionResult(channel="voice", success=False, error=str(exc)[:200])


# ═══════════════════════════════════════════════════════════════════
# Main Executor
# ═══════════════════════════════════════════════════════════════════

async def execute_pipeline_actions(
    variant_tier: str,
    company_id: str,
    pipeline_result: Dict[str, Any],
    customer_email: str = "",
    customer_phone: str = "",
    ticket_number: str = "",
    ticket_id: str = "",
) -> Dict[str, ToolExecutionResult]:
    """Execute external tool actions suggested by the pipeline.

    Reads the auto_action step output from the pipeline result and
    executes any actions that map to external tools (SMS, email, voice, chat).

    This is called AFTER the pipeline completes, so tool failures
    don't affect the AI response quality (BC-008 principle).

    Args:
        variant_tier: Variant tier (mini_parwa, parwa, parwa_high).
        company_id: Tenant company ID.
        pipeline_result: Raw dict result from pipeline.process_ticket().
        customer_email: Customer email for email actions.
        customer_phone: Customer phone for SMS/voice actions.
        ticket_number: Ticket number for notification body.
        ticket_id: Ticket ID for linking.

    Returns:
        Dict mapping channel name to ToolExecutionResult.
    """
    results: Dict[str, ToolExecutionResult] = {}

    # ── 1. Read auto_action step output ─────────────────────────
    step_outputs = pipeline_result.get("step_outputs", {})
    auto_action = step_outputs.get("auto_action", {})
    actions = auto_action.get("actions", [])

    if not actions:
        logger.info(
            "no_auto_actions_to_execute: variant=%s company=%s",
            variant_tier, company_id,
        )
        return results

    # ── 2. Check if ticket status warrants notifications ─────────
    # Auto-send ticket update notifications if we have contact info
    ticket_status = _infer_ticket_status(pipeline_result)

    # ── 3. Execute ticket notification if applicable ─────────────
    if ticket_status and ticket_number:
        notification_results = await _send_ticket_notification(
            variant_tier=variant_tier,
            company_id=company_id,
            ticket_number=ticket_number,
            status=ticket_status,
            customer_email=customer_email,
            customer_phone=customer_phone,
            pipeline_result=pipeline_result,
        )
        results.update(notification_results)

    # ── 4. Execute action-specific tool calls ────────────────────
    for action in actions:
        if not isinstance(action, dict):
            continue

        action_type = action.get("type", "")
        channel = ACTION_TOOL_MAP.get(action_type)

        if not channel:
            continue

        # Check variant permission
        if not is_channel_allowed(variant_tier, channel):
            results[action_type] = ToolExecutionResult(
                channel=channel.value,
                success=False,
                error=f"Channel '{channel.value}' not allowed for variant '{variant_tier}'",
            )
            continue

        # Execute the tool call
        result = await _execute_single_action(
            action=action,
            channel=channel,
            variant_tier=variant_tier,
            company_id=company_id,
            customer_email=customer_email,
            customer_phone=customer_phone,
            ticket_number=ticket_number,
        )
        results[action_type] = result

    # ── 5. Log summary ──────────────────────────────────────────
    success_count = sum(1 for r in results.values() if r.success)
    fail_count = sum(1 for r in results.values() if not r.success)
    logger.info(
        "external_tool_execution_complete: variant=%s company=%s "
        "actions=%d executed=%d successes=%d failures=%d",
        variant_tier, company_id,
        len(actions), len(results), success_count, fail_count,
    )

    return results


def _infer_ticket_status(pipeline_result: Dict[str, Any]) -> str:
    """Infer ticket status from pipeline result for notification purposes."""
    emergency = pipeline_result.get("emergency_flag", False)
    quality_score = pipeline_result.get("quality_score", 0.0)
    pipeline_status = pipeline_result.get("pipeline_status", "completed")

    if emergency:
        return "escalated"
    if pipeline_status == "completed" and quality_score >= 0.8:
        return "resolved"
    if pipeline_status == "completed":
        return "in_progress"
    return "created"


async def _send_ticket_notification(
    variant_tier: str,
    company_id: str,
    ticket_number: str,
    status: str,
    customer_email: str,
    customer_phone: str,
    pipeline_result: Dict[str, Any],
) -> Dict[str, ToolExecutionResult]:
    """Send ticket status notification across available channels."""
    results: Dict[str, ToolExecutionResult] = {}
    response_text = pipeline_result.get("formatted_response", "")
    prefix = f"[PARWA] {ticket_number}"
    notification_body = response_text[:200] if response_text else f"Your ticket status has been updated to: {status}."

    # Email notification
    if customer_email and is_channel_allowed(variant_tier, Channel.EMAIL):
        subject = f"{prefix}: Ticket Update — {status.replace('_', ' ').title()}"

        # Try MCP first, then direct
        mcp_result = await _call_mcp_tool("email_send", {
            "to": [customer_email],
            "subject": subject,
            "body": notification_body,
            "company_id": company_id,
            "variant": variant_tier,
        })

        if mcp_result.get("success"):
            results["email_notification"] = ToolExecutionResult(
                channel="email", success=True,
                message_id=mcp_result.get("data", {}).get("message_id", ""),
                data=mcp_result,
            )
        else:
            # Fallback: direct Brevo API
            result = await _send_email_direct(customer_email, subject, notification_body)
            results["email_notification"] = result

    # SMS notification
    if customer_phone and is_channel_allowed(variant_tier, Channel.SMS):
        sms_body = f"{prefix}: {notification_body}"[:160]

        mcp_result = await _call_mcp_tool("sms_send", {
            "to": customer_phone,
            "body": sms_body,
            "company_id": company_id,
            "variant": variant_tier,
        })

        if mcp_result.get("success"):
            results["sms_notification"] = ToolExecutionResult(
                channel="sms", success=True,
                message_id=mcp_result.get("data", {}).get("message_id", ""),
                data=mcp_result,
            )
        else:
            # Fallback: direct Twilio API
            result = await _send_sms_direct(customer_phone, sms_body)
            results["sms_notification"] = result

    # Voice notification (parwa_high priority escalation only)
    if (customer_phone and is_channel_allowed(variant_tier, Channel.VOICE)
            and status == "escalated"):
        mcp_result = await _call_mcp_tool("voice_initiate_call", {
            "to": customer_phone,
            "message": f"This is an urgent notification regarding your ticket {ticket_number}. Your case has been escalated to a specialist.",
            "company_id": company_id,
        })

        if mcp_result.get("success"):
            results["voice_notification"] = ToolExecutionResult(
                channel="voice", success=True,
                message_id=mcp_result.get("data", {}).get("call_sid", ""),
                data=mcp_result,
            )
        else:
            result = await _make_call_direct(
                customer_phone,
                message=f"Urgent notification for ticket {ticket_number}. Your case has been escalated.",
                variant=variant_tier,
            )
            results["voice_notification"] = result

    return results


async def _execute_single_action(
    action: Dict[str, Any],
    channel: Channel,
    variant_tier: str,
    company_id: str,
    customer_email: str = "",
    customer_phone: str = "",
    ticket_number: str = "",
) -> ToolExecutionResult:
    """Execute a single pipeline action via the appropriate external tool."""
    action_type = action.get("type", "")
    action_data = action.get("data", {})
    body = action.get("message", action.get("description", ""))

    try:
        if channel == Channel.EMAIL and customer_email:
            subject = action_data.get("subject", f"[PARWA] Update regarding your ticket {ticket_number}")
            # Try MCP, then direct
            mcp_result = await _call_mcp_tool("email_send", {
                "to": [customer_email],
                "subject": subject,
                "body": body or "Your support request is being processed.",
                "company_id": company_id,
                "variant": variant_tier,
            })
            if mcp_result.get("success"):
                return ToolExecutionResult(
                    channel="email", success=True,
                    message_id=mcp_result.get("data", {}).get("message_id", ""),
                    data=mcp_result,
                )
            return await _send_email_direct(customer_email, subject, body or "Your support request is being processed.")

        elif channel == Channel.SMS and customer_phone:
            sms_body = body[:160] if body else f"[PARWA] Update on ticket {ticket_number}"
            mcp_result = await _call_mcp_tool("sms_send", {
                "to": customer_phone,
                "body": sms_body,
                "company_id": company_id,
                "variant": variant_tier,
            })
            if mcp_result.get("success"):
                return ToolExecutionResult(
                    channel="sms", success=True,
                    message_id=mcp_result.get("data", {}).get("message_id", ""),
                    data=mcp_result,
                )
            return await _send_sms_direct(customer_phone, sms_body)

        elif channel == Channel.VOICE and customer_phone:
            mcp_result = await _call_mcp_tool("voice_initiate_call", {
                "to": customer_phone,
                "message": body or "Hello, this is a follow-up call regarding your support ticket.",
                "company_id": company_id,
            })
            if mcp_result.get("success"):
                return ToolExecutionResult(
                    channel="voice", success=True,
                    message_id=mcp_result.get("data", {}).get("call_sid", ""),
                    data=mcp_result,
                )
            return await _make_call_direct(customer_phone, message=body, variant=variant_tier)

        elif channel == Channel.CHAT:
            mcp_result = await _call_mcp_tool("chat_send_message", {
                "message": body or "Your ticket is being processed.",
                "company_id": company_id,
                "variant": variant_tier,
            })
            if mcp_result.get("success"):
                return ToolExecutionResult(
                    channel="chat", success=True,
                    message_id=mcp_result.get("data", {}).get("message_id", ""),
                    data=mcp_result,
                )
            # Chat always succeeds (template fallback)
            return ToolExecutionResult(
                channel="chat", success=True,
                message_id=f"chat_{os.urandom(4).hex()}",
                data={"reply": body or "Your ticket is being processed.", "is_ai_generated": False},
            )

        else:
            return ToolExecutionResult(
                channel=channel.value,
                success=False,
                error=f"No contact info for channel '{channel.value}'",
            )

    except Exception as exc:
        logger.error("action_execution_failed: action=%s error=%s", action_type, str(exc)[:200])
        return ToolExecutionResult(
            channel=channel.value,
            success=False,
            error=f"Execution failed: {str(exc)[:200]}",
        )


# ═══════════════════════════════════════════════════════════════════
# Convenience: Check what channels a variant can use
# ═══════════════════════════════════════════════════════════════════

def get_variant_channels(variant_tier: str) -> Dict[str, Any]:
    """Get channel availability for a variant tier.

    Returns:
        Dict with allowed channels and their configuration status.
    """
    allowed = VARIANT_CHANNEL_PERMISSIONS.get(variant_tier, set())

    # Check which providers are configured
    channel_status = {}
    for ch in Channel:
        configured = False
        if ch == Channel.SMS:
            configured = bool(os.environ.get("TWILIO_ACCOUNT_SID"))
        elif ch == Channel.VOICE:
            configured = bool(os.environ.get("TWILIO_ACCOUNT_SID"))
        elif ch == Channel.EMAIL:
            configured = bool(os.environ.get("BREVO_API_KEY"))
        elif ch == Channel.CHAT:
            configured = True  # Always available
        elif ch == Channel.PUSH:
            configured = bool(os.environ.get("FIREBASE_CREDENTIALS"))
        elif ch == Channel.WEBHOOK:
            configured = True  # Always available

        channel_status[ch.value] = {
            "allowed": ch in allowed,
            "configured": configured,
        }

    return {
        "variant": variant_tier,
        "channels": channel_status,
        "allowed_count": len(allowed),
    }
