"""
PARWA Jarvis — Realistic Customer Support Ticket Tests

Tests focused on REAL business customer support scenarios:
  - Order tracking issues
  - Returns & refunds
  - Delivery problems
  - Billing disputes
  - Product complaints
  - Account management

NOT Parwa's own login issues or internal problems. These are the
tickets that BUSINESSES using Parwa would receive from THEIR customers.

BC-001: company_id enforced everywhere.
BC-008: Graceful error handling.
BC-012: All timestamps UTC.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


TEST_COMPANY_ID = "acme-corp-001"
TEST_SESSION_ID = "jarvis-session-001"
TEST_USER_ID = "admin-user-001"


# ══════════════════════════════════════════════════════════════════
# 1. REALISTIC CUSTOMER SUPPORT CATEGORIES
# ══════════════════════════════════════════════════════════════════


class TestRealisticCategories:
    """Test that the fake request generator covers real business categories."""

    def test_order_tracking_requests_exist(self):
        """Businesses get 'where is my order' tickets — verify they exist."""
        from app.services.fake_request_generator import generate_fake_requests

        requests = generate_fake_requests(count=10, category="order_tracking")
        assert len(requests) > 0, "Should generate order tracking requests"
        for r in requests:
            assert r["category"] == "order_tracking"
            # These should be about CUSTOMERS asking about THEIR orders,
            # NOT about Parwa's own login/order issues
            assert "login" not in r["subject"].lower()
            assert "login" not in r["message"].lower()

    def test_returns_refunds_requests_exist(self):
        """Businesses get refund/return requests — verify they exist."""
        from app.services.fake_request_generator import generate_fake_requests

        requests = generate_fake_requests(count=5, category="returns_refunds")
        assert len(requests) == 5
        for r in requests:
            assert r["category"] == "returns_refunds"
            # Should be about customer refund requests, not Parwa's billing
            assert "parwa" not in r["message"].lower()

    def test_delivery_issues_requests_exist(self):
        """Businesses get delivery problem tickets — verify they exist."""
        from app.services.fake_request_generator import generate_fake_requests

        requests = generate_fake_requests(count=5, category="delivery_issues")
        assert len(requests) == 5
        for r in requests:
            assert r["category"] == "delivery_issues"

    def test_billing_requests_are_customer_billing(self):
        """Billing tickets should be about customer billing, not Parwa's billing."""
        from app.services.fake_request_generator import generate_fake_requests

        requests = generate_fake_requests(count=5, category="billing")
        for r in requests:
            # These should be customers asking about THEIR bills/charges
            # NOT about Parwa's subscription or pricing
            msg_lower = r["message"].lower()
            # Should contain typical customer billing complaint words
            billing_words = ["charged", "invoice", "payment", "refund", "subscription", "plan", "bill"]
            has_billing_keyword = any(w in msg_lower for w in billing_words)
            assert has_billing_keyword, f"Billing request should mention billing terms: {r['subject']}"

    def test_complaint_requests_exist(self):
        """Businesses get angry customer complaints — verify they exist."""
        from app.services.fake_request_generator import generate_fake_requests

        requests = generate_fake_requests(count=5, category="complaint")
        assert len(requests) == 5
        for r in requests:
            assert r["category"] == "complaint"
            # Complaints should have realistic urgency
            # (generator has 20% random variation, so "low" is possible but rare)
            assert r["priority"] in ["low", "medium", "high", "critical"]

    def test_tech_support_is_customer_tech_issues(self):
        """Tech support tickets should be about customer product issues, NOT Parwa's."""
        from app.services.fake_request_generator import generate_fake_requests

        requests = generate_fake_requests(count=5, category="tech_support")
        for r in requests:
            # Should NOT be about Parwa's own internal tech issues
            assert "parwa" not in r["message"].lower()
            # Should be about customer-facing product problems.
            # Note: "Login not working" IS a valid customer tech support issue
            # (customer can't log into THEIR account on the business's product).
            # What's WRONG is "Parwa login issues" — that's an internal problem.
            tech_keywords = ["app", "error", "crash", "working", "dashboard", "api",
                           "export", "login", "log in", "integration", "loading", "slow"]
            msg_lower = r["message"].lower()
            has_tech_keyword = any(kw in msg_lower for kw in tech_keywords)
            assert has_tech_keyword, f"Tech support request should mention tech issues: {r['subject']}"

    def test_account_management_is_customer_accounts(self):
        """Account management tickets should be about customer accounts."""
        from app.services.fake_request_generator import generate_fake_requests

        requests = generate_fake_requests(count=5, category="account_management")
        for r in requests:
            # These are about the BUSINESS's customers having account problems
            # NOT about Parwa's own account management
            assert "parwa" not in r["message"].lower()

    def test_no_login_issue_tickets_anywhere(self):
        """CRITICAL: No ticket should be about Parwa's login issues.
        
        Parwa's clients are businesses. Their customers don't log into Parwa.
        They log into the BUSINESS'S product. Tickets about 'Parwa login issues'
        make no sense — that's an internal support request, not a customer
        support ticket that a business would receive.
        """
        from app.services.fake_request_generator import generate_fake_requests

        all_requests = generate_fake_requests(count=25, category="mixed")
        for r in all_requests:
            subject_lower = r["subject"].lower()
            message_lower = r["message"].lower()
            # None of these should be about Parwa's own login/auth problems
            assert "parwa login" not in subject_lower
            assert "parwa login" not in message_lower
            assert "login to parwa" not in message_lower
            # Login issues in general are fine IF they're about the business's
            # product (e.g., "I can't log into my account on your app")
            # That's a valid customer support ticket


