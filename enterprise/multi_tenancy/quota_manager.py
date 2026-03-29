"""
Resource Quota Manager

Manages resource quotas for tenants in multi-tenant environments.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class ResourceType(str, Enum):
    """Types of resources that can be quotaed"""
    API_REQUESTS = "api_requests"
    STORAGE_BYTES = "storage_bytes"
    DATABASE_ROWS = "database_rows"
    BANDWIDTH_BYTES = "bandwidth_bytes"
    USERS = "users"
    TICKETS = "tickets"
    AI_RESPONSES = "ai_responses"
    WEBHOOK_CALLS = "webhook_calls"
    EXPORTS = "exports"
    CONCURRENT_SESSIONS = "concurrent_sessions"


class QuotaPeriod(str, Enum):
    """Quota period types"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    UNLIMITED = "unlimited"


@dataclass
class Quota:
    """Represents a resource quota"""
    quota_id: str
    tenant_id: str
    resource_type: ResourceType
    limit: int
    period: QuotaPeriod
    used: int = 0
    reset_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    warn_threshold: float = 0.8  # Warn at 80%
    hard_limit: bool = True  # Block when exceeded
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    @property
    def utilization(self) -> float:
        return (self.used / self.limit) * 100 if self.limit > 0 else 0

    @property
    def is_exceeded(self) -> bool:
        return self.used >= self.limit

    @property
    def is_warning(self) -> bool:
        return self.utilization >= (self.warn_threshold * 100)


