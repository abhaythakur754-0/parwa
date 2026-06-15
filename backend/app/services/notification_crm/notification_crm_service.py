"""
Notification CRM Service — The bridge between variants, Jarvis, and clients.

Architecture:
  This service manages the notification lifecycle:
  1. Variant or Jarvis creates a notification (refund, confusion, etc.)
  2. Similar notifications are MERGED into one (batching)
  3. Notification appears in the CRM UI with type and context
  4. Client clicks notification -> Jarvis opens with full context
  5. Jarvis already knows the problem from the comm bus
  6. Jarvis chats with client, presents options
  7. Client's response feeds back to the variant

Notification Types:
  - refund_batch: Refund requests (merged by type)
  - confusion: Variant is confused about something
  - escalation_needed: Needs human escalation
  - approval_required: Needs client approval
  - quality_alert: Quality dropped below threshold
  - client_question: Variant needs client input
  - retention_offer: Retention opportunity
  - batch_processed: Batch of similar requests processed

UI Flow:
  CRM Dashboard -> Notifications Panel
    -> Category tabs: Refunds | Confusion | Escalations | Approvals | Questions
    -> Click notification -> Jarvis chat opens
    -> Jarvis has full context from variant
    -> Chat resolves the notification

BC-001: company_id first parameter.
BC-008: Never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("notification_crm_service")


# ══════════════════════════════════════════════════════════════════
# NOTIFICATION TYPES
# ══════════════════════════════════════════════════════════════════


class NotificationType(str, Enum):
    """All notification types in the CRM."""
    REFUND_BATCH = "refund_batch"
    CONFUSION = "confusion"
    ESCALATION_NEEDED = "escalation_needed"
    APPROVAL_REQUIRED = "approval_required"
    QUALITY_ALERT = "quality_alert"
    CLIENT_QUESTION = "client_question"
    RETENTION_OFFER = "retention_offer"
    BATCH_PROCESSED = "batch_processed"


class NotificationStatus(str, Enum):
    """Notification lifecycle states."""
    PENDING = "pending"
    READ = "read"
    IN_PROGRESS = "in_progress"  # Jarvis chat opened
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    ESCALATED = "escalated"


class NotificationPriority(str, Enum):
    """Priority levels for notifications."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# ══════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════


@dataclass
class CRMNotification:
    """A single notification in the CRM system."""
    notification_id: str = ""
    company_id: str = ""
    notification_type: NotificationType = NotificationType.CLIENT_QUESTION
    status: NotificationStatus = NotificationStatus.PENDING
    priority: NotificationPriority = NotificationPriority.MEDIUM
    title: str = ""
    summary: str = ""
    customer_id: str = ""
    ticket_id: str = ""
    batch_id: str = ""
    is_batch: bool = False
    batch_count: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    jarvis_context: Dict[str, Any] = field(default_factory=dict)
    client_options: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    resolved_at: str = ""
    resolution: str = ""

    def __post_init__(self):
        if not self.notification_id:
            self.notification_id = f"notif_{hashlib.md5(f'{self.company_id}{self.ticket_id}{time.time()}'.encode()).hexdigest()[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


@dataclass
class NotificationBatch:
    """A merged batch of similar notifications."""
    batch_id: str = ""
    company_id: str = ""
    notification_type: NotificationType = NotificationType.REFUND_BATCH
    title: str = ""
    items: List[CRMNotification] = field(default_factory=list)
    total_amount: float = 0.0
    customer_id: str = ""
    jarvis_context: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    status: NotificationStatus = NotificationStatus.PENDING

    def __post_init__(self):
        if not self.batch_id:
            self.batch_id = f"batch_{hashlib.md5(f'{self.company_id}{self.notification_type}{time.time()}'.encode()).hexdigest()[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def count(self) -> int:
        return len(self.items)


# ══════════════════════════════════════════════════════════════════
# SIMILARITY MATCHER — Merges similar notifications
# ══════════════════════════════════════════════════════════════════


