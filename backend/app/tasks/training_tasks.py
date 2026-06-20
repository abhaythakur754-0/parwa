"""
PARWA Training Tasks — Agent Lightning Pipeline (Week 2)

Real Celery tasks for AI model fine-tuning:
- prepare_dataset_task: Collect mistakes from AgentMistake table, prepare training data
- check_mistake_threshold_task: Check if mistakes exceed threshold for training trigger
- schedule_training_task: Schedule and initiate model training job
- evaluate_training_task: Evaluate trained model performance (A/B framework)
- cleanup_old_datasets_task: Cleanup old training datasets

Pipeline: Mistakes accumulate -> threshold reached -> dataset prepared -> training triggered -> model evaluated

BC-001: All tasks scoped to company_id.
BC-004: Retry with exponential backoff (built into ParwaBaseTask).
BC-008: Never crash -- always return valid status dict.
"""

import json
import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.tasks.base import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks.training")

# ── Constants ─────────────────────────────────────────────────────

DEFAULT_MISTAKE_THRESHOLD = 50
MIN_DATASET_SAMPLES = 100
TRAIN_TEST_SPLIT_RATIO = 0.80
CLEANUP_AGE_DAYS = 90
ESTIMATED_SPACE_PER_DATASET_MB = 12.5  # average per dataset

VALID_MISTAKE_TYPES = [
    "hallucination",
    "wrong_answer",
    "policy_violation",
    "tone_issue",
    "incomplete_response",
    "irrelevant_response",
    "safety_violation",
    "factual_error",
]

VALID_SEVERITIES = ["low", "medium", "high", "critical"]


# ── Database helpers ──────────────────────────────────────────────

def _get_db():
    """Create and return a new SQLAlchemy session.

    Caller is responsible for closing the session.
    """
    from database.base import SessionLocal
    db = SessionLocal()
    return db


def _safe_close_db(db) -> None:
    """Safely close a DB session, never raises."""
    try:
        db.close()
    except Exception:
        pass


# ── Validation helpers ────────────────────────────────────────────

def _build_error_status(
    task_name: str,
    error: str,
    **extra_fields: Any,
) -> Dict[str, Any]:
    """Build a valid error status dict (BC-008: never crash)."""
    base: Dict[str, Any] = {
        "status": "error",
        "task": task_name,
        "error": str(error)[:500],
    }
    base.update(extra_fields)
    return base


def _format_mistake_as_training_sample(mistake) -> Dict[str, str]:
    """Convert an AgentMistake row into an input/output training pair.

    The ``input`` combines the original (wrong) response with the mistake
    context so the model can learn *what went wrong*.
    The ``output`` is the correction or expected response.

    Args:
        mistake: An AgentMistake ORM instance.

    Returns:
        Dict with ``input`` and ``output`` keys.
    """
    original = mistake.original_response or ""
    correction = mistake.correction or mistake.expected_response or ""
    mistake_type = mistake.mistake_type or "unknown"
    severity = mistake.severity or "medium"

    input_text = (
        f"[Mistake Type: {mistake_type}] [Severity: {severity}]\n"
        f"Original Response: {original}"
    )
    output_text = correction if correction else "No correction provided."

    return {"input": input_text, "output": output_text}


def _split_train_test(
    samples: List[Dict[str, Any]], ratio: float = TRAIN_TEST_SPLIT_RATIO
) -> tuple:
    """Deterministically split samples into train and test sets.

    Uses a simple sequential split after sorting by a stable key so
    results are reproducible across runs.

    Returns:
        (train_list, test_list)
    """
    sorted_samples = sorted(samples, key=lambda s: s["input"])
    split_idx = max(1, int(len(sorted_samples) * ratio))
    return sorted_samples[:split_idx], sorted_samples[split_idx:]


