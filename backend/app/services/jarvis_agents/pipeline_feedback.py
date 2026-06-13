"""
PARWA Jarvis Pipeline Feedback Handler (Phase 4)

Handles the feedback loop from command execution back to the pipeline.
When the command executor completes, this updates the shared state so
the main pipeline sees it.

This is the CRITICAL FEEDBACK LOOP that makes Jarvis multi-agentic.
After Jarvis takes an action, the main pipeline needs to know:

  - If AI was paused → pipeline routes to human
  - If quality recovery was applied → pipeline adjusts technique
  - If SLA protection was activated → pipeline prioritizes at-risk tickets
  - If escalation was triggered → pipeline knows escalation is in progress

ARCHITECTURE:
  Command Graph (JarvisCommandState) → command_executor
       ↓
  pipeline_feedback.apply_command_feedback()
       ↓
  Redis (real-time) + DB (durable)
       ↓
  Main Pipeline (ParwaGraphState) ← jarvis_awareness_injector_node reads it

This creates a CLOSED LOOP:
  Pipeline produces state → Awareness Engine detects issue →
  Jarvis Command Graph decides action → Command Executor runs it →
  Pipeline Feedback writes it back → Pipeline sees it next tick

The feedback loop is what makes the system MULTI-AGENTIC rather than
just multi-step. Without it, Jarvis is just shouting into the void.

BC-001: company_id first parameter on all public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("jarvis_pipeline_feedback")


# ══════════════════════════════════════════════════════════════════
# FEEDBACK TTL
# ══════════════════════════════════════════════════════════════════

FEEDBACK_TTL_SECONDS = 1800  # 30 minutes


async def apply_command_feedback(
    company_id: str,
    session_id: str,
    command_result: Dict[str, Any],
) -> bool:
    """Apply command execution feedback back to the variant pipeline.

    This is the critical "feedback loop" that makes Jarvis multi-agentic.
    After Jarvis takes an action, the main pipeline needs to know:

    - If AI was paused → pipeline routes to human
    - If quality recovery was applied → pipeline adjusts technique
    - If SLA protection was activated → pipeline prioritizes at-risk tickets
    - If escalation was triggered → pipeline knows escalation is in progress

    This function writes to Redis (fast, real-time) AND to DB (durable).

    The Redis key pattern is:
      parwa:{company_id}:jarvis:feedback:{session_id}

    The main pipeline's jarvis_awareness_injector_node reads this key
    and injects the feedback into ParwaGraphState.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        command_result: The command execution result dict from the
            command graph. Contains agent_type, agent_action,
            agent_decision, execution_status, execution_result, etc.

    Returns:
        True if feedback was applied successfully, False otherwise.
    """
    start_time = time.monotonic()

    try:
        agent_type = command_result.get("agent_type", "")
        agent_action = command_result.get("agent_action", "")
        execution_status = command_result.get("execution_status", "")
        agent_decision = command_result.get("agent_decision", {})
        execution_result = command_result.get("execution_result", {})

        # ── Build feedback payload ──
        feedback: Dict[str, Any] = {
            "feedback_id": _generate_feedback_id(company_id, session_id),
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "source": "jarvis_command_executor",
            "agent_type": agent_type,
            "agent_action": agent_action,
            "execution_status": execution_status,
        }

        # ── Map agent-specific feedback to pipeline fields ──
        pipeline_updates = _map_command_to_pipeline_updates(
            agent_type=agent_type,
            agent_action=agent_action,
            agent_decision=agent_decision,
            execution_result=execution_result,
        )

        feedback["pipeline_updates"] = pipeline_updates

        # ── Write to Redis (real-time) ──
        redis_success = await _write_feedback_to_redis(
            company_id, session_id, feedback,
        )

        # ── Write to DB (durable) ──
        db_success = _write_feedback_to_db(
            company_id, session_id, feedback,
        )

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        logger.info(
            "apply_command_feedback: company=%s, session=%s, "
            "agent=%s, action=%s, redis=%s, db=%s, "
            "pipeline_fields=%d, ms=%.1f",
            company_id, session_id, agent_type, agent_action,
            redis_success, db_success,
            len(pipeline_updates), elapsed_ms,
        )

        return redis_success or db_success  # At least one succeeded

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.warning(
            "apply_command_feedback_failed: company=%s, session=%s, "
            "error=%s, ms=%.1f",
            company_id, session_id, str(e)[:200], elapsed_ms,
        )
        return False


def apply_command_feedback_sync(
    company_id: str,
    session_id: str,
    command_result: Dict[str, Any],
) -> bool:
    """Synchronous wrapper for apply_command_feedback.

    Used by the command graph's _run_manual method which runs
    synchronously.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        command_result: The command execution result dict.

    Returns:
        True if feedback was applied successfully, False otherwise.
    """
    try:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    apply_command_feedback(
                        company_id, session_id, command_result,
                    ),
                )
                return future.result(timeout=10)
        except RuntimeError:
            return asyncio.run(
                apply_command_feedback(
                    company_id, session_id, command_result,
                ),
            )
    except Exception as e:
        logger.warning(
            "apply_command_feedback_sync_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        # Fallback: just write to DB synchronously
        try:
            feedback = {
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "source": "jarvis_command_executor_sync_fallback",
                "agent_type": command_result.get("agent_type", ""),
                "agent_action": command_result.get("agent_action", ""),
                "execution_status": command_result.get("execution_status", ""),
            }
            return _write_feedback_to_db(company_id, session_id, feedback)
        except Exception:
            return False


# ══════════════════════════════════════════════════════════════════
# COMMAND-TO-PIPELINE MAPPING
# ══════════════════════════════════════════════════════════════════


def _map_command_to_pipeline_updates(
    agent_type: str,
    agent_action: str,
    agent_decision: Dict[str, Any],
    execution_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Map a Jarvis command result to ParwaGraphState field updates.

    This is where the "translation" happens between Jarvis's action
    vocabulary and the pipeline's state fields.

    Args:
        agent_type: Which agent executed (escalation, sla_protection, etc.)
        agent_action: The action that was taken.
        agent_decision: Full agent decision dict.
        execution_result: Execution result from command_executor.

    Returns:
        Dict of ParwaGraphState field names → new values.
    """
    updates: Dict[str, Any] = {}

    # ── Escalation feedback ──
    if agent_type == "escalation":
        updates["urgency"] = "critical"
        updates["proposed_action"] = "escalate"
        updates["active_alerts"] = [{
            "alert_id": "jarvis_escalation",
            "severity": "critical",
            "message": (
                f"Jarvis escalated: {agent_decision.get('scope', 'all_urgent')} "
                f"to {agent_decision.get('escalation_tier', 'tier2')}"
            ),
            "channel": "jarvis",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]

    # ── AI Pause/Resume feedback ──
    if agent_action in ("pause_ai", "pause_all_ai"):
        updates["ai_paused"] = True
        updates["system_mode"] = "paused"
        updates["proposed_action"] = "escalate"  # Route to human
        updates["global_pause_reason"] = agent_decision.get(
            "reason", "Jarvis paused AI processing",
        )
        updates["paused_actions"] = ["auto_respond", "auto_refund"]

    if agent_action in ("resume_ai", "resume_all_ai"):
        updates["ai_paused"] = False
        updates["system_mode"] = "auto"
        updates["global_pause_reason"] = ""
        updates["paused_actions"] = []

    # ── Quality Recovery feedback ──
    if agent_type == "quality_recovery":
        strategy = agent_decision.get("strategy", "switch_technique")
        updates["drift_status"] = "recovering"
        updates["quality_alerts"] = [{
            "metric": "quality_score",
            "action": f"recovery_{strategy}",
            "strategy": strategy,
            "current_score": agent_decision.get("current_score"),
            "target_score": agent_decision.get("target_score", 0.85),
            "severity": "warning",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
        if strategy == "switch_technique":
            updates["technique_stack"] = agent_decision.get(
                "new_techniques", ["react"],
            )

    # ── SLA Protection feedback ──
    if agent_type == "sla_protection":
        updates["sla_protection_active"] = True
        updates["sla_protection_strategy"] = agent_decision.get(
            "strategy", "prioritize",
        )
        updates["urgency"] = "high"
        at_risk = agent_decision.get("at_risk_count", 0)
        if at_risk > 0:
            updates["active_alerts"] = [{
                "alert_id": "jarvis_sla_protection",
                "severity": "high",
                "message": (
                    f"SLA protection activated: {agent_decision.get('strategy', 'prioritize')} "
                    f"for {at_risk} at-risk tickets"
                ),
                "channel": "jarvis",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }]

    # ── Reassignment feedback ──
    if agent_type == "reassignment":
        updates["reassignment_in_progress"] = True
        updates["reassignment_from"] = agent_decision.get("from_agent", "")
        updates["reassignment_to"] = agent_decision.get("to_agent", "")
        updates["reassignment_count"] = agent_decision.get("ticket_count", 0)
        if agent_decision.get("upgrade_suggested", False):
            updates["active_alerts"] = [{
                "alert_id": "jarvis_upgrade_suggestion",
                "severity": "warning",
                "message": (
                    "Jarvis suggests upgrading variant tier due to "
                    "agent pool capacity limits"
                ),
                "channel": "jarvis",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }]

    # ── Emergency state feedback ──
    if agent_action in ("full_stop", "emergency_shutdown", "red_alert"):
        updates["emergency_state"] = "red_alert"
        updates["urgency"] = "critical"
        updates["legal_threat_detected"] = True
        updates["system_mode"] = "paused"
        updates["proposed_action"] = "escalate"
        updates["ai_paused"] = True

    # ── Notification feedback ──
    if agent_type == "notification":
        # Notifications don't change pipeline state, but we record
        # that Jarvis sent a notification for the audit trail
        updates["jarvis_feed_entry"] = {
            "type": "notification_sent",
            "channel": agent_decision.get("channel", "chat"),
            "severity": agent_decision.get("severity", "info"),
            "title": agent_decision.get("title", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── Pipeline query feedback (read-only, no state change) ──
    if agent_type == "pipeline_query":
        updates["jarvis_feed_entry"] = {
            "type": "pipeline_query_result",
            "query_type": agent_decision.get("query_type", "general"),
            "answer": agent_decision.get("answer", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return updates


# ══════════════════════════════════════════════════════════════════
# REDIS WRITE
# ══════════════════════════════════════════════════════════════════


async def _write_feedback_to_redis(
    company_id: str,
    session_id: str,
    feedback: Dict[str, Any],
) -> bool:
    """Write feedback to Redis for real-time pipeline consumption.

    The jarvis_awareness_injector_node in the main pipeline reads
    this key and injects the updates into ParwaGraphState.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        feedback: Feedback dict to write.

    Returns:
        True if write succeeded, False otherwise.
    """
    try:
        from app.services.jarvis_agents.variant_bridge import (
            _make_feedback_key,
        )

        from app.core.redis import get_redis
        redis = await get_redis()

        key = _make_feedback_key(company_id, session_id)
        await redis.set(
            key,
            json.dumps(feedback, default=str),
            ex=FEEDBACK_TTL_SECONDS,
        )

        # Also update the bridge state (merge feedback into it)
        from app.services.jarvis_agents.variant_bridge import (
            _make_bridge_key,
        )

        bridge_key = _make_bridge_key(company_id, session_id)
        existing_raw = await redis.get(bridge_key)
        existing = {}
        if existing_raw:
            try:
                existing = json.loads(existing_raw)
            except (json.JSONDecodeError, TypeError):
                pass

        # Merge pipeline updates into bridge state
        pipeline_updates = feedback.get("pipeline_updates", {})
        existing.update(pipeline_updates)
        existing["last_feedback_at"] = feedback.get("applied_at", "")

        await redis.set(
            bridge_key,
            json.dumps(existing, default=str),
            ex=3600,  # 1 hour TTL
        )

        logger.debug(
            "feedback_redis_write: company=%s, session=%s, "
            "feedback_id=%s, pipeline_fields=%d",
            company_id, session_id,
            feedback.get("feedback_id", ""),
            len(pipeline_updates),
        )

        return True

    except Exception as e:
        logger.debug(
            "feedback_redis_write_failed: company=%s, session=%s, error=%s",
            company_id, session_id, str(e)[:200],
        )
        return False


# ══════════════════════════════════════════════════════════════════
# DB WRITE
# ══════════════════════════════════════════════════════════════════


def _write_feedback_to_db(
    company_id: str,
    session_id: str,
    feedback: Dict[str, Any],
) -> bool:
    """Write feedback to DB for durable record and DB-only reads.

    This is the fallback for when Redis is unavailable, and also
    the durable record that persists beyond Redis TTL.

    Writes to the JarvisSession's context_json under the
    "jarvis_command_feedback" key.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        feedback: Feedback dict to write.

    Returns:
        True if DB write succeeded, False otherwise.
    """
    try:
        from database.base import SessionLocal
        from database.models.jarvis import JarvisSession

        db = SessionLocal()
        try:
            session = db.query(JarvisSession).filter(
                JarvisSession.id == session_id,
                JarvisSession.company_id == company_id,
            ).first()

            if session:
                ctx = {}
                if session.context_json:
                    try:
                        ctx = json.loads(session.context_json)
                    except (json.JSONDecodeError, TypeError):
                        ctx = {}

                # Add feedback entry
                ctx.setdefault("jarvis_command_feedback", [])
                ctx["jarvis_command_feedback"].append({
                    "feedback_id": feedback.get("feedback_id", ""),
                    "agent_type": feedback.get("agent_type", ""),
                    "agent_action": feedback.get("agent_action", ""),
                    "execution_status": feedback.get("execution_status", ""),
                    "pipeline_updates": feedback.get("pipeline_updates", {}),
                    "applied_at": feedback.get("applied_at", ""),
                    "source": feedback.get("source", ""),
                })

                # Keep last 20 feedback entries
                ctx["jarvis_command_feedback"] = (
                    ctx["jarvis_command_feedback"][-20:]
                )

                # Also store the latest pipeline updates at top level
                # for easy DB-only reads
                pipeline_updates = feedback.get("pipeline_updates", {})
                if pipeline_updates:
                    ctx["latest_jarvis_pipeline_updates"] = pipeline_updates
                    ctx["latest_jarvis_update_at"] = feedback.get(
                        "applied_at", "",
                    )

                session.context_json = json.dumps(ctx)
                session.updated_at = datetime.now(timezone.utc)
                db.commit()

                logger.debug(
                    "feedback_db_write: company=%s, session=%s, "
                    "feedback_id=%s",
                    company_id, session_id,
                    feedback.get("feedback_id", ""),
                )
                return True
            else:
                logger.debug(
                    "feedback_db_no_session: company=%s, session=%s",
                    company_id, session_id,
                )
                return False

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    except Exception as e:
        logger.debug(
            "feedback_db_write_failed: company=%s, session=%s, error=%s",
            company_id, session_id, str(e)[:200],
        )
        return False


# ══════════════════════════════════════════════════════════════════
# FEEDBACK HISTORY
# ══════════════════════════════════════════════════════════════════


def get_feedback_history(
    company_id: str,
    session_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Get the feedback history for a session from DB.

    This is useful for debugging and for the UI to show
    Jarvis's action history.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        limit: Max feedback entries to return.

    Returns:
        List of feedback entry dicts, newest first.
    """
    try:
        from database.base import SessionLocal
        from database.models.jarvis import JarvisSession

        db = SessionLocal()
        try:
            session = db.query(JarvisSession).filter(
                JarvisSession.id == session_id,
                JarvisSession.company_id == company_id,
            ).first()

            if session and session.context_json:
                ctx = json.loads(session.context_json)
                history = ctx.get("jarvis_command_feedback", [])
                # Return newest first
                return list(reversed(history[-limit:]))

            return []
        finally:
            db.close()

    except Exception as e:
        logger.debug(
            "feedback_history_failed: company=%s, session=%s, error=%s",
            company_id, session_id, str(e)[:200],
        )
        return []


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════


def _generate_feedback_id(company_id: str, session_id: str) -> str:
    """Generate a unique feedback ID.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.

    Returns:
        Unique feedback ID string.
    """
    import uuid
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    unique = uuid.uuid4().hex[:8]
    return f"fb_{timestamp}_{unique}"


__all__ = [
    "apply_command_feedback",
    "apply_command_feedback_sync",
    "get_feedback_history",
]
