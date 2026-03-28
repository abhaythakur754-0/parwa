"""
Tests for API Gateway Core
"""

import pytest
from datetime import datetime
from enterprise.api_gateway.gateway_core import (
    APIGateway, GatewayStatus, GatewayRequest, GatewayResponse, MiddlewareResult
)
from enterprise.api_gateway.request_router import (
    RequestRouter, RoutingStrategy, Route, RoutingResult
)
from enterprise.api_gateway.service_registry import (
    ServiceRegistry, ServiceStatus, ServiceInstance, ServiceDefinition
)


class TestAPIGateway:
    """Tests for APIGateway"""

    @pytest.fixture
    def gateway(self):
        return APIGateway(name="test-gateway")

    @pytest.mark.asyncio
    async def test_handle_request(self, gateway):
        response = await gateway.handle_request(
            method="GET",
            path="/api/test",
            headers={}
        )
        assert response.status_code == 200
        assert response.request_id is not None

    @pytest.mark.asyncio
    async def test_handle_post_request(self, gateway):
        response = await gateway.handle_request(
            method="POST",
            path="/api/users",
            headers={"Content-Type": "application/json"},
            body={"name": "test"}
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_middleware_blocks_request(self, gateway):
        async def blocking_middleware(request, response):
            return MiddlewareResult(proceed=False, response=GatewayResponse(
                request_id=request.request_id,
                status_code=403,
                body={"error": "Blocked"}
            ))

        gateway.add_middleware(blocking_middleware, "pre_routing")
        response = await gateway.handle_request("GET", "/api/test", {})
        assert response.status_code == 403

    def test_get_metrics(self, gateway):
        metrics = gateway.get_metrics()
        assert "total_requests" in metrics
        assert "status" in metrics

    def test_get_health(self, gateway):
        health = gateway.get_health()
        assert health["status"] == GatewayStatus.HEALTHY.value

    def test_set_status(self, gateway):
        gateway.set_status(GatewayStatus.DEGRADED)
        assert gateway._status == GatewayStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_multiple_requests(self, gateway):
        for i in range(5):
            response = await gateway.handle_request("GET", f"/api/test/{i}", {})
            assert response.status_code == 200

        metrics = gateway.get_metrics()
        assert metrics["total_requests"] == 5


class TestRequestRouter:
    """Tests for RequestRouter"""

    @pytest.fixture
    def router(self):
        return RequestRouter()

    def test_add_route(self, router):
        route = router.add_route(
            route_id="users_route",
            path_pattern="/api/users",
            service_name="user-service"
        )
        assert route.route_id == "users_route"

    def test_route_match(self, router):
        router.add_route("users", "/api/users", "user-service")
        result = router.route("/api/users", "GET")
        assert result.matched is True
        assert result.service_name == "user-service"

    def test_route_no_match(self, router):
        result = router.route("/api/unknown", "GET")
        assert result.matched is False

    def test_route_with_params(self, router):
        router.add_route("user_detail", "/api/users/{user_id}", "user-service")
        result = router.route("/api/users/123", "GET")
        assert result.matched is True
        assert result.params["user_id"] == "123"

    def test_route_method_filter(self, router):
        router.add_route("users_post", "/api/users", "user-service", methods=["POST"])
        result_get = router.route("/api/users", "GET")
        assert result_get.matched is False
        result_post = router.route("/api/users", "POST")
        assert result_post.matched is True

    def test_route_priority(self, router):
        router.add_route("general", "/api/{path}", "general-service", priority=1)
        router.add_route("specific", "/api/users", "user-service", priority=10)
        result = router.route("/api/users", "GET")
        assert result.service_name == "user-service"

    def test_get_route(self, router):
        router.add_route("test", "/api/test", "test-service")
        route = router.get_route("test")
        assert route is not None

    def test_remove_route(self, router):
        router.add_route("test", "/api/test", "test-service")
        result = router.remove_route("test")
        assert result is True
        assert router.get_route("test") is None

    def test_enable_disable_route(self, router):
        router.add_route("test", "/api/test", "test-service")
        router.disable_route("test")
        route = router.get_route("test")
        assert route.enabled is False
        router.enable_route("test")
        assert route.enabled is True

    def test_get_metrics(self, router):
        router.add_route("test", "/api/test", "test-service")
        router.route("/api/test", "GET")
        metrics = router.get_metrics()
        assert metrics["total_routed"] == 1


class TestServiceRegistry:
    """Tests for ServiceRegistry"""

    @pytest.fixture
    def registry(self):
        return ServiceRegistry()

    def test_register_instance(self, registry):
        instance = registry.register(
            service_name="user-service",
            host="localhost",
            port=8080
        )
        assert instance.instance_id is not None
        assert instance.status == ServiceStatus.HEALTHY

    def test_deregister_instance(self, registry):
        instance = registry.register("test-service", "localhost", 8080)
        result = registry.deregister(instance.instance_id)
        assert result is True

    def test_get_instance(self, registry):
        registry.register("test-service", "localhost", 8080)
        registry.register("test-service", "localhost", 8081)
        instance = registry.get_instance("test-service")
        assert instance is not None
        assert instance.service_name == "test-service"

    def test_get_instance_unknown_service(self, registry):
        instance = registry.get_instance("unknown-service")
        assert instance is None

    def test_heartbeat(self, registry):
        instance = registry.register("test-service", "localhost", 8080)
        result = registry.heartbeat(instance.instance_id)
        assert result is True

    def test_set_instance_status(self, registry):
        instance = registry.register("test-service", "localhost", 8080)
        registry.set_instance_status(instance.instance_id, ServiceStatus.UNHEALTHY)
        updated = registry._instances[instance.instance_id]
        assert updated.status == ServiceStatus.UNHEALTHY

    def test_record_request(self, registry):
        instance = registry.register("test-service", "localhost", 8080)
        registry.record_request(instance.instance_id)
        registry.record_request(instance.instance_id, error=True)
        assert instance.request_count == 2
        assert instance.error_count == 1

    def test_get_service(self, registry):
        registry.register("test-service", "localhost", 8080)
        service = registry.get_service("test-service")
        assert service is not None

    def test_get_instances(self, registry):
        registry.register("test-service", "localhost", 8080)
        registry.register("test-service", "localhost", 8081)
        instances = registry.get_instances("test-service")
        assert len(instances) == 2

    def test_check_health(self, registry):
        registry.register("test-service", "localhost", 8080)
        health = registry.check_health()
        assert "healthy" in health
        assert "unhealthy" in health

    def test_get_metrics(self, registry):
        registry.register("test-service", "localhost", 8080)
        metrics = registry.get_metrics()
        assert metrics["total_registrations"] == 1
        assert metrics["total_services"] == 1


class TestServiceInstance:
    """Tests for ServiceInstance"""

    def test_instance_url(self):
        instance = ServiceInstance(
            instance_id="test_001",
            service_name="test-service",
            host="localhost",
            port=8080
        )
        assert instance.url == "http://localhost:8080"

    def test_error_rate(self):
        instance = ServiceInstance(
            instance_id="test_001",
            service_name="test-service",
            host="localhost",
            port=8080,
            request_count=100,
            error_count=5
        )
        assert instance.error_rate == 5.0


class TestGatewayIntegration:
    """Integration tests"""

    @pytest.mark.asyncio
    async def test_full_gateway_workflow(self):
        gateway = APIGateway()
        router = RequestRouter()
        registry = ServiceRegistry()

        registry.register("user-service", "localhost", 8080)
        router.add_route("users", "/api/users", "user-service")

        route_result = router.route("/api/users", "GET")
        assert route_result.matched is True

        response = await gateway.handle_request("GET", "/api/users", {})
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
