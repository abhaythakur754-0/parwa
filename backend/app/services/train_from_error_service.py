"""
PARWA Train from Error Service (F-092) — Error-to-Training Pipeline

Converts error entries into training data points for AI model improvement.
Provides a one-click workflow for operators to flag errors as learning
opportunities and submit corrected responses.

Features:
- Create training data points from error entries
- Auto-extract context: error message, stack trace, affected ticket, AI response
- Deduplication: check for existing training_data_points with same error_id + ticket_id
- PII redaction on training data before storage (BC-010)
- Support manual correction notes and correct_response from operator
- Review workflow: queued_for_review → approved/rejected → in_dataset

Methods:
- create_training_point() — Create a new training point from an error
- get_training_points() — List training points with filters
- review_training_point() — Approve/reject a training point
- get_training_stats() — Aggregated training pipeline statistics

Building Codes: BC-001 (multi-tenant), BC-007 (AI model),
               BC-010 (GDPR/compliance), BC-012 (error handling)
"""

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("train_from_error_service")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Default pagination
DEFAULT_LIMIT = 20
MAX_LIMIT = 100

# Valid review actions
VALID_REVIEW_ACTIONS = {"approved", "rejected", "needs_revision"}

# Valid training statuses for filtering
VALID_STATUSES = {
    "queued_for_review", "approved", "rejected", "in_dataset", "archived",
}

# PII patterns for inline redaction (lightweight, BC-010)
_PII_PATTERNS = [
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
]


# ══════════════════════════════════════════════════════════════════
# PII REDACTION HELPERS (BC-010)
# ══════════════════════════════════════════════════════════════════


def _redact_pii(text: str) -> str:
    """Lightweight PII redaction for training data.

    Replaces emails, phone numbers, and SSNs with placeholders.
    Uses inline regex patterns — no external dependencies.

    BC-010: All training data is PII-redacted before storage.
    """
    if not text:
        return text

    redacted = text
    for pattern, replacement in _PII_PATTERNS:
        redacted = pattern.sub(replacement, redacted)

    return redacted


