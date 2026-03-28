"""Pipeline Monitor Module - Week 56, Builder 5"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import logging
import threading

logger = logging.getLogger(__name__)


class MetricType(Enum):
    THROUGHPUT = "throughput"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    BACKLOG = "backlog"
    SUCCESS_RATE = "success_rate"


class QualityDimension(Enum):
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    VALIDITY = "validity"


@dataclass
class PipelineMetric:
    name: str
    metric_type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class QualityScore:
    dimension: QualityDimension
    score: float
    details: Dict[str, Any] = field(default_factory=dict)
    measured_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_acceptable(self) -> bool:
        return self.score >= 0.8


@dataclass
class LineageNode:
    data_id: str
    source: str
    transformations: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LineageEdge:
    source_id: str
    target_id: str
    transformation: str = ""


class PipelineMonitor:
    def __init__(self, alert_threshold: float = 0.9):
        self.alert_threshold = alert_threshold
        self._metrics: List[PipelineMetric] = []
        self._alerts: List[Dict] = []
        self._lock = threading.Lock()

    def track(self, metric: PipelineMetric) -> None:
        with self._lock:
            self._metrics.append(metric)
            self._check_alert(metric)

    def _check_alert(self, metric: PipelineMetric) -> None:
        if metric.metric_type == MetricType.ERROR_RATE and metric.value > self.alert_threshold:
            self._alerts.append({
                "type": "high_error_rate",
                "value": metric.value,
                "timestamp": metric.timestamp
            })
        elif metric.metric_type == MetricType.LATENCY and metric.value > 1000:
            self._alerts.append({
                "type": "high_latency",
                "value": metric.value,
                "timestamp": metric.timestamp
            })

    def get_metrics(self, metric_type: Optional[MetricType] = None, limit: int = 100) -> List[PipelineMetric]:
        with self._lock:
            metrics = self._metrics
            if metric_type:
                metrics = [m for m in metrics if m.metric_type == metric_type]
            return metrics[-limit:]

    def get_alerts(self) -> List[Dict]:
        return self._alerts.copy()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            if not self._metrics:
                return {"total_metrics": 0}

            return {
                "total_metrics": len(self._metrics),
                "total_alerts": len(self._alerts),
                "last_metric": self._metrics[-1].name if self._metrics else None
            }

    def clear_alerts(self) -> None:
        self._alerts.clear()


class DataQualityManager:
    def __init__(self, thresholds: Dict[QualityDimension, float] = None):
        self.thresholds = thresholds or {qd: 0.8 for qd in QualityDimension}
        self._scores: List[QualityScore] = []

    def check(self, data: List[Dict], dimension: QualityDimension) -> QualityScore:
        if not data:
            return QualityScore(dimension=dimension, score=0.0, details={"error": "No data"})

        if dimension == QualityDimension.COMPLETENESS:
            total_fields = sum(len(d) for d in data)
            filled_fields = sum(sum(1 for v in d.values() if v is not None and v != "") for d in data)
            score = filled_fields / total_fields if total_fields > 0 else 0

        elif dimension == QualityDimension.ACCURACY:
            score = 0.85  # Placeholder - would use validation rules

        elif dimension == QualityDimension.CONSISTENCY:
            score = 0.9  # Placeholder - would check format consistency

        elif dimension == QualityDimension.TIMELINESS:
            score = 0.95  # Placeholder - would check data freshness

        elif dimension == QualityDimension.VALIDITY:
            score = 0.88  # Placeholder - would apply validation rules

        else:
            score = 0.0

        quality_score = QualityScore(dimension=dimension, score=score)
        self._scores.append(quality_score)
        return quality_score

    def get_scores(self, dimension: Optional[QualityDimension] = None) -> List[QualityScore]:
        if dimension:
            return [s for s in self._scores if s.dimension == dimension]
        return self._scores.copy()

    def get_average_score(self, dimension: QualityDimension) -> float:
        scores = [s.score for s in self._scores if s.dimension == dimension]
        return sum(scores) / len(scores) if scores else 0.0


class LineageTracker:
    def __init__(self):
        self._nodes: Dict[str, LineageNode] = {}
        self._edges: List[LineageEdge] = []
        self._lock = threading.Lock()

    def track(self, data_id: str, source: str, transformations: List[str] = None) -> None:
        with self._lock:
            node = LineageNode(
                data_id=data_id,
                source=source,
                transformations=transformations or []
            )
            self._nodes[data_id] = node

    def add_edge(self, source_id: str, target_id: str, transformation: str = "") -> None:
        with self._lock:
            self._edges.append(LineageEdge(
                source_id=source_id,
                target_id=target_id,
                transformation=transformation
            ))

    def get_lineage(self, data_id: str) -> Dict[str, Any]:
        with self._lock:
            node = self._nodes.get(data_id)
            if not node:
                return {}

            # Find upstream nodes
            upstream = []
            for edge in self._edges:
                if edge.target_id == data_id:
                    upstream.append({
                        "id": edge.source_id,
                        "transformation": edge.transformation
                    })

            # Find downstream nodes
            downstream = []
            for edge in self._edges:
                if edge.source_id == data_id:
                    downstream.append({
                        "id": edge.target_id,
                        "transformation": edge.transformation
                    })

            return {
                "node": {
                    "data_id": node.data_id,
                    "source": node.source,
                    "transformations": node.transformations
                },
                "upstream": upstream,
                "downstream": downstream
            }

    def get_full_lineage(self, data_id: str, depth: int = 5) -> Dict[str, Any]:
        result = self.get_lineage(data_id)
        if depth <= 0:
            return result

        for upstream in result.get("upstream", []):
            upstream["lineage"] = self.get_full_lineage(upstream["id"], depth - 1)

        return result

    def list_nodes(self) -> List[str]:
        return list(self._nodes.keys())

    def get_node(self, data_id: str) -> Optional[LineageNode]:
        return self._nodes.get(data_id)
