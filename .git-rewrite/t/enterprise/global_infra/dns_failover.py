# DNS Failover - Week 51 Builder 5
# DNS-based failover

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class FailoverPolicy(Enum):
    ACTIVE_PASSIVE = "active_passive"
    ACTIVE_ACTIVE = "active_active"
    WEIGHTED = "weighted"
    LATENCY = "latency"


class FailoverStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILOVER_ACTIVE = "failover_active"
    UNHEALTHY = "unhealthy"


@dataclass
class FailoverEndpoint:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    endpoint: str = ""
    region: str = ""
    weight: int = 100
    priority: int = 1
    is_primary: bool = False
    is_healthy: bool = True
    health_check_url: str = ""
    last_check: Optional[datetime] = None
    consecutive_failures: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FailoverGroup:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    domain: str = ""
    policy: FailoverPolicy = FailoverPolicy.ACTIVE_PASSIVE
    endpoints: List[str] = field(default_factory=list)
    status: FailoverStatus = FailoverStatus.HEALTHY
    primary_endpoint_id: Optional[str] = None
    active_endpoint_id: Optional[str] = None
    failover_threshold: int = 3
    recovery_threshold: int = 2
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FailoverEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    group_id: str = ""
    from_endpoint: str = ""
    to_endpoint: str = ""
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


