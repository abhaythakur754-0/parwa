"""
PARWA Jarvis↔Variant LangGraph Integration Bridge (Phase 4)

This is the BIDIRECTIONAL bridge that makes Jarvis TRULY multi-agentic.
It connects two previously separate LangGraph systems:

  1. Main CC Pipeline (core/langgraph/) — 19+ nodes processing customer
     messages via ParwaGraphState (24 groups, ~150 fields)

  2. Jarvis Command Graph (services/jarvis_agents/) — 7+ nodes for
     Jarvis's operational decisions via JarvisCommandState (6 groups)

Before Phase 4, these systems were DISCONNECTED:
  - Jarvis could SEE the pipeline state (via awareness engine) but
    couldn't INFLUENCE it mid-execution
  - The pipeline didn't know about Jarvis commands until the next tick
  - No feedback loop: command execution didn't propagate back to pipeline

Phase 4 bridges this gap with 5 key functions:

  inject_jarvis_state_into_pipeline()
    → Writes JarvisCommandState fields into ParwaGraphState via Redis
    → Pipeline nodes check these fields mid-execution

  read_pipeline_state_for_jarvis()
    → Reads ParwaGraphState GROUP 14/15/20 fields FROM Redis
    → Jarvis awareness engine uses this to see pipeline state

  sync_awareness_to_pipeline()
    → Pushes awareness snapshot (7 domains) into Redis
    → Main pipeline nodes can check Jarvis awareness mid-execution

  get_variant_aware_command_config()
    → Returns tier-appropriate command config
    → mini_parwa: notify-only, parwa: standard, parwa_high: full_autonomy

  check_jarvis_approval_needed()
    → Whether a Jarvis action needs human approval
    → Based on variant_tier + agent_type + agent_action

  apply_command_to_pipeline_state()
    → After command execution, writes result back to ParwaGraphState
    → The critical feedback loop

Redis Key Design:
  jarvis:bridge:{company_id}:{session_id}           — Shared bridge state
  jarvis:awareness:{company_id}:{session_id}         — Awareness snapshot
  jarvis:command_feedback:{company_id}:{session_id}  — Command feedback

All keys follow BC-001 (company_id first) and are tenant-isolated.

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

logger = get_logger("jarvis_variant_bridge")

# ══════════════════════════════════════════════════════════════════
# REDIS ACCESS PATTERN
# ══════════════════════════════════════════════════════════════════

# Bridge state TTL: 1 hour (pipeline reads are frequent)
BRIDGE_STATE_TTL_SECONDS = 3600
# Awareness snapshot TTL: 5 minutes (updated on every tick)
AWARENESS_TTL_SECONDS = 300
# Command feedback TTL: 30 minutes (read once, then expires)
COMMAND_FEEDBACK_TTL_SECONDS = 1800


def _get_redis_sync():
    """Get Redis client for synchronous contexts.

    Returns None if Redis is unavailable (BC-008).
    """
    try:
        from app.core.redis import get_redis
        # Note: get_redis() is async, but we use it in sync contexts
        # by running it in an event loop. For sync bridge functions,
        # we store/read from a simple cache or use the DB fallback.
        return None  # Sync Redis not available; use async or DB fallback
    except Exception:
        return None


async def _get_redis_async():
    """Get async Redis client.

    Returns None if Redis is unavailable (BC-008).
    """
    try:
        from app.core.redis import get_redis
        return await get_redis()
    except Exception:
        return None


def _make_bridge_key(company_id: str, session_id: str) -> str:
    """Build the Redis key for the bridge state.

    Pattern: parwa:{company_id}:jarvis:bridge:{session_id}

    BC-001: company_id is always first.
    """
    return f"parwa:{company_id}:jarvis:bridge:{session_id}"


def _make_awareness_key(company_id: str, session_id: str) -> str:
    """Build the Redis key for the awareness snapshot.

    Pattern: parwa:{company_id}:jarvis:awareness:{session_id}
    """
    return f"parwa:{company_id}:jarvis:awareness:{session_id}"


def _make_feedback_key(company_id: str, session_id: str) -> str:
    """Build the Redis key for command feedback.

    Pattern: parwa:{company_id}:jarvis:feedback:{session_id}
    """
    return f"parwa:{company_id}:jarvis:feedback:{session_id}"


# ══════════════════════════════════════════════════════════════════
# VARIANT TIER COMMAND CONFIGURATION
# ══════════════════════════════════════════════════════════════════

# Actions that are considered "monetary" (involve money/credits)
MONETARY_ACTIONS = {
    "refund", "issue_credit", "apply_discount", "reverse_charge",
    "waive_fee", "apply_coupon", "cancel_subscription",
}

# Actions that are considered "escalation" (involve human handoff)
ESCALATION_ACTIONS = {
    "escalate", "escalate_to_tier2", "escalate_to_manager",
    "human_handoff", "emergency_escalation",
}

# Actions that are considered "emergency" (system-level critical)
EMERGENCY_ACTIONS = {
    "full_stop", "red_alert", "emergency_shutdown",
    "pause_all_ai", "emergency_escalation", "circuit_breaker_trigger",
}

# Tier-specific command configurations
VARIANT_COMMAND_CONFIGS: Dict[str, Dict[str, Any]] = {
    "mini_parwa": {
        "mode": "notify_only",
        "description": (
            "Jarvis is in observe/notify mode. It can detect issues and "
            "notify humans, but CANNOT auto-execute actions like escalation, "
            "reassignment, or quality recovery. All actions require approval."
        ),
        "auto_execute_allowed": False,
        "approval_required_for": "all",
        "max_urgency_auto": "info",
        "can_pause_ai": False,
        "can_escalate": False,
        "can_reassign": False,
        "can_modify_technique": False,
        "can_activate_sla_protection": False,
    },
    "parwa": {
        "mode": "standard",
        "description": (
            "Jarvis can auto-execute with ZAI reasoning, but critical "
            "actions (monetary + escalation) need human approval. "
            "Standard operational decisions are auto-approved."
        ),
        "auto_execute_allowed": True,
        "approval_required_for": "monetary_escalation",
        "max_urgency_auto": "high",
        "can_pause_ai": True,
        "can_escalate": True,
        "can_reassign": True,
        "can_modify_technique": True,
        "can_activate_sla_protection": True,
    },
    "parwa_high": {
        "mode": "full_autonomy",
        "description": (
            "Jarvis has full autonomy. It can auto-execute everything "
            "including escalation and monetary actions. Only emergency "
            "actions need human approval (as a safety check)."
        ),
        "auto_execute_allowed": True,
        "approval_required_for": "emergency_only",
        "max_urgency_auto": "critical",
        "can_pause_ai": True,
        "can_escalate": True,
        "can_reassign": True,
        "can_modify_technique": True,
        "can_activate_sla_protection": True,
    },
}


# ══════════════════════════════════════════════════════════════════
# PUBLIC API: BIDIRECTIONAL BRIDGE FUNCTIONS
# ══════════════════════════════════════════════════════════════════


async def inject_jarvis_state_into_pipeline(
    company_id: str,
    session_id: str,
    command_state: Dict[str, Any],
) -> bool:
    """Inject JarvisCommandState fields into ParwaGraphState via Redis.

    This is the PRIMARY bridge function. After Jarvis makes a command
    decision (e.g., "pause AI"), this function writes the relevant
    fields into the shared Redis state so the main pipeline can see
    them mid-execution.

    Fields mapped from JarvisCommandState → ParwaGraphState:
      - ai_paused (from agent_action containing "pause")
      - emergency_state (from agent_decision.emergency_level)
      - co_pilot_suggestion (from agent_decision.co_pilot_text)
      - jarvis_feed_entry (from execution_result)
      - paused_channels (from agent_decision.paused_channels)
      - paused_actions (from agent_decision.paused_actions)

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        command_state: Current JarvisCommandState dict.

    Returns:
        True if injection succeeded, False otherwise.
    """
    try:
        redis = await _get_redis_async()
        if redis is None:
            logger.warning(
                "inject_jarvis_state: redis_unavailable, company=%s, session=%s",
                company_id, session_id,
            )
            return False

        # Extract relevant fields from JarvisCommandState
        agent_type = command_state.get("agent_type", "")
        agent_action = command_state.get("agent_action", "")
        agent_decision = command_state.get("agent_decision", {})
        execution_status = command_state.get("execution_status", "")
        execution_result = command_state.get("execution_result", {})

        # Build the bridge state that the pipeline will read
        bridge_state: Dict[str, Any] = {
            "injected_at": datetime.now(timezone.utc).isoformat(),
            "source": "jarvis_command_graph",
            "command_state_summary": {
                "agent_type": agent_type,
                "agent_action": agent_action,
                "execution_status": execution_status,
            },
        }

        # ── Map ai_paused ──
        # Jarvis paused AI → pipeline should route to human
        if agent_action in ("pause_ai", "pause_all_ai"):
            bridge_state["ai_paused"] = True
            bridge_state["global_pause_reason"] = agent_decision.get(
                "reason", "Jarvis commanded AI pause",
            )
        elif agent_action in ("resume_ai", "resume_all_ai"):
            bridge_state["ai_paused"] = False
            bridge_state["global_pause_reason"] = ""

        # ── Map emergency_state ──
        emergency_level = agent_decision.get("emergency_level", "")
        if emergency_level in ("red_alert", "full_stop", "yellow_alert"):
            bridge_state["emergency_state"] = emergency_level
        elif agent_action in ("full_stop", "emergency_shutdown"):
            bridge_state["emergency_state"] = "full_stop"

        # ── Map co_pilot_suggestion ──
        co_pilot_text = agent_decision.get("co_pilot_text", "")
        if co_pilot_text:
            bridge_state["co_pilot_suggestion"] = co_pilot_text
            bridge_state["co_pilot_suggestion_type"] = (
                agent_decision.get("co_pilot_type", "action_suggestion")
            )

        # ── Map jarvis_feed_entry ──
        if execution_result:
            bridge_state["jarvis_feed_entry"] = {
                "type": "command_execution",
                "agent_type": agent_type,
                "agent_action": agent_action,
                "status": execution_status,
                "result": execution_result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # ── Map paused_channels ──
        paused_channels = agent_decision.get("paused_channels", [])
        if paused_channels:
            bridge_state["paused_channels"] = paused_channels

        # ── Map paused_actions ──
        paused_actions = agent_decision.get("paused_actions", [])
        if paused_actions:
            bridge_state["paused_actions"] = paused_actions

        # Write to Redis
        key = _make_bridge_key(company_id, session_id)
        await redis.set(
            key,
            json.dumps(bridge_state, default=str),
            ex=BRIDGE_STATE_TTL_SECONDS,
        )

        logger.info(
            "inject_jarvis_state: company=%s, session=%s, "
            "agent=%s, action=%s, fields=%d",
            company_id, session_id, agent_type, agent_action,
            len(bridge_state),
        )
        return True

    except Exception as e:
        logger.warning(
            "inject_jarvis_state_failed: company=%s, session=%s, error=%s",
            company_id, session_id, str(e)[:200],
        )
        return False


async def read_pipeline_state_for_jarvis(
    company_id: str,
    session_id: str,
) -> Dict[str, Any]:
    """Read ParwaGraphState GROUP 14/15/20 fields from Redis.

    This is how Jarvis ASKS the pipeline "what are you doing right now?"
    The awareness engine uses this to provide Jarvis with real-time
    pipeline state.

    Falls back to DB read if Redis is unavailable.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.

    Returns:
        Dict with GROUP 14 (awareness), GROUP 15 (emergency controls),
        and GROUP 20 (jarvis command) fields. Empty dict on failure.
    """
    try:
        # ── Try Redis first (fast path) ──
        redis = await _get_redis_async()
        if redis is not None:
            awareness_key = _make_awareness_key(company_id, session_id)
            raw = await redis.get(awareness_key)
            if raw:
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    pass

        # ── Fallback: DB read ──
        return await _read_pipeline_state_from_db(company_id, session_id)

    except Exception as e:
        logger.warning(
            "read_pipeline_state_failed: company=%s, session=%s, error=%s",
            company_id, session_id, str(e)[:200],
        )
        return {}


async def _read_pipeline_state_from_db(
    company_id: str,
    session_id: str,
) -> Dict[str, Any]:
    """Fallback: Read pipeline state from the awareness snapshot DB.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.

    Returns:
        Dict with awareness fields from latest snapshot. Empty dict on failure.
    """
    try:
        from database.base import SessionLocal
        from database.models.jarvis_cc import JarvisAwarenessSnapshot

        db = SessionLocal()
        try:
            snapshot = (
                db.query(JarvisAwarenessSnapshot)
                .filter(
                    JarvisAwarenessSnapshot.session_id == session_id,
                    JarvisAwarenessSnapshot.company_id == company_id,
                )
                .order_by(JarvisAwarenessSnapshot.created_at.desc())
                .first()
            )

            if snapshot and snapshot.raw_state_json:
                return json.loads(snapshot.raw_state_json)

            return {}
        finally:
            db.close()

    except Exception as e:
        logger.debug(
            "db_fallback_read_failed: company=%s, session=%s, error=%s",
            company_id, session_id, str(e)[:200],
        )
        return {}


async def sync_awareness_to_pipeline(
    company_id: str,
    session_id: str,
    awareness_snapshot: Dict[str, Any],
) -> bool:
    """Push the awareness snapshot (7 domains) into Redis.

    This makes the awareness data available to the main pipeline nodes
    mid-execution. When the jarvis_awareness_injector_node runs in the
    main pipeline, it reads this data and injects it into
    ParwaGraphState GROUP 14/15 fields.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        awareness_snapshot: Current awareness state dict (7 domains).

    Returns:
        True if sync succeeded, False otherwise.
    """
    try:
        redis = await _get_redis_async()
        if redis is None:
            logger.warning(
                "sync_awareness: redis_unavailable, company=%s, session=%s",
                company_id, session_id,
            )
            return False

        key = _make_awareness_key(company_id, session_id)

        # Enrich with sync timestamp
        enriched = {
            **awareness_snapshot,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "source": "jarvis_awareness_engine",
        }

        await redis.set(
            key,
            json.dumps(enriched, default=str),
            ex=AWARENESS_TTL_SECONDS,
        )

        logger.debug(
            "sync_awareness: company=%s, session=%s, health=%s",
            company_id, session_id,
            awareness_snapshot.get("system_health", "unknown"),
        )
        return True

    except Exception as e:
        logger.warning(
            "sync_awareness_failed: company=%s, session=%s, error=%s",
            company_id, session_id, str(e)[:200],
        )
        return False


def get_variant_aware_command_config(
    company_id: str,
    variant_tier: str,
) -> Dict[str, Any]:
    """Return tier-appropriate command config for Jarvis.

    This function determines what Jarvis is ALLOWED to do based on
    the variant tier. This is a SYNCHRONOUS function (no Redis needed)
    because the config is deterministic based on tier.

    Tier Modes:
      - mini_parwa: notify_only — Jarvis can only notify, not auto-execute
        actions like escalation/reassignment. All actions need approval.
      - parwa: standard — Jarvis can auto-execute with ZAI reasoning,
        but critical actions (monetary/escalation) need approval.
      - parwa_high: full_autonomy — Jarvis can auto-execute everything
        including escalation. Only emergency needs approval.

    Args:
        company_id: Company ID for BC-001.
        variant_tier: Current variant tier (mini_parwa, parwa, parwa_high).

    Returns:
        Dict with command config for this tier.
    """
    try:
        config = VARIANT_COMMAND_CONFIGS.get(
            variant_tier,
            VARIANT_COMMAND_CONFIGS["mini_parwa"],
        )

        # Add runtime context
        config = {
            **config,
            "company_id": company_id,
            "variant_tier": variant_tier,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.debug(
            "variant_command_config: company=%s, tier=%s, mode=%s",
            company_id, variant_tier, config.get("mode", "unknown"),
        )
        return config

    except Exception as e:
        logger.warning(
            "variant_command_config_failed: company=%s, tier=%s, error=%s",
            company_id, variant_tier, str(e)[:200],
        )
        # BC-008: Return safest config
        return {
            **VARIANT_COMMAND_CONFIGS["mini_parwa"],
            "company_id": company_id,
            "variant_tier": variant_tier,
            "error": str(e)[:200],
        }


def check_jarvis_approval_needed(
    company_id: str,
    variant_tier: str,
    agent_type: str,
    agent_action: str,
) -> Dict[str, Any]:
    """Check whether a Jarvis action needs human approval before execution.

    Approval rules by variant_tier:
      - mini_parwa: ALL actions need approval (Jarvis is in observe mode)
      - parwa: Only escalation + monetary actions need approval
      - parwa_high: Only emergency actions need approval

    This is a SYNCHRONOUS function because approval rules are deterministic.

    Args:
        company_id: Company ID for BC-001.
        variant_tier: Current variant tier.
        agent_type: Which agent is executing (escalation, sla_protection, etc.)
        agent_action: The specific action being taken.

    Returns:
        Dict with:
          - approval_needed: bool
          - reason: str explaining why approval is/isn't needed
          - approval_type: "human" | "auto" | "notify"
          - variant_tier: the tier used for this decision
    """
    try:
        config = get_variant_aware_command_config(company_id, variant_tier)
        mode = config.get("mode", "notify_only")

        # ── mini_parwa: ALL actions need approval ──
        if mode == "notify_only":
            return {
                "approval_needed": True,
                "reason": (
                    f"Variant tier '{variant_tier}' is in notify-only mode. "
                    f"All Jarvis actions require human approval."
                ),
                "approval_type": "human",
                "variant_tier": variant_tier,
                "agent_type": agent_type,
                "agent_action": agent_action,
            }

        # ── parwa: Monetary + Escalation need approval ──
        if mode == "standard":
            is_monetary = agent_action in MONETARY_ACTIONS
            is_escalation = (
                agent_action in ESCALATION_ACTIONS
                or agent_type == "escalation"
            )

            if is_monetary or is_escalation:
                action_kind = "monetary" if is_monetary else "escalation"
                return {
                    "approval_needed": True,
                    "reason": (
                        f"Action '{agent_action}' is {action_kind}. "
                        f"Variant tier '{variant_tier}' requires human approval "
                        f"for {action_kind} actions."
                    ),
                    "approval_type": "human",
                    "variant_tier": variant_tier,
                    "agent_type": agent_type,
                    "agent_action": agent_action,
                }

            return {
                "approval_needed": False,
                "reason": (
                    f"Action '{agent_action}' is a standard operation. "
                    f"Variant tier '{variant_tier}' allows auto-execution "
                    f"for non-monetary, non-escalation actions."
                ),
                "approval_type": "auto",
                "variant_tier": variant_tier,
                "agent_type": agent_type,
                "agent_action": agent_action,
            }

        # ── parwa_high: Only emergency needs approval ──
        if mode == "full_autonomy":
            is_emergency = (
                agent_action in EMERGENCY_ACTIONS
                or agent_action == "full_stop"
            )

            if is_emergency:
                return {
                    "approval_needed": True,
                    "reason": (
                        f"Action '{agent_action}' is an emergency action. "
                        f"Even with full autonomy (tier '{variant_tier}'), "
                        f"emergency actions require human approval."
                    ),
                    "approval_type": "human",
                    "variant_tier": variant_tier,
                    "agent_type": agent_type,
                    "agent_action": agent_action,
                }

            return {
                "approval_needed": False,
                "reason": (
                    f"Variant tier '{variant_tier}' has full autonomy. "
                    f"Action '{agent_action}' is auto-approved."
                ),
                "approval_type": "auto",
                "variant_tier": variant_tier,
                "agent_type": agent_type,
                "agent_action": agent_action,
            }

        # Fallback: require approval (safest default)
        return {
            "approval_needed": True,
            "reason": f"Unknown mode '{mode}', requiring approval for safety.",
            "approval_type": "human",
            "variant_tier": variant_tier,
            "agent_type": agent_type,
            "agent_action": agent_action,
        }

    except Exception as e:
        logger.warning(
            "check_approval_failed: company=%s, tier=%s, error=%s",
            company_id, variant_tier, str(e)[:200],
        )
        # BC-008: Always require approval on error (safest)
        return {
            "approval_needed": True,
            "reason": f"Error checking approval: {str(e)[:200]}. Requiring approval for safety.",
            "approval_type": "human",
            "variant_tier": variant_tier,
            "agent_type": agent_type,
            "agent_action": agent_action,
            "error": str(e)[:200],
        }


async def apply_command_to_pipeline_state(
    company_id: str,
    session_id: str,
    command_result: Dict[str, Any],
) -> bool:
    """After a Jarvis command completes, write the result back to ParwaGraphState.

    This is the critical FEEDBACK LOOP that makes Jarvis multi-agentic.
    After Jarvis takes an action, the main pipeline needs to know:

      - If AI was paused → pipeline routes to human
      - If quality recovery was applied → pipeline adjusts technique
      - If SLA protection was activated → pipeline prioritizes at-risk tickets
      - If escalation was triggered → pipeline knows escalation is in progress

    Writes to Redis (fast, real-time) AND to DB (durable).

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        command_result: The command execution result dict from the command graph.

    Returns:
        True if application succeeded, False otherwise.
    """
    try:
        redis = await _get_redis_async()
        if redis is None:
            logger.warning(
                "apply_command_to_pipeline: redis_unavailable, "
                "company=%s, session=%s",
                company_id, session_id,
            )
            # Still try DB write
            return _apply_command_to_db(company_id, session_id, command_result)

        # Build the feedback state
        feedback: Dict[str, Any] = {
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "source": "jarvis_command_executor",
            "command_result_summary": {
                "agent_type": command_result.get("agent_type", ""),
                "agent_action": command_result.get("agent_action", ""),
                "execution_status": command_result.get("execution_status", ""),
            },
        }

        agent_type = command_result.get("agent_type", "")
        agent_action = command_result.get("agent_action", "")
        agent_decision = command_result.get("agent_decision", {})
        execution_result = command_result.get("execution_result", {})

        # ── Map specific command results to pipeline fields ──

        # Escalation → pipeline knows escalation is in progress
        if agent_type == "escalation":
            feedback["escalation_in_progress"] = True
            feedback["escalation_tier"] = agent_decision.get(
                "escalation_tier", "tier2",
            )
            feedback["escalation_scope"] = agent_decision.get("scope", "all_urgent")
            feedback["urgency"] = "critical"

        # AI Paused → pipeline routes to human
        if agent_action in ("pause_ai", "pause_all_ai"):
            feedback["ai_paused"] = True
            feedback["system_mode"] = "paused"
            feedback["proposed_action"] = "escalate"
            feedback["global_pause_reason"] = agent_decision.get(
                "reason", "Jarvis paused AI",
            )

        # AI Resumed → pipeline can resume auto processing
        if agent_action in ("resume_ai", "resume_all_ai"):
            feedback["ai_paused"] = False
            feedback["system_mode"] = "auto"
            feedback["global_pause_reason"] = ""

        # Quality Recovery → pipeline adjusts technique
        if agent_type == "quality_recovery":
            feedback["quality_alerts"] = [{
                "metric": "quality_score",
                "action": "recovery_applied",
                "strategy": agent_decision.get("strategy", "switch_technique"),
                "target_score": agent_decision.get("target_score", 0.85),
                "severity": "warning",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }]
            feedback["drift_status"] = "recovering"
            # If technique was switched, update
            if agent_decision.get("strategy") == "switch_technique":
                feedback["technique_stack"] = agent_decision.get(
                    "new_techniques", ["react"],
                )

        # SLA Protection → pipeline prioritizes at-risk tickets
        if agent_type == "sla_protection":
            feedback["sla_protection_active"] = True
            feedback["sla_protection_strategy"] = agent_decision.get(
                "strategy", "prioritize",
            )
            feedback["urgency"] = "high"

        # Reassignment → pipeline knows tickets are being moved
        if agent_type == "reassignment":
            feedback["reassignment_in_progress"] = True
            feedback["reassignment_from"] = agent_decision.get("from_agent", "")
            feedback["reassignment_to"] = agent_decision.get("to_agent", "")
            feedback["reassignment_count"] = agent_decision.get("ticket_count", 0)

        # Emergency state changes
        if agent_action in EMERGENCY_ACTIONS:
            feedback["emergency_state"] = "red_alert"
            feedback["urgency"] = "critical"
            feedback["legal_threat_detected"] = True  # Force human review

        # Write to Redis (fast, real-time)
        feedback_key = _make_feedback_key(company_id, session_id)
        await redis.set(
            feedback_key,
            json.dumps(feedback, default=str),
            ex=COMMAND_FEEDBACK_TTL_SECONDS,
        )

        # Also update the bridge state
        bridge_key = _make_bridge_key(company_id, session_id)
        existing_raw = await redis.get(bridge_key)
        existing = {}
        if existing_raw:
            try:
                existing = json.loads(existing_raw)
            except (json.JSONDecodeError, TypeError):
                pass

        # Merge feedback into bridge state
        existing.update(feedback)
        await redis.set(
            bridge_key,
            json.dumps(existing, default=str),
            ex=BRIDGE_STATE_TTL_SECONDS,
        )

        logger.info(
            "apply_command_to_pipeline: company=%s, session=%s, "
            "agent=%s, action=%s, fields=%d",
            company_id, session_id, agent_type, agent_action,
            len(feedback),
        )

        # Also write to DB for durability
        _apply_command_to_db(company_id, session_id, command_result)

        return True

    except Exception as e:
        logger.warning(
            "apply_command_to_pipeline_failed: company=%s, session=%s, error=%s",
            company_id, session_id, str(e)[:200],
        )
        return False


def _apply_command_to_db(
    company_id: str,
    session_id: str,
    command_result: Dict[str, Any],
) -> bool:
    """Write command result to DB for durable record.

    This is a fallback/complement to Redis. If Redis is down,
    the pipeline can still read command feedback from DB.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        command_result: The command execution result dict.

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

            if session and session.context_json:
                ctx = json.loads(session.context_json)
            else:
                ctx = {}

            # Add command feedback to context
            ctx.setdefault("jarvis_command_feedback", [])
            ctx["jarvis_command_feedback"].append({
                "agent_type": command_result.get("agent_type", ""),
                "agent_action": command_result.get("agent_action", ""),
                "execution_status": command_result.get("execution_status", ""),
                "applied_at": datetime.now(timezone.utc).isoformat(),
            })
            # Keep last 20 entries
            ctx["jarvis_command_feedback"] = ctx["jarvis_command_feedback"][-20:]

            session.context_json = json.dumps(ctx)
            session.updated_at = datetime.now(timezone.utc)
            db.commit()

            return True

        except Exception:
            db.rollback()
            return False
        finally:
            db.close()

    except Exception as e:
        logger.debug(
            "db_command_write_failed: company=%s, session=%s, error=%s",
            company_id, session_id, str(e)[:200],
        )
        return False


