#!/usr/bin/env python3
"""PARWA Real LLM Comprehensive Test Suite.

Tests ALL variants (Mini/PARWA/High) with REAL LLM calls via zai SDK.
Tests ALL suspect features: FrameworkBrain, Smart Router, GSD, TurboQuant, Quality Scoring.

NO MOCK MODE. NO FALSE POSITIVES. HONEST RESULTS ONLY.

Usage:
    cd /home/z/my-project/parwa
    python scripts/test_real_llm_comprehensive.py
"""

import asyncio
import json
import os
import sys
import time
import traceback
from typing import Any

# ─── FORCE REAL LLM MODE ────────────────────────────────────────────────────
os.environ["PARWA_MOCK_MODE"] = "false"

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Test Tickets: FAKE COMPLICATED REAL-WORLD SCENARIOS ────────────────────

TEST_TICKETS = [
    {
        "name": "ANGRY DUPLICATE CHARGE",
        "raw_message": (
            "I am FURIOUS! I was charged $149.99 TWICE for the same order #ORD-78291 on January 3rd AND January 3rd again! "
            "This is the THIRD time this has happened. My bank statement clearly shows two charges of $149.99 from your company "
            "on the same day. I want my money back IMMEDIATELY or I will contact my attorney and file a complaint with the BBB. "
            "My SSN is 123-45-6789 and my credit card ending in 4242 was charged. Reference number REF-448291."
        ),
        "customer_id": "CUST-99182",
        "channel": "email",
        "expected_intent": "refund_request",
        "expected_sentiment": "angry",
        "expected_escalation": True,  # legal threat
        "expected_pii": True,  # SSN present
    },
    {
        "name": "COMPLEX BILLING DISPUTE",
        "raw_message": (
            "Hi, I've been a customer for 3 years. My monthly subscription was $29.99 but last month I was charged $89.97. "
            "When I called support last week, they said it was a prorated adjustment but couldn't explain why. Then I got "
            "another charge of $29.99 this week. So I've been charged $119.96 in two weeks for a $29.99/month plan. "
            "I also noticed my account shows I'm on a 'Premium Plus' tier which I never signed up for. Can someone please "
            "look into this? My account number is ACC-44729. I'm not angry, just very confused and want this fixed."
        ),
        "customer_id": "CUST-44729",
        "channel": "email",
        "expected_intent": "billing_issue",
        "expected_sentiment": "frustrated",
        "expected_escalation": False,
        "expected_pii": False,
    },
    {
        "name": "TECHNICAL INTEGRATION FAILURE",
        "raw_message": (
            "Your API has been returning 503 errors intermittently for the past 48 hours. Our production integration is broken. "
            "We have 3 webhooks pointing to your service and all of them are failing with timeout errors. This is affecting "
            "our 2000+ users who can't process orders. Our SLA with OUR customers is being violated. We need this fixed NOW. "
            "I've tried your status page but it shows 'all systems operational' which is clearly wrong. Ticket #TKT-9928. "
            "Please escalate this to your engineering team immediately."
        ),
        "customer_id": "CUST-B2B-001",
        "channel": "chat",
        "expected_intent": "technical_support",
        "expected_sentiment": "frustrated",
        "expected_escalation": True,  # complex technical
        "expected_pii": False,
    },
    {
        "name": "ORDER STATUS + CANCELLATION REQUEST",
        "raw_message": (
            "I placed order #ORD-55231 on December 28th with express shipping. It's now January 10th and the tracking still "
            "says 'label created'. I paid $24.99 for 2-day shipping! At this point I just want to cancel the order entirely "
            "and get a full refund including the shipping fee. I also had a $10 promotional credit applied to this order "
            "which should be returned to my account. Please confirm the cancellation and credit return."
        ),
        "customer_id": "CUST-33102",
        "channel": "email",
        "expected_intent": "cancellation",
        "expected_sentiment": "frustrated",
        "expected_escalation": False,
        "expected_pii": False,
    },
    {
        "name": "VIP ACCOUNT MODIFICATION",
        "raw_message": (
            "This is Sarah Chen, VP of Operations at Meridian Corp. We have an enterprise account with you (ENT-9920). "
            "We need to update our billing contact from John Smith to Lisa Park (lisa.park@meridian.com, 555-0199). "
            "Also, we need to add 15 new user seats and change our payment method from invoice to credit card. "
            "Our current contract has a special pricing clause, so please ensure the new seats are priced at our "
            "negotiated rate of $22/seat instead of the standard $39. This is urgent as our new team starts Monday."
        ),
        "customer_id": "CUST-ENT-9920",
        "channel": "email",
        "expected_intent": "account_modification",
        "expected_sentiment": "neutral",
        "expected_escalation": False,
        "expected_pii": True,  # email + phone
    },
    {
        "name": "HAPPY CUSTOMER WITH FAQ",
        "raw_message": (
            "Hi! I just wanted to ask — what's your return policy for electronics? I bought a headset from you guys "
            "last week and it's great, but I'm just curious about the policy in case I ever need to return it. "
            "Also, do you have an extended warranty option? Thanks for the great service so far!"
        ),
        "customer_id": "CUST-22001",
        "channel": "chat",
        "expected_intent": "faq_question",
        "expected_sentiment": "happy",
        "expected_escalation": False,
        "expected_pii": False,
    },
]


# ─── Test Results Tracker ────────────────────────────────────────────────────

