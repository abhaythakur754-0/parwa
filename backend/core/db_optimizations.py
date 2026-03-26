"""
Database Optimizations for PARWA Performance Optimization.

Week 26 - Builder 2: Query Optimization + Connection Pooling
Target: Statement timeout, lock timeout, prepared statements, read replica routing

Features:
- Statement timeout: 30 seconds
- Lock timeout: 5 seconds
- Idle transaction timeout: 60 seconds
- Prepared statement cache
- Read replica routing (ready)
"""

import logging
from typing import Any, Optional, Dict, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import time

logger = logging.getLogger(__name__)


class DatabaseRole(Enum):
    """Database server roles."""
    PRIMARY = "primary"
    REPLICA = "replica"


@dataclass
class DBOptimizationConfig:
    """Configuration for database optimizations."""
    # Timeouts (in seconds)
    statement_timeout: float = 30.0
    lock_timeout: float = 5.0
    idle_transaction_timeout: float = 60.0
    connection_timeout: float = 10.0

    # Prepared statements
    prepared_statement_cache_size: int = 100
    max_prepared_statements: int = 500

    # Connection settings
    max_connections: int = 30
    min_connections: int = 5

    # Read replica settings
    read_replica_enabled: bool = False
    read_replica_url: Optional[str] = None
    read_replica_weight: float = 0.8  # 80% of reads go to replica

    # Query optimization
    default_fetch_size: int = 1000
    max_fetch_size: int = 10000

    # Logging
    log_slow_queries: bool = True
    slow_query_threshold_ms: float = 100.0
    log_parameters: bool = False


@dataclass
class PreparedStatement:
    """Cached prepared statement."""
    name: str
    query: str
    created_at: float
    use_count: int = 0
    last_used_at: float = 0.0


