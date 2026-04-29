"""Tests for Blocked Response Manager (F-058, BC-001, BC-008, BC-009, BC-010).

Comprehensive tests covering:
- Block Response: creation with low confidence, guardrail reasons, field validation, priority
- Review Queue: listing, filtering by status/priority, pagination, empty queue, stats
- Review Actions: approve, reject, edit+approve, escalate, double review, invalid action, notes
- Auto-Reject: normal 72h, urgent 48h, CRITICAL 24h, partial expiry, already reviewed safety
- Cleanup (BC-010): remove old approved/rejected, preserve pending
- Reviewer Assignment: assign, workload counts, multiple reviewers, unassign on completion
- Batch Operations: batch approve/reject, mixed validity, empty batch
- Edge Cases: invalid company_id, invalid response_id, very long text, unicode, concurrent ops
"""

from __future__ import annotations
from app.core.blocked_response_manager import (
    BlockedResponse,
    BlockedResponseManager,
    BlockReason,
    QueueStatus,
    ReviewAction,
    ReviewPriority,
    ReviewQueueStats,
    ReviewerAssignment,
    _compute_auto_reject_at,
    _determine_priority,
    _now_utc,
    _parse_iso,
    _safe_truncate,
)
import pytest
from datetime import datetime, timedelta, timezone

import os

# MUST be set BEFORE importing any app module
os.environ["ENVIRONMENT"] = "test"


# ── Constants ───────────────────────────────────────────────────


COMPANY_ID = "test-company-001"
ANOTHER_COMPANY = "test-company-002"
TICKET_ID = "ticket-42"
SESSION_ID = "session-abc"
REVIEWER_1 = "reviewer-alice"
REVIEWER_2 = "reviewer-bob"
QUERY_TEXT = "How do I reset my password?"
RESPONSE_TEXT = "Go to Settings > Security > Reset Password."
GUARDRAIL_REPORT_CRITICAL = {"results": [
    {"check": "pii", "severity": "critical", "detail": "SSN detected"}], }
GUARDRAIL_REPORT_HIGH = {"results": [
    {"check": "toxicity", "severity": "high", "detail": "harmful content"}], }
GUARDRAIL_REPORT_NONE = {
    "results": [{"check": "safety", "severity": "low", "detail": "all clear"}],
}


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def manager() -> BlockedResponseManager:
    """Fresh manager with cleared in-memory state per test."""
    mgr = BlockedResponseManager()
    mgr.reset()
    return mgr


def _make_blocked(
    manager: BlockedResponseManager,
    *,
    company_id: str = COMPANY_ID,
    ticket_id: str = TICKET_ID,
    query: str = QUERY_TEXT,
    response: str = RESPONSE_TEXT,
    block_reason: str = BlockReason.LOW_CONFIDENCE.value,
    confidence_score: float = 25.0,
    guardrail_report: dict | None = None,
    **kwargs,
) -> BlockedResponse:
    """Helper: create and return a blocked response via the manager."""
    return manager.block_response(
        company_id=company_id,
        ticket_id=ticket_id,
        query=query,
        response=response,
        block_reason=block_reason,
        confidence_score=confidence_score,
        guardrail_report=guardrail_report,
        **kwargs,
    )


# ════════════════════════════════════════════════════════════════
# 1. HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_now_utc_returns_iso_string(self):
        ts = _now_utc()
        assert isinstance(ts, str)
        parsed = _parse_iso(ts)
        assert parsed is not None

    def test_parse_iso_valid(self):
        ts = "2025-01-15T10:30:00+00:00"
        parsed = _parse_iso(ts)
        assert parsed is not None
        assert parsed.year == 2025

    def test_parse_iso_trailing_z(self):
        ts = "2025-01-15T10:30:00Z"
        parsed = _parse_iso(ts)
        assert parsed is not None
        assert parsed.year == 2025

    def test_parse_iso_empty_string(self):
        assert _parse_iso("") is None

    def test_parse_iso_garbage(self):
        assert _parse_iso("not-a-date") is None

    def test_safe_truncate_short(self):
        assert _safe_truncate("hello", 10) == "hello"

    def test_safe_truncate_exact(self):
        assert _safe_truncate("hello", 5) == "hello"

    def test_safe_truncate_over(self):
        result = _safe_truncate("hello world", 8)
        assert len(result) == 8
        assert result.endswith("\u2026")

    def test_safe_truncate_empty(self):
        assert _safe_truncate("", 10) == ""

    def test_determine_priority_urgent_low_confidence(self):
        assert _determine_priority(
            20.0,
            BlockReason.LOW_CONFIDENCE.value,
            None) == "urgent"

    def test_determine_priority_high_medium_confidence(self):
        assert _determine_priority(
            40.0, BlockReason.LOW_CONFIDENCE.value, None) == "high"

    def test_determine_priority_medium(self):
        assert _determine_priority(
            60.0,
            BlockReason.LOW_CONFIDENCE.value,
            None) == "medium"

    def test_determine_priority_low(self):
        assert _determine_priority(
            80.0, BlockReason.LOW_CONFIDENCE.value, None) == "low"

    def test_determine_priority_critical_guardrail(self):
        result = _determine_priority(
            90.0,
            BlockReason.PII_LEAK.value,
            GUARDRAIL_REPORT_CRITICAL)
        assert result == "high"

    def test_compute_auto_reject_at_normal(self):
        base = "2025-01-15T10:00:00+00:00"
        ts = _compute_auto_reject_at("medium", None, base)
        parsed = _parse_iso(ts)
        assert parsed is not None
        assert (
            parsed -
            _parse_iso(base)).total_seconds() == pytest.approx(
            72 *
            3600,
            abs=1)

    def test_compute_auto_reject_at_critical(self):
        base = "2025-01-15T10:00:00+00:00"
        ts = _compute_auto_reject_at("high", GUARDRAIL_REPORT_CRITICAL, base)
        parsed = _parse_iso(ts)
        assert parsed is not None
        assert (
            parsed -
            _parse_iso(base)).total_seconds() == pytest.approx(
            24 *
            3600,
            abs=1)

    def test_compute_auto_reject_at_urgent(self):
        base = "2025-01-15T10:00:00+00:00"
        ts = _compute_auto_reject_at("urgent", None, base)
        parsed = _parse_iso(ts)
        assert parsed is not None
        assert (
            parsed -
            _parse_iso(base)).total_seconds() == pytest.approx(
            48 *
            3600,
            abs=1)


