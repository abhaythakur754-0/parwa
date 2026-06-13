#!/usr/bin/env python3
"""PARWA Mini — Resilient Single-Ticket Test Runner.

Processes one ticket at a time, saving results incrementally.
Designed to survive rate limits and API failures.

Usage: python3 mini_resilient_test.py [start_index] [count]
  start_index: 0-based index of first ticket (default: 0)
  count: number of tickets to process (default: 15)
"""

import asyncio
import json
import os
import sys
import time
import traceback
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ["PARWA_MOCK_MODE"] = "false"

# Suppress most logs except errors
import logging
logging.basicConfig(level=logging.ERROR)


RESULTS_PATH = "/home/z/my-project/download/mini_honest_results.json"


# ─── Ticket Definitions ──────────────────────────────────────────────────────

TICKETS = [
    # EASY (5)
    {"id":"MINI-E01","ch":"chat","cust":"CUST-1001","subj":"Where is my order?","body":"I placed an order 5 days ago and haven't received any shipping updates. Can you check order ORD-2002?","cat":"order_status","diff":"easy","can":"yes"},
    {"id":"MINI-E02","ch":"chat","cust":"CUST-1005","subj":"When will my package arrive?","body":"My order ORD-2040 was shipped. When should I expect it?","cat":"order_status","diff":"easy","can":"yes"},
    {"id":"MINI-E03","ch":"email","cust":"CUST-1008","subj":"What is your refund policy?","body":"Hi, I was wondering what your refund policy is. Can you let me know the details?","cat":"faq","diff":"easy","can":"yes"},
    {"id":"MINI-E04","ch":"chat","cust":"CUST-1002","subj":"Do you offer express shipping?","body":"I need something delivered fast. Do you have express shipping options?","cat":"faq","diff":"easy","can":"yes"},
    {"id":"MINI-E05","ch":"email","cust":"CUST-1007","subj":"App keeps crashing","body":"Your mobile app crashes every time I open it. I'm on Android 14, Samsung Galaxy S24. Please help.","cat":"tech_support","diff":"easy","can":"yes"},
    # MEDIUM (5)
    {"id":"MINI-M01","ch":"email","cust":"CUST-1003","subj":"Incorrect charge on my subscription","body":"I was charged $79.99 but my plan is $49.99/month. There's a $30 overcharge. Fix this and refund the difference.","cat":"billing_dispute","diff":"medium","can":"partially"},
    {"id":"MINI-M02","ch":"chat","cust":"CUST-1004","subj":"My account is suspended","body":"I can't access my account. It says suspended. What happened? I need it fixed now.","cat":"account_suspended","diff":"medium","can":"partially"},
    {"id":"MINI-M03","ch":"email","cust":"CUST-1002","subj":"Update my billing address","body":"I moved and need to update my billing address to 123 New Street, New City, NY 10001.","cat":"account_modification","diff":"medium","can":"partially"},
    {"id":"MINI-M04","ch":"chat","cust":"CUST-1001","subj":"I think I was charged twice","body":"Hey, I see two charges of $189.99 on my card for the same order. Can you check?","cat":"duplicate_charge","diff":"medium","can":"partially"},
    {"id":"MINI-M05","ch":"email","cust":"CUST-1005","subj":"How do I return my keyboard?","body":"I bought a Mechanical Keyboard (ORD-2040) but it doesn't feel right. I want to return it.","cat":"return_request","diff":"medium","can":"partially"},
    # HARD (5)
    {"id":"MINI-H01","ch":"email","cust":"CUST-1001","subj":"I want a FULL REFUND NOW","body":"The Premium Headphones I received are completely broken! No sound from the left ear. I paid $189.99 and I want EVERY penny back!","cat":"refund_angry","diff":"hard","can":"partially"},
    {"id":"MINI-H02","ch":"chat","cust":"CUST-1006","subj":"Our integration stopped working","body":"Our API integration has been down for 2 hours. We're an enterprise customer and this is costing us revenue. We need this fixed immediately.","cat":"enterprise_critical","diff":"hard","can":"partially"},
    {"id":"MINI-H03","ch":"email","cust":"CUST-1004","subj":"Speak to a MANAGER","body":"This is the THIRD time my account has been suspended because of your billing system errors. I DEMAND to speak to a manager!","cat":"escalation_angry","diff":"hard","can":"yes"},
    {"id":"MINI-H04","ch":"chat","cust":"CUST-1003","subj":"Custom invoice needed","body":"We need a custom invoice format for our 50-seat enterprise license that includes our company tax ID and purchase order number.","cat":"custom_request","diff":"hard","can":"no"},
    {"id":"MINI-H05","ch":"email","cust":"CUST-1007","subj":"REFUND AND compensation","body":"Your Design Software crashed and I lost 4 hours of work. I want a refund for the license ($199.99) AND compensation for my lost time!","cat":"complex_refund","diff":"hard","can":"partially"},
]


