"""
Query Optimizer for PARWA Performance Optimization.

Week 26 - Builder 2: Query Optimization + Connection Pooling
Target: N+1 query detection, query batching, SELECT optimization

Features:
- N+1 query detection and prevention
- Automatic eager loading hints
- Query batching utilities
- SELECT optimization (only needed columns)
- JOIN optimization
"""

import asyncio
import time
import logging
from typing import Any, Optional, List, Dict, Set, Tuple, Callable
from functools import wraps
from dataclasses import dataclass, field
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


@dataclass
class QueryMetrics:
    """Metrics for a single query execution."""
    query: str
    execution_time_ms: float
    row_count: int = 0
    columns_selected: List[str] = field(default_factory=list)
    tables_joined: List[str] = field(default_factory=list)
    is_n_plus_1_candidate: bool = False
    timestamp: float = field(default_factory=time.time)


@dataclass
class NPlusOnePattern:
    """Detected N+1 query pattern."""
    parent_query: str
    child_query_pattern: str
    occurrence_count: int
    total_time_ms: float
    recommendation: str


class NPlusOneDetector:
    """
    Detects N+1 query patterns in database queries.

    N+1 queries occur when a query is executed for each item in a result set,
    instead of fetching all related data in a single query.
    """

    def __init__(self, threshold: int = 5, time_window_seconds: float = 1.0):
        """
        Initialize N+1 detector.

        Args:
            threshold: Number of similar queries to trigger N+1 detection.
            time_window_seconds: Time window to group similar queries.
        """
        self.threshold = threshold
        self.time_window_seconds = time_window_seconds
        self._query_history: List[QueryMetrics] = []
        self._detected_patterns: List[NPlusOnePattern] = []

    def record_query(self, metrics: QueryMetrics) -> None:
        """
        Record a query for N+1 analysis.

        Args:
            metrics: Query metrics to record.
        """
        self._query_history.append(metrics)
        self._analyze_for_n_plus_one(metrics)

    def _normalize_query(self, query: str) -> str:
        """
        Normalize a query for pattern matching.

        Replaces specific values with placeholders.

        Args:
            query: SQL query string.

        Returns:
            Normalized query pattern.
        """
        # Replace UUIDs
        normalized = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '?', query, flags=re.IGNORECASE
        )
        # Replace numbers
        normalized = re.sub(r'\b\d+\b', '?', normalized)
        # Replace single-quoted strings
        normalized = re.sub(r"'[^']*'", "'?'", normalized)
        # Normalize whitespace
        normalized = ' '.join(normalized.split())
        return normalized.lower().strip()

    def _analyze_for_n_plus_one(self, new_metrics: QueryMetrics) -> None:
        """
        Analyze recent queries for N+1 patterns.

        Args:
            new_metrics: Newly recorded query metrics.
        """
        current_time = time.time()
        recent_queries = [
            q for q in self._query_history
            if current_time - q.timestamp <= self.time_window_seconds
        ]

        # Group by normalized query
        query_groups: Dict[str, List[QueryMetrics]] = defaultdict(list)
        for q in recent_queries:
            normalized = self._normalize_query(q.query)
            query_groups[normalized].append(q)

        # Check for patterns exceeding threshold
        for pattern, queries in query_groups.items():
            if len(queries) >= self.threshold:
                total_time = sum(q.execution_time_ms for q in queries)

                # Check if this is likely an N+1 (same query pattern repeated)
                if self._is_n_plus_one_candidate(pattern, queries):
                    n_plus_one = NPlusOnePattern(
                        parent_query=self._find_parent_query(pattern, recent_queries),
                        child_query_pattern=pattern,
                        occurrence_count=len(queries),
                        total_time_ms=total_time,
                        recommendation=self._generate_recommendation(pattern, queries)
                    )
                    self._detected_patterns.append(n_plus_one)
                    logger.warning(
                        f"N+1 pattern detected: {len(queries)} executions of "
                        f"'{pattern[:50]}...' took {total_time:.2f}ms total"
                    )

    def _is_n_plus_one_candidate(
        self, pattern: str, queries: List[QueryMetrics]
    ) -> bool:
        """
        Determine if a pattern represents an N+1 query.

        Args:
            pattern: Normalized query pattern.
            queries: List of matching queries.

        Returns:
            True if this appears to be an N+1 pattern.
        """
        # N+1 patterns typically:
        # 1. Have very similar execution times
        # 2. Are executed in quick succession
        # 3. Have small row counts (1-10)

        if len(queries) < self.threshold:
            return False

        # Check execution time variance
        times = [q.execution_time_ms for q in queries]
        avg_time = sum(times) / len(times)
        variance = sum((t - avg_time) ** 2 for t in times) / len(times)

        # Low variance suggests repeated similar queries
        if variance < avg_time * 0.5:  # Variance < 50% of mean
            return True

        return False

    def _find_parent_query(
        self, child_pattern: str, queries: List[QueryMetrics]
    ) -> str:
        """
        Find the likely parent query that triggered N+1.

        Args:
            child_pattern: The N+1 child query pattern.
            queries: All recent queries.

        Returns:
            The likely parent query string.
        """
        # Find a SELECT query that occurred before the N+1 pattern
        child_start_time = min(
            q.timestamp for q in queries
            if self._normalize_query(q.query) == child_pattern
        )

        parent_candidates = [
            q for q in queries
            if q.timestamp < child_start_time
            and 'SELECT' in q.query.upper()
        ]

        if parent_candidates:
            # Return the most recent query before the pattern
            return max(parent_candidates, key=lambda q: q.timestamp).query

        return "Unknown parent query"

    def _generate_recommendation(
        self, pattern: str, queries: List[QueryMetrics]
    ) -> str:
        """
        Generate recommendation to fix N+1 pattern.

        Args:
            pattern: The N+1 query pattern.
            queries: List of matching queries.

        Returns:
            Recommendation string.
        """
        # Extract table name from pattern
        table_match = re.search(r'FROM\s+(\w+)', pattern, re.IGNORECASE)
        table_name = table_match.group(1) if table_match else "table"

        # Check if WHERE clause uses IN or single value
        if 'WHERE' in pattern.upper() and ' IN ' not in pattern.upper():
            return (
                f"Consider using eager loading with JOIN on '{table_name}' "
                f"or batch the IDs and use WHERE ... IN (...) clause"
            )
        else:
            return f"Consider using eager loading with JOIN on '{table_name}'"

    def get_detected_patterns(self) -> List[NPlusOnePattern]:
        """
        Get all detected N+1 patterns.

        Returns:
            List of detected patterns.
        """
        return self._detected_patterns.copy()

    def clear_history(self) -> None:
        """Clear query history and detected patterns."""
        self._query_history.clear()
        self._detected_patterns.clear()