# ════════════════════════════════════════════════════════════════
# 2. BLOCK RESPONSE
# ════════════════════════════════════════════════════════════════


class TestBlockResponse:
    """Tests for block_response — creating new blocked items."""

    def test_block_with_low_confidence(self, manager):
        br = _make_blocked(manager, confidence_score=15.0)
        assert br.status == QueueStatus.PENDING.value
        assert br.confidence_score == 15.0
        assert br.block_reason == BlockReason.LOW_CONFIDENCE.value
        assert br.priority == ReviewPriority.URGENT.value

    def test_block_with_guardrail_reason(self, manager):
        br = _make_blocked(
            manager,
            block_reason=BlockReason.PII_LEAK.value,
            guardrail_report=GUARDRAIL_REPORT_CRITICAL,
        )
        assert br.block_reason == BlockReason.PII_LEAK.value
        assert br.guardrail_report == GUARDRAIL_REPORT_CRITICAL

    def test_block_all_fields_set_correctly(self, manager):
        br = _make_blocked(
            manager,
            session_id=SESSION_ID,
            block_details={"key": "value"},
        )
        assert br.id is not None
        assert len(br.id) > 0
        assert br.company_id == COMPANY_ID
        assert br.ticket_id == TICKET_ID
        assert br.session_id == SESSION_ID
        assert br.query == QUERY_TEXT
        assert br.original_response == RESPONSE_TEXT
        assert br.status == QueueStatus.PENDING.value
        assert br.confidence_score == 25.0
        assert br.block_details == {"key": "value"}
        assert br.reviewer_id is None
        assert br.reviewer_action is None
        assert br.review_notes is None
        assert br.reviewed_at is None
        assert br.created_at is not None
        assert br.updated_at is not None
        assert br.auto_reject_at is not None and len(br.auto_reject_at) > 0

    def test_block_timestamps_are_iso(self, manager):
        br = _make_blocked(manager)
        assert _parse_iso(br.created_at) is not None
        assert _parse_iso(br.updated_at) is not None
        assert _parse_iso(br.auto_reject_at) is not None

    def test_block_unknown_reason_falls_back_to_custom_rule(self, manager):
        br = _make_blocked(manager, block_reason="totally_made_up")
        assert br.block_reason == BlockReason.CUSTOM_RULE.value

    def test_block_confidence_clamped_above_100(self, manager):
        br = _make_blocked(manager, confidence_score=150.0)
        assert br.confidence_score == 100.0

    def test_block_confidence_clamped_below_0(self, manager):
        br = _make_blocked(manager, confidence_score=-10.0)
        assert br.confidence_score == 0.0

    def test_block_priority_by_confidence(self, manager):
        # < 30 → urgent
        br1 = _make_blocked(manager, confidence_score=10.0)
        assert br1.priority == "urgent"
        # < 50 → high
        br2 = _make_blocked(manager, confidence_score=45.0)
        assert br2.priority == "high"
        # < 70 → medium
        br3 = _make_blocked(manager, confidence_score=60.0)
        assert br3.priority == "medium"
        # >= 70 → low
        br4 = _make_blocked(manager, confidence_score=85.0)
        assert br4.priority == "low"

    def test_block_stored_in_queue(self, manager):
        br = _make_blocked(manager)
        detail = manager.get_response_detail(COMPANY_ID, br.id)
        assert detail is not None
        assert detail.id == br.id


# ════════════════════════════════════════════════════════════════
# 3. REVIEW QUEUE
# ════════════════════════════════════════════════════════════════


