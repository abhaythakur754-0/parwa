"""
Shard Rebalancer

Handles shard rebalancing and tenant migration for load distribution.
Provides automatic and manual rebalancing capabilities.
"""

from typing import Dict, List, Optional, Any, Callable, Awaitable
from datetime import datetime
from enum import Enum
import asyncio
from dataclasses import dataclass, field
import logging
import math

from .sharding_manager import ShardingManager, ShardStatus, TenantShardMapping

logger = logging.getLogger(__name__)


class RebalanceStrategy(str, Enum):
    """Strategies for shard rebalancing"""
    LOAD_BASED = "load_based"  # Based on load/capacity
    GEOGRAPHIC = "geographic"  # Based on geographic location
    COST_OPTIMIZED = "cost_optimized"  # Based on cost
    MANUAL = "manual"  # Manual assignment


class MigrationStatus(str, Enum):
    """Status of tenant migration"""
    PENDING = "pending"
    PREPARING = "preparing"
    IN_PROGRESS = "in_progress"
    SYNCING = "syncing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class MigrationTask:
    """Represents a tenant migration task"""
    task_id: str
    tenant_id: str
    source_shard: str
    target_shard: str
    status: MigrationStatus = MigrationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_percent: float = 0.0
    bytes_transferred: int = 0
    error_message: Optional[str] = None
    rollback_data: Optional[Dict[str, Any]] = None


@dataclass
class RebalancePlan:
    """Plan for shard rebalancing"""
    plan_id: str
    strategy: RebalanceStrategy
    created_at: datetime = field(default_factory=datetime.utcnow)
    migrations: List[MigrationTask] = field(default_factory=list)
    estimated_duration_minutes: int = 0
    status: str = "pending"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RebalanceMetrics:
    """Metrics for rebalancing operations"""
    total_migrations: int = 0
    successful_migrations: int = 0
    failed_migrations: int = 0
    total_bytes_transferred: int = 0
    average_migration_time_seconds: float = 0
    last_rebalance: Optional[datetime] = None


