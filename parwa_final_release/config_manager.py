"""
Week 60 - Builder 4: Configuration Manager Module
Configuration management, secrets, and feature flags
"""

import time
import json
import hashlib
import threading
import secrets
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ConfigSource(Enum):
    """Configuration sources"""
    FILE = "file"
    ENVIRONMENT = "environment"
    DATABASE = "database"
    REMOTE = "remote"


class FeatureStatus(Enum):
    """Feature flag status"""
    ENABLED = "enabled"
    DISABLED = "disabled"
    PERCENTAGE = "percentage"
    TARGETED = "targeted"


@dataclass
class ConfigEntry:
    """Configuration entry"""
    key: str
    value: Any
    source: ConfigSource = ConfigSource.FILE
    encrypted: bool = False
    version: int = 1
    updated_at: float = field(default_factory=time.time)


@dataclass
class Secret:
    """Secret entry"""
    name: str
    value: str
    version: int = 1
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None


@dataclass
class FeatureFlag:
    """Feature flag definition"""
    name: str
    status: FeatureStatus = FeatureStatus.DISABLED
    percentage: int = 0
    targets: List[str] = field(default_factory=list)
    description: str = ""
    created_at: float = field(default_factory=time.time)


class ConfigManager:
    """
    Configuration manager for configs, environments, and overrides
    """

    def __init__(self):
        self.configs: Dict[str, ConfigEntry] = {}
        self.overrides: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.lock = threading.Lock()

    def set_config(self, key: str, value: Any,
                   source: ConfigSource = ConfigSource.FILE) -> ConfigEntry:
        """Set a configuration value"""
        entry = ConfigEntry(
            key=key,
            value=value,
            source=source
        )

        with self.lock:
            # Store history
            if key in self.configs:
                old_entry = self.configs[key]
                self.history[key].append({
                    "value": old_entry.value,
                    "version": old_entry.version,
                    "changed_at": time.time()
                })
                entry.version = old_entry.version + 1

            self.configs[key] = entry

        return entry

    def get_config(self, key: str, default: Any = None,
                   environment: str = None) -> Any:
        """Get configuration value"""
        # Check overrides first
        if environment and environment in self.overrides:
            if key in self.overrides[environment]:
                return self.overrides[environment][key]

        entry = self.configs.get(key)
        return entry.value if entry else default

    def set_override(self, environment: str, key: str, value: Any) -> None:
        """Set environment-specific override"""
        with self.lock:
            self.overrides[environment][key] = value

    def remove_override(self, environment: str, key: str) -> bool:
        """Remove environment override"""
        with self.lock:
            if environment in self.overrides and key in self.overrides[environment]:
                del self.overrides[environment][key]
                return True
        return False

    def get_history(self, key: str) -> List[Dict[str, Any]]:
        """Get configuration history"""
        return self.history.get(key, [])

    def list_configs(self, source: ConfigSource = None) -> List[str]:
        """List configuration keys"""
        if source:
            return [k for k, v in self.configs.items() if v.source == source]
        return list(self.configs.keys())

    def delete_config(self, key: str) -> bool:
        """Delete a configuration"""
        with self.lock:
            if key in self.configs:
                del self.configs[key]
                return True
        return False

    def export_configs(self, environment: str = None) -> Dict[str, Any]:
        """Export all configs for an environment"""
        result = {key: entry.value for key, entry in self.configs.items()}

        if environment and environment in self.overrides:
            result.update(self.overrides[environment])

        return result


