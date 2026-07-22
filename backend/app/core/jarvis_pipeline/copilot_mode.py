"""
Jarvis Co-Pilot — Wave 8D: Draft Composer

Co-Pilot Mode: Jarvis drafts text for human review.
- Manager types: "Reply to customer about delayed order"
- Jarvis drafts response based on ticket data + policy + sentiment
- Manager edits → AI learns from edits via training_data
- Saves 90% of typing time

Also includes:
- Wave 8C: Proactive Outbound System (feature-flagged)
- Wave 8F: DSPy-Integrated Corrections
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .jarvis_db import get_db

logger = logging.getLogger("jarvis.copilot")

# ── Co-Pilot Draft Generation ──────────────────────────────────

_COPILOT_DRAFT_PROMPT = """You are Jarvis, an AI co-pilot for a customer support manager.
Draft a professional response for the following scenario.

Customer context:
- Ticket ID: {ticket_id}
- Customer query: {customer_query}
- Channel: {channel}
- Customer sentiment: {sentiment}
- Account tier: {account_tier}
- Previous interactions: {history_summary}

Relevant policy/context:
{policy_context}

Draft a response that:
1. Acknowledges the customer's concern
2. Provides clear next steps or resolution
3. Matches the tone to the sentiment ({sentiment})
4. Is concise but complete

