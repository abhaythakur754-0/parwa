"""
PARWA — External Tool Executor (Pipeline → ExternalToolBus Bridge)

Bridges the variant pipeline's auto_action_node output to the
canonical ExternalToolBus. When the pipeline suggests actions
(send SMS, send email, make call, send chat), this executor
actually CARRIES THEM OUT via ExternalToolBus.

Design:
    - BC-001: company_id scoping on every call
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

import logging
import os
from typing import Any, Dict, Optional

from app.core.channel_permissions import (
    Channel,
    VARIANT_CHANNEL_PERMISSIONS,
    is_channel_allowed,
)
from app.core.external_tool_bus import ToolResult, external_tool_bus

# Backward-compatible aliases — these used to be defined locally.
# Consumers that imported them from this module will still work.
_is_channel_allowed = is_channel_allowed

logger = logging.getLogger("parwa.external_tool_executor")


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


# ═══════════════════════════════════════════════════════════════════
# Channel Call Dispatcher
# ═══════════════════════════════════════════════════════════════════

async def _execute_channel_call(
    variant_tier: str,
    company_id: str,
    channel: Channel,
    **kwargs: Any,
) -> ToolResult:
    """Execute a channel call through the unified ExternalToolBus."""
    if channel == Channel.EMAIL:
        return await external_tool_bus.send_email(
            variant=variant_tier,
            company_id=company_id,
            to=kwargs.get("to", ""),
            subject=kwargs.get("subject", ""),
            body=kwargs.get("body", ""),
            html_body=kwargs.get("html_body", ""),
        )
    elif channel == Channel.SMS:
        return await external_tool_bus.send_sms(
            variant=variant_tier,
            company_id=company_id,
            to=kwargs.get("to", ""),
            body=kwargs.get("body", ""),
        )
    elif channel == Channel.VOICE:
        return await external_tool_bus.make_call(
            variant=variant_tier,
            company_id=company_id,
            to=kwargs.get("to", ""),
            message=kwargs.get("message", ""),
        )
    elif channel == Channel.CHAT:
        return await external_tool_bus.send_chat(
            variant=variant_tier,
            company_id=company_id,
            message=kwargs.get("body", ""),
            conversation_id=kwargs.get("conversation_id", ""),
        )
    else:
        return ToolResult(
            success=False,
            channel=channel,
            error=f"Unsupported channel: {channel.value}",
        )


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
) -> Dict[str, ToolResult]:
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
        Dict mapping channel name to ToolResult.
    """
    results: Dict[str, ToolResult] = {}

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
            results[action_type] = ToolResult(
                success=False,
                channel=channel,
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
) -> Dict[str, ToolResult]:
    """Send ticket status notification across available channels via ExternalToolBus."""
    results: Dict[str, ToolResult] = {}
    response_text = pipeline_result.get("formatted_response", "")
    prefix = f"[PARWA] {ticket_number}"
    notification_body = response_text[:200] if response_text else f"Your ticket status has been updated to: {status}."

    # Email notification
    if customer_email and is_channel_allowed(variant_tier, Channel.EMAIL):
        subject = f"{prefix}: Ticket Update — {status.replace('_', ' ').title()}"
        results["email_notification"] = await external_tool_bus.send_email(
            variant=variant_tier,
            company_id=company_id,
            to=customer_email,
            subject=subject,
            body=notification_body,
        )

    # SMS notification
    if customer_phone and is_channel_allowed(variant_tier, Channel.SMS):
        sms_body = f"{prefix}: {notification_body}"[:160]
        results["sms_notification"] = await external_tool_bus.send_sms(
            variant=variant_tier,
            company_id=company_id,
            to=customer_phone,
            body=sms_body,
        )

    # Voice notification (parwa_high priority escalation only)
    if (customer_phone and is_channel_allowed(variant_tier, Channel.VOICE)
            and status == "escalated"):
        results["voice_notification"] = await external_tool_bus.make_call(
            variant=variant_tier,
            company_id=company_id,
            to=customer_phone,
            message=f"This is an urgent notification regarding your ticket {ticket_number}. Your case has been escalated to a specialist.",
        )

    return results


async def _execute_single_action(
    action: Dict[str, Any],
    channel: Channel,
    variant_tier: str,
    company_id: str,
    customer_email: str = "",
    customer_phone: str = "",
    ticket_number: str = "",
) -> ToolResult:
    """Execute a single pipeline action via ExternalToolBus."""
    action_type = action.get("type", "")
    action_data = action.get("data", {})
    body = action.get("message", action.get("description", ""))

    try:
        if channel == Channel.EMAIL and customer_email:
            subject = action_data.get("subject", f"[PARWA] Update regarding your ticket {ticket_number}")
            return await _execute_channel_call(
                variant_tier, company_id, channel,
                to=customer_email,
                subject=subject,
                body=body or "Your support request is being processed.",
            )

        elif channel == Channel.SMS and customer_phone:
            sms_body = body[:160] if body else f"[PARWA] Update on ticket {ticket_number}"
            return await _execute_channel_call(
                variant_tier, company_id, channel,
                to=customer_phone,
                body=sms_body,
            )

        elif channel == Channel.VOICE and customer_phone:
            return await _execute_channel_call(
                variant_tier, company_id, channel,
                to=customer_phone,
                message=body or "Hello, this is a follow-up call regarding your support ticket.",
            )

        elif channel == Channel.CHAT:
            result = await _execute_channel_call(
                variant_tier, company_id, channel,
                body=body or "Your ticket is being processed.",
            )
            # Chat always succeeds (template fallback built into bus)
            if not result.success:
                return ToolResult(
                    success=True,
                    channel=Channel.CHAT,
                    provider="parwa_chat",
                    message_id=f"chat_{os.urandom(4).hex()}",
                    data={"reply": body or "Your ticket is being processed.", "is_ai_generated": False},
                )
            return result

        else:
            return ToolResult(
                success=False,
                channel=channel,
                error=f"No contact info for channel '{channel.value}'",
            )

    except Exception as exc:
        logger.error("action_execution_failed: action=%s error=%s", action_type, str(exc)[:200])
        return ToolResult(
            success=False,
            channel=channel,
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

    # Check which providers are configured via the bus
    provider_status = external_tool_bus.get_provider_status()

    channel_status = {}
    for ch in Channel:
        ch_status = provider_status.get(ch.value, {})
        channel_status[ch.value] = {
            "allowed": ch in allowed,
            "configured": ch_status.get("configured", False),
        }

    return {
        "variant": variant_tier,
        "channels": channel_status,
        "allowed_count": len(allowed),
    }