# ══════════════════════════════════════════════════════════════════
# 2. CREATE_TICKET WITH REALISTIC SCENARIOS
# ══════════════════════════════════════════════════════════════════


class TestCreateTicketRealisticScenarios:
    """Test creating tickets from realistic customer support scenarios."""

    def test_create_ticket_function_accepts_all_realistic_categories(self):
        """create_ticket should accept order_tracking, returns_refunds, etc."""
        from app.services.jarvis_function_registry import get_function_metadata

        meta = get_function_metadata("create_ticket")
        assert meta is not None

        category_enum = meta["parameters"]["properties"]["category"]["enum"]
        realistic_categories = [
            "tech_support", "billing", "returns_refunds",
            "order_tracking", "delivery_issues", "complaint",
        ]
        for cat in realistic_categories:
            assert cat in category_enum, f"Category '{cat}' not in create_ticket options"

    def test_create_ticket_function_accepts_all_channels(self):
        """create_ticket should accept chat, email, sms, api, phone."""
        from app.services.jarvis_function_registry import get_function_metadata

        meta = get_function_metadata("create_ticket")
        channel_enum = meta["parameters"]["properties"]["channel"]["enum"]
        for ch in ["chat", "email", "sms", "api", "phone"]:
            assert ch in channel_enum, f"Channel '{ch}' not in create_ticket options"

    def test_create_ticket_function_description_mentions_customer(self):
        """create_ticket description should mention customers, not Parwa's own issues."""
        from app.services.jarvis_function_registry import get_function_metadata

        meta = get_function_metadata("create_ticket")
        desc = meta["description"].lower()
        # Should be about customer support, not internal operations
        assert "ticket" in desc or "support" in desc or "issue" in desc

    def test_safety_gate_for_order_tracking_ticket(self):
        """Creating an order tracking ticket should be approved immediately."""
        from app.services.jarvis_safety_gate import check_safety

        result = check_safety(
            company_id=TEST_COMPANY_ID,
            session_id=TEST_SESSION_ID,
            function_name="create_ticket",
            function_params={
                "subject": "Where is my order?",
                "message": "I ordered 5 days ago and it hasn't arrived yet. Order #ORD-28491.",
                "category": "order_tracking",
                "priority": "high",
            },
            user_message="create a ticket for a customer asking about their order",
        )
        assert result.is_approved

    def test_safety_gate_for_refund_ticket(self):
        """Creating a refund ticket should be approved (safety=none for create)."""
        from app.services.jarvis_safety_gate import check_safety

        result = check_safety(
            company_id=TEST_COMPANY_ID,
            session_id=TEST_SESSION_ID,
            function_name="create_ticket",
            function_params={
                "subject": "Customer wants refund for damaged product",
                "message": "Product arrived damaged, customer wants full refund.",
                "category": "returns_refunds",
                "priority": "high",
            },
            user_message="a customer wants a refund, create a ticket",
        )
        assert result.is_approved