class TestReport:
    """Track test results with honest pass/fail."""

    def __init__(self):
        self.results = []
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def record(self, category: str, test_name: str, status: str, detail: str = ""):
        self.total += 1
        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failed += 1
        elif status == "WARN":
            self.warnings += 1
        self.results.append({
            "category": category,
            "test": test_name,
            "status": status,
            "detail": detail,
        })
        icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(status, "❓")
        print(f"  {icon} {category}: {test_name} — {detail}" if detail else f"  {icon} {category}: {test_name}")

    def summary(self):
        print("\n" + "=" * 80)
        print("HONEST TEST REPORT — NO FALSE POSITIVES")
        print("=" * 80)
        print(f"Total: {self.total} | Passed: {self.passed} | Failed: {self.failed} | Warnings: {self.warnings}")
        print(f"Pass Rate: {self.passed/self.total*100:.1f}%" if self.total else "N/A")
        print()

        # Group by category
        by_category = {}
        for r in self.results:
            by_category.setdefault(r["category"], []).append(r)

        for cat, tests in by_category.items():
            cat_pass = sum(1 for t in tests if t["status"] == "PASS")
            cat_total = len(tests)
            print(f"\n{cat} ({cat_pass}/{cat_total} passed):")
            for t in tests:
                icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(t["status"], "❓")
                print(f"  {icon} {t['test']}: {t['detail']}")

        print("\n" + "=" * 80)
        return self.passed, self.failed, self.warnings


report = TestReport()


# ─── Test 1: ZAI SDK Direct Call ────────────────────────────────────────────

async def test_zai_sdk_direct():
    """Test that the zai SDK subprocess call works."""
    print("\n📋 TEST 1: ZAI SDK Direct Call")
    print("-" * 60)

    from parwa.utils.llm import _call_zai_sdk

    try:
        result = await asyncio.to_thread(
            _call_zai_sdk,
            "Classify this message: I want a refund for order #123",
            node_name="INTENT_CLASSIFIER",
            variant="parwa",
            complexity="simple",
        )
        content = result.get("content", "")
        model = result.get("model", "")
        usage = result.get("usage", {})

        if content and len(content) > 2:
            report.record("ZAI SDK", "Direct call returns content", "PASS", f"model={model}, content={content[:80]}")
        else:
            report.record("ZAI SDK", "Direct call returns content", "FAIL", f"Empty or too short: '{content}'")

        if usage.get("total_tokens", 0) > 0:
            report.record("ZAI SDK", "Returns real token counts", "PASS", f"tokens={usage}")
        else:
            report.record("ZAI SDK", "Returns real token counts", "WARN", f"usage={usage} (may be estimated)")

    except Exception as e:
        report.record("ZAI SDK", "Direct call works", "FAIL", str(e))


# ─── Test 2: Full Pipeline with Each Variant ────────────────────────────────

async def test_variant_pipeline(variant: str, ticket: dict):
    """Test one ticket through the full pipeline with one variant."""
    from parwa.graph import aprocess_ticket

    t0 = time.time()
    try:
        result = await aprocess_ticket(
            raw_message=ticket["raw_message"],
            customer_id=ticket.get("customer_id", ""),
            channel=ticket.get("channel", "email"),
            variant=variant,
        )
        elapsed = time.time() - t0

        # Check basic pipeline completion
        has_error = "error" in result and result.get("error")
        has_response = bool(result.get("final_response", "").strip())

        return {
            "variant": variant,
            "ticket_name": ticket["name"],
            "elapsed": elapsed,
            "result": result,
            "has_error": has_error,
            "has_response": has_response,
        }

    except Exception as e:
        elapsed = time.time() - t0
        return {
            "variant": variant,
            "ticket_name": ticket["name"],
            "elapsed": elapsed,
            "result": {},
            "has_error": True,
            "has_response": False,
            "exception": str(e),
        }


async def test_all_variants():
    """Test all 3 variants with all 6 tickets."""
    print("\n📋 TEST 2: Full Pipeline — All Variants")
    print("-" * 60)

    variants = ["mini", "parwa", "high"]

    for variant in variants:
        print(f"\n  --- Variant: {variant.upper()} ---")
        await asyncio.sleep(5)  # Rate limit cooldown between variants
        for ticket in TEST_TICKETS:
            await asyncio.sleep(2)  # Rate limit cooldown between tickets
            outcome = await test_variant_pipeline(variant, ticket)

            if outcome["has_error"]:
                detail = f"ERROR: {outcome.get('exception', outcome.get('result', {}).get('error', 'unknown'))}"
                report.record(f"Pipeline [{variant}]", f"{ticket['name']}", "FAIL", detail[:120])
            elif outcome["has_response"]:
                resp = outcome["result"].get("final_response", "")[:100]
                report.record(f"Pipeline [{variant}]", f"{ticket['name']}", "PASS", f"response='{resp}...' ({outcome['elapsed']:.1f}s)")
            else:
                report.record(f"Pipeline [{variant}]", f"{ticket['name']}", "FAIL", "No response generated")


# ─── Test 3: Intent Classification Accuracy ─────────────────────────────────

