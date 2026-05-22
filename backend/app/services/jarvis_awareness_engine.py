"""
PARWA Jarvis Awareness Engine

The brain that makes Jarvis PROACTIVE. Like a human employee who notices
things ("hey, ticket volume just spiked 3x"), the Awareness Engine monitors
the system state and generates alerts when something needs attention.

Architecture:
  8 Monitoring Domains (7 from GROUP 14 + Domain 8 Activity Store):
    1. PLAN & SUBSCRIPTION  — plan usage, renewal, subscription status
    2. SYSTEM HEALTH        — overall health, per-channel health
    3. TICKET VOLUME        — today vs avg, spike detection
    4. AGENT POOL           — utilization, capacity warnings
    5. TRAINING             — Agent Lightning training state, mistake count
    6. DRIFT & QUALITY      — model drift, quality score, quality alerts
    7. ERRORS               — last 5 errors, error rate tracking
    8. ACTIVITY STORE       — non-agentic awareness: user actions, billing,
                              system events, config changes, channel events

  Domain 8 (Activity Store) is the KEY differentiator for Jarvis awareness.
  For AGENTIC parts, Jarvis asks variant agents directly via variant_bridge.
  For NON-AGENTIC parts, Jarvis reads the Activity Store to know what happened.
  This avoids hardcoding 500+ awareness functions — instead, every action is
  logged and Jarvis reads it for contextual awareness.

  Tick Types:
    - periodic:  Automatic tick (every 30 seconds via Celery/Redis beat)
    - on_change: Written when a monitored field changes significantly
    - manual:    Triggered by user/admin from dashboard
    - emergency: Written when emergency_state changes

  Data Flow:
    ParwaGraphState GROUP 14 fields
        → collect_awareness_state() reads real-time data
        → run_awareness_tick() runs rule checks
        → writes JarvisAwarenessSnapshot (always)
        → writes JarvisProactiveAlert (when threshold breached)
        → updates CC session context

  Fallback Strategy:
    The engine NEVER crashes. If a domain collector fails, that domain's
    data is marked as "unknown" and the engine continues with the other
    domains. Partial awareness is better than no awareness.

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, ValidationError
from app.logger import get_logger
from database.models.jarvis import JarvisSession, JarvisMessage
from database.models.jarvis_cc import (
    JarvisAwarenessSnapshot,
    JarvisCommand,
    JarvisProactiveAlert,
)

logger = get_logger("jarvis_awareness_engine")


# ── Constants ──────────────────────────────────────────────────────

DEFAULT_TICK_INTERVAL_SECONDS = 30
MAX_SNAPSHOTS_PER_SESSION = 2880  # 24h at 30s intervals
SNAPSHOT_PRUNE_BATCH = 100
MAX_ALERTS_PER_SESSION = 50
ALERT_PRUNE_BATCH = 20

# Spike detection: volume > SPIKE_MULTIPLIER * avg = spike
SPIKE_MULTIPLIER = 2.0
# Utilization warning: > UTILIZATION_WARN_THRESHOLD = warning alert
UTILIZATION_WARN_THRESHOLD = 80.0
# Utilization critical: > UTILIZATION_CRITICAL_THRESHOLD = critical alert
UTILIZATION_CRITICAL_THRESHOLD = 95.0
# Quality score below this = warning
QUALITY_WARN_THRESHOLD = 0.70
# Quality score below this = critical
QUALITY_CRITICAL_THRESHOLD = 0.50
# Drift score above this = warning
DRIFT_WARN_THRESHOLD = 0.30
# Drift score above this = critical
DRIFT_CRITICAL_THRESHOLD = 0.60
# Plan usage above this = warning
PLAN_USAGE_WARN_THRESHOLD = 80.0
# Plan usage above this = critical
PLAN_USAGE_CRITICAL_THRESHOLD = 95.0
# Days until renewal below this = info
RENEWAL_INFO_THRESHOLD = 7
# Days until renewal below this = warning
RENEWAL_WARN_THRESHOLD = 3

# Alert TTL defaults (seconds)
ALERT_TTL_INFO = 3600       # 1 hour
ALERT_TTL_WARNING = 14400   # 4 hours
ALERT_TTL_CRITICAL = 86400  # 24 hours
ALERT_TTL_EMERGENCY = 0     # No expiry

# Cooldown: prevent alert spam during sustained issues (5 minutes)
RULE_COOLDOWN_SECONDS = 300
# Error rate thresholds (percentage of errors vs ticket volume)
ERROR_RATE_WARN_THRESHOLD = 0.10    # 10% error rate = warning
ERROR_RATE_CRITICAL_THRESHOLD = 0.25  # 25% error rate = critical
# Training mistake count threshold
TRAINING_MISTAKE_WARN_THRESHOLD = 10

__all__ = [
    # Main tick
    "run_awareness_tick",
    # State collection
    "collect_awareness_state",
    # Live LangGraph state
    "get_live_graph_state",
    # Snapshots
    "get_latest_snapshot",
    "get_snapshot_history",
    "create_snapshot",
    # Alerts
    "get_active_alerts",
    "acknowledge_alert",
    "dismiss_alert",
    "resolve_alert",
    "create_alert",
    # Pruning
    "prune_old_snapshots",
    "prune_expired_alerts",
    # Delta detection
    "compute_awareness_delta",
    # Threshold configuration
    "get_effective_thresholds",
]


# ══════════════════════════════════════════════════════════════════
# MAIN TICK: The Heart of the Awareness Engine
# ══════════════════════════════════════════════════════════════════


def run_awareness_tick(
    db: Session,
    company_id: str,
    session_id: str,
    user_id: str,
    tick_type: str = "periodic",
    override_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run a single awareness tick for a customer care session.

    This is the main entry point for the Awareness Engine.
    It collects current state, compares with previous snapshot,
    generates a new snapshot, and creates alerts if needed.

    Flow:
      1. Validate session (must be customer_care type)
      2. Collect current awareness state from 7 domains
      3. Get previous snapshot for delta detection
      4. Create new JarvisAwarenessSnapshot
      5. Run rule checks on each domain
      6. Create JarvisProactiveAlert for any threshold breaches
      7. Update CC session context
      8. Prune old snapshots if needed
      9. Return tick result with snapshot + alerts

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        user_id: User ID for security scoping.
        tick_type: One of periodic, on_change, manual, emergency.
        override_state: Optional pre-collected state (for testing/internal use).

    Returns:
        Dict with snapshot, alerts_created, tick_metadata.
    """
    start_time = time.monotonic()

    # ── Step 1: Validate session ──
    from app.services.jarvis_cc_service import get_cc_session

    session = get_cc_session(db, session_id, user_id, company_id)
    ctx = _safe_parse_json(session.context_json)

    # ── Step 2: Collect current awareness state ──
    if override_state:
        current_state = override_state
    else:
        # JV-02 FIX: Try to read live LangGraph state first, then merge
        # with DB-collected data. Live state takes precedence.
        live_state = get_live_graph_state(company_id, session_id)
        current_state = collect_awareness_state(
            db, company_id, session_id,
            live_graph_state=live_state,
        )

    # ── Step 3: Get previous snapshot for delta ──
    previous_snapshot = get_latest_snapshot(db, session_id, company_id)
    previous_state = None
    if previous_snapshot:
        try:
            previous_state = _safe_parse_json(previous_snapshot.raw_state_json)
        except Exception:
            pass  # BC-008

    # ── Step 4: Compute tick number ──
    tick_number = 1
    if previous_snapshot and previous_snapshot.tick_number:
        tick_number = previous_snapshot.tick_number + 1

    # ── Step 5: Compute delta ──
    delta = compute_awareness_delta(current_state, previous_state)

    # ── Step 6: Create snapshot ──
    snapshot = create_snapshot(
        db=db,
        session_id=session_id,
        company_id=company_id,
        state=current_state,
        tick_type=tick_type,
        tick_number=tick_number,
    )

    # ── Step 7: Run rule checks → generate alerts ──
    alerts_created = _run_rule_checks(
        db=db,
        session_id=session_id,
        company_id=company_id,
        current_state=current_state,
        delta=delta,
        snapshot_id=str(snapshot.id),
        session_context=ctx,
    )

    # ── Step 8: Update CC session context ──
    try:
        ctx["awareness_enabled"] = True
        ctx["awareness_last_tick"] = datetime.now(timezone.utc).isoformat()
        ctx["awareness_tick_number"] = tick_number
        ctx["awareness_system_health"] = current_state.get("system_health", "unknown")
        ctx["awareness_quality_score"] = current_state.get("quality_score")
        ctx["awareness_drift_score"] = current_state.get("drift_score")
        ctx["awareness_ticket_volume_today"] = current_state.get("ticket_volume_today", 0)
        ctx["active_alerts_count"] = len(alerts_created)
        ctx["last_awareness_delta"] = delta

        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()
    except Exception:
        logger.exception("Failed to update CC context after awareness tick")

    # ── Step 9: Prune old snapshots ──
    try:
        prune_old_snapshots(db, session_id, company_id)
    except Exception:
        logger.exception("Failed to prune old snapshots")

    # ── Step 10: Prune expired alerts ──
    try:
        prune_expired_alerts(db, session_id, company_id)
    except Exception:
        logger.exception("Failed to prune expired alerts")

    # ── Step 10b: Prune expired activity log entries ──
    try:
        from app.services.activity_store import prune_expired
        prune_expired(db, company_id=company_id)
    except Exception:
        logger.debug("activity_prune_non_fatal", exc_info=True)

    # ── Step 11: Dispatch events (Phase 2.4) ──
    try:
        from app.services import jarvis_event_dispatcher

        # Dispatch tick event
        jarvis_event_dispatcher.dispatch_tick_event(
            company_id=company_id,
            session_id=session_id,
            tick_number=tick_number,
            tick_type=tick_type,
            system_health=current_state.get("system_health", "unknown"),
            alerts_created=len(alerts_created),
            quality_score=current_state.get("quality_score"),
            drift_score=current_state.get("drift_score"),
        )

        # Dispatch alert events
        for alert in alerts_created:
            jarvis_event_dispatcher.dispatch_alert_event(
                company_id=company_id,
                session_id=session_id,
                alert_id=str(alert.id),
                alert_type=alert.alert_type,
                severity=alert.severity,
                title=alert.title,
                action="created",
            )

        # Dispatch state change events from delta
        for change in delta.get("new_alerts", []):
            jarvis_event_dispatcher.dispatch_state_event(
                company_id=company_id,
                session_id=session_id,
                field=change.get("field", "unknown"),
                old_value=change.get("from"),
                new_value=change.get("to"),
                change_type=change.get("change", "changed"),
            )
    except Exception:
        logger.debug("event_dispatch_non_fatal", exc_info=True)

    # ── Step 12: Auto-command from alerts (Phase 3) ──
    # When critical/emergency alerts are created, automatically route them
    # through the multi-agent command graph so Jarvis TAKES ACTION.
    try:
        for alert in alerts_created:
            if alert.severity in ("critical", "emergency"):
                from app.services.jarvis_agents.command_graph import run_command_from_alert

                run_command_from_alert(
                    company_id=company_id,
                    session_id=session_id,
                    user_id=user_id,
                    alert_id=str(alert.id),
                    alert_type=alert.alert_type,
                    alert_severity=alert.severity,
                    alert_message=alert.message,
                    alert_details=_safe_parse_json(alert.details_json),
                    awareness_snapshot=current_state,
                    session_context=ctx,
                    variant_tier=ctx.get("variant_tier", "mini_parwa"),
                )
                logger.info(
                    "auto_command_dispatched: alert=%s, type=%s, severity=%s",
                    str(alert.id), alert.alert_type, alert.severity,
                )
    except Exception:
        logger.debug("auto_command_non_fatal", exc_info=True)

    total_ms = round((time.monotonic() - start_time) * 1000, 2)

    tick_result = {
        "snapshot_id": str(snapshot.id),
        "tick_type": tick_type,
        "tick_number": tick_number,
        "alerts_created": len(alerts_created),
        "alert_ids": [str(a.id) for a in alerts_created],
        "system_health": current_state.get("system_health", "unknown"),
        "quality_score": current_state.get("quality_score"),
        "drift_score": current_state.get("drift_score"),
        "delta_significant": delta.get("has_significant_changes", False),
        "total_ms": total_ms,
    }

    logger.info(
        "awareness_tick_complete: session=%s, type=%s, tick=%d, "
        "alerts=%d, health=%s, quality=%s, delta=%s, ms=%s",
        session_id, tick_type, tick_number,
        len(alerts_created),
        current_state.get("system_health", "unknown"),
        current_state.get("quality_score", "N/A"),
        delta.get("has_significant_changes", False),
        total_ms,
    )

    return tick_result


