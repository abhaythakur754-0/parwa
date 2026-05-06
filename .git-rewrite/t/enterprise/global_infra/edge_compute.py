# Edge Compute - Week 51 Builder 3
# Edge computing nodes

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class EdgeNodeStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"


class ComputeTier(Enum):
    LIGHT = "light"
    STANDARD = "standard"
    HEAVY = "heavy"


@dataclass
class EdgeNode:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    region: str = ""
    endpoint: str = ""
    status: EdgeNodeStatus = EdgeNodeStatus.ONLINE
    tier: ComputeTier = ComputeTier.STANDARD
    cpu_cores: int = 4
    memory_mb: int = 8192
    available_cpu: float = 100.0
    available_memory: float = 100.0
    active_functions: int = 0
    max_functions: int = 100
    last_heartbeat: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ComputeRequest:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    function_name: str = ""
    node_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    result: Optional[Any] = None
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)


class EdgeCompute:
    """Edge computing node management"""

    def __init__(self):
        self._nodes: Dict[str, EdgeNode] = {}
        self._requests: List[ComputeRequest] = []
        self._metrics = {
            "total_nodes": 0,
            "total_requests": 0,
            "requests_by_region": {},
            "avg_execution_time_ms": 0.0
        }

    def register_node(
        self,
        name: str,
        region: str,
        endpoint: str,
        tier: ComputeTier = ComputeTier.STANDARD,
        cpu_cores: int = 4,
        memory_mb: int = 8192
    ) -> EdgeNode:
        """Register an edge node"""
        node = EdgeNode(
            name=name,
            region=region,
            endpoint=endpoint,
            tier=tier,
            cpu_cores=cpu_cores,
            memory_mb=memory_mb,
            last_heartbeat=datetime.utcnow()
        )
        self._nodes[node.id] = node
        self._metrics["total_nodes"] += 1
        return node

    def deregister_node(self, node_id: str) -> bool:
        """Deregister an edge node"""
        if node_id in self._nodes:
            del self._nodes[node_id]
            return True
        return False

    def update_node_status(
        self,
        node_id: str,
        status: EdgeNodeStatus
    ) -> bool:
        """Update node status"""
        node = self._nodes.get(node_id)
        if not node:
            return False
        node.status = status
        node.last_heartbeat = datetime.utcnow()
        return True

    def update_node_resources(
        self,
        node_id: str,
        available_cpu: float,
        available_memory: float,
        active_functions: int
    ) -> bool:
        """Update node resource availability"""
        node = self._nodes.get(node_id)
        if not node:
            return False
        node.available_cpu = available_cpu
        node.available_memory = available_memory
        node.active_functions = active_functions
        node.last_heartbeat = datetime.utcnow()
        return True

    def get_available_node(
        self,
        region: Optional[str] = None,
        min_cpu: float = 0,
        min_memory: float = 0
    ) -> Optional[EdgeNode]:
        """Get best available node"""
        candidates = [
            n for n in self._nodes.values()
            if n.status == EdgeNodeStatus.ONLINE
            and n.available_cpu >= min_cpu
            and n.available_memory >= min_memory
            and n.active_functions < n.max_functions
        ]

        if region:
            candidates = [n for n in candidates if n.region == region]

        if not candidates:
            return None

        # Return node with most available resources
        return max(candidates, key=lambda n: (n.available_cpu, n.available_memory))

    def execute_request(
        self,
        function_name: str,
        payload: Dict[str, Any],
        region: Optional[str] = None
    ) -> Optional[ComputeRequest]:
        """Execute a compute request"""
        node = self.get_available_node(region)
        if not node:
            return None

        request = ComputeRequest(
            function_name=function_name,
            node_id=node.id,
            payload=payload,
            status="running"
        )

        self._requests.append(request)
        self._metrics["total_requests"] += 1
        node.active_functions += 1

        return request

    def complete_request(
        self,
        request_id: str,
        result: Any,
        execution_time_ms: float,
        memory_used_mb: float
    ) -> bool:
        """Complete a compute request"""
        for request in self._requests:
            if request.id == request_id and request.status == "running":
                request.status = "completed"
                request.result = result
                request.execution_time_ms = execution_time_ms
                request.memory_used_mb = memory_used_mb

                # Release node resources
                node = self._nodes.get(request.node_id)
                if node:
                    node.active_functions = max(0, node.active_functions - 1)

                return True
        return False

    def fail_request(self, request_id: str, error: str = "") -> bool:
        """Mark request as failed"""
        for request in self._requests:
            if request.id == request_id and request.status == "running":
                request.status = "failed"
                request.result = {"error": error}

                node = self._nodes.get(request.node_id)
                if node:
                    node.active_functions = max(0, node.active_functions - 1)

                return True
        return False

    def get_node(self, node_id: str) -> Optional[EdgeNode]:
        """Get node by ID"""
        return self._nodes.get(node_id)

    def get_nodes_by_region(self, region: str) -> List[EdgeNode]:
        """Get all nodes in a region"""
        return [n for n in self._nodes.values() if n.region == region]

    def get_online_nodes(self) -> List[EdgeNode]:
        """Get all online nodes"""
        return [n for n in self._nodes.values() if n.status == EdgeNodeStatus.ONLINE]

    def get_node_metrics(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific node"""
        node = self._nodes.get(node_id)
        if not node:
            return None

        return {
            "id": node.id,
            "name": node.name,
            "status": node.status.value,
            "cpu_usage": 100 - node.available_cpu,
            "memory_usage": 100 - node.available_memory,
            "active_functions": node.active_functions,
            "utilization": node.active_functions / node.max_functions * 100
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get overall metrics"""
        online = len(self.get_online_nodes())
        total = len(self._nodes)

        return {
            **self._metrics,
            "online_nodes": online,
            "total_nodes": total,
            "availability": (online / total * 100) if total > 0 else 0
        }