def score_ticket(ticket: dict, state: dict, elapsed: float) -> dict:
    """Score a ticket result honestly."""
    cat = ticket["cat"]
    diff = ticket["diff"]
    resp = str(state.get("final_response", "")).lower()
    quality = float(state.get("quality_score", 0) or 0)
    escalated = bool(state.get("escalated", False))
    errors = state.get("pipeline_errors", [])
    intent = str(state.get("intent", "unknown"))
    sentiment = str(state.get("sentiment", "unknown"))

    resolution = "PARTIAL"
    explanation = ""
    replaces = "partially"

    if cat in ("order_status", "faq", "tech_support"):
        if escalated:
            resolution, explanation, replaces = "PARTIAL", "Escalated when should handle autonomously", "partially"
        elif any(kw in resp for kw in ["tracking","shipped","delivered","trk-","refund policy","shipping","express","troubleshoot","ticket created","return policy","within 30","estimated delivery","june"]):
            resolution, explanation, replaces = "RESOLVED", "Correct information provided autonomously", "yes"
        elif len(resp) > 80:
            resolution, explanation, replaces = "PARTIAL", "Response given but lacks specific details", "partially"
        else:
            resolution, explanation, replaces = "FAILED", "Response too short/generic", "no"
    elif cat in ("billing_dispute","account_suspended","account_modification","duplicate_charge","return_request"):
        if escalated:
            resolution, explanation, replaces = "RESOLVED", "Correctly collected info and escalated", "partially"
        elif any(kw in resp for kw in ["recommend","approval","manager","flag","unable to","cannot","can't process","need to","will need","has been flagged","escalat","review"]):
            resolution, explanation, replaces = "RESOLVED", "Correctly identified and recommended/flagged", "partially"
        elif any(kw in resp for kw in ["refund","charge","payment","address","suspended","duplicate","return","account","billing","overcharge"]):
            resolution, explanation, replaces = "PARTIAL", "Addressed topic but unclear constraint", "partially"
        else:
            resolution, explanation, replaces = "PARTIAL", "Responded but unclear handling", "partially"
    elif cat in ("refund_angry","escalation_angry"):
        if escalated or "escalat" in resp or "manager" in resp or "human" in resp or "supervisor" in resp:
            resolution, explanation, replaces = "RESOLVED", "Correctly escalated angry customer", "partially"
        elif "refund" in resp and "recommend" not in resp and "approval" not in resp:
            resolution, explanation, replaces = "WRONG", "Tried to execute refund instead of escalating", "no"
        else:
            resolution, explanation, replaces = "PARTIAL", "Unclear if escalation happened", "partially"
    elif cat == "enterprise_critical":
        if escalated or "escalat" in resp or "account manager" in resp or "dedicated" in resp or "priority" in resp:
            resolution, explanation, replaces = "RESOLVED", "Correctly escalated enterprise issue", "partially"
        else:
            resolution, explanation, replaces = "PARTIAL", "May not have recognized enterprise urgency", "no"
    elif cat == "custom_request":
        if escalated or any(kw in resp for kw in ["account manager","team","specialist","billing department","finance"]):
            resolution, explanation, replaces = "RESOLVED", "Correctly flagged as beyond capabilities", "partially"
        else:
            resolution, explanation, replaces = "FAILED", "Cannot handle custom enterprise requests", "no"
    elif cat == "complex_refund":
        if escalated or any(kw in resp for kw in ["recommend","approval","manager","escalat"]):
            resolution, explanation, replaces = "RESOLVED", "Complex refund correctly escalated/recommended", "partially"
        else:
            resolution, explanation, replaces = "PARTIAL", "May not have addressed all parts", "no"

    human_times = {"order_status":1.5,"faq":0.5,"tech_support":2.0,"billing_dispute":5.0,"account_suspended":6.0,"account_modification":3.0,"duplicate_charge":4.0,"return_request":5.0,"refund_angry":7.0,"enterprise_critical":12.0,"escalation_angry":15.0,"custom_request":12.0,"complex_refund":18.0}

    return {
        "ticket_id": ticket["id"], "category": cat, "difficulty": diff,
        "intent": intent, "sentiment": sentiment, "quality_score": quality,
        "resolution": resolution, "score_explanation": explanation,
        "escalated": escalated, "processing_time_seconds": round(elapsed, 2),
        "mini_replaces_human": replaces,
        "human_time_minutes": human_times.get(cat, 5.0),
        "final_response": str(state.get("final_response", ""))[:800],
        "pipeline_errors": errors[:3] if errors else [],
    }


