"""Month 4 Realistic Test Tickets — 15 comprehensive variant-comparison tickets.

Each ticket is designed to stress-test the 3 PARWA variants (mini, parwa, high)
across all 10 support categories. Tickets use real customer IDs from the fake CRM
and contain realistic customer messages with edge cases that trip up AI systems.

Categories (min 2 tickets per, except 1-ticket categories):
    1. Simple FAQ          (2) — Return policy, business hours
    2. Order Status        (2) — Tracking request, missing order
    3. Refund Request      (2) — Duplicate charge, defective product
    4. Billing Issue       (2) — Unauthorized charge, mystery subscription
    5. Technical Support   (1) — App crash
    6. Cancellation        (1) — Cancel order
    7. Account Modification(1) — Upgrade plan
    8. Complaint           (1) — Service quality
    9. Escalation          (1) — Legal threat
   10. Ambiguous/Multi-intent(2) — Cancel+refund, angry+technical

Customer mapping (from fake_crm/database.py):
    CUST-1001: Priya Sharma — premium, active, duplicate charge on ORD-2001
    CUST-1002: Marcus Johnson — standard, active, cancelled order ORD-2011
    CUST-1003: Aisha Patel — enterprise, active, $28,750 LTV, pending invoice
    CUST-1004: Chen Wei — premium, suspended, failed payment, card declined 3x
    CUST-1005: Sarah Mitchell — standard, active, shipped orders with tracking
    CUST-1006: Rajesh Kumar — enterprise, active, $52,300 LTV, top 5 account
    CUST-1007: Emily Rodriguez — premium, active, 2 open tech tickets, frustrated
    CUST-1008: Yuki Tanaka — standard, active, returned defective monitor
"""

from __future__ import annotations

from typing import Any


# ════════════════════════════════════════════════════════════════════════════════
# MONTH 4 TEST TICKETS — 15 realistic support interactions
# ════════════════════════════════════════════════════════════════════════════════