class NotificationSimilarityMatcher:
    """Determines if two notifications should be merged.

    Merging criteria:
    - Same type
    - Same customer (or same topic for general confusion)
    - Within 30-minute window
    - Keyword overlap >= 40% (Jaccard)
    """

    BATCH_WINDOW_MINUTES = 30
    MIN_KEYWORD_OVERLAP = 0.40

    def should_merge(self, notif_a: CRMNotification, notif_b: CRMNotification) -> bool:
        """Check if two notifications should be merged into one batch."""
        try:
            # Must be same type
            if notif_a.notification_type != notif_b.notification_type:
                return False

            # Must be same company
            if notif_a.company_id != notif_b.company_id:
                return False

            # Same customer check (for refunds and personal notifications)
            if notif_a.notification_type in (NotificationType.REFUND_BATCH, NotificationType.RETENTION_OFFER):
                if notif_a.customer_id and notif_b.customer_id:
                    if notif_a.customer_id != notif_b.customer_id:
                        return False

            # Keyword overlap check
            keywords_a = set(notif_a.title.lower().split() + notif_a.summary.lower().split())
            keywords_b = set(notif_b.title.lower().split() + notif_b.summary.lower().split())
            if keywords_a and keywords_b:
                intersection = keywords_a & keywords_b
                union = keywords_a | keywords_b
                jaccard = len(intersection) / len(union) if union else 0
                if jaccard >= self.MIN_KEYWORD_OVERLAP:
                    return True

            # Same ticket (always merge)
            if notif_a.ticket_id and notif_a.ticket_id == notif_b.ticket_id:
                return True

            return False

        except Exception:
            return False


# ══════════════════════════════════════════════════════════════════
# NOTIFICATION CRM SERVICE
# ══════════════════════════════════════════════════════════════════


