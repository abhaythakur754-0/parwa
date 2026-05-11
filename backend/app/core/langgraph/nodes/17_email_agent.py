"""
Email Agent Node — Group 10: Email Channel Delivery

Delivers the agent response via the email channel. Applies brand voice
template if configured, renders HTML email, and dispatches via the
channel dispatcher.

Processing Steps:
  1. Apply brand voice template (if brand_voice_profile is configured)
  2. Render email HTML from response text
  3. Dispatch via email channel
  4. Record delivery confirmation

State Contract:
  Reads:  agent_response, delivery_channel, tenant_id, customer_id,
          conversation_id, variant_tier, brand_voice_profile
  Writes: delivery_status, delivery_confirmation_id, delivery_timestamp,
          brand_voice_applied

BC-008: Never crash — if email rendering/dispatch fails, set
        delivery_status to "failed" with error details.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.logger import get_logger

logger = get_logger("node_email_agent")


# ──────────────────────────────────────────────────────────────
# Default fallback values for Email Agent output
# ──────────────────────────────────────────────────────────────

_DEFAULT_EMAIL_STATE: Dict[str, Any] = {
    "delivery_status": "failed",
    "delivery_confirmation_id": "",
    "delivery_timestamp": "",
    "brand_voice_applied": False,
}


# ═══════════════════════════════════════════════════════════════
# Internal: Apply Brand Voice Template
# ═══════════════════════════════════════════════════════════════


def _apply_brand_voice(
    response_text: str,
    brand_voice_profile: Dict[str, Any],
    tenant_id: str,
) -> str:
    """
    Apply brand voice template to the response text.

    Uses the production brand_voice_engine if available,
    otherwise applies basic template transformation.

    Args:
        response_text: The agent response text.
        brand_voice_profile: Brand voice settings dict.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        Response text with brand voice applied.
    """
    if not brand_voice_profile:
        return response_text

    try:
        from app.core.brand_voice_engine import apply_brand_voice  # type: ignore[import-untyped]

        result = apply_brand_voice(
            text=response_text,
            profile=brand_voice_profile,
            tenant_id=tenant_id,
        )
        return result.get("text", response_text)

    except ImportError:
        logger.info(
            "brand_voice_engine_unavailable_email",
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.warning(
            "brand_voice_apply_failed_email",
            tenant_id=tenant_id,
            error=str(exc),
        )

    # Fallback: basic brand voice application
    tone = brand_voice_profile.get("tone", "")
    greeting = brand_voice_profile.get("greeting", "")
    closing = brand_voice_profile.get("closing", "")

    branded_text = response_text
    if greeting:
        branded_text = f"{greeting}\n\n{branded_text}"
    if closing:
        branded_text = f"{branded_text}\n\n{closing}"

    # Replace prohibited terms
    prohibited = brand_voice_profile.get("prohibited_terms", [])
    for term in prohibited:
        if isinstance(term, str):
            branded_text = branded_text.replace(term, "***")

    return branded_text


# ═══════════════════════════════════════════════════════════════
# Internal: Render Email HTML
# ═══════════════════════════════════════════════════════════════


def _render_email_html(
    response_text: str,
    tenant_id: str,
    variant_tier: str,
) -> str:
    """
    Render the response text into an HTML email body.

    Uses the production email_renderer module if available,
    otherwise wraps in a simple HTML template.

    Args:
        response_text: Response text to render.
        tenant_id: Tenant identifier (BC-001).
        variant_tier: Variant tier string.

    Returns:
        HTML string for the email body.
    """
    try:
        from app.core.email_renderer import render_email  # type: ignore[import-untyped]

        result = render_email(
            content=response_text,
            tenant_id=tenant_id,
            variant_tier=variant_tier,
        )
        return result.get("html", response_text)

    except ImportError:
        logger.info(
            "email_renderer_unavailable",
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.warning(
            "email_render_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )

    # Fallback: basic HTML wrapper
    paragraphs = response_text.replace("\n\n", "</p><p>").replace("\n", "<br>")
    return f"""<html><body><div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
