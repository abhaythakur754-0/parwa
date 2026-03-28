"""
Data Transformation Engine Module
Week 56 - Advanced Data Pipelines

Provides data transformation capabilities with support for
various transformation types and chained operations.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union, TypeVar, Generic
from datetime import datetime
import logging
import copy

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TransformType(Enum):
    """Types of data transformations."""
    MAP = "map"
    FILTER = "filter"
    AGGREGATE = "aggregate"
    JOIN = "join"
    PIVOT = "pivot"
    SORT = "sort"
    GROUP = "group"
    FLATTEN = "flatten"
    MERGE = "merge"
    SPLIT = "split"
    RENAME = "rename"
    DROP = "drop"
    FILL = "fill"


class TransformStatus(Enum):
    """Status of a transformation."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TransformRule:
    """Rule defining a data transformation."""
    name: str
    transform_type: TransformType
    input_field: Optional[str] = None
    output_field: Optional[str] = None
    operation: Optional[Union[Callable, str]] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[Callable] = None
    enabled: bool = True
    description: str = ""
    order: int = 0

    def validate(self) -> List[str]:
        """Validate the transformation rule."""
        errors = []

        if not self.name:
            errors.append("Rule name is required")

        if not isinstance(self.transform_type, TransformType):
            errors.append("Invalid transform type")

        # Type-specific validation
        if self.transform_type == TransformType.MAP:
            if not self.operation:
                errors.append("Map transformation requires an operation")

        elif self.transform_type == TransformType.FILTER:
            if not self.condition and not self.operation:
                errors.append("Filter transformation requires a condition or operation")

        elif self.transform_type == TransformType.AGGREGATE:
            if not self.operation:
                errors.append("Aggregate transformation requires an operation")

        return errors


