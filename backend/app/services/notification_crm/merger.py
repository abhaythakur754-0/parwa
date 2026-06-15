"""
Notification Merger — Merges similar notifications into batches.

Merging Rules:
  1. Same notification_type → candidate for merging
  2. Similar content (title/description similarity > 0.7) → merge
  3. Same refund_reason → merge refund batches
  4. Same confusion topic → merge confusion notifications
  5. Max 50 items per batch (for UI readability)

Similarity Detection:
  - Keyword overlap for titles
  - Shared root words for descriptions
  - Exact match for refund_reason
  - Category match for confusion types
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.logger import get_logger
from app.services.notification_crm.models import (
    NotificationBatch,
    NotificationItem,
    NotificationType,
)

logger = get_logger("notification_merger")


def _keyword_overlap(text1: str, text2: str) -> float:
    """Calculate keyword overlap similarity between two texts.

    Uses simple word overlap. For production, use embeddings.
    """
    if not text1 or not text2:
        return 0.0

    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union) if union else 0.0


def _are_similar(item1: NotificationItem, item2: NotificationItem) -> bool:
    """Check if two notification items are similar enough to merge."""
    # Must be same type
    if item1.notification_type != item2.notification_type:
        return False

    # Must be same company
    if item1.company_id != item2.company_id:
        return False

    # Type-specific matching
    if item1.notification_type == NotificationType.REFUND_REQUEST:
        # Refunds: merge by same reason
        return item1.refund_reason.lower() == item2.refund_reason.lower()

    if item1.notification_type in (NotificationType.CONFUSION_ON_PRODUCT,
                                     NotificationType.CONFUSION_ON_BILLING):
        # Confusion: merge by similar topic
        title_sim = _keyword_overlap(item1.title, item2.title)
        return title_sim > 0.5

    if item1.notification_type == NotificationType.ASK_CLIENT:
        # Ask-client: merge by similar question
        question_sim = _keyword_overlap(item1.ask_client_question, item2.ask_client_question)
        return question_sim > 0.6

    # General: title similarity
    title_sim = _keyword_overlap(item1.title, item2.title)
    return title_sim > 0.7


class NotificationMerger:
    """Merges similar notifications into batches for efficient processing.

    When multiple customers have the same type of issue, we merge them
    into ONE notification so the client can address them in bulk.

    Example:
      50 customers confused about the same billing charge → 1 notification
      30 refund requests for "defective product" → 1 batch notification
    """

    def __init__(self, company_id: str):
        self.company_id = company_id
        self._batches: List[NotificationBatch] = []

    def add_notification(self, item: NotificationItem) -> NotificationBatch:
        """Add a notification item, merging if similar batch exists.

        Args:
            item: The notification item to add.

        Returns:
            The batch (existing or new) that the item was added to.
        """
        if item.company_id != self.company_id:
            item.company_id = self.company_id

        # Try to find a similar batch
        for batch in self._batches:
            if batch.notification_type != item.notification_type:
                continue
            if batch.status != "pending":
                continue

            # Check if this item is similar to items in the batch
            if batch.items and _are_similar(item, batch.items[0]):
                if batch.add_item(item):
                    logger.info(
                        "notification_merged",
                        item_id=item.id,
                        batch_id=batch.id,
                        batch_size=len(batch.items),
                    )
                    return batch

        # No similar batch found — create new one
        batch = NotificationBatch(
            notification_type=item.notification_type,
            title=item.title,
            description=item.description,
            company_id=self.company_id,
            items=[item],
        )

        # Build Jarvis context from the item
        batch.jarvis_context = {
            "type": item.notification_type,
            "ticket_id": item.ticket_id,
            "conversation_id": item.conversation_id,
            "variant_tier": item.variant_tier,
            "confidence": item.confidence,
            "customer_context": item.context,
            "ask_client_question": item.ask_client_question,
            "ask_client_options": item.ask_client_options,
        }

        self._batches.append(batch)

        logger.info(
            "notification_batch_created",
            batch_id=batch.id,
            type=item.notification_type,
            title=item.title,
        )

        return batch

    def get_pending_batches(self) -> List[NotificationBatch]:
        """Get all pending notification batches."""
        return [b for b in self._batches if b.status == "pending"]

    def get_batches_by_type(self, notif_type: NotificationType) -> List[NotificationBatch]:
        """Get batches by notification type."""
        return [b for b in self._batches if b.notification_type == notif_type]

    def get_refund_batches(self) -> List[NotificationBatch]:
        """Get all refund batches (for refund-first display)."""
        return [
            b for b in self._batches
            if b.notification_type == NotificationType.REFUND_REQUEST
            and b.status == "pending"
        ]

    def get_all_batches(self) -> List[NotificationBatch]:
        """Get all batches."""
        return list(self._batches)

    def mark_batch_viewed(self, batch_id: str) -> Optional[NotificationBatch]:
        """Mark a batch as viewed (client opened it)."""
        for batch in self._batches:
            if batch.id == batch_id:
                batch.status = "viewed"
                return batch
        return None

    def resolve_batch(self, batch_id: str, resolution: str,
                      resolution_data: Dict[str, Any] = None) -> Optional[NotificationBatch]:
        """Mark a batch as resolved with resolution details."""
        for batch in self._batches:
            if batch.id == batch_id:
                batch.status = "resolved"
                batch.resolution = resolution
                batch.resolution_data = resolution_data or {}
                return batch
        return None
