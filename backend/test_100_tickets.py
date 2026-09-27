"""
100-Ticket Variant Pipeline Test — Tests all 3 variants (mini_parwa, parwa, parwa_high)
with realistic customer requests across industries and channels.
"""
import asyncio
import json
import time
import uuid
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

COMPANY_ID = f"test_{uuid.uuid4().hex[:12]}"

# 100 realistic ticket scenarios
TICKETS = [
    # E-commerce (15 tickets)
    {"id": 1, "subject": "Where is my order? It's been 10 days", "industry": "ecommerce", "channel": "chat", "expected_intents": ["shipping"]},
    {"id": 2, "subject": "I received a damaged product, need replacement", "industry": "ecommerce", "channel": "email", "expected_intents": ["complaint", "shipping"]},
    {"id": 3, "subject": "How do I return this item?", "industry": "ecommerce", "channel": "chat", "expected_intents": ["refund"]},
    {"id": 4, "subject": "Wrong size delivered, need exchange ASAP", "industry": "ecommerce", "channel": "sms", "expected_intents": ["shipping", "complaint"]},
    {"id": 5, "subject": "Your website keeps crashing when I try to checkout", "industry": "ecommerce", "channel": "chat", "expected_intents": ["technical"]},
    {"id": 6, "subject": "I was charged twice for the same order", "industry": "ecommerce", "channel": "email", "expected_intents": ["billing", "overcharge"]},
    {"id": 7, "subject": "Can I get a price match on this item?", "industry": "ecommerce", "channel": "chat", "expected_intents": ["billing"]},
    {"id": 8, "subject": "The promo code isn't working at checkout", "industry": "ecommerce", "channel": "chat", "expected_intents": ["billing", "technical"]},
    {"id": 9, "subject": "My account was locked after too many login attempts", "industry": "ecommerce", "channel": "email", "expected_intents": ["account_access", "technical"]},
    {"id": 10, "subject": "I want to cancel my subscription box", "industry": "ecommerce", "channel": "chat", "expected_intents": ["cancellation"]},
    {"id": 11, "subject": "The product description doesn't match what I received", "industry": "ecommerce", "channel": "email", "expected_intents": ["complaint"]},
    {"id": 12, "subject": "Do you ship internationally?", "industry": "ecommerce", "channel": "chat", "expected_intents": ["shipping"]},
    {"id": 13, "subject": "I never received my refund from last month", "industry": "ecommerce", "channel": "email", "expected_intents": ["refund", "billing"]},
    {"id": 14, "subject": "Gift card balance showing zero after purchase", "industry": "ecommerce", "channel": "chat", "expected_intents": ["billing"]},
    {"id": 15, "subject": "Package delivered to wrong address", "industry": "ecommerce", "channel": "sms", "expected_intents": ["shipping", "complaint"]},
    # Healthcare (15 tickets)
    {"id": 16, "subject": "I need to reschedule my appointment", "industry": "healthcare", "channel": "call", "expected_intents": ["account"]},
    {"id": 17, "subject": "My insurance claim was denied incorrectly", "industry": "healthcare", "channel": "email", "expected_intents": ["billing", "complaint"]},
    {"id": 18, "subject": "The patient portal is not loading my lab results", "industry": "healthcare", "channel": "chat", "expected_intents": ["technical"]},
    {"id": 19, "subject": "How do I access my medical records online?", "industry": "healthcare", "channel": "chat", "expected_intents": ["account_access"]},
    {"id": 20, "subject": "I was overcharged for my consultation visit", "industry": "healthcare", "channel": "email", "expected_intents": ["billing", "overcharge"]},
    {"id": 21, "subject": "Need prescription refill authorization", "industry": "healthcare", "channel": "call", "expected_intents": ["account"]},
    {"id": 22, "subject": "Doctor's note never arrived via email", "industry": "healthcare", "channel": "chat", "expected_intents": ["shipping", "technical"]},
    {"id": 23, "subject": "Wrong medication dosage listed in my profile", "industry": "healthcare", "channel": "email", "expected_intents": ["complaint", "technical"]},
    {"id": 24, "subject": "Can I get a copy of my billing statement?", "industry": "healthcare", "channel": "chat", "expected_intents": ["billing"]},
    {"id": 25, "subject": "Appointment confirmation not received", "industry": "healthcare", "channel": "sms", "expected_intents": ["shipping"]},
    {"id": 26, "subject": "Telehealth video call keeps disconnecting", "industry": "healthcare", "channel": "chat", "expected_intents": ["technical", "broken"]},
    {"id": 27, "subject": "I need to update my emergency contact information", "industry": "healthcare", "channel": "chat", "expected_intents": ["account"]},
    {"id": 28, "subject": "Surprise bill for a service I didn't receive", "industry": "healthcare", "channel": "email", "expected_intents": ["billing", "complaint"]},
    {"id": 29, "subject": "How do I switch to a different primary care physician?", "industry": "healthcare", "channel": "chat", "expected_intents": ["account", "switch"]},
    {"id": 30, "subject": "Lab results showing wrong patient name", "industry": "healthcare", "channel": "call", "expected_intents": ["complaint", "error"]},
    # Banking (15 tickets)
    {"id": 31, "subject": "Unauthorized transaction on my credit card", "industry": "banking", "channel": "call", "expected_intents": ["billing", "complaint"]},
    {"id": 32, "subject": "My debit card was declined at the store", "industry": "banking", "channel": "sms", "expected_intents": ["technical", "billing"]},
    {"id": 33, "subject": "How do I dispute a charge on my statement?", "industry": "banking", "channel": "chat", "expected_intents": ["billing", "refund"]},
    {"id": 34, "subject": "Wire transfer not received after 5 business days", "industry": "banking", "channel": "email", "expected_intents": ["shipping", "billing"]},
    {"id": 35, "subject": "Mobile banking app crashes on login", "industry": "banking", "channel": "chat", "expected_intents": ["technical", "crash"]},
    {"id": 36, "subject": "Interest rate on my savings changed without notice", "industry": "banking", "channel": "email", "expected_intents": ["complaint", "billing"]},
    {"id": 37, "subject": "How do I set up direct deposit?", "industry": "banking", "channel": "chat", "expected_intents": ["account"]},
    {"id": 38, "subject": "Account frozen due to suspicious activity check", "industry": "banking", "channel": "call", "expected_intents": ["account_access", "technical"]},
    {"id": 39, "subject": "Mortgage payment not reflecting in my account", "industry": "banking", "channel": "email", "expected_intents": ["billing"]},
    {"id": 40, "subject": "Need to increase my credit limit", "industry": "banking", "channel": "chat", "expected_intents": ["subscription"]},
    {"id": 41, "subject": "ATM didn't dispense cash but debited my account", "industry": "banking", "channel": "call", "expected_intents": ["billing", "complaint"]},
    {"id": 42, "subject": "How do I close my savings account?", "industry": "banking", "channel": "chat", "expected_intents": ["cancellation"]},
    {"id": 43, "subject": "Foreign transaction fee not disclosed properly", "industry": "banking", "channel": "email", "expected_intents": ["billing", "complaint"]},
    {"id": 44, "subject": "Online banking session times out too quickly", "industry": "banking", "channel": "chat", "expected_intents": ["technical"]},
    {"id": 45, "subject": "Password reset email not arriving", "industry": "banking", "channel": "chat", "expected_intents": ["password_reset", "technical"]},
    # SaaS (20 tickets)
    {"id": 46, "subject": "How do I reset my password?", "industry": "saas", "channel": "chat", "expected_intents": ["password_reset"]},
    {"id": 47, "subject": "My API rate limit is too low for my usage", "industry": "saas", "channel": "email", "expected_intents": ["billing"]},
    {"id": 48, "subject": "Webhook integration not triggering properly", "industry": "saas", "channel": "chat", "expected_intents": ["technical", "bug"]},
    {"id": 49, "subject": "Dashboard loading extremely slow today", "industry": "saas", "channel": "chat", "expected_intents": ["technical"]},
    {"id": 50, "subject": "Can't export my data to CSV format", "industry": "saas", "channel": "email", "expected_intents": ["technical", "bug"]},
    {"id": 51, "subject": "Want to upgrade from Starter to Professional plan", "industry": "saas", "channel": "chat", "expected_intents": ["subscription"]},
    {"id": 52, "subject": "SSO login not working with our corporate IdP", "industry": "saas", "channel": "email", "expected_intents": ["login_issue", "technical"]},
    {"id": 53, "subject": "Custom report builder throwing 500 errors", "industry": "saas", "channel": "chat", "expected_intents": ["technical", "error"]},
    {"id": 54, "subject": "Need to add team members but seats are full", "industry": "saas", "channel": "chat", "expected_intents": ["subscription"]},
    {"id": 55, "subject": "Billing cycle changed without notification", "industry": "saas", "channel": "email", "expected_intents": ["billing", "complaint"]},
    {"id": 56, "subject": "Two-factor authentication codes not sending", "industry": "saas", "channel": "chat", "expected_intents": ["technical", "password_reset"]},
    {"id": 57, "subject": "Data migration tool keeps failing at 80%", "industry": "saas", "channel": "email", "expected_intents": ["technical", "error"]},
    {"id": 58, "subject": "Want to cancel my annual subscription early", "industry": "saas", "channel": "chat", "expected_intents": ["cancellation"]},
    {"id": 59, "subject": "Third-party integration not syncing data", "industry": "saas", "channel": "email", "expected_intents": ["technical"]},
    {"id": 60, "subject": "Analytics dashboard showing wrong metrics", "industry": "saas", "channel": "chat", "expected_intents": ["complaint", "technical"]},
    {"id": 61, "subject": "How do I set up user roles and permissions?", "industry": "saas", "channel": "chat", "expected_intents": ["account"]},
    {"id": 62, "subject": "Automated workflows not triggering on schedule", "industry": "saas", "channel": "email", "expected_intents": ["technical", "bug"]},
    {"id": 63, "subject": "Need a refund for the unused portion of my plan", "industry": "saas", "channel": "chat", "expected_intents": ["refund", "billing"]},
    {"id": 64, "subject": "Mobile app keeps logging me out", "industry": "saas", "channel": "sms", "expected_intents": ["technical", "login_issue"]},
    {"id": 65, "subject": "Feature I was promised during sales call is missing", "industry": "saas", "channel": "email", "expected_intents": ["complaint"]},
    # Telecom (15 tickets)
    {"id": 66, "subject": "Internet speed much slower than advertised", "industry": "telecom", "channel": "call", "expected_intents": ["complaint", "technical"]},
    {"id": 67, "subject": "Data overage charges I wasn't warned about", "industry": "telecom", "channel": "email", "expected_intents": ["billing", "complaint"]},
    {"id": 68, "subject": "Phone not receiving text messages", "industry": "telecom", "channel": "chat", "expected_intents": ["technical"]},
    {"id": 69, "subject": "How do I activate my new SIM card?", "industry": "telecom", "channel": "chat", "expected_intents": ["account"]},
    {"id": 70, "subject": "Service outage in my area for 3 days", "industry": "telecom", "channel": "call", "expected_intents": ["complaint", "technical"]},
    {"id": 71, "subject": "International roaming charges seem incorrect", "industry": "telecom", "channel": "email", "expected_intents": ["billing", "overcharge"]},
    {"id": 72, "subject": "Want to switch to a different data plan", "industry": "telecom", "channel": "chat", "expected_intents": ["switch", "subscription"]},
    {"id": 73, "subject": "Voicemail not working after update", "industry": "telecom", "channel": "sms", "expected_intents": ["technical", "bug"]},
    {"id": 74, "subject": "Need to port my number to another carrier", "industry": "telecom", "channel": "chat", "expected_intents": ["cancellation", "switch"]},
    {"id": 75, "subject": "Call quality is terrible with constant drops", "industry": "telecom", "channel": "call", "expected_intents": ["complaint", "technical"]},
    {"id": 76, "subject": "Equipment rental fee too high, want to buy my own", "industry": "telecom", "channel": "email", "expected_intents": ["billing"]},
    {"id": 77, "subject": "WiFi router keeps disconnecting devices", "industry": "telecom", "channel": "chat", "expected_intents": ["technical", "broken"]},
    {"id": 78, "subject": "Promotional pricing expired without notice", "industry": "telecom", "channel": "email", "expected_intents": ["billing", "complaint"]},
    {"id": 79, "subject": "Can't access my account after phone number change", "industry": "telecom", "channel": "chat", "expected_intents": ["account_access", "login_issue"]},
    {"id": 80, "subject": "Contract auto-renewed without my consent", "industry": "telecom", "channel": "email", "expected_intents": ["billing", "complaint"]},
    # Travel (10 tickets)
    {"id": 81, "subject": "Flight cancelled, need immediate rebooking", "industry": "travel", "channel": "call", "expected_intents": ["complaint", "shipping"]},
    {"id": 82, "subject": "Hotel booking confirmation not received", "industry": "travel", "channel": "email", "expected_intents": ["shipping"]},
    {"id": 83, "subject": "Wrong room type assigned at check-in", "industry": "travel", "channel": "call", "expected_intents": ["complaint"]},
    {"id": 84, "subject": "Rental car had damage not noted in contract", "industry": "travel", "channel": "email", "expected_intents": ["complaint", "billing"]},
    {"id": 85, "subject": "Refund for cancelled trip taking too long", "industry": "travel", "channel": "chat", "expected_intents": ["refund", "billing"]},
    {"id": 86, "subject": "Loyalty points not credited after recent stay", "industry": "travel", "channel": "chat", "expected_intents": ["billing"]},
    {"id": 87, "subject": "Travel insurance claim being denied unfairly", "industry": "travel", "channel": "email", "expected_intents": ["complaint", "billing"]},
    {"id": 88, "subject": "Need to change passenger name on booking", "industry": "travel", "channel": "call", "expected_intents": ["account"]},
    {"id": 89, "subject": "Baggage lost during connecting flight", "industry": "travel", "channel": "call", "expected_intents": ["complaint", "shipping"]},
    {"id": 90, "subject": "Price shown different from what I was charged", "industry": "travel", "channel": "email", "expected_intents": ["billing", "overcharge"]},
    # Insurance (10 tickets)
    {"id": 91, "subject": "Claim denied for pre-existing condition not listed", "industry": "insurance", "channel": "email", "expected_intents": ["complaint", "billing"]},
    {"id": 92, "subject": "Premium increased 30% at renewal without explanation", "industry": "insurance", "channel": "email", "expected_intents": ["billing", "complaint"]},
    {"id": 93, "subject": "Can't access my policy documents online", "industry": "insurance", "channel": "chat", "expected_intents": ["account_access", "technical"]},
    {"id": 94, "subject": "Need to add a new driver to my auto policy", "industry": "insurance", "channel": "chat", "expected_intents": ["account", "subscription"]},
    {"id": 95, "subject": "Adjuster not responding to my claim for 2 weeks", "industry": "insurance", "channel": "call", "expected_intents": ["complaint"]},
    {"id": 96, "subject": "Want to switch from comprehensive to liability only", "industry": "insurance", "channel": "chat", "expected_intents": ["switch", "subscription"]},
    {"id": 97, "subject": "Reimbursement check never arrived", "industry": "insurance", "channel": "email", "expected_intents": ["refund", "shipping"]},
    {"id": 98, "subject": "Home insurance doesn't cover flood damage?", "industry": "insurance", "channel": "chat", "expected_intents": ["complaint", "account"]},
    {"id": 99, "subject": "Need to cancel my policy effective immediately", "industry": "insurance", "channel": "call", "expected_intents": ["cancellation"]},
    {"id": 100, "subject": "Accident report shows wrong date and location", "industry": "insurance", "channel": "email", "expected_intents": ["complaint", "error"]},
]