MONTH4_TICKETS: list[dict[str, Any]] = [


    # ═══════════════════════════════════════════════════════════════════════════
    # 1. SIMPLE FAQ (2 tickets)
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "M4-001",
        "message": (
            "Hi there, I bought a Mechanical Keyboard from you guys about a week ago and I'm "
            "thinking it might not be the right fit for my setup. Could you tell me what your "
            "return policy is? Like how many days do I have to send it back, and do I need to "
            "pay for return shipping? I checked the website but the policy page was kind of "
            "confusing with all the different timeframes for different products. Just want to "
            "make sure I understand before I decide what to do. Thanks!"
        ),
        "customer_id": "CUST-1005",
        "variant": "parwa",
        "expected_intent": "faq_question",
        "expected_sentiment": "neutral",
        "expected_escalation": False,
        "expected_action": "share_faq",
        "difficulty": "simple",
        "category": "simple_faq",
        "notes": "Straightforward FAQ — all variants should handle this. Tests whether the system shares the correct return policy FAQ vs hallucinating one.",
    },

    {
        "id": "M4-002",
        "message": (
            "What are your customer support hours? I've been trying to reach someone all day "
            "and keep getting the automated system. I need to talk to a real person about my "
            "account. Is there a phone number I can call, or are you only available by email? "
            "Also do you have different hours on weekends? I work during the week so weekend "
            "support would be really helpful for me."
        ),
        "customer_id": "CUST-1002",
        "variant": "parwa",
        "expected_intent": "faq_question",
        "expected_sentiment": "frustrated",
        "expected_escalation": False,
        "expected_action": "share_faq",
        "difficulty": "simple",
        "category": "simple_faq",
        "notes": "FAQ with mild frustration — shouldn't escalate, but sentiment should register as frustrated. Tests FAQ matching with emotional overlay.",
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # 2. ORDER STATUS (2 tickets)
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "M4-003",
        "message": (
            "I placed an order for a Mechanical Keyboard and a Mouse Pad on June 10th and "
            "I got a shipping confirmation with tracking number TRK-55401. It's now been 3 "
            "days and the tracking hasn't updated at all since the initial scan. The estimated "
            "delivery was supposed to be June 14th. Can you check where my package actually is? "
            "This was supposed to be a birthday gift and I'm running out of time. I really "
            "need to know if it's going to arrive on time or if I should make other arrangements."
        ),
        "customer_id": "CUST-1005",
        "variant": "parwa",
        "expected_intent": "order_status",
        "expected_sentiment": "frustrated",
        "expected_escalation": False,
        "expected_action": "send_reply",
        "difficulty": "medium",
        "category": "order_status",
        "notes": "Order status with specific tracking number and real CRM data (Sarah's ORD-2040/2041). Tests whether the system looks up the actual order and tracking info rather than giving a generic response.",
    },

    {
        "id": "M4-004",
        "message": (
            "Hey, I ordered a Laptop Stand over a week ago and I still haven't received it. "
            "My order number is ORD-2003. When I check online it just says 'processing' but "
            "there's no tracking number yet. Is something wrong with my order? This is really "
            "frustrating because I paid for it on June 8th and it feels like nothing has "
            "happened since then. At this point I'm wondering if I should just cancel and "
            "get it somewhere else."
        ),
        "customer_id": "CUST-1001",
        "variant": "parwa",
        "expected_intent": "order_status",
        "expected_sentiment": "frustrated",
        "expected_escalation": False,
        "expected_action": "send_reply",
        "difficulty": "medium",
        "category": "order_status",
        "notes": "Processing order with no tracking — customer hints at cancellation but actual intent is status check. Premium customer (Priya). Tests whether system detects the real intent (order_status) vs misclassifying as cancellation.",
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # 3. REFUND REQUEST (2 tickets)
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "M4-005",
        "message": (
            "I was looking at my credit card statement and I noticed I was charged $189.99 "
            "TWICE for the same order on June 1st. Both charges are from your company and "
            "they're on the exact same date for the exact same amount. I only placed one "
            "order for Premium Headphones and a USB-C Cable. This is clearly a mistake on "
            "your end and I need one of those charges reversed immediately. I've been a loyal "
            "customer for over 3 years and this kind of billing error is really disappointing. "
            "Please refund the duplicate charge as soon as possible."
        ),
        "customer_id": "CUST-1001",
        "variant": "parwa",
        "expected_intent": "refund_request",
        "expected_sentiment": "frustrated",
        "expected_escalation": False,
        "expected_action": "process_refund",
        "difficulty": "medium",
        "category": "refund_request",
        "notes": "Duplicate charge — CRM confirms PAY-3001 and PAY-3002 are both $189.99 on same date. KB-001 says duplicate charges should be refunded immediately. Tests whether system actually verifies CRM data before recommending refund. Mini can only RECOMMEND; Parwa recommends with reasoning; High can EXECUTE after approval.",
    },

    {
        "id": "M4-006",
        "message": (
            "I purchased the Design Software License with the Plugin Pack on May 30th and the "
            "plugin keeps crashing every single time I try to open it. I've reinstalled it "
            "three times, tried on two different computers, and it still crashes. I've already "
            "submitted a support ticket about this (TKT-4040) but nobody has fixed it. At this "
            "point the software is completely unusable for me and I want a full refund of "
            "$249.98. I can't keep waiting for a fix that may never come — I have deadlines "
            "and I've already lost days of work because of this broken product."
        ),
        "customer_id": "CUST-1007",
        "variant": "parwa",
        "expected_intent": "refund_request",
        "expected_sentiment": "angry",
        "expected_escalation": False,
        "expected_action": "process_refund",
        "difficulty": "complex",
        "category": "refund_request",
        "notes": "Defective software refund — has open ticket TKT-4040. Angry sentiment + refund request. KB-006 says defective products get immediate replacement or refund. Tests whether system connects existing ticket to refund request, and whether it detects angry sentiment correctly. Also tests whether Mini recommends vs Parwa/High actually processes.",
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # 4. BILLING ISSUE (2 tickets)
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "M4-007",
        "message": (
            "I just noticed a charge of $59.99 on my credit card from your company that I "
            "did not authorize. I haven't purchased anything recently and I definitely didn't "
            "sign up for any subscription. My card ending in 1122 was charged on June 15th "
            "and I have no idea what this is for. I want this charge removed right away and "
            "I need to make sure no further charges are made to my card. This feels like "
            "fraud and I'm very concerned about the security of my payment information."
        ),
        "customer_id": "CUST-1004",
        "variant": "parwa",
        "expected_intent": "billing_issue",
        "expected_sentiment": "angry",
        "expected_escalation": True,
        "expected_action": "escalate",
        "difficulty": "complex",
        "category": "billing_issue",
        "notes": "Unauthorized charge on a suspended account — CUST-1004's card was actually declined (PAY-3031) and account is suspended. The $59.99 matches Pro Monthly subscription. This is tricky: the charge failed, so the customer's claim about an 'unauthorized charge' conflicts with CRM data (payment failed). Tests whether system checks CRM payments before acting. Also tests escalation because of fraud/security concern.",
    },

    {
        "id": "M4-008",
        "message": (
            "Why am I being charged $9.99 every month? I don't remember signing up for any "
            "monthly subscription. I bought a Portable Monitor from you a while back and "
            "that was supposed to be a one-time purchase. Now I keep seeing this recurring "
            "charge on my statement. I never agreed to a monthly plan. Please cancel whatever "
            "subscription this is and refund the last 3 months of charges. This is really "
            "sneaky to sign people up for recurring billing without their consent."
        ),
        "customer_id": "CUST-1008",
        "variant": "parwa",
        "expected_intent": "billing_issue",
        "expected_sentiment": "frustrated",
        "expected_escalation": False,
        "expected_action": "modify_account",
        "difficulty": "medium",
        "category": "billing_issue",
        "notes": "Mystery subscription — CUST-1008 has 'Basic Monthly' at $9.99. Customer doesn't realize they have a subscription. Tests whether system explains the subscription vs just cancelling. Sarcasm ('really sneaky') tests sentiment detection. Modify account needed to cancel subscription.",
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # 5. TECHNICAL SUPPORT (1 ticket)
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "M4-009",
        "message": (
            "Your app keeps crashing every time I try to export a project. I'm using version "
            "3.2.1 on Windows 11 and the crash happens consistently when I click File > Export "
            "> PDF. I get an error message that says 'Runtime Error: Memory allocation failed' "
            "and then the whole app closes. This has been happening for the past week. I've "
            "tried clearing the cache, running as administrator, and even reinstalling, but "
            "nothing works. I have the Design Software License and this is blocking my work "
            "entirely. Can someone please help me fix this?"
        ),
        "customer_id": "CUST-1007",
        "variant": "parwa",
        "expected_intent": "technical_support",
        "expected_sentiment": "frustrated",
        "expected_escalation": False,
        "expected_action": "send_reply",
        "difficulty": "medium",
        "category": "technical_support",
        "notes": "Detailed bug report with specific steps to reproduce. CUST-1007 has Design Software License and open tickets. Tests whether system provides actual troubleshooting steps vs generic 'try restarting' response. Also tests whether it connects to existing open tickets.",
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # 6. CANCELLATION (1 ticket)
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "M4-010",
        "message": (
            "I'd like to cancel my order ORD-2003 for the Laptop Stand. It's been sitting in "
            "'processing' for days and I haven't received any shipping confirmation. I've "
            "changed my mind and I don't need it anymore. Since it hasn't shipped yet, I "
            "should be able to cancel it and get a full refund of $79.99, right? Please "
            "process this cancellation as soon as possible. I paid via PayPal if that matters "
            "for the refund timeline."
        ),
        "customer_id": "CUST-1001",
        "variant": "parwa",
        "expected_intent": "cancellation",
        "expected_sentiment": "neutral",
        "expected_escalation": False,
        "expected_action": "cancel_order",
        "difficulty": "medium",
        "category": "cancellation",
        "notes": "Cancellation for processing order — ORD-2003 is indeed still in 'processing' with no tracking. KB-003 says orders can be cancelled before shipping. Payment was PayPal (PAY-3004). Tests whether system verifies order status before cancelling. Premium customer. Mini can only recommend, Parwa recommends, High can execute after approval.",
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # 7. ACCOUNT MODIFICATION (1 ticket)
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "M4-011",
        "message": (
            "I need to make a couple of changes to my account. First, I'd like to add 10 more "
            "seats to my Enterprise plan — we've hired new team members and our current 50-seat "
            "license isn't enough anymore. Second, our billing contact has changed — please "
            "update the billing email from the current one to billing@company.co.in. I also "
            "have a pending order ORD-2021 for additional seats — can you confirm that's still "
            "being processed? We need those licenses urgently as our new hires start next Monday."
        ),
        "customer_id": "CUST-1003",
        "variant": "parwa",
        "expected_intent": "account_modification",
        "expected_sentiment": "neutral",
        "expected_escalation": False,
        "expected_action": "modify_account",
        "difficulty": "complex",
        "category": "account_modification",
        "notes": "Multi-part account modification — enterprise customer (Aisha Patel) with $28,750 LTV. Wants seat increase + billing email change + order status check on ORD-2021. Tests multi-intent handling within account_modification. Enterprise accounts need account manager per KB-007/KB-009.",
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # 8. COMPLAINT (1 ticket)
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "M4-012",
        "message": (
            "I have to say, the level of service I've received lately has been absolutely "
            "terrible. First, my custom integration stopped working and it took 2 weeks to "
            "get it fixed. Then when I finally got someone on the support team, they had no "
            "idea about our enterprise setup and treated me like a basic customer. I pay "
            "$4,999 a month for Enterprise Plus with a 1-hour SLA, and I'm getting responses "
            "3 days later. Our dedicated team is supposed to be Sunita and Arjun, but I've "
            "been dealing with random agents who don't know our account. This is not what we "
            "agreed to in our contract. Something needs to change or we'll be looking at "
            "other vendors."
        ),
        "customer_id": "CUST-1006",
        "variant": "parwa",
        "expected_intent": "complaint",
        "expected_sentiment": "angry",
        "expected_escalation": True,
        "expected_action": "escalate",
        "difficulty": "critical",
        "category": "complaint",
        "notes": "Enterprise complaint — CUST-1006 is top 5 account ($52,300 LTV). References specific SLA (1hr response), dedicated team (Sunita + Arjun), and contract terms. Legal/business threat ('looking at other vendors'). Tests whether system recognizes enterprise SLA violations and escalates appropriately. Should NOT try to resolve with a simple apology.",
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # 9. ESCALATION (1 ticket)
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "M4-013",
        "message": (
            "This is the third time I'm contacting you about my suspended account and I've "
            "had enough. My account has been suspended for over a week because of a billing "
            "error on YOUR end — your system tried to charge an expired card that I never "
            "authorized for the subscription renewal. I never even wanted the Pro Monthly "
            "plan, someone from your team signed me up for it without my consent. I've "
            "already spoken to my attorney about this situation. If my account is not "
            "reactivated and this unauthorized charge removed within 24 hours, I will be "
            "filing a formal complaint with the consumer protection board and pursuing legal "
            "action. This is completely unacceptable."
        ),
        "customer_id": "CUST-1004",
        "variant": "parwa",
        "expected_intent": "escalation",
        "expected_sentiment": "angry",
        "expected_escalation": True,
        "expected_action": "escalate",
        "difficulty": "critical",
        "category": "escalation",
        "notes": "Legal threat + attorney mention — mandatory escalation per KB-008. CUST-1004 is suspended with failed payment. Complex: account suspension + billing dispute + legal threat. Tests whether system immediately escalates vs trying to resolve. Attorney/lawyer keywords must trigger escalation regardless of other factors.",
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # 10. AMBIGUOUS / MULTI-INTENT (2 tickets)
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "M4-014",
        "message": (
            "I want to cancel my Smart Watch order and get my money back. I ordered it on "
            "June 2nd but then I found a better price somewhere else. The order status says "
            "'cancelled' already but I haven't received my refund of $299.99 yet. It's been "
            "almost two weeks! If the order is already cancelled then where is my refund? I "
            "paid with my debit card ending in 8901. Either give me my money back or I'm "
            "going to dispute the charge with my bank. This should not take this long."
        ),
        "customer_id": "CUST-1002",
        "variant": "parwa",
        "expected_intent": "refund_request",
        "expected_sentiment": "frustrated",
        "expected_escalation": False,
        "expected_action": "process_refund",
        "difficulty": "complex",
        "category": "ambiguous_multi_intent",
        "notes": "Multi-intent: cancellation + refund — but order ORD-2011 is ALREADY cancelled and payment PAY-3011 is already refunded! The customer doesn't know the refund was processed. Tests whether system checks CRM to see the refund already exists and informs the customer vs initiating a duplicate refund. Primary intent is actually refund_request (they want their money), not cancellation (already done).",
    },

    {
        "id": "M4-015",
        "message": (
            "I am SO DONE with this. Your stupid software crashes every time I try to use it "
            "and nobody from support has bothered to respond to my ticket from last week. "
            "I have TWO open tickets — one for the plugin crash and one for the license "
            "activation issue — and nobody seems to care. I pay for Creative Pro every month "
            "and I can't even use the product! At the same time, I just noticed my renewal "
            "is coming up on July 20th and honestly, why would I even renew if this is the "
            "garbage support I get? Fix my technical issues AND explain why I should stay, "
            "or I'm done with your company."
        ),
        "customer_id": "CUST-1007",
        "variant": "parwa",
        "expected_intent": "complaint",
        "expected_sentiment": "angry",
        "expected_escalation": True,
        "expected_action": "escalate",
        "difficulty": "critical",
        "category": "ambiguous_multi_intent",
        "notes": "Triple intent: technical_support + complaint + implicit cancellation threat. CUST-1007 has 2 open tickets (TKT-4040, TKT-4041) and Creative Pro subscription renewing July 20. Angry + multiple unresolved tickets = escalation per KB-008 (3+ unresolved tickets). Tests whether system: (1) identifies primary intent as complaint, (2) detects escalation triggers, (3) addresses all 3 issues vs just one, (4) recognizes the retention risk.",
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # 11. NIGHTMARE TICKET — The ultimate variant killer (1 ticket)
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "M4-016",
        "message": (
            "Hi, I noticed something odd on my account and I'm hoping someone can clarify. "
            "I see a pending charge of $249.98 on my card ending in 7788 from May 30th — I "
            "believe that was for the Design Software License and Plugin Pack I ordered, which "
            "is fine. But here's the thing: the plugin has never worked. I submitted ticket "
            "TKT-4040 on June 5th about it crashing, and then another ticket TKT-4041 on "
            "June 8th because my license won't even activate properly. That was over a week "
            "ago. Nobody has responded to either ticket. Not even an acknowledgment.\n\n"
            "Now I'm in this strange situation where I'm paying $29.99/month for Creative Pro "
            "and I can't use any of it. The software I bought for $249.98 doesn't work. My "
            "open tickets are being ignored. And my subscription renews on July 20th — what "
            "exactly am I subscribing to if nothing functions?\n\n"
            "I've been a loyal customer for 3 years and this is the first time I've felt "
            "completely dismissed. I read somewhere that consumers have rights when products "
            "fail to perform as advertised, and I'm starting to understand why people pursue "
            "those options. I don't want to go down that road, but I also can't keep paying "
            "for something that doesn't work while being ignored.\n\n"
            "I need someone to: 1) explain why my tickets have been ignored for a week, "
            "2) either fix the software or refund the $249.98, and 3) tell me why I should "
            "trust that my Creative Pro subscription is worth keeping. A real response this "
            "time, please — not an automated acknowledgment."
        ),
        "customer_id": "CUST-1007",
        "variant": "parwa",
        "expected_intent": "complaint",
        "expected_sentiment": "angry",
        "expected_escalation": True,
        "expected_action": "escalate",
        "difficulty": "critical",
        "category": "nightmare_multi_intent",
        "notes": (
            "THE ULTIMATE VARIANT KILLER. This ticket is designed to trip up ALL variants: "
            "TRAP 1 (Intent): Starts with 'I noticed something odd' and mentions billing first — "
            "misleads into billing_issue or refund_request, but the PRIMARY intent is complaint "
            "(about ignored tickets, broken product, and dismissive service). "
            "TRAP 2 (Sentiment): Uses polite language ('hoping someone can clarify', 'please') "
            "but is deeply angry — subtle consumer rights threat, sarcasm ('what exactly am I "
            "subscribing to'), and 'completely dismissed' language. Tests if LLM reads tone or words. "
            "TRAP 3 (Escalation): 2 OPEN TICKETS (TKT-4040, TKT-4041) + this new one = 3+ unresolved. "
            "KB-008 says 3+ unresolved = mandatory escalation. Also mentions consumer rights = legal "
            "threat trigger. Also premium customer ($2,100 LTV) = VIP protocol KB-009. "
            "TRAP 4 (Action): Should ESCALATE, not process_refund or send_reply. System must "
            "recognize that with 3+ unresolved tickets + premium customer + legal hint = human needed. "
            "TRAP 5 (Multi-intent): billing inquiry + refund request + complaint + technical issue + "
            "retention risk — system must identify COMPLAINT as primary, not get distracted by billing. "
            "Mini should FAIL (no escalation node), Parwa might MISS the subtle escalation triggers, "
            "High should PASS (has full escalation + PII + VIP detection)."
        ),
    },
]