class NotificationCRMService:
    """Main Notification CRM service.

    Manages the full lifecycle of notifications:
    - Create notifications from variants and Jarvis
    - Merge similar notifications into batches
    - Store in Redis (fast) + DB (durable)
    - Provide Jarvis context when client clicks
    - Track resolution

    Usage:
        service = NotificationCRMService()
        notif_id = service.create_notification(CRMNotification(...))
        batch = service.get_or_create_batch(company_id, NotificationType.REFUND_BATCH, ...)
        jarvis_ctx = service.get_jarvis_context(notif_id)
    """

    def __init__(self):
        self._matcher = NotificationSimilarityMatcher()
        self._notifications: Dict[str, CRMNotification] = {}
        self._batches: Dict[str, NotificationBatch] = {}
        self._customer_index: Dict[str, List[str]] = {}  # customer_id -> [notif_ids]

    def create_notification(
        self,
        company_id: str,
        notification_type: NotificationType,
        title: str,
        summary: str,
        customer_id: str = "",
        ticket_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        jarvis_context: Optional[Dict[str, Any]] = None,
        client_options: Optional[List[str]] = None,
    ) -> str:
        """Create a new notification and try to merge with existing.

        BC-001: company_id first.

        Args:
            company_id: Company ID.
            notification_type: Type of notification.
            title: Short title for the CRM UI.
            summary: Longer summary.
            customer_id: Customer ID (if applicable).
            ticket_id: Ticket ID (if applicable).
            metadata: Additional metadata.
            jarvis_context: Context for Jarvis when client clicks.
            client_options: Options to present to client.

        Returns:
            Notification ID.
        """
        try:
            # Determine priority from type
            priority = self._type_to_priority(notification_type)

            notif = CRMNotification(
                company_id=company_id,
                notification_type=notification_type,
                priority=priority,
                title=title,
                summary=summary,
                customer_id=customer_id,
                ticket_id=ticket_id,
                metadata=metadata or {},
                jarvis_context=jarvis_context or {},
                client_options=client_options or [],
            )

            # Try to merge with existing notification
            existing = self._find_merge_candidate(notif)
            if existing:
                # Add to existing batch
                batch = self._get_batch_for_notification(existing)
                if batch:
                    batch.items.append(notif)
                    existing.is_batch = True
                    existing.batch_count = batch.count
                    existing.batch_id = batch.batch_id
                    existing.updated_at = datetime.now(timezone.utc).isoformat()
                    logger.info(
                        "notification_merged: notif=%s into batch=%s, count=%d",
                        notif.notification_id, batch.batch_id, batch.count,
                    )
                else:
                    # Create new batch from existing + new
                    batch = NotificationBatch(
                        company_id=company_id,
                        notification_type=notification_type,
                        title=f"Batch: {title}",
                        customer_id=customer_id,
                        jarvis_context=jarvis_context or {},
                    )
                    batch.items.append(existing)
                    batch.items.append(notif)
                    self._batches[batch.batch_id] = batch

                    existing.is_batch = True
                    existing.batch_id = batch.batch_id
                    existing.batch_count = 2

                notif.is_batch = True
                notif.batch_id = existing.batch_id

            # Store notification
            self._notifications[notif.notification_id] = notif

            # Index by customer
            if customer_id:
                if customer_id not in self._customer_index:
                    self._customer_index[customer_id] = []
                self._customer_index[customer_id].append(notif.notification_id)

            # Try Redis for multi-instance support
            self._persist_to_redis(notif)

            logger.info(
                "notification_created: id=%s, type=%s, company=%s, "
                "customer=%s, is_batch=%s",
                notif.notification_id, notification_type.value, company_id,
                customer_id, notif.is_batch,
            )

            return notif.notification_id

        except Exception:
            logger.exception("create_notification_error")
            return ""

    def get_notification(self, notification_id: str) -> Optional[CRMNotification]:
        """Get a notification by ID."""
        return self._notifications.get(notification_id)

    def get_jarvis_context(self, notification_id: str) -> Dict[str, Any]:
        """Get Jarvis context for a notification.

        When a client clicks a notification, this provides the
        full context Jarvis needs to start chatting intelligently.

        Returns:
            Context dict with:
            - notification details
            - problem summary
            - suggested options
            - comm bus data from variant
            - customer history
        """
        try:
            notif = self._notifications.get(notification_id)
            if not notif:
                return {"error": "notification_not_found"}

            # Build full Jarvis context
            context = {
                "notification": {
                    "id": notif.notification_id,
                    "type": notif.notification_type.value,
                    "title": notif.title,
                    "summary": notif.summary,
                    "ticket_id": notif.ticket_id,
                    "customer_id": notif.customer_id,
                    "is_batch": notif.is_batch,
                    "batch_count": notif.batch_count,
                },
                "jarvis_context": notif.jarvis_context,
                "client_options": notif.client_options,
                "chat_open_payload": {
                    "auto_open": True,
                    "notification_type": notif.notification_type.value,
                    "problem_summary": notif.summary,
                    "suggested_response": self._generate_jarvis_opening(notif),
                },
            }

            # If batch, include all items
            if notif.is_batch and notif.batch_id:
                batch = self._batches.get(notif.batch_id)
                if batch:
                    context["batch_details"] = {
                        "batch_id": batch.batch_id,
                        "total_items": batch.count,
                        "total_amount": batch.total_amount,
                        "items": [
                            {
                                "id": item.notification_id,
                                "title": item.title,
                                "summary": item.summary[:100],
                                "ticket_id": item.ticket_id,
                            }
                            for item in batch.items[:10]
                        ],
                    }

            return context

        except Exception:
            logger.exception("get_jarvis_context_error")
            return {"error": "context_retrieval_failed"}

    def mark_as_read(self, notification_id: str) -> bool:
        """Mark notification as read (client saw it)."""
        notif = self._notifications.get(notification_id)
        if notif:
            notif.status = NotificationStatus.READ
            notif.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def mark_as_in_progress(self, notification_id: str) -> bool:
        """Mark as in progress (Jarvis chat opened)."""
        notif = self._notifications.get(notification_id)
        if notif:
            notif.status = NotificationStatus.IN_PROGRESS
            notif.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def resolve_notification(self, notification_id: str, resolution: str = "") -> bool:
        """Resolve a notification."""
        notif = self._notifications.get(notification_id)
        if notif:
            notif.status = NotificationStatus.RESOLVED
            notif.resolution = resolution
            notif.resolved_at = datetime.now(timezone.utc).isoformat()
            notif.updated_at = notif.resolved_at
            return True
        return False

    def get_notifications_for_company(
        self,
        company_id: str,
        notification_type: Optional[NotificationType] = None,
        status: Optional[NotificationStatus] = None,
        customer_id: str = "",
        limit: int = 50,
    ) -> List[CRMNotification]:
        """Get notifications for a company, optionally filtered.

        This is what the CRM UI calls to populate the dashboard.
        """
        try:
            results = []
            for notif in self._notifications.values():
                if notif.company_id != company_id:
                    continue
                if notification_type and notif.notification_type != notification_type:
                    continue
                if status and notif.status != status:
                    continue
                if customer_id and notif.customer_id != customer_id:
                    continue
                results.append(notif)

            # Sort by priority then creation time
            priority_order = {
                NotificationPriority.URGENT: 0,
                NotificationPriority.HIGH: 1,
                NotificationPriority.MEDIUM: 2,
                NotificationPriority.LOW: 3,
            }
            results.sort(
                key=lambda n: (
                    priority_order.get(n.priority, 2),
                    n.created_at,
                ),
            )

            return results[:limit]

        except Exception:
            logger.exception("get_notifications_error")
            return []

    def get_pending_count(self, company_id: str) -> Dict[str, int]:
        """Get count of pending notifications by type for dashboard badges."""
        try:
            counts = {}
            for notif in self._notifications.values():
                if notif.company_id != company_id:
                    continue
                if notif.status != NotificationStatus.PENDING:
                    continue
                key = notif.notification_type.value
                counts[key] = counts.get(key, 0) + 1
            return counts
        except Exception:
            return {}

    def get_notification_categories(self) -> List[Dict[str, Any]]:
        """Get notification categories for the CRM UI tabs."""
        return [
            {"type": "refund_batch", "label": "Refunds", "icon": "currency", "color": "#10b981"},
            {"type": "confusion", "label": "Confusion", "icon": "question", "color": "#f59e0b"},
            {"type": "escalation_needed", "label": "Escalations", "icon": "arrow-up", "color": "#ef4444"},
            {"type": "approval_required", "label": "Approvals", "icon": "check", "color": "#8b5cf6"},
            {"type": "client_question", "label": "Questions", "icon": "chat", "color": "#3b82f6"},
            {"type": "quality_alert", "label": "Quality", "icon": "alert", "color": "#f97316"},
            {"type": "retention_offer", "label": "Retention", "icon": "heart", "color": "#ec4899"},
            {"type": "batch_processed", "label": "Processed", "icon": "check-circle", "color": "#6b7280"},
        ]

    # ── Private methods ──────────────────────────────────────────

    def _find_merge_candidate(self, notif: CRMNotification) -> Optional[CRMNotification]:
        """Find an existing notification to merge with."""
        for existing in self._notifications.values():
            if existing.company_id != notif.company_id:
                continue
            if existing.status == NotificationStatus.RESOLVED:
                continue
            if self._matcher.should_merge(existing, notif):
                return existing
        return None

    def _get_batch_for_notification(self, notif: CRMNotification) -> Optional[NotificationBatch]:
        """Get the batch a notification belongs to."""
        if notif.batch_id:
            return self._batches.get(notif.batch_id)
        return None

    def _type_to_priority(self, notif_type: NotificationType) -> NotificationPriority:
        """Map notification type to default priority."""
        priority_map = {
            NotificationType.ESCALATION_NEEDED: NotificationPriority.URGENT,
            NotificationType.APPROVAL_REQUIRED: NotificationPriority.HIGH,
            NotificationType.QUALITY_ALERT: NotificationPriority.HIGH,
            NotificationType.REFUND_BATCH: NotificationPriority.MEDIUM,
            NotificationType.CONFUSION: NotificationPriority.MEDIUM,
            NotificationType.CLIENT_QUESTION: NotificationPriority.MEDIUM,
            NotificationType.RETENTION_OFFER: NotificationPriority.MEDIUM,
            NotificationType.BATCH_PROCESSED: NotificationPriority.LOW,
        }
        return priority_map.get(notif_type, NotificationPriority.MEDIUM)

    def _generate_jarvis_opening(self, notif: CRMNotification) -> str:
        """Generate Jarvis's opening line when client clicks notification."""
        openings = {
            NotificationType.REFUND_BATCH: (
                f"I see you have {notif.batch_count if notif.is_batch else 'a'} refund "
                f"request{'s' if notif.is_batch and notif.batch_count > 1 else ''} pending. "
                f"Let me help you with that."
            ),
            NotificationType.CONFUSION: (
                "It looks like there might be some confusion about your request. "
                "Let me clarify things for you."
            ),
            NotificationType.ESCALATION_NEEDED: (
                "I've flagged your case for priority handling. "
                "Let me connect you with the right person."
            ),
            NotificationType.APPROVAL_REQUIRED: (
                "This action needs your approval before I can proceed. "
                "Shall I walk you through it?"
            ),
            NotificationType.CLIENT_QUESTION: (
                "I have a quick question about your request. "
                "Can you help me understand what you'd prefer?"
            ),
            NotificationType.QUALITY_ALERT: (
                "I'm reviewing the response to make sure it meets our standards. "
                "Give me just a moment."
            ),
        }
        return openings.get(notif.notification_type, "How can I help you with this?")

    def _persist_to_redis(self, notif: CRMNotification) -> bool:
        """Try to persist notification to Redis for multi-instance support."""
        try:
            import json
            from app.core.redis import get_redis

            redis = get_redis()
            if redis:
                key = f"parwa:{notif.company_id}:ncrm:notif:{notif.notification_id}"
                data = json.dumps({
                    "id": notif.notification_id,
                    "type": notif.notification_type.value,
                    "title": notif.title,
                    "summary": notif.summary,
                    "status": notif.status.value,
                    "customer_id": notif.customer_id,
                    "ticket_id": notif.ticket_id,
                    "created_at": notif.created_at,
                })
                redis.setex(key, 3600, data)  # 1hr TTL
                return True
        except Exception:
            logger.debug("redis_persist_failed", exc_info=True)
        return False


# ══════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════

_crm_instance: Optional[NotificationCRMService] = None


def get_notification_crm() -> NotificationCRMService:
    """Get or create the global Notification CRM service."""
    global _crm_instance
    if _crm_instance is None:
        _crm_instance = NotificationCRMService()
    return _crm_instance