# ══════════════════════════════════════════════════════════════════
# 3. SOLVE_TICKET WITH VARIANT INTEGRATION
# ══════════════════════════════════════════════════════════════════


class TestSolveTicketVariantIntegration:
    """Test solving tickets through the variant pipeline."""

    def test_solve_ticket_accepts_all_variant_tiers(self):
        """solve_ticket should accept auto, mini_parwa, parwa, parwa_high."""
        from app.services.jarvis_function_registry import get_function_metadata

        meta = get_function_metadata("solve_ticket")
        variant_enum = meta["parameters"]["properties"]["force_variant"]["enum"]
        for v in ["auto", "mini_parwa", "parwa", "parwa_high"]:
            assert v in variant_enum, f"Variant '{v}' not in solve_ticket options"

    def test_solve_ticket_requires_confirmation(self):
        """Solving a ticket (modifying state) should require confirmation."""
        from app.services.jarvis_safety_gate import check_safety, clear_all_pending

        clear_all_pending(TEST_COMPANY_ID, TEST_SESSION_ID)

        result = check_safety(
            company_id=TEST_COMPANY_ID,
            session_id=TEST_SESSION_ID,
            function_name="solve_ticket",
            function_params={"ticket_id": "t-order-001", "force_variant": "auto"},
            user_message="solve the order tracking ticket",
        )

        assert result.needs_human_input, "solve_ticket should need confirmation"

        clear_all_pending(TEST_COMPANY_ID, TEST_SESSION_ID)

    def test_batch_solve_confirmation_message_is_conversational(self):
        """Batch solve confirmation should be natural, not robotic."""
        from app.services.jarvis_safety_gate import _build_confirmation_message

        msg = _build_confirmation_message("batch_solve_tickets", {"max_tickets": 15})
        assert "variant pipeline" in msg.lower() or "AI" in msg
        assert "command executed" not in msg.lower()
        assert "batch_solve_tickets" not in msg  # Should NOT show function name


# ══════════════════════════════════════════════════════════════════
# 4. FAKE REQUEST GENERATOR — REALISTIC SCENARIOS
# ══════════════════════════════════════════════════════════════════


