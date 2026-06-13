"""Mini PARWA Real-World 30-Ticket Test — HONEST Assessment.

This test creates 30 realistic, complex customer support tickets covering
ALL capabilities that Mini PARWA claims to handle, then runs them through
the actual 22-node pipeline and gives an HONEST assessment of whether
Mini could replace 3 interns.

Ticket Categories:
  1-5:   Order Status & Tracking (Mini CAN EXECUTE)
  6-10:  FAQ & Policy Questions (Mini CAN EXECUTE)
  11-15: Refund Requests (Mini CANNOT execute — only RECOMMEND)
  16-20: Cancellation Requests (Mini CANNOT execute — only RECOMMEND)
  21-25: Account Modifications (Mini CANNOT execute — only RECOMMEND)
  26-28: SMS & Multi-Channel (Mini CAN execute SMS, DENIED voice)
  29-30: Escalation Triggers (Mini CAN escalate)

Honesty Rules:
  - We report EXACTLY what the pipeline does
  - We flag where Mini's restrictions change the outcome
  - We report pipeline errors honestly
  - We don't count a ticket as "resolved" if it was only recommended
  - We measure time taken (interns take 5-15 min per ticket)
"""

from __future__ import annotations

import asyncio
import json
import time
import traceback
from datetime import datetime
from typing import Any

# ─── 30 Real-World Tickets ────────────────────────────────────────────────────

