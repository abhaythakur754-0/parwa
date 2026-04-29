"""
Production Gap Fixes - Critical Utilities

This module provides utility functions and classes to address
production-critical gaps identified in the gap analysis.

GAP-002: Payment failure distributed lock
GAP-003: Chunked content PII detection
GAP-004: Confidence score optimistic locking
GAP-005: Training data tenant isolation
GAP-006: Tier transition usage freeze
"""

import hashlib
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("production_gaps")


# ═══════════════════════════════════════════════════════════════════════════════
# GAP-002: Payment Failure Distributed Lock
# ═══════════════════════════════════════════════════════════════════════════════


class PaymentFailureLock:
    """
    Distributed lock for payment failure state transitions.

    Ensures that only one payment failure processing can happen at a time
    for a given company, preventing race conditions during state transitions.

    Usage:
        async with PaymentFailureLock(redis, company_id, timeout=30) as acquired:
            if acquired:
                # Process payment failure atomically
                await process_failure(company_id)
    """

    LOCK_PREFIX = "parwa:payment_failure_lock:"
    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(self, redis_client, company_id: str, timeout: int = None):
        self.redis = redis_client
        self.company_id = company_id
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.lock_key = f"{self.LOCK_PREFIX}{company_id}"
        self.lock_value = str(uuid.uuid4())
        self._acquired = False

    async def acquire(self) -> bool:
        """Try to acquire the lock. Returns True if successful."""
        try:
            # SET with NX (only if not exists) and EX (expiry)
            result = await self.redis.set(
                self.lock_key,
                self.lock_value,
                nx=True,
                ex=self.timeout,
            )
            self._acquired = result is not None
            if self._acquired:
                logger.info(
                    "payment_failure_lock_acquired company_id=%s lock_key=%s",
                    self.company_id,
                    self.lock_key,
                )
            else:
                logger.warning(
                    "payment_failure_lock_failed company_id=%s lock_key=%s",
                    self.company_id,
                    self.lock_key,
                )
            return self._acquired
        except Exception as e:
            logger.error(
                "payment_failure_lock_error company_id=%s error=%s",
                self.company_id,
                str(e),
            )
            return False

    async def release(self) -> bool:
        """Release the lock if we own it."""
        if not self._acquired:
            return True

        try:
            # Only delete if we own the lock (check value)
            current_value = await self.redis.get(self.lock_key)
            if current_value and current_value.decode() == self.lock_value:
                await self.redis.delete(self.lock_key)
                logger.info(
                    "payment_failure_lock_released company_id=%s",
                    self.company_id,
                )
            self._acquired = False
            return True
        except Exception as e:
            logger.error(
                "payment_failure_lock_release_error company_id=%s error=%s",
                self.company_id,
                str(e),
            )
            return False

    async def __aenter__(self) -> bool:
        return await self.acquire()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()


# ═══════════════════════════════════════════════════════════════════════════════
# GAP-003: Chunked Content PII Detection
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class PIIChunkResult:
    """Result of PII detection on chunked content."""

    has_pii: bool
    pii_types: List[str]
    locations: List[Dict[str, Any]]
    chunk_index: Optional[int] = None
    is_cross_boundary: bool = False