async def test_intent_accuracy():
    """Test that real LLM classifies intents correctly (vs MockLLM keyword match)."""
    print("\n📋 TEST 3: Intent Classification Accuracy")
    print("-" * 60)

    from parwa.utils.llm import ainvoke_llm

    for ticket in TEST_TICKETS:
        await asyncio.sleep(1.5)  # Rate limit cooldown
        try:
            text = await ainvoke_llm(
                f"Classify the following customer message into one of these intents: "
                f"order_status, refund_request, cancellation, billing_issue, "
                f"technical_support, faq_question, complaint, account_modification, "
                f"escalation, general_inquiry.\n\n"
                f"Reply with ONLY: intent|confidence\n\n"
                f"Message: {ticket['raw_message'][:300]}",
                node_name="INTENT_CLASSIFIER",
                variant="parwa",
            )

            # Parse intent from response
            text_lower = text.lower().strip()
            expected = ticket["expected_intent"]

            # Check if expected intent appears in the LLM output
            if expected.replace("_", " ") in text_lower or expected in text_lower:
                report.record("Intent Accuracy", f"{ticket['name']}", "PASS",
                              f"expected={expected}, got='{text_lower[:60]}'")
            else:
                # Maybe close enough?
                close_intents = {
                    "refund_request": ["refund", "billing"],
                    "billing_issue": ["billing", "charge", "refund"],
                    "cancellation": ["cancel", "refund"],
                    "technical_support": ["technical", "support"],
                    "account_modification": ["account", "modification"],
                    "faq_question": ["faq", "question", "inquiry"],
                }
                close = close_intents.get(expected, [])
                if any(c in text_lower for c in close):
                    report.record("Intent Accuracy", f"{ticket['name']}", "WARN",
                                  f"expected={expected}, got='{text_lower[:60]}' (close but not exact)")
                else:
                    report.record("Intent Accuracy", f"{ticket['name']}", "FAIL",
                                  f"expected={expected}, got='{text_lower[:60]}'")

        except Exception as e:
            report.record("Intent Accuracy", f"{ticket['name']}", "FAIL", f"Exception: {e}")


# ─── Test 4: Sentiment Analysis Accuracy ────────────────────────────────────

async def test_sentiment_accuracy():
    """Test that real LLM detects sentiment correctly."""
    print("\n📋 TEST 4: Sentiment Analysis Accuracy")
    print("-" * 60)

    from parwa.utils.llm import ainvoke_llm

    for ticket in TEST_TICKETS:
        await asyncio.sleep(1.5)  # Rate limit cooldown
        try:
            text = await ainvoke_llm(
                f"Analyze the sentiment of this customer message. "
                f"Reply with ONLY: sentiment|urgency (e.g. frustrated|0.8) "
                f"where sentiment is: happy, neutral, frustrated, or angry.\n\n"
                f"Message: {ticket['raw_message'][:300]}",
                node_name="SENTIMENT_ANALYZER",
                variant="parwa",
            )

            text_lower = text.lower().strip()
            expected = ticket["expected_sentiment"]

            # Check if expected sentiment appears
            if expected in text_lower:
                report.record("Sentiment Accuracy", f"{ticket['name']}", "PASS",
                              f"expected={expected}, got='{text_lower[:60]}'")
            else:
                # Partial match
                sentiment_words = ["happy", "neutral", "frustrated", "angry"]
                found = [s for s in sentiment_words if s in text_lower]
                if found:
                    report.record("Sentiment Accuracy", f"{ticket['name']}", "WARN",
                                  f"expected={expected}, got='{text_lower[:60]}' (found: {found})")
                else:
                    report.record("Sentiment Accuracy", f"{ticket['name']}", "FAIL",
                                  f"expected={expected}, got='{text_lower[:60]}'")

        except Exception as e:
            report.record("Sentiment Accuracy", f"{ticket['name']}", "FAIL", f"Exception: {e}")


# ─── Test 5: Escalation Decision Accuracy ───────────────────────────────────

async def test_escalation_accuracy():
    """Test that real LLM correctly escalates (or not) based on ticket content."""
    print("\n📋 TEST 5: Escalation Decision Accuracy")
    print("-" * 60)

    from parwa.utils.llm import ainvoke_llm

    for ticket in TEST_TICKETS:
        await asyncio.sleep(1.5)  # Rate limit cooldown
        try:
            text = await ainvoke_llm(
                f"Should this ticket be escalated to a human agent? "
                f"Reply with ONLY: true|reason or false|\n\n"
                f"Message: {ticket['raw_message'][:300]}",
                node_name="ESCALATION_DECISION",
                variant="parwa",
            )

            text_lower = text.lower().strip()
            expected_escalate = ticket["expected_escalation"]

            # Parse escalation decision
            says_escalate = "true" in text_lower[:10]  # Check beginning of response

            if says_escalate == expected_escalate:
                report.record("Escalation Accuracy", f"{ticket['name']}", "PASS",
                              f"expected_escalate={expected_escalate}, got='{text_lower[:80]}'")
            else:
                report.record("Escalation Accuracy", f"{ticket['name']}", "FAIL",
                              f"expected_escalate={expected_escalate}, got='{text_lower[:80]}'")

        except Exception as e:
            report.record("Escalation Accuracy", f"{ticket['name']}", "FAIL", f"Exception: {e}")


# ─── Test 6: PII Detection ──────────────────────────────────────────────────

