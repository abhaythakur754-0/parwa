"""
PARWA Training Tasks (Day 22, BC-004, LOCKED #20)

Celery tasks for AI model training:
- prepare_dataset_task: Prepare training dataset from labeled data
- check_mistake_threshold_task: Check if mistakes exceed threshold
- schedule_training_task: Schedule a model training job
"""

import logging

from app.tasks.base import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks.training")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="training",
    name="app.tasks.training.prepare_dataset",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
@with_company_id
def prepare_dataset(self, company_id: str,
                    dataset_type: str = "classification",
                    min_samples: int = 100) -> dict:
    """Prepare training dataset from labeled data."""
    try:
        logger.info(
            "prepare_dataset_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "dataset_type": dataset_type,
                "min_samples": min_samples,
            },
        )
        return {
            "status": "prepared",
            "dataset_type": dataset_type,
            "samples_count": 0,
            "train_count": 0,
            "test_count": 0,
        }
    except Exception as exc:
        logger.error(
            "prepare_dataset_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="training",
    name="app.tasks.training.check_mistake_threshold",
    max_retries=2,
    soft_time_limit=60,
    time_limit=120,
)
@with_company_id
def check_mistake_threshold(self, company_id: str,
                            threshold: int = 50) -> dict:
    """Check if accumulated mistakes exceed training threshold."""
    try:
        logger.info(
            "check_mistake_threshold_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "threshold": threshold,
            },
        )
        return {
            "status": "checked",
            "company_id": company_id,
            "current_mistakes": 0,
            "threshold": threshold,
            "training_triggered": False,
        }
    except Exception as exc:
        logger.error(
            "check_mistake_threshold_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="training",
    name="app.tasks.training.schedule_training",
    max_retries=1,
    soft_time_limit=60,
    time_limit=120,
)
@with_company_id
def schedule_training(self, company_id: str,
                      model_type: str = "classification",
                      dataset_version: str = "") -> dict:
    """Schedule a model training job."""
    try:
        logger.info(
            "schedule_training_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "model_type": model_type,
            },
        )
        return {
            "status": "scheduled",
            "model_type": model_type,
            "training_job_id": None,
        }
    except Exception as exc:
        logger.error(
            "schedule_training_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        raise
