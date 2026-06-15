"""
Notification Batcher — Merges similar requests into batched notifications.

Groups incoming notification items by type, customer, content similarity, and
time window so that the CRM UI shows ONE actionable notification instead of
ten near-identical alerts.

Key features:
- Similarity detection via keyword overlap and optional embedding cosine sim
- Configurable batching window (default 30 min) with Redis TTL
- Max batch size cap (default 10) to keep notifications scannable
- Type-specific merge rules (refund_batch, confusion, escalation_needed, …)
- Batch context extraction for Jarvis chat integration

BC-001: All keys are tenant-scoped via ``parwa:{company_id}:*``.
BC-008: Never crashes — graceful degradation on Redis / embedding failures.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.redis import get_redis, make_key
from app.logger import get_logger

logger = get_logger("notification_batcher")

# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

BATCH_WINDOW_SECONDS: int = 1800  # 30 minutes
MAX_BATCH_SIZE: int = 10
BATCH_TTL_SECONDS: int = 86400  # 24 hours
MIN_KEYWORD_OVERLAP: float = 0.40  # Jaccard threshold for "similar content"

# Stop-words stripped before keyword extraction
_STOP_WORDS: Set[str] = {
    "a", "an", "the", "is", "it", "of", "for", "in", "on", "to", "and",
    "or", "with", "this", "that", "i", "me", "my", "we", "our", "you",
    "your", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "not", "no", "but", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "can", "could", "will", "would", "should", "may", "might", "shall",
}


class NotificationType(str, Enum):
    """Notification type taxonomy for the CRM UI."""

    REFUND_BATCH = "refund_batch"
    CONFUSION = "confusion"
    ESCALATION_NEEDED = "escalation_needed"
    APPROVAL_REQUIRED = "approval_required"
    QUALITY_ALERT = "quality_alert"
    CLIENT_QUESTION = "client_question"


class BatchStatus(str, Enum):
    """Lifecycle status of a batch group."""

    OPEN = "open"
    CLOSED = "closed"
    EXPIRED = "expired"


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class BatchItem:
    """A single item that may be merged into a batch notification.

    Attributes:
        id: Unique identifier (usually a ticket / request ID).
        notification_type: Semantic type from NotificationType enum.
        customer_id: Customer who triggered the item.
        content: Free-text description of the issue.
        metadata: Arbitrary extra data (amount, topic, variant_tier …).
        created_at: ISO-8601 timestamp.
    """

    id: str
    notification_type: str
    customer_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class BatchGroup:
    """Represents a batch of similar items stored in Redis.

    Attributes:
        batch_id: Unique batch identifier.
        company_id: Tenant scope.
        notification_type: Merged type for the batch.
        content_hash: Hash key used for dedup grouping.
        items: Ordered list of BatchItem objects.
        status: Current lifecycle status.
        created_at: When the first item was added.
        updated_at: When the batch was last modified.
    """

    batch_id: str
    company_id: str
    notification_type: str
    content_hash: str
    items: List[BatchItem] = field(default_factory=list)
    status: str = BatchStatus.OPEN
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ══════════════════════════════════════════════════════════════════
# SIMILARITY HELPERS
# ══════════════════════════════════════════════════════════════════


def _extract_keywords(text: str) -> Set[str]:
    """Return a set of meaningful keywords from *text*.

    Lowercases, strips punctuation, removes stop-words, and discards
    tokens shorter than 3 characters.
    """
    if not text:
        return set()
    tokens = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower()).split()
    return {t for t in tokens if len(t) >= 3 and t not in _STOP_WORDS}


def _jaccard_similarity(a: Set[str], b: Set[str]) -> float:
    """Compute Jaccard similarity between two keyword sets."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def _compute_content_hash(notification_type: str, keywords: Set[str]) -> str:
    """Produce a deterministic hash used for grouping similar items in Redis.

    The hash incorporates the notification type and the top-N most frequent
    keywords so that semantically close items land in the same bucket.
    """
    # Sort for determinism, take top 10 keywords
    top_keywords = sorted(keywords)[:10]
    raw = f"{notification_type}::{','.join(top_keywords)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _are_similar(
    item_a: BatchItem,
    item_b: BatchItem,
    keyword_cache: Optional[Dict[str, Set[str]]] = None,
) -> bool:
    """Decide whether two items are similar enough to batch together.

    Rules (all must pass):
    1. Same notification type.
    2. Within the batch time window.
    3. Content similarity >= MIN_KEYWORD_OVERLAP  OR  same customer.
    """
    # Rule 1: same type
    if item_a.notification_type != item_b.notification_type:
        return False

    # Rule 2: time window
    try:
        ts_a = datetime.fromisoformat(item_a.created_at)
        ts_b = datetime.fromisoformat(item_b.created_at)
        if abs((ts_a - ts_b).total_seconds()) > BATCH_WINDOW_SECONDS:
            return False
    except (ValueError, TypeError):
        pass  # malformed timestamps — allow batching

    # Rule 3: same customer → always batchable
    if item_a.customer_id and item_a.customer_id == item_b.customer_id:
        return True

    # Rule 3b: keyword overlap
    kw_a = (keyword_cache or {}).get(item_a.id) or _extract_keywords(item_a.content)
    kw_b = (keyword_cache or {}).get(item_b.id) or _extract_keywords(item_b.content)
    return _jaccard_similarity(kw_a, kw_b) >= MIN_KEYWORD_OVERLAP