<p>{paragraphs}</p>
</div></body></html>"""


# ═══════════════════════════════════════════════════════════════
# Internal: Dispatch Email
# ═══════════════════════════════════════════════════════════════


def _dispatch_email(
    html_body: str,
    state: Dict[str, Any],
    tenant_id: str,
) -> Dict[str, Any]:
    """
    Dispatch the email via the channel dispatcher.

    Uses the production channel_dispatcher module if available.

    Args:
        html_body: Rendered HTML email body.
        state: Current ParwaGraphState dict.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        Dict with confirmation_id and status.
    """
    try:
        from app.core.channel_dispatcher import dispatch  # type: ignore[import-untyped]

        result = dispatch(
            channel="email",
            content=html_body,
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
            "channel_dispatcher_unavailable_email",
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.warning(
            "email_dispatch_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )

    return {
        "confirmation_id": "",
        "status": "dispatch_pending",
    }


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def email_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Email Agent Node — Delivers response via the email channel.

    Applies brand voice template (if configured), renders email HTML,
    dispatches via the email channel, and records delivery confirmation.

    This node is only invoked when delivery_channel is "email".

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with delivery status and confirmation.
    """
    tenant_id = state.get("tenant_id", "unknown")
    variant_tier = state.get("variant_tier", "mini")
    delivery_channel = state.get("delivery_channel", "")
    now = datetime.now(timezone.utc).isoformat()

    logger.info(
        "email_agent_node_start",
        tenant_id=tenant_id,
        variant_tier=variant_tier,
        delivery_channel=delivery_channel,
        conversation_id=state.get("conversation_id", ""),
    )

    try:
        # ── Extract state fields ─────────────────────────────────
        agent_response = state.get("agent_response", "")
        customer_id = state.get("customer_id", "")
        conversation_id = state.get("conversation_id", "")
        brand_voice_profile = state.get("brand_voice_profile", {})

        # ── Validate we have content to deliver ──────────────────
        if not agent_response:
            logger.warning(
                "email_agent_no_response_to_deliver",
                tenant_id=tenant_id,
                conversation_id=conversation_id,
            )
            return {
                "delivery_status": "failed",
                "delivery_confirmation_id": "",
                "delivery_timestamp": now,
                "brand_voice_applied": False,
                "delivery_failure_reason": "No agent response to deliver",
            }

        # ── Step 1: Apply Brand Voice Template ───────────────────
        brand_voice_applied = False
        branded_response = agent_response

        if brand_voice_profile:
            branded_response = _apply_brand_voice(
                response_text=agent_response,
                brand_voice_profile=brand_voice_profile,
                tenant_id=tenant_id,
            )
            brand_voice_applied = True

            logger.info(
                "email_agent_brand_voice_applied",
                tenant_id=tenant_id,
                tone=brand_voice_profile.get("tone", ""),
            )

        # ── Step 2: Render Email HTML ────────────────────────────
        html_body = _render_email_html(
            response_text=branded_response,
            tenant_id=tenant_id,
            variant_tier=variant_tier,
        )

        logger.info(
            "email_agent_html_rendered",
            tenant_id=tenant_id,
            html_length=len(html_body),
        )

        # ── Step 3: Dispatch via Email Channel ───────────────────
        dispatch_result = _dispatch_email(
            html_body=html_body,
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

        # ── Build state update ───────────────────────────────────
        result: Dict[str, Any] = {
            "delivery_status": delivery_status,
            "delivery_confirmation_id": confirmation_id,
            "delivery_timestamp": now,
            "brand_voice_applied": brand_voice_applied,
        }

        logger.info(
            "email_agent_node_completed",
            tenant_id=tenant_id,
            delivery_status=delivery_status,
            confirmation_id=confirmation_id,
            brand_voice_applied=brand_voice_applied,
        )

        return result

    except Exception as exc:
        logger.error(
            "email_agent_node_fatal_error",
            tenant_id=tenant_id,
            error=str(exc),
        )

        # BC-008: On fatal error, set delivery_status to failed
        return {
            **_DEFAULT_EMAIL_STATE,
            "delivery_timestamp": datetime.now(timezone.utc).isoformat(),
            "delivery_failure_reason": f"Email delivery failed: {exc}",
            "errors": [f"Email agent failed: {exc}"],
        }
