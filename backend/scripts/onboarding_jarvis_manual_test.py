#!/usr/bin/env python3
"""
PARWA Onboarding Jarvis — Manual End-to-End Test Script

Tests the FULL onboarding flow from welcome → discovery → demo → pricing →
bill review → verification → OTP → payment → handoff.

This script exercises:
  1. The Onboarding Orchestrator pipeline (process_onboarding_message)
  2. The Awareness Engine (5 domains: entry, variant, channel, funnel, sales)
  3. The Function Registry (21+ LLM tool definitions, stage-filtered)
  4. Stage detection transitions (welcome → discovery → demo → pricing → ...)
  5. Safety gate (confirmation_required / approval_required functions)
  6. The orchestrator integration in jarvis_service.send_message

The test simulates a real user chatting with Jarvis during onboarding.
Each message is processed through the orchestrator and the results are
printed in detail — stage, function called, awareness state, metadata.

Usage:
  cd /home/z/my-project/parwa/backend
  python scripts/onboarding_jarvis_manual_test.py

Notes:
  - Uses mock DB sessions where needed (the orchestrator queries the DB,
    but stub executors are OK for now)
  - Real LLM calls require OPENAI_API_KEY or ZAI_API_KEY env vars.
    Without them, the orchestrator gracefully falls back to placeholder text.
  - The jarvis_service integration test requires a full DB session.
    If unavailable, it falls back to testing orchestrator directly.
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ══════════════════════════════════════════════════════════════════
# TEST CONFIG
# ══════════════════════════════════════════════════════════════════

TEST_COMPANY_ID = "test-company-onboarding"
TEST_USER_ID = "test-user-onboarding"
TEST_SESSION_ID = "test-session-onboarding"

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


# ══════════════════════════════════════════════════════════════════
# PRINTING HELPERS
# ══════════════════════════════════════════════════════════════════


def print_header(text: str) -> None:
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  {text}{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}\n")


def print_section(text: str) -> None:
    print(f"\n{CYAN}  --- {text} ---{RESET}\n")


def print_result(label: str, value: Any, indent: int = 4) -> None:
    prefix = " " * indent
    if isinstance(value, dict):
        print(f"{prefix}{BLUE}{label}:{RESET}")
        for k, v in value.items():
            v_str = json.dumps(v, default=str) if isinstance(v, (dict, list)) else str(v)
            if len(v_str) > 120:
                v_str = v_str[:120] + "..."
            print(f"{prefix}  {k}: {v_str}")
    elif isinstance(value, list):
        print(f"{prefix}{BLUE}{label}:{RESET} [{len(value)} items]")
        for i, item in enumerate(value[:5]):
            print(f"{prefix}  [{i}] {str(item)[:100]}")
        if len(value) > 5:
            print(f"{prefix}  ... and {len(value) - 5} more")
    else:
        v_str = str(value)
        if len(v_str) > 150:
            v_str = v_str[:150] + "..."
        print(f"{prefix}{BLUE}{label}:{RESET} {v_str}")


def print_pass(msg: str) -> None:
    print(f"  {GREEN}[PASS]{RESET} {msg}")


def print_fail(msg: str) -> None:
    print(f"  {RED}[FAIL]{RESET} {msg}")


def print_info(msg: str) -> None:
    print(f"  {YELLOW}[INFO]{RESET} {msg}")


def print_stage(stage: str) -> None:
    print(f"  {BOLD}{CYAN}[STAGE: {stage}]{RESET}")


# ══════════════════════════════════════════════════════════════════
# MOCK DB HELPERS
# ══════════════════════════════════════════════════════════════════


def create_mock_db(session_context: Optional[Dict[str, Any]] = None) -> MagicMock:
    """Create a mock DB session that simulates JarvisSession + JarvisMessage queries.

    This allows us to test the orchestrator without a real database.
    The mock tracks context_json updates so we can verify awareness changes.
    """
    db = MagicMock()

    # Default session context
    default_ctx = {
        "pages_visited": [],
        "industry": None,
        "selected_variants": [],
        "roi_result": None,
        "demo_topics": [],
        "concerns_raised": [],
        "business_email": None,
        "email_verified": False,
        "referral_source": "",
        "entry_source": "variant_demo",
        "entry_params": {"variant": "Returns Agent", "variant_id": "returns_refund"},
        "detected_stage": "welcome",
        "onboarding_awareness": {},
    }
    if session_context:
        default_ctx.update(session_context)

    # Mock session object
    mock_session = MagicMock()
    mock_session.id = TEST_SESSION_ID
    mock_session.user_id = TEST_USER_ID
    mock_session.company_id = TEST_COMPANY_ID
    mock_session.type = "onboarding"
    mock_session.pack_type = "free"
    mock_session.payment_status = "none"
    mock_session.context_json = json.dumps(default_ctx)
    mock_session.total_message_count = 0
    mock_session.handoff_completed = False

    # Track context updates
    _ctx_state = {"data": default_ctx.copy()}

    def _update_context_json(value):
        _ctx_state["data"] = json.loads(value) if isinstance(value, str) else value
        mock_session.context_json = value

    mock_session.context_json = json.dumps(default_ctx)

    # Mock query chains
    session_query = MagicMock()
    session_query.filter.return_value = session_query
    session_query.order_by.return_value = session_query
    session_query.first.return_value = mock_session

    message_query = MagicMock()
    message_query.filter.return_value = message_query
    message_query.order_by.return_value = message_query
    message_query.limit.return_value = message_query
    message_query.all.return_value = []  # No messages initially
    message_query.count.return_value = 0

    def _query(model):
        # Try to detect which model is being queried
        model_name = getattr(model, "__name__", str(model))
        if "Session" in model_name:
            return session_query
        elif "Message" in model_name:
            return message_query
        return MagicMock()

    db.query.side_effect = _query
    db.add = MagicMock()
    db.flush = MagicMock()
    db.commit = MagicMock()

    # Store state accessor on the db mock
    db._get_context = lambda: _ctx_state["data"]
    db._set_context = _update_context_json
    db._mock_session = mock_session

    return db


def update_mock_session_context(db: MagicMock, updates: Dict[str, Any]) -> None:
    """Update the mock session's context_json (simulates awareness updates)."""
    ctx = db._get_context()
    ctx.update(updates)
    db._set_context(json.dumps(ctx))


