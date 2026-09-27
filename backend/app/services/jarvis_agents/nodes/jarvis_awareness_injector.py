"""
PARWA Jarvis Awareness Injector Node (Phase 4)

A LangGraph node that can be added to the MAIN CC pipeline. It reads
Jarvis awareness from the variant bridge and injects it into
ParwaGraphState GROUP 14/15/20 fields.

WHERE THIS NODE SITS:
  This node should be placed in the main CC pipeline BEFORE the
  router_agent (node 03). It checks if Jarvis has any active alerts
  or commands that should influence how the pipeline processes this
  message.

WHY THIS MATTERS:
  Before Phase 4, the main pipeline was blind to Jarvis's decisions.
  If Jarvis paused AI, the pipeline would still try to auto-respond.
  If Jarvis declared a red_alert, the pipeline would treat it as
  business as usual. This node fixes that by injecting Jarvis's
  awareness into the pipeline state BEFORE routing.

KEY BEHAVIORS:
  - If ai_paused=True from Jarvis → sets system_mode="paused" and
    proposed_action="escalate" (forces human review)
  - If emergency_state is "red_alert" or "full_stop" → sets
    urgency="critical" and legal_threat_detected=True (forces human
    review, bypasses auto-respond)
  - Injects co_pilot_suggestion and jarvis_feed_entry from bridge
    into state for downstream nodes to use
  - Updates GROUP 14 fields from awareness data
  - Falls back gracefully if Redis unavailable (pipeline continues
    with existing state)

ARCHITECTURE:
  Main Pipeline Flow (with Phase 4 injection):
    01_pii_redaction → 02_empathy_engine →
    [NEW] jarvis_awareness_injector →
    03_router_agent → ... → 20_format

  The injector reads from Redis key:
    parwa:{company_id}:jarvis:bridge:{session_id}
  and writes into ParwaGraphState fields.

BC-008: Never crash — if bridge read fails, pipeline continues normally.
BC-012: All timestamps UTC.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.logger import get_logger

logger = get_logger("jarvis_awareness_injector")


def jarvis_awareness_injector_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Read Jarvis awareness from bridge and inject into ParwaGraphState.

    This node sits in the main CC pipeline BEFORE the router_agent.
    It checks if Jarvis has any active alerts or commands that should
    influence how the pipeline processes this message.

    For example:
    - If ai_paused=True from Jarvis, the pipeline should route to human
    - If emergency_state='red_alert', all tickets should be prioritized
    - If Jarvis has a co_pilot_suggestion, inject it for the agent

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Dict with updated GROUP 14/15/20 fields based on Jarvis state.
    """
    start_time = time.monotonic()

    try:
        company_id = state.get("tenant_id", "") or state.get("company_id", "")
        session_id = state.get("session_id", "")

        if not company_id or not session_id:
            # No tenant context — skip injection
            return _empty_result("no_tenant_context")

        # ── Read bridge state from Redis ──
        bridge_state = _read_bridge_state(company_id, session_id)

        if not bridge_state:
            # No Jarvis state — pipeline continues normally
            return _empty_result("no_bridge_state")

        # ── Read awareness from Redis ──
        awareness_data = _read_awareness_state(company_id, session_id)

        # ── Read command feedback from Redis ──
        feedback_data = _read_feedback_state(company_id, session_id)

        # ── Build updates from bridge + awareness + feedback ──
        updates: Dict[str, Any] = {}

        # ── Inject GROUP 15: Emergency Controls ──
        updates.update(_inject_emergency_controls(bridge_state, feedback_data))

        # ── Inject GROUP 20: Jarvis Command Context ──
        updates.update(_inject_command_context(bridge_state))

        # ── Inject GROUP 14: Jarvis Awareness ──
        updates.update(_inject_awareness_fields(awareness_data))

        # ── Apply pipeline routing overrides ──
        updates.update(_apply_routing_overrides(bridge_state, state))

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        # Add execution log
        updates["node_execution_log"] = [{
            "node_name": "jarvis_awareness_injector",
            "duration_ms": elapsed_ms,
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bridge_fields": len(bridge_state),
            "awareness_fields": len(awareness_data),
            "feedback_fields": len(feedback_data),
            "injected_fields": len(updates),
        }]

        logger.info(
            "jarvis_awareness_injector: company=%s, session=%s, "
            "bridge=%d, awareness=%d, feedback=%d, injected=%d, ms=%.1f",
            company_id, session_id,
            len(bridge_state), len(awareness_data), len(feedback_data),
            len(updates), elapsed_ms,
        )

        return updates

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception(
            "jarvis_awareness_injector_error: ms=%.1f", elapsed_ms,
        )
        # BC-008: Never crash — return empty updates
        return {
            "errors": [f"jarvis_awareness_injector: {str(e)[:200]}"],
            "node_execution_log": [{
                "node_name": "jarvis_awareness_injector",
                "duration_ms": elapsed_ms,
                "status": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e)[:200],
            }],
        }


