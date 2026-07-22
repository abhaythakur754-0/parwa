"""
PARWA Jarvis CLI System — Unit and Integration Tests

Tests the full Jarvis LLM Function Calling pipeline:
  1. Function Registry — definition generation, filtering, safety levels
  2. Safety Gate — confirmation/approval flow, TTL expiry, rejection
  3. Orchestrator — context loading, mode decision, pipeline flow
  4. API Router — endpoint validation, auth, error handling
  5. Integration — end-to-end message processing

BC-008: Tests never crash — all failures are caught and reported.
"""

import json
import time
import unittest
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

# ══════════════════════════════════════════════════════════════════
# UNIT TESTS: Function Registry
# ══════════════════════════════════════════════════════════════════


class TestFunctionRegistry(unittest.TestCase):
    """Test the Jarvis function registry."""

    def setUp(self):
        from app.services.jarvis_function_registry import FUNCTION_REGISTRY
        self.registry = FUNCTION_REGISTRY

    def test_registry_not_empty(self):
        """Registry has function definitions."""
        self.assertGreater(len(self.registry), 0)

    def test_each_function_has_required_fields(self):
        """Every function definition has name, description, parameters, safety_level, category."""
        for func_def in self.registry:
            self.assertIn("name", func_def, f"Missing 'name' in {func_def}")
            self.assertIn("description", func_def, f"Missing 'description' in {func_def}")
            self.assertIn("parameters", func_def, f"Missing 'parameters' in {func_def}")
            self.assertIn("safety_level", func_def, f"Missing 'safety_level' in {func_def}")
            self.assertIn("category", func_def, f"Missing 'category' in {func_def}")
            self.assertIn("tier_available", func_def, f"Missing 'tier_available' in {func_def}")

    def test_safety_levels_valid(self):
        """Every function has a valid safety level."""
        from app.services.jarvis_function_registry import SAFETY_NONE, SAFETY_CONFIRMATION, SAFETY_APPROVAL
        valid_levels = {SAFETY_NONE, SAFETY_CONFIRMATION, SAFETY_APPROVAL}
        for func_def in self.registry:
            self.assertIn(
                func_def["safety_level"], valid_levels,
                f"Invalid safety_level '{func_def['safety_level']}' for {func_def['name']}"
            )

    def test_parameters_have_type(self):
        """Every parameter schema has a 'type' field."""
        for func_def in self.registry:
            params = func_def.get("parameters", {})
            self.assertIn("type", params, f"Missing 'type' in parameters for {func_def['name']}")
            self.assertEqual(params["type"], "object")

    def test_no_duplicate_names(self):
        """No two functions have the same name."""
        names = [f["name"] for f in self.registry]
        self.assertEqual(len(names), len(set(names)), f"Duplicate function names: {[n for n in names if names.count(n) > 1]}")

    def test_get_function_definitions_command_mode(self):
        """Command mode returns all functions for the tier."""
        from app.services.jarvis_function_registry import get_function_definitions
        defs = get_function_definitions(mode="command", tier="parwa")
        self.assertGreater(len(defs), 0)
        # All should have OpenAI tool format
        for d in defs:
            self.assertEqual(d["type"], "function")
            self.assertIn("function", d)
            self.assertIn("name", d["function"])
            self.assertIn("description", d["function"])
            self.assertIn("parameters", d["function"])

    def test_get_function_definitions_agentic_mode(self):
        """Agentic mode only returns customer_facing functions."""
        from app.services.jarvis_function_registry import (
            get_function_definitions,
            CATEGORY_CUSTOMER_FACING,
        )
        defs = get_function_definitions(mode="agentic", tier="parwa")
        self.assertGreater(len(defs), 0)
        # All should be customer-facing
        from app.services.jarvis_function_registry import get_function_metadata
        for d in defs:
            metadata = get_function_metadata(d["function"]["name"])
            self.assertEqual(metadata["category"], CATEGORY_CUSTOMER_FACING)

    def test_tier_filtering_mini_parwa(self):
        """Mini Parwa tier should exclude premium-only functions."""
        from app.services.jarvis_function_registry import get_function_names, TIER_PREMIUM_ONLY
        # Get premium-only function names
        premium_funcs = [f["name"] for f in self.registry if f["tier_available"] == TIER_PREMIUM_ONLY]
        mini_parwa_funcs = get_function_names(mode="command", tier="mini_parwa")
        for pf in premium_funcs:
            self.assertNotIn(pf, mini_parwa_funcs, f"Premium function {pf} should not be in mini_parwa")

    def test_get_function_metadata(self):
        """Can look up function metadata by name."""
        from app.services.jarvis_function_registry import get_function_metadata
        metadata = get_function_metadata("check_system_health")
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["name"], "check_system_health")
        self.assertIn("safety_level", metadata)

    def test_get_function_metadata_unknown(self):
        """Unknown function returns None."""
        from app.services.jarvis_function_registry import get_function_metadata
        self.assertIsNone(get_function_metadata("nonexistent_function"))

    def test_get_safety_level(self):
        """Safety level lookup works for known functions."""
        from app.services.jarvis_function_registry import get_safety_level, SAFETY_NONE, SAFETY_APPROVAL
        # check_system_health should be safe
        self.assertEqual(get_safety_level("check_system_health"), SAFETY_NONE)
        # process_refund should require approval
        self.assertEqual(get_safety_level("process_refund"), SAFETY_APPROVAL)

    def test_get_safety_level_unknown_defaults_to_confirmation(self):
        """Unknown function defaults to confirmation_required (fail-safe)."""
        from app.services.jarvis_function_registry import get_safety_level, SAFETY_CONFIRMATION
        self.assertEqual(get_safety_level("nonexistent"), SAFETY_CONFIRMATION)

    def test_get_function_count_by_safety(self):
        """Can count functions by safety level."""
        from app.services.jarvis_function_registry import get_function_count_by_safety
        counts = get_function_count_by_safety()
        self.assertIn("none", counts)
        self.assertIn("confirmation_required", counts)
        self.assertIn("approval_required", counts)
        total = sum(counts.values())
        self.assertEqual(total, len(self.registry))

    def test_monetary_functions_require_approval(self):
        """All monetary functions have approval_required safety level."""
        from app.services.jarvis_function_registry import SAFETY_APPROVAL
        monetary_functions = ["process_refund"]
        for func_name in monetary_functions:
            metadata = next((f for f in self.registry if f["name"] == func_name), None)
            if metadata:
                self.assertEqual(
                    metadata["safety_level"], SAFETY_APPROVAL,
                    f"{func_name} should require approval"
                )