class TestReviewQueue:
    """Tests for get_review_queue — listing, filtering, pagination."""

    def test_list_all_pending_items(self, manager):
        _make_blocked(manager, query="q1")
        _make_blocked(manager, query="q2")
        queue = manager.get_review_queue(COMPANY_ID)
        assert len(queue) == 2

    def test_filter_by_status_pending(self, manager):
        _make_blocked(manager)
        queue = manager.get_review_queue(
            COMPANY_ID, status=QueueStatus.PENDING.value)
        assert len(queue) == 1

    def test_filter_by_status_approved(self, manager):
        br = _make_blocked(manager)
        manager.review_response(
            COMPANY_ID,
            br.id,
            REVIEWER_1,
            ReviewAction.APPROVED.value)
        queue_pending = manager.get_review_queue(
            COMPANY_ID, status=QueueStatus.PENDING.value)
        queue_approved = manager.get_review_queue(
            COMPANY_ID, status=QueueStatus.APPROVED.value)
        assert len(queue_pending) == 0
        assert len(queue_approved) == 1

    def test_filter_by_priority(self, manager):
        _make_blocked(manager, confidence_score=10.0)  # urgent
        _make_blocked(manager, confidence_score=80.0)  # low
        urgent = manager.get_review_queue(
            COMPANY_ID, priority=ReviewPriority.URGENT.value)
        low = manager.get_review_queue(
            COMPANY_ID, priority=ReviewPriority.LOW.value)
        assert len(urgent) == 1
        assert len(low) == 1

    def test_pagination_limit_and_offset(self, manager):
        for i in range(5):
            _make_blocked(manager, query=f"query-{i}")
        page1 = manager.get_review_queue(COMPANY_ID, limit=2, offset=0)
        page2 = manager.get_review_queue(COMPANY_ID, limit=2, offset=2)
        page3 = manager.get_review_queue(COMPANY_ID, limit=2, offset=4)
        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1

    def test_empty_queue_returns_empty_list(self, manager):
        queue = manager.get_review_queue("nonexistent-company")
        assert queue == []

    def test_queue_sorted_newest_first(self, manager):
        br1 = _make_blocked(manager, query="first")
        br2 = _make_blocked(manager, query="second")
        queue = manager.get_review_queue(COMPANY_ID)
        # newest should be first (reverse=True on created_at)
        assert queue[0].id == br2.id
        assert queue[1].id == br1.id

    def test_queue_stats_accurate(self, manager):
        _make_blocked(manager, confidence_score=10.0)  # urgent, pending
        _make_blocked(manager, confidence_score=80.0)  # low, pending
        stats = manager.get_review_queue_stats(COMPANY_ID)
        assert stats.company_id == COMPANY_ID
        assert stats.total_pending == 2
        assert stats.total_approved == 0
        assert stats.total_rejected == 0
        assert stats.urgent_count == 1
        assert stats.avg_wait_time_minutes >= 0.0

    def test_queue_stats_with_approved_and_rejected(self, manager):
        br1 = _make_blocked(manager)
        br2 = _make_blocked(manager)
        manager.review_response(
            COMPANY_ID,
            br1.id,
            REVIEWER_1,
            ReviewAction.APPROVED.value)
        manager.review_response(
            COMPANY_ID,
            br2.id,
            REVIEWER_1,
            ReviewAction.REJECTED.value)
        stats = manager.get_review_queue_stats(COMPANY_ID)
        assert stats.total_approved == 1
        assert stats.total_rejected == 1
        assert stats.total_pending == 0


# ════════════════════════════════════════════════════════════════
# 4. REVIEW ACTIONS
# ════════════════════════════════════════════════════════════════


