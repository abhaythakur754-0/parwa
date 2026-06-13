#!/usr/bin/env python3
"""Autonomous Observer — 6 Tickets, 2 Per Variant, No Assistant Involvement.

Creates 6 genuinely tough tickets, adds them to CRM, runs each variant
on its 2 assigned tickets. Just observes raw output.

ASSISTANT DOES NOT EVALUATE. ASSISTANT DOES NOT PARTICIPATE.
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
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger("parwa.autonomous_observer")

# ════════════════════════════════════════════════════════════════════════════════
# 6 TOUGH TICKETS — 2 per variant, targeting known weak spots
# ════════════════════════════════════════════════════════════════════════════════

TICKETS = {
    "mini": [
        {
            "customer_id": "CUST-1004",  # Chen Wei — suspended, card declined 3x
            "message": (
                "My card ending in 4532 keeps getting declined even though I updated it last week. "
                "I've been charged $89.99 for order ORD-2004 that I never placed, and my account shows suspended "
                "but nobody told me why. My SSN is 457-82-9101 — verify my identity and fix this immediately. "
                "Also I want to cancel my subscription, this is ridiculous. I've been a premium customer for 3 years "
                "and this is how I get treated? If this isn't resolved today I'm filing a complaint with the FTC. "
                "My email is chen.wei@protonmail.com and phone is +1-408-555-0147."
            ),
        },
        {
            "customer_id": "CUST-1007",  # Emily Rodriguez — frustrated, 2 open tech tickets
            "message": (
                "This is the SECOND time I'm writing about the same issue. My wireless headphones from ORD-2005 "
                "stopped working after 2 weeks and I already have an open ticket that nobody has responded to. "
                "I want a full refund of $129.99 AND I want to know why your support takes so long. "
                "At this point I'm wondering if I should just dispute the charge with my bank. "
                "The sound cuts out randomly and the left earpiece gets hot — this is a safety issue. "
                "Fix it or refund me, I don't want another replacement."
            ),
        },
    ],
    "parwa": [
        {
            "customer_id": "CUST-1003",  # Aisha Patel — enterprise, $28,750 LTV
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
        },
        {
            "customer_id": "CUST-1001",  # Priya Sharma — premium, duplicate charge
            "message": (
                "I just noticed I was charged $189.99 TWICE for the same order ORD-2001 on June 1st. "
                "One charge shows on my June statement and another pending charge appeared yesterday. "
                "I only ordered the Premium Headphones and USB-C Cable once. Can you check your records? "
                "I also have order ORD-2002 that was shipped last week — the tracking TRK-88292 hasn't updated "
                "in 4 days. Is there a shipping issue? I need the duplicate charge removed and an update on "
                "my other order's delivery."
            ),
        },
    ],
    "high": [
        {
            "customer_id": "CUST-1006",  # Rajesh Kumar — enterprise, $52,300 LTV
            "message": (
                "Ugh, I've been trying to get the new API integration working for a week and the docs are terrible. "
                "Every time I call the /v2/transactions endpoint I get a 503 error. "
                "Is there an outage? Also my colleague said we got overcharged on last month's invoice but I "
                "haven't had time to check. And why does the dashboard keep logging me out every 10 minutes? "
                "This is so annoying. I just want things to work. Also can someone tell me if our enterprise plan "
                "includes priority support? Because I feel like I'm getting basic-tier response times. "
                "Not mad, just tired of spending hours on stuff that should just work."
            ),
        },
        {
            "customer_id": "CUST-1008",  # Yuki Tanaka — standard, returned defective monitor
            "message": (
                "I returned the defective monitor from ORD-2006 two weeks ago and your return center confirmed "
                "they received it on June 3rd (tracking shows delivered). But I still haven't received my refund "
                "of $349.99. Your return policy says 5-7 business days and it's been 10 business days. "
                "Also, when I called customer service last week, the agent said they couldn't find my return "
                "in the system and told me to 'just wait.' That's not acceptable — I have the return confirmation "
                "email and the delivery receipt. Process my refund immediately or I'll dispute the original charge "
                "with my credit card company."
            ),
        },
    ],
}


async def run_autonomous() -> None:
    """Run 6 tough tickets — 2 per variant — and dump raw results.
    
    NO EVALUATION. NO PARTICIPATION. JUST OBSERVE.
    """
    os.environ["PARWA_MOCK_MODE"] = "false"
    
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm, get_crm
    
    all_results = {}
    
    for variant in ["mini", "parwa", "high"]:
        tickets = TICKETS[variant]
        all_results[variant] = []
        
        for idx, ticket in enumerate(tickets):
            print(f"\n{'='*80}")
            print(f"  VARIANT: {variant.upper()}  |  TICKET {idx+1}/2  |  CUSTOMER: {ticket['customer_id']}")
            print(f"{'='*80}")
            
            # Reset for clean run
            reset_parwa_graph()
            reset_crm()
            
            # Add ticket to CRM
            crm = get_crm()
            try:
                crm_ticket = crm.create_ticket(
                    customer_id=ticket["customer_id"],
                    subject=f"Support request - {variant} test {idx+1}"
                )
                print(f"  CRM Ticket: {crm_ticket['ticket_id']}")
            except Exception as e:
                print(f"  CRM Error: {e}")
            
            # Process
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
                
                raw = {
                    "variant": variant,
                    "ticket_num": idx + 1,
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
                    "action_plans": [],
                    "pii_detected": result.get("pii_detected", False),
                    "pii_items_found": result.get("pii_items_found", []),
                    "active_frameworks": result.get("active_frameworks", []),
                    "evidence_chain_count": len(result.get("evidence_chain", [])),
                    "reasoning_chain": result.get("reasoning_chain", [])[:2] if result.get("reasoning_chain") else [],
                    "pipeline_errors": result.get("pipeline_errors", []),
                    "final_response": result.get("final_response", ""),
                }
                
                # Extract action plans safely
                for ap in result.get("action_plans", [])[:5]:
                    if hasattr(ap, 'action_type'):
                        raw["action_plans"].append({
                            "action_type": str(ap.action_type),
                            "description": ap.description[:80] if ap.description else "",
                            "mode": str(ap.mode),
                        })
                    elif isinstance(ap, dict):
                        raw["action_plans"].append({
                            "action_type": str(ap.get("action_type", "?")),
                            "description": str(ap.get("description", ""))[:80],
                            "mode": str(ap.get("mode", "")),
                        })
                
                all_results[variant].append(raw)
                
                # Print RAW output
                print(f"  Time: {elapsed:.1f}s")
                print(f"  ─────────────────────────────────────────────")
                print(f"  Intent:              {raw['intent']}")
                print(f"  Intent Confidence:   {raw['intent_confidence']}")
                print(f"  Sentiment:           {raw['sentiment']}")
                print(f"  Should Escalate:     {raw['should_escalate']}")
                print(f"  Escalation Reason:   {raw['escalation_trigger_reason']}")
                print(f"  Multi-Intent:        {raw['multi_intent_detected']}")
                print(f"  Detected Intents:    {raw['detected_intents']}")
                print(f"  Clarifying Question: {raw['clarifying_question'][:100] if raw['clarifying_question'] else 'None'}")
                print(f"  Low Confidence:      {raw['low_confidence_flag']}")
                print(f"  Quality Score:       {raw['quality_score']}")
                print(f"  PII Detected:        {raw['pii_detected']}")
                print(f"  Frameworks Active:   {raw['active_frameworks']}")
                print(f"  Evidence Chain:      {raw['evidence_chain_count']} entries")
                print(f"  Reasoning Chain:     {len(raw['reasoning_chain'])} entries")
                if raw['action_plans']:
                    for i, ap in enumerate(raw['action_plans'][:3]):
                        print(f"  Action {i+1}: {ap['action_type']} | {ap['description'][:60]} | mode={ap['mode']}")
                if raw['pipeline_errors']:
                    print(f"  ERRORS: {raw['pipeline_errors']}")
                print(f"  ─────────────────────────────────────────────")
                print(f"  Response (first 400 chars):")
                print(f"  {raw['final_response'][:400]}")
                    
            except Exception as e:
                elapsed = time.time() - start
                print(f"  FAILED after {elapsed:.1f}s: {e}")
                all_results[variant].append({
                    "variant": variant,
                    "ticket_num": idx + 1,
                    "customer_id": ticket["customer_id"],
                    "error": str(e),
                    "elapsed_seconds": round(elapsed, 2),
                })
            
            # Rate limit buffer
            await asyncio.sleep(3)
    
    # Save raw results
    output_path = "/home/z/my-project/download/autonomous_6ticket_results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "mode": "autonomous_observer_6tickets",
        "note": "ASSISTANT DID NOT EVALUATE OR PARTICIPATE. Raw system output only.",
        "results": all_results,
    }
    
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    # Print summary table
    print(f"\n\n{'='*100}")
    print(f"  RAW SUMMARY — 6 TICKETS, 2 PER VARIANT, NO EVALUATION")
    print(f"{'='*100}")
    print(f"  {'Variant':<8} {'Ticket':<8} {'Customer':<12} {'Intent':<22} {'Sentiment':<22} {'Esc':<5} {'Multi':<6} {'Quality':<8} {'Time':<6}")
    print(f"  {'─'*8} {'─'*8} {'─'*12} {'─'*22} {'─'*22} {'─'*5} {'─'*6} {'─'*8} {'─'*6}")
    
    for variant in ["mini", "parwa", "high"]:
        for r in all_results[variant]:
            if "error" not in r:
                intent = str(r.get("intent", "?"))[:20]
                sentiment = str(r.get("sentiment", "?"))[:20]
                esc = str(r.get("should_escalate", "?"))[:4]
                multi = str(r.get("multi_intent_detected", "?"))[:5]
                quality = str(r.get("quality_score", "?"))[:7]
                t = f"{r.get('elapsed_seconds', 0):.0f}s"
                print(f"  {variant:<8} {r.get('ticket_num', '?'):<8} {r.get('customer_id', '?')[:11]:<12} {intent:<22} {sentiment:<22} {esc:<5} {multi:<6} {quality:<8} {t:<6}")
            else:
                print(f"  {variant:<8} {r.get('ticket_num', '?'):<8} {r.get('customer_id', '?')[:11]:<12} ERROR: {r['error'][:60]}")
    
    print(f"\n  Results saved to: {output_path}")
    print()


if __name__ == "__main__":
    asyncio.run(run_autonomous())