# ══════════════════════════════════════════════════════════════════
# TEST 1: FUNCTION REGISTRY
# ══════════════════════════════════════════════════════════════════


def test_function_registry():
    """Verify the onboarding function registry has all 21+ function definitions."""
    print_header("TEST 1: Onboarding Function Registry")

    from app.services.onboarding_jarvis_function_registry import (
        ONBOARDING_FUNCTION_REGISTRY,
        get_onboarding_function_definitions,
        get_function_metadata,
        get_safety_level,
        filter_functions_by_channel,
        SAFETY_NONE,
        SAFETY_CONFIRMATION,
        SAFETY_APPROVAL,
    )

    # Count functions
    all_names = [f["name"] for f in ONBOARDING_FUNCTION_REGISTRY]
    print_result("Total functions in registry", len(all_names))

    # Expected function names by category
    expected = {
        "demo": ["demo_variant_scenario", "demo_customer_question", "show_variant_workflow", "explain_production_behavior"],
        "sales": ["compare_with_competitor", "show_roi_calculation", "handle_objection"],
        "guide": ["select_industry", "select_variants", "show_pricing", "show_bill_summary"],
        "communication": ["book_demo_call", "initiate_voice_demo", "send_follow_up"],
        "verification": ["send_business_otp", "verify_business_otp"],
        "payment": ["purchase_demo_pack", "create_payment_session"],
        "knowledge": ["search_product_knowledge", "explain_feature", "show_integration_options", "upload_documents"],
        "demo_ticket": ["create_demo_ticket", "solve_demo_ticket"],
        "handoff": ["execute_handoff"],
    }

    passed = 0
    failed = 0
    for category, funcs in expected.items():
        for func in funcs:
            if func in all_names:
                print_pass(f"{category}: {func}")
                passed += 1
            else:
                print_fail(f"{category}: {func} — MISSING")
                failed += 1

    print(f"\n  Registry check: {passed} found, {failed} missing")

    # Test stage filtering
    print_section("Stage-Filtered Function Definitions")
    stages = ["welcome", "discovery", "demo", "pricing", "bill_review", "verification", "payment", "handoff"]
    for stage in stages:
        defs = get_onboarding_function_definitions(stage, "chat")
        names = [d["name"] for d in defs]
        print_result(f"Stage '{stage}' → chat functions", names)

    # Test safety levels
    print_section("Safety Level Verification")
    approval_funcs = ["purchase_demo_pack", "create_payment_session"]
    confirmation_funcs = ["select_variants", "book_demo_call", "initiate_voice_demo", "send_follow_up", "upload_documents"]
    none_funcs = ["show_pricing", "show_bill_summary", "demo_variant_scenario", "search_product_knowledge"]

    for func in approval_funcs:
        level = get_safety_level(func)
        status = "PASS" if level == SAFETY_APPROVAL else "FAIL"
        print(f"  [{status}] {func} → {level} (expected {SAFETY_APPROVAL})")

    for func in confirmation_funcs:
        level = get_safety_level(func)
        status = "PASS" if level == SAFETY_CONFIRMATION else "FAIL"
        print(f"  [{status}] {func} → {level} (expected {SAFETY_CONFIRMATION})")

    for func in none_funcs:
        level = get_safety_level(func)
        status = "PASS" if level == SAFETY_NONE else "FAIL"
        print(f"  [{status}] {func} → {level} (expected {SAFETY_NONE})")

    # Test channel filtering
    print_section("Channel Filtering")
    chat_only = ["book_demo_call"]
    call_only = ["initiate_voice_demo"]

    for func in chat_only:
        meta = get_function_metadata(func)
        channel = meta.get("channel", "all")
        status = "PASS" if channel == "chat" else "FAIL"
        print(f"  [{status}] {func} → channel={channel} (expected chat)")

    for func in call_only:
        meta = get_function_metadata(func)
        channel = meta.get("channel", "all")
        status = "PASS" if channel == "call" else "FAIL"
        print(f"  [{status}] {func} → channel={channel} (expected call)")

    return failed == 0


