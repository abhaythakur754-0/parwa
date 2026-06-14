"""
PARWA Pagination Schemas (API Layer)

Pydantic models for paginated request/response payloads.  These are
the **public-facing** schemas that API endpoints accept as query
parameters and return as JSON bodies.

Internal helpers live in ``backend.app.core.pagination``; this module
only re-exports and adapts them for the HTTP contract.
"""

from __future__ import annotations

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field, model_validator

from shared.utils.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MAX_OFFSET,
)

T = TypeVar("T")


# ── Request Schema ─────────────────────────────────────────────────


class PaginationRequest(BaseModel):
    """Query-parameter model for paginated list endpoints.

    Consumers pass ``offset``, ``limit``, ``sort_by``, ``sort_dir``, and
    optionally ``search`` as query-string parameters.  A
    ``model_validator`` ensures that values are clamped to the hard
    limits defined in ``shared.utils.pagination`` so that no endpoint
    can accidentally accept an oversized page.

    Example FastAPI usage::

        @router.get("/tickets")
        async def list_tickets(
            pagination: PaginationRequest = Depends(),
        ):
            params = parse_pagination(
                offset=pagination.offset,
                limit=pagination.limit,
            )
            ...
    """

    offset: int = Field(
        default=0,
        ge=0,
        description="Number of records to skip (0-based).",
    )
    limit: int = Field(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        description=f"Max records per page (max {MAX_PAGE_SIZE}).",
    )
    sort_by: Optional[str] = Field(
        default=None,
        description="Column name to sort by.",
    )
    sort_dir: str = Field(
        default="desc",
        description="Sort direction: 'asc' or 'desc'.",
    )
    search: Optional[str] = Field(
        default=None,
        description="Free-text search filter (exact usage depends on endpoint).",
    )

    @model_validator(mode="after")
    def clamp_values(self) -> "PaginationRequest":
        """Clamp offset/limit to hard security limits.

        Enforces ``MAX_OFFSET`` and ``MAX_PAGE_SIZE`` from
        ``shared.utils.pagination`` so that even if a client sends
        ``?limit=999999``, the value is silently reduced to the
        configured maximum.
        """
        if self.offset < 0:
            self.offset = 0
        if self.offset > MAX_OFFSET:
            self.offset = MAX_OFFSET

        if self.limit < 1:
            self.limit = DEFAULT_PAGE_SIZE
        if self.limit > MAX_PAGE_SIZE:
            self.limit = MAX_PAGE_SIZE

        if self.sort_dir not in ("asc", "desc"):
            self.sort_dir = "desc"

        return self


# ── Response Schema ────────────────────────────────────────────────


class PaginatedResponseSchema(BaseModel, Generic[T]):
    """Standard JSON envelope for every paginated API response.

    This is the **serialisation** counterpart to
    :class:`backend.app.core.pagination.PaginatedResponse`.  Endpoints
    should return instances of this schema so that FastAPI's
    ``response_model`` produces the correct OpenAPI documentation.

    Fields:
        items: The page of result objects (typed by *T*).
        total: Total number of records matching the query (not just
            this page).
        offset: The offset that was applied.
        limit: The limit that was applied.
        has_next: Whether a subsequent page exists.
        has_prev: Whether a preceding page exists.
        total_pages: Computed total number of pages.
    """

    items: List[T]
    total: int = Field(description="Total matching records.")
    offset: int = Field(description="Applied offset.")
    limit: int = Field(description="Applied page size.")
    has_next: bool = Field(description="True if a next page exists.")
    has_prev: bool = Field(description="True if a previous page exists.")
    total_pages: int = Field(description="Total number of pages.")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [],
                    "total": 0,
                    "offset": 0,
                    "limit": 20,
                    "has_next": False,
                    "has_prev": False,
                    "total_pages": 1,
                }
            ]
        }
    }
