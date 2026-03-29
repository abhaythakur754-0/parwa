"""API Key Manager - API key lifecycle management"""
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import secrets
import hashlib
import logging

logger = logging.getLogger(__name__)

class APIKeyStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"

@dataclass
class APIKey:
    key_id: str
    tenant_id: str
    name: str
    key_hash: str
    prefix: str
    scopes: Set[str] = field(default_factory=set)
    status: APIKeyStatus = APIKeyStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    request_count: int = 0
    rate_limit: int = 1000
    metadata: Dict[str, Any] = field(default_factory=dict)

class APIKeyManager:
    def __init__(self, key_prefix: str = "pk"):
        self.key_prefix = key_prefix
        self._keys: Dict[str, APIKey] = {}
        self._keys_by_tenant: Dict[str, List[str]] = {}

    def create_key(self, tenant_id: str, name: str, scopes: Optional[Set[str]] = None, expires_days: Optional[int] = 365, rate_limit: int = 1000) -> Dict[str, str]:
        key_id = f"key_{secrets.token_hex(8)}"
        raw_key = f"{self.key_prefix}_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        prefix = raw_key[:12]

        expires_at = datetime.utcnow() + timedelta(days=expires_days) if expires_days else None

        api_key = APIKey(
            key_id=key_id,
            tenant_id=tenant_id,
            name=name,
            key_hash=key_hash,
            prefix=prefix,
            scopes=scopes or set(),
            expires_at=expires_at,
            rate_limit=rate_limit
        )

        self._keys[key_id] = api_key
        if tenant_id not in self._keys_by_tenant:
            self._keys_by_tenant[tenant_id] = []
        self._keys_by_tenant[tenant_id].append(key_id)

        logger.info(f"Created API key {key_id} for tenant {tenant_id}")
        return {"key_id": key_id, "api_key": raw_key, "prefix": prefix}

    def validate_key(self, raw_key: str) -> Optional[APIKey]:
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        for key in self._keys.values():
            if key.key_hash == key_hash:
                if key.status != APIKeyStatus.ACTIVE:
                    return None
                if key.expires_at and datetime.utcnow() > key.expires_at:
                    key.status = APIKeyStatus.EXPIRED
                    return None
                key.last_used_at = datetime.utcnow()
                key.request_count += 1
                return key
        return None

    def revoke_key(self, key_id: str) -> bool:
        key = self._keys.get(key_id)
        if key:
            key.status = APIKeyStatus.REVOKED
            return True
        return False

    def get_key(self, key_id: str) -> Optional[APIKey]:
        return self._keys.get(key_id)

    def get_tenant_keys(self, tenant_id: str) -> List[APIKey]:
        key_ids = self._keys_by_tenant.get(tenant_id, [])
        return [self._keys[kid] for kid in key_ids if kid in self._keys]

    def check_scope(self, key: APIKey, required_scope: str) -> bool:
        if not key.scopes:
            return True
        return required_scope in key.scopes or "*" in key.scopes

    def delete_key(self, key_id: str) -> bool:
        key = self._keys.get(key_id)
        if key:
            del self._keys[key_id]
            if key.tenant_id in self._keys_by_tenant:
                self._keys_by_tenant[key.tenant_id] = [k for k in self._keys_by_tenant[key.tenant_id] if k != key_id]
            return True
        return False

    def get_metrics(self) -> Dict[str, Any]:
        return {"total_keys": len(self._keys), "active_keys": sum(1 for k in self._keys.values() if k.status == APIKeyStatus.ACTIVE)}
