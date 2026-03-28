"""
Data Cleaning Utilities for Week 56 Advanced Data Pipelines.
Provides comprehensive data cleaning with null handling, deduplication, and transformations.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
from enum import Enum
from datetime import datetime
import re
import copy


class CleaningOperation(Enum):
    """Supported cleaning operations."""
    TRIM = "trim"
    NORMALIZE = "normalize"
    FILL = "fill"
    DROP = "drop"
    TRANSFORM = "transform"
    UPPERCASE = "uppercase"
    LOWERCASE = "lowercase"
    STRIP = "strip"
    REPLACE = "replace"
    ROUND = "round"
    FLOOR = "floor"
    CEIL = "ceil"
    FILL_NULL = "fill_null"
    DROP_NULL = "drop_null"
    DEDUPLICATE = "deduplicate"
    SPLIT = "split"
    JOIN = "join"
    EXTRACT = "extract"
    DEFAULT = "default"


@dataclass
class CleaningRule:
    """
    Definition of a data cleaning rule.
    
    Attributes:
        field: Field name to apply cleaning to
        operation: Type of cleaning operation
        params: Parameters for the operation
        condition: Optional condition for applying the rule
        priority: Priority for rule execution (lower = higher priority)
    """
    field: str
    operation: CleaningOperation
    params: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[Callable[[Any], bool]] = None
    priority: int = 100
    
    def __post_init__(self):
        """Validate and normalize rule configuration."""
        if isinstance(self.operation, str):
            self.operation = CleaningOperation(self.operation)


@dataclass
class CleaningResult:
    """
    Result of data cleaning operation.
    
    Attributes:
        data: Cleaned data
        records_processed: Number of records processed
        records_modified: Number of records modified
        operations_applied: List of operations applied
        warnings: List of warning messages
        cleaned_at: Timestamp of cleaning
    """
    data: Union[Dict[str, Any], List[Dict[str, Any]]]
    records_processed: int = 0
    records_modified: int = 0
    operations_applied: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    cleaned_at: datetime = field(default_factory=datetime.utcnow)


class DataCleaner:
    """
    Comprehensive data cleaning utility.
    
    Features:
    - Multiple cleaning operations (TRIM, NORMALIZE, FILL, DROP, TRANSFORM)
    - Null handling (fill with defaults, drop records)
    - Deduplication support
    - Custom transformation functions
    - Batch processing
    
    Example:
        cleaner = DataCleaner()
        cleaner.add_rule(CleaningRule("name", CleaningOperation.TRIM))
        cleaner.add_rule(CleaningRule("age", CleaningOperation.FILL_NULL, {"value": 0}))
        
        result = cleaner.clean({"name": "  John  ", "age": None})
        # Result: {"name": "John", "age": 0}
    """
    
    def __init__(self, name: Optional[str] = None):
        """
        Initialize the data cleaner.
        
        Args:
            name: Optional name for the cleaner
        """
        self.name = name or "DataCleaner"
        self._rules: List[CleaningRule] = []
        self._transformers: Dict[str, Callable] = {}
        self._register_builtin_operations()
    
    def _register_builtin_operations(self) -> None:
        """Register built-in cleaning operations."""
        self._operations: Dict[CleaningOperation, Callable] = {
            CleaningOperation.TRIM: self._op_trim,
            CleaningOperation.NORMALIZE: self._op_normalize,
            CleaningOperation.FILL: self._op_fill,
            CleaningOperation.DROP: self._op_drop,
            CleaningOperation.TRANSFORM: self._op_transform,
            CleaningOperation.UPPERCASE: self._op_uppercase,
            CleaningOperation.LOWERCASE: self._op_lowercase,
            CleaningOperation.STRIP: self._op_strip,
            CleaningOperation.REPLACE: self._op_replace,
            CleaningOperation.ROUND: self._op_round,
            CleaningOperation.FLOOR: self._op_floor,
            CleaningOperation.CEIL: self._op_ceil,
            CleaningOperation.FILL_NULL: self._op_fill_null,
            CleaningOperation.DROP_NULL: self._op_drop_null,
            CleaningOperation.DEDUPLICATE: self._op_deduplicate,
            CleaningOperation.SPLIT: self._op_split,
            CleaningOperation.JOIN: self._op_join,
            CleaningOperation.EXTRACT: self._op_extract,
            CleaningOperation.DEFAULT: self._op_default,
        }
    
    def add_rule(self, rule: CleaningRule) -> 'DataCleaner':
        """
        Add a cleaning rule.
        
        Args:
            rule: CleaningRule to add
            
        Returns:
            Self for method chaining
        """
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)
        return self
    
    def add_rules(self, rules: List[CleaningRule]) -> 'DataCleaner':
        """
        Add multiple cleaning rules.
        
        Args:
            rules: List of CleaningRule objects
            
        Returns:
            Self for method chaining
        """
        self._rules.extend(rules)
        self._rules.sort(key=lambda r: r.priority)
        return self
    
    def register_transformer(self, name: str, func: Callable) -> None:
        """
        Register a custom transformation function.
        
        Args:
            name: Name of the transformer
            func: Transformation function that takes a value and params
        """
        self._transformers[name] = func
    
    def clean(self, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> CleaningResult:
        """
        Clean data according to all registered rules.
        
        Args:
            data: Single record or list of records to clean
            
        Returns:
            CleaningResult with cleaned data
        """
        if isinstance(data, list):
            return self._clean_batch(data)
        else:
            return self._clean_single(data)
    
    def _clean_single(self, data: Dict[str, Any]) -> CleaningResult:
        """Clean a single record."""
        result = CleaningResult(
            data=copy.deepcopy(data),
            records_processed=1,
            records_modified=0
        )
        
        for rule in self._rules:
            if rule.field in result.data:
                original_value = result.data[rule.field]
                new_value = self._apply_operation(rule, original_value, result)
                
                if new_value is not None or rule.operation == CleaningOperation.DROP:
                    if rule.operation == CleaningOperation.DROP:
                        if rule.field in result.data:
                            del result.data[rule.field]
                            result.records_modified += 1
                            result.operations_applied.append(f"drop:{rule.field}")
                    elif new_value != original_value:
                        result.data[rule.field] = new_value
                        result.records_modified += 1
                        result.operations_applied.append(f"{rule.operation.value}:{rule.field}")
        
        return result
    
    def _clean_batch(self, data: List[Dict[str, Any]]) -> CleaningResult:
        """Clean multiple records."""
        cleaned_data = []
        total_modified = 0
        operations = set()
        warnings = []
        
        # Handle deduplication at batch level
        dedupe_fields = [r for r in self._rules if r.operation == CleaningOperation.DEDUPLICATE]
        if dedupe_fields:
            seen = set()
            for record in data:
                key_fields = [r.field for r in dedupe_fields]
                key = tuple(record.get(f) for f in key_fields)
                if key not in seen:
                    seen.add(key)
                    result = self._clean_single(record)
                    cleaned_data.append(result.data)
                    total_modified += result.records_modified
                    operations.update(result.operations_applied)
                else:
                    total_modified += 1
            warnings.append(f"Deduplicated {len(data) - len(cleaned_data)} records")
        else:
            for record in data:
                result = self._clean_single(record)
                cleaned_data.append(result.data)
                total_modified += result.records_modified
                operations.update(result.operations_applied)
        
        return CleaningResult(
            data=cleaned_data,
            records_processed=len(data),
            records_modified=total_modified,
            operations_applied=list(operations),
            warnings=warnings
        )
    
    def _apply_operation(self, rule: CleaningRule, value: Any, result: CleaningResult) -> Any:
        """Apply a cleaning operation to a value."""
        # Check condition if present
        if rule.condition is not None and not rule.condition(value):
            return value
        
        operation = self._operations.get(rule.operation)
        if operation is None:
            result.warnings.append(f"Unknown operation: {rule.operation}")
            return value
        
        try:
            return operation(value, rule.params)
        except Exception as e:
            result.warnings.append(f"Error applying {rule.operation} to {rule.field}: {str(e)}")
            return value
    
    def clear_rules(self) -> None:
        """Clear all cleaning rules."""
        self._rules.clear()
    
    # Built-in operations
    
    def _op_trim(self, value: Any, params: Dict[str, Any]) -> Any:
        """Trim whitespace from strings."""
        if isinstance(value, str):
            return value.strip()
        return value
    
    def _op_normalize(self, value: Any, params: Dict[str, Any]) -> Any:
        """Normalize string (lowercase and normalize whitespace)."""
        if isinstance(value, str):
            # Normalize multiple whitespace to single space
            normalized = re.sub(r'\s+', ' ', value.strip().lower())
            return normalized
        return value
    
    def _op_fill(self, value: Any, params: Dict[str, Any]) -> Any:
        """Fill value with a specified value."""
        fill_value = params.get("value")
        condition = params.get("condition")
        
        if condition == "null" and value is None:
            return fill_value
        elif condition == "empty" and (value is None or value == ""):
            return fill_value
        elif condition is None:
            return fill_value
        
        return value
    
    def _op_drop(self, value: Any, params: Dict[str, Any]) -> Any:
        """Drop a field (handled specially in clean method)."""
        return None
    
    def _op_transform(self, value: Any, params: Dict[str, Any]) -> Any:
        """Apply custom transformation."""
        transformer_name = params.get("transformer")
        if transformer_name and transformer_name in self._transformers:
            return self._transformers[transformer_name](value, params)
        return value
    
    def _op_uppercase(self, value: Any, params: Dict[str, Any]) -> Any:
        """Convert to uppercase."""
        if isinstance(value, str):
            return value.upper()
        return value
    
    def _op_lowercase(self, value: Any, params: Dict[str, Any]) -> Any:
        """Convert to lowercase."""
        if isinstance(value, str):
            return value.lower()
        return value
    
    def _op_strip(self, value: Any, params: Dict[str, Any]) -> Any:
        """Strip specified characters from string."""
        if isinstance(value, str):
            chars = params.get("chars")
            if chars:
                return value.strip(chars)
            return value.strip()
        return value
    
    def _op_replace(self, value: Any, params: Dict[str, Any]) -> Any:
        """Replace substring in string."""
        if isinstance(value, str):
            old = params.get("old", "")
            new = params.get("new", "")
            return value.replace(old, new)
        return value
    
    def _op_round(self, value: Any, params: Dict[str, Any]) -> Any:
        """Round numeric value."""
        if isinstance(value, (int, float)):
            decimals = params.get("decimals", 0)
            return round(value, decimals)
        return value
    
    def _op_floor(self, value: Any, params: Dict[str, Any]) -> Any:
        """Floor numeric value."""
        if isinstance(value, (int, float)):
            import math
            return math.floor(value)
        return value
    
    def _op_ceil(self, value: Any, params: Dict[str, Any]) -> Any:
        """Ceiling numeric value."""
        if isinstance(value, (int, float)):
            import math
            return math.ceil(value)
        return value
    
    def _op_fill_null(self, value: Any, params: Dict[str, Any]) -> Any:
        """Fill null values with default."""
        if value is None:
            return params.get("value", params.get("default"))
        return value
    
    def _op_drop_null(self, value: Any, params: Dict[str, Any]) -> Any:
        """Mark null values for dropping (handled specially)."""
        return value
    
    def _op_deduplicate(self, value: Any, params: Dict[str, Any]) -> Any:
        """Deduplicate (handled at batch level)."""
        return value
    
    def _op_split(self, value: Any, params: Dict[str, Any]) -> Any:
        """Split string into list."""
        if isinstance(value, str):
            delimiter = params.get("delimiter", ",")
            return value.split(delimiter)
        return value
    
    def _op_join(self, value: Any, params: Dict[str, Any]) -> Any:
        """Join list into string."""
        if isinstance(value, list):
            delimiter = params.get("delimiter", ",")
            return delimiter.join(str(v) for v in value)
        return value
    
    def _op_extract(self, value: Any, params: Dict[str, Any]) -> Any:
        """Extract substring using regex."""
        if isinstance(value, str):
            pattern = params.get("pattern")
            group = params.get("group", 0)
            if pattern:
                match = re.search(pattern, value)
                if match:
                    return match.group(group)
        return value
    
    def _op_default(self, value: Any, params: Dict[str, Any]) -> Any:
        """Set default value if current is null or empty."""
        default = params.get("value", params.get("default"))
        if value is None or value == "":
            return default
        return value


def create_cleaner(rules: List[Dict[str, Any]]) -> DataCleaner:
    """
    Factory function to create a data cleaner from rule configurations.
    
    Args:
        rules: List of rule configuration dictionaries
        
    Returns:
        Configured DataCleaner instance
    """
    cleaner = DataCleaner()
    
    for rule_config in rules:
        rule = CleaningRule(
            field=rule_config["field"],
            operation=CleaningOperation(rule_config["operation"]),
            params=rule_config.get("params", {}),
            priority=rule_config.get("priority", 100)
        )
        cleaner.add_rule(rule)
    
    return cleaner


def clean_nulls(data: Dict[str, Any], fill_value: Any = None) -> Dict[str, Any]:
    """
    Quick utility to fill null values in data.
    
    Args:
        data: Data dictionary
        fill_value: Value to use for nulls
        
    Returns:
        Cleaned data dictionary
    """
    cleaner = DataCleaner()
    for key in data.keys():
        cleaner.add_rule(CleaningRule(
            field=key,
            operation=CleaningOperation.FILL_NULL,
            params={"value": fill_value}
        ))
    
    result = cleaner.clean(data)
    return result.data


def deduplicate_records(data: List[Dict[str, Any]], 
                        key_fields: List[str]) -> List[Dict[str, Any]]:
    """
    Quick utility to deduplicate records.
    
    Args:
        data: List of records
        key_fields: Fields to use for deduplication
        
    Returns:
        Deduplicated list of records
    """
    cleaner = DataCleaner()
    for field in key_fields:
        cleaner.add_rule(CleaningRule(
            field=field,
            operation=CleaningOperation.DEDUPLICATE,
            priority=0  # Process deduplication first
        ))
    
    result = cleaner.clean(data)
    return result.data
