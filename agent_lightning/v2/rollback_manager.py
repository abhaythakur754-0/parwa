"""
Rollback Manager - Quick rollback system for model deployments.

CRITICAL: Rollback must work in <30 seconds.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import logging
import time
import json
import os

logger = logging.getLogger(__name__)


class RollbackStatus(Enum):
    """Status of rollback operation"""
    PENDING = "pending"
    INITIATED = "initiated"
    SWITCHING_TRAFFIC = "switching_traffic"
    VERIFYING = "verifying"
    COMPLETE = "complete"
    FAILED = "failed"


class RollbackTrigger(Enum):
    """Triggers for rollback"""
    MANUAL = "manual"
    ERROR_RATE = "error_rate"
    ACCURACY_DROP = "accuracy_drop"
    LATENCY_SPIKE = "latency_spike"
    HEALTH_CHECK_FAILURE = "health_check_failure"
    REGRESSION_FAILURE = "regression_failure"


@dataclass
class ModelVersion:
    """Model version information"""
    version_id: str
    model_path: str
    deployed_at: datetime
    accuracy: float
    is_active: bool = False
    is_rollback_target: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "version_id": self.version_id,
            "model_path": self.model_path,
            "deployed_at": self.deployed_at.isoformat(),
            "accuracy": self.accuracy,
            "is_active": self.is_active,
            "is_rollback_target": self.is_rollback_target,
        }


@dataclass
class RollbackRecord:
    """Record of a rollback operation"""
    rollback_id: str
    trigger: RollbackTrigger
    from_version: str
    to_version: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    status: RollbackStatus = RollbackStatus.PENDING
    traffic_switch_time_ms: Optional[float] = None
    verification_passed: bool = False
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "rollback_id": self.rollback_id,
            "trigger": self.trigger.value,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "status": self.status.value,
            "traffic_switch_time_ms": self.traffic_switch_time_ms,
            "verification_passed": self.verification_passed,
            "reason": self.reason,
            "metadata": self.metadata,
        }


@dataclass
class RollbackConfig:
    """Configuration for rollback"""
    max_rollback_time_seconds: float = 30.0
    traffic_switch_timeout_ms: float = 5000.0
    verification_timeout_seconds: float = 10.0
    keep_version_history: int = 5
    audit_trail_enabled: bool = True


class RollbackManager:
    """
    Quick rollback system for model deployments.

    CRITICAL: Rollback must work in <30 seconds.

    Features:
    - One-command rollback
    - Instant traffic switch
    - Rollback verification
    - Version history
    - Audit trail
    """

    MAX_ROLLBACK_TIME_SECONDS = 30.0

    def __init__(
        self,
        version_registry_path: str,
        config: Optional[RollbackConfig] = None,
    ):
        """
        Initialize rollback manager.

        Args:
            version_registry_path: Path to version registry
            config: Rollback configuration
        """
        self.version_registry_path = version_registry_path
        self.config = config or RollbackConfig()
        self._versions: List[ModelVersion] = []
        self._audit_trail: List[RollbackRecord] = []
        self._active_version: Optional[ModelVersion] = None

        os.makedirs(os.path.dirname(version_registry_path), exist_ok=True)
        self._load_versions()

    def register_version(
        self,
        version_id: str,
        model_path: str,
        accuracy: float,
    ) -> ModelVersion:
        """
        Register a new model version.

        Args:
            version_id: Version identifier
            model_path: Path to model files
            accuracy: Validated accuracy

        Returns:
            Registered model version
        """
        version = ModelVersion(
            version_id=version_id,
            model_path=model_path,
            deployed_at=datetime.now(),
            accuracy=accuracy,
            is_active=True,
        )

        # Deactivate previous versions
        for v in self._versions:
            v.is_active = False

        self._versions.append(version)
        self._active_version = version

        # Limit history
        if len(self._versions) > self.config.keep_version_history:
            self._versions = self._versions[-self.config.keep_version_history :]

        self._save_versions()

        logger.info(f"Registered version: {version_id}")

        return version

    def rollback(
        self,
        target_version: Optional[str] = None,
        trigger: RollbackTrigger = RollbackTrigger.MANUAL,
        reason: str = "",
    ) -> RollbackRecord:
        """
        Execute rollback to previous version.

        Args:
            target_version: Specific version to rollback to (default: previous)
            trigger: What triggered the rollback
            reason: Human-readable reason

        Returns:
            Rollback record
        """
        start_time = time.time()
        rollback_id = f"rb_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Find target version
        if target_version:
            to_version = self._find_version(target_version)
        else:
            to_version = self._get_previous_version()

        if not to_version:
            return RollbackRecord(
                rollback_id=rollback_id,
                trigger=trigger,
                from_version=self._active_version.version_id if self._active_version else "none",
                to_version="none",
                start_time=datetime.now(),
                status=RollbackStatus.FAILED,
                reason="No target version available",
            )

        # Create rollback record
        record = RollbackRecord(
            rollback_id=rollback_id,
            trigger=trigger,
            from_version=self._active_version.version_id if self._active_version else "none",
            to_version=to_version.version_id,
            start_time=datetime.now(),
            status=RollbackStatus.INITIATED,
            reason=reason,
        )

        # Switch traffic
        record.status = RollbackStatus.SWITCHING_TRAFFIC
        switch_start = time.time()

        self._switch_traffic(to_version)

        switch_end = time.time()
        record.traffic_switch_time_ms = (switch_end - switch_start) * 1000

        # Verify
        record.status = RollbackStatus.VERIFYING
        record.verification_passed = self._verify_rollback(to_version)

        # Complete
        end_time = time.time()
        record.end_time = datetime.now()
        record.duration_seconds = end_time - start_time
        record.status = RollbackStatus.COMPLETE if record.verification_passed else RollbackStatus.FAILED

        # Update active version
        if record.verification_passed:
            for v in self._versions:
                v.is_active = v.version_id == to_version.version_id
            self._active_version = to_version

        # Add to audit trail
        if self.config.audit_trail_enabled:
            self._audit_trail.append(record)
            self._save_audit_trail()

        logger.info(
            f"Rollback complete: {record.rollback_id}, "
            f"duration: {record.duration_seconds:.2f}s"
        )

        return record

    def one_command_rollback(self) -> RollbackRecord:
        """
        One-command rollback to previous version.

        Returns:
            Rollback record
        """
        return self.rollback(
            trigger=RollbackTrigger.MANUAL,
            reason="One-command rollback initiated",
        )

    def get_active_version(self) -> Optional[ModelVersion]:
        """Get currently active version"""
        return self._active_version

    def get_version_history(self) -> List[ModelVersion]:
        """Get all registered versions"""
        return self._versions

    def get_audit_trail(self, limit: int = 20) -> List[RollbackRecord]:
        """Get audit trail of rollbacks"""
        return self._audit_trail[-limit:]

    def get_previous_version(self) -> Optional[ModelVersion]:
        """Get previous stable version"""
        return self._get_previous_version()

    def verify_rollback_capability(self) -> Dict[str, Any]:
        """Verify rollback capability is ready"""
        previous = self._get_previous_version()

        return {
            "rollback_ready": previous is not None,
            "previous_version_available": previous is not None,
            "active_version": self._active_version.version_id if self._active_version else None,
            "previous_version": previous.version_id if previous else None,
            "max_rollback_time_seconds": self.MAX_ROLLBACK_TIME_SECONDS,
        }

    def _find_version(self, version_id: str) -> Optional[ModelVersion]:
        """Find version by ID"""
        for v in self._versions:
            if v.version_id == version_id:
                return v
        return None

    def _get_previous_version(self) -> Optional[ModelVersion]:
        """Get previous stable version"""
        if len(self._versions) < 2:
            return None

        # Return second-to-last version
        return self._versions[-2] if len(self._versions) >= 2 else None

    def _switch_traffic(self, target: ModelVersion) -> None:
        """Switch traffic to target version"""
        # Simulate instant traffic switch
        # In production, would update load balancer/router
        time.sleep(0.001)  # Simulate minimal delay
        logger.info(f"Traffic switched to: {target.version_id}")

    def _verify_rollback(self, target: ModelVersion) -> bool:
        """Verify rollback succeeded"""
        # Simulate verification
        # In production, would check health endpoints
        return True

    def _load_versions(self) -> None:
        """Load versions from registry"""
        if os.path.exists(self.version_registry_path):
            with open(self.version_registry_path, "r") as f:
                data = json.load(f)
                self._versions = [
                    ModelVersion(**v) for v in data.get("versions", [])
                ]

    def _save_versions(self) -> None:
        """Save versions to registry"""
        data = {
            "versions": [v.to_dict() for v in self._versions],
            "last_updated": datetime.now().isoformat(),
        }
        with open(self.version_registry_path, "w") as f:
            json.dump(data, f, indent=2)

    def _save_audit_trail(self) -> None:
        """Save audit trail"""
        audit_path = self.version_registry_path.replace(".json", "_audit.json")
        data = {
            "audit_trail": [r.to_dict() for r in self._audit_trail],
            "last_updated": datetime.now().isoformat(),
        }
        with open(audit_path, "w") as f:
            json.dump(data, f, indent=2)


def quick_rollback(
    version_registry_path: str,
    reason: str = "Manual rollback",
) -> RollbackRecord:
    """
    Convenience function for quick rollback.

    Args:
        version_registry_path: Path to version registry
        reason: Reason for rollback

    Returns:
        Rollback record
    """
    manager = RollbackManager(version_registry_path=version_registry_path)
    return manager.rollback(trigger=RollbackTrigger.MANUAL, reason=reason)
