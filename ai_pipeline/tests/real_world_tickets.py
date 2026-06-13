"""Real-world fake test tickets for PARWA variant testing.

These are complicated, realistic customer support tickets that exercise
different aspects of the PARWA pipeline across all 3 variants.
"""

from __future__ import annotations

from typing import Any


TICKETS: list[dict[str, Any]] = [
    {
        "id": "REAL-001",
        "name": "Duplicate Charge Refund",
        "raw_message": (
            "Hi, I was checking my bank statement and noticed I've been charged "
            "twice for the same order. Order #ORD-78234 shows a charge of $149.99 "
            "on January 5th and again on January 5th. I only placed this order once. "
            "This is really frustrating as it's caused an overdraft fee on my account. "
            "I need this fixed immediately — the duplicate $149.99 needs to be refunded "
            "and I should be compensated for the $35 overdraft fee your double charge caused."
        ),
        "customer_id": "CUST-44921",
        "channel": "email",
        "expected_intent": "refund_request",
        "expected_complexity": "medium",
        "variant_expectations": {
            "mini": {"action_status": "recommended", "model_tier": "light", "response_contains": "submitted for approval"},
            "parwa": {"action_status": "executed", "model_tier": "medium", "response_contains": "refund has been processed"},
            "high": {"action_status": "executed", "model_tier": "medium", "response_contains": "refund has been processed"},
        },
    },
    {
        "id": "REAL-002",
        "name": "Angry Customer Legal Threat",
        "raw_message": (
            "This is completely UNACCEPTABLE! I have been waiting 3 weeks for my order "
            "and nobody has given me a straight answer. Your customer service rep 'Sarah' "
            "promised me a refund last week and NOTHING happened. I've been a customer for "
            "5 years and this is how you treat loyalty? I'm contacting my attorney if this "
            "isn't resolved by end of day. Order #ORD-99123. I want a FULL refund of $899.99 "
            "PLUS compensation for my time. This is FRAUD."
        ),
        "customer_id": "CUST-77832",
        "channel": "email",
        "expected_intent": "escalation",
        "expected_complexity": "critical",
        "variant_expectations": {
            "mini": {"action_status": "recommended", "should_escalate": True, "model_tier": "light"},
            "parwa": {"action_status": "executed", "should_escalate": True, "model_tier": "medium"},
            "high": {"action_status": "executed", "should_escalate": True, "model_tier": "medium"},
        },
    },
    {
        "id": "REAL-003",
        "name": "Social Media Complaint",
        "raw_message": (
            "@YourCompany Your product arrived DAMAGED! The screen on my new tablet "
            "is cracked right out of the box. This is the worst unboxing experience ever. "
            "I paid $599 for a BROKEN product. Need a replacement ASAP or I'm posting "
            "this everywhere. #disappointed #customercare"
        ),
        "customer_id": "CUST-33201",
        "channel": "social",
        "expected_intent": "complaint",
        "expected_complexity": "medium",
        "variant_expectations": {
            "mini": {"channel_blocked": True, "channel_fallback": "email", "action_status": "recommended"},
            "parwa": {"channel_blocked": False, "action_status": "executed"},
            "high": {"channel_blocked": False, "action_status": "executed"},
        },
    },
    {
        "id": "REAL-004",
        "name": "Voice Call Request",
        "raw_message": (
            "I need to speak with someone about my account. There are unauthorized "
            "charges on my account and I need to change my payment method immediately. "
            "I don't feel comfortable typing my card details — can someone call me? "
            "My number is on file. This is urgent."
        ),
        "customer_id": "CUST-55421",
        "channel": "voice",
        "expected_intent": "account_modification",
        "expected_complexity": "medium",
        "variant_expectations": {
            "mini": {"channel_blocked": True, "voice_action_denied": True, "channel_fallback": "email"},
            "parwa": {"channel_blocked": True, "voice_action_denied": True, "channel_fallback": "email"},
            "high": {"channel_blocked": False, "voice_action_executed": True},
        },
    },
    {
        "id": "REAL-005",
        "name": "Complex Technical Issue",
        "raw_message": (
            "I'm a developer using your API platform. Since the v3.2 update, I'm getting "
            "intermittent 503 errors on the /api/v3/users endpoint. It happens roughly "
            "every 1 in 50 requests. My error logs show the response time spikes from "
            "200ms to 30s before the 503. I've tried: 1) Regenerating API keys, "
            "2) Switching from us-east to eu-west region, 3) Using the v2 endpoint "
            "(which works fine). This is affecting my production app with 10k daily users. "
            "Can you check if there's a rate-limiting issue or if your v3 infrastructure "
            "has a known problem?"
        ),
        "customer_id": "CUST-DEV-001",
        "channel": "chat",
        "expected_intent": "technical_support",
        "expected_complexity": "complex",
        "variant_expectations": {
            "mini": {"model_tier": "light", "api_webhook_action": "denied"},
            "parwa": {"model_tier": "medium", "api_webhook_action": "executed"},
            "high": {"model_tier": "medium", "api_webhook_action": "executed"},
        },
    },
    {
        "id": "REAL-006",
        "name": "Billing Dispute Multiple Charges",
        "raw_message": (
            "I subscribed to your Pro plan at $49.99/month but my credit card shows "
            "3 charges: $49.99 on Jan 1, $74.99 on Jan 15, and $49.99 on Jan 28. "
            "I never upgraded or changed my plan. Looking at your pricing page, $74.99 "
            "is the Business tier which I never signed up for. Also, the Jan 28 charge "
            "is way too early — my billing cycle should be Feb 1. I want ALL incorrect "
            "charges reversed and an explanation of how this happened."
        ),
        "customer_id": "CUST-66210",
        "channel": "email",
        "expected_intent": "billing_issue",
        "expected_complexity": "complex",
        "variant_expectations": {
            "mini": {"refund_action": "recommended", "model_tier": "light"},
            "parwa": {"refund_action": "executed", "model_tier": "medium"},
            "high": {"refund_action": "executed", "model_tier": "medium"},
        },
    },
    {
        "id": "REAL-007",
        "name": "Order Cancellation Request",
        "raw_message": (
            "I need to cancel my order #ORD-44521 immediately. I found the same product "
            "cheaper on another site. The order hasn't shipped yet according to my tracking. "
            "Please cancel and confirm. Also, if any payment was already taken, I need it "
            "refunded to my original payment method."
        ),
        "customer_id": "CUST-22198",
        "channel": "chat",
        "expected_intent": "cancellation",
        "expected_complexity": "simple",
        "variant_expectations": {
            "mini": {"cancel_action": "recommended", "refund_action": "recommended"},
            "parwa": {"cancel_action": "executed", "refund_action": "executed"},
            "high": {"cancel_action": "executed", "refund_action": "executed"},
        },
    },
    {
        "id": "REAL-008",
        "name": "Bulk User Migration Request",
        "raw_message": (
            "We're migrating 500 user accounts from our old system to your platform. "
            "I need the bulk import API endpoint and a webhook to notify our system "
            "when each user is successfully created. Also, can I get analytics access "
            "to track the migration progress? This is for our enterprise account."
        ),
        "customer_id": "CUST-ENT-001",
        "channel": "email",
        "expected_intent": "general_inquiry",
        "expected_complexity": "complex",
        "variant_expectations": {
            "mini": {"bulk_action": "denied", "webhook_action": "denied", "analytics_action": "denied"},
            "parwa": {"bulk_action": "denied", "webhook_action": "executed", "analytics_action": "denied"},
            "high": {"bulk_action": "executed", "webhook_action": "executed", "analytics_action": "executed"},
        },
    },
    {
        "id": "REAL-009",
        "name": "Simple FAQ Question",
        "raw_message": (
            "What is your return policy? I bought a product last week and want to know "
            "if I can still return it."
        ),
        "customer_id": "CUST-99123",
        "channel": "chat",
        "expected_intent": "faq_question",
        "expected_complexity": "simple",
        "variant_expectations": {
            "mini": {"action_status": "executed", "model_tier": "light"},
            "parwa": {"action_status": "executed", "model_tier": "light"},
            "high": {"action_status": "executed", "model_tier": "light"},
        },
    },
    {
        "id": "REAL-010",
        "name": "GDPR Data Deletion Request",
        "raw_message": (
            "Under GDPR Article 17, I am exercising my right to erasure. My name is "
            "Jan Mueller, email jan.mueller@example.de, customer ID DE-44921. I want "
            "ALL my personal data deleted from your systems within 30 days as required "
            "by law. This includes: account details, order history, support tickets, "
            "and any analytics data you've collected. Please confirm in writing once "
            "complete. My phone number is +49 170 1234567 if you need to verify."
        ),
        "customer_id": "CUST-DE-44921",
        "channel": "email",
        "expected_intent": "account_modification",
        "expected_complexity": "critical",
        "variant_expectations": {
            "mini": {"pii_detected": True, "model_tier": "light", "modify_account_action": "recommended"},
            "parwa": {"pii_detected": True, "model_tier": "medium", "modify_account_action": "executed"},
            "high": {"pii_detected": True, "model_tier": "medium", "modify_account_action": "executed"},
        },
    },
]


def get_ticket(ticket_id: str) -> dict[str, Any] | None:
    """Get a test ticket by ID."""
    for ticket in TICKETS:
        if ticket["id"] == ticket_id:
            return ticket
    return None


def get_variant_test_cases(variant: str) -> list[dict[str, Any]]:
    """Get test cases relevant to a specific variant."""
    results = []
    for ticket in TICKETS:
        expectations = ticket.get("variant_expectations", {}).get(variant, {})
        results.append({
            "ticket_id": ticket["id"],
            "name": ticket["name"],
            "raw_message": ticket["raw_message"],
            "channel": ticket["channel"],
            "expected_intent": ticket["expected_intent"],
            "expected_complexity": ticket["expected_complexity"],
            "variant_expectations": expectations,
        })
    return results
