"""Anomaly Detector Module - Week 54, Builder 2"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    BEHAVIORAL = "behavioral"
    TRAFFIC = "traffic"
    ACCESS = "access"
    PERFORMANCE = "performance"


@dataclass
class Anomaly:
    anomaly_type: AnomalyType
    score: float
    threshold: float
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_anomaly(self) -> bool:
        return self.score > self.threshold


class Baseline:
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.values: List[float] = []

    def add(self, value: float) -> None:
        self.values.append(value)
        if len(self.values) > self.window_size:
            self.values = self.values[-self.window_size:]

    @property
    def mean(self) -> float:
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)

    @property
    def std(self) -> float:
        if len(self.values) < 2:
            return 0.0
        m = self.mean
        return (sum((x - m) ** 2 for x in self.values) / len(self.values)) ** 0.5


class AnomalyDetector:
    def __init__(self, default_threshold: float = 3.0):
        self.default_threshold = default_threshold
        self.baselines: Dict[str, Baseline] = {}
        self.anomalies: List[Anomaly] = []

    def get_baseline(self, name: str) -> Baseline:
        if name not in self.baselines:
            self.baselines[name] = Baseline()
        return self.baselines[name]

    def detect_anomalies(self, name: str, value: float, threshold: Optional[float] = None) -> Optional[Anomaly]:
        baseline = self.get_baseline(name)
        thresh = threshold or self.default_threshold

        if len(baseline.values) < 5:
            baseline.add(value)
            return None

        mean = baseline.mean
        std = baseline.std or 1.0
        score = abs(value - mean) / std

        anomaly = Anomaly(
            anomaly_type=AnomalyType.BEHAVIORAL,
            score=score,
            threshold=thresh,
            details={"name": name, "value": value, "mean": mean, "std": std},
        )

        if anomaly.is_anomaly:
            self.anomalies.append(anomaly)
            return anomaly

        baseline.add(value)
        return None

    def get_anomalies(self, anomaly_type: Optional[AnomalyType] = None) -> List[Anomaly]:
        if anomaly_type is None:
            return self.anomalies
        return [a for a in self.anomalies if a.anomaly_type == anomaly_type]

    def clear_anomalies(self) -> None:
        self.anomalies.clear()