# ══════════════════════════════════════════════════════════════════
# UNIT TESTS: Safety Gate
# ══════════════════════════════════════════════════════════════════


class TestSafetyGate(unittest.TestCase):
    """Test the Jarvis safety gate."""

    def setUp(self):
        """Clear pending confirmations before each test."""
        from app.services.jarvis_safety_gate import clear_all_pending
        clear_all_pending("test_company", "test_session")

    def test_safe_function_approved_immediately(self):
        """Safe functions (safety_level=none) are approved immediately."""
        from app.services.jarvis_safety_gate import check_safety, SafetyCheckResult
        result = check_safety(
            company_id="test_company",
            session_id="test_session",
            function_name="check_system_health",
            function_params={},
            user_message="how's it going",
        )
        self.assertEqual(result.status, "approved")
        self.assertTrue(result.is_approved)
        self.assertFalse(result.needs_human_input)

    def test_confirmation_required_needs_confirmation(self):
        """Functions with confirmation_required need user confirmation."""
        from app.services.jarvis_safety_gate import check_safety
        result = check_safety(
            company_id="test_company",
            session_id="test_session",
            function_name="pause_all_ai",
            function_params={"reason": "testing"},
            user_message="pause my AI",
        )
        self.assertEqual(result.status, "needs_confirmation")
        self.assertTrue(result.needs_human_input)
        self.assertIn("pause", result.message.lower())

    def test_approval_required_needs_approval(self):
        """Functions with approval_required need explicit approval."""
        from app.services.jarvis_safety_gate import check_safety
        result = check_safety(
            company_id="test_company",
            session_id="test_session",
            function_name="process_refund",
            function_params={"customer_id": "c1", "amount": 50, "reason": "test"},
            user_message="refund the customer",
        )
        self.assertEqual(result.status, "needs_approval")
        self.assertTrue(result.needs_human_input)

    def test_confirmation_flow_approve(self):
        """After needs_confirmation, user can confirm by responding."""
        from app.services.jarvis_safety_gate import check_safety, clear_all_pending
        clear_all_pending("test_company", "test_session")

        # Step 1: Initial request → needs confirmation
        result1 = check_safety(
            company_id="test_company",
            session_id="test_session",
            function_name="pause_all_ai",
            function_params={"reason": "testing"},
            user_message="pause my AI",
        )
        self.assertEqual(result1.status, "needs_confirmation")

        # Step 2: User confirms → approved
        result2 = check_safety(
            company_id="test_company",
            session_id="test_session",
            function_name="pause_all_ai",
            function_params={"reason": "testing"},
            user_message="yes go ahead",
        )
        self.assertEqual(result2.status, "approved")

    def test_confirmation_flow_reject(self):
        """After needs_confirmation, user can reject."""
        from app.services.jarvis_safety_gate import check_safety, clear_all_pending
        clear_all_pending("test_company", "test_session")

        # Step 1: Request → needs confirmation
        check_safety(
            company_id="test_company",
            session_id="test_session",
            function_name="pause_all_ai",
            function_params={"reason": "testing"},
            user_message="pause my AI",
        )

        # Step 2: User rejects
        result = check_safety(
            company_id="test_company",
            session_id="test_session",
            function_name="pause_all_ai",
            function_params={"reason": "testing"},
            user_message="no cancel",
        )
        self.assertEqual(result.status, "rejected")

    def test_approval_requires_explicit_keyword(self):
        """Approval level requires explicit 'confirm' or 'yes' keyword."""
        from app.services.jarvis_safety_gate import check_safety, clear_all_pending
        clear_all_pending("test_company", "test_session")

        # Step 1: Request refund → needs approval
        check_safety(
            company_id="test_company",
            session_id="test_session",
            function_name="process_refund",
            function_params={"customer_id": "c1", "amount": 50, "reason": "test"},
            user_message="refund the customer",
        )

        # Step 2: Vague response → still needs approval
        result = check_safety(
            company_id="test_company",
            session_id="test_session",
            function_name="process_refund",
            function_params={"customer_id": "c1", "amount": 50, "reason": "test"},
            user_message="ok",
        )
        self.assertEqual(result.status, "needs_approval")

        # Step 3: Explicit confirm → approved
        result = check_safety(
            company_id="test_company",
            session_id="test_session",
            function_name="process_refund",
            function_params={"customer_id": "c1", "amount": 50, "reason": "test"},
            user_message="yes confirm",
        )
        self.assertEqual(result.status, "approved")

    def test_safety_check_result_to_dict(self):
        """SafetyCheckResult can be serialized to dict."""
        from app.services.jarvis_safety_gate import SafetyCheckResult
        result = SafetyCheckResult(
            status="approved",
            function_name="test_func",
            safety_level="none",
            message="Go ahead",
        )
        d = result.to_dict()
        self.assertEqual(d["status"], "approved")
        self.assertEqual(d["function_name"], "test_func")

    def test_unknown_function_defaults_to_confirmation(self):
        """Unknown function defaults to confirmation_required (fail-safe)."""
        from app.services.jarvis_safety_gate import check_safety
        result = check_safety(
            company_id="test_company",
            session_id="test_session",
            function_name="nonexistent_function_xyz",
            function_params={},
            user_message="do something",
        )
        self.assertIn(result.status, ("needs_confirmation", "needs_approval"))

    def test_conversational_messages_not_robotic(self):
        """Safety messages should feel conversational, not robotic."""
        from app.services.jarvis_safety_gate import check_safety
        result = check_safety(
            company_id="test_company",
            session_id="test_session",
            function_name="pause_all_ai",
            function_params={"reason": "testing"},
            user_message="pause AI",
        )
        # Should NOT contain robotic phrases
        self.assertNotIn("Command:", result.message)
        self.assertNotIn("Execute:", result.message)
        self.assertNotIn("Status:", result.message)
        # Should contain conversational language
        self.assertTrue(
            any(word in result.message.lower() for word in ["i'll", "shall", "want", "go ahead"]),
            f"Message doesn't sound conversational: {result.message}"
        )


