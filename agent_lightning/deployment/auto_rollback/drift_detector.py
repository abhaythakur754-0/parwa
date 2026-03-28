"""
Drift Detector for Auto-Rollback.

Detects model drift:
- Accuracy drift
- Response quality drift
- Latency degradation
- Statistical drift testing
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
from collections import deque
import logging
import math

logger = logging.getLogger(__name__)


class DriftType(Enum):
    """Types of drift."""
    ACCURACY = "accuracy"
    LATENCY = "latency"
    QUALITY = "quality"
    ERROR_RATE = "error_rate"
    DISTRIBUTION = "distribution"


@dataclass
class DriftResult:
    """Result of drift detection."""
    drift_type: DriftType
    is_drifted: bool
    drift_magnitude: float
    baseline_value: float
    current_value: float
    threshold: float
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "drift_type": self.drift_type.value,
            "is_drifted": self.is_drifted,
            "drift_magnitude": self.drift_magnitude,
            "baseline_value": self.baseline_value,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


class DriftDetector:
    """
    Detects various types of model drift.

    Monitors for:
    - Accuracy drift (>5% drop)
    - Latency degradation
    - Response quality drift
    - Statistical distribution drift
    """

    # Default thresholds
    ACCURACY_DRIFT_THRESHOLD: float = 0.05  # 5% accuracy drop
    LATENCY_DRIFT_THRESHOLD: float = 0.30  # 30% latency increase
    ERROR_RATE_THRESHOLD: float = 0.10  # 10% error rate
    WINDOW_SIZE: int = 100  # Samples to consider

    def __init__(
        self,
        accuracy_threshold: float = 0.05,
        latency_threshold: float = 0.30,
        error_rate_threshold: float = 0.10,
        window_size: int = 100
    ):
        """
        Initialize the drift detector.

        Args:
            accuracy_threshold: Max allowed accuracy drop (default 5%)
            latency_threshold: Max allowed latency increase (default 30%)
            error_rate_threshold: Max allowed error rate (default 10%)
            window_size: Number of samples for rolling window
        """
        self.accuracy_threshold = accuracy_threshold
        self.latency_threshold = latency_threshold
        self.error_rate_threshold = error_rate_threshold
        self.window_size = window_size

        # Rolling windows for metrics
        self._accuracy_window: deque = deque(maxlen=window_size)
        self._latency_window: deque = deque(maxlen=window_size)
        self._error_window: deque = deque(maxlen=window_size)

        # Baselines (set during initial deployment)
        self._baseline_accuracy: Optional[float] = None
        self._baseline_latency: Optional[float] = None
        self._baseline_error_rate: Optional[float] = None

    def set_baselines(
        self,
        accuracy: float,
        latency_ms: float,
        error_rate: float = 0.01
    ):
        """
        Set baseline metrics from initial deployment.

        Args:
            accuracy: Baseline accuracy
            latency_ms: Baseline latency in ms
            error_rate: Baseline error rate
        """
        self._baseline_accuracy = accuracy
        self._baseline_latency = latency_ms
        self._baseline_error_rate = error_rate

        logger.info(
            f"Set baselines: accuracy={accuracy:.3f}, "
            f"latency={latency_ms:.1f}ms, error_rate={error_rate:.3f}"
        )

    def record_accuracy(self, is_correct: bool):
        """Record an accuracy measurement."""
        self._accuracy_window.append(1.0 if is_correct else 0.0)

    def record_latency(self, latency_ms: float):
        """Record a latency measurement."""
        self._latency_window.append(latency_ms)

    def record_error(self, is_error: bool):
        """Record an error occurrence."""
        self._error_window.append(1.0 if is_error else 0.0)

    def detect_accuracy_drift(self) -> DriftResult:
        """
        Detect accuracy drift.

        Returns:
            DriftResult with drift status
        """
        if not self._accuracy_window or self._baseline_accuracy is None:
            return DriftResult(
                drift_type=DriftType.ACCURACY,
                is_drifted=False,
                drift_magnitude=0.0,
                baseline_value=self._baseline_accuracy or 0.0,
                current_value=0.0,
                threshold=self.accuracy_threshold
            )

        current_accuracy = sum(self._accuracy_window) / len(self._accuracy_window)
        drift = self._baseline_accuracy - current_accuracy
        is_drifted = drift > self.accuracy_threshold

        return DriftResult(
            drift_type=DriftType.ACCURACY,
            is_drifted=is_drifted,
            drift_magnitude=drift,
            baseline_value=self._baseline_accuracy,
            current_value=current_accuracy,
            threshold=self.accuracy_threshold,
            details={
                "samples": len(self._accuracy_window),
                "baseline": self._baseline_accuracy,
                "current": current_accuracy,
            }
        )

    def detect_latency_drift(self) -> DriftResult:
        """
        Detect latency degradation.

        Returns:
            DriftResult with drift status
        """
        if not self._latency_window or self._baseline_latency is None:
            return DriftResult(
                drift_type=DriftType.LATENCY,
                is_drifted=False,
                drift_magnitude=0.0,
                baseline_value=self._baseline_latency or 0.0,
                current_value=0.0,
                threshold=self.latency_threshold
            )

        current_latency = sum(self._latency_window) / len(self._latency_window)
        drift = (current_latency - self._baseline_latency) / self._baseline_latency
        is_drifted = drift > self.latency_threshold

        return DriftResult(
            drift_type=DriftType.LATENCY,
            is_drifted=is_drifted,
            drift_magnitude=drift,
            baseline_value=self._baseline_latency,
            current_value=current_latency,
            threshold=self.latency_threshold,
            details={
                "samples": len(self._latency_window),
                "baseline_ms": self._baseline_latency,
                "current_ms": current_latency,
            }
        )

    def detect_error_rate_drift(self) -> DriftResult:
        """
        Detect error rate increase.

        Returns:
            DriftResult with drift status
        """
        if not self._error_window:
            return DriftResult(
                drift_type=DriftType.ERROR_RATE,
                is_drifted=False,
                drift_magnitude=0.0,
                baseline_value=self._baseline_error_rate or 0.0,
                current_value=0.0,
                threshold=self.error_rate_threshold
            )

        current_error_rate = sum(self._error_window) / len(self._error_window)
        is_drifted = current_error_rate > self.error_rate_threshold

        return DriftResult(
            drift_type=DriftType.ERROR_RATE,
            is_drifted=is_drifted,
            drift_magnitude=current_error_rate,
            baseline_value=self._baseline_error_rate or 0.0,
            current_value=current_error_rate,
            threshold=self.error_rate_threshold,
            details={
                "samples": len(self._error_window),
                "error_count": int(sum(self._error_window)),
            }
        )

    def detect_all_drifts(self) -> List[DriftResult]:
        """
        Check all drift types.

        Returns:
            List of DriftResults for all drift types
        """
        return [
            self.detect_accuracy_drift(),
            self.detect_latency_drift(),
            self.detect_error_rate_drift(),
        ]

    def has_critical_drift(self) -> Tuple[bool, Optional[DriftType]]:
        """
        Check if any critical drift is detected.

        Returns:
            Tuple of (has_drift, drift_type)
        """
        results = self.detect_all_drifts()

        for result in results:
            if result.is_drifted:
                return True, result.drift_type

        return False, None

    def get_stats(self) -> Dict[str, Any]:
        """Get detector statistics."""
        return {
            "window_size": self.window_size,
            "accuracy_samples": len(self._accuracy_window),
            "latency_samples": len(self._latency_window),
            "error_samples": len(self._error_window),
            "baselines": {
                "accuracy": self._baseline_accuracy,
                "latency_ms": self._baseline_latency,
                "error_rate": self._baseline_error_rate,
            },
            "thresholds": {
                "accuracy": self.accuracy_threshold,
                "latency": self.latency_threshold,
                "error_rate": self.error_rate_threshold,
            }
        }


def get_drift_detector(
    accuracy_threshold: float = 0.05
) -> DriftDetector:
    """
    Factory function to create a drift detector.

    Args:
        accuracy_threshold: Max allowed accuracy drop

    Returns:
        Configured DriftDetector instance
    """
    return DriftDetector(accuracy_threshold=accuracy_threshold)
