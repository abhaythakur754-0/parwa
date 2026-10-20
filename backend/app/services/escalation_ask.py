"""Structured escalation asks — "here is my problem, here is what I need".

Every path that fails to resolve a ticket (missing connection, missing
knowledge, unverified answer, approval over the limit, technical error,
customer asked for a human, or something never seen before) produces the
same structured block:

    {
      "escalation_type": "missing_connection",
      "problem": "<what blocked the AI, plain words>",
      "needed_from_team": "<the concrete ask: connect X / answer Y / approve Z>",
      "after_that": "<what happens once the team does it>",
      "capability": "<optional: the capability missing, e.g. payment gateway>",
    }

Storage + flow:
  - ticket.metadata_json["escalation_ask"] (+ "escalation_type") so the
    dashboard escalations page shows "Needs: ..." on every stuck ticket
    and Phase 3 auto-retry can find tickets blocked by a specific gap.
  - _push_to_crm_outbound renders it into the CRM note / webhook payload,
    so the CRM team sees an actionable request, not a dead-end "AI failed".
  - When the CRM team resolves the ticket, CRMResolutionService relays
    the answer to the customer AND writes it into the AI wiki
    (learn_from_resolution) — the agent then reacts from memory next time.
    This is the answer to "can the agent learn any answer the team gives,
    even for problems not in history?": yes — every resolution becomes a
    recalled pattern; CoVe re-verifies it before it reaches a customer.

No LLM calls: deterministic mapping keeps escalations instant and free.
"""

from typing import Any, Dict, Optional

# ── Type labels (dashboard + CRM note) ──────────────────────────────────
ESCALATION_TYPE_LABELS: Dict[str, str] = {
    "missing_connection": "Missing connection",
    "missing_knowledge": "Missing knowledge",
    "unverified_answer": "Answer failed verification",
    "approval_required": "Approval needed",
    "technical_error": "Technical error",
    "customer_requested_human": "Customer asked for a human",
    "unknown": "Needs review",
}

_LEARNING_PROMISE = (
    "Your resolution is sent to the customer automatically and the AI "
    "learns it — this ticket type gets solved by itself next time."
)

# ── required_action → capability the AI is missing ─────────────────────
# Ordered: first match wins. Patterns are matched with `in` (lowercase).
_ACTION_CAPABILITIES = [
    (("refund", "payment", "charge", "transaction", "payout"),
     {"capability": "a payment gateway integration",
      "examples": "Razorpay, Stripe, PayPal",
      "verb": "execute payments actions (refunds, status checks)"}),
    (("track", "shipping", "carrier", "delivery", "shipment", "logistics"),
     {"capability": "a shipping / carrier integration",
      "examples": "Shippo, ShipStation, AfterShip",
      "verb": "fetch live tracking and delivery status"}),
    (("order", "cart", "shop", "ecommerce", "e-commerce", "return", "exchange"),
     {"capability": "an ecommerce / store integration",
      "examples": "Shopify, WooCommerce",
      "verb": "look up and update orders"}),
    (("invoice", "subscription", "billing", "plan ", "upgrade", "downgrade"),
     {"capability": "a billing integration",
      "examples": "Stripe Billing, Razorpay Subscriptions",
      "verb": "check and change subscriptions or invoices"}),
    (("appointment", "booking", "calendar", "reschedule"),
     {"capability": "a scheduling integration",
      "examples": "Calendly, Google Calendar",
      "verb": "book or move appointments"}),
    (("inventory", "stock", "warehouse"),
     {"capability": "an inventory integration",
      "examples": "your inventory system",
      "verb": "check live stock levels"}),
    (("crm", "contact", "lead", "customer record"),
     {"capability": "a CRM integration",
      "examples": "HubSpot, Salesforce",
      "verb": "read and update the customer record"}),
]


def _capability_for_action(required_action: str) -> Optional[Dict[str, str]]:
    """Map a pipeline required_action to the missing capability."""
    a = (required_action or "").lower().strip()
    if not a:
        return None
    for patterns, cap in _ACTION_CAPABILITIES:
        if any(p in a for p in patterns):
            return cap
    return {
        "capability": "an integration for this action",
        "examples": f"whatever system performs '{required_action.strip()}'",
        "verb": f"perform '{required_action.strip()}'",
    }


def classify_reason(reason: str) -> str:
    """Map a raw escalation_reason string to a structured escalation type.

    Unknown reasons stay 'unknown' — still a structured ask, never a
    dead end. Matching is substring-based so future reasons written by
    new code paths classify without touching this file.
    """
    r = (reason or "").lower().strip()
    if not r:
        return "unknown"
    if "cove" in r or "verif" in r:
        return "unverified_answer"
    if "human" in r:
        return "customer_requested_human"
    if any(k in r for k in ("retry", "retries", "error", "exception", "crash")):
        return "technical_error"
    if "approval" in r or "limit" in r or "guardrail" in r or "pause_for_agent" in r:
        return "approval_required"
    if any(k in r for k in ("kb", "knowledge", "no_answer", "no answer", "gap", "interrupt")):
        return "missing_knowledge"
    if any(k in r for k in ("connection", "integration", "no_tool", "tool", "access")):
        return "missing_connection"
    return "unknown"


