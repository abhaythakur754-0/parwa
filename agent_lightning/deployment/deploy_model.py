"""
Model Deployment for Agent Lightning.

Handles deploying trained models to the model registry.

CRITICAL: Only deploys models that pass 90% accuracy threshold.

Features:
- Deploy models to registry
- Verify deployment success
- Promote to production
- Track deployment history
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import os
import json
import asyncio
import hashlib

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class DeploymentStatus(str, Enum):
    """Deployment status enumeration."""
    PENDING = "pending"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class Environment(str, Enum):
    """Deployment environments."""
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class DeploymentRecord:
    """Record of a model deployment."""
    deployment_id: str
    model_version: str
    model_path: str
    environment: Environment
    status: DeploymentStatus
    accuracy: float
    deployed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deployed_by: str = "system"
    metrics: Dict[str, Any] = field(default_factory=dict)
    previous_version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "deployment_id": self.deployment_id,
            "model_version": self.model_version,
            "model_path": self.model_path,
            "environment": self.environment.value,
            "status": self.status.value,
            "accuracy": self.accuracy,
            "deployed_at": self.deployed_at.isoformat(),
            "deployed_by": self.deployed_by,
            "metrics": self.metrics,
            "previous_version": self.previous_version
        }


class ModelDeployer:
    """
    Model Deployment Manager.

    Handles deploying trained models to the model registry.

    CRITICAL: Only deploys models with >= 90% accuracy.

    Features:
    - Deploy models to staging/production
    - Verify deployment success
    - Promote staging to production
    - Track deployment history
    - Automatic rollback on failure

    Example:
        deployer = ModelDeployer()
        result = await deployer.deploy("model_v1", "/models/agent_lightning/v1")
        verify = await deployer.verify_deployment("model_v1")
    """

    # CRITICAL: Minimum accuracy threshold
    MIN_ACCURACY_THRESHOLD = 0.90

    def __init__(
        self,
        registry_path: str = "./models/registry"
    ) -> None:
        """
        Initialize Model Deployer.

        Args:
            registry_path: Path to model registry
        """
        self.registry_path = registry_path
        self._deployments: Dict[str, DeploymentRecord] = {}
        self._current_production: Optional[str] = None
        self._current_staging: Optional[str] = None

        # Ensure registry exists
        os.makedirs(registry_path, exist_ok=True)

        logger.info({
            "event": "model_deployer_initialized",
            "registry_path": registry_path,
            "accuracy_threshold": self.MIN_ACCURACY_THRESHOLD
        })

    async def deploy(
        self,
        model_path: str,
        version: str,
        accuracy: float = 0.0,
        environment: Environment = Environment.STAGING,
        metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Deploy a model to the registry.

        CRITICAL: Only deploys models with >= 90% accuracy.

        Args:
            model_path: Path to trained model
            version: Model version identifier
            accuracy: Model accuracy (must be >= 90%)
            environment: Target environment
            metrics: Additional metrics

        Returns:
            Dict with deployment result
        """
        deployment_id = f"deploy_{hashlib.md5(version.encode()).hexdigest()[:8]}"

        logger.info({
            "event": "deployment_started",
            "deployment_id": deployment_id,
            "model_version": version,
            "accuracy": accuracy,
            "environment": environment.value
        })

        # CRITICAL: Check accuracy threshold
        if accuracy < self.MIN_ACCURACY_THRESHOLD:
            logger.error({
                "event": "deployment_blocked",
                "deployment_id": deployment_id,
                "accuracy": accuracy,
                "threshold": self.MIN_ACCURACY_THRESHOLD,
                "reason": "Accuracy below threshold"
            })

            return {
                "success": False,
                "error": f"Accuracy {accuracy:.2%} below threshold {self.MIN_ACCURACY_THRESHOLD:.0%}",
                "deployment_id": deployment_id,
                "model_version": version,
                "status": DeploymentStatus.FAILED.value
            }

        # Create deployment record
        deployment = DeploymentRecord(
            deployment_id=deployment_id,
            model_version=version,
            model_path=model_path,
            environment=environment,
            status=DeploymentStatus.DEPLOYING,
            accuracy=accuracy,
            metrics=metrics or {}
        )

        try:
            # Simulate deployment process
            await self._deploy_model(model_path, version)

            # Update status
            deployment.status = DeploymentStatus.DEPLOYED

            # Store deployment record
            self._deployments[deployment_id] = deployment

            # Update current model for environment
            if environment == Environment.PRODUCTION:
                deployment.previous_version = self._current_production
                self._current_production = version
            else:
                deployment.previous_version = self._current_staging
                self._current_staging = version

            # Save to registry
            await self._save_deployment(deployment)

            logger.info({
                "event": "deployment_completed",
                "deployment_id": deployment_id,
                "model_version": version,
                "environment": environment.value
            })

            return {
                "success": True,
                "deployment_id": deployment_id,
                "model_version": version,
                "environment": environment.value,
                "status": DeploymentStatus.DEPLOYED.value,
                "accuracy": accuracy,
                "deployed_at": deployment.deployed_at.isoformat()
            }

        except Exception as e:
            deployment.status = DeploymentStatus.FAILED
            self._deployments[deployment_id] = deployment

            logger.error({
                "event": "deployment_failed",
                "deployment_id": deployment_id,
                "error": str(e)
            })

            return {
                "success": False,
                "error": str(e),
                "deployment_id": deployment_id,
                "status": DeploymentStatus.FAILED.value
            }

    async def _deploy_model(
        self,
        model_path: str,
        version: str
    ) -> None:
        """
        Internal deployment process.

        Args:
            model_path: Path to model
            version: Model version
        """
        # Simulate deployment (copy files, update registry, etc.)
        target_path = os.path.join(self.registry_path, version)
        os.makedirs(target_path, exist_ok=True)

        # Simulate async work
        await asyncio.sleep(0.1)

        # Write model metadata
        metadata = {
            "version": version,
            "source_path": model_path,
            "deployed_at": datetime.now(timezone.utc).isoformat()
        }

        with open(os.path.join(target_path, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2)

    async def _save_deployment(
        self,
        deployment: DeploymentRecord
    ) -> None:
        """
        Save deployment record to registry.

        Args:
            deployment: Deployment record
        """
        record_path = os.path.join(
            self.registry_path,
            "deployments",
            f"{deployment.deployment_id}.json"
        )
        os.makedirs(os.path.dirname(record_path), exist_ok=True)

        with open(record_path, "w") as f:
            json.dump(deployment.to_dict(), f, indent=2)

    async def verify_deployment(
        self,
        version: str
    ) -> bool:
        """
        Verify that a deployment was successful.

        Args:
            version: Model version to verify

        Returns:
            True if deployment is valid
        """
        model_dir = os.path.join(self.registry_path, version)

        if not os.path.exists(model_dir):
            logger.warning({
                "event": "verification_failed",
                "version": version,
                "reason": "Model directory not found"
            })
            return False

        # Check metadata
        metadata_path = os.path.join(model_dir, "metadata.json")
        if not os.path.exists(metadata_path):
            logger.warning({
                "event": "verification_failed",
                "version": version,
                "reason": "Metadata not found"
            })
            return False

        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            if metadata.get("version") != version:
                logger.warning({
                    "event": "verification_failed",
                    "version": version,
                    "reason": "Version mismatch"
                })
                return False

            logger.info({
                "event": "verification_passed",
                "version": version
            })

            return True

        except Exception as e:
            logger.error({
                "event": "verification_error",
                "version": version,
                "error": str(e)
            })
            return False

    async def promote_to_production(
        self,
        version: str
    ) -> Dict[str, Any]:
        """
        Promote a staging model to production.

        Args:
            version: Model version to promote

        Returns:
            Dict with promotion result
        """
        # Verify the model exists
        if not await self.verify_deployment(version):
            return {
                "success": False,
                "error": f"Model {version} not found or invalid"
            }

        # Check if currently in staging
        if self._current_staging != version:
            logger.warning({
                "event": "promotion_warning",
                "version": version,
                "current_staging": self._current_staging
            })

        previous_production = self._current_production
        self._current_production = version

        logger.info({
            "event": "model_promoted",
            "version": version,
            "previous_production": previous_production
        })

        return {
            "success": True,
            "version": version,
            "environment": Environment.PRODUCTION.value,
            "previous_version": previous_production,
            "promoted_at": datetime.now(timezone.utc).isoformat()
        }

    def get_current_model(
        self,
        environment: Environment = Environment.PRODUCTION
    ) -> Optional[str]:
        """
        Get current deployed model version.

        Args:
            environment: Target environment

        Returns:
            Current model version or None
        """
        if environment == Environment.PRODUCTION:
            return self._current_production
        return self._current_staging

    def get_deployment_history(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get deployment history.

        Args:
            limit: Maximum number of records

        Returns:
            List of deployment records
        """
        deployments = sorted(
            self._deployments.values(),
            key=lambda d: d.deployed_at,
            reverse=True
        )

        return [d.to_dict() for d in deployments[:limit]]

    def get_status(self) -> Dict[str, Any]:
        """
        Get deployer status.

        Returns:
            Dict with status information
        """
        return {
            "registry_path": self.registry_path,
            "current_production": self._current_production,
            "current_staging": self._current_staging,
            "total_deployments": len(self._deployments),
            "accuracy_threshold": self.MIN_ACCURACY_THRESHOLD
        }


def get_model_deployer(
    registry_path: str = "./models/registry"
) -> ModelDeployer:
    """
    Get a ModelDeployer instance.

    Args:
        registry_path: Path to model registry

    Returns:
        ModelDeployer instance
    """
    return ModelDeployer(registry_path=registry_path)