class DNSFailover:
    """DNS-based failover management"""

    def __init__(self):
        self._groups: Dict[str, FailoverGroup] = {}
        self._endpoints: Dict[str, FailoverEndpoint] = {}
        self._events: List[FailoverEvent] = []
        self._metrics = {
            "total_groups": 0,
            "total_failovers": 0,
            "by_policy": {}
        }

    def create_group(
        self,
        name: str,
        domain: str,
        policy: FailoverPolicy = FailoverPolicy.ACTIVE_PASSIVE,
        failover_threshold: int = 3,
        recovery_threshold: int = 2
    ) -> FailoverGroup:
        """Create a failover group"""
        group = FailoverGroup(
            name=name,
            domain=domain,
            policy=policy,
            failover_threshold=failover_threshold,
            recovery_threshold=recovery_threshold
        )
        self._groups[group.id] = group
        self._metrics["total_groups"] += 1

        policy_key = policy.value
        self._metrics["by_policy"][policy_key] = \
            self._metrics["by_policy"].get(policy_key, 0) + 1

        return group

    def delete_group(self, group_id: str) -> bool:
        """Delete a failover group"""
        if group_id not in self._groups:
            return False

        group = self._groups[group_id]
        for endpoint_id in group.endpoints:
            if endpoint_id in self._endpoints:
                del self._endpoints[endpoint_id]

        del self._groups[group_id]
        return True

    def add_endpoint(
        self,
        group_id: str,
        name: str,
        endpoint: str,
        region: str = "",
        weight: int = 100,
        priority: int = 1,
        is_primary: bool = False,
        health_check_url: str = ""
    ) -> Optional[FailoverEndpoint]:
        """Add an endpoint to a group"""
        group = self._groups.get(group_id)
        if not group:
            return None

        ep = FailoverEndpoint(
            name=name,
            endpoint=endpoint,
            region=region,
            weight=weight,
            priority=priority,
            is_primary=is_primary,
            health_check_url=health_check_url
        )

        self._endpoints[ep.id] = ep
        group.endpoints.append(ep.id)

        if is_primary:
            group.primary_endpoint_id = ep.id
            group.active_endpoint_id = ep.id

        return ep

    def remove_endpoint(self, endpoint_id: str) -> bool:
        """Remove an endpoint"""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            return False

        for group in self._groups.values():
            if endpoint_id in group.endpoints:
                group.endpoints.remove(endpoint_id)

        del self._endpoints[endpoint_id]
        return True

    def update_endpoint_health(
        self,
        endpoint_id: str,
        is_healthy: bool
    ) -> Optional[str]:
        """Update endpoint health and trigger failover if needed"""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            return None

        endpoint.last_check = datetime.utcnow()

        if is_healthy:
            endpoint.consecutive_failures = 0
            endpoint.is_healthy = True
        else:
            endpoint.consecutive_failures += 1

        # Find group containing this endpoint
        for group in self._groups.values():
            if endpoint_id not in group.endpoints:
                continue

            # Check if failover needed
            if endpoint_id == group.active_endpoint_id:
                if endpoint.consecutive_failures >= group.failover_threshold:
                    return self._trigger_failover(group, endpoint)

            # Check if recovery possible
            if group.active_endpoint_id != group.primary_endpoint_id:
                primary = self._endpoints.get(group.primary_endpoint_id)
                if primary and primary.is_healthy and \
                   primary.consecutive_failures < group.recovery_threshold:
                    self._recover_to_primary(group)

        return None

    def _trigger_failover(
        self,
        group: FailoverGroup,
        failed_endpoint: FailoverEndpoint
    ) -> str:
        """Trigger failover to next healthy endpoint"""
        failed_endpoint.is_healthy = False

        # Find next healthy endpoint
        healthy_endpoints = [
            ep for ep in [
                self._endpoints[eid] for eid in group.endpoints
                if eid in self._endpoints
            ]
            if ep.id != failed_endpoint.id and ep.is_healthy
        ]

        if not healthy_endpoints:
            group.status = FailoverStatus.UNHEALTHY
            return ""

        # Select by policy
        if group.policy == FailoverPolicy.ACTIVE_PASSIVE:
            # Select by priority
            next_ep = min(healthy_endpoints, key=lambda e: e.priority)
        elif group.policy == FailoverPolicy.WEIGHTED:
            # Weighted selection
            import random
            total_weight = sum(e.weight for e in healthy_endpoints)
            r = random.uniform(0, total_weight)
            current = 0
            next_ep = healthy_endpoints[0]
            for ep in healthy_endpoints:
                current += ep.weight
                if r <= current:
                    next_ep = ep
                    break
        else:
            next_ep = healthy_endpoints[0]

        # Record event
        event = FailoverEvent(
            group_id=group.id,
            from_endpoint=failed_endpoint.id,
            to_endpoint=next_ep.id,
            reason=f"Health check failed {failed_endpoint.consecutive_failures} times"
        )
        self._events.append(event)

        group.active_endpoint_id = next_ep.id
        group.status = FailoverStatus.FAILOVER_ACTIVE
        self._metrics["total_failovers"] += 1

        return next_ep.id

    def _recover_to_primary(self, group: FailoverGroup) -> bool:
        """Recover to primary endpoint"""
        primary = self._endpoints.get(group.primary_endpoint_id)
        if not primary or not primary.is_healthy:
            return False

        current = self._endpoints.get(group.active_endpoint_id)
        if current:
            event = FailoverEvent(
                group_id=group.id,
                from_endpoint=current.id,
                to_endpoint=primary.id,
                reason="Primary endpoint recovered"
            )
            self._events.append(event)

        group.active_endpoint_id = primary.id
        group.status = FailoverStatus.HEALTHY
        return True

    def get_group(self, group_id: str) -> Optional[FailoverGroup]:
        """Get group by ID"""
        return self._groups.get(group_id)

    def get_endpoint(self, endpoint_id: str) -> Optional[FailoverEndpoint]:
        """Get endpoint by ID"""
        return self._endpoints.get(endpoint_id)

    def get_active_endpoint(self, group_id: str) -> Optional[FailoverEndpoint]:
        """Get active endpoint for a group"""
        group = self._groups.get(group_id)
        if not group or not group.active_endpoint_id:
            return None
        return self._endpoints.get(group.active_endpoint_id)

    def get_endpoints_by_group(self, group_id: str) -> List[FailoverEndpoint]:
        """Get all endpoints in a group"""
        group = self._groups.get(group_id)
        if not group:
            return []
        return [self._endpoints[eid] for eid in group.endpoints if eid in self._endpoints]

    def get_failover_history(
        self,
        group_id: str,
        limit: int = 100
    ) -> List[FailoverEvent]:
        """Get failover history for a group"""
        events = [e for e in self._events if e.group_id == group_id]
        return events[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        """Get failover metrics"""
        return self._metrics.copy()
