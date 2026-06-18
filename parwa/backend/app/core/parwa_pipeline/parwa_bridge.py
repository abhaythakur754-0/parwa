"""
PARWA-Jarvis Bridge — Wave 4 + Wave 5

Provides:
  - load_system_flags(tenant_id) — called by PARWA nodes to get active Jarvis flags
  - write_quality_score_to_jarvis(state) — called by Node 6 after scoring
  - write_to_jarvis_inbox(state, stuck_reason, what_was_tried) — called by Node 8 when stuck
  - record_training_signal(...) — called when human approves/rejects/edit
  - score_confidence(...) — Wave 5A: compute confidence and routing
  - route_by_sentiment(...) — Wave 5C: sentiment-based routing
  - check_approval_gate(...) — Wave 5D: approval gate checking
  - recommend_variant(...) — Wave 5E: variant recommendation

All methods are async and use the Jarvis DB backend.
The bridge is the SINGLE point of contact — PARWA nodes never import jarvis_db directly.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("parwa.jarvis_bridge")

# Cache TTL: flags are cached for 5 seconds to avoid DB hits on every node
_FLAG_CACHE: Dict[str, Dict[str, Any]] = {}  # tenant_id -> {flags, loaded_at}
_FLAG_CACHE_TTL = 5.0


async def load_system_flags(tenant_id: str) -> Dict[str, Any]:
    """Load all active Jarvis system flags for a tenant.

    Returns a dict organized by flag_type for O(1) lookups:
    {
        "global_shutdown": True/False,
        "paused_actions": ["refund", "account_change"],
        "redirected_channels": {"instagram": "ai", "calls": "human"},
        "force_mode": "supervised",
        "approval_overrides": ["address_change", "plan_change"],
        "guidance": {"TKT-123": "Check Shopify order..."},
        "all_flags": [...],  # raw flags for debugging
    }

    Cached for 5 seconds per tenant.
    """
    now = time.time()
    cached = _FLAG_CACHE.get(tenant_id)

    # Return cached if fresh
    if cached and (now - cached["loaded_at"]) < _FLAG_CACHE_TTL:
        return cached["result"]

    # Load from DB
    from app.core.jarvis_pipeline.jarvis_db import get_db
    db = get_db()
    flags = await db.get_active_flags(tenant_id)

    result = {
        "global_shutdown": False,
        "paused_actions": [],
        "redirected_channels": {},
        "force_mode": None,
        "approval_overrides": [],
        "guidance": {},
        "all_flags": flags,
    }

    for flag in flags:
        ftype = flag.get("flag_type", "")
        fval = flag.get("flag_value", "")
        target_id = flag.get("target_id")

        if ftype == "global_shutdown":
            result["global_shutdown"] = True

        elif ftype == "pause_action":
            if fval not in result["paused_actions"]:
                result["paused_actions"].append(fval)

        elif ftype == "redirect_channel":
            # flag_value format: "channel:route_to" e.g. "instagram:ai"
            parts = fval.split(":", 1)
            if len(parts) == 2:
                result["redirected_channels"][parts[0]] = parts[1]

        elif ftype == "force_mode":
            result["force_mode"] = fval

        elif ftype == "approval_override":
            if fval not in result["approval_overrides"]:
                result["approval_overrides"].append(fval)

        elif ftype == "guidance":
            # target_id is the ticket_id for guidance flags
            if target_id:
                result["guidance"][target_id] = fval

    _FLAG_CACHE[tenant_id] = {"result": result, "loaded_at": now}
    return result


def invalidate_flag_cache(tenant_id: Optional[str] = None):
    """Invalidate flag cache (called after flag changes)."""
    if tenant_id:
        _FLAG_CACHE.pop(tenant_id, None)
    else:
        _FLAG_CACHE.clear()


async def write_quality_score_to_jarvis(
    tenant_id: str,
    ticket_id: str,
    quality_score: float,
    resolution_path: str = "",
    nodes_reached: Optional[List[str]] = None,
    llm_calls: int = 0,
    tokens_used: int = 0,
) -> Optional[Dict[str, Any]]:
    """Write quality score from PARWA Node 6 to Jarvis DB.

    Non-blocking. Failures are logged but don't affect pipeline flow.
    Returns the score record or None on failure.
    """
    try:
        from app.core.jarvis_pipeline.jarvis_db import get_db
        db = get_db()
        record = await db.write_quality_score(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            overall_score=quality_score,
            resolution_path=resolution_path,
            nodes_reached=nodes_reached or [],
            llm_calls=llm_calls,
            tokens_used=tokens_used,
        )
        logger.info(
            "Quality score written: tenant=%s ticket=%s score=%.4f path=%s",
            tenant_id, ticket_id, quality_score, resolution_path,
        )
        return record
    except Exception as e:
        logger.warning("Failed to write quality score to Jarvis: %s", e)
        return None


async def write_to_jarvis_inbox(
    tenant_id: str,
    ticket_id: str,
    stuck_reason: str,
    quality_score: float,
    what_was_tried: str,
) -> Optional[Dict[str, Any]]:
    """PARWA writes to Jarvis inbox when stuck (Node 8 escalation).

    Non-blocking. Failures logged but don't affect pipeline.
    """
    try:
        from app.core.jarvis_pipeline.jarvis_db import get_db
        db = get_db()
        msg = await db.write_to_inbox(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            stuck_reason=stuck_reason,
            quality_score=quality_score,
            what_was_tried=what_was_tried,
            inbox_type="parwa_stuck",
        )
        logger.info(
            "Inbox message written: tenant=%s ticket=%s reason=%s",
            tenant_id, ticket_id, stuck_reason,
        )
        return msg
    except Exception as e:
        logger.warning("Failed to write to Jarvis inbox: %s", e)
        return None


async def record_training_signal(
    tenant_id: str,
    ticket_id: str,
    signal_type: str,
    original_response: str = "",
    corrected_response: str = "",
    quality_score: float = 0.0,
    ticket_type: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Record training data from human approval/rejection/edit.

    signal_type: "approved", "rejected", "edited"
    """
    try:
        from app.core.jarvis_pipeline.jarvis_db import get_db
        db = get_db()
        record = await db.record_training_data(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            signal_type=signal_type,
            original_response=original_response,
            corrected_response=corrected_response,
            quality_score=quality_score,
            ticket_type=ticket_type,
            metadata=metadata,
        )
        logger.info(
            "Training data recorded: tenant=%s ticket=%s signal=%s",
            tenant_id, ticket_id, signal_type,
        )
        return record
    except Exception as e:
        logger.warning("Failed to record training data: %s", e)
        return None


