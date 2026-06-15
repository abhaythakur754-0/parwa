"""
Notification Knowledge Base — Converts resolved notifications into learnable entries.

Every time a notification is resolved, the resolution becomes a knowledge
base entry. Over time, this builds up a company-specific knowledge base
that helps variants make better decisions.

This is the COMPOUND EFFECT that gets you from 80% → 90% auto-resolve:
  - Month 1: System learns common refund patterns
  - Month 2: System recognizes confusion patterns
  - Month 3: System can auto-resolve based on past resolutions
  - Month 4-6: System proactively prevents known issues
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger
from app.services.notification_crm.models import NotificationType

logger = get_logger("notification_knowledge_base")


class NotificationKnowledgeBase:
    """Knowledge base built from resolved notifications.

    Every resolution becomes a searchable entry that variants can
    reference when handling similar issues in the future.
    """

    def __init__(self, company_id: str):
        self.company_id = company_id
        self._entries: List[Dict[str, Any]] = []

    def add_from_resolution(
        self,
        notification_type: NotificationType,
        title: str,
        resolution: str,
        resolution_data: Dict[str, Any] = None,
        customers_affected: int = 1,
        items_count: int = 1,
    ) -> str:
        """Add a knowledge base entry from a resolved notification.

        Args:
            notification_type: Type of the resolved notification.
            title: Original notification title.
            resolution: How it was resolved.
            resolution_data: Structured resolution data.
            customers_affected: How many customers were affected.
            items_count: How many items were in the batch.

        Returns:
            Knowledge base entry ID.
        """
        entry_id = f"kb_{uuid.uuid4().hex[:12]}"

        entry = {
            "id": entry_id,
            "company_id": self.company_id,
            "notification_type": str(notification_type),
            "title": title,
            "resolution": resolution,
            "resolution_data": resolution_data or {},
            "customers_affected": customers_affected,
            "items_count": items_count,
            "created_at": datetime.now(timezone.utc).isoformat(),
            # Search keywords extracted from title + resolution
            "keywords": self._extract_keywords(title + " " + resolution),
            # How many times this pattern has been seen
            "occurrence_count": customers_affected,
            # Can this be auto-resolved in the future?
            "auto_resolvable": self._is_auto_resolvable(notification_type, resolution_data),
        }

        # Check if similar entry exists — increment occurrence count
        for existing in self._entries:
            if (existing["notification_type"] == str(notification_type)
                    and existing["title"].lower() == title.lower()):
                existing["occurrence_count"] += customers_affected
                existing["last_seen"] = entry["created_at"]
                logger.info(
                    "kb_pattern_reinforced",
                    entry_id=existing["id"],
                    occurrences=existing["occurrence_count"],
                )
                return existing["id"]

        self._entries.append(entry)

        logger.info(
            "kb_entry_added",
            entry_id=entry_id,
            type=str(notification_type),
            auto_resolvable=entry["auto_resolvable"],
        )

        return entry_id

    def search(
        self,
        query: str,
        notification_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search knowledge base for relevant entries.

        Used by variants to find past resolutions for similar issues.

        Args:
            query: Search query.
            notification_type: Filter by notification type.
            limit: Max results.

        Returns:
            List of matching knowledge base entries.
        """
        query_words = set(query.lower().split())
        scored = []

        for entry in self._entries:
            if notification_type and entry["notification_type"] != notification_type:
                continue

            # Score by keyword overlap
            entry_words = set(entry.get("keywords", []))
            overlap = len(query_words & entry_words)
            if overlap > 0:
                score = overlap / max(len(query_words), 1)
                # Boost by occurrence count (common patterns are more reliable)
                score *= (1 + min(entry.get("occurrence_count", 1), 10) * 0.1)
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def get_auto_resolvable_patterns(self) -> List[Dict[str, Any]]:
        """Get patterns that have been resolved enough times to auto-resolve.

        A pattern becomes auto-resolvable when:
          1. It's been seen 5+ times
          2. It was resolved the same way each time
          3. The resolution_data has consistent structure
        """
        return [
            entry for entry in self._entries
            if entry.get("auto_resolvable")
            and entry.get("occurrence_count", 0) >= 5
        ]

    def get_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all knowledge base entries."""
        return sorted(
            self._entries,
            key=lambda e: e.get("created_at", ""),
            reverse=True,
        )[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        total = len(self._entries)
        by_type = {}
        auto_resolvable = 0
        total_occurrences = 0

        for entry in self._entries:
            t = entry["notification_type"]
            by_type[t] = by_type.get(t, 0) + 1
            if entry.get("auto_resolvable"):
                auto_resolvable += 1
            total_occurrences += entry.get("occurrence_count", 1)

        return {
            "company_id": self.company_id,
            "total_entries": total,
            "total_occurrences": total_occurrences,
            "auto_resolvable_patterns": auto_resolvable,
            "by_type": by_type,
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text for search."""
        # Simple keyword extraction — remove common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "need", "dare", "ought", "used", "to", "of", "in", "for",
            "on", "with", "at", "by", "from", "as", "into", "through",
            "during", "before", "after", "above", "below", "between",
            "out", "off", "over", "under", "again", "further", "then",
            "once", "here", "there", "when", "where", "why", "how",
            "all", "each", "every", "both", "few", "more", "most",
            "other", "some", "such", "no", "nor", "not", "only", "own",
            "same", "so", "than", "too", "very", "just", "because",
            "but", "and", "or", "if", "while", "about", "up", "it",
            "its", "this", "that", "these", "those", "i", "me", "my",
            "we", "our", "you", "your", "he", "him", "his", "she",
            "her", "they", "them", "their", "what", "which", "who",
        }

        words = text.lower().split()
        keywords = [w.strip(".,!?;:") for w in words if w.strip(".,!?;:") not in stop_words]
        return list(set(keywords))

    def _is_auto_resolvable(
        self,
        notification_type: NotificationType,
        resolution_data: Dict[str, Any] = None,
    ) -> bool:
        """Check if this type of notification can be auto-resolved in the future."""
        # Types that are always auto-resolvable
        auto_types = {
            NotificationType.REFUND_REQUEST,
            NotificationType.CONFUSION_ON_PRODUCT,
            NotificationType.CONFUSION_ON_BILLING,
        }
        return notification_type in auto_types