# ══════════════════════════════════════════════════════════════════
# CONVENIENCE: SYNC WRAPPERS
# ══════════════════════════════════════════════════════════════════


def inject_jarvis_state_sync(
    company_id: str,
    session_id: str,
    command_state: Dict[str, Any],
) -> bool:
    """Synchronous wrapper for inject_jarvis_state_into_pipeline."""
    try:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    inject_jarvis_state_into_pipeline(
                        company_id, session_id, command_state,
                    ),
                )
                return future.result(timeout=10)
        except RuntimeError:
            return asyncio.run(
                inject_jarvis_state_into_pipeline(
                    company_id, session_id, command_state,
                ),
            )
    except Exception as e:
        logger.warning(
            "inject_jarvis_state_sync_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return False


def read_pipeline_state_sync(
    company_id: str,
    session_id: str,
) -> Dict[str, Any]:
    """Synchronous wrapper for read_pipeline_state_for_jarvis."""
    try:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    read_pipeline_state_for_jarvis(company_id, session_id),
                )
                return future.result(timeout=10)
        except RuntimeError:
            return asyncio.run(
                read_pipeline_state_for_jarvis(company_id, session_id),
            )
    except Exception as e:
        logger.warning(
            "read_pipeline_state_sync_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return {}


def sync_awareness_sync(
    company_id: str,
    session_id: str,
    awareness_snapshot: Dict[str, Any],
) -> bool:
    """Synchronous wrapper for sync_awareness_to_pipeline."""
    try:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    sync_awareness_to_pipeline(
                        company_id, session_id, awareness_snapshot,
                    ),
                )
                return future.result(timeout=10)
        except RuntimeError:
            return asyncio.run(
                sync_awareness_to_pipeline(
                    company_id, session_id, awareness_snapshot,
                ),
            )
    except Exception as e:
        logger.warning(
            "sync_awareness_sync_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return False


def apply_command_sync(
    company_id: str,
    session_id: str,
    command_result: Dict[str, Any],
) -> bool:
    """Synchronous wrapper for apply_command_to_pipeline_state."""
    try:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    apply_command_to_pipeline_state(
                        company_id, session_id, command_result,
                    ),
                )
                return future.result(timeout=10)
        except RuntimeError:
            return asyncio.run(
                apply_command_to_pipeline_state(
                    company_id, session_id, command_result,
                ),
            )
    except Exception as e:
        logger.warning(
            "apply_command_sync_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        return False


__all__ = [
    # Core bridge functions (async)
    "inject_jarvis_state_into_pipeline",
    "read_pipeline_state_for_jarvis",
    "sync_awareness_to_pipeline",
    "apply_command_to_pipeline_state",
    # Variant tier config (sync)
    "get_variant_aware_command_config",
    "check_jarvis_approval_needed",
    # Sync wrappers
    "inject_jarvis_state_sync",
    "read_pipeline_state_sync",
    "sync_awareness_sync",
    "apply_command_sync",
]
