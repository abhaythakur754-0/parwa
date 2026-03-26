"""
PARWA MCP Registry.

Handles MCP server registry connection, discovery, and management.
Provides service discovery for MCP tools and resources.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum
import asyncio

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class RegistryStatus(str, Enum):
    """Registry connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class MCPServerInfo:
    """MCP Server information model."""

    def __init__(
        self,
        server_id: str,
        name: str,
        url: str,
        server_type: str = "generic",
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize MCP Server Info.

        Args:
            server_id: Unique server identifier
            name: Human-readable server name
            url: Server URL
            server_type: Server type (knowledge, integration, tool)
            capabilities: List of server capabilities
            metadata: Additional server metadata
        """
        self.server_id = server_id
        self.name = name
        self.url = url
        self.server_type = server_type
        self.capabilities = capabilities or []
        self.metadata = metadata or {}
        self.registered_at = datetime.now(timezone.utc)
        self.last_heartbeat: Optional[datetime] = None
        self.is_healthy = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "server_id": self.server_id,
            "name": self.name,
            "url": self.url,
            "server_type": self.server_type,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
            "registered_at": self.registered_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "is_healthy": self.is_healthy,
        }


class MCPRegistry:
    """
    MCP Registry for server discovery and management.

    Features:
    - Server registration and discovery
    - Health monitoring
    - Capability-based routing
    - Load balancing support
    """

    HEARTBEAT_INTERVAL = 60  # seconds
    HEALTH_CHECK_INTERVAL = 30  # seconds

    def __init__(
        self,
        registry_url: Optional[str] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize MCP Registry.

        Args:
            registry_url: Registry service URL
            company_id: Company UUID for scoping
        """
        self.registry_url = registry_url
        self.company_id = company_id
        self._status = RegistryStatus.DISCONNECTED
        self._servers: Dict[str, MCPServerInfo] = {}
        self._tools_index: Dict[str, List[str]] = {}  # tool_name -> server_ids
        self._resources_index: Dict[str, List[str]] = {}  # resource_uri -> server_ids

    @property
    def status(self) -> str:
        """Get current registry status."""
        return self._status

    @property
    def is_connected(self) -> bool:
        """Check if registry is connected."""
        return self._status == RegistryStatus.CONNECTED

    async def connect(self) -> bool:
        """
        Connect to the MCP registry.

        Returns:
            True if connected successfully
        """
        if self._status == RegistryStatus.CONNECTED:
            return True

        self._status = RegistryStatus.CONNECTING

        try:
            # Simulated connection
            await asyncio.sleep(0.1)

            # Load initial server list
            await self._load_servers()

            self._status = RegistryStatus.CONNECTED

            logger.info({
                "event": "mcp_registry_connected",
                "registry_url": self.registry_url,
                "company_id": str(self.company_id) if self.company_id else None,
            })

            return True

        except Exception as e:
            self._status = RegistryStatus.ERROR

            logger.error({
                "event": "mcp_registry_connection_failed",
                "error": str(e),
                "registry_url": self.registry_url,
            })

            return False

    async def disconnect(self) -> None:
        """Disconnect from the MCP registry."""
        self._servers.clear()
        self._tools_index.clear()
        self._resources_index.clear()
        self._status = RegistryStatus.DISCONNECTED

        logger.info({
            "event": "mcp_registry_disconnected",
            "company_id": str(self.company_id) if self.company_id else None,
        })

    async def _load_servers(self) -> None:
        """Load initial server list from registry."""
        # In production, would fetch from registry service
        # For now, start with empty
        pass

    def register_server(
        self,
        name: str,
        url: str,
        server_type: str = "generic",
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MCPServerInfo:
        """
        Register an MCP server with the registry.

        Args:
            name: Server name
            url: Server URL
            server_type: Server type
            capabilities: Server capabilities
            metadata: Additional metadata

        Returns:
            Registered MCPServerInfo
        """
        server_id = str(uuid4())

        server = MCPServerInfo(
            server_id=server_id,
            name=name,
            url=url,
            server_type=server_type,
            capabilities=capabilities or [],
            metadata=metadata or {},
        )

        self._servers[server_id] = server

        logger.info({
            "event": "mcp_server_registered",
            "server_id": server_id,
            "name": name,
            "url": url,
            "server_type": server_type,
        })

        return server

    def unregister_server(self, server_id: str) -> bool:
        """
        Unregister an MCP server.

        Args:
            server_id: Server ID to unregister

        Returns:
            True if server was unregistered
        """
        if server_id in self._servers:
            server = self._servers[server_id]
            del self._servers[server_id]

            logger.info({
                "event": "mcp_server_unregistered",
                "server_id": server_id,
                "name": server.name,
            })

            return True

        return False

    def get_server(self, server_id: str) -> Optional[MCPServerInfo]:
        """
        Get server by ID.

        Args:
            server_id: Server ID

        Returns:
            MCPServerInfo if found, None otherwise
        """
        return self._servers.get(server_id)

    def get_servers_by_type(self, server_type: str) -> List[MCPServerInfo]:
        """
        Get servers by type.

        Args:
            server_type: Server type to filter by

        Returns:
            List of matching servers
        """
        return [
            server for server in self._servers.values()
            if server.server_type == server_type
        ]

    def get_servers_by_capability(self, capability: str) -> List[MCPServerInfo]:
        """
        Get servers that have a specific capability.

        Args:
            capability: Capability to search for

        Returns:
            List of matching servers
        """
        return [
            server for server in self._servers.values()
            if capability in server.capabilities
        ]

    def get_all_servers(self) -> List[MCPServerInfo]:
        """
        Get all registered servers.

        Returns:
            List of all servers
        """
        return list(self._servers.values())

    def get_healthy_servers(self) -> List[MCPServerInfo]:
        """
        Get all healthy servers.

        Returns:
            List of healthy servers
        """
        return [
            server for server in self._servers.values()
            if server.is_healthy
        ]

    def register_tool(self, tool_name: str, server_id: str) -> None:
        """
        Register a tool with a server.

        Args:
            tool_name: Tool name
            server_id: Server ID that provides this tool
        """
        if tool_name not in self._tools_index:
            self._tools_index[tool_name] = []

        if server_id not in self._tools_index[tool_name]:
            self._tools_index[tool_name].append(server_id)

        logger.debug({
            "event": "mcp_tool_registered_to_server",
            "tool_name": tool_name,
            "server_id": server_id,
        })

    def register_resource(self, resource_uri: str, server_id: str) -> None:
        """
        Register a resource with a server.

        Args:
            resource_uri: Resource URI
            server_id: Server ID that provides this resource
        """
        if resource_uri not in self._resources_index:
            self._resources_index[resource_uri] = []

        if server_id not in self._resources_index[resource_uri]:
            self._resources_index[resource_uri].append(server_id)

        logger.debug({
            "event": "mcp_resource_registered_to_server",
            "resource_uri": resource_uri,
            "server_id": server_id,
        })

    def get_servers_for_tool(self, tool_name: str) -> List[MCPServerInfo]:
        """
        Get servers that provide a specific tool.

        Args:
            tool_name: Tool name

        Returns:
            List of servers providing the tool
        """
        server_ids = self._tools_index.get(tool_name, [])
        return [
            self._servers[sid] for sid in server_ids
            if sid in self._servers and self._servers[sid].is_healthy
        ]

    def get_servers_for_resource(self, resource_uri: str) -> List[MCPServerInfo]:
        """
        Get servers that provide a specific resource.

        Args:
            resource_uri: Resource URI

        Returns:
            List of servers providing the resource
        """
        server_ids = self._resources_index.get(resource_uri, [])
        return [
            self._servers[sid] for sid in server_ids
            if sid in self._servers and self._servers[sid].is_healthy
        ]

    def update_server_heartbeat(self, server_id: str) -> bool:
        """
        Update server heartbeat timestamp.

        Args:
            server_id: Server ID

        Returns:
            True if server exists and was updated
        """
        if server_id in self._servers:
            self._servers[server_id].last_heartbeat = datetime.now(timezone.utc)
            self._servers[server_id].is_healthy = True
            return True
        return False

    def mark_server_unhealthy(self, server_id: str) -> bool:
        """
        Mark a server as unhealthy.

        Args:
            server_id: Server ID

        Returns:
            True if server exists and was marked
        """
        if server_id in self._servers:
            self._servers[server_id].is_healthy = False

            logger.warning({
                "event": "mcp_server_marked_unhealthy",
                "server_id": server_id,
                "name": self._servers[server_id].name,
            })

            return True
        return False

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on registry.

        Returns:
            Health status dict
        """
        total_servers = len(self._servers)
        healthy_servers = len(self.get_healthy_servers())
        total_tools = len(self._tools_index)
        total_resources = len(self._resources_index)

        return {
            "status": self._status,
            "is_connected": self.is_connected,
            "registry_url": self.registry_url,
            "servers": {
                "total": total_servers,
                "healthy": healthy_servers,
                "unhealthy": total_servers - healthy_servers,
            },
            "tools_registered": total_tools,
            "resources_registered": total_resources,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_registry_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Statistics dict
        """
        server_types: Dict[str, int] = {}
        for server in self._servers.values():
            server_types[server.server_type] = server_types.get(server.server_type, 0) + 1

        return {
            "total_servers": len(self._servers),
            "healthy_servers": len(self.get_healthy_servers()),
            "server_types": server_types,
            "total_tools": len(self._tools_index),
            "total_resources": len(self._resources_index),
        }