@dataclass
class QuotaUsage:
    """Quota usage record"""
    usage_id: str
    tenant_id: str
    resource_type: ResourceType
    amount: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class QuotaManager:
    """
    Manages resource quotas for tenants.

    Features:
    - Multiple resource types
    - Flexible quota periods
    - Usage tracking
    - Warning thresholds
    - Quota enforcement
    """

    def __init__(self):
        # Quota storage
        self._quotas: Dict[str, Quota] = {}  # quota_id -> Quota
        self._tenant_quotas: Dict[str, Dict[ResourceType, str]] = {}  # tenant -> {resource -> quota_id}

        # Usage history
        self._usage_history: List[QuotaUsage] = []

        # Metrics
        self._metrics = {
            "total_quotas": 0,
            "quotas_exceeded": 0,
            "total_usage_records": 0
        }

    def create_quota(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        limit: int,
        period: QuotaPeriod = QuotaPeriod.MONTHLY,
        warn_threshold: float = 0.8,
        hard_limit: bool = True
    ) -> Quota:
        """Create a new quota for a tenant"""
        quota_id = f"quota_{tenant_id}_{resource_type.value}"

        # Calculate reset time
        reset_at = self._calculate_reset_time(period)

        quota = Quota(
            quota_id=quota_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            limit=limit,
            period=period,
            reset_at=reset_at,
            warn_threshold=warn_threshold,
            hard_limit=hard_limit
        )

        self._quotas[quota_id] = quota

        # Index by tenant
        if tenant_id not in self._tenant_quotas:
            self._tenant_quotas[tenant_id] = {}
        self._tenant_quotas[tenant_id][resource_type] = quota_id

        self._metrics["total_quotas"] += 1

        logger.info(f"Created quota {quota_id}: {limit} {resource_type.value} per {period.value}")
        return quota

    def _calculate_reset_time(self, period: QuotaPeriod) -> datetime:
        """Calculate when quota resets"""
        now = datetime.utcnow()

        if period == QuotaPeriod.HOURLY:
            return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        elif period == QuotaPeriod.DAILY:
            return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        elif period == QuotaPeriod.WEEKLY:
            days_until_monday = (7 - now.weekday()) % 7
            return (now + timedelta(days=days_until_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == QuotaPeriod.MONTHLY:
            next_month = now.replace(day=1) + timedelta(days=32)
            return next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == QuotaPeriod.YEARLY:
            return now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return None  # Unlimited

    def get_quota(self, tenant_id: str, resource_type: ResourceType) -> Optional[Quota]:
        """Get quota for tenant and resource type"""
        if tenant_id not in self._tenant_quotas:
            return None
        quota_id = self._tenant_quotas[tenant_id].get(resource_type)
        if not quota_id:
            return None
        return self._quotas.get(quota_id)

    def check_quota(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        amount: int = 1
    ) -> Dict[str, Any]:
        """
        Check if tenant can consume amount of resource.

        Returns:
            Dict with allowed status and quota info
        """
        quota = self.get_quota(tenant_id, resource_type)

        if not quota:
            # No quota = unlimited
            return {"allowed": True, "reason": "no_quota"}

        # Check if quota needs reset
        if quota.reset_at and datetime.utcnow() >= quota.reset_at:
            self._reset_quota(quota)

        result = {
            "allowed": True,
            "quota_id": quota.quota_id,
            "limit": quota.limit,
            "used": quota.used,
            "remaining": quota.remaining,
            "utilization": round(quota.utilization, 2)
        }

        if quota.is_exceeded:
            result["allowed"] = not quota.hard_limit
            result["reason"] = "quota_exceeded"
            if quota.hard_limit:
                self._metrics["quotas_exceeded"] += 1
        elif quota.is_warning:
            result["warning"] = True
            result["message"] = f"Quota usage at {quota.utilization:.1f}%"

        return result

    def consume_quota(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        amount: int = 1,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Consume quota for a resource.

        Returns:
            Dict with consumption result
        """
        check_result = self.check_quota(tenant_id, resource_type, amount)

        if not check_result.get("allowed", True):
            return check_result

        quota = self.get_quota(tenant_id, resource_type)

        if quota:
            quota.used += amount

            # Record usage
            usage_id = f"usage_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{len(self._usage_history)}"
            usage = QuotaUsage(
                usage_id=usage_id,
                tenant_id=tenant_id,
                resource_type=resource_type,
                amount=amount,
                description=description
            )
            self._usage_history.append(usage)
            self._metrics["total_usage_records"] += 1

        return {
            **check_result,
            "consumed": amount,
            "new_used": quota.used if quota else amount
        }

    def release_quota(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        amount: int = 1
    ) -> bool:
        """Release quota (for cancelled operations)"""
        quota = self.get_quota(tenant_id, resource_type)
        if not quota:
            return False

        quota.used = max(0, quota.used - amount)
        return True

    def _reset_quota(self, quota: Quota) -> None:
        """Reset a quota for new period"""
        quota.used = 0
        quota.reset_at = self._calculate_reset_time(quota.period)
        logger.info(f"Reset quota {quota.quota_id}")

    def update_quota_limit(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        new_limit: int
    ) -> Optional[Quota]:
        """Update quota limit"""
        quota = self.get_quota(tenant_id, resource_type)
        if not quota:
            return None

        quota.limit = new_limit
        logger.info(f"Updated quota {quota.quota_id} limit to {new_limit}")
        return quota

    def get_tenant_quotas(self, tenant_id: str) -> List[Quota]:
        """Get all quotas for a tenant"""
        if tenant_id not in self._tenant_quotas:
            return []

        return [
            self._quotas[quota_id]
            for quota_id in self._tenant_quotas[tenant_id].values()
            if quota_id in self._quotas
        ]

    def get_usage_history(
        self,
        tenant_id: str,
        resource_type: Optional[ResourceType] = None,
        limit: int = 100
    ) -> List[QuotaUsage]:
        """Get usage history for a tenant"""
        history = [u for u in self._usage_history if u.tenant_id == tenant_id]

        if resource_type:
            history = [u for u in history if u.resource_type == resource_type]

        return sorted(history, key=lambda x: x.timestamp, reverse=True)[:limit]

    def get_quota_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get quota summary for a tenant"""
        quotas = self.get_tenant_quotas(tenant_id)

        return {
            "tenant_id": tenant_id,
            "total_quotas": len(quotas),
            "quotas_exceeded": sum(1 for q in quotas if q.is_exceeded),
            "quotas_warning": sum(1 for q in quotas if q.is_warning and not q.is_exceeded),
            "quotas": [
                {
                    "resource": q.resource_type.value,
                    "limit": q.limit,
                    "used": q.used,
                    "remaining": q.remaining,
                    "utilization": round(q.utilization, 2),
                    "period": q.period.value,
                    "reset_at": q.reset_at.isoformat() if q.reset_at else None
                }
                for q in quotas
            ]
        }

    def delete_quota(self, tenant_id: str, resource_type: ResourceType) -> bool:
        """Delete a quota"""
        quota = self.get_quota(tenant_id, resource_type)
        if not quota:
            return False

        del self._quotas[quota.quota_id]
        del self._tenant_quotas[tenant_id][resource_type]

        return True

    def get_metrics(self) -> Dict[str, Any]:
        """Get quota manager metrics"""
        return {
            **self._metrics,
            "active_tenants": len(self._tenant_quotas)
        }
