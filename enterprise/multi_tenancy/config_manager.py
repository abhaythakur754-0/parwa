"""
Tenant Configuration Manager

Manages per-tenant configurations for multi-tenant environments.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import logging
import json
import copy

logger = logging.getLogger(__name__)


class ConfigScope(str, Enum):
    """Configuration scope levels"""
    GLOBAL = "global"
    TENANT = "tenant"
    USER = "user"


class ConfigType(str, Enum):
    """Configuration value types"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"
    LIST = "list"


@dataclass
class ConfigEntry:
    """A configuration entry"""
    key: str
    value: Any
    config_type: ConfigType
    scope: ConfigScope
    tenant_id: Optional[str] = None
    description: str = ""
    default_value: Optional[Any] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    is_secret: bool = False
    validation_rules: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigHistory:
    """Configuration change history"""
    history_id: str
    key: str
    tenant_id: Optional[str]
    old_value: Any
    new_value: Any
    changed_by: str
    changed_at: datetime = field(default_factory=datetime.utcnow)
    reason: str = ""


class ConfigManager:
    """
    Manages tenant-specific configurations.

    Features:
    - Per-tenant configuration
    - Configuration inheritance
    - Version history
    - Validation
    - Secrets management
    """

    def __init__(self):
        # Configuration storage
        self._global_configs: Dict[str, ConfigEntry] = {}
        self._tenant_configs: Dict[str, Dict[str, ConfigEntry]] = {}

        # History
        self._history: List[ConfigHistory] = []

        # Default configurations
        self._defaults: Dict[str, Any] = {}

        # Initialize defaults
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Initialize default configurations"""
        defaults = {
            "ai.model": "gpt-4",
            "ai.max_tokens": 4096,
            "ai.temperature": 0.7,
            "features.advanced_analytics": False,
            "features.custom_branding": False,
            "features.api_access": True,
            "limits.max_users": 10,
            "limits.max_tickets": 1000,
            "limits.storage_gb": 10,
            "notifications.email": True,
            "notifications.sms": False,
            "notifications.slack": False,
            "security.sso_enabled": False,
            "security.mfa_required": False,
            "security.session_timeout_minutes": 60,
        }

        for key, value in defaults.items():
            self._defaults[key] = value
            self.set_global(key, value, description=f"Default {key}")

    def set_global(
        self,
        key: str,
        value: Any,
        config_type: ConfigType = ConfigType.STRING,
        description: str = "",
        is_secret: bool = False
    ) -> ConfigEntry:
        """Set a global configuration"""
        entry = ConfigEntry(
            key=key,
            value=value,
            config_type=config_type,
            scope=ConfigScope.GLOBAL,
            description=description,
            is_secret=is_secret
        )

        # Check if exists and increment version
        if key in self._global_configs:
            entry.version = self._global_configs[key].version + 1

        self._global_configs[key] = entry

        logger.info(f"Set global config: {key} = {value if not is_secret else '***'}")
        return entry

    def set_tenant(
        self,
        tenant_id: str,
        key: str,
        value: Any,
        config_type: ConfigType = ConfigType.STRING,
        description: str = "",
        is_secret: bool = False,
        changed_by: str = "system"
    ) -> ConfigEntry:
        """Set a tenant-specific configuration"""
        if tenant_id not in self._tenant_configs:
            self._tenant_configs[tenant_id] = {}

        # Get old value for history
        old_value = None
        if key in self._tenant_configs[tenant_id]:
            old_value = self._tenant_configs[tenant_id][key].value

        entry = ConfigEntry(
            key=key,
            value=value,
            config_type=config_type,
            scope=ConfigScope.TENANT,
            tenant_id=tenant_id,
            description=description,
            is_secret=is_secret
        )

        # Check version
        if key in self._tenant_configs[tenant_id]:
            entry.version = self._tenant_configs[tenant_id][key].version + 1

        self._tenant_configs[tenant_id][key] = entry

        # Record history
        self._record_history(key, tenant_id, old_value, value, changed_by)

        logger.info(f"Set tenant config: {tenant_id}/{key} = {value if not is_secret else '***'}")
        return entry

    def get(
        self,
        key: str,
        tenant_id: Optional[str] = None,
        default: Optional[Any] = None
    ) -> Any:
        """Get configuration value with inheritance"""
        # Check tenant-specific first
        if tenant_id and tenant_id in self._tenant_configs:
            if key in self._tenant_configs[tenant_id]:
                return self._tenant_configs[tenant_id][key].value

        # Check global
        if key in self._global_configs:
            return self._global_configs[key].value

        # Check defaults
        if key in self._defaults:
            return self._defaults[key]

        return default

    def get_entry(
        self,
        key: str,
        tenant_id: Optional[str] = None
    ) -> Optional[ConfigEntry]:
        """Get full configuration entry"""
        if tenant_id and tenant_id in self._tenant_configs:
            if key in self._tenant_configs[tenant_id]:
                return self._tenant_configs[tenant_id][key]

        if key in self._global_configs:
            return self._global_configs[key]

        return None

    def delete(
        self,
        key: str,
        tenant_id: Optional[str] = None
    ) -> bool:
        """Delete a configuration"""
        if tenant_id:
            if tenant_id in self._tenant_configs and key in self._tenant_configs[tenant_id]:
                del self._tenant_configs[tenant_id][key]
                return True
        else:
            if key in self._global_configs:
                del self._global_configs[key]
                return True

        return False

    def get_tenant_configs(self, tenant_id: str) -> Dict[str, Any]:
        """Get all configs for a tenant (merged with global)"""
        configs = {}

        # Start with defaults
        configs.update(self._defaults)

        # Override with global
        for key, entry in self._global_configs.items():
            configs[key] = entry.value

        # Override with tenant-specific
        if tenant_id in self._tenant_configs:
            for key, entry in self._tenant_configs[tenant_id].items():
                configs[key] = entry.value

        return configs

    def get_all_tenant_keys(self, tenant_id: str) -> List[str]:
        """Get all config keys for a tenant"""
        keys = set(self._defaults.keys())
        keys.update(self._global_configs.keys())

        if tenant_id in self._tenant_configs:
            keys.update(self._tenant_configs[tenant_id].keys())

        return sorted(keys)

    def _record_history(
        self,
        key: str,
        tenant_id: Optional[str],
        old_value: Any,
        new_value: Any,
        changed_by: str,
        reason: str = ""
    ) -> None:
        """Record configuration change history"""
        history_id = f"hist_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{len(self._history)}"

        history = ConfigHistory(
            history_id=history_id,
            key=key,
            tenant_id=tenant_id,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by,
            reason=reason
        )

        self._history.append(history)

    def get_history(
        self,
        tenant_id: Optional[str] = None,
        key: Optional[str] = None,
        limit: int = 100
    ) -> List[ConfigHistory]:
        """Get configuration history"""
        history = self._history

        if tenant_id:
            history = [h for h in history if h.tenant_id == tenant_id]

        if key:
            history = [h for h in history if h.key == key]

        return sorted(history, key=lambda x: x.changed_at, reverse=True)[:limit]

    def rollback(
        self,
        history_id: str,
        changed_by: str = "system"
    ) -> Optional[ConfigEntry]:
        """Rollback to a previous configuration"""
        for h in self._history:
            if h.history_id == history_id:
                if h.tenant_id:
                    return self.set_tenant(
                        tenant_id=h.tenant_id,
                        key=h.key,
                        value=h.old_value,
                        changed_by=changed_by
                    )
                else:
                    return self.set_global(h.key, h.old_value)

        return None

    def export_configs(
        self,
        tenant_id: Optional[str] = None,
        include_secrets: bool = False
    ) -> Dict[str, Any]:
        """Export configurations"""
        configs = {}

        if tenant_id:
            configs = self.get_tenant_configs(tenant_id)
        else:
            for key, entry in self._global_configs.items():
                if include_secrets or not entry.is_secret:
                    configs[key] = entry.value

        return configs

    def import_configs(
        self,
        configs: Dict[str, Any],
        tenant_id: Optional[str] = None,
        changed_by: str = "import"
    ) -> int:
        """Import configurations"""
        count = 0

        for key, value in configs.items():
            if tenant_id:
                self.set_tenant(tenant_id, key, value, changed_by=changed_by)
            else:
                self.set_global(key, value)
            count += 1

        return count

    def get_metrics(self) -> Dict[str, Any]:
        """Get configuration metrics"""
        return {
            "global_configs": len(self._global_configs),
            "tenants_with_configs": len(self._tenant_configs),
            "total_tenant_configs": sum(
                len(configs) for configs in self._tenant_configs.values()
            ),
            "history_entries": len(self._history)
        }