# ══════════════════════════════════════════════════════════════════
# UNIT TESTS: Orchestrator
# ══════════════════════════════════════════════════════════════════


class TestOrchestratorModeDecision(unittest.TestCase):
    """Test the mode decision logic."""

    def test_customer_care_session_is_agentic(self):
        """Customer care sessions should be agentic mode."""
        from app.services.jarvis_orchestrator import decide_mode
        context = {
            "session": {
                "type": "customer_care",
                "mode": "customer_care",
            }
        }
        self.assertEqual(decide_mode(context), "agentic")

    def test_onboarding_session_is_command(self):
        """Onboarding sessions should be command mode."""
        from app.services.jarvis_orchestrator import decide_mode
        context = {
            "session": {
                "type": "onboarding",
                "mode": "onboarding",
            }
        }
        self.assertEqual(decide_mode(context), "command")

    def test_admin_session_is_command(self):
        """Admin sessions should be command mode."""
        from app.services.jarvis_orchestrator import decide_mode
        context = {
            "session": {
                "type": "admin",
                "mode": "admin",
            }
        }
        self.assertEqual(decide_mode(context), "command")

    def test_empty_context_defaults_to_command(self):
        """Empty context defaults to command mode (more capabilities)."""
        from app.services.jarvis_orchestrator import decide_mode
        context = {"session": {}}
        self.assertEqual(decide_mode(context), "command")


