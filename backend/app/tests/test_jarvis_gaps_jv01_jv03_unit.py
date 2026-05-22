"""
Unit tests for Jarvis gaps JV-01 through JV-03.

JV-01: ZAI SDK never initializes in FastAPI (loop.is_running() bug)
JV-02: Awareness engine doesn't read LangGraph live state
JV-03: Command handlers are stubs (add_agents, call_customer)

Run from project root: PYTHONPATH=backend pytest backend/app/tests/test_jarvis_gaps_jv01_jv03_unit.py -v
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


class TestJV01ZAIClientSDKInit(unittest.TestCase):
    """JV-01: ZAI SDK never initializes in FastAPI.

    Bug: _ensure_sdk() set self._sdk=None, self._initialized=True when
    loop.is_running(), permanently blocking SDK init in FastAPI.

    Fix: _ensure_sdk() now sets self._initialized=False when in a running
    loop, and chat_async() calls _ensure_sdk_async() which properly
    initializes the SDK using await ZAI.create().
    """

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

    def test_ensure_sdk_marks_uninitialized_when_loop_running(self):
        """JV-01: _ensure_sdk() should NOT permanently mark initialized in running loop."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()

        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = True
            mock_get_loop.return_value = mock_loop
            result = client._ensure_sdk()

        self.assertFalse(result)
        self.assertFalse(client._initialized,
                         "JV-01: _initialized should be False, not True, "
                         "so chat_async can retry via _ensure_sdk_async")

    def test_ensure_sdk_async_initializes_properly(self):
        """JV-01: _ensure_sdk_async() should initialize SDK using await."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()
        mock_sdk = MagicMock()
        mock_zai_module = MagicMock()
        mock_zai_module.ZAI = AsyncMock(return_value=mock_sdk)

        with patch.dict("sys.modules", {"z_ai_web_dev_sdk": mock_zai_module}):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(client._ensure_sdk_async())
            finally:
                loop.close()

        self.assertTrue(result)
        self.assertIsNotNone(client._sdk)
        self.assertTrue(client._initialized)

    def test_ensure_sdk_async_handles_failure_gracefully(self):
        """JV-01: _ensure_sdk_async() should handle errors gracefully."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()

        # Use a side_effect function that only raises for z_ai_web_dev_sdk
        real_import = __import__
        def selective_import(name, *args, **kwargs):
            if name == "z_ai_web_dev_sdk":
                raise ImportError("no module")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=selective_import):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(client._ensure_sdk_async())
            finally:
                loop.close()

        self.assertFalse(result)
        self.assertIsNone(client._sdk)
        self.assertTrue(client._initialized)

    def test_old_bug_sdk_permanently_none_in_running_loop(self):
        """JV-01 regression: Verify the OLD behavior is fixed."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()

        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = True
            mock_get_loop.return_value = mock_loop
            client._ensure_sdk()

        self.assertFalse(client._initialized,
                         "JV-01 REGRESSION: _initialized should be False "
                         "after loop.is_running(), not True (old bug)")

    def test_chat_async_calls_ensure_sdk_async(self):
        """JV-01: chat_async should call _ensure_sdk_async, not _ensure_sdk."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()
        client._sdk = None
        client._initialized = False

        async def fake_ensure_sdk_async():
            client._sdk = MagicMock()
            client._sdk.chat.completions.create = AsyncMock(return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content='{"agent":"test"}'))]
            ))
            client._initialized = True
            return True

        client._ensure_sdk_async = AsyncMock(side_effect=fake_ensure_sdk_async)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(client.chat_async("command_router", "test message"))
        finally:
            loop.close()

        client._ensure_sdk_async.assert_called()


