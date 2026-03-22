"""
Model Rollback for Agent Lightning.

Handles rolling back to previous model versions.

CRITICAL: Ensures safe rollback with verification.

Features:
- Rollback to previous version
- Get previous stable version
- Verify rollback success
- Track rollback history
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import os
import json
import asyncio

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class RollbackStatus(str, Enum):
    """Rollback status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


@dataclass
class RollbackRecord:
    """Record of a model rollback."""
    rollback_id: str
    from_version: str
    to_version: str
    reason: str
    status: RollbackStatus
    initiated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    initiated_by: str = "system"
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rollback_id": self.rollback_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "reason": self.reason,
            "status": self.status.value,
            "initiated_at": self.initiated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "initiated_by": self.initiated_by,
            "verified": self.verified
        }


class ModelRollback:
    """
    Model Rollback Manager.

    Handles rolling back to previous model versions safely.

    CRITICAL: Always verifies rollback success.

    Features:
    - Rollback to specific version
    - Rollback to previous stable
    - Verify rollback success
    - Track rollback history
    - Audit trail for compliance

    Example:
        rollback = ModelRollback()
        result = await rollback.rollback("model_v1", reason="Accuracy drop")
        verify = await rollback.verify_rollback("model_v1")
    """

    def __init__(
        self,
        registry_path: str = "./models/registry"
    ) -> None:
        """
        Initialize Model Rollback.

        Args:
            registry_path: Path to model registry
        """
        self.registry_path = registry_path
        self._rollbacks: List[RollbackRecord] = []
        self._version_history: List[str] = []
        self._current_version: Optional[str] = None

        # Ensure registry exists
        os.makedirs(registry_path, exist_ok=True)

        logger.info({
            "event": "model_rollback_initialized",
            "registry_path": registry_path
        })

    async def rollback(
        self,
        target_version: str,
        reason: str = "Manual rollback",
        initiated_by: str = "system"
    ) -> Dict[str, Any]:
        """
        Rollback to a specific model version.

        Args:
            target_version: Version to rollback to
            reason: Reason for rollback
            initiated_by: Who initiated the rollback

        Returns:
            Dict with rollback result
        """
        rollback_id = f"rb_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        logger.info({
            "event": "rollback_initiated",
            "rollback_id": rollback_id,
            "target_version": target_version,
            "reason": reason
        })

        # Create rollback record
        rollback_record = RollbackRecord(
            rollback_id=rollback_id,
            from_version=self._current_version or "unknown",
            to_version=target_version,
            reason=reason,
            status=RollbackStatus.IN_PROGRESS,
            initiated_by=initiated_by
        )

        try:
            # Verify target version exists
            if not await self._verify_version_exists(target_version):
                rollback_record.status = RollbackStatus.FAILED
                self._rollbacks.append(rollback_record)

                return {
                    "success": False,
                    "error": f"Target version {target_version} not found",
                    "rollback_id": rollback_id
                }

            # Perform rollback
            previous_version = self._current_version
            self._current_version = target_version

            # Update version history
            if previous_version and previous_version not in self._version_history:
                self._version_history.append(previous_version)

            # Mark completed
            rollback_record.status = RollbackStatus.COMPLETED
            rollback_record.completed_at = datetime.now(timezone.utc)
            self._rollbacks.append(rollback_record)

            # Save rollback record
            await self._save_rollback_record(rollback_record)

            logger.info({
                "event": "rollback_completed",
                "rollback_id": rollback_id,
                "from_version": previous_version,
                "to_version": target_version
            })

            return {
                "success": True,
                "rollback_id": rollback_id,
                "from_version": previous_version,
                "to_version": target_version,
                "reason": reason,
                "completed_at": rollback_record.completed_at.isoformat()
            }

        except Exception as e:
            rollback_record.status = RollbackStatus.FAILED
            self._rollbacks.append(rollback_record)

            logger.error({
                "event": "rollback_failed",
                "rollback_id": rollback_id,
                "error": str(e)
            })

            return {
                "success": False,
                "error": str(e),
                "rollback_id": rollback_id
            }

    async def get_previous_version(self) -> Dict[str, Any]:
        """
        Get the previous stable model version.

        Returns:
            Dict with previous version info
        """
        if not self._version_history:
            return {
                "success": False,
                "error": "No previous version available",
                "current_version": self._current_version
            }

        previous = self._version_history[-1] if self._version_history else None

        return {
            "success": True,
            "previous_version": previous,
            "current_version": self._current_version,
            "version_history_count": len(self._version_history)
        }

    async def verify_rollback(
        self,
        version: str
    ) -> bool:
        """
        Verify that rollback was successful.

        Args:
            version: Version to verify

        Returns:
            True if rollback was successful
        """
        # Check if this is the current version
        if self._current_version != version:
            logger.warning({
                "event": "rollback_verification_warning",
                "expected_version": version,
                "current_version": self._current_version
            })
            return False

        # Verify model files exist
        if not await self._verify_version_exists(version):
            logger.error({
                "event": "rollback_verification_failed",
                "version": version,
                "reason": "Model files not found"
            })
            return False

        # Mark the rollback as verified
        for rb in reversed(self._rollbacks):
            if rb.to_version == version and rb.status == RollbackStatus.COMPLETED:
                rb.verified = True
                rb.status = RollbackStatus.VERIFIED
                break

        logger.info({
            "event": "rollback_verified",
            "version": version
        })

        return True

    async def _verify_version_exists(
        self,
        version: str
    ) -> bool:
        """
        Verify that a model version exists in the registry.

        Args:
            version: Version to verify

        Returns:
            True if version exists
        """
        version_path = os.path.join(self.registry_path, version)

        if not os.path.exists(version_path):
            return False

        # Check for metadata file
        metadata_path = os.path.join(version_path, "metadata.json")

        if not os.path.exists(metadata_path):
            return False

        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            return metadata.get("version") == version

        except Exception:
            return False

    async def _save_rollback_record(
        self,
        record: RollbackRecord
    ) -> None:
        """
        Save rollback record to registry.

        Args:
            record: Rollback record to save
        """
        records_path = os.path.join(
            self.registry_path,
            "rollbacks",
            f"{record.rollback_id}.json"
        )
        os.makedirs(os.path.dirname(records_path), exist_ok=True)

        with open(records_path, "w") as f:
            json.dump(record.to_dict(), f, indent=2)

    def set_current_version(
        self,
        version: str
    ) -> None:
        """
        Set the current version (for initialization).

        Args:
            version: Current version to set
        """
        if self._current_version and self._current_version != version:
            if self._current_version not in self._version_history:
                self._version_history.append(self._current_version)

        self._current_version = version

    def get_rollback_history(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get rollback history.

        Args:
            limit: Maximum number of records

        Returns:
            List of rollback records
        """
        return [rb.to_dict() for rb in self._rollbacks[-limit:]]

    def get_available_versions(self) -> List[str]:
        """
        Get list of available versions to rollback to.

        Returns:
            List of version strings
        """
        versions = []

        # Check registry for all versions
        if os.path.exists(self.registry_path):
            for item in os.listdir(self.registry_path):
                item_path = os.path.join(self.registry_path, item)
                if os.path.isdir(item_path):
                    metadata_path = os.path.join(item_path, "metadata.json")
                    if os.path.exists(metadata_path):
                        versions.append(item)

        return sorted(versions)

    def get_status(self) -> Dict[str, Any]:
        """
        Get rollback manager status.

        Returns:
            Dict with status information
        """
        return {
            "registry_path": self.registry_path,
            "current_version": self._current_version,
            "version_history_count": len(self._version_history),
            "rollback_count": len(self._rollbacks),
            "available_versions": self.get_available_versions()
        }


def get_model_rollback(
    registry_path: str = "./models/registry"
) -> ModelRollback:
    """
    Get a ModelRollback instance.

    Args:
        registry_path: Path to model registry

    Returns:
        ModelRollback instance
    """
    return ModelRollback(registry_path=registry_path)
