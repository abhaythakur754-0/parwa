"""
Mistake Threshold Service — F-101: 50-Mistake Threshold Trigger

Implements the automatic training activation mechanism that fires when an AI agent
accumulates exactly 50 mistake reports. Per BC-007 rule 10, this threshold
is LOCKED and cannot be modified by any admin.

Building Codes:
- BC-007 rule 10: MISTAKE_THRESHOLD = 50 is hard-coded constant,
  NO DB config, NO env var, NO admin override. If anyone modifies this
  value, CI must fail.
- BC-004: Background Jobs (Celery tasks for threshold checks)
- BC-009: Approval Workflow (audit trail before auto-training)
- BC-012: Error handling (retry logic for training initiation failures)
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger("parwa.mistake_threshold")

# ═══════════════════════════════════════════════════════════════════════════════
# CRITICAL: LOCKED THRESHOLD — DO NOT MODIFY
# BC-007 Rule 10: This value is hard-coded and immutable.
# Changing this value violates the system specification and will cause CI failure.
# ═══════════════════════════════════════════════════════════════════════════════

MISTAKE_THRESHOLD = 50  # LOCKED — DO NOT CHANGE

# Verify the threshold hasn't been tampered with
assert MISTAKE_THRESHOLD == 50, (
    "CRITICAL: MISTAKE_THRESHOLD has been modified from the required value of 50. "
    "This violates BC-007 rule 10 and will cause CI failure."
)

# ── Mistake types for categorization ────────────────────────────────────

MISTAKE_TYPE_INCORRECT_RESPONSE = "incorrect_response"
MISTAKE_TYPE_HALLUCINATION = "hallucination"
MISTAKE_TYPE_TONE_ISSUE = "tone_issue"
MISTAKE_TYPE_INCOMPLETE = "incomplete"
MISTAKE_TYPE_POLICY_VIOLATION = "policy_violation"
MISTAKE_TYPE_ESCALATION_NEEDED = "escalation_needed"
MISTAKE_TYPE_OTHER = "other"

# ── Severity levels ─────────────────────────────────────────────────────

SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
SEVERITY_CRITICAL = "critical"


class MistakeThresholdService:
    """Service for managing the 50-Mistake Threshold Trigger (F-101).

    This service:
    - Records and tracks agent mistakes
    - Enforces the LOCKED threshold of 50 mistakes
    - Automatically triggers training when threshold is reached
    - Manages mistake count lifecycle

    IMPORTANT: The threshold value of 50 is immutable and enforced at the
    code level. No configuration can change it.

    Usage:
        service = MistakeThresholdService(db)
        result = service.report_mistake(company_id, agent_id, mistake_data)
        status = service.get_threshold_status(company_id, agent_id)
    """

    def __init__(self, db: Session):
        self.db = db

    # ════════════════════════════════════════════════════════════════════════════
    # Mistake Reporting
    # ════════════════════════════════════════════════════════════════════════════

    def report_mistake(
        self,
        company_id: str,
        agent_id: str,
        ticket_id: Optional[str] = None,
        mistake_type: str = MISTAKE_TYPE_OTHER,
        original_response: Optional[str] = None,
        expected_response: Optional[str] = None,
        correction: Optional[str] = None,
        severity: str = SEVERITY_MEDIUM,
        reported_by: Optional[str] = None,
    ) -> Dict:
        """Report a new agent mistake.

        This method:
        1. Creates the mistake record
        2. Checks if threshold is reached
        3. If threshold reached, triggers training automatically

        Args:
            company_id: Tenant company ID.
            agent_id: Agent that made the mistake.
            ticket_id: Related ticket ID.
            mistake_type: Type of mistake (incorrect_response, hallucination, etc.).
            original_response: The incorrect AI response.
            expected_response: What the response should have been.
            correction: Corrected response or action taken.
            severity: Mistake severity (low, medium, high, critical).
            reported_by: User who reported the mistake.

        Returns:
            Dict with mistake_id, current_count, threshold_status, and
            training_triggered flag.
        """
        from database.models.training import AgentMistake

        # Create the mistake record
        mistake = AgentMistake(
            company_id=company_id,
            agent_id=agent_id,
            session_id=ticket_id,
            mistake_type=mistake_type,
            original_response=original_response,
            expected_response=expected_response,
            correction=correction,
            severity=severity,
            used_in_training=False,
        )
        self.db.add(mistake)
        self.db.commit()
        self.db.refresh(mistake)

        # Get current mistake count
        current_count = self._get_mistake_count(company_id, agent_id)

        logger.info(
            "mistake_reported",
            extra={
                "company_id": company_id,
                "agent_id": agent_id,
                "mistake_id": str(mistake.id),
                "mistake_type": mistake_type,
                "severity": severity,
                "current_count": current_count,
                "threshold": MISTAKE_THRESHOLD,
            },
        )

        # Check if threshold is reached
        training_triggered = False
        training_run_id = None

        if current_count >= MISTAKE_THRESHOLD:
            training_triggered, training_run_id = self._trigger_training_if_needed(
                company_id, agent_id)

        return {
            "status": "reported",
            "mistake_id": str(mistake.id),
            "agent_id": agent_id,
            "current_count": current_count,
            "threshold": MISTAKE_THRESHOLD,
            "training_triggered": training_triggered,
            "training_run_id": training_run_id,
        }

    def get_threshold_status(self, company_id: str, agent_id: str) -> Dict:
        """Get the current threshold status for an agent.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent ID.

        Returns:
            Dict with current_count, threshold, percentage, and triggered status.
        """
        current_count = self._get_mistake_count(company_id, agent_id)
        triggered = current_count >= MISTAKE_THRESHOLD

        return {
            "agent_id": agent_id,
            "current_count": current_count,
            "threshold": MISTAKE_THRESHOLD,
            "percentage": round((current_count / MISTAKE_THRESHOLD) * 100, 1),
            "triggered": triggered,
            "remaining": max(0, MISTAKE_THRESHOLD - current_count),
        }

    def get_mistake_history(
        self,
        company_id: str,
        agent_id: str,
        limit: int = 50,
        offset: int = 0,
        severity: Optional[str] = None,
        mistake_type: Optional[str] = None,
    ) -> Dict:
        """Get mistake history for an agent.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent ID.
            limit: Max results.
            offset: Pagination offset.
            severity: Optional severity filter.
            mistake_type: Optional type filter.

        Returns:
            Dict with mistakes list and total count.
        """
        from database.models.training import AgentMistake

        query = (
            self.db.query(AgentMistake)
            .filter(
                AgentMistake.company_id == company_id,
                AgentMistake.agent_id == agent_id,
            )
        )

        if severity:
            query = query.filter(AgentMistake.severity == severity)
        if mistake_type:
            query = query.filter(AgentMistake.mistake_type == mistake_type)

        total = query.count()
        mistakes = (
            query
            .order_by(AgentMistake.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "mistakes": [
                {
                    "id": str(m.id),
                    "ticket_id": str(m.session_id) if m.session_id else None,
                    "mistake_type": m.mistake_type,
                    "severity": m.severity,
                    "original_response": m.original_response[:200] + "..." if m.original_response and len(m.original_response) > 200 else m.original_response,
                    "used_in_training": m.used_in_training,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in mistakes
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_mistake_stats(self, company_id: str, agent_id: str) -> Dict:
        """Get mistake statistics for an agent.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent ID.

        Returns:
            Dict with statistics by type, severity, and trends.
        """
        from database.models.training import AgentMistake

        # Total count
        total = (
            self.db.query(func.count(AgentMistake.id))
            .filter(
                AgentMistake.company_id == company_id,
                AgentMistake.agent_id == agent_id,
            )
            .scalar()
        ) or 0

        # By type
        by_type_rows = (
            self.db.query(
                AgentMistake.mistake_type,
                func.count(AgentMistake.id),
            )
            .filter(
                AgentMistake.company_id == company_id,
                AgentMistake.agent_id == agent_id,
            )
            .group_by(AgentMistake.mistake_type)
            .all()
        )
        by_type = {t: c for t, c in by_type_rows}

        # By severity
        by_severity_rows = (
            self.db.query(
                AgentMistake.severity,
                func.count(AgentMistake.id),
            )
            .filter(
                AgentMistake.company_id == company_id,
                AgentMistake.agent_id == agent_id,
            )
            .group_by(AgentMistake.severity)
            .all()
        )
        by_severity = {s: c for s, c in by_severity_rows}

        # Used in training count
        used_in_training = (
            self.db.query(func.count(AgentMistake.id))
            .filter(
                AgentMistake.company_id == company_id,
                AgentMistake.agent_id == agent_id,
                AgentMistake.used_in_training,
            )
            .scalar()
        ) or 0

        return {
            "total_mistakes": total,
            "threshold": MISTAKE_THRESHOLD,
            "percentage_to_threshold": round(
                (total / MISTAKE_THRESHOLD) * 100,
                1),
            "by_type": by_type,
            "by_severity": by_severity,
            "used_in_training": used_in_training,
            "available_for_training": total - used_in_training,
        }

    def reset_mistake_count(
            self,
            company_id: str,
            agent_id: str,
            reason: str = "training_completed") -> Dict:
        """Reset the mistake count for an agent.

        This should only be called after a successful training run deployment.
        Marks existing mistakes as used_in_training.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent ID.
            reason: Reason for reset.

        Returns:
            Dict with reset status.
        """
        from database.models.training import AgentMistake

        # Mark all unprocessed mistakes as used in training
        updated = (
            self.db.query(AgentMistake)
            .filter(
                AgentMistake.company_id == company_id,
                AgentMistake.agent_id == agent_id,
                AgentMistake.used_in_training is False,
            )
            .update({"used_in_training": True})
        )

        self.db.commit()

        logger.info(
            "mistake_count_reset",
            extra={
                "company_id": company_id,
                "agent_id": agent_id,
                "mistakes_marked": updated,
                "reason": reason,
            },
        )

        return {
            "status": "reset",
            "agent_id": agent_id,
            "mistakes_marked_as_used": updated,
            "reason": reason,
        }

    # ════════════════════════════════════════════════════════════════════════════
    # Private Methods
    # ════════════════════════════════════════════════════════════════════════════

    def _get_mistake_count(self, company_id: str, agent_id: str) -> int:
        """Get the current unprocessed mistake count for an agent.

        Only counts mistakes not yet used in training.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent ID.

        Returns:
            Current mistake count.
        """
        from database.models.training import AgentMistake

        return (
            self.db.query(func.count(AgentMistake.id))
            .filter(
                AgentMistake.company_id == company_id,
                AgentMistake.agent_id == agent_id,
                AgentMistake.used_in_training is False,
            )
            .scalar()
        ) or 0

    def _trigger_training_if_needed(
            self,
            company_id: str,
            agent_id: str) -> tuple:
        """Trigger training if threshold is reached and not already training.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent ID.

        Returns:
            Tuple of (training_triggered: bool, training_run_id: Optional[str]).
        """
        from database.models.training import TrainingRun
        from app.services.agent_training_service import (
            AgentTrainingService,
            TRAINING_STATUS_QUEUED,
            TRAINING_STATUS_INITIALIZING,
            TRAINING_STATUS_RUNNING,
        )

        # Check if agent is already training
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
            logger.warning(
                "threshold_reached_but_training_in_progress",
                extra={
                    "company_id": company_id,
                    "agent_id": agent_id,
                    "existing_run_id": str(existing_run.id),
                },
            )
            return (False, None)

        # Create or get a dataset from mistakes
        dataset = self._create_dataset_from_mistakes(company_id, agent_id)

        if not dataset:
            logger.error(
                "failed_to_create_training_dataset",
                extra={"company_id": company_id, "agent_id": agent_id},
            )
            return (False, None)

        # Trigger training via AgentTrainingService
        training_service = AgentTrainingService(self.db)
        result = training_service.create_training_run(
            company_id=company_id,
            agent_id=agent_id,
            dataset_id=dataset["dataset_id"],
            name=f"Auto-training triggered by {MISTAKE_THRESHOLD} mistakes",
            trigger="auto_threshold",
        )

        if result.get("status") == "created":
            logger.info(
                "auto_training_triggered",
                extra={
                    "company_id": company_id,
                    "agent_id": agent_id,
                    "training_run_id": result.get("run_id"),
                    "threshold": MISTAKE_THRESHOLD,
                },
            )

            # Create audit trail entry (BC-009)
            self._create_audit_trail(
                company_id, agent_id, result.get("run_id"), MISTAKE_THRESHOLD
            )

            # Send notification
            self._send_threshold_notification(
                company_id, agent_id, result.get("run_id"))

            return (True, result.get("run_id"))
        else:
            logger.error(
                "auto_training_failed",
                extra={
                    "company_id": company_id,
                    "agent_id": agent_id,
                    "error": result.get("error"),
                },
            )
            return (False, None)

    def _create_dataset_from_mistakes(
            self,
            company_id: str,
            agent_id: str) -> Optional[Dict]:
        """Create a training dataset from agent mistakes.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent ID.

        Returns:
            Dict with dataset_id or None on failure.
        """
        from database.models.training import TrainingDataset, AgentMistake

        # Get unprocessed mistakes
        mistakes = (
            self.db.query(AgentMistake)
            .filter(
                AgentMistake.company_id == company_id,
                AgentMistake.agent_id == agent_id,
                AgentMistake.used_in_training is False,
            )
            .all()
        )

        if len(mistakes) < MISTAKE_THRESHOLD:
            logger.warning(
                "insufficient_mistakes_for_dataset",
                extra={
                    "company_id": company_id,
                    "agent_id": agent_id,
                    "count": len(mistakes),
                    "required": MISTAKE_THRESHOLD,
                },
            )
            return None

        # Create dataset
        dataset = TrainingDataset(
            company_id=company_id,
            agent_id=agent_id,
            name=f"Mistakes dataset - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            source="mistakes",
            record_count=len(mistakes),
            status="ready",
        )
        self.db.add(dataset)
        self.db.commit()
        self.db.refresh(dataset)

        return {"dataset_id": str(dataset.id), "sample_count": len(mistakes)}

    def _create_audit_trail(
        self, company_id: str, agent_id: str, run_id: str, threshold: int
    ) -> None:
        """Create audit trail entry for auto-training trigger.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent ID.
            run_id: Training run ID.
            threshold: Threshold that was reached.
        """
        try:
            from app.services.audit_service import AuditService

            audit = AuditService(self.db)
            audit.log_event(
                company_id=company_id,
                event_type="auto_training_triggered",
                entity_type="agent",
                entity_id=agent_id,
                details={
                    "training_run_id": run_id,
                    "threshold": threshold,
                    "trigger": "auto_threshold",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as exc:
            logger.error(
                "audit_trail_creation_failed",
                extra={"error": str(exc)[:200]},
            )

    def _send_threshold_notification(
        self, company_id: str, agent_id: str, run_id: str
    ) -> None:
        """Send notification that threshold was reached.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent ID.
            run_id: Training run ID.
        """
        try:
            from app.services.notification_service import NotificationService

            notification_service = NotificationService(self.db)
            notification_service.create_notification(
                company_id=company_id,
                notification_type="training_triggered",
                title=f"Agent training triggered ({MISTAKE_THRESHOLD} mistakes)",
                message=f"Agent {agent_id[:8]} has reached the mistake threshold. "
                f"Training run {run_id[:8]} has been started automatically.",
                priority="high",
                related_entity_type="training_run",
                related_entity_id=run_id,
            )
        except Exception as exc:
            logger.error(
                "threshold_notification_failed",
                extra={"error": str(exc)[:200]},
            )