def load_results() -> list[dict]:
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH) as f:
            return json.load(f)
    return []


def save_results(results: list[dict]):
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)


async def process_one(ticket: dict) -> dict:
    """Process a single ticket through the Mini PARWA pipeline."""
    from parwa.graph import aprocess_ticket

    start = time.time()
    try:
        state = await aprocess_ticket(
            raw_message=ticket["body"],
            customer_id=ticket["cust"],
            channel=ticket["ch"],
            variant="mini",
            interrupt_before_action=False,
        )
        elapsed = time.time() - start
        return score_ticket(ticket, state, elapsed)
    except Exception as e:
        elapsed = time.time() - start
        return {
            "ticket_id": ticket["id"], "category": ticket["cat"],
            "difficulty": ticket["diff"], "resolution": "FAILED",
            "score_explanation": f"Pipeline crashed: {str(e)[:100]}",
            "mini_replaces_human": "no", "processing_time_seconds": round(elapsed, 2),
            "quality_score": 0, "escalated": False,
            "human_time_minutes": 5.0,
            "final_response": f"ERROR: {str(e)[:200]}",
            "intent": "error", "sentiment": "error",
            "pipeline_errors": [{"error": str(e)[:200]}],
        }


async def main():
    start_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 15

    results = load_results()
    done_ids = {r["ticket_id"] for r in results}

    batch = TICKETS[start_idx:start_idx + count]
    remaining = [t for t in batch if t["id"] not in done_ids]

    print(f"PARWA MINI TEST — Processing {len(remaining)} tickets (skip {len(batch)-len(remaining)} done)", flush=True)

    for i, ticket in enumerate(remaining, 1):
        tid = ticket["id"]
        print(f"\n[{i}/{len(remaining)}] {tid} — {ticket['subj']}", flush=True)

        result = await process_one(ticket)
        results.append(result)
        save_results(results)

        print(f"  Intent: {result['intent']} | Sent: {result['sentiment']} | Q: {result['quality_score']:.0f}", flush=True)
        print(f"  Escalated: {result['escalated']} | Time: {result['processing_time_seconds']:.1f}s", flush=True)
        print(f"  >>> {result['resolution']} | Replaces: {result['mini_replaces_human']} | {result['score_explanation']}", flush=True)
        resp_short = result['final_response'][:200].replace('\n', ' ')
        print(f"  Resp: {resp_short}...", flush=True)

        # Rate limit: wait between tickets
        if i < len(remaining):
            await asyncio.sleep(5)

    # Summary
    if len(results) >= 15 or len(remaining) == 0:
        print(f"\n\n{'='*70}", flush=True)
        print("FINAL REPORT — MINI PARWA ($1,000/month)", flush=True)
        print(f"{'='*70}", flush=True)

        resolved = sum(1 for r in results if r["resolution"] == "RESOLVED")
        partial = sum(1 for r in results if r["resolution"] == "PARTIAL")
        failed = sum(1 for r in results if r["resolution"] in ("FAILED", "WRONG"))

        print(f"\nRESOLVED: {resolved} | PARTIAL: {partial} | FAILED: {failed} / {len(results)}", flush=True)

        yes_r = sum(1 for r in results if r["mini_replaces_human"] == "yes")
        par_r = sum(1 for r in results if r["mini_replaces_human"] == "partially")
        no_r = sum(1 for r in results if r["mini_replaces_human"] == "no")

        print(f"Fully replaces human: {yes_r}/{len(results)} ({100*yes_r/len(results):.0f}%)", flush=True)
        print(f"Partially replaces: {par_r}/{len(results)} ({100*par_r/len(results):.0f}%)", flush=True)
        print(f"Cannot replace: {no_r}/{len(results)} ({100*no_r/len(results):.0f}%)", flush=True)

        for r in results:
            print(f"  {r['ticket_id']:<12} {r['category']:<20} {r['difficulty']:<6} {r['resolution']:<10} {r['mini_replaces_human']:<10} {r['processing_time_seconds']:.1f}s Q:{r['quality_score']:.0f}", flush=True)

    print(f"\nResults saved: {RESULTS_PATH}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
