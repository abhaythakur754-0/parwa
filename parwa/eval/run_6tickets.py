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
    # ─── MINI variant (2 tickets) ───
    # Ticket 1: COMPOUND — billing + escalation threat + PII + account suspended
    # Tests: Bug #1 (escalation should NOT bypass pipeline), Bug #2 (billing NOT escalation),
    #        Bug #7 (LLM-first response should be specific, not generic)
    ("mini", "CUST-1004", "I was charged $89.99 for order ORD-2030 on May 10th and then AGAIN on June 1st for the same order. My account shows suspended because your system tried to charge my card 3 times for the SAME subscription. I have been a premium customer for 2 years and this is unacceptable. If this duplicate charge and account suspension are not fixed today, I am filing a complaint with the FTC and contacting my attorney about consumer fraud. My SSN is 457-82-9101 for verification. Fix my account, refund the duplicate charge, and cancel the $59.99 monthly subscription I never agreed to renew."),

    # Ticket 2: MULTI-INTENT — technical issue + refund request + complaint about being ignored
    # Tests: Bug #3 (multi-intent detection), quality of compound response
    ("mini", "CUST-1007", "This is my THIRD email about the same problem. The Design Software from order ORD-2060 crashes every time I open a project file larger than 50MB. I have 2 open tickets (TKT-4040 and TKT-4041) and NOBODY has responded to either one in over a week. At this point I want a full refund of $249.98 because the software is completely unusable for my work. The plugin pack is also broken. I am a professional designer and I am losing client projects because of this. Either fix the crashing issue OR give me my money back — I do not want another 'we are looking into it' response."),

    # ─── PARWA variant (2 tickets) ───
    # Ticket 3: ENTERPRISE + legal threat + billing — must solve the billing AND escalate
    # Tests: Bug #1 (pipeline must continue despite escalation), Bug #2 (billing_issue not just escalation)
    ("parwa", "CUST-1003", "We have a serious billing discrepancy that needs immediate attention. Invoice for Q2 licensing ($4,999.00) shows as pending in your system for 2 weeks despite our wire transfer PAY-3020 being completed on May 15th. Additionally, the 10 additional seats on order ORD-2021 ($499.90) have not been provisioned despite the order being placed on June 1st. Our legal department has reviewed the contract and we may have grounds for breach of contract if this is not resolved within 48 hours. This is the THIRD billing issue we have had this year. As an enterprise account with a $52,300 lifetime value, we expect the dedicated support we were promised. Please process the invoice, provision the seats, and have our account manager Raj K. contact us directly."),

    # Ticket 4: DUPLICATE CHARGE + shipping delay — two real issues to solve
    # Tests: Bug #3 (multi-intent), quality of specific data in response
    ("parwa", "CUST-1001", "I was charged $189.99 TWICE for order ORD-2001 on the same day (June 1st). I see PAY-3001 and PAY-3002 both for $189.99 on my statement. I only ordered Premium Headphones and USB-C Cable ONCE. Please refund the duplicate charge immediately. Also, my order ORD-2002 (Wireless Charger, $49.99) was shipped on June 5th with tracking TRK-88292 but the tracking has not updated in 4 days. Is there a shipping problem? I need both issues resolved — the duplicate charge AND the shipping delay."),

    # ─── HIGH variant (2 tickets) ───
    # Ticket 5: COMPLEX MULTI-ISSUE — API errors + billing overcharge + dashboard bug + enterprise complaint
    # Tests: Bug #3 (multi-intent), Bug #4 (FrameworkBrain should activate), compound resolution
    ("high", "CUST-1006", "Three critical issues on our enterprise account that need resolution: 1) API endpoint /v2/transactions returns 503 errors consistently — our integration is down and we cannot process transactions. Order ORD-2052 for API Access Tier 3 ($999) is still processing after 2 weeks. 2) Our finance team flagged an overcharge on the last invoice — we were billed for 200 seats at $4,999 but our contract shows 200 seats at $2,499.50 each. That is a $499.50 discrepancy. 3) The dashboard logs out every 10 minutes making it impossible to use. We pay $4,999/month for Enterprise Plus with 200 seats and a 1-hour response SLA. Our dedicated team Sunita and Arjun have not responded to our messages. At this point we need to know if we should start evaluating other vendors because this level of service is not what was promised in our contract."),

    # Ticket 6: REFUND + escalation threat — returned product, refund not processed, CS failed
    # Tests: Bug #1 (escalation flag set but pipeline continues), Bug #2 (refund_request not just escalation),
    #        LLM-first response should mention specific amounts and dates
    ("high", "CUST-1008", "I returned the defective monitor from ORD-2070 on May 20th and your return center confirmed receipt on May 25th. Tracking shows delivered. But I still have NOT received my $349.99 refund. Your return policy says 5-7 business days — it has been 15 business days. When I called support last week, the agent could not find my return and told me to 'just wait.' I have the return confirmation email and delivery receipt. I also see you already charged me $349.99 for the replacement monitor on ORD-2071. Process my refund for ORD-2070 immediately or I will dispute both charges with my credit card company and file a complaint with the Consumer Financial Protection Bureau. I want a specific answer: when will the $349.99 be in my account?"),
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