class TestJV02AwarenessEngineLiveState(unittest.TestCase):
    """JV-02: Awareness engine doesn't read LangGraph live state.

    Bug: collect_awareness_state() only queries DB — stale data.
    Fix: Added live_graph_state parameter, _merge_live_graph_state(), get_live_graph_state().
    """

    def test_collect_awareness_state_accepts_live_graph_state(self):
        """JV-02: collect_awareness_state should accept live_graph_state param."""
        from app.services.jarvis_awareness_engine import collect_awareness_state
        import inspect

        sig = inspect.signature(collect_awareness_state)
        params = list(sig.parameters.keys())
        self.assertIn("live_graph_state", params)

    def test_merge_live_graph_state_overrides_db_values(self):
        """JV-02: Live state should take precedence over DB values."""
        from app.services.jarvis_awareness_engine import _merge_live_graph_state

        db_state = {
            "system_health": "healthy",
            "quality_score": 0.75,
            "drift_score": 0.10,
            "ticket_volume_today": 42,
        }
        live_state = {
            "jarvis_system_health": "critical",
            "jarvis_quality_score": 0.45,
            "jarvis_drift_score": 0.55,
            "jarvis_ticket_volume_today": 87,
        }

        merged = _merge_live_graph_state(db_state, live_state)

        self.assertEqual(merged["system_health"], "critical")
        self.assertEqual(merged["quality_score"], 0.45)
        self.assertEqual(merged["drift_score"], 0.55)
        self.assertEqual(merged["ticket_volume_today"], 87)

    def test_merge_marks_live_state_merged_flag(self):
        """JV-02: Merged state should set _live_state_merged flag."""
        from app.services.jarvis_awareness_engine import _merge_live_graph_state

        db_state = {"system_health": "healthy"}
        live_state = {"jarvis_system_health": "critical"}

        merged = _merge_live_graph_state(db_state, live_state)

        self.assertTrue(merged["_live_state_merged"])
        self.assertIn("system_health", merged["_live_state_keys"])

    def test_merge_handles_empty_live_state(self):
        """JV-02: Empty live state should not modify DB values."""
        from app.services.jarvis_awareness_engine import _merge_live_graph_state

        db_state = {"system_health": "healthy", "quality_score": 0.85}
        merged = _merge_live_graph_state(db_state, {})

        self.assertFalse(merged["_live_state_merged"])
        self.assertEqual(merged["system_health"], "healthy")
        self.assertEqual(merged["quality_score"], 0.85)

    def test_merge_handles_none_values_in_live_state(self):
        """JV-02: None values in live state should NOT override DB values."""
        from app.services.jarvis_awareness_engine import _merge_live_graph_state

        db_state = {"system_health": "healthy", "quality_score": 0.85}
        live_state = {"jarvis_system_health": None, "jarvis_quality_score": 0.50}

        merged = _merge_live_graph_state(db_state, live_state)

        self.assertEqual(merged["system_health"], "healthy")
        self.assertEqual(merged["quality_score"], 0.50)

    def test_merge_handles_all_group14_fields(self):
        """JV-02: All GROUP 14 fields should be mappable."""
        from app.services.jarvis_awareness_engine import _merge_live_graph_state

        db_state = {
            "system_health": "healthy", "channel_health": {},
            "active_alerts": [], "ticket_volume_today": 10,
            "ticket_volume_avg": 8.0, "ticket_volume_spike": False,
            "active_agents": 3, "agent_pool_capacity": 5,
            "agent_pool_utilization": 60.0, "training_running": False,
            "training_mistake_count": 0, "training_model_version": "",
            "drift_status": "none", "drift_score": 0.0,
            "quality_score": 0.80, "quality_alerts": [],
            "last_5_errors": [], "subscription_status": "active",
            "current_plan": "mini_parwa", "plan_usage_today": 50.0,
            "days_until_renewal": 30,
        }
        live_state = {
            "jarvis_system_health": "degraded",
            "jarvis_channel_health": {"email": "down"},
            "jarvis_active_alerts": [{"type": "spike"}],
            "jarvis_ticket_volume_today": 25,
            "jarvis_ticket_volume_avg": 12.0,
            "jarvis_ticket_volume_spike": True,
            "jarvis_active_agents": 5,
            "jarvis_agent_pool_capacity": 10,
            "jarvis_agent_pool_utilization": 50.0,
            "jarvis_training_running": True,
            "jarvis_training_mistake_count": 3,
            "jarvis_training_model_version": "v2",
            "jarvis_drift_status": "slight",
            "jarvis_drift_score": 0.15,
            "jarvis_quality_score": 0.65,
            "jarvis_quality_alerts": [{"level": "warn"}],
            "jarvis_last_5_errors": [{"error": "timeout"}],
            "jarvis_subscription_status": "past_due",
            "jarvis_current_plan": "mega_parwa",
            "jarvis_plan_usage_today": 92.0,
            "jarvis_days_until_renewal": 2,
        }

        merged = _merge_live_graph_state(db_state, live_state)

        self.assertEqual(merged["system_health"], "degraded")
        self.assertEqual(merged["ticket_volume_spike"], True)
        self.assertEqual(merged["active_agents"], 5)
        self.assertEqual(merged["training_running"], True)
        self.assertEqual(merged["quality_score"], 0.65)
        self.assertEqual(merged["subscription_status"], "past_due")
        self.assertTrue(merged["_live_state_merged"])
        self.assertEqual(len(merged["_live_state_keys"]), 21)

    def test_get_live_graph_state_in_all_exports(self):
        """JV-02: get_live_graph_state should be in __all__."""
        from app.services.jarvis_awareness_engine import __all__
        self.assertIn("get_live_graph_state", __all__)


