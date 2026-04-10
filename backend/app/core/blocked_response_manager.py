"""
F-058: Blocked Response Manager + Review Queue (BC-001, BC-008, BC-009, BC-010)

When an AI response fails confidence checks or guardrails, it is routed
to a review queue for human inspection. Agents can approve, edit, or
reject blocked responses. Items not reviewed within their timeout window
are automatically rejected.

Core behaviours:
- BC-001: company_id is always the first parameter on every method.
- BC-009: Approval workflow for blocked AI responses.
- BC-010: Data lifecycle compliance — auto-cleanup of old records.
- BC-008: Never crash; every public method is wrapped with safe guards.

Storage:
  In-memory ``Dict[str, Dict[str, BlockedResponse]]`` keyed by
  company_id → response_id.  DB persistence is handled by the API /
  ORM layer; this manager is the pure-business-logic core.

Auto-reject timeouts (default):
  - CRITICAL guardrail blocks → 24 hours
  - URGENT priority           → 48 hours
  - All other items           → 72 hours
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.app.logger import get_logger

logger = get_logger("blocked_response_manager")


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class BlockReason(str, Enum):
    """Why an AI response was blocked from delivery."""

    LOW_CONFIDENCE = "low_confidence"
    GUARDRAIL_BLOCKED = "guardrail_blocked"
    PII_LEAK = "pii_leak"
    HALLUCINATION = "hallucination"
    PROMPT_INJECTION = "prompt_injection"
    CONTENT_SAFETY = "content_safety"
    POLICY_VIOLATION = "policy_violation"
    TONE_VIOLATION = "tone_violation"
    LENGTH_VIOLATION = "length_violation"
    TOPIC_IRRELEVANCE = "topic_irrelevance"
    CUSTOM_RULE = "custom_rule"
    TIMEOUT = "timeout"


class ReviewAction(str, Enum):
    """Actions a human reviewer can take on a blocked response."""

    APPROVED = "approved"
    APPROVED_EDITED = "approved_edited"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    AUTO_REJECTED = "auto_rejected"


class ReviewPriority(str, Enum):
    """Priority levels for items in the review queue."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class QueueStatus(str, Enum):
    """Lifecycle states for a blocked response in the queue."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_REJECTED = "auto_rejected"
    EXPIRED = "expired"


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class BlockedResponse:
    """A single blocked AI response awaiting (or having received) review.

    Attributes:
        id: Unique identifier for this blocked-response record.
        company_id: Tenant identifier (BC-001).
        ticket_id: The support ticket this response belongs to.
        session_id: Optional conversation session identifier.
        query: The original customer query that triggered the AI.
        original_response: The AI-generated response that was blocked.
        edited_response: Reviewer-corrected text (if action is approved_edited).
        block_reason: The :class:`BlockReason` value explaining the block.
        block_details: Structured metadata — confidence score, guard
            results, matched patterns, etc.
        confidence_score: AI confidence at the time of generation (0-100).
        guardrail_report: Full guardrail-engine report dict, if available.
        priority: :class:`ReviewPriority` value for triage.
        status: :class:`QueueStatus` value tracking lifecycle.
        reviewer_id: ID of the agent who reviewed this response.
        reviewer_action: :class:`ReviewAction` value chosen by the reviewer.
        review_notes: Free-text notes from the reviewer.
        reviewed_at: ISO timestamp when the review was completed.
        auto_reject_at: ISO timestamp when auto-rejection triggers.
        created_at: ISO timestamp when the item was created.
        updated_at: ISO timestamp of the last mutation.
    """

    id: str
    company_id: str
    ticket_id: str
    session_id: Optional[str] = None
    query: str = ""
    original_response: str = ""
    edited_response: Optional[str] = None
    block_reason: str = BlockReason.LOW_CONFIDENCE.value
    block_details: Dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0
    guardrail_report: Optional[Dict[str, Any]] = None
    priority: str = ReviewPriority.MEDIUM.value
    status: str = QueueStatus.PENDING.value
    reviewer_id: Optional[str] = None
    reviewer_action: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[str] = None
    auto_reject_at: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


@dataclass
class ReviewQueueStats:
    """Aggregate statistics for a company's review queue.

    Attributes:
        company_id: Tenant identifier (BC-001).
        total_pending: Items in ``pending`` state.
        total_in_review: Items currently being reviewed.
        total_approved: Items approved (original or edited).
        total_rejected: Items manually rejected by a reviewer.
        total_auto_rejected: Items automatically rejected on timeout.
        total_expired: Items marked expired.
        avg_wait_time_minutes: Average wait time for items still pending.
        urgent_count: Pending/in-review items with URGENT priority.
        high_count: Pending/in-review items with HIGH priority.
    """

    company_id: str
    total_pending: int = 0
    total_in_review: int = 0
    total_approved: int = 0
    total_rejected: int = 0
    total_auto_rejected: int = 0
    total_expired: int = 0
    avg_wait_time_minutes: float = 0.0
    urgent_count: int = 0
    high_count: int = 0


@dataclass
class ReviewerAssignment:
    """Workload summary for a single reviewer.

    Attributes:
        reviewer_id: Unique identifier of the reviewer / agent.
        reviewer_name: Human-readable display name.
        assigned_count: Number of items currently assigned to them.
        last_assigned_at: ISO timestamp of the most recent assignment.
    """

    reviewer_id: str
    reviewer_name: str = ""
    assigned_count: int = 0
    last_assigned_at: Optional[str] = None


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Auto-reject timeout durations (hours) keyed by priority.
_AUTO_REJECT_TIMEOUTS: Dict[str, int] = {
    ReviewPriority.URGENT.value: 48,
    ReviewPriority.HIGH.value: 72,
    ReviewPriority.MEDIUM.value: 72,
    ReviewPriority.LOW.value: 72,
}

# Special timeout for CRITICAL severity guardrail blocks (24 h).
_CRITICAL_GUARDRAIL_TIMEOUT_HOURS: int = 24

# Confidence thresholds used for automatic priority assignment.
_URGENT_CONFIDENCE_THRESHOLD: float = 30.0
_HIGH_CONFIDENCE_THRESHOLD: float = 50.0
_MEDIUM_CONFIDENCE_THRESHOLD: float = 70.0

# Default cleanup retention period (days).
_DEFAULT_CLEANUP_DAYS: int = 90

# Maximum text lengths for stored fields (defensive truncation).
_MAX_QUERY_LENGTH: int = 10_000
_MAX_RESPONSE_LENGTH: int = 50_000
_MAX_NOTES_LENGTH: int = 5_000


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════


def _now_utc() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _safe_truncate(text: str, max_length: int) -> str:
    """Truncate *text* to *max_length* characters, appending ``…`` if cut."""
    if not text:
        return text
    if len(text) <= max_length:
        return text
    return text[:max_length - 1] + "\u2026"


def _parse_iso(ts: str) -> Optional[datetime]:
    """Best-effort ISO timestamp parser.  Returns ``None`` on failure."""
    if not ts:
        return None
    try:
        # Handle trailing 'Z' which fromisoformat does not accept.
        cleaned = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        return None


def _determine_priority(
    confidence_score: float,
    block_reason: str,
    guardrail_report: Optional[Dict[str, Any]],
) -> str:
    """Assign a :class:`ReviewPriority` based on confidence & guardrails.

    Priority logic (highest wins):
    - CRITICAL confidence < 30%  → URGENT
    - Any CRITICAL guardrail    → HIGH
    - confidence < 50%          → HIGH
    - confidence < 70%          → MEDIUM
    - otherwise                 → LOW

    Args:
        confidence_score: AI confidence at time of block (0-100).
        block_reason: :class:`BlockReason` value.
        guardrail_report: Optional guardrail-engine report dict.

    Returns:
        One of the :class:`ReviewPriority` values.
    """
    # Check for CRITICAL severity in the guardrail report.
    is_critical_guardrail = False
    if guardrail_report:
        try:
            for result in guardrail_report.get("results", []):
                severity = result.get("severity", "").lower()
                if severity == "critical":
                    is_critical_guardrail = True
                    break
        except Exception:
            logger.warning("Failed to inspect guardrail_report for severity")

    if confidence_score < _URGENT_CONFIDENCE_THRESHOLD:
        return ReviewPriority.URGENT.value
    if is_critical_guardrail:
        return ReviewPriority.HIGH.value
    if confidence_score < _HIGH_CONFIDENCE_THRESHOLD:
        return ReviewPriority.HIGH.value
    if confidence_score < _MEDIUM_CONFIDENCE_THRESHOLD:
        return ReviewPriority.MEDIUM.value
    return ReviewPriority.LOW.value


def _compute_auto_reject_at(
    priority: str,
    guardrail_report: Optional[Dict[str, Any]],
    created_at: Optional[str] = None,
) -> str:
    """Compute the ISO timestamp at which auto-rejection fires.

    CRITICAL guardrail blocks use a 24-hour window regardless of
    the computed priority.  Otherwise the timeout is looked up from
    ``_AUTO_REJECT_TIMEOUTS`` by priority.

    Args:
        priority: :class:`ReviewPriority` value.
        guardrail_report: Optional guardrail report (to detect CRITICAL).
        created_at: Optional creation timestamp; defaults to now.

    Returns:
        ISO timestamp string of the auto-reject deadline.
    """
    base = _parse_iso(created_at) if created_at else datetime.now(timezone.utc)
    if base is None:
        base = datetime.now(timezone.utc)

    # Check if any guardrail result has CRITICAL severity.
    has_critical = False
    if guardrail_report:
        try:
            for r in guardrail_report.get("results", []):
                if r.get("severity", "").lower() == "critical":
                    has_critical = True
                    break
        except Exception:
            logger.warning("Failed to check guardrail severity for timeout")

    hours = (
        _CRITICAL_GUARDRAIL_TIMEOUT_HOURS
        if has_critical
        else _AUTO_REJECT_TIMEOUTS.get(priority, 72)
    )

    deadline = base + timedelta(hours=hours)
    return deadline.isoformat()


# ══════════════════════════════════════════════════════════════════
# MAIN CLASS
# ══════════════════════════════════════════════════════════════════


class BlockedResponseManager:
    """F-058: Blocked Response Manager + Review Queue.

    Manages the lifecycle of AI responses that were blocked by
    guardrails or confidence gates.  Supports queueing, prioritisation,
    human review (approve / edit / reject / escalate), auto-rejection
    on timeout, and lifecycle cleanup of old records.

    All public methods accept **company_id** as the first positional
    argument (BC-001) and are defensively coded to never raise
    unhandled exceptions (BC-008).

    Storage is in-memory via a class-level ``_queue`` dict.  The
    API / ORM layer is responsible for persisting records to a database.
    """

    # Class-level in-memory store: {company_id: {response_id: BlockedResponse}}
    _queue: Dict[str, Dict[str, BlockedResponse]] = {}

    # Track reviewer assignments per company: {company_id: {reviewer_id: ReviewerAssignment}}
    _reviewers: Dict[str, Dict[str, ReviewerAssignment]] = {}

    # ── Create / Block ─────────────────────────────────────────

    def block_response(
        self,
        company_id: str,
        ticket_id: str,
        query: str,
        response: str,
        block_reason: str,
        confidence_score: float = 0.0,
        guardrail_report: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> BlockedResponse:
        """Add a blocked AI response to the review queue.

        Args:
            company_id: Tenant identifier (BC-001).
            ticket_id: Support ticket the response belongs to.
            query: Original customer query text.
            response: The blocked AI-generated response.
            block_reason: :class:`BlockReason` value.
            confidence_score: AI confidence (0-100). Defaults to 0.
            guardrail_report: Full guardrail-engine report, if available.
            **kwargs: Optional extras — ``session_id``, ``block_details``.

        Returns:
            The created :class:`BlockedResponse` record.
        """
        try:
            response_id = str(uuid.uuid4())
            now = _now_utc()

            # Truncate defensively to prevent unbounded storage growth.
            safe_query = _safe_truncate(str(query or ""), _MAX_QUERY_LENGTH)
            safe_response = _safe_truncate(
                str(response or ""), _MAX_RESPONSE_LENGTH,
            )

            # Validate block_reason against the enum; fall back gracefully.
            try:
                BlockReason(block_reason)
            except ValueError:
                logger.warning(
                    "Unknown block_reason '%s', using custom_rule",
                    block_reason,
                )
                block_reason = BlockReason.CUSTOM_RULE.value

            # Clamp confidence_score.
            confidence_score = max(0.0, min(100.0, float(confidence_score)))

            # Determine priority.
            priority = _determine_priority(
                confidence_score, block_reason, guardrail_report,
            )

            # Compute auto-reject deadline.
            auto_reject_at = _compute_auto_reject_at(
                priority, guardrail_report, now,
            )

            blocked = BlockedResponse(
                id=response_id,
                company_id=company_id,
                ticket_id=ticket_id,
                session_id=kwargs.get("session_id"),
                query=safe_query,
                original_response=safe_response,
                block_reason=block_reason,
                block_details=kwargs.get("block_details", {}),
                confidence_score=confidence_score,
                guardrail_report=guardrail_report,
                priority=priority,
                status=QueueStatus.PENDING.value,
                auto_reject_at=auto_reject_at,
                created_at=now,
                updated_at=now,
            )

            # Persist to in-memory store.
            if company_id not in self._queue:
                self._queue[company_id] = {}
            self._queue[company_id][response_id] = blocked

            logger.info(
                "Blocked response queued",
                company_id=company_id,
                response_id=response_id,
                ticket_id=ticket_id,
                block_reason=block_reason,
                priority=priority,
                confidence_score=confidence_score,
            )

            return blocked

        except Exception:
            logger.error(
                "block_response failed (BC-008)",
                company_id=company_id,
                ticket_id=ticket_id,
                exc_info=True,
            )
            # Return a minimal fallback record so callers never crash.
            return BlockedResponse(
                id=str(uuid.uuid4()),
                company_id=company_id,
                ticket_id=ticket_id,
                query=str(query or "")[:200],
                original_response=str(response or "")[:200],
                block_reason=block_reason,
                confidence_score=confidence_score,
                status=QueueStatus.PENDING.value,
                auto_reject_at=_now_utc(),
                created_at=_now_utc(),
                updated_at=_now_utc(),
            )

    # ── Queue retrieval ────────────────────────────────────────

    def get_review_queue(
        self,
        company_id: str,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[BlockedResponse]:
        """Retrieve items from the review queue with optional filters.

        Args:
            company_id: Tenant identifier (BC-001).
            status: Optional :class:`QueueStatus` to filter by.
            priority: Optional :class:`ReviewPriority` to filter by.
            limit: Maximum number of items to return (default 50).
            offset: Number of items to skip for pagination (default 0).

        Returns:
            List of :class:`BlockedResponse` matching the filters.
        """
        try:
            company_items = self._queue.get(company_id, {})
            results: List[BlockedResponse] = []

            for item in company_items.values():
                # Apply status filter.
                if status and item.status != status:
                    continue
                # Apply priority filter.
                if priority and item.priority != priority:
                    continue
                results.append(item)

            # Sort by created_at descending (newest first).
            results.sort(
                key=lambda r: r.created_at,
                reverse=True,
            )

            # Paginate.
            return results[offset : offset + limit]

        except Exception:
            logger.error(
                "get_review_queue failed (BC-008)",
                company_id=company_id,
                exc_info=True,
            )
            return []

    # ── Statistics ─────────────────────────────────────────────

    def get_review_queue_stats(self, company_id: str) -> ReviewQueueStats:
        """Aggregate statistics for a company's review queue.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            A :class:`ReviewQueueStats` snapshot of the current queue.
        """
        try:
            company_items = self._queue.get(company_id, {})
            now = datetime.now(timezone.utc)

            stats = ReviewQueueStats(company_id=company_id)

            pending_wait_minutes: List[float] = []

            for item in company_items.values():
                if item.status == QueueStatus.PENDING.value:
                    stats.total_pending += 1
                    created = _parse_iso(item.created_at)
                    if created:
                        wait = (now - created).total_seconds() / 60.0
                        pending_wait_minutes.append(wait)
                elif item.status == QueueStatus.IN_REVIEW.value:
                    stats.total_in_review += 1
                elif item.status == QueueStatus.APPROVED.value:
                    stats.total_approved += 1
                elif item.status == QueueStatus.REJECTED.value:
                    stats.total_rejected += 1
                elif item.status == QueueStatus.AUTO_REJECTED.value:
                    stats.total_auto_rejected += 1
                elif item.status == QueueStatus.EXPIRED.value:
                    stats.total_expired += 1

                # Count URGENT and HIGH items that are still actionable.
                if item.status in (
                    QueueStatus.PENDING.value,
                    QueueStatus.IN_REVIEW.value,
                ):
                    if item.priority == ReviewPriority.URGENT.value:
                        stats.urgent_count += 1
                    elif item.priority == ReviewPriority.HIGH.value:
                        stats.high_count += 1

            # Compute average wait time for pending items.
            if pending_wait_minutes:
                stats.avg_wait_time_minutes = round(
                    sum(pending_wait_minutes) / len(pending_wait_minutes), 2,
                )

            return stats

        except Exception:
            logger.error(
                "get_review_queue_stats failed (BC-008)",
                company_id=company_id,
                exc_info=True,
            )
            return ReviewQueueStats(company_id=company_id)

    # ── Single item retrieval ──────────────────────────────────

    def get_response_detail(
        self,
        company_id: str,
        response_id: str,
    ) -> Optional[BlockedResponse]:
        """Retrieve a single blocked response by ID.

        Args:
            company_id: Tenant identifier (BC-001).
            response_id: Unique identifier of the blocked response.

        Returns:
            The :class:`BlockedResponse`, or ``None`` if not found.
        """
        try:
            company_items = self._queue.get(company_id, {})
            return company_items.get(response_id)
        except Exception:
            logger.error(
                "get_response_detail failed (BC-008)",
                company_id=company_id,
                response_id=response_id,
                exc_info=True,
            )
            return None

    # ── Review actions ─────────────────────────────────────────

    def review_response(
        self,
        company_id: str,
        response_id: str,
        reviewer_id: str,
        action: str,
        notes: Optional[str] = None,
        edited_response: Optional[str] = None,
    ) -> Optional[BlockedResponse]:
        """Approve, reject, edit, or escalate a blocked response.

        Args:
            company_id: Tenant identifier (BC-001).
            response_id: Unique identifier of the blocked response.
            reviewer_id: ID of the human reviewer performing the action.
            action: One of the :class:`ReviewAction` values.
            notes: Optional free-text notes from the reviewer.
            edited_response: Corrected response text when
                *action* is ``approved_edited``.

        Returns:
            The updated :class:`BlockedResponse`, or ``None`` if not found.
        """
        try:
            item = self._get_item_safe(company_id, response_id)
            if item is None:
                logger.warning(
                    "review_response: item not found",
                    company_id=company_id,
                    response_id=response_id,
                )
                return None

            # Validate the action.
            try:
                ReviewAction(action)
            except ValueError:
                logger.warning(
                    "Invalid review action '%s', rejecting",
                    action,
                )
                action = ReviewAction.REJECTED.value

            # Prevent re-review of already-finalised items.
            if item.status in (
                QueueStatus.APPROVED.value,
                QueueStatus.REJECTED.value,
                QueueStatus.AUTO_REJECTED.value,
                QueueStatus.EXPIRED.value,
            ):
                logger.warning(
                    "review_response: item already finalised (status=%s)",
                    item.status,
                    company_id=company_id,
                    response_id=response_id,
                )
                return item

            now = _now_utc()

            # Map action to the resulting QueueStatus.
            status_map: Dict[str, str] = {
                ReviewAction.APPROVED.value: QueueStatus.APPROVED.value,
                ReviewAction.APPROVED_EDITED.value: QueueStatus.APPROVED.value,
                ReviewAction.REJECTED.value: QueueStatus.REJECTED.value,
                ReviewAction.ESCALATED.value: QueueStatus.IN_REVIEW.value,
                ReviewAction.AUTO_REJECTED.value: QueueStatus.AUTO_REJECTED.value,
            }

            item.reviewer_id = reviewer_id
            item.reviewer_action = action
            item.review_notes = _safe_truncate(
                str(notes or ""), _MAX_NOTES_LENGTH,
            )
            item.reviewed_at = now
            item.status = status_map.get(action, item.status)
            item.updated_at = now

            # Store edited response when action is approved_edited.
            if action == ReviewAction.APPROVED_EDITED.value and edited_response:
                item.edited_response = _safe_truncate(
                    str(edited_response), _MAX_RESPONSE_LENGTH,
                )

            # Clear the auto-reject deadline for finalised items.
            if item.status in (
                QueueStatus.APPROVED.value,
                QueueStatus.REJECTED.value,
                QueueStatus.AUTO_REJECTED.value,
            ):
                item.auto_reject_at = ""

            logger.info(
                "Response reviewed",
                company_id=company_id,
                response_id=response_id,
                reviewer_id=reviewer_id,
                action=action,
                status=item.status,
            )

            return item

        except Exception:
            logger.error(
                "review_response failed (BC-008)",
                company_id=company_id,
                response_id=response_id,
                exc_info=True,
            )
            return None

    # ── Reviewer assignment ────────────────────────────────────

    def assign_reviewer(
        self,
        company_id: str,
        response_id: str,
        reviewer_id: str,
    ) -> Optional[BlockedResponse]:
        """Assign a blocked response to a specific reviewer.

        Sets status to ``in_review`` and records the reviewer.  If a
        reviewer name is already registered in ``_reviewers`` it is
        preserved; otherwise a default placeholder is used.

        Args:
            company_id: Tenant identifier (BC-001).
            response_id: Unique identifier of the blocked response.
            reviewer_id: ID of the agent to assign.

        Returns:
            The updated :class:`BlockedResponse`, or ``None`` if not found.
        """
        try:
            item = self._get_item_safe(company_id, response_id)
            if item is None:
                logger.warning(
                    "assign_reviewer: item not found",
                    company_id=company_id,
                    response_id=response_id,
                )
                return None

            # Only pending items can be assigned.
            if item.status != QueueStatus.PENDING.value:
                logger.warning(
                    "assign_reviewer: item not in pending state (status=%s)",
                    item.status,
                    company_id=company_id,
                    response_id=response_id,
                )
                return item

            now = _now_utc()
            item.reviewer_id = reviewer_id
            item.status = QueueStatus.IN_REVIEW.value
            item.updated_at = now

            # Update the reviewer workload tracker.
            if company_id not in self._reviewers:
                self._reviewers[company_id] = {}

            existing = self._reviewers[company_id].get(reviewer_id)
            if existing:
                existing.assigned_count += 1
                existing.last_assigned_at = now
            else:
                self._reviewers[company_id][reviewer_id] = ReviewerAssignment(
                    reviewer_id=reviewer_id,
                    assigned_count=1,
                    last_assigned_at=now,
                )

            logger.info(
                "Reviewer assigned",
                company_id=company_id,
                response_id=response_id,
                reviewer_id=reviewer_id,
            )

            return item

        except Exception:
            logger.error(
                "assign_reviewer failed (BC-008)",
                company_id=company_id,
                response_id=response_id,
                exc_info=True,
            )
            return None

    # ── Reviewer workload ──────────────────────────────────────

    def get_reviewer_workload(
        self,
        company_id: str,
    ) -> List[ReviewerAssignment]:
        """Get the current workload for all reviewers in a company.

        Returns reviewers sorted by descending assignment count so the
        most-loaded reviewers appear first.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            List of :class:`ReviewerAssignment` entries.
        """
        try:
            company_reviewers = self._reviewers.get(company_id, {})

            # Recalculate actual in-review counts from live queue data.
            company_items = self._queue.get(company_id, {})
            live_counts: Dict[str, int] = {}
            for item in company_items.values():
                if (
                    item.status == QueueStatus.IN_REVIEW.value
                    and item.reviewer_id
                ):
                    live_counts[item.reviewer_id] = (
                        live_counts.get(item.reviewer_id, 0) + 1
                    )

            # Merge tracked data with live counts.
            result: List[ReviewerAssignment] = []
            for reviewer_id, assignment in company_reviewers.items():
                merged = ReviewerAssignment(
                    reviewer_id=reviewer_id,
                    reviewer_name=assignment.reviewer_name,
                    assigned_count=live_counts.get(
                        reviewer_id, assignment.assigned_count,
                    ),
                    last_assigned_at=assignment.last_assigned_at,
                )
                result.append(merged)

            # Include reviewers found in live data but not yet tracked.
            for reviewer_id, count in live_counts.items():
                if reviewer_id not in company_reviewers:
                    result.append(
                        ReviewerAssignment(
                            reviewer_id=reviewer_id,
                            assigned_count=count,
                        )
                    )

            result.sort(key=lambda r: r.assigned_count, reverse=True)
            return result

        except Exception:
            logger.error(
                "get_reviewer_workload failed (BC-008)",
                company_id=company_id,
                exc_info=True,
            )
            return []

    # ── Escalation ─────────────────────────────────────────────

    def escalate_response(
        self,
        company_id: str,
        response_id: str,
        reason: str,
    ) -> Optional[BlockedResponse]:
        """Escalate a blocked response for higher-level review.

        Sets the reviewer action to ``escalated`` and preserves the
        ``in_review`` status.  The escalation reason is stored in
        ``review_notes``.

        Args:
            company_id: Tenant identifier (BC-001).
            response_id: Unique identifier of the blocked response.
            reason: Free-text reason for escalation.

        Returns:
            The updated :class:`BlockedResponse`, or ``None`` if not found.
        """
        try:
            item = self._get_item_safe(company_id, response_id)
            if item is None:
                logger.warning(
                    "escalate_response: item not found",
                    company_id=company_id,
                    response_id=response_id,
                )
                return None

            now = _now_utc()
            item.reviewer_action = ReviewAction.ESCALATED.value
            item.review_notes = _safe_truncate(
                str(reason or ""), _MAX_NOTES_LENGTH,
            )
            item.status = QueueStatus.IN_REVIEW.value
            item.updated_at = now

            # Optionally boost priority on escalation.
            priority_order = [
                ReviewPriority.LOW.value,
                ReviewPriority.MEDIUM.value,
                ReviewPriority.HIGH.value,
            ]
            if item.priority in priority_order:
                current_idx = priority_order.index(item.priority)
                item.priority = priority_order[min(
                    current_idx + 1, len(priority_order) - 1,
                )]

            logger.info(
                "Response escalated",
                company_id=company_id,
                response_id=response_id,
                reason=reason[:200],
                new_priority=item.priority,
            )

            return item

        except Exception:
            logger.error(
                "escalate_response failed (BC-008)",
                company_id=company_id,
                response_id=response_id,
                exc_info=True,
            )
            return None

    # ── Batch review ───────────────────────────────────────────

    def batch_review(
        self,
        company_id: str,
        response_ids: List[str],
        reviewer_id: str,
        action: str,
        notes: Optional[str] = None,
    ) -> List[BlockedResponse]:
        """Apply the same review action to multiple responses at once.

        Args:
            company_id: Tenant identifier (BC-001).
            response_ids: List of blocked-response IDs to review.
            reviewer_id: ID of the reviewer performing the batch action.
            action: One of the :class:`ReviewAction` values.
            notes: Optional notes applied to every item.

        Returns:
            List of updated :class:`BlockedResponse` records.
        """
        results: List[BlockedResponse] = []
        for rid in response_ids:
            try:
                reviewed = self.review_response(
                    company_id=company_id,
                    response_id=rid,
                    reviewer_id=reviewer_id,
                    action=action,
                    notes=notes,
                )
                if reviewed is not None:
                    results.append(reviewed)
            except Exception:
                logger.error(
                    "batch_review: failed for response_id=%s (BC-008)",
                    rid,
                    company_id=company_id,
                    exc_info=True,
                )

        logger.info(
            "Batch review completed",
            company_id=company_id,
            reviewer_id=reviewer_id,
            action=action,
            requested_count=len(response_ids),
            processed_count=len(results),
        )

        return results

    # ── Auto-reject processing ─────────────────────────────────

    def process_auto_rejects(self, company_id: str) -> int:
        """Find and auto-reject expired items in the review queue.

        Any item whose ``auto_reject_at`` timestamp has passed and whose
        status is still ``pending`` or ``in_review`` is transitioned to
        ``auto_rejected``.

        This method is designed to be called by a periodic task
        (e.g. Celery beat).

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            The number of items auto-rejected in this pass.
        """
        try:
            company_items = self._queue.get(company_id, {})
            now = datetime.now(timezone.utc)
            rejected_count = 0

            for item in list(company_items.values()):
                # Only act on items that are still actionable.
                if item.status not in (
                    QueueStatus.PENDING.value,
                    QueueStatus.IN_REVIEW.value,
                ):
                    continue

                deadline = _parse_iso(item.auto_reject_at)
                if deadline is None:
                    continue

                if now >= deadline:
                    item.status = QueueStatus.AUTO_REJECTED.value
                    item.reviewer_action = ReviewAction.AUTO_REJECTED.value
                    item.review_notes = (
                        f"Auto-rejected: review deadline expired "
                        f"at {item.auto_reject_at}"
                    )
                    item.reviewed_at = _now_utc()
                    item.updated_at = _now_utc()
                    item.auto_reject_at = ""
                    rejected_count += 1

            if rejected_count > 0:
                logger.info(
                    "Auto-rejected expired items",
                    company_id=company_id,
                    rejected_count=rejected_count,
                )

            return rejected_count

        except Exception:
            logger.error(
                "process_auto_rejects failed (BC-008)",
                company_id=company_id,
                exc_info=True,
            )
            return 0

    # ── Lifecycle cleanup ──────────────────────────────────────

    def cleanup_old_records(self, company_id: str, days: int = 90) -> int:
        """Delete old, fully-processed records from the queue.

        Removes items that have been in a terminal state
        (approved, rejected, auto_rejected, expired) for longer than
        *days* days.  This satisfies BC-010 (data lifecycle compliance).

        Items that are still ``pending`` or ``in_review`` are never
        cleaned up, regardless of age.

        Args:
            company_id: Tenant identifier (BC-001).
            days: Retention period in days (default 90).

        Returns:
            The number of records deleted.
        """
        try:
            company_items = self._queue.get(company_id, {})
            if not company_items:
                return 0

            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(days=max(1, days))
            deleted_count = 0

            terminal_statuses = {
                QueueStatus.APPROVED.value,
                QueueStatus.REJECTED.value,
                QueueStatus.AUTO_REJECTED.value,
                QueueStatus.EXPIRED.value,
            }

            ids_to_delete: List[str] = []
            for rid, item in company_items.items():
                if item.status not in terminal_statuses:
                    continue

                # Use updated_at (last mutation) as the reference point.
                updated = _parse_iso(item.updated_at)
                if updated is None:
                    updated = _parse_iso(item.created_at)
                if updated is None:
                    continue

                if updated < cutoff:
                    ids_to_delete.append(rid)

            for rid in ids_to_delete:
                del company_items[rid]
                deleted_count += 1

            if deleted_count > 0:
                logger.info(
                    "Cleaned up old records",
                    company_id=company_id,
                    deleted_count=deleted_count,
                    retention_days=days,
                )

            return deleted_count

        except Exception:
            logger.error(
                "cleanup_old_records failed (BC-008)",
                company_id=company_id,
                exc_info=True,
            )
            return 0

    # ── Internal helpers ───────────────────────────────────────

    def _get_item_safe(
        self,
        company_id: str,
        response_id: str,
    ) -> Optional[BlockedResponse]:
        """Safely retrieve a single item from the in-memory store.

        Args:
            company_id: Tenant identifier.
            response_id: Unique response identifier.

        Returns:
            The :class:`BlockedResponse`, or ``None``.
        """
        company_items = self._queue.get(company_id, {})
        return company_items.get(response_id)

    # ── Utility: process auto-rejects for all companies ────────

    def process_all_auto_rejects(self) -> int:
        """Run auto-reject processing for every known company.

        Convenience method for a system-wide periodic task.

        Returns:
            Total number of items auto-rejected across all companies.
        """
        total = 0
        for company_id in list(self._queue.keys()):
            total += self.process_auto_rejects(company_id)
        return total

    # ── Utility: cleanup old records for all companies ─────────

    def cleanup_all_old_records(self, days: int = 90) -> int:
        """Run lifecycle cleanup for every known company.

        Convenience method for a system-wide periodic task.

        Args:
            days: Retention period in days (default 90).

        Returns:
            Total number of records deleted across all companies.
        """
        total = 0
        for company_id in list(self._queue.keys()):
            total += self.cleanup_old_records(company_id, days=days)
        return total

    # ── Utility: get queue counts across all companies ─────────

    def get_global_queue_summary(self) -> Dict[str, Any]:
        """Return a high-level summary of the review queue globally.

        Useful for admin dashboards and system health monitoring.

        Returns:
            Dict with keys: total_companies, total_items,
            total_pending, total_in_review, total_approved,
            total_rejected, total_auto_rejected, total_expired.
        """
        try:
            summary: Dict[str, Any] = {
                "total_companies": len(self._queue),
                "total_items": 0,
                "total_pending": 0,
                "total_in_review": 0,
                "total_approved": 0,
                "total_rejected": 0,
                "total_auto_rejected": 0,
                "total_expired": 0,
            }

            for company_items in self._queue.values():
                for item in company_items.values():
                    summary["total_items"] += 1
                    status_key = f"total_{item.status}"
                    if status_key in summary:
                        summary[status_key] += 1

            return summary

        except Exception:
            logger.error(
                "get_global_queue_summary failed (BC-008)",
                exc_info=True,
            )
            return {
                "total_companies": 0,
                "total_items": 0,
                "total_pending": 0,
                "total_in_review": 0,
                "total_approved": 0,
                "total_rejected": 0,
                "total_auto_rejected": 0,
                "total_expired": 0,
            }

    # ── Utility: reset queue (testing / teardown) ──────────────

    def reset(self) -> None:
        """Clear all in-memory data.  For testing purposes only."""
        self._queue.clear()
        self._reviewers.clear()
        logger.info("BlockedResponseManager queue reset")
