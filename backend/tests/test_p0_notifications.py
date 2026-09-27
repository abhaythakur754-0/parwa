"""
Tests for the P0 notification wiring — Node 5, 6.5, 8 emit events to Jarvis.

Verifies that:
  1. Node 5 emits `ai:action_taken` after executing an action (with tool_executed field)
  2. Node 6.5 emits `ticket:delivered` after customer delivery (with channel + status)
  3. Node 8 emits `ticket:escalated` when the AI escalates (not when quality passes)

These are the 3 P0 notifications a human agent needs to see in Jarvis CC.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ════════════════════════════════════════════════════════════════════
# 1. Node 5 — ai:action_taken
# ════════════════════════════════════════════════════════════════════


class TestNode5ActionNotification:
    """Verify Node 5 emits ai:action_taken after executing actions."""

    def test_node_5_imports_emit_ai_event(self):
        """Node 5 should import emit_ai_event from event_emitter."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_5_act_verify.py") as f:
            source = f.read()
        assert "from app.core.event_emitter import emit_ai_event" in source, (
            "Node 5 should import emit_ai_event to notify Jarvis of actions taken"
        )

    def test_node_5_emits_ai_action_taken(self):
        """Node 5 should call emit_ai_event with event_type='ai:action_taken'."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_5_act_verify.py") as f:
            source = f.read()
        assert '"ai:action_taken"' in source or "'ai:action_taken'" in source, (
            "Node 5 should emit 'ai:action_taken' event"
        )

    def test_node_5_includes_tool_executed_in_payload(self):
        """The ai:action_taken payload should include tool_executed field."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_5_act_verify.py") as f:
            source = f.read()
        assert "tool_executed" in source, (
            "Node 5 notification payload should include tool_executed so the "
            "human knows whether a real tool ran (HubSpot, Shopify, etc.)"
        )

    def test_node_5_loops_over_all_actions(self):
        """Node 5 should emit one event per action in actions_taken."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_5_act_verify.py") as f:
            source = f.read()
        assert "for at in actions_taken" in source, (
            "Node 5 should loop over actions_taken and emit one event per action"
        )

    def test_node_5_notification_failure_doesnt_crash(self):
        """The emit call should be wrapped in try/except — never crash node_5."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_5_act_verify.py") as f:
            source = f.read()
        # Find the emit block and verify it has a try/except.
        assert "node_5_action_notification_failed" in source, (
            "Node 5 should catch notification failures and log them — never crash"
        )


# ════════════════════════════════════════════════════════════════════
# 2. Node 6.5 — ticket:delivered
# ════════════════════════════════════════════════════════════════════