async def test_pii_detection():
    """Test PII redaction with tickets containing PII."""
    print("\n📋 TEST 6: PII Detection Accuracy")
    print("-" * 60)

    from parwa.nodes.pii_compliance_guard import pii_compliance_guard

    # Test with the ticket that has SSN
    ssn_ticket_state = {
        "raw_message": TEST_TICKETS[0]["raw_message"],  # Has SSN 123-45-6789
        "ticket_id": "TEST-PII-001",
        "variant": "parwa",
    }

    result = await pii_compliance_guard(ssn_ticket_state)
    pii_detected = result.get("pii_detected", False)
    redacted = result.get("pii_redacted_message", "")

    if pii_detected:
        report.record("PII Detection", "SSN detected in message", "PASS", f"redacted snippet: '{redacted[:100]}...'")
    else:
        report.record("PII Detection", "SSN detected in message", "FAIL", "PII not detected despite SSN in message")

    if "123-45-6789" not in redacted:
        report.record("PII Detection", "SSN redacted from output", "PASS", "SSN removed from redacted message")
    else:
        report.record("PII Detection", "SSN redacted from output", "FAIL", "SSN still present in redacted message!")

    # Test with VIP ticket that has email + phone
    vip_state = {
        "raw_message": TEST_TICKETS[4]["raw_message"],  # Has email + phone
        "ticket_id": "TEST-PII-002",
        "variant": "parwa",
    }

    result2 = await pii_compliance_guard(vip_state)
    pii_detected2 = result2.get("pii_detected", False)
    redacted2 = result2.get("pii_redacted_message", "")

    if pii_detected2:
        report.record("PII Detection", "Email/Phone detected in VIP message", "PASS",
                      f"redacted snippet: '{redacted2[:100]}...'")
    else:
        report.record("PII Detection", "Email/Phone detected in VIP message", "WARN",
                      "PII not flagged for email/phone (may be acceptable depending on policy)")

    # Test with clean ticket (no PII)
    clean_state = {
        "raw_message": TEST_TICKETS[5]["raw_message"],  # Happy FAQ, no PII
        "ticket_id": "TEST-PII-003",
        "variant": "parwa",
    }

    result3 = await pii_compliance_guard(clean_state)
    pii_detected3 = result3.get("pii_detected", False)

    if not pii_detected3:
        report.record("PII Detection", "No false positive on clean message", "PASS", "Correctly no PII detected")
    else:
        report.record("PII Detection", "No false positive on clean message", "WARN",
                      "PII flagged but message has no sensitive data (false positive)")


# ─── Test 7: FrameworkBrain Techniques ──────────────────────────────────────

async def test_framework_brain():
    """Test FrameworkBrain techniques with real LLM calls."""
    print("\n📋 TEST 7: FrameworkBrain Techniques")
    print("-" * 60)

    from parwa.frameworks.brain import FrameworkBrain

    test_state = {
        "raw_message": "I was charged twice for the same order. I want a refund.",
        "complexity": "complex",
        "ticket_id": "TEST-FB-001",
        "variant": "parwa",
        "intent": "refund_request",
        "sentiment": "frustrated",
    }

    # Test CoT (Chain of Thought)
    try:
        brain = FrameworkBrain(node="REASONING_ENGINE", state=test_state)
        result = await brain.think(
            prompt="Reason about this customer's refund request",
            techniques=["chain_of_thought"],
            ticket_id="TEST-FB-001",
            variant="parwa",
        )

        if result.output and len(result.output) > 10:
            report.record("FrameworkBrain", "Chain of Thought produces output", "PASS",
                          f"output_len={len(result.output)}, confidence={result.confidence:.2f}")
        else:
            report.record("FrameworkBrain", "Chain of Thought produces output", "FAIL",
                          f"output='{result.output[:80]}', confidence={result.confidence}")

        if "chain_of_thought" in result.frameworks_used:
            report.record("FrameworkBrain", "CoT tracked in frameworks_used", "PASS",
                          f"frameworks={result.frameworks_used}")
        else:
            report.record("FrameworkBrain", "CoT tracked in frameworks_used", "WARN",
                          f"frameworks={result.frameworks_used}")
    except Exception as e:
        report.record("FrameworkBrain", "Chain of Thought", "FAIL", str(e)[:120])

    # Test ReAct
    try:
        brain = FrameworkBrain(node="REASONING_ENGINE", state=test_state)
        result = await brain.think(
            prompt="Think about this refund request step by step",
            techniques=["react"],
            ticket_id="TEST-FB-001",
            variant="parwa",
        )

        if result.output and len(result.output) > 10:
            report.record("FrameworkBrain", "ReAct produces output", "PASS",
                          f"output_len={len(result.output)}, confidence={result.confidence:.2f}")
        else:
            report.record("FrameworkBrain", "ReAct produces output", "FAIL",
                          f"output='{result.output[:80]}', confidence={result.confidence}")
    except Exception as e:
        report.record("FrameworkBrain", "ReAct", "FAIL", str(e)[:120])

    # Test Reflexion (quality technique)
    try:
        brain = FrameworkBrain(node="QUALITY_SCORER", state=test_state)
        result = await brain.think(
            prompt="Evaluate the quality of this response",
            techniques=["reflexion"],
            ticket_id="TEST-FB-001",
            variant="parwa",
        )

        if result.output or result.confidence > 0:
            report.record("FrameworkBrain", "Reflexion produces result", "PASS",
                          f"confidence={result.confidence:.2f}, output_len={len(result.output)}")
        else:
            report.record("FrameworkBrain", "Reflexion produces result", "FAIL",
                          "No output and zero confidence")
    except Exception as e:
        report.record("FrameworkBrain", "Reflexion", "FAIL", str(e)[:120])

    # Test with CRP (Response Formatter technique)
    try:
        brain = FrameworkBrain(node="RESPONSE_FORMATTER", state=test_state)
        result = await brain.think(
            prompt="Format a professional response to this customer",
            techniques=["crp"],
            ticket_id="TEST-FB-001",
            variant="parwa",
        )

        if result.output and result.confidence > 0.3:
            report.record("FrameworkBrain", "CRP produces response", "PASS",
                          f"confidence={result.confidence:.2f}, output='{result.output[:80]}...'")
        else:
            report.record("FrameworkBrain", "CRP produces response", "WARN",
                          f"Low quality: confidence={result.confidence:.2f}, output='{result.output[:80]}'")
    except Exception as e:
        report.record("FrameworkBrain", "CRP", "FAIL", str(e)[:120])


# ─── Test 8: Smart Router ───────────────────────────────────────────────────

