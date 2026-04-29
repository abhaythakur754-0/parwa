"""
PARWA Pagination Utilities

Provides safe pagination parameter parsing with maximum limits
to prevent DoS attacks via extremely large page sizes.
"""

from typing import NamedTuple

# Hard limits — cannot be overridden
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_OFFSET = 10000


class PaginationParams(NamedTuple):
    """Validated pagination parameters."""

    offset: int
    limit: int


def parse_pagination(
    offset: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    max_limit: int = MAX_PAGE_SIZE,
    max_offset: int = MAX_OFFSET,
) -> PaginationParams:
    """Parse and validate pagination parameters.

    Enforces maximum page size and offset to prevent DoS via
    extremely large queries (e.g., ?limit=999999999).

    Args:
        offset: Number of records to skip (default 0).
        limit: Maximum records to return (default 20).
        max_limit: Hard cap on limit (default 100).
        max_offset: Hard cap on offset (default 10000).

    Returns:
        PaginationParams with validated offset and limit.
    """
    # Validate offset
    if not isinstance(offset, int) or offset < 0:
        offset = 0
    if offset > max_offset:
        offset = max_offset

    # Validate limit
    if not isinstance(limit, int) or limit < 1:
        limit = DEFAULT_PAGE_SIZE
    if limit > max_limit:
        limit = max_limit

    return PaginationParams(offset=offset, limit=limit)


def get_next_offset(current_offset: int, limit: int, total_count: int) -> int:
    """Calculate the next page offset.

    Returns current_offset + limit only if there are more results.
    If we've reached the end, returns the current offset (no next page).

    Args:
        current_offset: Current page offset.
        limit: Current page size.
        total_count: Total number of available records.

    Returns:
        Offset for the next page, or current_offset if no more results.
    """
    next_offset = current_offset + limit
    if next_offset >= total_count:
        return current_offset
    return next_offset


def get_total_pages(total_count: int, page_size: int) -> int:
    """Calculate total number of pages.

    Args:
        total_count: Total number of records.
        page_size: Number of records per page.

    Returns:
        Total number of pages (minimum 1).
    """
    if total_count <= 0 or page_size <= 0:
        return 1
    pages = (total_count + page_size - 1) // page_size
    return max(pages, 1)