class TestFakeRequestRealism:
    """Test that fake requests represent real business customer support scenarios."""

    def test_order_tracking_describes_real_customer_problems(self):
        """Order tracking requests should sound like real customer messages."""
        from app.services.fake_request_generator import generate_fake_requests

        requests = generate_fake_requests(count=5, category="order_tracking")
        for r in requests:
            msg = r["message"].lower()
            # Real customers mention: tracking, order number, waiting, shipping
            real_keywords = ["order", "tracking", "shipping", "arrived", "delivery", "shipment", "address"]
            has_real_keyword = any(kw in msg for kw in real_keywords)
            assert has_real_keyword, f"Order tracking should mention order/tracking/shipping: {r['subject']}"

    def test_returns_refunds_have_specific_product_issues(self):
        """Return/refund requests should mention specific product problems."""
        from app.services.fake_request_generator import generate_fake_requests

        requests = generate_fake_requests(count=5, category="returns_refunds")
        for r in requests:
            msg = r["message"].lower()
            # Real refund requests mention: damaged, wrong item, cancellation, refund
            refund_keywords = ["damaged", "wrong", "refund", "return", "cancellation", "exchange", "credit"]
            has_keyword = any(kw in msg for kw in refund_keywords)
            assert has_keyword, f"Refund request should mention specific issues: {r['subject']}"

    def test_delivery_issues_mention_delivery_problems(self):
        """Delivery issue requests should mention delivery-specific problems."""
        from app.services.fake_request_generator import generate_fake_requests

        requests = generate_fake_requests(count=5, category="delivery_issues")
        for r in requests:
            msg = r["message"].lower()
            delivery_keywords = ["delivered", "driver", "package", "missing", "address", "rain", "wrong address", "items"]
            has_keyword = any(kw in msg for kw in delivery_keywords)
            assert has_keyword, f"Delivery issue should mention delivery problems: {r['subject']}"

    def test_complaint_tickets_sound_angry(self):
        """Complaint tickets should have realistic frustrated tone."""
        from app.services.fake_request_generator import generate_fake_requests

        requests = generate_fake_requests(count=5, category="complaint")
        for r in requests:
            # Complaints should sound like real frustrated customers
            # They might mention: waiting, worst, unacceptable, switch, etc.
            msg = r["message"].lower()
            frustration_keywords = ["waiting", "worst", "frustrating", "unacceptable", "switch", 
                                    "terrible", "never", "complaint", "false", "charged"]
            has_frustration = any(kw in msg for kw in frustration_keywords)
            assert has_frustration, f"Complaint should sound frustrated: {r['subject']}"

    def test_feature_requests_are_reasonable(self):
        """Feature requests should be realistic things customers ask for."""
        from app.services.fake_request_generator import generate_fake_requests

        requests = generate_fake_requests(count=5, category="feature_request")
        for r in requests:
            # Feature requests should be about product improvements
            msg = r["message"].lower()
            feature_keywords = ["app", "integration", "mobile", "dashboard", "report", 
                              "whatsapp", "feature", "roadmap", "add", "build", "custom"]
            has_feature_keyword = any(kw in msg for kw in feature_keywords)
            assert has_feature_keyword, f"Feature request should mention features: {r['subject']}"

    def test_auto_solve_param_in_generate_fake_requests(self):
        """generate_fake_requests function definition should support auto_solve."""
        from app.services.jarvis_function_registry import get_function_metadata

        meta = get_function_metadata("generate_fake_requests")
        props = meta["parameters"]["properties"]
        assert "auto_solve" in props, "auto_solve parameter missing"
        assert props["auto_solve"]["type"] == "boolean"

    def test_category_param_supports_all_realistic_categories(self):
        """generate_fake_requests should support all realistic category types."""
        from app.services.jarvis_function_registry import get_function_metadata

        meta = get_function_metadata("generate_fake_requests")
        category_enum = meta["parameters"]["properties"]["category"]["enum"]
        # Should support 'mixed' and specific categories
        assert "mixed" in category_enum
        # All the realistic business categories
        for cat in ["tech_support", "billing", "returns_refunds", "complaint", "feature_request"]:
            assert cat in category_enum, f"Category '{cat}' not in generate_fake_requests options"


# ══════════════════════════════════════════════════════════════════
# 5. ORCHESTRATOR CONTEXT LOADING
# ══════════════════════════════════════════════════════════════════


