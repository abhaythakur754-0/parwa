#!/usr/bin/env python3
"""Nightmare Ticket Test — ONE ticket, THREE variants, PURE OBSERVATION.

This script runs the M4-016 "nightmare" ticket through each variant
(mini, parwa, high) one at a time. We do NOT influence the LLM responses
in any way — we just send the ticket through the pipeline and observe
what each variant produces.

The goal: See if the variants can handle a truly tough, multi-trap ticket
on their own, without any assistance or bias from us.

What this ticket tests:
  TRAP 1: Starts with billing language but PRIMARY intent = complaint
  TRAP 2: Polite words mask deeply angry sentiment
  TRAP 3: 3+ unresolved tickets + consumer rights hint = MUST escalate
  TRAP 4: Should ESCALATE, not refund or just reply
  TRAP 5: Multi-intent: billing + refund + complaint + technical + retention

Expected results:
  - Intent: complaint
  - Sentiment: angry
  - Escalation: True
  - Action: escalate
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("parwa.eval.nightmare_test")

# Ensure mock mode is OFF
os.environ["PARWA_MOCK_MODE"] = "false"


# The nightmare ticket
NIGHTMARE_TICKET = {
    "id": "M4-016",
    "message": (
        "Hi, I noticed something odd on my account and I'm hoping someone can clarify. "
        "I see a pending charge of $249.98 on my card ending in 7788 from May 30th — I "
        "believe that was for the Design Software License and Plugin Pack I ordered, which "
        "is fine. But here's the thing: the plugin has never worked. I submitted ticket "
        "TKT-4040 on June 5th about it crashing, and then another ticket TKT-4041 on "
        "June 8th because my license won't even activate properly. That was over a week "
        "ago. Nobody has responded to either ticket. Not even an acknowledgment.\n\n"
        "Now I'm in this strange situation where I'm paying $29.99/month for Creative Pro "
        "and I can't use any of it. The software I bought for $249.98 doesn't work. My "
        "open tickets are being ignored. And my subscription renews on July 20th — what "
        "exactly am I subscribing to if nothing functions?\n\n"
        "I've been a loyal customer for 3 years and this is the first time I've felt "
        "completely dismissed. I read somewhere that consumers have rights when products "
        "fail to perform as advertised, and I'm starting to understand why people pursue "
        "those options. I don't want to go down that road, but I also can't keep paying "
        "for something that doesn't work while being ignored.\n\n"
        "I need someone to: 1) explain why my tickets have been ignored for a week, "
        "2) either fix the software or refund the $249.98, and 3) tell me why I should "
        "trust that my Creative Pro subscription is worth keeping. A real response this "
        "time, please — not an automated acknowledgment."
    ),
    "customer_id": "CUST-1007",
    "expected_intent": "complaint",
    "expected_sentiment": "angry",
    "expected_escalation": True,
    "expected_action": "escalate",
}


async def run_nightmare_for_variant(variant: str) -> dict:
    """Run the nightmare ticket through ONE variant and return raw results.

    We just call the pipeline and observe — NO modifications, NO hints,
    NO interference with the LLM responses.
    """
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm

    # Clean slate for each variant
    reset_parwa_graph()
    reset_crm()

    logger.info("=" * 70)
    logger.info("NIGHTMARE TEST: Running M4-016 through '%s' variant", variant)
    logger.info("=" * 70)

    start_time = time.time()

    try:
        result = await aprocess_ticket(
            raw_message=NIGHTMARE_TICKET["message"],
            customer_id=NIGHTMARE_TICKET["customer_id"],
            channel="email",
            variant=variant,
        )
        elapsed_ms = (time.time() - start_time) * 1000

        # Extract ALL the fields we care about
        predicted_intent = str(result.get("intent", "unknown")).lower().replace("intenttype.", "")
        if "." in predicted_intent:
            predicted_intent = predicted_intent.split(".")[-1]

        predicted_sentiment = str(result.get("sentiment", "unknown")).lower().replace("sentimenttype.", "")
        if "." in predicted_sentiment:
            predicted_sentiment = predicted_sentiment.split(".")[-1]

        predicted_escalate = result.get("should_escalate", False)
        if isinstance(predicted_escalate, str):
            predicted_escalate = predicted_escalate.lower() in ("true", "yes")

        action_plans = result.get("action_plans", [])
        predicted_action = ""
        if action_plans and isinstance(action_plans, list):
            first_action = action_plans[0]
            if isinstance(first_action, dict):
                predicted_action = str(first_action.get("action_type", "")).lower()

        # Also check final_response for action hints
        final_response = result.get("final_response", "")
        if not predicted_action and final_response:
            response_lower = final_response.lower()
            if "refund" in response_lower:
                predicted_action = "process_refund"
            elif "cancel" in response_lower:
                predicted_action = "cancel_order"
            elif "escalat" in response_lower:
                predicted_action = "escalate_to_human"
            elif "faq" in response_lower or "policy" in response_lower:
                predicted_action = "share_faq"

        # Evaluation
        intent_match = predicted_intent == NIGHTMARE_TICKET["expected_intent"]
        sentiment_match = predicted_sentiment == NIGHTMARE_TICKET["expected_sentiment"]
        escalation_match = predicted_escalate == NIGHTMARE_TICKET["expected_escalation"]
        action_match = (
            predicted_action == NIGHTMARE_TICKET["expected_action"]
            or "escalat" in predicted_action
            or NIGHTMARE_TICKET["expected_action"] in predicted_action
        )

        output = {
            "variant": variant,
            "ticket_id": "M4-016",
            "elapsed_ms": round(elapsed_ms, 0),
            # Predictions
            "predicted_intent": predicted_intent,
            "predicted_sentiment": predicted_sentiment,
            "predicted_escalate": predicted_escalate,
            "predicted_action": predicted_action,
            "intent_confidence": result.get("intent_confidence", 0),
            "quality_score": result.get("quality_score", 0),
            # Month 4 fields
            "clarifying_question": result.get("clarifying_question", ""),
            "multi_intent_detected": result.get("multi_intent_detected", False),
            "detected_intents": result.get("detected_intents", []),
            "low_confidence_flag": result.get("low_confidence_flag", False),
            "escalation_trigger_reason": result.get("escalation_trigger_reason", ""),
            "escalation_reason": result.get("escalation_reason", ""),
            # Expected
            "expected_intent": NIGHTMARE_TICKET["expected_intent"],
            "expected_sentiment": NIGHTMARE_TICKET["expected_sentiment"],
            "expected_escalation": NIGHTMARE_TICKET["expected_escalation"],
            "expected_action": NIGHTMARE_TICKET["expected_action"],
            # Correctness
            "intent_correct": intent_match,
            "sentiment_correct": sentiment_match,
            "escalation_correct": escalation_match,
            "action_correct": action_match,
            "overall_pass": intent_match and sentiment_match and escalation_match and action_match,
            # Raw response preview
            "final_response_preview": final_response[:500] if final_response else "",
            "pipeline_error": None,
        }

        return output

    except Exception as exc:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error("NIGHTMARE TEST FAILED for %s: %s", variant, exc, exc_info=True)
        return {
            "variant": variant,
            "ticket_id": "M4-016",
            "elapsed_ms": round(elapsed_ms, 0),
            "pipeline_error": str(exc),
            "overall_pass": False,
            "intent_correct": False,
            "sentiment_correct": False,
            "escalation_correct": False,
            "action_correct": False,
        }


async def main() -> None:
    """Run the nightmare ticket through all 3 variants sequentially."""
    print("\n" + "=" * 80)
    print("  NIGHTMARE TICKET TEST — M4-016")
    print("  Pure Observation Mode: No interference, just watching what the variants do")
    print("=" * 80)
    print()
    print("  Expected: intent=complaint | sentiment=angry | escalation=True | action=escalate")
    print()

    results = {}

    for variant in ["mini", "parwa", "high"]:
        logger.info("\n>>> Starting %s variant...", variant.upper())
        result = await run_nightmare_for_variant(variant)
        results[variant] = result

        # Print immediately so we can see progress
        icon = {"mini": "🟡", "parwa": "🔵", "high": "🟣"}.get(variant, "⚪")
        name = {"mini": "Mini PARWA", "parwa": "PARWA", "high": "PARWA High"}.get(variant, variant)
        status = "✓ PASS" if result.get("overall_pass") else "✗ FAIL"

        print(f"\n{icon} {name} — {status}")
        print("-" * 60)
        if result.get("pipeline_error"):
            print(f"  ERROR: {result['pipeline_error']}")
        else:
            intent_icon = "✓" if result.get("intent_correct") else "✗"
            sent_icon = "✓" if result.get("sentiment_correct") else "✗"
            esc_icon = "✓" if result.get("escalation_correct") else "✗"
            act_icon = "✓" if result.get("action_correct") else "✗"

            print(f"  Intent:     {intent_icon} {result.get('predicted_intent', '?'):20s}  (expected: {result.get('expected_intent', '?')})")
            print(f"  Sentiment:  {sent_icon} {result.get('predicted_sentiment', '?'):20s}  (expected: {result.get('expected_sentiment', '?')})")
            print(f"  Escalation: {esc_icon} {str(result.get('predicted_escalate', '?')):20s}  (expected: {result.get('expected_escalation', '?')})")
            print(f"  Action:     {act_icon} {result.get('predicted_action', '?'):20s}  (expected: {result.get('expected_action', '?')})")
            print(f"  Confidence: {result.get('intent_confidence', 0):.3f}")
            print(f"  Quality:    {result.get('quality_score', 0):.3f}")
            print(f"  Time:       {result.get('elapsed_ms', 0):.0f}ms")

            # Month 4 specific fields
            if result.get("multi_intent_detected"):
                print(f"  Multi-intent: YES — {result.get('detected_intents', [])}")
            if result.get("clarifying_question"):
                print(f"  Clarifying Q: {result['clarifying_question'][:100]}")
            if result.get("low_confidence_flag"):
                print(f"  Low confidence: YES")
            if result.get("escalation_trigger_reason") or result.get("escalation_reason"):
                esc_reason = result.get("escalation_trigger_reason") or result.get("escalation_reason", "")
                print(f"  Escalation reason: {esc_reason[:150]}")

            # Show response preview
            if result.get("final_response_preview"):
                print(f"\n  Response preview:")
                print(f"  {result['final_response_preview'][:300]}")

        # Rate limit pause between variants
        if variant != "high":
            logger.info("Pausing 5s before next variant...")
            await asyncio.sleep(5)

    # ─── Summary ───
    print("\n\n" + "=" * 80)
    print("  NIGHTMARE TICKET RESULTS SUMMARY")
    print("=" * 80)
    print(f"\n  {'Variant':<12s} {'Intent':<8s} {'Sentiment':<10s} {'Escalation':<11s} {'Action':<8s} {'Overall'}")
    print(f"  {'─' * 12} {'─' * 8} {'─' * 10} {'─' * 11} {'─' * 8} {'─' * 7}")

    for variant in ["mini", "parwa", "high"]:
        r = results.get(variant, {})
        intent_s = "✓" if r.get("intent_correct") else "✗"
        sent_s = "✓" if r.get("sentiment_correct") else "✗"
        esc_s = "✓" if r.get("escalation_correct") else "✗"
        act_s = "✓" if r.get("action_correct") else "✗"
        overall = "PASS" if r.get("overall_pass") else "FAIL"
        name = {"mini": "Mini", "parwa": "PARWA", "high": "High"}[variant]
        print(f"  {name:<12s} {intent_s:<8s} {sent_s:<10s} {esc_s:<11s} {act_s:<8s} {overall}")

    # What each variant got WRONG
    print("\n  Detailed mistakes:")
    for variant in ["mini", "parwa", "high"]:
        r = results.get(variant, {})
        mistakes = []
        if not r.get("intent_correct"):
            mistakes.append(f"intent: got '{r.get('predicted_intent', '?')}' expected 'complaint'")
        if not r.get("sentiment_correct"):
            mistakes.append(f"sentiment: got '{r.get('predicted_sentiment', '?')}' expected 'angry'")
        if not r.get("escalation_correct"):
            mistakes.append(f"escalation: got '{r.get('predicted_escalate', '?')}' expected True")
        if not r.get("action_correct"):
            mistakes.append(f"action: got '{r.get('predicted_action', '?')}' expected 'escalate'")
        name = {"mini": "Mini", "parwa": "PARWA", "high": "High"}[variant]
        if mistakes:
            for m in mistakes:
                print(f"    {name}: {m}")
        else:
            print(f"    {name}: No mistakes — PERFECT!")

    # Save results
    output_path = "/home/z/my-project/download/nightmare_test_results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to: {output_path}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