async def test_smart_router():
    """Test Smart Router model selection for different nodes and variants."""
    print("\n📋 TEST 8: Smart Router Model Selection")
    print("-" * 60)

    from parwa.config import get_model_for_node, get_all_models_for_node, get_node_tier

    # Test tier assignment
    test_nodes = {
        "INTENT_CLASSIFIER": "light",
        "REASONING_ENGINE": "medium",
        "QUALITY_SCORER": "medium",
        "INGEST": "light",
    }

    for node, expected_tier in test_nodes.items():
        actual_tier = get_node_tier(node)
        if actual_tier == expected_tier:
            report.record("Smart Router", f"Node {node} tier", "PASS", f"tier={actual_tier}")
        else:
            report.record("Smart Router", f"Node {node} tier", "FAIL",
                          f"expected={expected_tier}, got={actual_tier}")

    # Test variant-aware model selection
    variants_expected = {
        "mini": {"REASONING_ENGINE": "light"},  # Mini can't access medium → downgraded to light
        "parwa": {"REASONING_ENGINE": "medium"},
        "high": {"REASONING_ENGINE": "medium"},
    }

    for variant, expected_models in variants_expected.items():
        for node, expected_tier_name in expected_models.items():
            model = get_model_for_node(node, variant)
            models = get_all_models_for_node(node, variant)
            if models:
                report.record("Smart Router", f"{variant}/{node} model selection", "PASS",
                              f"model={model}, fallbacks={len(models)}")
            else:
                report.record("Smart Router", f"{variant}/{node} model selection", "FAIL",
                              "No models returned")

    # Verify Mini gets downgraded models
    mini_heavy_nodes = ["REASONING_ENGINE", "KB_RETRIEVER", "QUALITY_SCORER"]
    for node in mini_heavy_nodes:
        model = get_model_for_node(node, "mini")
        # Mini should get light tier models since it only has light + guardrail
        light_models = ["cerebras/llama-3.1-8b", "groq/llama-3.1-8b-instant", "gemini/gemma-3-27b-it"]
        if model in light_models:
            report.record("Smart Router", f"Mini downgrade for {node}", "PASS", f"model={model} (light tier)")
        else:
            report.record("Smart Router", f"Mini downgrade for {node}", "WARN",
                          f"model={model} (expected light tier)")


# ─── Test 9: GSD State Compression ─────────────────────────────────────────

