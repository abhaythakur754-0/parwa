"""PARWA Mini — Batch Test with NVIDIA API (DeepSeek-V4-Pro) + ZAI SDK fallback."""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ["PARWA_MOCK_MODE"] = "false"

import logging
logging.basicConfig(level=logging.WARNING)
for name in ["parwa.llm", "parwa.graph", "parwa.nodes", "httpx", "httpcore"]:
    logging.getLogger(name).setLevel(logging.WARNING)


@dataclass
class MiniTicket:
    ticket_id: str; channel: str; customer_id: str; subject: str; body: str
    category: str; difficulty: str; expected_mini_behavior: str
    expected_human_behavior: str; mini_can_handle: str; test_purpose: str

@dataclass
class TicketResult:
    ticket_id: str; category: str; difficulty: str
    intent_detected: str = ""; sentiment_detected: str = ""; complexity_score: str = ""
    quality_score: float = 0.0; final_response: str = ""
    actions_taken: list = field(default_factory=list); escalation: bool = False
    pipeline_errors: list = field(default_factory=list)
    processing_time_seconds: float = 0.0; llm_backend_used: str = ""
    resolution: str = ""; score_explanation: str = ""
    human_time_estimate_minutes: float = 0.0; human_would_resolve: bool = True
    mini_replaces_human: str = ""


