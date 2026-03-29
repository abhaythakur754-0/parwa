"""
Service Registry

Service discovery and registry for backend services.
"""

from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging
import asyncio
import time

logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    """Service health status"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DRAINING = "draining"
    UNKNOWN = "unknown"


@dataclass
class ServiceInstance:
    """A single service instance"""
    instance_id: str
    service_name: str
    host: str
    port: int
    status: ServiceStatus = ServiceStatus.HEALTHY
    weight: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    request_count: int = 0
    error_count: int = 0

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def error_rate(self) -> float:
        if self.request_count == 0:
            return 0
        return (self.error_count / self.request_count) * 100


@dataclass
class ServiceDefinition:
    """Definition of a service"""
    service_name: str
    instances: List[ServiceInstance] = field(default_factory=list)
    health_check_path: str = "/health"
    health_check_interval: int = 30
    load_balance_strategy: str = "round_robin"
    metadata: Dict[str, Any] = field(default_factory=dict)


class ServiceRegistry:
    """
    Service discovery and registry.

    Features:
    - Service registration/deregistration
    - Health checking
    - Load balancing support
    - Instance weighting
    """

    def __init__(
        self,
        heartbeat_timeout: int = 60,
        health_check_enabled: bool = True
    ):
        self.heartbeat_timeout = heartbeat_timeout
        self.health_check_enabled = health_check_enabled

        # Service storage
        self._services: Dict[str, ServiceDefinition] = {}
        self._instances: Dict[str, ServiceInstance] = {}

        # Load balancing state
        self._round_robin_index: Dict[str, int] = {}

        # Metrics
        self._metrics = {
            "total_registrations": 0,
            "total_deregistrations": 0,
            "total_health_checks": 0,
            "instances_healthy": 0,
            "instances_unhealthy": 0
        }

    def register(
        self,
        service_name: str,
        host: str,
        port: int,
        weight: int = 1,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ServiceInstance:
        """
        Register a service instance.

        Args:
            service_name: Name of the service
            host: Instance host
            port: Instance port
            weight: Load balancing weight
            metadata: Additional metadata

        Returns:
            Registered ServiceInstance
        """
        instance_id = f"{service_name}_{host}_{port}"

        instance = ServiceInstance(
            instance_id=instance_id,
            service_name=service_name,
            host=host,
            port=port,
            weight=weight,
            metadata=metadata or {}
        )

        # Store instance
        self._instances[instance_id] = instance

        # Add to service definition
        if service_name not in self._services:
            self._services[service_name] = ServiceDefinition(service_name=service_name)

        # Remove old instance with same ID if exists
        self._services[service_name].instances = [
            i for i in self._services[service_name].instances
            if i.instance_id != instance_id
        ]
        self._services[service_name].instances.append(instance)

        self._metrics["total_registrations"] += 1
        self._metrics["instances_healthy"] += 1

        logger.info(f"Registered instance: {instance_id}")
        return instance

    def deregister(self, instance_id: str) -> bool:
        """
        Deregister a service instance.

        Args:
            instance_id: Instance to deregister

        Returns:
            True if deregistered, False if not found
        """
        instance = self._instances.get(instance_id)
        if not instance:
            return False

        # Remove from instances
        del self._instances[instance_id]

        # Remove from service
        service = self._services.get(instance.service_name)
        if service:
            service.instances = [
                i for i in service.instances
                if i.instance_id != instance_id
            ]

        self._metrics["total_deregistrations"] += 1

        if instance.status == ServiceStatus.HEALTHY:
            self._metrics["instances_healthy"] -= 1
        else:
            self._metrics["instances_unhealthy"] -= 1

        logger.info(f"Deregistered instance: {instance_id}")
        return True

    def get_instance(
        self,
        service_name: str,
        strategy: str = "round_robin"
    ) -> Optional[ServiceInstance]:
        """
        Get an instance for a service using load balancing.

        Args:
            service_name: Service to get instance for
            strategy: Load balancing strategy

        Returns:
            ServiceInstance or None
        """
        service = self._services.get(service_name)
        if not service:
            return None

        # Filter healthy instances
        healthy = [
            i for i in service.instances
            if i.status == ServiceStatus.HEALTHY
        ]

        if not healthy:
            return None

        if strategy == "round_robin":
            return self._round_robin(service_name, healthy)
        elif strategy == "weighted":
            return self._weighted_selection(healthy)
        elif strategy == "least_connections":
            return self._least_connections(healthy)
        else:
            return healthy[0]

    def _round_robin(
        self,
        service_name: str,
        instances: List[ServiceInstance]
    ) -> ServiceInstance:
        """Round-robin selection"""
        index = self._round_robin_index.get(service_name, 0)
        instance = instances[index % len(instances)]
        self._round_robin_index[service_name] = index + 1
        return instance

    def _weighted_selection(
        self,
        instances: List[ServiceInstance]
    ) -> ServiceInstance:
        """Weighted random selection"""
        import random

        total_weight = sum(i.weight for i in instances)
        r = random.uniform(0, total_weight)

        cumulative = 0
        for instance in instances:
            cumulative += instance.weight
            if r <= cumulative:
                return instance

        return instances[-1]

    def _least_connections(
        self,
        instances: List[ServiceInstance]
    ) -> ServiceInstance:
        """Select instance with least connections"""
        return min(instances, key=lambda i: i.request_count)

    def heartbeat(self, instance_id: str) -> bool:
        """
        Record a heartbeat from an instance.

        Args:
            instance_id: Instance sending heartbeat

        Returns:
            True if heartbeat recorded, False if instance not found
        """
        instance = self._instances.get(instance_id)
        if not instance:
            return False

        instance.last_heartbeat = datetime.utcnow()
        return True

    def set_instance_status(
        self,
        instance_id: str,
        status: ServiceStatus
    ) -> bool:
        """Set instance health status"""
        instance = self._instances.get(instance_id)
        if not instance:
            return False

        old_status = instance.status
        instance.status = status

        # Update metrics
        if old_status == ServiceStatus.HEALTHY and status != ServiceStatus.HEALTHY:
            self._metrics["instances_healthy"] -= 1
            self._metrics["instances_unhealthy"] += 1
        elif old_status != ServiceStatus.HEALTHY and status == ServiceStatus.HEALTHY:
            self._metrics["instances_healthy"] += 1
            self._metrics["instances_unhealthy"] -= 1

        return True

    def record_request(
        self,
        instance_id: str,
        error: bool = False
    ) -> None:
        """Record a request to an instance"""
        instance = self._instances.get(instance_id)
        if instance:
            instance.request_count += 1
            if error:
                instance.error_count += 1

    def get_service(self, service_name: str) -> Optional[ServiceDefinition]:
        """Get a service definition"""
        return self._services.get(service_name)

    def get_instances(self, service_name: str) -> List[ServiceInstance]:
        """Get all instances for a service"""
        service = self._services.get(service_name)
        return service.instances if service else []

    def get_all_services(self) -> List[ServiceDefinition]:
        """Get all registered services"""
        return list(self._services.values())

    def check_health(self) -> Dict[str, Any]:
        """
        Check health of all instances.

        Returns:
            Health check results
        """
        self._metrics["total_health_checks"] += 1
        results = {
            "healthy": 0,
            "unhealthy": 0,
            "unknown": 0,
            "details": {}
        }

        now = datetime.utcnow()
        timeout = timedelta(seconds=self.heartbeat_timeout)

        for instance_id, instance in self._instances.items():
            # Check heartbeat timeout
            if now - instance.last_heartbeat > timeout:
                instance.status = ServiceStatus.UNHEALTHY

            if instance.status == ServiceStatus.HEALTHY:
                results["healthy"] += 1
            elif instance.status == ServiceStatus.UNHEALTHY:
                results["unhealthy"] += 1
            else:
                results["unknown"] += 1

            results["details"][instance_id] = {
                "status": instance.status.value,
                "last_heartbeat": instance.last_heartbeat.isoformat(),
                "error_rate": round(instance.error_rate, 2)
            }

        return results

    def cleanup_stale_instances(self) -> int:
        """Remove instances that haven't sent heartbeats"""
        now = datetime.utcnow()
        timeout = timedelta(seconds=self.heartbeat_timeout * 2)

        stale_ids = [
            iid for iid, inst in self._instances.items()
            if now - inst.last_heartbeat > timeout
        ]

        for instance_id in stale_ids:
            self.deregister(instance_id)

        return len(stale_ids)

    def get_metrics(self) -> Dict[str, Any]:
        """Get registry metrics"""
        return {
            **self._metrics,
            "total_services": len(self._services),
            "total_instances": len(self._instances)
        }