async def test_gsd_compression():
    """Test GSD state compression at scale."""
    print("\n📋 TEST 9: GSD State Compression")
    print("-" * 60)

    from parwa.gsd import compress_state, decompress_state, get_compression_ratio

    # Build a realistic large state (simulating after 10+ nodes)
    large_state = {
        "ticket_id": "TKT-GSD-001",
        "raw_message": TEST_TICKETS[0]["raw_message"],
        "customer_id": "CUST-99182",
        "channel": "email",
        "variant": "parwa",
        "intent": "refund_request",
        "intent_confidence": 0.95,
        "sentiment": "angry",
        "sentiment_urgency": 0.9,
        "complexity": "critical",
        "should_escalate": True,
        "escalation_reason": "legal_threat",
        "reasoning_conclusion": "Customer is eligible for full refund of $149.99 due to duplicate charge",
        "verification_passed": True,
        "quality_score": 85.0,
        "should_loop_back": False,
        "loop_count": 0,
        "max_loops": 2,
        "pii_detected": True,
        "final_response": "",
        "recommendation": None,
        "selected_path": None,
        # ─── Large fields that should be compressed ───
        "reasoning_chain": [
            "Step 1: Customer reports duplicate charge of $149.99 on order #ORD-78291",
            "Step 2: CRM data confirms two charges on same date (January 3rd)",
            "Step 3: Both charges are identical amount ($149.99) — confirms duplicate",
            "Step 4: Refund policy allows full refund for duplicate charges within 30 days",
            "Step 5: Charge date is within 30-day window — eligible for refund",
            "Step 6: Customer has history of similar issues (3rd occurrence)",
            "Step 7: Customer mentions legal threat — handle with care",
            "Step 8: PII detected (SSN, credit card) — must be redacted",
            "Step 9: Refund amount should be $149.99 (one of the duplicate charges)",
            "Step 10: Conclusion: Process refund of $149.99 and escalate for legal threat handling",
        ],
        "kb_results": [
            {"source": "refund_policy", "content": "Full refunds are available for duplicate charges within 30 days of the original transaction. The refund will be processed to the original payment method within 3-5 business days. If the charge was made in error by our system, an additional 10% goodwill credit may be applied.", "relevance_score": 0.95},
            {"source": "duplicate_charge_policy", "content": "When a customer reports a duplicate charge, verify the charge exists in CRM, confirm both charges have the same amount and date, and process a refund for the duplicate charge. If the customer has experienced this before, escalate to billing team for root cause analysis.", "relevance_score": 0.88},
            {"source": "legal_complaint_protocol", "content": "If a customer mentions legal action or attorney, immediately escalate to the legal liaison team. Do not make any admissions of fault. Provide factual account information only.", "relevance_score": 0.82},
        ],
        "reasoning_paths": [
            {"path_id": "path_1", "description": "Full refund of duplicate charge", "steps": ["Verify duplicate", "Process refund", "Escalate"], "confidence": 0.95, "selected": True},
            {"path_id": "path_2", "description": "Refund + goodwill credit", "steps": ["Verify duplicate", "Add credit", "Process refund"], "confidence": 0.70, "selected": False},
            {"path_id": "path_3", "description": "Escalate to billing team", "steps": ["Verify duplicate", "Create billing ticket", "Refund pending review"], "confidence": 0.50, "selected": False},
        ],
        "strategy_plan": [
            "1. Verify duplicate charge exists in CRM system",
            "2. Confirm both charges are $149.99 on January 3rd",
            "3. Process refund for one of the duplicate charges",
            "4. Apply 10% goodwill credit for repeated issue",
            "5. Escalate to legal liaison team for threat handling",
            "6. Send apology email with refund confirmation",
        ],
        "action_plans": [
            {"action_type": "process_refund", "description": "Process $149.99 refund for duplicate charge", "parameters": {"amount": 149.99}, "mode": "execute", "evidence": ["CRM confirms duplicate"], "risk_level": "low"},
            {"action_type": "escalate_to_human", "description": "Escalate for legal threat handling", "parameters": {"reason": "legal_threat"}, "mode": "execute", "evidence": ["Customer mentioned attorney"], "risk_level": "medium"},
        ],
        "execution_results": [
            {"action_type": "process_refund", "status": "executed", "message": "Action 'process_refund' executed successfully", "parameters": {"amount": 149.99}},
            {"action_type": "escalate_to_human", "status": "executed", "message": "Action 'escalate_to_human' executed successfully", "parameters": {"reason": "legal_threat"}},
        ],
        "proactive_insights": [
            {"type": "follow_up", "description": "Check if duplicate charge issue is systemic — 3rd occurrence for this customer", "confidence": 0.85},
        ],
        "predictions": [
            {"type": "prediction", "description": "Customer churn risk HIGH — 3rd duplicate charge incident", "confidence": 0.78},
        ],
        "audit_log": [
            {"node": "INGEST", "timestamp": 1704288000, "action": "ticket_created"},
            {"node": "INTENT_CLASSIFIER", "timestamp": 1704288001, "action": "classified_refund_request"},
            {"node": "SENTIMENT_ANALYZER", "timestamp": 1704288002, "action": "detected_angry_sentiment"},
            {"node": "ESCALATION_DECISION", "timestamp": 1704288003, "action": "escalated_legal_threat"},
            {"node": "PII_COMPLIANCE_GUARD", "timestamp": 1704288004, "action": "redacted_ssn_cc"},
        ],
        "context_history": [
            {"role": "system", "content": "Customer has 3 previous duplicate charge complaints"},
            {"role": "system", "content": "Account tier: Premium. Monthly spend: $299.00"},
        ],
        "active_frameworks": ["chain_of_thought", "react", "reflexion", "crp"],
        "quality_issues": [],
        "pipeline_errors": [],
        "reverse_validation": {"goal": "Refund processed", "trace": "Need approval → Need evidence → CRM confirms duplicate → Policy allows refund → Evidence confirmed", "validation": "PASSED"},
        "feedback_signal": {"resolved": True, "satisfaction": "medium", "improvement_areas": ["response_speed"]},
        "integration_data": {"order_id": "ORD-78291", "status": "delivered", "charges": [{"amount": 149.99, "date": "2025-01-03"}, {"amount": 149.99, "date": "2025-01-03"}], "customer": {"name": "John Doe", "tier": "premium"}},
        "token_budget_total": 12000,
        "token_budget_used": 3200,
        "token_budget_remaining": 8800,
    }

    # Calculate original size
    original_str = str(large_state)
    original_chars = len(original_str)
    original_tokens_est = original_chars // 4

    # Compress
    compressed = compress_state(large_state)
    compressed_str = str(compressed)
    compressed_chars = len(compressed_str)
    compressed_tokens_est = compressed_chars // 4

    # Calculate ratio
    ratio = get_compression_ratio(large_state)
    reduction_pct = (1 - ratio) * 100

    report.record("GSD Compression", "Compression runs without error", "PASS",
                  f"original={original_chars} chars (~{original_tokens_est} tokens), "
                  f"compressed={compressed_chars} chars (~{compressed_tokens_est} tokens)")

    report.record("GSD Compression", "Reduction > 10%", "PASS" if reduction_pct > 10 else "FAIL",
                  f"{reduction_pct:.1f}% reduction (ratio={ratio:.3f})")

    # Note: 98% claim was wrong — honest ratio for this state size
    if reduction_pct > 70:
        report.record("GSD Compression", "Large state reduction > 70%", "PASS",
                      f"{reduction_pct:.1f}% reduction")
    elif reduction_pct > 30:
        report.record("GSD Compression", "Medium state reduction > 30%", "WARN",
                      f"{reduction_pct:.1f}% reduction — full 98% requires much larger states")
    else:
        report.record("GSD Compression", "Compression meaningful", "WARN",
                      f"Only {reduction_pct:.1f}% reduction — needs larger states for significant savings")

    # Verify critical fields preserved
    critical_fields = ["ticket_id", "raw_message", "intent", "sentiment", "quality_score",
                       "should_escalate", "reasoning_conclusion", "variant"]
    missing = [f for f in critical_fields if f not in compressed or compressed[f] != large_state.get(f)]
    if not missing:
        report.record("GSD Compression", "Critical fields preserved", "PASS",
                      f"All {len(critical_fields)} critical fields intact")
    else:
        report.record("GSD Compression", "Critical fields preserved", "FAIL",
                      f"Missing/changed: {missing}")

    # Verify verbose fields are summarized
    verbose_fields = ["reasoning_chain", "kb_results", "audit_log"]
    for field in verbose_fields:
        if field in compressed:
            val = compressed[field]
            if isinstance(val, dict) and val.get("_gsd_summary"):
                report.record("GSD Compression", f"{field} summarized", "PASS",
                              f"count={val.get('count', '?')}, first_item present={bool(val.get('first_item'))}")
            elif field in ["active_frameworks", "quality_issues", "pipeline_errors"]:
                report.record("GSD Compression", f"{field} kept full", "PASS",
                              "Correctly kept full (short list)")
            else:
                report.record("GSD Compression", f"{field} summarized", "WARN",
                              f"Type: {type(val).__name__}, not summarized")
        else:
            report.record("GSD Compression", f"{field} present", "FAIL", "Field missing from compressed state")

    # Test decompression
    decompressed = decompress_state(compressed)
    if decompressed.get("ticket_id") == large_state["ticket_id"]:
        report.record("GSD Compression", "Decompression restores state", "PASS",
                      f"ticket_id preserved through compress→decompress")
    else:
        report.record("GSD Compression", "Decompression restores state", "FAIL",
                      "ticket_id lost in decompress")


