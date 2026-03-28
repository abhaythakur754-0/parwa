"""Transformer - Request/Response transformation for API Gateway"""
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import logging
import json
import re
import copy

logger = logging.getLogger(__name__)


class TransformType(str, Enum):
    """Types of transformations"""
    HEADER_ADD = "header_add"
    HEADER_REMOVE = "header_remove"
    HEADER_RENAME = "header_rename"
    BODY_TRANSFORM = "body_transform"
    QUERY_ADD = "query_add"
    QUERY_REMOVE = "query_remove"
    PATH_REWRITE = "path_rewrite"


@dataclass
class TransformRule:
    """A single transformation rule"""
    name: str
    transform_type: TransformType
    source: Optional[str] = None  # Source key/path
    target: Optional[str] = None  # Target key/path
    value: Optional[Any] = None   # Static value for add operations
    condition: Optional[Callable[[Dict], bool]] = None  # Optional condition
    transform_func: Optional[Callable[[Any], Any]] = None  # Optional transform function
    enabled: bool = True
    priority: int = 0  # Higher priority transforms run first


@dataclass
class TransformContext:
    """Context for transformation"""
    tenant_id: Optional[str] = None
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransformResult:
    """Result of a transformation"""
    success: bool
    data: Dict[str, Any]
    transforms_applied: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class Transformer:
    """
    Request/Response Transformer for API Gateway.

    Features:
    - Header modification (add, remove, rename)
    - Body transformation with custom functions
    - Query parameter manipulation
    - Path rewriting
    - Conditional transformations
    - Priority-based execution
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._request_transforms: List[TransformRule] = []
        self._response_transforms: List[TransformRule] = []
        self._metrics = {
            "total_transforms": 0,
            "successful_transforms": 0,
            "failed_transforms": 0
        }

    def add_transform(
        self,
        rule: TransformRule,
        phase: str = "request"
    ) -> None:
        """
        Add a transformation rule.

        Args:
            rule: The transformation rule to add
            phase: 'request' or 'response'
        """
        if phase == "request":
            self._request_transforms.append(rule)
            self._request_transforms.sort(key=lambda x: -x.priority)
        else:
            self._response_transforms.append(rule)
            self._response_transforms.sort(key=lambda x: -x.priority)

        logger.info(f"Added {phase} transform: {rule.name} ({rule.transform_type.value})")

    def transform_request(
        self,
        headers: Dict[str, str],
        body: Optional[Any] = None,
        query_params: Optional[Dict[str, str]] = None,
        path: Optional[str] = None,
        context: Optional[TransformContext] = None
    ) -> TransformResult:
        """
        Transform an incoming request.

        Args:
            headers: Request headers
            body: Request body (dict or any)
            query_params: Query parameters
            path: Request path
            context: Transformation context

        Returns:
            TransformResult with transformed data
        """
        self._metrics["total_transforms"] += 1
        result = TransformResult(
            success=True,
            data={
                "headers": dict(headers),
                "body": copy.deepcopy(body) if body else None,
                "query_params": dict(query_params) if query_params else {},
                "path": path
            },
            transforms_applied=[],
            errors=[]
        )

        try:
            context = context or TransformContext()

            for rule in self._request_transforms:
                if not rule.enabled:
                    continue

                try:
                    applied = self._apply_transform(rule, result.data, context)
                    if applied:
                        result.transforms_applied.append(rule.name)
                except Exception as e:
                    result.errors.append(f"Transform '{rule.name}' failed: {str(e)}")
                    logger.error(f"Transform '{rule.name}' failed: {e}")

            self._metrics["successful_transforms"] += 1

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            self._metrics["failed_transforms"] += 1
            logger.error(f"Request transformation failed: {e}")

        return result

    def transform_response(
        self,
        headers: Dict[str, str],
        body: Optional[Any] = None,
        context: Optional[TransformContext] = None
    ) -> TransformResult:
        """
        Transform an outgoing response.

        Args:
            headers: Response headers
            body: Response body
            context: Transformation context

        Returns:
            TransformResult with transformed data
        """
        self._metrics["total_transforms"] += 1
        result = TransformResult(
            success=True,
            data={
                "headers": dict(headers),
                "body": copy.deepcopy(body) if body else None
            },
            transforms_applied=[],
            errors=[]
        )

        try:
            context = context or TransformContext()

            for rule in self._response_transforms:
                if not rule.enabled:
                    continue

                try:
                    applied = self._apply_transform(rule, result.data, context)
                    if applied:
                        result.transforms_applied.append(rule.name)
                except Exception as e:
                    result.errors.append(f"Transform '{rule.name}' failed: {str(e)}")
                    logger.error(f"Transform '{rule.name}' failed: {e}")

            self._metrics["successful_transforms"] += 1

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            self._metrics["failed_transforms"] += 1
            logger.error(f"Response transformation failed: {e}")

        return result

    def _apply_transform(
        self,
        rule: TransformRule,
        data: Dict[str, Any],
        context: TransformContext
    ) -> bool:
        """Apply a single transformation rule"""
        # Check condition if present
        if rule.condition and not rule.condition(data):
            return False

        if rule.transform_type == TransformType.HEADER_ADD:
            return self._apply_header_add(rule, data)

        elif rule.transform_type == TransformType.HEADER_REMOVE:
            return self._apply_header_remove(rule, data)

        elif rule.transform_type == TransformType.HEADER_RENAME:
            return self._apply_header_rename(rule, data)

        elif rule.transform_type == TransformType.BODY_TRANSFORM:
            return self._apply_body_transform(rule, data)

        elif rule.transform_type == TransformType.QUERY_ADD:
            return self._apply_query_add(rule, data)

        elif rule.transform_type == TransformType.QUERY_REMOVE:
            return self._apply_query_remove(rule, data)

        elif rule.transform_type == TransformType.PATH_REWRITE:
            return self._apply_path_rewrite(rule, data)

        return False

    def _apply_header_add(self, rule: TransformRule, data: Dict) -> bool:
        """Add a header"""
        if rule.target and rule.value is not None:
            data["headers"][rule.target] = rule.value
            return True
        return False

    def _apply_header_remove(self, rule: TransformRule, data: Dict) -> bool:
        """Remove a header"""
        if rule.source and rule.source in data["headers"]:
            del data["headers"][rule.source]
            return True
        return False

    def _apply_header_rename(self, rule: TransformRule, data: Dict) -> bool:
        """Rename a header"""
        if rule.source and rule.target and rule.source in data["headers"]:
            data["headers"][rule.target] = data["headers"].pop(rule.source)
            return True
        return False

    def _apply_body_transform(self, rule: TransformRule, data: Dict) -> bool:
        """Transform body content"""
        body = data.get("body")
        if body is None:
            return False

        if rule.transform_func:
            data["body"] = rule.transform_func(body)
            return True

        if rule.source and rule.target and isinstance(body, dict):
            if rule.source in body:
                value = body[rule.source]
                if rule.transform_func:
                    value = rule.transform_func(value)
                body[rule.target] = value
                if rule.source != rule.target:
                    del body[rule.source]
                return True

        return False

    def _apply_query_add(self, rule: TransformRule, data: Dict) -> bool:
        """Add a query parameter"""
        if rule.target and rule.value is not None:
            data["query_params"][rule.target] = rule.value
            return True
        return False

    def _apply_query_remove(self, rule: TransformRule, data: Dict) -> bool:
        """Remove a query parameter"""
        if rule.source and rule.source in data.get("query_params", {}):
            del data["query_params"][rule.source]
            return True
        return False

    def _apply_path_rewrite(self, rule: TransformRule, data: Dict) -> bool:
        """Rewrite the request path"""
        path = data.get("path")
        if path and rule.source and rule.target:
            new_path = re.sub(rule.source, rule.target, path)
            data["path"] = new_path
            return path != new_path
        return False

    def remove_transform(self, name: str, phase: str = "request") -> bool:
        """Remove a transformation rule by name"""
        transforms = self._request_transforms if phase == "request" else self._response_transforms
        for i, rule in enumerate(transforms):
            if rule.name == name:
                transforms.pop(i)
                logger.info(f"Removed {phase} transform: {name}")
                return True
        return False

    def enable_transform(self, name: str, phase: str = "request") -> bool:
        """Enable a transformation rule"""
        transforms = self._request_transforms if phase == "request" else self._response_transforms
        for rule in transforms:
            if rule.name == name:
                rule.enabled = True
                return True
        return False

    def disable_transform(self, name: str, phase: str = "request") -> bool:
        """Disable a transformation rule"""
        transforms = self._request_transforms if phase == "request" else self._response_transforms
        for rule in transforms:
            if rule.name == name:
                rule.enabled = False
                return True
        return False

    def get_transform(self, name: str, phase: str = "request") -> Optional[TransformRule]:
        """Get a transformation rule by name"""
        transforms = self._request_transforms if phase == "request" else self._response_transforms
        for rule in transforms:
            if rule.name == name:
                return rule
        return None

    def get_all_transforms(self, phase: str = "request") -> List[TransformRule]:
        """Get all transformation rules for a phase"""
        return list(self._request_transforms if phase == "request" else self._response_transforms)

    def get_metrics(self) -> Dict[str, Any]:
        """Get transformer metrics"""
        return {
            **self._metrics,
            "request_transforms": len(self._request_transforms),
            "response_transforms": len(self._response_transforms),
            "active_request_transforms": sum(1 for t in self._request_transforms if t.enabled),
            "active_response_transforms": sum(1 for t in self._response_transforms if t.enabled),
            "success_rate": (
                self._metrics["successful_transforms"] / self._metrics["total_transforms"] * 100
                if self._metrics["total_transforms"] > 0 else 100
            )
        }

    def clear_transforms(self, phase: Optional[str] = None) -> None:
        """Clear all transforms (optionally for specific phase)"""
        if phase == "request":
            self._request_transforms.clear()
        elif phase == "response":
            self._response_transforms.clear()
        else:
            self._request_transforms.clear()
            self._response_transforms.clear()
        logger.info(f"Cleared transforms for phase: {phase or 'all'}")


# Convenience functions for common transformations
def create_header_add_rule(
    name: str,
    header_name: str,
    header_value: str,
    priority: int = 0
) -> TransformRule:
    """Create a header addition rule"""
    return TransformRule(
        name=name,
        transform_type=TransformType.HEADER_ADD,
        target=header_name,
        value=header_value,
        priority=priority
    )


def create_header_remove_rule(
    name: str,
    header_name: str,
    priority: int = 0
) -> TransformRule:
    """Create a header removal rule"""
    return TransformRule(
        name=name,
        transform_type=TransformType.HEADER_REMOVE,
        source=header_name,
        priority=priority
    )


def create_body_transform_rule(
    name: str,
    transform_func: Callable[[Any], Any],
    priority: int = 0
) -> TransformRule:
    """Create a body transformation rule"""
    return TransformRule(
        name=name,
        transform_type=TransformType.BODY_TRANSFORM,
        transform_func=transform_func,
        priority=priority
    )
