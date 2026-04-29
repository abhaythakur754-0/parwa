"""
PARWA Core Pagination Utilities

Provides reusable pagination, sorting, and filtering helpers for
SQLAlchemy queries.  Designed to work with both PostgreSQL (production)
and SQLite (CI tests).

Key components:
    - PaginatedResponse[T]: Generic Pydantic model for paginated API responses.
    - paginate_query(): Efficient single-query pagination (window function on
      PostgreSQL, separate count fallback on SQLite).
    - build_paginated_response(): Convenience wrapper combining pagination +
      optional schema transformation.
    - SortParams / parse_sort(): Safe sort-parameter parsing with field
      whitelisting.
    - FilterParams / apply_filters(): Declarative filter building with
      operator mapping to SQLAlchemy expressions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Generic,
    List,
    Optional,
    Sequence,
    TypeVar,
)

from pydantic import BaseModel
from sqlalchemy import func, select, Select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Query
from sqlalchemy.sql.expression import ColumnElement

from shared.utils.pagination import (
    PaginationParams,
    get_total_pages,
)

logger = logging.getLogger(__name__)


# ── Generic type variable ──────────────────────────────────────────

T = TypeVar("T")
ModelT = TypeVar("ModelT")


# ── PaginatedResponse ──────────────────────────────────────────────


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard envelope for every paginated API response.

    Generic over *T* — the schema type of each item in ``items``.
    All fields are read-only from the consumer's perspective.

    Example::

        >>> resp = PaginatedResponse[UserSchema](
        ...     items=[user1, user2],
        ...     total=42,
        ...     offset=0,
        ...     limit=20,
        ... )
        >>> resp.total_pages
        3
    """

    items: List[T]
    total: int
    offset: int
    limit: int
    has_next: bool
    has_prev: bool
    total_pages: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [{"id": "abc-123", "name": "Example"}],
                    "total": 42,
                    "offset": 0,
                    "limit": 20,
                    "has_next": True,
                    "has_prev": False,
                    "total_pages": 3,
                }
            ]
        }
    }


# ── Database dialect detection ────────────────────────────────────


def _is_sqlite(bind: Engine) -> bool:
    """Return ``True`` if *bind* is a SQLite connection."""
    return bind.dialect.name == "sqlite"


# ── paginate_query ─────────────────────────────────────────────────


def paginate_query(
    query: Query,
    params: PaginationParams,
    session: Any,
) -> tuple[list[Any], int]:
    """Apply offset/limit to a SQLAlchemy *Query* and return items + total.

    **PostgreSQL fast path** — uses ``SELECT COUNT(*) OVER()`` window
    function so the data rows and total count are fetched in a single
    round-trip.

    **SQLite fallback** — runs a separate ``SELECT count(*)`` query
    because SQLite has limited window-function support in older versions
    and the test suite uses an in-memory DB.

    Args:
        query: A SQLAlchemy ORM ``Query`` object (already filtered/sorted).
        params: Validated :class:`PaginationParams` from
            :func:`shared.utils.pagination.parse_pagination`.
        session: The SQLAlchemy :class:`Session` used to execute queries.

    Returns:
        A ``(items, total)`` tuple where *items* is a ``list`` of ORM
        model instances and *total* is the ``int`` row count.
    """

    bind = session.get_bind()
    base_query = query

    if not _is_sqlite(bind):
        # ── PostgreSQL: single-query with COUNT(*) OVER() ─────────
        base_select = (
            query.statement.with_only_columns(
                query.column_descriptions[0]["expr"]  # type: ignore[arg-type]
            )
            if hasattr(query, "column_descriptions")
            else query.statement
        )

        # Build: SELECT <original columns>, COUNT(*) OVER() AS _total
        # We use add_columns to inject the window function.
        paginated_q = query.session.execute(
            select(
                *base_select.columns,  # type: ignore[arg-type]
                func.count().over().label("_total"),
            )
            .offset(params.offset)
            .limit(params.limit)
        )

        rows = paginated_q.fetchall()
        total = int(rows[0][-1]) if rows else 0
        items = [row[0] for row in rows] if rows else []
    else:
        # ── SQLite: separate count query ─────────────────────────
        count_q = query.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_q.scalar() or 0

        result = query.offset(params.offset).limit(params.limit).all()
        items = list(result)

    return items, total