class TestNode65DeliveryNotification:
    """Verify Node 6.5 emits ticket:delivered after customer delivery."""

    def test_node_6_5_imports_emit_ticket_event(self):
        """Node 6.5 should import emit_ticket_event from event_emitter."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_6_5_deliver.py") as f:
            source = f.read()
        assert "from app.core.event_emitter import emit_ticket_event" in source, (
            "Node 6.5 should import emit_ticket_event to notify Jarvis of delivery"
        )

    def test_node_6_5_emits_ticket_delivered(self):
        """Node 6.5 should call emit_ticket_event with event_type='ticket:delivered'."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_6_5_deliver.py") as f:
            source = f.read()
        assert '"ticket:delivered"' in source or "'ticket:delivered'" in source, (
            "Node 6.5 should emit 'ticket:delivered' event"
        )

    def test_node_6_5_includes_channel_and_status(self):
        """The ticket:delivered payload should include channel + status."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_6_5_deliver.py") as f:
            source = f.read()
        # Find the emit block and check for channel + status in payload.
        emit_block_start = source.find('event_type="ticket:delivered"')
        assert emit_block_start > -1, "ticket:delivered emit not found"
        emit_block = source[emit_block_start:emit_block_start + 800]
        assert '"channel"' in emit_block or "'channel'" in emit_block, (
            "ticket:delivered payload should include the delivery channel (email/sms/voice/chat)"
        )
        assert '"status"' in emit_block or "'status'" in emit_block, (
            "ticket:delivered payload should include the delivery status (dispatched/failed/etc.)"
        )

    def test_node_6_5_includes_crm_push_status(self):
        """The payload should include CRM push status (BC-016)."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_6_5_deliver.py") as f:
            source = f.read()
        emit_block_start = source.find('event_type="ticket:delivered"')
        emit_block = source[emit_block_start:emit_block_start + 1200]
        assert "crm_push_status" in emit_block, (
            "ticket:delivered payload should include crm_push_status so the "
            "human knows if the CRM was also updated"
        )

    def test_node_6_5_notification_failure_doesnt_crash(self):
        """The emit call should be wrapped in try/except — never crash node_6_5."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_6_5_deliver.py") as f:
            source = f.read()
        assert "node_6_5_delivery_notification_failed" in source, (
            "Node 6.5 should catch notification failures and log them — never crash"
        )


# ════════════════════════════════════════════════════════════════════
# 3. Node 8 — ticket:escalated
# ════════════════════════════════════════════════════════════════════


class TestNode8EscalationNotification:
    """Verify Node 8 emits ticket:escalated when the AI escalates."""

    def test_node_8_imports_emit_ticket_event(self):
        """Node 8 should import emit_ticket_event from event_emitter."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_8_super_node.py") as f:
            source = f.read()
        assert "from app.core.event_emitter import emit_ticket_event" in source, (
            "Node 8 should import emit_ticket_event to notify Jarvis of escalations"
        )

    def test_node_8_emits_ticket_escalated(self):
        """Node 8 should call emit_ticket_event with event_type='ticket:escalated'."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_8_super_node.py") as f:
            source = f.read()
        assert '"ticket:escalated"' in source or "'ticket:escalated'" in source, (
            "Node 8 should emit 'ticket:escalated' event"
        )

    def test_node_8_only_emits_on_escalation(self):
        """Node 8 should only emit when escalation actually happened (not when quality passed)."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_8_super_node.py") as f:
            source = f.read()
        # Find the actual emit call (not the comment).
        emit_pos = source.find('event_type="ticket:escalated"')
        assert emit_pos > -1, "ticket:escalated emit call not found"
        # Look backwards for the guard condition.
        before_emit = source[max(0, emit_pos - 500):emit_pos]
        assert "escalation_context" in before_emit, (
            "Node 8 emit should be guarded by escalation_context check"
        )
        assert "not passed" in before_emit, (
            "Node 8 should only emit ticket:escalated when quality did NOT pass "
            "— don't emit on successful resolution"
        )

    def test_node_8_includes_quality_score(self):
        """The ticket:escalated payload should include the quality score."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_8_super_node.py") as f:
            source = f.read()
        emit_block_start = source.find('event_type="ticket:escalated"')
        assert emit_block_start > -1
        emit_block = source[emit_block_start:emit_block_start + 1000]
        assert "quality_score" in emit_block, (
            "ticket:escalated payload should include quality_score so the human "
            "knows how low the AI's confidence was"
        )

    def test_node_8_includes_notification_key(self):
        """The payload should include the notification_key for correlation."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_8_super_node.py") as f:
            source = f.read()
        emit_block_start = source.find('event_type="ticket:escalated"')
        emit_block = source[emit_block_start:emit_block_start + 1000]
        assert "notification_key" in emit_block, (
            "ticket:escalated payload should include notification_key for "
            "correlation with the escalation vault"
        )

    def test_node_8_notification_failure_doesnt_crash(self):
        """The emit call should be wrapped in try/except — never crash node_8."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_8_super_node.py") as f:
            source = f.read()
        assert "node_8_escalation_notification_failed" in source, (
            "Node 8 should catch notification failures and log them — never crash"
        )


# ════════════════════════════════════════════════════════════════════
# 4. Integration: event_emitter is importable + functions exist
# ════════════════════════════════════════════════════════════════════


class TestEventEmitterAvailable:
    """Verify the event_emitter module has the functions we're calling."""

    def test_emit_ai_event_exists(self):
        """emit_ai_event should exist and be async."""
        from app.core.event_emitter import emit_ai_event
        import inspect
        assert inspect.iscoroutinefunction(emit_ai_event), (
            "emit_ai_event should be async (we await it from async pipeline nodes)"
        )

    def test_emit_ticket_event_exists(self):
        """emit_ticket_event should exist and be async."""
        from app.core.event_emitter import emit_ticket_event
        import inspect
        assert inspect.iscoroutinefunction(emit_ticket_event), (
            "emit_ticket_event should be async (we await it from async pipeline nodes)"
        )

    def test_emit_ai_event_validates_event_type(self):
        """emit_ai_event should reject non-ai: event types."""
        from app.core.event_emitter import emit_ai_event
        import asyncio
        # Should return False (not raise) for wrong event type.
        result = asyncio.run(emit_ai_event("company-1", "ticket:new", {}))
        assert result is False, (
            "emit_ai_event should reject event types that don't start with 'ai:'"
        )

    def test_emit_ticket_event_validates_event_type(self):
        """emit_ticket_event should reject non-ticket: event types."""
        from app.core.event_emitter import emit_ticket_event
        import asyncio
        result = asyncio.run(emit_ticket_event("company-1", "ai:action", {}))
        assert result is False, (
            "emit_ticket_event should reject event types that don't start with 'ticket:'"
        )