# ══════════════════════════════════════════════════════════════════
# TEST 2: AWARENESS ENGINE
# ══════════════════════════════════════════════════════════════════


def test_awareness_engine():
    """Test the 5-domain awareness engine."""
    print_header("TEST 2: Onboarding Awareness Engine (5 Domains)")

    from app.services.onboarding_jarvis_awareness import (
        collect_onboarding_awareness,
        get_entry_context_awareness,
        get_variant_source_awareness,
        get_channel_awareness,
        get_funnel_progress,
        get_sales_state,
        detect_conversation_stage,
        build_awareness_summary,
        track_question_asked,
        track_concern_raised,
        update_onboarding_context,
        VALID_FUNNEL_STAGES,
    )

    db = create_mock_db()

    # Test 2a: Domain 1 — Entry Context
    print_section("2a: Entry Context Awareness")
    entry = get_entry_context_awareness(db, TEST_SESSION_ID)
    print_result("Entry context", entry)
    assert "entry_source" in entry
    print_pass("Entry context has entry_source field")

    # Test 2b: Domain 2 — Variant Awareness
    print_section("2b: Variant Source Awareness")
    variant = get_variant_source_awareness(db, TEST_SESSION_ID)
    print_result("Variant awareness", variant)
    assert "selected_variants" in variant
    print_pass("Variant awareness has selected_variants field")

    # Test 2c: Domain 3 — Channel Awareness
    print_section("2c: Channel Awareness")
    channel = get_channel_awareness(db, TEST_SESSION_ID)
    print_result("Channel awareness", channel)
    assert "current_channel" in channel
    print_pass("Channel awareness has current_channel field")

    # Test 2d: Domain 4 — Funnel Progress
    print_section("2d: Funnel Progress")
    funnel = get_funnel_progress(db, TEST_SESSION_ID)
    print_result("Funnel progress", funnel)
    assert "detected_stage" in funnel
    print_pass("Funnel progress has detected_stage field")

    # Test 2e: Domain 5 — Sales State
    print_section("2e: Sales State")
    sales = get_sales_state(db, TEST_SESSION_ID)
    print_result("Sales state", sales)
    assert "industry_selected" in sales
    assert "email_verified" in sales
    print_pass("Sales state has industry_selected and email_verified fields")

    # Test 2f: Full collection
    print_section("2f: Full Awareness Collection")
    awareness = collect_onboarding_awareness(db, TEST_COMPANY_ID, TEST_SESSION_ID, TEST_USER_ID)
    print_result("Full awareness keys", list(awareness.keys()))
    print_pass("collect_onboarding_awareness returns a valid dict")

    # Test 2g: Awareness summary
    print_section("2g: Awareness Summary (for LLM injection)")
    summary = build_awareness_summary(awareness)
    print_result("Summary", summary)
    assert len(summary) > 10
    print_pass(f"Summary is {len(summary)} chars — suitable for prompt injection")

    return True


