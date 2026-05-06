"""
Shard Router

Routes database queries to appropriate shards based on tenant context.
Provides transparent shard routing for application layer.
"""

from typing import Dict, List, Optional, Any, Callable, Awaitable
from datetime import datetime
from enum import Enum
import asyncio
from dataclasses import dataclass, field
import logging
from contextlib import asynccontextmanager

from .sharding_manager import ShardingManager, ShardStatus

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    """Types of database queries"""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    BULK = "bulk"
    TRANSACTION = "transaction"


class RoutingMode(str, Enum):
    """Routing modes for query distribution"""
    PRIMARY = "primary"  # Route to primary shard
    REPLICA = "replica"  # Route to replica for reads
    BROADCAST = "broadcast"  # Broadcast to all shards
    FANOUT = "fanout"  # Fan-out to specific shards


@dataclass
class QueryContext:
    """Context for a database query"""
    query_type: QueryType
    tenant_id: Optional[str] = None
    table_name: Optional[str] = None
    query_id: str = field(default_factory=lambda: f"qry_{datetime.utcnow().timestamp()}")
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # Higher priority = more important
    timeout_ms: int = 30000  # 30 seconds default


@dataclass
class RoutingResult:
    """Result of shard routing decision"""
    shard_id: str
    connection_string: str
    is_replica: bool = False
    routing_time_ms: float = 0
    cached: bool = False


@dataclass
class ConnectionPool:
    """Connection pool for a shard"""
    shard_id: str
    primary: str
    replicas: List[str] = field(default_factory=list)
    max_connections: int = 20
    active_connections: int = 0
    healthy: bool = True


