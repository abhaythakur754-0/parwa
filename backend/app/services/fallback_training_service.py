"""
Fallback Training Service — F-106 Bi-Weekly Scheduled Retraining

Provides automatic scheduled retraining for agents to maintain model freshness
and adapt to evolving patterns in customer interactions.

# TODO (Day 6 — I5): Add stricter tenant scoping to training data access.
# The dataset preparation and training runs below are already scoped by
# company_id in the SQL queries, but the DatasetPreparationService and
# training workers should validate company_id on every operation to
# prevent cross-tenant data leakage during batch processing.

Features:
- Bi-weekly (every 14 days) scheduled retraining
- Smart scheduling based on last training date
- Automatic dataset preparation from recent mistakes
- Training effectiveness tracking
- Graceful handling of concurrent training

Building Codes:
- BC-001: Multi-tenant isolation (all queries scoped by company_id)
- BC-004: Background Jobs (Celery tasks for scheduled training)
- BC-007: AI Model Interaction (Training pipeline integration)
- BC-012: Error handling (structured errors, retry logic)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

from sqlalchemy.orm import Session

logger = logging.getLogger("parwa.fallback_training")

# ── Constants ───────────────────────────────────────────────────────────────

# Bi-weekly interval (14 days)
RETRAINING_INTERVAL_DAYS = 14

# Minimum new mistakes for retraining to be worthwhile
MIN_NEW_MISTAKES_FOR_RETRAINING = 10

# Minimum days since last training to consider retraining
MIN_DAYS_SINCE_TRAINING = 7

# Training priority levels
PRIORITY_LOW = "low"
PRIORITY_NORMAL = "normal"
PRIORITY_HIGH = "high"

# Retraining triggers
RETRAINING_TRIGGER_SCHEDULED = "scheduled"  # Bi-weekly scheduled
RETRAINING_TRIGGER_FALLBACK = "fallback"    # Fallback after failed training
RETRAINING_TRIGGER_STALE = "stale"          # Model is stale (old)


class FallbackTrainingService:
    """Service for managing bi-weekly scheduled retraining (F-106).

    This service handles:
    - Checking which agents are due for retraining
    - Scheduling retraining jobs
    - Tracking retraining history
    - Managing training effectiveness metrics

    Usage:
        service = FallbackTrainingService(db)
        due_agents = service.get_agents_due_for_retraining(company_id)
        result = service.schedule_retraining(company_id, agent_id)
    """

    def __init__(self, db: Session):
        self.db = db

    # ══════════════════════════════════════════════════════════════════════════
    # Retraining Eligibility
    # ══════════════════════════════════════════════════════════════════════════

    def get_agents_due_for_retraining(
        self,
        company_id: str,
        include_force: bool = False,
    ) -> List[Dict]:
        """Get list of agents that are due for bi-weekly retraining.

        Args:
            company_id: Tenant company ID.
            include_force: If True, include agents regardless of timing.

        Returns:
            List of agents with retraining eligibility info.
        """
        from database.models.agent import Agent
        from database.models.training import TrainingRun, AgentMistake

        # Get all active agents
        agents = (
            self.db.query(Agent)
            .filter(
                Agent.company_id == company_id,
                Agent.status == "active",
            )
            .all()
        )

        due_agents = []
        now = datetime.now(timezone.utc)

        for agent in agents:
            # Get last successful training run
            last_training = (
                self.db.query(TrainingRun)
                .filter(
                    TrainingRun.company_id == company_id,
                    TrainingRun.agent_id == str(agent.id),
                    TrainingRun.status == "completed",
                )
                .order_by(TrainingRun.completed_at.desc())
                .first()
            )

            # Get new mistakes since last training
            mistakes_query = (
                self.db.query(AgentMistake)
                .filter(
                    AgentMistake.company_id == company_id,
                    AgentMistake.agent_id == str(agent.id),
                )
            )

            if last_training and last_training.completed_at:
                mistakes_query = mistakes_query.filter(
                    AgentMistake.created_at > last_training.completed_at
                )

            new_mistakes_count = mistakes_query.count()

            # Calculate days since last training
            days_since_training = None
            if last_training and last_training.completed_at:
                delta = now - last_training.completed_at
                days_since_training = delta.days

            # Determine if retraining is due
            is_due = False
            reason = ""

            if include_force:
                is_due = True
                reason = "forced"
            elif last_training is None:
                # Never trained - should use cold start (F-107) instead
                is_due = False
                reason = "never_trained_use_cold_start"
            elif days_since_training is not None and days_since_training >= RETRAINING_INTERVAL_DAYS:
                if new_mistakes_count >= MIN_NEW_MISTAKES_FOR_RETRAINING:
                    is_due = True
                    reason = "scheduled_biweekly"
                else:
                    is_due = True
                    reason = "scheduled_biweekly_low_mistakes"
            elif days_since_training is not None and days_since_training >= MIN_DAYS_SINCE_TRAINING:
                if new_mistakes_count >= MIN_NEW_MISTAKES_FOR_RETRAINING * 3:
                    is_due = True
                    reason = "high_mistakes_early_retrain"
                else:
                    is_due = False
                    reason = f"not_due_yet_{
                        RETRAINING_INTERVAL_DAYS -
                        days_since_training}_days_remaining"
            else:
                is_due = False
                reason = "recently_trained"

            due_agents.append({
                "agent_id": str(agent.id),
                "agent_name": agent.name,
                "agent_status": agent.status,
                "last_training_id": str(last_training.id) if last_training else None,
                "last_training_date": last_training.completed_at.isoformat() if last_training and last_training.completed_at else None,
                "days_since_training": days_since_training,
                "new_mistakes_count": new_mistakes_count,
                "is_due_for_retraining": is_due,
                "reason": reason,
                "retraining_interval_days": RETRAINING_INTERVAL_DAYS,
            })

        return due_agents

    def get_retraining_schedule(
        self,
        company_id: str,
        days_ahead: int = 30,
    ) -> Dict:
        """Get the upcoming retraining schedule for the company.

        Args:
            company_id: Tenant company ID.
            days_ahead: Number of days to look ahead.

        Returns:
            Dict with schedule information.
        """
        from database.models.agent import Agent
        from database.models.training import TrainingRun

        agents = (
            self.db.query(Agent)
            .filter(
                Agent.company_id == company_id,
                Agent.status == "active",
            )
            .all()
        )

        schedule = []
        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=days_ahead)

        for agent in agents:
            last_training = (
                self.db.query(TrainingRun)
                .filter(
                    TrainingRun.company_id == company_id,
                    TrainingRun.agent_id == str(agent.id),
                    TrainingRun.status == "completed",
                )
                .order_by(TrainingRun.completed_at.desc())
                .first()
            )

            if last_training and last_training.completed_at:
                next_training = last_training.completed_at + \
                    timedelta(days=RETRAINING_INTERVAL_DAYS)
            else:
                # Cold start agents - schedule immediately
                next_training = now

            if next_training <= end_date:
                schedule.append({
                    "agent_id": str(agent.id),
                    "agent_name": agent.name,
                    "scheduled_date": next_training.isoformat(),
                    "is_overdue": next_training < now,
                })

        # Sort by scheduled date
        schedule.sort(key=lambda x: x["scheduled_date"])

        return {
            "company_id": company_id,
            "schedule": schedule,
            "interval_days": RETRAINING_INTERVAL_DAYS,
            "generated_at": now.isoformat(),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Retraining Execution
    # ══════════════════════════════════════════════════════════════════════════

    def schedule_retraining(
        self,
        company_id: str,
        agent_id: str,
        force: bool = False,
        priority: str = PRIORITY_NORMAL,
    ) -> Dict:
        """Schedule bi-weekly retraining for an agent.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent to retrain.
            force: Force retraining even if not due.
            priority: Training priority (low, normal, high).

        Returns:
            Dict with scheduling result.
        """
        from app.services.agent_training_service import AgentTrainingService
        from app.services.dataset_preparation_service import DatasetPreparationService

        # Check eligibility
        due_agents = self.get_agents_due_for_retraining(
            company_id, include_force=force)
        agent_info = next(
            (a for a in due_agents if a["agent_id"] == agent_id), None)

        if not agent_info:
            return {
                "status": "error",
                "error": f"Agent {agent_id} not found or not active",
            }

        if not agent_info["is_due_for_retraining"] and not force:
            return {
                "status": "skipped",
                "reason": agent_info["reason"],
                "agent_id": agent_id,
                "next_training_days": RETRAINING_INTERVAL_DAYS - (agent_info["days_since_training"] or 0),
            }

        # Check if already training
        from database.models.training import TrainingRun
        active_run = (
            self.db.query(TrainingRun)
            .filter(
                TrainingRun.company_id == company_id,
                TrainingRun.agent_id == agent_id,
                TrainingRun.status.in_(["queued", "initializing", "running"]),
            )
            .first()
        )

        if active_run:
            return {
                "status": "skipped",
                "reason": "already_training",
                "agent_id": agent_id,
                "active_run_id": str(active_run.id),
            }

        try:
            # Prepare dataset from recent mistakes
            dataset_service = DatasetPreparationService(self.db)
            dataset_result = dataset_service.prepare_dataset(
                company_id=company_id,
                agent_id=agent_id,
                source="mistakes",
                min_samples=MIN_NEW_MISTAKES_FOR_RETRAINING,
                force_prepare=True,
            )

            if dataset_result.get("status") != "prepared":
                # Try with all available data
                dataset_result = dataset_service.prepare_dataset(
                    company_id=company_id,
                    agent_id=agent_id,
                    source="all",
                    min_samples=10,
                    force_prepare=True,
                )

            if dataset_result.get("status") != "prepared":
                return {
                    "status": "error",
                    "error": f"Dataset preparation failed: {
                        dataset_result.get('error')}",
                    "agent_id": agent_id,
                }

            # Create training run with scheduled trigger
            training_service = AgentTrainingService(self.db)
            run_result = training_service.create_training_run(
                company_id=company_id,
                agent_id=agent_id,
                dataset_id=dataset_result["dataset_id"],
                name=f"Bi-weekly retraining - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
                trigger=RETRAINING_TRIGGER_SCHEDULED,
                epochs=3,
            )

            if run_result.get("status") != "created":
                return {
                    "status": "error",
                    "error": run_result.get("error"),
                    "agent_id": agent_id,
                }

            logger.info(
                "fallback_training_scheduled",
                extra={
                    "company_id": company_id,
                    "agent_id": agent_id,
                    "run_id": run_result["run_id"],
                    "dataset_id": dataset_result["dataset_id"],
                    "priority": priority,
                },
            )

            return {
                "status": "scheduled",
                "agent_id": agent_id,
                "run_id": run_result["run_id"],
                "dataset_id": dataset_result["dataset_id"],
                "sample_count": dataset_result.get("sample_count"),
                "trigger": RETRAINING_TRIGGER_SCHEDULED,
                "priority": priority,
            }

        except Exception as exc:
            logger.error(
                "fallback_training_schedule_failed",
                extra={
                    "company_id": company_id,
                    "agent_id": agent_id,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "error": str(exc)[:500],
                "agent_id": agent_id,
            }

    def schedule_all_due_retraining(self, company_id: str) -> Dict:
        """Schedule retraining for all agents that are due.

        Args:
            company_id: Tenant company ID.

        Returns:
            Dict with scheduling results.
        """
        due_agents = self.get_agents_due_for_retraining(company_id)
        eligible_agents = [a for a in due_agents if a["is_due_for_retraining"]]

        results = {
            "scheduled": [],
            "skipped": [],
            "errors": [],
        }

        for agent in eligible_agents:
            result = self.schedule_retraining(
                company_id=company_id,
                agent_id=agent["agent_id"],
            )

            if result["status"] == "scheduled":
                results["scheduled"].append(result)
            elif result["status"] == "skipped":
                results["skipped"].append(result)
            else:
                results["errors"].append(result)

        logger.info(
            "bulk_fallback_training_scheduled",
            extra={
                "company_id": company_id,
                "scheduled_count": len(results["scheduled"]),
                "skipped_count": len(results["skipped"]),
                "error_count": len(results["errors"]),
            },
        )

        return {
            "status": "completed",
            "company_id": company_id,
            "total_due": len(eligible_agents),
            "scheduled": len(results["scheduled"]),
            "skipped": len(results["skipped"]),
            "errors": len(results["errors"]),
            "details": results,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Training Effectiveness
    # ══════════════════════════════════════════════════════════════════════════

    def get_training_effectiveness(
        self,
        company_id: str,
        agent_id: Optional[str] = None,
        runs: int = 5,
    ) -> Dict:
        """Get effectiveness metrics for recent training runs.

        Compares pre-training and post-training performance to measure
        the effectiveness of the retraining process.

        Args:
            company_id: Tenant company ID.
            agent_id: Optional agent filter.
            runs: Number of recent runs to analyze.

        Returns:
            Dict with effectiveness metrics.
        """
        from database.models.training import TrainingRun, AgentMistake

        query = (
            self.db.query(TrainingRun)
            .filter(
                TrainingRun.company_id == company_id,
                TrainingRun.status == "completed",
            )
        )

        if agent_id:
            query = query.filter(TrainingRun.agent_id == agent_id)

        recent_runs = (
            query
            .order_by(TrainingRun.completed_at.desc())
            .limit(runs)
            .all()
        )

        effectiveness_data = []

        for run in recent_runs:
            # Get mistakes before training (7 days before)
            if run.started_at:
                before_start = run.started_at - timedelta(days=7)
                before_end = run.started_at
            else:
                before_start = run.created_at - \
                    timedelta(days=7) if run.created_at else datetime.now(timezone.utc) - timedelta(days=7)
                before_end = run.created_at if run.created_at else datetime.now(
                    timezone.utc)

            after_start = run.completed_at if run.completed_at else datetime.now(
                timezone.utc)
            after_end = after_start + timedelta(days=7)

            mistakes_before = (
                self.db.query(AgentMistake)
                .filter(
                    AgentMistake.company_id == company_id,
                    AgentMistake.agent_id == run.agent_id,
                    AgentMistake.created_at >= before_start,
                    AgentMistake.created_at < before_end,
                )
                .count()
            )

            mistakes_after = (
                self.db.query(AgentMistake)
                .filter(
                    AgentMistake.company_id == company_id,
                    AgentMistake.agent_id == run.agent_id,
                    AgentMistake.created_at >= after_start,
                    AgentMistake.created_at < after_end,
                )
                .count()
            )

            # Calculate improvement
            if mistakes_before > 0:
                improvement_pct = (
                    (mistakes_before - mistakes_after) / mistakes_before) * 100
            else:
                improvement_pct = 0 if mistakes_after == 0 else -100

            run_metrics = run.metrics or {}
            final_accuracy = run_metrics.get("final_accuracy", 0)
            quality_score = run_metrics.get("quality_score", 0)

            effectiveness_data.append({
                "run_id": str(run.id),
                "agent_id": str(run.agent_id),
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "trigger": run.trigger,
                "final_accuracy": final_accuracy,
                "quality_score": quality_score,
                "mistakes_before": mistakes_before,
                "mistakes_after": mistakes_after,
                "improvement_pct": round(improvement_pct, 2),
                "cost_usd": float(run.cost_usd) if run.cost_usd else 0,
            })

        # Calculate aggregate metrics
        avg_improvement = 0
        avg_accuracy = 0
        total_cost = 0

        if effectiveness_data:
            improvements = [d["improvement_pct"] for d in effectiveness_data]
            accuracies = [d["final_accuracy"]
                          for d in effectiveness_data if d["final_accuracy"]]
            costs = [d["cost_usd"] for d in effectiveness_data]

            avg_improvement = sum(improvements) / len(improvements)
            avg_accuracy = sum(accuracies) / \
                len(accuracies) if accuracies else 0
            total_cost = sum(costs)

        return {
            "company_id": company_id,
            "agent_id": agent_id,
            "runs_analyzed": len(effectiveness_data),
            "average_improvement_pct": round(avg_improvement, 2),
            "average_accuracy": round(avg_accuracy, 4),
            "total_cost_usd": round(total_cost, 2),
            "retraining_interval_days": RETRAINING_INTERVAL_DAYS,
            "runs": effectiveness_data,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Configuration
    # ══════════════════════════════════════════════════════════════════════════

    def get_retraining_config(self, company_id: str) -> Dict:
        """Get retraining configuration for a company.

        Args:
            company_id: Tenant company ID.

        Returns:
            Dict with retraining config.
        """
        return {
            "company_id": company_id,
            "retraining_interval_days": RETRAINING_INTERVAL_DAYS,
            "min_new_mistakes_for_retraining": MIN_NEW_MISTAKES_FOR_RETRAINING,
            "min_days_since_training": MIN_DAYS_SINCE_TRAINING,
            "note": "Bi-weekly retraining runs every 14 days with automatic dataset preparation from recent mistakes.",
        }

    def get_retraining_stats(self, company_id: str) -> Dict:
        """Get overall retraining statistics for a company.

        Args:
            company_id: Tenant company ID.

        Returns:
            Dict with retraining stats.
        """
        from database.models.training import TrainingRun

        # Get all scheduled training runs
        scheduled_runs = (
            self.db.query(TrainingRun)
            .filter(
                TrainingRun.company_id == company_id,
                TrainingRun.trigger == RETRAINING_TRIGGER_SCHEDULED,
            )
            .all()
        )

        total = len(scheduled_runs)
        completed = len([r for r in scheduled_runs if r.status == "completed"])
        failed = len([r for r in scheduled_runs if r.status == "failed"])
        running = len([r for r in scheduled_runs if r.status == "running"])

        total_cost = sum(float(r.cost_usd or 0) for r in scheduled_runs)

        # Get agents due for retraining
        due_agents = self.get_agents_due_for_retraining(company_id)
        agents_due = [a for a in due_agents if a["is_due_for_retraining"]]

        return {
            "company_id": company_id,
            "total_scheduled_runs": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "total_cost_usd": round(total_cost, 2),
            "agents_currently_due": len(agents_due),
            "retraining_interval_days": RETRAINING_INTERVAL_DAYS,
        }
