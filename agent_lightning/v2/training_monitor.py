"""
Training Monitor - Real-time training progress monitoring.

CRITICAL: Monitors training without exposing client data.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum
import logging
import time
import json
import os

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(Enum):
    """Types of tracked metrics"""
    LOSS = "loss"
    ACCURACY = "accuracy"
    LEARNING_RATE = "learning_rate"
    GPU_MEMORY = "gpu_memory"
    GRADIENT_NORM = "gradient_norm"
    THROUGHPUT = "throughput"


@dataclass
class TrainingAlert:
    """Training alert"""
    timestamp: datetime
    level: AlertLevel
    message: str
    metric_type: Optional[MetricType] = None
    current_value: Optional[float] = None
    threshold: Optional[float] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "message": self.message,
            "metric_type": self.metric_type.value if self.metric_type else None,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "suggestion": self.suggestion,
        }


@dataclass
class ProgressUpdate:
    """Training progress update"""
    step: int
    epoch: int
    total_steps: int
    progress_percent: float
    elapsed_seconds: float
    estimated_remaining_seconds: float
    current_loss: float
    current_accuracy: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "step": self.step,
            "epoch": self.epoch,
            "total_steps": self.total_steps,
            "progress_percent": self.progress_percent,
            "elapsed_seconds": self.elapsed_seconds,
            "estimated_remaining_seconds": self.estimated_remaining_seconds,
            "current_loss": self.current_loss,
            "current_accuracy": self.current_accuracy,
            "timestamp": self.timestamp.isoformat(),
        }


class TrainingMonitor:
    """
    Real-time training progress monitoring for Agent Lightning v2.

    Features:
    - Real-time training progress
    - Loss curve tracking
    - Accuracy tracking
    - GPU memory monitoring
    - Training time estimation
    - Alert on training issues
    """

    # Default alert thresholds
    ALERT_THRESHOLDS = {
        "loss_spike": 0.5,      # Loss increase threshold
        "accuracy_drop": 0.05,   # Accuracy drop threshold
        "memory_high": 14000,    # GPU memory MB
        "slow_progress": 10.0,   # Seconds per step
    }

    def __init__(
        self,
        output_dir: Optional[str] = None,
        alert_callback: Optional[Callable[[TrainingAlert], None]] = None,
    ):
        """
        Initialize training monitor.

        Args:
            output_dir: Directory to save monitoring logs
            alert_callback: Callback for alerts
        """
        self.output_dir = output_dir
        self.alert_callback = alert_callback

        self._start_time: Optional[datetime] = None
        self._loss_history: List[Dict[str, Any]] = []
        self._accuracy_history: List[Dict[str, Any]] = []
        self._memory_history: List[Dict[str, Any]] = []
        self._alerts: List[TrainingAlert] = []
        self._previous_metrics: Dict[str, float] = {}

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

    def start_monitoring(self) -> None:
        """Start monitoring session"""
        self._start_time = datetime.now()
        logger.info("Training monitoring started")

    def stop_monitoring(self) -> Dict[str, Any]:
        """Stop monitoring and get summary"""
        if not self._start_time:
            return {"error": "Monitoring not started"}

        end_time = datetime.now()
        duration = (end_time - self._start_time).total_seconds()

        summary = {
            "start_time": self._start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "total_steps": len(self._loss_history),
            "final_loss": self._loss_history[-1]["value"] if self._loss_history else None,
            "final_accuracy": self._accuracy_history[-1]["value"] if self._accuracy_history else None,
            "best_accuracy": max(h["value"] for h in self._accuracy_history) if self._accuracy_history else None,
            "alerts_count": len(self._alerts),
            "critical_alerts": sum(1 for a in self._alerts if a.level == AlertLevel.CRITICAL),
        }

        # Save monitoring log
        if self.output_dir:
            log_path = os.path.join(self.output_dir, "monitoring_log.json")
            with open(log_path, "w") as f:
                json.dump({
                    "summary": summary,
                    "loss_history": self._loss_history,
                    "accuracy_history": self._accuracy_history,
                    "memory_history": self._memory_history,
                    "alerts": [a.to_dict() for a in self._alerts],
                }, f, indent=2)

        logger.info(f"Training monitoring stopped: {duration:.1f}s")
        return summary

    def record_step(
        self,
        step: int,
        epoch: int,
        loss: float,
        accuracy: float,
        learning_rate: Optional[float] = None,
        gpu_memory_mb: Optional[float] = None,
        gradient_norm: Optional[float] = None,
    ) -> ProgressUpdate:
        """
        Record training step metrics.

        Args:
            step: Current training step
            epoch: Current epoch
            loss: Current loss value
            accuracy: Current accuracy
            learning_rate: Current learning rate
            gpu_memory_mb: Current GPU memory usage
            gradient_norm: Current gradient norm

        Returns:
            ProgressUpdate
        """
        timestamp = datetime.now()

        # Record metrics
        self._loss_history.append({
            "step": step,
            "epoch": epoch,
            "value": loss,
            "timestamp": timestamp.isoformat(),
        })

        self._accuracy_history.append({
            "step": step,
            "epoch": epoch,
            "value": accuracy,
            "timestamp": timestamp.isoformat(),
        })

        if gpu_memory_mb:
            self._memory_history.append({
                "step": step,
                "value": gpu_memory_mb,
                "timestamp": timestamp.isoformat(),
            })

        # Check for issues
        self._check_metrics(step, loss, accuracy, gpu_memory_mb)

        # Calculate progress
        elapsed = (timestamp - self._start_time).total_seconds() if self._start_time else 0
        steps_per_second = step / elapsed if elapsed > 0 else 1

        # Estimate remaining (assuming 1000 total steps as placeholder)
        total_steps = 1000  # Would be passed from config
        remaining_steps = max(0, total_steps - step)
        estimated_remaining = remaining_steps / steps_per_second if steps_per_second > 0 else 0

        return ProgressUpdate(
            step=step,
            epoch=epoch,
            total_steps=total_steps,
            progress_percent=(step / total_steps) * 100 if total_steps > 0 else 0,
            elapsed_seconds=elapsed,
            estimated_remaining_seconds=estimated_remaining,
            current_loss=loss,
            current_accuracy=accuracy,
            timestamp=timestamp,
        )

    def get_loss_curve(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get loss curve data"""
        return self._loss_history[-limit:]

    def get_accuracy_curve(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get accuracy curve data"""
        return self._accuracy_history[-limit:]

    def get_memory_usage(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get memory usage history"""
        return self._memory_history[-limit:]

    def get_alerts(self, level: Optional[AlertLevel] = None) -> List[TrainingAlert]:
        """Get alerts, optionally filtered by level"""
        if level:
            return [a for a in self._alerts if a.level == level]
        return self._alerts

    def estimate_completion_time(
        self,
        current_step: int,
        total_steps: int,
    ) -> Dict[str, Any]:
        """Estimate training completion time"""
        if not self._start_time or current_step == 0:
            return {
                "estimated_remaining_seconds": None,
                "estimated_completion_time": None,
            }

        elapsed = (datetime.now() - self._start_time).total_seconds()
        steps_per_second = current_step / elapsed

        remaining_steps = total_steps - current_step
        remaining_seconds = remaining_steps / steps_per_second if steps_per_second > 0 else 0

        estimated_completion = datetime.now() + timedelta(seconds=remaining_seconds)

        return {
            "elapsed_seconds": elapsed,
            "steps_per_second": steps_per_second,
            "remaining_steps": remaining_steps,
            "estimated_remaining_seconds": remaining_seconds,
            "estimated_completion_time": estimated_completion.isoformat(),
        }

    def _check_metrics(
        self,
        step: int,
        loss: float,
        accuracy: float,
        gpu_memory_mb: Optional[float],
    ) -> None:
        """Check metrics for issues and generate alerts"""
        # Check loss spike
        if self._previous_metrics.get("loss"):
            loss_increase = loss - self._previous_metrics["loss"]
            if loss_increase > self.ALERT_THRESHOLDS["loss_spike"]:
                self._create_alert(
                    level=AlertLevel.WARNING,
                    message=f"Loss spike detected: +{loss_increase:.4f}",
                    metric_type=MetricType.LOSS,
                    current_value=loss,
                    threshold=self._previous_metrics["loss"] + self.ALERT_THRESHOLDS["loss_spike"],
                    suggestion="Consider reducing learning rate",
                )

        # Check accuracy drop
        if self._previous_metrics.get("accuracy"):
            accuracy_drop = self._previous_metrics["accuracy"] - accuracy
            if accuracy_drop > self.ALERT_THRESHOLDS["accuracy_drop"]:
                self._create_alert(
                    level=AlertLevel.WARNING,
                    message=f"Accuracy drop detected: -{accuracy_drop:.2%}",
                    metric_type=MetricType.ACCURACY,
                    current_value=accuracy,
                    threshold=self._previous_metrics["accuracy"] - self.ALERT_THRESHOLDS["accuracy_drop"],
                    suggestion="Check for overfitting or data issues",
                )

        # Check memory
        if gpu_memory_mb and gpu_memory_mb > self.ALERT_THRESHOLDS["memory_high"]:
            self._create_alert(
                level=AlertLevel.WARNING,
                message=f"High GPU memory usage: {gpu_memory_mb:.0f}MB",
                metric_type=MetricType.GPU_MEMORY,
                current_value=gpu_memory_mb,
                threshold=self.ALERT_THRESHOLDS["memory_high"],
                suggestion="Consider reducing batch size",
            )

        # Update previous metrics
        self._previous_metrics["loss"] = loss
        self._previous_metrics["accuracy"] = accuracy
        if gpu_memory_mb:
            self._previous_metrics["gpu_memory"] = gpu_memory_mb

    def _create_alert(
        self,
        level: AlertLevel,
        message: str,
        metric_type: Optional[MetricType] = None,
        current_value: Optional[float] = None,
        threshold: Optional[float] = None,
        suggestion: Optional[str] = None,
    ) -> None:
        """Create and store an alert"""
        alert = TrainingAlert(
            timestamp=datetime.now(),
            level=level,
            message=message,
            metric_type=metric_type,
            current_value=current_value,
            threshold=threshold,
            suggestion=suggestion,
        )

        self._alerts.append(alert)

        # Log
        if level == AlertLevel.CRITICAL:
            logger.critical(message)
        elif level == AlertLevel.ERROR:
            logger.error(message)
        elif level == AlertLevel.WARNING:
            logger.warning(message)
        else:
            logger.info(message)

        # Callback
        if self.alert_callback:
            self.alert_callback(alert)


# Import timedelta for estimate_completion_time
from datetime import timedelta