# ═══════════════════════════════════════════════════════════════
# Wave 5: Intelligence Layer Bridge Functions
# ═══════════════════════════════════════════════════════════════


async def score_confidence(
    tenant_id: str,
    ticket_id: str,
    ticket_type: str = "",
    query: str = "",
    required_action: str = "",
    is_vip: bool = False,
    value_usd: float = 0.0,
    policy_count: int = 0,
) -> Optional[Dict[str, Any]]:
    """Wave 5A: Compute confidence score and routing for a ticket.

    Delegates to confidence_engine. Logs result to DB.
    Non-blocking: returns None on failure (doesn't break pipeline).
    """
    try:
        from app.core.jarvis_pipeline.confidence_engine import score_ticket_confidence
        from app.core.jarvis_pipeline.jarvis_db import get_db

        result = await score_ticket_confidence(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            ticket_type=ticket_type,
            query=query,
            required_action=required_action,
            is_vip=is_vip,
            value_usd=value_usd,
            policy_count=policy_count,
        )

        # Persist to DB
        db = get_db()
        await db.record_confidence(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            confidence=result["confidence"],
            routing=result["routing"],
            factors=result["factors"],
        )

        logger.info("Confidence scored: ticket=%s score=%.4f route=%s",
                    ticket_id, result["confidence"], result["routing"])
        return result

    except Exception as e:
        logger.warning("Failed to score confidence: %s", e)
        return None


async def route_by_sentiment(
    tenant_id: str,
    ticket_id: str,
    query: str,
    customer_context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Wave 5C: Route a ticket based on sentiment analysis.

    Delegates to sentiment_router. Logs result to DB.
    Non-blocking.
    """
    try:
        from app.core.jarvis_pipeline.sentiment_router import route_by_sentiment as _route
        from app.core.jarvis_pipeline.jarvis_db import get_db

        result = await _route(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            query=query,
            customer_context=customer_context,
        )

        # Persist sentiment to DB
        db = get_db()
        await db.record_sentiment(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            sentiment=result["sentiment"],
        )

        logger.info("Sentiment routed: ticket=%s score=%.2f route=%s",
                    ticket_id, result["sentiment"]["score"], result["route"])
        return result

    except Exception as e:
        logger.warning("Failed to route by sentiment: %s", e)
        return None


async def check_approval_gate(
    tenant_id: str,
    action: str,
    confidence: float = 1.0,
    is_vip: bool = False,
    value_usd: float = 0.0,
) -> Optional[Dict[str, Any]]:
    """Wave 5D: Check if an action requires human approval.

    Delegates to approval_gates module.
    Non-blocking: returns None on failure (defaults to requiring approval).
    """
    try:
        from app.core.jarvis_pipeline.approval_gates import check_approval_required

        result = await check_approval_required(
            tenant_id=tenant_id,
            action=action,
            confidence=confidence,
            is_vip=is_vip,
            value_usd=value_usd,
        )

        logger.info("Approval gate: action=%s required=%s gate=%s",
                    action, result["required"], result["gate_type"])
        return result

    except Exception as e:
        logger.warning("Failed to check approval gate: %s", e)
        # Fail-safe: require approval when gate check fails
        return {
            "required": True,
            "reason": f"Approval gate check failed ({e}), defaulting to require approval",
            "gate_type": "error_failsafe",
            "action": action,
            "confidence": confidence,
        }


async def recommend_variant(
    tenant_id: str,
    ticket_id: str,
    query: str,
    current_variant: str = "mini",
    required_action: str = "",
) -> Optional[Dict[str, Any]]:
    """Wave 5E: Recommend whether a variant upgrade is needed.

    Delegates to variant_recommender.
    Non-blocking.
    """
    try:
        from app.core.jarvis_pipeline.variant_recommender import recommend_variant as _recommend

        result = await _recommend(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            query=query,
            current_variant=current_variant,
            required_action=required_action,
        )

        if result["upgrade_needed"]:
            logger.info("Variant upgrade recommended: ticket=%s %s → %s",
                        ticket_id, current_variant, result["recommended_variant"])

        return result

    except Exception as e:
        logger.warning("Failed to recommend variant: %s", e)
        return None