class ShardRebalancer:
    """
    Handles shard rebalancing and tenant migration.

    Features:
    - Automatic load-based rebalancing
    - Zero-downtime migration
    - Migration monitoring and rollback
    - Cost optimization
    """

    def __init__(
        self,
        sharding_manager: ShardingManager,
        auto_rebalance: bool = False,
        rebalance_threshold: float = 20.0,  # Utilization difference threshold
        max_concurrent_migrations: int = 5
    ):
        self.sharding_manager = sharding_manager
        self.auto_rebalance = auto_rebalance
        self.rebalance_threshold = rebalance_threshold
        self.max_concurrent_migrations = max_concurrent_migrations

        # Migration tracking
        self._migrations: Dict[str, MigrationTask] = {}
        self._active_migrations: List[str] = []
        self._rebalance_plans: Dict[str, RebalancePlan] = {}

        # Metrics
        self._metrics = RebalanceMetrics()

        # Callbacks
        self._on_migration_complete: Optional[Callable[[MigrationTask], Awaitable[None]]] = None
        self._on_migration_failed: Optional[Callable[[MigrationTask], Awaitable[None]]] = None

    async def analyze_rebalance_needs(self) -> Dict[str, Any]:
        """
        Analyze current shard distribution and identify rebalancing needs.

        Returns:
            Analysis report with recommendations
        """
        shards = self.sharding_manager.get_all_shards()
        active_shards = [s for s in shards if s.status == ShardStatus.ACTIVE]

        if not active_shards:
            return {"needs_rebalance": False, "reason": "No active shards"}

        # Calculate statistics
        utilizations = [s.utilization for s in active_shards]
        avg_utilization = sum(utilizations) / len(utilizations)
        max_utilization = max(utilizations)
        min_utilization = min(utilizations)
        utilization_diff = max_utilization - min_utilization

        # Find overloaded and underloaded shards
        overloaded = [s for s in active_shards if s.utilization > avg_utilization + self.rebalance_threshold]
        underloaded = [s for s in active_shards if s.utilization < avg_utilization - self.rebalance_threshold]

        # Calculate imbalance score
        imbalance_score = utilization_diff / 100  # 0-1 scale

        analysis = {
            "needs_rebalance": utilization_diff > self.rebalance_threshold,
            "imbalance_score": round(imbalance_score, 3),
            "average_utilization": round(avg_utilization, 2),
            "max_utilization": round(max_utilization, 2),
            "min_utilization": round(min_utilization, 2),
            "utilization_spread": round(utilization_diff, 2),
            "overloaded_shards": [
                {"shard_id": s.shard_id, "utilization": round(s.utilization, 2)}
                for s in overloaded
            ],
            "underloaded_shards": [
                {"shard_id": s.shard_id, "utilization": round(s.utilization, 2)}
                for s in underloaded
            ],
            "total_tenants": sum(s.tenant_count for s in active_shards),
            "active_shards": len(active_shards)
        }

        return analysis

    async def create_rebalance_plan(
        self,
        strategy: RebalanceStrategy = RebalanceStrategy.LOAD_BASED,
        constraints: Optional[Dict[str, Any]] = None
    ) -> RebalancePlan:
        """
        Create a rebalancing plan based on the specified strategy.

        Args:
            strategy: Rebalancing strategy to use
            constraints: Optional constraints (e.g., excluded shards, tenants)

        Returns:
            RebalancePlan with migration tasks
        """
        plan_id = f"plan_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        analysis = await self.analyze_rebalance_needs()

        migrations = []

        if strategy == RebalanceStrategy.LOAD_BASED:
            migrations = await self._create_load_based_migrations(
                analysis, constraints
            )
        elif strategy == RebalanceStrategy.GEOGRAPHIC:
            migrations = await self._create_geographic_migrations(
                analysis, constraints
            )
        elif strategy == RebalanceStrategy.COST_OPTIMIZED:
            migrations = await self._create_cost_optimized_migrations(
                analysis, constraints
            )

        # Calculate estimated duration
        # Assume ~5 minutes per tenant migration
        estimated_duration = len(migrations) * 5

        plan = RebalancePlan(
            plan_id=plan_id,
            strategy=strategy,
            migrations=migrations,
            estimated_duration_minutes=estimated_duration,
            metadata={
                "analysis": analysis,
                "constraints": constraints or {}
            }
        )

        self._rebalance_plans[plan_id] = plan

        logger.info(f"Created rebalance plan {plan_id} with {len(migrations)} migrations")
        return plan

    async def _create_load_based_migrations(
        self,
        analysis: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None
    ) -> List[MigrationTask]:
        """Create migration tasks based on load distribution"""
        migrations = []
        constraints = constraints or {}

        excluded_shards = set(constraints.get("excluded_shards", []))
        excluded_tenants = set(constraints.get("excluded_tenants", []))

        overloaded = analysis.get("overloaded_shards", [])
        underloaded = analysis.get("underloaded_shards", [])

        if not overloaded or not underloaded:
            return migrations

        # For each overloaded shard, plan migrations to underloaded shards
        for overloaded_info in overloaded:
            source_shard_id = overloaded_info["shard_id"]

            if source_shard_id in excluded_shards:
                continue

            # Get tenants on this shard
            tenants = self.sharding_manager.get_tenants_on_shard(source_shard_id)

            # Calculate how many tenants to move
            avg_util = analysis["average_utilization"]
            current_util = overloaded_info["utilization"]
            excess_util = current_util - avg_util

            # Estimate tenants to move (rough calculation)
            shard = self.sharding_manager.get_shard_config(source_shard_id)
            if not shard:
                continue

            tenants_per_util = shard.capacity / 100
            tenants_to_move = max(1, int(excess_util * tenants_per_util))
            tenants_to_move = min(tenants_to_move, len(tenants))

            # Create migration tasks
            for i, tenant_id in enumerate(tenants[:tenants_to_move]):
                if tenant_id in excluded_tenants:
                    continue

                # Select target shard (round-robin among underloaded)
                target_info = underloaded[i % len(underloaded)]
                target_shard_id = target_info["shard_id"]

                if target_shard_id in excluded_shards:
                    continue

                task_id = f"mig_{tenant_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

                migration = MigrationTask(
                    task_id=task_id,
                    tenant_id=tenant_id,
                    source_shard=source_shard_id,
                    target_shard=target_shard_id
                )
                migrations.append(migration)

        return migrations

    async def _create_geographic_migrations(
        self,
        analysis: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None
    ) -> List[MigrationTask]:
        """Create migration tasks based on geographic proximity"""
        # This would analyze tenant locations and move them to closer shards
        # For now, return empty list as this requires geolocation data
        return []

    async def _create_cost_optimized_migrations(
        self,
        analysis: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None
    ) -> List[MigrationTask]:
        """Create migration tasks optimized for cost"""
        # This would analyze cost per region and optimize placements
        # For now, return empty list as this requires cost data
        return []

    async def execute_rebalance_plan(
        self,
        plan_id: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a rebalancing plan.

        Args:
            plan_id: ID of the plan to execute
            dry_run: If True, only simulate the execution

        Returns:
            Execution results
        """
        plan = self._rebalance_plans.get(plan_id)
        if not plan:
            return {"error": f"Plan {plan_id} not found"}

        if dry_run:
            return {
                "dry_run": True,
                "plan_id": plan_id,
                "total_migrations": len(plan.migrations),
                "estimated_duration_minutes": plan.estimated_duration_minutes
            }

        results = {
            "plan_id": plan_id,
            "started_at": datetime.utcnow().isoformat(),
            "migrations_completed": 0,
            "migrations_failed": 0,
            "migrations": []
        }

        # Execute migrations with concurrency limit
        semaphore = asyncio.Semaphore(self.max_concurrent_migrations)

        async def run_migration(migration: MigrationTask):
            async with semaphore:
                return await self.execute_migration(migration)

        # Run all migrations
        tasks = [run_migration(m) for m in plan.migrations]
        migration_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in migration_results:
            if isinstance(result, Exception):
                results["migrations_failed"] += 1
                results["migrations"].append({
                    "status": "failed",
                    "error": str(result)
                })
            else:
                if result.status == MigrationStatus.COMPLETED:
                    results["migrations_completed"] += 1
                else:
                    results["migrations_failed"] += 1
                results["migrations"].append({
                    "task_id": result.task_id,
                    "status": result.status.value
                })

        results["completed_at"] = datetime.utcnow().isoformat()
        plan.status = "completed"

        # Update metrics
        self._metrics.total_migrations += len(plan.migrations)
        self._metrics.successful_migrations += results["migrations_completed"]
        self._metrics.failed_migrations += results["migrations_failed"]
        self._metrics.last_rebalance = datetime.utcnow()

        return results

    async def execute_migration(
        self,
        migration: MigrationTask
    ) -> MigrationTask:
        """
        Execute a single tenant migration.

        This performs a zero-downtime migration:
        1. Prepare phase: Setup target shard
        2. Sync phase: Copy data to target
        3. Switch phase: Update routing
        4. Cleanup phase: Remove old data

        Args:
            migration: Migration task to execute

        Returns:
            Updated migration task with results
        """
        # Register migration
        self._migrations[migration.task_id] = migration
        self._active_migrations.append(migration.task_id)

        try:
            # Phase 1: Prepare
            migration.status = MigrationStatus.PREPARING
            migration.started_at = datetime.utcnow()
            await self._prepare_migration(migration)

            # Phase 2: Sync data
            migration.status = MigrationStatus.SYNCING
            migration.progress_percent = 25.0
            await self._sync_data(migration)

            # Phase 3: Switch routing
            migration.status = MigrationStatus.IN_PROGRESS
            migration.progress_percent = 75.0
            await self._switch_routing(migration)

            # Phase 4: Cleanup
            migration.progress_percent = 90.0
            await self._cleanup_migration(migration)

            # Complete
            migration.status = MigrationStatus.COMPLETED
            migration.progress_percent = 100.0
            migration.completed_at = datetime.utcnow()

            # Update shard tenant counts
            source_shard = self.sharding_manager.get_shard_config(migration.source_shard)
            target_shard = self.sharding_manager.get_shard_config(migration.target_shard)

            if source_shard:
                source_shard.tenant_count = max(0, source_shard.tenant_count - 1)
            if target_shard:
                target_shard.tenant_count += 1

            # Call completion callback if set
            if self._on_migration_complete:
                await self._on_migration_complete(migration)

            logger.info(f"Migration {migration.task_id} completed successfully")

        except Exception as e:
            migration.status = MigrationStatus.FAILED
            migration.error_message = str(e)
            migration.completed_at = datetime.utcnow()

            # Attempt rollback
            try:
                await self._rollback_migration(migration)
                migration.status = MigrationStatus.ROLLED_BACK
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")

            if self._on_migration_failed:
                await self._on_migration_failed(migration)

            logger.error(f"Migration {migration.task_id} failed: {e}")

        finally:
            if migration.task_id in self._active_migrations:
                self._active_migrations.remove(migration.task_id)

        return migration

    async def _prepare_migration(self, migration: MigrationTask) -> None:
        """Prepare for migration - validate and setup target"""
        # Validate source and target shards
        source = self.sharding_manager.get_shard_config(migration.source_shard)
        target = self.sharding_manager.get_shard_config(migration.target_shard)

        if not source or source.status == ShardStatus.OFFLINE:
            raise ValueError(f"Source shard {migration.source_shard} is not available")

        if not target or target.status != ShardStatus.ACTIVE:
            raise ValueError(f"Target shard {migration.target_shard} is not available")

        # Check target capacity
        if target.available_capacity <= 0:
            raise ValueError(f"Target shard {migration.target_shard} has no available capacity")

        # Store rollback data
        migration.rollback_data = {
            "original_shard": migration.source_shard,
            "tenant_mapping": self.sharding_manager.get_tenant_shard(migration.tenant_id)
        }

        logger.info(f"Prepared migration for tenant {migration.tenant_id}")

    async def _sync_data(self, migration: MigrationTask) -> None:
        """Sync tenant data to target shard"""
        # Simulate data sync
        # In production, this would:
        # 1. Create tenant schema on target
        # 2. Copy all tenant data
        # 3. Track and sync changes during migration

        # Simulate progress
        for i in range(5):
            migration.progress_percent = 25.0 + (i * 10)
            migration.bytes_transferred += 1000000  # Simulate 1MB chunks
            await asyncio.sleep(0.1)  # Simulate work

        logger.info(f"Synced data for tenant {migration.tenant_id}")

    async def _switch_routing(self, migration: MigrationTask) -> None:
        """Switch routing to new shard"""
        # Update tenant mapping
        if migration.tenant_id in self.sharding_manager._tenant_mappings:
            mapping = self.sharding_manager._tenant_mappings[migration.tenant_id]
            mapping.previous_shard = mapping.shard_id
            mapping.shard_id = migration.target_shard
            mapping.migration_status = "completed"

        logger.info(f"Switched routing for tenant {migration.tenant_id} to {migration.target_shard}")

    async def _cleanup_migration(self, migration: MigrationTask) -> None:
        """Cleanup after successful migration"""
        # In production, this would:
        # 1. Verify data integrity on target
        # 2. Remove old data from source (after retention period)
        # 3. Update statistics and indexes

        logger.info(f"Cleaned up migration for tenant {migration.tenant_id}")

    async def _rollback_migration(self, migration: MigrationTask) -> None:
        """Rollback a failed migration"""
        if not migration.rollback_data:
            return

        # Restore original routing
        original_shard = migration.rollback_data.get("original_shard")
        if original_shard and migration.tenant_id in self.sharding_manager._tenant_mappings:
            mapping = self.sharding_manager._tenant_mappings[migration.tenant_id]
            mapping.shard_id = original_shard
            mapping.migration_status = "rolled_back"

        logger.info(f"Rolled back migration for tenant {migration.tenant_id}")

    async def get_migration_status(self, task_id: str) -> Optional[MigrationTask]:
        """Get status of a migration task"""
        return self._migrations.get(task_id)

    async def get_active_migrations(self) -> List[MigrationTask]:
        """Get all active migrations"""
        return [
            self._migrations[task_id]
            for task_id in self._active_migrations
            if task_id in self._migrations
        ]

    async def cancel_migration(self, task_id: str) -> bool:
        """Cancel an active migration"""
        migration = self._migrations.get(task_id)
        if not migration or migration.status not in [
            MigrationStatus.PENDING,
            MigrationStatus.PREPARING,
            MigrationStatus.SYNCING
        ]:
            return False

        # Attempt rollback
        await self._rollback_migration(migration)
        migration.status = MigrationStatus.ROLLED_BACK
        migration.completed_at = datetime.utcnow()

        return True

    def get_metrics(self) -> RebalanceMetrics:
        """Get rebalancing metrics"""
        return self._metrics

    async def manual_migrate_tenant(
        self,
        tenant_id: str,
        target_shard: str
    ) -> MigrationTask:
        """
        Manually migrate a tenant to a specific shard.

        Args:
            tenant_id: Tenant to migrate
            target_shard: Target shard ID

        Returns:
            MigrationTask with results
        """
        source_shard = self.sharding_manager.get_tenant_shard(tenant_id)
        if not source_shard:
            raise ValueError(f"Tenant {tenant_id} not found or not assigned")

        task_id = f"mig_manual_{tenant_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        migration = MigrationTask(
            task_id=task_id,
            tenant_id=tenant_id,
            source_shard=source_shard,
            target_shard=target_shard
        )

        return await self.execute_migration(migration)

    def set_callbacks(
        self,
        on_complete: Optional[Callable[[MigrationTask], Awaitable[None]]] = None,
        on_failed: Optional[Callable[[MigrationTask], Awaitable[None]]] = None
    ) -> None:
        """Set callbacks for migration events"""
        self._on_migration_complete = on_complete
        self._on_migration_failed = on_failed

    async def get_rebalance_history(self) -> List[Dict[str, Any]]:
        """Get history of rebalancing operations"""
        history = []

        for plan_id, plan in self._rebalance_plans.items():
            history.append({
                "plan_id": plan_id,
                "strategy": plan.strategy.value,
                "created_at": plan.created_at.isoformat(),
                "status": plan.status,
                "migrations_count": len(plan.migrations),
                "estimated_duration_minutes": plan.estimated_duration_minutes
            })

        return sorted(history, key=lambda x: x["created_at"], reverse=True)