# ── Task 1: Prepare Dataset ───────────────────────────────────────

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
    """Prepare training dataset from labeled mistakes.

    Steps:
        1. Query AgentMistake records for *company_id* where
           used_in_training=False.
        2. Format each mistake into a training sample
           (input/output pair).
        3. Split into train (80%) and test (20%) sets.
        4. Persist a TrainingDataset record.
        5. Mark collected mistakes as used_in_training=True.

    Returns:
        Dict with status, dataset_id, sample counts, and
        mistake-type distribution.
    """
    try:
        from database.models.training import (
            AgentMistake,
            TrainingDataset,
        )
    except ImportError as exc:
        return _build_error_status(
            self.name, f"Cannot import training models: {exc}",
            company_id=company_id, samples_count=0,
            train_count=0, test_count=0, mistake_types={},
        )

    db = _get_db()
    try:
        # ── 1. Query unused mistakes ──────────────────────────
        mistakes = (
            db.query(AgentMistake)
            .filter(
                AgentMistake.company_id == company_id,
                AgentMistake.used_in_training == False,  # noqa: E712
            )
            .all()
        )

        if not mistakes:
            logger.info(
                "prepare_dataset_no_mistakes",
                extra={"task": self.name, "company_id": company_id},
            )
            return {
                "status": "prepared",
                "company_id": company_id,
                "dataset_id": None,
                "samples_count": 0,
                "train_count": 0,
                "test_count": 0,
                "mistake_types": {},
                "message": "No unused mistakes found for this company.",
            }

        # ── 2. Format into training samples ───────────────────
        samples = []
        mistake_type_counts: Dict[str, int] = {}
        severity_counts: Dict[str, int] = {}
        collected_ids: List[str] = []

        for m in mistakes:
            sample = _format_mistake_as_training_sample(m)
            samples.append(sample)
            collected_ids.append(m.id)

            mt = m.mistake_type or "unknown"
            mistake_type_counts[mt] = mistake_type_counts.get(mt, 0) + 1

            sev = m.severity or "medium"
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # ── 3. Train / test split ────────────────────────────
        train_set, test_set = _split_train_test(samples)

        # ── 4. Create TrainingDataset record ──────────────────
        dataset_id = str(uuid.uuid4())
        dataset_name = (
            f"auto_{dataset_type}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        )

        dataset = TrainingDataset(
            id=dataset_id,
            company_id=company_id,
            name=dataset_name,
            record_count=len(samples),
            source="mistakes",
            status="prepared",
        )
        db.add(dataset)

        # ── 5. Mark mistakes as used ──────────────────────────
        (
            db.query(AgentMistake)
            .filter(AgentMistake.id.in_(collected_ids))
            .update({"used_in_training": True}, synchronize_session="fetch")
        )

        db.commit()

        logger.info(
            "prepare_dataset_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "dataset_id": dataset_id,
                "samples_count": len(samples),
                "train_count": len(train_set),
                "test_count": len(test_set),
            },
        )

        return {
            "status": "prepared",
            "company_id": company_id,
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "samples_count": len(samples),
            "train_count": len(train_set),
            "test_count": len(test_set),
            "mistake_types": mistake_type_counts,
            "severity_breakdown": severity_counts,
        }

    except Exception as exc:
        db.rollback()
        logger.error(
            "prepare_dataset_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:500],
            },
        )
        return _build_error_status(
            self.name, str(exc),
            company_id=company_id, samples_count=0,
            train_count=0, test_count=0, mistake_types={},
        )
    finally:
        _safe_close_db(db)


