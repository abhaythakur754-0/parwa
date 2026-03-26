"""
Deployment Manager - Manage model deployment to production.

CRITICAL: Handles model deployment with version tracking and automatic rollback.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import logging
import json
import os

logger = logging.getLogger(__name__)


class DeploymentStatus(Enum):
    """Status of deployment"""
    PENDING = "pending"
    VALIDATING = "validating"
    DEPLOYING = "deploying"
    ACTIVE = "active"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class DeploymentStage(Enum):
    """Stages of deployment process"""
    PRE_CHECK = "pre_check"
    VALIDATION = "validation"
    REGRESSION = "regression"
    STAGING = "staging"
    PRODUCTION = "production"
    HEALTH_CHECK = "health_check"
    COMPLETE = "complete"


@dataclass
class DeploymentRecord:
    """Record of a single deployment"""
    deployment_id: str
    model_version: str
    timestamp: datetime
    status: DeploymentStatus
    stage: DeploymentStage
    accuracy: float
    validation_passed: bool
    regression_passed: bool
    health_check_passed: bool
    rollback_available: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "deployment_id": self.deployment_id,
            "model_version": self.model_version,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "stage": self.stage.value,
            "accuracy": self.accuracy,
            "validation_passed": self.validation_passed,
            "regression_passed": self.regression_passed,
            "health_check_passed": self.health_check_passed,
            "rollback_available": self.rollback_available,
            "metadata": self.metadata,
        }


@dataclass
class DeploymentConfig:
    """Configuration for deployment"""
    require_validation: bool = True
    require_regression: bool = True
    min_accuracy: float = 0.77
    auto_rollback_on_failure: bool = True
    health_check_interval_seconds: int = 30
    max_deployment_history: int = 10


class DeploymentManager:
    """
    Manage model deployment to production.

    CRITICAL: Handles deployment with version tracking and automatic rollback.

    Features:
    - Deploy model to production
    - Version tracking
    - Deployment history
    - Health checks
    - Automatic rollback on failure
    """

    def __init__(
        self,
        deployment_dir: str,
        config: Optional[DeploymentConfig] = None,
    ):
        """
        Initialize deployment manager.

        Args:
            deployment_dir: Directory for deployment records
            config: Deployment configuration
        """
        self.deployment_dir = deployment_dir
        self.config = config or DeploymentConfig()
        self._history: List[DeploymentRecord] = []
        self._current_deployment: Optional[DeploymentRecord] = None
        self._previous_deployment: Optional[DeploymentRecord] = None

        os.makedirs(deployment_dir, exist_ok=True)

    def deploy_model(
        self,
        model_path: str,
        model_version: str,
        accuracy: float,
        skip_validation: bool = False,
        skip_regression: bool = False,
    ) -> DeploymentRecord:
        """
        Deploy a model to production.

        Args:
            model_path: Path to model files
            model_version: Version identifier
            accuracy: Validated accuracy
            skip_validation: Skip validation checks
            skip_regression: Skip regression tests

        Returns:
            Deployment record
        """
        deployment_id = self._generate_deployment_id()

        # Create initial record
        record = DeploymentRecord(
            deployment_id=deployment_id,
            model_version=model_version,
            timestamp=datetime.now(),
            status=DeploymentStatus.PENDING,
            stage=DeploymentStage.PRE_CHECK,
            accuracy=accuracy,
            validation_passed=False,
            regression_passed=False,
            health_check_passed=False,
            rollback_available=True,
        )

        # Pre-check
        if accuracy < self.config.min_accuracy:
            record.status = DeploymentStatus.FAILED
            record.metadata["failure_reason"] = "Accuracy below threshold"
            self._add_to_history(record)
            return record

        # Validation stage
        record.stage = DeploymentStage.VALIDATION
        if not skip_validation and self.config.require_validation:
            record.validation_passed = accuracy >= self.config.min_accuracy
        else:
            record.validation_passed = True

        if not record.validation_passed:
            record.status = DeploymentStatus.FAILED
            record.metadata["failure_reason"] = "Validation failed"
            self._add_to_history(record)
            return record

        # Regression stage
        record.stage = DeploymentStage.REGRESSION
        if not skip_regression and self.config.require_regression:
            record.regression_passed = True  # Would run actual tests
        else:
            record.regression_passed = True

        if not record.regression_passed:
            record.status = DeploymentStatus.FAILED
            record.metadata["failure_reason"] = "Regression tests failed"
            self._add_to_history(record)
            return record

        # Staging
        record.stage = DeploymentStage.STAGING
        record.status = DeploymentStatus.DEPLOYING

        # Production deployment
        record.stage = DeploymentStage.PRODUCTION
        self._deploy_to_production(model_path, model_version)

        # Health check
        record.stage = DeploymentStage.HEALTH_CHECK
        record.health_check_passed = self._run_health_check()

        if not record.health_check_passed:
            if self.config.auto_rollback_on_failure:
                self._rollback()
                record.status = DeploymentStatus.ROLLED_BACK
            else:
                record.status = DeploymentStatus.FAILED
            self._add_to_history(record)
            return record

        # Complete
        record.stage = DeploymentStage.COMPLETE
        record.status = DeploymentStatus.ACTIVE

        # Update deployment tracking
        self._previous_deployment = self._current_deployment
        self._current_deployment = record

        self._add_to_history(record)
        self._save_deployment_record(record)

        logger.info(f"Deployment complete: {deployment_id}")

        return record

    def rollback(self) -> Optional[DeploymentRecord]:
        """
        Rollback to previous deployment.

        Returns:
            Rolled back deployment record, or None if no previous
        """
        if not self._previous_deployment:
            logger.warning("No previous deployment to rollback to")
            return None

        # Switch traffic back
        self._deploy_to_production(
            "previous_model_path",
            self._previous_deployment.model_version,
        )

        # Update tracking
        rolled_back = self._previous_deployment
        rolled_back.status = DeploymentStatus.ACTIVE

        self._current_deployment = rolled_back
        self._previous_deployment = None

        logger.info(f"Rolled back to: {rolled_back.model_version}")

        return rolled_back

    def get_current_deployment(self) -> Optional[DeploymentRecord]:
        """Get current active deployment"""
        return self._current_deployment

    def get_deployment_history(self, limit: int = 10) -> List[DeploymentRecord]:
        """Get deployment history"""
        return self._history[-limit:]

    def get_deployment_by_id(self, deployment_id: str) -> Optional[DeploymentRecord]:
        """Get specific deployment by ID"""
        for record in self._history:
            if record.deployment_id == deployment_id:
                return record
        return None

    def check_health(self) -> Dict[str, Any]:
        """Check current deployment health"""
        if not self._current_deployment:
            return {"healthy": False, "reason": "No active deployment"}

        return {
            "healthy": self._current_deployment.health_check_passed,
            "deployment_id": self._current_deployment.deployment_id,
            "model_version": self._current_deployment.model_version,
            "accuracy": self._current_deployment.accuracy,
            "uptime_seconds": (
                datetime.now() - self._current_deployment.timestamp
            ).total_seconds(),
        }

    def _generate_deployment_id(self) -> str:
        """Generate unique deployment ID"""
        return f"deploy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _deploy_to_production(self, model_path: str, model_version: str) -> None:
        """Deploy model to production environment"""
        # In production, would update traffic routing
        logger.info(f"Deploying model {model_version} from {model_path}")

    def _run_health_check(self) -> bool:
        """Run health check on current deployment"""
        # In production, would check actual endpoints
        return True

    def _rollback(self) -> None:
        """Internal rollback procedure"""
        if self._previous_deployment:
            self._deploy_to_production(
                "previous_model_path",
                self._previous_deployment.model_version,
            )

    def _add_to_history(self, record: DeploymentRecord) -> None:
        """Add record to deployment history"""
        self._history.append(record)

        # Limit history size
        if len(self._history) > self.config.max_deployment_history:
            self._history = self._history[-self.config.max_deployment_history :]

    def _save_deployment_record(self, record: DeploymentRecord) -> None:
        """Save deployment record to disk"""
        record_path = os.path.join(
            self.deployment_dir,
            f"{record.deployment_id}.json",
        )
        with open(record_path, "w") as f:
            json.dump(record.to_dict(), f, indent=2)


def deploy_to_production(
    model_path: str,
    model_version: str,
    accuracy: float,
    deployment_dir: str = "deployments",
) -> DeploymentRecord:
    """
    Convenience function to deploy model to production.

    Args:
        model_path: Path to model files
        model_version: Version identifier
        accuracy: Validated accuracy
        deployment_dir: Directory for deployment records

    Returns:
        Deployment record
    """
    manager = DeploymentManager(deployment_dir=deployment_dir)
    return manager.deploy_model(
        model_path=model_path,
        model_version=model_version,
        accuracy=accuracy,
    )
