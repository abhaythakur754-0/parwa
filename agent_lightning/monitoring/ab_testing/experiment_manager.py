"""
Experiment Manager for A/B Testing.

Manages experiment lifecycle:
- Create/stop experiments
- Variant assignment
- Results tracking
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """Experiment status."""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"


@dataclass
class ExperimentConfig:
    """Configuration for an experiment."""
    name: str
    description: str = ""
    control_model: str = "current"
    treatment_model: str = "new"
    traffic_split: float = 0.10  # 10% to treatment
    min_sample_size: int = 1000
    duration_days: int = 7
    success_metric: str = "accuracy"
    auto_stop_on_significance: bool = True


@dataclass
class Experiment:
    """An A/B testing experiment."""
    experiment_id: str
    name: str
    config: ExperimentConfig
    status: ExperimentStatus
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    variants: List[str] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "config": {
                "name": self.config.name,
                "description": self.config.description,
                "control_model": self.config.control_model,
                "treatment_model": self.config.treatment_model,
                "traffic_split": self.config.traffic_split,
                "min_sample_size": self.config.min_sample_size,
                "duration_days": self.config.duration_days,
                "success_metric": self.config.success_metric,
            },
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "variants": self.variants,
            "results": self.results,
        }


class ExperimentManager:
    """
    Manages A/B testing experiments.

    Features:
    - Create/stop experiments
    - Experiment configuration
    - Variant assignment
    - Results tracking
    """

    def __init__(self):
        """Initialize the experiment manager."""
        self._experiments: Dict[str, Experiment] = {}
        self._active_experiment: Optional[str] = None

    def create_experiment(
        self,
        name: str,
        config: Optional[ExperimentConfig] = None,
        **kwargs
    ) -> Experiment:
        """
        Create a new experiment.

        Args:
            name: Experiment name
            config: Experiment configuration
            **kwargs: Additional config parameters

        Returns:
            Created Experiment
        """
        if config is None:
            config = ExperimentConfig(name=name, **kwargs)

        experiment_id = f"exp_{uuid.uuid4().hex[:8]}"

        experiment = Experiment(
            experiment_id=experiment_id,
            name=name,
            config=config,
            status=ExperimentStatus.DRAFT,
            variants=["control", "treatment"]
        )

        self._experiments[experiment_id] = experiment

        logger.info(f"Created experiment {experiment_id}: {name}")

        return experiment

    def start_experiment(self, experiment_id: str) -> Experiment:
        """
        Start an experiment.

        Args:
            experiment_id: Experiment to start

        Returns:
            Updated Experiment
        """
        if experiment_id not in self._experiments:
            raise ValueError(f"Experiment {experiment_id} not found")

        experiment = self._experiments[experiment_id]

        if experiment.status != ExperimentStatus.DRAFT:
            raise ValueError(f"Cannot start experiment in {experiment.status.value} status")

        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.now()
        self._active_experiment = experiment_id

        logger.info(f"Started experiment {experiment_id}")

        return experiment

    def stop_experiment(
        self,
        experiment_id: str,
        reason: str = "manual"
    ) -> Experiment:
        """
        Stop an experiment.

        Args:
            experiment_id: Experiment to stop
            reason: Reason for stopping

        Returns:
            Updated Experiment
        """
        if experiment_id not in self._experiments:
            raise ValueError(f"Experiment {experiment_id} not found")

        experiment = self._experiments[experiment_id]

        experiment.status = ExperimentStatus.STOPPED
        experiment.ended_at = datetime.now()
        experiment.results["stop_reason"] = reason

        if self._active_experiment == experiment_id:
            self._active_experiment = None

        logger.info(f"Stopped experiment {experiment_id}: {reason}")

        return experiment

    def complete_experiment(
        self,
        experiment_id: str,
        winner: str,
        results: Dict[str, Any]
    ) -> Experiment:
        """
        Mark experiment as completed with results.

        Args:
            experiment_id: Experiment to complete
            winner: Winning variant
            results: Experiment results

        Returns:
            Updated Experiment
        """
        if experiment_id not in self._experiments:
            raise ValueError(f"Experiment {experiment_id} not found")

        experiment = self._experiments[experiment_id]

        experiment.status = ExperimentStatus.COMPLETED
        experiment.ended_at = datetime.now()
        experiment.results = {
            **results,
            "winner": winner,
        }

        if self._active_experiment == experiment_id:
            self._active_experiment = None

        logger.info(f"Completed experiment {experiment_id}, winner: {winner}")

        return experiment

    def pause_experiment(self, experiment_id: str) -> Experiment:
        """Pause a running experiment."""
        if experiment_id not in self._experiments:
            raise ValueError(f"Experiment {experiment_id} not found")

        experiment = self._experiments[experiment_id]
        experiment.status = ExperimentStatus.PAUSED

        logger.info(f"Paused experiment {experiment_id}")

        return experiment

    def resume_experiment(self, experiment_id: str) -> Experiment:
        """Resume a paused experiment."""
        if experiment_id not in self._experiments:
            raise ValueError(f"Experiment {experiment_id} not found")

        experiment = self._experiments[experiment_id]
        experiment.status = ExperimentStatus.RUNNING

        logger.info(f"Resumed experiment {experiment_id}")

        return experiment

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get experiment by ID."""
        return self._experiments.get(experiment_id)

    def get_active_experiment(self) -> Optional[Experiment]:
        """Get currently active experiment."""
        if self._active_experiment:
            return self._experiments.get(self._active_experiment)
        return None

    def list_experiments(
        self,
        status: Optional[ExperimentStatus] = None
    ) -> List[Experiment]:
        """
        List experiments, optionally filtered by status.

        Args:
            status: Filter by status

        Returns:
            List of experiments
        """
        experiments = list(self._experiments.values())

        if status:
            experiments = [e for e in experiments if e.status == status]

        return sorted(experiments, key=lambda e: e.created_at, reverse=True)

    def get_stats(self) -> Dict[str, Any]:
        """Get experiment statistics."""
        status_counts = {}
        for exp in self._experiments.values():
            status = exp.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_experiments": len(self._experiments),
            "active_experiment": self._active_experiment,
            "by_status": status_counts,
        }


def get_experiment_manager() -> ExperimentManager:
    """Factory function to create an experiment manager."""
    return ExperimentManager()
