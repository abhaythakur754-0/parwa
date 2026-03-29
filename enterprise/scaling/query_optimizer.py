"""
Query Optimizer Module - Week 52, Builder 2
Database query optimization and analysis
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Set
import logging
import re

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Type of SQL query"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    JOIN = "JOIN"
    SUBQUERY = "SUBQUERY"


class OptimizationLevel(Enum):
    """Optimization suggestion level"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class QueryPlan:
    """Query execution plan"""
    query: str
    estimated_cost: float
    estimated_rows: int
    execution_time_ms: Optional[float] = None
    actual_rows: Optional[int] = None
    scan_type: str = "unknown"
    index_used: Optional[str] = None
    tables_scanned: List[str] = field(default_factory=list)
    joins: List[str] = field(default_factory=list)


@dataclass
class QueryAnalysis:
    """Analysis result for a query"""
    query: str
    query_type: QueryType
    tables: List[str] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    where_clauses: List[str] = field(default_factory=list)
    join_clauses: List[str] = field(default_factory=list)
    order_by: List[str] = field(default_factory=list)
    group_by: List[str] = field(default_factory=list)
    has_subquery: bool = False
    has_wildcard: bool = False
    has_distinct: bool = False
    has_limit: bool = False


@dataclass
class OptimizationSuggestion:
    """Optimization suggestion"""
    query: str
    suggestion: str
    level: OptimizationLevel
    reason: str
    estimated_improvement: float = 0.0
    apply_sql: Optional[str] = None


class QueryParser:
    """
    SQL Query parser for analysis.
    """

    # Regex patterns for SQL parsing
    PATTERNS = {
        "select": r"SELECT\s+(.+?)\s+FROM",
        "from": r"FROM\s+(\w+)",
        "where": r"WHERE\s+(.+?)(?:\s+GROUP|\s+ORDER|\s+LIMIT|$)",
        "join": r"(?:LEFT\s+|RIGHT\s+|INNER\s+)?JOIN\s+(\w+)",
        "order_by": r"ORDER\s+BY\s+(.+?)(?:\s+LIMIT|$)",
        "group_by": r"GROUP\s+BY\s+(.+?)(?:\s+ORDER|\s+HAVING|\s+LIMIT|$)",
        "limit": r"LIMIT\s+(\d+)",
        "subquery": r"\([^)]*SELECT[^)]*\)",
    }

    def parse(self, query: str) -> QueryAnalysis:
        """Parse a SQL query and return analysis"""
        query_upper = query.upper().strip()

        # Determine query type
        query_type = self._determine_query_type(query_upper)

        # Extract components
        tables = self._extract_tables(query, query_upper)
        columns = self._extract_columns(query, query_upper)
        where_clauses = self._extract_where(query, query_upper)
        join_clauses = self._extract_joins(query, query_upper)
        order_by = self._extract_order_by(query, query_upper)
        group_by = self._extract_group_by(query, query_upper)

        # Check for patterns
        has_subquery = bool(re.search(self.PATTERNS["subquery"], query, re.IGNORECASE))
        has_wildcard = "SELECT *" in query_upper or "SELECT\t*" in query_upper
        has_distinct = "SELECT DISTINCT" in query_upper
        has_limit = bool(re.search(self.PATTERNS["limit"], query, re.IGNORECASE))

        return QueryAnalysis(
            query=query,
            query_type=query_type,
            tables=tables,
            columns=columns,
            where_clauses=where_clauses,
            join_clauses=join_clauses,
            order_by=order_by,
            group_by=group_by,
            has_subquery=has_subquery,
            has_wildcard=has_wildcard,
            has_distinct=has_distinct,
            has_limit=has_limit,
        )

    def _determine_query_type(self, query_upper: str) -> QueryType:
        """Determine the type of query"""
        if query_upper.startswith("SELECT"):
            if " JOIN " in query_upper:
                return QueryType.JOIN
            if re.search(self.PATTERNS["subquery"], query_upper, re.IGNORECASE):
                return QueryType.SUBQUERY
            return QueryType.SELECT
        elif query_upper.startswith("INSERT"):
            return QueryType.INSERT
        elif query_upper.startswith("UPDATE"):
            return QueryType.UPDATE
        elif query_upper.startswith("DELETE"):
            return QueryType.DELETE
        return QueryType.SELECT

    def _extract_tables(self, query: str, query_upper: str) -> List[str]:
        """Extract table names from query"""
        tables = []

        # FROM clause
        from_match = re.search(self.PATTERNS["from"], query, re.IGNORECASE)
        if from_match:
            tables.append(from_match.group(1).strip("`\"[]"))

        # JOIN clauses
        join_matches = re.findall(self.PATTERNS["join"], query, re.IGNORECASE)
        for match in join_matches:
            tables.append(match.strip("`\"[]"))

        # UPDATE table
        if query_upper.startswith("UPDATE"):
            update_match = re.search(r"UPDATE\s+([^\s]+)", query, re.IGNORECASE)
            if update_match:
                tables.append(update_match.group(1).strip("`\"[]"))

        # INSERT INTO table
        if query_upper.startswith("INSERT"):
            insert_match = re.search(r"INSERT\s+INTO\s+([^\s]+)", query, re.IGNORECASE)
            if insert_match:
                tables.append(insert_match.group(1).strip("`\"[]"))

        # DELETE FROM table
        if query_upper.startswith("DELETE"):
            delete_match = re.search(r"DELETE\s+FROM\s+([^\s]+)", query, re.IGNORECASE)
            if delete_match:
                tables.append(delete_match.group(1).strip("`\"[]"))

        return list(set(tables))

    def _extract_columns(self, query: str, query_upper: str) -> List[str]:
        """Extract column names from SELECT query"""
        columns = []

        select_match = re.search(self.PATTERNS["select"], query, re.IGNORECASE)
        if select_match:
            cols_str = select_match.group(1)
            if "*" not in cols_str:
                # Split by comma and clean up
                for col in cols_str.split(","):
                    col = col.strip()
                    # Remove alias (AS keyword)
                    if " AS " in col.upper():
                        col = col.split()[0]
                    columns.append(col.strip("`\"[]"))

        return columns

    def _extract_where(self, query: str, query_upper: str) -> List[str]:
        """Extract WHERE clause conditions"""
        where_match = re.search(self.PATTERNS["where"], query, re.IGNORECASE)
        if where_match:
            return [where_match.group(1).strip()]
        return []

    def _extract_joins(self, query: str, query_upper: str) -> List[str]:
        """Extract JOIN clauses"""
        return re.findall(self.PATTERNS["join"], query, re.IGNORECASE)

    def _extract_order_by(self, query: str, query_upper: str) -> List[str]:
        """Extract ORDER BY columns"""
        order_match = re.search(self.PATTERNS["order_by"], query, re.IGNORECASE)
        if order_match:
            return [col.strip() for col in order_match.group(1).split(",")]
        return []

    def _extract_group_by(self, query: str, query_upper: str) -> List[str]:
        """Extract GROUP BY columns"""
        group_match = re.search(self.PATTERNS["group_by"], query, re.IGNORECASE)
        if group_match:
            return [col.strip() for col in group_match.group(1).split(",")]
        return []