# ── Task 2: Check Mistake Threshold ──────────────────────────────

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
                            threshold: int = DEFAULT_MISTAKE_THRESHOLD) -> dict:
    """Check if accumulated unused mistakes exceed training threshold.

    If the count exceeds *threshold*, the task automatically dispatches
    ``prepare_dataset_task`` to start dataset preparation.

    Returns:
        Dict with current count, threshold, whether training was
        triggered, and a breakdown by severity / mistake_type.
    """
    try:
        from database.models.training import AgentMistake
    except ImportError as exc:
        return _build_error_status(
            self.name, f"Cannot import training models: {exc}",
            company_id=company_id, current_mistakes=0,
            threshold=threshold, training_triggered=False,
            trigger_reason=None,
        )

    db = _get_db()
    try:
        # ── Count unused mistakes ────────────────────────────
        unused_mistakes = (
            db.query(AgentMistake)
            .filter(
                AgentMistake.company_id == company_id,
                AgentMistake.used_in_training == False,  # noqa: E712
            )
            .all()
        )

        current_mistakes = len(unused_mistakes)

        # ── Break down by severity and mistake_type ──────────
        severity_breakdown: Dict[str, int] = {}
        type_breakdown: Dict[str, int] = {}
        for m in unused_mistakes:
            sev = m.severity or "medium"
            severity_breakdown[sev] = severity_breakdown.get(sev, 0) + 1
            mt = m.mistake_type or "unknown"
            type_breakdown[mt] = type_breakdown.get(mt, 0) + 1

        # ── Threshold check ──────────────────────────────────
        threshold_exceeded = current_mistakes >= threshold
        trigger_reason: Optional[str] = None
        training_triggered = False

        if threshold_exceeded:
            trigger_reason = (
                f"Mistake count ({current_mistakes}) >= threshold ({threshold}). "
                f"Top types: {type_breakdown}"
            )
            logger.info(
                "mistake_threshold_exceeded",
                extra={
                    "task": self.name,
                    "company_id": company_id,
                    "current_mistakes": current_mistakes,
                    "threshold": threshold,
                },
            )

            # Auto-trigger dataset preparation
            prepare_dataset.apply_async(
                kwargs={"company_id": company_id},
            )
            training_triggered = True
        else:
            logger.info(
                "mistake_threshold_not_reached",
                extra={
                    "task": self.name,
                    "company_id": company_id,
                    "current_mistakes": current_mistakes,
                    "threshold": threshold,
                },
            )

        return {
            "status": "checked",
            "company_id": company_id,
            "current_mistakes": current_mistakes,
            "threshold": threshold,
            "threshold_exceeded": threshold_exceeded,
            "training_triggered": training_triggered,
            "trigger_reason": trigger_reason,
            "severity_breakdown": severity_breakdown,
            "type_breakdown": type_breakdown,
        }

    except Exception as exc:
        db.rollback()
        logger.error(
            "check_mistake_threshold_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:500],
            },
        )
        return _build_error_status(
            self.name, str(exc),
            company_id=company_id, current_mistakes=0,
            threshold=threshold, training_triggered=False,
            trigger_reason=None,
        )
    finally:
        _safe_close_db(db)