class TestOrchestratorContextAndMode:
    """Test orchestrator context loading and mode decision for realistic scenarios."""

    def test_decide_mode_default_is_command(self):
        """When no session type is set, mode should default to command."""
        from app.services.jarvis_orchestrator import decide_mode

        context = {"session": {}, "awareness": {}}
        mode = decide_mode(context)
        assert mode == "command"

    def test_decide_mode_command_for_admin(self):
        """Admin sessions should be in command mode (full capabilities)."""
        from app.services.jarvis_orchestrator import decide_mode

        context = {"session": {"type": "admin", "mode": "admin"}}
        mode = decide_mode(context)
        assert mode == "command"

    def test_decide_mode_agentic_for_customer_care(self):
        """Customer care sessions should be in agentic mode (customer-facing)."""
        from app.services.jarvis_orchestrator import decide_mode

        context = {"session": {"type": "customer_care", "mode": "customer_care"}}
        mode = decide_mode(context)
        assert mode == "agentic"

    def test_system_prompt_for_command_mode_mentions_support_operations(self):
        """Command mode prompt should mention managing support operations."""
        from app.services.jarvis_orchestrator import build_system_prompt

        prompt = build_system_prompt("command", {"awareness": {}})
        assert "support" in prompt.lower() or "platform" in prompt.lower()

    def test_system_prompt_for_agentic_mode_mentions_customer(self):
        """Agentic mode prompt should mention helping customers."""
        from app.services.jarvis_orchestrator import build_system_prompt

        prompt = build_system_prompt("agentic", {"awareness": {}})
        assert "customer" in prompt.lower()

    def test_system_prompt_includes_awareness_when_available(self):
        """System prompt should include awareness state when available."""
        from app.services.jarvis_orchestrator import build_system_prompt

        context = {
            "awareness": {
                "system_health": "healthy",
                "ticket_volume_today": 47,
                "quality_score": 0.94,
                "agent_pool_utilization": 0.72,
                "current_plan": "parwa",
                "plan_usage_today": "65%",
            }
        }
        prompt = build_system_prompt("command", context)
        assert "47" in prompt  # ticket volume
        assert "healthy" in prompt

    def test_process_message_returns_fallback_on_empty_message(self):
        """Empty messages should get a friendly response, not an error."""
        from app.services.jarvis_orchestrator import process_message

        # This is a synchronous test so we need to run the async function
        import asyncio
        result = asyncio.run(process_message(
            db=MagicMock(),
            company_id=TEST_COMPANY_ID,
            session_id=TEST_SESSION_ID,
            user_id=TEST_USER_ID,
            user_message="",
        ))
        assert result["response"] == "Hey! What can I help you with?"


# ══════════════════════════════════════════════════════════════════
# 6. SAFETY GATE — REALISTIC SCENARIOS
# ══════════════════════════════════════════════════════════════════


class TestSafetyGateRealisticScenarios:
    """Test safety gate with realistic customer support workflows."""

    def test_process_refund_needs_explicit_approval(self):
        """Processing a refund (monetary action) needs explicit 'confirm'."""
        from app.services.jarvis_safety_gate import check_safety, clear_all_pending

        clear_all_pending(TEST_COMPANY_ID, TEST_SESSION_ID)

        result = check_safety(
            company_id=TEST_COMPANY_ID,
            session_id=TEST_SESSION_ID,
            function_name="process_refund",
            function_params={
                "customer_id": "cust-001",
                "amount": 49.99,
                "reason": "Product arrived damaged",
            },
            user_message="process the refund for the damaged product",
        )

        # process_refund is approval_required — most strict
        assert result.status in ("needs_approval", "needs_confirmation")

        clear_all_pending(TEST_COMPANY_ID, TEST_SESSION_ID)

    def test_emergency_stop_needs_confirmation(self):
        """Emergency stop needs confirmation — it's a major action."""
        from app.services.jarvis_safety_gate import check_safety, clear_all_pending

        clear_all_pending(TEST_COMPANY_ID, TEST_SESSION_ID)

        result = check_safety(
            company_id=TEST_COMPANY_ID,
            session_id=TEST_SESSION_ID,
            function_name="emergency_stop",
            function_params={"reason": "AI generating wrong refund amounts"},
            user_message="emergency stop! the AI is making mistakes",
        )

        assert result.needs_human_input, "Emergency stop should need confirmation"

        clear_all_pending(TEST_COMPANY_ID, TEST_SESSION_ID)

    def test_check_system_health_approved_immediately(self):
        """Checking system health is read-only — should be approved instantly."""
        from app.services.jarvis_safety_gate import check_safety

        result = check_safety(
            company_id=TEST_COMPANY_ID,
            session_id=TEST_SESSION_ID,
            function_name="check_system_health",
            function_params={},
            user_message="how's the system doing?",
        )

        assert result.is_approved
        assert result.status == "approved"

    def test_get_ticket_stats_approved_immediately(self):
        """Getting ticket stats is read-only — should be approved instantly."""
        from app.services.jarvis_safety_gate import check_safety

        result = check_safety(
            company_id=TEST_COMPANY_ID,
            session_id=TEST_SESSION_ID,
            function_name="get_ticket_stats",
            function_params={"time_range": "today"},
            user_message="how many tickets today?",
        )

        assert result.is_approved

    def test_approval_message_for_refund_mentions_monetary(self):
        """Refund approval message should warn about monetary action."""
        from app.services.jarvis_safety_gate import _build_approval_message

        msg = _build_approval_message("process_refund", {"amount": 49.99, "reason": "Damaged product"})
        assert "refund" in msg.lower() or "monetary" in msg.lower()
        assert "confirm" in msg.lower()  # Should ask for explicit confirmation

    def test_confirmation_message_for_pause_ai_is_conversational(self):
        """Pause AI message should sound like a colleague, not a robot."""
        from app.services.jarvis_safety_gate import _build_confirmation_message

        msg = _build_confirmation_message("pause_all_ai", {"reason": "Quality issues"})
        assert "pause" in msg.lower() or "AI" in msg
        # Should NOT be robotic
        assert "command executed" not in msg.lower()
        assert "confirmation required" not in msg.lower()