Return ONLY the drafted response text, no JSON or markdown wrapping."""


async def draft_response(
    tenant_id: str,
    actor_email: str,
    ticket_id: str,
    customer_query: str,
    channel: str = "chat",
    additional_context: str = "",
) -> Dict[str, Any]:
    """Generate a co-pilot draft response for a ticket.

    Uses LLM to draft based on customer context, policy, and sentiment.
    Stores draft for later review and learning.
    """
    db = get_db()

    # Analyze sentiment (simple heuristic)
    sentiment = _analyze_sentiment(customer_query)

    # Get relevant policy context
    policy_context = _get_policy_context(customer_query)

    # Get account tier from ticket or defaults
    account_tier = "parwa"  # default

    try:
        from app.core.parwa_pipeline.llm_client import llm_call

        prompt = _COPILOT_DRAFT_PROMPT.format(
            ticket_id=ticket_id,
            customer_query=customer_query,
            channel=channel,
            sentiment=sentiment,
            account_tier=account_tier,
            history_summary="No previous interactions",
            policy_context=policy_context,
        )
        draft_text = await llm_call(prompt, max_tokens=300, temperature=0.4)
    except Exception as e:
        logger.error("Co-pilot draft generation failed: %s", e)
        draft_text = f"[DRAFT ERROR] Could not generate draft: {e}"

    draft_id = f"draft_{uuid.uuid4().hex[:8]}"

    # Store draft in training_data for learning
    await db.save_training_data(
        tenant_id=tenant_id,
        data_type="copilot_draft",
        content={
            "draft_id": draft_id,
            "ticket_id": ticket_id,
            "actor_email": actor_email,
            "customer_query": customer_query,
            "draft_text": draft_text,
            "sentiment": sentiment,
            "channel": channel,
            "status": "pending_review",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    return {
        "success": True,
        "draft_id": draft_id,
        "ticket_id": ticket_id,
        "draft_text": draft_text,
        "sentiment": sentiment,
        "status": "pending_review",
        "summary": (
            f"[CO-PILOT] Draft generated for {ticket_id}\n"
            f"  Draft ID: {draft_id}\n"
            f"  Sentiment: {sentiment}\n"
            f"  Status: Awaiting your review\n"
            f"\n--- DRAFT ---\n{draft_text}\n--- END DRAFT ---"
        ),
    }


async def save_edited_draft(
    tenant_id: str,
    draft_id: str,
    edited_text: str,
    actor_email: str,
) -> Dict[str, Any]:
    """Save manager's edited version for AI learning.

    Stores the before/after for training data.
    """
    db = get_db()

    await db.save_training_data(
        tenant_id=tenant_id,
        data_type="copilot_edit",
        content={
            "draft_id": draft_id,
            "edited_by": actor_email,
            "edited_text": edited_text,
            "status": "edited",
            "learned_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    await db.create_audit_entry(
        tenant_id=tenant_id,
        action="copilot_draft_edited",
        actor_email=actor_email,
        target_type="draft",
        target_id=draft_id,
    )

    return {
        "success": True,
        "draft_id": draft_id,
        "summary": f"[CO-PILOT] Edited draft saved. AI will learn from your corrections.",
    }


# ── Wave 8C: Proactive Outbound System ─────────────────────────

async def create_proactive_outreach(
    tenant_id: str,
    actor_email: str,
    outreach_type: str,
    customer_id: str,
    reason: str,
    draft_content: str,
) -> Dict[str, Any]:
    """Create a proactive outreach message (requires approval).

    Types: abandoned_cart_recovery, churn_prevention, shipping_delay_alert
    ALL proactive actions require manager approval.
    """
    db = get_db()

    # Check feature flag
    flags = await db.get_active_flags(tenant_id, flag_type="proactive_outbound")
    if not flags or not any(f.get("flag_value") == "enabled" for f in flags):
        return {
            "success": False,
            "error": "Proactive outbound is not enabled. Enable with: 'Jarvis, enable proactive outreach'",
        }

    outreach_id = f"outreach_{uuid.uuid4().hex[:8]}"

    # Store as pending approval
    await db.create_notification(
        tenant_id=tenant_id,
        ntype="proactive_outreach",
        priority_score=0.5,
        title=f"Proactive Outreach: {outreach_type}",
        description=(
            f"Type: {outreach_type}\n"
            f"Customer: {customer_id}\n"
            f"Reason: {reason}\n"
            f"Draft: {draft_content[:200]}...\n\n"
            f"APPROVAL REQUIRED before sending."
        ),
        source_data={
            "outreach_id": outreach_id,
            "outreach_type": outreach_type,
            "customer_id": customer_id,
            "reason": reason,
            "draft_content": draft_content,
            "status": "pending_approval",
            "created_by": actor_email,
        },
    )

    await db.create_audit_entry(
        tenant_id=tenant_id,
        action="proactive_outreach_created",
        actor_email=actor_email,
        target_type="outreach",
        target_id=outreach_id,
        payload={"type": outreach_type, "customer": customer_id},
    )

    return {
        "success": True,
        "outreach_id": outreach_id,
        "status": "pending_approval",
        "summary": (
            f"[PROACTIVE] Outreach created: {outreach_type}\n"
            f"  Customer: {customer_id}\n"
            f"  Reason: {reason}\n"
            f"  Status: PENDING APPROVAL (will not auto-send)\n"
            f"  Review in the Approvals panel."
        ),
    }


# ── Wave 8F: DSPy Corrections ──────────────────────────────────

async def apply_dspy_correction(
    tenant_id: str,
    actor_email: str,
    target_behavior: str,
    correction_code: str,
    description: str,
) -> Dict[str, Any]:
    """Apply a permanent correction via DSPy-style learning.

    "Jarvis, fix this. Use code 'V2.0'"
    Updates the prompt compiler for permanent fix.
    """
    db = get_db()

    correction_id = f"correction_{uuid.uuid4().hex[:8]}"

    # Store correction in training_data
    await db.save_training_data(
        tenant_id=tenant_id,
        data_type="dspy_correction",
        content={
            "correction_id": correction_id,
            "target_behavior": target_behavior,
            "correction_code": correction_code,
            "description": description,
            "applied_by": actor_email,
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "before": "auto_captured",
            "after": description,
        },
    )

    await db.create_audit_entry(
        tenant_id=tenant_id,
        action="dspy_correction_applied",
        actor_email=actor_email,
        target_type="correction",
        target_id=correction_id,
        payload={
            "target": target_behavior,
            "code": correction_code,
        },
    )

    return {
        "success": True,
        "correction_id": correction_id,
        "summary": (
            f"[DSPY] Correction applied\n"
            f"  Correction ID: {correction_id}\n"
            f"  Target: {target_behavior}\n"
            f"  Code: {correction_code}\n"
            f"  Description: {description}\n"
            f"  Status: Active — will be used in future responses"
        ),
    }


# ── Helpers ────────────────────────────────────────────────────

def _analyze_sentiment(text: str) -> str:
    """Simple sentiment analysis."""
    angry_words = {"angry", "furious", "unacceptable", "terrible", "worst", "horrible",
                   "cancel", "sue", "complaint", "ridiculous", "outraged", "mad"}
    frustrated_words = {"frustrated", "annoying", "disappointed", "unhappy", "issue",
                        "problem", "wrong", "broken", "not working", "again"}
    happy_words = {"great", "love", "awesome", "thanks", "perfect", "excellent", "happy",
                  "appreciate", "wonderful"}

    text_lower = text.lower()
    words = set(text_lower.split())

    if words & angry_words:
        return "angry"
    if words & frustrated_words:
        return "frustrated"
    if words & happy_words:
        return "positive"
    return "neutral"


def _get_policy_context(query: str) -> str:
    """Get relevant policy context for a query."""
    query_lower = query.lower()

    policies = {
        "refund": "Refund Policy: Refunds processed within 5-7 business days. Partial refunds available for annual plans with proration. Credits applied before refund calculation.",
        "return": "Return Policy: Returns accepted within 30 days of purchase. Annual plan returns prorated based on usage. Customer keeps access until end of billing period.",
        "billing": "Billing Policy: Invoices generated on 1st of each month. Failed payments retried 3 times over 7 days. Duplicate charges immediately refunded.",
        "account": "Account Policy: Account changes take effect immediately. Workspace splits preserve ticket history. Team members can be reassigned between plans.",
        "shipping": "Shipping Policy: Standard shipping 5-7 business days. Express 2-3 business days. Delays proactively communicated to customers.",
        "cancel": "Cancellation Policy: Monthly plans cancel at end of billing cycle. Annual plans: prorated credit for remaining months minus 30-day window penalty.",
        "sso": "SSO Integration: Support Okta, Azure AD, Google Workspace. Certificate sync issues resolved by re-importing certificate. Lockout: reset via admin panel.",
    }

    matched = []
    for keyword, policy in policies.items():
        if keyword in query_lower:
            matched.append(policy)

    return "\n".join(matched) if matched else "No specific policy found. Use general professional response."