TICKETS: list[dict[str, Any]] = [
    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY A: Order Status & Tracking (Mini CAN EXECUTE — should resolve)
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T01",
        "category": "ORDER_STATUS",
        "customer_id": "CUST-1001",
        "channel": "email",
        "subject": "Where is my laptop stand order?",
        "message": "Hi, I ordered a Laptop Stand on June 8th (order ORD-2003) and it's still showing as 'processing'. It's been 5 days now. Can you tell me what's going on? I need it for my home office setup this week.",
        "expected_action": "SHARE_POLICY",
        "mini_can_execute": True,
        "intern_difficulty": "easy",
        "intern_time_min": 5,
    },
    {
        "id": "T02",
        "category": "ORDER_STATUS",
        "customer_id": "CUST-1005",
        "channel": "email",
        "subject": "Tracking not updating for my keyboard",
        "message": "I ordered a Mechanical Keyboard and Mouse Pad on June 10th. The tracking number TRK-55401 hasn't updated in 3 days. It says estimated delivery June 14th but the tracking still shows 'label created'. Is my package lost? This is frustrating.",
        "expected_action": "SEND_REPLY",
        "mini_can_execute": True,
        "intern_difficulty": "easy",
        "intern_time_min": 5,
    },
    {
        "id": "T03",
        "category": "ORDER_STATUS",
        "customer_id": "CUST-1001",
        "channel": "chat",
        "subject": "Multiple orders — need status on all",
        "message": "Hey, I have 3 orders with you. ORD-2001 (Premium Headphones), ORD-2002 (Wireless Charger), and ORD-2003 (Laptop Stand). Can you give me status on all three? The headphones were delivered but I want to confirm. The charger was shipped and the stand is still processing. Just want to verify everything.",
        "expected_action": "SEND_REPLY",
        "mini_can_execute": True,
        "intern_difficulty": "easy",
        "intern_time_min": 7,
    },
    {
        "id": "T04",
        "category": "ORDER_STATUS",
        "customer_id": "CUST-1008",
        "channel": "email",
        "subject": "Replacement monitor shipping status",
        "message": "I returned a defective Portable Monitor (ORD-2070) and you shipped a replacement (ORD-2071) with tracking TRK-33101. The estimated delivery was today, June 13th. I haven't received it yet and the tracking hasn't updated since yesterday. Please check.",
        "expected_action": "SEND_REPLY",
        "mini_can_execute": True,
        "intern_difficulty": "easy",
        "intern_time_min": 5,
    },
    {
        "id": "T05",
        "category": "ORDER_STATUS",
        "customer_id": "CUST-1003",
        "channel": "email",
        "subject": "Enterprise order processing delay",
        "message": "This is Aisha Patel from enterprise. We placed an order ORD-2021 for additional 10 seats on June 1st and it's still 'processing'. Our team is growing and we need these seats activated immediately. This is impacting our operations. As an enterprise customer, I expect faster turnaround.",
        "expected_action": "SEND_REPLY",
        "mini_can_execute": True,
        "intern_difficulty": "medium",
        "intern_time_min": 8,
    },

    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY B: FAQ & Policy Questions (Mini CAN EXECUTE — should resolve)
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T06",
        "category": "FAQ",
        "customer_id": "CUST-1002",
        "channel": "chat",
        "subject": "What's your refund policy?",
        "message": "Hey, I'm thinking about buying a Bluetooth Speaker but wanted to check — what's your refund policy? How many days do I have to return it if I don't like it?",
        "expected_action": "SHARE_FAQ",
        "mini_can_execute": True,
        "intern_difficulty": "trivial",
        "intern_time_min": 3,
    },
    {
        "id": "T07",
        "category": "FAQ",
        "customer_id": "CUST-1008",
        "channel": "email",
        "subject": "How do I return an item?",
        "message": "I need to know how to return an item. What's the process? Do I need to print a label? How long does it take to get my money back?",
        "expected_action": "SHARE_FAQ",
        "mini_can_execute": True,
        "intern_difficulty": "trivial",
        "intern_time_min": 3,
    },
    {
        "id": "T08",
        "category": "FAQ",
        "customer_id": "CUST-1007",
        "channel": "email",
        "subject": "Warranty question for design software",
        "message": "I bought your Design Software License and Plugin Pack recently. The plugin keeps crashing. Does the warranty cover software issues? What are my options if the software doesn't work as advertised?",
        "expected_action": "SHARE_FAQ",
        "mini_can_execute": True,
        "intern_difficulty": "easy",
        "intern_time_min": 5,
    },
    {
        "id": "T09",
        "category": "FAQ",
        "customer_id": "CUST-1006",
        "channel": "chat",
        "subject": "Enterprise support options",
        "message": "We're evaluating our support contract. What enterprise support options do you offer? We currently have Enterprise Plus with 200 seats. What's the SLA? Do we get a dedicated account manager?",
        "expected_action": "SHARE_FAQ",
        "mini_can_execute": True,
        "intern_difficulty": "easy",
        "intern_time_min": 5,
    },
    {
        "id": "T10",
        "category": "FAQ",
        "customer_id": "CUST-1004",
        "channel": "email",
        "subject": "How do I secure my account?",
        "message": "My account was recently suspended and I'm worried about security. How do I secure my account? I want to enable two-factor authentication. Also, how do I change my password? I think someone might have accessed my account.",
        "expected_action": "SHARE_FAQ",
        "mini_can_execute": True,
        "intern_difficulty": "easy",
        "intern_time_min": 5,
    },

    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY C: Refund Requests (Mini CANNOT execute — only RECOMMEND)
    # Mini collects info, verifies eligibility, sends to manager.
    # An intern would PROCESS the refund. Mini cannot.
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T11",
        "category": "REFUND",
        "customer_id": "CUST-1001",
        "channel": "email",
        "subject": "I was charged twice for the same order!",
        "message": "I just checked my credit card statement and I was charged TWICE for order ORD-2001. I see two charges of $189.99 on June 1st — payment IDs PAY-3001 and PAY-3002. This is clearly a duplicate charge. I want an immediate refund for the duplicate. This is unacceptable.",
        "expected_action": "PROCESS_REFUND",
        "mini_can_execute": False,  # RECOMMEND only
        "intern_difficulty": "medium",
        "intern_time_min": 10,
    },
    {
        "id": "T12",
        "category": "REFUND",
        "customer_id": "CUST-1007",
        "channel": "email",
        "subject": "Plugin crashes — want refund for plugin pack",
        "message": "I bought the Plugin Pack (ORD-2060, $49.99) and it crashes every time I open it. I have an open ticket TKT-4040 about this and nobody has helped. It's been 8 days. I want a full refund for the Plugin Pack. The product doesn't work as advertised.",
        "expected_action": "PROCESS_REFUND",
        "mini_can_execute": False,  # RECOMMEND only
        "intern_difficulty": "medium",
        "intern_time_min": 10,
    },
    {
        "id": "T13",
        "category": "REFUND",
        "customer_id": "CUST-1005",
        "channel": "chat",
        "subject": "Want to return mechanical keyboard",
        "message": "Hi, I just received my Mechanical Keyboard (ORD-2040) and I don't like the feel of the switches. It's not defective, I just prefer different switches. Can I return it for a full refund? It's within the 30-day window.",
        "expected_action": "PROCESS_REFUND",
        "mini_can_execute": False,  # RECOMMEND only
        "intern_difficulty": "medium",
        "intern_time_min": 8,
    },
    {
        "id": "T14",
        "category": "REFUND",
        "customer_id": "CUST-1003",
        "channel": "email",
        "subject": "Enterprise refund — invoice discrepancy on bulk order",
        "message": "We were overcharged on order ORD-2020. The invoice says $4,999.00 but our contract price for the Office License Pack x50 with Support Add-on is $4,499.00. That's a $500 overcharge. We need this corrected immediately with a refund for the difference. Our account manager Raj K. should have the contract details.",
        "expected_action": "PROCESS_REFUND",
        "mini_can_execute": False,  # RECOMMEND only
        "intern_difficulty": "hard",
        "intern_time_min": 15,
    },
    {
        "id": "T15",
        "category": "REFUND",
        "customer_id": "CUST-1002",
        "channel": "email",
        "subject": "Refund for cancelled smart watch order",
        "message": "I cancelled my Smart Watch order (ORD-2011) and the payment (PAY-3011, $299.99) shows as 'refunded' in your system, but I haven't received the money back in my bank account yet. It's been 10 days since the refund was initiated. When will I see the refund?",
        "expected_action": "SEND_REPLY",
        "mini_can_execute": True,  # This is actually a status inquiry, not a new refund
        "intern_difficulty": "medium",
        "intern_time_min": 7,
    },

    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY D: Cancellation Requests (Mini CANNOT execute — only RECOMMEND)
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T16",
        "category": "CANCELLATION",
        "customer_id": "CUST-1001",
        "channel": "email",
        "subject": "Cancel my laptop stand order",
        "message": "I want to cancel my Laptop Stand order (ORD-2003). It's still showing as 'processing' so it hasn't shipped yet. I found a better price elsewhere. Please cancel and refund immediately.",
        "expected_action": "CANCEL_ORDER",
        "mini_can_execute": False,  # RECOMMEND only
        "intern_difficulty": "easy",
        "intern_time_min": 7,
    },
    {
        "id": "T17",
        "category": "CANCELLATION",
        "customer_id": "CUST-1007",
        "channel": "chat",
        "subject": "Cancel my Creative Pro subscription",
        "message": "I want to cancel my Creative Pro subscription. It's $29.99/month and I'm not using it enough to justify the cost. My renewal date is July 20th. Can you cancel it for me? Will it end immediately or at the renewal date?",
        "expected_action": "MODIFY_ACCOUNT",
        "mini_can_execute": False,  # RECOMMEND only
        "intern_difficulty": "medium",
        "intern_time_min": 10,
    },
    {
        "id": "T18",
        "category": "CANCELLATION",
        "customer_id": "CUST-1006",
        "channel": "email",
        "subject": "Need to cancel API Access order — budget freeze",
        "message": "This is Rajesh Kumar from Enterprise. Due to an unexpected budget freeze, we need to cancel our API Access Tier 3 order (ORD-2052, $999.00). It's currently 'processing'. Please cancel and ensure the pending invoice PAY-3052 is also voided. Our account manager should have context on this.",
        "expected_action": "CANCEL_ORDER",
        "mini_can_execute": False,  # RECOMMEND only
        "intern_difficulty": "hard",
        "intern_time_min": 12,
    },
    {
        "id": "T19",
        "category": "CANCELLATION",
        "customer_id": "CUST-1004",
        "channel": "email",
        "subject": "Cancel my Pro Monthly subscription",
        "message": "My account is suspended and I can't even use the Pro Monthly subscription ($59.99/mo). I want to cancel it. I'm not paying for something I can't access. Also, my card was declined — I need to update my payment method too.",
        "expected_action": "MODIFY_ACCOUNT",
        "mini_can_execute": False,  # RECOMMEND only
        "intern_difficulty": "hard",
        "intern_time_min": 12,
    },
    {
        "id": "T20",
        "category": "CANCELLATION",
        "customer_id": "CUST-1005",
        "channel": "chat",
        "subject": "Can I cancel my order before it ships?",
        "message": "I just ordered a Mechanical Keyboard and Mouse Pad a few hours ago (ORD-2040, ORD-2041). They're both showing as 'shipped' already. Is it too late to cancel? If so, I want to return them as soon as they arrive.",
        "expected_action": "SEND_REPLY",
        "mini_can_execute": True,  # This is a policy question about cancellation
        "intern_difficulty": "medium",
        "intern_time_min": 7,
    },

    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY E: Account Modifications (Mini CANNOT execute — only RECOMMEND)
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T21",
        "category": "ACCOUNT_MOD",
        "customer_id": "CUST-1004",
        "channel": "email",
        "subject": "Account suspended — need to update payment",
        "message": "My account got suspended because my card ending in 1122 was declined 3 times. I need to update my payment method to a new card. Can you reactivate my account and let me update my billing info? This is urgent — I have an active Pro Monthly subscription.",
        "expected_action": "MODIFY_ACCOUNT",
        "mini_can_execute": False,  # RECOMMEND only
        "intern_difficulty": "medium",
        "intern_time_min": 10,
    },
    {
        "id": "T22",
        "category": "ACCOUNT_MOD",
        "customer_id": "CUST-1003",
        "channel": "email",
        "subject": "Add 20 more seats to our enterprise plan",
        "message": "Our company is growing again. We need to add 20 more seats to our Enterprise plan. We currently have 50 seats. Please add 20 and adjust the billing accordingly. Our account manager Raj K. can authorize this. Also, we need the seats active by Monday.",
        "expected_action": "MODIFY_ACCOUNT",
        "mini_can_execute": False,  # RECOMMEND only
        "intern_difficulty": "hard",
        "intern_time_min": 15,
    },
    {
        "id": "T23",
        "category": "ACCOUNT_MOD",
        "customer_id": "CUST-1007",
        "channel": "email",
        "subject": "Change my email address",
        "message": "I'm changing my email from emily.r@design.co to emily.rodriguez@newstudio.com. Can you update my account email? I want to make sure I still get all my notifications and license information at the new address.",
        "expected_action": "MODIFY_ACCOUNT",
        "mini_can_execute": False,  # RECOMMEND only
        "intern_difficulty": "easy",
        "intern_time_min": 7,
    },
    {
        "id": "T24",
        "category": "ACCOUNT_MOD",
        "customer_id": "CUST-1001",
        "channel": "chat",
        "subject": "Upgrade from Pro Annual to Enterprise",
        "message": "I've been a premium customer for 3 years and my business is growing. I want to upgrade my Pro Annual plan ($599/year) to an Enterprise plan. What would that look like? How many seats would I get? Can you process the upgrade?",
        "expected_action": "MODIFY_ACCOUNT",
        "mini_can_execute": False,  # RECOMMEND only
        "intern_difficulty": "hard",
        "intern_time_min": 12,
    },
    {
        "id": "T25",
        "category": "ACCOUNT_MOD",
        "customer_id": "CUST-1004",
        "channel": "email",
        "subject": "Reset my password — locked out",
        "message": "I'm completely locked out of my account. It's suspended and I can't remember my password anyway. I need a password reset link sent to my email chen.wei@tech.cn. This is urgent — I have cloud storage files I can't access.",
        "expected_action": "MODIFY_ACCOUNT",
        "mini_can_execute": False,  # RECOMMEND only
        "intern_difficulty": "easy",
        "intern_time_min": 5,
    },

    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY F: SMS & Multi-Channel (Mini CAN send SMS, DENIED voice)
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T26",
        "category": "SMS",
        "customer_id": "CUST-1001",
        "channel": "email",
        "subject": "Send me a text when my order ships",
        "message": "Can you send me an SMS text message when my Laptop Stand (ORD-2003) ships? I don't check email often and I want to know as soon as it goes out. My phone number is on file.",
        "expected_action": "SEND_SMS",
        "mini_can_execute": True,
        "intern_difficulty": "easy",
        "intern_time_min": 5,
    },
    {
        "id": "T27",
        "category": "VOICE_DENIED",
        "customer_id": "CUST-1005",
        "channel": "chat",
        "subject": "I want a phone call about my order",
        "message": "I'm frustrated about my keyboard order. I want to speak to someone on the phone. Can you call me back? My number is +1-555-987-6543. I want a voice call to discuss this.",
        "expected_action": "VOICE_CALL",
        "mini_can_execute": False,  # DENIED — voice is addon only on Mini
        "intern_difficulty": "medium",
        "intern_time_min": 8,
    },
    {
        "id": "T28",
        "category": "SMS",
        "customer_id": "CUST-1003",
        "channel": "email",
        "subject": "Text me the invoice details",
        "message": "Please send me an SMS with the invoice details for our pending payment PAY-3021 ($499.90). Our finance team needs a text notification for the pending invoice. Phone: +91-99887-76655",
        "expected_action": "SEND_SMS",
        "mini_can_execute": True,
        "intern_difficulty": "easy",
        "intern_time_min": 5,
    },

    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY G: Escalation Triggers (Mini CAN escalate)
    # ═══════════════════════════════════════════════════════════════════════
    {
        "id": "T29",
        "category": "ESCALATION",
        "customer_id": "CUST-1006",
        "channel": "email",
        "subject": "I'm contacting my attorney — breach of contract",
        "message": "This is the THIRD time our enterprise integration has failed (see TKT-4030). Our custom SLA guarantees 1-hour response time and we've been waiting 3 DAYS. This is a breach of our contract. I'm contacting my attorney if this isn't resolved today. We pay $4,999/month for Enterprise Plus and this level of service is unacceptable.",
        "expected_action": "ESCALATE_TO_HUMAN",
        "mini_can_execute": True,
        "intern_difficulty": "hard",
        "intern_time_min": 12,
    },
    {
        "id": "T30",
        "category": "ESCALATION",
        "customer_id": "CUST-1007",
        "channel": "email",
        "subject": "I want to speak to a manager NOW",
        "message": "I have TWO open tickets (TKT-4040 and TKT-4041) that nobody has responded to. The plugin crashes and my license won't activate. It's been over a week. I'm a 3-year loyal customer and this is how you treat me? I want to speak to a human agent immediately. Nobody has responded to my previous messages and I'm fed up.",
        "expected_action": "ESCALATE_TO_HUMAN",
        "mini_can_execute": True,
        "intern_difficulty": "hard",
        "intern_time_min": 10,
    },
]


