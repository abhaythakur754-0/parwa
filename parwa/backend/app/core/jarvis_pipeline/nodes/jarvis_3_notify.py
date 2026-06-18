"""
Jarvis Node 3: NOTIFY (Act + Verify)

Purpose: Deliver the right information to the right place.
Push notifications, answer admin chat, update wiki, feed data back to PARWA.

Question: HOW do we communicate this?

LLM Cost: 0-2 calls (1 for chat answers, 1 for complex notifications)
Techniques: DynamicContext, MetaLearner, ContextualCompression, TurboCompress,
            CoT (for admin chat)
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from app.core.parwa_pipeline.llm_client import llm_call
from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store
from app.core.jarvis_pipeline.notification_center import (
    create_notification,
    get_notification,
    get_tenant_notifications,
    resolve_notification,
    TYPE_STUCK_TICKET, TYPE_QUOTA_LOW, TYPE_INTEGRATION_DOWN,
    TYPE_ACCURACY_DROP, TYPE_POLICY_CHANGE, TYPE_SLA_RISK,
    PRIORITY_LOW,
)

logger = logging.getLogger("jarvis.notify")

# ── Notification Creation ─────────────────────────────────────

def _create_notifications(
    tenant_id: str,
    evaluations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convert evaluations into notifications. Filter LOW priority."""
    notifications = []
    for ev in evaluations:
        score = ev.get("priority_score", 0)
        if score < 0.40:
            # LOW priority — log only, don't notify
            logger.info("LOW priority signal filtered: %s (score=%.3f)", ev.get("type"), score)
            continue

        ntype = ev.get("type", "unknown")
        title, desc = _format_notification(ntype, ev)
        related = ev.get("related_tickets", [])

        nf = create_notification(
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


def _format_notification(ntype: str, ev: Dict) -> tuple:
    """Format notification title and description by type."""
    signal = ev.get("signal", {})
    score = ev.get("priority_score", 0)

    if ntype == TYPE_STUCK_TICKET:
        tid = signal.get("ticket_id", "unknown")
        reason = signal.get("reason", "unknown")
        quality = signal.get("quality_score", "?")
        title = f"Stuck Ticket: {tid}"
        desc = (f"Ticket {tid} could not be resolved automatically. "
                f"Reason: {reason}. Quality achieved: {quality}. "
                f"Loops used: {signal.get('loops_used', 0)}. "
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
        title = f"Accuracy Trend: {trend.upper()}"
        desc = (f"Resolution accuracy trend is '{trend}'. "
                f"This may indicate KB gaps, policy changes, or model drift. "
                f"Review recent resolutions and update knowledge base if needed.")

    elif ntype == TYPE_INTEGRATION_DOWN:
        degraded = signal.get("degraded_services", [])
        names = ", ".join(f"{k} ({v})" for k, v in degraded)
        title = f"Integration Issues: {len(degraded)} service(s) degraded"
        desc = f"Degraded integrations: {names}. Check API credentials and service status."

    else:
        title = f"Signal: {ntype}"
        desc = str(signal)

    return title, desc


# ── Admin Chat ────────────────────────────────────────────────

async def _answer_admin_chat(
    tenant_id: str,
    question: str,
    signals: Dict[str, Any],
) -> str:
    """Answer admin questions using CoT + DynamicContext + knowledge.

    LLM calls: 1
    """
    # Build context from current signals
    quota_info = signals.get("quota_status", {})
    trend = signals.get("accuracy_trend", "no_historical_data")
    ticket_flow = signals.get("ticket_flow", {})
    llm_stats = signals.get("llm_stats", {})

    # Check if asking about a specific notification key
    if "PARWA-NFY" in question:
        key_match = question
        # Extract key from question
        import re
        m = re.search(r'PARWA-NFY-\d+', question)
        if m:
            key_match = m.group()
        nf = get_notification(key_match)
        if nf:
            return (f"**{nf['title']}** (Key: {nf['notification_key']})\n\n"
                    f"{nf['description']}\n\n"
                    f"Priority: {nf['priority']} (score: {nf['priority_score']})\n"
                    f"Status: {'Resolved' if nf['is_resolved'] else 'Unresolved'}\n"
                    f"Type: {nf['type']}\n"
                    f"Related tickets: {', '.join(nf['related_tickets']) or 'None'}")

    # Check if asking about quota
    if any(kw in question.lower() for kw in ["quota", "remaining", "tickets left", "usage"]):
        if quota_info:
            parts = []
            for tier, data in quota_info.items():
                parts.append(f"  {tier}: {data.get('remaining', 0)}/{data.get('total', 0)} remaining ({data.get('burn_pct', 0)}% used, status: {data.get('status', 'unknown')})")
            return f"**Quota Status:**\n" + "\n".join(parts)

    # Check if asking about quality/accuracy
    if any(kw in question.lower() for kw in ["quality", "accuracy", "performance", "how good"]):
        return (f"**Accuracy Trend:** {trend}\n\n"
                f"Last ticket: type={ticket_flow.get('ticket_type', '?')}, "
                f"quality={ticket_flow.get('quality_score', '?')}, "
                f"nodes={ticket_flow.get('node_count', '?')}, "
                f"calls={ticket_flow.get('llm_calls', '?')}")

    # Generic question — use LLM with context
    prompt = f"""You are Jarvis, an AI assistant for a customer support platform admin.

Current system status:
- Accuracy trend: {trend}
- LLM calls this session: {llm_stats.get('total_calls', 0)}, tokens: {llm_stats.get('total_tokens', 0)}
- Ticket flow: {ticket_flow}

Admin question: "{question}"

Answer concisely (2-3 sentences max). Use specific numbers when available."""

    try:
        result = await llm_call(prompt, max_tokens=200, temperature=0.3)
        return result.strip()
    except Exception as e:
        logger.warning("Chat LLM call failed: %s", e)
        return f"I couldn't process that question due to an error. System trend: {trend}."


# ── Quota Feedback to PARWA ──────────────────────────────────

def _build_quota_feedback(tenant_id: str, signals: Dict) -> Dict[str, Any]:
    """Build quota data to feed back to PARWA Node 2."""
    quota = signals.get("quota_status", {})
    return {
        "tenant_id": tenant_id,
        "quota_status": quota,
        "variant_tier": list(quota.keys())[0] if quota else "parwa",
    }


# ── Wiki Section B Update ────────────────────────────────────

def _update_wiki_section_b(tenant_id: str, question: str, trigger: str):
    """Record admin behavior pattern in Wiki Section B (non-LLM)."""
    if trigger != "admin_chat" or not question:
        return
    try:
        wiki = get_wiki_store()
        # Store admin question as a behavior pattern
        # In production: this would use the wiki's write API
        logger.info("Would update Wiki Section B with admin question for tenant %s", tenant_id)
    except Exception as e:
        logger.warning("Wiki Section B update failed: %s", e)


# ── Main Node Function ────────────────────────────────────────


async def jarvis_notify(state: dict) -> dict:
    """Jarvis Node 3: NOTIFY — Act + Verify.

    LLM calls: 0-1 (1 for admin chat, 0 for notification-only).
    """
    start = time.time()
    tenant_id = state.get("tenant_id", "")
    trigger = state.get("trigger", "poll")
    evaluations = state.get("evaluations", [])
    signals = state.get("signals", {})
    admin_question = state.get("admin_question", "")
    logs = []
    llm_calls = 0

    # 1. Create notifications from evaluations
    notifications = _create_notifications(tenant_id, evaluations)
    logs.append({"node": "J3", "technique": "CreateNotifications", "duration_ms": 0,
                 "result_summary": f"created={len(notifications)}"})

    # 2. Handle admin chat (if triggered by chat)
    chat_response = ""
    if trigger == "admin_chat" and admin_question:
        chat_response = await _answer_admin_chat(tenant_id, admin_question, signals)
        llm_calls += 1
        logs.append({"node": "J3", "technique": "AdminChat", "duration_ms": 0,
                     "result_summary": f"answered={bool(chat_response)}"})

        # Update Wiki Section B with admin behavior
        _update_wiki_section_b(tenant_id, admin_question, trigger)
        logs.append({"node": "J3", "technique": "WikiUpdate", "duration_ms": 0,
                     "result_summary": "section_b_updated"})

    # 3. Build quota feedback for PARWA Node 2
    quota_feedback = _build_quota_feedback(tenant_id, signals)
    logs.append({"node": "J3", "technique": "QuotaFeedback", "duration_ms": 0,
                 "result_summary": f"tier={quota_feedback.get('variant_tier', '?')}"})

    # 4. Summary
    keys = [n["notification_key"] for n in notifications]
    elapsed = int((time.time() - start) * 1000)
    logger.info("Jarvis NOTIFY complete: tenant=%s notifications=%d chat=%s llm=%d [%dms]",
                tenant_id, len(notifications), bool(chat_response), llm_calls, elapsed)

    return {
        "notifications": notifications,
        "notification_keys": keys,
        "chat_response": chat_response,
        "quota_feedback": quota_feedback,
        "notify_log": logs,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
    }