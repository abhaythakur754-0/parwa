# Retention Manager - Week 49 Builder 4
# Data retention policy management

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class RetentionAction(Enum):
    DELETE = "delete"
    ARCHIVE = "archive"
    ANONYMIZE = "anonymize"
    REVIEW = "review"


class RetentionStatus(Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    ARCHIVED = "archived"
    DELETED = "deleted"


@dataclass
class RetentionPolicy:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    data_type: str = ""
    retention_days: int = 365
    action: RetentionAction = RetentionAction.ARCHIVE
    legal_hold: bool = False
    compliance_tags: List[str] = field(default_factory=list)
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RetentionItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    policy_id: str = ""
    data_type: str = ""
    data_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    status: RetentionStatus = RetentionStatus.ACTIVE
    last_reviewed: Optional[datetime] = None


class RetentionManager:
    """Manages data retention policies"""

    def __init__(self):
        self._policies: Dict[str, RetentionPolicy] = {}
        self._items: Dict[str, RetentionItem] = {}
        self._metrics = {
            "total_policies": 0,
            "total_items": 0,
            "items_expired": 0,
            "items_archived": 0
        }

    def create_policy(
        self,
        tenant_id: str,
        name: str,
        data_type: str,
        retention_days: int,
        action: RetentionAction = RetentionAction.ARCHIVE
    ) -> RetentionPolicy:
        """Create a retention policy"""
        policy = RetentionPolicy(
            tenant_id=tenant_id,
            name=name,
            data_type=data_type,
            retention_days=retention_days,
            action=action
        )
        self._policies[policy.id] = policy
        self._metrics["total_policies"] += 1
        return policy

    def register_item(
        self,
        tenant_id: str,
        policy_id: str,
        data_type: str,
        data_id: str
    ) -> Optional[RetentionItem]:
        """Register an item under a retention policy"""
        policy = self._policies.get(policy_id)
        if not policy:
            return None

        item = RetentionItem(
            tenant_id=tenant_id,
            policy_id=policy_id,
            data_type=data_type,
            data_id=data_id,
            expires_at=datetime.utcnow() + timedelta(days=policy.retention_days)
        )

        self._items[item.id] = item
        self._metrics["total_items"] += 1
        return item

    def get_expired_items(self, tenant_id: str) -> List[RetentionItem]:
        """Get all expired items for a tenant"""
        now = datetime.utcnow()
        return [
            i for i in self._items.values()
            if i.tenant_id == tenant_id
            and i.status == RetentionStatus.ACTIVE
            and i.expires_at
            and i.expires_at <= now
        ]

    def get_policy(self, policy_id: str) -> Optional[RetentionPolicy]:
        """Get a policy by ID"""
        return self._policies.get(policy_id)

    def get_policies_by_tenant(self, tenant_id: str) -> List[RetentionPolicy]:
        """Get all policies for a tenant"""
        return [p for p in self._policies.values() if p.tenant_id == tenant_id]

    def apply_legal_hold(self, policy_id: str) -> bool:
        """Apply legal hold to a policy"""
        policy = self._policies.get(policy_id)
        if not policy:
            return False
        policy.legal_hold = True
        return True

    def release_legal_hold(self, policy_id: str) -> bool:
        """Release legal hold from a policy"""
        policy = self._policies.get(policy_id)
        if not policy:
            return False
        policy.legal_hold = False
        return True

    def get_metrics(self) -> Dict[str, Any]:
        """Get retention metrics"""
        return self._metrics.copy()