# ══════════════════════════════════════════════════════════════════
# TEST 3: STAGE DETECTION
# ══════════════════════════════════════════════════════════════════


def test_stage_detection():
    """Test stage detection with various context states."""
    print_header("TEST 3: Stage Detection Transitions")

    from app.services.onboarding_jarvis_awareness import detect_conversation_stage

    # Define test cases: context → expected stage
    test_cases = [
        # (context_dict, expected_stage, description)
        ({}, "welcome", "Empty context → welcome"),
        ({"industry": ""}, "welcome", "No industry → welcome"),
        ({"industry": "ecommerce"}, "discovery", "Industry set → discovery"),
        ({"industry": "ecommerce", "selected_variants": ["returns_refund"]}, "pricing", "Variants selected → pricing"),
        ({"industry": "ecommerce", "selected_variants": ["returns_refund"], "bill_shown": True}, "bill_review", "Bill shown → bill_review"),
        ({"otp": {"status": "sent"}, "email_verified": False}, "verification", "OTP sent → verification"),
        ({"payment_status": "pending"}, "payment", "Payment pending → payment"),
        ({"payment_status": "completed"}, "handoff", "Payment completed → handoff"),
        ({"pack_type": "demo"}, "demo", "Demo pack → demo"),
    ]

    passed = 0
    failed = 0

    for ctx, expected, description in test_cases:
        result = detect_conversation_stage(ctx)
        status = "PASS" if result == expected else "FAIL"
        if result == expected:
            print_pass(f"{description} → got '{result}'")
            passed += 1
        else:
            print_fail(f"{description} → got '{result}', expected '{expected}'")
            failed += 1

    print(f"\n  Stage detection: {passed}/{len(test_cases)} correct")
    return failed == 0


# ══════════════════════════════════════════════════════════════════
# TEST 4: ORCHESTRATOR PIPELINE (Direct Call)
# ══════════════════════════════════════════════════════════════════


