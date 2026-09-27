"""
Tests for pipeline notification persistence — verifies pipeline events are
persisted to the notifications DB table so humans see them even when offline.

Also verifies:
  - Each event type gets the right action_url (click-through destination)
  - The persister is called from emit_to_tenant (the single chokepoint)
  - The persister never crashes the emit pipeline (BC-012)
  - P2 Node 2 ticket:routed notification is wired
"""

from __future__ import annotations

import pytest


# ════════════════════════════════════════════════════════════════════
# 1. Pipeline Notification Persister
# ════════════════════════════════════════════════════════════════════


class TestPipelineNotificationPersister:
    """Verify the persister module exists and is wired correctly."""

    def test_persister_module_exists(self):
        """The persister module should exist."""
        from app.core import pipeline_notification_persister
        assert hasattr(pipeline_notification_persister, "persist_pipeline_notification"), (
            "persist_pipeline_notification function should exist"
        )

    def test_persister_has_event_config_for_all_pipeline_events(self):
        """EVENT_CONFIG should include all 7 P0+P1+P2 event types."""
        from app.core.pipeline_notification_persister import EVENT_CONFIG
        expected = [
            "ai:action_taken",
            "ticket:delivered",
            "ticket:escalated",
            "ticket:auto_resolved",
            "ticket:knowledge_gap",
            "ai:quality_low",
            "ticket:routed",
        ]
        for evt in expected:
            assert evt in EVENT_CONFIG, f"EVENT_CONFIG missing '{evt}'"

    def test_persister_routes_escalated_to_escalations_page(self):
        """ticket:escalated should route to /dashboard/escalations."""
        from app.core.pipeline_notification_persister import EVENT_CONFIG
        config = EVENT_CONFIG["ticket:escalated"]
        assert "/dashboard/escalations" in config["url_template"], (
            "ticket:escalated notification should link to the escalations page "
            "(where the Escalation Vault entries live), not just Jarvis CC"
        )

    def test_persister_routes_delivered_to_tickets_page(self):
        """ticket:delivered should route to /dashboard/tickets."""
        from app.core.pipeline_notification_persister import EVENT_CONFIG
        config = EVENT_CONFIG["ticket:delivered"]
        assert "/dashboard/tickets" in config["url_template"], (
            "ticket:delivered notification should link to the ticket detail page"
        )

    def test_persister_routes_knowledge_gap_to_knowledge_page(self):
        """ticket:knowledge_gap should route to /dashboard/knowledge."""
        from app.core.pipeline_notification_persister import EVENT_CONFIG
        config = EVENT_CONFIG["ticket:knowledge_gap"]
        assert "/dashboard/knowledge" in config["url_template"], (
            "ticket:knowledge_gap notification should link to the knowledge base "
            "page so the human can add missing docs"
        )

    def test_persister_routes_routed_to_variants_page(self):
        """ticket:routed should route to /dashboard/variants."""
        from app.core.pipeline_notification_persister import EVENT_CONFIG
        config = EVENT_CONFIG["ticket:routed"]
        assert "/dashboard/variants" in config["url_template"], (
            "ticket:routed notification should link to the variants page "
            "so the human can see why routing was surprising"
        )

    def test_persister_escalated_has_urgent_priority(self):
        """ticket:escalated should be urgent priority."""
        from app.core.pipeline_notification_persister import EVENT_CONFIG
        assert EVENT_CONFIG["ticket:escalated"]["priority"] == "urgent", (
            "ticket:escalated should be urgent — the human needs to act NOW"
        )

    def test_persister_auto_resolved_has_low_priority(self):
        """ticket:auto_resolved should be low priority (informational)."""
        from app.core.pipeline_notification_persister import EVENT_CONFIG
        assert EVENT_CONFIG["ticket:auto_resolved"]["priority"] == "low", (
            "ticket:auto_resolved is informational — don't spam the human with high priority"
        )


# ════════════════════════════════════════════════════════════════════
# 2. emit_to_tenant calls the persister
# ════════════════════════════════════════════════════════════════════


class TestEmitToTenantPersisterWiring:
    """Verify emit_to_tenant calls persist_pipeline_notification."""

    def test_socketio_imports_persister(self):
        """socketio.py should import the persister."""
        with open("/home/z/my-project/parwa/backend/app/core/socketio.py") as f:
            source = f.read()
        assert "persist_pipeline_notification" in source, (
            "emit_to_tenant should call persist_pipeline_notification so pipeline "
            "events are persisted to the DB, not just Socket.io + Redis"
        )

    def test_socketio_persister_call_is_in_try_except(self):
        """The persister call should be wrapped in try/except (BC-012)."""
        with open("/home/z/my-project/parwa/backend/app/core/socketio.py") as f:
            source = f.read()
        assert "pipeline_persist_failed" in source, (
            "Persister failure should be caught and logged — never crash the emit pipeline"
        )

    def test_socketio_persister_called_after_event_buffer(self):
        """The persister should be called AFTER the event buffer store."""
        with open("/home/z/my-project/parwa/backend/app/core/socketio.py") as f:
            source = f.read()
        buffer_pos = source.find("store_event")
        persister_pos = source.find("persist_pipeline_notification")
        assert buffer_pos > -1 and persister_pos > -1, "Both store_event and persister should be present"
        assert persister_pos > buffer_pos, (
            "Persister should be called AFTER event buffer store — "
            "real-time delivery takes priority over persistence"
        )


# ════════════════════════════════════════════════════════════════════
# 3. P2 Node 2 — ticket:routed
# ════════════════════════════════════════════════════════════════════


class TestNode2RoutedNotification:
    """Verify Node 2 emits ticket:routed when routing is surprising."""

    def test_node_2_imports_emit_ticket_event(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_2_smart_route.py") as f:
            source = f.read()
        assert "from app.core.event_emitter import emit_ticket_event" in source, (
            "Node 2 should import emit_ticket_event for routing notifications"
        )

    def test_node_2_emits_ticket_routed(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_2_smart_route.py") as f:
            source = f.read()
        assert '"ticket:routed"' in source or "'ticket:routed'" in source, (
            "Node 2 should emit 'ticket:routed' event"
        )

    def test_node_2_only_emits_when_surprising(self):
        """Should only emit when routing is surprising (path override or quota exhausted)."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_2_smart_route.py") as f:
            source = f.read()
        emit_pos = source.find('event_type="ticket:routed"')
        assert emit_pos > -1, "ticket:routed emit not found"
        before_emit = source[max(0, emit_pos - 800):emit_pos]
        assert "is_surprising" in before_emit, (
            "Node 2 should only emit ticket:routed when is_surprising is True"
        )

    def test_node_2_includes_surprise_reason(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_2_smart_route.py") as f:
            source = f.read()
        emit_pos = source.find('event_type="ticket:routed"')
        emit_block = source[emit_pos:emit_pos + 800]
        assert "surprise_reason" in emit_block, (
            "ticket:routed payload should include surprise_reason so the human "
            "knows WHY the routing was surprising"
        )

    def test_node_2_notification_failure_doesnt_crash(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_2_smart_route.py") as f:
            source = f.read()
        assert "node_2_routed_notification_failed" in source, (
            "Node 2 should catch notification failures — never crash"
        )

    def test_ticket_routed_is_registered(self):
        """ticket:routed must be registered in EventRegistry."""
        from app.core.events import EventRegistry
        registry = EventRegistry()
        et = registry.get("ticket:routed")
        assert et is not None, (
            "ticket:routed must be registered — otherwise emit_event silently drops it"
        )
