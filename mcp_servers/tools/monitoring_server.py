"""
PARWA Monitoring MCP Server.

MCP server for system monitoring operations including service status,
alert management, and metrics collection.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import random

from mcp_servers.base_server import BaseMCPServer
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


# Mock data for testing
MOCK_SERVICES = {
    "api-gateway": {
        "service_id": "api-gateway",
        "name": "API Gateway",
        "status": "healthy",
        "uptime_seconds": 1209600,  # 14 days
        "last_check": "2026-03-21T10:00:00Z",
        "response_time_ms": 45,
        "error_rate": 0.12
    },
    "mcp-knowledge": {
        "service_id": "mcp-knowledge",
        "name": "Knowledge MCP Servers",
        "status": "healthy",
        "uptime_seconds": 1209600,
        "last_check": "2026-03-21T10:00:00Z",
        "response_time_ms": 32,
        "error_rate": 0.05
    },
    "mcp-integrations": {
        "service_id": "mcp-integrations",
        "name": "Integration MCP Servers",
        "status": "healthy",
        "uptime_seconds": 1209600,
        "last_check": "2026-03-21T10:00:00Z",
        "response_time_ms": 58,
        "error_rate": 0.08
    },
    "mcp-tools": {
        "service_id": "mcp-tools",
        "name": "Tools MCP Servers",
        "status": "healthy",
        "uptime_seconds": 1209600,
        "last_check": "2026-03-21T10:00:00Z",
        "response_time_ms": 41,
        "error_rate": 0.03
    },
    "ai-engine": {
        "service_id": "ai-engine",
        "name": "AI Engine (GSD + TRIVYA)",
        "status": "healthy",
        "uptime_seconds": 604800,  # 7 days
        "last_check": "2026-03-21T10:00:00Z",
        "response_time_ms": 850,
        "error_rate": 0.15
    },
    "knowledge-base": {
        "service_id": "knowledge-base",
        "name": "Knowledge Base",
        "status": "healthy",
        "uptime_seconds": 1209600,
        "last_check": "2026-03-21T10:00:00Z",
        "response_time_ms": 25,
        "error_rate": 0.02
    },
    "guardrails": {
        "service_id": "guardrails",
        "name": "Guardrails Service",
        "status": "healthy",
        "uptime_seconds": 1209600,
        "last_check": "2026-03-21T10:00:00Z",
        "response_time_ms": 15,
        "error_rate": 0.01
    }
}

MOCK_ALERTS = [
    {
        "alert_id": "ALT-001",
        "service_id": "api-gateway",
        "severity": "warning",
        "message": "High request latency detected",
        "timestamp": "2026-03-21T09:45:00Z",
        "acknowledged": False,
        "acknowledged_by": None
    },
    {
        "alert_id": "ALT-002",
        "service_id": "ai-engine",
        "severity": "info",
        "message": "Token usage approaching daily limit",
        "timestamp": "2026-03-21T09:30:00Z",
        "acknowledged": True,
        "acknowledged_by": "admin@example.com"
    }
]


class MonitoringServer(BaseMCPServer):
    """
    MCP server for monitoring operations.

    Provides tools for:
    - Service status checks
    - Alert management
    - System metrics collection
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize Monitoring server.

        Args:
            config: Optional server configuration
        """
        super().__init__("monitoring-server", config)
        self._services = dict(MOCK_SERVICES)
        self._alerts = list(MOCK_ALERTS)

    def _register_tools(self) -> None:
        """Register all monitoring tools."""
        self.register_tool(
            name="get_service_status",
            description="Get status of all services or a specific service",
            parameters_schema={
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "string",
                        "description": "Optional service ID for specific status"
                    }
                },
                "required": []
            },
            handler=self._handle_get_service_status
        )

        self.register_tool(
            name="get_alerts",
            description="Get alerts filtered by severity",
            parameters_schema={
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "description": "Filter by severity level",
                        "enum": ["critical", "warning", "info", "all"]
                    }
                },
                "required": []
            },
            handler=self._handle_get_alerts
        )

        self.register_tool(
            name="acknowledge_alert",
            description="Acknowledge an alert",
            parameters_schema={
                "type": "object",
                "properties": {
                    "alert_id": {
                        "type": "string",
                        "description": "The alert ID to acknowledge"
                    },
                    "acknowledged_by": {
                        "type": "string",
                        "description": "User acknowledging the alert"
                    }
                },
                "required": ["alert_id", "acknowledged_by"]
            },
            handler=self._handle_acknowledge_alert
        )

        self.register_tool(
            name="get_metrics",
            description="Get system metrics",
            parameters_schema={
                "type": "object",
                "properties": {
                    "metric_type": {
                        "type": "string",
                        "description": "Type of metrics to retrieve",
                        "enum": ["system", "application", "all"]
                    }
                },
                "required": []
            },
            handler=self._handle_get_metrics
        )

    async def _handle_get_service_status(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle get_service_status tool call.

        Args:
            params: Tool parameters containing optional service_id

        Returns:
            Service status information
        """
        service_id = params.get("service_id")

        if service_id:
            service = self._services.get(service_id)
            if not service:
                return {
                    "status": "error",
                    "message": f"Service '{service_id}' not found"
                }

            # Update last check time
            service["last_check"] = datetime.now(timezone.utc).isoformat()

            return {
                "status": "success",
                "service": service
            }

        # Return all services
        services_list = []
        healthy_count = 0
        degraded_count = 0
        down_count = 0

        for service in self._services.values():
            service["last_check"] = datetime.now(timezone.utc).isoformat()
            services_list.append(service)

            if service["status"] == "healthy":
                healthy_count += 1
            elif service["status"] == "degraded":
                degraded_count += 1
            else:
                down_count += 1

        logger.info({
            "event": "service_status_retrieved",
            "total_services": len(services_list),
            "healthy": healthy_count
        })

        return {
            "status": "success",
            "services": services_list,
            "summary": {
                "total": len(services_list),
                "healthy": healthy_count,
                "degraded": degraded_count,
                "down": down_count
            }
        }

    async def _handle_get_alerts(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_alerts tool call.

        Args:
            params: Tool parameters containing optional severity filter

        Returns:
            List of alerts
        """
        severity = params.get("severity", "all")

        if severity == "all":
            filtered_alerts = self._alerts
        else:
            filtered_alerts = [
                a for a in self._alerts if a["severity"] == severity
            ]

        # Sort by timestamp (newest first)
        filtered_alerts.sort(key=lambda x: x["timestamp"], reverse=True)

        logger.info({
            "event": "alerts_retrieved",
            "severity_filter": severity,
            "count": len(filtered_alerts)
        })

        return {
            "status": "success",
            "alerts": filtered_alerts,
            "total_count": len(filtered_alerts),
            "unacknowledged_count": sum(1 for a in filtered_alerts if not a["acknowledged"])
        }

    async def _handle_acknowledge_alert(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle acknowledge_alert tool call.

        Args:
            params: Tool parameters containing alert_id and acknowledged_by

        Returns:
            Acknowledged alert details
        """
        alert_id = params["alert_id"]
        acknowledged_by = params["acknowledged_by"]

        # Find alert
        alert = next((a for a in self._alerts if a["alert_id"] == alert_id), None)

        if not alert:
            return {
                "status": "error",
                "message": f"Alert '{alert_id}' not found"
            }

        if alert["acknowledged"]:
            return {
                "status": "error",
                "message": f"Alert '{alert_id}' is already acknowledged"
            }

        # Acknowledge alert
        alert["acknowledged"] = True
        alert["acknowledged_by"] = acknowledged_by
        alert["acknowledged_at"] = datetime.now(timezone.utc).isoformat()

        logger.info({
            "event": "alert_acknowledged",
            "alert_id": alert_id,
            "acknowledged_by": acknowledged_by
        })

        return {
            "status": "success",
            "alert": alert,
            "message": f"Alert '{alert_id}' acknowledged by {acknowledged_by}"
        }

    async def _handle_get_metrics(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_metrics tool call.

        Args:
            params: Tool parameters containing optional metric_type

        Returns:
            System and application metrics
        """
        metric_type = params.get("metric_type", "all")
        now = datetime.now(timezone.utc)

        metrics = {}

        if metric_type in ["system", "all"]:
            metrics["system"] = {
                "cpu": {
                    "usage_percent": round(random.uniform(20, 60), 1),
                    "cores": 8,
                    "load_average": [1.2, 1.5, 1.3]
                },
                "memory": {
                    "usage_percent": round(random.uniform(40, 70), 1),
                    "total_gb": 32,
                    "used_gb": round(random.uniform(12, 22), 1),
                    "available_gb": round(random.uniform(10, 20), 1)
                },
                "disk": {
                    "usage_percent": round(random.uniform(30, 50), 1),
                    "total_gb": 500,
                    "used_gb": round(random.uniform(150, 250), 1),
                    "free_gb": round(random.uniform(250, 350), 1)
                },
                "network": {
                    "bytes_in_per_sec": random.randint(1000000, 5000000),
                    "bytes_out_per_sec": random.randint(500000, 2000000),
                    "connections_active": random.randint(100, 500)
                }
            }

        if metric_type in ["application", "all"]:
            metrics["application"] = {
                "requests": {
                    "total_per_minute": random.randint(100, 500),
                    "successful_per_minute": random.randint(95, 490),
                    "failed_per_minute": random.randint(0, 10),
                    "avg_response_time_ms": random.randint(50, 200)
                },
                "mcp_servers": {
                    "total_servers": 11,
                    "healthy_servers": 11,
                    "total_tool_calls": random.randint(1000, 5000),
                    "avg_tool_response_ms": random.randint(30, 100)
                },
                "ai_engine": {
                    "active_conversations": random.randint(50, 200),
                    "avg_response_time_ms": random.randint(500, 1500),
                    "tokens_used_today": random.randint(500000, 2000000),
                    "cache_hit_rate": round(random.uniform(70, 90), 1)
                },
                "guardrails": {
                    "hallucinations_blocked": random.randint(5, 20),
                    "competitor_mentions_blocked": random.randint(2, 10),
                    "pii_exposures_prevented": random.randint(1, 5),
                    "refund_bypass_attempts_blocked": random.randint(0, 3)
                }
            }

        logger.info({
            "event": "metrics_retrieved",
            "metric_type": metric_type
        })

        return {
            "status": "success",
            "timestamp": now.isoformat(),
            "metrics": metrics
        }
