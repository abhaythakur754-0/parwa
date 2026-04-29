"""
Model Deployment Service — F-105

Deploys validated models with safety mechanisms:
- Canary releases (gradual rollout)
- Auto-rollback on failure detection
- Blue-green deployment support
- Deployment monitoring

Building Codes:
- BC-001: Multi-tenant isolation
- BC-007: AI Model Interaction
- BC-012: Error handling
- BC-004: Background Jobs for monitoring
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict
from uuid import uuid4
from enum import Enum

from sqlalchemy.orm import Session

logger = logging.getLogger("parwa.model_deployment")

# ── Constants ───────────────────────────────────────────────────────────────

# Deployment status values


class DeploymentStatus(str, Enum):
    PENDING = "pending"
    INITIALIZING = "initializing"
    CANARY = "canary"  # Canary phase
    ROLLING_OUT = "rolling_out"  # Gradual rollout
    ACTIVE = "active"  # Fully deployed
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    PAUSED = "paused"


# Deployment strategies


class DeploymentStrategy(str, Enum):
    CANARY = "canary"  # Gradual rollout with monitoring
    BLUE_GREEN = "blue_green"  # Instant switch with rollback capability
    ROLLING = "rolling"  # Gradual replacement


# Rollback triggers


class RollbackTrigger(str, Enum):
    ERROR_RATE = "error_rate"
    LATENCY = "latency"
    ACCURACY_DROP = "accuracy_drop"
    MANUAL = "manual"
    SAFETY_VIOLATION = "safety_violation"


# Default thresholds
DEFAULT_CANARY_PERCENTAGE = 5  # Start with 5% traffic
DEFAULT_ROLLOUT_INCREMENT = 10  # Increase by 10% each step
DEFAULT_ROLLOUT_INTERVAL_MINUTES = 5  # Wait 5 min between increments
DEFAULT_ERROR_RATE_THRESHOLD = 0.05  # Rollback if >5% errors
DEFAULT_LATENCY_THRESHOLD_MS = 3000  # Rollback if p95 >3s
DEFAULT_ACCURACY_DROP_THRESHOLD = 0.05  # Rollback if accuracy drops >5%

# Canary thresholds
CANARY_ERROR_RATE_THRESHOLD = 0.02  # 2% error rate during canary
CANARY_LATENCY_THRESHOLD_MS = 2500  # 2.5s latency during canary


class ModelDeploymentService:
    """Service for deploying models with safety mechanisms (F-105).

    This service handles:
    - Canary releases
    - Auto-rollback on failure
    - Blue-green deployments
    - Deployment monitoring

    Usage:
        service = ModelDeploymentService(db)
        deployment = service.create_deployment(company_id, validation_id, model_path)
        service.start_canary(deployment_id)
    """

    def __init__(self, db: Session):
        self.db = db

    # ══════════════════════════════════════════════════════════════════════════
    # Deployment CRUD
    # ══════════════════════════════════════════════════════════════════════════

    def create_deployment(
        self,
        company_id: str,
        agent_id: str,
        model_path: str,
        validation_id: str,
        strategy: str = DeploymentStrategy.CANARY.value,
        baseline_model_path: Optional[str] = None,
    ) -> Dict:
        """Create a new deployment record.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent ID.
            model_path: Path to the validated model.
            validation_id: Validation run ID.
            strategy: Deployment strategy.
            baseline_model_path: Current production model (for rollback).

        Returns:
            Dict with deployment_id and status.
        """
        deployment_id = str(uuid4())

        deployment = {
            "id": deployment_id,
            "company_id": company_id,
            "agent_id": agent_id,
            "model_path": model_path,
            "validation_id": validation_id,
            "baseline_model_path": baseline_model_path,
            "strategy": strategy,
            "status": DeploymentStatus.PENDING.value,
            "canary_percentage": 0,
            "target_percentage": 100,
            "current_percentage": 0,
            "rollback_thresholds": {
                "error_rate": DEFAULT_ERROR_RATE_THRESHOLD,
                "latency_p95_ms": DEFAULT_LATENCY_THRESHOLD_MS,
                "accuracy_drop": DEFAULT_ACCURACY_DROP_THRESHOLD,
            },
            "metrics": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "deployment_created",
            extra={
                "company_id": company_id,
                "agent_id": agent_id,
                "deployment_id": deployment_id,
                "strategy": strategy,
            },
        )

        return deployment

    def start_deployment(
        self,
        deployment: Dict,
        canary_percentage: int = DEFAULT_CANARY_PERCENTAGE,
    ) -> Dict:
        """Start the deployment process.

        Args:
            deployment: Deployment dict.
            canary_percentage: Initial traffic percentage for canary.

        Returns:
            Updated deployment dict.
        """
        deployment_id = deployment["id"]
        strategy = deployment.get("strategy", DeploymentStrategy.CANARY.value)

        deployment["status"] = DeploymentStatus.INITIALIZING.value
        deployment["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "deployment_starting",
            extra={
                "deployment_id": deployment_id,
                "strategy": strategy,
                "canary_percentage": canary_percentage,
            },
        )

        if strategy == DeploymentStrategy.CANARY.value:
            return self._start_canary_phase(deployment, canary_percentage)
        elif strategy == DeploymentStrategy.BLUE_GREEN.value:
            return self._start_blue_green(deployment)
        else:
            return self._start_rolling_deployment(deployment)

    # ══════════════════════════════════════════════════════════════════════════
    # Canary Deployment
    # ══════════════════════════════════════════════════════════════════════════

    def _start_canary_phase(self, deployment: Dict, canary_percentage: int) -> Dict:
        """Start canary phase of deployment.

        Args:
            deployment: Deployment dict.
            canary_percentage: Percentage of traffic to route to new model.

        Returns:
            Updated deployment dict.
        """
        deployment["status"] = DeploymentStatus.CANARY.value
        deployment["canary_percentage"] = canary_percentage
        deployment["current_percentage"] = canary_percentage
        deployment["canary_started_at"] = datetime.now(timezone.utc).isoformat()
        deployment["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "canary_phase_started",
            extra={
                "deployment_id": deployment["id"],
                "canary_percentage": canary_percentage,
            },
        )

        return deployment

    def check_canary_health(self, deployment: Dict) -> Dict:
        """Check canary health metrics.

        Args:
            deployment: Deployment dict.

        Returns:
            Dict with health status.
        """
        deployment_id = deployment["id"]
        thresholds = deployment.get("rollback_thresholds", {})

        # Get current metrics (simulated)
        metrics = self._collect_deployment_metrics(deployment)
        deployment["metrics"] = metrics

        health_status = {
            "healthy": True,
            "triggers": [],
            "metrics": metrics,
        }

        # Check error rate
        error_rate = metrics.get("error_rate", 0)
        if error_rate > thresholds.get("error_rate", DEFAULT_ERROR_RATE_THRESHOLD):
            health_status["healthy"] = False
            health_status["triggers"].append(
                {
                    "type": RollbackTrigger.ERROR_RATE.value,
                    "actual": error_rate,
                    "threshold": thresholds.get("error_rate"),
                }
            )

        # Check latency
        latency_p95 = metrics.get("latency_p95_ms", 0)
        if latency_p95 > thresholds.get("latency_p95_ms", DEFAULT_LATENCY_THRESHOLD_MS):
            health_status["healthy"] = False
            health_status["triggers"].append(
                {
                    "type": RollbackTrigger.LATENCY.value,
                    "actual": latency_p95,
                    "threshold": thresholds.get("latency_p95_ms"),
                }
            )

        # Check accuracy (if available)
        if "accuracy" in metrics:
            baseline_accuracy = deployment.get("baseline_accuracy", 0.85)
            accuracy_drop = baseline_accuracy - metrics["accuracy"]
            if accuracy_drop > thresholds.get(
                "accuracy_drop", DEFAULT_ACCURACY_DROP_THRESHOLD
            ):
                health_status["healthy"] = False
                health_status["triggers"].append(
                    {
                        "type": RollbackTrigger.ACCURACY_DROP.value,
                        "actual": accuracy_drop,
                        "threshold": thresholds.get("accuracy_drop"),
                    }
                )

        logger.info(
            "canary_health_check",
            extra={
                "deployment_id": deployment_id,
                "healthy": health_status["healthy"],
                "triggers": len(health_status["triggers"]),
            },
        )

        return health_status

    def advance_canary(
        self,
        deployment: Dict,
        increment: int = DEFAULT_ROLLOUT_INCREMENT,
    ) -> Dict:
        """Advance canary to higher traffic percentage.

        Args:
            deployment: Deployment dict.
            increment: Percentage to increase.

        Returns:
            Updated deployment dict.
        """
        current = deployment.get("current_percentage", 0)
        new_percentage = min(current + increment, 100)

        if new_percentage >= 100:
            deployment["status"] = DeploymentStatus.ACTIVE.value
            deployment["current_percentage"] = 100
            deployment["completed_at"] = datetime.now(timezone.utc).isoformat()
        else:
            deployment["status"] = DeploymentStatus.ROLLING_OUT.value
            deployment["current_percentage"] = new_percentage

        deployment["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "canary_advanced",
            extra={
                "deployment_id": deployment["id"],
                "from_percentage": current,
                "to_percentage": new_percentage,
            },
        )

        return deployment

    # ══════════════════════════════════════════════════════════════════════════
    # Blue-Green Deployment
    # ══════════════════════════════════════════════════════════════════════════

    def _start_blue_green(self, deployment: Dict) -> Dict:
        """Start blue-green deployment.

        Args:
            deployment: Deployment dict.

        Returns:
            Updated deployment dict.
        """
        # In blue-green, we deploy to "green" environment
        # but don't switch traffic yet
        # Use CANARY as staging
        deployment["status"] = DeploymentStatus.CANARY.value
        deployment["current_percentage"] = 0  # No traffic yet
        deployment["green_model_path"] = deployment["model_path"]
        deployment["blue_model_path"] = deployment.get("baseline_model_path")
        deployment["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "blue_green_staging_started",
            extra={"deployment_id": deployment["id"]},
        )

        return deployment

    def switch_blue_green(self, deployment: Dict) -> Dict:
        """Switch traffic from blue to green.

        Args:
            deployment: Deployment dict.

        Returns:
            Updated deployment dict.
        """
        deployment["status"] = DeploymentStatus.ACTIVE.value
        deployment["current_percentage"] = 100
        deployment["switched_at"] = datetime.now(timezone.utc).isoformat()
        deployment["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "blue_green_switched",
            extra={
                "deployment_id": deployment["id"],
                "new_model": deployment["model_path"],
            },
        )

        return deployment

    # ══════════════════════════════════════════════════════════════════════════
    # Rolling Deployment
    # ══════════════════════════════════════════════════════════════════════════

    def _start_rolling_deployment(self, deployment: Dict) -> Dict:
        """Start rolling deployment.

        Args:
            deployment: Deployment dict.

        Returns:
            Updated deployment dict.
        """
        deployment["status"] = DeploymentStatus.ROLLING_OUT.value
        deployment["current_percentage"] = DEFAULT_ROLLOUT_INCREMENT
        deployment["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "rolling_deployment_started",
            extra={
                "deployment_id": deployment["id"],
                "initial_percentage": deployment["current_percentage"],
            },
        )

        return deployment

    # ══════════════════════════════════════════════════════════════════════════
    # Auto-Rollback
    # ══════════════════════════════════════════════════════════════════════════

    def trigger_rollback(
        self,
        deployment: Dict,
        reason: str,
        trigger_type: str = RollbackTrigger.MANUAL.value,
    ) -> Dict:
        """Trigger automatic rollback.

        Args:
            deployment: Deployment dict.
            reason: Reason for rollback.
            trigger_type: Type of trigger.

        Returns:
            Updated deployment dict.
        """
        deployment_id = deployment["id"]
        baseline_model = deployment.get("baseline_model_path")

        deployment["status"] = DeploymentStatus.ROLLING_BACK.value
        deployment["rollback_reason"] = reason
        deployment["rollback_trigger"] = trigger_type
        deployment["rollback_started_at"] = datetime.now(timezone.utc).isoformat()
        deployment["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.warning(
            "rollback_triggered",
            extra={
                "deployment_id": deployment_id,
                "reason": reason,
                "trigger_type": trigger_type,
                "baseline_model": baseline_model,
            },
        )

        # Perform rollback
        if baseline_model:
            deployment["model_path"] = baseline_model
            deployment["current_percentage"] = 100  # Back to baseline

        deployment["status"] = DeploymentStatus.ROLLED_BACK.value
        deployment["rollback_completed_at"] = datetime.now(timezone.utc).isoformat()
        deployment["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "rollback_completed",
            extra={
                "deployment_id": deployment_id,
                "restored_model": baseline_model,
            },
        )

        return deployment

    def check_and_auto_rollback(self, deployment: Dict) -> Dict:
        """Check deployment health and auto-rollback if needed.

        Args:
            deployment: Deployment dict.

        Returns:
            Dict with status.
        """
        if deployment.get("status") not in [
            DeploymentStatus.CANARY.value,
            DeploymentStatus.ROLLING_OUT.value,
        ]:
            return {"action": "none", "reason": "Not in deployable state"}

        # Check health
        health = self.check_canary_health(deployment)

        if not health["healthy"]:
            # Auto-rollback triggered
            triggers = health.get("triggers", [])
            primary_trigger = triggers[0] if triggers else {}

            updated_deployment = self.trigger_rollback(
                deployment=deployment,
                reason=f"Auto-rollback: {primary_trigger.get('type', 'unknown')}",
                trigger_type=primary_trigger.get(
                    "type", RollbackTrigger.ERROR_RATE.value
                ),
            )

            return {
                "action": "rollback",
                "reason": primary_trigger.get("type"),
                "triggers": triggers,
                "deployment": updated_deployment,
            }

        return {"action": "continue", "health": health}

    # ══════════════════════════════════════════════════════════════════════════
    # Monitoring
    # ══════════════════════════════════════════════════════════════════════════

    def _collect_deployment_metrics(self, deployment: Dict) -> Dict:
        """Collect deployment metrics for monitoring.

        Args:
            deployment: Deployment dict.

        Returns:
            Dict with metrics.
        """
        # Simulate metric collection
        # In production, this would query actual monitoring systems
        base_error_rate = 0.01
        base_latency = 200

        # Add some variance based on deployment status
        status = deployment.get("status", "pending")
        if status == DeploymentStatus.CANARY.value:
            # Canary might have slightly higher metrics
            error_rate = base_error_rate + 0.005
            latency_p95 = base_latency + 100
        elif status == DeploymentStatus.ROLLING_OUT.value:
            error_rate = base_error_rate + 0.003
            latency_p95 = base_latency + 50
        else:
            error_rate = base_error_rate
            latency_p95 = base_latency

        return {
            "error_rate": round(error_rate, 4),
            "latency_p50_ms": round(latency_p95 * 0.6, 0),
            "latency_p95_ms": round(latency_p95, 0),
            "latency_p99_ms": round(latency_p95 * 1.5, 0),
            "requests_per_minute": 100 + (deployment.get("current_percentage", 0) * 2),
            "accuracy": 0.87 + (deployment.get("current_percentage", 0) / 1000),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_deployment_status(self, deployment: Dict) -> Dict:
        """Get current deployment status.

        Args:
            deployment: Deployment dict.

        Returns:
            Dict with status info.
        """
        metrics = self._collect_deployment_metrics(deployment)

        return {
            "deployment_id": deployment.get("id"),
            "status": deployment.get("status"),
            "strategy": deployment.get("strategy"),
            "current_percentage": deployment.get("current_percentage", 0),
            "model_path": deployment.get("model_path"),
            "baseline_model_path": deployment.get("baseline_model_path"),
            "metrics": metrics,
            "created_at": deployment.get("created_at"),
            "updated_at": deployment.get("updated_at"),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Deployment Control
    # ══════════════════════════════════════════════════════════════════════════

    def pause_deployment(self, deployment: Dict) -> Dict:
        """Pause an active deployment.

        Args:
            deployment: Deployment dict.

        Returns:
            Updated deployment dict.
        """
        if deployment.get("status") not in [
            DeploymentStatus.CANARY.value,
            DeploymentStatus.ROLLING_OUT.value,
        ]:
            return deployment

        deployment["status"] = DeploymentStatus.PAUSED.value
        deployment["paused_at"] = datetime.now(timezone.utc).isoformat()
        deployment["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "deployment_paused",
            extra={
                "deployment_id": deployment["id"],
                "at_percentage": deployment.get("current_percentage"),
            },
        )

        return deployment

    def resume_deployment(self, deployment: Dict) -> Dict:
        """Resume a paused deployment.

        Args:
            deployment: Deployment dict.

        Returns:
            Updated deployment dict.
        """
        if deployment.get("status") != DeploymentStatus.PAUSED.value:
            return deployment

        # Resume at the same percentage
        deployment["status"] = DeploymentStatus.ROLLING_OUT.value
        deployment["resumed_at"] = datetime.now(timezone.utc).isoformat()
        deployment["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "deployment_resumed",
            extra={
                "deployment_id": deployment["id"],
                "at_percentage": deployment.get("current_percentage"),
            },
        )

        return deployment

    def cancel_deployment(
        self, deployment: Dict, reason: str = "Cancelled by user"
    ) -> Dict:
        """Cancel a deployment.

        Args:
            deployment: Deployment dict.
            reason: Cancellation reason.

        Returns:
            Updated deployment dict.
        """
        # If there's a baseline, rollback to it
        if deployment.get("baseline_model_path"):
            return self.trigger_rollback(
                deployment=deployment,
                reason=reason,
                trigger_type=RollbackTrigger.MANUAL.value,
            )

        deployment["status"] = DeploymentStatus.FAILED.value
        deployment["cancellation_reason"] = reason
        deployment["cancelled_at"] = datetime.now(timezone.utc).isoformat()
        deployment["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "deployment_cancelled",
            extra={
                "deployment_id": deployment["id"],
                "reason": reason,
            },
        )

        return deployment