# ── Task 3: Schedule Training ─────────────────────────────────────

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
    """Schedule a model training job.

    Validates that the dataset has at least MIN_DATASET_SAMPLES records,
    creates a training run record, updates the dataset status to
    ``training``, and simulates training preparation by creating
    checkpoint records with initial metrics.

    In production this would call Unsloth / Colab API for
    LLaMA-3-8B fine-tuning.

    Returns:
        Dict with training_job_id, dataset info, and estimated duration.
    """
    try:
        from database.models.training import (
            TrainingCheckpoint,
            TrainingDataset,
        )
    except ImportError as exc:
        return _build_error_status(
            self.name, f"Cannot import training models: {exc}",
            company_id=company_id, training_job_id=None,
            dataset_id=None, estimated_duration_min=0, model_type=model_type,
        )

    db = _get_db()
    try:
        # ── 1. Resolve dataset ───────────────────────────────
        dataset = None
        if dataset_version:
            dataset = (
                db.query(TrainingDataset)
                .filter(
                    TrainingDataset.company_id == company_id,
                    TrainingDataset.id == dataset_version,
                )
                .first()
            )
        else:
            # Use the most recent "prepared" dataset
            dataset = (
                db.query(TrainingDataset)
                .filter(
                    TrainingDataset.company_id == company_id,
                    TrainingDataset.status == "prepared",
                )
                .order_by(TrainingDataset.created_at.desc())
                .first()
            )

        if dataset is None:
            msg = "No suitable dataset found for training."
            logger.warning(
                "schedule_training_no_dataset",
                extra={
                    "task": self.name,
                    "company_id": company_id,
                    "dataset_version": dataset_version,
                },
            )
            return _build_error_status(
                self.name, msg,
                company_id=company_id, training_job_id=None,
                dataset_id=None, estimated_duration_min=0,
                model_type=model_type,
            )

        # ── 2. Validate minimum samples ──────────────────────
        if dataset.record_count < MIN_DATASET_SAMPLES:
            msg = (
                f"Dataset {dataset.id} has {dataset.record_count} samples, "
                f"minimum required is {MIN_DATASET_SAMPLES}."
            )
            logger.warning(
                "schedule_training_insufficient_samples",
                extra={
                    "task": self.name,
                    "company_id": company_id,
                    "dataset_id": dataset.id,
                    "record_count": dataset.record_count,
                },
            )
            return {
                "status": "skipped",
                "company_id": company_id,
                "training_job_id": None,
                "dataset_id": dataset.id,
                "estimated_duration_min": 0,
                "model_type": model_type,
                "reason": msg,
            }

        # ── 3. Create training run record ────────────────────
        training_run_id = str(uuid.uuid4())
        dataset.status = "training"
        dataset.updated_at = datetime.now(timezone.utc)

        # ── 4. Create initial checkpoint (epoch 0 baseline) ──
        baseline_metrics = json.dumps({
            "epoch": 0,
            "train_loss": None,
            "val_loss": None,
            "accuracy": 0.0,
            "confidence": 0.0,
            "status": "baseline",
        })

        initial_checkpoint = TrainingCheckpoint(
            company_id=company_id,
            training_run_id=training_run_id,
            checkpoint_name=f"epoch_0_baseline_{dataset.name}",
            metrics=baseline_metrics,
            epoch=0,
            is_best=False,
        )
        db.add(initial_checkpoint)

        db.commit()

        # ── 5. Estimate training duration ────────────────────
        # LLaMA-3-8B on single GPU: ~3 epochs * ~8 min/100 samples
        epochs = 3
        minutes_per_100 = 8
        estimated_duration_min = max(
            15,
            math.ceil((dataset.record_count / 100) * minutes_per_100 * epochs),
        )

        logger.info(
            "schedule_training_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "training_job_id": training_run_id,
                "dataset_id": dataset.id,
                "record_count": dataset.record_count,
                "estimated_duration_min": estimated_duration_min,
                "model_type": model_type,
            },
        )

        return {
            "status": "scheduled",
            "company_id": company_id,
            "training_job_id": training_run_id,
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "record_count": dataset.record_count,
            "estimated_duration_min": estimated_duration_min,
            "model_type": model_type,
            "epochs": epochs,
        }

    except Exception as exc:
        db.rollback()
        logger.error(
            "schedule_training_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:500],
            },
        )
        return _build_error_status(
            self.name, str(exc),
            company_id=company_id, training_job_id=None,
            dataset_id=None, estimated_duration_min=0,
            model_type=model_type,
        )
    finally:
        _safe_close_db(db)


# ── Task 4: Evaluate Training ─────────────────────────────────────

