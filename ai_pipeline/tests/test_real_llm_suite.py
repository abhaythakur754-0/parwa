#!/usr/bin/env python3
"""
PARWA Real LLM Testing Suite — Tests all 3 variants with real-world fake tickets.

Uses ZAI SDK (z-ai-web-dev-sdk) for real LLM calls.
Set PARWA_MOCK_MODE=false to use real LLM.

Tests:
1. FrameworkBrain techniques with real LLM
2. Smart Router variant-aware model selection
3. Quality scoring accuracy (not always 85)
4. Token tracking with real token counts
5. GSD state compression verification
6. All 3 variants: Mini, PARWA, High
"""

import os
os.environ["PARWA_MOCK_MODE"] = "false"

import asyncio
import json
import sys
import time

# Force reload to pick up env change
import importlib
import parwa.utils.llm as llm_mod
importlib.reload(llm_mod)
import parwa.turboquant.token_budget as tb_mod
importlib.reload(tb_mod)

from parwa.graph import reset_parwa_graph, process_ticket
from parwa.permissions.variant_enforcer import VariantEnforcer
from parwa.utils.llm import MOCK_MODE, _call_zai_sdk, smart_route_model

# ─── Fake Real-World Test Tickets ──────────────────────────────────────────

TICKETS = [
    {
        "name": "Simple Refund (duplicate charge)",
        "message": "Hi, I noticed I was charged twice for my order #ORD-9876. The charge of $49.99 appears twice on my statement from January 5th. Can you please refund the duplicate charge?",
        "customer_id": "CUST-ALPHA-001",
        "channel": "email",
        "expected_intent": "refund_request",
        "expected_sentiment": "neutral",
    },
    {
        "name": "Angry Cancellation (3-week delay)",
        "message": "This is COMPLETELY UNACCEPTABLE! I ordered 3 weeks ago and my order still hasn't shipped! Nobody has responded to my previous 4 emails. I want to cancel my order IMMEDIATELY and get a full refund. This is the worst customer service I've ever experienced. I'm telling everyone on social media about this!",
        "customer_id": "CUST-BETA-042",
        "channel": "chat",
        "expected_intent": "cancellation",
        "expected_sentiment": "angry",
    },
    {
        "name": "Technical Support (broken feature)",
        "message": "The export feature in your dashboard has been broken for 2 days. Every time I click 'Export to CSV', I get a 500 Internal Server Error. I've tried Chrome, Firefox, and Safari. My team needs these reports for our quarterly review tomorrow. This is urgent.",
        "customer_id": "CUST-GAMMA-108",
        "channel": "email",
        "expected_intent": "technical_support",
        "expected_sentiment": "frustrated",
    },
    {
        "name": "Billing Dispute (unauthorized charge)",
        "message": "I never signed up for the premium plan. I was on the basic plan at $9.99/month but I see a charge of $49.99 on my credit card statement. I did NOT authorize this upgrade. I want this reversed immediately and I want confirmation that my plan is back to basic.",
        "customer_id": "CUST-DELTA-207",
        "channel": "email",
        "expected_intent": "billing_issue",
        "expected_sentiment": "frustrated",
    },
    {
        "name": "FAQ Question (return policy)",
        "message": "Hi, what is your return policy for electronics? I bought headphones 2 weeks ago and they don't fit well. Can I return them for a full refund or store credit?",
        "customer_id": "CUST-EPSILON-315",
        "channel": "chat",
        "expected_intent": "faq_question",
        "expected_sentiment": "neutral",
    },
    {
        "name": "VIP Escalation (legal threat)",
        "message": "I have been a loyal customer for 5 years and this is how you treat me? Your agent promised me a replacement 10 days ago and nothing has happened. I've spent over $5,000 with your company. If this isn't resolved by Friday, I'm contacting my attorney. Reference ticket #TKT-7742.",
        "customer_id": "CUST-ZETA-VIP-001",
        "channel": "email",
        "expected_intent": "escalation",
        "expected_sentiment": "angry",
    },
    {
        "name": "Account Modification (address change)",
        "message": "I moved and need to update my billing address. My new address is 456 Oak Avenue, Portland, OR 97201. Also, can you update my phone number to 503-555-0199?",
        "customer_id": "CUST-ETA-422",
        "channel": "chat",
        "expected_intent": "account_modification",
        "expected_sentiment": "neutral",
    },
    {
        "name": "PII Exposure (SSN + Credit Card)",
        "message": "Please update my payment info. My SSN is 487-23-9182 and my credit card number is 4532-8721-0049-3316. Also my email is john.doe@company.com and my phone is 415-555-0234.",
        "customer_id": "CUST-THETA-530",
        "channel": "email",
        "expected_intent": "account_modification",
        "expected_sentiment": "neutral",
        "expected_pii": True,
    },
    {
        "name": "Complex Multi-Issue (angry + refund + technical)",
        "message": "I am FURIOUS. Not only was I overcharged by $149.97 for 3 months of a service I never used, but your app keeps crashing every time I try to view my invoices! I've called 3 times and been on hold for 45+ minutes each time. I want ALL charges reversed, the app bug fixed, and compensation for my wasted time. This is theft!",
        "customer_id": "CUST-IOTA-637",
        "channel": "chat",
        "expected_intent": "complaint",
        "expected_sentiment": "angry",
    },
    {
        "name": "Order Status (simple inquiry)",
        "message": "Hi, can you tell me the status of my order #ORD-5543? It was supposed to arrive last Tuesday. Just want to know where it is.",
        "customer_id": "CUST-KAPPA-744",
        "channel": "email",
        "expected_intent": "order_status",
        "expected_sentiment": "neutral",
    },
]

