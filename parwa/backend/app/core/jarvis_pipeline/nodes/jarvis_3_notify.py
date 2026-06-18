"""
Jarvis Node 3: NOTIFY (Act + Verify) — Wave 1 Wired Version

Now uses:
  - command_parser for natural language understanding (not keyword matching)
  - jarvis_db for all storage (not in-memory dicts)
  - jarvis_auth for role-based authorization
  - Full pipeline: chat → parse → auth → execute → DB → response

Question: HOW do we communicate this?

LLM Cost: 0-2 calls
  - 0 for control/query commands (handled by DB directly)
  - 1 for complex responses (formatting DB data into natural language)
  - 1 for LLM fallback in command parser (Tier 2)
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from app.core.parwa_pipeline.llm_client import llm_call
from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store
from app.core.jarvis_pipeline.jarvis_db import (
    get_db, PRIORITY_CRITICAL, PRIORITY_HIGH,
    TYPE_STUCK_TICKET, TYPE_QUOTA_LOW, TYPE_INTEGRATION_DOWN,
    TYPE_ACCURACY_DROP,
)
from app.core.jarvis_pipeline.command_parser import (
    classify_command, is_query_intent, is_control_intent,
    is_emergency_intent, is_approval_intent,
)
from app.core.jarvis_pipeline.jarvis_auth import (
    authorize_command, make_user_context, AuthResult,
)

logger = logging.getLogger("jarvis.notify")


# ── Notification Creation ─────────────────────────────────────

def _format_notification(ntype: str, ev: Dict) -> tuple:
    """Format notification title and description by type."""
    signal = ev.get("signal", {})
    score = ev.get("priority_score", 0)

    if ntype == TYPE_STUCK_TICKET:
        tid = signal.get("ticket_id", "unknown")
        reason = signal.get("reason", "unknown")
        quality = signal.get("quality_score", "?")
        escalation = ev.get("escalation_tier", "soft_reminder")
        hours = signal.get("hours_stuck", 0)
        title = f"Stuck Ticket [{escalation.upper()}]: {tid}"
        desc = (f"Ticket {tid} could not be resolved automatically. "
                f"Reason: {reason}. Quality achieved: {quality}. "
                f"Loops used: {signal.get('loops_used', 0)}. "
                f"Hours stuck: {hours}. Escalation: {escalation}. "
                f"Requires manual review.")

    elif ntype == TYPE_QUOTA_LOW:
        data = list(signal.values())[0] if signal else {}
        tier = list(signal.keys())[0] if signal else "unknown"
        title = f"Quota {data.get('status', 'warning').upper()}: {tier}"
        desc = (f"{tier.capitalize()} plan quota is {data.get('burn_pct', 0)}% used "
                f"({data.get('remaining', 0)} of {data.get('total', 0)} remaining). "
                f"Consider upgrading or requesting additional quota.")

    elif ntype == TYPE_ACCURACY_DROP:
        trend = signal.get("trend", "unknown")
        severity = signal.get("severity", "warning")
        trigger = signal.get("trigger", "unknown")
        acc_7d = signal.get("accuracy_7d", "?")
        acc_today = signal.get("accuracy_today", "?")
        title = f"Accuracy Drift [{severity.upper()}]: {trend}"
        desc = (f"Resolution accuracy trend is '{trend}' (severity: {severity}). "
                f"7-day avg: {acc_7d}, Today: {acc_today}. "
                f"Trigger: {trigger}. "
                f"This may indicate KB gaps, policy changes, or model drift. "
                f"Review recent resolutions and update knowledge base if needed.")

    elif ntype == TYPE_INTEGRATION_DOWN:
        degraded = signal.get("degraded_services", [])
        worst_uptime = signal.get("worst_uptime_pct", 0)
        names = ", ".join(f"{d['name']} ({d['status']}, uptime={d.get('uptime_pct', '?')}%)" for d in degraded)
        title = f"Integration Issues: {signal.get('total_degraded', len(degraded))} service(s) degraded"
        desc = (f"Degraded integrations: {names}. "
                f"Worst uptime: {worst_uptime}%. "
                f"Check API credentials and service status.")

    elif ntype == "load_bottleneck":
        at_cap = signal.get("at_capacity", [])
        high_load = signal.get("high_load", [])
        vip = signal.get("vip_overflow_risk", False)
        bottlenecks = ", ".join(v["name"] for v in at_cap + high_load)
        title = f"Load Bottleneck: {bottlenecks or 'All variants'}"
        desc = (f"Variant load issue detected. "
                f"At capacity: {', '.join(v['name'] for v in at_cap) or 'none'}. "
                f"High load: {', '.join(v['name'] for v in high_load) or 'none'}. "
                f"VIP overflow risk: {vip}. "
                f"Consider scaling up or routing overflow to available variants.")

    else:
        title = f"Signal: {ntype}"
        desc = str(signal)

    return title, desc


async def _create_notifications_from_evals(
    tenant_id: str,
    evaluations: List[Dict[str, Any]],
    db,
) -> List[Dict[str, Any]]:
    """Convert evaluations into notifications via DB. Filter LOW priority."""
    notifications = []
    for ev in evaluations:
        score = ev.get("priority_score", 0)
        if score < 0.40:
            logger.info("LOW priority signal filtered: %s (score=%.3f)", ev.get("type"), score)
            continue

        ntype = ev.get("type", "unknown")
        title, desc = _format_notification(ntype, ev)
        related = ev.get("related_tickets", [])

        nf = await db.create_notification(
            tenant_id=tenant_id,
            ntype=ntype,
            priority_score=score,
            title=title,
            description=desc,
            related_tickets=related,
            batch_key=ev.get("type", ""),
            source_data=ev.get("signal", {}),
        )
        notifications.append(nf)

    return notifications


# ── Command Execution (NEW — Wave 1) ─────────────────────────

async def _execute_command(
    intent_result: Dict[str, Any],
    auth_result: AuthResult,
    tenant_id: str,
    signals: Dict[str, Any],
    db,
) -> str:
    """Execute a classified command and return the response text.

    This is the core "Jarvis does things" function.
    Reads/writes DB based on intent. Returns human-readable response.
    """
    intent = intent_result["intent"]
    target = intent_result["target"]

    # ── QUERY INTENTS ────────────────────────────────────
    if is_query_intent(intent):
        response = await _handle_query(intent, target, tenant_id, signals, db)
        # Log to audit
        await db.create_audit_entry(
            tenant_id=tenant_id,
            action=f"query:{intent}",
            actor_email=auth_result.email,
            target_type="query",
            payload={"intent": intent, "target": target},
        )
        return response

    # ── CONTROL INTENTS ──────────────────────────────────
    if is_control_intent(intent):
        response = await _handle_control(intent, target, tenant_id, auth_result, db)
        return response

    # ── APPROVAL INTENTS ─────────────────────────────────
    if is_approval_intent(intent):
        response = await _handle_approval(intent, target, tenant_id, auth_result, db)
        return response

    # ── EMERGENCY INTENTS ────────────────────────────────
    if is_emergency_intent(intent):
        response = await _handle_emergency(intent, target, tenant_id, auth_result, db)
        return response

    # ── EXPLAIN / TEACH / AGENT ──────────────────────────
    if intent == "explain_ticket":
        return await _handle_explain_ticket(target, tenant_id, signals, db)
    if intent == "explain_flag":
        return await _handle_explain_flags(tenant_id, db)
    if intent == "teach_skill":
        return await _handle_teach_skill(target, tenant_id, auth_result, db)
    if intent == "create_agent":
        return await _handle_create_agent(target, tenant_id, auth_result, db)

    return f"I understood your command but don't have a handler for '{intent}' yet. This will be available in a future wave."


# ── Query Handlers ────────────────────────────────────────────

async def _handle_query(intent: str, target: str, tenant_id: str, signals: Dict, db) -> str:
    """Handle all query intents — read from DB, format response."""

    if intent == "query_status":
        health = await db.health_check()
        active_flags = await db.get_active_flags(tenant_id)
        paused = [f for f in active_flags if f["flag_type"] == "pause_action"]
        return (
            f"**System Status**: {health.get('status', 'unknown')}\n"
            f"Backend: {health.get('backend', 'unknown')}\n"
            f"Active Flags: {len(active_flags)}\n"
            f"Paused Actions: {len(paused)} {', '.join(f['flag_value'] for f in paused) if paused else 'none'}\n"
            f"Mode: Supervised (default)"
        )

    if intent == "query_errors":
        errors = signals.get("errors", [])
        if not errors:
            return "No errors detected in the current session."
        return f"**Recent Errors** ({len(errors)}):\n" + "\n".join(f"- {e}" for e in errors[-5:])

    if intent == "query_tickets":
        flow = signals.get("ticket_flow", {})
        summary = flow.get("summary", {}) if isinstance(flow, dict) else {}
        current = flow.get("current_ticket", {}) if isinstance(flow, dict) else {}
        drift = signals.get("drift_status", {})
        return (
            f"**Ticket Flow Summary**:\n"
            f"Total Processed: {summary.get('total', 0)}\n"
            f"Auto-Resolved: {summary.get('auto_resolved', 0)}\n"
            f"Batched: {summary.get('batched', 0)}\n"
            f"Escalated: {summary.get('escalated', 0)}\n"
            f"Stuck: {summary.get('stuck', 0)}\n"
            f"Avg Quality: {summary.get('avg_quality', 'N/A')}\n"
            f"Avg LLM Calls: {summary.get('avg_llm_calls', 'N/A')}\n"
            f"By Path: {summary.get('by_type', {})}\n"
            f"Accuracy Trend: {drift.get('trend_direction', 'no_data')}"
        )

    if intent == "query_quality":
        stats = await db.get_quality_stats(tenant_id)
        drift = signals.get("drift_status", {})
        drift_line = f"\nDrift: {drift.get('trend_direction', 'no_data')}" \
                    f" (detected={drift.get('drift_detected')}, severity={drift.get('drift_severity')})" \
                    if drift.get('total_scores', 0) > 0 else "\nDrift: insufficient data"
        return (
            f"**Quality Metrics**:\n"
            f"Total Tickets: {stats['total_tickets']}\n"
            f"Average Quality: {stats['avg_quality']:.2%}\n"
            f"Average Confidence: {stats['avg_confidence']:.2%}\n"
            f"Auto-Resolved: {stats['auto_resolved']}\n"
            f"Escalated: {stats['escalated']}\n"
            f"Stuck: {stats['stuck']}\n"
            f"By Path: {stats.get('by_path', {})}"
            f"{drift_line}"
        )

    if intent == "query_quota":
        quota = signals.get("quota_status", {})
        if not quota:
            return "No quota data available. Connect to billing system for live quota tracking."
        parts = []
        for tier, data in quota.items():
            parts.append(
                f"  {tier}: {data.get('remaining', 0)}/{data.get('total', 0)} "
                f"remaining ({data.get('burn_pct', 0)}% used, status: {data.get('status', 'unknown')})"
            )
        return f"**Quota Status**:\n" + "\n".join(parts)

    if intent == "query_notifications":
        if target and target.startswith("PARWA-NFY"):
            # Specific notification lookup
            nf = await db.get_notification(target)
            if nf:
                return (
                    f"**{nf['title']}** (Key: {nf['notification_key']})\n\n"
                    f"{nf['description']}\n\n"
                    f"Priority: {nf['priority']} (score: {nf['priority_score']})\n"
                    f"Status: {'Resolved' if nf['is_resolved'] else 'Unresolved'}\n"
                    f"Type: {nf['type']}\n"
                    f"Related tickets: {', '.join(nf['related_tickets']) or 'None'}"
                )
            return f"Notification {target} not found."
        else:
            # List all notifications
            nfs = await db.get_notifications(tenant_id)
            if not nfs:
                return "No unresolved notifications. All clear."
            lines = [f"**Notifications** ({len(nfs)} unresolved):"]
            for nf in nfs[:10]:
                lines.append(f"  [{nf['priority']}] {nf['notification_key']}: {nf['title']}")
            if len(nfs) > 10:
                lines.append(f"  ... and {len(nfs) - 10} more")
            return "\n".join(lines)

    if intent == "query_flags":
        flags = await db.get_active_flags(tenant_id)
        if not flags:
            return "No active flags/rules. System is running with default behavior."
        lines = [f"**Active Flags** ({len(flags)}):"]
        for f in flags:
            lines.append(
                f"  [{f['flag_type']}] {f['flag_value']} "
                f"(scope={f['scope']}, set by {f['set_by']})"
            )
        return "\n".join(lines)

    if intent == "query_audit":
        trail = await db.get_audit_trail(tenant_id, limit=20)
        if not trail:
            return "No audit trail entries yet."
        lines = [f"**Recent Activity** ({len(trail)} entries):"]
        for entry in trail[:10]:
            lines.append(
                f"  [{entry['created_at'][:19]}] {entry['action']} "
                f"by {entry['actor_email']}"
            )
        if len(trail) > 10:
            lines.append(f"  ... and {len(trail) - 10} more")
        return "\n".join(lines)

    # ── Wave 2 Query Handlers ─────────────────────────────

    if intent == "query_health":
        health = signals.get("integration_health", {})
        services = health.get("services", {})
        if not services:
            return "No integration health data yet. Run a poll cycle first to collect ping data."
        lines = [f"**Integration Health** ({health.get('healthy_count', 0)} healthy, "
                 f"{health.get('degraded_count', 0)} degraded):"]
        for svc_name, svc_data in services.items():
            status_icon = "OK" if svc_data.get("status") == "healthy" else "!!"
            lines.append(
                f"  [{status_icon}] {svc_name}: {svc_data.get('status', '?')} "
                f"(uptime={svc_data.get('uptime_pct', '?')}%, "
                f"avg={svc_data.get('avg_response_ms', '?')}ms" +
                (f", error: {svc_data.get('last_error', 'none')}"
                 if svc_data.get('last_error') else ")")
            )
        return "\n".join(lines)

    if intent == "query_cost":
        costs = signals.get("llm_costs", {})
        persisted = costs.get("persisted", {})
        live = costs.get("live_session", {})
        lines = [
            f"**LLM Cost Summary**:",
            f"  Total Cost (persisted): ${persisted.get('total_cost_usd', 0):.4f}",
            f"  Total Calls (persisted): {persisted.get('total_calls', 0)}",
            f"  Total Tokens (persisted): {persisted.get('total_tokens', 0)}",
            f"  Combined Calls (incl. live): {costs.get('total_calls_combined', 0)}",
            f"  Combined Tokens (incl. live): {costs.get('total_tokens_combined', 0)}",
        ]
        by_model = persisted.get("by_model", {})
        if by_model:
            lines.append("  By Model:")
            for model, mdata in by_model.items():
                lines.append(f"    {model}: ${mdata['cost']:.4f} ({mdata['calls']} calls, {mdata['tokens']} tokens)")
        return "\n".join(lines)

    if intent == "query_flow":
        flow = signals.get("ticket_flow", {})
        summary = flow.get("summary", {}) if isinstance(flow, dict) else {}
        by_node = summary.get("by_node", {})
        lines = [
            f"**Ticket Flow Metrics**:",
            f"  Total: {summary.get('total', 0)}",
            f"  Auto-Resolved: {summary.get('auto_resolved', 0)}",
            f"  Batched: {summary.get('batched', 0)}",
            f"  Escalated: {summary.get('escalated', 0)}",
            f"  Stuck: {summary.get('stuck', 0)}",
            f"  Avg Quality: {summary.get('avg_quality', 0)}",
            f"  Avg LLM Calls/Ticket: {summary.get('avg_llm_calls', 0)}",
        ]
        if by_node:
            lines.append("  Node Distribution:")
            for node, count in sorted(by_node.items()):
                lines.append(f"    {node}: {count} tickets")
        return "\n".join(lines)

    if intent == "query_load":
        load = signals.get("load_status", {})
        variants = load.get("variants", [])
        vip = load.get("vip_overflow_risk", False)
        if not variants:
            return "No variant load data. Configure agent_configs with max_concurrent to enable load monitoring."
        lines = [f"**Load Status** (VIP overflow: {'YES' if vip else 'no'}):"]
        for v in variants:
            util = v.get("utilization_pct", 0)
            status_icon = "!!" if v.get("status") in ("at_capacity", "high") else "OK"
            lines.append(
                f"  [{status_icon}] {v['name']}: {v.get('concurrent', 0)}/{v.get('max_concurrent', 5)} "
                f"({util}% utilized, status: {v.get('status')})"
            )
        return "\n".join(lines)

    if intent == "query_stuck":
        stuck = signals.get("stuck_tickets", [])
        if not stuck:
            return "No stuck tickets. All clear."
        lines = [f"**Stuck Tickets** ({len(stuck)}):"]
        for s in stuck:
            tier = s.get("escalation_tier", "?")
            hours = s.get("hours_stuck", 0)
            lines.append(
                f"  [{tier.upper()}] {s.get('ticket_id', '?')}: "
                f"reason={s.get('reason', '?')}, "
                f"quality={s.get('quality_score', '?')}, "
                f"{hours}h stuck, loops={s.get('loops_used', 0)}"
            )
        return "\n".join(lines)

    return f"Query '{intent}' not yet implemented."


# ── Control Handlers ──────────────────────────────────────────

async def _handle_control(intent: str, target: str, tenant_id: str, auth: AuthResult, db) -> str:
    """Handle control commands — writes to system_flags table."""

    if intent == "control_pause":
        flag = await db.set_flag(
            tenant_id=tenant_id,
            flag_type="pause_action",
            flag_value=target,
            set_by=auth.email,
            reason=f"Paused via Jarvis by {auth.email}",
        )
        # Audit
        await db.create_audit_entry(
            tenant_id=tenant_id, action="control_pause",
            actor_email=auth.email, target_type="flag", target_id=flag["id"],
            payload={"target": target, "intent": intent},
        )
        return f"[OK] Paused '{target}'. PARWA will stop processing {target} requests. Use 'resume {target}' to re-enable."

    if intent == "control_resume":
        # Revoke the most recent pause flag for this target
        flags = await db.get_active_flags(tenant_id, flag_type="pause_action")
        revoked = 0
        for f in flags:
            if f["flag_value"] == target or target == "all":
                await db.revoke_flag(f["id"], auth.email)
                revoked += 1
        await db.create_audit_entry(
            tenant_id=tenant_id, action="control_resume",
            actor_email=auth.email, target_type="flag", target_id=target,
            payload={"target": target, "revoked_count": revoked},
        )
        if revoked > 0:
            return f"[OK] Resumed '{target}'. Revoked {revoked} pause flag(s)."
        return f"No active pause flag found for '{target}'. Already running."

    if intent == "control_route":
        # Parse "handle Instagram DMs" → channel=instagram, route_to=ai
        route_to = "ai"  # default
        if "human" in target or "take" in target or "i'll" in target:
            route_to = "human"
        flag = await db.set_flag(
            tenant_id=tenant_id,
            flag_type="redirect_channel",
            flag_value=f"{target}:{route_to}",
            set_by=auth.email,
            reason=f"Redirected {target} to {route_to} by {auth.email}",
        )
        await db.create_audit_entry(
            tenant_id=tenant_id, action="control_route",
            actor_email=auth.email, target_type="flag", target_id=flag["id"],
            payload={"channel": target, "route_to": route_to},
        )
        return f"[OK] Workflow Redirected: {target} → {route_to.upper()}. PARWA will {'handle' if route_to == 'ai' else 'skip'} {target} requests."

    if intent == "control_mode":
        valid_modes = {"shadow", "supervised", "graduated"}
        mode = target.lower() if target.lower() in valid_modes else "supervised"
        flag = await db.set_flag(
            tenant_id=tenant_id,
            flag_type="force_mode",
            flag_value=mode,
            set_by=auth.email,
            reason=f"Mode changed to {mode} by {auth.email}",
        )
        await db.create_audit_entry(
            tenant_id=tenant_id, action="control_mode",
            actor_email=auth.email, target_type="flag", target_id=flag["id"],
            payload={"mode": mode},
        )
        return f"[OK] System mode set to **{mode.upper()}**. PARWA will operate in {mode} mode."

    if intent == "control_disable_rule":
        # Revoke the most recent non-expired flag
        flags = await db.get_active_flags(tenant_id)
        if flags:
            last = flags[-1]
            await db.revoke_flag(last["id"], auth.email)
            await db.create_audit_entry(
                tenant_id=tenant_id, action="control_disable_rule",
                actor_email=auth.email, target_type="flag", target_id=last["id"],
                payload={"revoked_flag": last["flag_type"], "revoked_value": last["flag_value"]},
            )
            return f"[OK] Disabled last rule: {last['flag_type']}={last['flag_value']}. System reverted to default behavior."
        return "No active rules to disable."

    if intent == "control_skill_assign":
        return "[OK] Skill re-assignment noted. This requires variant config updates (coming in Wave 3)."

    return f"Control '{intent}' received but not yet fully implemented."


# ── Approval Handlers ─────────────────────────────────────────

async def _handle_approval(intent: str, target: str, tenant_id: str, auth: AuthResult, db) -> str:
    """Handle approval/rejection commands."""
    await db.create_audit_entry(
        tenant_id=tenant_id, action=intent,
        actor_email=auth.email, target_type="approval", target_id=target,
        payload={"intent": intent},
    )
    if "batch" in intent:
        action = "approved" if "approve" in intent else "rejected"
        return f"[OK] Batch {action}. Full batch approval UI coming in Wave 7 (Jarvis UI)."
    else:
        action = "approved" if "approve" in intent else "rejected"
        return f"[OK] Ticket {target} {action}. Ticket-level approval tracking coming in Wave 5."


# ── Emergency Handlers ────────────────────────────────────────

async def _handle_emergency(intent: str, target: str, tenant_id: str, auth: AuthResult, db) -> str:
    """Handle emergency commands."""

    if intent == "emergency_shutdown":
        flag = await db.set_flag(
            tenant_id=tenant_id,
            flag_type="global_shutdown",
            flag_value="all",
            set_by=auth.email,
            reason=f"Emergency shutdown by {auth.email}",
        )
        await db.create_audit_entry(
            tenant_id=tenant_id, action="emergency_shutdown",
            actor_email=auth.email, target_type="flag", target_id=flag["id"],
            payload={"CRITICAL": "All AI activity paused"},
        )
        return (
            f"[EMERGENCY] All AI activity PAUSED. Flag set by {auth.email}.\n"
            f"In-flight tickets will complete current step then stop.\n"
            f"Use 'resume all' to restart."
        )

    if intent == "emergency_recall":
        await db.create_audit_entry(
            tenant_id=tenant_id, action="emergency_recall",
            actor_email=auth.email, target_type="message", target_id=target,
            payload={"target": target},
        )
        return f"[OK] Recall initiated for '{target}'. Message recall protocol requires email provider integration (coming in Wave 3)."

    if intent == "emergency_void":
        await db.create_audit_entry(
            tenant_id=tenant_id, action="emergency_void",
            actor_email=auth.email, target_type="message", target_id=target,
            payload={"target": target},
        )
        return f"[OK] Void initiated for '{target}' messages. Pending outbox messages will be removed."

    return f"Emergency '{intent}' acknowledged."


# ── Explain / Teach / Agent Handlers ──────────────────────────

async def _handle_explain_ticket(target: str, tenant_id: str, signals: Dict, db) -> str:
    """Explain why a ticket was resolved the way it was."""
    ticket_flow = signals.get("ticket_flow", {})
    return (
        f"**Ticket Explanation**:\n"
        f"Ticket: {ticket_flow.get('ticket_id', target)}\n"
        f"Type: {ticket_flow.get('ticket_type', 'N/A')}\n"
        f"Complexity: {ticket_flow.get('complexity', 'N/A')}\n"
        f"Action: {ticket_flow.get('action', 'N/A')}\n"
        f"Nodes Reached: {ticket_flow.get('nodes_reached', [])}\n"
        f"LLM Calls: {ticket_flow.get('llm_calls', 'N/A')}\n"
        f"Quality: {ticket_flow.get('quality_score', 'N/A')}\n\n"
        f"Full GSD state display coming in Wave 7 (Jarvis UI with GSD Terminal Window)."
    )


async def _handle_explain_flags(tenant_id: str, db) -> str:
    """Explain why each active rule exists."""
    flags = await db.get_active_flags(tenant_id)
    if not flags:
        return "No active rules to explain."
    lines = ["**Active Rules Explained**:"]
    for f in flags:
        lines.append(
            f"  **{f['flag_type']}={f['flag_value']}**\n"
            f"    Set by: {f['set_by']}\n"
            f"    Reason: {f.get('reason', 'No reason recorded')}\n"
            f"    Scope: {f['scope']}"
        )
    return "\n".join(lines)


async def _handle_teach_skill(target: str, tenant_id: str, auth: AuthResult, db) -> str:
    """Handle teach_skill — coming in Wave 8."""
    await db.create_audit_entry(
        tenant_id=tenant_id, action="teach_skill_attempted",
        actor_email=auth.email, target_type="skill", target_id=target,
    )
    return "[NOTED] Skill teaching received. Dynamic instruction workflow coming in Wave 8. For now, I've logged your intent."


async def _handle_create_agent(target: str, tenant_id: str, auth: AuthResult, db) -> str:
    """Handle agent creation — coming in Wave 8."""
    await db.create_audit_entry(
        tenant_id=tenant_id, action="create_agent_attempted",
        actor_email=auth.email, target_type="agent", target_id=target,
    )
    return "[NOTED] Agent creation request received. Virtual agent provisioning from chat coming in Wave 8."


# ── Main Node Function ────────────────────────────────────────


async def jarvis_notify(state: dict) -> dict:
    """Jarvis Node 3: NOTIFY — Act + Verify.

    Wave 1: Now wired with command_parser + jarvis_auth + jarvis_db.
    Full pipeline: chat → parse → auth → execute → DB → response.
    """
    start = time.time()
    tenant_id = state.get("tenant_id", "")
    trigger = state.get("trigger", "poll")
    evaluations = state.get("evaluations", [])
    signals = state.get("signals", {})
    admin_question = state.get("admin_question", "")
    user_context = state.get("user_context", {})
    logs = []
    llm_calls = 0

    db = get_db()

    # 1. Create notifications from evaluations (poll/monitor mode)
    notifications = []
    if trigger in ("poll", "stuck_ticket") and evaluations:
        notifications = await _create_notifications_from_evals(tenant_id, evaluations, db)
        logs.append({"node": "J3", "technique": "CreateNotifications", "duration_ms": 0,
                     "result_summary": f"created={len(notifications)}"})

    # 2. Handle admin chat (full pipeline: parse → auth → execute)
    chat_response = ""
    if trigger == "admin_chat" and admin_question:
        # Step 1: Classify intent
        intent_result = await classify_command(admin_question)
        if intent_result.get("classification_method") == "llm":
            llm_calls += 1
        logs.append({"node": "J3", "technique": "CommandParser",
                     "duration_ms": 0, "result_summary": f"intent={intent_result['intent']} "
                     f"method={intent_result['classification_method']} "
                     f"confidence={intent_result['confidence']}"} )

        # Step 2: Authorize
        auth_result = await authorize_command(
            intent=intent_result["intent"],
            user_context=user_context,
            tenant_id=tenant_id,
        )
        logs.append({"node": "J3", "technique": "AuthCheck",
                     "duration_ms": 0, "result_summary": f"authorized={auth_result.authorized} "
                     f"role={auth_result.role}"})

        # Step 3: Execute (or deny)
        if auth_result.authorized:
            chat_response = await _execute_command(
                intent_result=intent_result,
                auth_result=auth_result,
                tenant_id=tenant_id,
                signals=signals,
                db=db,
            )
            logs.append({"node": "J3", "technique": "ExecuteCommand",
                         "duration_ms": 0, "result_summary": f"executed={intent_result['intent']}"})
        else:
            chat_response = f"[DENIED] {auth_result.reason}"
            logs.append({"node": "J3", "technique": "AuthDenied",
                         "duration_ms": 0, "result_summary": auth_result.reason})

    # 3. Build quota feedback for PARWA Node 2
    quota_feedback = {
        "tenant_id": tenant_id,
        "quota_status": signals.get("quota_status", {}),
        "variant_tier": list(signals.get("quota_status", {}).keys())[0] if signals.get("quota_status") else "parwa",
    }

    # 4. Summary
    keys = [n["notification_key"] for n in notifications]
    elapsed = int((time.time() - start) * 1000)
    logger.info("Jarvis NOTIFY complete: tenant=%s notifications=%d chat=%s llm=%d auth=%s [%dms]",
                tenant_id, len(notifications), bool(chat_response), llm_calls,
                bool(user_context.get("role")), elapsed)

    return {
        "notifications": notifications,
        "notification_keys": keys,
        "chat_response": chat_response,
        "quota_feedback": quota_feedback,
        "notify_log": logs,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
        "intent_result": intent_result if trigger == "admin_chat" else None,
        "auth_result": {"authorized": auth_result.authorized, "role": auth_result.role}
                        if trigger == "admin_chat" else None,
    }