def paginate_query_v2(
    stmt: Select,
    params: PaginationParams,
    session: Any,
) -> tuple[list[Any], int]:
    """Apply offset/limit to a SQLAlchemy 2.0 *Select* statement.

    Works identically to :func:`paginate_query` but accepts a
    :class:`sqlalchemy.select` construct instead of a legacy ``Query``.
    This is the recommended entry-point for new code.

    Args:
        stmt: A SQLAlchemy 2.0 ``select()`` statement.
        params: Validated :class:`PaginationParams`.
        session: The SQLAlchemy :class:`Session`.

    Returns:
        ``(items, total)`` tuple.
    """

    bind = session.get_bind()

    if not _is_sqlite(bind):
        # PostgreSQL: inject COUNT(*) OVER() as the last column
        count_window = func.count().over().label("_total")
        enriched = stmt.add_columns(count_window)
        paginated = enriched.offset(params.offset).limit(params.limit)

        rows = session.execute(paginated).fetchall()
        total = int(rows[0][-1]) if rows else 0
        # Strip the trailing _total column from each row
        items = [row[:-1] for row in rows] if rows else []
    else:
        # SQLite: separate count for compatibility
        pass

        count_subq = select(func.count()).select_from(stmt.subquery())
        total = session.execute(count_subq).scalar() or 0

        paginated = stmt.offset(params.offset).limit(params.limit)
        items = list(session.execute(paginated).scalars().all())

    return items, total


# ── build_paginated_response ──────────────────────────────────────


def build_paginated_response(
    query: Query | Select,
    params: PaginationParams,
    session: Any,
    *,
    schema: Optional[type[BaseModel]] = None,
    transform: Optional[Callable[[Any], T]] = None,
) -> PaginatedResponse[T]:
    """Build a :class:`PaginatedResponse[T]` from a SQLAlchemy query.

    This is the **primary convenience function** that most API endpoints
    should use.  It combines:

    1. :func:`paginate_query` / :func:`paginate_query_v2` to fetch the
       page of results.
    2. Optional schema transformation (ORM → Pydantic).
    3. Pagination metadata calculation (has_next, has_prev, total_pages).

    Either *schema* or *transform* may be provided:

    * **schema** — a Pydantic model class; each ORM instance is
      passed through ``schema.model_validate(item)``.
    * **transform** — an arbitrary callable that maps an ORM instance
      to the desired output type.

    If neither is provided, raw ORM instances are returned (useful
    for internal service-to-service calls).

    Args:
        query: SQLAlchemy ``Query`` or 2.0 ``Select`` statement.
        params: Validated :class:`PaginationParams`.
        session: The SQLAlchemy :class:`Session`.
        schema: Optional Pydantic model for item transformation.
        transform: Optional callable for custom item transformation.

    Returns:
        A fully populated :class:`PaginatedResponse[T]`.

    Raises:
        ValueError: If both *schema* and *transform* are provided.
    """

    if schema is not None and transform is not None:
        raise ValueError("Provide either 'schema' or 'transform', not both.")

    # Pick the right executor based on query type
    if isinstance(query, Select):
        items, total = paginate_query_v2(query, params, session)
    else:
        items, total = paginate_query(query, params, session)

    # Transform items if a schema or transform was given
    if schema is not None:
        mapped_items: list[Any] = [schema.model_validate(item) for item in items]
    elif transform is not None:
        mapped_items = [transform(item) for item in items]
    else:
        mapped_items = items  # type: ignore[assignment]

    total_pages = get_total_pages(total, params.limit)
    has_next = (params.offset + params.limit) < total
    has_prev = params.offset > 0

    return PaginatedResponse[T](
        items=mapped_items,  # type: ignore[arg-type]
        total=total,
        offset=params.offset,
        limit=params.limit,
        has_next=has_next,
        has_prev=has_prev,
        total_pages=total_pages,
    )


# ── Sort utilities ────────────────────────────────────────────────

DEFAULT_SORT_DIRECTION = "desc"

# Columns that must NEVER appear in ORDER BY clauses, even without
# an explicit whitelist.  Sorting by these could leak sensitive data
# or cause performance issues (full table scans on unindexed columns).
_SENSITIVE_SORT_COLUMNS: frozenset[str] = frozenset(
    {
        "password_hash",
        "password",
        "secret_key",
        "secret",
        "token_hash",
        "token",
        "credentials_encrypted",
        "auth_config",
        "connection_string",
        "mfa_secret",
        "refresh_token",
        "access_token",
        "api_key",
        "key_hash",
        "card_number",
        "ssn",
        "social_security",
    }
)


class SortParams(__import__("typing").NamedTuple):  # type: ignore[misc, valid-type]
    """Validated sort parameters.

    Attributes:
        field: The column/attribute name to sort by.
        direction: Either ``"asc"`` or ``"desc"``.
    """

    field: str
    direction: str