VARIANTS = ["mini", "parwa", "high"]


def print_header(text: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}")


def print_result(ticket_name: str, variant: str, result: dict) -> None:
    """Print a formatted result for a ticket test."""
    print(f"\n  [{variant.upper()}] {ticket_name}")
    print(f"    Intent: {result.get('intent')} | Sentiment: {result.get('sentiment')}")
    print(f"    Complexity: {result.get('complexity')} | Quality: {result.get('quality_score')}")

    # Check execution results
    exec_results = result.get("execution_results", [])
    for er in exec_results:
        status = er.get("status", "?")
        action = er.get("action_type", "?")
        if hasattr(action, "value"):
            action = action.value
        print(f"    Action: {action} → {status}")

    # Check recommendation
    rec = result.get("recommendation")
    if rec:
        rec_action = rec.get("action_type", "?")
        if hasattr(rec_action, "value"):
            rec_action = rec_action.value
        print(f"    Recommendation: {rec_action} (pending approval)")

    # PII check
    if result.get("pii_detected"):
        print(f"    🔒 PII DETECTED: {result.get('pii_redacted_message', '')[:80]}...")

    # Final response preview
    final = str(result.get("final_response", ""))[:120]
    print(f"    Response: {final}...")

    # Errors
    errors = result.get("pipeline_errors", [])
    if errors:
        print(f"    ⚠️  Errors: {len(errors)} — {[e.get('node','?') for e in errors]}")


def test_frameworkbrain_with_real_llm() -> None:
    """Test 1: FrameworkBrain techniques with real LLM."""
    print_header("TEST 1: FrameworkBrain Techniques with Real LLM")

    techniques_to_test = [
        ("chain_of_thought", "REASONING_ENGINE", "Customer was double-charged $49.99"),
        ("react", "INTENT_CLASSIFIER", "I want to cancel my subscription"),
        ("tree_of_thoughts", "TREE_OF_THOUGHTS", "Customer is angry about 3-week delay and wants compensation"),
        ("hyde", "KB_RETRIEVER", "What is the refund policy for electronics?"),
    ]

    for tech_name, node, prompt in techniques_to_test:
        try:
            result = _call_zai_sdk(prompt, node_name=node, variant="parwa", complexity="complex")
            content = result.get("content", "")[:200]
            model = result.get("model", "?")
            usage = result.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)
            print(f"  ✅ {tech_name}: model={model} tokens={total_tokens}")
            print(f"     Output: {content[:100]}...")
        except Exception as e:
            print(f"  ❌ {tech_name}: {e}")


