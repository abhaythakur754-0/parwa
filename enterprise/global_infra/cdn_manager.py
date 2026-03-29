# CDN Manager - Week 51 Builder 2
# CDN configuration and management

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class CDNProvider(Enum):
    CLOUDFRONT = "cloudfront"
    CLOUDFLARE = "cloudflare"
    FASTLY = "fastly"
    AKAMAI = "akamai"


class CacheBehavior(Enum):
    CACHE_FIRST = "cache_first"
    NETWORK_FIRST = "network_first"
    STALE_WHILE_REVALIDATE = "stale_while_revalidate"


@dataclass
class CDNConfig:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    provider: CDNProvider = CDNProvider.CLOUDFRONT
    domain: str = ""
    origin: str = ""
    ttl_seconds: int = 3600
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CacheRule:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    config_id: str = ""
    path_pattern: str = "/*"
    ttl_seconds: int = 3600
    behavior: CacheBehavior = CacheBehavior.CACHE_FIRST
    query_string_cache: bool = False
    headers_to_cache: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


class CDNManager:
    """Manages CDN configuration and operations"""

    def __init__(self):
        self._configs: Dict[str, CDNConfig] = {}
        self._rules: Dict[str, CacheRule] = {}
        self._metrics = {
            "total_configs": 0,
            "total_rules": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "purge_requests": 0
        }

    def create_config(
        self,
        name: str,
        provider: CDNProvider,
        domain: str,
        origin: str,
        ttl_seconds: int = 3600
    ) -> CDNConfig:
        """Create a CDN configuration"""
        config = CDNConfig(
            name=name,
            provider=provider,
            domain=domain,
            origin=origin,
            ttl_seconds=ttl_seconds
        )
        self._configs[config.id] = config
        self._metrics["total_configs"] += 1
        return config

    def update_config(
        self,
        config_id: str,
        **kwargs
    ) -> bool:
        """Update CDN configuration"""
        config = self._configs.get(config_id)
        if not config:
            return False

        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return True

    def delete_config(self, config_id: str) -> bool:
        """Delete a CDN configuration"""
        if config_id in self._configs:
            del self._configs[config_id]
            return True
        return False

    def add_cache_rule(
        self,
        config_id: str,
        path_pattern: str,
        ttl_seconds: int = 3600,
        behavior: CacheBehavior = CacheBehavior.CACHE_FIRST
    ) -> Optional[CacheRule]:
        """Add a cache rule"""
        if config_id not in self._configs:
            return None

        rule = CacheRule(
            config_id=config_id,
            path_pattern=path_pattern,
            ttl_seconds=ttl_seconds,
            behavior=behavior
        )
        self._rules[rule.id] = rule
        self._metrics["total_rules"] += 1
        return rule

    def remove_cache_rule(self, rule_id: str) -> bool:
        """Remove a cache rule"""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def get_config(self, config_id: str) -> Optional[CDNConfig]:
        """Get configuration by ID"""
        return self._configs.get(config_id)

    def get_config_by_domain(self, domain: str) -> Optional[CDNConfig]:
        """Get configuration by domain"""
        for config in self._configs.values():
            if config.domain == domain:
                return config
        return None

    def get_rules_for_config(self, config_id: str) -> List[CacheRule]:
        """Get all rules for a configuration"""
        return [r for r in self._rules.values() if r.config_id == config_id]

    def purge_cache(
        self,
        config_id: str,
        paths: Optional[List[str]] = None
    ) -> bool:
        """Purge cache for paths"""
        config = self._configs.get(config_id)
        if not config:
            return False

        self._metrics["purge_requests"] += 1
        return True

    def purge_all(self, config_id: str) -> bool:
        """Purge all cache for a configuration"""
        return self.purge_cache(config_id, ["/*"])

    def record_cache_hit(self) -> None:
        """Record a cache hit"""
        self._metrics["cache_hits"] += 1

    def record_cache_miss(self) -> None:
        """Record a cache miss"""
        self._metrics["cache_misses"] += 1

    def get_cache_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self._metrics["cache_hits"] + self._metrics["cache_misses"]
        if total == 0:
            return 0.0
        return (self._metrics["cache_hits"] / total) * 100

    def enable_config(self, config_id: str) -> bool:
        """Enable a configuration"""
        config = self._configs.get(config_id)
        if not config:
            return False
        config.enabled = True
        return True

    def disable_config(self, config_id: str) -> bool:
        """Disable a configuration"""
        config = self._configs.get(config_id)
        if not config:
            return False
        config.enabled = False
        return True

    def get_configs_by_provider(self, provider: CDNProvider) -> List[CDNConfig]:
        """Get all configs for a provider"""
        return [c for c in self._configs.values() if c.provider == provider]

    def get_enabled_configs(self) -> List[CDNConfig]:
        """Get all enabled configurations"""
        return [c for c in self._configs.values() if c.enabled]

    def get_metrics(self) -> Dict[str, Any]:
        """Get CDN metrics"""
        return {
            **self._metrics,
            "cache_hit_rate": round(self.get_cache_hit_rate(), 2)
        }
