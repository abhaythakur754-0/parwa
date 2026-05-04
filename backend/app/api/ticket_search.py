"""
PARWA Ticket Search API - F-048 Search Endpoints (Day 28)

Implements F-048: Ticket search API with:
- Full-text search with filters
- Auto-complete suggestions
- Recent searches

BC-001: All endpoints are tenant-isolated.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.services.ticket_search_service import TicketSearchService


router = APIRouter(prefix="/tickets", tags=["ticket-search"])


# ── SCHEMAS ────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    """Search request body."""
    query: Optional[str] = Field(None, min_length=2, max_length=200)
    status: Optional[List[str]] = None
    priority: Optional[List[str]] = None
    category: Optional[List[str]] = None
    assigned_to: Optional[str] = None
    channel: Optional[str] = None
    customer_id: Optional[str] = None
    tags: Optional[List[str]] = None
    is_spam: Optional[bool] = None
    is_frozen: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    sort_by: str = "relevance"
    sort_order: str = "desc"
    include_snippets: bool = True
    fuzzy: bool = True


class SearchResult(BaseModel):
    """Single search result."""
    id: str
    company_id: str
    customer_id: Optional[str]
    channel: str
    status: str
    subject: Optional[str]
    priority: str
    category: Optional[str]
    tags: List[str]
    assigned_to: Optional[str]
    is_spam: bool
    frozen: bool
    created_at: Optional[str]
    updated_at: Optional[str]
    snippets: Optional[List[Dict[str, str]]] = None


class SearchResponse(BaseModel):
    """Search response."""
    items: List[SearchResult]
    total: int
    page: int
    page_size: int
    query: Optional[str] = None
    error: Optional[str] = None


class SuggestionResponse(BaseModel):
    """Auto-complete suggestions response."""
    suggestions: List[str]
    partial: str


class RecentSearchItem(BaseModel):
    """Recent search item."""
    query: str
    timestamp: str


class RecentSearchesResponse(BaseModel):
    """Recent searches response."""
    searches: List[RecentSearchItem]


# ── ENDPOINTS ──────────────────────────────────────────────────────────────

@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Full-text search tickets",
)
async def search_tickets(
    request: Request,
    query: Optional[str] = Query(None, min_length=2, max_length=200),
    status: Optional[List[str]] = Query(None),
    priority: Optional[List[str]] = Query(None),
    category: Optional[List[str]] = Query(None),
    assigned_to: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    is_spam: Optional[bool] = Query(None),
    is_frozen: Optional[bool] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("relevance"),
    sort_order: str = Query("desc"),
    include_snippets: bool = Query(True),
    fuzzy: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Full-text search across tickets.

    F-048: Search with filters and fuzzy matching.

    Search across:
    - Ticket subject
    - Message content
    - Customer name
    - Customer email

    Supports:
    - Fuzzy matching for typos
    - Filter by status, priority, category, assignee, channel, tags
    - Sort by relevance, created_at, updated_at, priority
    - Highlighted snippets showing match context
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = TicketSearchService(db, company_id)

    results, total, error = service.search(
        query=query,
        status=status,
        priority=priority,
        category=category,
        assigned_to=assigned_to,
        channel=channel,
        customer_id=customer_id,
        tags=tags,
        is_spam=is_spam,
        is_frozen=is_frozen,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        include_snippets=include_snippets,
        fuzzy=fuzzy,
        user_id=user_id,
    )

    return SearchResponse(
        items=[SearchResult(**r) for r in results],
        total=total,
        page=page,
        page_size=page_size,
        query=query,
        error=error,
    )


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Full-text search tickets (POST)",
)
async def search_tickets_post(
    data: SearchRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Full-text search across tickets (POST version).

    F-048: Search with filters and fuzzy matching.
    Use POST for complex queries with many filters.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = TicketSearchService(db, company_id)

    results, total, error = service.search(
        query=data.query,
        status=data.status,
        priority=data.priority,
        category=data.category,
        assigned_to=data.assigned_to,
        channel=data.channel,
        customer_id=data.customer_id,
        tags=data.tags,
        is_spam=data.is_spam,
        is_frozen=data.is_frozen,
        date_from=data.date_from,
        date_to=data.date_to,
        page=data.page,
        page_size=data.page_size,
        sort_by=data.sort_by,
        sort_order=data.sort_order,
        include_snippets=data.include_snippets,
        fuzzy=data.fuzzy,
        user_id=user_id,
    )

    return SearchResponse(
        items=[SearchResult(**r) for r in results],
        total=total,
        page=data.page,
        page_size=data.page_size,
        query=data.query,
        error=error,
    )


@router.get(
    "/search/suggestions",
    response_model=SuggestionResponse,
    summary="Get search suggestions",
)
async def get_search_suggestions(
    partial: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Get auto-complete suggestions for search.

    F-048: Auto-complete suggestions from ticket subjects
    and customer names/emails.
    """
    company_id = current_user.get("company_id")

    service = TicketSearchService(db, company_id)

    suggestions = service.get_suggestions(partial, limit)

    return SuggestionResponse(
        suggestions=suggestions,
        partial=partial,
    )


@router.get(
    "/search/recent",
    response_model=RecentSearchesResponse,
    summary="Get recent searches",
)
async def get_recent_searches(
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Get recent searches for current user.

    F-048: Recent searches stored in Redis per user.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = TicketSearchService(db, company_id)

    searches = service.get_recent_searches(user_id)

    return RecentSearchesResponse(
        searches=[RecentSearchItem(**s) for s in searches],
    )


@router.delete(
    "/search/recent",
    summary="Clear recent searches",
)
async def clear_recent_searches(
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Dict[str, bool]:
    """Clear recent searches for current user.

    F-048: Clear recent searches from Redis.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = TicketSearchService(db, company_id)

    cleared = service.clear_recent_searches(user_id)

    return {"cleared": cleared}


@router.get(
    "/search/similar",
    summary="Find similar tickets",
)
async def find_similar_tickets(
    text: str = Query(..., min_length=10, max_length=1000),
    threshold: float = Query(0.85, ge=0.5, le=1.0),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Find tickets similar to given text.

    F-048: Similarity search for duplicate detection
    and related tickets.
    """
    company_id = current_user.get("company_id")

    service = TicketSearchService(db, company_id)

    similar = service.search_by_similarity(text, threshold, limit)

    return {
        "similar_tickets": similar,
        "query_text": text[:100] + "..." if len(text) > 100 else text,
        "threshold": threshold,
    }