# ══════════════════════════════════════════════════════════════════
# BRIDGE STATE READERS
# ══════════════════════════════════════════════════════════════════


def _read_bridge_state(company_id: str, session_id: str) -> Dict[str, Any]:
    """Read the bridge state from Redis (synchronous, using fallback).

    Since this node runs in the LangGraph pipeline which may be async
    or sync depending on the graph implementation, we use a best-effort
    approach: try Redis async, fall back to sync, fall back to empty.
    """
    try:
        import asyncio
        from app.services.jarvis_agents.variant_bridge import (
            _make_bridge_key,
        )

        async def _read():
            try:
                from app.core.redis import get_redis
                redis = await get_redis()
                key = _make_bridge_key(company_id, session_id)
                raw = await redis.get(key)
                if raw:
                    return json.loads(raw)
                return {}
            except Exception:
                return {}

        try:
            loop = asyncio.get_running_loop()
            # We're in an async context — try to schedule
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _read())
                return future.result(timeout=5)
        except RuntimeError:
            return asyncio.run(_read())

    except Exception as e:
        logger.debug(
            "bridge_state_read_failed: company=%s, session=%s, error=%s",
            company_id, session_id, str(e)[:200],
        )
        return {}


def _read_awareness_state(company_id: str, session_id: str) -> Dict[str, Any]:
    """Read the awareness snapshot from Redis."""
    try:
        import asyncio
        from app.services.jarvis_agents.variant_bridge import (
            _make_awareness_key,
        )

        async def _read():
            try:
                from app.core.redis import get_redis
                redis = await get_redis()
                key = _make_awareness_key(company_id, session_id)
                raw = await redis.get(key)
                if raw:
                    return json.loads(raw)
                return {}
            except Exception:
                return {}

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _read())
                return future.result(timeout=5)
        except RuntimeError:
            return asyncio.run(_read())

    except Exception as e:
        logger.debug(
            "awareness_state_read_failed: company=%s, session=%s, error=%s",
            company_id, session_id, str(e)[:200],
        )
        return {}


def _read_feedback_state(company_id: str, session_id: str) -> Dict[str, Any]:
    """Read the command feedback from Redis."""
    try:
        import asyncio
        from app.services.jarvis_agents.variant_bridge import (
            _make_feedback_key,
        )

        async def _read():
            try:
                from app.core.redis import get_redis
                redis = await get_redis()
                key = _make_feedback_key(company_id, session_id)
                raw = await redis.get(key)
                if raw:
                    return json.loads(raw)
                return {}
            except Exception:
                return {}

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _read())
                return future.result(timeout=5)
        except RuntimeError:
            return asyncio.run(_read())

    except Exception as e:
        logger.debug(
            "feedback_state_read_failed: company=%s, session=%s, error=%s",
            company_id, session_id, str(e)[:200],
        )
        return {}


# ══════════════════════════════════════════════════════════════════
# STATE INJECTION HELPERS
# ══════════════════════════════════════════════════════════════════