def generate_all_tickets() -> list[MiniTicket]:
    tickets = []
    # EASY
    tickets.append(MiniTicket("MINI-E01","chat","CUST-1001","Where is my order?","I placed an order 5 days ago and haven't received any shipping updates. Can you check order ORD-2002?","order_status","easy","EXECUTE: Look up ORD-2002, provide status.","Look up order, provide tracking. 1-2 minutes.","yes","Basic order status"))
    tickets.append(MiniTicket("MINI-E02","chat","CUST-1005","When will my package arrive?","My order ORD-2040 was shipped. When should I expect it?","order_status","easy","EXECUTE: Look up ORD-2040, give delivery date.","Check order, give delivery date. 1 minute.","yes","Delivery estimate"))
    tickets.append(MiniTicket("MINI-E03","email","CUST-1008","What is your refund policy?","Hi, I was wondering what your refund policy is. Can you let me know the details?","faq","easy","EXECUTE: Share refund policy.","Copy-paste from KB. 30 seconds.","yes","FAQ"))
    tickets.append(MiniTicket("MINI-E04","chat","CUST-1002","Do you offer express shipping?","I need something delivered fast. Do you have express shipping options?","faq","easy","EXECUTE: Share shipping policy.","Look up shipping policy. 30 seconds.","yes","Shipping FAQ"))
    tickets.append(MiniTicket("MINI-E05","email","CUST-1007","App keeps crashing","Your mobile app crashes every time I open it. I'm on Android 14, Samsung Galaxy S24. Please help.","tech_support","easy","EXECUTE: Create ticket + troubleshooting.","Create ticket, send troubleshooting. 2 minutes.","yes","Tech support"))
    # MEDIUM
    tickets.append(MiniTicket("MINI-M01","email","CUST-1003","Incorrect charge on my subscription","I was charged $79.99 but my plan is $49.99/month. There's a $30 overcharge. Fix this and refund the difference.","billing_dispute","medium","COLLECT: Verify pricing. RECOMMEND refund. CANNOT execute.","Verify overcharge, process $30 refund. 5 minutes.","partially","Billing dispute"))
    tickets.append(MiniTicket("MINI-M02","chat","CUST-1004","My account is suspended","I can't access my account. It says suspended. What happened? I need it fixed now.","account_suspended","medium","COLLECT: See payment declined. RECOMMEND: Update payment.","Explain, update payment, reactivate. 5-8 minutes.","partially","Suspended account"))
    tickets.append(MiniTicket("MINI-M03","email","CUST-1002","Update my billing address","I moved and need to update my billing address to 123 New Street, New City, NY 10001.","account_modification","medium","RECOMMEND: Collect new address, prepare change request.","Verify, update address, confirm. 3 minutes.","partially","Account change"))
    tickets.append(MiniTicket("MINI-M04","chat","CUST-1001","I think I was charged twice","Hey, I see two charges of $189.99 on my card for the same order. Can you check?","duplicate_charge","medium","COLLECT: Find duplicate. RECOMMEND refund. CANNOT execute.","Check payments, process refund. 3-5 minutes.","partially","Duplicate charge"))
    tickets.append(MiniTicket("MINI-M05","email","CUST-1005","How do I return my keyboard?","I bought a Mechanical Keyboard (ORD-2040) but it doesn't feel right. I want to return it.","return_request","medium","Share return policy. Check eligibility. RECOMMEND.","Check eligibility, initiate return. 5 minutes.","partially","Return request"))
    # HARD
    tickets.append(MiniTicket("MINI-H01","email","CUST-1001","I want a FULL REFUND for my defective headphones NOW","The Premium Headphones I received are completely broken! No sound from the left ear. I paid $189.99 and I want EVERY penny back!","refund_angry","hard","COLLECT: Verify. RECOMMEND refund. Cannot execute. Customer frustrated.","Verify, process refund, offer replacement, empathize. 5-8 minutes.","partially","Angry refund"))
    tickets.append(MiniTicket("MINI-H02","chat","CUST-1006","Our integration stopped working and we're losing money","Our API integration has been down for 2 hours. We're an enterprise customer and this is costing us revenue. We need this fixed immediately.","enterprise_critical","hard","ESCALATE: Enterprise + SLA + revenue impact.","Engage account manager, check API, apply SLA credit. 10-15 minutes.","partially","Enterprise critical"))
    tickets.append(MiniTicket("MINI-H03","email","CUST-1004","I want to speak to a MANAGER about my suspended account","This is the THIRD time my account has been suspended because of your billing system errors. I DEMAND to speak to a manager!","escalation_angry","hard","ESCALATE: Angry + 'manager' keyword = immediate escalation.","Manager takes over, reviews, waives fees. 15-20 minutes.","yes","Escalation trigger"))
    tickets.append(MiniTicket("MINI-H04","chat","CUST-1003","We need a custom invoice for our accounting department","We need a custom invoice format for our 50-seat enterprise license that includes our company tax ID and purchase order number.","custom_request","hard","Flag for account manager — beyond Mini's capabilities.","Generate custom invoice with tax ID/PO. 10-15 minutes.","no","Custom enterprise request"))
    tickets.append(MiniTicket("MINI-H05","email","CUST-1007","REFUND for broken software AND compensation for lost work","Your Design Software crashed and I lost 4 hours of work. I want a refund for the license ($199.99) AND compensation for my lost time!","complex_refund","hard","COLLECT: Verify. RECOMMEND: Refund eligible. Compensation = policy exception. Flag for manager.","Check license, process refund, negotiate compensation. 15-20 minutes.","partially","Multi-part demand"))
    return tickets


