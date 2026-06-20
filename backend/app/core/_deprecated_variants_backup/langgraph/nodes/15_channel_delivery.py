"""
Channel Delivery Node — Group 10: Channel Dispatch Routing

Routes the agent response to the appropriate delivery channel based on
variant tier and channel availability. This node does NOT actually deliver
the response — it determines which channel will be used and whether a
fallback is needed.

Routing Logic:
  1. Check if the requested channel is available for this tier
  2. If not available, fall back to email (always available)
  3. Set delivery_channel to the actual channel that will be used
  4. Mark fallback_attempted if channel was changed

Channel Availability per Tier:
  Mini:  email, sms, chat, api (no voice, no video)
  Pro:   email, sms, chat, api, voice
  High:  email, sms, chat, api, voice, video

State Contract:
  Reads:  variant_tier, channel, agent_response, tenant_id,
          customer_id, conversation_id
  Writes: delivery_channel, delivery_status, fallback_attempted

BC-008: Never crash — defaults to email fallback on any error.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

from typing import Any, Dict

from app.logger import get_logger

logger = get_logger("node_channel_delivery")


# ──────────────────────────────────────────────────────────────
# Default fallback values for Channel Delivery output
# ──────────────────────────────────────────────────────────────

_DEFAULT_CHANNEL_STATE: Dict[str, Any] = {
    "delivery_channel": "email",
    "delivery_status": "pending",
    "fallback_attempted": False,
}


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def channel_delivery_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Channel Delivery Node — Routes response to the appropriate delivery channel.

    Determines which channel will actually be used to deliver the response
    based on tier availability. If the requested channel is unavailable for
    the tenant's tier, falls back to email (always available).

    This node does NOT perform actual delivery — channel agents (email, sms,
    voice) handle the actual dispatch downstream.

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with delivery_channel, delivery_status,
        and fallback_attempted.
    """
    tenant_id = state.get("tenant_id", "unknown")
    variant_tier = state.get("variant_tier", "mini")
    requested_channel = state.get("channel", "email")

    logger.info(
        "channel_delivery_node_start",
        tenant_id=tenant_id,
        variant_tier=variant_tier,
        requested_channel=requested_channel,
    )

    try:
        # ── Lazy import config helpers ───────────────────────────
        from app.core.langgraph.config import (  # type: ignore[import-untyped]
            get_available_channels,
            is_voice_enabled,
            is_video_enabled,
        )

        # ── Extract state fields ─────────────────────────────────
        agent_response = state.get("agent_response", "")
        customer_id = state.get("customer_id", "")
        conversation_id = state.get("conversation_id", "")

        # ── Get available channels for this tier ─────────────────
        available_channels = get_available_channels(variant_tier)

        logger.info(
            "channel_delivery_available_channels",
            tenant_id=tenant_id,
            variant_tier=variant_tier,
            available_channels=available_channels,
            requested_channel=requested_channel,
        )

        # ── Determine actual delivery channel ────────────────────
        delivery_channel = requested_channel
        fallback_attempted = False

        if requested_channel in available_channels:
            # Requested channel is available — use it
            delivery_channel = requested_channel

            # Additional tier-specific checks for voice/video
            if requested_channel == "voice" and not is_voice_enabled(variant_tier):
                logger.warning(
                    "channel_delivery_voice_not_enabled_fallback",
                    tenant_id=tenant_id,
                    variant_tier=variant_tier,
                )
                delivery_channel = "email"
                fallback_attempted = True

            elif requested_channel == "video" and not is_video_enabled(variant_tier):
                logger.warning(
                    "channel_delivery_video_not_enabled_fallback",
                    tenant_id=tenant_id,
                    variant_tier=variant_tier,
                )
                delivery_channel = "email"
                fallback_attempted = True

        else:
            # Requested channel NOT available for this tier — fall back to email
            logger.warning(
                "channel_delivery_channel_unavailable_fallback_to_email",
                tenant_id=tenant_id,
                variant_tier=variant_tier,
                requested_channel=requested_channel,
                available_channels=available_channels,
            )
            delivery_channel = "email"
            fallback_attempted = True

        # ── Validate we have content to deliver ──────────────────
        if not agent_response:
            logger.warning(
                "channel_delivery_no_agent_response",
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                customer_id=customer_id,
            )

        # ── Build state update ───────────────────────────────────
        result = {
            "delivery_channel": delivery_channel,
            "delivery_status": "routed",
            "fallback_attempted": fallback_attempted,
        }

        if fallback_attempted:
            logger.info(
                "channel_delivery_fallback_applied",
                tenant_id=tenant_id,
                variant_tier=variant_tier,
                original_channel=requested_channel,
                fallback_channel=delivery_channel,
            )
        else:
            logger.info(
                "channel_delivery_channel_confirmed",
                tenant_id=tenant_id,
                variant_tier=variant_tier,
                delivery_channel=delivery_channel,
            )

        return result

    except Exception as exc:
        logger.error(
            "channel_delivery_node_fatal_error",
            tenant_id=tenant_id,
            error=str(exc),
        )

        # BC-008: On fatal error, default to email (always available)
        return {
            **_DEFAULT_CHANNEL_STATE,
            "delivery_channel": "email",
            "delivery_status": "routed_fallback",
            "fallback_attempted": True,
            "errors": [f"Channel delivery routing failed: {exc}"],
        }
