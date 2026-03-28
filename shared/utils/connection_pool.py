"""
Connection Pool Manager for PARWA Performance Optimization.

Week 26 - Builder 2: Query Optimization + Connection Pooling
Target: Handle 500 concurrent connections efficiently

Features:
- Async connection pool (asyncpg)
- Pool size: 20 connections, max overflow: 10
- Connection health checks
- Pool metrics monitoring
- Connection reuse optimization
"""

import asyncio
import time
import logging
from typing import Any, Optional, Dict, List, Callable
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from functools import wraps
import threading

logger = logging.getLogger(__name__)


@dataclass
class PoolMetrics:
    """Connection pool metrics."""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    waiting_requests: int = 0
    total_acquisitions: int = 0
    total_releases: int = 0
    acquisition_time_ms: float = 0.0
    avg_acquisition_time_ms: float = 0.0
    connection_errors: int = 0
    last_error: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class MockConnection:
    """Mock database connection for testing."""

    def __init__(self, conn_id: int):
        self.conn_id = conn_id
        self._closed = False
        self._transaction = None

    async def execute(self, query: str, *args) -> str:
        """Execute a query."""
        if self._closed:
            raise RuntimeError("Connection is closed")
        await asyncio.sleep(0.001)  # Simulate query time
        return "OK"

    async def fetch(self, query: str, *args) -> List[Dict]:
        """Fetch rows."""
        if self._closed:
            raise RuntimeError("Connection is closed")
        await asyncio.sleep(0.001)  # Simulate query time
        return []

    async def fetchrow(self, query: str, *args) -> Optional[Dict]:
        """Fetch a single row."""
        if self._closed:
            raise RuntimeError("Connection is closed")
        await asyncio.sleep(0.001)  # Simulate query time
        return {}

    async def fetchval(self, query: str, *args) -> Any:
        """Fetch a single value."""
        if self._closed:
            raise RuntimeError("Connection is closed")
        await asyncio.sleep(0.001)  # Simulate query time
        return None

    async def begin(self):
        """Begin a transaction."""
        self._transaction = True
        return self

    async def commit(self):
        """Commit the transaction."""
        self._transaction = None

    async def rollback(self):
        """Rollback the transaction."""
        self._transaction = None

    async def close(self):
        """Close the connection."""
        self._closed = True

    def is_closed(self) -> bool:
        """Check if connection is closed."""
        return self._closed