async def test_variant(variant_tier, tickets):
    """Test a specific variant with all 100 tickets."""
    if variant_tier == "mini_parwa":
        from app.core.mini_parwa.graph import MiniParwaPipeline
        pipeline = MiniParwaPipeline()
    elif variant_tier == "parwa":
        from app.core.parwa.graph import ParwaPipeline
        pipeline = ParwaPipeline()
    elif variant_tier == "parwa_high":
        from app.core.parwa_high.graph import ParwaHighPipeline
        pipeline = ParwaHighPipeline()
    else:
        raise ValueError(f"Unknown variant: {variant_tier}")

    results = []
    for ticket in tickets:
        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                pipeline.process_ticket(
                    query=ticket["subject"],
                    company_id=COMPANY_ID,
                    industry=ticket["industry"],
                    channel=ticket["channel"],
                    customer_tier="free",
                ),
                timeout=30.0,
            )
            latency = round((time.monotonic() - start) * 1000, 2)
            
            # Extract key metrics
            steps = result.get("steps_completed", [])
            quality = result.get("quality_score", 0)
            if isinstance(quality, (int, float)) and quality > 1.0:
                quality = quality / 100.0
            
            technique_detail = result.get("technique", {})
            if isinstance(technique_detail, dict):
                technique_name = technique_detail.get("primary_technique", "direct")
                activated = technique_detail.get("activated_techniques", [])
            else:
                technique_name = str(technique_detail)
                activated = []

            results.append({
                "ticket_id": ticket["id"],
                "subject": ticket["subject"],
                "variant_tier": variant_tier,
                "industry": ticket["industry"],
                "pipeline_status": result.get("pipeline_status", "unknown"),
                "quality_score": round(quality, 3) if quality else 0,
                "latency_ms": latency,
                "steps_completed": steps,
                "technique_used": technique_name,
                "activated_techniques": activated,
                "emergency_flag": result.get("emergency_flag", False),
                "empathy_score": result.get("empathy_score", 0),
                "classification_intent": result.get("classification", {}).get("intent", "general") if isinstance(result.get("classification"), dict) else "general",
                "channel": ticket["channel"],
                "expected_intents": ticket.get("expected_intents", []),
                "response_preview": (result.get("final_response", "") or result.get("formatted_response", ""))[:150],
                "error": result.get("error"),
            })
        except asyncio.TimeoutError:
            results.append({
                "ticket_id": ticket["id"], "subject": ticket["subject"],
                "variant_tier": variant_tier, "industry": ticket["industry"],
                "pipeline_status": "timeout", "quality_score": 0, "latency_ms": 30000,
                "steps_completed": [], "technique_used": "timeout", "activated_techniques": [],
                "emergency_flag": False, "empathy_score": 0, "classification_intent": "unknown",
                "channel": ticket["channel"], "expected_intents": ticket.get("expected_intents", []),
                "response_preview": "", "error": "timeout",
            })
        except Exception as e:
            results.append({
                "ticket_id": ticket["id"], "subject": ticket["subject"],
                "variant_tier": variant_tier, "industry": ticket["industry"],
                "pipeline_status": "error", "quality_score": 0, "latency_ms": 0,
                "steps_completed": [], "technique_used": "error", "activated_techniques": [],
                "emergency_flag": False, "empathy_score": 0, "classification_intent": "unknown",
                "channel": ticket["channel"], "expected_intents": ticket.get("expected_intents", []),
                "response_preview": "", "error": str(e)[:100],
            })

    return results


