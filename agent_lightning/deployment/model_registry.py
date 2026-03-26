"""
Agent Lightning - Model Registry Module.

Tracks model versions, deployments, and provides safe promotion workflow.

Key Features:
- Register new model versions
- Track active model per company
- List version history
- Atomic version switches
- Immutable version records
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid
import json
import logging

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class ModelVersion(BaseModel):
    """Model version record."""
    version: str
    model_id: str
    company_id: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    training_data_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    status: str = "development"
    deployment_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict()


class ModelRegistrationResult(BaseModel):
    """Result of model registration."""
    success: bool
    version: str
    model_id: str
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None

    model_config = ConfigDict()


class ModelActivationResult(BaseModel):
    """Result of model activation."""
    success: bool
    version: str
    previous_version: Optional[str] = None
    activated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None

    model_config = ConfigDict()


class ModelRegistry:
    """
    Model version registry for Agent Lightning.

    Provides immutable version tracking and safe model promotion.

    Usage:
        registry = ModelRegistry()
        await registry.register_model("v1.0.0", {"accuracy": 0.95})
        await registry.set_active("v1.0.0")
        current = await registry.get_current_model()
    """

    def __init__(self) -> None:
        """Initialize model registry."""
        # Version storage: version -> ModelVersion
        self._versions: Dict[str, ModelVersion] = {}

        # Company active model mapping: company_id -> version
        self._active_models: Dict[str, str] = {}

        # Version history per company
        self._version_history: Dict[str, List[str]] = {}

        # Registration count
        self._registration_count = 0

    async def register_model(
        self,
        version: str,
        metrics: Dict[str, Any],
        company_id: str = "default",
        training_data_hash: Optional[str] = None,
        created_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ModelRegistrationResult:
        """
        Register a new model version.

        Args:
            version: Version string (e.g., "v1.0.0")
            metrics: Performance metrics (accuracy, f1, etc.)
            company_id: Company ID
            training_data_hash: Hash of training data used
            created_by: Who created this version
            metadata: Additional metadata

        Returns:
            ModelRegistrationResult
        """
        try:
            # Check if version already exists
            if version in self._versions:
                return ModelRegistrationResult(
                    success=False,
                    version=version,
                    model_id="",
                    error=f"Version {version} already exists"
                )

            # Generate model ID
            model_id = f"model_{uuid.uuid4().hex[:12]}"

            # Create version record
            model_version = ModelVersion(
                version=version,
                model_id=model_id,
                company_id=company_id,
                metrics=metrics,
                training_data_hash=training_data_hash,
                created_by=created_by,
                status="development",
                metadata=metadata or {}
            )

            # Store version
            self._versions[version] = model_version

            # Add to history
            if company_id not in self._version_history:
                self._version_history[company_id] = []
            self._version_history[company_id].append(version)

            self._registration_count += 1

            logger.info({
                "event": "model_registered",
                "version": version,
                "model_id": model_id,
                "company_id": company_id,
                "metrics": metrics
            })

            return ModelRegistrationResult(
                success=True,
                version=version,
                model_id=model_id
            )

        except Exception as e:
            logger.error({
                "event": "model_registration_failed",
                "version": version,
                "error": str(e)
            })

            return ModelRegistrationResult(
                success=False,
                version=version,
                model_id="",
                error=str(e)
            )

    async def get_current_model(
        self,
        company_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Get the current active model for a company.

        Args:
            company_id: Company ID

        Returns:
            Dict with current model info or empty if none
        """
        active_version = self._active_models.get(company_id)

        if not active_version:
            return {
                "success": False,
                "error": "No active model for company",
                "company_id": company_id
            }

        model = self._versions.get(active_version)

        if not model:
            return {
                "success": False,
                "error": "Active model version not found",
                "version": active_version
            }

        return {
            "success": True,
            "version": model.version,
            "model_id": model.model_id,
            "company_id": model.company_id,
            "metrics": model.metrics,
            "status": model.status,
            "created_at": model.created_at.isoformat(),
            "deployment_count": model.deployment_count
        }

    async def list_versions(
        self,
        company_id: str = "default",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        List model versions for a company.

        Args:
            company_id: Company ID
            limit: Maximum versions to return

        Returns:
            List of version records
        """
        versions = self._version_history.get(company_id, [])

        result = []
        for version in reversed(versions[-limit:]):
            model = self._versions.get(version)
            if model:
                result.append({
                    "version": model.version,
                    "model_id": model.model_id,
                    "metrics": model.metrics,
                    "status": model.status,
                    "created_at": model.created_at.isoformat(),
                    "is_active": version == self._active_models.get(company_id)
                })

        return result

    async def set_active(
        self,
        version: str,
        company_id: str = "default"
    ) -> ModelActivationResult:
        """
        Set a model version as active.

        Args:
            version: Version to activate
            company_id: Company ID

        Returns:
            ModelActivationResult
        """
        try:
            # Check if version exists
            if version not in self._versions:
                return ModelActivationResult(
                    success=False,
                    version=version,
                    error=f"Version {version} not found"
                )

            model = self._versions[version]

            # Get previous version
            previous_version = self._active_models.get(company_id)

            # Update active model
            self._active_models[company_id] = version

            # Update model status and deployment count
            model.status = "production"
            model.deployment_count += 1

            # Mark previous as deprecated if exists
            if previous_version and previous_version in self._versions:
                prev_model = self._versions[previous_version]
                if prev_model.status == "production":
                    prev_model.status = "deprecated"

            logger.info({
                "event": "model_activated",
                "version": version,
                "company_id": company_id,
                "previous_version": previous_version
            })

            return ModelActivationResult(
                success=True,
                version=version,
                previous_version=previous_version
            )

        except Exception as e:
            logger.error({
                "event": "model_activation_failed",
                "version": version,
                "error": str(e)
            })

            return ModelActivationResult(
                success=False,
                version=version,
                error=str(e)
            )

    async def get_version(
        self,
        version: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get details of a specific version.

        Args:
            version: Version string

        Returns:
            Version details or None
        """
        model = self._versions.get(version)

        if not model:
            return None

        return {
            "version": model.version,
            "model_id": model.model_id,
            "company_id": model.company_id,
            "metrics": model.metrics,
            "status": model.status,
            "training_data_hash": model.training_data_hash,
            "created_at": model.created_at.isoformat(),
            "created_by": model.created_by,
            "deployment_count": model.deployment_count,
            "metadata": model.metadata
        }

    async def get_metrics_history(
        self,
        company_id: str = "default",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get metrics history for a company's models.

        Args:
            company_id: Company ID
            limit: Maximum records

        Returns:
            List of metrics records
        """
        versions = self._version_history.get(company_id, [])
        history = []

        for version in reversed(versions[-limit:]):
            model = self._versions.get(version)
            if model:
                history.append({
                    "version": model.version,
                    "metrics": model.metrics,
                    "created_at": model.created_at.isoformat()
                })

        return history

    async def compare_versions(
        self,
        version1: str,
        version2: str
    ) -> Dict[str, Any]:
        """
        Compare two model versions.

        Args:
            version1: First version
            version2: Second version

        Returns:
            Comparison result
        """
        model1 = self._versions.get(version1)
        model2 = self._versions.get(version2)

        if not model1 or not model2:
            return {
                "success": False,
                "error": "One or both versions not found"
            }

        metrics1 = model1.metrics
        metrics2 = model2.metrics

        # Calculate differences
        diff = {}
        all_keys = set(metrics1.keys()) | set(metrics2.keys())

        for key in all_keys:
            val1 = metrics1.get(key, 0)
            val2 = metrics2.get(key, 0)

            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                diff[key] = {
                    "version1": val1,
                    "version2": val2,
                    "change": val2 - val1,
                    "change_percent": ((val2 - val1) / val1 * 100) if val1 != 0 else 0
                }

        return {
            "success": True,
            "version1": {
                "version": version1,
                "metrics": metrics1
            },
            "version2": {
                "version": version2,
                "metrics": metrics2
            },
            "comparison": diff
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dict with stats
        """
        active_count = len(self._active_models)

        by_status = {}
        for model in self._versions.values():
            by_status[model.status] = by_status.get(model.status, 0) + 1

        return {
            "total_registrations": self._registration_count,
            "total_versions": len(self._versions),
            "active_models": active_count,
            "by_status": by_status
        }


# Global registry instance
_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """
    Get the global ModelRegistry instance.

    Returns:
        ModelRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry (for testing)."""
    global _registry
    _registry = None