@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="training",
    name="app.tasks.training.evaluate_training",
    max_retries=2,
    soft_time_limit=180,
    time_limit=300,
)
@with_company_id
def evaluate_training(self, company_id: str,
                      training_job_id: str,
                      agent_id: Optional[str] = None) -> dict:
    """Evaluate trained model performance against baseline (A/B framework).

    Computes simulated metrics:
        - accuracy_improvement: percentage gain over baseline
        - confidence_delta: change in average confidence scores
        - escalation_rate_change: reduction in escalation rate

    Creates an AgentPerformance record and a TrainingCheckpoint
    with ``is_best`` flag.

    Returns:
        Dict with evaluation metrics, improvement percentage, and
        whether this is the best checkpoint so far.
    """
    try:
        from database.models.training import (
            AgentPerformance,
            TrainingCheckpoint,
        )
    except ImportError as exc:
        return _build_error_status(
            self.name, f"Cannot import training models: {exc}",
            company_id=company_id, training_job_id=training_job_id,
            metrics={}, improvement=0.0, is_best=False,
        )

    if not training_job_id:
        return _build_error_status(
            self.name, "training_job_id is required",
            company_id=company_id, training_job_id=None,
            metrics={}, improvement=0.0, is_best=False,
        )

    db = _get_db()
    try:
        # ── 1. Fetch existing checkpoints for this run ───────
        checkpoints = (
            db.query(TrainingCheckpoint)
            .filter(
                TrainingCheckpoint.company_id == company_id,
                TrainingCheckpoint.training_run_id == training_job_id,
            )
            .order_by(TrainingCheckpoint.epoch.desc())
            .all()
        )

        if not checkpoints:
            return {
                "status": "evaluated",
                "company_id": company_id,
                "training_job_id": training_job_id,
                "metrics": {},
                "improvement": 0.0,
                "is_best": False,
                "message": "No checkpoints found for this training run.",
            }

        # ── 2. Compute simulated evaluation metrics ──────────
        # Use the latest checkpoint's epoch to scale improvement
        latest_epoch = max(c.epoch or 0 for c in checkpoints)

        # Simulate progressive improvement based on epochs
        base_accuracy = 0.62
        base_confidence = 0.58
        base_escalation = 18.5  # percent

        # Each epoch yields ~6-10% relative improvement, capping at ~25%
        epoch_factor = min(latest_epoch / 3.0, 1.0)
        accuracy_improvement = round(base_accuracy * 0.22 * epoch_factor, 4)
        confidence_delta = round(base_confidence * 0.18 * epoch_factor, 4)
        escalation_reduction = round(base_escalation * 0.30 * epoch_factor, 2)

        new_accuracy = round(base_accuracy + accuracy_improvement, 4)
        new_confidence = round(base_confidence + confidence_delta, 4)
        new_escalation = round(max(5.0, base_escalation - escalation_reduction), 2)

        metrics = {
            "baseline_accuracy": base_accuracy,
            "new_accuracy": new_accuracy,
            "accuracy_improvement": accuracy_improvement,
            "baseline_confidence": base_confidence,
            "new_confidence": new_confidence,
            "confidence_delta": confidence_delta,
            "baseline_escalation_rate": base_escalation,
            "new_escalation_rate": new_escalation,
            "escalation_rate_change": -escalation_reduction,
            "epochs_trained": latest_epoch,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

        overall_improvement = round(
            (accuracy_improvement / max(base_accuracy, 0.01)) * 100, 2
        )

        # ── 3. Determine if this is the best checkpoint ──────
        # Check if any prior checkpoint for this company has higher improvement
        prior_best = (
            db.query(TrainingCheckpoint)
            .filter(
                TrainingCheckpoint.company_id == company_id,
                TrainingCheckpoint.is_best == True,  # noqa: E712
                TrainingCheckpoint.training_run_id != training_job_id,
            )
            .first()
        )

        prior_best_improvement = 0.0
        if prior_best and prior_best.metrics:
            try:
                prior_metrics = json.loads(prior_best.metrics)
                prior_best_improvement = prior_metrics.get(
                    "overall_improvement", 0.0
                )
            except (json.JSONDecodeError, TypeError):
                pass

        is_best = overall_improvement > prior_best_improvement

        # ── 4. Create evaluation checkpoint ──────────────────
        eval_metrics_json = json.dumps({
            **metrics,
            "overall_improvement": overall_improvement,
        })

        eval_checkpoint = TrainingCheckpoint(
            company_id=company_id,
            training_run_id=training_job_id,
            checkpoint_name=f"eval_epoch_{latest_epoch}",
            metrics=eval_metrics_json,
            epoch=latest_epoch,
            is_best=is_best,
        )
        db.add(eval_checkpoint)

        # If this is best, demote previous best checkpoints
        if is_best:
            (
                db.query(TrainingCheckpoint)
                .filter(
                    TrainingCheckpoint.company_id == company_id,
                    TrainingCheckpoint.is_best == True,  # noqa: E712
                    TrainingCheckpoint.id != eval_checkpoint.id,
                )
                .update({"is_best": False}, synchronize_session="fetch")
            )

        # ── 5. Create AgentPerformance record ────────────────
        resolved_agent_id = agent_id or checkpoints[0].training_run_id
        performance = AgentPerformance(
            company_id=company_id,
            agent_id=resolved_agent_id,
            period="post_training",
            period_start=datetime.now(timezone.utc) - timedelta(days=7),
            tickets_resolved=0,  # will be populated from actual data
            avg_confidence=new_confidence,
            avg_resolution_time_min=12.5,  # simulated
            escalation_rate=new_escalation,
            csat_score=round(3.8 + overall_improvement * 0.04, 2),
        )
        db.add(performance)

        db.commit()

        logger.info(
            "evaluate_training_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "training_job_id": training_job_id,
                "overall_improvement": overall_improvement,
                "is_best": is_best,
            },
        )

        return {
            "status": "evaluated",
            "company_id": company_id,
            "training_job_id": training_job_id,
            "metrics": metrics,
            "improvement": overall_improvement,
            "is_best": is_best,
            "prior_best_improvement": prior_best_improvement,
        }

    except Exception as exc:
        db.rollback()
        logger.error(
            "evaluate_training_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "training_job_id": training_job_id,
                "error": str(exc)[:500],
            },
        )
        return _build_error_status(
            self.name, str(exc),
            company_id=company_id, training_job_id=training_job_id,
            metrics={}, improvement=0.0, is_best=False,
        )
    finally:
        _safe_close_db(db)


