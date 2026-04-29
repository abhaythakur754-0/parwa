"""
Agent Training Service — F-100 Lightning Training Loop

Orchestrates the full training lifecycle:
1. Dataset preparation and validation
2. Training run initialization
3. Progress monitoring
4. Checkpoint management
5. Result aggregation
6. Auto-deployment trigger

# TODO (Day 6 — I5): Training data operations MUST enforce tenant isolation.
# While all SQL queries in this service filter by company_id, the Celery
# training task (execute_training_run) runs in a background worker and must
# re-validate company_id before accessing any training data.  Ensure the
# training worker picks up company_id from the Celery task context and
# passes it to every DB query.  Training datasets should NEVER be shared
# across companies without explicit shared-variant scoping (see
# TrainingDataIsolationService in services/training_data_isolation.py).

Building Codes:
- BC-001: Multi-tenant isolation (all queries scoped by company_id)
- BC-004: Background Jobs (Celery tasks for long-running training)
- BC-007: AI Model Interaction (Smart Router integration)
- BC-012: Error handling (structured errors, DLQ for failures)
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict
from decimal import Decimal

from sqlalchemy.orm import Session

logger = logging.getLogger("parwa.agent_training")

# ── Constants ───────────────────────────────────────────────────────────────

# Training status values
TRAINING_STATUS_QUEUED = "queued"
TRAINING_STATUS_INITIALIZING = "initializing"
TRAINING_STATUS_RUNNING = "running"
TRAINING_STATUS_COMPLETED = "completed"
TRAINING_STATUS_FAILED = "failed"
TRAINING_STATUS_CANCELLED = "cancelled"

# Trigger types
TRIGGER_MANUAL = "manual"
TRIGGER_AUTO_THRESHOLD = "auto_threshold"  # F-101
TRIGGER_SCHEDULED = "scheduled"  # F-106
TRIGGER_COLD_START = "cold_start"  # F-107

# Default training hyperparameters
DEFAULT_EPOCHS = 3
DEFAULT_LEARNING_RATE = 0.0001
DEFAULT_BATCH_SIZE = 16

# Minimum samples for training
MIN_SAMPLES_FOR_TRAINING = 50

# Estimated time per epoch (minutes)
ESTIMATED_MINUTES_PER_EPOCH = 10


class AgentTrainingService:
    """Service for managing the Agent Lightning Training Loop (F-100).

    This service handles:
    - Creating and managing training runs
    - Tracking training progress
    - Managing checkpoints
    - Coordinating with external GPU providers (Colab/RunPod)

    Usage:
        service = AgentTrainingService(db)
        run = service.create_training_run(company_id, agent_id, dataset_id)
        service.update_progress(run_id, epoch, progress_pct, metrics)
    """

    def __init__(self, db: Session):
        self.db = db

    # ══════════════════════════════════════════════════════════════════════════
    # Training Run CRUD
    # ══════════════════════════════════════════════════════════════════════════

    def create_training_run(
        self,
        company_id: str,
        agent_id: str,
        dataset_id: str,
        name: Optional[str] = None,
        trigger: str = TRIGGER_MANUAL,
        base_model: Optional[str] = None,
        epochs: int = DEFAULT_EPOCHS,
        learning_rate: float = DEFAULT_LEARNING_RATE,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> Dict:
        """Create a new training run.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent to train.
            dataset_id: Dataset to use for training.
            name: Optional run name.
            trigger: Trigger type (manual/auto_threshold/scheduled/cold_start).
            base_model: Base model identifier.
            epochs: Number of training epochs.
            learning_rate: Learning rate for optimizer.
            batch_size: Batch size for training.

        Returns:
            Dict with run_id, status, and estimated completion time.
        """
        from database.models.training import TrainingRun, TrainingDataset

        # Validate dataset exists and has enough samples
        dataset = (
            self.db.query(TrainingDataset)
            .filter(
                TrainingDataset.company_id == company_id,
                TrainingDataset.id == dataset_id,
            )
            .first()
        )
        if not dataset:
            return {
                "status": "error",
                "error": f"Dataset {dataset_id} not found",
            }

        if (dataset.record_count or 0) < MIN_SAMPLES_FOR_TRAINING:
            return {
                "status": "error",
                "error": f"Dataset has only {
                    dataset.record_count} samples. Minimum {MIN_SAMPLES_FOR_TRAINING} required.",
            }

        # Check agent isn't already training
        existing_run = (
            self.db.query(TrainingRun)
            .filter(
                TrainingRun.company_id == company_id,
                TrainingRun.agent_id == agent_id,
                TrainingRun.status.in_([
                    TRAINING_STATUS_QUEUED,
                    TRAINING_STATUS_INITIALIZING,
                    TRAINING_STATUS_RUNNING,
                ]),
            )
            .first()
        )
        if existing_run:
            return {
                "status": "error",
                "error": f"Agent already has an active training run: {
                    existing_run.id}",
                "existing_run_id": str(
                    existing_run.id),
            }

        # Create training run
        run = TrainingRun(
            company_id=company_id,
            agent_id=agent_id,
            dataset_id=dataset_id,
            name=name or f"Training run for agent {agent_id[:8]}",
            trigger=trigger,
            base_model=base_model or "parwa-base-v1",
            epochs=epochs,
            learning_rate=learning_rate,
            batch_size=batch_size,
            status=TRAINING_STATUS_QUEUED,
            total_epochs=epochs,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        # Update dataset status
        dataset.status = "in_use"
        self.db.commit()

        # Queue the training task
        self._queue_training_task(company_id, str(run.id))

        logger.info(
            "training_run_created",
            extra={
                "company_id": company_id,
                "agent_id": agent_id,
                "run_id": str(run.id),
                "trigger": trigger,
                "epochs": epochs,
            },
        )

        estimated_minutes = epochs * ESTIMATED_MINUTES_PER_EPOCH

        return {
            "status": "created",
            "run_id": str(run.id),
            "agent_id": agent_id,
            "dataset_id": dataset_id,
            "trigger": trigger,
            "epochs": epochs,
            "estimated_completion_minutes": estimated_minutes,
        }

    def get_training_run(self, company_id: str, run_id: str) -> Optional[Dict]:
        """Get training run details.

        Args:
            company_id: Tenant company ID.
            run_id: Training run ID.

        Returns:
            Dict with run details or None if not found.
        """
        from database.models.training import TrainingRun

        run = (
            self.db.query(TrainingRun)
            .filter(
                TrainingRun.company_id == company_id,
                TrainingRun.id == run_id,
            )
            .first()
        )

        if not run:
            return None

        return self._run_to_dict(run)

    def list_training_runs(
        self,
        company_id: str,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict:
        """List training runs for a tenant.

        Args:
            company_id: Tenant company ID.
            agent_id: Optional filter by agent.
            status: Optional filter by status.
            limit: Max results to return.
            offset: Offset for pagination.

        Returns:
            Dict with runs list and total count.
        """
        from database.models.training import TrainingRun

        query = (
            self.db.query(TrainingRun)
            .filter(TrainingRun.company_id == company_id)
        )

        if agent_id:
            query = query.filter(TrainingRun.agent_id == agent_id)
        if status:
            query = query.filter(TrainingRun.status == status)

        total = query.count()
        runs = (
            query
            .order_by(TrainingRun.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "runs": [self._run_to_dict(r) for r in runs],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def update_progress(
        self,
        company_id: str,
        run_id: str,
        epoch: int,
        progress_pct: float,
        metrics: Optional[Dict] = None,
    ) -> Dict:
        """Update training run progress.

        Called by the training worker during training.

        Args:
            company_id: Tenant company ID.
            run_id: Training run ID.
            epoch: Current epoch number.
            progress_pct: Progress percentage (0-100).
            metrics: Optional metrics dict (loss, accuracy, etc.).

        Returns:
            Dict with status.
        """
        from database.models.training import TrainingRun

        run = (
            self.db.query(TrainingRun)
            .filter(
                TrainingRun.company_id == company_id,
                TrainingRun.id == run_id,
            )
            .first()
        )

        if not run:
            return {"status": "error", "error": "Run not found"}

        run.current_epoch = epoch
        run.progress_pct = progress_pct
        run.status = TRAINING_STATUS_RUNNING

        if metrics:
            existing_metrics = run.metrics or {}
            existing_metrics.update(metrics)
            run.metrics = existing_metrics

        self.db.commit()

        logger.info(
            "training_progress_updated",
            extra={
                "company_id": company_id,
                "run_id": run_id,
                "epoch": epoch,
                "progress_pct": progress_pct,
            },
        )

        return {"status": "updated", "run_id": run_id}

    def complete_training_run(
        self,
        company_id: str,
        run_id: str,
        model_path: Optional[str] = None,
        final_metrics: Optional[Dict] = None,
        cost_usd: Optional[float] = None,
    ) -> Dict:
        """Mark a training run as completed.

        Args:
            company_id: Tenant company ID.
            run_id: Training run ID.
            model_path: Path to the trained model.
            final_metrics: Final training metrics.
            cost_usd: Total GPU cost.

        Returns:
            Dict with status and next steps.
        """
        from database.models.training import TrainingRun

        run = (
            self.db.query(TrainingRun)
            .filter(
                TrainingRun.company_id == company_id,
                TrainingRun.id == run_id,
            )
            .first()
        )

        if not run:
            return {"status": "error", "error": "Run not found"}

        run.status = TRAINING_STATUS_COMPLETED
        run.progress_pct = 100
        run.completed_at = datetime.now(timezone.utc)
        run.model_path = model_path

        if final_metrics:
            existing_metrics = run.metrics or {}
            existing_metrics.update(final_metrics)
            run.metrics = existing_metrics

        if cost_usd is not None:
            run.cost_usd = Decimal(str(cost_usd))

        self.db.commit()

        logger.info(
            "training_run_completed",
            extra={
                "company_id": company_id,
                "run_id": run_id,
                "model_path": model_path,
                "cost_usd": str(run.cost_usd),
            },
        )

        return {
            "status": "completed",
            "run_id": run_id,
            "model_path": model_path,
            "next_step": "validation_required",  # F-104
        }

    def fail_training_run(
        self,
        company_id: str,
        run_id: str,
        error_message: str,
    ) -> Dict:
        """Mark a training run as failed.

        Args:
            company_id: Tenant company ID.
            run_id: Training run ID.
            error_message: Error description.

        Returns:
            Dict with status.
        """
        from database.models.training import TrainingRun

        run = (
            self.db.query(TrainingRun)
            .filter(
                TrainingRun.company_id == company_id,
                TrainingRun.id == run_id,
            )
            .first()
        )

        if not run:
            return {"status": "error", "error": "Run not found"}

        run.status = TRAINING_STATUS_FAILED
        run.error_message = error_message
        run.completed_at = datetime.now(timezone.utc)

        self.db.commit()

        logger.error(
            "training_run_failed",
            extra={
                "company_id": company_id,
                "run_id": run_id,
                "error_message": error_message[:500],
            },
        )

        return {"status": "failed", "run_id": run_id}

    def cancel_training_run(self, company_id: str, run_id: str) -> Dict:
        """Cancel a training run.

        Args:
            company_id: Tenant company ID.
            run_id: Training run ID.

        Returns:
            Dict with status.
        """
        from database.models.training import TrainingRun

        run = (
            self.db.query(TrainingRun)
            .filter(
                TrainingRun.company_id == company_id,
                TrainingRun.id == run_id,
            )
            .first()
        )

        if not run:
            return {"status": "error", "error": "Run not found"}

        if run.status not in [
                TRAINING_STATUS_COMPLETED,
                TRAINING_STATUS_FAILED,
                TRAINING_STATUS_CANCELLED]:
            return {
                "status": "error",
                "error": f"Cannot cancel run with status: {run.status}",
            }

        run.status = TRAINING_STATUS_CANCELLED
        run.completed_at = datetime.now(timezone.utc)

        self.db.commit()

        logger.info(
            "training_run_cancelled",
            extra={
                "company_id": company_id,
                "run_id": run_id,
            },
        )

        return {"status": "cancelled", "run_id": run_id}

    # ══════════════════════════════════════════════════════════════════════════
    # Checkpoint Management
    # ══════════════════════════════════════════════════════════════════════════

    def create_checkpoint(
        self,
        company_id: str,
        run_id: str,
        epoch: int,
        checkpoint_name: str,
        model_path: Optional[str] = None,
        s3_path: Optional[str] = None,
        metrics: Optional[Dict] = None,
        is_best: bool = False,
    ) -> Dict:
        """Create a training checkpoint.

        Args:
            company_id: Tenant company ID.
            run_id: Training run ID.
            epoch: Epoch number.
            checkpoint_name: Name for the checkpoint.
            model_path: Local path to checkpoint.
            s3_path: S3 path to checkpoint.
            metrics: Checkpoint metrics.
            is_best: Whether this is the best checkpoint so far.

        Returns:
            Dict with checkpoint_id.
        """
        from database.models.training import TrainingCheckpoint, TrainingRun

        # Verify run exists
        run = (
            self.db.query(TrainingRun)
            .filter(
                TrainingRun.company_id == company_id,
                TrainingRun.id == run_id,
            )
            .first()
        )
        if not run:
            return {"status": "error", "error": "Run not found"}

        # If this is the best, unmark previous best
        if is_best:
            self.db.query(TrainingCheckpoint).filter(
                TrainingCheckpoint.company_id == company_id,
                TrainingCheckpoint.training_run_id == run_id,
                TrainingCheckpoint.is_best,
            ).update({"is_best": False})

        checkpoint = TrainingCheckpoint(
            company_id=company_id,
            training_run_id=run_id,
            checkpoint_name=checkpoint_name,
            model_path=model_path,
            s3_path=s3_path,
            epoch=epoch,
            metrics=metrics or {},
            is_best=is_best,
        )
        if metrics:
            checkpoint.loss = metrics.get("loss")
            checkpoint.accuracy = metrics.get("accuracy")

        self.db.add(checkpoint)
        self.db.commit()
        self.db.refresh(checkpoint)

        logger.info(
            "training_checkpoint_created",
            extra={
                "company_id": company_id,
                "run_id": run_id,
                "checkpoint_id": str(checkpoint.id),
                "epoch": epoch,
                "is_best": is_best,
            },
        )

        return {
            "status": "created",
            "checkpoint_id": str(checkpoint.id),
            "is_best": is_best,
        }

    def get_best_checkpoint(
            self,
            company_id: str,
            run_id: str) -> Optional[Dict]:
        """Get the best checkpoint for a training run.

        Args:
            company_id: Tenant company ID.
            run_id: Training run ID.

        Returns:
            Dict with checkpoint details or None.
        """
        from database.models.training import TrainingCheckpoint

        checkpoint = (
            self.db.query(TrainingCheckpoint)
            .filter(
                TrainingCheckpoint.company_id == company_id,
                TrainingCheckpoint.training_run_id == run_id,
                TrainingCheckpoint.is_best,
            )
            .first()
        )

        if not checkpoint:
            return None

        return {
            "checkpoint_id": str(
                checkpoint.id),
            "checkpoint_name": checkpoint.checkpoint_name,
            "model_path": checkpoint.model_path,
            "s3_path": checkpoint.s3_path,
            "epoch": checkpoint.epoch,
            "metrics": checkpoint.metrics,
            "created_at": checkpoint.created_at.isoformat() if checkpoint.created_at else None,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Statistics
    # ══════════════════════════════════════════════════════════════════════════

    def get_training_stats(
            self,
            company_id: str,
            agent_id: Optional[str] = None) -> Dict:
        """Get training statistics for a tenant or agent.

        Args:
            company_id: Tenant company ID.
            agent_id: Optional agent filter.

        Returns:
            Dict with training statistics.
        """
        from database.models.training import TrainingRun

        query = (
            self.db.query(TrainingRun)
            .filter(TrainingRun.company_id == company_id)
        )
        if agent_id:
            query = query.filter(TrainingRun.agent_id == agent_id)

        runs = query.all()

        total_runs = len(runs)
        completed = len([r for r in runs if r.status ==
                        TRAINING_STATUS_COMPLETED])
        failed = len([r for r in runs if r.status == TRAINING_STATUS_FAILED])
        running = len([r for r in runs if r.status == TRAINING_STATUS_RUNNING])
        queued = len([r for r in runs if r.status == TRAINING_STATUS_QUEUED])

        total_cost = sum(float(r.cost_usd or 0) for r in runs)

        triggers = {}
        for run in runs:
            t = run.trigger or TRIGGER_MANUAL
            triggers[t] = triggers.get(t, 0) + 1

        return {
            "total_runs": total_runs,
            "completed": completed,
            "failed": failed,
            "running": running,
            "queued": queued,
            "total_cost_usd": round(total_cost, 2),
            "by_trigger": triggers,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Private Methods
    # ══════════════════════════════════════════════════════════════════════════

    def _queue_training_task(self, company_id: str, run_id: str) -> None:
        """Queue the Celery training task.

        Args:
            company_id: Tenant company ID.
            run_id: Training run ID.
        """
        try:
            from app.tasks.training_tasks import execute_training_run

            execute_training_run.delay(company_id, run_id)
            logger.info(
                "training_task_queued",
                extra={"company_id": company_id, "run_id": run_id},
            )
        except Exception as exc:
            logger.error(
                "training_task_queue_failed",
                extra={
                    "company_id": company_id,
                    "run_id": run_id,
                    "error": str(exc)[:200],
                },
            )

    @staticmethod
    def _run_to_dict(run) -> Dict:
        """Convert a TrainingRun to a dictionary."""
        return {
            "id": str(run.id),
            "company_id": str(run.company_id),
            "agent_id": str(run.agent_id),
            "dataset_id": str(run.dataset_id) if run.dataset_id else None,
            "name": run.name,
            "trigger": run.trigger,
            "base_model": run.base_model,
            "status": run.status,
            "progress_pct": run.progress_pct,
            "current_epoch": run.current_epoch,
            "total_epochs": run.total_epochs,
            "epochs": run.epochs,
            "learning_rate": float(run.learning_rate) if run.learning_rate else None,
            "batch_size": run.batch_size,
            "metrics": run.metrics or {},
            "model_path": run.model_path,
            "checkpoint_path": run.checkpoint_path,
            "provider": run.provider,
            "instance_id": run.instance_id,
            "gpu_type": run.gpu_type,
            "cost_usd": float(run.cost_usd) if run.cost_usd else 0.0,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "error_message": run.error_message,
        }
