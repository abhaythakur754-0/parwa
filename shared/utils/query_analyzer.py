"""
Query Analyzer for PARWA Performance Optimization.

Week 26 - Builder 2: Query Optimization + Connection Pooling
Target: Slow query detection (>100ms), query plan analysis, index recommendations

Features:
- Slow query detection (>100ms threshold)
- Query plan analysis
- Index usage reporting
- Query recommendations
- Performance logging
"""

import re
import time
import logging
from typing import Any, Optional, List, Dict, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """SQL query types."""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    OTHER = "OTHER"


@dataclass
class QueryPlanNode:
    """Node in a query execution plan."""
    node_type: str
    actual_time_ms: float = 0.0
    rows: int = 0
    index_name: Optional[str] = None
    children: List["QueryPlanNode"] = field(default_factory=list)


@dataclass
class QueryAnalysis:
    """Analysis result for a single query."""
    query: str
    query_type: QueryType
    execution_time_ms: float
    is_slow: bool
    uses_index: bool
    indexes_used: List[str]
    table_scans: List[str]
    recommendations: List[str]
    plan_summary: Optional[str] = None
    row_count: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class SlowQueryLog:
    """Log entry for a slow query."""
    query: str
    execution_time_ms: float
    threshold_ms: float
    timestamp: float
    caller_info: Optional[str] = None
    params: Optional[str] = None


