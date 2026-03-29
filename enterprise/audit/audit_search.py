# Audit Search - Week 49 Builder 1
# Audit log search and filtering engine

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import re


class SearchOperator(Enum):
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN_OR_EQUAL = "lte"
    IN = "in"
    NOT_IN = "not_in"
    REGEX = "regex"


class SortOrder(Enum):
    ASC = "asc"
    DESC = "desc"


@dataclass
class SearchCondition:
    field: str
    operator: SearchOperator
    value: Any


@dataclass
class SearchQuery:
    conditions: List[SearchCondition] = field(default_factory=list)
    sort_by: str = "timestamp"
    sort_order: SortOrder = SortOrder.DESC
    limit: int = 100
    offset: int = 0


@dataclass
class SearchResult:
    total: int = 0
    items: List[Any] = field(default_factory=list)
    page: int = 1
    page_size: int = 100
    has_more: bool = False


@dataclass
class SearchIndex:
    field: str
    values: Dict[str, List[str]] = field(default_factory=dict)  # value -> event_ids


class AuditSearchEngine:
    """Search and filter audit logs"""

    def __init__(self, audit_logger=None):
        self._audit_logger = audit_logger
        self._indexes: Dict[str, SearchIndex] = {}
        self._indexed_fields = [
            "tenant_id", "user_id", "event_type", "severity",
            "status", "resource_type", "resource_id", "action"
        ]
        self._query_cache: Dict[str, SearchResult] = {}
        self._metrics = {
            "total_searches": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }

    def set_audit_logger(self, logger) -> None:
        """Set the audit logger source"""
        self._audit_logger = logger

    def build_index(self) -> None:
        """Build search indexes from audit events"""
        if not self._audit_logger:
            return

        # Initialize indexes
        for field in self._indexed_fields:
            self._indexes[field] = SearchIndex(field=field)

        # Index all events
        for event in self._audit_logger._events:
            self._index_event(event)

    def _index_event(self, event: Any) -> None:
        """Index a single event"""
        for field in self._indexed_fields:
            if field in self._indexes:
                value = getattr(event, field, None)
                if value is not None:
                    value_str = str(value.value) if hasattr(value, 'value') else str(value)
                    if value_str not in self._indexes[field].values:
                        self._indexes[field].values[value_str] = []
                    self._indexes[field].values[value_str].append(event.id)

    def search(
        self,
        query: SearchQuery,
        events: Optional[List[Any]] = None
    ) -> SearchResult:
        """Execute a search query"""
        self._metrics["total_searches"] += 1

        # Use provided events or get from logger
        if events is None:
            if self._audit_logger:
                events = self._audit_logger._events.copy()
            else:
                events = []

        # Apply conditions
        filtered = self._apply_conditions(events, query.conditions)

        # Sort results
        filtered = self._apply_sort(filtered, query.sort_by, query.sort_order)

        # Calculate pagination
        total = len(filtered)
        page_size = query.limit
        page = (query.offset // page_size) + 1 if page_size > 0 else 1

        # Apply pagination
        start = query.offset
        end = start + query.limit
        paginated = filtered[start:end]

        return SearchResult(
            total=total,
            items=paginated,
            page=page,
            page_size=page_size,
            has_more=end < total
        )

    def _apply_conditions(
        self,
        events: List[Any],
        conditions: List[SearchCondition]
    ) -> List[Any]:
        """Apply filter conditions to events"""
        if not conditions:
            return events

        result = []
        for event in events:
            if self._matches_all_conditions(event, conditions):
                result.append(event)

        return result

    def _matches_all_conditions(
        self,
        event: Any,
        conditions: List[SearchCondition]
    ) -> bool:
        """Check if event matches all conditions"""
        for condition in conditions:
            if not self._matches_condition(event, condition):
                return False
        return True

    def _matches_condition(
        self,
        event: Any,
        condition: SearchCondition
    ) -> bool:
        """Check if event matches a single condition"""
        value = getattr(event, condition.field, None)

        # Handle enum values
        if hasattr(value, 'value'):
            value = value.value

        if value is None:
            return False

        value_str = str(value)
        condition_value = condition.value

        if condition.operator == SearchOperator.EQUALS:
            return value_str == str(condition_value)

        elif condition.operator == SearchOperator.NOT_EQUALS:
            return value_str != str(condition_value)

        elif condition.operator == SearchOperator.CONTAINS:
            return str(condition_value).lower() in value_str.lower()

        elif condition.operator == SearchOperator.STARTS_WITH:
            return value_str.lower().startswith(str(condition_value).lower())

        elif condition.operator == SearchOperator.ENDS_WITH:
            return value_str.lower().endswith(str(condition_value).lower())

        elif condition.operator == SearchOperator.GREATER_THAN:
            return self._compare_values(value, condition_value) > 0

        elif condition.operator == SearchOperator.LESS_THAN:
            return self._compare_values(value, condition_value) < 0

        elif condition.operator == SearchOperator.GREATER_THAN_OR_EQUAL:
            return self._compare_values(value, condition_value) >= 0

        elif condition.operator == SearchOperator.LESS_THAN_OR_EQUAL:
            return self._compare_values(value, condition_value) <= 0

        elif condition.operator == SearchOperator.IN:
            return value_str in [str(v) for v in condition_value]

        elif condition.operator == SearchOperator.NOT_IN:
            return value_str not in [str(v) for v in condition_value]

        elif condition.operator == SearchOperator.REGEX:
            return bool(re.search(str(condition_value), value_str))

        return False

    def _compare_values(self, a: Any, b: Any) -> int:
        """Compare two values"""
        try:
            if isinstance(a, datetime) and isinstance(b, (str, datetime)):
                if isinstance(b, str):
                    b = datetime.fromisoformat(b)
                return (a - b).total_seconds()
            return (a > b) - (a < b)
        except (TypeError, ValueError):
            return (str(a) > str(b)) - (str(a) < str(b))

    def _apply_sort(
        self,
        events: List[Any],
        sort_by: str,
        sort_order: SortOrder
    ) -> List[Any]:
        """Sort events by field"""
        def get_sort_key(event):
            value = getattr(event, sort_by, None)
            if hasattr(value, 'value'):
                value = value.value
            if isinstance(value, datetime):
                return value.timestamp()
            return value or ""

        reverse = sort_order == SortOrder.DESC
        return sorted(events, key=get_sort_key, reverse=reverse)

    def quick_search(
        self,
        tenant_id: str,
        text: str,
        limit: int = 50
    ) -> List[Any]:
        """Quick text search across multiple fields"""
        if not self._audit_logger:
            return []

        events = [e for e in self._audit_logger._events if e.tenant_id == tenant_id]
        text_lower = text.lower()

        results = []
        for event in events:
            # Search in multiple text fields
            searchable = " ".join([
                str(event.description or ""),
                str(event.action or ""),
                str(event.resource_type or ""),
                str(event.resource_id or ""),
                str(event.user_id or "")
            ]).lower()

            if text_lower in searchable:
                results.append(event)

        return results[:limit]

    def search_by_time_range(
        self,
        tenant_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 100
    ) -> List[Any]:
        """Search events within a time range"""
        if not self._audit_logger:
            return []

        events = [
            e for e in self._audit_logger._events
            if e.tenant_id == tenant_id
            and start_time <= e.timestamp <= end_time
        ]

        return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]

    def search_by_user(
        self,
        tenant_id: str,
        user_id: str,
        event_types: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[Any]:
        """Search events by user"""
        if not self._audit_logger:
            return []

        events = [
            e for e in self._audit_logger._events
            if e.tenant_id == tenant_id
            and e.user_id == user_id
        ]

        if event_types:
            events = [
                e for e in events
                if e.event_type.value in event_types
            ]

        return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]

    def search_by_resource(
        self,
        tenant_id: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Any]:
        """Search events by resource"""
        if not self._audit_logger:
            return []

        events = [
            e for e in self._audit_logger._events
            if e.tenant_id == tenant_id
            and e.resource_type == resource_type
        ]

        if resource_id:
            events = [e for e in events if e.resource_id == resource_id]

        return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_index_stats(self) -> Dict[str, Any]:
        """Get search index statistics"""
        stats = {}
        for field, index in self._indexes.items():
            stats[field] = {
                "unique_values": len(index.values),
                "total_entries": sum(len(ids) for ids in index.values.values())
            }
        return stats

    def get_metrics(self) -> Dict[str, Any]:
        """Get search engine metrics"""
        return {
            **self._metrics,
            "index_count": len(self._indexes),
            "cache_size": len(self._query_cache)
        }

    def clear_cache(self) -> int:
        """Clear query cache"""
        count = len(self._query_cache)
        self._query_cache.clear()
        return count

    def rebuild_indexes(self) -> None:
        """Rebuild all search indexes"""
        self._indexes.clear()
        self.build_index()
