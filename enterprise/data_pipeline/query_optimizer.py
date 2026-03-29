"""
Query Optimization Engine

Provides query optimization capabilities including plan generation,
cost estimation, index suggestions, and join optimization.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from datetime import datetime
import re


class JoinType(Enum):
    """Supported join types."""
    INNER = "INNER"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    FULL = "FULL"
    CROSS = "CROSS"


class ScanType(Enum):
    """Table scan types."""
    SEQUENTIAL = "SEQUENTIAL"
    INDEX = "INDEX"
    PARTITION = "PARTITION"


@dataclass
class ColumnStats:
    """Statistics for a table column."""
    column_name: str
    distinct_count: int
    null_count: int
    min_value: Any = None
    max_value: Any = None
    avg_size: float = 0.0

    def selectivity(self, value: Any) -> float:
        """Estimate selectivity for a value."""
        if self.distinct_count == 0:
            return 1.0
        return 1.0 / self.distinct_count


@dataclass
class TableStats:
    """Statistics for a table."""
    table_name: str
    row_count: int
    size_bytes: int
    column_stats: Dict[str, ColumnStats] = field(default_factory=dict)
    last_analyzed: datetime = field(default_factory=datetime.utcnow)

    def get_column_stats(self, column_name: str) -> Optional[ColumnStats]:
        """Get statistics for a specific column."""
        return self.column_stats.get(column_name)


@dataclass
class IndexSuggestion:
    """Suggestion for creating an index."""
    table_name: str
    columns: List[str]
    index_type: str  # BTREE, HASH, BITMAP
    reason: str
    estimated_benefit: float  # Percentage improvement

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "table_name": self.table_name,
            "columns": self.columns,
            "index_type": self.index_type,
            "reason": self.reason,
            "estimated_benefit": self.estimated_benefit
        }


@dataclass
class QueryStep:
    """Single step in a query execution plan."""
    step_id: int
    operation: str
    table_name: Optional[str] = None
    cost: float = 0.0
    cardinality: int = 0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step_id": self.step_id,
            "operation": self.operation,
            "table_name": self.table_name,
            "cost": self.cost,
            "cardinality": self.cardinality,
            "details": self.details
        }


@dataclass
class QueryPlan:
    """
    Query execution plan with steps and cost estimate.
    """
    query_id: str
    steps: List[QueryStep]
    total_cost: float
    estimated_rows: int
    estimated_time_ms: float
    tables_accessed: List[str] = field(default_factory=list)
    indexes_used: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary."""
        return {
            "query_id": self.query_id,
            "steps": [step.to_dict() for step in self.steps],
            "total_cost": self.total_cost,
            "estimated_rows": self.estimated_rows,
            "estimated_time_ms": self.estimated_time_ms,
            "tables_accessed": self.tables_accessed,
            "indexes_used": self.indexes_used,
            "created_at": self.created_at.isoformat()
        }

    def get_step(self, step_id: int) -> Optional[QueryStep]:
        """Get step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None


@dataclass
class OptimizationRule:
    """
    Rule for query optimization with condition and transformation.
    """
    name: str
    description: str
    condition: Callable[[Dict[str, Any]], bool]
    transformation: Callable[[Dict[str, Any]], Dict[str, Any]]
    priority: int = 0  # Higher = more important
    enabled: bool = True

    def apply(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Apply rule if condition is met.
        
        Args:
            context: Query context to evaluate
            
        Returns:
            Transformed context if rule applied, None otherwise
        """
        if not self.enabled:
            return None
        
        if self.condition(context):
            return self.transformation(context)
        
        return None


@dataclass
class JoinOptimization:
    """Result of join optimization analysis."""
    join_order: List[str]
    join_type: JoinType
    estimated_cost: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "join_order": self.join_order,
            "join_type": self.join_type.value,
            "estimated_cost": self.estimated_cost,
            "reason": self.reason
        }


