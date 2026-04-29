"""
GSD Tenant Configuration Persistence (GSD-1)

Hybrid persistence layer for GSD tenant configurations:
- PostgreSQL: Authoritative storage with JSONB config field
- Redis: Cache layer with 5-minute TTL
- Memory: Local cache with 30-second refresh

This enables:
1. Survival of tenant configs across backend restarts
2. Fast access via Redis cache
3. Consistency across multiple worker replicas
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import time

import redis.asyncio as aioredis

logger = logging.getLogger("parwa.gsd_persistence")

# Redis key patterns
REDIS_GSD_CONFIG_PREFIX = "parwa:gsd:config"
REDIS_GSD_CONFIG_TTL = 300  # 5 minutes


@dataclass
class GSDTenantConfig:
    """Tenant-specific GSD configuration."""

    company_id: str
    variant_id: str = "parwa"

    # State machine settings
    max_retries_per_state: int = 3
    escalation_enabled: bool = True
    escalation_timeout_seconds: int = 300  # 5 minutes

    # Greeting state
    greeting_template: str = "Hello! How can I help you today?"
    collect_name_enabled: bool = True

    # Diagnosis state
    max_diagnosis_questions: int = 5
    diagnosis_confidence_threshold: float = 0.85

    # Resolution state
    auto_resolution_enabled: bool = True
    resolution_confirmation_required: bool = True

    # Follow-up state
    follow_up_delay_hours: int = 24
    follow_up_max_attempts: int = 2

    # Additional settings (JSONB in PostgreSQL)
    custom_settings: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GSDTenantConfig":
        """Create from dictionary."""
        # Handle missing fields with defaults
        return cls(
            company_id=data.get("company_id", ""),
            variant_id=data.get("variant_id", "parwa"),
            max_retries_per_state=data.get("max_retries_per_state", 3),
            escalation_enabled=data.get("escalation_enabled", True),
            escalation_timeout_seconds=data.get("escalation_timeout_seconds", 300),
            greeting_template=data.get(
                "greeting_template", "Hello! How can I help you today?"
            ),
            collect_name_enabled=data.get("collect_name_enabled", True),
            max_diagnosis_questions=data.get("max_diagnosis_questions", 5),
            diagnosis_confidence_threshold=data.get(
                "diagnosis_confidence_threshold", 0.85
            ),
            auto_resolution_enabled=data.get("auto_resolution_enabled", True),
            resolution_confirmation_required=data.get(
                "resolution_confirmation_required", True
            ),
            follow_up_delay_hours=data.get("follow_up_delay_hours", 24),
            follow_up_max_attempts=data.get("follow_up_max_attempts", 2),
            custom_settings=data.get("custom_settings", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


class GSDConfigPersistence:
    """
    Hybrid persistence for GSD tenant configurations.

    Read path: Memory -> Redis -> PostgreSQL
    Write path: PostgreSQL -> Redis -> Memory

    This ensures configs survive restarts and are consistent across workers.
    """

    MEMORY_REFRESH_INTERVAL = 30  # seconds

    def __init__(
        self,
        redis_client: aioredis.Redis,
        db_session_factory=None,
    ):
        """Initialize with Redis client and DB session factory."""
        self._redis = redis_client
        self._db_session_factory = db_session_factory

        # Local memory cache with timestamps
        self._memory_cache: Dict[str, GSDTenantConfig] = {}
        self._memory_timestamps: Dict[str, float] = {}

    def _get_redis_key(self, company_id: str) -> str:
        """Get Redis key for a tenant's config."""
        return f"{REDIS_GSD_CONFIG_PREFIX}:{company_id}"

    async def get_config(self, company_id: str) -> Optional[GSDTenantConfig]:
        """
        Get tenant config with hybrid read path.

        Priority: Memory (if fresh) -> Redis -> PostgreSQL
        """
        # Check memory cache first (fastest)
        if company_id in self._memory_cache:
            cached_at = self._memory_timestamps.get(company_id, 0)
            if time.time() - cached_at < self.MEMORY_REFRESH_INTERVAL:
                return self._memory_cache[company_id]

        # Check Redis cache
        redis_key = self._get_redis_key(company_id)
        try:
            cached_data = await self._redis.get(redis_key)
            if cached_data:
                config_dict = json.loads(cached_data)
                config = GSDTenantConfig.from_dict(config_dict)

                # Update memory cache
                self._memory_cache[company_id] = config
                self._memory_timestamps[company_id] = time.time()

                return config
        except Exception as e:
            logger.warning("Redis read failed for %s: %s", company_id, e)

        # Fall back to PostgreSQL
        config = await self._load_from_postgres(company_id)

        if config:
            # Update caches
            await self._update_caches(company_id, config)

        return config

    async def save_config(self, config: GSDTenantConfig) -> bool:
        """
        Save tenant config with hybrid write path.

        Writes to: PostgreSQL -> Redis -> Memory
        """
        company_id = config.company_id

        # Update timestamp
        now = datetime.now(timezone.utc).isoformat()
        config.updated_at = now
        if not config.created_at:
            config.created_at = now

        # Write to PostgreSQL (authoritative)
        success = await self._save_to_postgres(config)
        if not success:
            logger.error("Failed to save GSD config for %s to PostgreSQL", company_id)
            return False

        # Update caches
        await self._update_caches(company_id, config)

        logger.info("Saved GSD config for %s", company_id)
        return True

    async def delete_config(self, company_id: str) -> bool:
        """Delete tenant config from all layers."""
        # Delete from PostgreSQL
        success = await self._delete_from_postgres(company_id)

        # Delete from Redis
        redis_key = self._get_redis_key(company_id)
        try:
            await self._redis.delete(redis_key)
        except Exception as e:
            logger.warning("Redis delete failed for %s: %s", company_id, e)

        # Delete from memory
        self._memory_cache.pop(company_id, None)
        self._memory_timestamps.pop(company_id, None)

        logger.info("Deleted GSD config for %s", company_id)
        return success

    async def _update_caches(self, company_id: str, config: GSDTenantConfig) -> None:
        """Update both Redis and memory caches."""
        # Update Redis
        redis_key = self._get_redis_key(company_id)
        try:
            await self._redis.setex(
                redis_key,
                REDIS_GSD_CONFIG_TTL,
                json.dumps(config.to_dict()),
            )
        except Exception as e:
            logger.warning("Redis write failed for %s: %s", company_id, e)

        # Update memory
        self._memory_cache[company_id] = config
        self._memory_timestamps[company_id] = time.time()

    async def _load_from_postgres(self, company_id: str) -> Optional[GSDTenantConfig]:
        """Load config from PostgreSQL gsd_tenant_configs table."""
        if not self._db_session_factory:
            logger.warning(
                "No DB session factory, returning default config for %s", company_id
            )
            return GSDTenantConfig(company_id=company_id)

        try:
            async with self._db_session_factory() as session:
                # Query gsd_tenant_configs table
                result = await session.execute(
                    """
                    SELECT config_data FROM gsd_tenant_configs
                    WHERE company_id = :company_id
                    """,
                    {"company_id": company_id},
                )
                row = result.fetchone()

                if row:
                    config_dict = row[0]
                    return GSDTenantConfig.from_dict(config_dict)

        except Exception as e:
            logger.error("PostgreSQL read failed for %s: %s", company_id, e)

        # Return default config if not found
        return GSDTenantConfig(company_id=company_id)

    async def _save_to_postgres(self, config: GSDTenantConfig) -> bool:
        """Save config to PostgreSQL gsd_tenant_configs table."""
        if not self._db_session_factory:
            logger.warning("No DB session factory, skipping PostgreSQL save")
            return True  # Assume success for development

        try:
            async with self._db_session_factory() as session:
                # Upsert config
                await session.execute(
                    """
                    INSERT INTO gsd_tenant_configs (company_id, config_data, updated_at)
                    VALUES (:company_id, :config_data, NOW())
                    ON CONFLICT (company_id)
                    DO UPDATE SET
                        config_data = EXCLUDED.config_data,
                        updated_at = NOW()
                    """,
                    {
                        "company_id": config.company_id,
                        "config_data": json.dumps(config.to_dict()),
                    },
                )
                await session.commit()

            return True

        except Exception as e:
            logger.error("PostgreSQL save failed for %s: %s", config.company_id, e)
            return False

    async def _delete_from_postgres(self, company_id: str) -> bool:
        """Delete config from PostgreSQL."""
        if not self._db_session_factory:
            return True

        try:
            async with self._db_session_factory() as session:
                await session.execute(
                    """
                    DELETE FROM gsd_tenant_configs WHERE company_id = :company_id
                    """,
                    {"company_id": company_id},
                )
                await session.commit()

            return True

        except Exception as e:
            logger.error("PostgreSQL delete failed for %s: %s", company_id, e)
            return False

    async def bootstrap_from_postgres(self) -> int:
        """
        Load all tenant configs from PostgreSQL into Redis/memory.

        Called on backend startup to warm caches.
        Returns count of configs loaded.
        """
        if not self._db_session_factory:
            logger.warning("No DB session factory, skipping bootstrap")
            return 0

        try:
            async with self._db_session_factory() as session:
                result = await session.execute("""
                    SELECT company_id, config_data FROM gsd_tenant_configs
                    """)
                rows = result.fetchall()

                for row in rows:
                    company_id = row[0]
                    config_dict = row[1]
                    config = GSDTenantConfig.from_dict(config_dict)
                    await self._update_caches(company_id, config)

                logger.info(
                    "Bootstrapped %d GSD tenant configs from PostgreSQL", len(rows)
                )
                return len(rows)

        except Exception as e:
            logger.error("Bootstrap from PostgreSQL failed: %s", e)
            return 0


# Singleton instance
_gsd_config_persistence: Optional[GSDConfigPersistence] = None


async def get_gsd_config_persistence() -> GSDConfigPersistence:
    """Get or create the singleton GSD config persistence instance."""
    global _gsd_config_persistence

    if _gsd_config_persistence is None:
        from app.core.redis import get_redis_client

        redis_client = await get_redis_client()

        # Try to import DB session factory
        db_session_factory = None
        try:
            from app.core.database import get_async_session

            db_session_factory = get_async_session
        except ImportError:
            pass

        _gsd_config_persistence = GSDConfigPersistence(
            redis_client=redis_client,
            db_session_factory=db_session_factory,
        )

        # Bootstrap from PostgreSQL
        await _gsd_config_persistence.bootstrap_from_postgres()

    return _gsd_config_persistence