# ══════════════════════════════════════════════════════════════════
# NOTIFICATION BATCHER
# ══════════════════════════════════════════════════════════════════


class NotificationBatcher:
    """Merges similar incoming items into batched notifications.

    Usage::

        batcher = NotificationBatcher()
        result = await batcher.add_item(
            company_id="acme",
            item=BatchItem(
                id="tkt_001",
                notification_type="refund_batch",
                customer_id="cust_42",
                content="Customer requests refund for order #1234",
                metadata={"amount": 49.99},
            ),
        )
        # result is a dict with batch_id, is_new_batch, items_count, …

    All state is held in Redis with TTLs so stale batches auto-expire.
    """

    def __init__(
        self,
        batch_window_seconds: int = BATCH_WINDOW_SECONDS,
        max_batch_size: int = MAX_BATCH_SIZE,
        batch_ttl_seconds: int = BATCH_TTL_SECONDS,
    ) -> None:
        self._batch_window = batch_window_seconds
        self._max_batch_size = max_batch_size
        self._batch_ttl = batch_ttl_seconds

    # ── Public API ───────────────────────────────────────────────

    async def add_item(
        self, company_id: str, item: BatchItem
    ) -> Dict[str, Any]:
        """Add *item* to an existing batch or create a new one.

        Returns a dict describing the outcome::

            {
                "batch_id": "b_abc123",
                "is_new_batch": True,
                "items_count": 1,
                "notification_type": "refund_batch",
                "title": "Refund Batch",
                "jarvis_context": { … },
            }
        """
        try:
            redis = await get_redis()
            keywords = _extract_keywords(item.content)
            content_hash = _compute_content_hash(item.notification_type, keywords)

            # Look for an existing open batch that matches
            batch = await self._find_matching_batch(
                redis, company_id, item, content_hash
            )

            if batch is not None and len(batch.items) < self._max_batch_size:
                # Merge into existing batch
                batch.items.append(item)
                batch.updated_at = datetime.now(timezone.utc).isoformat()
                await self._save_batch(redis, company_id, batch)
                logger.info(
                    "batch_item_merged",
                    batch_id=batch.batch_id,
                    item_id=item.id,
                    items_count=len(batch.items),
                    company_id=company_id,
                )
                return self._build_result(batch, is_new_batch=False)
            else:
                # Create a new batch
                batch_id = self._generate_batch_id(company_id, content_hash)
                batch = BatchGroup(
                    batch_id=batch_id,
                    company_id=company_id,
                    notification_type=item.notification_type,
                    content_hash=content_hash,
                    items=[item],
                )
                await self._save_batch(redis, company_id, batch)
                # Register batch in the company's batch index
                index_key = make_key(company_id, "ncrm", "batch_index")
                await redis.sadd(index_key, batch_id)
                await redis.expire(index_key, self._batch_ttl)
                logger.info(
                    "batch_created",
                    batch_id=batch_id,
                    item_id=item.id,
                    notification_type=item.notification_type,
                    company_id=company_id,
                )
                return self._build_result(batch, is_new_batch=True)

        except Exception as exc:
            logger.error(
                "batcher_add_item_failed",
                item_id=item.id,
                company_id=company_id,
                error=str(exc)[:200],
            )
            # Return a minimal result so callers never crash (BC-008)
            return {
                "batch_id": f"fallback_{item.id}",
                "is_new_batch": True,
                "items_count": 1,
                "notification_type": item.notification_type,
                "title": self._type_to_title(item.notification_type),
                "jarvis_context": {
                    "items": [self._item_to_dict(item)],
                    "fallback": True,
                },
            }

    async def get_batch(
        self, company_id: str, batch_id: str
    ) -> Optional[BatchGroup]:
        """Retrieve a batch by ID.  Returns None if not found or expired."""
        try:
            redis = await get_redis()
            key = make_key(company_id, "ncrm", "batch", batch_id)
            raw = await redis.get(key)
            if raw is None:
                return None
            return self._deserialize_batch(raw)
        except Exception as exc:
            logger.error("batcher_get_batch_failed", batch_id=batch_id, error=str(exc)[:200])
            return None

    async def get_open_batches(
        self, company_id: str, notification_type: Optional[str] = None
    ) -> List[BatchGroup]:
        """Return all open batches for a company, optionally filtered by type."""
        try:
            redis = await get_redis()
            index_key = make_key(company_id, "ncrm", "batch_index")
            batch_ids = await redis.smembers(index_key)
            batches: List[BatchGroup] = []
            for bid in batch_ids:
                batch = await self.get_batch(company_id, bid)
                if batch is None or batch.status != BatchStatus.OPEN:
                    continue
                if notification_type and batch.notification_type != notification_type:
                    continue
                batches.append(batch)
            return batches
        except Exception as exc:
            logger.error("batcher_get_open_batches_failed", error=str(exc)[:200])
            return []

    async def close_batch(self, company_id: str, batch_id: str) -> bool:
        """Mark a batch as closed so it no longer accepts new items."""
        try:
            batch = await self.get_batch(company_id, batch_id)
            if batch is None:
                return False
            batch.status = BatchStatus.CLOSED
            batch.updated_at = datetime.now(timezone.utc).isoformat()
            redis = await get_redis()
            await self._save_batch(redis, company_id, batch)
            logger.info("batch_closed", batch_id=batch_id, company_id=company_id)
            return True
        except Exception as exc:
            logger.error("batcher_close_batch_failed", batch_id=batch_id, error=str(exc)[:200])
            return False

    async def get_jarvis_context(
        self, company_id: str, batch_id: str
    ) -> Dict[str, Any]:
        """Build the context payload Jarvis receives when a notification is clicked.

        Includes:
        - notification_type and human-readable title
        - all items in the batch with their metadata
        - suggested action options based on the type
        - total amount for refund batches
        """
        try:
            batch = await self.get_batch(company_id, batch_id)
            if batch is None:
                return {"error": "batch_not_found", "batch_id": batch_id}

            items_data = [self._item_to_dict(i) for i in batch.items]
            ctx: Dict[str, Any] = {
                "batch_id": batch.batch_id,
                "notification_type": batch.notification_type,
                "title": self._type_to_title(batch.notification_type),
                "items": items_data,
                "items_count": len(batch.items),
                "created_at": batch.created_at,
                "updated_at": batch.updated_at,
            }

            # Type-specific enrichment
            if batch.notification_type == NotificationType.REFUND_BATCH:
                total = sum(
                    float(i.metadata.get("amount", 0)) for i in batch.items
                )
                ctx["total_amount"] = round(total, 2)
                ctx["action_options"] = [
                    {"id": "approve_all", "label": "Approve All Refunds"},
                    {"id": "review_each", "label": "Review Each Refund"},
                    {"id": "reject_all", "label": "Reject All Refunds"},
                ]
            elif batch.notification_type == NotificationType.CONFUSION:
                topics = list(
                    {i.metadata.get("topic", "unknown") for i in batch.items}
                )
                ctx["confusion_topics"] = topics
                ctx["action_options"] = [
                    {"id": "send_clarification", "label": "Send Clarification to All"},
                    {"id": "review_each", "label": "Review Each Individually"},
                    {"id": "update_docs", "label": "Update Help Docs"},
                ]
            elif batch.notification_type == NotificationType.ESCALATION_NEEDED:
                ctx["action_options"] = [
                    {"id": "take_over", "label": "Take Over Conversation"},
                    {"id": "provide_guidance", "label": "Provide Guidance to Variant"},
                    {"id": "dismiss", "label": "Dismiss Escalation"},
                ]
            elif batch.notification_type == NotificationType.APPROVAL_REQUIRED:
                ctx["action_options"] = [
                    {"id": "approve", "label": "Approve Action"},
                    {"id": "deny", "label": "Deny Action"},
                    {"id": "modify", "label": "Modify and Approve"},
                ]
            elif batch.notification_type == NotificationType.QUALITY_ALERT:
                ctx["action_options"] = [
                    {"id": "investigate", "label": "Investigate Quality Drop"},
                    {"id": "adjust_threshold", "label": "Adjust Quality Threshold"},
                    {"id": "dismiss", "label": "Dismiss Alert"},
                ]
            elif batch.notification_type == NotificationType.CLIENT_QUESTION:
                ctx["action_options"] = [
                    {"id": "answer", "label": "Answer Question"},
                    {"id": "schedule_call", "label": "Schedule a Call"},
                    {"id": "dismiss", "label": "Dismiss"},
                ]

            return ctx
        except Exception as exc:
            logger.error(
                "batcher_jarvis_context_failed",
                batch_id=batch_id,
                error=str(exc)[:200],
            )
            return {"error": "context_generation_failed", "detail": str(exc)[:200]}

    # ── Private helpers ──────────────────────────────────────────

    async def _find_matching_batch(
        self,
        redis,
        company_id: str,
        item: BatchItem,
        content_hash: str,
    ) -> Optional[BatchGroup]:
        """Search open batches for one that matches *item* by hash then similarity."""
        # Fast path: exact content-hash match
        hash_key = make_key(
            company_id, "ncrm", "batch_hash", item.notification_type, content_hash
        )
        existing_batch_id = await redis.get(hash_key)
        if existing_batch_id:
            batch = await self.get_batch(company_id, existing_batch_id)
            if batch and batch.status == BatchStatus.OPEN:
                # Verify time window is still valid
                if self._is_within_window(batch):
                    return batch
                else:
                    # Batch expired — close it and let a new one be created
                    await self.close_batch(company_id, batch.batch_id)

        # Slow path: scan open batches for similarity
        open_batches = await self.get_open_batches(
            company_id, notification_type=item.notification_type
        )
        for batch in open_batches:
            if not self._is_within_window(batch):
                continue
            # Compare against the latest item in the batch as representative
            if batch.items and _are_similar(item, batch.items[-1]):
                return batch

        return None

    def _is_within_window(self, batch: BatchGroup) -> bool:
        """Check whether the batch's most recent item is within the window."""
        try:
            latest = datetime.fromisoformat(batch.updated_at)
            elapsed = (datetime.now(timezone.utc) - latest).total_seconds()
            return elapsed <= self._batch_window
        except (ValueError, TypeError):
            return True  # Malformed timestamp — assume within window

    async def _save_batch(
        self, redis, company_id: str, batch: BatchGroup
    ) -> None:
        """Persist a BatchGroup to Redis with TTL."""
        key = make_key(company_id, "ncrm", "batch", batch.batch_id)
        serialized = self._serialize_batch(batch)
        await redis.set(key, serialized, ex=self._batch_ttl)

        # Also maintain the content-hash → batch_id mapping
        hash_key = make_key(
            company_id, "ncrm", "batch_hash", batch.notification_type, batch.content_hash
        )
        await redis.set(hash_key, batch.batch_id, ex=self._batch_ttl)

    @staticmethod
    def _generate_batch_id(company_id: str, content_hash: str) -> str:
        """Deterministic yet unique batch ID."""
        raw = f"{company_id}:{content_hash}:{time.time_ns()}"
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"b_{h}"

    @staticmethod
    def _type_to_title(notification_type: str) -> str:
        """Human-readable title for a notification type."""
        _TITLES = {
            NotificationType.REFUND_BATCH: "Refund Batch",
            NotificationType.CONFUSION: "Customer Confusion",
            NotificationType.ESCALATION_NEEDED: "Escalation Needed",
            NotificationType.APPROVAL_REQUIRED: "Approval Required",
            NotificationType.QUALITY_ALERT: "Quality Alert",
            NotificationType.CLIENT_QUESTION: "Client Question",
        }
        return _TITLES.get(notification_type, "Notification")

    def _build_result(
        self, batch: BatchGroup, *, is_new_batch: bool
    ) -> Dict[str, Any]:
        """Shape the return value for add_item()."""
        return {
            "batch_id": batch.batch_id,
            "is_new_batch": is_new_batch,
            "items_count": len(batch.items),
            "notification_type": batch.notification_type,
            "title": self._type_to_title(batch.notification_type),
            "jarvis_context": {
                "batch_id": batch.batch_id,
                "notification_type": batch.notification_type,
                "items": [self._item_to_dict(i) for i in batch.items],
                "total_amount": (
                    round(sum(float(i.metadata.get("amount", 0)) for i in batch.items), 2)
                    if batch.notification_type == NotificationType.REFUND_BATCH
                    else None
                ),
            },
        }

    @staticmethod
    def _item_to_dict(item: BatchItem) -> Dict[str, Any]:
        """Convert a BatchItem to a JSON-safe dict."""
        return {
            "id": item.id,
            "notification_type": item.notification_type,
            "customer_id": item.customer_id,
            "content": item.content,
            "metadata": item.metadata,
            "created_at": item.created_at,
        }

    # ── Serialization ────────────────────────────────────────────

    @staticmethod
    def _serialize_batch(batch: BatchGroup) -> str:
        """Serialize BatchGroup to JSON string for Redis storage."""
        return json.dumps({
            "batch_id": batch.batch_id,
            "company_id": batch.company_id,
            "notification_type": batch.notification_type,
            "content_hash": batch.content_hash,
            "items": [
                {
                    "id": i.id,
                    "notification_type": i.notification_type,
                    "customer_id": i.customer_id,
                    "content": i.content,
                    "metadata": i.metadata,
                    "created_at": i.created_at,
                }
                for i in batch.items
            ],
            "status": batch.status,
            "created_at": batch.created_at,
            "updated_at": batch.updated_at,
        })

    @staticmethod
    def _deserialize_batch(raw: str) -> BatchGroup:
        """Reconstruct a BatchGroup from Redis JSON string."""
        data = json.loads(raw)
        items = [
            BatchItem(
                id=i["id"],
                notification_type=i["notification_type"],
                customer_id=i["customer_id"],
                content=i["content"],
                metadata=i.get("metadata", {}),
                created_at=i.get("created_at", ""),
            )
            for i in data.get("items", [])
        ]
        return BatchGroup(
            batch_id=data["batch_id"],
            company_id=data["company_id"],
            notification_type=data["notification_type"],
            content_hash=data["content_hash"],
            items=items,
            status=data.get("status", BatchStatus.OPEN),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


# ── Singleton ────────────────────────────────────────────────────

_notification_batcher: Optional[NotificationBatcher] = None


def get_notification_batcher() -> NotificationBatcher:
    """Return the module-level NotificationBatcher singleton."""
    global _notification_batcher
    if _notification_batcher is None:
        _notification_batcher = NotificationBatcher()
    return _notification_batcher