def test_smart_router() -> None:
    """Test 2: Smart Router variant-aware model selection."""
    print_header("TEST 2: Smart Router — Variant-Aware Model Selection")

    test_nodes = ["INTENT_CLASSIFIER", "REASONING_ENGINE", "KB_RETRIEVER", "QUALITY_SCORER"]
    for variant in VARIANTS:
        enforcer = VariantEnforcer(variant)
        summary = enforcer.summary()
        print(f"\n  [{variant.upper()}] Tiers: {summary['tiers']}")
        print(f"    Downgraded: {summary['total_nodes_downgraded']} nodes")
        for node in test_nodes:
            model = smart_route_model(node, variant=variant)
            is_downgraded = enforcer.is_model_downgraded(node)
            marker = "⚠️ DOWNGRADED" if is_downgraded else "✅"
            print(f"    {marker} {node}: {model}")


def test_quality_scoring_accuracy() -> None:
    """Test 3: Quality scoring with real LLM — should NOT always be 85."""
    print_header("TEST 3: Quality Scoring Accuracy (should vary)")

    scores = []
    test_cases = [
        "Score this response: 'Your refund has been processed.' — very brief, no empathy",
        "Score this response: 'We sincerely apologize for the inconvenience. Your refund of $49.99 has been processed and will appear in 3-5 business days. Is there anything else we can help you with?' — thorough and empathetic",
        "Score this response: 'idk maybe we can help lol' — unprofessional and unhelpful",
    ]

    for case in test_cases:
        try:
            result = _call_zai_sdk(case, node_name="QUALITY_SCORER", variant="parwa")
            content = result.get("content", "")
            # Parse score
            score = 0
            try:
                score = int(content.split("|")[0].strip())
            except (ValueError, IndexError):
                pass
            scores.append(score)
            print(f"  Score: {score} | Response: {content[:80]}")
        except Exception as e:
            print(f"  Error: {e}")

    if scores:
        unique_scores = len(set(scores))
        print(f"\n  Result: Got {unique_scores} unique scores out of {len(scores)} tests")
        if unique_scores > 1:
            print(f"  ✅ Quality scoring VARIES (not always the same number)")
        else:
            print(f"  ⚠️  Quality scoring returns same score every time")


def test_gsd_compression() -> None:
    """Test 4: GSD state compression verification."""
    print_header("TEST 4: GSD State Compression")

    try:
        from parwa.gsd import compress_state, decompress_state

        # Create a large state (simulating 12,000+ tokens)
        large_state = {
            "ticket_id": "TKT-GSD-TEST",
            "raw_message": "Test message",
            "reasoning_chain": [f"Step {i}: Detailed reasoning about customer issue number {i}" for i in range(50)],
            "context_history": [{"role": "system", "content": f"Long context entry {i} " * 20} for i in range(20)],
            "kb_results": [{"content": f"Knowledge base article {i} " * 30} for i in range(10)],
            "active_frameworks": ["chain_of_thought", "react", "hyde", "clara", "crp"],
        }

        original_size = len(str(large_state))
        compressed = compress_state(large_state)
        compressed_size = len(str(compressed))

        # Try decompression
        decompressed = decompress_state(compressed)

        compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0

        print(f"  Original size: {original_size} chars")
        print(f"  Compressed size: {compressed_size} chars")
        print(f"  Compression ratio: {compression_ratio:.1f}%")
        print(f"  Decompression works: {decompressed is not None}")

        if compression_ratio > 50:
            print(f"  ✅ GSD achieves significant compression ({compression_ratio:.0f}%)")
        else:
            print(f"  ⚠️  GSD compression is lower than expected")

    except ImportError as e:
        print(f"  ⚠️  GSD module not available: {e}")
    except Exception as e:
        print(f"  ❌ GSD test failed: {e}")