class PreparedStatementCache:
    """
    Cache for prepared statements to improve query performance.

    Prepared statements are compiled once and reused, reducing
    parsing overhead for repeated queries.
    """

    def __init__(self, max_size: int = 100):
        """
        Initialize prepared statement cache.

        Args:
            max_size: Maximum number of statements to cache.
        """
        self.max_size = max_size
        self._cache: Dict[str, PreparedStatement] = {}
        self._query_to_name: Dict[str, str] = {}
        self._counter = 0

    def get(self, query: str) -> Optional[PreparedStatement]:
        """
        Get a prepared statement from cache.

        Args:
            query: SQL query string.

        Returns:
            PreparedStatement if found, None otherwise.
        """
        normalized = self._normalize_query(query)
        stmt = self._cache.get(normalized)

        if stmt:
            stmt.use_count += 1
            stmt.last_used_at = time.time()
            return stmt

        return None

    def put(self, query: str) -> PreparedStatement:
        """
        Add a prepared statement to cache.

        Args:
            query: SQL query string.

        Returns:
            PreparedStatement created.
        """
        normalized = self._normalize_query(query)

        # Check if already exists
        if normalized in self._cache:
            return self._cache[normalized]

        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size:
            self._evict_oldest()

        # Create new statement
        self._counter += 1
        name = f"stmt_{self._counter}"
        stmt = PreparedStatement(
            name=name,
            query=query,
            created_at=time.time(),
            last_used_at=time.time()
        )

        self._cache[normalized] = stmt
        self._query_to_name[query] = name

        return stmt

    def _normalize_query(self, query: str) -> str:
        """
        Normalize a query for caching.

        Args:
            query: SQL query string.

        Returns:
            Normalized query string.
        """
        return ' '.join(query.split()).lower().strip()

    def _evict_oldest(self) -> None:
        """Evict the least recently used statement."""
        if not self._cache:
            return

        # Find LRU statement
        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].last_used_at
        )

        del self._cache[lru_key]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats.
        """
        total_uses = sum(s.use_count for s in self._cache.values())

        return {
            "cache_size": len(self._cache),
            "max_size": self.max_size,
            "total_statements_created": self._counter,
            "total_uses": total_uses,
            "hit_rate": (
                total_uses / (total_uses + self._counter)
                if (total_uses + self._counter) > 0 else 0
            ),
            "top_queries": sorted(
                [
                    {"query": s.query[:100], "uses": s.use_count}
                    for s in self._cache.values()
                ],
                key=lambda x: x["uses"],
                reverse=True
            )[:10],
        }

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._query_to_name.clear()


class ReadReplicaRouter:
    """
    Routes read queries to read replicas for load distribution.

    Supports weighted routing to distribute queries between
    primary and replica servers.
    """

    def __init__(
        self,
        replica_weight: float = 0.8,
        health_check_interval: float = 30.0
    ):
        """
        Initialize read replica router.

        Args:
            replica_weight: Weight for routing to replica (0.0-1.0).
            health_check_interval: Seconds between health checks.
        """
        self.replica_weight = replica_weight
        self.health_check_interval = health_check_interval

        self._replica_healthy = True
        self._last_health_check = 0.0

    def should_use_replica(self, query: str) -> bool:
        """
        Determine if query should go to replica.

        Args:
            query: SQL query string.

        Returns:
            True if query should go to replica.
        """
        # Only route SELECT queries to replica
        if not self._is_read_query(query):
            return False

        # Check replica health
        if not self._replica_healthy:
            return False

        # Weight-based routing
        import random
        return random.random() < self.replica_weight

    def _is_read_query(self, query: str) -> bool:
        """
        Check if query is a read query.

        Args:
            query: SQL query string.

        Returns:
            True if query is a SELECT.
        """
        normalized = query.strip().upper()
        return normalized.startswith("SELECT")

    def mark_replica_unhealthy(self) -> None:
        """Mark replica as unhealthy."""
        self._replica_healthy = False
        logger.warning("Read replica marked as unhealthy")

    def mark_replica_healthy(self) -> None:
        """Mark replica as healthy."""
        self._replica_healthy = True
        logger.info("Read replica marked as healthy")

    def get_status(self) -> Dict[str, Any]:
        """
        Get router status.

        Returns:
            Dictionary with router status.
        """
        return {
            "replica_healthy": self._replica_healthy,
            "replica_weight": self.replica_weight,
            "last_health_check": self._last_health_check,
        }


class DBOptimizations:
    """
    Main database optimizations manager.

    Manages timeouts, prepared statements, and read replica routing.
    """

    def __init__(self, config: Optional[DBOptimizationConfig] = None):
        """
        Initialize database optimizations.

        Args:
            config: Optimization configuration.
        """
        self.config = config or DBOptimizationConfig()
        self.prepared_statements = PreparedStatementCache(
            max_size=self.config.prepared_statement_cache_size
        )
        self.read_replica_router = ReadReplicaRouter(
            replica_weight=self.config.read_replica_weight
        )

    def get_connection_options(self) -> Dict[str, Any]:
        """
        Get connection options for database connection.

        Returns:
            Dictionary of connection options.
        """
        return {
            "statement_timeout": f"{int(self.config.statement_timeout * 1000)}ms",
            "lock_timeout": f"{int(self.config.lock_timeout * 1000)}ms",
            "idle_in_transaction_session_timeout": (
                f"{int(self.config.idle_transaction_timeout * 1000)}ms"
            ),
        }

    def get_session_init_sql(self) -> str:
        """
        Get SQL to initialize a database session with optimizations.

        Returns:
            SQL string for session initialization.
        """
        return f"""
            SET statement_timeout = '{int(self.config.statement_timeout * 1000)}ms';
            SET lock_timeout = '{int(self.config.lock_timeout * 1000)}ms';
            SET idle_in_transaction_session_timeout = '{int(self.config.idle_transaction_timeout * 1000)}ms';
        """

    def prepare_query(self, query: str) -> PreparedStatement:
        """
        Prepare a query for execution.

        Args:
            query: SQL query string.

        Returns:
            PreparedStatement.
        """
        cached = self.prepared_statements.get(query)
        if cached:
            return cached
        return self.prepared_statements.put(query)

    def route_query(self, query: str) -> DatabaseRole:
        """
        Determine which database server should handle the query.

        Args:
            query: SQL query string.

        Returns:
            DatabaseRole (PRIMARY or REPLICA).
        """
        if not self.config.read_replica_enabled:
            return DatabaseRole.PRIMARY

        if self.read_replica_router.should_use_replica(query):
            return DatabaseRole.REPLICA

        return DatabaseRole.PRIMARY

    def get_stats(self) -> Dict[str, Any]:
        """
        Get optimization statistics.

        Returns:
            Dictionary with optimization stats.
        """
        return {
            "prepared_statements": self.prepared_statements.get_stats(),
            "read_replica": self.read_replica_router.get_status(),
            "config": {
                "statement_timeout": self.config.statement_timeout,
                "lock_timeout": self.config.lock_timeout,
                "idle_transaction_timeout": self.config.idle_transaction_timeout,
                "read_replica_enabled": self.config.read_replica_enabled,
            },
        }


# Global optimizations instance
_optimizations: Optional[DBOptimizations] = None


def get_db_optimizations() -> DBOptimizations:
    """
    Get the global database optimizations instance.

    Returns:
        DBOptimizations instance.
    """
    global _optimizations
    if _optimizations is None:
        _optimizations = DBOptimizations()
    return _optimizations


def configure_db_optimizations(config: DBOptimizationConfig) -> None:
    """
    Configure the global database optimizations.

    Args:
        config: Optimization configuration.
    """
    global _optimizations
    _optimizations = DBOptimizations(config)


__all__ = [
    "DatabaseRole",
    "DBOptimizationConfig",
    "PreparedStatement",
    "PreparedStatementCache",
    "ReadReplicaRouter",
    "DBOptimizations",
    "get_db_optimizations",
    "configure_db_optimizations",
]
