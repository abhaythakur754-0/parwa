# Global Load Balancer - Week 51 Builder 1
# Global traffic distribution

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class BalancingStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    LATENCY_BASED = "latency_based"
    WEIGHTED = "weighted"
    GEOGRAPHIC = "geographic"


class RegionHealth(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class BackendServer:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    region: str = ""
    host: str = ""
    port: int = 443
    weight: int = 1
    max_connections: int = 1000
    current_connections: int = 0
    health: RegionHealth = RegionHealth.HEALTHY
    latency_ms: float = 0.0
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LoadBalancerConfig:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy: BalancingStrategy = BalancingStrategy.ROUND_ROBIN
    health_check_interval: int = 30
    health_check_timeout: int = 10
    unhealthy_threshold: int = 3
    healthy_threshold: int = 2
    sticky_session: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


class GlobalLoadBalancer:
    """Global traffic distribution across regions"""

    def __init__(self):
        self._configs: Dict[str, LoadBalancerConfig] = {}
        self._servers: Dict[str, BackendServer] = {}
        self._server_index: int = 0
        self._metrics = {
            "total_requests": 0,
            "requests_by_region": {},
            "requests_by_strategy": {}
        }

    def create_config(
        self,
        name: str,
        strategy: BalancingStrategy = BalancingStrategy.ROUND_ROBIN,
        health_check_interval: int = 30
    ) -> LoadBalancerConfig:
        """Create a load balancer configuration"""
        config = LoadBalancerConfig(
            name=name,
            strategy=strategy,
            health_check_interval=health_check_interval
        )
        self._configs[config.id] = config
        return config

    def add_server(
        self,
        region: str,
        host: str,
        port: int = 443,
        weight: int = 1,
        max_connections: int = 1000
    ) -> BackendServer:
        """Add a backend server"""
        server = BackendServer(
            region=region,
            host=host,
            port=port,
            weight=weight,
            max_connections=max_connections
        )
        self._servers[server.id] = server
        return server

    def remove_server(self, server_id: str) -> bool:
        """Remove a backend server"""
        if server_id in self._servers:
            del self._servers[server_id]
            return True
        return False

    def get_next_server(self, strategy: Optional[BalancingStrategy] = None) -> Optional[BackendServer]:
        """Get next server based on strategy"""
        healthy_servers = [
            s for s in self._servers.values()
            if s.enabled and s.health == RegionHealth.HEALTHY
        ]

        if not healthy_servers:
            return None

        if strategy == BalancingStrategy.ROUND_ROBIN or strategy is None:
            return self._round_robin(healthy_servers)
        elif strategy == BalancingStrategy.LEAST_CONNECTIONS:
            return self._least_connections(healthy_servers)
        elif strategy == BalancingStrategy.LATENCY_BASED:
            return self._latency_based(healthy_servers)
        elif strategy == BalancingStrategy.WEIGHTED:
            return self._weighted(healthy_servers)
        else:
            return self._round_robin(healthy_servers)

    def _round_robin(self, servers: List[BackendServer]) -> BackendServer:
        """Round robin selection"""
        server = servers[self._server_index % len(servers)]
        self._server_index += 1
        return server

    def _least_connections(self, servers: List[BackendServer]) -> BackendServer:
        """Select server with least connections"""
        return min(servers, key=lambda s: s.current_connections)

    def _latency_based(self, servers: List[BackendServer]) -> BackendServer:
        """Select server with lowest latency"""
        return min(servers, key=lambda s: s.latency_ms)

    def _weighted(self, servers: List[BackendServer]) -> BackendServer:
        """Weighted random selection"""
        import random
        total_weight = sum(s.weight for s in servers)
        r = random.uniform(0, total_weight)
        current = 0
        for server in servers:
            current += server.weight
            if r <= current:
                return server
        return servers[0]

    def record_request(
        self,
        server_id: str,
        latency_ms: float = 0.0,
        region: str = ""
    ) -> bool:
        """Record a request to a server"""
        server = self._servers.get(server_id)
        if not server:
            return False

        self._metrics["total_requests"] += 1

        if region:
            self._metrics["requests_by_region"][region] = \
                self._metrics["requests_by_region"].get(region, 0) + 1

        server.latency_ms = latency_ms
        return True

    def increment_connections(self, server_id: str) -> bool:
        """Increment connection count"""
        server = self._servers.get(server_id)
        if not server:
            return False
        server.current_connections += 1
        return True

    def decrement_connections(self, server_id: str) -> bool:
        """Decrement connection count"""
        server = self._servers.get(server_id)
        if not server:
            return False
        server.current_connections = max(0, server.current_connections - 1)
        return True

    def update_server_health(
        self,
        server_id: str,
        health: RegionHealth
    ) -> bool:
        """Update server health status"""
        server = self._servers.get(server_id)
        if not server:
            return False
        server.health = health
        return True

    def enable_server(self, server_id: str) -> bool:
        """Enable a server"""
        server = self._servers.get(server_id)
        if not server:
            return False
        server.enabled = True
        return True

    def disable_server(self, server_id: str) -> bool:
        """Disable a server"""
        server = self._servers.get(server_id)
        if not server:
            return False
        server.enabled = False
        return True

    def get_server(self, server_id: str) -> Optional[BackendServer]:
        """Get server by ID"""
        return self._servers.get(server_id)

    def get_servers_by_region(self, region: str) -> List[BackendServer]:
        """Get all servers in a region"""
        return [s for s in self._servers.values() if s.region == region]

    def get_healthy_servers(self) -> List[BackendServer]:
        """Get all healthy servers"""
        return [
            s for s in self._servers.values()
            if s.enabled and s.health == RegionHealth.HEALTHY
        ]

    def get_config(self, config_id: str) -> Optional[LoadBalancerConfig]:
        """Get configuration by ID"""
        return self._configs.get(config_id)

    def get_metrics(self) -> Dict[str, Any]:
        """Get load balancer metrics"""
        return {
            **self._metrics,
            "total_servers": len(self._servers),
            "healthy_servers": len(self.get_healthy_servers())
        }