# ─── Test Runner ──────────────────────────────────────────────────────────────

async def run_mini_test() -> dict[str, Any]:
    """Run all 30 tickets through Mini PARWA and collect honest results."""

    from parwa.graph import aprocess_ticket
    from parwa.config import VARIANT_CONFIG, ACTION_PERMISSIONS
    from parwa.state import ExecutionMode, ActionType

    results: list[dict[str, Any]] = []
    start_time = time.time()

    print("=" * 90)
    print("  MINI PARWA — REAL-WORLD 30-TICKET HONEST ASSESSMENT")
    print("=" * 90)
    print()
    print("  Variant: Mini PARWA ('The 24/7 Trainee')")
    print(f"  Price: ${VARIANT_CONFIG['mini']['price_monthly']:,}/month")
    print(f"  Capacity: {VARIANT_CONFIG['mini']['tickets_per_day']} tickets/day, {VARIANT_CONFIG['mini']['concurrent_tickets']} concurrent")
    print(f"  Channels: {[c.value for c in VARIANT_CONFIG['mini']['channels']]}")
    print(f"  Model Tiers: Light only (Gemma-4B)")
    print(f"  Action Style: {VARIANT_CONFIG['mini']['action_style']} (collects info, verifies eligibility)")
    print(f"  AI Resolution Target: {VARIANT_CONFIG['mini']['ai_resolution_rate']*100:.0f}%")
    print()

    # Print Mini's permissions
    print("  Mini CAN EXECUTE:")
    for action, mode in ACTION_PERMISSIONS["mini"].items():
        if mode == ExecutionMode.EXECUTE:
            print(f"    ✅ {action.value}")
    print()
    print("  Mini can only RECOMMEND (needs manager approval):")
    for action, mode in ACTION_PERMISSIONS["mini"].items():
        if mode == ExecutionMode.RECOMMEND:
            print(f"    ⚠️  {action.value}")
    print()
    print("  Mini is DENIED:")
    for action, mode in ACTION_PERMISSIONS["mini"].items():
        if mode == ExecutionMode.DENY:
            print(f"    ❌ {action.value}")
    print()
    print("=" * 90)
    print()

    for i, ticket in enumerate(TICKETS):
        tid = ticket["id"]
        cat = ticket["category"]
        cid = ticket["customer_id"]
        channel = ticket["channel"]
        message = ticket["message"]
        subject = ticket["subject"]

        print(f"[{tid}] {cat}: {subject}")
        print(f"     Customer: {cid} | Channel: {channel}")

        t_start = time.time()
        try:
            result = await aprocess_ticket(
                raw_message=message,
                customer_id=cid,
                channel=channel,
                variant="mini",
            )
            t_elapsed = time.time() - t_start

            # Extract key results
            intent = result.get("intent", "unknown")
            sentiment = result.get("sentiment", "unknown")
            complexity = result.get("complexity", "unknown")
            final_response = result.get("final_response", "")[:200]
            action_plans = result.get("action_plans", [])
            quality_score = result.get("quality_score", 0)
            should_escalate = result.get("should_escalate", False)
            pipeline_errors = result.get("pipeline_errors", [])

            # Determine what actions were planned
            action_summary = []
            for ap in action_plans:
                at = ap.get("action_type", "unknown")
                mode = ap.get("mode", "unknown")
                action_summary.append(f"{at}({mode})")

            # Determine outcome
            if pipeline_errors:
                outcome = "PIPELINE_ERROR"
            elif should_escalate:
                outcome = "ESCALATED"
            elif any(ap.get("action_type") in ("process_refund", "cancel_order", "modify_account") and ap.get("mode") == "recommend" for ap in action_plans):
                outcome = "RECOMMENDED_ONLY"
            elif action_plans and all(ap.get("mode") == "execute" for ap in action_plans):
                outcome = "EXECUTED"
            elif action_plans:
                outcome = "PARTIAL"
            else:
                outcome = "NO_ACTION"

            # Can Mini fully resolve this ticket?
            fully_resolved = outcome == "EXECUTED"

            entry = {
                "ticket_id": tid,
                "category": cat,
                "subject": subject,
                "intent": intent,
                "sentiment": sentiment,
                "complexity": complexity,
                "actions": action_summary,
                "outcome": outcome,
                "quality_score": quality_score,
                "fully_resolved": fully_resolved,
                "elapsed_seconds": round(t_elapsed, 2),
                "pipeline_errors": len(pipeline_errors),
                "mini_expected_to_execute": ticket["mini_can_execute"],
                "intern_difficulty": ticket["intern_difficulty"],
                "intern_time_min": ticket["intern_time_min"],
            }
            results.append(entry)

            # Print result
            outcome_emoji = "✅" if fully_resolved else "⚠️" if outcome == "RECOMMENDED_ONLY" else "❌" if outcome == "PIPELINE_ERROR" else "🔄"
            print(f"     Intent: {intent} | Sentiment: {sentiment} | Complexity: {complexity}")
            print(f"     Actions: {', '.join(action_summary) if action_summary else 'none'}")
            print(f"     Outcome: {outcome_emoji} {outcome} | Quality: {quality_score:.0f}/100 | Time: {t_elapsed:.1f}s")
            if pipeline_errors:
                print(f"     ⚠️  Pipeline errors: {len(pipeline_errors)}")
            print()

        except Exception as e:
            t_elapsed = time.time() - t_start
            results.append({
                "ticket_id": tid,
                "category": cat,
                "subject": subject,
                "outcome": "EXCEPTION",
                "fully_resolved": False,
                "elapsed_seconds": round(t_elapsed, 2),
                "error": str(e),
                "mini_expected_to_execute": ticket["mini_can_execute"],
                "intern_difficulty": ticket["intern_difficulty"],
                "intern_time_min": ticket["intern_time_min"],
            })
            print(f"     ❌ EXCEPTION: {e}")
            print()

    total_time = time.time() - start_time

    # ─── Final Honest Assessment ───────────────────────────────────────────

    print()
    print("=" * 90)
    print("  HONEST ASSESSMENT — MINI PARWA vs 3 INTERNS")
    print("=" * 90)
    print()

    # Count outcomes
    executed = [r for r in results if r["outcome"] == "EXECUTED"]
    recommended = [r for r in results if r["outcome"] == "RECOMMENDED_ONLY"]
    escalated = [r for r in results if r["outcome"] == "ESCALATED"]
    errors = [r for r in results if r["outcome"] in ("PIPELINE_ERROR", "EXCEPTION")]
    partial = [r for r in results if r["outcome"] == "PARTIAL"]

    # Mini CAN execute tickets
    can_execute_tickets = [r for r in results if r.get("mini_expected_to_execute", False)]
    cannot_execute_tickets = [r for r in results if not r.get("mini_expected_to_execute", True)]

    # Resolution rate among tickets Mini SHOULD be able to resolve
    mini_resolvable_resolved = [r for r in can_execute_tickets if r["fully_resolved"]]
    mini_resolvable_rate = len(mini_resolvable_resolved) / len(can_execute_tickets) * 100 if can_execute_tickets else 0

    # Overall stats
    avg_quality = sum(r.get("quality_score", 0) for r in results) / len(results) if results else 0
    avg_time = sum(r.get("elapsed_seconds", 0) for r in results) / len(results) if results else 0
    total_intern_time = sum(r.get("intern_time_min", 0) for r in results)

    print(f"  TOTAL TICKETS: {len(results)}")
    print(f"  Pipeline Time: {total_time:.1f}s total, {avg_time:.1f}s avg per ticket")
    print()
    print(f"  OUTCOMES:")
    print(f"    ✅ Fully Executed (Mini did the work):   {len(executed)}")
    print(f"    ⚠️  Recommended Only (needs human):       {len(recommended)}")
    print(f"    🔄 Escalated to Human:                    {len(escalated)}")
    print(f"    🔀 Partial (mixed modes):                 {len(partial)}")
    print(f"    ❌ Pipeline Errors:                        {len(errors)}")
    print()
    print(f"  TICKETS MINI CAN EXECUTE: {len(can_execute_tickets)}")
    print(f"    Actually resolved: {len(mini_resolvable_resolved)} ({mini_resolvable_rate:.0f}%)")
    print()
    print(f"  TICKETS MINI CAN ONLY RECOMMEND: {len(cannot_execute_tickets)}")
    print(f"    (These need a manager to approve — Mini preps the request)")
    print()
    print(f"  Average Quality Score: {avg_quality:.0f}/100")
    print(f"  Estimated Intern Time for Same 30 Tickets: {total_intern_time} minutes ({total_intern_time/60:.1f} hours)")
    print()

    # Category breakdown
    print("  CATEGORY BREAKDOWN:")
    categories = {}
    for r in results:
        cat = r.get("category", "UNKNOWN")
        if cat not in categories:
            categories[cat] = {"total": 0, "executed": 0, "recommended": 0, "escalated": 0, "errors": 0}
        categories[cat]["total"] += 1
        if r["outcome"] == "EXECUTED":
            categories[cat]["executed"] += 1
        elif r["outcome"] == "RECOMMENDED_ONLY":
            categories[cat]["recommended"] += 1
        elif r["outcome"] == "ESCALATED":
            categories[cat]["escalated"] += 1
        elif r["outcome"] in ("PIPELINE_ERROR", "EXCEPTION"):
            categories[cat]["errors"] += 1

    for cat, stats in categories.items():
        print(f"    {cat:20s}: {stats['total']} tickets — {stats['executed']} executed, {stats['recommended']} recommended, {stats['escalated']} escalated, {stats['errors']} errors")
    print()

    # The BIG question
    print("  " + "=" * 86)
    print("  CAN MINI PARWA ($1,000/mo) REPLACE 3 INTERNS?")
    print("  " + "=" * 86)
    print()

    # What Mini does well
    mini_strengths = []
    mini_weaknesses = []

    if mini_resolvable_rate >= 80:
        mini_strengths.append(f"Resolves {mini_resolvable_rate:.0f}% of tickets it's allowed to execute (FAQs, status, SMS)")
    elif mini_resolvable_rate >= 50:
        mini_weaknesses.append(f"Only resolves {mini_resolvable_rate:.0f}% of tickets it's allowed to execute — below 60% target")
    else:
        mini_weaknesses.append(f"Only resolves {mini_resolvable_rate:.0f}% of tickets it's allowed to execute — WAY below 60% target")

    if len(recommended) > 0:
        mini_weaknesses.append(f"Cannot execute {len(recommended)} tickets (refunds, cancellations, account changes) — these need human approval")

    if len(errors) > 0:
        mini_weaknesses.append(f"{len(errors)} tickets hit pipeline errors — reliability issue")

    if avg_quality < 60:
        mini_weaknesses.append(f"Average quality score {avg_quality:.0f}/100 is below acceptable threshold (80)")
    elif avg_quality >= 80:
        mini_strengths.append(f"Average quality score {avg_quality:.0f}/100 meets the 80+ threshold")

    if avg_time < 30:
        mini_strengths.append(f"Processes tickets in {avg_time:.1f}s vs interns taking 5-15 minutes — massive speed advantage")

    print("  MINI STRENGTHS:")
    if mini_strengths:
        for s in mini_strengths:
            print(f"    ✅ {s}")
    else:
        print("    (none identified)")
    print()

    print("  MINI WEAKNESSES:")
    if mini_weaknesses:
        for w in mini_weaknesses:
            print(f"    ⚠️  {w}")
    else:
        print("    (none identified)")
    print()

    # Final verdict
    fully_resolved_count = len(executed)
    needs_human = len(recommended) + len(escalated) + len(errors)

    print("  VERDICT:")
    if fully_resolved_count >= 20 and len(errors) == 0:
        print("    🟢 Mini can handle routine tickets (status, FAQ, SMS) AUTONOMOUSLY.")
        print("    🟡 Mini CANNOT execute financial/account changes — needs manager approval.")
        print("    🟢 Combined: Mini + 1 manager > 3 interns (faster on routine, safe on financial)")
    elif fully_resolved_count >= 10:
        print("    🟡 Mini can handle SOME routine tickets autonomously.")
        print("    🟡 Many tickets need human intervention (recommendations, escalations).")
        print("    🟡 Mini + 1 manager might replace 1-2 interns, not 3.")
    else:
        print("    🔴 Mini is struggling with most tickets.")
        print("    🔴 Too many errors or unresolved issues.")
        print("    🔴 Not ready to replace even 1 intern in current state.")
    print()

    # Intern comparison
    print(f"  INTERN COMPARISON:")
    print(f"    3 interns × 8 hours = 24 person-hours/day capacity")
    print(f"    3 interns average time per ticket: ~8 minutes")
    print(f"    3 interns can handle: ~180 tickets/day")
    print(f"    Mini PARWA capacity: {VARIANT_CONFIG['mini']['tickets_per_day']} tickets/day")
    print(f"    Mini PARWA resolution rate: {VARIANT_CONFIG['mini']['ai_resolution_rate']*100:.0f}% target")
    print(f"    Mini PARWA actual (this test): {fully_resolved_count}/{len(results)} = {fully_resolved_count/len(results)*100:.0f}% fully resolved")
    print(f"    Mini PARWA + human for recommendations: {(fully_resolved_count+len(recommended))}/{len(results)} = {(fully_resolved_count+len(recommended))/len(results)*100:.0f}% actionable")
    print()

    print("=" * 90)

    # Save results
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "variant": "mini",
        "total_tickets": len(results),
        "results": results,
        "summary": {
            "executed": len(executed),
            "recommended_only": len(recommended),
            "escalated": len(escalated),
            "partial": len(partial),
            "errors": len(errors),
            "mini_resolvable_rate": mini_resolvable_rate,
            "avg_quality": avg_quality,
            "avg_time_seconds": avg_time,
            "total_intern_time_minutes": total_intern_time,
        },
    }

    return report


def main():
    """Entry point."""
    report = asyncio.run(run_mini_test())

    # Save report
    output_path = "/home/z/my-project/download/mini_parwa_30_ticket_assessment.json"
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