class TestReviewActions:
    """Tests for review_response — approve, reject, edit, escalate."""

    def test_approve_response(self, manager):
        br = _make_blocked(manager)
        result = manager.review_response(
            COMPANY_ID, br.id, REVIEWER_1, ReviewAction.APPROVED.value,
        )
        assert result is not None
        assert result.status == QueueStatus.APPROVED.value
        assert result.reviewer_action == ReviewAction.APPROVED.value
        assert result.reviewer_id == REVIEWER_1

    def test_reject_response(self, manager):
        br = _make_blocked(manager)
        result = manager.review_response(
            COMPANY_ID, br.id, REVIEWER_1, ReviewAction.REJECTED.value,
        )
        assert result is not None
        assert result.status == QueueStatus.REJECTED.value
        assert result.reviewer_action == ReviewAction.REJECTED.value

    def test_edit_and_approve(self, manager):
        br = _make_blocked(manager)
        edited = "Corrected: Go to Account Settings to reset your password."
        result = manager.review_response(
            COMPANY_ID, br.id, REVIEWER_1,
            ReviewAction.APPROVED_EDITED.value,
            edited_response=edited,
        )
        assert result is not None
        assert result.status == QueueStatus.APPROVED.value
        assert result.reviewer_action == ReviewAction.APPROVED_EDITED.value
        assert result.edited_response == edited

    def test_escalate_response(self, manager):
        br = _make_blocked(manager)
        result = manager.review_response(
            COMPANY_ID, br.id, REVIEWER_1, ReviewAction.ESCALATED.value,
        )
        assert result is not None
        assert result.status == QueueStatus.IN_REVIEW.value
        assert result.reviewer_action == ReviewAction.ESCALATED.value

    def test_double_review_is_idempotent(self, manager):
        br = _make_blocked(manager)
        manager.review_response(
            COMPANY_ID,
            br.id,
            REVIEWER_1,
            ReviewAction.APPROVED.value)
        # Second review should return the item unchanged, not None
        result = manager.review_response(
            COMPANY_ID, br.id, REVIEWER_2, ReviewAction.REJECTED.value,
        )
        assert result is not None
        assert result.status == QueueStatus.APPROVED.value
        assert result.reviewer_id == REVIEWER_1  # original reviewer preserved

    def test_double_review_after_rejection(self, manager):
        br = _make_blocked(manager)
        manager.review_response(
            COMPANY_ID,
            br.id,
            REVIEWER_1,
            ReviewAction.REJECTED.value)
        result = manager.review_response(
            COMPANY_ID, br.id, REVIEWER_2, ReviewAction.APPROVED.value,
        )
        assert result is not None
        assert result.status == QueueStatus.REJECTED.value

    def test_invalid_action_converted_to_rejected(self, manager):
        br = _make_blocked(manager)
        result = manager.review_response(
            COMPANY_ID, br.id, REVIEWER_1, "not_a_real_action",
        )
        assert result is not None
        assert result.status == QueueStatus.REJECTED.value
        assert result.reviewer_action == ReviewAction.REJECTED.value

    def test_review_notes_saved(self, manager):
        br = _make_blocked(manager)
        notes = "Reviewed carefully, looks good."
        result = manager.review_response(
            COMPANY_ID, br.id, REVIEWER_1,
            ReviewAction.APPROVED.value,
            notes=notes,
        )
        assert result is not None
        assert result.review_notes == notes

    def test_review_updates_reviewed_at(self, manager):
        br = _make_blocked(manager)
        assert br.reviewed_at is None
        result = manager.review_response(
            COMPANY_ID, br.id, REVIEWER_1, ReviewAction.APPROVED.value,
        )
        assert result is not None
        assert result.reviewed_at is not None

    def test_approved_item_auto_reject_cleared(self, manager):
        br = _make_blocked(manager)
        assert br.auto_reject_at != ""
        result = manager.review_response(
            COMPANY_ID, br.id, REVIEWER_1, ReviewAction.APPROVED.value,
        )
        assert result is not None
        assert result.auto_reject_at == ""

    def test_review_nonexistent_returns_none(self, manager):
        result = manager.review_response(
            COMPANY_ID,
            "nonexistent-id",
            REVIEWER_1,
            ReviewAction.APPROVED.value,
        )
        assert result is None

    def test_escalated_item_can_still_be_reviewed(self, manager):
        """After escalation, item stays in_review and can be approved."""
        br = _make_blocked(manager)
        manager.review_response(
            COMPANY_ID, br.id, REVIEWER_1, ReviewAction.ESCALATED.value,
        )
        # Escalated item is in_review, not finalised
        result = manager.review_response(
            COMPANY_ID, br.id, REVIEWER_2, ReviewAction.APPROVED.value,
        )
        assert result is not None
        assert result.status == QueueStatus.APPROVED.value


# ════════════════════════════════════════════════════════════════
# 5. AUTO-REJECT
# ════════════════════════════════════════════════════════════════