def build_escalation_ask(
    reason: str,
    required_action: str = "",
    context_hint: str = "",
) -> Dict[str, Any]:
    """Build the structured ask for an escalation.

    Args:
        reason: raw escalation_reason (e.g. "max_retries_exceeded",
            "cove_blocked", "kb_gap_no_tool", "client_requested_human").
        required_action: pipeline required_action when known
            (e.g. "execute_refund", "track_shipment", "provide_info").
        context_hint: optional extra context (the interrupt question,
            the pipeline error text) shown to the team.
    """
    etype = classify_reason(reason)
    hint = (context_hint or "").strip()

    if etype == "missing_connection":
        cap = _capability_for_action(required_action) or {
            "capability": "a system integration",
            "examples": "the system that performs this action",
            "verb": "perform this action",
        }
        return {
            "escalation_type": etype,
            "problem": (
                f"I understood the request and know how to solve it, but I "
                f"have no connection to {cap['capability']} — I physically "
                f"cannot {cap['verb']} for the customer."
            ),
            "needed_from_team": (
                f"Connect {cap['capability']} (e.g. {cap['examples']}) in "
                f"Integrations."
            ),
            "after_that": (
                "Hit Retry on this ticket — I will build the tool against "
                "the new connection and finish it automatically."
            ),
            "capability": cap["capability"],
        }

    if etype == "missing_knowledge":
        return {
            "escalation_type": etype,
            "problem": (
                "The answer to this request is not in the knowledge base, "
                "so I cannot answer it truthfully."
                + (f" What I still need an answer for: {hint[:220]}" if hint else "")
            ),
            "needed_from_team": (
                "Provide the correct answer / policy for this request "
                "(or add it to the knowledge base)."
            ),
            "after_that": _LEARNING_PROMISE,
        }

    if etype == "unverified_answer":
        return {
            "escalation_type": etype,
            "problem": (
                "I drafted an answer, but my fact-check could not verify it "
                "against the knowledge base — I don't guess with customers."
            ),
            "needed_from_team": (
                "Verify the correct answer for the customer's question and "
                "resolve the ticket in your CRM."
            ),
            "after_that": _LEARNING_PROMISE,
        }

    if etype == "approval_required":
        return {
            "escalation_type": etype,
            "problem": (
                f"This request needs an action "
                f"({required_action or 'sensitive action'}) that is above "
                f"the tenant's auto-approval limit."
            ),
            "needed_from_team": (
                f"Approve / perform '{required_action or 'the requested action'}' "
                f"manually, or adjust the auto-approval limit if this is common."
            ),
            "after_that": _LEARNING_PROMISE,
        }

    if etype == "technical_error":
        return {
            "escalation_type": etype,
            "problem": (
                "The AI pipeline hit a technical problem before finishing "
                + (f"(detail: {hint[:180]})" if hint else "(all retries used).")
            ),
            "needed_from_team": (
                "Review this ticket and resolve it in your CRM; the "
                "technical detail is recorded on the ticket diagnostics."
            ),
            "after_that": _LEARNING_PROMISE,
        }

    if etype == "customer_requested_human":
        return {
            "escalation_type": etype,
            "problem": "The customer explicitly asked for a human agent.",
            "needed_from_team": (
                "Have a team member respond to the customer in your CRM."
            ),
            "after_that": _LEARNING_PROMISE,
        }

    return {
        "escalation_type": "unknown",
        "problem": (
            hint[:250] if hint else
            "I could not resolve this ticket with my current knowledge, "
            "tools, and connections."
        ),
        "needed_from_team": (
            "Review the customer's request and resolve it in your CRM."
        ),
        "after_that": _LEARNING_PROMISE,
    }


def format_ask_for_crm(ask: Dict[str, Any]) -> str:
    """Render the structured ask as a readable block for CRM notes.

    Used for the Zendesk/HubSpot internal-note fields and the generic
    webhook payload, so the team always sees Problem → What I need →
    What happens next instead of a bare "AI failed".
    """
    if not isinstance(ask, dict):
        return ""
    label = ESCALATION_TYPE_LABELS.get(
        ask.get("escalation_type", ""), "Needs review"
    )
    parts = [f"Problem: {ask.get('problem', '')}"]
    needed = ask.get("needed_from_team", "")
    if needed:
        parts.append(f"What I need from your team: {needed}")
    after = ask.get("after_that", "")
    if after:
        parts.append(f"Once done: {after}")
    return f"[{label}] " + " | ".join(p for p in parts if p)


def apply_escalation_ask(
    ticket,
    reason: str,
    required_action: str = "",
    context_hint: str = "",
) -> Dict[str, Any]:
    """Build the ask and persist it on ticket.metadata_json.

    Mutates the ticket in place (escalation_reason kept in sync,
    escalation_type + escalation_ask added). The CALLER commits.
    Best-effort: a metadata failure never breaks the escalation itself.
    Returns the ask dict (also when persistence failed).
    """
    import json

    ask = build_escalation_ask(reason, required_action, context_hint)
    try:
        metadata: Dict[str, Any] = {}
        if ticket.metadata_json:
            try:
                metadata = json.loads(ticket.metadata_json)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        if reason:
            metadata["escalation_reason"] = reason
        metadata["escalation_type"] = ask["escalation_type"]
        metadata["escalation_ask"] = ask
        ticket.metadata_json = json.dumps(metadata)
    except Exception:  # noqa: BLE001 — never break an escalation on metadata
        pass
    return ask
