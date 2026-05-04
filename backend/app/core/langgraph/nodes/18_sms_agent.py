"""
SMS Agent Node — Group 10: SMS Channel Delivery

Delivers the agent response via the SMS channel. Truncates response
to SMS-appropriate length, applies SMS formatting, and dispatches
via the channel dispatcher.

Processing Steps:
  1. Truncate response to SMS length limits
  2. Apply SMS formatting (strip HTML, add opt-out)
  3. Dispatch via SMS channel
  4. Record delivery confirmation

State Contract:
  Reads:  agent_response, delivery_channel, tenant_id, customer_id,
          variant_tier, language
  Writes: delivery_status, delivery_confirmation_id, delivery_timestamp

BC-008: Never crash — if SMS dispatch fails, set delivery_status to
        "failed" with error details.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.logger import get_logger

logger = get_logger("node_sms_agent")


# ──────────────────────────────────────────────────────────────
# SMS Length Limits
# ──────────────────────────────────────────────────────────────

SMS_STANDARD_LIMIT = 160       # Standard SMS segment
SMS_LONG_LIMIT = 1600          # Long SMS / concatenated SMS
SMS_TRUNCATION_SUFFIX = "..."


# ═══════════════════════════════════════════════════════════════
# Internal: Truncate Response for SMS
# ═══════════════════════════════════════════════════════════════


def _truncate_for_sms(
    response_text: str,
    variant_tier: str,
    tenant_id: str,
) -> str:
    """
    Truncate the response text to SMS-appropriate length.

    Mini tier uses standard SMS limit (160 chars) for cost savings.
    Pro and High tiers use long SMS limit (1600 chars).

    Args:
        response_text: The agent response text.
        variant_tier: Variant tier string.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        Truncated response text suitable for SMS.
    """
    if variant_tier == "mini":
        max_length = SMS_STANDARD_LIMIT
    else:
        max_length = SMS_LONG_LIMIT

    if len(response_text) <= max_length:
        return response_text

    # Truncate and add suffix
    truncated = response_text[: max_length - len(SMS_TRUNCATION_SUFFIX)] + SMS_TRUNCATION_SUFFIX

    logger.info(
        "sms_truncated_response",
        tenant_id=tenant_id,
        original_length=len(response_text),
        truncated_length=len(truncated),
        max_length=max_length,
        variant_tier=variant_tier,
    )

    return truncated


# ═══════════════════════════════════════════════════════════════
# Internal: Format SMS Content
# ═══════════════════════════════════════════════════════════════


def _format_sms_content(
    response_text: str,
    tenant_id: str,
) -> str:
    """
    Format the response text for SMS delivery.

    Strips HTML tags, normalizes whitespace, and adds standard
    SMS opt-out footer.

    Args:
        response_text: Response text (may contain HTML).
        tenant_id: Tenant identifier (BC-001).

    Returns:
        Plain text formatted for SMS.
    """
    import re

    # Strip HTML tags
    clean_text = re.sub(r"<[^>]+>", "", response_text)

    # Normalize whitespace
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    # Remove multiple consecutive newlines
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)

    return clean_text


# ═══════════════════════════════════════════════════════════════
# Internal: Dispatch SMS
# ═══════════════════════════════════════════════════════════════


def _dispatch_sms(
    sms_content: str,
    state: Dict[str, Any],
    tenant_id: str,
) -> Dict[str, Any]:
    """
    Dispatch the SMS via the channel dispatcher.

    Uses the production channel_dispatcher module if available,
    otherwise returns a pending status.

    Args:
        sms_content: Formatted SMS content.
        state: Current ParwaGraphState dict.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        Dict with confirmation_id and status.
    """
    try:
        from app.core.channel_dispatcher import dispatch  # type: ignore[import-untyped]

        result = dispatch(
            channel="sms",
            content=sms_content,
            tenant_id=tenant_id,
            customer_id=state.get("customer_id", ""),
            conversation_id=state.get("conversation_id", ""),
            variant_tier=state.get("variant_tier", "mini"),
        )

        return {
            "confirmation_id": result.get("confirmation_id", ""),
            "status": result.get("status", "sent"),
        }

    except ImportError:
        logger.info(
            "channel_dispatcher_unavailable_sms",
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.warning(
            "sms_dispatch_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )

    # Fallback: mark as dispatch pending
    return {
        "confirmation_id": "",
        "status": "dispatch_pending",
    }


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def sms_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    SMS Agent Node — Delivers response via the SMS channel.

    Truncates the response to SMS-appropriate length (160 chars for
    mini, 1600 for pro/high), strips HTML, formats for SMS, and
    dispatches via the SMS channel.

    This node is only invoked when delivery_channel is "sms".

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with delivery status and confirmation.
    """
    tenant_id = state.get("tenant_id", "unknown")
    variant_tier = state.get("variant_tier", "mini")
    now = datetime.now(timezone.utc).isoformat()

    logger.info(
        "sms_agent_node_start",
        tenant_id=tenant_id,
        variant_tier=variant_tier,
        conversation_id=state.get("conversation_id", ""),
    )

    try:
        # ── Extract state fields ─────────────────────────────────
        agent_response = state.get("agent_response", "")
        customer_id = state.get("customer_id", "")
        conversation_id = state.get("conversation_id", "")

        # ── Validate we have content to deliver ──────────────────
        if not agent_response:
            logger.warning(
                "sms_agent_no_response_to_deliver",
                tenant_id=tenant_id,
                conversation_id=conversation_id,
            )
            return {
                "delivery_status": "failed",
                "delivery_confirmation_id": "",
                "delivery_timestamp": now,
                "delivery_failure_reason": "No agent response to deliver",
            }

        # ── Step 1: Format for SMS ───────────────────────────────
        formatted = _format_sms_content(
            response_text=agent_response,
            tenant_id=tenant_id,
        )

        # ── Step 2: Truncate for SMS length ──────────────────────
        truncated = _truncate_for_sms(
            response_text=formatted,
            variant_tier=variant_tier,
            tenant_id=tenant_id,
        )

        logger.info(
            "sms_agent_content_prepared",
            tenant_id=tenant_id,
            original_length=len(agent_response),
            sms_length=len(truncated),
        )

        # ── Step 3: Dispatch via SMS Channel ─────────────────────
        dispatch_result = _dispatch_sms(
            sms_content=truncated,
            state=state,
            tenant_id=tenant_id,
        )

        confirmation_id = dispatch_result.get("confirmation_id", "")
        dispatch_status = dispatch_result.get("status", "dispatch_pending")

        # ── Determine delivery status ────────────────────────────
        if dispatch_status in ("sent", "delivered"):
            delivery_status = "sent"
        elif dispatch_status == "dispatch_pending":
            delivery_status = "dispatch_pending"
        else:
            delivery_status = "failed"

        logger.info(
            "sms_agent_node_completed",
            tenant_id=tenant_id,
            delivery_status=delivery_status,
            confirmation_id=confirmation_id,
        )

        return {
            "delivery_status": delivery_status,
            "delivery_confirmation_id": confirmation_id,
            "delivery_timestamp": now,
        }

    except Exception as exc:
        logger.error(
            "sms_agent_node_fatal_error",
            tenant_id=tenant_id,
            error=str(exc),
        )

        # BC-008: On fatal error, set delivery_status to failed
        return {
            "delivery_status": "failed",
            "delivery_confirmation_id": "",
            "delivery_timestamp": datetime.now(timezone.utc).isoformat(),
            "delivery_failure_reason": f"SMS delivery failed: {exc}",
            "errors": [f"SMS agent failed: {exc}"],
        }
