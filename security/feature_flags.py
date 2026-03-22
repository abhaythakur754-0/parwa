import json
import os
from uuid import UUID
from typing import Any, Dict, Optional
from shared.utils.cache import Cache
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)

class FeatureManager:
    """
    Manages application feature flags with support for tiered defaults and per-company overrides.
    Uses Redis for performance and caching.
    """
    def __init__(self, cache: Optional[Cache] = None):
        self.settings = get_settings()
        self.cache = cache or Cache()
        self.flags_dir = self.settings.feature_flags_path

    async def _get_tier_flags_from_json(self, tier: str) -> Dict[str, Any]:
        """Load default flags for a specific plan tier from JSON files."""
        file_path = os.path.join(self.flags_dir, f"{tier}_flags.json")
        try:
            if not os.path.exists(file_path):
                logger.warning("tier_flags_json_not_found", extra={"context": {"path": file_path}})
                return {}
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error("tier_flags_load_failed", extra={"context": {"path": file_path, "error": str(e)}})
            return {}

    async def is_enabled(self, feature_name: str, company_id: UUID, plan_tier: str) -> bool:
        """
        Check if a feature is enabled for a specific company.
        Precedence:
        1. Redis Override (per-company)
        2. Redis Tier Cache (global for tier)
        3. File System (JSON defaults)
        """
        # 1. Check for per-company override in Redis
        override_key = f"ff:override:{company_id}:{feature_name}"
        override = await self.cache.get(override_key)
        if override is not None:
            return bool(override)

        # 2. Check for cached tier flags
        tier_cache_key = f"ff:tier:{plan_tier}"
        tier_flags = await self.cache.get(tier_cache_key)
        
        # 3. If cache miss, load from JSON and populate cache
        if tier_flags is None:
            tier_flags = await self._get_tier_flags_from_json(plan_tier)
            if tier_flags:
                # Cache for 1 hour
                await self.cache.set(tier_cache_key, tier_flags, expire=3600)
        
        # 4. Return the flag status from tier flags
        return bool(tier_flags.get(feature_name, False))

    async def set_override(self, company_id: UUID, feature_name: str, enabled: bool, expire: int = 86400):
        """Set a feature flag override in Redis for a specific company (defaults to 24h)."""
        override_key = f"ff:override:{company_id}:{feature_name}"
        await self.cache.set(override_key, enabled, expire=expire)
        logger.info("feature_flag_override_set", extra={"context": {"company_id": str(company_id), "feature": feature_name, "enabled": enabled}})

    async def clear_override(self, company_id: UUID, feature_name: str):
        """Remove a feature flag override from Redis."""
        override_key = f"ff:override:{company_id}:{feature_name}"
        await self.cache.delete(override_key)
