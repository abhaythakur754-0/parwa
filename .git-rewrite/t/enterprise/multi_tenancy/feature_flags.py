"""
Feature Flags Module

Manages feature flags for tenant-specific feature enablement.
"""

from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class FeatureStatus(str, Enum):
    """Feature flag status"""
    ENABLED = "enabled"
    DISABLED = "disabled"
    PERCENTAGE = "percentage"  # Rollout percentage
    WHITELIST = "whitelist"  # Only for specific tenants


@dataclass
class FeatureFlag:
    """A feature flag definition"""
    flag_id: str
    name: str
    description: str
    status: FeatureStatus = FeatureStatus.DISABLED
    rollout_percentage: int = 0
    whitelisted_tenants: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TenantOverride:
    """Tenant-specific feature override"""
    tenant_id: str
    flag_id: str
    enabled: bool
    reason: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


class FeatureFlags:
    """
    Manages feature flags for multi-tenant environments.

    Features:
    - Global feature enablement
    - Per-tenant overrides
    - Percentage rollouts
    - Whitelist-based access
    """

    def __init__(self):
        # Feature flags
        self._flags: Dict[str, FeatureFlag] = {}

        # Tenant overrides
        self._overrides: Dict[str, Dict[str, TenantOverride]] = {}  # tenant -> flag -> override

        # Metrics
        self._metrics = {
            "total_checks": 0,
            "enabled_count": 0,
            "disabled_count": 0
        }

        # Initialize common features
        self._initialize_features()

    def _initialize_features(self) -> None:
        """Initialize common feature flags"""
        features = [
            ("advanced_analytics", "Advanced Analytics Dashboard", False),
            ("custom_branding", "Custom Branding Options", False),
            ("api_access", "API Access", True),
            ("webhooks", "Webhook Integrations", True),
            ("sso", "Single Sign-On", False),
            ("audit_logs", "Enhanced Audit Logs", False),
            ("ai_custom_models", "Custom AI Models", False),
            ("priority_support", "Priority Support", False),
            ("data_export", "Data Export", True),
            ("team_collaboration", "Team Collaboration", False),
        ]

        for flag_id, name, default in features:
            self.create_flag(
                flag_id=flag_id,
                name=name,
                description=name,
                status=FeatureStatus.ENABLED if default else FeatureStatus.DISABLED
            )

    def create_flag(
        self,
        flag_id: str,
        name: str,
        description: str = "",
        status: FeatureStatus = FeatureStatus.DISABLED,
        rollout_percentage: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FeatureFlag:
        """Create a new feature flag"""
        flag = FeatureFlag(
            flag_id=flag_id,
            name=name,
            description=description,
            status=status,
            rollout_percentage=rollout_percentage,
            metadata=metadata or {}
        )

        self._flags[flag_id] = flag

        logger.info(f"Created feature flag: {flag_id} ({status.value})")
        return flag

    def is_enabled(
        self,
        flag_id: str,
        tenant_id: str
    ) -> bool:
        """Check if a feature is enabled for a tenant"""
        self._metrics["total_checks"] += 1

        flag = self._flags.get(flag_id)
        if not flag:
            self._metrics["disabled_count"] += 1
            return False

        # Check tenant override first
        if tenant_id in self._overrides and flag_id in self._overrides[tenant_id]:
            override = self._overrides[tenant_id][flag_id]
            result = override.enabled
        elif flag.status == FeatureStatus.ENABLED:
            result = True
        elif flag.status == FeatureStatus.DISABLED:
            result = False
        elif flag.status == FeatureStatus.PERCENTAGE:
            # Hash-based percentage rollout
            result = self._check_percentage(flag, tenant_id)
        elif flag.status == FeatureStatus.WHITELIST:
            result = tenant_id in flag.whitelisted_tenants
        else:
            result = False

        if result:
            self._metrics["enabled_count"] += 1
        else:
            self._metrics["disabled_count"] += 1

        return result

    def _check_percentage(self, flag: FeatureFlag, tenant_id: str) -> bool:
        """Check if tenant is in rollout percentage"""
        import hashlib

        hash_val = int(hashlib.md5(f"{flag.flag_id}:{tenant_id}".encode()).hexdigest(), 16)
        return (hash_val % 100) < flag.rollout_percentage

    def enable(self, flag_id: str) -> bool:
        """Globally enable a feature flag"""
        flag = self._flags.get(flag_id)
        if not flag:
            return False

        flag.status = FeatureStatus.ENABLED
        flag.updated_at = datetime.utcnow()

        logger.info(f"Enabled feature flag: {flag_id}")
        return True

    def disable(self, flag_id: str) -> bool:
        """Globally disable a feature flag"""
        flag = self._flags.get(flag_id)
        if not flag:
            return False

        flag.status = FeatureStatus.DISABLED
        flag.updated_at = datetime.utcnow()

        logger.info(f"Disabled feature flag: {flag_id}")
        return True

    def set_rollout_percentage(
        self,
        flag_id: str,
        percentage: int
    ) -> bool:
        """Set rollout percentage for a feature"""
        flag = self._flags.get(flag_id)
        if not flag:
            return False

        flag.status = FeatureStatus.PERCENTAGE
        flag.rollout_percentage = min(100, max(0, percentage))
        flag.updated_at = datetime.utcnow()

        logger.info(f"Set {flag_id} rollout to {percentage}%")
        return True

    def add_to_whitelist(
        self,
        flag_id: str,
        tenant_id: str
    ) -> bool:
        """Add tenant to feature whitelist"""
        flag = self._flags.get(flag_id)
        if not flag:
            return False

        flag.status = FeatureStatus.WHITELIST
        flag.whitelisted_tenants.add(tenant_id)
        flag.updated_at = datetime.utcnow()

        logger.info(f"Added {tenant_id} to whitelist for {flag_id}")
        return True

    def remove_from_whitelist(
        self,
        flag_id: str,
        tenant_id: str
    ) -> bool:
        """Remove tenant from feature whitelist"""
        flag = self._flags.get(flag_id)
        if not flag:
            return False

        flag.whitelisted_tenants.discard(tenant_id)
        flag.updated_at = datetime.utcnow()

        return True

    def set_tenant_override(
        self,
        tenant_id: str,
        flag_id: str,
        enabled: bool,
        reason: str = ""
    ) -> TenantOverride:
        """Set tenant-specific override"""
        if tenant_id not in self._overrides:
            self._overrides[tenant_id] = {}

        override = TenantOverride(
            tenant_id=tenant_id,
            flag_id=flag_id,
            enabled=enabled,
            reason=reason
        )

        self._overrides[tenant_id][flag_id] = override

        logger.info(f"Set override for {tenant_id}/{flag_id}: {'enabled' if enabled else 'disabled'}")
        return override

    def clear_tenant_override(
        self,
        tenant_id: str,
        flag_id: str
    ) -> bool:
        """Clear tenant-specific override"""
        if tenant_id in self._overrides and flag_id in self._overrides[tenant_id]:
            del self._overrides[tenant_id][flag_id]
            return True
        return False

    def get_flag(self, flag_id: str) -> Optional[FeatureFlag]:
        """Get a feature flag"""
        return self._flags.get(flag_id)

    def get_all_flags(self) -> List[FeatureFlag]:
        """Get all feature flags"""
        return list(self._flags.values())

    def get_tenant_flags(self, tenant_id: str) -> Dict[str, bool]:
        """Get all flags for a tenant"""
        return {
            flag_id: self.is_enabled(flag_id, tenant_id)
            for flag_id in self._flags
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get feature flag metrics"""
        return {
            **self._metrics,
            "total_flags": len(self._flags),
            "enabled_flags": sum(1 for f in self._flags.values() if f.status == FeatureStatus.ENABLED),
            "tenants_with_overrides": len(self._overrides)
        }

    def delete_flag(self, flag_id: str) -> bool:
        """Delete a feature flag"""
        if flag_id in self._flags:
            del self._flags[flag_id]
            return True
        return False
