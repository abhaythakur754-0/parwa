#!/usr/bin/env python3
"""Quick 6-ticket autonomous observer — runs one ticket at a time."""

from __future__ import annotations

import asyncio, json, os, sys, time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ["PARWA_MOCK_MODE"] = "false"

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

TICKETS = [
    ("mini", "CUST-1004", "My card ending in 4532 keeps getting declined even though I updated it last week. I have been charged 89.99 for order ORD-2004 that I never placed, and my account shows suspended but nobody told me why. My SSN is 457-82-9101 verify my identity and fix this immediately. Also I want to cancel my subscription, this is ridiculous. I have been a premium customer for 3 years and this is how I get treated? If this is not resolved today I am filing a complaint with the FTC. My email is chen.wei@protonmail.com and phone is +1-408-555-0147."),
    ("mini", "CUST-1007", "This is the SECOND time I am writing about the same issue. My wireless headphones from ORD-2005 stopped working after 2 weeks and I already have an open ticket that nobody has responded to. I want a full refund of 129.99 AND I want to know why your support takes so long. At this point I am wondering if I should just dispute the charge with my bank. The sound cuts out randomly and the left earpiece gets hot this is a safety issue. Fix it or refund me, I do not want another replacement."),
    ("parwa", "CUST-1003", "Hi, I am writing about invoice INV-3001 that has been pending for 2 weeks now. We are an enterprise client and this kind of delay is unacceptable for our accounts payable cycle. My finance team is asking questions and frankly I do not have answers. The amount is 4250 for the Q2 licensing and we were promised processing within 3 business days. I brought this up in our last quarterly review and was told it would be prioritized. At this point I need to explore whether we have grounds for breach of contract. Our legal department has been informed. Please provide a status update and a firm resolution timeline. This is the third time we have had billing issues this year."),
    ("parwa", "CUST-1001", "I just noticed I was charged 189.99 TWICE for the same order ORD-2001 on June 1st. One charge shows on my June statement and another pending charge appeared yesterday. I only ordered the Premium Headphones and USB-C Cable once. Can you check your records? I also have order ORD-2002 that was shipped last week the tracking TRK-88292 has not updated in 4 days. Is there a shipping issue? I need the duplicate charge removed and an update on my other order delivery."),
    ("high", "CUST-1006", "Ugh, I have been trying to get the new API integration working for a week and the docs are terrible. Every time I call the /v2/transactions endpoint I get a 503 error. Is there an outage? Also my colleague said we got overcharged on last month invoice but I have not had time to check. And why does the dashboard keep logging me out every 10 minutes? This is so annoying. I just want things to work. Also can someone tell me if our enterprise plan includes priority support? Because I feel like I am getting basic-tier response times. Not mad, just tired of spending hours on stuff that should just work."),
    ("high", "CUST-1008", "I returned the defective monitor from ORD-2006 two weeks ago and your return center confirmed they received it on June 3rd tracking shows delivered. But I still have not received my refund of 349.99. Your return policy says 5-7 business days and it has been 10 business days. Also, when I called customer service last week, the agent said they could not find my return in the system and told me to just wait. That is not acceptable I have the return confirmation email and the delivery receipt. Process my refund immediately or I will dispute the original charge with my credit card company."),
]

async def run():
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm, get_crm
    
    results = []
    
    print(f"\n{'='*120}")
    print(f"  AUTONOMOUS OBSERVER — 6 TICKETS (2 per variant) — NO ASSISTANT EVALUATION")
    print(f"{'='*120}")
    
    for variant, cust_id, msg in TICKETS:
        reset_parwa_graph()
        reset_crm()
        
        # Add to CRM
        try:
            crm = get_crm()
            tkt = crm.create_ticket(customer_id=cust_id, subject=f"Support - {variant}")
            crm_tkt = tkt['ticket_id']
        except:
            crm_tkt = "N/A"
        
        start = time.time()
        try:
            r = await aprocess_ticket(raw_message=msg, customer_id=cust_id, channel='email', variant=variant)
            elapsed = time.time() - start
            
            entry = {
                "variant": variant, "customer_id": cust_id, "crm_ticket": crm_tkt,
                "time_s": round(elapsed, 1),
                "intent": str(r.get("intent", "?")),
                "confidence": r.get("intent_confidence", 0),
                "sentiment": str(r.get("sentiment", "?")),
                "escalate": r.get("should_escalate", False),
                "esc_reason": r.get("escalation_trigger_reason", ""),
                "multi_intent": r.get("multi_intent_detected", False),
                "detected_intents": r.get("detected_intents", []),
                "clarifying_q": r.get("clarifying_question", "")[:100],
                "pii_detected": r.get("pii_detected", False),
                "quality_score": r.get("quality_score", 0),
                "frameworks": len(r.get("active_frameworks", [])),
                "evidence": len(r.get("evidence_chain", [])),
                "reasoning": len(r.get("reasoning_chain", [])),
                "actions": [],
                "errors": r.get("pipeline_errors", []),
                "response": r.get("final_response", "")[:300],
            }
            for ap in r.get("action_plans", [])[:3]:
                if hasattr(ap, 'action_type'):
                    entry["actions"].append(f"{ap.action_type}: {ap.description[:40] if ap.description else ''}")
                elif isinstance(ap, dict):
                    entry["actions"].append(f"{ap.get('action_type')}: {ap.get('description','')[:40]}")
            
            results.append(entry)
            
            print(f"  {variant.upper():<6} {cust_id:<12} | intent={entry['intent']:<22} conf={entry['confidence']:.2f} | sent={entry['sentiment']:<25} esc={str(entry['escalate']):<5} multi={str(entry['multi_intent']):<6} det={entry['detected_intents']} | qual={entry['quality_score']:<5} fw={entry['frameworks']} ev={entry['evidence']} reas={entry['reasoning']} | pii={entry['pii_detected']} | {entry['time_s']}s")
            if entry['actions']:
                for a in entry['actions'][:2]:
                    print(f"    → {a}")
            if entry['errors']:
                print(f"    ERRORS: {entry['errors']}")
                
        except Exception as e:
            elapsed = time.time() - start
            results.append({"variant": variant, "customer_id": cust_id, "error": str(e), "time_s": round(elapsed, 1)})
            print(f"  {variant.upper():<6} {cust_id:<12} | FAILED: {e}")
        
        await asyncio.sleep(2)
    
    # Save
    output_path = "/home/z/my-project/download/autonomous_6ticket_results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"timestamp": datetime.now().isoformat(), "note": "ASSISTANT DID NOT EVALUATE", "results": results}, f, indent=2, default=str)
    
    print(f"\n  Results saved to: {output_path}")

asyncio.run(run())
