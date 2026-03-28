"""
Response Optimizer for PARWA Performance Optimization.

Week 26 - Builder 4: API Response Caching + Compression
Target: JSON minification, null field stripping, response size logging

Features:
- JSON response minification
- Null field stripping
- Response size logging
- Large response pagination
- Field selection support
"""

import json
import logging
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)


@dataclass
class OptimizationStats:
    """Statistics for response optimization."""
    original_size: int = 0
    optimized_size: int = 0
    null_fields_removed: int = 0
    whitespace_removed: int = 0

    @property
    def reduction_percent(self) -> float:
        """Calculate size reduction percentage."""
        if self.original_size == 0:
            return 0.0
        return ((self.original_size - self.optimized_size) / self.original_size) * 100


class ResponseOptimizer:
    """
    Optimizes API responses for size and performance.

    Features:
    - JSON minification
    - Null field stripping
    - Field selection
    - Response pagination for large data
    - Size logging
    """

    # Fields commonly null that can be stripped
    NULLABLE_FIELDS: Set[str] = {
        "middle_name",
        "notes",
        "metadata",
        "extra",
        "custom_fields",
        "preferences",
        "settings",
        "description",
        "comment",
        "tags",
        "attachments",
    }

    # Maximum response size before pagination (in bytes)
    MAX_RESPONSE_SIZE = 1024 * 1024  # 1MB

    def __init__(
        self,
        strip_nulls: bool = True,
        minify_json: bool = True,
        log_size: bool = True,
        max_response_size: int = MAX_RESPONSE_SIZE
    ):
        """
        Initialize response optimizer.

        Args:
            strip_nulls: Whether to strip null fields.
            minify_json: Whether to minify JSON output.
            log_size: Whether to log response sizes.
            max_response_size: Maximum response size before pagination.
        """
        self.strip_nulls = strip_nulls
        self.minify_json = minify_json
        self.log_size = log_size
        self.max_response_size = max_response_size

    def optimize(
        self,
        data: Any,
        fields: Optional[List[str]] = None,
        exclude_fields: Optional[List[str]] = None
    ) -> tuple[str, OptimizationStats]:
        """
        Optimize response data.

        Args:
            data: Response data to optimize.
            fields: Specific fields to include (field selection).
            exclude_fields: Fields to exclude.

        Returns:
            Tuple of (optimized JSON string, optimization stats).
        """
        stats = OptimizationStats()
        original_json = json.dumps(data, default=str)
        stats.original_size = len(original_json)

        # Apply field selection
        if fields:
            data = self._select_fields(data, fields)

        # Apply field exclusion
        if exclude_fields:
            data = self._exclude_fields(data, exclude_fields)

        # Strip null fields
        if self.strip_nulls:
            data, null_count = self._strip_nulls(data)
            stats.null_fields_removed = null_count

        # Minify JSON
        if self.minify_json:
            optimized_json = json.dumps(data, separators=(",", ":"), default=str)
            stats.whitespace_removed = len(original_json) - len(optimized_json)
        else:
            optimized_json = json.dumps(data, default=str)

        stats.optimized_size = len(optimized_json)

        # Log size
        if self.log_size:
            logger.debug(
                f"Response optimized: {stats.original_size} -> {stats.optimized_size} bytes "
                f"({stats.reduction_percent:.1f}% reduction)"
            )

        return optimized_json, stats

    def _select_fields(self, data: Any, fields: List[str]) -> Any:
        """
        Select specific fields from data.

        Args:
            data: Response data.
            fields: Fields to include.

        Returns:
            Data with only selected fields.
        """
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if k in fields}
        elif isinstance(data, list):
            return [self._select_fields(item, fields) for item in data]
        return data

    def _exclude_fields(self, data: Any, exclude_fields: List[str]) -> Any:
        """
        Exclude specific fields from data.

        Args:
            data: Response data.
            exclude_fields: Fields to exclude.

        Returns:
            Data with excluded fields removed.
        """
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if k not in exclude_fields}
        elif isinstance(data, list):
            return [self._exclude_fields(item, exclude_fields) for item in data]
        return data

    def _strip_nulls(self, data: Any) -> tuple[Any, int]:
        """
        Strip null fields from data.

        Args:
            data: Response data.

        Returns:
            Tuple of (cleaned data, count of removed nulls).
        """
        null_count = 0

        def clean(obj: Any) -> Any:
            nonlocal null_count

            if isinstance(obj, dict):
                cleaned = {}
                for k, v in obj.items():
                    if v is None:
                        # Only strip if in nullable fields set or nested object
                        if k in self.NULLABLE_FIELDS or k.startswith("_"):
                            null_count += 1
                            continue
                    cleaned[k] = clean(v)
                return cleaned
            elif isinstance(obj, list):
                return [clean(item) for item in obj]
            return obj

        return clean(data), null_count

    def should_paginate(self, data: Any) -> bool:
        """
        Check if response should be paginated.

        Args:
            data: Response data.

        Returns:
            True if response exceeds size limit.
        """
        estimated_size = len(json.dumps(data, default=str))
        return estimated_size > self.max_response_size

    def paginate(
        self,
        data: List[Any],
        page: int = 1,
        per_page: int = 100
    ) -> Dict[str, Any]:
        """
        Paginate large list responses.

        Args:
            data: List data to paginate.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Paginated response dict.
        """
        total = len(data)
        total_pages = (total + per_page - 1) // per_page

        start = (page - 1) * per_page
        end = start + per_page

        return {
            "data": data[start:end],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            }
        }

    def transform_for_client(
        self,
        data: Any,
        client_id: str,
        variant: str = "default"
    ) -> Any:
        """
        Transform response based on client variant.

        Args:
            data: Response data.
            client_id: Client identifier.
            variant: Client variant type.

        Returns:
            Transformed data.
        """
        # Mini variant: strip all optional fields
        if variant == "mini":
            essential_fields = {"id", "status", "created_at", "updated_at"}
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if k in essential_fields}
            elif isinstance(data, list):
                return [
                    {k: v for k, v in item.items() if k in essential_fields}
                    for item in data
                ]

        return data


# Global optimizer instance
_optimizer: Optional[ResponseOptimizer] = None


def get_response_optimizer() -> ResponseOptimizer:
    """
    Get the global response optimizer instance.

    Returns:
        ResponseOptimizer instance.
    """
    global _optimizer
    if _optimizer is None:
        _optimizer = ResponseOptimizer()
    return _optimizer


__all__ = [
    "OptimizationStats",
    "ResponseOptimizer",
    "get_response_optimizer",
]