def score_result(ticket: MiniTicket, state: dict, elapsed: float) -> TicketResult:
    tr = TicketResult(
        ticket_id=ticket.ticket_id, category=ticket.category, difficulty=ticket.difficulty,
        intent_detected=str(state.get("intent", "unknown")),
        sentiment_detected=str(state.get("sentiment", "unknown")),
        complexity_score=str(state.get("complexity", "unknown")),
        quality_score=float(state.get("quality_score", 0) or 0),
        final_response=str(state.get("final_response", "")),
        actions_taken=state.get("actions", []) or [],
        escalation=bool(state.get("escalated", False)),
        pipeline_errors=state.get("pipeline_errors", []) or [],
        processing_time_seconds=elapsed,
        llm_backend_used=str(state.get("llm_backend", "unknown")),
    )

    resp = tr.final_response.lower()
    cat = ticket.category

    if cat in ("order_status", "faq", "tech_support"):
        if tr.escalation:
            tr.resolution = "PARTIAL"; tr.score_explanation = "Escalated when should handle autonomously"; tr.mini_replaces_human = "partially"
        elif any(kw in resp for kw in ["tracking","shipped","delivered","trk-","refund policy","shipping","express","troubleshoot","ticket created","return policy","within 30"]):
            tr.resolution = "RESOLVED"; tr.score_explanation = "Correct information provided autonomously"; tr.mini_replaces_human = "yes"
        elif len(tr.final_response) > 80:
            tr.resolution = "PARTIAL"; tr.score_explanation = "Response given but may lack specific details"; tr.mini_replaces_human = "partially"
        else:
            tr.resolution = "FAILED"; tr.score_explanation = "Response too short/generic"; tr.mini_replaces_human = "no"
    elif cat in ("billing_dispute","account_suspended","account_modification","duplicate_charge","return_request"):
        if tr.escalation:
            tr.resolution = "RESOLVED"; tr.score_explanation = "Correctly collected info and escalated"; tr.mini_replaces_human = "partially"
        elif any(kw in resp for kw in ["recommend","approval","manager","flag","need to verify","review","forward"]):
            tr.resolution = "RESOLVED"; tr.score_explanation = "Correctly identified issue and recommended"; tr.mini_replaces_human = "partially"
        elif any(kw in resp for kw in ["refund","charge","payment","address","suspended","duplicate","return","account"]):
            tr.resolution = "PARTIAL"; tr.score_explanation = "Addressed topic but unclear constraint"; tr.mini_replaces_human = "partially"
        else:
            tr.resolution = "PARTIAL"; tr.score_explanation = "Responded but unclear handling"; tr.mini_replaces_human = "partially"
    elif cat in ("refund_angry","escalation_angry"):
        if tr.escalation or "escalat" in resp or "manager" in resp or "human" in resp:
            tr.resolution = "RESOLVED"; tr.score_explanation = "Correctly escalated angry customer"; tr.mini_replaces_human = "partially"
        elif "refund" in resp and "recommend" not in resp and "approval" not in resp:
            tr.resolution = "WRONG"; tr.score_explanation = "May have tried to execute refund"; tr.mini_replaces_human = "no"
        else:
            tr.resolution = "PARTIAL"; tr.score_explanation = "Unclear if escalation happened"; tr.mini_replaces_human = "partially"
    elif cat == "enterprise_critical":
        if tr.escalation or "escalat" in resp or "account manager" in resp:
            tr.resolution = "RESOLVED"; tr.score_explanation = "Correctly escalated enterprise issue"; tr.mini_replaces_human = "partially"
        else:
            tr.resolution = "PARTIAL"; tr.score_explanation = "May not have recognized enterprise urgency"; tr.mini_replaces_human = "no"
    elif cat == "custom_request":
        if tr.escalation or "account manager" in resp or "team" in resp or "specialist" in resp:
            tr.resolution = "RESOLVED"; tr.score_explanation = "Correctly flagged as beyond capabilities"; tr.mini_replaces_human = "partially"
        else:
            tr.resolution = "FAILED"; tr.score_explanation = "Cannot handle custom enterprise requests"; tr.mini_replaces_human = "no"
    elif cat == "complex_refund":
        if tr.escalation or "recommend" in resp or "approval" in resp or "manager" in resp:
            tr.resolution = "RESOLVED"; tr.score_explanation = "Complex refund correctly escalated/recommended"; tr.mini_replaces_human = "partially"
        else:
            tr.resolution = "PARTIAL"; tr.score_explanation = "May not have addressed all parts"; tr.mini_replaces_human = "no"
    else:
        tr.resolution = "PARTIAL"; tr.score_explanation = "Unknown category"; tr.mini_replaces_human = "partially"

    human_times = {"order_status":1.5,"faq":0.5,"tech_support":2.0,"billing_dispute":5.0,"account_suspended":6.0,"account_modification":3.0,"duplicate_charge":4.0,"return_request":5.0,"refund_angry":7.0,"enterprise_critical":12.0,"escalation_angry":15.0,"custom_request":12.0,"complex_refund":18.0}
    tr.human_time_estimate_minutes = human_times.get(cat, 5.0)
    tr.human_would_resolve = True
    return tr


# Get batch from command line arg: python mini_batch_test.py 0 5 (start=0, count=5)
BATCH_START = int(sys.argv[1]) if len(sys.argv) > 1 else 0
BATCH_COUNT = int(sys.argv[2]) if len(sys.argv) > 2 else 5