def parse_sort(
    sort_by: Optional[str] = None,
    sort_dir: Optional[str] = None,
    *,
    default_field: str = "created_at",
    default_direction: str = DEFAULT_SORT_DIRECTION,
    allowed_fields: Optional[Sequence[str]] = None,
) -> SortParams:
    """Parse and validate sort query parameters.

    **Security**: When *allowed_fields* is provided, any sort field not
    in the whitelist is silently replaced with *default_field*.  This
    prevents clients from triggering queries on arbitrary or sensitive
    columns.

    Args:
        sort_by: Raw ``sort_by`` query parameter (may be ``None``).
        sort_dir: Raw ``sort_dir`` query parameter (may be ``None``).
        default_field: Fallback field when *sort_by* is empty/invalid.
        default_direction: Fallback direction (default ``"desc"``).
        allowed_fields: Optional whitelist of sortable column names.

    Returns:
        A validated :class:`SortParams` named tuple.
    """

    # Normalise direction
    direction = sort_dir.strip().lower() if sort_dir else default_direction
    if direction not in ("asc", "desc"):
        direction = default_direction

    # Normalise field
    field_name = sort_by.strip() if sort_by else default_field

    # L45 FIX: Block sensitive columns even without explicit whitelist.
    # This prevents sorting by password_hash, secret_key, etc. when a
    # developer forgets to pass allowed_fields.
    if field_name.lower() in _SENSITIVE_SORT_COLUMNS:
        logger.warning(
            "Rejected sort field %r — matches sensitive column blocklist",
            field_name,
        )
        field_name = default_field

    # Whitelist enforcement
    if allowed_fields is not None and field_name not in allowed_fields:
        logger.warning(
            "Rejected sort field %r — not in allowed fields %s",
            field_name,
            allowed_fields,
        )
        field_name = default_field

    return SortParams(field=field_name, direction=direction)


# ── Filter utilities ──────────────────────────────────────────────

# Supported filter operators mapped to SQLAlchemy expressions.
_OPERATOR_MAP: dict[str, Callable] = {
    "eq": lambda col, val: col == val,
    "neq": lambda col, val: col != val,
    "gt": lambda col, val: col > val,
    "gte": lambda col, val: col >= val,
    "lt": lambda col, val: col < val,
    "lte": lambda col, val: col <= val,
    "like": lambda col, val: col.like(val),
    "ilike": lambda col, val: col.ilike(val),
    "in": lambda col, val: (
        col.in_(val) if isinstance(val, (list, tuple)) else col == val
    ),
    "not_in": lambda col, val: (
        col.notin_(val) if isinstance(val, (list, tuple)) else col != val
    ),
}


@dataclass
class FilterParams:
    """Declarative filter specification for a single column.

    Attributes:
        field: The model attribute / column name.
        operator: One of ``eq``, ``neq``, ``gt``, ``gte``, ``lt``,
            ``lte``, ``like``, ``ilike``, ``in``, ``not_in``.
        value: The comparison value.  For ``in`` / ``not_in``, pass
            a list or tuple.
    """

    field: str
    operator: str
    value: Any


def apply_filters(
    query: Query | Select,
    model_class: type,
    filters: Sequence[FilterParams],
) -> Query | Select:
    """Apply a list of :class:`FilterParams` to a SQLAlchemy query.

    Each filter is translated into the corresponding SQLAlchemy
    expression and AND-combined with the existing query's WHERE clause.

    Filters with a ``value`` of ``None`` or an empty string (for string
    operators) are **skipped** so that omitted query parameters do not
    accidentally filter out all rows.

    Args:
        query: SQLAlchemy ``Query`` or 2.0 ``Select`` to filter.
        model_class: The SQLAlchemy ORM model class (used to resolve
            attribute names to columns).
        filters: Sequence of :class:`FilterParams` to apply.

    Returns:
        The query with all applicable filter expressions added.

    Raises:
        ValueError: If an unsupported operator is provided.
    """

    for f in filters:
        # Skip empty / None values
        if f.value is None:
            continue
        if isinstance(f.value, str) and f.value.strip() == "":
            continue

        # Resolve the column from the model class
        if not hasattr(model_class, f.field):
            logger.warning(
                "Filter field %r not found on model %s — skipping",
                f.field,
                model_class.__name__,
            )
            continue

        column = getattr(model_class, f.field)

        # Look up the operator
        op_func = _OPERATOR_MAP.get(f.operator)
        if op_func is None:
            raise ValueError(
                f"Unsupported filter operator '{f.operator}'. "
                f"Supported: {sorted(_OPERATOR_MAP.keys())}"
            )

        expression: ColumnElement = op_func(column, f.value)
        query = (
            query.filter(expression)
            if isinstance(query, Query)
            else query.where(expression)
        )  # type: ignore[union-attr]

    return query