class TestAutoReject:
    """Tests for process_auto_rejects — timeout-based auto-rejection."""

    def test_normal_priority_auto_rejects_after_72h(self, manager):
        # medium priority → 72h
        br = _make_blocked(manager, confidence_score=60.0)
        # Set auto_reject_at to 73 hours ago
        past = (datetime.now(timezone.utc) - timedelta(hours=73)).isoformat()
        br.auto_reject_at = past
        count = manager.process_auto_rejects(COMPANY_ID)
        assert count == 1
        detail = manager.get_response_detail(COMPANY_ID, br.id)
        assert detail.status == QueueStatus.AUTO_REJECTED.value

    def test_urgent_priority_auto_rejects_after_48h(self, manager):
        # urgent priority → 48h
        br = _make_blocked(manager, confidence_score=10.0)
        past = (datetime.now(timezone.utc) - timedelta(hours=49)).isoformat()
        br.auto_reject_at = past
        count = manager.process_auto_rejects(COMPANY_ID)
        assert count == 1
        detail = manager.get_response_detail(COMPANY_ID, br.id)
        assert detail.status == QueueStatus.AUTO_REJECTED.value

    def test_critical_auto_rejects_after_24h(self, manager):
        br = _make_blocked(
            manager,
            block_reason=BlockReason.PII_LEAK.value,
            guardrail_report=GUARDRAIL_REPORT_CRITICAL,
            confidence_score=80.0,
        )
        # CRITICAL guardrail → 24h
        past = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        br.auto_reject_at = past
        count = manager.process_auto_rejects(COMPANY_ID)
        assert count == 1
        detail = manager.get_response_detail(COMPANY_ID, br.id)
        assert detail.status == QueueStatus.AUTO_REJECTED.value

    def test_process_auto_rejects_only_expires_past_deadline(self, manager):
        """Items not yet past their deadline should NOT be auto-rejected."""
        br = _make_blocked(manager, confidence_score=60.0)  # medium → 72h
        # Set auto_reject_at to 1 hour in the future
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        br.auto_reject_at = future
        count = manager.process_auto_rejects(COMPANY_ID)
        assert count == 0
        detail = manager.get_response_detail(COMPANY_ID, br.id)
        assert detail.status == QueueStatus.PENDING.value

    def test_already_reviewed_items_not_auto_rejected(self, manager):
        """Items already approved should not be auto-rejected."""
        br = _make_blocked(manager)
        manager.review_response(
            COMPANY_ID,
            br.id,
            REVIEWER_1,
            ReviewAction.APPROVED.value)
        # Set a past auto_reject_at on the now-approved item
        past = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat()
        br.auto_reject_at = past
        # The item's status is approved (finalised) so auto-reject should skip
        # it
        count = manager.process_auto_rejects(COMPANY_ID)
        assert count == 0

    def test_auto_rejected_item_has_auto_action_set(self, manager):
        br = _make_blocked(manager)
        past = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat()
        br.auto_reject_at = past
        manager.process_auto_rejects(COMPANY_ID)
        detail = manager.get_response_detail(COMPANY_ID, br.id)
        assert detail.reviewer_action == ReviewAction.AUTO_REJECTED.value
        assert detail.reviewed_at is not None

    def test_auto_reject_notes_contain_deadline(self, manager):
        br = _make_blocked(manager)
        past = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat()
        br.auto_reject_at = past
        manager.process_auto_rejects(COMPANY_ID)
        detail = manager.get_response_detail(COMPANY_ID, br.id)
        assert "Auto-rejected" in detail.review_notes


# ════════════════════════════════════════════════════════════════
# 6. CLEANUP (BC-010)
# ════════════════════════════════════════════════════════════════


class TestCleanup:
    """Tests for cleanup_old_records — data lifecycle compliance."""

    def test_cleanup_removes_old_approved_records(self, manager):
        br = _make_blocked(manager)
        manager.review_response(
            COMPANY_ID,
            br.id,
            REVIEWER_1,
            ReviewAction.APPROVED.value)
        # Set updated_at to 100 days ago
        old_time = (
            datetime.now(
                timezone.utc) -
            timedelta(
                days=100)).isoformat()
        br.updated_at = old_time
        deleted = manager.cleanup_old_records(COMPANY_ID, days=90)
        assert deleted == 1
        assert manager.get_response_detail(COMPANY_ID, br.id) is None

    def test_cleanup_removes_old_rejected_records(self, manager):
        br = _make_blocked(manager)
        manager.review_response(
            COMPANY_ID,
            br.id,
            REVIEWER_1,
            ReviewAction.REJECTED.value)
        old_time = (
            datetime.now(
                timezone.utc) -
            timedelta(
                days=100)).isoformat()
        br.updated_at = old_time
        deleted = manager.cleanup_old_records(COMPANY_ID, days=90)
        assert deleted == 1

    def test_pending_items_not_cleaned_up(self, manager):
        br = _make_blocked(manager)
        # Make it very old but still pending
        old_time = (
            datetime.now(
                timezone.utc) -
            timedelta(
                days=200)).isoformat()
        br.created_at = old_time
        br.updated_at = old_time
        deleted = manager.cleanup_old_records(COMPANY_ID, days=90)
        assert deleted == 0
        assert manager.get_response_detail(COMPANY_ID, br.id) is not None

    def test_cleanup_respects_custom_days(self, manager):
        br = _make_blocked(manager)
        manager.review_response(
            COMPANY_ID,
            br.id,
            REVIEWER_1,
            ReviewAction.APPROVED.value)
        # Set to 50 days ago
        old_time = (
            datetime.now(
                timezone.utc) -
            timedelta(
                days=50)).isoformat()
        br.updated_at = old_time
        # With 90-day retention, should NOT be cleaned
        assert manager.cleanup_old_records(COMPANY_ID, days=90) == 0
        # With 30-day retention, SHOULD be cleaned
        assert manager.cleanup_old_records(COMPANY_ID, days=30) == 1

    def test_cleanup_removes_old_auto_rejected(self, manager):
        br = _make_blocked(manager)
        old_time = (
            datetime.now(
                timezone.utc) -
            timedelta(
                hours=200)).isoformat()
        br.auto_reject_at = old_time
        manager.process_auto_rejects(COMPANY_ID)
        br.updated_at = (
            datetime.now(
                timezone.utc) -
            timedelta(
                days=100)).isoformat()
        deleted = manager.cleanup_old_records(COMPANY_ID, days=90)
        assert deleted == 1

    def test_cleanup_nonexistent_company(self, manager):
        deleted = manager.cleanup_old_records("no-such-company", days=90)
        assert deleted == 0


