"""
PARWA Pipeline V2 — Test Script (Dry Run + Live)

Tests 2 complicated tickets through the full 8-node pipeline.
Set DRY_RUN=true to test graph structure without real LLM calls.
Set DRY_RUN=false (default) to use NVIDIA Llama 3.1 8B.

Ticket 1: Complex refund request ($1,200, Pro plan, multiple issues)
Ticket 2: Billing dispute with plan change request
"""

import asyncio
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone

# Add project to path
sys.path.insert(0, "/home/z/my-project/parwa/backend")

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant

DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"

# If dry run, patch llm_call to return mock responses
if DRY_RUN:
    print("*** DRY RUN MODE — using mock LLM responses ***")
    print("*** Set DRY_RUN=false to use real NVIDIA API ***\n")

    # Patch at the module level before any imports happen
    # We need to mock litellm.acompletion directly since all nodes go through it
    from unittest import mock

    _call_count = [0]
    _original_completion = None

    async def _mock_completion(*args, **kwargs):
        _call_count[0] += 1
        # Build a mock response
        class MockChoice:
            class MockMessage:
                content = ""
            message = MockMessage()
        class MockResponse:
            choices = [MockChoice()]

        prompt = kwargs.get("messages", [{}])[0].get("content", "")
        prompt_lower = prompt.lower()

        if "confidence" in prompt_lower and "0.0" in prompt_lower:
            MockChoice.MockMessage.content = "0.85"
        elif "critique" in prompt_lower and ("accuracy" in prompt_lower or "score" in prompt_lower):
            MockChoice.MockMessage.content = "ACCURACY: 8/10\nCOMPLETENESS: 7/10\nCLARITY: 9/10\nRELEVANCE: 8/10\nACTIONABILITY: 8/10\nOVERALL: 8/10\nCRITIQUE: Could be more specific about refund amount"
        elif "improve" in prompt_lower or "better version" in prompt_lower:
            MockChoice.MockMessage.content = "The refund process has been verified. Based on our records, you are eligible for a full refund of $1,200. The $75 credit from the previous billing error will be applied. Your data will be available for export for 30 days after cancellation."
        elif "why" in prompt_lower and "fail" in prompt_lower:
            MockChoice.MockMessage.content = "FAILURE ANALYSIS: 1) Previous attempts did not address the $75 credit. 2) Data retention policy was not mentioned. 3) The answer was too generic."
        elif "independent solutions" in prompt_lower or "solve" in prompt_lower:
            MockChoice.MockMessage.content = "Based on the refund policy, a Pro plan customer within the annual billing cycle is eligible for a prorated refund. The outstanding credit of $75 should be applied first."
        elif "improved answer" in prompt_lower or "enhanced" in prompt_lower:
            MockChoice.MockMessage.content = "After reviewing your account: 1) You are eligible for a full refund of $1,200. 2) The $75 credit will be applied. 3) Data export available for 30 days."
        elif "validate" in prompt_lower and "backward" in prompt_lower:
            MockChoice.MockMessage.content = "VALID: YES\nCONFIDENCE: 0.88\nIMPROVEMENTS: Add specific timeline for refund processing"
        elif "refund" in prompt_lower and "hypothetical" in prompt_lower:
            MockChoice.MockMessage.content = "Customer is eligible for prorated annual refund. Credit of $75 applies. Data export available for 30 days."
        elif "rewrite" in prompt_lower and "question" in prompt_lower:
            MockChoice.MockMessage.content = "1. What is the refund process?\n2. How do I get my credit applied?\n3. What happens to my data?"
        elif "broader" in prompt_lower and "principle" in prompt_lower:
            MockChoice.MockMessage.content = "Broader principle: Annual subscription refunds follow prorated calculation. Credits applied before refund."
        elif "knowledge area" in prompt_lower or "relevant" in prompt_lower:
            MockChoice.MockMessage.content = "RELEVANT_KNOWLEDGE: Refund policy, credit application, data retention\nREQUIRED_INFO: Refund amount, credit details\nPOSSIBLE_GAPS: Exact proration method"
        elif "rate" in prompt_lower and "confidence" in prompt_lower:
            MockChoice.MockMessage.content = "0.82"
        elif "think about" in prompt_lower and "action" in prompt_lower:
            MockChoice.MockMessage.content = "THOUGHT: Verify refund eligibility, check credit balance, process refund, notify of data retention."
        elif "correct and reversible" in prompt_lower or "verify" in prompt_lower:
            MockChoice.MockMessage.content = "VERIFIED: YES\nRISK: low\nDETAILS: Refund is within policy limits."
        elif "order" in prompt_lower and "easiest" in prompt_lower:
            MockChoice.MockMessage.content = "1. Calculate refund amount\n2. Verify eligibility\n3. Process refund"
        elif "step by step" in prompt_lower:
            MockChoice.MockMessage.content = "Step 1: Verify Pro plan and tenure. Step 2: Confirm $1,200 charge. Step 3: Apply $75 credit. Step 4: Process refund."
        elif "alternative" in prompt_lower or "better path" in prompt_lower:
            MockChoice.MockMessage.content = "CONFIRMED: Current approach covers all aspects."
        elif "progress" in prompt_lower:
            MockChoice.MockMessage.content = "3/3 sub-problems solved"
        elif "rate your confidence" in prompt_lower:
            MockChoice.MockMessage.content = "0.86"
        else:
            MockChoice.MockMessage.content = "This is a mock response for testing purposes."

        return MockResponse()

    import litellm as _litellm

    _original_completion = _litellm.acompletion
    _litellm.acompletion = _mock_completion
    print(f"Mock litellm.acompletion patched\n")


