"""
API Gateway Core

Core gateway functionality including request handling,
routing, and middleware management.
"""

from typing import Dict, List, Optional, Any, Callable, Awaitable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import asyncio
import logging
import time
import uuid

logger = logging.getLogger(__name__)


class GatewayStatus(str, Enum):
    """Gateway operational status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class RequestPhase(str, Enum):
    """Phases of request processing"""
    RECEIVED = "received"
    VALIDATED = "validated"
    ROUTED = "routed"
    FORWARDED = "forwarded"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class GatewayRequest:
    """Represents an incoming API request"""
    request_id: str
    method: str
    path: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    body: Optional[Any] = None
    tenant_id: Optional[str] = None
    api_key: Optional[str] = None
    source_ip: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GatewayResponse:
    """Represents an API response"""
    request_id: str
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Any] = None
    latency_ms: float = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MiddlewareResult:
    """Result from middleware processing"""
    proceed: bool = True
    response: Optional[GatewayResponse] = None
    modified_request: Optional[GatewayRequest] = None
    error: Optional[str] = None


class APIGateway:
    """
    Enterprise API Gateway.

    Features:
    - Request handling and routing
    - Middleware pipeline
    - Health monitoring
    - Request logging
    """

    def __init__(
        self,
        name: str = "api-gateway",
        max_request_size: int = 10 * 1024 * 1024,  # 10MB
        request_timeout: int = 30
    ):
        self.name = name
        self.max_request_size = max_request_size
        self.request_timeout = request_timeout

        # Middleware pipeline
        self._middleware: List[Callable] = []
        self._pre_routing_middleware: List[Callable] = []
        self._post_routing_middleware: List[Callable] = []

        # Request tracking
        self._active_requests: Dict[str, GatewayRequest] = {}

        # Metrics
        self._metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_latency_ms": 0,
            "requests_by_method": {},
            "requests_by_path": {}
        }

        # Status
        self._status = GatewayStatus.HEALTHY

    def add_middleware(
        self,
        middleware: Callable,
        phase: str = "pre_routing"
    ) -> None:
        """Add middleware to the pipeline"""
        if phase == "pre_routing":
            self._pre_routing_middleware.append(middleware)
        elif phase == "post_routing":
            self._post_routing_middleware.append(middleware)
        else:
            self._middleware.append(middleware)

        logger.info(f"Added middleware at {phase} phase")

    async def handle_request(
        self,
        method: str,
        path: str,
        headers: Dict[str, str],
        query_params: Optional[Dict[str, str]] = None,
        body: Optional[Any] = None,
        source_ip: Optional[str] = None
    ) -> GatewayResponse:
        """
        Handle an incoming API request.

        Args:
            method: HTTP method
            path: Request path
            headers: Request headers
            query_params: Query parameters
            body: Request body
            source_ip: Client IP address

        Returns:
            GatewayResponse
        """
        start_time = time.time()
        request_id = str(uuid.uuid4())

        # Create request object
        request = GatewayRequest(
            request_id=request_id,
            method=method.upper(),
            path=path,
            headers=headers,
            query_params=query_params or {},
            body=body,
            source_ip=source_ip
        )

        # Track active request
        self._active_requests[request_id] = request
        self._metrics["total_requests"] += 1

        # Update method metrics
        self._metrics["requests_by_method"][method] = \
            self._metrics["requests_by_method"].get(method, 0) + 1

        try:
            # Pre-routing middleware
            for middleware in self._pre_routing_middleware:
                result = await self._run_middleware(middleware, request)
                if not result.proceed:
                    return result.response or self._error_response(
                        request_id, 403, "Request blocked by middleware"
                    )
                if result.modified_request:
                    request = result.modified_request

            # General middleware
            for middleware in self._middleware:
                result = await self._run_middleware(middleware, request)
                if not result.proceed:
                    return result.response or self._error_response(
                        request_id, 403, "Request blocked by middleware"
                    )

            # Route request (placeholder - would connect to router)
            response = await self._route_request(request)

            # Post-routing middleware
            for middleware in self._post_routing_middleware:
                await self._run_middleware(middleware, request, response)

            # Update metrics
            self._metrics["successful_requests"] += 1

            latency = (time.time() - start_time) * 1000
            response.latency_ms = latency
            self._metrics["total_latency_ms"] += latency

            return response

        except Exception as e:
            self._metrics["failed_requests"] += 1
            logger.error(f"Request {request_id} failed: {e}")

            return self._error_response(request_id, 500, str(e))

        finally:
            # Remove from active requests
            self._active_requests.pop(request_id, None)

    async def _run_middleware(
        self,
        middleware: Callable,
        request: GatewayRequest,
        response: Optional[GatewayResponse] = None
    ) -> MiddlewareResult:
        """Run a middleware function"""
        try:
            if asyncio.iscoroutinefunction(middleware):
                result = await middleware(request, response)
            else:
                result = middleware(request, response)

            if isinstance(result, MiddlewareResult):
                return result

            # Default to proceed if middleware returns truthy
            return MiddlewareResult(proceed=bool(result))

        except Exception as e:
            logger.error(f"Middleware error: {e}")
            return MiddlewareResult(proceed=False, error=str(e))

    async def _route_request(self, request: GatewayRequest) -> GatewayResponse:
        """Route request to appropriate service (placeholder)"""
        # This would normally route to actual services
        return GatewayResponse(
            request_id=request.request_id,
            status_code=200,
            body={"message": "Request processed", "request_id": request.request_id}
        )

    def _error_response(
        self,
        request_id: str,
        status_code: int,
        message: str
    ) -> GatewayResponse:
        """Create an error response"""
        return GatewayResponse(
            request_id=request_id,
            status_code=status_code,
            body={"error": message, "request_id": request_id}
        )

    def get_active_requests(self) -> List[GatewayRequest]:
        """Get all active requests"""
        return list(self._active_requests.values())

    def get_metrics(self) -> Dict[str, Any]:
        """Get gateway metrics"""
        total = self._metrics["total_requests"]
        avg_latency = (
            self._metrics["total_latency_ms"] / total
            if total > 0 else 0
        )

        return {
            **self._metrics,
            "average_latency_ms": round(avg_latency, 2),
            "active_requests": len(self._active_requests),
            "status": self._status.value
        }

    def get_health(self) -> Dict[str, Any]:
        """Get gateway health status"""
        return {
            "status": self._status.value,
            "name": self.name,
            "active_requests": len(self._active_requests),
            "total_requests": self._metrics["total_requests"],
            "success_rate": (
                self._metrics["successful_requests"] /
                self._metrics["total_requests"] * 100
                if self._metrics["total_requests"] > 0 else 100
            )
        }

    def set_status(self, status: GatewayStatus) -> None:
        """Set gateway status"""
        self._status = status
        logger.info(f"Gateway status changed to: {status.value}")
