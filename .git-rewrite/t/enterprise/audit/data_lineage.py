# Data Lineage - Week 49 Builder 3
# Data lineage tracking for governance

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class LineageDirection(Enum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"


@dataclass
class LineageNode:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    type: str = ""  # source, transformation, destination
    system: str = ""
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LineageEdge:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    tenant_id: str = ""
    transformation: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


class DataLineage:
    """Tracks data lineage and provenance"""

    def __init__(self):
        self._nodes: Dict[str, LineageNode] = {}
        self._edges: Dict[str, LineageEdge] = {}
        self._metrics = {
            "total_nodes": 0,
            "total_edges": 0,
            "by_type": {}
        }

    def add_node(
        self,
        tenant_id: str,
        name: str,
        type: str,
        system: str = "",
        description: str = ""
    ) -> LineageNode:
        """Add a lineage node"""
        node = LineageNode(
            tenant_id=tenant_id,
            name=name,
            type=type,
            system=system,
            description=description
        )
        self._nodes[node.id] = node
        self._metrics["total_nodes"] += 1
        self._metrics["by_type"][type] = self._metrics["by_type"].get(type, 0) + 1
        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        tenant_id: str,
        transformation: str = ""
    ) -> Optional[LineageEdge]:
        """Add an edge between nodes"""
        if source_id not in self._nodes or target_id not in self._nodes:
            return None

        edge = LineageEdge(
            source_id=source_id,
            target_id=target_id,
            tenant_id=tenant_id,
            transformation=transformation
        )
        self._edges[edge.id] = edge
        self._metrics["total_edges"] += 1
        return edge

    def get_node(self, node_id: str) -> Optional[LineageNode]:
        """Get a node by ID"""
        return self._nodes.get(node_id)

    def get_upstream(self, node_id: str) -> List[LineageNode]:
        """Get upstream nodes"""
        upstream = []
        for edge in self._edges.values():
            if edge.target_id == node_id:
                source = self._nodes.get(edge.source_id)
                if source:
                    upstream.append(source)
        return upstream

    def get_downstream(self, node_id: str) -> List[LineageNode]:
        """Get downstream nodes"""
        downstream = []
        for edge in self._edges.values():
            if edge.source_id == node_id:
                target = self._nodes.get(edge.target_id)
                if target:
                    downstream.append(target)
        return downstream

    def get_lineage_path(
        self,
        from_id: str,
        to_id: str
    ) -> List[str]:
        """Get lineage path between two nodes"""
        visited = set()
        path = []

        def dfs(current, target, current_path):
            if current == target:
                return current_path
            if current in visited:
                return None
            visited.add(current)

            for edge in self._edges.values():
                if edge.source_id == current:
                    result = dfs(edge.target_id, target, current_path + [edge.target_id])
                    if result:
                        return result
            return None

        return dfs(from_id, to_id, [from_id]) or []

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and its edges"""
        if node_id not in self._nodes:
            return False

        # Remove edges
        self._edges = {
            k: v for k, v in self._edges.items()
            if v.source_id != node_id and v.target_id != node_id
        }

        del self._nodes[node_id]
        return True

    def get_metrics(self) -> Dict[str, Any]:
        """Get lineage metrics"""
        return self._metrics.copy()