async def run_batch():
    from parwa.graph import aprocess_ticket
    tickets = generate_all_tickets()
    batch = tickets[BATCH_START:BATCH_START + BATCH_COUNT]
    results = []

    print("=" * 80)
    print(f"PARWA MINI — BATCH TEST (NVIDIA DeepSeek-V4-Pro + ZAI SDK)")
    print(f"Batch: tickets {BATCH_START+1}-{BATCH_START+len(batch)} of {len(tickets)}")
    print("=" * 80)

    for i, ticket in enumerate(batch, 1):
        print(f"\n[{i}/{len(batch)}] {ticket.ticket_id} — {ticket.subject}")
        print(f"  Channel: {ticket.channel} | Customer: {ticket.customer_id} | Diff: {ticket.difficulty}")
        sys.stdout.flush()

        start = time.time()
        try:
            state = await aprocess_ticket(
                raw_message=ticket.body,
                customer_id=ticket.customer_id,
                channel=ticket.channel,
                variant="mini",
                interrupt_before_action=False,
            )
            elapsed = time.time() - start
            tr = score_result(ticket, state, elapsed)
            results.append(tr)

            print(f"  Intent: {tr.intent_detected} | Sentiment: {tr.sentiment_detected}")
            print(f"  Quality: {tr.quality_score:.0f} | Escalated: {tr.escalation} | Time: {tr.processing_time_seconds:.1f}s")
            if tr.pipeline_errors:
                print(f"  Errors: {tr.pipeline_errors[:2]}")
            resp_preview = tr.final_response[:300].replace('\n', ' ')
            print(f"  Response: {resp_preview}...")
            print(f"  >>> RESULT: {tr.resolution} | Replaces Human: {tr.mini_replaces_human}")
            print(f"  >>> Why: {tr.score_explanation}")
        except Exception as e:
            elapsed = time.time() - start
            tr = TicketResult(
                ticket_id=ticket.ticket_id, category=ticket.category, difficulty=ticket.difficulty,
                processing_time_seconds=elapsed, resolution="FAILED",
                score_explanation=f"Pipeline crashed: {str(e)[:100]}", mini_replaces_human="no",
            )
            results.append(tr)
            print(f"  CRASHED: {str(e)[:150]}")

        sys.stdout.flush()
        # Wait between tickets to respect rate limits
        await asyncio.sleep(3)

    # Summary
    resolved = sum(1 for r in results if r.resolution == "RESOLVED")
    partial = sum(1 for r in results if r.resolution == "PARTIAL")
    failed = sum(1 for r in results if r.resolution in ("FAILED", "WRONG"))

    print(f"\n{'='*80}")
    print(f"BATCH RESULTS ({BATCH_START+1}-{BATCH_START+len(batch)})")
    print(f"{'='*80}")
    print(f"RESOLVED: {resolved}/{len(results)} | PARTIAL: {partial}/{len(results)} | FAILED: {failed}/{len(results)}")
    for r in results:
        print(f"  {r.ticket_id:<12} {r.category:<20} {r.difficulty:<6} {r.resolution:<10} {r.mini_replaces_human:<10} {r.processing_time_seconds:.1f}s Q:{r.quality_score:.0f}")

    # Save batch results
    out = []
    for r in results:
        out.append({
            "ticket_id": r.ticket_id, "category": r.category, "difficulty": r.difficulty,
            "intent": r.intent_detected, "sentiment": r.sentiment_detected,
            "quality_score": r.quality_score, "resolution": r.resolution,
            "score_explanation": r.score_explanation, "escalated": r.escalation,
            "processing_time_seconds": round(r.processing_time_seconds, 2),
            "mini_replaces_human": r.mini_replaces_human,
            "human_time_minutes": r.human_time_estimate_minutes,
            "final_response": r.final_response[:500],
        })
    path = f"/home/z/my-project/download/mini_batch_{BATCH_START}_{BATCH_START+BATCH_COUNT}.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults saved: {path}")
    return results


if __name__ == "__main__":
    asyncio.run(run_batch())