class ShardRouter:
    """
    Routes database queries to appropriate shards.

    Features:
    - Transparent shard routing
    - Read/Write splitting
    - Connection pooling
    - Query caching
    - Load balancing
    """

    def __init__(
        self,
        sharding_manager: ShardingManager,
        enable_read_replicas: bool = True,
        cache_ttl_seconds: int = 300
    ):
        self.sharding_manager = sharding_manager
        self.enable_read_replicas = enable_read_replicas
        self.cache_ttl_seconds = cache_ttl_seconds

        # Connection pools
        self._connection_pools: Dict[str, ConnectionPool] = {}

        # Routing cache
        self._routing_cache: Dict[str, RoutingResult] = {}
        self._cache_timestamps: Dict[str, datetime] = {}

        # Metrics
        self._routing_metrics = {
            "total_routes": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0
        }

        # Initialize connection pools
        self._initialize_connection_pools()

    def _initialize_connection_pools(self) -> None:
        """Initialize connection pools for all shards"""
        for shard in self.sharding_manager.get_all_shards():
            pool = ConnectionPool(
                shard_id=shard.shard_id,
                primary=shard.connection_string,
                replicas=self._generate_replica_strings(shard.connection_string),
                max_connections=20
            )
            self._connection_pools[shard.shard_id] = pool

        logger.info(f"Initialized {len(self._connection_pools)} connection pools")

    def _generate_replica_strings(self, primary: str, num_replicas: int = 2) -> List[str]:
        """Generate replica connection strings from primary"""
        replicas = []
        for i in range(num_replicas):
            # Replace primary identifier with replica
            replica = primary.replace("@", f"@replica{i}.", 1) if "@" in primary else f"{primary}-replica{i}"
            replicas.append(replica)
        return replicas

    async def route(
        self,
        query: str,
        context: QueryContext
    ) -> RoutingResult:
        """
        Route a query to the appropriate shard.

        Args:
            query: SQL query string
            context: Query context with tenant and query type

        Returns:
            RoutingResult with shard and connection info
        """
        start_time = datetime.utcnow()
        self._routing_metrics["total_routes"] += 1

        # Check cache first
        cache_key = self._get_cache_key(context)
        if cache_key:
            cached_result = self._get_cached_routing(cache_key)
            if cached_result:
                cached_result.cached = True
                cached_result.routing_time_ms = self._get_elapsed_ms(start_time)
                self._routing_metrics["cache_hits"] += 1
                return cached_result

        self._routing_metrics["cache_misses"] += 1

        # Determine routing strategy
        shard_id = await self._determine_shard(context)

        # Get connection string
        is_replica = False
        if self.enable_read_replicas and context.query_type == QueryType.SELECT:
            connection_string = await self._get_replica_connection(shard_id)
            is_replica = True
        else:
            connection_string = await self._get_primary_connection(shard_id)

        result = RoutingResult(
            shard_id=shard_id,
            connection_string=connection_string,
            is_replica=is_replica,
            routing_time_ms=self._get_elapsed_ms(start_time)
        )

        # Cache the result
        if cache_key:
            self._cache_routing(cache_key, result)

        return result

    async def _determine_shard(self, context: QueryContext) -> str:
        """Determine which shard to route to"""
        if context.tenant_id:
            # Get or assign shard for tenant
            if context.query_type in [QueryType.SELECT]:
                return await self.sharding_manager.get_shard_for_read(context.tenant_id)
            else:
                return await self.sharding_manager.get_shard_for_write(context.tenant_id)

        # No tenant context - route to least loaded shard
        return await self._get_least_loaded_shard()

    async def _get_least_loaded_shard(self) -> str:
        """Get the shard with lowest load"""
        shards = self.sharding_manager.get_all_shards()
        active_shards = [s for s in shards if s.status == ShardStatus.ACTIVE]

        if not active_shards:
            raise RuntimeError("No active shards available")

        # Select shard with lowest utilization
        selected = min(active_shards, key=lambda s: s.utilization)
        return selected.shard_id

    async def _get_primary_connection(self, shard_id: str) -> str:
        """Get primary connection for a shard"""
        pool = self._connection_pools.get(shard_id)
        if not pool:
            raise RuntimeError(f"No connection pool for shard {shard_id}")

        if not pool.healthy:
            raise RuntimeError(f"Connection pool for shard {shard_id} is unhealthy")

        return pool.primary

    async def _get_replica_connection(self, shard_id: str) -> str:
        """Get replica connection for a shard (with fallback to primary)"""
        pool = self._connection_pools.get(shard_id)
        if not pool:
            raise RuntimeError(f"No connection pool for shard {shard_id}")

        # Use replica if available and healthy
        if pool.replicas and pool.healthy:
            # Simple round-robin for now
            return pool.replicas[0]

        # Fallback to primary
        return pool.primary

    def _get_cache_key(self, context: QueryContext) -> Optional[str]:
        """Generate cache key for routing decision"""
        if not context.tenant_id:
            return None

        return f"{context.tenant_id}:{context.query_type.value}"

    def _get_cached_routing(self, cache_key: str) -> Optional[RoutingResult]:
        """Get cached routing result if still valid"""
        if cache_key not in self._routing_cache:
            return None

        timestamp = self._cache_timestamps.get(cache_key)
        if not timestamp:
            return None

        # Check TTL
        elapsed = (datetime.utcnow() - timestamp).total_seconds()
        if elapsed > self.cache_ttl_seconds:
            # Cache expired
            del self._routing_cache[cache_key]
            del self._cache_timestamps[cache_key]
            return None

        # Return cached result (copy to avoid mutation)
        cached = self._routing_cache[cache_key]
        return RoutingResult(
            shard_id=cached.shard_id,
            connection_string=cached.connection_string,
            is_replica=cached.is_replica,
            routing_time_ms=cached.routing_time_ms
        )

    def _cache_routing(self, cache_key: str, result: RoutingResult) -> None:
        """Cache a routing result"""
        self._routing_cache[cache_key] = RoutingResult(
            shard_id=result.shard_id,
            connection_string=result.connection_string,
            is_replica=result.is_replica,
            routing_time_ms=result.routing_time_ms
        )
        self._cache_timestamps[cache_key] = datetime.utcnow()

    def _get_elapsed_ms(self, start: datetime) -> float:
        """Get elapsed time in milliseconds"""
        return (datetime.utcnow() - start).total_seconds() * 1000

    async def route_batch(
        self,
        queries: List[tuple]  # List of (query, context)
    ) -> Dict[str, List[RoutingResult]]:
        """
        Route a batch of queries, grouping by shard.

        Returns:
            Dict mapping shard_id to list of routing results
        """
        results_by_shard: Dict[str, List[RoutingResult]] = {}

        for query, context in queries:
            result = await self.route(query, context)
            if result.shard_id not in results_by_shard:
                results_by_shard[result.shard_id] = []
            results_by_shard[result.shard_id].append(result)

        return results_by_shard

    @asynccontextmanager
    async def connection(self, tenant_id: str, query_type: QueryType = QueryType.SELECT):
        """
        Context manager for getting a database connection.

        Usage:
            async with router.connection("tenant_001", QueryType.SELECT) as conn:
                # Use connection
                pass
        """
        context = QueryContext(
            query_type=query_type,
            tenant_id=tenant_id
        )

        result = await self.route("", context)
        pool = self._connection_pools.get(result.shard_id)

        if pool:
            pool.active_connections += 1

        try:
            yield result.connection_string
        finally:
            if pool:
                pool.active_connections -= 1

    async def broadcast_to_all_shards(
        self,
        query: str,
        context: QueryContext
    ) -> List[RoutingResult]:
        """
        Broadcast a query to all active shards.
        Used for cross-tenant queries or system operations.
        """
        results = []
        shards = self.sharding_manager.get_all_shards()

        for shard in shards:
            if shard.status == ShardStatus.ACTIVE:
                result = RoutingResult(
                    shard_id=shard.shard_id,
                    connection_string=shard.connection_string,
                    is_replica=False
                )
                results.append(result)

        return results

    async def execute_on_shards(
        self,
        shard_ids: List[str],
        query: str,
        context: QueryContext
    ) -> Dict[str, RoutingResult]:
        """
        Execute a query on specific shards.
        """
        results = {}

        for shard_id in shard_ids:
            shard = self.sharding_manager.get_shard_config(shard_id)
            if shard and shard.status in [ShardStatus.ACTIVE, ShardStatus.READ_ONLY]:
                results[shard_id] = RoutingResult(
                    shard_id=shard_id,
                    connection_string=shard.connection_string,
                    is_replica=context.query_type == QueryType.SELECT
                )

        return results

    def get_metrics(self) -> Dict[str, Any]:
        """Get routing metrics"""
        return {
            **self._routing_metrics,
            "cache_size": len(self._routing_cache),
            "connection_pools": {
                shard_id: {
                    "active_connections": pool.active_connections,
                    "max_connections": pool.max_connections,
                    "healthy": pool.healthy
                }
                for shard_id, pool in self._connection_pools.items()
            }
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on router"""
        pool_health = {}

        for shard_id, pool in self._connection_pools.items():
            # Simulate connection check
            is_healthy = pool.active_connections < pool.max_connections
            pool.healthy = is_healthy
            pool_health[shard_id] = {
                "healthy": is_healthy,
                "utilization": pool.active_connections / pool.max_connections
            }

        return {
            "router_healthy": all(p["healthy"] for p in pool_health.values()),
            "pools": pool_health,
            "metrics": self._routing_metrics
        }

    def clear_cache(self) -> None:
        """Clear the routing cache"""
        self._routing_cache.clear()
        self._cache_timestamps.clear()
        logger.info("Routing cache cleared")

    async def get_shard_for_tenant(self, tenant_id: str) -> Optional[str]:
        """Get the shard assigned to a tenant"""
        return self.sharding_manager.get_tenant_shard(tenant_id)

    async def get_tenant_routing_info(self, tenant_id: str) -> Dict[str, Any]:
        """Get detailed routing info for a tenant"""
        shard_id = await self.get_shard_for_tenant(tenant_id)
        if not shard_id:
            return {"error": "Tenant not found or not assigned"}

        shard = self.sharding_manager.get_shard_config(shard_id)
        pool = self._connection_pools.get(shard_id)

        return {
            "tenant_id": tenant_id,
            "shard_id": shard_id,
            "shard_status": shard.status.value if shard else "unknown",
            "shard_region": shard.region if shard else "unknown",
            "connection_pool": {
                "active": pool.active_connections if pool else 0,
                "max": pool.max_connections if pool else 0,
                "healthy": pool.healthy if pool else False
            }
        }