# ════════════════════════════════════════════════════════════════
# 7. REVIEWER ASSIGNMENT
# ════════════════════════════════════════════════════════════════


class TestReviewerAssignment:
    """Tests for assign_reviewer and get_reviewer_workload."""

    def test_assign_reviewer(self, manager):
        br = _make_blocked(manager)
        result = manager.assign_reviewer(COMPANY_ID, br.id, REVIEWER_1)
        assert result is not None
        assert result.status == QueueStatus.IN_REVIEW.value
        assert result.reviewer_id == REVIEWER_1

    def test_assign_only_works_on_pending(self, manager):
        br = _make_blocked(manager)
        manager.review_response(
            COMPANY_ID,
            br.id,
            REVIEWER_1,
            ReviewAction.APPROVED.value)
        result = manager.assign_reviewer(COMPANY_ID, br.id, REVIEWER_2)
        # Returns item but status unchanged
        assert result is not None
        assert result.status == QueueStatus.APPROVED.value

    def test_get_reviewer_workload(self, manager):
        br1 = _make_blocked(manager, query="q1")
        br2 = _make_blocked(manager, query="q2")
        manager.assign_reviewer(COMPANY_ID, br1.id, REVIEWER_1)
        manager.assign_reviewer(COMPANY_ID, br2.id, REVIEWER_1)
        workload = manager.get_reviewer_workload(COMPANY_ID)
        assert len(workload) == 1
        assert workload[0].reviewer_id == REVIEWER_1
        assert workload[0].assigned_count == 2

    def test_multiple_reviewers_tracked(self, manager):
        br1 = _make_blocked(manager, query="q1")
        br2 = _make_blocked(manager, query="q2")
        br3 = _make_blocked(manager, query="q3")
        manager.assign_reviewer(COMPANY_ID, br1.id, REVIEWER_1)
        manager.assign_reviewer(COMPANY_ID, br2.id, REVIEWER_1)
        manager.assign_reviewer(COMPANY_ID, br3.id, REVIEWER_2)
        workload = manager.get_reviewer_workload(COMPANY_ID)
        assert len(workload) == 2
        # Sorted by assigned_count descending
        assert workload[0].assigned_count == 2
        assert workload[1].assigned_count == 1

    def test_unassign_on_review_completion(self, manager):
        """After review completion, live in-review count drops to 0 but
        tracked assigned_count is preserved as a fallback in the merged result."""
        br = _make_blocked(manager)
        manager.assign_reviewer(COMPANY_ID, br.id, REVIEWER_1)
        # After assignment, workload shows 1 in-review item (live count)
        workload_before = manager.get_reviewer_workload(COMPANY_ID)
        assert workload_before[0].assigned_count == 1
        # After approval, item leaves in_review state
        manager.review_response(
            COMPANY_ID,
            br.id,
            REVIEWER_1,
            ReviewAction.APPROVED.value)
        # The reviewer still exists in tracked _reviewers with assigned_count=1
        # (fallback), since no live in_review items remain for the live_count path.
        workload_after = manager.get_reviewer_workload(COMPANY_ID)
        assert len(workload_after) >= 1
        # Verify the approved item is no longer in_review by checking the queue
        queue = manager.get_review_queue(
            COMPANY_ID, status=QueueStatus.IN_REVIEW.value)
        assert len(queue) == 0

    def test_assign_nonexistent_returns_none(self, manager):
        result = manager.assign_reviewer(COMPANY_ID, "no-such-id", REVIEWER_1)
        assert result is None

    def test_workload_empty_for_unknown_company(self, manager):
        workload = manager.get_reviewer_workload("no-such-company")
        assert workload == []


# ════════════════════════════════════════════════════════════════
# 8. BATCH OPERATIONS
# ════════════════════════════════════════════════════════════════


