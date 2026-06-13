"""Retest V2 — Brand NEW tough test tickets (different from M4-001 to M4-016).

8 tickets designed to test edge cases NOT covered by the Month 4 dataset:
1. SARCASTIC COMPLAINT — Passive-aggressive, hard for sentiment analysis
2. PARTIAL REFUND — Customer wants partial refund, not full
3. SHIPPING DAMAGE — Physical damage claim with replacement vs refund choice
4. ACCOUNT REACTIVATION — Suspended account wants back in + disputes charge
5. MULTI-ORDER STATUS — Customer has multiple orders, wants status on all
6. ENTERPRISE INVOICE DISPUTE — Enterprise disputes a pending invoice
7. SUBSCRIPTION DOWNGRADE + STORED PAYMENT — Downgrade request + expired card
8. THE GASLIGHTER — Customer claims they never ordered something (but CRM says they did)
"""

from __future__ import annotations

from typing import Any


RETEST_V2_TICKETS: list[dict[str, Any]] = [


    # ═══════════════════════════════════════════════════════════════════════════
    # RT2-001: SARCASTIC COMPLAINT — Passive-aggressive, hard for sentiment
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "RT2-001",
        "message": (
            "Oh wow, what a SURPRISE — another email from your company that doesn't "
            "actually solve my problem. How original. I've been waiting for someone — "
            "anyone — to fix the Wireless Charger I bought on June 5th that literally "
            "does not charge anything. It's basically a very expensive paperweight at "
            "this point. But hey, at least your automated reply system works flawlessly, "
            "right? That's something. The charger doesn't work, your support doesn't "
            "work, but those automated 'we received your message' emails? 10 out of 10. "
            "Truly impressive consistency. Anyway, I'd like a replacement or my $49.99 "
            "back. Whichever requires the least amount of human interaction, since that "
            "seems to be in short supply around here."
        ),
        "customer_id": "CUST-1001",
        "variant": "parwa",
        "expected_intent": "refund_request",
        "expected_sentiment": "frustrated",
        "expected_escalation": False,
        "expected_action": "process_refund",
        "difficulty": "medium",
        "category": "sarcastic_complaint",
        "notes": (
            "TRAP: Sentiment is FRUSTRATED with sarcasm, not ANGRY. The customer uses "
            "sarcasm ('Oh wow, what a SURPRISE') and passive-aggressive humor ('10 out of 10') "
            "but is not making threats or using aggressive language. Tests whether LLM reads "
            "actual emotional state vs surface words. ORD-2002 has Wireless Charger at $49.99 "
            "that was shipped. KB-006 says defective products get replacement or refund. "
            "Should NOT escalate — this is a standard refund request with a snarky tone."
        ),
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # RT2-002: PARTIAL REFUND — Customer only wants partial, not full
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "RT2-002",
        "message": (
            "I received my Bluetooth Speaker from order ORD-2010, and it works fine for "
            "the most part, but the Bluetooth range is nowhere near what was advertised. "
            "Your product page says 30 meters, but I can barely get 8 meters before it "
            "starts cutting out. I don't want to return it — I actually like the sound "
            "quality — but this is clearly not as described. I think a partial refund "
            "would be fair here. Maybe refund me 40% since the core feature is defective "
            "but the product is still usable? I paid $129.99 and I'd like about $52 back. "
            "Is that something you can do? I'm not trying to be unreasonable, I just "
            "want fair compensation for a product that doesn't fully match its description."
        ),
        "customer_id": "CUST-1002",
        "variant": "parwa",
        "expected_intent": "refund_request",
        "expected_sentiment": "neutral",
        "expected_intent": "refund_request",
        "expected_sentiment": "neutral",
        "expected_escalation": False,
        "expected_action": "process_refund",
        "difficulty": "medium",
        "category": "partial_refund",
        "notes": (
            "TRICKY: Customer explicitly says they DON'T want a full return/refund — "
            "they want a PARTIAL refund of $52 (40% of $129.99). Tests whether the system "
            "listens to the specific request instead of defaulting to 'full refund or "
            "replacement'. ORD-2010 is delivered Bluetooth Speaker at $129.99. KB-006 "
            "covers defective products. Standard tier customer, neutral tone, no escalation. "
            "This tests whether the system can handle nuanced refund amounts."
        ),
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # RT2-003: SHIPPING DAMAGE — Physical damage with replacement vs refund choice
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "RT2-003",
        "message": (
            "My Mechanical Keyboard arrived today and the box was completely crushed on "
            "one side. The keyboard itself has a cracked spacebar and two of the key "
            "switches are loose and rattling around. The tracking number was TRK-55401 "
            "if that helps. I can send photos of the damage. This was supposed to be a "
            "birthday present for my partner and now it's ruined. I want to know my "
            "options — can you send a replacement right away, or should I just get a "
            "refund and buy something else? I need this resolved quickly because the "
            "birthday is in 3 days. Order was ORD-2040 for $159.99."
        ),
        "customer_id": "CUST-1005",
        "variant": "parwa",
        "expected_intent": "refund_request",
        "expected_sentiment": "frustrated",
        "expected_escalation": False,
        "expected_action": "process_refund",
        "difficulty": "medium",
        "category": "shipping_damage",
        "notes": (
            "Shipping damage with urgency. ORD-2040 is Mechanical Keyboard at $159.99, "
            "tracking TRK-55401. KB-006 says defective products: replacement or refund "
            "(customer's choice). Customer is asking for their options, not demanding one. "
            "Time pressure (birthday in 3 days) means replacement might not arrive in time — "
            "system should recognize this and recommend refund + express reorder. Not an "
            "escalation case — standard defective product handling."
        ),
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # RT2-004: ACCOUNT REACTIVATION — Suspended account + disputes charge
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "RT2-004",
        "message": (
            "My account has been suspended and I need it reactivated immediately. I "
            "noticed you tried to charge my card for the Pro Monthly subscription renewal, "
            "but I never authorized that charge. I originally bought the Cloud Storage 1TB "
            "as a one-time purchase for $99.99 — that was it. I never signed up for any "
            "monthly subscription. Looking at my payment history, there's also a duplicate "
            "charge for the same Cloud Storage on June 1st that I didn't authorize either. "
            "So not only did you sign me up for a subscription I never wanted, you also "
            "double-charged me for the original purchase. Now my account is suspended "
            "because of YOUR billing errors. I need: 1) the duplicate charge of $99.99 "
            "refunded, 2) the unauthorized $59.99 subscription charge removed, 3) my "
            "account reactivated. This is ridiculous — you can't just charge people's "
            "cards without permission and then suspend them when the charge fails."
        ),
        "customer_id": "CUST-1004",
        "variant": "parwa",
        "expected_intent": "billing_issue",
        "expected_sentiment": "angry",
        "expected_escalation": True,
        "expected_action": "escalate",
        "difficulty": "critical",
        "category": "account_reactivation_billing",
        "notes": (
            "CRITICAL multi-issue ticket: CUST-1004 (Chen Wei) is SUSPENDED. CRM shows: "
            "PAY-3030 ($99.99 completed), PAY-3030D ($99.99 DUPLICATE on June 1), "
            "PAY-3031 ($59.99 FAILED — card declined). Customer disputes both the "
            "duplicate charge AND the subscription. KB-001 says duplicate charges are "
            "refunded immediately. KB-002 covers failed payments. KB-004 covers "
            "account suspension. Premium customer (KB-009 VIP protocol). Multiple "
            "billing issues + suspended account + angry = escalation. "
            "TRAP: The customer is angry but has LEGITIMATE billing complaints — "
            "the system should NOT just dismiss this as 'unfounded anger'. "
            "Both duplicate charge AND unauthorized subscription need addressing."
        ),
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # RT2-005: MULTI-ORDER STATUS — Multiple orders, wants status on all
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "RT2-005",
        "message": (
            "Hi, I have several orders and I'm getting confused about what's where. "
            "Can you give me a status update on ALL of my orders? I know I ordered a "
            "Premium Headphones and USB-C Cable, then a Wireless Charger, and then a "
            "Laptop Stand. The headphones arrived fine, but I'm not sure about the "
            "charger — did it ship? And the laptop stand — I ordered that over a week "
            "ago and I haven't heard anything. Also, I noticed I was charged $189.99 "
            "twice on June 1st — is that related to the headphones order? Just want "
            "to make sure everything is in order. Thanks."
        ),
        "customer_id": "CUST-1001",
        "variant": "parwa",
        "expected_intent": "order_status",
        "expected_sentiment": "neutral",
        "expected_escalation": False,
        "expected_action": "send_reply",
        "difficulty": "complex",
        "category": "multi_order_status",
        "notes": (
            "Multi-intent: order_status + billing inquiry. CUST-1001 (Priya) has: "
            "ORD-2001 (delivered, $189.99, Premium Headphones + USB-C Cable), "
            "ORD-2002 (shipped, $49.99, Wireless Charger, tracking TRK-88292), "
            "ORD-2003 (processing, $79.99, Laptop Stand, NO tracking). "
            "ALSO: PAY-3001 and PAY-3002 are BOTH $189.99 on June 1 = duplicate charge. "
            "The customer mentions the duplicate charge almost as an afterthought — "
            "tests whether system catches the billing issue even when primary intent "
            "is order_status. PRIMARY intent = order_status, but system should also "
            "flag the duplicate charge and address it. Premium customer."
        ),
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # RT2-006: ENTERPRISE INVOICE DISPUTE — Disputes a pending invoice amount
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "RT2-006",
        "message": (
            "This is Rajesh Kumar from TechCorp India. I'm reviewing our invoice for "
            "the additional seats order (ORD-2021) and there's a discrepancy. The invoice "
            "shows $499.90 for 10 additional seats, but our contract specifies a rate of "
            "$45 per seat for Enterprise Plus accounts, which would be $450.00, not $499.90. "
            "That's a $49.90 overcharge. Also, the payment shows as 'pending' in your system "
            "but we haven't received the actual invoice to process the wire transfer. Our "
            "accounts payable team needs a corrected invoice before they can release payment. "
            "Additionally, our dedicated team (Sunita and Arjun) haven't responded to my "
            "emails about this for 5 business days. We have a 1-hour SLA and this is now "
            "well past that. Please correct the invoice and have our account team reach out."
        ),
        "customer_id": "CUST-1006",
        "variant": "parwa",
        "expected_intent": "billing_issue",
        "expected_sentiment": "frustrated",
        "expected_escalation": True,
        "expected_action": "escalate",
        "difficulty": "critical",
        "category": "enterprise_invoice_dispute",
        "notes": (
            "Enterprise customer ($52,300 LTV) with invoice dispute. ORD-2021 is "
            "processing at $499.90, PAY-3052 is pending. Customer claims contract rate "
            "is $45/seat = $450 not $499.90. SLA violation (1hr response, now 5 days). "
            "KB-008: Enterprise + SLA requirements = escalate. KB-009: VIP protocol. "
            "Multiple triggers for escalation: enterprise account, SLA violation, "
            "invoice discrepancy, unresponsive dedicated team. "
            "The system should escalate AND address the invoice question, not just "
            "send a generic 'we'll look into it' response."
        ),
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # RT2-007: SUBSCRIPTION DOWNGRADE + STORED PAYMENT — Downgrade + payment issue
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "RT2-007",
        "message": (
            "I want to downgrade my Creative Pro subscription to Basic Monthly. The $29.99 "
            "per month is too much for me right now since the design software isn't working "
            "properly and I can't use most of the Creative Pro features anyway. I've been "
            "having issues with the plugin pack crashing (I submitted ticket TKT-4040 about "
            "this) and the license activation (TKT-4041), so at this point I'm paying for "
            "features I can't even use. Please switch me to the $9.99 Basic Monthly plan. "
            "Also, my current card ending in 7788 is expiring this month, so you'll need "
            "to use my new card for future payments. Actually, can you tell me what payment "
            "method you have on file? I want to make sure it's up to date before the next "
            "billing cycle on July 20th."
        ),
        "customer_id": "CUST-1007",
        "variant": "parwa",
        "expected_intent": "account_modification",
        "expected_sentiment": "frustrated",
        "expected_escalation": False,
        "expected_action": "modify_account",
        "difficulty": "complex",
        "category": "subscription_change_payment",
        "notes": (
            "Multi-intent: account_modification (downgrade) + payment_method_update + "
            "reference to existing open tickets. CUST-1007 has Creative Pro at $29.99 "
            "renewing July 20th. Has 2 open tickets (TKT-4040, TKT-4041). KB-007: "
            "Downgrades take effect at next renewal. The customer also references their "
            "open tickets — system should acknowledge these but NOT treat this as a "
            "complaint/escalation (customer is being practical, not threatening). "
            "TRICKY: Card ending 7788 is the card on file (PAY-3060). Customer wants "
            "to update payment AND downgrade. System should handle both requests and "
            "confirm what happens when (downgrade at next renewal per KB-007)."
        ),
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # RT2-008: THE GASLIGHTER — Customer claims they never ordered (but CRM says they did)
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "id": "RT2-008",
        "message": (
            "I just checked my bank statement and there's a charge of $349.99 from your "
            "company that I absolutely did NOT make. I never ordered a Portable Monitor "
            "or a Replacement Monitor. I don't even know what that is. Someone must have "
            "hacked my account and made purchases using my information. I want this charge "
            "removed immediately and my account secured. How did someone place orders with "
            "my account without my knowledge? This is a serious security breach and I'm "
            "very concerned about my personal data. I demand a full investigation and "
            "refund of $349.99. I also see a charge from last month for $349.99 that "
            "was supposedly refunded — but I never received any refund. This whole thing "
            "is extremely suspicious."
        ),
        "customer_id": "CUST-1008",
        "variant": "parwa",
        "expected_intent": "billing_issue",
        "expected_sentiment": "angry",
        "expected_escalation": True,
        "expected_action": "escalate",
        "difficulty": "critical",
        "category": "gaslighter_security",
        "notes": (
            "THE GASLIGHTER: Customer claims they never ordered anything, but CRM shows: "
            "ORD-2070 (Portable Monitor, $349.99, RETURNED, 'Defective screen'), "
            "ORD-2071 (Replacement Monitor, $349.99, SHIPPED, tracking TRK-33101), "
            "PAY-3070 (refunded $349.99 for original), PAY-3071 (completed $349.99 for "
            "replacement). Customer ALSO had a previous ticket TKT-4050 about dead pixels. "
            "So the customer clearly DID order these items, returned the first one, and "
            "got a replacement. The refund WAS processed. Tests whether system checks CRM "
            "before blindly agreeing with the customer. Must NOT just say 'we'll refund you' "
            "— that would be a double refund. Must present the evidence: 'our records show...' "
            "Security concern + possible account compromise claim = escalate for investigation "
            "even though records show legitimate activity. The system should BOTH escalate "
            "(for security investigation) AND explain what CRM shows."
        ),
    },
]
