"""
Tests for the P1 notification wiring — Node 7, Node 3, Node 6 emit events to Jarvis.

Verifies that:
  1. Node 7 emits `ticket:auto_resolved` when AI closes a simple ticket without human involvement
  2. Node 3 emits `ticket:knowledge_gap` when knowledge is insufficient (AI working blind)
  3. Node 6 emits `ai:quality_low` when CLARA quality gate scores below threshold

These are the P1 notifications — they give the human context about what the AI
is doing and where it's struggling.
"""

from __future__ import annotations

import pytest


# ════════════════════════════════════════════════════════════════════
# 1. Node 7 — ticket:auto_resolved
# ════════════════════════════════════════════════════════════════════


class TestNode7AutoResolvedNotification:
    """Verify Node 7 emits ticket:auto_resolved when AI closes a simple ticket."""

    def test_node_7_imports_emit_ticket_event(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_7_simple_resolver.py") as f:
            source = f.read()
        assert "from app.core.event_emitter import emit_ticket_event" in source, (
            "Node 7 should import emit_ticket_event to notify Jarvis of auto-resolution"
        )

    def test_node_7_emits_ticket_auto_resolved(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_7_simple_resolver.py") as f:
            source = f.read()
        assert '"ticket:auto_resolved"' in source or "'ticket:auto_resolved'" in source, (
            "Node 7 should emit 'ticket:auto_resolved' event"
        )

    def test_node_7_only_emits_when_resolved(self):
        """Should only emit when confidence is high enough (not auto-upgraded)."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_7_simple_resolver.py") as f:
            source = f.read()
        emit_pos = source.find('event_type="ticket:auto_resolved"')
        assert emit_pos > -1, "ticket:auto_resolved emit not found"
        before_emit = source[max(0, emit_pos - 500):emit_pos]
        assert "not auto_upgraded" in before_emit, (
            "Node 7 should only emit ticket:auto_resolved when the ticket was NOT auto-upgraded "
            "(i.e. the AI actually resolved it, not passed to Node 4)"
        )
        assert "QUALITY_SIMPLE_SAFETY_NET" in before_emit, (
            "Node 7 should check confidence >= QUALITY_SIMPLE_SAFETY_NET before emitting"
        )

    def test_node_7_includes_confidence_in_payload(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_7_simple_resolver.py") as f:
            source = f.read()
        emit_pos = source.find('event_type="ticket:auto_resolved"')
        emit_block = source[emit_pos:emit_pos + 800]
        assert "confidence" in emit_block, (
            "ticket:auto_resolved payload should include confidence score"
        )
        assert "ticket_type" in emit_block, (
            "ticket:auto_resolved payload should include ticket_type"
        )

    def test_node_7_notification_failure_doesnt_crash(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_7_simple_resolver.py") as f:
            source = f.read()
        assert "node_7_auto_resolved_notification_failed" in source, (
            "Node 7 should catch notification failures — never crash"
        )


# ════════════════════════════════════════════════════════════════════
# 2. Node 3 — ticket:knowledge_gap
# ════════════════════════════════════════════════════════════════════


class TestNode3KnowledgeGapNotification:
    """Verify Node 3 emits ticket:knowledge_gap when knowledge is insufficient."""

    def test_node_3_imports_emit_ticket_event(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_3_knowledge_fetch.py") as f:
            source = f.read()
        assert "from app.core.event_emitter import emit_ticket_event" in source, (
            "Node 3 should import emit_ticket_event to notify Jarvis of knowledge gaps"
        )

    def test_node_3_emits_ticket_knowledge_gap(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_3_knowledge_fetch.py") as f:
            source = f.read()
        assert '"ticket:knowledge_gap"' in source or "'ticket:knowledge_gap'" in source, (
            "Node 3 should emit 'ticket:knowledge_gap' event"
        )

    def test_node_3_only_emits_when_insufficient(self):
        """Should only emit when knowledge is NOT sufficient."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_3_knowledge_fetch.py") as f:
            source = f.read()
        emit_pos = source.find('event_type="ticket:knowledge_gap"')
        assert emit_pos > -1, "ticket:knowledge_gap emit not found"
        before_emit = source[max(0, emit_pos - 500):emit_pos]
        assert "not sufficiency" in before_emit or "not sufficient" in before_emit, (
            "Node 3 should only emit ticket:knowledge_gap when knowledge is NOT sufficient"
        )

    def test_node_3_includes_query_and_docs_count(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_3_knowledge_fetch.py") as f:
            source = f.read()
        emit_pos = source.find('event_type="ticket:knowledge_gap"')
        emit_block = source[emit_pos:emit_pos + 800]
        assert "query" in emit_block, (
            "ticket:knowledge_gap payload should include the customer query"
        )
        assert "docs_found" in emit_block, (
            "ticket:knowledge_gap payload should include docs_found count"
        )

    def test_node_3_includes_contradictory_flag(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_3_knowledge_fetch.py") as f:
            source = f.read()
        emit_pos = source.find('event_type="ticket:knowledge_gap"')
        emit_block = source[emit_pos:emit_pos + 800]
        assert "contradictory" in emit_block, (
            "ticket:knowledge_gap payload should include contradictory flag"
        )

    def test_node_3_notification_failure_doesnt_crash(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_3_knowledge_fetch.py") as f:
            source = f.read()
        assert "node_3_knowledge_gap_notification_failed" in source, (
            "Node 3 should catch notification failures — never crash"
        )


# ════════════════════════════════════════════════════════════════════
# 3. Node 6 — ai:quality_low
# ════════════════════════════════════════════════════════════════════


class TestNode6QualityLowNotification:
    """Verify Node 6 emits ai:quality_low when CLARA quality gate fails."""

    def test_node_6_imports_emit_ai_event(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_6_quality_format.py") as f:
            source = f.read()
        assert "from app.core.event_emitter import emit_ai_event" in source, (
            "Node 6 should import emit_ai_event to notify Jarvis of low quality"
        )

    def test_node_6_emits_ai_quality_low(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_6_quality_format.py") as f:
            source = f.read()
        assert '"ai:quality_low"' in source or "'ai:quality_low'" in source, (
            "Node 6 should emit 'ai:quality_low' event"
        )

    def test_node_6_only_emits_when_quality_fails(self):
        """Should only emit when quality did NOT pass."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_6_quality_format.py") as f:
            source = f.read()
        emit_pos = source.find('event_type="ai:quality_low"')
        assert emit_pos > -1, "ai:quality_low emit not found"
        before_emit = source[max(0, emit_pos - 300):emit_pos]
        assert "not quality_passed" in before_emit, (
            "Node 6 should only emit ai:quality_low when quality did NOT pass"
        )

    def test_node_6_includes_quality_score_and_threshold(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_6_quality_format.py") as f:
            source = f.read()
        emit_pos = source.find('event_type="ai:quality_low"')
        emit_block = source[emit_pos:emit_pos + 800]
        assert "quality_score" in emit_block, (
            "ai:quality_low payload should include the actual quality score"
        )
        assert "quality_threshold" in emit_block, (
            "ai:quality_low payload should include the threshold so the human "
            "knows how far below the AI scored"
        )

    def test_node_6_includes_quality_details(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_6_quality_format.py") as f:
            source = f.read()
        emit_pos = source.find('event_type="ai:quality_low"')
        emit_block = source[emit_pos:emit_pos + 800]
        assert "quality_details" in emit_block, (
            "ai:quality_low payload should include quality_details (which sub-scores failed)"
        )

    def test_node_6_notification_failure_doesnt_crash(self):
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_6_quality_format.py") as f:
            source = f.read()
        assert "node_6_quality_low_notification_failed" in source, (
            "Node 6 should catch notification failures — never crash"
        )