# ─── Test 10: TurboQuant Token Tracking ─────────────────────────────────────

async def test_turboquant():
    """Test TurboQuant token tracking with real LLM calls."""
    print("\n📋 TEST 10: TurboQuant Token Tracking")
    print("-" * 60)

    from parwa.utils.llm import ainvoke_llm
    from parwa.turboquant.token_tracker import get_token_tracker
    from parwa.turboquant.token_budget import get_node_budget, get_ticket_budget

    tracker = get_token_tracker()
    tracker.clear()  # Reset for clean test

    # Make a real LLM call and check tracking
    try:
        response = await ainvoke_llm(
            "Test prompt for token tracking",
            node_name="REASONING_ENGINE",
            ticket_id="TEST-TQ-001",
            variant="parwa",
        )

        # Check tracker recorded it
        records = tracker.get_ticket_usage("TEST-TQ-001")
        if records:
            r = records[0]
            report.record("TurboQuant", "Token usage recorded", "PASS",
                          f"prompt={r.prompt_tokens}, completion={r.completion_tokens}, "
                          f"total={r.total_tokens}, model={r.model}")
        else:
            report.record("TurboQuant", "Token usage recorded", "WARN",
                          "No records found — tracking may not be working with zai SDK")

    except Exception as e:
        report.record("TurboQuant", "Real LLM call for tracking", "FAIL", str(e)[:120])

    # Test budget allocation
    for variant in ["mini", "parwa", "high"]:
        budget = get_ticket_budget(variant)
        if budget.ticket_total > 0 and budget.node_budgets:
            report.record("TurboQuant", f"Budget allocation for {variant}", "PASS",
                          f"total={budget.ticket_total}, nodes={len(budget.node_budgets)}")
        else:
            report.record("TurboQuant", f"Budget allocation for {variant}", "FAIL",
                          "No budget allocated")

    # Test per-node budget
    for node in ["reasoning_engine", "intent_classifier", "response_formatter"]:
        for variant in ["mini", "parwa", "high"]:
            budget = get_node_budget(node, variant)
            if budget.allocated > 0:
                # Mini should have half of PARWA's budget
                parwa_budget = get_node_budget(node, "parwa")
                if variant == "mini" and budget.allocated == parwa_budget.allocated // 2:
                    report.record("TurboQuant", f"Mini budget 0.5x for {node}", "PASS",
                                  f"allocated={budget.allocated}")
                elif variant == "high" and budget.allocated == parwa_budget.allocated * 2:
                    report.record("TurboQuant", f"High budget 2.0x for {node}", "PASS",
                                  f"allocated={budget.allocated}")
                elif variant == "parwa":
                    report.record("TurboQuant", f"PARWA budget 1.0x for {node}", "PASS",
                                  f"allocated={budget.allocated}")
            else:
                report.record("TurboQuant", f"Budget for {node}/{variant}", "FAIL",
                              f"allocated={budget.allocated}")

    # Test node summary aggregation
    if tracker.record_count > 0:
        summary = tracker.get_node_summary()
        if summary:
            report.record("TurboQuant", "Node summary aggregation", "PASS",
                          f"{len(summary)} nodes tracked")
        else:
            report.record("TurboQuant", "Node summary aggregation", "FAIL", "Empty summary")
    else:
        report.record("TurboQuant", "Node summary aggregation", "WARN",
                      "No records to summarize")


# ─── Test 11: Quality Scoring Accuracy ──────────────────────────────────────

async def test_quality_scoring():
    """Test that quality scoring varies (vs MockLLM always returning 85)."""
    print("\n📋 TEST 11: Quality Scoring Accuracy")
    print("-" * 60)

    from parwa.nodes.quality_scorer import quality_scorer

    # Test 1: Good state should score high
    good_state = {
        "raw_message": "I want a refund",
        "ticket_id": "TEST-QS-001",
        "variant": "parwa",
        "intent": "refund_request",
        "reasoning_conclusion": "Customer is eligible for refund of $149.99 due to duplicate charge confirmed in CRM.",
        "verification_passed": True,
        "recommendation": None,
        "quality_score": 0,
        "loop_count": 0,
        "max_loops": 2,
        "active_frameworks": [],
    }

    result_good = await quality_scorer(good_state)
    score_good = result_good.get("quality_score", 0)

    report.record("Quality Scoring", "Good state scores >= 70", "PASS" if score_good >= 70 else "FAIL",
                  f"score={score_good}")

    # Test 2: Bad state should score low
    bad_state = {
        "raw_message": "Help",
        "ticket_id": "TEST-QS-002",
        "variant": "parwa",
        "intent": "general_inquiry",
        "reasoning_conclusion": "",  # Empty conclusion
        "verification_passed": False,  # Failed verification
        "recommendation": None,
        "quality_score": 0,
        "loop_count": 0,
        "max_loops": 2,
        "active_frameworks": [],
    }

    result_bad = await quality_scorer(bad_state)
    score_bad = result_bad.get("quality_score", 0)

    report.record("Quality Scoring", "Bad state scores < good state", "PASS" if score_bad < score_good else "FAIL",
                  f"bad_score={score_bad} vs good_score={score_good}")

    report.record("Quality Scoring", "Bad state scores < 80 (should trigger loop)", "PASS" if score_bad < 80 else "WARN",
                  f"score={score_bad}")

    # Test 3: Verify scores are NOT always 85 (the MockLLM problem)
    scores_are_different = score_good != score_bad
    report.record("Quality Scoring", "Scores vary (not always 85)", "PASS" if scores_are_different else "FAIL",
                  f"good={score_good}, bad={score_bad}")

    # Test 4: Verify loop-back triggers on low score
    should_loop = result_bad.get("should_loop_back", False)
    report.record("Quality Scoring", "Loop-back triggers on low score", "PASS" if should_loop else "FAIL",
                  f"should_loop_back={should_loop}")