# ════════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

def get_tickets_by_category(category: str) -> list[dict[str, Any]]:
    """Filter tickets by category."""
    return [t for t in MONTH4_TICKETS if t["category"] == category]


def get_tickets_by_difficulty(difficulty: str) -> list[dict[str, Any]]:
    """Filter tickets by difficulty level."""
    return [t for t in MONTH4_TICKETS if t["difficulty"] == difficulty]


def get_ticket_by_id(ticket_id: str) -> dict[str, Any] | None:
    """Get a specific ticket by ID."""
    return next((t for t in MONTH4_TICKETS if t["id"] == ticket_id), None)


def get_dataset_stats() -> dict[str, Any]:
    """Get summary statistics about the Month 4 ticket dataset."""
    categories: dict[str, int] = {}
    difficulties: dict[str, int] = {}
    escalation_count = 0
    sentiment_counts: dict[str, int] = {}
    intent_counts: dict[str, int] = {}

    for ticket in MONTH4_TICKETS:
        cat = ticket["category"]
        categories[cat] = categories.get(cat, 0) + 1

        diff = ticket["difficulty"]
        difficulties[diff] = difficulties.get(diff, 0) + 1

        if ticket["expected_escalation"]:
            escalation_count += 1

        sent = ticket["expected_sentiment"]
        sentiment_counts[sent] = sentiment_counts.get(sent, 0) + 1

        intent = ticket["expected_intent"]
        intent_counts[intent] = intent_counts.get(intent, 0) + 1

    return {
        "total_tickets": len(MONTH4_TICKETS),
        "categories": categories,
        "difficulties": difficulties,
        "escalation_rate": round(escalation_count / len(MONTH4_TICKETS) * 100, 1),
        "sentiment_distribution": sentiment_counts,
        "intent_distribution": intent_counts,
        "unique_customers": len({t["customer_id"] for t in MONTH4_TICKETS}),
    }


if __name__ == "__main__":
    import json
    stats = get_dataset_stats()
    print("Month 4 Ticket Dataset Statistics")
    print("=" * 50)
    print(json.dumps(stats, indent=2))
    print(f"\nTickets: {stats['total_tickets']}")
    print(f"Categories: {len(stats['categories'])}")
    print(f"Escalation rate: {stats['escalation_rate']}%")
