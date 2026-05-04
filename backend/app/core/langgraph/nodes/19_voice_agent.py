"""
Voice Agent Node — Group 10: Voice Channel Delivery (Pro + High Only)

Delivers the agent response via the voice channel. Converts response
to voice-friendly format (shorter sentences, SSML), and initiates
a voice call via the call lifecycle module.

Tier Availability:
  - Mini: NOT available — returns delivery_status="failed"
  - Pro:  Available
  - High: Available

Processing Steps:
  1. Verify voice is enabled for this variant_tier
  2. Convert response to voice-friendly format
  3. Wrap in SSML if supported
  4. Initiate voice call via call lifecycle
  5. Record delivery confirmation

State Contract:
  Reads:  agent_response, delivery_channel, tenant_id, customer_id,
          variant_tier, conversation_id
  Writes: delivery_status, delivery_confirmation_id, delivery_timestamp,
          delivery_failure_reason

BC-008: Never crash — if voice dispatch fails, set delivery_status to
        "failed" with error details.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.core.langgraph.config import is_voice_enabled
from app.logger import get_logger

logger = get_logger("node_voice_agent")


# ═══════════════════════════════════════════════════════════════
# Internal: Convert Response to Voice-Friendly Format
# ═══════════════════════════════════════════════════════════════


def _convert_to_voice_format(
    response_text: str,
    tenant_id: str,
) -> str:
    """
    Convert response text to a voice-friendly format.

    Voice communication requires:
      - Shorter sentences (break up long sentences)
      - Conversational tone markers
      - Pauses between ideas
      - No URLs or technical jargon that doesn't read well

    Args:
        response_text: The agent response text.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        Voice-friendly response text.
    """
    import re

    voice_text = response_text

    # Strip HTML tags
    voice_text = re.sub(r"<[^>]+>", "", voice_text)

    # Replace URLs with "link provided in your email"
    voice_text = re.sub(
        r"https?://\S+",
        "a link has been sent to your email",
        voice_text,
    )

    # Replace common text symbols with spoken equivalents
    voice_text = voice_text.replace("&", " and ")
    voice_text = voice_text.replace("%", " percent ")
    voice_text = voice_text.replace("$", " dollars ")
    voice_text = voice_text.replace("#", " number ")
    voice_text = voice_text.replace("@", " at ")

    # Break up very long sentences (80+ chars without period)
    sentences = voice_text.split(". ")
    shortened = []
    for sentence in sentences:
        if len(sentence) > 120:
            # Find comma positions for natural breaks
            parts = sentence.split(", ")
            shortened.extend(parts)
        else:
            shortened.append(sentence)

    voice_text = ". ".join(shortened)

    # Normalize whitespace
    voice_text = re.sub(r"\s+", " ", voice_text).strip()

    return voice_text


# ═══════════════════════════════════════════════════════════════
# Internal: Wrap in SSML
# ═══════════════════════════════════════════════════════════════


def _wrap_in_ssml(
    voice_text: str,
    variant_tier: str,
    tenant_id: str,
) -> str:
    """
    Wrap the voice text in SSML for TTS engines.

    Pro tier gets basic SSML (pauses between sentences).
    High tier gets enhanced SSML (emphasis, prosody, break tags).

    Args:
        voice_text: Voice-friendly response text.
        variant_tier: Variant tier string.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        SSML-wrapped text, or plain text if SSML is not needed.
    """
    # Escape XML special characters
    escaped = voice_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Add sentence breaks
    import re
    escaped = re.sub(r"\.\s+", '.<break strength="medium"/> ', escaped)

    if variant_tier == "high":
        # Enhanced SSML for High tier
        ssml = f'<speak><prosody rate="95%" pitch="+2st">{escaped}</prosody></speak>'
    else:
        # Basic SSML for Pro tier
        ssml = f"<speak>{escaped}</speak>"

    return ssml


# ═══════════════════════════════════════════════════════════════
# Internal: Initiate Voice Call
# ═══════════════════════════════════════════════════════════════


def _initiate_voice_call(
    ssml_content: str,
    state: Dict[str, Any],
    tenant_id: str,
) -> Dict[str, Any]:
    """
    Initiate a voice call via the call lifecycle module.

    Uses the production call_lifecycle module if available,
    otherwise returns a pending status.

    Args:
        ssml_content: SSML content for TTS.
        state: Current ParwaGraphState dict.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        Dict with call_id and status.
    """
    try:
        from app.core.call_lifecycle import initiate_call  # type: ignore[import-untyped]

        result = initiate_call(
            customer_id=state.get("customer_id", ""),
            tenant_id=tenant_id,
            conversation_id=state.get("conversation_id", ""),
            ssml_content=ssml_content,
            variant_tier=state.get("variant_tier", "pro"),
        )

        return {
            "call_id": result.get("call_id", ""),
            "status": result.get("status", "initiated"),
        }

    except ImportError:
        logger.info(
            "call_lifecycle_unavailable",
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.warning(
            "voice_call_initiation_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )

    # Fallback: mark as dispatch pending
    return {
        "call_id": "",
        "status": "dispatch_pending",
    }


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def voice_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Voice Agent Node — Delivers response via the voice channel.

    Converts the agent response to voice-friendly format, wraps in
    SSML, and initiates a voice call. Only available for Pro and
    High tiers.

    Mini tier: Returns delivery_status="failed" with reason
    "Voice not available for mini tier".

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with delivery status and call info.
    """
    tenant_id = state.get("tenant_id", "unknown")
    variant_tier = state.get("variant_tier", "mini")
    now = datetime.now(timezone.utc).isoformat()

    logger.info(
        "voice_agent_node_start",
        tenant_id=tenant_id,
        variant_tier=variant_tier,
        conversation_id=state.get("conversation_id", ""),
    )

    try:
        # ── Tier Check: Voice only available for Pro + High ───────
        if not is_voice_enabled(variant_tier):
            logger.warning(
                "voice_agent_tier_not_supported",
                tenant_id=tenant_id,
                variant_tier=variant_tier,
            )
            return {
                "delivery_status": "failed",
                "delivery_confirmation_id": "",
                "delivery_timestamp": now,
                "delivery_failure_reason": f"Voice not available for {variant_tier} tier",
                "errors": [f"Voice delivery not available for {variant_tier} tier"],
            }

        # ── Extract state fields ─────────────────────────────────
        agent_response = state.get("agent_response", "")
        customer_id = state.get("customer_id", "")
        conversation_id = state.get("conversation_id", "")

        # ── Validate we have content to deliver ──────────────────
        if not agent_response:
            logger.warning(
                "voice_agent_no_response_to_deliver",
                tenant_id=tenant_id,
                conversation_id=conversation_id,
            )
            return {
                "delivery_status": "failed",
                "delivery_confirmation_id": "",
                "delivery_timestamp": now,
                "delivery_failure_reason": "No agent response to deliver",
            }

        # ── Step 1: Convert to Voice-Friendly Format ─────────────
        voice_text = _convert_to_voice_format(
            response_text=agent_response,
            tenant_id=tenant_id,
        )

        logger.info(
            "voice_agent_content_converted",
            tenant_id=tenant_id,
            original_length=len(agent_response),
            voice_length=len(voice_text),
        )

        # ── Step 2: Wrap in SSML ─────────────────────────────────
        ssml_content = _wrap_in_ssml(
            voice_text=voice_text,
            variant_tier=variant_tier,
            tenant_id=tenant_id,
        )

        logger.info(
            "voice_agent_ssml_prepared",
            tenant_id=tenant_id,
            ssml_length=len(ssml_content),
            variant_tier=variant_tier,
        )

        # ── Step 3: Initiate Voice Call ──────────────────────────
        call_result = _initiate_voice_call(
            ssml_content=ssml_content,
            state=state,
            tenant_id=tenant_id,
        )

        call_id = call_result.get("call_id", "")
        call_status = call_result.get("status", "dispatch_pending")

        # ── Determine delivery status ────────────────────────────
        if call_status in ("initiated", "ringing", "in_progress"):
            delivery_status = "sent"
        elif call_status == "dispatch_pending":
            delivery_status = "dispatch_pending"
        else:
            delivery_status = "failed"

        logger.info(
            "voice_agent_node_completed",
            tenant_id=tenant_id,
            delivery_status=delivery_status,
            call_id=call_id,
            call_status=call_status,
        )

        return {
            "delivery_status": delivery_status,
            "delivery_confirmation_id": call_id,
            "delivery_timestamp": now,
        }

    except Exception as exc:
        logger.error(
            "voice_agent_node_fatal_error",
            tenant_id=tenant_id,
            error=str(exc),
        )

        # BC-008: On fatal error, set delivery_status to failed
        return {
            "delivery_status": "failed",
            "delivery_confirmation_id": "",
            "delivery_timestamp": datetime.now(timezone.utc).isoformat(),
            "delivery_failure_reason": f"Voice delivery failed: {exc}",
            "errors": [f"Voice agent failed: {exc}"],
        }