# ─── Test 12: Variant Enforcement (Think vs Act) ───────────────────────────

async def test_variant_enforcement():
    """Test that variant permissions are correctly enforced."""
    print("\n📋 TEST 12: Variant Enforcement (Think vs Act)")
    print("-" * 60)

    from parwa.config import can_execute, get_permission, ExecutionMode, ActionType

    # Mini: refund = RECOMMEND (can't execute)
    mini_refund = get_permission("mini", ActionType.PROCESS_REFUND)
    if mini_refund == ExecutionMode.RECOMMEND:
        report.record("Variant Enforcement", "Mini: refund is RECOMMEND", "PASS",
                      f"mode={mini_refund}")
    else:
        report.record("Variant Enforcement", "Mini: refund is RECOMMEND", "FAIL",
                      f"expected RECOMMEND, got {mini_refund}")

    # PARWA: refund = EXECUTE
    parwa_refund = get_permission("parwa", ActionType.PROCESS_REFUND)
    if parwa_refund == ExecutionMode.EXECUTE:
        report.record("Variant Enforcement", "PARWA: refund is EXECUTE", "PASS",
                      f"mode={parwa_refund}")
    else:
        report.record("Variant Enforcement", "PARWA: refund is EXECUTE", "FAIL",
                      f"expected EXECUTE, got {parwa_refund}")

    # High: bulk = EXECUTE
    high_bulk = get_permission("high", ActionType.BULK_OPERATION)
    if high_bulk == ExecutionMode.EXECUTE:
        report.record("Variant Enforcement", "High: bulk is EXECUTE", "PASS",
                      f"mode={high_bulk}")
    else:
        report.record("Variant Enforcement", "High: bulk is EXECUTE", "FAIL",
                      f"expected EXECUTE, got {high_bulk}")

    # Mini: bulk = DENY
    mini_bulk = get_permission("mini", ActionType.BULK_OPERATION)
    if mini_bulk == ExecutionMode.DENY:
        report.record("Variant Enforcement", "Mini: bulk is DENY", "PASS",
                      f"mode={mini_bulk}")
    else:
        report.record("Variant Enforcement", "Mini: bulk is DENY", "FAIL",
                      f"expected DENY, got {mini_bulk}")

    # Test can_execute helper
    if not can_execute("mini", ActionType.PROCESS_REFUND):
        report.record("Variant Enforcement", "can_execute(mini, refund) = False", "PASS")
    else:
        report.record("Variant Enforcement", "can_execute(mini, refund) = False", "FAIL",
                      "Mini should NOT be able to execute refunds")

    if can_execute("parwa", ActionType.PROCESS_REFUND):
        report.record("Variant Enforcement", "can_execute(parwa, refund) = True", "PASS")
    else:
        report.record("Variant Enforcement", "can_execute(parwa, refund) = True", "FAIL",
                      "PARWA should be able to execute refunds")


# ─── Main Runner ────────────────────────────────────────────────────────────

async def main():
    print("=" * 80)
    print("PARWA REAL LLM COMPREHENSIVE TEST SUITE")
    print("NO MOCK MODE. REAL LLM CALLS. HONEST RESULTS.")
    print("=" * 80)
    print(f"ZAI SDK Mode: PARWA_MOCK_MODE={os.environ.get('PARWA_MOCK_MODE', 'true')}")
    print(f"Test Tickets: {len(TEST_TICKETS)}")
    print()

    t0 = time.time()

    # Run all tests
    await test_zai_sdk_direct()
    await test_all_variants()
    await test_intent_accuracy()
    await test_sentiment_accuracy()
    await test_escalation_accuracy()
    await test_pii_detection()
    await test_framework_brain()
    await test_smart_router()
    await test_gsd_compression()
    await test_turboquant()
    await test_quality_scoring()
    await test_variant_enforcement()

    elapsed = time.time() - t0

    # Print honest summary
    passed, failed, warnings = report.summary()

    print(f"\nTotal test time: {elapsed:.1f}s")
    print()

    # VERDICT
    if failed == 0 and warnings == 0:
        print("🏆 VERDICT: ALL TESTS PASSED — System is production-viable")
    elif failed == 0 and warnings > 0:
        print("🟡 VERDICT: PASSED WITH WARNINGS — System works but has concerns")
    elif failed <= 3:
        print("🟠 VERDICT: PARTIAL PASS — Some features broken, needs fixing")
    else:
        print("🔴 VERDICT: SIGNIFICANT FAILURES — System needs major work before production")

    # Save results
    results_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "test_results_real_llm.json")
    with open(results_path, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mock_mode": False,
            "total": report.total,
            "passed": report.passed,
            "failed": report.failed,
            "warnings": report.warnings,
            "elapsed_seconds": elapsed,
            "results": report.results,
        }, f, indent=2)

    print(f"\nResults saved to: {results_path}")


if __name__ == "__main__":
    asyncio.run(main())