class SecretManager:
    """
    Secret manager for secrets, encryption, and rotation
    """

    def __init__(self, encryption_key: str = None):
        self.encryption_key = encryption_key or secrets.token_hex(32)
        self.secrets: Dict[str, Secret] = {}
        self.audit_log: List[Dict[str, Any]] = []
        self.lock = threading.Lock()

    def store_secret(self, name: str, value: str,
                     expires_in: int = None) -> Secret:
        """Store a secret"""
        secret = Secret(
            name=name,
            value=self._encrypt(value),
            expires_at=time.time() + expires_in if expires_in else None
        )

        with self.lock:
            if name in self.secrets:
                secret.version = self.secrets[name].version + 1
            self.secrets[name] = secret
            self._audit("store", name)

        return secret

    def get_secret(self, name: str) -> Optional[str]:
        """Get a secret value"""
        secret = self.secrets.get(name)
        if not secret:
            return None

        if secret.expires_at and time.time() > secret.expires_at:
            return None

        with self.lock:
            self._audit("access", name)

        return self._decrypt(secret.value)

    def rotate_secret(self, name: str, new_value: str) -> Optional[Secret]:
        """Rotate a secret"""
        if name not in self.secrets:
            return None

        with self.lock:
            old_version = self.secrets[name].version
            secret = Secret(
                name=name,
                value=self._encrypt(new_value),
                version=old_version + 1
            )
            self.secrets[name] = secret
            self._audit("rotate", name)

        return secret

    def delete_secret(self, name: str) -> bool:
        """Delete a secret"""
        with self.lock:
            if name in self.secrets:
                del self.secrets[name]
                self._audit("delete", name)
                return True
        return False

    def list_secrets(self) -> List[str]:
        """List secret names"""
        return list(self.secrets.keys())

    def _encrypt(self, value: str) -> str:
        """Encrypt value (simplified)"""
        return hashlib.sha256(f"{self.encryption_key}:{value}".encode()).hexdigest()

    def _decrypt(self, value: str) -> str:
        """Decrypt value (placeholder - real impl would reverse encryption)"""
        return value

    def _audit(self, action: str, name: str) -> None:
        """Record audit log"""
        self.audit_log.append({
            "action": action,
            "secret": name,
            "timestamp": time.time()
        })

    def get_audit_log(self, name: str = None) -> List[Dict[str, Any]]:
        """Get audit log"""
        if name:
            return [e for e in self.audit_log if e["secret"] == name]
        return list(self.audit_log)


class FeatureFlags:
    """
    Feature flags for toggles, rollouts, and A/B testing
    """

    def __init__(self):
        self.flags: Dict[str, FeatureFlag] = {}
        self.user_assignments: Dict[str, Dict[str, str]] = defaultdict(dict)
        self.lock = threading.Lock()

    def create_flag(self, name: str, description: str = "",
                    status: FeatureStatus = FeatureStatus.DISABLED) -> FeatureFlag:
        """Create a feature flag"""
        flag = FeatureFlag(
            name=name,
            description=description,
            status=status
        )

        with self.lock:
            self.flags[name] = flag

        return flag

    def enable(self, name: str) -> bool:
        """Enable a feature flag"""
        flag = self.flags.get(name)
        if not flag:
            return False

        with self.lock:
            flag.status = FeatureStatus.ENABLED

        return True

    def disable(self, name: str) -> bool:
        """Disable a feature flag"""
        flag = self.flags.get(name)
        if not flag:
            return False

        with self.lock:
            flag.status = FeatureStatus.DISABLED

        return True

    def set_percentage(self, name: str, percentage: int) -> bool:
        """Set rollout percentage"""
        flag = self.flags.get(name)
        if not flag or percentage < 0 or percentage > 100:
            return False

        with self.lock:
            flag.status = FeatureStatus.PERCENTAGE
            flag.percentage = percentage

        return True

    def add_target(self, name: str, target: str) -> bool:
        """Add a target to the flag"""
        flag = self.flags.get(name)
        if not flag:
            return False

        with self.lock:
            if target not in flag.targets:
                flag.targets.append(target)
                flag.status = FeatureStatus.TARGETED

        return True

    def remove_target(self, name: str, target: str) -> bool:
        """Remove a target from the flag"""
        flag = self.flags.get(name)
        if not flag:
            return False

        with self.lock:
            if target in flag.targets:
                flag.targets.remove(target)

        return True

    def is_enabled(self, name: str, user_id: str = None) -> bool:
        """Check if flag is enabled for user"""
        flag = self.flags.get(name)
        if not flag:
            return False

        if flag.status == FeatureStatus.ENABLED:
            return True

        if flag.status == FeatureStatus.DISABLED:
            return False

        if flag.status == FeatureStatus.TARGETED:
            if user_id and user_id in flag.targets:
                return True
            return False

        if flag.status == FeatureStatus.PERCENTAGE:
            if user_id:
                hash_val = int(hashlib.md5(f"{name}:{user_id}".encode()).hexdigest()[:8], 16)
                return (hash_val % 100) < flag.percentage
            return flag.percentage >= 50  # Default for no user

        return False

    def get_flag(self, name: str) -> Optional[FeatureFlag]:
        """Get flag by name"""
        return self.flags.get(name)

    def list_flags(self) -> List[str]:
        """List all flag names"""
        return list(self.flags.keys())

    def delete_flag(self, name: str) -> bool:
        """Delete a feature flag"""
        with self.lock:
            if name in self.flags:
                del self.flags[name]
                return True
        return False
