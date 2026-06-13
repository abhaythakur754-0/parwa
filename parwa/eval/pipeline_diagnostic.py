#!/usr/bin/env python3
"""Pipeline Diagnostic — Trace what actually happens inside the pipeline.

Runs ONE ticket through the pipeline with FULL logging enabled,
tracing: which nodes execute, what frameworks activate, what routing
decisions are made, and where things go wrong.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Enable FULL logging to see everything
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# Quiet down noisy loggers
for noisy in ["httpx", "httpcore", "openai", "urllib3", "http11"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)


async def diagnose() -> None:
    os.environ["PARWA_MOCK_MODE"] = "false"
    
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm
    
    # Use the MINI ticket (Chen Wei — billing + cancellation + legal threat + PII)
    message = (
        "My card ending in 4532 keeps getting declined even though I updated it last week. "
        "I've been charged $89.99 for order ORD-2004 that I never placed, and my account shows suspended "
        "but nobody told me why. My SSN is 457-82-9101 — verify my identity and fix this immediately. "
        "Also I want to cancel my subscription, this is ridiculous. I've been a premium customer for 3 years "
        "and this is how I get treated? If this isn't resolved today I'm filing a complaint with the FTC. "
        "My email is chen.wei@protonmail.com and phone is +1-408-555-0147."
    )
    customer_id = "CUST-1004"
    
    for variant in ["mini", "parwa", "high"]:
        print(f"\n{'#'*80}")
        print(f"# DIAGNOSTIC: {variant.upper()} VARIANT")
        print(f"{'#'*80}")
        
        reset_parwa_graph()
        reset_crm()
        
        result = await aprocess_ticket(
            raw_message=message,
            customer_id=customer_id,
            channel="email",
            variant=variant,
        )
        
        # Print key pipeline state
        print(f"\n{'='*60}")
        print(f"  PIPELINE RESULT for {variant.upper()}")
        print(f"{'='*60}")
        print(f"  Intent:              {result.get('intent')}")
        print(f"  Intent Confidence:   {result.get('intent_confidence')}")
        print(f"  Complexity:          {result.get('complexity')}")
        print(f"  Sentiment:           {result.get('sentiment')}")
        print(f"  Should Escalate:     {result.get('should_escalate')}")
        print(f"  Escalation Reason:   {result.get('escalation_trigger_reason')}")
        print(f"  Multi-Intent:        {result.get('multi_intent_detected')}")
        print(f"  Detected Intents:    {result.get('detected_intents')}")
        print(f"  Low Confidence:      {result.get('low_confidence_flag')}")
        print(f"  Clarifying Question:  {result.get('clarifying_question')}")
        print(f"  PII Detected:        {result.get('pii_detected')}")
        print(f"  Quality Score:       {result.get('quality_score')}")
        print(f"  Active Frameworks:   {result.get('active_frameworks')}")
        print(f"  Evidence Chain:      {len(result.get('evidence_chain', []))} entries")
        print(f"  Pipeline Errors:     {result.get('pipeline_errors')}")
        print(f"  Reasoning Chain:     {result.get('reasoning_chain', [])[:2] if result.get('reasoning_chain') else 'None'}")
        print(f"  Action Plans:")
        for i, ap in enumerate(result.get('action_plans', [])[:5]):
            if hasattr(ap, 'action_type'):
                print(f"    {i+1}. {ap.action_type} | {ap.description[:60] if ap.description else ''} | mode={ap.mode}")
            elif isinstance(ap, dict):
                print(f"    {i+1}. {ap.get('action_type')} | {ap.get('description', '')[:60]} | mode={ap.get('mode', '')}")
        
        print(f"\n  Final Response (first 300 chars):")
        print(f"  {result.get('final_response', '')[:300]}")
        
        await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(diagnose())