async def run_ticket(ticket: dict, graph) -> dict:
    """Run a single ticket through the pipeline."""
    ticket_id = ticket["ticket_id"]
    print(f"\n{'='*70}")
    print(f"TICKET: {ticket_id}")
    print(f"Query: {ticket['query']}")
    print(f"{'='*70}")

    start = time.time()

    # Set test variant
    set_test_variant(ticket["tenant_id"], ticket["variant_tier"], ticket["quota"])

    # Build initial state
    initial_state = {
        "ticket_id": ticket_id,
        "tenant_id": ticket["tenant_id"],
        "query": ticket["query"],
        "channel_type": ticket.get("channel_type", "email"),
        "customer_context": ticket.get("customer_context", {}),
        "metadata": {
            "sender": ticket.get("sender", "customer@example.com"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "loop_count": 0,
        "total_token_usage": 0,
        "technique_log": [],
        "errors": [],
    }

    try:
        compiled = graph.compile()
        result = await compiled.ainvoke(initial_state)

        elapsed = time.time() - start

        # Print results
        print(f"\n--- RESULTS [{elapsed:.1f}s] ---")
        print(f"Status:        {result.get('status', 'unknown')}")
        print(f"Ticket Type:   {result.get('ticket_type', 'N/A')}")
        print(f"Complexity:    {result.get('complexity', 'N/A')}")
        print(f"Variant Tier:  {result.get('variant_tier', 'N/A')}")
        print(f"Route:         {result.get('route_decision', result.get('current_path', 'N/A'))}")
        print(f"Total LLM:     {result.get('total_token_usage', 0)} calls")
        print(f"Quality Score: {result.get('quality_score', 'N/A')}")
        print(f"Loop Count:    {result.get('loop_count', 0)}")

        if result.get("escalation_context"):
            esc = result["escalation_context"]
            print(f"Escalation:    YES (key: {esc.get('notification_key', 'N/A')})")
            print(f"Super Quality: {result.get('super_node_quality', 'N/A')}")

        if result.get("simple_confidence") is not None:
            print(f"Simple Conf:   {result['simple_confidence']:.2f}")
            print(f"Auto Upgraded: {result.get('auto_upgraded', False)}")

        print(f"\n--- TECHNIQUES RUN ---")
        for log in result.get("technique_log", []):
            node = log.get("node", "?")
            tech = log.get("technique", "?")
            summary = log.get("result_summary", "")
            print(f"  Node {node}: {tech:<25} -> {summary}")

        print(f"\n--- FINAL RESPONSE ---")
        response = result.get("final_response", "") or result.get("formatted_response", "") or result.get("simple_answer", "") or result.get("super_node_answer", "")
        print(response[:2000] if response else "(no response generated)")

        return result

    except Exception as e:
        elapsed = time.time() - start
        print(f"\n--- ERROR [{elapsed:.1f}s] ---")
        print(f"Error: {e}")
        traceback.print_exc()
        return {"error": str(e)}


async def main():
    print("=" * 70)
    print("PARWA Pipeline V2 - Test Runner")
    print(f"Mode: {'DRY RUN (mock LLM)' if DRY_RUN else 'LIVE (NVIDIA Llama 3.1 8B)'}")
    print("=" * 70)

    # Build pipeline
    graph = build_parwa_pipeline()
    print("\nPipeline built successfully.")

    # Ticket 1: Complex refund - should go complex path
    ticket_1 = {
        "ticket_id": "tkt_test_001",
        "tenant_id": "tenant_test_a",
        "query": (
            "I have been a Pro plan customer for 8 months and I need to cancel my annual subscription "
            "and get a refund. I was charged $1,200 for the annual plan but I also have an outstanding "
            "credit of $75 from a previous billing error that was never applied. I want the full refund "
            "processed to my original payment method, and I want to know what happens to my stored data."
        ),
        "channel_type": "email",
        "variant_tier": "high",
        "quota": 2000,
        "customer_context": {
            "account_tier": "pro",
            "customer_tenure_days": 240,
            "recent_ticket_count": 3,
            "lifetime_value": 2400,
        },
        "sender": "sarah.chen@company.com",
    }

    # Ticket 2: Billing dispute with plan change - complex
    ticket_2 = {
        "ticket_id": "tkt_test_002",
        "tenant_id": "tenant_test_a",
        "query": (
            "I was charged $149 twice this month, once on the 1st and again on the 15th. "
            "Looking at my invoices, the first charge shows the correct Pro plan rate but "
            "the second one shows the High plan rate of $499. I never upgraded to High plan. "
            "Additionally, my team member who uses the same account key is seeing a different "
            "pricing page than me, she sees $99/mo instead of $149. I want both the duplicate "
            "charge fixed and an explanation for the pricing discrepancy."
        ),
        "channel_type": "chat",
        "variant_tier": "high",
        "quota": 1999,
        "customer_context": {
            "account_tier": "pro",
            "customer_tenure_days": 180,
            "recent_ticket_count": 1,
            "lifetime_value": 1500,
        },
        "sender": "mike.r@startup.io",
    }

    # Run both tickets
    results = []
    for ticket in [ticket_1, ticket_2]:
        result = await run_ticket(ticket, graph)
        results.append({"ticket_id": ticket["ticket_id"], "result": result})

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    for r in results:
        tid = r["ticket_id"]
        res = r["result"]
        status = res.get("status", "ERROR")
        llm = res.get("total_token_usage", 0)
        quality = res.get("quality_score", res.get("simple_confidence", "N/A"))
        print(f"  {tid}: status={status}, llm_calls={llm}, quality={quality}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())