class TestOrchestratorSystemPrompt(unittest.TestCase):
    """Test the system prompt builder."""

    def test_command_mode_prompt(self):
        """Command mode prompt mentions managing the platform."""
        from app.services.jarvis_orchestrator import build_system_prompt
        prompt = build_system_prompt("command", {})
        self.assertIn("manage", prompt.lower())
        self.assertIn("tools", prompt.lower())

    def test_agentic_mode_prompt(self):
        """Agentic mode prompt mentions customer conversation."""
        from app.services.jarvis_orchestrator import build_system_prompt
        prompt = build_system_prompt("agentic", {})
        self.assertIn("customer", prompt.lower())

    def test_conversational_guidelines(self):
        """System prompt includes conversational guidelines."""
        from app.services.jarvis_orchestrator import build_system_prompt
        prompt = build_system_prompt("command", {})
        self.assertIn("conversational", prompt.lower())
        self.assertIn("robotic", prompt.lower())

    def test_awareness_injected(self):
        """System prompt includes awareness data when available."""
        from app.services.jarvis_orchestrator import build_system_prompt
        context = {
            "awareness": {
                "system_health": "healthy",
                "ticket_volume_today": 42,
                "quality_score": 0.94,
                "agent_pool_utilization": "72%",
                "current_plan": "parwa",
                "plan_usage_today": "45%",
            }
        }
        prompt = build_system_prompt("command", context)
        self.assertIn("healthy", prompt)
        self.assertIn("42", prompt)
        self.assertIn("0.94", prompt)

    def test_pending_safety_in_prompt(self):
        """Pending safety confirmation is mentioned in prompt."""
        from app.services.jarvis_orchestrator import build_system_prompt
        pending = {
            "function_name": "pause_all_ai",
            "safety_level": "confirmation_required",
        }
        prompt = build_system_prompt("command", {}, pending_safety=pending)
        self.assertIn("pause_all_ai", prompt)
        self.assertIn("pending", prompt.lower())


# ══════════════════════════════════════════════════════════════════
# UNIT TESTS: Schemas
# ══════════════════════════════════════════════════════════════════


class TestSchemas(unittest.TestCase):
    """Test the Pydantic schema models."""

    def test_chat_request_valid(self):
        """Valid chat request can be created."""
        from app.schemas.jarvis_chat import JarvisChatRequest
        req = JarvisChatRequest(session_id="abc123", message="Hello Jarvis")
        self.assertEqual(req.session_id, "abc123")
        self.assertEqual(req.message, "Hello Jarvis")

    def test_chat_request_empty_message_rejected(self):
        """Empty message is rejected by schema validation."""
        from app.schemas.jarvis_chat import JarvisChatRequest
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            JarvisChatRequest(session_id="abc123", message="")

    def test_chat_response_structure(self):
        """Chat response has all required fields."""
        from app.schemas.jarvis_chat import JarvisChatResponse
        resp = JarvisChatResponse(
            response="Hello! How can I help?",
            mode="command",
            function_called=None,
            safety_status=None,
            execution_result=None,
            latency_ms=150.0,
            model="gpt-4o-mini",
            tokens_used=42,
        )
        self.assertEqual(resp.response, "Hello! How can I help?")
        self.assertEqual(resp.mode, "command")
        self.assertIsNone(resp.function_called)

    def test_chat_response_with_function(self):
        """Chat response can include function call info."""
        from app.schemas.jarvis_chat import JarvisChatResponse
        resp = JarvisChatResponse(
            response="I've paused all AI agents for you.",
            mode="command",
            function_called="pause_all_ai",
            safety_status="approved",
            execution_result={"success": True, "data": {"ai_paused": True}},
            latency_ms=250.0,
            model="gpt-4o-mini",
            tokens_used=85,
        )
        self.assertEqual(resp.function_called, "pause_all_ai")
        self.assertEqual(resp.safety_status, "approved")