class TestJV03CommandHandlerStubs(unittest.TestCase):
    """JV-03: Command handlers may be stubs.

    Bug: add_agents and call_customer return status dicts without actual DB writes.
    Fix: Both now write to DB (VariantInstance, JarvisProactiveAlert, session context).
    """

    def test_add_agents_handler_updates_variant_instance(self):
        """JV-03: add_agents should write to VariantInstance in DB."""
        from app.services.jarvis_command_service import _handler_add_agents

        mock_db = MagicMock()
        mock_instance = MagicMock()
        mock_instance.active_agents = 3
        mock_session = MagicMock()
        mock_session.context_json = "{}"

        # First query: VariantInstance, second query: JarvisSession
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

        # Patch the import inside the handler so VariantInstance is found
        with patch.dict("sys.modules", {"database.models.core": MagicMock(VariantInstance=MagicMock())}):
            result = _handler_add_agents(
                db=mock_db, company_id="comp1", session_id="sess1",
                parsed={"parameters": {"count": 2}}, user_id="user1",
            )

        self.assertEqual(mock_instance.active_agents, 5,
                         "JV-03: add_agents should increment active_agents")
        mock_db.flush.assert_called()

    def test_add_agents_handler_returns_provisioned_status(self):
        """JV-03: add_agents result should indicate actual provisioning."""
        from app.services.jarvis_command_service import _handler_add_agents

        mock_db = MagicMock()
        mock_instance = MagicMock()
        mock_instance.active_agents = 3
        mock_session = MagicMock()
        mock_session.context_json = "{}"

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

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["provisioned"], True)
        self.assertEqual(result["data"]["new_agents"], 5)
        self.assertEqual(result["data"]["status"], "provisioned")

    def test_add_agents_handler_handles_missing_model(self):
        """JV-03: add_agents should handle VariantInstance not found."""
        from app.services.jarvis_command_service import _handler_add_agents

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = _handler_add_agents(
            db=mock_db, company_id="comp1", session_id="sess1",
            parsed={"parameters": {"count": 2}}, user_id="user1",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["provisioned"], False)
        self.assertEqual(result["data"]["status"], "pending")

    def test_call_customer_handler_creates_alert(self):
        """JV-03: call_customer should create a JarvisProactiveAlert."""
        from app.services.jarvis_command_service import _handler_call_customer

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.context_json = "{}"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = _handler_call_customer(
            db=mock_db, company_id="comp1", session_id="sess1",
            parsed={"parameters": {}}, user_id="user1",
        )

        self.assertTrue(mock_db.add.called, "JV-03: call_customer should add alert to DB")
        mock_db.flush.assert_called()

    def test_call_customer_handler_returns_call_id(self):
        """JV-03: call_customer result should include a call_id."""
        from app.services.jarvis_command_service import _handler_call_customer

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.context_json = "{}"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = _handler_call_customer(
            db=mock_db, company_id="comp1", session_id="sess1",
            parsed={"parameters": {}}, user_id="user1",
        )

        self.assertTrue(result["success"])
        self.assertIsNotNone(result["data"]["call_id"])

    def test_call_customer_handler_updates_session_context(self):
        """JV-03: call_customer should write call audit to session context."""
        from app.services.jarvis_command_service import _handler_call_customer

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.context_json = "{}"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        _handler_call_customer(
            db=mock_db, company_id="comp1", session_id="sess1",
            parsed={"parameters": {}}, user_id="user1",
        )

        updated_ctx = json.loads(mock_session.context_json)
        self.assertIn("outbound_call_history", updated_ctx)
        self.assertEqual(len(updated_ctx["outbound_call_history"]), 1)
        self.assertIn("last_call_id", updated_ctx)


if __name__ == "__main__":
    unittest.main()
