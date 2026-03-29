# Region Manager - Week 51 Builder 4
# Multi-region management

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class RegionStatus(Enum):
    ACTIVE = "active"
    STANDBY = "standby"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


class RegionTier(Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    EDGE = "edge"


@dataclass
class Region:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    code: str = ""
    tier: RegionTier = RegionTier.PRIMARY
    status: RegionStatus = RegionStatus.ACTIVE
    endpoint: str = ""
    capacity: int = 100
    current_load: int = 0
    data_residency: str = ""
    compliance_tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


class RegionManager:
    """Manages multiple deployment regions"""

    def __init__(self):
        self._regions: Dict[str, Region] = {}
        self._metrics = {
            "total_regions": 0,
            "active_regions": 0,
            "by_tier": {},
            "by_status": {}
        }

    def create_region(
        self,
        name: str,
        code: str,
        tier: RegionTier = RegionTier.PRIMARY,
        endpoint: str = "",
        capacity: int = 100,
        data_residency: str = "",
        compliance_tags: Optional[List[str]] = None
    ) -> Region:
        """Create a new region"""
        region = Region(
            name=name,
            code=code,
            tier=tier,
            endpoint=endpoint,
            capacity=capacity,
            data_residency=data_residency,
            compliance_tags=compliance_tags or []
        )
        self._regions[region.id] = region
        self._metrics["total_regions"] += 1

        tier_key = tier.value
        self._metrics["by_tier"][tier_key] = \
            self._metrics["by_tier"].get(tier_key, 0) + 1

        return region

    def update_region_status(
        self,
        region_id: str,
        status: RegionStatus
    ) -> bool:
        """Update region status"""
        region = self._regions.get(region_id)
        if not region:
            return False

        old_status = region.status.value
        region.status = status

        # Update metrics
        self._metrics["by_status"][old_status] = \
            max(0, self._metrics["by_status"].get(old_status, 0) - 1)
        new_status = status.value
        self._metrics["by_status"][new_status] = \
            self._metrics["by_status"].get(new_status, 0) + 1

        return True

    def update_region_load(
        self,
        region_id: str,
        current_load: int
    ) -> bool:
        """Update region load"""
        region = self._regions.get(region_id)
        if not region:
            return False
        region.current_load = current_load
        return True

    def get_region(self, region_id: str) -> Optional[Region]:
        """Get region by ID"""
        return self._regions.get(region_id)

    def get_region_by_code(self, code: str) -> Optional[Region]:
        """Get region by code"""
        for region in self._regions.values():
            if region.code == code:
                return region
        return None

    def get_regions_by_tier(self, tier: RegionTier) -> List[Region]:
        """Get all regions of a tier"""
        return [r for r in self._regions.values() if r.tier == tier]

    def get_regions_by_status(self, status: RegionStatus) -> List[Region]:
        """Get all regions with a status"""
        return [r for r in self._regions.values() if r.status == status]

    def get_active_regions(self) -> List[Region]:
        """Get all active regions"""
        return self.get_regions_by_status(RegionStatus.ACTIVE)

    def get_available_regions(
        self,
        min_capacity: int = 0,
        data_residency: Optional[str] = None
    ) -> List[Region]:
        """Get available regions based on criteria"""
        regions = [
            r for r in self._regions.values()
            if r.status == RegionStatus.ACTIVE
            and r.current_load < r.capacity
        ]

        if min_capacity > 0:
            regions = [r for r in regions if r.capacity >= min_capacity]

        if data_residency:
            regions = [r for r in regions if r.data_residency == data_residency]

        return regions

    def get_region_with_least_load(self) -> Optional[Region]:
        """Get region with least load"""
        active = self.get_active_regions()
        if not active:
            return None
        return min(active, key=lambda r: r.current_load / r.capacity if r.capacity > 0 else 0)

    def get_region_with_most_capacity(self) -> Optional[Region]:
        """Get region with most available capacity"""
        active = self.get_active_regions()
        if not active:
            return None
        return max(active, key=lambda r: r.capacity - r.current_load)

    def check_compliance(
        self,
        region_id: str,
        required_tags: List[str]
    ) -> bool:
        """Check if region meets compliance requirements"""
        region = self._regions.get(region_id)
        if not region:
            return False
        return all(tag in region.compliance_tags for tag in required_tags)

    def delete_region(self, region_id: str) -> bool:
        """Delete a region"""
        if region_id in self._regions:
            region = self._regions[region_id]
            self._metrics["total_regions"] -= 1
            self._metrics["by_tier"][region.tier.value] -= 1
            del self._regions[region_id]
            return True
        return False

    def get_region_utilization(self, region_id: str) -> Optional[float]:
        """Get region utilization percentage"""
        region = self._regions.get(region_id)
        if not region or region.capacity == 0:
            return None
        return (region.current_load / region.capacity) * 100

    def get_metrics(self) -> Dict[str, Any]:
        """Get region manager metrics"""
        active = len(self.get_active_regions())
        return {
            **self._metrics,
            "active_regions": active,
            "availability": (active / self._metrics["total_regions"] * 100)
            if self._metrics["total_regions"] > 0 else 0
        }