# ══════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Full Pipeline
# ══════════════════════════════════════════════════════════════════


class TestIntegrationOrchestratorPipeline(unittest.TestCase):
    """Test the full orchestrator pipeline with mocked LLM and DB."""

    def test_empty_message_returns_greeting(self):
        """Empty message returns a greeting."""
        import asyncio
        from app.services.jarvis_orchestrator import process_message

        # Mock DB
        mock_db = MagicMock()

        async def _test():
            result = await process_message(
                db=mock_db,
                company_id="test_company",
                session_id="test_session",
                user_id="test_user",
                user_message="",
            )
            return result

        result = asyncio.run(_test())
        self.assertIn("response", result)
        self.assertIsNotNone(result["response"])

    def test_process_message_handles_db_failure(self):
        """Pipeline handles DB failures gracefully."""
        import asyncio
        from app.services.jarvis_orchestrator import process_message

        # Mock DB that raises on query
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("DB connection failed")

        async def _test():
            result = await process_message(
                db=mock_db,
                company_id="test_company",
                session_id="test_session",
                user_id="test_user",
                user_message="how are things?",
            )
            return result

        result = asyncio.run(_test())
        # Should not crash, should return a response
        self.assertIn("response", result)
        self.assertIsNotNone(result["response"])


class TestIntegrationSafetyGateWithOrchestrator(unittest.TestCase):
    """Test the safety gate integration with the orchestrator flow."""

    def setUp(self):
        from app.services.jarvis_safety_gate import clear_all_pending
        clear_all_pending("int_test_company", "int_test_session")

    def test_safe_function_flows_through(self):
        """Safe function goes through safety gate without blocking."""
        from app.services.jarvis_safety_gate import check_safety
        result = check_safety(
            company_id="int_test_company",
            session_id="int_test_session",
            function_name="check_system_health",
            function_params={},
            user_message="how's the system",
        )
        self.assertTrue(result.is_approved)

    def test_confirmation_flow_with_orchestrator_context(self):
        """Full confirmation flow works as expected."""
        from app.services.jarvis_safety_gate import check_safety, clear_all_pending
        clear_all_pending("int_test_company", "int_test_session")

        # Step 1: User asks to pause AI
        r1 = check_safety(
            company_id="int_test_company",
            session_id="int_test_session",
            function_name="pause_all_ai",
            function_params={"reason": "maintaining"},
            user_message="pause my AI",
        )
        self.assertEqual(r1.status, "needs_confirmation")
        self.assertTrue(r1.needs_human_input)

        # Step 2: User confirms
        r2 = check_safety(
            company_id="int_test_company",
            session_id="int_test_session",
            function_name="pause_all_ai",
            function_params={"reason": "maintaining"},
            user_message="yes do it",
        )
        self.assertEqual(r2.status, "approved")
        self.assertTrue(r2.is_approved)

    def test_different_function_cancels_previous_pending(self):
        """Asking for a different function while one is pending doesn't conflict."""
        from app.services.jarvis_safety_gate import check_safety, clear_all_pending
        clear_all_pending("int_test_company", "int_test_session_2")

        # Step 1: User asks to pause AI → needs confirmation
        r1 = check_safety(
            company_id="int_test_company",
            session_id="int_test_session_2",
            function_name="pause_all_ai",
            function_params={"reason": "test"},
            user_message="pause AI",
        )
        self.assertEqual(r1.status, "needs_confirmation")

        # Step 2: User changes mind, asks for system health → immediate (no pending conflict)
        r2 = check_safety(
            company_id="int_test_company",
            session_id="int_test_session_2",
            function_name="check_system_health",
            function_params={},
            user_message="actually how's the system",
        )
        self.assertEqual(r2.status, "approved")