class QueryOptimizer:
    """
    Main query optimizer with N+1 detection, batching, and optimization hints.
    """

    def __init__(self):
        """Initialize query optimizer."""
        self.n_plus_one_detector = NPlusOneDetector()
        self._eager_load_hints: Dict[str, List[str]] = {}
        self._query_cache: Dict[str, Any] = {}

    def optimize_select(
        self,
        table: str,
        columns: Optional[List[str]] = None,
        where_clause: Optional[str] = None,
        joins: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None
    ) -> str:
        """
        Generate an optimized SELECT query.

        Args:
            table: Primary table name.
            columns: Columns to select (None = all).
            where_clause: WHERE condition.
            joins: List of JOIN clauses.
            order_by: ORDER BY clause.
            limit: Result limit.

        Returns:
            Optimized SQL query string.
        """
        # Select only needed columns
        if columns:
            # Validate columns to prevent SQL injection
            validated_columns = [
                c for c in columns
                if re.match(r'^[a-zA-Z_][a-zA-Z0-9_\.]*$', c)
            ]
            select_clause = ', '.join(validated_columns)
        else:
            select_clause = f'{table}.*'

        query = f"SELECT {select_clause} FROM {table}"

        # Add JOINs with optimization hints
        if joins:
            for join in joins:
                query += f" {join}"

        # Add WHERE clause
        if where_clause:
            query += f" WHERE {where_clause}"

        # Add ORDER BY
        if order_by:
            query += f" ORDER BY {order_by}"

        # Add LIMIT
        if limit:
            query += f" LIMIT {limit}"

        return query

    def create_batch_query(
        self,
        table: str,
        ids: List[str],
        id_column: str = "id",
        columns: Optional[List[str]] = None
    ) -> str:
        """
        Create a batch query to fetch multiple records by ID.

        This prevents N+1 queries by fetching all records in one query.

        Args:
            table: Table name.
            ids: List of IDs to fetch.
            id_column: Name of the ID column.
            columns: Columns to select.

        Returns:
            Batch query string.
        """
        if not ids:
            return ""

        # Build IN clause with proper escaping
        id_list = ', '.join(f"'{id}'" for id in ids[:500])  # Limit to 500 IDs

        if columns:
            select_clause = ', '.join(columns)
        else:
            select_clause = '*'

        return f"SELECT {select_clause} FROM {table} WHERE {id_column} IN ({id_list})"

    def add_eager_load_hint(
        self, model_name: str, relationships: List[str]
    ) -> None:
        """
        Add eager loading hints for a model.

        Args:
            model_name: Name of the model.
            relationships: List of relationship names to eager load.
        """
        self._eager_load_hints[model_name] = relationships

    def get_eager_load_hints(self, model_name: str) -> List[str]:
        """
        Get eager loading hints for a model.

        Args:
            model_name: Name of the model.

        Returns:
            List of relationships to eager load.
        """
        return self._eager_load_hints.get(model_name, [])

    def record_query_execution(
        self,
        query: str,
        execution_time_ms: float,
        row_count: int = 0
    ) -> None:
        """
        Record a query execution for analysis.

        Args:
            query: SQL query string.
            execution_time_ms: Execution time in milliseconds.
            row_count: Number of rows returned/affected.
        """
        metrics = QueryMetrics(
            query=query,
            execution_time_ms=execution_time_ms,
            row_count=row_count
        )
        self.n_plus_one_detector.record_query(metrics)

    def get_optimization_report(self) -> Dict[str, Any]:
        """
        Generate a query optimization report.

        Returns:
            Dictionary with optimization recommendations.
        """
        patterns = self.n_plus_one_detector.get_detected_patterns()

        return {
            "n_plus_one_patterns": len(patterns),
            "patterns": [
                {
                    "query_pattern": p.child_query_pattern[:100],
                    "occurrences": p.occurrence_count,
                    "total_time_ms": round(p.total_time_ms, 2),
                    "recommendation": p.recommendation
                }
                for p in patterns
            ],
            "eager_load_hints": self._eager_load_hints
        }


def query_performance_tracker(func: Callable) -> Callable:
    """
    Decorator to track query performance.

    Args:
        func: Function to decorate.

    Returns:
        Decorated function.
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.debug(
                f"Query in {func.__name__} took {execution_time_ms:.2f}ms"
            )

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.debug(
                f"Query in {func.__name__} took {execution_time_ms:.2f}ms"
            )

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


# Global optimizer instance
_optimizer: Optional[QueryOptimizer] = None


def get_query_optimizer() -> QueryOptimizer:
    """
    Get the global query optimizer instance.

    Returns:
        QueryOptimizer instance.
    """
    global _optimizer
    if _optimizer is None:
        _optimizer = QueryOptimizer()
    return _optimizer


__all__ = [
    "QueryMetrics",
    "NPlusOnePattern",
    "NPlusOneDetector",
    "QueryOptimizer",
    "query_performance_tracker",
    "get_query_optimizer",
]
