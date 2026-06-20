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
    is_emergency_intent, is_approval_intent, is_report_intent,
)
from app.core.jarvis_pipeline.command_executor import (
    execute_command, validate_command, get_effective_flags,
    ExecutionResult,
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
    raw_input: str = "",
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
        response = await _handle_control(intent, target, tenant_id, auth_result, db,
                                         raw_input=raw_input)
        return response

    # ── APPROVAL INTENTS ─────────────────────────────────
    if is_approval_intent(intent):
        response = await _handle_approval(intent, target, tenant_id, auth_result, db)
        return response

    # ── EMERGENCY INTENTS ────────────────────────────────
    if is_emergency_intent(intent):
        response = await _handle_emergency(intent, target, tenant_id, auth_result, db,
                                          raw_input=raw_input)
        return response

    # ── GUIDANCE INTENTS (escalated ticket human guidance) ──
    if intent == "provide_guidance":
        return await _handle_provide_guidance(target, tenant_id, auth_result, db, raw_input=raw_input)
    if intent == "resume_ticket":
        return await _handle_resume_ticket(target, tenant_id, auth_result, db)

    # ── EXPLAIN / TEACH / AGENT ──────────────────────────
    if intent == "explain_ticket":
        return await _handle_explain_ticket(target, tenant_id, signals, db)
    if intent == "explain_flag":
        return await _handle_explain_flags(tenant_id, db)
    if intent == "teach_skill":
        return await _handle_teach_skill(target, tenant_id, auth_result, db)
    if intent == "create_agent":
        return await _handle_create_agent(target, tenant_id, auth_result, db)
    if intent == "control_approval_override":
        # Wave 3: approval override via executor
        result = await execute_command(
            intent=intent, target=target, tenant_id=tenant_id,
            actor_email=auth_result.email, raw_input=raw_input,
        )
        return result.response

    return f"I understood your command but don't have a handler for '{intent}' yet."


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

    # ── Wave 6 Query Handlers ─────────────────────────────

    if intent == "query_report":
        return await _handle_wave6_report(target, tenant_id, db)

    if intent == "query_sla":
        return await _handle_wave6_sla(tenant_id, db)

    if intent == "query_health_score":
        return await _handle_wave6_health_score(tenant_id, db)

    if intent == "query_roi":
        return await _handle_wave6_roi(tenant_id, db)

    if intent == "query_agent_health":
        return await _handle_wave6_agent_health(target, tenant_id, db)

    return f"Query '{intent}' not yet implemented."


# ── Control Handlers ──────────────────────────────────────────

async def _handle_control(intent: str, target: str, tenant_id: str, auth: AuthResult, db,
                           raw_input: str = "") -> str:
    """Handle control commands via command_executor (Wave 3).

    5-step pipeline: validate → resolve → execute → verify → respond.
    All conflicts auto-resolved. All actions audited.
    """
    result = await execute_command(
        intent=intent,
        target=target,
        tenant_id=tenant_id,
        actor_email=auth.email,
        raw_input=raw_input,
    )

    # Build response with warnings and conflict info
    response = result.response
    if result.warnings:
        response += "\n\nWarnings:\n" + "\n".join(f"  - {w}" for w in result.warnings)
    if result.conflicts_resolved:
        names = [f["flag_type"] + "=" + f["flag_value"] for f in result.conflicts_resolved]
        response += f"\n\nAuto-resolved conflicts: {', '.join(names)}"
    if result.undo_id:
        response += f"\n\nTo undo: **'disable my last rule'**"

    return response


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

async def _handle_emergency(intent: str, target: str, tenant_id: str, auth: AuthResult, db,
                            raw_input: str = "") -> str:
    """Handle emergency commands via command_executor (Wave 3).

    Real execution: recall marks outbox, void removes outbox, shutdown sets flag + notification.
    """
    result = await execute_command(
        intent=intent,
        target=target,
        tenant_id=tenant_id,
        actor_email=auth.email,
        raw_input=raw_input,
    )

    response = result.response
    if result.warnings:
        response += "\n\nWarnings:\n" + "\n".join(f"  - {w}" for w in result.warnings)
    if result.undo_id and intent != "emergency_shutdown":
        response += f"\n\nTo undo: **'disable my last rule'**"

    return response


# ── Guidance Handlers (Escalation Vault Integration) ────────────

async def _handle_provide_guidance(
    target: str, tenant_id: str, auth: AuthResult, db,
    raw_input: str = "",
) -> str:
    """Handle human guidance for an escalated ticket.

    When a human agent provides guidance in JARVIS for a stuck ticket,
    this saves the guidance to the escalation vault so PARWA can resume.

    Usage:
      "guide PARWA-NFY-001: Customer is on enterprise plan, approved for full refund"
      "guide escalation_abc123: Try using the refund process v2 steps"
    """
    import re

    # Parse: target is the notification key or escalation ID
    # raw_input has the full guidance after the colon
    guidance_text = ""
    if ":" in raw_input:
        parts = raw_input.split(":", 1)
        guidance_text = parts[1].strip()
    else:
        # guidance_text is whatever comes after the intent+target
        intent_prefix = f"guide {target}"
        if raw_input.startswith(intent_prefix):
            guidance_text = raw_input[len(intent_prefix):].strip()
        elif raw_input.startswith(f"provide_guidance {target}"):
            guidance_text = raw_input[len(f"provide_guidance {target}"):].strip()

    if not guidance_text or len(guidance_text) < 5:
        return (
            "**[ERROR]** Guidance text too short. Please provide detailed guidance.\n\n"
            "Usage: `guide <notification_key>: <your guidance>`\n"
            "Example: `guide PARWA-NFY-001: Customer is enterprise, approved for $199 refund, ref #REF-8832`"
        )

    await db.create_audit_entry(
        tenant_id=tenant_id,
        action="provide_guidance",
        actor_email=auth.email,
        target_type="escalation",
        target_id=target,
        payload={"guidance": guidance_text, "source": "jarvis_chat"},
    )

    # Try to find escalation by notification key first, then by escalation ID
    from app.core.escalation_vault.vault_manager import VaultManager

    record = await VaultManager.get_escalation_by_notification(target)
    if not record:
        record = await VaultManager.get_escalation(target)

    if not record:
        return (
            f"**[NOT FOUND]** No escalation found for '{target}'.\n\n"
            "Use the notification key (PARWA-NFY-XXX) or escalation ID."
        )

    # Check if already resolved
    if record.get("reprocess_status") == "done":
        return (
            f"**[ALREADY RESOLVED]** Escalation {record['escalation_id'][:8]} "
            f"was already reprocessed on {record.get('reprocess_completed_at', 'unknown')}."
        )

    # Save guidance to vault
    vault_record = await VaultManager.provide_human_guidance(
        escalation_id=record["escalation_id"],
        guidance=guidance_text,
        source="jarvis_chat",
    )

    if vault_record:
        return (
            f"**[OK] Guidance saved** for escalation {record['escalation_id'][:8]}\n\n"
            f"Original ticket: {record.get('original_ticket_id', '?')}\n"
            f"Query: {record.get('original_query', '?')[:100]}...\n"
            f"Guidance: {guidance_text[:200]}...\n\n"
            f"Status: **Eligible for resume**\n\n"
            f"To resume now: `resume {record['escalation_id'][:8]}`\n"
            f"Or wait for auto-resume cron."
        )
    else:
        return f"**[ERROR]** Failed to save guidance for escalation {record['escalation_id'][:8]}"


async def _handle_resume_ticket(
    target: str, tenant_id: str, auth: AuthResult, db,
) -> str:
    """Handle manual resume trigger for an escalated ticket.

    Usage: "resume <escalation_id>"
    """
    await db.create_audit_entry(
        tenant_id=tenant_id,
        action="resume_ticket",
        actor_email=auth.email,
        target_type="escalation",
        target_id=target,
    )

    from app.core.escalation_vault.vault_manager import VaultManager

    # Find escalation by ID or notification key
    record = await VaultManager.get_escalation(target)
    if not record:
        record = await VaultManager.get_escalation_by_notification(target)

    if not record:
        return f"**[NOT FOUND]** No escalation found for '{target}'."

    if record.get("human_status") != "guidance_provided":
        return (
            f"**[NOT READY]** Escalation {record['escalation_id'][:8]} needs guidance first.\n"
            f"Current status: {record.get('human_status', 'unknown')}\n\n"
            f"Provide guidance: `guide {record.get('notification_key', record['escalation_id'][:12])}: <your guidance>`"
        )

    # Trigger resume pipeline
    from app.core.escalation_vault.resume_pipeline import resume_escalated_ticket

    result = await resume_escalated_ticket(record["escalation_id"], tenant_id)

    if result.get("success"):
        return (
            f"**[RESOLVED]** Resume successful for escalation {record['escalation_id'][:8]}\n\n"
            f"Quality: {result.get('reprocess_quality', 0):.2f}\n"
            f"LLM calls: {result.get('llm_calls', 0)}\n"
            f"Elapsed: {result.get('elapsed_ms', 0)}ms\n"
            f"CRM push: {'Success' if result.get('crm_push', {}).get('success') else 'N/A'}\n\n"
            f"Response preview: {result.get('reprocess_result', '')[:200]}..."
        )
    else:
        return (
            f"**[FAILED]** Resume did not pass quality check.\n\n"
            f"Quality: {result.get('reprocess_quality', 0):.2f} (threshold: 0.88)\n"
            f"This ticket still needs manual handling."
        )


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


# ── Wave 6 Report/Query Handlers ─────────────────────────────

async def _handle_wave6_report(target: str, tenant_id: str, db) -> str:
    """Wave 6: Handle report queries — weekly wins or performance dashboard."""
    try:
        from app.core.jarvis_pipeline.report_generator import (
            generate_weekly_wins_report, get_performance_dashboard,
            format_weekly_report_text,
        )

        if target == "dashboard":
            dashboard = await get_performance_dashboard(tenant_id)
            va = dashboard.get("volume_accuracy", {})
            ct = dashboard.get("confidence_trends", {})
            eg = dashboard.get("efficiency_gains", {})
            lines = [
                "**Performance Dashboard**:",
                f"  Tickets Handled: {va.get('total_tickets', 0)}",
                f"  Auto-Resolved: {va.get('auto_resolved', 0)} ({va.get('auto_resolve_pct', 0):.1f}%)",
                f"  Avg Quality: {va.get('avg_quality', 0):.1%}",
                f"  Quality Trend: {va.get('quality_trend', 'stable')}",
                f"  Avg Confidence: {ct.get('avg_confidence', 0):.1%} ({ct.get('trend_direction', 'N/A')})",
                f"  Manager Time Saved: {eg.get('manager_time_saved_minutes', 0):.0f} min",
                f"  Training Priorities: {eg.get('total_priority_areas', 0)} areas",
            ]
            return "\n".join(lines)
        else:
            report = await generate_weekly_wins_report(tenant_id)
            return format_weekly_report_text(report)
    except Exception as e:
        logger.error("Wave 6 report handler error: %s", e)
        return f"[ERROR] Failed to generate report: {e}"


async def _handle_wave6_sla(tenant_id: str, db) -> str:
    """Wave 6: Handle SLA queries."""
    try:
        from app.core.jarvis_pipeline.sla_calculator import compute_sla_status

        sla = await compute_sla_status(tenant_id)
        status = sla.get("sla_status", "unknown")
        actual = sla.get("actual_uptime_pct", 0)
        target = sla.get("target_uptime_pct", 99.5)
        credit = sla.get("credit_owed_usd", 0)
        incidents = sla.get("incident_count", 0)
        lines = [
            "**SLA Status**:",
            f"  Status: {status.upper()}",
            f"  Actual Uptime: {actual:.2f}%",
            f"  Target Uptime: {target:.1f}%",
            f"  Gap: {sla.get('uptime_gap_pct', 0):.2f}%",
            f"  Downtime: {sla.get('total_downtime_seconds', 0):.0f} seconds",
            f"  Incidents: {incidents}",
        ]
        if credit > 0:
            lines.append(f"  Credit Owed: ${credit:.2f}")
        lines.append(f"\n{sla.get('recommendation', '')}")
        return "\n".join(lines)
    except Exception as e:
        logger.error("Wave 6 SLA handler error: %s", e)
        return f"[ERROR] Failed to compute SLA: {e}"


async def _handle_wave6_health_score(tenant_id: str, db) -> str:
    """Wave 6: Handle customer health score queries."""
    try:
        from app.core.jarvis_pipeline.health_scorer import get_customer_health

        health = await get_customer_health(tenant_id)
        score = health.get("health_score", 0)
        pct = health.get("readiness_pct", 0)
        grade = health.get("grade", "early")
        achieved = health.get("achieved_milestones", 0)
        total = health.get("total_milestones", 0)

        lines = [
            "**Customer Health Score**:",
            f"  Readiness: {pct}% (grade: {grade})",
            f"  Milestones: {achieved}/{total} achieved",
        ]
        for m in health.get("milestones", []):
            icon = "OK" if m["achieved"] else ".."
            lines.append(f"  [{icon}] {m['name']}: {'done' if m['achieved'] else 'pending'}")
        lines.append(f"\n{health.get('success_coach_message', '')}")
        return "\n".join(lines)
    except Exception as e:
        logger.error("Wave 6 health score handler error: %s", e)
        return f"[ERROR] Failed to compute health score: {e}"


async def _handle_wave6_roi(tenant_id: str, db) -> str:
    """Wave 6: Handle ROI queries."""
    try:
        from app.core.jarvis_pipeline.health_scorer import calculate_roi

        roi = await calculate_roi(tenant_id)
        lines = [
            "**ROI Analysis** (30-day):",
            f"  Total Tickets: {roi.get('total_tickets', 0)}",
            f"  Auto-Resolved: {roi.get('auto_resolved', 0)} ({roi.get('auto_resolve_pct', 0):.1f}%)",
            f"  Human-Handled: {roi.get('human_handled', 0)}",
            f"  Human Cost (estimated): ${roi.get('human_cost_usd', 0):.2f}",
            f"  AI Cost: ${roi.get('ai_cost_usd', 0):.2f}",
            f"  Net Savings: ${roi.get('net_savings_usd', 0):.2f}",
            f"  ROI: {roi.get('roi_pct', 0):.1f}%",
            f"\n{roi.get('recommendation', '')}",
        ]
        return "\n".join(lines)
    except Exception as e:
        logger.error("Wave 6 ROI handler error: %s", e)
        return f"[ERROR] Failed to calculate ROI: {e}"


async def _handle_wave6_agent_health(target: str, tenant_id: str, db) -> str:
    """Wave 6: Handle agent health / quality coach queries."""
    try:
        from app.core.jarvis_pipeline.quality_coach import (
            get_agent_health_summary, generate_weekly_quality_report,
            generate_mistake_analysis, run_drift_check_and_alert,
        )

        if target == "quality_report":
            report = await generate_weekly_quality_report(tenant_id)
            health = report.get("health_score", {})
            recs = report.get("recommendations", [])
            lines = [
                "**Weekly Quality Report**:",
                f"  Health Score: {health.get('health_score', 0):.1%} (Grade: {health.get('grade', '?')})",
                f"  Total Tickets: {report.get('performance', {}).get('total_tickets', 0)}",
                f"  Avg Quality: {report.get('performance', {}).get('avg_quality', 0):.1%}",
                f"  Mistakes: {report.get('mistakes', {}).get('total_mistakes', 0)}",
            ]
            if recs:
                lines.append("  Recommendations:")
                for r in recs[:5]:
                    lines.append(f"    - [{r.get('priority', '?')}] {r.get('text', '')[:100]}")
            return "\n".join(lines)
        else:
            summary = await get_agent_health_summary(tenant_id)
            score = summary.get("health_score", 0)
            grade = summary.get("grade", "?")
            weakest = summary.get("weakest_component", "?")
            components = summary.get("components", {})
            lines = [
                "**Agent Health Summary**:",
                f"  Score: {score:.1%} (Grade: {grade})",
                f"  Weakest: {weakest}",
            ]
            for name, val in components.items():
                if isinstance(val, (int, float)):
                    lines.append(f"    {name}: {val:.1%}")
            lines.append(f"\n{summary.get('recommendation', '')}")
            return "\n".join(lines)
    except Exception as e:
        logger.error("Wave 6 agent health handler error: %s", e)
        return f"[ERROR] Failed to get agent health: {e}"


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
                raw_input=admin_question,
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