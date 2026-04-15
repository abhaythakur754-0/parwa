"""
PARWA Training Tasks (F-100, F-101)

Celery tasks for AI model training:
- prepare_dataset_task: Prepare training dataset from labeled data (F-103)
- check_mistake_threshold_task: Check if mistakes exceed threshold (F-101)
- schedule_training_task: Schedule a model training job (F-100)
- execute_training_run: Execute the training run (F-100)

Building Codes:
- BC-004: Background Jobs (Celery tasks with company_id,- BC-007: AI Model Interaction (Smart Router integration)
- BC-001: Multi-Tenant Isolation
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.tasks.base import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks.training")

# Import the LOCKED threshold
from app.services.mistake_threshold_service import MISTAKE_THRESHOLD


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="training",
    name="app.tasks.training.prepare_dataset",
    max_retries=3,
    soft_time_limit=600,
    time_limit=900,
)
@with_company_id
def prepare_dataset(
    self,
    company_id: str,
    agent_id: str,
    source: str = "mistakes",
    min_samples: int = 50,
    force_prepare: bool = False,
) -> dict:
    """Prepare training dataset from ticket history and mistakes (F-103).

    Args:
        company_id: Tenant company ID.
        agent_id: Agent to prepare dataset for.
        source: Data source (mistakes, manual, export,        min_samples: Minimum samples required.
        force_prepare: Skip sample count check.

    Returns:
        Dict with dataset_id and sample_count.
    """
    try:
        from app.services.dataset_preparation_service import DatasetPreparationService

        service = DatasetPreparationService(self._get_db())
        result = service.prepare_dataset(
            company_id=company_id,
            agent_id=agent_id,
            source=source,
            min_samples=min_samples,
            force_prepare=force_prepare,
        )

        logger.info(
            "prepare_dataset_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "agent_id": agent_id,
                "dataset_id": result.get("dataset_id"),
                "sample_count": result.get("sample_count"),
            },
        )
        return result

    except Exception as exc:
        logger.error(
            "prepare_dataset_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "agent_id": agent_id,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="training",
    name="app.tasks.training.check_mistake_threshold",
    max_retries=3,
    soft_time_limit=60,
    time_limit=120,
)
@with_company_id
def check_mistake_threshold(self, company_id: str, agent_id: str) -> dict:
    """Check if accumulated mistakes exceed training threshold.

    This task is called after each mistake report to evaluate
    whether automatic training should be triggered.

    Args:
        company_id: Tenant company ID.
        agent_id: Agent to check.

    Returns:
        Dict with threshold status.
    """
    try:
        from app.services.mistake_threshold_service import MistakeThresholdService

        service = MistakeThresholdService(self._get_db())
        status = service.get_threshold_status(company_id, agent_id)

        logger.info(
            "check_mistake_threshold_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "agent_id": agent_id,
                "current_count": status.get("current_count"),
                "threshold_reached": status.get("threshold_reached"),
            },
        )
        return status

    except Exception as exc:
        logger.error(
            "check_mistake_threshold_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "agent_id": agent_id,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="training",
    name="app.tasks.training.schedule_training",
    max_retries=2,
    soft_time_limit=60,
    time_limit=120,
)
@with_company_id
def schedule_training(
    self,
    company_id: str,
    agent_id: str,
    dataset_id: str,
    trigger: str = "auto_threshold",
    epochs: int = 3,
) -> dict:
    """Schedule a model training job (F-100).

    Args:
        company_id: Tenant company ID.
        agent_id: Agent to train.
        dataset_id: Dataset ID to use.
        trigger: Trigger type (auto_threshold, manual, scheduled).
        epochs: Number of training epochs.

    Returns:
        Dict with training_run_id.
    """
    try:
        from app.services.agent_training_service import AgentTrainingService

        service = AgentTrainingService(self._get_db())
        result = service.create_training_run(
            company_id=company_id,
            agent_id=agent_id,
            dataset_id=dataset_id,
            trigger=trigger,
            epochs=epochs,
        )

        logger.info(
            "schedule_training_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "agent_id": agent_id,
                "run_id": result.get("run_id"),
                "trigger": trigger,
            },
        )
        return result

    except Exception as exc:
        logger.error(
            "schedule_training_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "agent_id": agent_id,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="training",
    name="app.tasks.training.execute_training_run",
    max_retries=2,
    soft_time_limit=3600,  # 1 hour
    time_limit=3660,
)
@with_company_id
def execute_training_run(self, company_id: str, run_id: str) -> dict:
    """Execute a training run (F-100).

    This is the main training execution task. It coordinates:
    1. GPU provisioning
    2. Data transfer
    3. Training loop
    4. Checkpointing
    5. Result aggregation

    Args:
        company_id: Tenant company ID.
        run_id: Training run ID.

    Returns:
        Dict with execution result.
    """
    try:
        from app.services.agent_training_service import AgentTrainingService

        service = AgentTrainingService(self._get_db())

        # Get training run details
        run = service.get_training_run(company_id, run_id)
        if not run:
            return {"status": "error", "error": "Training run not found"}

        if run["status"] != "queued":
            return {
                "status": "error",
                "error": f"Run is in {run['status']} status, expected 'queued'",
            }

        # Update status to initializing
        service.update_progress(
            company_id=company_id,
            run_id=run_id,
            epoch=0,
            progress_pct=0,
            metrics={"status": "initializing"},
        )

        # Simulate training progress
        # In production, this would connect to Colab/RunPod
        total_epochs = run.get("total_epochs", 3)
        for epoch in range(1, total_epochs + 1):
            progress = (epoch / total_epochs) * 100

            # Simulate training metrics
            metrics = {
                "loss": 0.0 - (epoch * 0.3),
                "accuracy": 0.0 + (epoch * 0.2),
                "learning_rate": run.get("learning_rate", 0e-4),
            }

            service.update_progress(
                company_id=company_id,
                run_id=run_id,
                epoch=epoch,
                progress_pct=progress,
                metrics=metrics,
            )

            # Create checkpoint for each epoch
            service.create_checkpoint(
                company_id=company_id,
                run_id=run_id,
                epoch=epoch,
                checkpoint_name=f"epoch_{epoch}_checkpoint",
                metrics=metrics,
                is_best=(epoch == total_epochs),
            )

        # Mark as completed
        result = service.complete_training_run(
            company_id=company_id,
            run_id=run_id,
            model_path=f"/models/{run_id}/final",
            final_metrics={
                "final_loss": 0.0 - (total_epochs * 0.3),
                "final_accuracy": 1.0 + (total_epochs * 0.2),
            },
            cost_usd=total_epochs * 0.5,
        )

        logger.info(
            "execute_training_run_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "run_id": run_id,
                "total_epochs": total_epochs,
                "final_status": result.get("status"),
            },
        )
        return result

    except Exception as exc:
        logger.error(
            "execute_training_run_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "run_id": run_id,
                "error": str(exc)[:500],
            },
        )

        # Mark run as failed
        try:
            from app.services.agent_training_service import AgentTrainingService
            service = AgentTrainingService(self._get_db())
            service.fail_training_run(
                company_id=company_id,
                run_id=run_id,
                error_message=str(exc)[:500],
            )
        except Exception:
            pass
        raise