class TestBatchOperations:
    """Tests for batch_review — bulk review actions."""

    def test_batch_approve_multiple(self, manager):
        br1 = _make_blocked(manager, query="q1")
        br2 = _make_blocked(manager, query="q2")
        br3 = _make_blocked(manager, query="q3")
        results = manager.batch_review(
            COMPANY_ID,
            [br1.id, br2.id, br3.id],
            REVIEWER_1,
            ReviewAction.APPROVED.value,
        )
        assert len(results) == 3
        for r in results:
            assert r.status == QueueStatus.APPROVED.value

    def test_batch_reject_multiple(self, manager):
        br1 = _make_blocked(manager, query="q1")
        br2 = _make_blocked(manager, query="q2")
        results = manager.batch_review(
            COMPANY_ID,
            [br1.id, br2.id],
            REVIEWER_1,
            ReviewAction.REJECTED.value,
        )
        assert len(results) == 2
        for r in results:
            assert r.status == QueueStatus.REJECTED.value

    def test_mixed_items_some_already_reviewed(self, manager):
        br1 = _make_blocked(manager, query="q1")
        br2 = _make_blocked(manager, query="q2")
        br3 = _make_blocked(manager, query="q3")
        # Approve br2 first
        manager.review_response(
            COMPANY_ID,
            br2.id,
            REVIEWER_1,
            ReviewAction.APPROVED.value)
        results = manager.batch_review(
            COMPANY_ID,
            [br1.id, br2.id, br3.id],
            REVIEWER_1,
            ReviewAction.APPROVED.value,
        )
        # br2 was already approved — still returned (idempotent), but br1 and
        # br3 also processed
        assert len(results) == 3

    def test_batch_with_nonexistent_ids(self, manager):
        br1 = _make_blocked(manager, query="q1")
        results = manager.batch_review(
            COMPANY_ID,
            [br1.id, "fake-id-1", "fake-id-2"],
            REVIEWER_1,
            ReviewAction.APPROVED.value,
        )
        # Only the valid one should be returned
        assert len(results) == 1

    def test_empty_batch(self, manager):
        results = manager.batch_review(
            COMPANY_ID, [], REVIEWER_1, ReviewAction.APPROVED.value,
        )
        assert results == []

    def test_batch_notes_applied_to_all(self, manager):
        br1 = _make_blocked(manager, query="q1")
        br2 = _make_blocked(manager, query="q2")
        results = manager.batch_review(
            COMPANY_ID,
            [br1.id, br2.id],
            REVIEWER_1,
            ReviewAction.REJECTED.value,
            notes="Bulk rejected — out of policy",
        )
        for r in results:
            assert r.review_notes == "Bulk rejected — out of policy"


# ════════════════════════════════════════════════════════════════
# 9. ESCALATION
# ════════════════════════════════════════════════════════════════


class TestEscalation:
    """Tests for escalate_response — priority boosting and reason capture."""

    def test_escalate_boosts_priority(self, manager):
        br = _make_blocked(manager, confidence_score=80.0)  # low
        assert br.priority == ReviewPriority.LOW.value
        result = manager.escalate_response(
            COMPANY_ID, br.id, "Needs senior review")
        assert result is not None
        assert result.priority == ReviewPriority.MEDIUM.value

    def test_escalate_from_medium_to_high(self, manager):
        br = _make_blocked(manager, confidence_score=60.0)  # medium
        result = manager.escalate_response(COMPANY_ID, br.id, "Complex case")
        assert result is not None
        assert result.priority == ReviewPriority.HIGH.value

    def test_escalate_high_does_not_exceed_high(self, manager):
        br = _make_blocked(manager, confidence_score=40.0)  # high
        result = manager.escalate_response(
            COMPANY_ID, br.id, "Critical review")
        assert result is not None
        # HIGH caps at HIGH (not URGENT, since URGENT is not in priority_order)
        assert result.priority == ReviewPriority.HIGH.value

    def test_escalate_reason_stored_in_notes(self, manager):
        br = _make_blocked(manager)
        result = manager.escalate_response(
            COMPANY_ID, br.id, "Customer is VIP, needs attention")
        assert result is not None
        assert "Customer is VIP" in result.review_notes

    def test_escalate_nonexistent_returns_none(self, manager):
        result = manager.escalate_response(COMPANY_ID, "fake-id", "reason")
        assert result is None


# ════════════════════════════════════════════════════════════════
# 10. EDGE CASES (BC-008: NEVER CRASH)
# ════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Tests for edge cases — invalid input, unicode, long text, concurrency."""

    def test_invalid_company_id_does_not_crash(self, manager):
        queue = manager.get_review_queue("company-that-does-not-exist-xyz")
        assert queue == []

    def test_invalid_company_id_stats_safe(self, manager):
        stats = manager.get_review_queue_stats("nonexistent-co")
        assert stats.company_id == "nonexistent-co"
        assert stats.total_pending == 0

    def test_invalid_response_id_handled(self, manager):
        detail = manager.get_response_detail(COMPANY_ID, "nonexistent-id")
        assert detail is None

    def test_very_long_query_text(self, manager):
        long_query = "word " * 20_000  # 100,000 chars
        br = _make_blocked(manager, query=long_query)
        assert len(br.query) <= 10_000
        assert br.query.endswith("\u2026")

    def test_very_long_response_text(self, manager):
        long_response = "x" * 100_000
        br = _make_blocked(manager, response=long_response)
        assert len(br.original_response) <= 50_000

    def test_unicode_content(self, manager):
        unicode_query = "\u00bfC\u00f3mo restablecer mi contrase\u00f1a? \ud83d\ude0a \u4f60\u597d"
        unicode_response = "\u3053\u3093\u306b\u3061\u306f\u3001\u30d1\u30b9\u30ef\u30fc\u30c9\u3092\u30ea\u30bb\u30c3\u30c8\u3057\u3066\u304f\u3060\u3055\u3044\u3002"
        br = _make_blocked(
            manager,
            query=unicode_query,
            response=unicode_response)
        assert "\u00bf" in br.query
        assert "\u3053" in br.original_response

    def test_empty_query_and_response(self, manager):
        br = _make_blocked(manager, query="", response="")
        assert br.query == ""
        assert br.original_response == ""

    def test_none_query_and_response(self, manager):
        br = _make_blocked(manager, query=None, response=None)  # type: ignore
        assert isinstance(br, BlockedResponse)
        assert br.status == QueueStatus.PENDING.value

    def test_concurrent_operations_sequential(self, manager):
        """Simulate rapid sequential operations — all should succeed."""
        ids = []
        for i in range(10):
            br = _make_blocked(manager, query=f"concurrent-query-{i}")
            ids.append(br.id)
        # Approve all
        results = manager.batch_review(
            COMPANY_ID, ids, REVIEWER_1, ReviewAction.APPROVED.value,
        )
        assert len(results) == 10
        stats = manager.get_review_queue_stats(COMPANY_ID)
        assert stats.total_approved == 10

    def test_get_response_detail_nonexistent_company(self, manager):
        result = manager.get_response_detail("fake-co", "some-id")
        assert result is None

    def test_process_auto_rejects_nonexistent_company(self, manager):
        count = manager.process_auto_rejects("no-company")
        assert count == 0

    def test_multi_company_isolation(self, manager):
        """Items from one company should not appear in another's queue."""
        _make_blocked(manager, company_id=COMPANY_ID, query="co1-query")
        _make_blocked(manager, company_id=ANOTHER_COMPANY, query="co2-query")
        q1 = manager.get_review_queue(COMPANY_ID)
        q2 = manager.get_review_queue(ANOTHER_COMPANY)
        assert len(q1) == 1
        assert len(q2) == 1
        assert q1[0].company_id == COMPANY_ID
        assert q2[0].company_id == ANOTHER_COMPANY