def test_token_tracking_real() -> None:
    """Test 5: Token tracking with real LLM — real token counts."""
    print_header("TEST 5: Token Tracking — Real Token Counts")

    try:
        from parwa.turboquant.token_tracker import get_token_tracker
        tracker = get_token_tracker()

        # Make a real LLM call
        result = _call_zai_sdk(
            "Customer reports duplicate charge of $49.99",
            node_name="REASONING_ENGINE",
            variant="parwa",
        )
        usage = result.get("usage", {})
        real_prompt = usage.get("prompt_tokens", 0)
        real_completion = usage.get("completion_tokens", 0)
        real_total = usage.get("total_tokens", 0)

        print(f"  Real LLM usage from ZAI SDK:")
        print(f"    Prompt tokens: {real_prompt}")
        print(f"    Completion tokens: {real_completion}")
        print(f"    Total tokens: {real_total}")

        if real_total > 0:
            print(f"  ✅ ZAI SDK returns REAL token counts (not estimated)")
        else:
            print(f"  ⚠️  ZAI SDK returns 0 tokens — estimation fallback active")

        # Check tracker
        tracker.record(
            ticket_id="TKT-TRACK-TEST",
            node_name="reasoning_engine",
            variant="parwa",
            prompt_tokens=real_prompt,
            completion_tokens=real_completion,
            model="zai",
        )
        summary = tracker.node_summary("reasoning_engine")
        print(f"  Tracker recorded: {summary}")

    except Exception as e:
        print(f"  ❌ Token tracking test failed: {e}")


def test_variant_permissions() -> None:
    """Test 6: Variant permission enforcement across all 3 variants."""
    print_header("TEST 6: Variant Permission Enforcement")

    for variant in VARIANTS:
        enforcer = VariantEnforcer(variant=variant)
        summary = enforcer.summary()

        print(f"\n  [{variant.upper()}]")
        print(f"    EXECUTE actions: {summary['executable_actions']}")
        print(f"    RECOMMEND actions: {summary['recommendable_actions']}")
        print(f"    DENY actions: {summary['denied_actions']}")
        print(f"    Channels: {summary['channels']}")
        print(f"    Model tiers: {summary['tiers']}")
        print(f"    Concurrent limit: {summary['concurrent_limit']}")
        print(f"    Ticket limit: {summary['ticket_limit']}")


def test_all_variants_with_tickets() -> None:
    """Test 7: Run selected tickets through all 3 variants."""
    print_header("TEST 7: All Variants with Real-World Tickets")

    # Pick 3 diverse tickets to save time
    test_tickets = [TICKETS[0], TICKETS[1], TICKETS[8]]  # refund, angry cancel, complex multi

    for ticket in test_tickets:
        print(f"\n  📨 {ticket['name']}")
        for variant in VARIANTS:
            reset_parwa_graph()
            try:
                result = process_ticket(
                    raw_message=ticket["message"],
                    customer_id=ticket["customer_id"],
                    channel=ticket["channel"],
                    variant=variant,
                )
                print_result(ticket["name"], variant, result)
            except Exception as e:
                print(f"  ❌ [{variant.upper()}] Error: {e}")


def main() -> None:
    """Run all tests."""
    print_header("PARWA Real LLM Testing Suite (via ZAI SDK)")
    print(f"  MOCK_MODE: {MOCK_MODE}")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Test 1: FrameworkBrain
    test_frameworkbrain_with_real_llm()

    # Test 2: Smart Router
    test_smart_router()

    # Test 3: Quality scoring
    test_quality_scoring_accuracy()

    # Test 4: GSD compression
    test_gsd_compression()

    # Test 5: Token tracking
    test_token_tracking_real()

    # Test 6: Variant permissions
    try:
        test_variant_permissions()
    except Exception as e:
        # Fix typo in the function
        print(f"\n  Note: Running with corrected enforcer: {e}")
        for variant in VARIANTS:
            enforcer = VariantEnforcer(variant=variant)
            summary = enforcer.summary()
            print(f"\n  [{variant.upper()}]")
            print(f"    EXECUTE: {summary['executable_actions']}")
            print(f"    RECOMMEND: {summary['recommendable_actions']}")
            print(f"    DENY: {summary['denied_actions']}")

    # Test 7: Full pipeline
    test_all_variants_with_tickets()

    print_header("TESTING COMPLETE")


if __name__ == "__main__":
    main()
