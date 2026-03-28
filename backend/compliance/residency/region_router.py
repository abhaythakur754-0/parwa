"""
Region Router for Data Residency.

Routes requests to correct region:
- Client-to-region mapping
- Dynamic region selection
- Failover handling
- Latency optimization
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from enum import Enum
import logging
import random

logger = logging.getLogger(__name__)


class Region(str, Enum):
    """Available regions."""
    EU = "eu-west-1"
    US = "us-east-1"
    APAC = "ap-southeast-1"


@dataclass
class RegionConfig:
    """Configuration for a region."""
    region: Region
    endpoint: str
    priority: int = 1
    healthy: bool = True
    latency_ms: int = 100
    last_check: Optional[datetime] = None


@dataclass
class RoutingDecision:
    """Result of a routing decision."""
    client_id: str
    selected_region: Region
    reason: str
    latency_ms: int
    timestamp: datetime = field(default_factory=datetime.now)
    alternate_regions: List[Region] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "client_id": self.client_id,
            "selected_region": self.selected_region.value,
            "reason": self.reason,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoformat(),
            "alternate_regions": [r.value for r in self.alternate_regions]
        }


class RegionRouter:
    """
    Routes requests to correct region.

    Features:
    - Route requests to correct region
    - Client-to-region mapping
    - Dynamic region selection
    - Failover handling
    - Latency optimization
    """

    def __init__(
        self,
        client_region_mapping: Optional[Dict[str, Region]] = None,
        region_configs: Optional[Dict[Region, RegionConfig]] = None
    ):
        """
        Initialize the region router.

        Args:
            client_region_mapping: Mapping of client IDs to regions
            region_configs: Configuration for each region
        """
        self._client_regions: Dict[str, Region] = client_region_mapping or {}
        self._region_configs: Dict[Region, RegionConfig] = region_configs or self._default_configs()
        self._routing_history: List[RoutingDecision] = []

    def _default_configs(self) -> Dict[Region, RegionConfig]:
        """Get default region configurations."""
        return {
            Region.EU: RegionConfig(
                region=Region.EU,
                endpoint="parwa-eu.example.com",
                priority=1,
                latency_ms=50
            ),
            Region.US: RegionConfig(
                region=Region.US,
                endpoint="parwa-us.example.com",
                priority=1,
                latency_ms=30
            ),
            Region.APAC: RegionConfig(
                region=Region.APAC,
                endpoint="parwa-apac.example.com",
                priority=1,
                latency_ms=80
            )
        }

    def register_client(self, client_id: str, region: Region) -> None:
        """
        Register a client with their assigned region.

        Args:
            client_id: Client identifier
            region: Assigned region for client
        """
        self._client_regions[client_id] = region
        logger.info(f"Registered client {client_id} to region {region.value}")

    def get_region(self, client_id: str) -> Optional[Region]:
        """
        Get the assigned region for a client.

        Args:
            client_id: Client identifier

        Returns:
            Assigned region or None
        """
        return self._client_regions.get(client_id)

    def route(
        self,
        client_id: str,
        prefer_low_latency: bool = True
    ) -> RoutingDecision:
        """
        Route a request for a client.

        Args:
            client_id: Client identifier
            prefer_low_latency: Whether to optimize for latency

        Returns:
            RoutingDecision with selected region
        """
        assigned_region = self.get_region(client_id)

        if assigned_region:
            # Client has assigned region - use it
            config = self._region_configs.get(assigned_region)
            latency = config.latency_ms if config else 100

            decision = RoutingDecision(
                client_id=client_id,
                selected_region=assigned_region,
                reason="Assigned region",
                latency_ms=latency,
                alternate_regions=[]
            )
        else:
            # No assigned region - select best available
            selected_region = self._select_best_region(prefer_low_latency)
            config = self._region_configs.get(selected_region)
            latency = config.latency_ms if config else 100

            decision = RoutingDecision(
                client_id=client_id,
                selected_region=selected_region,
                reason="Best available region",
                latency_ms=latency,
                alternate_regions=[r for r in Region if r != selected_region]
            )

        self._routing_history.append(decision)
        return decision

    def _select_best_region(self, prefer_low_latency: bool) -> Region:
        """Select the best available region."""
        healthy_regions = [
            (region, config)
            for region, config in self._region_configs.items()
            if config.healthy
        ]

        if not healthy_regions:
            # All regions unhealthy - return EU as default
            logger.warning("All regions unhealthy, defaulting to EU")
            return Region.EU

        if prefer_low_latency:
            # Sort by latency
            healthy_regions.sort(key=lambda x: x[1].latency_ms)
            return healthy_regions[0][0]
        else:
            # Sort by priority
            healthy_regions.sort(key=lambda x: x[1].priority)
            return healthy_regions[0][0]

    def route_with_failover(
        self,
        client_id: str,
        excluded_regions: Optional[List[Region]] = None
    ) -> RoutingDecision:
        """
        Route with failover support.

        Args:
            client_id: Client identifier
            excluded_regions: Regions to exclude from selection

        Returns:
            RoutingDecision with failover options
        """
        excluded = excluded_regions or []
        assigned_region = self.get_region(client_id)

        if assigned_region and assigned_region not in excluded:
            config = self._region_configs.get(assigned_region)
            if config and config.healthy:
                # Primary region available
                return RoutingDecision(
                    client_id=client_id,
                    selected_region=assigned_region,
                    reason="Primary region",
                    latency_ms=config.latency_ms,
                    alternate_regions=[]
                )

        # Need to failover
        available_regions = [
            region for region in Region
            if region not in excluded and self._region_configs.get(region, RegionConfig(region=region, endpoint="")).healthy
        ]

        if not available_regions:
            raise RuntimeError(f"No available regions for client {client_id}")

        # Select best available
        selected = self._select_best_region(True)
        config = self._region_configs.get(selected)

        decision = RoutingDecision(
            client_id=client_id,
            selected_region=selected,
            reason="Failover",
            latency_ms=config.latency_ms if config else 100,
            alternate_regions=[r for r in available_regions if r != selected]
        )

        self._routing_history.append(decision)
        return decision

    def update_region_health(self, region: Region, healthy: bool) -> None:
        """
        Update health status of a region.

        Args:
            region: Region to update
            healthy: Health status
        """
        if region in self._region_configs:
            self._region_configs[region].healthy = healthy
            self._region_configs[region].last_check = datetime.now()
            logger.info(f"Region {region.value} health updated to {healthy}")

    def update_region_latency(self, region: Region, latency_ms: int) -> None:
        """
        Update latency for a region.

        Args:
            region: Region to update
            latency_ms: Measured latency in milliseconds
        """
        if region in self._region_configs:
            self._region_configs[region].latency_ms = latency_ms
            logger.debug(f"Region {region.value} latency updated to {latency_ms}ms")

    def get_region_config(self, region: Region) -> Optional[RegionConfig]:
        """Get configuration for a region."""
        return self._region_configs.get(region)

    def get_all_regions(self) -> List[Region]:
        """Get all available regions."""
        return list(Region)

    def get_healthy_regions(self) -> List[Region]:
        """Get all healthy regions."""
        return [
            region for region, config in self._region_configs.items()
            if config.healthy
        ]

    def get_routing_stats(self) -> Dict[str, Any]:
        """
        Get routing statistics.

        Returns:
            Statistics dictionary
        """
        region_counts = {}
        for decision in self._routing_history:
            region = decision.selected_region.value
            region_counts[region] = region_counts.get(region, 0) + 1

        return {
            "total_routes": len(self._routing_history),
            "registered_clients": len(self._client_regions),
            "healthy_regions": len(self.get_healthy_regions()),
            "routes_by_region": region_counts,
            "region_configs": {
                region.value: {
                    "healthy": config.healthy,
                    "latency_ms": config.latency_ms,
                    "priority": config.priority
                }
                for region, config in self._region_configs.items()
            }
        }


def get_region_router() -> RegionRouter:
    """Factory function to create a region router."""
    return RegionRouter()