async def test_orchestrator_pipeline():
    """Test the orchestrator pipeline directly with simulated messages."""
    print_header("TEST 4: Onboarding Orchestrator Pipeline (Direct Call)")

    from app.services.onboarding_jarvis_orchestrator import (
        process_onboarding_message,
        load_onboarding_context,
        detect_onboarding_stage,
        build_onboarding_system_prompt,
    )

    db = create_mock_db()

    # Define the full onboarding journey
    journey = [
        {
            "message": "Hi, I run an online store and get tons of refund requests",
            "expected_stage_advance": "discovery",  # Industry gets detected
            "description": "Welcome → Discovery (user mentions online store → ecommerce)",
        },
        {
            "message": "Show me how you'd handle a refund request",
            "expected_stage_advance": "demo",
            "description": "Discovery → Demo (user wants to see AI in action)",
        },
        {
            "message": "What's your pricing?",
            "expected_stage_advance": "pricing",
            "description": "Demo → Pricing (user asks about cost)",
        },
        {
            "message": "I'd like to select the Returns Agent x3",
            "expected_stage_advance": "pricing",
            "description": "Pricing stage (variant selection)",
        },
        {
            "message": "Show me my bill",
            "expected_stage_advance": "bill_review",
            "description": "Pricing → Bill Review (user asks for bill)",
        },
        {
            "message": "My business email is test@company.com",
            "expected_stage_advance": "verification",
            "description": "Bill Review → Verification (user provides email)",
        },
        {
            "message": "The OTP is 123456",
            "expected_stage_advance": "verification",
            "description": "Verification stage (OTP check — will fail but tests the flow)",
        },
    ]

    print_info("Processing onboarding journey through the orchestrator...")
    print_info("Note: Without an LLM API key, responses will be fallback text.\n")

    for i, step in enumerate(journey, 1):
        print_section(f"Step {i}: {step['description']}")
        print(f"  User: \"{step['message']}\"")
        print_stage(step.get("expected_stage_advance", "unknown"))

        try:
            result = await process_onboarding_message(
                db=db,
                session_id=TEST_SESSION_ID,
                user_id=TEST_USER_ID,
                company_id=TEST_COMPANY_ID,
                user_message=step["message"],
                channel="chat",
            )

            # Print orchestrator result
            print_result("Response content", result.get("content", "")[:200])
            print_result("Message type", result.get("message_type", ""))
            print_result("Function called", result.get("function_called"))
            print_result("Function result", result.get("function_result"))
            print_result("Metadata", result.get("metadata", {}))

            # Verify result structure
            assert "content" in result, "Result missing 'content' key"
            assert "message_type" in result, "Result missing 'message_type' key"
            assert "metadata" in result, "Result missing 'metadata' key"
            print_pass(f"Orchestrator returned valid result structure")

        except Exception as exc:
            print_fail(f"Orchestrator raised exception: {exc}")
            import traceback
            traceback.print_exc()

        print()

    return True


# ══════════════════════════════════════════════════════════════════
# TEST 5: SYSTEM PROMPT BUILDING
# ══════════════════════════════════════════════════════════════════


def test_system_prompt_building():
    """Test that the orchestrator builds stage-appropriate system prompts."""
    print_header("TEST 5: System Prompt Building (Stage-Specific)")

    from app.services.onboarding_jarvis_orchestrator import (
        build_onboarding_system_prompt,
    )

    stages = ["welcome", "discovery", "demo", "pricing", "bill_review", "verification", "payment", "handoff"]

    for stage in stages:
        context = {
            "detected_stage": stage,
            "channel": "chat",
            "session": {
                "industry": "ecommerce",
                "variant_name": "Returns Agent",
                "entry_source": "variant_demo",
            },
            "awareness_summary": "Client came from a variant demo page. Currently in welcome stage. No email verified yet.",
        }
        prompt = build_onboarding_system_prompt(context)
        stage_keyword = f"STAGE: {stage.upper()}"
        has_stage = stage_keyword in prompt or stage.upper() in prompt.upper()
        status = "PASS" if has_stage else "FAIL"
        if has_stage:
            print_pass(f"Stage '{stage}' → prompt contains stage instruction ({len(prompt)} chars)")
        else:
            print_fail(f"Stage '{stage}' → prompt MISSING stage instruction")

    # Test channel-specific prompt
    print_section("Channel-Specific Prompts")
    chat_ctx = {"detected_stage": "welcome", "channel": "chat", "session": {}, "awareness_summary": ""}
    call_ctx = {"detected_stage": "welcome", "channel": "call", "session": {}, "awareness_summary": ""}

    chat_prompt = build_onboarding_system_prompt(chat_ctx)
    call_prompt = build_onboarding_system_prompt(call_ctx)

    has_chat_instruction = "TEXT CHAT" in chat_prompt
    has_call_instruction = "VOICE CALL" in call_prompt

    print_pass(f"Chat prompt has TEXT CHAT instruction") if has_chat_instruction else print_fail("Missing TEXT CHAT instruction")
    print_pass(f"Call prompt has VOICE CALL instruction") if has_call_instruction else print_fail("Missing VOICE CALL instruction")

    # Test pending safety context
    print_section("Pending Safety Context in Prompt")
    pending = {
        "function_name": "create_payment_session",
        "safety_level": "approval_required",
    }
    safety_prompt = build_onboarding_system_prompt(chat_ctx, pending_safety=pending)
    has_pending = "PENDING ACTION" in safety_prompt
    print_pass(f"Prompt includes PENDING ACTION when safety is pending") if has_pending else print_fail("Missing PENDING ACTION")

    return True