class QueryAnalyzer:
    """
    Analyzes SQL queries for performance optimization.

    Features:
    - Detects slow queries (configurable threshold)
    - Analyzes query plans for index usage
    - Generates optimization recommendations
    - Tracks query patterns over time
    """

    def __init__(
        self,
        slow_query_threshold_ms: float = 100.0,
        log_slow_queries: bool = True,
        max_logged_queries: int = 1000
    ):
        """
        Initialize query analyzer.

        Args:
            slow_query_threshold_ms: Threshold for slow query detection.
            log_slow_queries: Whether to log slow queries.
            max_logged_queries: Maximum number of queries to keep in log.
        """
        self.slow_query_threshold_ms = slow_query_threshold_ms
        self.log_slow_queries = log_slow_queries
        self.max_logged_queries = max_logged_queries

        self._slow_query_log: List[SlowQueryLog] = []
        self._query_stats: Dict[str, Dict] = defaultdict(
            lambda: {
                "count": 0,
                "total_time_ms": 0.0,
                "max_time_ms": 0.0,
                "min_time_ms": float("inf"),
                "avg_time_ms": 0.0,
            }
        )
        self._table_access_stats: Dict[str, int] = defaultdict(int)
        self._index_usage_stats: Dict[str, int] = defaultdict(int)

    def analyze_query(
        self,
        query: str,
        execution_time_ms: float,
        row_count: int = 0,
        query_plan: Optional[str] = None
    ) -> QueryAnalysis:
        """
        Analyze a query execution.

        Args:
            query: SQL query string.
            execution_time_ms: Execution time in milliseconds.
            row_count: Number of rows affected/returned.
            query_plan: EXPLAIN ANALYZE output (optional).

        Returns:
            QueryAnalysis result.
        """
        # Determine query type
        query_type = self._get_query_type(query)

        # Check if slow
        is_slow = execution_time_ms > self.slow_query_threshold_ms

        # Log slow query
        if is_slow and self.log_slow_queries:
            self._log_slow_query(query, execution_time_ms)

        # Parse query plan if available
        indexes_used = []
        table_scans = []
        uses_index = False
        plan_summary = None

        if query_plan:
            indexes_used, table_scans, uses_index, plan_summary = (
                self._parse_query_plan(query_plan)
            )

        # Update stats
        self._update_stats(query, execution_time_ms)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            query, query_type, execution_time_ms, uses_index,
            indexes_used, table_scans, row_count
        )

        return QueryAnalysis(
            query=query,
            query_type=query_type,
            execution_time_ms=execution_time_ms,
            is_slow=is_slow,
            uses_index=uses_index,
            indexes_used=indexes_used,
            table_scans=table_scans,
            recommendations=recommendations,
            plan_summary=plan_summary,
            row_count=row_count
        )

    def _get_query_type(self, query: str) -> QueryType:
        """
        Determine the type of SQL query.

        Args:
            query: SQL query string.

        Returns:
            QueryType enum value.
        """
        normalized = query.strip().upper()
        for qt in QueryType:
            if normalized.startswith(qt.value):
                return qt
        return QueryType.OTHER

    def _log_slow_query(self, query: str, execution_time_ms: float) -> None:
        """
        Log a slow query.

        Args:
            query: SQL query string.
            execution_time_ms: Execution time in milliseconds.
        """
        entry = SlowQueryLog(
            query=query,
            execution_time_ms=execution_time_ms,
            threshold_ms=self.slow_query_threshold_ms,
            timestamp=time.time()
        )

        self._slow_query_log.append(entry)

        # Trim log if needed
        if len(self._slow_query_log) > self.max_logged_queries:
            self._slow_query_log = self._slow_query_log[-self.max_logged_queries:]

        logger.warning(
            f"Slow query detected: {execution_time_ms:.2f}ms > "
            f"{self.slow_query_threshold_ms}ms threshold"
        )

    def _parse_query_plan(
        self, plan: str
    ) -> Tuple[List[str], List[str], bool, str]:
        """
        Parse a query execution plan.

        Args:
            plan: EXPLAIN ANALYZE output.

        Returns:
            Tuple of (indexes_used, table_scans, uses_index, plan_summary).
        """
        indexes_used = []
        table_scans = []
        uses_index = False

        # Extract index scans
        index_matches = re.findall(
            r'Index Scan[^"]*on[^"]*using\s+(\w+)',
            plan, re.IGNORECASE
        )
        indexes_used.extend(index_matches)

        # Extract index-only scans
        index_only_matches = re.findall(
            r'Index Only Scan[^"]*using\s+(\w+)',
            plan, re.IGNORECASE
        )
        indexes_used.extend(index_only_matches)

        # Check for sequential scans
        seq_scan_matches = re.findall(
            r'Seq Scan on\s+(\w+)',
            plan, re.IGNORECASE
        )
        table_scans.extend(seq_scan_matches)

        # Determine if index was used
        uses_index = len(indexes_used) > 0

        # Update index usage stats
        for idx in indexes_used:
            self._index_usage_stats[idx] += 1

        # Update table access stats
        for table in table_scans:
            self._table_access_stats[table] += 1

        # Create plan summary
        plan_summary = plan[:500] if len(plan) > 500 else plan

        return indexes_used, table_scans, uses_index, plan_summary

    def _update_stats(self, query: str, execution_time_ms: float) -> None:
        """
        Update query statistics.

        Args:
            query: SQL query string.
            execution_time_ms: Execution time in milliseconds.
        """
        # Normalize query for grouping
        normalized = self._normalize_query(query)

        stats = self._query_stats[normalized]
        stats["count"] += 1
        stats["total_time_ms"] += execution_time_ms
        stats["max_time_ms"] = max(stats["max_time_ms"], execution_time_ms)
        stats["min_time_ms"] = min(stats["min_time_ms"], execution_time_ms)
        stats["avg_time_ms"] = (
            stats["total_time_ms"] / stats["count"]
        )

    def _normalize_query(self, query: str) -> str:
        """
        Normalize a query for pattern matching.

        Args:
            query: SQL query string.

        Returns:
            Normalized query string.
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

    def _generate_recommendations(
        self,
        query: str,
        query_type: QueryType,
        execution_time_ms: float,
        uses_index: bool,
        indexes_used: List[str],
        table_scans: List[str],
        row_count: int
    ) -> List[str]:
        """
        Generate optimization recommendations.

        Args:
            query: SQL query string.
            query_type: Type of query.
            execution_time_ms: Execution time.
            uses_index: Whether index was used.
            indexes_used: List of indexes used.
            table_scans: List of tables scanned.
            row_count: Number of rows.

        Returns:
            List of recommendations.
        """
        recommendations = []

        # Check for missing index
        if table_scans and not uses_index:
            for table in table_scans:
                recommendations.append(
                    f"Consider adding an index on '{table}' table. "
                    f"Query is performing sequential scan."
                )

        # Check for slow query
        if execution_time_ms > self.slow_query_threshold_ms:
            recommendations.append(
                f"Query exceeds {self.slow_query_threshold_ms}ms threshold. "
                f"Consider optimizing or caching results."
            )

        # Check for SELECT *
        if query_type == QueryType.SELECT and "SELECT *" in query.upper():
            recommendations.append(
                "Avoid SELECT *. Specify only needed columns to reduce "
                "data transfer and improve performance."
            )

        # Check for large result sets
        if row_count > 10000:
            recommendations.append(
                f"Large result set ({row_count} rows). "
                f"Consider adding LIMIT or pagination."
            )

        # Check for missing WHERE clause on SELECT
        if query_type == QueryType.SELECT:
            if "WHERE" not in query.upper():
                recommendations.append(
                    "Query has no WHERE clause. This may return excessive data. "
                    "Consider adding filtering conditions."
                )

        return recommendations

    def get_slow_queries(self, limit: int = 100) -> List[SlowQueryLog]:
        """
        Get recent slow queries.

        Args:
            limit: Maximum number of queries to return.

        Returns:
            List of slow query log entries.
        """
        return sorted(
            self._slow_query_log,
            key=lambda x: x.execution_time_ms,
            reverse=True
        )[:limit]

    def get_query_stats(self) -> Dict[str, Dict]:
        """
        Get query statistics.

        Returns:
            Dictionary of query stats.
        """
        return dict(self._query_stats)

    def get_table_access_stats(self) -> Dict[str, int]:
        """
        Get table access statistics.

        Returns:
            Dictionary of table access counts.
        """
        return dict(self._table_access_stats)

    def get_index_usage_stats(self) -> Dict[str, int]:
        """
        Get index usage statistics.

        Returns:
            Dictionary of index usage counts.
        """
        return dict(self._index_usage_stats)

    def get_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive query analysis report.

        Returns:
            Dictionary with analysis report.
        """
        return {
            "slow_queries": {
                "count": len(self._slow_query_log),
                "threshold_ms": self.slow_query_threshold_ms,
                "top_slow": [
                    {
                        "query": sq.query[:200],
                        "execution_time_ms": round(sq.execution_time_ms, 2),
                    }
                    for sq in self.get_slow_queries(10)
                ],
            },
            "query_patterns": {
                "total_patterns": len(self._query_stats),
                "top_by_avg_time": sorted(
                    [
                        {"pattern": k[:100], **v}
                        for k, v in self._query_stats.items()
                    ],
                    key=lambda x: x["avg_time_ms"],
                    reverse=True,
                )[:10],
            },
            "table_access": dict(
                sorted(
                    self._table_access_stats.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:20]
            ),
            "index_usage": dict(
                sorted(
                    self._index_usage_stats.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:20]
            ),
        }

    def clear_stats(self) -> None:
        """Clear all statistics and logs."""
        self._slow_query_log.clear()
        self._query_stats.clear()
        self._table_access_stats.clear()
        self._index_usage_stats.clear()


# Global analyzer instance
_analyzer: Optional[QueryAnalyzer] = None


def get_query_analyzer() -> QueryAnalyzer:
    """
    Get the global query analyzer instance.

    Returns:
        QueryAnalyzer instance.
    """
    global _analyzer
    if _analyzer is None:
        _analyzer = QueryAnalyzer()
    return _analyzer


__all__ = [
    "QueryType",
    "QueryPlanNode",
    "QueryAnalysis",
    "SlowQueryLog",
    "QueryAnalyzer",
    "get_query_analyzer",
]