class ChunkAwarePIIDetector:
    """
    PII detector that handles content split into chunks.

    Uses sliding window approach to detect PII that spans chunk boundaries.

    Usage:
        detector = ChunkAwarePIIDetector(overlap_size=50)
        results = detector.detect_chunks(chunks)
        if results.has_pii:
            print(f"Found {results.pii_types}")
    """

    DEFAULT_OVERLAP_SIZE = 50

    # PII patterns
    PATTERNS = {
        "ssn": re.compile(r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b"),
        "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        "email": re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    }

    def __init__(self, overlap_size: int = None):
        self.overlap_size = overlap_size or self.DEFAULT_OVERLAP_SIZE

    def detect_chunks(
        self,
        chunks: List[str],
    ) -> PIIChunkResult:
        """
        Detect PII across multiple chunks using sliding window.

        Args:
            chunks: List of text chunks to analyze

        Returns:
            PIIChunkResult with detection information
        """
        all_pii_types = set()
        all_locations = []

        previous_tail = ""

        for i, chunk in enumerate(chunks):
            # Combine with overlap from previous chunk
            combined = previous_tail + chunk

            # Detect PII in combined text
            for pii_type, pattern in self.PATTERNS.items():
                matches = list(pattern.finditer(combined))
                for match in matches:
                    # Check if match is in the overlap region (cross-boundary)
                    is_cross_boundary = match.start() < len(previous_tail)

                    all_pii_types.add(pii_type)
                    all_locations.append(
                        {
                            "type": pii_type,
                            "value": match.group(),
                            "chunk_index": i,
                            "is_cross_boundary": is_cross_boundary,
                            "start": match.start(),
                            "end": match.end(),
                        }
                    )

            # Store tail for next iteration
            previous_tail = (
                chunk[-self.overlap_size :]
                if len(chunk) >= self.overlap_size
                else chunk
            )

        return PIIChunkResult(
            has_pii=len(all_pii_types) > 0,
            pii_types=list(all_pii_types),
            locations=all_locations,
        )

    def detect_single(self, text: str) -> PIIChunkResult:
        """Detect PII in a single text string."""
        return self.detect_chunks([text])


# ═══════════════════════════════════════════════════════════════════════════════
# GAP-004: Confidence Score Optimistic Locking
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ConfidenceScore:
    """
    Confidence score with optimistic locking support.

    Includes version field for detecting concurrent modifications.
    """

    score: float
    version: int = 0
    components: Dict[str, float] = field(default_factory=dict)
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ConfidenceScoreManager:
    """
    Manager for confidence scores with optimistic locking.

    Prevents lost updates when multiple agents update the same score.

    Usage:
        manager = ConfidenceScoreManager()

        # Get current score with version
        current = manager.get_score(ticket_id)

        # Try to update (fails if version mismatch)
        success = manager.update_score(
            ticket_id,
            new_score=0.85,
            expected_version=current.version,
        )
    """

    # In-memory store (replace with Redis/DB in production)
    _store: Dict[str, ConfidenceScore] = {}
    _lock = threading.Lock()

    def get_score(self, entity_id: str) -> Optional[ConfidenceScore]:
        """Get current confidence score with version."""
        with self._lock:
            return self._store.get(entity_id)

    def update_score(
        self,
        entity_id: str,
        new_score: float,
        expected_version: int,
        components: Optional[Dict[str, float]] = None,
    ) -> Tuple[bool, Optional[ConfidenceScore]]:
        """
        Update score with optimistic locking.

        Returns:
            Tuple of (success, new_score_if_successful)
        """
        with self._lock:
            current = self._store.get(entity_id)

            # Check version
            if current and current.version != expected_version:
                logger.warning(
                    "confidence_score_version_mismatch entity_id=%s "
                    "expected=%s actual=%s",
                    entity_id,
                    expected_version,
                    current.version,
                )
                return False, current

            # Create new score with incremented version
            new_version = (current.version + 1) if current else 1
            new_confidence = ConfidenceScore(
                score=new_score,
                version=new_version,
                components=components or {},
            )

            self._store[entity_id] = new_confidence

            logger.info(
                "confidence_score_updated entity_id=%s score=%s version=%s",
                entity_id,
                new_score,
                new_version,
            )

            return True, new_confidence

    def init_score(
        self,
        entity_id: str,
        initial_score: float = 0.5,
        components: Optional[Dict[str, float]] = None,
    ) -> ConfidenceScore:
        """Initialize a new confidence score."""
        with self._lock:
            confidence = ConfidenceScore(
                score=initial_score,
                version=1,
                components=components or {},
            )
            self._store[entity_id] = confidence
            return confidence


# ═══════════════════════════════════════════════════════════════════════════════
# GAP-005: Training Data Tenant Isolation
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class VectorSearchFilters:
    """
    Mandatory filters for vector search queries.

    Ensures tenant and variant isolation in vector index queries.
    """

    company_id: str
    variant_id: Optional[str] = None
    additional_filters: Dict[str, Any] = field(default_factory=dict)

    def to_metadata_filter(self) -> Dict[str, Any]:
        """Convert to metadata filter dict for vector search."""
        filters = {
            "company_id": self.company_id,
        }
        if self.variant_id:
            filters["variant_id"] = self.variant_id
        filters.update(self.additional_filters)
        return filters

    def validate(self) -> bool:
        """Validate that required filters are present."""
        if not self.company_id:
            raise ValueError("company_id is required for vector search")
        return True


def build_training_record(
    content: str,
    embedding: List[float],
    company_id: str,
    variant_id: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a training record with mandatory isolation metadata.

    Ensures all training data includes company_id and variant_id
    for proper isolation in vector index.
    """
    record = {
        "id": str(uuid.uuid4()),
        "content": content,
        "embedding": embedding,
        "metadata": {
            "company_id": company_id,
            "variant_id": variant_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": hashlib.sha256(content.encode()).hexdigest()[:16],
        },
    }

    if metadata:
        record["metadata"].update(metadata)

    return record


# ═══════════════════════════════════════════════════════════════════════════════
# GAP-006: Tier Transition Usage Freeze
# ═══════════════════════════════════════════════════════════════════════════════


class TierTransitionLock:
    """
    Lock for tier transitions to freeze usage counting during upgrade/downgrade.

    Prevents race conditions where tickets could be counted against wrong tier.

    Usage:
        async with TierTransitionLock(redis, company_id) as lock:
            # Usage counting is frozen
            await upgrade_tier(company_id, new_tier)
            # Lock releases, usage counting resumes with new tier
    """

    LOCK_PREFIX = "parwa:tier_transition_lock:"
    DEFAULT_TIMEOUT = 60  # seconds

    def __init__(self, redis_client, company_id: str, timeout: int = None):
        self.redis = redis_client
        self.company_id = company_id
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.lock_key = f"{self.LOCK_PREFIX}{company_id}"
        self._acquired = False

    async def is_locked(self) -> bool:
        """Check if tier transition is in progress."""
        try:
            value = await self.redis.get(self.lock_key)
            return value is not None
        except Exception:
            return False

    async def acquire(self) -> bool:
        """Acquire the tier transition lock."""
        try:
            result = await self.redis.set(
                self.lock_key,
                str(uuid.uuid4()),
                nx=True,
                ex=self.timeout,
            )
            self._acquired = result is not None

            if self._acquired:
                logger.info(
                    "tier_transition_lock_acquired company_id=%s",
                    self.company_id,
                )

            return self._acquired
        except Exception as e:
            logger.error(
                "tier_transition_lock_error company_id=%s error=%s",
                self.company_id,
                str(e),
            )
            return False

    async def release(self) -> bool:
        """Release the tier transition lock."""
        if not self._acquired:
            return True

        try:
            await self.redis.delete(self.lock_key)
            self._acquired = False
            logger.info(
                "tier_transition_lock_released company_id=%s",
                self.company_id,
            )
            return True
        except Exception as e:
            logger.error(
                "tier_transition_lock_release_error company_id=%s error=%s",
                self.company_id,
                str(e),
            )
            return False

    async def __aenter__(self) -> "TierTransitionLock":
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()


async def check_usage_allowed_during_transition(redis_client, company_id: str) -> bool:
    """
    Check if usage operations are allowed (not frozen during tier transition).

    Returns:
        True if usage operations are allowed, False if frozen.
    """
    lock = TierTransitionLock(redis_client, company_id)
    return not await lock.is_locked()


# ═══════════════════════════════════════════════════════════════════════════════
# GAP-013: Tenant Cache Invalidation
# ═══════════════════════════════════════════════════════════════════════════════


async def delete_all_tenant_redis_keys(redis_client, company_id: str) -> int:
    """
    Delete all Redis keys for a tenant.

    Called when a tenant account is deleted to ensure no cached data remains.

    Args:
        redis_client: Redis client instance
        company_id: Tenant ID to delete keys for

    Returns:
        Number of keys deleted
    """
    pattern = f"parwa:{company_id}:*"
    deleted_count = 0

    try:
        # SCAN for keys matching pattern
        cursor = 0
        while True:
            cursor, keys = await redis_client.scan(
                cursor=cursor,
                match=pattern,
                count=100,
            )

            if keys:
                await redis_client.delete(*keys)
                deleted_count += len(keys)

            if cursor == 0:
                break

        logger.info(
            "tenant_cache_invalidated company_id=%s keys_deleted=%s",
            company_id,
            deleted_count,
        )

        return deleted_count

    except Exception as e:
        logger.error(
            "tenant_cache_invalidation_error company_id=%s error=%s",
            company_id,
            str(e),
        )
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# Export Summary
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # GAP-002
    "PaymentFailureLock",
    # GAP-003
    "ChunkAwarePIIDetector",
    "PIIChunkResult",
    # GAP-004
    "ConfidenceScore",
    "ConfidenceScoreManager",
    # GAP-005
    "VectorSearchFilters",
    "build_training_record",
    # GAP-006
    "TierTransitionLock",
    "check_usage_allowed_during_transition",
    # GAP-013
    "delete_all_tenant_redis_keys",
]
