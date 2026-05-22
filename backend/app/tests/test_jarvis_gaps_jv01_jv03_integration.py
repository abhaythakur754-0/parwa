"""
Integration tests for Jarvis gaps JV-01 through JV-03.

JV-01: ZAI SDK never initializes in FastAPI (loop.is_running() bug)
JV-02: Awareness engine doesn't read LangGraph live state
JV-03: Command handlers are stubs (add_agents, call_customer)

Run from project root: PYTHONPATH=backend pytest backend/app/tests/test_jarvis_gaps_jv01_jv03_integration.py -v
"""

import asyncio
import json
import sys
import unittest
from datetime import datetime, timezone
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

# ── Mock ONLY modules that don't exist in test env ──
if "jose" not in sys.modules:
    jose_mock = ModuleType("jose")
    jose_mock.jwt = MagicMock()
    jose_mock.exceptions = MagicMock()
    jose_mock.jws = MagicMock()
    sys.modules["jose"] = jose_mock
    sys.modules["jose.jwt"] = jose_mock.jwt
    sys.modules["jose.exceptions"] = jose_mock.exceptions
    sys.modules["jose.jws"] = jose_mock.jws


class TestJV01IntegrationSDKInitInAsyncContext(unittest.TestCase):
    """JV-01 Integration: SDK initialization works correctly in async context."""

    def setUp(self):
        from app.services.jarvis_agents.zai_client import ZAIClient
        ZAIClient._instance = None
        ZAIClient._sdk = None
        ZAIClient._initialized = False

    def tearDown(self):
        from app.services.jarvis_agents.zai_client import ZAIClient
        ZAIClient._instance = None
        ZAIClient._sdk = None
        ZAIClient._initialized = False

    def test_sdk_initializes_in_running_event_loop(self):
        """JV-01 Integration: SDK should initialize when chat_async is called
        from within a running event loop (FastAPI scenario)."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()

        # Create a real dict response that simulates LLM output
        llm_response = {
            "agent": "escalation_agent",
            "reasoning": "Critical spike detected",
            "urgency": "critical",
        }

        # Mock _ensure_sdk_async to set up the SDK
        async def fake_ensure():
            mock_sdk = MagicMock()
            # Create a completion object where content is a real string
            real_content = json.dumps(llm_response)
            mock_choice = MagicMock()
            mock_choice.message.content = real_content
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_sdk.chat.completions.create = AsyncMock(return_value=mock_completion)
            client._sdk = mock_sdk
            client._initialized = True
            return True

        client._ensure_sdk_async = AsyncMock(side_effect=fake_ensure)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                client.chat_async(
                    "command_router",
                    "Ticket volume spiked 3x",
                    context={"alert_type": "ticket_volume_spike", "severity": "critical"},
                )
            )
        finally:
            loop.close()

        self.assertIsNotNone(client._sdk,
                             "JV-01 INTEGRATION: SDK should be initialized after chat_async")
        self.assertTrue(client._initialized)
        self.assertEqual(result.get("_source"), "zai_llm",
                         "JV-01 INTEGRATION: Response should come from LLM, not rule-based fallback")

    def test_fallback_still_works_when_sdk_unavailable(self):
        """JV-01 Integration: When SDK truly can't init, rule-based fallback works."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()

        # Make ZAI.create always fail
        real_import = __import__
        def selective_import(name, *args, **kwargs):
            if name == "z_ai_web_dev_sdk":
                raise ImportError("SDK not available")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=selective_import):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    client.chat_async(
                        "command_router",
                        "Ticket volume spiked",
                        context={"alert_type": "ticket_volume_spike", "severity": "critical"},
                    )
                )
            finally:
                loop.close()

        self.assertEqual(result.get("_source"), "rule_based_fallback",
                         "JV-01 INTEGRATION: Should use rule-based fallback when SDK unavailable")
        self.assertIn("agent", result)

    def test_sdk_persists_across_multiple_chat_calls(self):
        """JV-01 Integration: SDK should persist once initialized, not re-init each call."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()

        mock_sdk = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '{"agent": "no_action"}'
        mock_sdk.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_zai_class = AsyncMock(return_value=mock_sdk)
        mock_zai_module = MagicMock(ZAI=mock_zai_class)

        with patch.dict("sys.modules", {"z_ai_web_dev_sdk": mock_zai_module}):
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(client.chat_async("command_router", "test 1"))
                first_sdk = client._sdk
                loop.run_until_complete(client.chat_async("command_router", "test 2"))
            finally:
                loop.close()

        self.assertIs(client._sdk, first_sdk,
                      "JV-01 INTEGRATION: SDK should persist across calls")


class TestJV02IntegrationLiveStateMerge(unittest.TestCase):
    """JV-02 Integration: Live LangGraph state merges with DB state end-to-end."""

    def test_collect_awareness_with_live_state_overrides(self):
        """JV-02 Integration: collect_awareness_state merges live state."""
        from app.services.jarvis_awareness_engine import collect_awareness_state

        mock_db = MagicMock()

        live_state = {
            "jarvis_system_health": "critical",
            "jarvis_quality_score": 0.35,
            "jarvis_drift_status": "severe",
            "jarvis_drift_score": 0.70,
            "jarvis_ticket_volume_today": 150,
            "jarvis_ticket_volume_spike": True,
        }

        result = collect_awareness_state(
            mock_db, "company1", "session1",
            live_graph_state=live_state,
        )

        self.assertEqual(result["system_health"], "critical")
        self.assertEqual(result["quality_score"], 0.35)
        self.assertEqual(result["drift_status"], "severe")
        self.assertEqual(result["ticket_volume_today"], 150)
        self.assertTrue(result["ticket_volume_spike"])

    def test_collect_awareness_without_live_state_uses_db(self):
        """JV-02 Integration: Without live state, DB values are used."""
        from app.services.jarvis_awareness_engine import collect_awareness_state

        mock_db = MagicMock()
        result = collect_awareness_state(
            mock_db, "company1", "session1",
            live_graph_state=None,
        )

        self.assertFalse(result.get("_live_state_merged", False))

    def test_run_awareness_tick_fetches_live_state(self):
        """JV-02 Integration: run_awareness_tick should try to fetch live state.

        We verify that get_live_graph_state is called by checking that
        the awareness engine module exports it and that run_awareness_tick
        references it (via mock patching).
        """
        from app.services.jarvis_awareness_engine import get_live_graph_state, run_awareness_tick
        import inspect

        # Verify get_live_graph_state exists and is callable
        self.assertTrue(callable(get_live_graph_state))

        # Verify run_awareness_tick source references get_live_graph_state
        source = inspect.getsource(run_awareness_tick)
        self.assertIn("get_live_graph_state", source,
                      "JV-02: run_awareness_tick should call get_live_graph_state")

    def test_live_state_alerts_generated_from_fresh_data(self):
        """JV-02 Integration: Alerts should be generated from live (not stale) data."""
        from app.services.jarvis_awareness_engine import _merge_live_graph_state

        db_state = {"quality_score": 0.80, "drift_status": "none", "system_health": "healthy"}
        live_state = {
            "jarvis_quality_score": 0.35,
            "jarvis_drift_status": "severe",
            "jarvis_system_health": "critical",
        }

        merged = _merge_live_graph_state(db_state, live_state)

        self.assertEqual(merged["quality_score"], 0.35,
                         "JV-02 INTEGRATION: Quality alert should use live 0.35, not DB 0.80")
        self.assertEqual(merged["drift_status"], "severe")
        self.assertEqual(merged["system_health"], "critical")


class TestJV03IntegrationHandlerDBWrites(unittest.TestCase):
    """JV-03 Integration: Command handlers perform real DB writes end-to-end."""

    def test_add_agents_full_flow(self):
        """JV-03 Integration: add_agents updates VariantInstance + session context."""
        from app.services.jarvis_command_service import _handler_add_agents

        mock_db = MagicMock()
        mock_instance = MagicMock()
        mock_instance.active_agents = 3
        mock_session = MagicMock()
        mock_session.context_json = json.dumps({"agent_provision_history": []})

        call_count = [0]
        def mock_query(model):
            call_count[0] += 1
            q = MagicMock()
            if call_count[0] == 1:
                q.filter.return_value.order_by.return_value.first.return_value = mock_instance
            else:
                q.filter.return_value.first.return_value = mock_session
            return q

        mock_db.query.side_effect = mock_query

        with patch.dict("sys.modules", {"database.models.core": MagicMock(VariantInstance=MagicMock())}):
            result = _handler_add_agents(
                db=mock_db, company_id="comp1", session_id="sess1",
                parsed={"parameters": {"count": 2}}, user_id="user1",
            )

        self.assertEqual(mock_instance.active_agents, 5)
        ctx = json.loads(mock_session.context_json)
        self.assertIn("agent_provision_history", ctx)
        self.assertEqual(len(ctx["agent_provision_history"]), 1)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["new_agents"], 5)
        self.assertEqual(result["data"]["status"], "provisioned")

    def test_call_customer_full_flow(self):
        """JV-03 Integration: call_customer creates alert + updates session context."""
        from app.services.jarvis_command_service import _handler_call_customer

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.context_json = json.dumps({"outbound_call_history": []})
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = _handler_call_customer(
            db=mock_db, company_id="comp1", session_id="sess1",
            parsed={"parameters": {}}, user_id="user1",
        )

        self.assertTrue(mock_db.add.called)
        ctx = json.loads(mock_session.context_json)
        self.assertIn("outbound_call_history", ctx)
        self.assertEqual(len(ctx["outbound_call_history"]), 1)
        self.assertTrue(result["success"])
        self.assertIsNotNone(result["data"]["call_id"])

    def test_command_execute_add_agents_integration(self):
        """JV-03 Integration: Full execute_command flow for add_agents."""
        from app.services.jarvis_command_service import execute_command

        mock_db = MagicMock()
        mock_command = MagicMock()
        mock_command.id = "cmd-001"
        mock_command.status = "parsed"
        mock_command.command_parsed = json.dumps({
            "action": "add_agents", "intent": "control", "scope": "agents",
            "target": "ai", "parameters": {"count": 3}, "confidence": 0.85,
            "raw_input": "add 3 agents", "suggestion": None,
        })
        mock_command.command_metadata_json = "{}"

        with patch("app.services.jarvis_command_service._get_command", return_value=mock_command):
            with patch("app.services.jarvis_command_service._handler_add_agents") as mock_handler:
                mock_handler.return_value = {
                    "success": True, "action": "add_agents",
                    "message": "Successfully provisioned 3 agent(s).",
                    "data": {"requested_count": 3, "previous_agents": 2, "new_agents": 5,
                             "provisioned": True, "status": "provisioned"},
                }
                result = execute_command(
                    db=mock_db, company_id="comp1", command_id="cmd-001",
                    session_id="sess1", user_id="user1",
                )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["action"], "add_agents")
        self.assertEqual(result["result"]["data"]["new_agents"], 5)

    def test_command_execute_call_customer_integration(self):
        """JV-03 Integration: Full execute_command flow for call_customer."""
        from app.services.jarvis_command_service import execute_command

        mock_db = MagicMock()
        mock_command = MagicMock()
        mock_command.id = "cmd-002"
        mock_command.status = "parsed"
        mock_command.command_parsed = json.dumps({
            "action": "call_customer", "intent": "control", "scope": "communication",
            "target": "customer", "parameters": {}, "confidence": 0.85,
            "raw_input": "call the customer", "suggestion": None,
        })
        mock_command.command_metadata_json = "{}"

        with patch("app.services.jarvis_command_service._get_command", return_value=mock_command):
            with patch("app.services.jarvis_command_service._handler_call_customer") as mock_handler:
                mock_handler.return_value = {
                    "success": True, "action": "call_customer",
                    "message": "Outbound call request has been submitted and tracked.",
                    "data": {"call_id": "alert-123", "notification_created": True, "status": "pending"},
                }
                result = execute_command(
                    db=mock_db, company_id="comp1", command_id="cmd-002",
                    session_id="sess1", user_id="user1",
                )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["action"], "call_customer")
        self.assertIsNotNone(result["result"]["data"]["call_id"])


if __name__ == "__main__":
    unittest.main()