class QueryOptimizer:
    """
    Query optimization engine for improving query performance.
    
    Features:
    - Query plan generation
    - Cost-based optimization
    - Index suggestions
    - Join optimization
    - Rule-based transformations
    """

    def __init__(self):
        """Initialize query optimizer."""
        self._table_stats: Dict[str, TableStats] = {}
        self._indexes: Dict[str, List[str]] = {}  # table -> indexed columns
        self._rules: List[OptimizationRule] = []
        self._query_counter = 0
        
        # Add default optimization rules
        self._add_default_rules()

    def _add_default_rules(self) -> None:
        """Add default optimization rules."""
        
        # Rule: Push down filters
        self.add_rule(OptimizationRule(
            name="filter_pushdown",
            description="Push filters down to table scans",
            condition=lambda ctx: "filters" in ctx and "tables" in ctx,
            transformation=lambda ctx: {**ctx, "filter_pushdown": True},
            priority=10
        ))

        # Rule: Use index for equality predicates
        self.add_rule(OptimizationRule(
            name="index_scan",
            description="Use index for equality predicates",
            condition=lambda ctx: bool(ctx.get("equality_preds")),
            transformation=lambda ctx: {**ctx, "use_index": True},
            priority=8
        ))

        # Rule: Eliminate redundant joins
        self.add_rule(OptimizationRule(
            name="join_elimination",
            description="Remove unnecessary joins",
            condition=lambda ctx: ctx.get("join_count", 0) > 2,
            transformation=lambda ctx: {**ctx, "eliminate_redundant_joins": True},
            priority=9
        ))

        # Rule: Partition pruning
        self.add_rule(OptimizationRule(
            name="partition_pruning",
            description="Prune partitions based on predicates",
            condition=lambda ctx: bool(ctx.get("partition_keys")),
            transformation=lambda ctx: {**ctx, "prune_partitions": True},
            priority=7
        ))

    def add_rule(self, rule: OptimizationRule) -> None:
        """Add an optimization rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def remove_rule(self, rule_name: str) -> bool:
        """Remove a rule by name."""
        for i, rule in enumerate(self._rules):
            if rule.name == rule_name:
                del self._rules[i]
                return True
        return False

    def get_rules(self) -> List[OptimizationRule]:
        """Get all optimization rules."""
        return list(self._rules)

    def set_table_stats(self, stats: TableStats) -> None:
        """Set statistics for a table."""
        self._table_stats[stats.table_name] = stats

    def get_table_stats(self, table_name: str) -> Optional[TableStats]:
        """Get statistics for a table."""
        return self._table_stats.get(table_name)

    def register_index(self, table_name: str, columns: List[str]) -> None:
        """Register an index for a table."""
        if table_name not in self._indexes:
            self._indexes[table_name] = []
        self._indexes[table_name].extend(columns)

    def get_indexes(self, table_name: str) -> List[str]:
        """Get indexed columns for a table."""
        return self._indexes.get(table_name, [])

    def optimize(self, query: Dict[str, Any]) -> QueryPlan:
        """
        Optimize a query and generate execution plan.
        
        Args:
            query: Query specification with tables, filters, joins, etc.
            
        Returns:
            Optimized QueryPlan
        """
        self._query_counter += 1
        query_id = f"q{self._query_counter:06d}"
        
        # Apply optimization rules
        context = self._prepare_context(query)
        
        for rule in self._rules:
            result = rule.apply(context)
            if result:
                context = result
        
        # Generate execution plan
        steps = self._generate_plan_steps(context)
        
        # Calculate costs
        total_cost, total_rows, total_time = self._estimate_costs(steps, context)
        
        return QueryPlan(
            query_id=query_id,
            steps=steps,
            total_cost=total_cost,
            estimated_rows=total_rows,
            estimated_time_ms=total_time,
            tables_accessed=context.get("tables", []),
            indexes_used=context.get("indexes_used", [])
        )

    def _prepare_context(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare optimization context from query."""
        context = dict(query)
        
        # Extract table information
        tables = query.get("tables", [])
        context["tables"] = tables
        
        # Analyze filters
        filters = query.get("filters", {})
        equality_preds = []
        range_preds = []
        
        for col, condition in filters.items():
            if isinstance(condition, dict):
                if "$eq" in condition:
                    equality_preds.append(col)
                elif "$gte" in condition or "$lte" in condition:
                    range_preds.append(col)
            else:
                equality_preds.append(col)
        
        context["equality_preds"] = equality_preds
        context["range_preds"] = range_preds
        
        # Check for indexed columns
        indexes_used = []
        for table in tables:
            indexed_cols = set(self.get_indexes(table))
            for col in equality_preds:
                if col in indexed_cols:
                    indexes_used.append(f"{table}.{col}")
        
        context["indexes_used"] = indexes_used
        
        # Join analysis
        joins = query.get("joins", [])
        context["join_count"] = len(joins)
        
        # Partition keys
        context["partition_keys"] = query.get("partition_keys", [])
        
        return context

    def _generate_plan_steps(self, context: Dict[str, Any]) -> List[QueryStep]:
        """Generate execution plan steps."""
        steps = []
        step_id = 0
        tables = context.get("tables", [])
        filters = context.get("filters", {})
        
        # Determine scan type for each table
        for table in tables:
            step_id += 1
            table_stats = self.get_table_stats(table)
            indexed_cols = set(self.get_indexes(table))
            
            # Check if we can use index scan
            scan_type = ScanType.SEQUENTIAL
            if context.get("use_index") and any(
                col in indexed_cols for col in context.get("equality_preds", [])
            ):
                scan_type = ScanType.INDEX
            elif context.get("prune_partitions"):
                scan_type = ScanType.PARTITION
            
            row_count = table_stats.row_count if table_stats else 1000
            
            steps.append(QueryStep(
                step_id=step_id,
                operation=f"SCAN_{scan_type.value}",
                table_name=table,
                cost=row_count * (0.1 if scan_type == ScanType.INDEX else 1.0),
                cardinality=row_count,
                details={"scan_type": scan_type.value}
            ))
            
            # Add filter step if filters exist
            if filters:
                step_id += 1
                selectivity = 0.1  # Default selectivity
                
                steps.append(QueryStep(
                    step_id=step_id,
                    operation="FILTER",
                    table_name=table,
                    cost=row_count * 0.01,
                    cardinality=int(row_count * selectivity),
                    details={"predicates": list(filters.keys())}
                ))
        
        # Add join steps
        joins = context.get("joins", [])
        for join in joins:
            step_id += 1
            steps.append(QueryStep(
                step_id=step_id,
                operation="JOIN",
                cost=1000,  # Base join cost
                cardinality=500,
                details={
                    "join_type": join.get("type", "INNER"),
                    "left_table": join.get("left_table"),
                    "right_table": join.get("right_table"),
                    "on": join.get("on")
                }
            ))
        
        # Add aggregation step if present
        if context.get("aggregation"):
            step_id += 1
            steps.append(QueryStep(
                step_id=step_id,
                operation="AGGREGATE",
                cost=100,
                cardinality=10,
                details=context.get("aggregation")
            ))
        
        # Add sort step if needed
        if context.get("order_by"):
            step_id += 1
            steps.append(QueryStep(
                step_id=step_id,
                operation="SORT",
                cost=500,
                cardinality=steps[-1].cardinality if steps else 100,
                details={"order_by": context.get("order_by")}
            ))
        
        return steps

    def _estimate_costs(
        self,
        steps: List[QueryStep],
        context: Dict[str, Any]
    ) -> Tuple[float, int, float]:
        """Estimate total cost, rows, and time."""
        total_cost = sum(step.cost for step in steps)
        total_rows = steps[-1].cardinality if steps else 0
        total_time = total_cost * 0.1  # ms per cost unit
        
        return total_cost, total_rows, total_time

    def suggest_indexes(
        self,
        query: Dict[str, Any],
        table_name: Optional[str] = None
    ) -> List[IndexSuggestion]:
        """
        Suggest indexes for a query.
        
        Args:
            query: Query to analyze
            table_name: Specific table (optional)
            
        Returns:
            List of index suggestions
        """
        suggestions = []
        context = self._prepare_context(query)
        
        tables = [table_name] if table_name else context.get("tables", [])
        
        for table in tables:
            existing_indexes = set(self.get_indexes(table))
            
            # Suggest index on equality predicates
            for col in context.get("equality_preds", []):
                if col not in existing_indexes:
                    suggestions.append(IndexSuggestion(
                        table_name=table,
                        columns=[col],
                        index_type="BTREE",
                        reason=f"Column '{col}' used in equality predicate",
                        estimated_benefit=50.0
                    ))
            
            # Suggest composite index for multiple predicates
            eq_preds = context.get("equality_preds", [])
            if len(eq_preds) > 1:
                composite_cols = [c for c in eq_preds if c not in existing_indexes]
                if composite_cols:
                    suggestions.append(IndexSuggestion(
                        table_name=table,
                        columns=composite_cols,
                        index_type="BTREE",
                        reason="Composite index for multiple predicates",
                        estimated_benefit=70.0
                    ))
            
            # Suggest index on join columns
            for join in context.get("joins", []):
                on_clause = join.get("on", {})
                for col in on_clause.keys():
                    if col not in existing_indexes:
                        suggestions.append(IndexSuggestion(
                            table_name=table,
                            columns=[col],
                            index_type="HASH",
                            reason=f"Column '{col}' used in join",
                            estimated_benefit=60.0
                        ))
        
        return suggestions

    def optimize_joins(
        self,
        query: Dict[str, Any]
    ) -> List[JoinOptimization]:
        """
        Analyze and optimize join order and types.
        
        Args:
            query: Query with joins to optimize
            
        Returns:
            List of join optimization recommendations
        """
        optimizations = []
        joins = query.get("joins", [])
        
        if not joins:
            return optimizations
        
        # Simple heuristic: order tables by size
        tables = query.get("tables", [])
        table_sizes = []
        
        for table in tables:
            stats = self.get_table_stats(table)
            size = stats.row_count if stats else 1000
            table_sizes.append((table, size))
        
        # Sort by size (smallest first for better join performance)
        sorted_tables = sorted(table_sizes, key=lambda x: x[1])
        optimal_order = [t[0] for t in sorted_tables]
        
        # Analyze each join
        for i, join in enumerate(joins):
            join_type = JoinType.INNER
            if join.get("type") == "LEFT":
                join_type = JoinType.LEFT
            elif join.get("type") == "RIGHT":
                join_type = JoinType.RIGHT
            elif join.get("type") == "FULL":
                join_type = JoinType.FULL
            
            # Estimate cost based on table sizes
            left_table = join.get("left_table", "")
            right_table = join.get("right_table", "")
            
            left_size = next((s for t, s in table_sizes if t == left_table), 1000)
            right_size = next((s for t, s in table_sizes if t == right_table), 1000)
            
            estimated_cost = left_size * right_size * 0.001
            
            optimizations.append(JoinOptimization(
                join_order=optimal_order,
                join_type=join_type,
                estimated_cost=estimated_cost,
                reason=f"Join order optimized by table cardinality"
            ))
        
        return optimizations

    def analyze_query(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a query and return comprehensive insights.
        
        Args:
            query: Query to analyze
            
        Returns:
            Analysis results including plan, suggestions, and metrics
        """
        plan = self.optimize(query)
        index_suggestions = self.suggest_indexes(query)
        join_optimizations = self.optimize_joins(query)
        
        return {
            "query_plan": plan.to_dict(),
            "index_suggestions": [s.to_dict() for s in index_suggestions],
            "join_optimizations": [j.to_dict() for j in join_optimizations],
            "warnings": self._generate_warnings(plan),
            "recommendations": self._generate_recommendations(plan, index_suggestions)
        }

    def _generate_warnings(self, plan: QueryPlan) -> List[str]:
        """Generate warnings for potential issues."""
        warnings = []
        
        if plan.total_cost > 10000:
            warnings.append("High estimated cost - consider adding filters or indexes")
        
        sequential_scans = [
            s for s in plan.steps if "SEQUENTIAL" in s.operation
        ]
        if len(sequential_scans) > 1:
            warnings.append("Multiple sequential scans detected - consider indexes")
        
        if plan.estimated_rows > 100000:
            warnings.append("Large result set - consider adding LIMIT or filters")
        
        return warnings

    def _generate_recommendations(
        self,
        plan: QueryPlan,
        index_suggestions: List[IndexSuggestion]
    ) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        if index_suggestions:
            recommendations.append(
                f"Consider creating {len(index_suggestions)} suggested indexes"
            )
        
        if not plan.indexes_used and plan.tables_accessed:
            recommendations.append(
                "No indexes used - query performance may be suboptimal"
            )
        
        for step in plan.steps:
            if step.operation == "SORT" and step.details.get("order_by"):
                recommendations.append(
                    f"Consider adding index on ORDER BY columns: {step.details['order_by']}"
                )
        
        return recommendations

    def explain_plan(self, query: Dict[str, Any]) -> str:
        """
        Generate human-readable explanation of query plan.
        
        Args:
            query: Query to explain
            
        Returns:
            Formatted plan explanation
        """
        plan = self.optimize(query)
        
        lines = [
            f"Query Plan: {plan.query_id}",
            f"=" * 50,
            f"Estimated Cost: {plan.total_cost:.2f}",
            f"Estimated Rows: {plan.estimated_rows}",
            f"Estimated Time: {plan.estimated_time_ms:.2f}ms",
            "",
            "Execution Steps:"
        ]
        
        for step in plan.steps:
            lines.append(f"  [{step.step_id}] {step.operation}")
            if step.table_name:
                lines.append(f"      Table: {step.table_name}")
            lines.append(f"      Cost: {step.cost:.2f}, Rows: {step.cardinality}")
            if step.details:
                for key, value in step.details.items():
                    lines.append(f"      {key}: {value}")
        
        lines.extend([
            "",
            f"Tables Accessed: {', '.join(plan.tables_accessed)}",
            f"Indexes Used: {', '.join(plan.indexes_used) or 'None'}"
        ])
        
        return "\n".join(lines)
