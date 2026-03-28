# Failover Manager - Week 50 Builder 4
# Failover automation

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class FailoverStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING_OVER = "failing_over"
    FAILOVER_COMPLETE = "failover_complete"
    FAILED = "failed"


class RegionStatus(Enum):
    PRIMARY = "primary"
    STANDBY = "standby"
    OFFLINE = "offline"


@dataclass
class Region:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    status: RegionStatus = RegionStatus.STANDBY
    endpoint: str = ""
    priority: int = 1
    health_check_url: str = ""
    last_health_check: Optional[datetime] = None
    is_healthy: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FailoverEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_region_id: str = ""
    to_region_id: str = ""
    status: FailoverStatus = FailoverStatus.HEALTHY
    reason: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    dns_updated: bool = False
    traffic_switched: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


class FailoverManager:
    """Manages automated failover"""

    def __init__(self):
        self._regions: Dict[str, Region] = {}
        self._events: List[FailoverEvent] = []
        self._primary_region_id: Optional[str] = None
        self._metrics = {
            "total_failovers": 0,
            "successful": 0,
            "failed": 0,
            "total_regions": 0
        }

    def register_region(
        self,
        name: str,
        endpoint: str,
        priority: int = 1,
        health_check_url: str = "",
        is_primary: bool = False
    ) -> Region:
        """Register a region"""
        region = Region(
            name=name,
            endpoint=endpoint,
            priority=priority,
            health_check_url=health_check_url,
            status=RegionStatus.PRIMARY if is_primary else RegionStatus.STANDBY
        )
        self._regions[region.id] = region
        self._metrics["total_regions"] += 1

        if is_primary:
            self._primary_region_id = region.id

        return region

    def update_region_health(
        self,
        region_id: str,
        is_healthy: bool
    ) -> bool:
        """Update region health status"""
        region = self._regions.get(region_id)
        if not region:
            return False

        region.is_healthy = is_healthy
        region.last_health_check = datetime.utcnow()

        # Check if primary is unhealthy - trigger failover
        if region_id == self._primary_region_id and not is_healthy:
            self._trigger_automatic_failover(region_id)

        return True

    def _trigger_automatic_failover(self, from_region_id: str) -> Optional[FailoverEvent]:
        """Trigger automatic failover"""
        standby_regions = [
            r for r in self._regions.values()
            if r.status == RegionStatus.STANDBY and r.is_healthy
        ]

        if not standby_regions:
            return None

        # Sort by priority
        standby_regions.sort(key=lambda r: r.priority)
        target = standby_regions[0]

        return self.initiate_failover(from_region_id, target.id, "Automatic failover - primary unhealthy")

    def initiate_failover(
        self,
        from_region_id: str,
        to_region_id: str,
        reason: str = ""
    ) -> Optional[FailoverEvent]:
        """Initiate a failover"""
        from_region = self._regions.get(from_region_id)
        to_region = self._regions.get(to_region_id)

        if not from_region or not to_region:
            return None

        event = FailoverEvent(
            from_region_id=from_region_id,
            to_region_id=to_region_id,
            status=FailoverStatus.FAILING_OVER,
            reason=reason,
            started_at=datetime.utcnow()
        )
        self._events.append(event)
        self._metrics["total_failovers"] += 1
        return event

    def complete_dns_update(self, event_id: str) -> bool:
        """Mark DNS update complete"""
        for event in self._events:
            if event.id == event_id and event.status == FailoverStatus.FAILING_OVER:
                event.dns_updated = True
                return True
        return False

    def complete_traffic_switch(self, event_id: str) -> bool:
        """Mark traffic switch complete"""
        for event in self._events:
            if event.id == event_id and event.status == FailoverStatus.FAILING_OVER:
                event.traffic_switched = True
                return True
        return False

    def complete_failover(self, event_id: str) -> bool:
        """Complete a failover"""
        for event in self._events:
            if event.id == event_id and event.status == FailoverStatus.FAILING_OVER:
                event.status = FailoverStatus.FAILOVER_COMPLETE
                event.completed_at = datetime.utcnow()

                # Update region statuses
                from_region = self._regions.get(event.from_region_id)
                to_region = self._regions.get(event.to_region_id)

                if from_region:
                    from_region.status = RegionStatus.STANDBY
                if to_region:
                    to_region.status = RegionStatus.PRIMARY
                    self._primary_region_id = to_region.id

                self._metrics["successful"] += 1
                return True
        return False

    def fail_failover(self, event_id: str, reason: str = "") -> bool:
        """Mark failover as failed"""
        for event in self._events:
            if event.id == event_id:
                event.status = FailoverStatus.FAILED
                event.completed_at = datetime.utcnow()
                event.reason = f"{event.reason} - {reason}" if event.reason else reason
                self._metrics["failed"] += 1
                return True
        return False

    def get_region(self, region_id: str) -> Optional[Region]:
        """Get region by ID"""
        return self._regions.get(region_id)

    def get_primary_region(self) -> Optional[Region]:
        """Get current primary region"""
        if self._primary_region_id:
            return self._regions.get(self._primary_region_id)
        return None

    def get_standby_regions(self) -> List[Region]:
        """Get all standby regions"""
        return [r for r in self._regions.values() if r.status == RegionStatus.STANDBY]

    def get_healthy_regions(self) -> List[Region]:
        """Get all healthy regions"""
        return [r for r in self._regions.values() if r.is_healthy]

    def get_event(self, event_id: str) -> Optional[FailoverEvent]:
        """Get event by ID"""
        for event in self._events:
            if event.id == event_id:
                return event
        return None

    def get_active_events(self) -> List[FailoverEvent]:
        """Get active failover events"""
        return [e for e in self._events if e.status == FailoverStatus.FAILING_OVER]

    def get_event_history(self, limit: int = 100) -> List[FailoverEvent]:
        """Get event history"""
        return self._events[-limit:]

    def get_failover_status(self) -> FailoverStatus:
        """Get overall failover status"""
        if any(e.status == FailoverStatus.FAILING_OVER for e in self._events):
            return FailoverStatus.FAILING_OVER

        primary = self.get_primary_region()
        if not primary:
            return FailoverStatus.FAILED
        if not primary.is_healthy:
            return FailoverStatus.DEGRADED

        return FailoverStatus.HEALTHY

    def get_metrics(self) -> Dict[str, Any]:
        return {
            **self._metrics,
            "primary_region": self._primary_region_id,
            "failover_status": self.get_failover_status().value
        }

    def set_region_offline(self, region_id: str) -> bool:
        """Set region offline"""
        region = self._regions.get(region_id)
        if not region:
            return False
        region.status = RegionStatus.OFFLINE
        return True

    def bring_region_online(self, region_id: str) -> bool:
        """Bring region back online as standby"""
        region = self._regions.get(region_id)
        if not region:
            return False
        region.status = RegionStatus.STANDBY
        region.is_healthy = True
        return True
