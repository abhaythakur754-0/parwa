"""
PARWA Tag Service - MF03 Tag Management (Day 26)

Implements MF03: Tags/Labels with:
- Tag CRUD operations
- Auto-tagging based on content
- Tag-based filtering and search
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database.models.tickets import Ticket


class TagService:
    """Tag management and auto-tagging."""

    # Auto-tag patterns
    AUTO_TAG_PATTERNS = {
        # Product/feature tags
        "api": [r"\bapi\b", r"\brest\b", r"\bgraphql\b", r"\bendpoint\b"],
        "dashboard": [r"\bdashboard\b", r"\bui\b", r"\binterface\b"],
        "mobile": [r"\bmobile\b", r"\bios\b", r"\bandroid\b", r"\bapp\b"],
        "integration": [r"\bintegration\b", r"\bconnect\b", r"\bsync\b"],
        "webhook": [r"\bwebhook\b", r"\bcallback\b"],

        # Issue type tags
        "bug": [r"\bbug\b", r"\berror\b", r"\bcrash\b", r"\bbroken\b"],
        "performance": [r"\bslow\b", r"\bperformance\b", r"\btimeout\b", r"\blag\b"],
        "security": [r"\bsecurity\b", r"\bvulnerability\b", r"\bbreach\b"],
        "data-loss": [r"\bdata loss\b", r"\bmissing data\b", r"\bdeleted\b"],

        # Customer type tags
        "enterprise": [r"\benterprise\b", r"\bcontract\b"],
        "trial": [r"\btrial\b", r"\bdemo\b", r"\bfree\b"],
        "vip": [r"\bvip\b", r"\bexecutive\b", r"\bmanager\b"],

        # Status tags
        "blocked": [r"\bblocked\b", r"\bstuck\b", r"\bcannot proceed\b"],
        "urgent": [r"\burgent\b", r"\bcritical\b", r"\basap\b"],
        "feedback": [r"\bfeedback\b", r"\bsuggestion\b", r"\breview\b"],
    }

    # Tag categories for organization
    TAG_CATEGORIES = {
        "product": ["api", "dashboard", "mobile", "integration", "webhook"],
        "issue": ["bug", "performance", "security", "data-loss"],
        "customer": ["enterprise", "trial", "vip"],
        "status": ["blocked", "urgent", "feedback"],
    }

    # Maximum tags per ticket
    MAX_TAGS_PER_TICKET = 20

    # Maximum tag length
    MAX_TAG_LENGTH = 50

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    def auto_tag(self, text: str) -> List[str]:
        """Generate automatic tags from text content.

        Args:
            text: Text to analyze

        Returns:
            List of auto-detected tags
        """
        if not text:
            return []

        text_lower = text.lower()
        tags = []

        for tag, patterns in self.AUTO_TAG_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    tags.append(tag)
                    break

        return tags

    def add_tags(
        self,
        ticket_id: str,
        tags: List[str],
        auto: bool = False,
    ) -> Tuple[List[str], List[str]]:
        """Add tags to a ticket.

        Args:
            ticket_id: Ticket ID
            tags: Tags to add
            auto: Whether these are auto-generated tags

        Returns:
            Tuple of (current_tags, added_tags)
        """
        # Validate and clean tags
        clean_tags = self._clean_tags(tags)

        # Get ticket
        ticket = self.db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.company_id == self.company_id,
        ).first()

        if not ticket:
            return [], []

        # Get current tags
        current_tags = json.loads(ticket.tags or "[]")

        # Add new tags
        added_tags = []
        for tag in clean_tags:
            if tag not in current_tags:
                if len(current_tags) < self.MAX_TAGS_PER_TICKET:
                    current_tags.append(tag)
                    added_tags.append(tag)

        # Update ticket
        ticket.tags = json.dumps(current_tags)
        ticket.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        return current_tags, added_tags

    def remove_tags(
        self,
        ticket_id: str,
        tags: List[str],
    ) -> Tuple[List[str], List[str]]:
        """Remove tags from a ticket.

        Args:
            ticket_id: Ticket ID
            tags: Tags to remove

        Returns:
            Tuple of (current_tags, removed_tags)
        """
        # Get ticket
        ticket = self.db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.company_id == self.company_id,
        ).first()

        if not ticket:
            return [], []

        # Get current tags
        current_tags = json.loads(ticket.tags or "[]")

        # Remove tags
        removed_tags = []
        for tag in tags:
            if tag in current_tags:
                current_tags.remove(tag)
                removed_tags.append(tag)

        # Update ticket
        ticket.tags = json.dumps(current_tags)
        ticket.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        return current_tags, removed_tags

    def set_tags(
        self,
        ticket_id: str,
        tags: List[str],
    ) -> List[str]:
        """Set ticket tags (replace all existing).

        Args:
            ticket_id: Ticket ID
            tags: New tags list

        Returns:
            Updated tags list
        """
        # Validate and clean tags
        clean_tags = self._clean_tags(tags)[:self.MAX_TAGS_PER_TICKET]

        # Get ticket
        ticket = self.db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.company_id == self.company_id,
        ).first()

        if not ticket:
            return []

        # Update ticket
        ticket.tags = json.dumps(clean_tags)
        ticket.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        return clean_tags

    def get_popular_tags(
        self,
        limit: int = 50,
        category: Optional[str] = None,
    ) -> List[Tuple[str, int]]:
        """Get most popular tags across tickets.

        Args:
            limit: Maximum tags to return
            category: Filter by tag category

        Returns:
            List of (tag, count) tuples
        """
        # Get all ticket tags
        tickets = self.db.query(Ticket.tags).filter(
            Ticket.company_id == self.company_id,
        ).all()

        # Count tags
        tag_counts: Dict[str, int] = {}
        for (tags_json,) in tickets:
            if tags_json:
                tags = json.loads(tags_json)
                for tag in tags:
                    if category:
                        # Filter by category
                        if tag not in self.TAG_CATEGORIES.get(category, []):
                            continue
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Sort by count
        sorted_tags = sorted(
            tag_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return sorted_tags[:limit]

    def search_by_tags(
        self,
        tags: List[str],
        match_all: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Ticket], int]:
        """Search tickets by tags.

        Args:
            tags: Tags to search for
            match_all: If True, ticket must have all tags
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (tickets, total_count)
        """
        query = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
        )

        # Filter by tags
        for tag in tags:
            if match_all:
                query = query.filter(Ticket.tags.contains(f'"{tag}"'))
            else:
                query = query.filter(Ticket.tags.contains(f'"{tag}"'))

        # Count
        total = query.count()

        # Paginate
        offset = (page - 1) * page_size
        tickets = query.offset(offset).limit(page_size).all()

        return tickets, total

    def suggest_tags(
            self,
            text: str,
            existing_tags: List[str] = None) -> List[str]:
        """Suggest tags based on text content.

        Args:
            text: Text to analyze
            existing_tags: Already applied tags

        Returns:
            List of suggested tags
        """
        existing = set(existing_tags or [])
        auto_tags = set(self.auto_tag(text))

        # Remove already applied
        suggestions = auto_tags - existing

        return list(suggestions)

    def get_tag_category(self, tag: str) -> Optional[str]:
        """Get category for a tag.

        Args:
            tag: Tag name

        Returns:
            Category name or None
        """
        for category, tags in self.TAG_CATEGORIES.items():
            if tag in tags:
                return category
        return None

    def _clean_tags(self, tags: List[str]) -> List[str]:
        """Clean and validate tags.

        Args:
            tags: Raw tags list

        Returns:
            Cleaned tags list
        """
        clean = []

        for tag in tags:
            if not tag:
                continue

            # Normalize: lowercase, replace spaces with dashes
            normalized = tag.lower().strip().replace(" ", "-")

            # Remove invalid characters
            normalized = re.sub(r"[^a-z0-9\-_]", "", normalized)

            # Validate length
            if 0 < len(normalized) <= self.MAX_TAG_LENGTH:
                clean.append(normalized)

        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for tag in clean:
            if tag not in seen:
                seen.add(tag)
                unique.append(tag)

        return unique