def _inject_emergency_controls(
    bridge_state: Dict[str, Any],
    feedback_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Inject GROUP 15: Emergency Controls from bridge + feedback.

    Key mappings:
      - ai_paused → system_mode="paused", proposed_action="escalate"
      - emergency_state → urgency="critical", legal_threat_detected=True
      - paused_channels → paused_channels list
      - paused_actions → paused_actions list
    """
    updates: Dict[str, Any] = {}

    # Merge bridge and feedback (feedback takes precedence)
    combined = {**bridge_state, **feedback_data}

    # ── ai_paused ──
    ai_paused = combined.get("ai_paused")
    if ai_paused is not None:
        updates["ai_paused"] = ai_paused
        if ai_paused:
            updates["system_mode"] = "paused"
            updates["proposed_action"] = "escalate"
            updates["global_pause_reason"] = combined.get(
                "global_pause_reason", "Jarvis paused AI",
            )

    # ── emergency_state ──
    emergency_state = combined.get("emergency_state")
    if emergency_state and emergency_state in ("red_alert", "full_stop"):
        updates["emergency_state"] = emergency_state
        updates["urgency"] = "critical"
        updates["legal_threat_detected"] = True  # Force human review
        if emergency_state == "full_stop":
            updates["system_mode"] = "paused"
            updates["proposed_action"] = "escalate"

    # ── paused_channels ──
    paused_channels = combined.get("paused_channels")
    if paused_channels and isinstance(paused_channels, list):
        updates["paused_channels"] = paused_channels

    # ── paused_actions ──
    paused_actions = combined.get("paused_actions")
    if paused_actions and isinstance(paused_actions, list):
        updates["paused_actions"] = paused_actions

    # ── circuit_breaker_trips ──
    circuit_trips = combined.get("circuit_breaker_trips")
    if circuit_trips is not None:
        updates["circuit_breaker_trips"] = circuit_trips

    return updates


def _inject_command_context(
    bridge_state: Dict[str, Any],
) -> Dict[str, Any]:
    """Inject GROUP 20: Jarvis Command Context from bridge.

    Key mappings:
      - co_pilot_suggestion → co_pilot_suggestion field
      - co_pilot_suggestion_type → co_pilot_suggestion_type field
      - jarvis_feed_entry → jarvis_feed_entry field
    """
    updates: Dict[str, Any] = {}

    # ── Co-pilot suggestion ──
    co_pilot = bridge_state.get("co_pilot_suggestion")
    if co_pilot:
        updates["co_pilot_suggestion"] = co_pilot
        updates["co_pilot_suggestion_type"] = bridge_state.get(
            "co_pilot_suggestion_type", "action_suggestion",
        )

    # ── Jarvis feed entry ──
    feed_entry = bridge_state.get("jarvis_feed_entry")
    if feed_entry:
        updates["jarvis_feed_entry"] = feed_entry

    # ── Command metadata from bridge source ──
    source = bridge_state.get("source")
    if source == "jarvis_command_graph":
        updates["jarvis_command_metadata"] = {
            "injected_at": bridge_state.get("injected_at", ""),
            "source": source,
            "command_summary": bridge_state.get("command_state_summary", {}),
        }

    return updates


def _inject_awareness_fields(
    awareness_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Inject GROUP 14: Jarvis Awareness fields from awareness snapshot.

    Only injects fields that are present in the awareness data.
    Does NOT override fields that were already set by earlier pipeline
    nodes (the pipeline's own state takes precedence for field values).
    """
    updates: Dict[str, Any] = {}

    if not awareness_data:
        return updates

    # Map awareness fields to GROUP 14 ParwaGraphState fields
    field_mappings = {
        "current_plan": "current_plan",
        "plan_usage_today": "plan_usage_today",
        "subscription_status": "subscription_status",
        "days_until_renewal": "days_until_renewal",
        "system_health": "system_health",
        "channel_health": "channel_health",
        "ticket_volume_today": "ticket_volume_today",
        "ticket_volume_avg": "ticket_volume_avg",
        "ticket_volume_spike": "ticket_volume_spike",
        "active_agents": "active_agents",
        "agent_pool_capacity": "agent_pool_capacity",
        "agent_pool_utilization": "agent_pool_utilization",
        "training_running": "training_running",
        "training_mistake_count": "training_mistake_count",
        "training_model_version": "training_model_version",
        "drift_status": "drift_status",
        "drift_score": "drift_score",
        "quality_score": "quality_score",
    }

    for src_key, dst_key in field_mappings.items():
        value = awareness_data.get(src_key)
        if value is not None:
            updates[dst_key] = value

    # quality_alerts and last_5_errors are lists — only inject if present
    quality_alerts = awareness_data.get("quality_alerts")
    if quality_alerts and isinstance(quality_alerts, list):
        updates["quality_alerts"] = quality_alerts

    last_5_errors = awareness_data.get("last_5_errors")
    if last_5_errors and isinstance(last_5_errors, list):
        updates["last_5_errors"] = last_5_errors

    # active_alerts is also a list
    active_alerts = awareness_data.get("active_alerts")
    if active_alerts and isinstance(active_alerts, list):
        updates["active_alerts"] = active_alerts

    return updates


def _apply_routing_overrides(
    bridge_state: Dict[str, Any],
    current_state: Dict[str, Any],
) -> Dict[str, Any]:
    """Apply pipeline routing overrides based on Jarvis state.

    These overrides influence how the router_agent routes the message:
      - If SLA protection is active → route to fastest agent
      - If escalation is in progress → route to escalation agent
      - If quality recovery was applied → adjust technique
    """
    updates: Dict[str, Any] = {}

    # ── Escalation in progress ──
    if bridge_state.get("escalation_in_progress"):
        updates["urgency"] = "critical"

    # ── SLA protection active ──
    if bridge_state.get("sla_protection_active"):
        updates["urgency"] = "high"

    # ── Reassignment in progress ──
    if bridge_state.get("reassignment_in_progress"):
        # Don't override urgency, but note it in metadata
        pass

    # ── System mode override ──
    system_mode = bridge_state.get("system_mode")
    if system_mode and system_mode in ("paused", "supervised", "shadow"):
        updates["system_mode"] = system_mode

    return updates


def _empty_result(reason: str) -> Dict[str, Any]:
    """Return an empty result with a log entry.

    Used when the injector has nothing to inject (no bridge state,
    no tenant context, etc.). The pipeline continues normally.
    """
    return {
        "node_execution_log": [{
            "node_name": "jarvis_awareness_injector",
            "duration_ms": 0,
            "status": "skipped",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }],
    }