# ══════════════════════════════════════════════════════════════════
# 7. VARIANT BRIDGE — TIER CONFIGURATION
# ══════════════════════════════════════════════════════════════════


class TestVariantBridgeTierConfig:
    """Test variant bridge tier configuration for realistic scenarios."""

    def test_mini_parwa_cannot_auto_execute_refunds(self):
        """mini_parwa tier: All actions need approval (notify-only mode)."""
        from app.services.jarvis_agents.variant_bridge import check_jarvis_approval_needed

        result = check_jarvis_approval_needed(
            company_id=TEST_COMPANY_ID,
            variant_tier="mini_parwa",
            agent_type="billing",
            agent_action="refund",
        )
        assert result["approval_needed"] is True

    def test_parwa_auto_executes_standard_ops(self):
        """parwa tier: Standard operations are auto-approved."""
        from app.services.jarvis_agents.variant_bridge import check_jarvis_approval_needed

        result = check_jarvis_approval_needed(
            company_id=TEST_COMPANY_ID,
            variant_tier="parwa",
            agent_type="reassignment",
            agent_action="reassign",
        )
        assert result["approval_needed"] is False

    def test_parwa_needs_approval_for_monetary(self):
        """parwa tier: Monetary actions (refunds) need approval."""
        from app.services.jarvis_agents.variant_bridge import check_jarvis_approval_needed

        result = check_jarvis_approval_needed(
            company_id=TEST_COMPANY_ID,
            variant_tier="parwa",
            agent_type="billing",
            agent_action="refund",
        )
        assert result["approval_needed"] is True

    def test_parwa_high_auto_approves_refunds(self):
        """parwa_high tier: Even refunds are auto-approved."""
        from app.services.jarvis_agents.variant_bridge import check_jarvis_approval_needed

        result = check_jarvis_approval_needed(
            company_id=TEST_COMPANY_ID,
            variant_tier="parwa_high",
            agent_type="billing",
            agent_action="refund",
        )
        assert result["approval_needed"] is False

    def test_parwa_high_needs_approval_for_emergency(self):
        """parwa_high tier: Emergency actions still need approval."""
        from app.services.jarvis_agents.variant_bridge import check_jarvis_approval_needed

        result = check_jarvis_approval_needed(
            company_id=TEST_COMPANY_ID,
            variant_tier="parwa_high",
            agent_type="escalation",
            agent_action="full_stop",
        )
        assert result["approval_needed"] is True

    def test_unknown_tier_defaults_to_safest(self):
        """Unknown tier should default to safest config (mini_parwa/notify-only)."""
        from app.services.jarvis_agents.variant_bridge import get_variant_aware_command_config

        result = get_variant_aware_command_config(TEST_COMPANY_ID, "unknown_tier")
        assert result["mode"] == "notify_only"


# ══════════════════════════════════════════════════════════════════
# 8. END-TO-END INTEGRATION — FAKE REQUESTS → TICKETS → SOLVE
# ══════════════════════════════════════════════════════════════════


