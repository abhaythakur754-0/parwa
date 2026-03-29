"""
Request Router

Routes incoming requests to appropriate backend services.
"""

from typing import Dict, List, Optional, Any, Pattern
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import re
import logging

logger = logging.getLogger(__name__)


class RoutingStrategy(str, Enum):
    """Routing strategies"""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED = "weighted"
    HASH = "hash"
    RANDOM = "random"


@dataclass
class Route:
    """Represents a routing rule"""
    route_id: str
    path_pattern: str
    service_name: str
    methods: List[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    strip_prefix: bool = True
    add_prefix: str = ""
    priority: int = 0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches(self, path: str, method: str) -> bool:
        """Check if route matches path and method"""
        if not self.enabled:
            return False

        if method.upper() not in [m.upper() for m in self.methods]:
            return False

        # Check path pattern
        pattern = self.path_pattern.replace("{", r"(?P<").replace("}", r">[^/]+)")
        pattern = f"^{pattern}(/.*)?$"

        return bool(re.match(pattern, path))


@dataclass
class RoutingResult:
    """Result of routing decision"""
    route_id: str
    service_name: str
    target_path: str
    matched: bool = True
    params: Dict[str, str] = field(default_factory=dict)


class RequestRouter:
    """
    Routes requests to backend services.

    Features:
    - Pattern-based routing
    - Path transformation
    - Load balancing strategies
    - Route priorities
    """

    def __init__(self, strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN):
        self.strategy = strategy

        # Route storage
        self._routes: Dict[str, Route] = {}
        self._routes_by_service: Dict[str, List[str]] = {}

        # Load balancing state
        self._round_robin_index: Dict[str, int] = {}
        self._connection_counts: Dict[str, int] = {}

        # Metrics
        self._metrics = {
            "total_routed": 0,
            "routes_matched": {},
            "routing_errors": 0
        }

    def add_route(
        self,
        route_id: str,
        path_pattern: str,
        service_name: str,
        methods: Optional[List[str]] = None,
        strip_prefix: bool = True,
        add_prefix: str = "",
        priority: int = 0
    ) -> Route:
        """Add a routing rule"""
        route = Route(
            route_id=route_id,
            path_pattern=path_pattern,
            service_name=service_name,
            methods=methods or ["GET", "POST", "PUT", "DELETE"],
            strip_prefix=strip_prefix,
            add_prefix=add_prefix,
            priority=priority
        )

        self._routes[route_id] = route

        # Index by service
        if service_name not in self._routes_by_service:
            self._routes_by_service[service_name] = []
        self._routes_by_service[service_name].append(route_id)

        logger.info(f"Added route {route_id}: {path_pattern} -> {service_name}")
        return route

    def route(
        self,
        path: str,
        method: str
    ) -> RoutingResult:
        """
        Route a request to a service.

        Args:
            path: Request path
            method: HTTP method

        Returns:
            RoutingResult with target service and path
        """
        self._metrics["total_routed"] += 1

        # Find matching routes (sorted by priority)
        matching_routes = sorted(
            [r for r in self._routes.values() if r.matches(path, method)],
            key=lambda r: r.priority,
            reverse=True
        )

        if not matching_routes:
            self._metrics["routing_errors"] += 1
            return RoutingResult(
                route_id="",
                service_name="",
                target_path=path,
                matched=False
            )

        # Take highest priority match
        route = matching_routes[0]

        # Extract path parameters
        params = self._extract_params(route, path)

        # Transform path
        target_path = self._transform_path(route, path)

        # Update metrics
        self._metrics["routes_matched"][route.route_id] = \
            self._metrics["routes_matched"].get(route.route_id, 0) + 1

        return RoutingResult(
            route_id=route.route_id,
            service_name=route.service_name,
            target_path=target_path,
            params=params
        )

    def _extract_params(self, route: Route, path: str) -> Dict[str, str]:
        """Extract path parameters"""
        params = {}

        # Build regex pattern with named groups
        pattern = route.path_pattern
        param_names = re.findall(r"\{(\w+)\}", pattern)

        for param in param_names:
            pattern = pattern.replace(f"{{{param}}}", f"(?P<{param}>[^/]+)")

        pattern = f"^{pattern}$"
        match = re.match(pattern, path)

        if match:
            params = match.groupdict()

        return params

    def _transform_path(self, route: Route, path: str) -> str:
        """Transform path based on route rules"""
        target_path = path

        # Strip prefix
        if route.strip_prefix:
            prefix = route.path_pattern.split("{")[0].rstrip("/")
            if path.startswith(prefix):
                target_path = path[len(prefix):]

        # Add new prefix
        if route.add_prefix:
            target_path = route.add_prefix + target_path

        # Ensure path starts with /
        if not target_path.startswith("/"):
            target_path = "/" + target_path

        return target_path

    def get_route(self, route_id: str) -> Optional[Route]:
        """Get a route by ID"""
        return self._routes.get(route_id)

    def get_routes_for_service(self, service_name: str) -> List[Route]:
        """Get all routes for a service"""
        route_ids = self._routes_by_service.get(service_name, [])
        return [self._routes[rid] for rid in route_ids if rid in self._routes]

    def remove_route(self, route_id: str) -> bool:
        """Remove a route"""
        route = self._routes.get(route_id)
        if not route:
            return False

        del self._routes[route_id]

        # Remove from service index
        if route.service_name in self._routes_by_service:
            self._routes_by_service[route.service_name] = [
                rid for rid in self._routes_by_service[route.service_name]
                if rid != route_id
            ]

        return True

    def enable_route(self, route_id: str) -> bool:
        """Enable a route"""
        route = self._routes.get(route_id)
        if route:
            route.enabled = True
            return True
        return False

    def disable_route(self, route_id: str) -> bool:
        """Disable a route"""
        route = self._routes.get(route_id)
        if route:
            route.enabled = False
            return True
        return False

    def get_all_routes(self) -> List[Route]:
        """Get all routes"""
        return list(self._routes.values())

    def get_metrics(self) -> Dict[str, Any]:
        """Get routing metrics"""
        return {
            **self._metrics,
            "total_routes": len(self._routes),
            "routes_by_service": {
                service: len(routes)
                for service, routes in self._routes_by_service.items()
            }
        }

    def clear_routes(self) -> int:
        """Clear all routes"""
        count = len(self._routes)
        self._routes.clear()
        self._routes_by_service.clear()
        return count