@dataclass
class TransformResult:
    """Result of a transformation operation."""
    rule_name: str
    transform_type: TransformType
    status: TransformStatus
    input_records: int = 0
    output_records: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=dict)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Check if transformation succeeded."""
        return self.status == TransformStatus.COMPLETED


@dataclass
class TransformChain:
    """Chain of transformation rules to be applied sequentially."""
    name: str
    rules: List[TransformRule] = field(default_factory=list)
    stop_on_error: bool = True

    def add_rule(self, rule: TransformRule) -> None:
        """Add a rule to the chain."""
        rule.order = len(self.rules)
        self.rules.append(rule)

    def remove_rule(self, rule_name: str) -> bool:
        """Remove a rule by name."""
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                self.rules.pop(i)
                # Reorder remaining rules
                for j, r in enumerate(self.rules):
                    r.order = j
                return True
        return False

    def get_rule(self, rule_name: str) -> Optional[TransformRule]:
        """Get a rule by name."""
        for rule in self.rules:
            if rule.name == rule_name:
                return rule
        return None

    def validate(self) -> List[str]:
        """Validate all rules in the chain."""
        errors = []
        rule_names = set()

        for rule in self.rules:
            # Check for duplicate names
            if rule.name in rule_names:
                errors.append(f"Duplicate rule name: {rule.name}")
            rule_names.add(rule.name)

            # Validate individual rule
            errors.extend(rule.validate())

        return errors


class TransformEngine:
    """
    Data transformation engine.

    Supports various transformation types and chained operations
    for complex data processing pipelines.
    """

    def __init__(self):
        """Initialize the transform engine."""
        self._transformers: Dict[TransformType, Callable] = {}
        self._custom_operations: Dict[str, Callable] = {}
        self._results: List[TransformResult] = []

        # Register built-in transformers
        self._register_builtin_transformers()

    def _register_builtin_transformers(self) -> None:
        """Register built-in transformation handlers."""
        self._transformers[TransformType.MAP] = self._transform_map
        self._transformers[TransformType.FILTER] = self._transform_filter
        self._transformers[TransformType.AGGREGATE] = self._transform_aggregate
        self._transformers[TransformType.JOIN] = self._transform_join
        self._transformers[TransformType.PIVOT] = self._transform_pivot
        self._transformers[TransformType.SORT] = self._transform_sort
        self._transformers[TransformType.GROUP] = self._transform_group
        self._transformers[TransformType.FLATTEN] = self._transform_flatten
        self._transformers[TransformType.MERGE] = self._transform_merge
        self._transformers[TransformType.SPLIT] = self._transform_split
        self._transformers[TransformType.RENAME] = self._transform_rename
        self._transformers[TransformType.DROP] = self._transform_drop
        self._transformers[TransformType.FILL] = self._transform_fill

    def register_custom_operation(self, name: str, operation: Callable) -> None:
        """
        Register a custom operation.

        Args:
            name: Operation name
            operation: Callable that performs the operation
        """
        self._custom_operations[name] = operation

    def transform(
        self,
        data: Any,
        rule: TransformRule
    ) -> TransformResult:
        """
        Apply a single transformation rule to data.

        Args:
            data: Input data to transform
            rule: Transformation rule to apply

        Returns:
            TransformResult with transformed data
        """
        result = TransformResult(
            rule_name=rule.name,
            transform_type=rule.transform_type,
            status=TransformStatus.RUNNING,
            input_records=self._count_records(data)
        )

        start_time = datetime.now()

        try:
            if not rule.enabled:
                result.status = TransformStatus.SKIPPED
                result.warnings.append("Rule is disabled")
            else:
                transformer = self._transformers.get(rule.transform_type)

                if not transformer:
                    raise ValueError(
                        f"No transformer registered for type {rule.transform_type.value}"
                    )

                transformed_data = transformer(data, rule)
                result.status = TransformStatus.COMPLETED
                result.output_records = self._count_records(transformed_data)
                result.metadata["output_data"] = transformed_data

        except Exception as e:
            result.status = TransformStatus.FAILED
            result.errors.append(str(e))

        result.duration_ms = (
            datetime.now() - start_time
        ).total_seconds() * 1000

        self._results.append(result)
        return result

    def transform_chain(
        self,
        data: Any,
        chain: TransformChain
    ) -> List[TransformResult]:
        """
        Apply a chain of transformations sequentially.

        Args:
            data: Input data
            chain: TransformChain containing rules

        Returns:
            List of TransformResult for each rule
        """
        results = []
        current_data = data

        for rule in sorted(chain.rules, key=lambda r: r.order):
            result = self.transform(current_data, rule)
            results.append(result)

            if not result.success and chain.stop_on_error:
                break

            if result.success and "output_data" in result.metadata:
                current_data = result.metadata["output_data"]

        return results

    def transform_batch(
        self,
        data: Any,
        rules: List[TransformRule]
    ) -> List[TransformResult]:
        """
        Apply multiple transformations in sequence.

        Args:
            data: Input data
            rules: List of transformation rules

        Returns:
            List of TransformResult for each rule
        """
        chain = TransformChain(name="batch_transform")
        for rule in rules:
            chain.add_rule(rule)
        return self.transform_chain(data, chain)

    def _count_records(self, data: Any) -> int:
        """Count records in data."""
        if data is None:
            return 0
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            return len(data)
        return 1

    def _get_operation(self, operation: Union[Callable, str, None]) -> Optional[Callable]:
        """Get operation callable from rule."""
        if operation is None:
            return None
        if callable(operation):
            return operation
        if isinstance(operation, str):
            return self._custom_operations.get(operation)
        return None

    def _transform_map(self, data: Any, rule: TransformRule) -> Any:
        """Apply map transformation."""
        operation = self._get_operation(rule.operation)

        if isinstance(data, list):
            if rule.input_field:
                return [
                    {
                        **item,
                        rule.output_field or rule.input_field: operation(item.get(rule.input_field))
                    }
                    if isinstance(item, dict) else item
                    for item in data
                ]
            return [operation(item) for item in data]

        if isinstance(data, dict):
            if rule.input_field:
                result = copy.deepcopy(data)
                result[rule.output_field or rule.input_field] = operation(
                    data.get(rule.input_field)
                )
                return result
            return operation(data)

        return operation(data)

    def _transform_filter(self, data: Any, rule: TransformRule) -> Any:
        """Apply filter transformation."""
        condition = rule.condition or self._get_operation(rule.operation)

        if isinstance(data, list):
            return [item for item in data if condition(item)]

        if isinstance(data, dict):
            return {
                k: v for k, v in data.items()
                if condition({k: v})
            }

        return data

    def _transform_aggregate(self, data: Any, rule: TransformRule) -> Any:
        """Apply aggregate transformation."""
        if not isinstance(data, list):
            return data

        operation = self._get_operation(rule.operation)
        field = rule.input_field
        params = rule.parameters

        # Extract field values if specified
        if field:
            values = [
                item.get(field) if isinstance(item, dict) else item
                for item in data
                if isinstance(item, dict) and item.get(field) is not None
            ]
        else:
            values = data

        # Apply aggregation operation
        if operation:
            return operation(values)

        # Built-in aggregation types
        agg_type = params.get("type", "sum")

        if agg_type == "sum":
            return sum(v for v in values if isinstance(v, (int, float)))
        elif agg_type == "count":
            return len(values)
        elif agg_type == "avg" or agg_type == "mean":
            numeric = [v for v in values if isinstance(v, (int, float))]
            return sum(numeric) / len(numeric) if numeric else 0
        elif agg_type == "min":
            return min(values) if values else None
        elif agg_type == "max":
            return max(values) if values else None
        elif agg_type == "first":
            return values[0] if values else None
        elif agg_type == "last":
            return values[-1] if values else None

        return values

    def _transform_join(self, data: Any, rule: TransformRule) -> Any:
        """Apply join transformation."""
        params = rule.parameters
        right_data = params.get("right_data", [])
        left_key = params.get("left_key", rule.input_field)
        right_key = params.get("right_key", "id")
        join_type = params.get("join_type", "inner")

        if not isinstance(data, list):
            return data

        # Build lookup from right data
        right_lookup = {}
        for item in right_data:
            key = item.get(right_key) if isinstance(item, dict) else item
            right_lookup[key] = item

        result = []

        for left_item in data:
            left_key_val = (
                left_item.get(left_key) if isinstance(left_item, dict) else left_item
            )

            right_match = right_lookup.get(left_key_val)

            if right_match:
                if isinstance(left_item, dict) and isinstance(right_match, dict):
                    merged = {**left_item, **right_match}
                    result.append(merged)
                else:
                    result.append((left_item, right_match))
            elif join_type == "left":
                result.append(left_item)

        return result

    def _transform_pivot(self, data: Any, rule: TransformRule) -> Any:
        """Apply pivot transformation."""
        if not isinstance(data, list):
            return data

        params = rule.parameters
        index_col = params.get("index")
        columns_col = params.get("columns")
        values_col = params.get("values")

        result = {}

        for item in data:
            if not isinstance(item, dict):
                continue

            index_val = item.get(index_col)
            col_val = item.get(columns_col)
            val = item.get(values_col)

            if index_val not in result:
                result[index_val] = {}

            result[index_val][col_val] = val

        return result

    def _transform_sort(self, data: Any, rule: TransformRule) -> Any:
        """Apply sort transformation."""
        if not isinstance(data, list):
            return data

        params = rule.parameters
        key = rule.input_field
        reverse = params.get("reverse", False)

        def sort_key(item):
            if isinstance(item, dict) and key:
                return item.get(key, "")
            return item

        return sorted(data, key=sort_key, reverse=reverse)

    def _transform_group(self, data: Any, rule: TransformRule) -> Any:
        """Apply group transformation."""
        if not isinstance(data, list):
            return data

        key = rule.input_field or rule.parameters.get("key")
        result = {}

        for item in data:
            if isinstance(item, dict):
                group_key = item.get(key)
            else:
                group_key = item

            if group_key not in result:
                result[group_key] = []

            result[group_key].append(item)

        return result

    def _transform_flatten(self, data: Any, rule: TransformRule) -> Any:
        """Apply flatten transformation."""
        if isinstance(data, list):
            result = []
            for item in data:
                if isinstance(item, list):
                    result.extend(item)
                else:
                    result.append(item)
            return result

        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                if isinstance(v, dict):
                    for sub_k, sub_v in v.items():
                        result[f"{k}_{sub_k}"] = sub_v
                else:
                    result[k] = v
            return result

        return data

    def _transform_merge(self, data: Any, rule: TransformRule) -> Any:
        """Apply merge transformation."""
        params = rule.parameters
        other_data = params.get("data", [])
        strategy = params.get("strategy", "extend")

        if not isinstance(data, list):
            return data

        if strategy == "extend":
            return data + other_data
        elif strategy == "unique":
            return list(set(data + other_data))
        elif strategy == "intersect":
            return [item for item in data if item in other_data]

        return data

    def _transform_split(self, data: Any, rule: TransformRule) -> Any:
        """Apply split transformation."""
        params = rule.parameters
        delimiter = params.get("delimiter", ",")
        field = rule.input_field

        if isinstance(data, str):
            return data.split(delimiter)

        if isinstance(data, dict) and field:
            val = data.get(field, "")
            if isinstance(val, str):
                result = copy.deepcopy(data)
                result[field] = val.split(delimiter)
                return result

        return data

    def _transform_rename(self, data: Any, rule: TransformRule) -> Any:
        """Apply rename transformation."""
        params = rule.parameters
        mapping = params.get("mapping", {})

        if isinstance(data, dict):
            return {mapping.get(k, k): v for k, v in data.items()}

        if isinstance(data, list):
            return [
                {mapping.get(k, k): v for k, v in item.items()}
                if isinstance(item, dict) else item
                for item in data
            ]

        return data

    def _transform_drop(self, data: Any, rule: TransformRule) -> Any:
        """Apply drop transformation."""
        params = rule.parameters
        fields = params.get("fields", [])
        if rule.input_field:
            fields.append(rule.input_field)

        if isinstance(data, dict):
            return {k: v for k, v in data.items() if k not in fields}

        if isinstance(data, list):
            return [
                {k: v for k, v in item.items() if k not in fields}
                if isinstance(item, dict) else item
                for item in data
            ]

        return data

    def _transform_fill(self, data: Any, rule: TransformRule) -> Any:
        """Apply fill transformation."""
        params = rule.parameters
        fill_value = params.get("value")
        fields = params.get("fields", [rule.input_field] if rule.input_field else None)

        if isinstance(data, dict):
            result = copy.deepcopy(data)
            for field in (fields or list(data.keys())):
                if field in result and result[field] is None:
                    result[field] = fill_value
            return result

        if isinstance(data, list):
            return [
                self._transform_fill(item, rule) if isinstance(item, dict) else item
                for item in data
            ]

        return data

    def get_results(self) -> List[TransformResult]:
        """Get all transformation results."""
        return self._results.copy()

    def clear_results(self) -> None:
        """Clear stored results."""
        self._results = []


def create_transform_rule(
    name: str,
    transform_type: TransformType,
    input_field: Optional[str] = None,
    output_field: Optional[str] = None,
    operation: Optional[Union[Callable, str]] = None,
    **kwargs
) -> TransformRule:
    """
    Create a transformation rule.

    Args:
        name: Rule name
        transform_type: Type of transformation
        input_field: Input field name
        output_field: Output field name
        operation: Operation to apply
        **kwargs: Additional rule parameters

    Returns:
        TransformRule instance
    """
    return TransformRule(
        name=name,
        transform_type=transform_type,
        input_field=input_field,
        output_field=output_field,
        operation=operation,
        parameters=kwargs
    )