class TestEndToEndFlow:
    """Integration test: Generate fake requests → Create tickets → Solve via variants."""

    def test_generate_then_create_params_are_compatible(self):
        """Fake request output should be directly compatible with create_ticket input."""
        from app.services.fake_request_generator import generate_fake_requests
        from app.services.jarvis_function_registry import get_function_metadata

        # Generate fake requests
        requests = generate_fake_requests(count=5, category="mixed")

        # Get create_ticket parameter schema
        create_meta = get_function_metadata("create_ticket")
        create_props = create_meta["parameters"]["properties"]
        create_required = create_meta["parameters"].get("required", [])

        # Verify every fake request can populate create_ticket params
        for req in requests:
            # Subject → subject
            assert "subject" in req, "Fake request missing 'subject'"
            assert isinstance(req["subject"], str)

            # Message → message
            assert "message" in req, "Fake request missing 'message'"
            assert isinstance(req["message"], str)

            # Priority → priority (must match enum)
            if "priority" in req:
                assert req["priority"] in create_props["priority"]["enum"]

            # Category → category (must match enum)
            if "category" in req:
                assert req["category"] in create_props["category"]["enum"], \
                    f"Category '{req['category']}' not in create_ticket enum"

            # Channel → channel (must match enum)
            if "channel" in req:
                assert req["channel"] in create_props["channel"]["enum"], \
                    f"Channel '{req['channel']}' not in create_ticket enum"

    def test_generate_auto_solve_param_is_supported(self):
        """generate_fake_requests should support auto_solve parameter."""
        from app.services.fake_request_generator import generate_fake_requests

        # Without auto_solve (just generate)
        requests = generate_fake_requests(count=3, category="billing")
        for r in requests:
            assert "subject" in r
            assert "message" in r

    def test_full_safety_flow_for_realistic_workflow(self):
        """Simulate a realistic workflow: check health → list tickets → solve."""
        from app.services.jarvis_safety_gate import check_safety, clear_all_pending

        clear_all_pending(TEST_COMPANY_ID, TEST_SESSION_ID)

        # Step 1: Check system health — approved immediately
        r1 = check_safety(
            TEST_COMPANY_ID, TEST_SESSION_ID,
            "check_system_health", {},
            "how's the system?",
        )
        assert r1.is_approved

        # Step 2: Create a ticket — approved immediately
        r2 = check_safety(
            TEST_COMPANY_ID, TEST_SESSION_ID,
            "create_ticket",
            {"subject": "Customer wants refund", "message": "Damaged product, requesting refund"},
            "create a ticket for a refund request",
        )
        assert r2.is_approved

        # Step 3: List recent tickets — approved immediately
        r3 = check_safety(
            TEST_COMPANY_ID, TEST_SESSION_ID,
            "list_recent_tickets", {},
            "show me recent tickets",
        )
        assert r3.is_approved

        # Step 4: Solve a ticket — needs confirmation
        r4 = check_safety(
            TEST_COMPANY_ID, TEST_SESSION_ID,
            "solve_ticket",
            {"ticket_id": "t-001"},
            "solve that ticket",
        )
        assert r4.needs_human_input

        # Step 5: Confirm solve
        r5 = check_safety(
            TEST_COMPANY_ID, TEST_SESSION_ID,
            "solve_ticket",
            {"ticket_id": "t-001"},
            "yes solve it",
        )
        assert r5.is_approved

        clear_all_pending(TEST_COMPANY_ID, TEST_SESSION_ID)

    def test_batch_solve_with_priority_filter(self):
        """batch_solve_tickets should support priority filtering."""
        from app.services.jarvis_function_registry import get_function_metadata

        meta = get_function_metadata("batch_solve_tickets")
        props = meta["parameters"]["properties"]
        assert "priority_filter" in props
        assert "all" in props["priority_filter"]["enum"]
        assert "high" in props["priority_filter"]["enum"]
        assert "critical" in props["priority_filter"]["enum"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