def _redact_dict(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Recursively redact PII from a dictionary's string values."""
    if not data:
        return data

    redacted = {}
    for key, value in data.items():
        if isinstance(value, str):
            redacted[key] = _redact_pii(value)
        elif isinstance(value, dict):
            redacted[key] = _redact_dict(value)
        elif isinstance(value, list):
            redacted[key] = [
                _redact_pii(item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            redacted[key] = value

    return redacted


# ══════════════════════════════════════════════════════════════════
# SERVICE FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def create_training_point(
    company_id: str,
    db,
    error_id: str,
    created_by: str,
    ticket_id: Optional[str] = None,
    correction_notes: Optional[str] = None,
    expected_response: Optional[str] = None,
    source: str = "error_manual",
) -> Dict[str, Any]:
    """Create a training data point from an error entry.

    Auto-extracts context from the error log (message, stack trace,
    affected ticket data). Deduplicates by checking for existing
    training points with the same error_id + ticket_id. All text
    fields are PII-redacted before storage (BC-010).

    Args:
        company_id: Tenant identifier (BC-001).
        db: SQLAlchemy session.
        error_id: The error log UUID to convert.
        created_by: ID of the operator creating this training point.
        ticket_id: Optional ticket ID (if error was ticket-related).
        correction_notes: Optional manual notes from the operator.
        expected_response: Optional correct response from the operator.
        source: Source of the training data (default 'error_manual').

    Returns:
        Created training point dictionary.
    """
    try:
        from app.models.system_health import ErrorLog, TrainingDataPoint

        # 1. Fetch the source error
        error = db.query(ErrorLog).filter(
            ErrorLog.id == error_id,
            ErrorLog.company_id == company_id,
        ).first()

        if not error:
            return {
                "error": "Error not found",
                "error_id": error_id,
            }

        # 2. Deduplication check
        existing = db.query(TrainingDataPoint).filter(
            TrainingDataPoint.company_id == company_id,
            TrainingDataPoint.error_id == error_id,
            TrainingDataPoint.ticket_id == ticket_id,
        ).first()

        if existing:
            return {
                "message": "Training point already exists for this error+ticket combination",
                "training_point_id": str(existing.id),
                "status": existing.status,
                "error_id": error_id,
                "ticket_id": ticket_id,
            }

        # 3. Auto-extract context from error
        input_context = json.dumps({
            "error_type": error.error_type,
            "error_message": error.message,
            "subsystem": error.subsystem,
            "severity": error.severity,
            "affected_ticket_id": error.affected_ticket_id,
            "affected_agent_id": error.affected_agent_id,
        })

        # Get AI response if this error was ticket-related
        ai_response = None
        if error.affected_ticket_id:
            ai_response = _extract_ai_response(
                company_id, error.affected_ticket_id, db,
            )

        # 4. PII-redact all text fields (BC-010)
        safe_input_context = _redact_pii(input_context)
        safe_ai_response = _redact_pii(ai_response) if ai_response else None
        safe_expected_response = _redact_pii(expected_response) if expected_response else None
        safe_correction_notes = _redact_pii(correction_notes) if correction_notes else None

        # 5. Determine intent label from error type
        intent_label = _infer_intent_label(error.error_type, error.message)

        # 6. Create the training data point
        training_point = TrainingDataPoint(
            company_id=company_id,
            error_id=error_id,
            ticket_id=ticket_id,
            input_context=safe_input_context,
            ai_response=safe_ai_response,
            expected_response=safe_expected_response,
            correction_notes=safe_correction_notes,
            intent_label=intent_label,
            source=source,
            status="queued_for_review",
            created_by=created_by,
        )
        db.add(training_point)
        db.flush()

        logger.info(
            "training_point_created",
            company_id=company_id,
            training_point_id=str(training_point.id),
            error_id=error_id,
            source=source,
            created_by=created_by,
        )

        return {
            "id": str(training_point.id),
            "company_id": company_id,
            "error_id": error_id,
            "ticket_id": ticket_id,
            "intent_label": intent_label,
            "source": source,
            "status": training_point.status,
            "created_by": created_by,
            "created_at": (
                training_point.created_at.isoformat()
                if training_point.created_at else None
            ),
            "pii_redacted": True,
        }

    except Exception as exc:
        logger.error(
            "train_from_error_create_error",
            company_id=company_id,
            error_id=error_id,
            error=str(exc),
        )
        return {
            "error": str(exc)[:200],
            "error_id": error_id,
        }


def get_training_points(
    company_id: str,
    db,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    status: Optional[str] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """List training data points with optional filters.

    Args:
        company_id: Tenant identifier (BC-001).
        db: SQLAlchemy session.
        limit: Pagination limit.
        offset: Pagination offset.
        status: Optional status filter.
        source: Optional source filter.

    Returns:
        Dictionary with training points list and metadata.
    """
    try:
        from app.models.system_health import TrainingDataPoint

        query = db.query(TrainingDataPoint).filter(
            TrainingDataPoint.company_id == company_id,
        )

        if status and status in VALID_STATUSES:
            query = query.filter(TrainingDataPoint.status == status)
        if source:
            query = query.filter(TrainingDataPoint.source == source)

        total = query.count()

        effective_limit = min(max(limit, 1), MAX_LIMIT)
        points = (
            query
            .order_by(TrainingDataPoint.created_at.desc())
            .offset(offset)
            .limit(effective_limit)
            .all()
        )

        return {
            "training_points": [
                {
                    "id": str(tp.id),
                    "company_id": tp.company_id,
                    "error_id": tp.error_id,
                    "ticket_id": tp.ticket_id,
                    "intent_label": tp.intent_label,
                    "source": tp.source,
                    "status": tp.status,
                    "created_by": tp.created_by,
                    "reviewed_by": tp.reviewed_by,
                    "created_at": (
                        tp.created_at.isoformat() if tp.created_at else None
                    ),
                    "reviewed_at": (
                        tp.reviewed_at.isoformat() if tp.reviewed_at else None
                    ),
                    "has_correction": bool(tp.correction_notes),
                    "has_expected_response": bool(tp.expected_response),
                }
                for tp in points
            ],
            "total": total,
            "limit": effective_limit,
            "offset": offset,
        }

    except Exception as exc:
        logger.error(
            "train_from_error_list_error",
            company_id=company_id,
            error=str(exc),
        )
        return {
            "training_points": [],
            "total": 0,
            "error": str(exc)[:200],
        }


def review_training_point(
    training_point_id: str,
    company_id: str,
    db,
    reviewer_id: str,
    action: str,
    review_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Review a training data point (approve, reject, or request revision).

    Workflow:
    - queued_for_review → approved → in_dataset (after batch commit)
    - queued_for_review → rejected → archived
    - queued_for_review → needs_revision → back to create

    Args:
        training_point_id: The training point UUID.
        company_id: Tenant identifier (BC-001).
        db: SQLAlchemy session.
        reviewer_id: ID of the reviewer.
        action: Review action ('approved', 'rejected', 'needs_revision').
        review_notes: Optional notes from the reviewer.

    Returns:
        Updated training point dictionary.
    """
    if action not in VALID_REVIEW_ACTIONS:
        return {
            "error": f"Invalid action '{action}'. Must be one of: {', '.join(sorted(VALID_REVIEW_ACTIONS))}",
            "training_point_id": training_point_id,
        }

    try:
        from app.models.system_health import TrainingDataPoint

        tp = db.query(TrainingDataPoint).filter(
            TrainingDataPoint.id == training_point_id,
            TrainingDataPoint.company_id == company_id,
        ).first()

        if not tp:
            return {
                "error": "Training point not found",
                "training_point_id": training_point_id,
            }

        if tp.status not in ("queued_for_review", "needs_revision"):
            return {
                "error": f"Cannot review training point in status '{tp.status}'",
                "training_point_id": training_point_id,
                "current_status": tp.status,
            }

        # Apply the review action
        previous_status = tp.status
        if action == "approved":
            tp.status = "approved"
        elif action == "rejected":
            tp.status = "rejected"
        elif action == "needs_revision":
            tp.status = "queued_for_review"

        tp.reviewed_by = reviewer_id
        tp.reviewed_at = datetime.now(timezone.utc)

        # Append review notes to correction_notes if provided
        if review_notes:
            safe_notes = _redact_pii(review_notes)
            existing_notes = tp.correction_notes or ""
            separator = "\n---\n" if existing_notes else ""
            tp.correction_notes = f"{existing_notes}{separator}[REVIEW by {reviewer_id}]: {safe_notes}"

        db.flush()

        logger.info(
            "training_point_reviewed",
            company_id=company_id,
            training_point_id=training_point_id,
            action=action,
            reviewer_id=reviewer_id,
            previous_status=previous_status,
            new_status=tp.status,
        )

        return {
            "id": str(tp.id),
            "training_point_id": training_point_id,
            "previous_status": previous_status,
            "new_status": tp.status,
            "action": action,
            "reviewed_by": reviewer_id,
            "reviewed_at": (
                tp.reviewed_at.isoformat() if tp.reviewed_at else None
            ),
        }

    except Exception as exc:
        logger.error(
            "train_from_error_review_error",
            company_id=company_id,
            training_point_id=training_point_id,
            error=str(exc),
        )
        return {
            "error": str(exc)[:200],
            "training_point_id": training_point_id,
        }


def get_training_stats(
    company_id: str,
    db,
) -> Dict[str, Any]:
    """Get aggregated training pipeline statistics.

    Returns counts by status, source, and recent activity for the
    training pipeline dashboard.

    Args:
        company_id: Tenant identifier (BC-001).
        db: SQLAlchemy session.

    Returns:
        Dictionary with training statistics.
    """
    try:
        from app.models.system_health import TrainingDataPoint
        from sqlalchemy import func

        # Total count
        total = db.query(func.count(TrainingDataPoint.id)).filter(
            TrainingDataPoint.company_id == company_id,
        ).scalar() or 0

        # By status
        status_counts = db.query(
            TrainingDataPoint.status, func.count(TrainingDataPoint.id),
        ).filter(
            TrainingDataPoint.company_id == company_id,
        ).group_by(TrainingDataPoint.status).all()

        by_status = {row[0]: row[1] for row in status_counts}

        # By source
        source_counts = db.query(
            TrainingDataPoint.source, func.count(TrainingDataPoint.id),
        ).filter(
            TrainingDataPoint.company_id == company_id,
        ).group_by(TrainingDataPoint.source).all()

        by_source = {row[0]: row[1] for row in source_counts}

        # By intent label (top 10)
        intent_counts = db.query(
            TrainingDataPoint.intent_label, func.count(TrainingDataPoint.id),
        ).filter(
            TrainingDataPoint.company_id == company_id,
            TrainingDataPoint.intent_label.isnot(None),
        ).group_by(TrainingDataPoint.intent_label).order_by(
            func.count(TrainingDataPoint.id).desc(),
        ).limit(10).all()

        by_intent = [
            {"intent": row[0], "count": row[1]}
            for row in intent_counts
        ]

        # Recently reviewed (last 24 hours)
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_reviews = db.query(func.count(TrainingDataPoint.id)).filter(
            TrainingDataPoint.company_id == company_id,
            TrainingDataPoint.reviewed_at >= since,
        ).scalar() or 0

        # Ready for dataset (approved)
        ready_for_dataset = by_status.get("approved", 0)

        return {
            "total": total,
            "by_status": by_status,
            "by_source": by_source,
            "by_intent": by_intent,
            "recent_reviews_24h": recent_reviews,
            "ready_for_dataset": ready_for_dataset,
            "review_backlog": by_status.get("queued_for_review", 0),
        }

    except Exception as exc:
        logger.error(
            "train_from_error_stats_error",
            company_id=company_id,
            error=str(exc),
        )
        return {
            "total": 0,
            "by_status": {},
            "by_source": {},
            "by_intent": [],
            "error": str(exc)[:200],
        }


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _extract_ai_response(
    company_id: str,
    ticket_id: str,
    db,
) -> Optional[str]:
    """Extract the last AI response for a ticket.

    Tries to find the most recent AI-generated message for the ticket.
    """
    try:
        from database.models.tickets import Ticket
        from database.models.tickets import TicketMessage

        # Check if TicketMessage model exists
        msg = db.query(TicketMessage).filter(
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.company_id == company_id,
            TicketMessage.sender_type == "ai",
        ).order_by(TicketMessage.created_at.desc()).first()

        if msg:
            return getattr(msg, "content", None) or getattr(msg, "body", None)

    except Exception:
        pass

    return None


def _infer_intent_label(error_type: str, message: str) -> str:
    """Infer an intent label from the error type and message.

    Uses simple heuristic matching to categorize errors into
    intent labels suitable for training.
    """
    if not error_type and not message:
        return "unknown"

    text = f"{error_type} {message}".lower()

    # Classification errors
    if any(kw in text for kw in ("classification", "intent", "category")):
        return "classification_error"

    # Response generation errors
    if any(kw in text for kw in ("generation", "response", "ai_response", "llm")):
        return "response_generation_error"

    # Integration errors
    if any(kw in text for kw in ("integration", "webhook", "api", "paddle", "brevo")):
        return "integration_error"

    # Auth errors
    if any(kw in text for kw in ("auth", "token", "jwt", "permission")):
        return "authentication_error"

    # Database errors
    if any(kw in text for kw in ("database", "db", "sql", "query", "postgres")):
        return "database_error"

    # Timeout errors
    if any(kw in text for kw in ("timeout", "timed out", "deadline")):
        return "timeout_error"

    # Rate limit errors
    if any(kw in text for kw in ("rate limit", "429", "throttle")):
        return "rate_limit_error"

    # Default
    return "general_error"


__all__ = [
    "create_training_point",
    "get_training_points",
    "review_training_point",
    "get_training_stats",
]