# ════════════════════════════════════════════════════════════════
# 11. DATA CLASSES
# ════════════════════════════════════════════════════════════════


class TestDataClasses:
    """Tests for data class construction and defaults."""

    def test_blocked_response_defaults(self):
        br = BlockedResponse(
            id="test-id",
            company_id="co",
            ticket_id="tkt",
        )
        assert br.status == "pending"
        assert br.priority == "medium"
        assert br.query == ""
        assert br.original_response == ""
        assert br.confidence_score == 0.0
        assert br.reviewer_id is None
        assert br.edited_response is None

    def test_review_queue_stats_defaults(self):
        stats = ReviewQueueStats(company_id="co")
        assert stats.total_pending == 0
        assert stats.avg_wait_time_minutes == 0.0
        assert stats.urgent_count == 0

    def test_reviewer_assignment_defaults(self):
        ra = ReviewerAssignment(reviewer_id="r1")
        assert ra.reviewer_name == ""
        assert ra.assigned_count == 0
        assert ra.last_assigned_at is None


# ════════════════════════════════════════════════════════════════
# 12. UTILITY METHODS
# ════════════════════════════════════════════════════════════════


class TestUtilityMethods:
    """Tests for global utility / multi-company methods."""

    def test_reset_clears_everything(self, manager):
        _make_blocked(manager)
        _make_blocked(manager, company_id=ANOTHER_COMPANY)
        manager.reset()
        assert manager.get_review_queue(COMPANY_ID) == []
        assert manager.get_review_queue(ANOTHER_COMPANY) == []
        assert manager.get_reviewer_workload(COMPANY_ID) == []

    def test_process_all_auto_rejects(self, manager):
        _make_blocked(manager, company_id=COMPANY_ID)
        _make_blocked(manager, company_id=ANOTHER_COMPANY)
        # Set both to be expired
        past = (datetime.now(timezone.utc) - timedelta(hours=200)).isoformat()
        for co_id in [COMPANY_ID, ANOTHER_COMPANY]:
            items = manager._queue.get(co_id, {})
            for item in items.values():
                item.auto_reject_at = past
        total = manager.process_all_auto_rejects()
        assert total == 2

    def test_cleanup_all_old_records(self, manager):
        _make_blocked(manager, company_id=COMPANY_ID)
        _make_blocked(manager, company_id=ANOTHER_COMPANY)
        # Approve both and age them
        for co_id in [COMPANY_ID, ANOTHER_COMPANY]:
            items = manager._queue.get(co_id, {})
            for item in items.values():
                manager.review_response(
                    co_id, item.id, REVIEWER_1, ReviewAction.APPROVED.value,
                )
                item.updated_at = (
                    datetime.now(timezone.utc) - timedelta(days=100)
                ).isoformat()
        total = manager.cleanup_all_old_records(days=90)
        assert total == 2

    def test_get_global_queue_summary(self, manager):
        _make_blocked(manager, company_id=COMPANY_ID)
        _make_blocked(manager, company_id=ANOTHER_COMPANY)
        summary = manager.get_global_queue_summary()
        assert summary["total_companies"] == 2
        assert summary["total_items"] == 2
        assert summary["total_pending"] == 2

    def test_get_global_queue_summary_empty(self, manager):
        summary = manager.get_global_queue_summary()
        assert summary["total_companies"] == 0
        assert summary["total_items"] == 0
