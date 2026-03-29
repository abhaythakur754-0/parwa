"""
Multi-Tenant Database Sharding Manager

Provides database sharding capabilities for enterprise multi-tenancy:
- Horizontal sharding across multiple database instances
- Tenant-to-shard mapping
- Shard health monitoring
- Automatic failover and recovery
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import hashlib
import asyncio
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class ShardStatus(str, Enum):
    """Status of a database shard"""
    ACTIVE = "active"
    READ_ONLY = "read_only"
    MIGRATING = "migrating"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class ShardingStrategy(str, Enum):
    """Sharding strategies for tenant distribution"""
    HASH = "hash"  # Hash-based sharding
    RANGE = "range"  # Range-based sharding
    DIRECTORY = "directory"  # Directory-based (lookup table)
    GEOGRAPHIC = "geographic"  # Geographic-based sharding


@dataclass
class ShardConfig:
    """Configuration for a database shard"""
    shard_id: str
    connection_string: str
    region: str
    capacity: int  # Max tenants
    status: ShardStatus = ShardStatus.ACTIVE
    tenant_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_health_check: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def utilization(self) -> float:
        """Calculate shard utilization percentage"""
        return (self.tenant_count / self.capacity) * 100 if self.capacity > 0 else 0

    @property
    def available_capacity(self) -> int:
        """Calculate available capacity"""
        return max(0, self.capacity - self.tenant_count)


@dataclass
class TenantShardMapping:
    """Mapping between tenant and shard"""
    tenant_id: str
    shard_id: str
    assigned_at: datetime = field(default_factory=datetime.utcnow)
    migration_status: Optional[str] = None
    previous_shard: Optional[str] = None


class ShardingManager:
    """
    Manages database sharding for multi-tenant deployments.

    Features:
    - Multiple sharding strategies
    - Automatic tenant-to-shard assignment
    - Shard health monitoring
    - Capacity management
    - Migration coordination
    """

    def __init__(
        self,
        strategy: ShardingStrategy = ShardingStrategy.HASH,
        total_shards: int = 4,
        replication_factor: int = 2
    ):
        self.strategy = strategy
        self.total_shards = total_shards
        self.replication_factor = replication_factor

        # Shard storage
        self._shards: Dict[str, ShardConfig] = {}
        self._tenant_mappings: Dict[str, TenantShardMapping] = {}

        # Virtual nodes for consistent hashing
        self._virtual_nodes: Dict[int, str] = {}
        self._virtual_nodes_per_shard = 150

        # Initialize shards
        self._initialize_shards()

    def _initialize_shards(self) -> None:
        """Initialize shard configurations"""
        regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]

        for i in range(self.total_shards):
            shard_id = f"shard_{i:03d}"
            region = regions[i % len(regions)]

            self._shards[shard_id] = ShardConfig(
                shard_id=shard_id,
                connection_string=f"postgresql://shard_{i}@{region}.db.parwa.io:5432/parwa",
                region=region,
                capacity=100,  # 100 tenants per shard
                status=ShardStatus.ACTIVE
            )

        # Setup virtual nodes for consistent hashing
        self._setup_virtual_nodes()

        logger.info(f"Initialized {self.total_shards} shards")

    def _setup_virtual_nodes(self) -> None:
        """Setup virtual nodes for consistent hashing"""
        self._virtual_nodes.clear()

        for shard_id in self._shards:
            for i in range(self._virtual_nodes_per_shard):
                virtual_key = self._hash(f"{shard_id}:vnode:{i}")
                self._virtual_nodes[virtual_key] = shard_id

        # Sort virtual nodes for binary search
        self._sorted_vnodes = sorted(self._virtual_nodes.keys())

    def _hash(self, key: str) -> int:
        """Generate consistent hash for a key"""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    async def assign_tenant_to_shard(
        self,
        tenant_id: str,
        preferred_region: Optional[str] = None
    ) -> TenantShardMapping:
        """
        Assign a tenant to an appropriate shard.

        Args:
            tenant_id: Unique tenant identifier
            preferred_region: Optional preferred region for the tenant

        Returns:
            TenantShardMapping with shard assignment
        """
        # Check if tenant already has a mapping
        if tenant_id in self._tenant_mappings:
            return self._tenant_mappings[tenant_id]

        # Get appropriate shard based on strategy
        shard_id = await self._select_shard(tenant_id, preferred_region)

        # Create mapping
        mapping = TenantShardMapping(
            tenant_id=tenant_id,
            shard_id=shard_id
        )
        self._tenant_mappings[tenant_id] = mapping

        # Update shard tenant count
        self._shards[shard_id].tenant_count += 1

        logger.info(f"Assigned tenant {tenant_id} to shard {shard_id}")
        return mapping

    async def _select_shard(
        self,
        tenant_id: str,
        preferred_region: Optional[str] = None
    ) -> str:
        """Select appropriate shard for tenant"""

        if self.strategy == ShardingStrategy.HASH:
            return self._select_shard_hash(tenant_id)
        elif self.strategy == ShardingStrategy.RANGE:
            return self._select_shard_range(tenant_id)
        elif self.strategy == ShardingStrategy.DIRECTORY:
            return await self._select_shard_directory(tenant_id, preferred_region)
        elif self.strategy == ShardingStrategy.GEOGRAPHIC:
            return self._select_shard_geographic(preferred_region)
        else:
            return self._select_shard_hash(tenant_id)

    def _select_shard_hash(self, tenant_id: str) -> str:
        """Select shard using consistent hashing"""
        tenant_hash = self._hash(tenant_id)

        # Binary search for the appropriate virtual node
        left, right = 0, len(self._sorted_vnodes) - 1
        while left < right:
            mid = (left + right) // 2
            if self._sorted_vnodes[mid] < tenant_hash:
                left = mid + 1
            else:
                right = mid

        vnode_key = self._sorted_vnodes[left]
        return self._virtual_nodes[vnode_key]

    def _select_shard_range(self, tenant_id: str) -> str:
        """Select shard based on tenant ID ranges"""
        # Extract numeric part if possible
        try:
            tenant_num = int(''.join(filter(str.isdigit, tenant_id)))
        except ValueError:
            tenant_num = self._hash(tenant_id)

        # Calculate shard based on range
        shard_index = tenant_num % self.total_shards
        return f"shard_{shard_index:03d}"

    async def _select_shard_directory(
        self,
        tenant_id: str,
        preferred_region: Optional[str] = None
    ) -> str:
        """Select shard using directory (lookup table) approach"""
        # Find shard with available capacity
        candidates = [
            s for s in self._shards.values()
            if s.status == ShardStatus.ACTIVE and s.available_capacity > 0
        ]

        # Filter by preferred region if specified
        if preferred_region:
            region_candidates = [s for s in candidates if s.region == preferred_region]
            if region_candidates:
                candidates = region_candidates

        # Select shard with lowest utilization
        if candidates:
            selected = min(candidates, key=lambda s: s.utilization)
            return selected.shard_id

        raise RuntimeError("No available shards for tenant assignment")

    def _select_shard_geographic(self, preferred_region: Optional[str]) -> str:
        """Select shard based on geographic location"""
        region = preferred_region or "us-east-1"

        # Find shards in the preferred region
        region_shards = [
            s for s in self._shards.values()
            if s.region == region and s.status == ShardStatus.ACTIVE
        ]

        if region_shards:
            # Select shard with lowest utilization in region
            selected = min(region_shards, key=lambda s: s.utilization)
            return selected.shard_id

        # Fallback to any available shard
        active_shards = [
            s for s in self._shards.values()
            if s.status == ShardStatus.ACTIVE and s.available_capacity > 0
        ]

        if active_shards:
            selected = min(active_shards, key=lambda s: s.utilization)
            return selected.shard_id

        raise RuntimeError(f"No available shards in region {region}")

    def get_tenant_shard(self, tenant_id: str) -> Optional[str]:
        """Get the shard ID for a tenant"""
        mapping = self._tenant_mappings.get(tenant_id)
        return mapping.shard_id if mapping else None

    def get_shard_config(self, shard_id: str) -> Optional[ShardConfig]:
        """Get configuration for a specific shard"""
        return self._shards.get(shard_id)

    def get_all_shards(self) -> List[ShardConfig]:
        """Get all shard configurations"""
        return list(self._shards.values())

    async def get_shard_for_read(self, tenant_id: str) -> str:
        """Get shard for read operations (may include replicas)"""
        shard_id = self.get_tenant_shard(tenant_id)
        if not shard_id:
            # Auto-assign if not found
            mapping = await self.assign_tenant_to_shard(tenant_id)
            shard_id = mapping.shard_id

        shard = self._shards.get(shard_id)
        if not shard or shard.status == ShardStatus.OFFLINE:
            raise RuntimeError(f"Shard {shard_id} is not available for reads")

        return shard_id

    async def get_shard_for_write(self, tenant_id: str) -> str:
        """Get shard for write operations"""
        shard_id = self.get_tenant_shard(tenant_id)
        if not shard_id:
            # Auto-assign if not found
            mapping = await self.assign_tenant_to_shard(tenant_id)
            shard_id = mapping.shard_id

        shard = self._shards.get(shard_id)
        if not shard:
            raise RuntimeError(f"Shard {shard_id} not found")

        if shard.status not in [ShardStatus.ACTIVE, ShardStatus.MIGRATING]:
            raise RuntimeError(f"Shard {shard_id} is not available for writes")

        return shard_id

    async def update_shard_status(
        self,
        shard_id: str,
        status: ShardStatus
    ) -> bool:
        """Update the status of a shard"""
        shard = self._shards.get(shard_id)
        if not shard:
            return False

        old_status = shard.status
        shard.status = status
        shard.last_health_check = datetime.utcnow()

        logger.info(f"Shard {shard_id} status changed: {old_status} -> {status}")
        return True

    async def get_shard_metrics(self) -> Dict[str, Any]:
        """Get metrics for all shards"""
        metrics = {
            "total_shards": len(self._shards),
            "total_tenants": len(self._tenant_mappings),
            "shards": []
        }

        for shard in self._shards.values():
            shard_metrics = {
                "shard_id": shard.shard_id,
                "status": shard.status.value,
                "region": shard.region,
                "tenant_count": shard.tenant_count,
                "capacity": shard.capacity,
                "utilization": round(shard.utilization, 2),
                "available_capacity": shard.available_capacity,
                "last_health_check": shard.last_health_check.isoformat() if shard.last_health_check else None
            }
            metrics["shards"].append(shard_metrics)

        # Calculate aggregate metrics
        active_shards = [s for s in self._shards.values() if s.status == ShardStatus.ACTIVE]
        metrics["active_shards"] = len(active_shards)
        metrics["average_utilization"] = (
            sum(s.utilization for s in active_shards) / len(active_shards)
        ) if active_shards else 0

        return metrics

    async def find_overloaded_shards(self, threshold: float = 80.0) -> List[ShardConfig]:
        """Find shards exceeding utilization threshold"""
        return [
            shard for shard in self._shards.values()
            if shard.utilization > threshold and shard.status == ShardStatus.ACTIVE
        ]

    async def find_underutilized_shards(self, threshold: float = 20.0) -> List[ShardConfig]:
        """Find shards below utilization threshold"""
        return [
            shard for shard in self._shards.values()
            if shard.utilization < threshold and shard.status == ShardStatus.ACTIVE
        ]

    def get_tenants_on_shard(self, shard_id: str) -> List[str]:
        """Get all tenants assigned to a specific shard"""
        return [
            mapping.tenant_id
            for mapping in self._tenant_mappings.values()
            if mapping.shard_id == shard_id
        ]

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all shards"""
        results = {
            "healthy": 0,
            "unhealthy": 0,
            "details": {}
        }

        for shard_id, shard in self._shards.items():
            # Simulate health check
            is_healthy = shard.status in [ShardStatus.ACTIVE, ShardStatus.READ_ONLY]
            shard.last_health_check = datetime.utcnow()

            results["details"][shard_id] = {
                "healthy": is_healthy,
                "status": shard.status.value,
                "checked_at": shard.last_health_check.isoformat()
            }

            if is_healthy:
                results["healthy"] += 1
            else:
                results["unhealthy"] += 1

        return results

    def get_capacity_report(self) -> Dict[str, Any]:
        """Generate capacity report"""
        total_capacity = sum(s.capacity for s in self._shards.values())
        total_used = sum(s.tenant_count for s in self._shards.values())

        return {
            "total_capacity": total_capacity,
            "total_used": total_used,
            "total_available": total_capacity - total_used,
            "overall_utilization": (total_used / total_capacity * 100) if total_capacity > 0 else 0,
            "shards_by_region": self._get_capacity_by_region()
        }

    def _get_capacity_by_region(self) -> Dict[str, Dict[str, int]]:
        """Get capacity breakdown by region"""
        by_region: Dict[str, Dict[str, int]] = {}

        for shard in self._shards.values():
            if shard.region not in by_region:
                by_region[shard.region] = {
                    "capacity": 0,
                    "used": 0,
                    "available": 0
                }

            by_region[shard.region]["capacity"] += shard.capacity
            by_region[shard.region]["used"] += shard.tenant_count
            by_region[shard.region]["available"] += shard.available_capacity

        return by_region
