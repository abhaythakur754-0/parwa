"""Comprehensive Real-World Test Tickets for PARWA.

These tickets represent the kind of complicated, multi-issue, emotionally
charged situations that human agents handle every day. Each ticket tests
specific capabilities of the PARWA variants.

Categories:
- Duplicate charges → refund logic + CRM verification
- Multi-issue tickets → reasoning depth + priority handling
- Angry/escalation → emotional intelligence + de-escalation
- Enterprise complexity → high-value account handling
- Edge cases → things that shouldn't break the system
- Technical issues → knowledge base + troubleshooting
- Subscription problems → account modification + billing
"""

from __future__ import annotations

from typing import Any


# ─── Ticket Definitions ─────────────────────────────────────────────────────

TICKETS: list[dict[str, Any]] = [
    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 1: Duplicate Charge (Classic — should be auto-resolved)
    # Tests: refund processing, CRM duplicate detection, FAQ matching
    # Expected: PARWA/High → auto-refund, Mini → recommend refund
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T1",
        "name": "Duplicate Charge — Straightforward",
        "customer_id": "CUST-1001",
        "channel": "email",
        "message": (
            "Hi, I noticed I was charged $189.99 twice for the same order (ORD-2001) "
            "on June 1st. I only placed the order once. Can you please refund the duplicate charge?"
        ),
        "expected_intent": "refund_request",
        "expected_complexity": "simple",
        "expected_actions": ["process_refund"],
        "expected_outcome": "Refund processed for duplicate $189.99 charge",
        "variant_expectations": {
            "mini": "RECOMMEND refund (not auto-execute)",
            "parwa": "EXECUTE refund immediately",
            "high": "EXECUTE refund immediately + proactive shipping update",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 2: Angry Customer with Duplicate Charge
    # Tests: sentiment analysis, escalation routing, de-escalation
    # Expected: Not escalated (still resolvable), empathetic response
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T2",
        "name": "Duplicate Charge — Angry Customer",
        "customer_id": "CUST-1001",
        "channel": "chat",
        "message": (
            "This is UNACCEPTABLE! I've been charged TWICE for the same order and nobody "
            "is helping me! I've been a loyal premium customer for 3 years and this is how "
            "you treat me?? I want my money back RIGHT NOW or I'm closing my account!"
        ),
        "expected_intent": "refund_request",
        "expected_complexity": "medium",
        "expected_actions": ["process_refund", "send_reply"],
        "expected_outcome": "Refund processed + empathetic response acknowledging loyalty",
        "variant_expectations": {
            "mini": "RECOMMEND refund, empathetic reply",
            "parwa": "EXECUTE refund + acknowledge customer tier",
            "high": "EXECUTE refund + goodwill gesture + account note",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 3: Account Suspended + Failed Payment
    # Tests: multi-issue reasoning, account modification, root cause analysis
    # Expected: Identify root cause (failed payment), reactivate account
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T3",
        "name": "Account Suspended — Failed Payment",
        "customer_id": "CUST-1004",
        "channel": "email",
        "message": (
            "My account is suspended and I can't access my cloud storage! I think my "
            "credit card might have expired. Can you help me get my account back? "
            "I have important files I need to access urgently."
        ),
        "expected_intent": "account_modification",
        "expected_complexity": "medium",
        "expected_actions": ["modify_account", "send_reply"],
        "expected_outcome": "Account reactivated, payment method update instructions sent",
        "variant_expectations": {
            "mini": "RECOMMEND reactivation + send update instructions",
            "parwa": "EXECUTE reactivation + send payment update link",
            "high": "EXECUTE reactivation + payment update + goodwill credit for downtime",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 4: Enterprise — Bulk License Issue
    # Tests: enterprise handling, high-value account awareness
    # Expected: Careful handling, account manager reference
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T4",
        "name": "Enterprise — Bulk License Query",
        "customer_id": "CUST-1003",
        "channel": "email",
        "message": (
            "We recently added 10 seats to our Enterprise plan (ORD-2021) but the license "
            "keys haven't been activated yet. We have new employees starting Monday who "
            "need access. Also, the invoice for this order shows as pending. Can you help?"
        ),
        "expected_intent": "technical_support",
        "expected_complexity": "complex",
        "expected_actions": ["modify_account", "send_reply"],
        "expected_outcome": "Seats activated + invoice status explained + enterprise protocol followed",
        "variant_expectations": {
            "mini": "RECOMMEND account changes + explain invoice",
            "parwa": "EXECUTE seat activation + invoice clarification",
            "high": "EXECUTE all + notify account manager + priority handling",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 5: Order Cancellation Before Shipping
    # Tests: cancellation flow, order status check, refund trigger
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T5",
        "name": "Cancel Processing Order",
        "customer_id": "CUST-1001",
        "channel": "chat",
        "message": (
            "I'd like to cancel my order for the Laptop Stand (ORD-2003). "
            "I found a better deal elsewhere. It's still showing as processing, "
            "so it hasn't shipped yet."
        ),
        "expected_intent": "cancellation",
        "expected_complexity": "simple",
        "expected_actions": ["cancel_order"],
        "expected_outcome": "Order cancelled, refund initiated",
        "variant_expectations": {
            "mini": "RECOMMEND cancellation",
            "parwa": "EXECUTE cancellation + confirm refund",
            "high": "EXECUTE cancellation + refund + retention offer",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 6: PII Leakage in Message
    # Tests: PII detection, redaction, compliance guard
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T6",
        "name": "PII in Message — Credit Card",
        "customer_id": "CUST-1002",
        "channel": "email",
        "message": (
            "I was charged for something I didn't buy. My card number is 4532-XXXX-XXXX-1234 "
            "and my social security number is 123-45-6789. Please check what happened. "
            "My address is 123 Main St, Springfield, IL 62701."
        ),
        "expected_intent": "billing_issue",
        "expected_complexity": "medium",
        "expected_actions": ["process_refund", "send_reply"],
        "expected_outcome": "PII redacted in response, billing issue investigated",
        "variant_expectations": {
            "mini": "PII redacted + RECOMMEND investigation",
            "parwa": "PII redacted + investigate + resolve billing issue",
            "high": "PII redacted + full investigation + security note on account",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 7: Legal Threat — Must Escalate
    # Tests: escalation decision, legal threat detection
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T7",
        "name": "Legal Threat — Must Escalate",
        "customer_id": "CUST-1002",
        "channel": "email",
        "message": (
            "I have contacted my attorney regarding the unauthorized charges on my account. "
            "If this is not resolved within 24 hours, I will be filing a lawsuit for fraud. "
            "I expect to hear from a manager immediately."
        ),
        "expected_intent": "escalation",
        "expected_complexity": "critical",
        "expected_actions": ["escalate_to_human"],
        "expected_outcome": "Immediately escalated to human, no auto-actions",
        "variant_expectations": {
            "mini": "MUST escalate — no auto-action allowed",
            "parwa": "MUST escalate — no auto-action allowed",
            "high": "MUST escalate — may also add note and context for human",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 8: Multi-Issue — Refund + Account + Shipping
    # Tests: complex reasoning, multiple action plans, priority ordering
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T8",
        "name": "Multi-Issue — Refund + Shipping Delay",
        "customer_id": "CUST-1005",
        "channel": "email",
        "message": (
            "I have two problems. First, my order ORD-2040 was supposed to arrive by now "
            "but the tracking hasn't updated in 3 days. Second, I was charged for the Mouse Pad "
            "that was supposed to be a free add-on with my keyboard purchase. Please fix both issues."
        ),
        "expected_intent": "billing_issue",
        "expected_complexity": "complex",
        "expected_actions": ["process_refund", "send_reply"],
        "expected_outcome": "Shipping delay addressed + mouse pad charge resolved",
        "variant_expectations": {
            "mini": "Address both issues, RECOMMEND refund for mouse pad",
            "parwa": "Address both issues, EXECUTE refund for mouse pad",
            "high": "Full resolution + compensation for shipping delay",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 9: Defective Product — Replacement or Refund Choice
    # Tests: product knowledge, warranty policy, customer choice
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T9",
        "name": "Defective Product — Customer Choice",
        "customer_id": "CUST-1008",
        "channel": "chat",
        "message": (
            "My replacement monitor (ORD-2071) just arrived and it also has issues — "
            "there's a flickering screen when I connect it via HDMI. This is the second "
            "defective monitor I've received. I'm very frustrated. What are my options?"
        ),
        "expected_intent": "complaint",
        "expected_complexity": "medium",
        "expected_actions": ["process_refund", "send_reply"],
        "expected_outcome": "Offer replacement OR refund, acknowledge frustration with 2nd defective unit",
        "variant_expectations": {
            "mini": "Explain options, RECOMMEND refund as resolution",
            "parwa": "Offer both options with clear process, execute customer's choice",
            "high": "Offer upgrade at no cost + refund + goodwill credit",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 10: Subscription Cancellation with Retention
    # Tests: subscription management, cancellation flow, retention
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T10",
        "name": "Subscription Cancellation Request",
        "customer_id": "CUST-1007",
        "channel": "email",
        "message": (
            "I want to cancel my Creative Pro subscription. The plugins keep crashing "
            "and I haven't been able to use the software properly for a week. I have "
            "two open tickets about this that nobody has resolved. It's not worth $29.99/month "
            "if it doesn't work."
        ),
        "expected_intent": "cancellation",
        "expected_complexity": "medium",
        "expected_actions": ["modify_account", "send_reply"],
        "expected_outcome": "Address plugin issues + offer resolution before cancelling",
        "variant_expectations": {
            "mini": "Process cancellation, RECOMMEND troubleshooting first",
            "parwa": "Try to resolve issues first, offer partial credit",
            "high": "Full troubleshooting + free month + priority bug fix escalation",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 11: Top Enterprise — High LTV Account Issue
    # Tests: enterprise protocol, account manager awareness, big money handling
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T11",
        "name": "Enterprise Top Account — API Issue",
        "customer_id": "CUST-1006",
        "channel": "email",
        "message": (
            "Our API access tier (ORD-2052) is still showing as processing after 11 days. "
            "We have 200 seats depending on this integration for our Q3 launch. This is "
            "blocking our development timeline. We need this resolved today."
        ),
        "expected_intent": "technical_support",
        "expected_complexity": "complex",
        "expected_actions": ["modify_account", "escalate_to_human"],
        "expected_outcome": "API access activated or escalated with urgency",
        "variant_expectations": {
            "mini": "RECOMMEND escalation to account manager",
            "parwa": "Activate API access + notify account manager",
            "high": "Immediate activation + account manager notification + SLA acknowledgment",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 12: Vague Complaint — Needs Clarification
    # Tests: intent classification accuracy, clarification handling
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T12",
        "name": "Vague Complaint — Needs Clarification",
        "customer_id": "CUST-1002",
        "channel": "chat",
        "message": "Something is wrong with my account. Things aren't working right.",
        "expected_intent": "general_inquiry",
        "expected_complexity": "simple",
        "expected_actions": ["send_reply"],
        "expected_outcome": "Ask for clarification about what specifically isn't working",
        "variant_expectations": {
            "mini": "Ask for details + share FAQ",
            "parwa": "Ask for details + pull account info to anticipate",
            "high": "Pull account info + proactively check for known issues",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 13: Password Reset + Account Access
    # Tests: account modification, security protocol
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T13",
        "name": "Password Reset Request",
        "customer_id": "CUST-1004",
        "channel": "email",
        "message": (
            "I can't log into my account. I think someone may have changed my password. "
            "Can you help me reset it? My email is chen.wei@tech.cn"
        ),
        "expected_intent": "account_modification",
        "expected_complexity": "simple",
        "expected_actions": ["modify_account", "send_reply"],
        "expected_outcome": "Password reset link sent + security verification note",
        "variant_expectations": {
            "mini": "Send reset link, RECOMMEND security review",
            "parwa": "Send reset link + add security note to account",
            "high": "Reset link + security note + proactive account monitoring",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 14: Refund Policy Question — FAQ Match
    # Tests: FAQ matching, policy sharing, simple resolution
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T14",
        "name": "Refund Policy Question",
        "customer_id": "CUST-1005",
        "channel": "chat",
        "message": (
            "What's your refund policy? I'm thinking about buying the mechanical keyboard "
            "but want to make sure I can return it if I don't like it."
        ),
        "expected_intent": "faq_question",
        "expected_complexity": "simple",
        "expected_actions": ["share_faq", "share_policy"],
        "expected_outcome": "Share refund policy FAQ + specific return window for keyboard",
        "variant_expectations": {
            "mini": "Share FAQ + policy — same for all variants",
            "parwa": "Share FAQ + policy + product-specific details",
            "high": "Share FAQ + policy + product details + proactive recommendation",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 15: Long-Time Customer with Multiple Open Issues
    # Tests: churn risk detection, proactive insights, customer retention
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T15",
        "name": "Frustrated Loyal Customer — Multiple Issues",
        "customer_id": "CUST-1007",
        "channel": "email",
        "message": (
            "This is the third email I'm sending. My plugin keeps crashing (ticket TKT-4040), "
            "my license won't activate (ticket TKT-4041), and nobody has responded to either ticket "
            "in days. I've been a loyal customer for 3 years and I'm seriously considering switching "
            "to your competitor. This level of support is unacceptable for a premium subscriber."
        ),
        "expected_intent": "complaint",
        "expected_complexity": "complex",
        "expected_actions": ["escalate_to_human", "modify_account"],
        "expected_outcome": "Escalate due to multiple unresolved tickets + retention effort",
        "variant_expectations": {
            "mini": "Escalate to human + empathize",
            "parwa": "Escalate + offer partial credit + acknowledge open tickets",
            "high": "Priority escalation + free month + dedicated support + account manager alert",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 16: Warranty Claim on Expired Warranty
    # Tests: edge case — policy enforcement, knowledge base accuracy
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T16",
        "name": "Warranty Claim — Outside Warranty Period",
        "customer_id": "CUST-1002",
        "channel": "email",
        "message": (
            "My Bluetooth Speaker (ORD-2010) has stopped working after 7 months. "
            "I'd like to file a warranty claim. How do I proceed?"
        ),
        "expected_intent": "technical_support",
        "expected_complexity": "simple",
        "expected_actions": ["share_faq", "send_reply"],
        "expected_outcome": "Warranty covers 24 months — claim is valid, provide instructions",
        "variant_expectations": {
            "mini": "Share warranty FAQ + claim instructions",
            "parwa": "Verify warranty status + share claim process",
            "high": "Verify warranty + file claim + offer immediate support",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 17: Voice Channel — High Variant Only
    # Tests: channel permissions, variant-aware routing
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T17",
        "name": "Voice Channel — High Only",
        "customer_id": "CUST-1001",
        "channel": "voice",
        "message": (
            "Hi, I'm calling about my recent order. The tracking number TRK-88292 "
            "hasn't updated in 2 days and I need to know where my package is."
        ),
        "expected_intent": "order_status",
        "expected_complexity": "simple",
        "expected_actions": ["send_reply"],
        "expected_outcome": "Order status provided; voice channel handled by High variant only",
        "variant_expectations": {
            "mini": "DENIED — voice channel not available for Mini",
            "parwa": "DENIED — voice channel not available for PARWA",
            "high": "EXECUTE — voice channel supported, provide order status",
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TICKET 18: Bulk Operation Request — High Only
    # Tests: BULK_OPERATION permission, variant differentiation
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T18",
        "name": "Bulk License Upgrade — High Only",
        "customer_id": "CUST-1006",
        "channel": "email",
        "message": (
            "We need to upgrade 200 seats from Basic to Enterprise and also add the API "
            "Tier 3 access. Can you process this as a bulk operation? We need it done by end of week."
        ),
        "expected_intent": "account_modification",
        "expected_complexity": "complex",
        "expected_actions": ["bulk_operation", "modify_account"],
        "expected_outcome": "Bulk seat upgrade processed (High) or denied (Mini/PARWA)",
        "variant_expectations": {
            "mini": "DENY bulk operation — not available, RECOMMEND alternative",
            "parwa": "DENY bulk operation — suggest contacting sales",
            "high": "EXECUTE bulk upgrade + API access + account manager notification",
        },
    },
]


def get_tickets() -> list[dict[str, Any]]:
    """Get all test tickets."""
    return TICKETS


def get_ticket(ticket_id: str) -> dict[str, Any] | None:
    """Get a specific test ticket by ID."""
    for t in TICKETS:
        if t["id"] == ticket_id:
            return t
    return None


def get_tickets_by_complexity(complexity: str) -> list[dict[str, Any]]:
    """Get tickets filtered by expected complexity."""
    return [t for t in TICKETS if t.get("expected_complexity") == complexity]


def get_tickets_by_intent(intent: str) -> list[dict[str, Any]]:
    """Get tickets filtered by expected intent."""
    return [t for t in TICKETS if t.get("expected_intent") == intent]