# ══════════════════════════════════════════════════════════════════
# STATE COLLECTION: Read real-time data from 7 domains
# ══════════════════════════════════════════════════════════════════


def collect_awareness_state(
    db: Session,
    company_id: str,
    session_id: str,
    live_graph_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Collect current awareness state from all 8 monitoring domains.

    Each domain collector is independently wrapped in try/except (BC-008).
    If a collector fails, its fields are set to safe defaults and
    the engine continues with the other domains.

    JV-02 FIX: The awareness engine previously ONLY read from the database,
    which could be stale compared to the live LangGraph state. Now it accepts
    an optional ``live_graph_state`` parameter containing the current
    ParwaGraphState. When provided, the live state is merged with the DB
    data, with live state taking precedence for fields that are more recent.
    This ensures awareness decisions are based on the freshest available data.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: CC session ID for context lookup.
        live_graph_state: Optional live ParwaGraphState dict from LangGraph.
            When provided, its GROUP 14 fields are merged with DB data,
            with live values taking precedence.

    Returns:
        Dict with all GROUP 14 fields populated from real-time data.
    """
    state: Dict[str, Any] = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "collection_errors": [],
    }

    # Domain 1: Plan & Subscription
    state.update(_collect_plan_subscription(db, company_id))

    # Domain 2: System Health
    state.update(_collect_system_health(db, company_id))

    # Domain 3: Ticket Volume
    state.update(_collect_ticket_volume(db, company_id))

    # Domain 4: Agent Pool
    state.update(_collect_agent_pool(db, company_id))

    # Domain 5: Training (Agent Lightning)
    state.update(_collect_training(db, company_id))

    # Domain 6: Drift & Quality
    state.update(_collect_drift_quality(db, company_id))

    # Domain 7: Errors
    state.update(_collect_errors(db, company_id))

    # Domain 8: Activity Store (non-agentic awareness)
    # This is where Jarvis gets awareness of things that aren't
    # handled by agentic variant agents: user actions, billing,
    # channel events, admin actions, integrations, etc.
    state.update(_collect_activity_store(db, company_id, session_id))

    # Domain 9: Shadow Mode awareness
    # Jarvis MUST know if shadow mode is on/off, what phase it's in,
    # and which variants are being compared. Without this, Jarvis can't
    # understand why certain tickets are being handled differently.
    state.update(_collect_shadow_mode(db, company_id))

    # Domain 10: Dashboard & Ticket Actions awareness
    # Jarvis MUST know what the user is doing in the dashboard:
    # which pages they visit, which tickets they interact with,
    # which settings they change. This enables context-aware conversations.
    state.update(_collect_dashboard_awareness(db, company_id, session_id))

    # Domain 11: Onboarding Funnel awareness
    # Jarvis MUST know about the onboarding pipeline: how many sessions
    # are active, verification rates, payment conversion, and drop-off
    # points. This gives Jarvis full awareness of the pre-purchase funnel.
    state.update(_collect_onboarding_awareness(db, company_id))

    # ── JV-02: Merge live LangGraph state (takes precedence over DB) ──
    if live_graph_state and isinstance(live_graph_state, dict):
        state = _merge_live_graph_state(state, live_graph_state)

    return state


def _merge_live_graph_state(
    db_state: Dict[str, Any],
    live_state: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge live LangGraph ParwaGraphState into DB-collected state.

    JV-02 FIX: Live LangGraph state reflects in-flight graph executions
    that haven't been persisted to DB yet. This function merges the live
    state into the DB state, with live values taking precedence for all
    GROUP 14 awareness fields.

    Mapping from ParwaGraphState GROUP 14 fields to awareness state keys:
      - jarvis_system_health       → system_health
      - jarvis_channel_health      → channel_health
      - jarvis_active_alerts       → active_alerts
      - jarvis_ticket_volume_today → ticket_volume_today
      - jarvis_ticket_volume_avg   → ticket_volume_avg
      - jarvis_ticket_volume_spike → ticket_volume_spike
      - jarvis_active_agents       → active_agents
      - jarvis_agent_pool_capacity → agent_pool_capacity
      - jarvis_agent_pool_utilization → agent_pool_utilization
      - jarvis_training_running    → training_running
      - jarvis_training_mistake_count → training_mistake_count
      - jarvis_training_model_version → training_model_version
      - jarvis_drift_status        → drift_status
      - jarvis_drift_score         → drift_score
      - jarvis_quality_score       → quality_score
      - jarvis_quality_alerts      → quality_alerts
      - jarvis_last_5_errors       → last_5_errors
      - jarvis_subscription_status → subscription_status
      - jarvis_current_plan        → current_plan
      - jarvis_plan_usage_today    → plan_usage_today
      - jarvis_days_until_renewal  → days_until_renewal

    Args:
        db_state: State collected from DB queries.
        live_state: Live ParwaGraphState from LangGraph.

    Returns:
        Merged state dict with live values taking precedence.
    """
    # Mapping: ParwaGraphState key → awareness state key
    field_map = {
        "jarvis_system_health": "system_health",
        "jarvis_channel_health": "channel_health",
        "jarvis_active_alerts": "active_alerts",
        "jarvis_ticket_volume_today": "ticket_volume_today",
        "jarvis_ticket_volume_avg": "ticket_volume_avg",
        "jarvis_ticket_volume_spike": "ticket_volume_spike",
        "jarvis_active_agents": "active_agents",
        "jarvis_agent_pool_capacity": "agent_pool_capacity",
        "jarvis_agent_pool_utilization": "agent_pool_utilization",
        "jarvis_training_running": "training_running",
        "jarvis_training_mistake_count": "training_mistake_count",
        "jarvis_training_model_version": "training_model_version",
        "jarvis_drift_status": "drift_status",
        "jarvis_drift_score": "drift_score",
        "jarvis_quality_score": "quality_score",
        "jarvis_quality_alerts": "quality_alerts",
        "jarvis_last_5_errors": "last_5_errors",
        "jarvis_subscription_status": "subscription_status",
        "jarvis_current_plan": "current_plan",
        "jarvis_plan_usage_today": "plan_usage_today",
        "jarvis_days_until_renewal": "days_until_renewal",
    }

    merged = dict(db_state)
    merged["_live_state_merged"] = False
    merged["_live_state_keys"] = []

    for lg_key, awareness_key in field_map.items():
        if lg_key in live_state and live_state[lg_key] is not None:
            merged[awareness_key] = live_state[lg_key]
            merged["_live_state_merged"] = True
            merged["_live_state_keys"].append(awareness_key)

    if merged["_live_state_merged"]:
        logger.info(
            "live_state_merged: keys=%s, live_overrides=%d",
            merged["_live_state_keys"],
            len(merged["_live_state_keys"]),
        )

    return merged


def get_live_graph_state(
    company_id: str,
    session_id: str,
) -> Optional[Dict[str, Any]]:
    """Retrieve the current live LangGraph ParwaGraphState for a session.

    JV-02 FIX: This function reads from the LangGraph checkpointer to get
    the most recent graph state for a session. This is the "live" state that
    may contain more recent data than what has been persisted to the DB.

    If the LangGraph graph or checkpointer is not available, returns None
    and the awareness engine will fall back to DB-only data.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.

    Returns:
        Dict with live ParwaGraphState fields, or None if unavailable.
    """
    try:
        from app.core.langgraph.graph import get_compiled_graph

        graph = get_compiled_graph()
        if graph is None:
            return None

        # Read from checkpointer using thread_id = session_id
        config = {"configurable": {"thread_id": session_id}}
        state_snapshot = graph.get_state(config)

        if state_snapshot and state_snapshot.values:
            live_state = dict(state_snapshot.values)
            logger.debug(
                "live_graph_state_retrieved: session=%s, keys=%d",
                session_id, len(live_state),
            )
            return live_state

    except ImportError:
        logger.debug("langgraph_not_available: skipping live state read")
    except Exception as e:
        logger.debug(
            "live_graph_state_failed: session=%s, error=%s",
            session_id, str(e)[:200],
        )

    return None



# ══════════════════════════════════════════════════════════════════
# DOMAIN 8: ACTIVITY STORE (Non-Agentic Awareness)
# ══════════════════════════════════════════════════════════════════


def _collect_activity_store(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Collect non-agentic awareness from the Activity Store.

    This is Domain 8 — the key differentiator. For AGENTIC parts,
    Jarvis asks variant agents directly via variant_bridge. For
    NON-AGENTIC parts (user actions, billing, system events, config
    changes), Jarvis reads the Activity Store.

    The Activity Store records EVERY action in the system, so Jarvis
    doesn't need hardcoded awareness functions. Instead, it reads
    what happened and REASONS about it using the ZAI LLM.

    Returns:
        Dict with activity_awareness fields:
          - activity_total_last_hour: count of activities in last hour
          - activity_billing_awareness: billing events summary
          - activity_user_awareness: user behavior summary
          - activity_system_awareness: system events summary
          - activity_flags: auto-detected flags for Jarvis
          - activity_recent_high: last 5 high-importance events
    """
    defaults: Dict[str, Any] = {
        "activity_total_last_hour": 0,
        "activity_billing_awareness": {},
        "activity_user_awareness": {},
        "activity_system_awareness": {},
        "activity_flags": [],
        "activity_recent_high": [],
    }

    try:
        from app.services.activity_store import get_awareness_context

        # Get the full awareness context from the Activity Store
        # This reads recent activities for this tenant (1 hour window)
        awareness = get_awareness_context(db, company_id, hours=1)

        defaults["activity_total_last_hour"] = awareness.get("summary", {}).get("total_count", 0)
        defaults["activity_billing_awareness"] = awareness.get("billing_awareness", {})
        defaults["activity_user_awareness"] = awareness.get("user_action_awareness", {})
        defaults["activity_system_awareness"] = awareness.get("system_awareness", {})
        defaults["activity_flags"] = awareness.get("flags", [])
        defaults["activity_recent_high"] = awareness.get("summary", {}).get("recent_high", [])

        logger.debug(
            "domain8_activity_store: company=%s, total_last_hour=%d, flags=%d",
            company_id,
            defaults["activity_total_last_hour"],
            len(defaults["activity_flags"]),
        )

    except Exception as e:
        logger.warning(
            "domain8_activity_store_failed: company=%s, error=%s",
            company_id, str(e)[:200],
        )
        defaults["activity_store_error"] = str(e)[:200]

    return defaults


# ══════════════════════════════════════════════════════════════════
# SNAPSHOT MANAGEMENT
# ══════════════════════════════════════════════════════════════════


def create_snapshot(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    tick_type: str = "periodic",
    tick_number: int = 1,
) -> JarvisAwarenessSnapshot:
    """Create a new JarvisAwarenessSnapshot from collected state.

    Maps GROUP 14 fields from the state dict to the ORM model columns.
    Also stores the complete raw state in raw_state_json for recovery.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        state: Collected awareness state dict.
        tick_type: periodic, on_change, manual, or emergency.
        tick_number: Monotonically increasing tick counter.

    Returns:
        JarvisAwarenessSnapshot ORM instance.
    """
    # Channel health → JSON
    channel_health = state.get("channel_health", {})
    if isinstance(channel_health, dict):
        channel_health_json = json.dumps(channel_health)
    else:
        channel_health_json = json.dumps({})

    # Active alerts → JSON
    active_alerts = state.get("active_alerts", [])
    if isinstance(active_alerts, list):
        active_alerts_json = json.dumps(active_alerts)
        active_alerts_count = len(active_alerts)
    else:
        active_alerts_json = "[]"
        active_alerts_count = 0

    # Quality alerts → JSON
    quality_alerts = state.get("quality_alerts", [])
    quality_alerts_json = json.dumps(quality_alerts) if isinstance(quality_alerts, list) else "[]"

    # Last 5 errors → JSON
    last_5_errors = state.get("last_5_errors", [])
    last_5_errors_json = json.dumps(last_5_errors) if isinstance(last_5_errors, list) else "[]"

    # Raw state → JSON (complete dump for crash recovery)
    raw_state_json = json.dumps(state, default=str)

    snapshot = JarvisAwarenessSnapshot(
        session_id=session_id,
        company_id=company_id,
        snapshot_type=tick_type,
        tick_number=tick_number,
        current_plan=state.get("current_plan"),
        plan_usage_today=state.get("plan_usage_today"),
        subscription_status=state.get("subscription_status"),
        days_until_renewal=state.get("days_until_renewal"),
        system_health=state.get("system_health", "unknown"),
        channel_health_json=channel_health_json,
        active_alerts_count=active_alerts_count,
        active_alerts_json=active_alerts_json,
        ticket_volume_today=state.get("ticket_volume_today", 0),
        ticket_volume_avg=state.get("ticket_volume_avg"),
        ticket_volume_spike=state.get("ticket_volume_spike", False),
        active_agents=state.get("active_agents", 0),
        agent_pool_capacity=state.get("agent_pool_capacity", 0),
        agent_pool_utilization=state.get("agent_pool_utilization"),
        training_running=state.get("training_running", False),
        training_mistake_count=state.get("training_mistake_count", 0),
        training_model_version=state.get("training_model_version"),
        drift_status=state.get("drift_status", "none"),
        drift_score=state.get("drift_score"),
        quality_score=state.get("quality_score"),
        quality_alerts_json=quality_alerts_json,
        last_5_errors_json=last_5_errors_json,
        raw_state_json=raw_state_json,
        # Domain 9: Shadow Mode
        shadow_mode_active=state.get("shadow_mode_active", False),
        shadow_mode_phase=state.get("shadow_mode_phase"),
        shadow_mode_live_variant=state.get("shadow_mode_live_variant"),
        shadow_mode_shadow_variant=state.get("shadow_mode_shadow_variant"),
        shadow_mode_win_rate=state.get("shadow_mode_win_rate"),
        shadow_mode_total_comparisons=state.get("shadow_mode_total_comparisons", 0),
        shadow_mode_quality_streak=state.get("shadow_mode_quality_streak", 0),
        shadow_mode_recent_events_json=json.dumps(
            state.get("shadow_mode_recent_events", []), default=str
        ),
        # Domain 10: Dashboard & Ticket Actions
        user_current_page=state.get("user_current_page"),
        recent_dashboard_action_count=state.get("recent_dashboard_action_count", 0),
        recent_ticket_action_count=state.get("recent_ticket_action_count", 0),
        recent_dashboard_events_json=json.dumps(
            state.get("recent_dashboard_events", []), default=str
        ),
        recent_ticket_actions_json=json.dumps(
            state.get("recent_ticket_actions", []), default=str
        ),
        # Domain 11: Onboarding Funnel awareness
        onboarding_active_sessions=state.get("onboarding_active_sessions", 0),
        onboarding_verification_rate=state.get("onboarding_verification_rate"),
        onboarding_payment_rate=state.get("onboarding_payment_rate"),
        onboarding_handoff_rate=state.get("onboarding_handoff_rate"),
        onboarding_stage_distribution_json=json.dumps(
            state.get("onboarding_stage_distribution", {}), default=str
        ),
        onboarding_flags_json=json.dumps(
            state.get("onboarding_flags", []), default=str
        ),
    )
    db.add(snapshot)
    db.flush()

    logger.debug(
        "snapshot_created: id=%s, session=%s, tick=%d, type=%s, health=%s",
        snapshot.id, session_id, tick_number, tick_type,
        state.get("system_health", "unknown"),
    )

    return snapshot


def get_latest_snapshot(
    db: Session,
    session_id: str,
    company_id: str,
) -> Optional[JarvisAwarenessSnapshot]:
    """Get the most recent awareness snapshot for a session.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.

    Returns:
        JarvisAwarenessSnapshot or None.
    """
    return (
        db.query(JarvisAwarenessSnapshot)
        .filter(
            JarvisAwarenessSnapshot.session_id == session_id,
            JarvisAwarenessSnapshot.company_id == company_id,
        )
        .order_by(JarvisAwarenessSnapshot.created_at.desc())
        .first()
    )


def get_snapshot_history(
    db: Session,
    session_id: str,
    company_id: str,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[JarvisAwarenessSnapshot], int]:
    """Get paginated snapshot history for a session.

    Returns snapshots in reverse chronological order (newest first).

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        limit: Max snapshots to return.
        offset: Pagination offset.

    Returns:
        Tuple of (snapshots_list, total_count).
    """
    query = (
        db.query(JarvisAwarenessSnapshot)
        .filter(
            JarvisAwarenessSnapshot.session_id == session_id,
            JarvisAwarenessSnapshot.company_id == company_id,
        )
        .order_by(JarvisAwarenessSnapshot.created_at.desc())
    )
    total = query.count()
    snapshots = query.offset(offset).limit(limit).all()
    return snapshots, total


# ══════════════════════════════════════════════════════════════════
# ALERT MANAGEMENT
# ══════════════════════════════════════════════════════════════════


def create_alert(
    db: Session,
    session_id: str,
    company_id: str,
    alert_type: str,
    severity: str,
    category: str,
    title: str,
    message: str,
    details_json: str = "{}",
    action_required: bool = False,
    action_url: Optional[str] = None,
    ttl_seconds: int = 0,
    related_snapshot_id: Optional[str] = None,
    dedup_key: Optional[str] = None,
) -> Optional[JarvisProactiveAlert]:
    """Create a proactive alert, with optional deduplication.

    If a dedup_key is provided and an active alert with the same
    dedup_key (stored in details_json) already exists, no new alert
    is created. This prevents alert storms.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        alert_type: Type of alert (e.g., ticket_volume_spike).
        severity: info, warning, critical, emergency.
        category: Alert category (e.g., system_health).
        title: Short alert title.
        message: Detailed alert message.
        details_json: JSON string with structured details.
        action_required: Whether user action is needed.
        action_url: Deep link to dashboard section.
        ttl_seconds: Time-to-live in seconds (0 = no expiry).
        related_snapshot_id: ID of the triggering snapshot.
        dedup_key: Optional deduplication key.

    Returns:
        JarvisProactiveAlert or None if deduplicated.
    """
    # Deduplication check
    if dedup_key:
        existing = (
            db.query(JarvisProactiveAlert)
            .filter(
                JarvisProactiveAlert.session_id == session_id,
                JarvisProactiveAlert.company_id == company_id,
                JarvisProactiveAlert.alert_type == alert_type,
                JarvisProactiveAlert.status == "active",
            )
            .first()
        )
        if existing:
            # Check if details contain same dedup_key
            try:
                existing_details = _safe_parse_json(existing.details_json)
                if existing_details.get("_dedup_key") == dedup_key:
                    logger.debug(
                        "alert_deduped: type=%s, key=%s, session=%s",
                        alert_type, dedup_key, session_id,
                    )
                    return None  # Already have an active alert for this
            except Exception:
                pass

    # Cooldown check: prevent alert spam during sustained issues
    if dedup_key and _is_in_cooldown(db, session_id, company_id, dedup_key):
        logger.debug(
            "alert_cooldown: type=%s, key=%s, session=%s",
            alert_type, dedup_key, session_id,
        )
        return None

    # Add dedup_key to details
    try:
        details = _safe_parse_json(details_json)
        details["_dedup_key"] = dedup_key or ""
        details_json = json.dumps(details)
    except Exception:
        pass

    # Determine TTL based on severity if not specified
    if ttl_seconds == 0:
        ttl_seconds = {
            "info": ALERT_TTL_INFO,
            "warning": ALERT_TTL_WARNING,
            "critical": ALERT_TTL_CRITICAL,
            "emergency": ALERT_TTL_EMERGENCY,
        }.get(severity, ALERT_TTL_INFO)

    alert = JarvisProactiveAlert(
        session_id=session_id,
        company_id=company_id,
        alert_type=alert_type,
        severity=severity,
        category=category,
        title=title,
        message=message,
        details_json=details_json,
        action_required=action_required,
        action_url=action_url,
        ttl_seconds=ttl_seconds,
        related_snapshot_id=related_snapshot_id,
        status="active",
    )
    db.add(alert)
    db.flush()

    logger.info(
        "alert_created: id=%s, type=%s, severity=%s, category=%s, "
        "session=%s, action_required=%s",
        alert.id, alert_type, severity, category, session_id, action_required,
    )

    return alert


def get_active_alerts(
    db: Session,
    session_id: str,
    company_id: str,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[JarvisProactiveAlert], int]:
    """Get active (non-resolved, non-expired) alerts for a session.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        severity: Filter by severity (optional).
        category: Filter by category (optional).
        limit: Max alerts to return.
        offset: Pagination offset.

    Returns:
        Tuple of (alerts_list, total_count).
    """
    query = (
        db.query(JarvisProactiveAlert)
        .filter(
            JarvisProactiveAlert.session_id == session_id,
            JarvisProactiveAlert.company_id == company_id,
            JarvisProactiveAlert.status.in_(["active", "acknowledged"]),
        )
    )

    if severity:
        query = query.filter(JarvisProactiveAlert.severity == severity)
    if category:
        query = query.filter(JarvisProactiveAlert.category == category)

    query = query.order_by(
        # Emergency first, then critical, warning, info
        JarvisProactiveAlert.severity.desc(),
        JarvisProactiveAlert.created_at.desc(),
    )

    total = query.count()
    alerts = query.offset(offset).limit(limit).all()
    return alerts, total


def acknowledge_alert(
    db: Session,
    alert_id: str,
    session_id: str,
    company_id: str,
    user_id: str,
) -> JarvisProactiveAlert:
    """Acknowledge an active alert.

    Args:
        db: SQLAlchemy session.
        alert_id: Alert ID.
        session_id: CC session ID for security scoping.
        company_id: Company ID for BC-001.
        user_id: User ID who acknowledged.

    Returns:
        Updated JarvisProactiveAlert.

    Raises:
        NotFoundError: If alert not found or not in active state.
    """
    alert = (
        db.query(JarvisProactiveAlert)
        .filter(
            JarvisProactiveAlert.id == alert_id,
            JarvisProactiveAlert.session_id == session_id,
            JarvisProactiveAlert.company_id == company_id,
            JarvisProactiveAlert.status == "active",
        )
        .first()
    )
    if not alert:
        raise NotFoundError(
            message="Active alert not found",
            details={"alert_id": alert_id},
        )

    alert.status = "acknowledged"
    alert.acknowledged_by = user_id
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.updated_at = datetime.now(timezone.utc)
    db.flush()

    logger.info(
        "alert_acknowledged: id=%s, user=%s, session=%s",
        alert_id, user_id, session_id,
    )

    return alert


def dismiss_alert(
    db: Session,
    alert_id: str,
    session_id: str,
    company_id: str,
    user_id: str,
) -> JarvisProactiveAlert:
    """Dismiss an active or acknowledged alert.

    Args:
        db: SQLAlchemy session.
        alert_id: Alert ID.
        session_id: CC session ID for security scoping.
        company_id: Company ID for BC-001.
        user_id: User ID who dismissed.

    Returns:
        Updated JarvisProactiveAlert.

    Raises:
        NotFoundError: If alert not found or already resolved/expired.
    """
    alert = (
        db.query(JarvisProactiveAlert)
        .filter(
            JarvisProactiveAlert.id == alert_id,
            JarvisProactiveAlert.session_id == session_id,
            JarvisProactiveAlert.company_id == company_id,
            JarvisProactiveAlert.status.in_(["active", "acknowledged"]),
        )
        .first()
    )
    if not alert:
        raise NotFoundError(
            message="Dismissible alert not found",
            details={"alert_id": alert_id},
        )

    alert.status = "dismissed"
    alert.acknowledged_by = user_id
    alert.acknowledged_at = alert.acknowledged_at or datetime.now(timezone.utc)
    alert.updated_at = datetime.now(timezone.utc)
    db.flush()

    logger.info(
        "alert_dismissed: id=%s, user=%s, session=%s",
        alert_id, user_id, session_id,
    )

    return alert


def resolve_alert(
    db: Session,
    alert_id: str,
    session_id: str,
    company_id: str,
) -> JarvisProactiveAlert:
    """Resolve an active or acknowledged alert.

    Typically called when the underlying issue has been fixed
    (e.g., system health recovered, quality score improved).

    Args:
        db: SQLAlchemy session.
        alert_id: Alert ID.
        session_id: CC session ID for security scoping.
        company_id: Company ID for BC-001.

    Returns:
        Updated JarvisProactiveAlert.

    Raises:
        NotFoundError: If alert not found.
    """
    alert = (
        db.query(JarvisProactiveAlert)
        .filter(
            JarvisProactiveAlert.id == alert_id,
            JarvisProactiveAlert.session_id == session_id,
            JarvisProactiveAlert.company_id == company_id,
            JarvisProactiveAlert.status.in_(["active", "acknowledged"]),
        )
        .first()
    )
    if not alert:
        raise NotFoundError(
            message="Resolvable alert not found",
            details={"alert_id": alert_id},
        )

    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    alert.updated_at = datetime.now(timezone.utc)
    db.flush()

    logger.info(
        "alert_resolved: id=%s, type=%s, session=%s",
        alert_id, alert.alert_type, session_id,
    )

    return alert


# ══════════════════════════════════════════════════════════════════
# PRUNING: Prevent unbounded growth
# ══════════════════════════════════════════════════════════════════


def prune_old_snapshots(
    db: Session,
    session_id: str,
    company_id: str,
    max_keep: int = MAX_SNAPSHOTS_PER_SESSION,
) -> int:
    """Prune old snapshots to prevent unbounded DB growth.

    Keeps the most recent `max_keep` snapshots per session.
    Emergency and on_change snapshots are always preserved.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        max_keep: Maximum snapshots to keep per session.

    Returns:
        Number of snapshots pruned.
    """
    # Count total snapshots for this session
    total = (
        db.query(func.count(JarvisAwarenessSnapshot.id))
        .filter(
            JarvisAwarenessSnapshot.session_id == session_id,
            JarvisAwarenessSnapshot.company_id == company_id,
        )
        .scalar()
    )

    if total <= max_keep:
        return 0

    # Find IDs to keep (most recent + emergency/on_change)
    keep_ids = (
        db.query(JarvisAwarenessSnapshot.id)
        .filter(
            JarvisAwarenessSnapshot.session_id == session_id,
            JarvisAwarenessSnapshot.company_id == company_id,
        )
        .order_by(JarvisAwarenessSnapshot.created_at.desc())
        .limit(max_keep)
        .all()
    )
    keep_id_set = {row[0] for row in keep_ids}

    # Also keep emergency and on_change snapshots
    special_ids = (
        db.query(JarvisAwarenessSnapshot.id)
        .filter(
            JarvisAwarenessSnapshot.session_id == session_id,
            JarvisAwarenessSnapshot.company_id == company_id,
            JarvisAwarenessSnapshot.snapshot_type.in_(["emergency", "on_change"]),
        )
        .all()
    )
    keep_id_set.update(row[0] for row in special_ids)

    # Delete snapshots not in keep set (batch of SNAPSHOT_PRUNE_BATCH)
    # SQLAlchemy doesn't support .limit().delete(), so we fetch IDs first
    to_delete_ids = (
        db.query(JarvisAwarenessSnapshot.id)
        .filter(
            JarvisAwarenessSnapshot.session_id == session_id,
            JarvisAwarenessSnapshot.company_id == company_id,
            JarvisAwarenessSnapshot.id.notin_(keep_id_set),
        )
        .limit(SNAPSHOT_PRUNE_BATCH)
        .all()
    )
    delete_id_set = {row[0] for row in to_delete_ids}
    pruned = 0
    if delete_id_set:
        pruned = (
            db.query(JarvisAwarenessSnapshot)
            .filter(JarvisAwarenessSnapshot.id.in_(delete_id_set))
            .delete(synchronize_session="fetch")
        )
    db.flush()

    if pruned > 0:
        logger.info(
            "snapshots_pruned: session=%s, pruned=%d, kept=%d",
            session_id, pruned, len(keep_id_set),
        )

    return pruned


def prune_expired_alerts(
    db: Session,
    session_id: str,
    company_id: str,
) -> int:
    """Mark expired alerts (past their TTL) as expired.

    Only processes active alerts with non-zero TTL.
    Emergency alerts (TTL=0) never expire automatically.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.

    Returns:
        Number of alerts expired.
    """
    now = datetime.now(timezone.utc)

    # Find active alerts with TTL that have expired
    active_alerts = (
        db.query(JarvisProactiveAlert)
        .filter(
            JarvisProactiveAlert.session_id == session_id,
            JarvisProactiveAlert.company_id == company_id,
            JarvisProactiveAlert.status == "active",
            JarvisProactiveAlert.ttl_seconds > 0,
        )
        .all()
    )

    expired_count = 0
    for alert in active_alerts:
        if alert.created_at:
            expires_at = alert.created_at + timedelta(seconds=alert.ttl_seconds)
            if now > expires_at:
                alert.status = "expired"
                alert.updated_at = now
                expired_count += 1

    if expired_count > 0:
        db.flush()
        logger.info(
            "alerts_expired: session=%s, count=%d",
            session_id, expired_count,
        )

    return expired_count


# ══════════════════════════════════════════════════════════════════
# DELTA DETECTION: What changed since last tick?
# ══════════════════════════════════════════════════════════════════


def compute_awareness_delta(
    current: Dict[str, Any],
    previous: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute the delta between current and previous awareness state.

    Detects significant changes that might require alerts or
    on_change snapshots. A change is "significant" if it crosses
    a threshold or changes a discrete status value.

    Args:
        current: Current awareness state dict.
        previous: Previous awareness state dict (None if first tick).

    Returns:
        Dict with:
          - changed_fields: Dict of {field: {"from": old, "to": new}}
          - has_significant_changes: bool
          - new_alerts: List of alert-worthy changes
          - recovered: List of fields that improved
    """
    if previous is None:
        return {
            "changed_fields": {},
            "has_significant_changes": True,  # First tick is always significant
            "new_alerts": [],
            "recovered": [],
            "is_first_tick": True,
        }

    delta: Dict[str, Any] = {
        "changed_fields": {},
        "has_significant_changes": False,
        "new_alerts": [],
        "recovered": [],
        "is_first_tick": False,
    }

    # Fields to check for discrete status changes
    status_fields = [
        "system_health", "subscription_status", "drift_status",
        "training_running",
    ]

    # Fields to check for threshold crossings
    threshold_fields = {
        "plan_usage_today": [PLAN_USAGE_WARN_THRESHOLD, PLAN_USAGE_CRITICAL_THRESHOLD],
        "agent_pool_utilization": [UTILIZATION_WARN_THRESHOLD, UTILIZATION_CRITICAL_THRESHOLD],
        "quality_score": [QUALITY_CRITICAL_THRESHOLD, QUALITY_WARN_THRESHOLD],  # Reversed: lower = worse
        "drift_score": [DRIFT_WARN_THRESHOLD, DRIFT_CRITICAL_THRESHOLD],
    }

    # Check discrete status changes
    for field in status_fields:
        old_val = previous.get(field)
        new_val = current.get(field)
        if old_val != new_val and old_val is not None and new_val is not None:
            delta["changed_fields"][field] = {"from": old_val, "to": new_val}

            # System health changes are always significant
            if field == "system_health":
                severity_order = {"healthy": 0, "degraded": 1, "critical": 2, "down": 3}
                old_sev = severity_order.get(old_val, 0)
                new_sev = severity_order.get(new_val, 0)
                if new_sev > old_sev:
                    delta["has_significant_changes"] = True
                    delta["new_alerts"].append({
                        "field": field,
                        "change": "worsened",
                        "from": old_val,
                        "to": new_val,
                    })
                elif new_sev < old_sev:
                    delta["recovered"].append({
                        "field": field,
                        "change": "improved",
                        "from": old_val,
                        "to": new_val,
                    })

            # Subscription status changes
            if field == "subscription_status":
                delta["has_significant_changes"] = True
                if new_val in ("past_due", "cancelled"):
                    delta["new_alerts"].append({
                        "field": field,
                        "change": "worsened",
                        "from": old_val,
                        "to": new_val,
                    })

            # Drift status changes
            if field == "drift_status":
                severity_order = {"none": 0, "slight": 1, "moderate": 2, "severe": 3}
                old_sev = severity_order.get(old_val, 0)
                new_sev = severity_order.get(new_val, 0)
                if new_sev > old_sev:
                    delta["has_significant_changes"] = True
                    delta["new_alerts"].append({
                        "field": field,
                        "change": "worsened",
                        "from": old_val,
                        "to": new_val,
                    })
                elif new_sev < old_sev:
                    delta["recovered"].append({
                        "field": field,
                        "change": "improved",
                        "from": old_val,
                        "to": new_val,
                    })

    # Check threshold crossings
    for field, thresholds in threshold_fields.items():
        old_val = previous.get(field)
        new_val = current.get(field)

        if old_val is None or new_val is None:
            continue

        try:
            old_float = float(old_val)
            new_float = float(new_val)
        except (ValueError, TypeError):
            continue

        # For quality_score, lower is worse (reversed thresholds)
        if field == "quality_score":
            # thresholds = [QUALITY_CRITICAL_THRESHOLD, QUALITY_WARN_THRESHOLD]
            # = [0.50, 0.70] — crit first, warn second for quality
            crit_thresh, warn_thresh = thresholds  # crit=0.50, warn=0.70
            if new_float < crit_thresh and old_float >= crit_thresh:
                delta["has_significant_changes"] = True
                delta["new_alerts"].append({
                    "field": field,
                    "change": "crossed_critical",
                    "from": old_float,
                    "to": new_float,
                    "threshold": crit_thresh,
                })
            elif new_float < warn_thresh and old_float >= warn_thresh:
                delta["has_significant_changes"] = True
                delta["new_alerts"].append({
                    "field": field,
                    "change": "crossed_warning",
                    "from": old_float,
                    "to": new_float,
                    "threshold": warn_thresh,
                })
            elif new_float >= warn_thresh and old_float < warn_thresh:
                delta["recovered"].append({
                    "field": field,
                    "change": "recovered_above_warning",
                    "from": old_float,
                    "to": new_float,
                })
        else:
            warn_thresh, crit_thresh = thresholds  # warn < crit for others
            if new_float >= crit_thresh and old_float < crit_thresh:
                delta["has_significant_changes"] = True
                delta["new_alerts"].append({
                    "field": field,
                    "change": "crossed_critical",
                    "from": old_float,
                    "to": new_float,
                    "threshold": crit_thresh,
                })
            elif new_float >= warn_thresh and old_float < warn_thresh:
                delta["has_significant_changes"] = True
                delta["new_alerts"].append({
                    "field": field,
                    "change": "crossed_warning",
                    "from": old_float,
                    "to": new_float,
                    "threshold": warn_thresh,
                })
            elif new_float < warn_thresh and old_float >= warn_thresh:
                delta["recovered"].append({
                    "field": field,
                    "change": "recovered_below_warning",
                    "from": old_float,
                    "to": new_float,
                })

    # Check ticket volume spike
    old_spike = previous.get("ticket_volume_spike", False)
    new_spike = current.get("ticket_volume_spike", False)
    if new_spike and not old_spike:
        delta["has_significant_changes"] = True
        delta["new_alerts"].append({
            "field": "ticket_volume_spike",
            "change": "spike_detected",
            "today": current.get("ticket_volume_today"),
            "avg": current.get("ticket_volume_avg"),
        })

    return delta


# ══════════════════════════════════════════════════════════════════
# DOMAIN COLLECTORS: Read real-time data from each domain
# ══════════════════════════════════════════════════════════════════


def _collect_plan_subscription(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 1: Plan & Subscription.

    Reads subscription status, plan usage, and renewal info.
    """
    result = {
        "current_plan": "mini_parwa",
        "plan_usage_today": 0.0,
        "subscription_status": "active",
        "days_until_renewal": 30,
    }

    try:
        from database.models.core import Subscription
        subscription = (
            db.query(Subscription)
            .filter(Subscription.company_id == company_id)
            .order_by(Subscription.created_at.desc())
            .first()
        )
        if subscription:
            result["current_plan"] = subscription.plan_type or "mini_parwa"
            result["subscription_status"] = subscription.status or "active"
            if subscription.usage_percentage is not None:
                result["plan_usage_today"] = float(subscription.usage_percentage)
            if subscription.renewal_date:
                days_left = (subscription.renewal_date - datetime.now(timezone.utc).date()).days
                result["days_until_renewal"] = max(0, days_left)
    except Exception:
        logger.debug("plan_subscription_collection_failed: company=%s", company_id)

    return result


def _collect_system_health(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 2: System Health.

    Reads overall system health and per-channel health.
    """
    result = {
        "system_health": "healthy",
        "channel_health": {},
        "active_alerts": [],
    }

    try:
        from database.models.core import EmergencyState
        emergency = (
            db.query(EmergencyState)
            .filter(EmergencyState.company_id == company_id)
            .order_by(EmergencyState.created_at.desc())
            .first()
        )
        if emergency:
            if emergency.is_paused:
                result["system_health"] = "critical"
            elif emergency.paused_channels:
                result["system_health"] = "degraded"
                channels = emergency.paused_channels.split(",") if isinstance(emergency.paused_channels, str) else []
                for ch in channels:
                    result["channel_health"][ch.strip()] = "paused"
    except Exception:
        logger.debug("system_health_collection_failed: company=%s", company_id)

    # Per-channel health from recent delivery failures
    try:
        from database.models.tickets import Ticket
        from sqlalchemy import case

        # Check for recent delivery failures per channel
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        channel_stats = (
            db.query(
                Ticket.channel,
                func.count(Ticket.id).label("total"),
                func.sum(case(
                    (Ticket.status == "delivery_failed", 1),
                    else_=0,
                )).label("failed"),
            )
            .filter(
                Ticket.company_id == company_id,
                Ticket.created_at >= recent_cutoff,
            )
            .group_by(Ticket.channel)
            .all()
        )

        for ch, total, failed in channel_stats:
            if total and total > 0:
                failure_rate = (failed or 0) / total
                if failure_rate > 0.5:
                    result["channel_health"][ch] = "down"
                    result["system_health"] = "degraded"
                elif failure_rate > 0.2:
                    result["channel_health"][ch] = "degraded"
                else:
                    result["channel_health"][ch] = "healthy"
    except Exception:
        logger.debug("channel_health_collection_failed: company=%s", company_id)

    return result


def _collect_ticket_volume(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 3: Ticket Volume.

    Reads today's ticket count, 7-day average, and detects spikes.
    """
    result = {
        "ticket_volume_today": 0,
        "ticket_volume_avg": 0.0,
        "ticket_volume_spike": False,
    }

    try:
        from database.models.tickets import Ticket

        # Today's count
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        today_count = (
            db.query(func.count(Ticket.id))
            .filter(
                Ticket.company_id == company_id,
                Ticket.created_at >= today_start,
            )
            .scalar()
        )
        result["ticket_volume_today"] = today_count or 0

        # 7-day average (excluding today)
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        avg_result = (
            db.query(func.count(Ticket.id) / 7.0)
            .filter(
                Ticket.company_id == company_id,
                Ticket.created_at >= seven_days_ago,
                Ticket.created_at < today_start,
            )
            .scalar()
        )
        result["ticket_volume_avg"] = float(avg_result or 0)

        # Spike detection
        if result["ticket_volume_avg"] > 0:
            spike_ratio = result["ticket_volume_today"] / result["ticket_volume_avg"]
            result["ticket_volume_spike"] = spike_ratio >= SPIKE_MULTIPLIER

    except Exception:
        logger.debug("ticket_volume_collection_failed: company=%s", company_id)

    return result


def _collect_agent_pool(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 4: Agent Pool.

    Reads active agent count, capacity, and utilization.
    """
    result = {
        "active_agents": 0,
        "agent_pool_capacity": 5,
        "agent_pool_utilization": 0.0,
    }

    try:
        from database.models.core import VariantInstance
        instance = (
            db.query(VariantInstance)
            .filter(VariantInstance.company_id == company_id)
            .order_by(VariantInstance.created_at.desc())
            .first()
        )
        if instance:
            result["active_agents"] = getattr(instance, "active_agents", 0) or 0
            result["agent_pool_capacity"] = getattr(instance, "agent_capacity", 5) or 5
            if result["agent_pool_capacity"] > 0:
                result["agent_pool_utilization"] = round(
                    (result["active_agents"] / result["agent_pool_capacity"]) * 100, 2
                )
    except Exception:
        logger.debug("agent_pool_collection_failed: company=%s", company_id)

    return result


def _collect_training(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 5: Training (Agent Lightning).

    Reads training state, mistake count, and model version.
    """
    result = {
        "training_running": False,
        "training_mistake_count": 0,
        "training_model_version": "",
    }

    try:
        from database.models.core import TrainingJob
        job = (
            db.query(TrainingJob)
            .filter(TrainingJob.company_id == company_id)
            .order_by(TrainingJob.created_at.desc())
            .first()
        )
        if job:
            result["training_running"] = getattr(job, "status", "") == "running"
            result["training_mistake_count"] = getattr(job, "mistake_count", 0) or 0
            result["training_model_version"] = getattr(job, "model_version", "") or ""
    except Exception:
        logger.debug("training_collection_failed: company=%s", company_id)

    return result


def _collect_drift_quality(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 6: Drift & Quality.

    Reads model drift status, drift score, quality score, and quality alerts.
    """
    result = {
        "drift_status": "none",
        "drift_score": 0.0,
        "quality_score": 0.0,
        "quality_alerts": [],
    }

    try:
        from database.models.core import QualityMetric
        metric = (
            db.query(QualityMetric)
            .filter(QualityMetric.company_id == company_id)
            .order_by(QualityMetric.created_at.desc())
            .first()
        )
        if metric:
            result["drift_status"] = getattr(metric, "drift_status", "none") or "none"
            result["drift_score"] = float(getattr(metric, "drift_score", 0) or 0)
            result["quality_score"] = float(getattr(metric, "quality_score", 0) or 0)
    except Exception:
        logger.debug("drift_quality_collection_failed: company=%s", company_id)

    return result


def _collect_errors(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 7: Errors.

    Reads last 5 errors from the error log.
    """
    result = {
        "last_5_errors": [],
    }

    try:
        from database.models.core import ErrorLog
        errors = (
            db.query(ErrorLog)
            .filter(ErrorLog.company_id == company_id)
            .order_by(ErrorLog.created_at.desc())
            .limit(5)
            .all()
        )
        for err in errors:
            result["last_5_errors"].append({
                "error": getattr(err, "error_message", ""),
                "node": getattr(err, "node_name", ""),
                "timestamp": err.created_at.isoformat() if err.created_at else "",
                "tenant_id": company_id,
            })
    except Exception:
        logger.debug("errors_collection_failed: company=%s", company_id)

    return result


# ══════════════════════════════════════════════════════════════════
# DOMAIN 8: ACTIVITY STORE (Non-Agentic Awareness)
# ══════════════════════════════════════════════════════════════════


def _collect_activity_store(
    db: Session,
    company_id: str,
    session_id: str,
) -> Dict[str, Any]:
    """Domain 8: Activity Store (Non-Agentic Awareness).

    This is the key domain that gives Jarvis awareness of everything
    that ISN'T handled by agentic variant agents. The Activity Store
    records user actions, billing events, channel events, admin
    actions, and system events.

    For AGENTIC parts (ticket handling, quality, escalation), Jarvis
    asks the variant agents directly via variant_bridge.
    For NON-AGENTIC parts (everything else), Jarvis reads the
    Activity Store.

    Returns:
        Dict with:
          - activity_store_connected: bool
          - recent_activity: last 20 events
          - activity_summary: counts by source/category/severity
          - control_boundary_summary: what Jarvis can/cannot control
          - unread_activity_count: events since last tick
          - critical_activity_count: critical/emergency events
          - collection_timestamp: when this was collected
    """
    result: Dict[str, Any] = {
        "activity_store_connected": False,
        "recent_activity": [],
        "activity_summary": {},
        "control_boundary_summary": {},
        "unread_activity_count": 0,
        "critical_activity_count": 0,
    }

    try:
        from app.services.jarvis_activity_store import collect_activity_awareness

        # Determine variant scope from session context
        variant_scope = None
        try:
            from app.services.jarvis_cc_service import get_cc_session
            session = get_cc_session(db, session_id, "", company_id)
            if session and session.context_json:
                ctx = _safe_parse_json(session.context_json)
                variant_scope = ctx.get("variant_tier")
        except Exception:
            pass  # BC-008: Continue without variant scope

        activity_data = collect_activity_awareness(
            db, company_id, variant_scope=variant_scope,
        )

        result.update(activity_data)

    except Exception:
        logger.debug(
            "activity_store_collection_failed: company=%s, session=%s",
            company_id, session_id,
        )

    return result


def _run_rule_checks(
    db: Session,
    session_id: str,
    company_id: str,
    current_state: Dict[str, Any],
    delta: Dict[str, Any],
    snapshot_id: str,
    session_context: Optional[Dict[str, Any]] = None,
) -> List[JarvisProactiveAlert]:
    """Run all rule checks against current state and create alerts.

    Each rule is independently wrapped in try/except (BC-008).
    A rule failure does NOT prevent other rules from running.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        current_state: Current awareness state.
        delta: Delta from previous state.
        snapshot_id: ID of the snapshot that triggered this check.
        session_context: Optional parsed session context for threshold overrides.

    Returns:
        List of newly created alerts.
    """
    alerts: List[JarvisProactiveAlert] = []

    # Compute threshold overrides from session context
    overrides = _get_threshold_overrides(session_context)

    # Rule 1: System Health
    try:
        rule_alerts = _check_system_health(db, session_id, company_id, current_state, snapshot_id, overrides)
        if rule_alerts:
            alerts.extend(rule_alerts if isinstance(rule_alerts, list) else [rule_alerts])
    except Exception:
        logger.exception("system_health_rule_failed: session=%s", session_id)

    # Rule 2: Ticket Volume Spike
    try:
        alert = _check_ticket_volume_spike(db, session_id, company_id, current_state, snapshot_id, overrides)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("ticket_volume_rule_failed: session=%s", session_id)

    # Rule 3: Agent Pool Utilization
    try:
        rule_alerts = _check_agent_pool(db, session_id, company_id, current_state, snapshot_id, overrides)
        if rule_alerts:
            alerts.extend(rule_alerts if isinstance(rule_alerts, list) else [rule_alerts])
    except Exception:
        logger.exception("agent_pool_rule_failed: session=%s", session_id)

    # Rule 4: Quality Score Drop
    try:
        alert = _check_quality(db, session_id, company_id, current_state, delta, snapshot_id, overrides)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("quality_rule_failed: session=%s", session_id)

    # Rule 5: Model Drift
    try:
        alert = _check_drift(db, session_id, company_id, current_state, delta, snapshot_id, overrides)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("drift_rule_failed: session=%s", session_id)

    # Rule 6: Plan Usage
    try:
        alert = _check_plan_usage(db, session_id, company_id, current_state, snapshot_id, overrides)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("plan_usage_rule_failed: session=%s", session_id)

    # Rule 7: Subscription Status
    try:
        alert = _check_subscription(db, session_id, company_id, current_state, delta, snapshot_id)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("subscription_rule_failed: session=%s", session_id)

    # Rule 8: Renewal Warning
    try:
        alert = _check_renewal(db, session_id, company_id, current_state, snapshot_id, overrides)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("renewal_rule_failed: session=%s", session_id)

    # Rule 9: Error Rate
    try:
        alert = _check_error_rate(db, session_id, company_id, current_state, snapshot_id, overrides)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("error_rate_rule_failed: session=%s", session_id)

    # Rule 10: Compound Spike + Quality Drop
    try:
        alert = _check_compound_spike_quality(db, session_id, company_id, current_state, snapshot_id, overrides)
        if alert:
            alerts.append(alert)
    except Exception:
        logger.exception("compound_spike_quality_rule_failed: session=%s", session_id)

    # Rule 11: Training Status
    try:
        rule_alerts = _check_training_status(db, session_id, company_id, current_state, delta, snapshot_id, overrides)
        if rule_alerts:
            alerts.extend(rule_alerts if isinstance(rule_alerts, list) else [rule_alerts])
    except Exception:
        logger.exception("training_status_rule_failed: session=%s", session_id)

    # Rule 12: Activity Store Critical Events
    # Check for critical/emergency events in the Activity Store
    # (non-agentic events like payment failures, channel outages, etc.)
    try:
        rule_alerts = _check_activity_store_critical(db, session_id, company_id, current_state, snapshot_id, overrides)
        if rule_alerts:
            alerts.extend(rule_alerts if isinstance(rule_alerts, list) else [rule_alerts])
    except Exception:
        logger.exception("activity_store_rule_failed: session=%s", session_id)

    return alerts


def _check_system_health(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    snapshot_id: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> Optional[List[JarvisProactiveAlert]]:
    """Rule 1: System Health Check.

    Alerts when system health is degraded, critical, or down.
    Also creates individual alerts for each channel that is "down" or "degraded".
    Returns a list of alerts (main + channel-specific).
    """
    overrides = overrides or {}
    health = state.get("system_health", "healthy")
    created_alerts: List[JarvisProactiveAlert] = []

    # Channel-specific health alerts (always check, even if overall is healthy)
    channel_health = state.get("channel_health", {})
    for channel, ch_status in channel_health.items():
        if ch_status == "down":
            _escalate_if_needed(
                db, session_id, company_id, "channel_health_down",
                "warning", f"channel_health_{channel}",
            )
            ch_alert = create_alert(
                db=db,
                session_id=session_id,
                company_id=company_id,
                alert_type="channel_health_down",
                severity="warning",
                category="system_health",
                title=f"Channel Down: {channel}",
                message=f"Channel '{channel}' is reporting as down. Delivery failures exceed 50%.",
                details_json=json.dumps({
                    "channel": channel,
                    "channel_status": ch_status,
                }),
                action_required=True,
                action_url="/dashboard/settings?tab=system-health",
                related_snapshot_id=snapshot_id,
                dedup_key=f"channel_health_{channel}",
            )
            if ch_alert:
                created_alerts.append(ch_alert)
        elif ch_status == "degraded":
            _escalate_if_needed(
                db, session_id, company_id, "channel_health_degraded",
                "info", f"channel_health_{channel}",
            )
            ch_alert = create_alert(
                db=db,
                session_id=session_id,
                company_id=company_id,
                alert_type="channel_health_degraded",
                severity="info",
                category="system_health",
                title=f"Channel Degraded: {channel}",
                message=f"Channel '{channel}' is experiencing degraded performance. Delivery failures between 20-50%.",
                details_json=json.dumps({
                    "channel": channel,
                    "channel_status": ch_status,
                }),
                action_required=False,
                action_url="/dashboard/settings?tab=system-health",
                related_snapshot_id=snapshot_id,
                dedup_key=f"channel_health_{channel}",
            )
            if ch_alert:
                created_alerts.append(ch_alert)

    # Main system health alert
    if health == "healthy":
        return created_alerts if created_alerts else None

    severity_map = {
        "degraded": "warning",
        "critical": "critical",
        "down": "emergency",
    }
    severity = severity_map.get(health, "info")

    unhealthy_channels = [ch for ch, status in channel_health.items() if status != "healthy"]

    message = f"System health is {health}"
    if unhealthy_channels:
        message += f". Affected channels: {', '.join(unhealthy_channels)}"

    _escalate_if_needed(
        db, session_id, company_id, "system_health_degraded",
        severity, f"system_health_{health}",
    )

    main_alert = create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="system_health_degraded",
        severity=severity,
        category="system_health",
        title=f"System Health: {health.title()}",
        message=message,
        details_json=json.dumps({
            "system_health": health,
            "unhealthy_channels": unhealthy_channels,
            "channel_health": channel_health,
        }),
        action_required=health in ("critical", "down"),
        action_url="/dashboard/settings?tab=system-health",
        related_snapshot_id=snapshot_id,
        dedup_key=f"system_health_{health}",
    )
    if main_alert:
        created_alerts.insert(0, main_alert)

    return created_alerts if created_alerts else None


def _check_ticket_volume_spike(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    snapshot_id: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> Optional[JarvisProactiveAlert]:
    """Rule 2: Ticket Volume Spike.

    Alerts when today's volume exceeds 2x the 7-day average.
    """
    overrides = overrides or {}
    spike_multiplier = overrides.get("spike_multiplier", SPIKE_MULTIPLIER)

    if not state.get("ticket_volume_spike", False):
        return None

    today = state.get("ticket_volume_today", 0)
    avg = state.get("ticket_volume_avg", 0)
    ratio = today / avg if avg > 0 else 0

    _escalate_if_needed(
        db, session_id, company_id, "ticket_volume_spike",
        "warning", "ticket_volume_spike",
    )

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="ticket_volume_spike",
        severity="warning",
        category="ticket_volume",
        title="Ticket Volume Spike Detected",
        message=f"Today's ticket volume ({today}) is {ratio:.1f}x the 7-day average ({avg:.0f}).",
        details_json=json.dumps({
            "ticket_volume_today": today,
            "ticket_volume_avg": avg,
            "spike_ratio": round(ratio, 2),
            "spike_multiplier_threshold": spike_multiplier,
        }),
        action_required=True,
        action_url="/dashboard/tickets?filter=today",
        related_snapshot_id=snapshot_id,
        dedup_key="ticket_volume_spike",
    )


def _check_agent_pool(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    snapshot_id: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> Optional[List[JarvisProactiveAlert]]:
    """Rule 3: Agent Pool Utilization.

    Alerts when utilization exceeds warning (80%) or critical (95%) thresholds.
    Also creates a separate critical alert when active_agents == 0 AND
    agent_pool_capacity > 0 (no agents running at all).
    Returns a list of alerts.
    """
    overrides = overrides or {}
    util_warn = overrides.get("utilization_warn", UTILIZATION_WARN_THRESHOLD)
    util_critical = overrides.get("utilization_critical", UTILIZATION_CRITICAL_THRESHOLD)

    utilization = state.get("agent_pool_utilization", 0)
    active = state.get("active_agents", 0)
    capacity = state.get("agent_pool_capacity", 0)
    created_alerts: List[JarvisProactiveAlert] = []

    # Agent Pool Zero Alert: no agents running at all
    if active == 0 and capacity > 0:
        _escalate_if_needed(
            db, session_id, company_id, "agent_pool_zero",
            "critical", "agent_pool_zero",
        )
        zero_alert = create_alert(
            db=db,
            session_id=session_id,
            company_id=company_id,
            alert_type="agent_pool_zero",
            severity="critical",
            category="agent_pool",
            title="Agent Pool: Zero Active Agents",
            message=(
                f"No agents are running despite a capacity of {capacity}. "
                "The system cannot process any tickets. Immediate action required."
            ),
            details_json=json.dumps({
                "active_agents": active,
                "capacity": capacity,
                "utilization": utilization,
            }),
            action_required=True,
            action_url="/dashboard/settings?tab=plan",
            related_snapshot_id=snapshot_id,
            dedup_key="agent_pool_zero",
        )
        if zero_alert:
            created_alerts.append(zero_alert)

    if utilization is None:
        return created_alerts if created_alerts else None

    try:
        util_float = float(utilization)
    except (ValueError, TypeError):
        return created_alerts if created_alerts else None

    if util_float < util_warn:
        return created_alerts if created_alerts else None

    severity = "critical" if util_float >= util_critical else "warning"

    _escalate_if_needed(
        db, session_id, company_id, "agent_pool_utilization_high",
        severity, "agent_pool_utilization",
    )

    util_alert = create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="agent_pool_utilization_high",
        severity=severity,
        category="agent_pool",
        title=f"Agent Pool Utilization: {util_float:.0f}%",
        message=(
            f"Agent pool is at {util_float:.0f}% utilization "
            f"({active}/{capacity} agents active). "
            + ("Consider upgrading your plan for more capacity." if severity == "critical"
               else "Monitor for potential capacity issues.")
        ),
        details_json=json.dumps({
            "utilization": util_float,
            "active_agents": active,
            "capacity": capacity,
            "warn_threshold": util_warn,
            "critical_threshold": util_critical,
        }),
        action_required=severity == "critical",
        action_url="/dashboard/settings?tab=plan",
        related_snapshot_id=snapshot_id,
        dedup_key="agent_pool_utilization",
    )
    if util_alert:
        created_alerts.append(util_alert)

    return created_alerts if created_alerts else None


def _check_quality(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    delta: Dict[str, Any],
    snapshot_id: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> Optional[JarvisProactiveAlert]:
    """Rule 4: Quality Score Drop.

    Alerts when quality score drops below warning (0.70) or critical (0.50).
    """
    overrides = overrides or {}
    quality_warn = overrides.get("quality_warn", QUALITY_WARN_THRESHOLD)
    quality_critical = overrides.get("quality_critical", QUALITY_CRITICAL_THRESHOLD)

    quality = state.get("quality_score")
    if quality is None:
        return None

    try:
        q_float = float(quality)
    except (ValueError, TypeError):
        return None

    if q_float >= quality_warn:
        return None

    severity = "critical" if q_float < quality_critical else "warning"

    # Check if this is a new drop (delta detection)
    quality_drops = [a for a in delta.get("new_alerts", []) if a.get("field") == "quality_score"]
    is_new_drop = len(quality_drops) > 0

    message = f"Response quality score has dropped to {q_float:.2f}"
    if is_new_drop:
        message += " (new drop detected)"
    message += ". This may affect customer satisfaction."

    _escalate_if_needed(
        db, session_id, company_id, "quality_drop",
        severity, "quality_score_drop",
    )

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="quality_drop",
        severity=severity,
        category="quality",
        title=f"Quality Score: {q_float:.2f}",
        message=message,
        details_json=json.dumps({
            "quality_score": q_float,
            "warn_threshold": quality_warn,
            "critical_threshold": quality_critical,
            "is_new_drop": is_new_drop,
        }),
        action_required=severity == "critical",
        action_url="/dashboard/quality",
        related_snapshot_id=snapshot_id,
        dedup_key="quality_score_drop",
    )


def _check_drift(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    delta: Dict[str, Any],
    snapshot_id: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> Optional[JarvisProactiveAlert]:
    """Rule 5: Model Drift.

    Alerts when drift score exceeds warning (0.30) or critical (0.60).
    """
    overrides = overrides or {}
    drift_warn = overrides.get("drift_warn", DRIFT_WARN_THRESHOLD)
    drift_critical = overrides.get("drift_critical", DRIFT_CRITICAL_THRESHOLD)

    drift_score = state.get("drift_score")
    drift_status = state.get("drift_status", "none")

    if drift_score is None:
        return None

    try:
        d_float = float(drift_score)
    except (ValueError, TypeError):
        return None

    if d_float < drift_warn:
        return None

    severity = "critical" if d_float >= drift_critical else "warning"

    _escalate_if_needed(
        db, session_id, company_id, "drift_detected",
        severity, "drift_detected",
    )

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="drift_detected",
        severity=severity,
        category="drift",
        title=f"Model Drift: {drift_status.title()} ({d_float:.2f})",
        message=(
            f"Model drift has been detected (score: {d_float:.2f}, status: {drift_status}). "
            "Consider triggering Agent Lightning training to correct the drift."
        ),
        details_json=json.dumps({
            "drift_score": d_float,
            "drift_status": drift_status,
            "warn_threshold": drift_warn,
            "critical_threshold": drift_critical,
        }),
        action_required=severity == "critical",
        action_url="/dashboard/training",
        related_snapshot_id=snapshot_id,
        dedup_key="drift_detected",
    )


def _check_plan_usage(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    snapshot_id: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> Optional[JarvisProactiveAlert]:
    """Rule 6: Plan Usage.

    Alerts when plan usage exceeds warning (80%) or critical (95%).
    """
    overrides = overrides or {}
    plan_warn = overrides.get("plan_usage_warn", PLAN_USAGE_WARN_THRESHOLD)
    plan_critical = overrides.get("plan_usage_critical", PLAN_USAGE_CRITICAL_THRESHOLD)

    usage = state.get("plan_usage_today")
    if usage is None:
        return None

    try:
        u_float = float(usage)
    except (ValueError, TypeError):
        return None

    if u_float < plan_warn:
        return None

    severity = "critical" if u_float >= plan_critical else "warning"
    plan = state.get("current_plan", "unknown")

    _escalate_if_needed(
        db, session_id, company_id, "plan_usage_high",
        severity, "plan_usage_high",
    )

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="plan_usage_high",
        severity=severity,
        category="billing",
        title=f"Plan Usage: {u_float:.0f}%",
        message=(
            f"Your {plan} plan usage is at {u_float:.0f}% today. "
            + ("You may hit your daily limit soon." if severity == "warning"
               else "You are about to hit your daily limit. Consider upgrading.")
        ),
        details_json=json.dumps({
            "plan_usage_today": u_float,
            "current_plan": plan,
            "warn_threshold": plan_warn,
            "critical_threshold": plan_critical,
        }),
        action_required=severity == "critical",
        action_url="/dashboard/billing",
        related_snapshot_id=snapshot_id,
        dedup_key="plan_usage_high",
    )


def _check_subscription(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    delta: Dict[str, Any],
    snapshot_id: str,
) -> Optional[JarvisProactiveAlert]:
    """Rule 7: Subscription Status.

    Alerts when subscription status changes to past_due or cancelled.
    """
    sub_status = state.get("subscription_status", "active")
    if sub_status == "active" or sub_status == "trial":
        return None

    # Only alert on delta (status change) to avoid spam
    sub_changes = [a for a in delta.get("new_alerts", []) if a.get("field") == "subscription_status"]
    if not sub_changes and delta.get("is_first_tick") is not True:
        # If not first tick and no delta change, don't re-alert
        return None

    severity = "critical" if sub_status == "past_due" else "warning"

    _escalate_if_needed(
        db, session_id, company_id, "subscription_status_change",
        severity, f"subscription_{sub_status}",
    )

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="subscription_status_change",
        severity=severity,
        category="billing",
        title=f"Subscription: {sub_status.title()}",
        message=f"Your subscription status has changed to '{sub_status}'. Please update your payment method.",
        details_json=json.dumps({
            "subscription_status": sub_status,
            "plan": state.get("current_plan", "unknown"),
        }),
        action_required=True,
        action_url="/dashboard/billing",
        related_snapshot_id=snapshot_id,
        dedup_key=f"subscription_{sub_status}",
    )


def _check_renewal(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    snapshot_id: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> Optional[JarvisProactiveAlert]:
    """Rule 8: Renewal Warning.

    Alerts when renewal is approaching (7 days = info, 3 days = warning).
    """
    overrides = overrides or {}
    renewal_info = overrides.get("renewal_info", RENEWAL_INFO_THRESHOLD)
    renewal_warn = overrides.get("renewal_warn", RENEWAL_WARN_THRESHOLD)

    days = state.get("days_until_renewal")
    if days is None:
        return None

    try:
        days_int = int(days)
    except (ValueError, TypeError):
        return None

    if days_int > renewal_info:
        return None

    if days_int <= renewal_warn:
        severity = "warning"
    else:
        severity = "info"

    plan = state.get("current_plan", "unknown")

    _escalate_if_needed(
        db, session_id, company_id, "renewal_approaching",
        severity, "renewal_approaching",
    )

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="renewal_approaching",
        severity=severity,
        category="billing",
        title=f"Renewal in {days_int} Days",
        message=f"Your {plan} plan renews in {days_int} days. Please ensure your payment method is up to date.",
        details_json=json.dumps({
            "days_until_renewal": days_int,
            "current_plan": plan,
        }),
        action_required=days_int <= renewal_warn,
        action_url="/dashboard/billing",
        related_snapshot_id=snapshot_id,
        dedup_key="renewal_approaching",
    )


def _check_error_rate(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    snapshot_id: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> Optional[JarvisProactiveAlert]:
    """Rule 9: Error Rate.

    Alerts when there are 3+ recent errors.
    Also tracks error rate as a percentage using ticket volume data:
      - 10% error rate = warning
      - 25% error rate = critical
    """
    overrides = overrides or {}
    error_rate_warn = overrides.get("error_rate_warn", ERROR_RATE_WARN_THRESHOLD)
    error_rate_critical = overrides.get("error_rate_critical", ERROR_RATE_CRITICAL_THRESHOLD)

    errors = state.get("last_5_errors", [])
    if not isinstance(errors, list) or len(errors) < 3:
        return None

    # Determine severity based on error count (existing logic)
    severity = "critical" if len(errors) >= 5 else "warning"

    # Also compute error rate as percentage if ticket volume is available
    ticket_volume_today = state.get("ticket_volume_today", 0)
    error_rate = None
    if ticket_volume_today and ticket_volume_today > 0:
        error_rate = len(errors) / max(ticket_volume_today, 1)
        # Escalate severity if error rate is very high
        if error_rate >= error_rate_critical:
            severity = "critical"
        elif error_rate >= error_rate_warn and severity != "critical":
            severity = "warning"

    error_summaries = [e.get("error", "Unknown")[:50] for e in errors]

    details = {
        "error_count": len(errors),
        "error_summaries": error_summaries,
    }
    if error_rate is not None:
        details["error_rate"] = round(error_rate, 4)
        details["error_rate_warn_threshold"] = error_rate_warn
        details["error_rate_critical_threshold"] = error_rate_critical
        details["ticket_volume_today"] = ticket_volume_today

    _escalate_if_needed(
        db, session_id, company_id, "error_rate_high",
        severity, "error_rate_high",
    )

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="error_rate_high",
        severity=severity,
        category="system_health",
        title=f"{len(errors)} Recent Errors Detected",
        message=(
            f"{len(errors)} errors have been detected in the last hour. "
            + (f"Error rate: {error_rate:.1%}." if error_rate is not None else "")
            + "This may indicate a system issue that needs attention."
        ),
        details_json=json.dumps(details),
        action_required=severity == "critical",
        action_url="/dashboard/logs",
        related_snapshot_id=snapshot_id,
        dedup_key="error_rate_high",
    )


def _check_compound_spike_quality(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    snapshot_id: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> Optional[JarvisProactiveAlert]:
    """Rule 10: Compound Spike + Quality Drop.

    If BOTH ticket_volume_spike=True AND quality_score < quality_warn_threshold,
    create a CRITICAL alert. This catches the scenario where volume spike
    is causing quality degradation.
    """
    overrides = overrides or {}
    quality_warn = overrides.get("quality_warn", QUALITY_WARN_THRESHOLD)

    # Both conditions must be true
    if not state.get("ticket_volume_spike", False):
        return None

    quality = state.get("quality_score")
    if quality is None:
        return None

    try:
        q_float = float(quality)
    except (ValueError, TypeError):
        return None

    if q_float >= quality_warn:
        return None

    today = state.get("ticket_volume_today", 0)
    avg = state.get("ticket_volume_avg", 0)
    ratio = today / avg if avg > 0 else 0

    _escalate_if_needed(
        db, session_id, company_id, "compound_spike_quality_drop",
        "critical", "compound_spike_quality_drop",
    )

    return create_alert(
        db=db,
        session_id=session_id,
        company_id=company_id,
        alert_type="compound_spike_quality_drop",
        severity="critical",
        category="quality",
        title="Spike + Quality Drop: Critical",
        message=(
            f"Ticket volume spike ({ratio:.1f}x avg) is coinciding with quality "
            f"degradation (score: {q_float:.2f}). High volume is likely causing "
            "response quality to suffer. Consider adding more agents or "
            "temporarily adjusting automation rules."
        ),
        details_json=json.dumps({
            "ticket_volume_today": today,
            "ticket_volume_avg": avg,
            "spike_ratio": round(ratio, 2),
            "quality_score": q_float,
            "quality_warn_threshold": quality_warn,
        }),
        action_required=True,
        action_url="/dashboard/quality",
        related_snapshot_id=snapshot_id,
        dedup_key="compound_spike_quality_drop",
    )


def _check_training_status(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    delta: Dict[str, Any],
    snapshot_id: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> Optional[List[JarvisProactiveAlert]]:
    """Rule 11: Training Status.

    Alerts on:
      - Training just completed (training_running=False AND previous state had
        training_running=True via delta) → info alert
      - High mistake count (training_mistake_count >= 10) → warning alert
    Returns a list of alerts.
    """
    overrides = overrides or {}
    mistake_warn = overrides.get("training_mistake_warn", TRAINING_MISTAKE_WARN_THRESHOLD)

    created_alerts: List[JarvisProactiveAlert] = []

    # Training just completed: current=False, previous=True (via delta)
    training_running = state.get("training_running", False)
    if not training_running:
        # Check delta for training_running change from True to False
        changed_fields = delta.get("changed_fields", {})
        training_change = changed_fields.get("training_running")
        if training_change and training_change.get("from") is True and training_change.get("to") is False:
            _escalate_if_needed(
                db, session_id, company_id, "training_completed",
                "info", "training_completed",
            )
            completed_alert = create_alert(
                db=db,
                session_id=session_id,
                company_id=company_id,
                alert_type="training_completed",
                severity="info",
                category="training",
                title="Agent Lightning Training Completed",
                message=(
                    "Agent Lightning training has finished. "
                    "Review the new model version and quality metrics."
                ),
                details_json=json.dumps({
                    "training_running": False,
                    "model_version": state.get("training_model_version", ""),
                }),
                action_required=False,
                action_url="/dashboard/training",
                related_snapshot_id=snapshot_id,
                dedup_key="training_completed",
            )
            if completed_alert:
                created_alerts.append(completed_alert)

    # High mistake count
    mistake_count = state.get("training_mistake_count", 0)
    try:
        m_count = int(mistake_count)
    except (ValueError, TypeError):
        m_count = 0

    if m_count >= mistake_warn:
        _escalate_if_needed(
            db, session_id, company_id, "training_mistakes_high",
            "warning", "training_mistakes_high",
        )
        mistake_alert = create_alert(
            db=db,
            session_id=session_id,
            company_id=company_id,
            alert_type="training_mistakes_high",
            severity="warning",
            category="training",
            title=f"Training Mistakes: {m_count}",
            message=(
                f"Agent Lightning training has recorded {m_count} mistakes. "
                "This may indicate the training data needs review or the "
                "model configuration needs adjustment."
            ),
            details_json=json.dumps({
                "training_mistake_count": m_count,
                "training_running": training_running,
                "model_version": state.get("training_model_version", ""),
                "mistake_warn_threshold": mistake_warn,
            }),
            action_required=True,
            action_url="/dashboard/training",
            related_snapshot_id=snapshot_id,
            dedup_key="training_mistakes_high",
        )
        if mistake_alert:
            created_alerts.append(mistake_alert)

    return created_alerts if created_alerts else None


# ══════════════════════════════════════════════════════════════════
# RULE 12: ACTIVITY STORE CRITICAL EVENTS
# ══════════════════════════════════════════════════════════════════


def _check_activity_store_critical(
    db: Session,
    session_id: str,
    company_id: str,
    state: Dict[str, Any],
    snapshot_id: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> Optional[List[JarvisProactiveAlert]]:
    """Rule 12: Activity Store Critical Events.

    Checks the Activity Store for critical/emergency events that
    need Jarvis's attention. These are non-agentic events like
    payment failures, channel outages, security issues, etc.

    For AGENTIC events (handled by variant agents), this rule
    creates info-level alerts since the agents will handle them.
    For NON-AGENTIC events (notify_only, human_required), this
    rule creates warning/critical alerts since Jarvis or a human
    needs to act.

    Returns a list of alerts.
    """
    created_alerts: List[JarvisProactiveAlert] = []

    try:
        critical_count = state.get("critical_activity_count", 0)

        if critical_count == 0:
            return None

        # Get the actual critical events
        activity_summary = state.get("activity_summary", {})
        critical_events = activity_summary.get("critical_events", [])

        if not critical_events:
            return None

        # Create alert for critical activity events
        # Group by control boundary for smarter alerting
        control_summary = state.get("control_boundary_summary", {})
        human_required = control_summary.get("human_required", 0)
        jarvis_can_act = control_summary.get("jarvis_can_act", 0)

        # Build alert message
        event_descriptions = []
        for evt in critical_events[:5]:
            action = evt.get("action", "unknown")
            source = evt.get("event_source", "unknown")
            category = evt.get("event_category", "unknown")
            event_descriptions.append(f"{source}/{category}: {action}")

        message = (
            f"{critical_count} critical activity event(s) detected in the last 24 hours. "
            f"Key events: {'; '.join(event_descriptions[:3])}. "
        )

        if human_required > 0:
            message += f"{human_required} event(s) require human attention. "
        if jarvis_can_act > 0:
            message += f"{jarvis_can_act} event(s) can be handled by Jarvis. "

        # Determine severity based on control boundary
        if human_required > 0:
            severity = "critical"
        elif jarvis_can_act > 0:
            severity = "warning"
        else:
            severity = "warning"

        alert = create_alert(
            db=db,
            session_id=session_id,
            company_id=company_id,
            alert_type="activity_store_critical",
            severity=severity,
            category="system_health",
            title="Critical Activity Events Detected",
            message=message,
            details_json=json.dumps({
                "critical_count": critical_count,
                "human_required": human_required,
                "jarvis_can_act": jarvis_can_act,
                "notify_only": control_summary.get("notify_only", 0),
                "agent_controlled": control_summary.get("agent_controlled", 0),
                "top_events": critical_events[:5],
            }),
            action_required=human_required > 0,
            action_url="/dashboard/activity",
            related_snapshot_id=snapshot_id,
            dedup_key="activity_store_critical",
        )
        if alert:
            created_alerts.append(alert)

    except Exception:
        logger.debug(
            "activity_store_rule_failed: company=%s, session=%s",
            company_id, session_id,
        )

    return created_alerts if created_alerts else None


# ══════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ══════════════════════════════════════════════════════════════════


# Severity ordering for escalation comparisons
_SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2, "emergency": 3}


def _is_in_cooldown(
    db: Session,
    session_id: str,
    company_id: str,
    dedup_key: str,
) -> bool:
    """Check if an alert with the same dedup_key was created within the cooldown window.

    Queries for active or acknowledged alerts with the same _dedup_key
    in details_json that were created within RULE_COOLDOWN_SECONDS.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        dedup_key: Deduplication key to check.

    Returns:
        True if in cooldown (should skip), False otherwise.
    """
    try:
        cooldown_cutoff = datetime.now(timezone.utc) - timedelta(seconds=RULE_COOLDOWN_SECONDS)
        recent_alerts = (
            db.query(JarvisProactiveAlert)
            .filter(
                JarvisProactiveAlert.session_id == session_id,
                JarvisProactiveAlert.company_id == company_id,
                JarvisProactiveAlert.status.in_(["active", "acknowledged"]),
                JarvisProactiveAlert.created_at >= cooldown_cutoff,
            )
            .all()
        )
        for alert in recent_alerts:
            try:
                details = _safe_parse_json(alert.details_json)
                if details.get("_dedup_key") == dedup_key:
                    return True
            except Exception:
                continue
        return False
    except Exception:
        logger.exception("cooldown_check_failed: session=%s, key=%s", session_id, dedup_key)
        return False  # BC-008: on failure, don't block alert creation


def _escalate_if_needed(
    db: Session,
    session_id: str,
    company_id: str,
    alert_type: str,
    new_severity: str,
    dedup_key: str,
) -> None:
    """Resolve acknowledged alerts with the same dedup_key but lower severity.

    If an acknowledged alert exists for the same dedup_key with a lower
    severity than the new alert, resolve the old one so the new
    higher-severity alert can be created.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        alert_type: Alert type of the new alert.
        new_severity: Severity of the new alert being created.
        dedup_key: Deduplication key to match.
    """
    try:
        new_sev_level = _SEVERITY_ORDER.get(new_severity, 0)
        acknowledged_alerts = (
            db.query(JarvisProactiveAlert)
            .filter(
                JarvisProactiveAlert.session_id == session_id,
                JarvisProactiveAlert.company_id == company_id,
                JarvisProactiveAlert.alert_type == alert_type,
                JarvisProactiveAlert.status == "acknowledged",
            )
            .all()
        )
        for alert in acknowledged_alerts:
            try:
                details = _safe_parse_json(alert.details_json)
                if details.get("_dedup_key") == dedup_key:
                    old_sev_level = _SEVERITY_ORDER.get(alert.severity, 0)
                    if new_sev_level > old_sev_level:
                        alert.status = "resolved"
                        alert.resolved_at = datetime.now(timezone.utc)
                        alert.updated_at = datetime.now(timezone.utc)
                        logger.info(
                            "alert_escalated: resolved old id=%s severity=%s "
                            "in favor of new severity=%s, key=%s",
                            alert.id, alert.severity, new_severity, dedup_key,
                        )
            except Exception:
                continue
        db.flush()
    except Exception:
        logger.exception("escalation_check_failed: session=%s, key=%s", session_id, dedup_key)


def _get_threshold_overrides(session_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Read threshold overrides from session context JSON.

    The context may contain a key "awareness_threshold_overrides" with
    values like {"quality_warn": 0.80, "quality_critical": 0.60}.

    Args:
        session_context: Parsed session context dict.

    Returns:
        Dict of threshold override key-value pairs (empty if none).
    """
    if not session_context or not isinstance(session_context, dict):
        return {}
    try:
        overrides = session_context.get("awareness_threshold_overrides", {})
        if isinstance(overrides, dict):
            return overrides
        return {}
    except Exception:
        return {}


def get_effective_thresholds(
    company_id: str,
    session_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return the merged thresholds (defaults + overrides) for a company.

    Useful for the API to show current threshold configuration.
    BC-001: company_id is first parameter.
    BC-008: Wrapped in try/except — never crashes.

    Args:
        company_id: Company ID for BC-001.
        session_context: Optional parsed session context dict with overrides.

    Returns:
        Dict with all threshold names and their effective values.
    """
    try:
        overrides = _get_threshold_overrides(session_context)
        defaults = {
            "spike_multiplier": SPIKE_MULTIPLIER,
            "utilization_warn": UTILIZATION_WARN_THRESHOLD,
            "utilization_critical": UTILIZATION_CRITICAL_THRESHOLD,
            "quality_warn": QUALITY_WARN_THRESHOLD,
            "quality_critical": QUALITY_CRITICAL_THRESHOLD,
            "drift_warn": DRIFT_WARN_THRESHOLD,
            "drift_critical": DRIFT_CRITICAL_THRESHOLD,
            "plan_usage_warn": PLAN_USAGE_WARN_THRESHOLD,
            "plan_usage_critical": PLAN_USAGE_CRITICAL_THRESHOLD,
            "renewal_info": RENEWAL_INFO_THRESHOLD,
            "renewal_warn": RENEWAL_WARN_THRESHOLD,
            "error_rate_warn": ERROR_RATE_WARN_THRESHOLD,
            "error_rate_critical": ERROR_RATE_CRITICAL_THRESHOLD,
            "training_mistake_warn": TRAINING_MISTAKE_WARN_THRESHOLD,
            "rule_cooldown_seconds": RULE_COOLDOWN_SECONDS,
        }
        # Merge overrides on top of defaults
        effective = dict(defaults)
        for key, value in overrides.items():
            if key in effective:
                effective[key] = value
        return effective
    except Exception:
        logger.exception("get_effective_thresholds_failed: company=%s", company_id)
        return {
            "spike_multiplier": SPIKE_MULTIPLIER,
            "utilization_warn": UTILIZATION_WARN_THRESHOLD,
            "utilization_critical": UTILIZATION_CRITICAL_THRESHOLD,
            "quality_warn": QUALITY_WARN_THRESHOLD,
            "quality_critical": QUALITY_CRITICAL_THRESHOLD,
            "drift_warn": DRIFT_WARN_THRESHOLD,
            "drift_critical": DRIFT_CRITICAL_THRESHOLD,
            "plan_usage_warn": PLAN_USAGE_WARN_THRESHOLD,
            "plan_usage_critical": PLAN_USAGE_CRITICAL_THRESHOLD,
            "renewal_info": RENEWAL_INFO_THRESHOLD,
            "renewal_warn": RENEWAL_WARN_THRESHOLD,
            "error_rate_warn": ERROR_RATE_WARN_THRESHOLD,
            "error_rate_critical": ERROR_RATE_CRITICAL_THRESHOLD,
            "training_mistake_warn": TRAINING_MISTAKE_WARN_THRESHOLD,
            "rule_cooldown_seconds": RULE_COOLDOWN_SECONDS,
        }


def _safe_parse_json(raw: Optional[str]) -> Dict[str, Any]:
    """Safely parse JSON string, returning empty dict on failure."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _collect_shadow_mode(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 9: Shadow Mode awareness.

    Jarvis MUST know the shadow mode state because it directly
    affects which variant handles customer messages. If shadow mode
    is active, some messages go to the shadow variant for A/B testing.
    Jarvis needs to know this to understand why responses might differ.

    Returns:
        Dict with shadow_mode_active, shadow_mode_phase,
        live_variant, shadow_variant, shadow_win_rate, etc.
    """
    result: Dict[str, Any] = {
        "shadow_mode_active": False,
        "shadow_mode_phase": "off",
        "shadow_mode_live_variant": None,
        "shadow_mode_shadow_variant": None,
        "shadow_mode_win_rate": None,
        "shadow_mode_total_comparisons": 0,
        "shadow_mode_quality_streak": 0,
    }

    try:
        from app.services.shadow_mode_service import get_shadow_mode_service
        service = get_shadow_mode_service()
        status = service.get_status(company_id=company_id)

        if hasattr(status, 'to_dict'):
            status_dict = status.to_dict()
        elif isinstance(status, dict):
            status_dict = status
        else:
            return result

        active = status_dict.get("active", False)
        result["shadow_mode_active"] = active
        result["shadow_mode_phase"] = status_dict.get("status", "off") if active else "off"
        result["shadow_mode_live_variant"] = status_dict.get("live_variant")
        result["shadow_mode_shadow_variant"] = status_dict.get("shadow_variant")
        result["shadow_mode_win_rate"] = status_dict.get("shadow_win_rate")
        result["shadow_mode_total_comparisons"] = status_dict.get("total_comparisons", 0)
        result["shadow_mode_quality_streak"] = status_dict.get("quality_streak", 0)
        result["shadow_mode_sample_rate"] = status_dict.get("sample_rate")
        result["shadow_mode_auto_graduation_window"] = status_dict.get("auto_graduation_window")

        # Also check for recent shadow mode activity events in the Activity Store
        try:
            from app.services.jarvis_activity_store import query_events
            shadow_events, _ = query_events(
                db=db,
                company_id=company_id,
                event_category="shadow_mode",
                page_size=5,
            )
            result["shadow_mode_recent_events"] = shadow_events
        except Exception:
            result["shadow_mode_recent_events"] = []

    except Exception:
        # Shadow mode service may not be available — BC-008
        logger.debug(
            "shadow_mode_collection_failed: company=%s", company_id,
        )

    return result


def _collect_dashboard_awareness(
    db: Session,
    company_id: str,
    session_id: str,
) -> Dict[str, Any]:
    """Domain 10: Dashboard & Ticket Actions awareness.

    Jarvis MUST know what the user is doing in the dashboard. This
    enables context-aware conversations. If a user is on the billing
    page and says "I need help", Jarvis should know they're looking
    at billing. If they just resolved 5 tickets, Jarvis should
    acknowledge their productivity.

    This reads dashboard and ticket action events from the Activity
    Store, giving Jarvis a real-time picture of user activity.

    Returns:
        Dict with recent_dashboard_events, recent_ticket_actions,
        user_current_page, active_ticket_count, etc.
    """
    result: Dict[str, Any] = {
        "recent_dashboard_events": [],
        "recent_ticket_actions": [],
        "user_current_page": None,
        "recent_ticket_action_count": 0,
    }

    try:
        from app.services.jarvis_activity_store import query_events

        # Get recent dashboard events (page views, button clicks)
        dashboard_events, dashboard_count = query_events(
            db=db,
            company_id=company_id,
            event_category="dashboard",
            page_size=10,
        )
        result["recent_dashboard_events"] = dashboard_events
        result["recent_dashboard_action_count"] = dashboard_count

        # Extract current page from most recent dashboard event
        if dashboard_events:
            latest = dashboard_events[0]
            ctx = latest.get("context", {})
            if isinstance(ctx, dict):
                result["user_current_page"] = ctx.get("page")

        # Get recent ticket actions (create, update, resolve, escalate)
        ticket_events, ticket_count = query_events(
            db=db,
            company_id=company_id,
            event_category="dashboard",
            action="ticket_",
            page_size=10,
        )
        result["recent_ticket_actions"] = ticket_events
        result["recent_ticket_action_count"] = ticket_count

    except Exception:
        # Dashboard awareness is non-critical — BC-008
        logger.debug(
            "dashboard_awareness_collection_failed: company=%s, session=%s",
            company_id, session_id,
        )

    return result


# ══════════════════════════════════════════════════════════════════
# DOMAIN 11: ONBOARDING FUNNEL AWARENESS
# ══════════════════════════════════════════════════════════════════


def _collect_onboarding_awareness(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Domain 11: Onboarding Funnel awareness.

    Jarvis MUST know about the onboarding pipeline. This gives Jarvis
    full awareness of the pre-purchase funnel:
      - How many active onboarding sessions are running
      - What stage users are at
      - Email verification rates
      - Payment conversion rates
      - Where users drop off
      - Onboarding flags (low conversion, etc.)

    This data comes from the Activity Store (Domain 8 already logs
    onboarding actions via jarvis_onboarding_service.log_onboarding_action).
    This collector reads those events and provides a structured summary
    for the awareness engine.

    Why this matters:
      If a user just completed onboarding and enters the CC dashboard,
      CC Jarvis can see:
        - onboarding_active_sessions: 3 (other prospects in pipeline)
        - onboarding_payment_rate: 45% (healthy conversion)
        - onboarding_flags: ["low_verification_rate"] (action needed)

      This enables CC Jarvis to say things like:
        "I see your verification rate is a bit low — want me to
         optimize the OTP flow?"

    Returns:
        Dict with onboarding funnel awareness data.
    """
    result: Dict[str, Any] = {
        "onboarding_active_sessions": 0,
        "onboarding_stage_distribution": {},
        "onboarding_verification_rate": 0.0,
        "onboarding_payment_rate": 0.0,
        "onboarding_handoff_rate": 0.0,
        "onboarding_top_entry_sources": [],
        "onboarding_flags": [],
    }

    try:
        from app.services.jarvis_onboarding_service import get_onboarding_awareness

        # Delegate to the onboarding service's awareness function
        # which reads from the Activity Store
        onboarding_data = get_onboarding_awareness(
            db=db,
            company_id=company_id,
            hours=1,
        )

        result.update(onboarding_data)

        logger.debug(
            "domain11_onboarding_awareness: company=%s, active=%d, "
            "verification_rate=%s, payment_rate=%s, flags=%d",
            company_id,
            result.get("onboarding_active_sessions", 0),
            result.get("onboarding_verification_rate", "N/A"),
            result.get("onboarding_payment_rate", "N/A"),
            len(result.get("onboarding_flags", [])),
        )

    except Exception:
        # Onboarding awareness is non-critical — BC-008
        logger.debug(
            "onboarding_awareness_collection_failed: company=%s",
            company_id,
        )

    return result