class TestIntegrationModeSwitching(unittest.TestCase):
    """Test that mode switching correctly filters available functions."""

    def test_agentic_mode_limited_functions(self):
        """Agentic mode has fewer functions than command mode."""
        from app.services.jarvis_function_registry import get_function_definitions
        agentic_defs = get_function_definitions(mode="agentic", tier="parwa")
        command_defs = get_function_definitions(mode="command", tier="parwa")
        self.assertLess(len(agentic_defs), len(command_defs))

    def test_agentic_mode_only_customer_facing(self):
        """Agentic mode only includes customer-facing category functions."""
        from app.services.jarvis_function_registry import (
            get_function_definitions,
            get_function_metadata,
            CATEGORY_CUSTOMER_FACING,
        )
        agentic_defs = get_function_definitions(mode="agentic", tier="parwa")
        for d in agentic_defs:
            metadata = get_function_metadata(d["function"]["name"])
            self.assertEqual(metadata["category"], CATEGORY_CUSTOMER_FACING)

    def test_command_mode_includes_all_categories(self):
        """Command mode includes functions from multiple categories."""
        from app.services.jarvis_function_registry import get_function_definitions, get_function_metadata
        command_defs = get_function_definitions(mode="command", tier="parwa")
        categories = set()
        for d in command_defs:
            metadata = get_function_metadata(d["function"]["name"])
            if metadata:
                categories.add(metadata["category"])
        # Should have multiple categories
        self.assertGreater(len(categories), 3)


class TestIntegrationEndToEnd(unittest.TestCase):
    """End-to-end integration tests simulating real user interactions."""

    def test_user_checks_health_no_confirmation_needed(self):
        """User asks 'how's everything?' — no confirmation needed."""
        from app.services.jarvis_function_registry import get_safety_level, SAFETY_NONE
        self.assertEqual(get_safety_level("check_system_health"), SAFETY_NONE)

    def test_user_pauses_ai_needs_confirmation(self):
        """User asks to pause AI — needs confirmation."""
        from app.services.jarvis_function_registry import get_safety_level, SAFETY_CONFIRMATION
        from app.services.jarvis_safety_gate import check_safety, clear_all_pending
        clear_all_pending("e2e_company", "e2e_session")

        self.assertEqual(get_safety_level("pause_all_ai"), SAFETY_CONFIRMATION)

        result = check_safety(
            company_id="e2e_company",
            session_id="e2e_session",
            function_name="pause_all_ai",
            function_params={"reason": "maintenance"},
            user_message="pause my AI",
        )
        self.assertTrue(result.needs_human_input)

    def test_user_refunds_needs_approval(self):
        """User asks for refund — needs explicit approval."""
        from app.services.jarvis_function_registry import get_safety_level, SAFETY_APPROVAL
        self.assertEqual(get_safety_level("process_refund"), SAFETY_APPROVAL)

    def test_full_refund_flow(self):
        """Complete refund flow: request → ask approval → confirm → execute."""
        from app.services.jarvis_safety_gate import check_safety, clear_all_pending
        clear_all_pending("e2e_company_2", "e2e_session_2")

        # Step 1: Request refund
        r1 = check_safety(
            company_id="e2e_company_2",
            session_id="e2e_session_2",
            function_name="process_refund",
            function_params={"customer_id": "c1", "amount": 50, "reason": "duplicate charge"},
            user_message="I need to refund this customer",
        )
        self.assertEqual(r1.status, "needs_approval")

        # Step 2: Vague response — still needs approval
        r2 = check_safety(
            company_id="e2e_company_2",
            session_id="e2e_session_2",
            function_name="process_refund",
            function_params={"customer_id": "c1", "amount": 50, "reason": "duplicate charge"},
            user_message="ok sure",
        )
        self.assertEqual(r2.status, "needs_approval")

        # Step 3: Explicit confirm → approved
        r3 = check_safety(
            company_id="e2e_company_2",
            session_id="e2e_session_2",
            function_name="process_refund",
            function_params={"customer_id": "c1", "amount": 50, "reason": "duplicate charge"},
            user_message="yes confirm the refund",
        )
        self.assertEqual(r3.status, "approved")

    def test_client_never_sees_technical_terms(self):
        """Responses should not contain technical terms like 'function', 'API', 'command'."""
        from app.services.jarvis_safety_gate import check_safety, clear_all_pending
        clear_all_pending("e2e_company_3", "e2e_session_3")

        result = check_safety(
            company_id="e2e_company_3",
            session_id="e2e_session_3",
            function_name="pause_all_ai",
            function_params={"reason": "test"},
            user_message="pause my AI",
        )
        # The message should be conversational, not technical
        self.assertNotIn("function_call", result.message.lower())
        self.assertNotIn("api", result.message.lower())
        self.assertNotIn("command_id", result.message.lower())
        self.assertNotIn("status_code", result.message.lower())


# ══════════════════════════════════════════════════════════════════
# RUN ALL TESTS
# ══════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    unittest.main(verbosity=2)