def analyze_results(variant_tier, results):
    """Analyze and print results for a variant."""
    total = len(results)
    statuses = {}
    for r in results:
        s = r["pipeline_status"]
        statuses[s] = statuses.get(s, 0) + 1
    
    successes = [r for r in results if r["pipeline_status"] in ("success", "completed")]
    avg_quality = sum(r["quality_score"] for r in successes) / len(successes) if successes else 0
    avg_latency = sum(r["latency_ms"] for r in successes) / len(successes) if successes else 0

    # Collect all unique steps
    all_steps = set()
    for r in results:
        all_steps.update(r["steps_completed"])

    # Technique distribution
    techniques = {}
    for r in results:
        t = r["technique_used"]
        techniques[t] = techniques.get(t, 0) + 1

    # Deep enrichment hits
    deep_nodes = {"complaint_handler", "retention_negotiator", "billing_resolver", "tech_diagnostic", "shipping_tracker"}
    deep_hits = sum(1 for r in results if any(s in deep_nodes for s in r["steps_completed"]))

    # Smart enrichment hits
    smart_hits = sum(1 for r in results if "smart_enrichment" in r["steps_completed"])

    # All activated techniques
    all_activated = set()
    for r in results:
        all_activated.update(r.get("activated_techniques", []))

    print(f"\n{'='*70}")
    print(f"  {variant_tier.upper()} RESULTS")
    print(f"{'='*70}")
    print(f"  Total tickets:  {total}")
    print(f"  Statuses:       {statuses}")
    print(f"  Avg Quality:    {avg_quality:.3f}")
    print(f"  Avg Latency:    {avg_latency:.1f}ms")
    print(f"  Smart Enrich:   {smart_hits}/{total}")
    print(f"  Deep Enrich:    {deep_hits}/{total}")
    print(f"  Techniques:     {techniques}")
    print(f"  Activated:      {sorted(all_activated)}")
    print(f"  All Steps:      {sorted(all_steps)}")
    
    return {
        "variant": variant_tier,
        "total": total,
        "statuses": statuses,
        "avg_quality": round(avg_quality, 3),
        "avg_latency": round(avg_latency, 1),
        "smart_enrichment_hits": smart_hits,
        "deep_enrichment_hits": deep_hits,
        "techniques": techniques,
        "all_activated": sorted(all_activated),
        "all_steps": sorted(all_steps),
    }