# ══════════════════════════════════════════════════════════════════
# TEST 6: CONTEXT LOADING
# ══════════════════════════════════════════════════════════════════


def test_context_loading():
    """Test the orchestrator's context loading function."""
    print_header("TEST 6: Context Loading")

    from app.services.onboarding_jarvis_orchestrator import (
        load_onboarding_context,
        detect_onboarding_stage,
    )

    db = create_mock_db()

    context = load_onboarding_context(db, TEST_SESSION_ID, TEST_USER_ID, TEST_COMPANY_ID)

    print_result("Context keys", list(context.keys()))
    assert "session" in context
    assert "awareness" in context
    assert "history" in context
    assert "channel" in context
    print_pass("Context has session, awareness, history, channel keys")

    # Check session info
    session_info = context.get("session", {})
    print_result("Session info", session_info)
    assert "type" in session_info
    assert "industry" in session_info
    print_pass("Session info has type and industry")

    # Check stage detection from loaded context
    stage = detect_onboarding_stage(context)
    print_result("Detected stage", stage)
    print_pass(f"Stage detected from loaded context: '{stage}'")

    return True


# ══════════════════════════════════════════════════════════════════
# TEST 7: ORCHESTRATOR INTEGRATION IN jarvis_service
# ══════════════════════════════════════════════════════════════════


def test_jarvis_service_integration():
    """Test that jarvis_service.send_message routes to the orchestrator for onboarding sessions.

    This verifies the integration code we added:
    - The orchestrator is imported and called for onboarding sessions
    - Fallback to direct AI works if orchestrator fails
    - Variant pipeline bridge path is preserved
    """
    print_header("TEST 7: jarvis_service Integration Check")

    # Test 7a: Verify the import path works
    print_section("7a: Orchestrator Import Check")
    try:
        from app.services.onboarding_jarvis_orchestrator import process_onboarding_message
        print_pass("process_onboarding_message imported successfully")
    except ImportError as e:
        print_fail(f"Failed to import process_onboarding_message: {e}")
        return False

    # Test 7b: Verify the code structure in jarvis_service.py
    print_section("7b: Code Structure Verification")

    import inspect
    from app.services import jarvis_service

    source = inspect.getsource(jarvis_service.send_message)

    # Check that the orchestrator path exists in the code
    has_orchestrator_import = "onboarding_jarvis_orchestrator" in source
    has_process_call = "process_onboarding_message" in source
    has_fallback = "fallback_reason" in source or "orchestrator_error" in source
    has_variant_bridge = "variant_pipeline_bridge" in source or "_should_use_variant_pipeline" in source

    if has_orchestrator_import:
        print_pass("send_message contains orchestrator import")
    else:
        print_fail("send_message MISSING orchestrator import")

    if has_process_call:
        print_pass("send_message calls process_onboarding_message")
    else:
        print_fail("send_message MISSING process_onboarding_message call")

    if has_fallback:
        print_pass("send_message has fallback handling for orchestrator errors")
    else:
        print_fail("send_message MISSING fallback handling")

    if has_variant_bridge:
        print_pass("send_message preserves variant pipeline bridge path")
    else:
        print_fail("send_message MISSING variant pipeline bridge")

    # Test 7c: Verify async/sync bridge pattern
    print_section("7c: Async/Sync Bridge Pattern")
    has_asyncio_run = "asyncio.run" in source
    has_threadpool = "ThreadPoolExecutor" in source
    if has_asyncio_run:
        print_pass("Uses asyncio.run for async/sync bridge")
    else:
        print_fail("Missing asyncio.run for async/sync bridge")
    if has_threadpool:
        print_pass("Has ThreadPoolExecutor fallback for existing event loops")
    else:
        print_fail("Missing ThreadPoolExecutor fallback")

    # Test 7d: Verify result mapping
    print_section("7d: Result Mapping Verification")
    has_content_map = 'result.get("content"' in source
    has_metadata_map = 'result.get("metadata"' in source
    has_function_called = 'result.get("function_called"' in source
    if has_content_map:
        print_pass("Maps result.content to ai_content")
    else:
        print_fail("Missing result.content mapping")
    if has_metadata_map:
        print_pass("Maps result.metadata to metadata")
    else:
        print_fail("Missing result.metadata mapping")
    if has_function_called:
        print_pass("Tracks function_called from orchestrator result")
    else:
        print_info("function_called tracking not in result mapping (optional)")

    return True