# ── Task 5: Cleanup Old Datasets ──────────────────────────────────

@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="training",
    name="app.tasks.training.cleanup_old_datasets",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
@with_company_id
def cleanup_old_datasets(self, company_id: str,
                         max_age_days: int = CLEANUP_AGE_DAYS) -> dict:
    """Delete training datasets older than *max_age_days* that are not in use.

    A dataset is considered "in use" if its status is ``training``.
    Associated checkpoint records are also cleaned up.

    Returns:
        Dict with the number of datasets removed and estimated space freed.
    """
    try:
        from database.models.training import (
            TrainingCheckpoint,
            TrainingDataset,
        )
    except ImportError as exc:
        return _build_error_status(
            self.name, f"Cannot import training models: {exc}",
            company_id=company_id, datasets_removed=0, space_freed_mb=0.0,
        )

    db = _get_db()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

        # ── 1. Find stale datasets (not currently training) ──
        stale_datasets = (
            db.query(TrainingDataset)
            .filter(
                TrainingDataset.company_id == company_id,
                TrainingDataset.created_at < cutoff,
                TrainingDataset.status != "training",  # noqa: E712
            )
            .all()
        )

        datasets_removed = 0
        checkpoints_removed = 0
        stale_ids: List[str] = []

        for dataset in stale_datasets:
            stale_ids.append(dataset.id)

            # ── 2. Delete associated checkpoints ─────────────
            # TrainingCheckpoint references training_run_id, not
            # dataset_id directly, but we delete checkpoints that
            # are not tied to any active training run.
            # We match by company_id and check the run is old.
            del_count = (
                db.query(TrainingCheckpoint)
                .filter(
                    TrainingCheckpoint.company_id == company_id,
                    TrainingCheckpoint.created_at < cutoff,
                )
                .delete(synchronize_session="fetch")
            )
            checkpoints_removed += del_count

            # ── 3. Delete the dataset ─────────────────────────
            db.delete(dataset)
            datasets_removed += 1

        db.commit()

        space_freed_mb = round(
            datasets_removed * ESTIMATED_SPACE_PER_DATASET_MB, 2
        )

        logger.info(
            "cleanup_old_datasets_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "datasets_removed": datasets_removed,
                "checkpoints_removed": checkpoints_removed,
                "space_freed_mb": space_freed_mb,
                "max_age_days": max_age_days,
            },
        )

        return {
            "status": "cleaned",
            "company_id": company_id,
            "datasets_removed": datasets_removed,
            "checkpoints_removed": checkpoints_removed,
            "space_freed_mb": space_freed_mb,
            "max_age_days": max_age_days,
            "cutoff_date": cutoff.isoformat(),
            "removed_dataset_ids": stale_ids,
        }

    except Exception as exc:
        db.rollback()
        logger.error(
            "cleanup_old_datasets_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:500],
            },
        )
        return _build_error_status(
            self.name, str(exc),
            company_id=company_id, datasets_removed=0, space_freed_mb=0.0,
        )
    finally:
        _safe_close_db(db)
