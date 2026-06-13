#!/usr/bin/env python3
"""Autonomous Observer — Hands-off variant testing.

Creates 3 TOUGH tickets (one per variant), adds them to CRM,
runs each through its assigned variant, and outputs ONLY raw results.

ASSISTANT DOES NOT EVALUATE. ASSISTANT DOES NOT PARTICIPATE.
Just observe what the system produces on its own.

Usage:
    python -m parwa.eval.autonomous_observer
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

logging.basicConfig(
    level=logging.WARNING,  # Quiet — only show warnings/errors
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger("parwa.autonomous_observer")

# ════════════════════════════════════════════════════════════════════════════════
# 3 TOUGH TICKETS — targeting known weak spots of each variant
# ════════════════════════════════════════════════════════════════════════════════

# TICKET 1 → MINI VARIANT
# Weak spots: No PII guard, no escalation decision, can't handle multi-intent,
#             simpler reasoning, no situation model, no policy guard
# Strategy: Hidden PII + multi-intent (billing + cancellation) + subtle escalation signal
MINI_TICKET = {
    "customer_id": "CUST-1004",  # Chen Wei — suspended, card declined 3x
    "message": (
        "My card ending in 4532 keeps getting declined even though I updated it last week. "
        "I've been charged $89.99 for order ORD-2004 that I never placed, and my account shows suspended "
        "but nobody told me why. My SSN is 457-82-9101 — verify my identity and fix this immediately. "
        "Also I want to cancel my subscription, this is ridiculous. I've been a premium customer for 3 years "
        "and this is how I get treated? If this isn't resolved today I'm filing a complaint with the FTC. "
        "My email is chen.wei@protonmail.com and phone is +1-408-555-0147."
    ),
    "expected": {
        "intent": "billing_issue",       # Actually multi-intent: billing + cancellation
        "sentiment": "angry",            # NOT frustrated — it's escalated anger with legal threat
        "escalation": True,              # Legal threat ("FTC complaint") = must escalate
        "pii_detected": True,            # SSN exposed — must flag
    }
}

# TICKET 2 → PARWA VARIANT
# Weak spots: Might miss subtle escalation signals, might misclassify
#             mixed intent as primary only, sentiment can be wrong on surface-neutral
# Strategy: Looks like simple complaint but has buried legal threat + wrong sentiment surface
PARWA_TICKET = {
    "customer_id": "CUST-1003",  # Aisha Patel — enterprise, $28,750 LTV, pending invoice
    "message": (
        "Hi, I'm writing about invoice INV-3001 that's been pending for 2 weeks now. "
        "We're an enterprise client and this kind of delay is unacceptable for our accounts payable cycle. "
        "My finance team is asking questions and frankly I don't have answers. "
        "The amount is $4,250 for the Q2 licensing and we were promised processing within 3 business days. "
        "I brought this up in our last quarterly review and was told it would be prioritized. "
        "At this point I need to explore whether we have grounds for breach of contract. "
        "Our legal department has been informed. Please provide a status update and a firm resolution timeline. "
        "This is the third time we've had billing issues this year."
    ),
    "expected": {
        "intent": "billing_issue",       # Not complaint — it's a billing/invoice issue
        "sentiment": "frustrated",       # NOT neutral — "unacceptable", "breach of contract", third time
        "escalation": True,              # Legal dept informed + breach of contract = escalate
        "pii_detected": False,           # No PII in this message
    }
}

# TICKET 3 → HIGH VARIANT
# Weak spots: Might over-process, over-escalate, or get confused by genuine ambiguity.
#             High variant has ALL nodes — might trip over itself.
# Strategy: Genuinely ambiguous — venting + tech issue + billing question + should NOT escalate
HIGH_TICKET = {
    "customer_id": "CUST-1006",  # Rajesh Kumar — enterprise, $52,300 LTV, top 5 account
    "message": (
        "Ugh, I've been trying to get the new API integration working for a week and the docs are terrible. "
        "Every time I call the /v2/transactions endpoint I get a 503 error. "
        "Is there an outage? Also my colleague said we got overcharged on last month's invoice but I "
        "haven't had time to check. And why does the dashboard keep logging me out every 10 minutes? "
        "This is so annoying. I just want things to work. Also can someone tell me if our enterprise plan "
        "includes priority support? Because I feel like I'm getting basic-tier response times. "
        "Not mad, just tired of spending hours on stuff that should just work."
    ),
    "expected": {
        "intent": "technical_support",   # Primary is tech, secondary is billing
        "sentiment": "frustrated",       # NOT angry — "not mad, just tired"
        "escalation": False,             # No legal threat, no real escalation trigger
        "pii_detected": False,           # No PII
    }
}


async def run_autonomous() -> None:
    """Run 3 tough tickets — one per variant — and dump raw results.
    
    NO EVALUATION. NO PARTICIPATION. JUST OBSERVE.
    """
    os.environ["PARWA_MOCK_MODE"] = "false"
    
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm, get_crm
    
    tickets = [
        ("mini", MINI_TICKET),
        ("parwa", PARWA_TICKET),
        ("high", HIGH_TICKET),
    ]
    
    results = []
    
    for variant, ticket in tickets:
        print(f"\n{'='*80}")
        print(f"  VARIANT: {variant.upper()}  |  CUSTOMER: {ticket['customer_id']}")
        print(f"{'='*80}")
        
        # Reset for clean run
        reset_parwa_graph()
        reset_crm()
        
        # Add ticket to CRM
        crm = get_crm()
        try:
            crm_ticket = crm.create_ticket(
                customer_id=ticket["customer_id"],
                subject=f"Support request - {variant} test"
            )
            print(f"  CRM Ticket Created: {crm_ticket['ticket_id']}")
        except Exception as e:
            print(f"  CRM Error: {e}")
        
        # Process ticket through pipeline
        print(f"  Processing through {variant} pipeline...")
        start = time.time()
        
        try:
            result = await aprocess_ticket(
                raw_message=ticket["message"],
                customer_id=ticket["customer_id"],
                channel="email",
                variant=variant,
            )
            elapsed = time.time() - start
            
            # Extract raw outputs — NO EVALUATION
            raw = {
                "variant": variant,
                "customer_id": ticket["customer_id"],
                "elapsed_seconds": round(elapsed, 2),
                "intent": str(result.get("intent", "N/A")),
                "intent_confidence": result.get("intent_confidence", 0),
                "sentiment": str(result.get("sentiment", "N/A")),
                "should_escalate": result.get("should_escalate", False),
                "escalation_trigger_reason": result.get("escalation_trigger_reason", ""),
                "clarifying_question": result.get("clarifying_question", ""),
                "multi_intent_detected": result.get("multi_intent_detected", False),
                "detected_intents": result.get("detected_intents", []),
                "low_confidence_flag": result.get("low_confidence_flag", False),
                "quality_score": result.get("quality_score", 0),
                "action_plans": result.get("action_plans", []),
                "pii_detected": result.get("pii_detected", False),
                "pii_items_found": result.get("pii_items_found", []),
                "final_response": result.get("final_response", ""),
                "pipeline_errors": result.get("pipeline_errors", []),
                "nodes_executed": result.get("nodes_executed", []),
            }
            
            results.append(raw)
            
            # Print RAW output — no commentary, no evaluation
            print(f"  Time: {elapsed:.1f}s")
            print(f"  ─────────────────────────────────────────────")
            print(f"  Intent:              {raw['intent']}")
            print(f"  Intent Confidence:   {raw['intent_confidence']}")
            print(f"  Sentiment:           {raw['sentiment']}")
            print(f"  Should Escalate:     {raw['should_escalate']}")
            print(f"  Escalation Reason:   {raw['escalation_trigger_reason']}")
            print(f"  Clarifying Question: {raw['clarifying_question']}")
            print(f"  Multi-Intent:        {raw['multi_intent_detected']}")
            print(f"  Detected Intents:    {raw['detected_intents']}")
            print(f"  Low Confidence:      {raw['low_confidence_flag']}")
            print(f"  Quality Score:       {raw['quality_score']}")
            print(f"  PII Detected:        {raw['pii_detected']}")
            print(f"  PII Items Found:     {raw['pii_items_found']}")
            print(f"  Nodes Executed:      {len(raw['nodes_executed'])} nodes")
            if raw['action_plans']:
                for i, ap in enumerate(raw['action_plans'][:3]):
                    if isinstance(ap, dict):
                        print(f"  Action {i+1}: {ap.get('action_type', '?')} → {ap.get('description', '')[:80]}")
            print(f"  ─────────────────────────────────────────────")
            print(f"  Final Response (first 500 chars):")
            print(f"  {raw['final_response'][:500]}")
            if raw['pipeline_errors']:
                print(f"  ERRORS: {raw['pipeline_errors']}")
                
        except Exception as e:
            elapsed = time.time() - start
            print(f"  FAILED after {elapsed:.1f}s: {e}")
            results.append({
                "variant": variant,
                "customer_id": ticket["customer_id"],
                "error": str(e),
                "elapsed_seconds": round(elapsed, 2),
            })
        
        # Rate limit buffer between variants
        if variant != "high":
            print(f"\n  (waiting 3s before next variant...)")
            await asyncio.sleep(3)
    
    # Save raw results
    output_path = "/home/z/my-project/download/autonomous_observer_results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "mode": "autonomous_observer",
        "note": "ASSISTANT DID NOT EVALUATE OR PARTICIPATE. Raw system output only.",
        "tickets": {
            "mini": {
                "customer_id": MINI_TICKET["customer_id"],
                "message_preview": MINI_TICKET["message"][:200],
                "expected": MINI_TICKET["expected"],
            },
            "parwa": {
                "customer_id": PARWA_TICKET["customer_id"],
                "message_preview": PARWA_TICKET["message"][:200],
                "expected": PARWA_TICKET["expected"],
            },
            "high": {
                "customer_id": HIGH_TICKET["customer_id"],
                "message_preview": HIGH_TICKET["message"][:200],
                "expected": HIGH_TICKET["expected"],
            },
        },
        "results": results,
    }
    
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n\n{'='*80}")
    print(f"  RAW RESULTS SAVED TO: {output_path}")
    print(f"{'='*80}")
    
    # Print comparison — RAW ONLY, no evaluation
    print(f"\n  SIDE-BY-SIDE RAW OUTPUT (NO EVALUATION):")
    print(f"  {'Field':<25s} {'Mini':<25s} {'Parwa':<25s} {'High':<25s}")
    print(f"  {'─'*25} {'─'*25} {'─'*25} {'─'*25}")
    
    if len(results) == 3 and not any("error" in r for r in results):
        fields = [
            ("intent", "intent"),
            ("confidence", "intent_confidence"),
            ("sentiment", "sentiment"),
            ("escalate", "should_escalate"),
            ("escal_reason", "escalation_trigger_reason"),
            ("multi_intent", "multi_intent_detected"),
            ("low_conf", "low_confidence_flag"),
            ("quality", "quality_score"),
            ("pii_detected", "pii_detected"),
            ("nodes", "nodes_executed"),
            ("time_s", "elapsed_seconds"),
        ]
        for label, key in fields:
            vals = []
            for r in results:
                v = r.get(key, "N/A")
                if isinstance(v, list):
                    v = len(v)
                elif isinstance(v, bool):
                    v = str(v)
                elif isinstance(v, float):
                    v = f"{v:.2f}" if v < 10 else f"{v:.0f}"
                vals.append(str(v)[:24])
            print(f"  {label:<25s} {vals[0]:<25s} {vals[1]:<25s} {vals[2]:<25s}")
    
    print()


if __name__ == "__main__":
    asyncio.run(run_autonomous())