class QueryOptimizer:
    """
    Query optimizer that analyzes and suggests improvements.
    """

    def __init__(self):
        self.parser = QueryParser()
        self.slow_query_threshold_ms: float = 1000.0
        self.query_history: Dict[str, List[QueryPlan]] = {}
        self.index_suggestions: Dict[str, Set[str]] = {}

    def analyze(self, query: str) -> QueryAnalysis:
        """Analyze a query"""
        return self.parser.parse(query)

    def suggest_optimizations(
        self,
        query: str,
        plan: Optional[QueryPlan] = None,
    ) -> List[OptimizationSuggestion]:
        """Generate optimization suggestions for a query"""
        analysis = self.analyze(query)
        suggestions = []

        # Check for SELECT *
        if analysis.has_wildcard:
            suggestions.append(OptimizationSuggestion(
                query=query,
                suggestion="Avoid SELECT * - specify only needed columns",
                level=OptimizationLevel.MEDIUM,
                reason="SELECT * retrieves all columns, increasing I/O and memory",
                estimated_improvement=20.0,
            ))

        # Check for missing LIMIT
        if analysis.query_type == QueryType.SELECT and not analysis.has_limit:
            suggestions.append(OptimizationSuggestion(
                query=query,
                suggestion="Add LIMIT clause to restrict result set",
                level=OptimizationLevel.LOW,
                reason="Without LIMIT, query may return millions of rows",
                estimated_improvement=30.0,
            ))

        # Check for subqueries
        if analysis.has_subquery:
            suggestions.append(OptimizationSuggestion(
                query=query,
                suggestion="Consider using JOIN instead of subquery",
                level=OptimizationLevel.MEDIUM,
                reason="JOINs are often more efficient than subqueries",
                estimated_improvement=25.0,
            ))

        # Check for ORDER BY without index
        if analysis.order_by and plan and not plan.index_used:
            order_cols = ", ".join(analysis.order_by)
            suggestions.append(OptimizationSuggestion(
                query=query,
                suggestion=f"Consider adding index on ORDER BY columns: {order_cols}",
                level=OptimizationLevel.HIGH,
                reason="ORDER BY without matching index requires filesort",
                estimated_improvement=40.0,
                apply_sql=f"CREATE INDEX idx_order ON table_name ({order_cols})",
            ))

        # Check for WHERE clause without index
        if analysis.where_clauses and plan and not plan.index_used:
            suggestions.append(OptimizationSuggestion(
                query=query,
                suggestion="Consider adding index on WHERE clause columns",
                level=OptimizationLevel.HIGH,
                reason="WHERE clause without index requires full table scan",
                estimated_improvement=50.0,
            ))

        # Check for many JOINs
        if len(analysis.join_clauses) > 3:
            suggestions.append(OptimizationSuggestion(
                query=query,
                suggestion="Consider denormalization or breaking into multiple queries",
                level=OptimizationLevel.MEDIUM,
                reason="Many JOINs can significantly impact performance",
                estimated_improvement=35.0,
            ))

        # Check execution time if plan provided
        if plan and plan.execution_time_ms:
            if plan.execution_time_ms > self.slow_query_threshold_ms:
                suggestions.append(OptimizationSuggestion(
                    query=query,
                    suggestion="Query is slow - review execution plan",
                    level=OptimizationLevel.CRITICAL,
                    reason=f"Execution time {plan.execution_time_ms:.0f}ms exceeds threshold",
                    estimated_improvement=50.0,
                ))

        # Check for full table scan
        if plan and plan.scan_type == "full":
            suggestions.append(OptimizationSuggestion(
                query=query,
                suggestion="Query uses full table scan - add appropriate index",
                level=OptimizationLevel.CRITICAL,
                reason="Full table scans are very inefficient for large tables",
                estimated_improvement=60.0,
            ))

        return suggestions

    def record_plan(self, query: str, plan: QueryPlan) -> None:
        """Record a query execution plan"""
        query_hash = self._hash_query(query)
        if query_hash not in self.query_history:
            self.query_history[query_hash] = []
        self.query_history[query_hash].append(plan)

    def get_slow_queries(self, threshold_ms: float = None) -> List[Tuple[str, QueryPlan]]:
        """Get queries that exceeded threshold"""
        threshold = threshold_ms or self.slow_query_threshold_ms
        slow_queries = []

        for query_hash, plans in self.query_history.items():
            for plan in plans:
                if plan.execution_time_ms and plan.execution_time_ms > threshold:
                    # Find original query
                    slow_queries.append((self._find_query_by_hash(query_hash), plan))

        return sorted(slow_queries, key=lambda x: x[1].execution_time_ms, reverse=True)

    def suggest_indexes(self) -> Dict[str, List[str]]:
        """Generate index suggestions based on query patterns"""
        index_suggestions = {}

        for query_hash, plans in self.query_history.items():
            for plan in plans:
                if not plan.index_used:
                    query = self._find_query_by_hash(query_hash)
                    if query:
                        analysis = self.analyze(query)
                        for table in analysis.tables:
                            if table not in index_suggestions:
                                index_suggestions[table] = []

                            # Suggest indexes for WHERE columns
                            if analysis.where_clauses:
                                index_suggestions[table].append(
                                    f"WHERE: {analysis.where_clauses[0]}"
                                )

                            # Suggest indexes for ORDER BY
                            if analysis.order_by:
                                index_suggestions[table].append(
                                    f"ORDER BY: {', '.join(analysis.order_by)}"
                                )

        return index_suggestions

    def _hash_query(self, query: str) -> str:
        """Create a hash for a query"""
        import hashlib
        normalized = " ".join(query.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()

    def _find_query_by_hash(self, query_hash: str) -> Optional[str]:
        """Find original query by hash"""
        for query, plans in self.query_history.items():
            if self._hash_query(query) == query_hash:
                return query
        return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get optimizer statistics"""
        total_queries = len(self.query_history)
        total_plans = sum(len(plans) for plans in self.query_history.values())
        slow_queries = len(self.get_slow_queries())

        return {
            "total_unique_queries": total_queries,
            "total_plans_recorded": total_plans,
            "slow_queries_count": slow_queries,
            "slow_query_threshold_ms": self.slow_query_threshold_ms,
        }


class QueryRewriter:
    """
    Query rewriter that can automatically optimize queries.
    """

    def __init__(self):
        self.parser = QueryParser()

    def rewrite(self, query: str) -> Tuple[str, List[str]]:
        """
        Rewrite a query for better performance.
        Returns the rewritten query and list of changes made.
        """
        changes = []
        rewritten = query

        # Normalize whitespace
        rewritten = " ".join(rewritten.split())
        if rewritten != query:
            changes.append("Normalized whitespace")

        # Convert NOT IN to NOT EXISTS (usually faster)
        if "NOT IN" in rewritten.upper():
            rewritten = self._convert_not_in_to_not_exists(rewritten)
            changes.append("Converted NOT IN to NOT EXISTS")

        # Remove unnecessary DISTINCT with PRIMARY KEY
        if "SELECT DISTINCT" in rewritten.upper():
            # This is a simple heuristic - real implementation would need schema info
            pass

        # Optimize OR conditions
        if " OR " in rewritten.upper() and "WHERE" in rewritten.upper():
            rewritten = self._optimize_or_conditions(rewritten)
            changes.append("Optimized OR conditions")

        return rewritten, changes

    def _convert_not_in_to_not_exists(self, query: str) -> str:
        """Convert NOT IN to NOT EXISTS"""
        # Simple pattern matching - real implementation would need full parsing
        pattern = r"(\w+)\s+NOT\s+IN\s*\(([^)]+)\)"
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            column = match.group(1)
            subquery = match.group(2)
            if "SELECT" in subquery.upper():
                return query.replace(
                    match.group(0),
                    f"NOT EXISTS ({subquery.replace('SELECT', f'SELECT 1 FROM', 1)} AND {column} = ...)"
                )
        return query

    def _optimize_or_conditions(self, query: str) -> str:
        """Optimize OR conditions to UNION"""
        # This is a placeholder - real implementation would parse and restructure
        return query