async def main():
    print("="*70)
    print("  PARWA 100-TICKET VARIANT PIPELINE TEST")
    print("="*70)
    
    all_results = {}
    summaries = []
    
    for variant in ["mini_parwa", "parwa", "parwa_high"]:
        print(f"\n>>> Testing {variant}...")
        results = await test_variant(variant, TICKETS)
        summary = analyze_results(variant, results)
        summaries.append(summary)
        all_results[variant] = {"summary": summary, "tickets": results}

    # Save results
    output = {
        "test_run": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            "company_id": COMPANY_ID,
            "total_tickets": 100,
            "variant_tiers_tested": ["mini_parwa", "parwa", "parwa_high"],
        },
        "results": all_results,
    }
    
    with open("test_results_variant_100.json", "w") as f:
        json.dump(output, f, indent=2, default=str)

    # Print comparative summary
    print(f"\n{'='*70}")
    print(f"  COMPARATIVE SUMMARY")
    print(f"{'='*70}")
    print(f"  {'Variant':<15} {'Quality':<10} {'Latency':<12} {'SmartE':<8} {'DeepE':<8} {'Statuses'}")
    for s in summaries:
        print(f"  {s['variant']:<15} {s['avg_quality']:<10.3f} {s['avg_latency']:<12.1f} {s['smart_enrichment_hits']:<8} {s['deep_enrichment_hits']:<8} {s['statuses']}")
    
    print(f"\n  Results saved to test_results_variant_100.json")


if __name__ == "__main__":
    asyncio.run(main())
