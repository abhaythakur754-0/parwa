"""
PARWA Ticket Search Service - Full-Text Search (Day 28)

Implements F-048: Ticket search with:
- Full-text search across subject, content, customer info
- Fuzzy matching (Levenshtein distance)
- Filter by status, priority, category, assignee, channel, date range, tags
- Sort by created_at, updated_at, priority, SLA time remaining
- Highlighted matching snippets
- Recent searches stored in Redis

BC-001: All queries are tenant-isolated via company_id.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from difflib import SequenceMatcher

from sqlalchemy import and_, desc, or_, func, text, case
from sqlalchemy.orm import Session

from database.models.tickets import (
    Ticket,
    TicketMessage,
    Customer,
    TicketStatus,
    TicketPriority,
)
from app.core.redis import get_redis, make_key


class TicketSearchService:
    """Full-text search service for tickets."""

    # Redis key for recent searches (per user)
    RECENT_SEARCHES_KEY = "recent_searches"
    MAX_RECENT_SEARCHES = 10
    RECENT_SEARCHES_TTL = 604800  # 7 days

    # Search configuration
    MIN_QUERY_LENGTH = 2
    MAX_QUERY_LENGTH = 200
    FUZZY_THRESHOLD = 0.7  # Minimum similarity for fuzzy match
    MAX_RESULTS = 500

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    # ── MAIN SEARCH ─────────────────────────────────────────────────────────

    def search(
        self,
        query: Optional[str] = None,
        status: Optional[List[str]] = None,
        priority: Optional[List[str]] = None,
        category: Optional[List[str]] = None,
        assigned_to: Optional[str] = None,
        channel: Optional[str] = None,
        customer_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_spam: Optional[bool] = None,
        is_frozen: Optional[bool] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "relevance",
        sort_order: str = "desc",
        include_snippets: bool = True,
        fuzzy: bool = True,
        user_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int, Optional[str]]:
        """Execute full-text search on tickets.

        Args:
            query: Search query string
            status: Filter by status list
            priority: Filter by priority list
            category: Filter by category list
            assigned_to: Filter by assignee ID
            channel: Filter by channel
            customer_id: Filter by customer ID
            tags: Filter by tags (matches any)
            is_spam: Filter by spam status
            is_frozen: Filter by frozen status
            date_from: Filter by creation date (from)
            date_to: Filter by creation date (to)
            page: Page number (1-based)
            page_size: Items per page
            sort_by: Sort field (relevance, created_at, updated_at, priority)
            sort_order: Sort direction (asc/desc)
            include_snippets: Include highlighted snippets in results
            fuzzy: Enable fuzzy matching for typos
            user_id: User ID for storing recent searches

        Returns:
            Tuple of (results list, total count, error message)
        """
        # Validate query
        if query:
            query = self._sanitize_query(query)
            if len(query) < self.MIN_QUERY_LENGTH:
                return [], 0, f"Query must be at least {self.MIN_QUERY_LENGTH} characters"
            if len(query) > self.MAX_QUERY_LENGTH:
                query = query[:self.MAX_QUERY_LENGTH]

        # Build base query
        base_query = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id
        )

        # Join with customer for customer name/email search
        if query:
            base_query = base_query.outerjoin(
                Customer, Customer.id == Ticket.customer_id
            )

        # Apply filters
        base_query = self._apply_filters(
            base_query, status, priority, category, assigned_to,
            channel, customer_id, tags, is_spam, is_frozen,
            date_from, date_to
        )

        # Apply search query
        if query:
            base_query = self._apply_search_query(
                base_query, query, fuzzy
            )

        # Get total count before pagination
        total = base_query.count()

        # Apply sorting
        base_query = self._apply_sorting(base_query, sort_by, sort_order, query)

        # Paginate
        offset = (page - 1) * page_size
        tickets = base_query.offset(offset).limit(page_size).all()

        # Build results with snippets
        results = []
        for ticket in tickets:
            result = self._ticket_to_dict(ticket)
            if include_snippets and query:
                result["snippets"] = self._get_snippets(ticket, query)
            results.append(result)

        # Store recent search
        if query and user_id:
            self._store_recent_search(user_id, query)

        return results, total, None

    # ── SUGGESTIONS ─────────────────────────────────────────────────────────

    def get_suggestions(
        self,
        partial: str,
        limit: int = 5,
    ) -> List[str]:
        """Get auto-complete suggestions for search.

        Args:
            partial: Partial search query
            limit: Maximum suggestions to return

        Returns:
            List of suggested search terms
        """
        if len(partial) < self.MIN_QUERY_LENGTH:
            return []

        suggestions = set()
        partial_lower = partial.lower()

        # Search in ticket subjects
        tickets = self.db.query(Ticket.subject).filter(
            Ticket.company_id == self.company_id,
            Ticket.subject.ilike(f"%{partial}%"),
        ).limit(limit * 2).all()

        for (subject,) in tickets:
            if subject:
                words = subject.split()
                for word in words:
                    if word.lower().startswith(partial_lower):
                        suggestions.add(word)
                    if len(suggestions) >= limit:
                        break
            if len(suggestions) >= limit:
                break

        # Search in customer names/emails
        customers = self.db.query(Customer.name, Customer.email).filter(
            Customer.company_id == self.company_id,
            or_(
                Customer.name.ilike(f"%{partial}%"),
                Customer.email.ilike(f"%{partial}%"),
            )
        ).limit(limit).all()

        for name, email in customers:
            if name and partial_lower in name.lower():
                suggestions.add(name)
            if email and partial_lower in email.lower():
                suggestions.add(email.split("@")[0])
            if len(suggestions) >= limit:
                break

        return list(suggestions)[:limit]

    # ── RECENT SEARCHES ─────────────────────────────────────────────────────

    def get_recent_searches(
        self,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """Get recent searches for a user.

        Args:
            user_id: User ID

        Returns:
            List of recent searches with timestamps
        """
        try:
            redis = get_redis()
            key = make_key(self.company_id, f"{self.RECENT_SEARCHES_KEY}:{user_id}")
            data = redis.lrange(key, 0, self.MAX_RECENT_SEARCHES - 1)

            searches = []
            for item in data:
                try:
                    searches.append(json.loads(item))
                except (json.JSONDecodeError, TypeError):
                    continue

            return searches
        except Exception:
            return []

    def clear_recent_searches(
        self,
        user_id: str,
    ) -> bool:
        """Clear recent searches for a user.

        Args:
            user_id: User ID

        Returns:
            True if cleared successfully
        """
        try:
            redis = get_redis()
            key = make_key(self.company_id, f"{self.RECENT_SEARCHES_KEY}:{user_id}")
            redis.delete(key)
            return True
        except Exception:
            return False

    # ── SEARCH INDEX ────────────────────────────────────────────────────────

    def index_ticket(
        self,
        ticket_id: str,
    ) -> bool:
        """Index a ticket for search (called on create/update).

        For now, this is a no-op as we use PostgreSQL full-text search.
        In the future, this could populate an external search index.

        Args:
            ticket_id: Ticket ID to index

        Returns:
            True if indexed successfully
        """
        # Placeholder for future external search index integration
        return True

    # ── PRIVATE HELPERS ─────────────────────────────────────────────────────

    def _sanitize_query(self, query: str) -> str:
        """Sanitize search query.

        Args:
            query: Raw query string

        Returns:
            Sanitized query string
        """
        # Remove special characters that could cause SQL injection
        query = re.sub(r"[;'\"]", "", query)
        # Collapse whitespace
        query = " ".join(query.split())
        return query.strip()

    def _apply_filters(
        self,
        base_query,
        status: Optional[List[str]],
        priority: Optional[List[str]],
        category: Optional[List[str]],
        assigned_to: Optional[str],
        channel: Optional[str],
        customer_id: Optional[str],
        tags: Optional[List[str]],
        is_spam: Optional[bool],
        is_frozen: Optional[bool],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
    ):
        """Apply filters to base query."""
        if status:
            base_query = base_query.filter(Ticket.status.in_(status))

        if priority:
            base_query = base_query.filter(Ticket.priority.in_(priority))

        if category:
            base_query = base_query.filter(Ticket.category.in_(category))

        if assigned_to:
            base_query = base_query.filter(Ticket.assigned_to == assigned_to)

        if channel:
            base_query = base_query.filter(Ticket.channel == channel)

        if customer_id:
            base_query = base_query.filter(Ticket.customer_id == customer_id)

        if is_spam is not None:
            base_query = base_query.filter(Ticket.is_spam == is_spam)

        if is_frozen is not None:
            base_query = base_query.filter(Ticket.frozen == is_frozen)

        if date_from:
            base_query = base_query.filter(Ticket.created_at >= date_from)

        if date_to:
            base_query = base_query.filter(Ticket.created_at <= date_to)

        if tags:
            for tag in tags:
                base_query = base_query.filter(Ticket.tags.contains(f'"{tag}"'))

        return base_query

    def _apply_search_query(
        self,
        base_query,
        query: str,
        fuzzy: bool,
    ):
        """Apply full-text search query."""
        search_pattern = f"%{query}%"

        # Build search conditions
        search_conditions = [
            Ticket.subject.ilike(search_pattern),
            Ticket.metadata_json.ilike(search_pattern),
        ]

        # Add customer search
        search_conditions.extend([
            Customer.name.ilike(search_pattern),
            Customer.email.ilike(search_pattern),
        ])

        # Add message content search via subquery
        message_ticket_ids = self.db.query(TicketMessage.ticket_id).filter(
            TicketMessage.company_id == self.company_id,
            TicketMessage.content.ilike(search_pattern),
        ).subquery()

        search_conditions.append(Ticket.id.in_(message_ticket_ids))

        # If fuzzy matching, add similar terms
        if fuzzy:
            fuzzy_conditions = self._build_fuzzy_conditions(query)
            search_conditions.extend(fuzzy_conditions)

        base_query = base_query.filter(or_(*search_conditions))

        return base_query

    def _build_fuzzy_conditions(self, query: str) -> List:
        """Build fuzzy matching conditions.

        Uses similarity-based matching for common typos.
        """
        conditions = []

        # Get distinct words from tickets for fuzzy matching
        # This is a simplified approach - in production, use pg_trgm extension
        words = query.split()
        for word in words:
            if len(word) >= 4:
                # Add prefix match for typos
                conditions.append(Ticket.subject.ilike(f"{word[:3]}%"))

        return conditions

    def _apply_sorting(
        self,
        base_query,
        sort_by: str,
        sort_order: str,
        query: Optional[str],
    ):
        """Apply sorting to query."""
        if sort_by == "relevance" and query:
            # For relevance, prioritize exact matches in subject
            # Use CASE statement for relevance scoring
            relevance_case = case(
                (Ticket.subject.ilike(f"%{query}%"), 100),
                (Ticket.subject.ilike(f"{query}%"), 80),
                else_=50
            )
            if sort_order == "desc":
                base_query = base_query.order_by(desc(relevance_case), desc(Ticket.created_at))
            else:
                base_query = base_query.order_by(relevance_case, Ticket.created_at)
        else:
            # Standard column sorting
            sort_column = getattr(Ticket, sort_by, Ticket.created_at)

            # Handle priority sorting (critical > high > medium > low)
            if sort_by == "priority":
                priority_order = case(
                    (Ticket.priority == TicketPriority.critical.value, 1),
                    (Ticket.priority == TicketPriority.high.value, 2),
                    (Ticket.priority == TicketPriority.medium.value, 3),
                    (Ticket.priority == TicketPriority.low.value, 4),
                    else_=5
                )
                if sort_order == "desc":
                    base_query = base_query.order_by(priority_order)
                else:
                    base_query = base_query.order_by(desc(priority_order))
            elif sort_order == "desc":
                base_query = base_query.order_by(desc(sort_column))
            else:
                base_query = base_query.order_by(sort_column)

        return base_query

    def _get_snippets(
        self,
        ticket: Ticket,
        query: str,
        max_length: int = 200,
    ) -> List[Dict[str, str]]:
        """Get highlighted snippets for search results.

        Args:
            ticket: Ticket model
            query: Search query
            max_length: Maximum snippet length

        Returns:
            List of snippet dicts with field and text
        """
        snippets = []
        query_lower = query.lower()

        # Check subject
        if ticket.subject and query_lower in ticket.subject.lower():
            snippet = self._highlight_match(ticket.subject, query)
            snippets.append({
                "field": "subject",
                "text": snippet[:max_length],
            })

        # Check messages
        messages = self.db.query(TicketMessage).filter(
            TicketMessage.ticket_id == ticket.id,
            TicketMessage.content.ilike(f"%{query}%"),
        ).limit(3).all()

        for msg in messages:
            if msg.content:
                snippet = self._highlight_match(msg.content, query)
                snippets.append({
                    "field": "message",
                    "text": snippet[:max_length],
                })

        return snippets

    def _highlight_match(
        self,
        text: str,
        query: str,
        highlight_start: str = "**",
        highlight_end: str = "**",
    ) -> str:
        """Highlight matching text.

        Args:
            text: Text to search in
            query: Query to highlight
            highlight_start: Start marker
            highlight_end: End marker

        Returns:
            Text with highlighted matches
        """
        # Find context around match
        text_lower = text.lower()
        query_lower = query.lower()

        idx = text_lower.find(query_lower)
        if idx == -1:
            return text

        # Get context (50 chars before and after)
        start = max(0, idx - 50)
        end = min(len(text), idx + len(query) + 50)

        snippet = text[start:end]

        # Add ellipsis
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        # Highlight the match
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        snippet = pattern.sub(f"{highlight_start}\\g<0>{highlight_end}", snippet)

        return snippet

    def _ticket_to_dict(self, ticket: Ticket) -> Dict[str, Any]:
        """Convert ticket to dictionary."""
        tags = []
        if ticket.tags:
            try:
                tags = json.loads(ticket.tags)
            except (json.JSONDecodeError, TypeError):
                tags = []

        return {
            "id": ticket.id,
            "company_id": ticket.company_id,
            "customer_id": ticket.customer_id,
            "channel": ticket.channel,
            "status": ticket.status,
            "subject": ticket.subject,
            "priority": ticket.priority,
            "category": ticket.category,
            "tags": tags,
            "assigned_to": ticket.assigned_to,
            "is_spam": ticket.is_spam or False,
            "frozen": ticket.frozen or False,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        }

    def _store_recent_search(
        self,
        user_id: str,
        query: str,
    ) -> None:
        """Store recent search in Redis.

        Args:
            user_id: User ID
            query: Search query
        """
        try:
            redis = get_redis()
            key = make_key(self.company_id, f"{self.RECENT_SEARCHES_KEY}:{user_id}")

            # Create search record
            search_record = json.dumps({
                "query": query,
                "timestamp": datetime.utcnow().isoformat(),
            })

            # Add to list (LPUSH adds to front)
            redis.lpush(key, search_record)

            # Trim to max size
            redis.ltrim(key, 0, self.MAX_RECENT_SEARCHES - 1)

            # Set TTL
            redis.expire(key, self.RECENT_SEARCHES_TTL)
        except Exception:
            pass  # Fail silently for recent searches

    # ── ADVANCED SEARCH ─────────────────────────────────────────────────────

    def search_by_similarity(
        self,
        text: str,
        threshold: float = 0.85,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search for tickets similar to given text.

        Used for duplicate detection and related tickets.

        Args:
            text: Text to compare against
            threshold: Minimum similarity score (0-1)
            limit: Maximum results

        Returns:
            List of similar tickets with similarity scores
        """
        results = []

        # Get recent open tickets
        recent = datetime.utcnow() - timedelta(days=30)
        tickets = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.status.in_([
                TicketStatus.open.value,
                TicketStatus.assigned.value,
                TicketStatus.in_progress.value,
            ]),
            Ticket.created_at >= recent,
        ).limit(100).all()

        for ticket in tickets:
            if ticket.subject:
                similarity = self._calculate_similarity(text, ticket.subject)
                if similarity >= threshold:
                    results.append({
                        "ticket": self._ticket_to_dict(ticket),
                        "similarity": similarity,
                    })

        # Sort by similarity
        results.sort(key=lambda x: x["similarity"], reverse=True)

        return results[:limit]

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings.

        Uses SequenceMatcher for fuzzy comparison.

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity score between 0 and 1
        """
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