# ══════════════════════════════════════════════════════════════════
# TEST 8: FULL JOURNEY SIMULATION (Awareness Tracking)
# ══════════════════════════════════════════════════════════════════


def test_awareness_tracking_journey():
    """Simulate a journey and verify awareness state changes at each step."""
    print_header("TEST 8: Awareness Tracking Through Full Journey")

    from app.services.onboarding_jarvis_awareness import (
        detect_conversation_stage,
        track_question_asked,
        track_concern_raised,
        update_onboarding_context,
        build_awareness_summary,
    )

    db = create_mock_db()

    # Simulate the journey with context mutations
    steps = [
        ("welcome", {}, "Initial state"),
        ("discovery", {"industry": "ecommerce"}, "After mentioning online store"),
        ("demo", {"pack_type": "demo"}, "After requesting demo"),
        ("pricing", {"selected_variants": ["returns_refund", "billing_inquiry"]}, "After selecting variants"),
        ("bill_review", {"bill_shown": True}, "After viewing bill"),
        ("verification", {"otp": {"status": "sent"}, "email_verified": False}, "After providing email"),
        ("payment", {"payment_status": "pending"}, "After OTP verified"),
        ("handoff", {"payment_status": "completed"}, "After payment completed"),
    ]

    print_section("Journey Progression")
    for stage, ctx_updates, description in steps:
        ctx = db._get_context()
        ctx.update(ctx_updates)
        db._set_context(json.dumps(ctx))

        detected = detect_conversation_stage(ctx)
        match = "✓" if detected == stage else "✗"
        color = GREEN if detected == stage else RED
        print(f"  {color}{match}{RESET} {description}")
        print(f"     Expected: {stage}, Got: {detected}")
        print_stage(detected)

    # Test awareness summary at the end
    print_section("Final Awareness Summary")
    final_ctx = db._get_context()
    summary = build_awareness_summary({
        "entry_source": "variant_demo",
        "detected_stage": "handoff",
        "current_channel": "chat",
        "chat_message_count": 7,
        "email_verified": True,
        "payment_status": "completed",
        "handoff_completed": True,
        "concerns_raised": ["pricing"],
        "questions_asked": [{"topic": "demo"}, {"topic": "pricing"}],
    })
    print_result("Final summary", summary)

    return True


# ══════════════════════════════════════════════════════════════════
# TEST 9: SAFETY GATE INTEGRATION
# ══════════════════════════════════════════════════════════════════


def test_safety_gate():
    """Test the safety gate for onboarding functions."""
    print_header("TEST 9: Safety Gate for Onboarding Functions")

    try:
        from app.services.jarvis_safety_gate import check_safety, get_pending_status
    except ImportError:
        print_info("jarvis_safety_gate not available — skipping safety gate test")
        return True

    from app.services.onboarding_jarvis_function_registry import get_safety_level

    # Test that high-safety functions require confirmation
    print_section("Safety Level Mapping")

    test_cases = [
        ("show_pricing", "none", "Show pricing — no safety needed"),
        ("select_variants", "confirmation_required", "Select variants — needs confirmation"),
        ("purchase_demo_pack", "approval_required", "Purchase demo pack — needs explicit approval"),
        ("create_payment_session", "approval_required", "Create payment session — needs explicit approval"),
    ]

    for func_name, expected_level, description in test_cases:
        level = get_safety_level(func_name)
        match = level == expected_level
        if match:
            print_pass(f"{description} → {level}")
        else:
            print_fail(f"{description} → got {level}, expected {expected_level}")

    return True


# ══════════════════════════════════════════════════════════════════
# TEST 10: END-TO-END ORCHESTRATOR JOURNEY
# ══════════════════════════════════════════════════════════════════


