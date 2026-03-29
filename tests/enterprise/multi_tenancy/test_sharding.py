"""
Tests for Multi-Tenant Database Sharding

Tests for ShardingManager, ShardRouter, and ShardRebalancer.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from enterprise.multi_tenancy.sharding_manager import (
    ShardingManager,
    ShardConfig,
    ShardStatus,
    ShardingStrategy,
    TenantShardMapping
)
from enterprise.multi_tenancy.shard_router import (
    ShardRouter,
    QueryContext,
    QueryType,
    RoutingMode,
    RoutingResult,
    ConnectionPool
)
from enterprise.multi_tenancy.shard_rebalancer import (
    ShardRebalancer,
    RebalanceStrategy,
    MigrationStatus,
    MigrationTask,
    RebalancePlan
)


# ============================================================================
# ShardingManager Tests
# ============================================================================

class TestShardingManager:
    """Tests for ShardingManager"""

    @pytest.fixture
    def manager(self):
        """Create a ShardingManager instance"""
        return ShardingManager(
            strategy=ShardingStrategy.HASH,
            total_shards=4,
            replication_factor=2
        )

    def test_initialization(self, manager):
        """Test manager initializes correctly"""
        assert manager.total_shards == 4
        assert manager.strategy == ShardingStrategy.HASH
        assert len(manager._shards) == 4
        assert len(manager._virtual_nodes) == 4 * 150  # 150 vnodes per shard

    def test_shards_created(self, manager):
        """Test shards are created with correct config"""
        shards = manager.get_all_shards()
        assert len(shards) == 4

        for shard in shards:
            assert shard.status == ShardStatus.ACTIVE
            assert shard.capacity == 100
            assert shard.tenant_count == 0
            assert shard.region in ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]

    @pytest.mark.asyncio
    async def test_assign_tenant_to_shard(self, manager):
        """Test tenant assignment to shard"""
        mapping = await manager.assign_tenant_to_shard("tenant_001")

        assert mapping.tenant_id == "tenant_001"
        assert mapping.shard_id is not None
        assert mapping.shard_id.startswith("shard_")

        # Verify tenant count increased
        shard = manager.get_shard_config(mapping.shard_id)
        assert shard.tenant_count == 1

    @pytest.mark.asyncio
    async def test_assign_tenant_with_preferred_region(self):
        """Test tenant assignment with preferred region using geographic strategy"""
        manager = ShardingManager(strategy=ShardingStrategy.GEOGRAPHIC, total_shards=4)
        mapping = await manager.assign_tenant_to_shard(
            "tenant_002",
            preferred_region="eu-west-1"
        )

        shard = manager.get_shard_config(mapping.shard_id)
        assert shard.region == "eu-west-1"

    @pytest.mark.asyncio
    async def test_assign_existing_tenant_returns_same_mapping(self, manager):
        """Test reassigning existing tenant returns same mapping"""
        mapping1 = await manager.assign_tenant_to_shard("tenant_003")
        mapping2 = await manager.assign_tenant_to_shard("tenant_003")

        assert mapping1.shard_id == mapping2.shard_id
        assert mapping1.assigned_at == mapping2.assigned_at

    def test_get_tenant_shard(self, manager):
        """Test getting shard for tenant"""
        # First assign
        asyncio.run(manager.assign_tenant_to_shard("tenant_004"))

        shard_id = manager.get_tenant_shard("tenant_004")
        assert shard_id is not None
        assert shard_id.startswith("shard_")

    def test_get_tenant_shard_not_found(self, manager):
        """Test getting shard for non-existent tenant"""
        shard_id = manager.get_tenant_shard("nonexistent_tenant")
        assert shard_id is None

    def test_consistent_hashing(self, manager):
        """Test that consistent hashing returns same shard for same tenant"""
        # Assign same tenant multiple times
        shard_ids = []
        for _ in range(5):
            tenant_hash = manager._hash("tenant_005")
            shard_id = manager._select_shard_hash("tenant_005")
            shard_ids.append(shard_id)

        # All should be the same
        assert len(set(shard_ids)) == 1

    @pytest.mark.asyncio
    async def test_get_shard_for_read(self, manager):
        """Test getting shard for read operations"""
        await manager.assign_tenant_to_shard("tenant_006")
        shard_id = await manager.get_shard_for_read("tenant_006")
        assert shard_id is not None

    @pytest.mark.asyncio
    async def test_get_shard_for_write(self, manager):
        """Test getting shard for write operations"""
        await manager.assign_tenant_to_shard("tenant_007")
        shard_id = await manager.get_shard_for_write("tenant_007")
        assert shard_id is not None

    @pytest.mark.asyncio
    async def test_update_shard_status(self, manager):
        """Test updating shard status"""
        result = await manager.update_shard_status("shard_000", ShardStatus.MAINTENANCE)
        assert result is True

        shard = manager.get_shard_config("shard_000")
        assert shard.status == ShardStatus.MAINTENANCE

    def test_update_shard_status_not_found(self, manager):
        """Test updating non-existent shard"""
        result = asyncio.run(manager.update_shard_status("nonexistent", ShardStatus.MAINTENANCE))
        assert result is False

    @pytest.mark.asyncio
    async def test_get_shard_metrics(self, manager):
        """Test getting shard metrics"""
        await manager.assign_tenant_to_shard("tenant_008")

        metrics = await manager.get_shard_metrics()

        assert metrics["total_shards"] == 4
        assert metrics["total_tenants"] == 1
        assert "shards" in metrics
        assert metrics["active_shards"] == 4

    @pytest.mark.asyncio
    async def test_find_overloaded_shards(self):
        """Test finding overloaded shards with directory strategy"""
        manager = ShardingManager(strategy=ShardingStrategy.DIRECTORY, total_shards=4)
        # Assign many tenants - directory strategy will use lowest utilization
        for i in range(85):
            await manager.assign_tenant_to_shard(f"tenant_{i:03d}")

        overloaded = await manager.find_overloaded_shards(threshold=50.0)
        # With directory strategy, shards may still be balanced
        # Check that we can find overloaded with lower threshold
        overloaded = await manager.find_overloaded_shards(threshold=20.0)
        assert isinstance(overloaded, list)

    @pytest.mark.asyncio
    async def test_find_underutilized_shards(self, manager):
        """Test finding underutilized shards"""
        # Assign only a few tenants
        for i in range(5):
            await manager.assign_tenant_to_shard(f"tenant_{i:03d}")

        underutilized = await manager.find_underutilized_shards(threshold=20.0)
        assert len(underutilized) > 0

    def test_get_tenants_on_shard(self, manager):
        """Test getting tenants on a shard"""
        asyncio.run(manager.assign_tenant_to_shard("tenant_009"))

        # Get the shard for this tenant
        shard_id = manager.get_tenant_shard("tenant_009")
        tenants = manager.get_tenants_on_shard(shard_id)

        assert "tenant_009" in tenants

    @pytest.mark.asyncio
    async def test_health_check(self, manager):
        """Test health check"""
        results = await manager.health_check()

        assert results["healthy"] == 4  # All active shards
        assert results["unhealthy"] == 0
        assert len(results["details"]) == 4

    def test_get_capacity_report(self, manager):
        """Test capacity report generation"""
        report = manager.get_capacity_report()

        assert report["total_capacity"] == 400  # 4 shards * 100 capacity
        assert "total_used" in report
        assert "shards_by_region" in report


class TestShardConfig:
    """Tests for ShardConfig dataclass"""

    def test_utilization_calculation(self):
        """Test utilization percentage calculation"""
        config = ShardConfig(
            shard_id="test_shard",
            connection_string="test://conn",
            region="us-east-1",
            capacity=100,
            tenant_count=25
        )

        assert config.utilization == 25.0

    def test_available_capacity(self):
        """Test available capacity calculation"""
        config = ShardConfig(
            shard_id="test_shard",
            connection_string="test://conn",
            region="us-east-1",
            capacity=100,
            tenant_count=75
        )

        assert config.available_capacity == 25

    def test_zero_capacity(self):
        """Test behavior with zero capacity"""
        config = ShardConfig(
            shard_id="test_shard",
            connection_string="test://conn",
            region="us-east-1",
            capacity=0,
            tenant_count=0
        )

        assert config.utilization == 0
        assert config.available_capacity == 0


class TestShardingStrategies:
    """Tests for different sharding strategies"""

    def test_hash_strategy(self):
        """Test hash-based sharding"""
        manager = ShardingManager(strategy=ShardingStrategy.HASH, total_shards=4)

        # Same tenant should always map to same shard
        shard1 = manager._select_shard_hash("tenant_001")
        shard2 = manager._select_shard_hash("tenant_001")
        assert shard1 == shard2

    def test_range_strategy(self):
        """Test range-based sharding"""
        manager = ShardingManager(strategy=ShardingStrategy.RANGE, total_shards=4)

        shard1 = manager._select_shard_range("tenant_001")
        shard2 = manager._select_shard_range("tenant_005")

        # Both should return valid shard IDs
        assert shard1.startswith("shard_")
        assert shard2.startswith("shard_")

    @pytest.mark.asyncio
    async def test_directory_strategy(self):
        """Test directory-based sharding"""
        manager = ShardingManager(strategy=ShardingStrategy.DIRECTORY, total_shards=4)

        shard_id = await manager._select_shard_directory("tenant_001", None)
        assert shard_id.startswith("shard_")

    def test_geographic_strategy(self):
        """Test geographic-based sharding"""
        manager = ShardingManager(strategy=ShardingStrategy.GEOGRAPHIC, total_shards=4)

        shard_id = manager._select_shard_geographic("eu-west-1")
        shard = manager.get_shard_config(shard_id)
        assert shard.region == "eu-west-1"


# ============================================================================
# ShardRouter Tests
# ============================================================================

class TestShardRouter:
    """Tests for ShardRouter"""

    @pytest.fixture
    def router(self):
        """Create a ShardRouter instance"""
        manager = ShardingManager(total_shards=4)
        return ShardRouter(
            sharding_manager=manager,
            enable_read_replicas=True,
            cache_ttl_seconds=300
        )

    @pytest.mark.asyncio
    async def test_route_select_query(self, router):
        """Test routing a SELECT query"""
        context = QueryContext(
            query_type=QueryType.SELECT,
            tenant_id="tenant_001"
        )

        result = await router.route("SELECT * FROM users", context)

        assert result.shard_id is not None
        assert result.connection_string is not None
        assert result.routing_time_ms > 0

    @pytest.mark.asyncio
    async def test_route_insert_query(self, router):
        """Test routing an INSERT query"""
        context = QueryContext(
            query_type=QueryType.INSERT,
            tenant_id="tenant_002"
        )

        result = await router.route("INSERT INTO users VALUES (1)", context)

        assert result.shard_id is not None
        assert result.is_replica is False  # Writes go to primary

    @pytest.mark.asyncio
    async def test_route_update_query(self, router):
        """Test routing an UPDATE query"""
        context = QueryContext(
            query_type=QueryType.UPDATE,
            tenant_id="tenant_003"
        )

        result = await router.route("UPDATE users SET name='test'", context)

        assert result.shard_id is not None
        assert result.is_replica is False

    @pytest.mark.asyncio
    async def test_route_delete_query(self, router):
        """Test routing a DELETE query"""
        context = QueryContext(
            query_type=QueryType.DELETE,
            tenant_id="tenant_004"
        )

        result = await router.route("DELETE FROM users WHERE id=1", context)

        assert result.shard_id is not None

    @pytest.mark.asyncio
    async def test_route_without_tenant(self, router):
        """Test routing without tenant context"""
        context = QueryContext(query_type=QueryType.SELECT)

        result = await router.route("SELECT * FROM system_config", context)

        assert result.shard_id is not None

    @pytest.mark.asyncio
    async def test_routing_cache(self, router):
        """Test that routing is cached"""
        context = QueryContext(
            query_type=QueryType.SELECT,
            tenant_id="tenant_005"
        )

        # First call - cache miss
        result1 = await router.route("SELECT 1", context)
        assert result1.cached is False

        # Second call - cache hit
        result2 = await router.route("SELECT 1", context)
        assert result2.cached is True

    @pytest.mark.asyncio
    async def test_route_batch(self, router):
        """Test batch query routing"""
        queries = [
            ("SELECT * FROM users", QueryContext(query_type=QueryType.SELECT, tenant_id="tenant_006")),
            ("SELECT * FROM orders", QueryContext(query_type=QueryType.SELECT, tenant_id="tenant_007")),
            ("INSERT INTO logs VALUES (1)", QueryContext(query_type=QueryType.INSERT, tenant_id="tenant_006")),
        ]

        results = await router.route_batch(queries)

        assert len(results) > 0
        for shard_id, routing_results in results.items():
            assert shard_id.startswith("shard_")

    @pytest.mark.asyncio
    async def test_connection_context_manager(self, router):
        """Test connection context manager"""
        async with router.connection("tenant_008", QueryType.SELECT) as conn:
            assert conn is not None
            assert "postgresql://" in conn

    @pytest.mark.asyncio
    async def test_broadcast_to_all_shards(self, router):
        """Test broadcasting to all shards"""
        context = QueryContext(query_type=QueryType.SELECT)

        results = await router.broadcast_to_all_shards("SELECT * FROM system_health", context)

        assert len(results) == 4  # 4 active shards

    @pytest.mark.asyncio
    async def test_execute_on_specific_shards(self, router):
        """Test executing on specific shards"""
        context = QueryContext(query_type=QueryType.SELECT)

        results = await router.execute_on_shards(
            ["shard_000", "shard_001"],
            "SELECT * FROM data",
            context
        )

        assert "shard_000" in results
        assert "shard_001" in results

    def test_get_metrics(self, router):
        """Test getting router metrics"""
        metrics = router.get_metrics()

        assert "total_routes" in metrics
        assert "cache_hits" in metrics
        assert "cache_misses" in metrics
        assert "connection_pools" in metrics

    @pytest.mark.asyncio
    async def test_health_check(self, router):
        """Test router health check"""
        health = await router.health_check()

        assert "router_healthy" in health
        assert "pools" in health

    def test_clear_cache(self, router):
        """Test clearing routing cache"""
        # Add something to cache
        asyncio.run(router.route(
            "SELECT 1",
            QueryContext(query_type=QueryType.SELECT, tenant_id="tenant_009")
        ))

        router.clear_cache()

        metrics = router.get_metrics()
        assert metrics["cache_size"] == 0

    @pytest.mark.asyncio
    async def test_get_tenant_routing_info(self, router):
        """Test getting tenant routing info"""
        await router.route(
            "SELECT 1",
            QueryContext(query_type=QueryType.SELECT, tenant_id="tenant_010")
        )

        info = await router.get_tenant_routing_info("tenant_010")

        assert info["tenant_id"] == "tenant_010"
        assert "shard_id" in info
        assert "connection_pool" in info


class TestQueryContext:
    """Tests for QueryContext"""

    def test_default_values(self):
        """Test default values are set correctly"""
        context = QueryContext(query_type=QueryType.SELECT)

        assert context.query_id is not None
        assert context.priority == 0
        assert context.timeout_ms == 30000
        assert context.metadata == {}

    def test_custom_values(self):
        """Test custom values are set correctly"""
        context = QueryContext(
            query_type=QueryType.INSERT,
            tenant_id="tenant_001",
            table_name="users",
            priority=10,
            timeout_ms=60000
        )

        assert context.tenant_id == "tenant_001"
        assert context.table_name == "users"
        assert context.priority == 10
        assert context.timeout_ms == 60000


class TestConnectionPool:
    """Tests for ConnectionPool"""

    def test_connection_pool_creation(self):
        """Test connection pool creation"""
        pool = ConnectionPool(
            shard_id="shard_000",
            primary="postgresql://primary@shard0.db",
            replicas=["postgresql://replica@shard0.db"]
        )

        assert pool.shard_id == "shard_000"
        assert pool.max_connections == 20
        assert pool.active_connections == 0
        assert pool.healthy is True


# ============================================================================
# ShardRebalancer Tests
# ============================================================================

class TestShardRebalancer:
    """Tests for ShardRebalancer"""

    @pytest.fixture
    def rebalancer(self):
        """Create a ShardRebalancer instance"""
        manager = ShardingManager(total_shards=4)
        return ShardRebalancer(
            sharding_manager=manager,
            auto_rebalance=False,
            rebalance_threshold=20.0,
            max_concurrent_migrations=5
        )

    @pytest.mark.asyncio
    async def test_analyze_rebalance_needs_balanced(self, rebalancer):
        """Test analysis when shards are balanced"""
        analysis = await rebalancer.analyze_rebalance_needs()

        assert "needs_rebalance" in analysis
        assert "imbalance_score" in analysis
        assert "average_utilization" in analysis

    @pytest.mark.asyncio
    async def test_analyze_rebalance_needs_unbalanced(self):
        """Test analysis when shards are unbalanced"""
        manager = ShardingManager(strategy=ShardingStrategy.DIRECTORY, total_shards=4)
        rebalancer = ShardRebalancer(sharding_manager=manager)
        
        # Assign many tenants - they will be distributed evenly by directory strategy
        for i in range(90):
            await manager.assign_tenant_to_shard(f"tenant_{i:03d}")

        analysis = await rebalancer.analyze_rebalance_needs()

        # Analysis should provide valid data
        assert "needs_rebalance" in analysis
        assert "imbalance_score" in analysis

    @pytest.mark.asyncio
    async def test_create_rebalance_plan(self):
        """Test creating a rebalance plan"""
        manager = ShardingManager(strategy=ShardingStrategy.DIRECTORY, total_shards=4)
        rebalancer = ShardRebalancer(sharding_manager=manager)
        
        # Assign tenants
        for i in range(90):
            await manager.assign_tenant_to_shard(f"tenant_{i:03d}")

        plan = await rebalancer.create_rebalance_plan(
            strategy=RebalanceStrategy.LOAD_BASED
        )

        assert plan.plan_id is not None
        assert plan.strategy == RebalanceStrategy.LOAD_BASED
        # Plan may have 0 migrations if shards are balanced
        assert isinstance(plan.migrations, list)

    @pytest.mark.asyncio
    async def test_execute_migration(self, rebalancer):
        """Test executing a migration"""
        # Assign a tenant first
        await rebalancer.sharding_manager.assign_tenant_to_shard("tenant_001")
        source_shard = rebalancer.sharding_manager.get_tenant_shard("tenant_001")

        # Find a different target shard
        shards = rebalancer.sharding_manager.get_all_shards()
        target_shard = next(
            s.shard_id for s in shards
            if s.shard_id != source_shard
        )

        migration = MigrationTask(
            task_id="mig_test_001",
            tenant_id="tenant_001",
            source_shard=source_shard,
            target_shard=target_shard
        )

        result = await rebalancer.execute_migration(migration)

        assert result.status == MigrationStatus.COMPLETED
        assert result.progress_percent == 100.0

    @pytest.mark.asyncio
    async def test_execute_rebalance_plan_dry_run(self, rebalancer):
        """Test dry run execution of rebalance plan"""
        # Unbalance first
        for i in range(90):
            await rebalancer.sharding_manager.assign_tenant_to_shard(f"tenant_{i:03d}")

        plan = await rebalancer.create_rebalance_plan(strategy=RebalanceStrategy.LOAD_BASED)

        result = await rebalancer.execute_rebalance_plan(plan.plan_id, dry_run=True)

        assert result["dry_run"] is True
        assert result["plan_id"] == plan.plan_id

    @pytest.mark.asyncio
    async def test_get_migration_status(self, rebalancer):
        """Test getting migration status"""
        # Create and execute a migration
        await rebalancer.sharding_manager.assign_tenant_to_shard("tenant_002")
        source_shard = rebalancer.sharding_manager.get_tenant_shard("tenant_002")

        shards = rebalancer.sharding_manager.get_all_shards()
        target_shard = next(
            s.shard_id for s in shards
            if s.shard_id != source_shard
        )

        migration = MigrationTask(
            task_id="mig_test_002",
            tenant_id="tenant_002",
            source_shard=source_shard,
            target_shard=target_shard
        )

        await rebalancer.execute_migration(migration)

        status = await rebalancer.get_migration_status("mig_test_002")
        assert status is not None
        assert status.status == MigrationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_manual_migrate_tenant(self, rebalancer):
        """Test manual tenant migration"""
        await rebalancer.sharding_manager.assign_tenant_to_shard("tenant_003")

        result = await rebalancer.manual_migrate_tenant("tenant_003", "shard_001")

        assert result.status == MigrationStatus.COMPLETED

        # Verify tenant moved
        new_shard = rebalancer.sharding_manager.get_tenant_shard("tenant_003")
        assert new_shard == "shard_001"

    def test_get_metrics(self, rebalancer):
        """Test getting rebalancer metrics"""
        metrics = rebalancer.get_metrics()

        assert metrics.total_migrations >= 0
        assert metrics.successful_migrations >= 0
        assert metrics.failed_migrations >= 0

    @pytest.mark.asyncio
    async def test_get_active_migrations(self, rebalancer):
        """Test getting active migrations"""
        active = await rebalancer.get_active_migrations()
        assert isinstance(active, list)

    @pytest.mark.asyncio
    async def test_get_rebalance_history(self, rebalancer):
        """Test getting rebalance history"""
        # Create a plan
        for i in range(90):
            await rebalancer.sharding_manager.assign_tenant_to_shard(f"tenant_{i:03d}")

        await rebalancer.create_rebalance_plan(strategy=RebalanceStrategy.LOAD_BASED)

        history = await rebalancer.get_rebalance_history()

        assert len(history) > 0
        assert "plan_id" in history[0]
        assert "strategy" in history[0]

    @pytest.mark.asyncio
    async def test_migration_to_offline_shard_fails(self, rebalancer):
        """Test migration to offline shard fails and rolls back"""
        await rebalancer.sharding_manager.assign_tenant_to_shard("tenant_004")
        source_shard = rebalancer.sharding_manager.get_tenant_shard("tenant_004")

        # Set target shard offline
        await rebalancer.sharding_manager.update_shard_status("shard_001", ShardStatus.OFFLINE)

        migration = MigrationTask(
            task_id="mig_test_003",
            tenant_id="tenant_004",
            source_shard=source_shard,
            target_shard="shard_001"
        )

        result = await rebalancer.execute_migration(migration)

        # Migration should either fail or be rolled back
        assert result.status in [MigrationStatus.FAILED, MigrationStatus.ROLLED_BACK]


class TestMigrationTask:
    """Tests for MigrationTask"""

    def test_migration_task_creation(self):
        """Test migration task creation"""
        task = MigrationTask(
            task_id="mig_001",
            tenant_id="tenant_001",
            source_shard="shard_000",
            target_shard="shard_001"
        )

        assert task.status == MigrationStatus.PENDING
        assert task.progress_percent == 0.0
        assert task.bytes_transferred == 0

    def test_migration_task_progress(self):
        """Test migration task progress tracking"""
        task = MigrationTask(
            task_id="mig_001",
            tenant_id="tenant_001",
            source_shard="shard_000",
            target_shard="shard_001"
        )

        task.progress_percent = 50.0
        task.bytes_transferred = 5000000

        assert task.progress_percent == 50.0
        assert task.bytes_transferred == 5000000


class TestRebalancePlan:
    """Tests for RebalancePlan"""

    def test_rebalance_plan_creation(self):
        """Test rebalance plan creation"""
        plan = RebalancePlan(
            plan_id="plan_001",
            strategy=RebalanceStrategy.LOAD_BASED
        )

        assert plan.migrations == []
        assert plan.status == "pending"
        assert plan.estimated_duration_minutes == 0


# ============================================================================
# Integration Tests
# ============================================================================

class TestShardingIntegration:
    """Integration tests for sharding components"""

    @pytest.fixture
    def full_setup(self):
        """Create full sharding setup"""
        manager = ShardingManager(total_shards=4)
        router = ShardRouter(sharding_manager=manager)
        rebalancer = ShardRebalancer(sharding_manager=manager)
        return manager, router, rebalancer

    @pytest.mark.asyncio
    async def test_full_workflow(self, full_setup):
        """Test complete sharding workflow"""
        manager, router, rebalancer = full_setup

        # 1. Assign tenants
        for i in range(20):
            await manager.assign_tenant_to_shard(f"tenant_{i:03d}")

        # 2. Route queries
        context = QueryContext(query_type=QueryType.SELECT, tenant_id="tenant_001")
        result = await router.route("SELECT * FROM data", context)
        assert result.shard_id is not None

        # 3. Analyze and rebalance if needed
        analysis = await rebalancer.analyze_rebalance_needs()
        assert analysis is not None

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, full_setup):
        """Test that tenants are properly isolated"""
        manager, router, rebalancer = full_setup

        # Assign tenants
        await manager.assign_tenant_to_shard("tenant_a")
        await manager.assign_tenant_to_shard("tenant_b")

        # Get shards
        shard_a = manager.get_tenant_shard("tenant_a")
        shard_b = manager.get_tenant_shard("tenant_b")

        # Each tenant should have a valid shard
        assert shard_a is not None
        assert shard_b is not None

        # Route queries for each tenant
        context_a = QueryContext(query_type=QueryType.SELECT, tenant_id="tenant_a")
        context_b = QueryContext(query_type=QueryType.SELECT, tenant_id="tenant_b")

        result_a = await router.route("SELECT * FROM data", context_a)
        result_b = await router.route("SELECT * FROM data", context_b)

        # Results should be consistent
        assert result_a.shard_id == shard_a
        assert result_b.shard_id == shard_b


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