class ConnectionPool:
    """
    Async connection pool for PostgreSQL database connections.

    Features:
    - Configurable pool size with overflow
    - Connection health checks
    - Automatic reconnection
    - Metrics collection
    """

    def __init__(
        self,
        pool_size: int = 20,
        max_overflow: int = 10,
        connection_timeout: float = 30.0,
        idle_timeout: float = 300.0,
        health_check_interval: float = 60.0,
        database_url: Optional[str] = None
    ):
        """
        Initialize connection pool.

        Args:
            pool_size: Base pool size.
            max_overflow: Maximum additional connections.
            connection_timeout: Timeout for acquiring connection.
            idle_timeout: Timeout for idle connections.
            health_check_interval: Interval for health checks.
            database_url: Database connection URL.
        """
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.max_connections = pool_size + max_overflow
        self.connection_timeout = connection_timeout
        self.idle_timeout = idle_timeout
        self.health_check_interval = health_check_interval
        self.database_url = database_url

        self._pool: List[Any] = []
        self._active: Dict[int, Any] = {}
        self._semaphore = asyncio.Semaphore(self.max_connections)
        self._lock = asyncio.Lock()
        self._metrics = PoolMetrics()
        self._conn_counter = 0
        self._health_check_task: Optional[asyncio.Task] = None
        self._closed = False

    async def initialize(self) -> None:
        """Initialize the connection pool."""
        async with self._lock:
            for _ in range(self.pool_size):
                conn = await self._create_connection()
                self._pool.append(conn)

            self._metrics.total_connections = len(self._pool)
            self._metrics.idle_connections = len(self._pool)

            # Start health check task
            self._health_check_task = asyncio.create_task(
                self._health_check_loop()
            )

            logger.info(
                f"Connection pool initialized with {len(self._pool)} connections"
            )

    async def _create_connection(self) -> MockConnection:
        """
        Create a new database connection.

        Returns:
            Database connection.
        """
        self._conn_counter += 1
        # In production, this would use asyncpg.connect(self.database_url)
        return MockConnection(self._conn_counter)

    async def _health_check_loop(self) -> None:
        """Periodic health check for connections."""
        while not self._closed:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._check_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _check_connections(self) -> None:
        """Check health of all connections."""
        async with self._lock:
            unhealthy = []

            for i, conn in enumerate(self._pool):
                try:
                    # Simple health check query
                    await conn.execute("SELECT 1")
                except Exception:
                    unhealthy.append(i)

            # Replace unhealthy connections
            for i in unhealthy:
                try:
                    await self._pool[i].close()
                except Exception:
                    pass
                self._pool[i] = await self._create_connection()
                self._metrics.connection_errors += 1

            if unhealthy:
                logger.warning(
                    f"Replaced {len(unhealthy)} unhealthy connections"
                )

    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a connection from the pool.

        Yields:
            Database connection.

        Raises:
            TimeoutError: If connection cannot be acquired within timeout.
        """
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        start_time = time.time()
        conn = None

        try:
            # Wait for available slot
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.connection_timeout
            )

            async with self._lock:
                # Try to get from pool
                if self._pool:
                    conn = self._pool.pop()
                    self._metrics.idle_connections = len(self._pool)
                else:
                    # Create new connection (overflow)
                    conn = await self._create_connection()
                    self._metrics.total_connections += 1

                conn_id = id(conn)
                self._active[conn_id] = conn
                self._metrics.active_connections = len(self._active)
                self._metrics.total_acquisitions += 1

                # Update acquisition time
                acquisition_time = (time.time() - start_time) * 1000
                self._metrics.acquisition_time_ms = acquisition_time
                # Update rolling average
                n = self._metrics.total_acquisitions
                prev_avg = self._metrics.avg_acquisition_time_ms
                self._metrics.avg_acquisition_time_ms = (
                    prev_avg * (n - 1) + acquisition_time
                ) / n

            yield conn

        finally:
            # Return connection to pool
            if conn is not None:
                async with self._lock:
                    conn_id = id(conn)
                    if conn_id in self._active:
                        del self._active[conn_id]

                    # Check if we should return to pool or close
                    if (
                        len(self._pool) < self.pool_size
                        and not conn.is_closed()
                    ):
                        self._pool.append(conn)
                    else:
                        try:
                            await conn.close()
                        except Exception:
                            pass
                        self._metrics.total_connections -= 1

                    self._metrics.active_connections = len(self._active)
                    self._metrics.idle_connections = len(self._pool)
                    self._metrics.total_releases += 1

                self._semaphore.release()

    async def execute(self, query: str, *args) -> str:
        """
        Execute a query using a connection from the pool.

        Args:
            query: SQL query string.
            *args: Query parameters.

        Returns:
            Query result.
        """
        async with self.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> List[Dict]:
        """
        Fetch rows using a connection from the pool.

        Args:
            query: SQL query string.
            *args: Query parameters.

        Returns:
            List of rows.
        """
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> Optional[Dict]:
        """
        Fetch a single row using a connection from the pool.

        Args:
            query: SQL query string.
            *args: Query parameters.

        Returns:
            Row or None.
        """
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args) -> Any:
        """
        Fetch a single value using a connection from the pool.

        Args:
            query: SQL query string.
            *args: Query parameters.

        Returns:
            Value or None.
        """
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)

    def get_metrics(self) -> PoolMetrics:
        """
        Get pool metrics.

        Returns:
            PoolMetrics instance.
        """
        return self._metrics

    async def close(self) -> None:
        """Close all connections in the pool."""
        self._closed = True

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        async with self._lock:
            for conn in self._pool:
                try:
                    await conn.close()
                except Exception:
                    pass

            for conn in self._active.values():
                try:
                    await conn.close()
                except Exception:
                    pass

            self._pool.clear()
            self._active.clear()
            self._metrics.total_connections = 0
            self._metrics.active_connections = 0
            self._metrics.idle_connections = 0

        logger.info("Connection pool closed")


class ConnectionPoolManager:
    """
    Manager for multiple connection pools.

    Manages pools for different databases (primary, replica).
    """

    def __init__(self):
        """Initialize pool manager."""
        self._pools: Dict[str, ConnectionPool] = {}
        self._lock = threading.Lock()

    def create_pool(
        self,
        name: str,
        pool_size: int = 20,
        max_overflow: int = 10,
        **kwargs
    ) -> ConnectionPool:
        """
        Create a new connection pool.

        Args:
            name: Pool name.
            pool_size: Base pool size.
            max_overflow: Maximum additional connections.
            **kwargs: Additional pool options.

        Returns:
            ConnectionPool instance.
        """
        with self._lock:
            if name in self._pools:
                raise ValueError(f"Pool '{name}' already exists")

            pool = ConnectionPool(
                pool_size=pool_size,
                max_overflow=max_overflow,
                **kwargs
            )
            self._pools[name] = pool
            return pool

    def get_pool(self, name: str = "default") -> ConnectionPool:
        """
        Get a connection pool by name.

        Args:
            name: Pool name.

        Returns:
            ConnectionPool instance.

        Raises:
            KeyError: If pool doesn't exist.
        """
        with self._lock:
            if name not in self._pools:
                raise KeyError(f"Pool '{name}' not found")
            return self._pools[name]

    async def initialize_all(self) -> None:
        """Initialize all pools."""
        for pool in self._pools.values():
            await pool.initialize()

    async def close_all(self) -> None:
        """Close all pools."""
        for pool in self._pools.values():
            await pool.close()

    def get_all_metrics(self) -> Dict[str, Dict]:
        """
        Get metrics for all pools.

        Returns:
            Dictionary of pool metrics.
        """
        return {
            name: {
                "total_connections": pool._metrics.total_connections,
                "active_connections": pool._metrics.active_connections,
                "idle_connections": pool._metrics.idle_connections,
                "total_acquisitions": pool._metrics.total_acquisitions,
                "avg_acquisition_time_ms": round(
                    pool._metrics.avg_acquisition_time_ms, 3
                ),
                "connection_errors": pool._metrics.connection_errors,
            }
            for name, pool in self._pools.items()
        }


# Global pool manager
_pool_manager: Optional[ConnectionPoolManager] = None


def get_pool_manager() -> ConnectionPoolManager:
    """
    Get the global pool manager instance.

    Returns:
        ConnectionPoolManager instance.
    """
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = ConnectionPoolManager()
    return _pool_manager


async def get_connection(pool_name: str = "default"):
    """
    Get a connection from the specified pool.

    Args:
        pool_name: Name of the pool.

    Returns:
        Database connection context manager.
    """
    manager = get_pool_manager()
    pool = manager.get_pool(pool_name)
    return pool.acquire()


__all__ = [
    "PoolMetrics",
    "MockConnection",
    "ConnectionPool",
    "ConnectionPoolManager",
    "get_pool_manager",
    "get_connection",
]
