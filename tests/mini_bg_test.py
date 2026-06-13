"""PARWA Mini — Background Test with NVIDIA API (Llama-3.1-8B + DeepSeek-V4-Pro) + ZAI SDK fallback.

Runs all 15 tickets sequentially, saving results after each ticket.
Reads saved results on startup to skip already-completed tickets.

Run: nohup python3 mini_bg_test.py > /home/z/my-project/download/mini_test_log.txt 2>&1 &
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ["PARWA_MOCK_MODE"] = "false"

import logging
logging.basicConfig(level=logging.WARNING)
for name in ["parwa.llm", "parwa.graph", "parwa.nodes", "httpx", "httpcore", "httpcore.http11"]:
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
    # EASY (5)
    tickets.append(MiniTicket("MINI-E01","chat","CUST-1001","Where is my order?","I placed an order 5 days ago and haven't received any shipping updates. Can you check order ORD-2002?","order_status","easy","EXECUTE: Look up ORD-2002, provide tracking.","Look up order, provide tracking. 1-2 min.","yes","Basic order status"))
    tickets.append(MiniTicket("MINI-E02","chat","CUST-1005","When will my package arrive?","My order ORD-2040 was shipped. When should I expect it?","order_status","easy","EXECUTE: Look up ORD-2040, give delivery date.","Check order, give delivery date. 1 min.","yes","Delivery estimate"))
    tickets.append(MiniTicket("MINI-E03","email","CUST-1008","What is your refund policy?","Hi, I was wondering what your refund policy is. Can you let me know the details?","faq","easy","EXECUTE: Share refund policy.","Copy-paste from KB. 30 seconds.","yes","FAQ"))
    tickets.append(MiniTicket("MINI-E04","chat","CUST-1002","Do you offer express shipping?","I need something delivered fast. Do you have express shipping options?","faq","easy","EXECUTE: Share shipping policy.","Look up shipping policy. 30 seconds.","yes","Shipping FAQ"))
    tickets.append(MiniTicket("MINI-E05","email","CUST-1007","App keeps crashing","Your mobile app crashes every time I open it. I'm on Android 14, Samsung Galaxy S24. Please help.","tech_support","easy","EXECUTE: Create ticket + troubleshooting.","Create ticket, send troubleshooting. 2 minutes.","yes","Tech support"))
    # MEDIUM (5)
    tickets.append(MiniTicket("MINI-M01","email","CUST-1003","Incorrect charge on my subscription","I was charged $79.99 but my plan is $49.99/month. There's a $30 overcharge. Fix this and refund the difference.","billing_dispute","medium","COLLECT: Verify pricing. RECOMMEND refund. CANNOT execute.","Verify overcharge, process $30 refund. 5 min.","partially","Billing dispute"))
    tickets.append(MiniTicket("MINI-M02","chat","CUST-1004","My account is suspended","I can't access my account. It says suspended. What happened? I need it fixed now.","account_suspended","medium","COLLECT: See payment declined. RECOMMEND: Update payment.","Explain, update payment, reactivate. 5-8 min.","partially","Suspended account"))
    tickets.append(MiniTicket("MINI-M03","email","CUST-1002","Update my billing address","I moved and need to update my billing address to 123 New Street, New City, NY 10001.","account_modification","medium","RECOMMEND: Collect new address, prepare change request.","Verify, update address, confirm. 3 min.","partially","Account change"))
    tickets.append(MiniTicket("MINI-M04","chat","CUST-1001","I think I was charged twice","Hey, I see two charges of $189.99 on my card for the same order. Can you check?","duplicate_charge","medium","COLLECT: Find duplicate. RECOMMEND refund. CANNOT execute.","Check payments, process refund. 3-5 min.","partially","Duplicate charge"))
    tickets.append(MiniTicket("MINI-M05","email","CUST-1005","How do I return my keyboard?","I bought a Mechanical Keyboard (ORD-2040) but it doesn't feel right. I want to return it.","return_request","medium","Share return policy. Check eligibility. RECOMMEND.","Check eligibility, initiate return. 5 min.","partially","Return request"))
    # HARD (5)
    tickets.append(MiniTicket("MINI-H01","email","CUST-1001","I want a FULL REFUND for my defective headphones NOW","The Premium Headphones I received are completely broken! No sound from the left ear. I paid $189.99 and I want EVERY penny back!","refund_angry","hard","COLLECT: Verify. RECOMMEND refund. Cannot execute.","Verify, process refund, offer replacement, empathize. 5-8 min.","partially","Angry refund"))
    tickets.append(MiniTicket("MINI-H02","chat","CUST-1006","Our integration stopped working and we're losing money","Our API integration has been down for 2 hours. We're an enterprise customer and this is costing us revenue. We need this fixed immediately.","enterprise_critical","hard","ESCALATE: Enterprise + SLA + revenue impact.","Engage account manager, check API, apply SLA credit. 10-15 min.","partially","Enterprise critical"))
    tickets.append(MiniTicket("MINI-H03","email","CUST-1004","I want to speak to a MANAGER about my suspended account","This is the THIRD time my account has been suspended because of your billing system errors. I DEMAND to speak to a manager!","escalation_angry","hard","ESCALATE: Angry + 'manager' keyword = immediate escalation.","Manager takes over, reviews, waives fees. 15-20 min.","yes","Escalation trigger"))
    tickets.append(MiniTicket("MINI-H04","chat","CUST-1003","We need a custom invoice for our accounting department","We need a custom invoice format for our 50-seat enterprise license that includes our company tax ID and purchase order number.","custom_request","hard","Flag for account manager — beyond Mini's capabilities.","Generate custom invoice with tax ID/PO. 10-15 min.","no","Custom enterprise request"))
    tickets.append(MiniTicket("MINI-H05","email","CUST-1007","REFUND for broken software AND compensation for lost work","Your Design Software crashed and I lost 4 hours of work. I want a refund for the license ($199.99) AND compensation for my lost time!","complex_refund","hard","COLLECT: Verify. RECOMMEND: Refund eligible. Compensation = policy exception. Flag for manager.","Check license, process refund, negotiate compensation. 15-20 min.","partially","Multi-part demand"))
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
        elif any(kw in resp for kw in ["tracking","shipped","delivered","trk-","refund policy","shipping","express","troubleshoot","ticket created","return policy","within 30","order status","tracking number","estimated delivery","june"]):
            tr.resolution = "RESOLVED"; tr.score_explanation = "Correct information provided autonomously"; tr.mini_replaces_human = "yes"
        elif len(tr.final_response) > 80:
            tr.resolution = "PARTIAL"; tr.score_explanation = "Response given but may lack specific details"; tr.mini_replaces_human = "partially"
        else:
            tr.resolution = "FAILED"; tr.score_explanation = "Response too short/generic"; tr.mini_replaces_human = "no"
    elif cat in ("billing_dispute","account_suspended","account_modification","duplicate_charge","return_request"):
        if tr.escalation:
            tr.resolution = "RESOLVED"; tr.score_explanation = "Correctly collected info and escalated"; tr.mini_replaces_human = "partially"
        elif any(kw in resp for kw in ["recommend","approval","manager","flag","need to verify","review","forward","unable to","cannot","can't process","need to","will need","has been flagged","escalat"]):
            tr.resolution = "RESOLVED"; tr.score_explanation = "Correctly identified issue and recommended/flagged"; tr.mini_replaces_human = "partially"
        elif any(kw in resp for kw in ["refund","charge","payment","address","suspended","duplicate","return","account","billing","overcharge"]):
            tr.resolution = "PARTIAL"; tr.score_explanation = "Addressed topic but unclear if proper constraint applied"; tr.mini_replaces_human = "partially"
        else:
            tr.resolution = "PARTIAL"; tr.score_explanation = "Responded but unclear handling of financial constraint"; tr.mini_replaces_human = "partially"
    elif cat in ("refund_angry","escalation_angry"):
        if tr.escalation or "escalat" in resp or "manager" in resp or "human" in resp or "supervisor" in resp:
            tr.resolution = "RESOLVED"; tr.score_explanation = "Correctly escalated angry customer"; tr.mini_replaces_human = "partially"
        elif "refund" in resp and "recommend" not in resp and "approval" not in resp:
            tr.resolution = "WRONG"; tr.score_explanation = "May have tried to execute refund instead of escalating"; tr.mini_replaces_human = "no"
        else:
            tr.resolution = "PARTIAL"; tr.score_explanation = "Responded but unclear if escalation happened"; tr.mini_replaces_human = "partially"
    elif cat == "enterprise_critical":
        if tr.escalation or "escalat" in resp or "account manager" in resp or "dedicated" in resp or "priority" in resp:
            tr.resolution = "RESOLVED"; tr.score_explanation = "Correctly escalated enterprise issue"; tr.mini_replaces_human = "partially"
        else:
            tr.resolution = "PARTIAL"; tr.score_explanation = "May not have recognized enterprise urgency"; tr.mini_replaces_human = "no"
    elif cat == "custom_request":
        if tr.escalation or "account manager" in resp or "team" in resp or "specialist" in resp or "billing department" in resp or "finance" in resp:
            tr.resolution = "RESOLVED"; tr.score_explanation = "Correctly flagged as beyond capabilities"; tr.mini_replaces_human = "partially"
        else:
            tr.resolution = "FAILED"; tr.score_explanation = "Cannot handle custom enterprise requests"; tr.mini_replaces_human = "no"
    elif cat == "complex_refund":
        if tr.escalation or "recommend" in resp or "approval" in resp or "manager" in resp or "escalat" in resp:
            tr.resolution = "RESOLVED"; tr.score_explanation = "Complex refund correctly escalated/recommended"; tr.mini_replaces_human = "partially"
        else:
            tr.resolution = "PARTIAL"; tr.score_explanation = "May not have addressed all parts"; tr.mini_replaces_human = "no"
    else:
        tr.resolution = "PARTIAL"; tr.score_explanation = "Unknown category"; tr.mini_replaces_human = "partially"

    human_times = {"order_status":1.5,"faq":0.5,"tech_support":2.0,"billing_dispute":5.0,"account_suspended":6.0,"account_modification":3.0,"duplicate_charge":4.0,"return_request":5.0,"refund_angry":7.0,"enterprise_critical":12.0,"escalation_angry":15.0,"custom_request":12.0,"complex_refund":18.0}
    tr.human_time_estimate_minutes = human_times.get(cat, 5.0)
    tr.human_would_resolve = True
    return tr


def result_to_dict(r: TicketResult) -> dict:
    return {
        "ticket_id": r.ticket_id, "category": r.category, "difficulty": r.difficulty,
        "intent": r.intent_detected, "sentiment": r.sentiment_detected,
        "quality_score": r.quality_score, "resolution": r.resolution,
        "score_explanation": r.score_explanation, "escalated": r.escalation,
        "processing_time_seconds": round(r.processing_time_seconds, 2),
        "mini_replaces_human": r.mini_replaces_human,
        "human_time_minutes": r.human_time_estimate_minutes,
        "final_response": r.final_response[:800],
    }


RESULTS_PATH = "/home/z/my-project/download/mini_honest_results.json"
LOG_PATH = "/home/z/my-project/download/mini_test_log.txt"


def load_existing_results() -> list[dict]:
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH) as f:
            return json.load(f)
    return []


def save_results(results: list[dict]):
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)


def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


async def run_full_test():
    from parwa.graph import aprocess_ticket

    tickets = generate_all_tickets()
    existing = load_existing_results()
    done_ids = {r["ticket_id"] for r in existing}
    results = list(existing)

    log("=" * 70)
    log("PARWA MINI — HONEST TEST (NVIDIA Llama-3.1-8B + DeepSeek-V4-Pro + ZAI SDK)")
    log(f"Tickets: {len(tickets)} | Already done: {len(done_ids)} | Remaining: {len(tickets) - len(done_ids)}")
    log("=" * 70)

    for i, ticket in enumerate(tickets, 1):
        if ticket.ticket_id in done_ids:
            log(f"[{i}/{len(tickets)}] SKIP {ticket.ticket_id} (already done)")
            continue

        log(f"\n[{i}/{len(tickets)}] {ticket.ticket_id} — {ticket.subject}")
        log(f"  Channel: {ticket.channel} | Customer: {ticket.customer_id} | Diff: {ticket.difficulty}")

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

            log(f"  Intent: {tr.intent_detected} | Sentiment: {tr.sentiment_detected} | Complexity: {tr.complexity_score}")
            log(f"  Quality: {tr.quality_score:.0f} | Escalated: {tr.escalation} | Time: {tr.processing_time_seconds:.1f}s")
            if tr.pipeline_errors:
                log(f"  Errors: {tr.pipeline_errors[:2]}")
            resp_preview = tr.final_response[:300].replace('\n', ' ')
            log(f"  Response: {resp_preview}...")
            log(f"  >>> RESULT: {tr.resolution} | Replaces Human: {tr.mini_replaces_human}")
            log(f"  >>> Why: {tr.score_explanation}")

            results.append(result_to_dict(tr))
            save_results(results)

        except Exception as e:
            elapsed = time.time() - start
            tr = TicketResult(
                ticket_id=ticket.ticket_id, category=ticket.category, difficulty=ticket.difficulty,
                processing_time_seconds=elapsed, resolution="FAILED",
                score_explanation=f"Pipeline crashed: {str(e)[:100]}", mini_replaces_human="no",
            )
            results.append(result_to_dict(tr))
            save_results(results)
            log(f"  CRASHED: {str(e)[:150]}")

        # Wait between tickets for rate limiting
        if i < len(tickets):
            log(f"  Waiting 5s for rate limit...")
            await asyncio.sleep(5)

    # ─── FINAL SUMMARY ───
    log("\n\n" + "=" * 70)
    log("HONEST PERFORMANCE REPORT — MINI PARWA ($1,000/month)")
    log("=" * 70)

    resolved = [r for r in results if r["resolution"] == "RESOLVED"]
    partial = [r for r in results if r["resolution"] == "PARTIAL"]
    failed = [r for r in results if r["resolution"] in ("FAILED", "WRONG")]

    log(f"\nOVERALL: RESOLVED={len(resolved)} PARTIAL={len(partial)} FAILED={len(failed)} / {len(results)}")

    for diff in ["easy", "medium", "hard"]:
        dr = [r for r in results if r["difficulty"] == diff]
        if dr:
            d_res = sum(1 for r in dr if r["resolution"] == "RESOLVED")
            d_par = sum(1 for r in dr if r["resolution"] == "PARTIAL")
            d_fail = sum(1 for r in dr if r["resolution"] in ("FAILED", "WRONG"))
            log(f"  {diff.upper()}: Resolved={d_res} Partial={d_par} Failed={d_fail}")

    yes_rep = sum(1 for r in results if r["mini_replaces_human"] == "yes")
    par_rep = sum(1 for r in results if r["mini_replaces_human"] == "partially")
    no_rep = sum(1 for r in results if r["mini_replaces_human"] == "no")

    log(f"\nHUMAN REPLACEMENT:")
    log(f"  Fully replaces: {yes_rep}/{len(results)} ({100*yes_rep/len(results):.0f}%)")
    log(f"  Partially replaces: {par_rep}/{len(results)} ({100*par_rep/len(results):.0f}%)")
    log(f"  Cannot replace: {no_rep}/{len(results)} ({100*no_rep/len(results):.0f}%)")

    avg_mini = sum(r["processing_time_seconds"] for r in results) / len(results) if results else 0
    avg_human = sum(r["human_time_minutes"] for r in results) / len(results) if results else 0
    log(f"\nSPEED:")
    log(f"  Mini avg: {avg_mini:.1f}s per ticket")
    log(f"  Human avg: {avg_human:.1f} min per ticket")
    if avg_mini > 0:
        log(f"  Speed: {avg_human*60/avg_mini:.1f}x faster than human")

    log(f"\nPER-TICKET DETAIL:")
    for r in results:
        log(f"  {r['ticket_id']:<12} {r['category']:<20} {r['difficulty']:<6} {r['resolution']:<10} {r['mini_replaces_human']:<10} {r['processing_time_seconds']:.1f}s Q:{r['quality_score']:.0f}")

    full_pct = 100 * yes_rep / len(results) if results else 0
    partial_pct = 100 * (yes_rep + par_rep) / len(results) if results else 0

    log(f"""
FINAL HONEST VERDICT
====================
Mini PARWA at $1,000/month:
  - FULLY handles {yes_rep}/{len(results)} tickets ({full_pct:.0f}%)
  - PARTIALLY handles {par_rep}/{len(results)} tickets
  - CANNOT handle {no_rep}/{len(results)} tickets
  - Total coverage: {partial_pct:.0f}% (fully + partially)

HONEST TRUTH:
  Mini is a TRIAGE + FAQ bot, not a full replacement agent.
  It resolves {full_pct:.0f}% fully, assists on {partial_pct:.0f}%, 
  but still needs a human for {100*no_rep/len(results):.0f}%.
""")

    log(f"Results saved: {RESULTS_PATH}")
    log(f"Log saved: {LOG_PATH}")


if __name__ == "__main__":
    asyncio.run(run_full_test())