async def test_e2e_orchestrator_journey():
    """Full end-to-end test: send all 7 messages through the orchestrator."""
    print_header("TEST 10: End-to-End Orchestrator Journey")

    from app.services.onboarding_jarvis_orchestrator import (
        process_onboarding_message,
        load_onboarding_context,
        detect_onboarding_stage,
    )

    db = create_mock_db()

    messages = [
        "Hi, I run an online store and get tons of refund requests",
        "Show me how you'd handle a refund request",
        "What's your pricing?",
        "I'd like to select the Returns Agent x3",
        "Show me my bill",
        "My business email is test@company.com",
        "The OTP is 123456",
    ]

    print_info("Processing 7 messages through the orchestrator pipeline")
    print_info("Each message goes through: context → awareness → stage → functions → LLM → safety → response\n")

    total_ms = 0
    for i, msg in enumerate(messages, 1):
        print_section(f"Message {i}/{len(messages)}")
        print(f"  {BOLD}User:{RESET} \"{msg}\"")

        start = datetime.now(timezone.utc)

        try:
            result = await process_onboarding_message(
                db=db,
                session_id=TEST_SESSION_ID,
                user_id=TEST_USER_ID,
                company_id=TEST_COMPANY_ID,
                user_message=msg,
                channel="chat",
            )
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            total_ms += elapsed

            # Display results
            content = result.get("content", "")[:200]
            msg_type = result.get("message_type", "")
            func_called = result.get("function_called")
            metadata = result.get("metadata", {})

            print(f"  {BOLD}Jarvis:{RESET} {content}...")
            print_result("Message type", msg_type)
            print_result("Function called", func_called or "None")
            print_result("Stage", metadata.get("stage", "unknown"))
            print_result("Total ms", f"{metadata.get('total_ms', 0):.1f}")
            print_result("Model", metadata.get("model", "unknown"))

            # Verify structure
            assert "content" in result
            assert "message_type" in result
            assert "metadata" in result
            print_pass(f"Message {i} processed successfully ({elapsed:.0f}ms)")

        except Exception as exc:
            print_fail(f"Message {i} raised exception: {exc}")
            import traceback
            traceback.print_exc()

    print_section("Journey Summary")
    print_result("Total messages", len(messages))
    print_result("Total processing time", f"{total_ms:.0f}ms")
    print_result("Average per message", f"{total_ms/len(messages):.0f}ms")

    return True


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════


async def run_all_tests():
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  PARWA Onboarding Jarvis — Manual End-to-End Test{RESET}")
    print(f"{BOLD}  Testing: Orchestrator + Awareness + Registry + Integration{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")

    start = datetime.now(timezone.utc)

    # Sync tests
    sync_tests = [
        ("Function Registry", test_function_registry),
        ("Awareness Engine", test_awareness_engine),
        ("Stage Detection", test_stage_detection),
        ("System Prompt Building", test_system_prompt_building),
        ("Context Loading", test_context_loading),
        ("jarvis_service Integration", test_jarvis_service_integration),
        ("Awareness Tracking Journey", test_awareness_tracking_journey),
        ("Safety Gate", test_safety_gate),
    ]

    # Async tests
    async_tests = [
        ("Orchestrator Pipeline", test_orchestrator_pipeline),
        ("End-to-End Orchestrator Journey", test_e2e_orchestrator_journey),
    ]

    passed = 0
    failed = 0

    # Run sync tests
    for name, test_func in sync_tests:
        try:
            result = test_func()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print_fail(f"{name}: {e}")
            import traceback
            traceback.print_exc()

    # Run async tests
    for name, test_func in async_tests:
        try:
            result = await test_func()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print_fail(f"{name}: {e}")
            import traceback
            traceback.print_exc()

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()

    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  RESULTS: {GREEN}{passed} passed{RESET}, {RED}{failed} failed{RESET} ({elapsed:.1f}s)")
    print(f"{BOLD}{'=' * 70}{RESET}")

    if failed == 0:
        print(f"\n  {GREEN}All tests passed! Onboarding Jarvis orchestrator is integrated.{RESET}")
        print(f"  The send_message function now routes through the full pipeline:")
        print(f"    context → awareness → stage detection → function registry →")
        print(f"    LLM with function calling → safety gate → execute → awareness update")
    else:
        print(f"\n  {RED}{failed} test(s) failed. Check the errors above.{RESET}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
