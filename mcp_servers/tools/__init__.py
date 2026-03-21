"""
PARWA MCP Tools Servers.

This package contains MCP servers for various tool operations:
- NotificationServer: User notifications via multiple channels
- ComplianceServer: GDPR and compliance checks
- SLAServer: SLA calculation and breach detection
- AnalyticsServer: Metrics and reporting (Builder 3)
- MonitoringServer: System monitoring (Builder 3)

All servers inherit from BaseMCPServer and provide tool-based operations.
"""
from mcp_servers.base_server import BaseMCPServer, MCPServerState, ToolResult
from mcp_servers.tools.notification_server import NotificationServer
from mcp_servers.tools.compliance_server import ComplianceServer
from mcp_servers.tools.sla_server import SLAServer

# Will be added by Builder 3
# from mcp_servers.tools.analytics_server import AnalyticsServer
# from mcp_servers.tools.monitoring_server import MonitoringServer

__all__ = [
    "BaseMCPServer",
    "MCPServerState",
    "ToolResult",
    "NotificationServer",
    "ComplianceServer",
    "SLAServer",
    # "AnalyticsServer",
    # "MonitoringServer",
]
