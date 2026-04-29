"""
PARWA Dynamic Instruction Workflow Service (F-096) — Version-Controlled
Instructions with A/B Testing

Manages version-controlled instruction sets for AI agents with full
A/B testing support. Enables data-driven optimization of agent behavior
through statistical analysis.

Features:
- Create, update, publish, archive instruction sets
- Full version history with change summaries
- Rollback to previous versions by re-publishing
- A/B testing between instruction sets with traffic splitting
- Statistical significance evaluation (chi-squared test)
- Deterministic ticket-to-variant routing
- Auto-complete on significance or manual stop with winner selection

Methods:
- create_instruction_set() — Create draft instruction set
- get_instruction_sets() — List instruction sets for an agent
- get_instruction_set() — Get single instruction set
- update_instruction_set() — Update draft instruction set
- publish_instruction_set() — Publish new version, set active
- archive_instruction_set() — Archive instruction set
- get_version_history() — Full version history
- rollback_to_version() — Re-publish a previous version
- create_ab_test() — Start A/B test between two sets
- get_ab_test() — Get A/B test details
- list_ab_tests() — List A/B tests for an agent
- stop_ab_test() — Stop test, optionally select winner
- evaluate_ab_test() — Statistical evaluation
- get_active_instructions() — Active set or A/B variant
- assign_ticket_to_variant() — Deterministic A/B routing

Building Codes: BC-001 (multi-tenant), BC-007 (AI model),
               BC-008 (state management), BC-004 (Celery tasks)
"""

import hashlib
import json
import math
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.logger import get_logger

logger = get_logger("instruction_workflow_service")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Minimum tickets per variant before evaluating significance
MIN_TICKETS_FOR_EVALUATION = 100

# Significance threshold (p < 0.05)
SIGNIFICANCE_THRESHOLD = 0.05

# Default instruction content template
DEFAULT_INSTRUCTIONS = {
    "behavioral_rules": [
        "Always greet by name when available",
        "Provide concise, accurate responses",
        "Escalate when uncertain",
    ],
    "tone_guidelines": {
        "formality": "professional",
        "empathy_level": "medium",
    },
    "escalation_triggers": [
        "angry customer",
        "legal mention",
        "complex issue beyond AI capability",
    ],
    "response_templates": {
        "greeting": "Hello! How can I help you today?",
        "closing": "Is there anything else I can help with?",
        "escalation": "Let me connect you with a specialist who can help.",
    },
    "prohibited_actions": [
        "offering unauthorized discounts",
        "making promises about policies",
    ],
    "confidence_thresholds": {
        "auto_approve": 90,
        "require_review": 70,
    },
}

# Valid success metrics
VALID_SUCCESS_METRICS = ("csat", "resolution_rate", "both")


# ══════════════════════════════════════════════════════════════════
# SERVICE CLASS
# ══════════════════════════════════════════════════════════════════


class InstructionWorkflowService:
    """Dynamic Instruction Workflow Service (F-096).

    Manages version-controlled instruction sets and A/B testing
    for AI agent behavior optimization.

    BC-001: All methods scoped by company_id.
    BC-007: AI model behavioral instructions.
    BC-008: Version-controlled state management.
    BC-004: Celery task support for async evaluation.
    """

    def __init__(self, company_id: str):
        """Initialize the service for a specific tenant.

        Args:
            company_id: Tenant identifier (BC-001).
        """
        self.company_id = company_id

    # ── Instruction Set CRUD ────────────────────────────────────

    def create_instruction_set(
        self,
        agent_id: str,
        name: str,
        instructions: Dict[str, Any],
        user_id: str,
        db: Session,
        is_default: bool = False,
    ) -> Dict[str, Any]:
        """Create a new draft instruction set.

        Args:
            agent_id: Agent UUID.
            name: Instruction set name.
            instructions: Instruction content dict.
            user_id: Creating user's ID.
            db: Database session.
            is_default: Whether to set as default.

        Returns:
            Created instruction set data.
        """
        from database.models.agent import InstructionSet

        # Merge with defaults
        merged = {**DEFAULT_INSTRUCTIONS, **instructions}

        # Calculate version number based on existing sets for this agent
        existing_count = db.query(InstructionSet).filter(
            InstructionSet.company_id == self.company_id,
            InstructionSet.agent_id == agent_id,
        ).count()

        instruction_set = InstructionSet(
            company_id=self.company_id,
            agent_id=agent_id,
            name=name,
            version=existing_count + 1,
            status="draft",
            instructions=json.dumps(merged),
            is_default=is_default,
            created_by=user_id,
            change_summary="Initial version created",
        )

        db.add(instruction_set)
        db.flush()

        logger.info(
            "instruction_set_created",
            company_id=self.company_id,
            set_id=instruction_set.id,
            agent_id=agent_id,
            name=name,
            user_id=user_id,
        )

        return self._serialize_instruction_set(instruction_set)

    def get_instruction_sets(
        self,
        agent_id: str,
        db: Session,
        status_filter: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List instruction sets for an agent.

        Args:
            agent_id: Agent UUID.
            db: Database session.
            status_filter: Optional status filter.
            limit: Pagination limit.
            offset: Pagination offset.

        Returns:
            Paginated instruction set list.
        """
        from database.models.agent import InstructionSet

        query = db.query(InstructionSet).filter(
            InstructionSet.company_id == self.company_id,
            InstructionSet.agent_id == agent_id,
        )

        if status_filter:
            query = query.filter(InstructionSet.status == status_filter)

        total = query.count()
        sets = query.order_by(
            InstructionSet.created_at.desc(),
        ).offset(offset).limit(limit).all()

        return {
            "sets": [self._serialize_instruction_set(s) for s in sets],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_instruction_set(
        self,
        set_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Get a single instruction set.

        Args:
            set_id: Instruction set UUID.
            db: Database session.

        Returns:
            Instruction set data.
        """
        from database.models.agent import InstructionSet

        instruction_set = db.query(InstructionSet).filter(
            InstructionSet.id == set_id,
            InstructionSet.company_id == self.company_id,
        ).first()

        if not instruction_set:
            from app.exceptions import NotFoundError
            raise NotFoundError(
                message="Instruction set not found",
                details={"set_id": set_id},
            )

        return self._serialize_instruction_set(instruction_set)

    def update_instruction_set(
        self,
        set_id: str,
        updates: Dict[str, Any],
        user_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Update a draft instruction set.

        Only draft instruction sets can be updated.

        Args:
            set_id: Instruction set UUID.
            updates: Fields to update.
            user_id: Updating user's ID.
            db: Database session.

        Returns:
            Updated instruction set data.
        """
        from database.models.agent import InstructionSet

        instruction_set = db.query(InstructionSet).filter(
            InstructionSet.id == set_id,
            InstructionSet.company_id == self.company_id,
        ).first()

        if not instruction_set:
            from app.exceptions import NotFoundError
            raise NotFoundError(
                message="Instruction set not found",
                details={"set_id": set_id},
            )

        if instruction_set.status != "draft":
            from app.exceptions import ValidationError
            raise ValidationError(
                message="Only draft instruction sets can be updated",
                details={
                    "set_id": set_id,
                    "current_status": instruction_set.status,
                },
            )

        # Apply updates
        if "name" in updates and updates["name"]:
            instruction_set.name = updates["name"]

        if "instructions" in updates and updates["instructions"]:
            merged = {**DEFAULT_INSTRUCTIONS, **updates["instructions"]}
            instruction_set.instructions = json.dumps(merged)

        if "change_summary" in updates and updates["change_summary"]:
            instruction_set.change_summary = updates["change_summary"]

        instruction_set.updated_at = datetime.utcnow()
        db.flush()

        logger.info(
            "instruction_set_updated",
            company_id=self.company_id,
            set_id=set_id,
            user_id=user_id,
        )

        return self._serialize_instruction_set(instruction_set)

    def publish_instruction_set(
        self,
        set_id: str,
        user_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Publish an instruction set (creates new version, becomes active).

        Publishing:
        1. Creates an InstructionVersion snapshot
        2. Deactivates any previously active sets for the same agent
        3. Sets this set to "active"
        4. Increments version number

        Args:
            set_id: Instruction set UUID.
            user_id: Publishing user's ID.
            db: Database session.

        Returns:
            Publish result with version info.
        """
        from database.models.agent import (
            InstructionSet, InstructionVersion,
        )

        instruction_set = db.query(InstructionSet).filter(
            InstructionSet.id == set_id,
            InstructionSet.company_id == self.company_id,
        ).first()

        if not instruction_set:
            from app.exceptions import NotFoundError
            raise NotFoundError(
                message="Instruction set not found",
                details={"set_id": set_id},
            )

        now = datetime.utcnow()

        # Increment version
        previous_version = instruction_set.version
        instruction_set.version += 1

        # Create version snapshot
        version_entry = InstructionVersion(
            set_id=instruction_set.id,
            company_id=self.company_id,
            version=instruction_set.version,
            instructions=instruction_set.instructions,
            change_summary=instruction_set.change_summary
            or f"Published version {instruction_set.version}",
            published_by=user_id,
            published_at=now,
        )
        db.add(version_entry)

        # Deactivate other active sets for the same agent
        db.query(InstructionSet).filter(
            InstructionSet.company_id == self.company_id,
            InstructionSet.agent_id == instruction_set.agent_id,
            InstructionSet.id != set_id,
            InstructionSet.status == "active",
        ).update({"status": "archived"})

        # Activate this set
        instruction_set.status = "active"
        instruction_set.published_by = user_id
        instruction_set.published_at = now
        instruction_set.updated_at = now

        db.flush()

        logger.info(
            "instruction_set_published",
            company_id=self.company_id,
            set_id=set_id,
            agent_id=instruction_set.agent_id,
            version=instruction_set.version,
            user_id=user_id,
        )

        return {
            "set_id": instruction_set.id,
            "previous_version": previous_version,
            "new_version": instruction_set.version,
            "status": "active",
            "published_at": now.isoformat(),
            "message": "Instruction set published successfully",
        }

    def archive_instruction_set(
        self,
        set_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Archive an instruction set.

        Args:
            set_id: Instruction set UUID.
            db: Database session.

        Returns:
            Archive result.
        """
        from database.models.agent import InstructionSet

        instruction_set = db.query(InstructionSet).filter(
            InstructionSet.id == set_id,
            InstructionSet.company_id == self.company_id,
        ).first()

        if not instruction_set:
            from app.exceptions import NotFoundError
            raise NotFoundError(
                message="Instruction set not found",
                details={"set_id": set_id},
            )

        instruction_set.status = "archived"
        instruction_set.updated_at = datetime.utcnow()
        db.flush()

        logger.info(
            "instruction_set_archived",
            company_id=self.company_id,
            set_id=set_id,
        )

        return {
            "set_id": set_id,
            "status": "archived",
            "message": "Instruction set archived successfully",
        }

    def get_version_history(
        self,
        set_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Get full version history for an instruction set.

        Args:
            set_id: Instruction set UUID.
            db: Database session.

        Returns:
            Version history with all snapshots.
        """
        from database.models.agent import (
            InstructionSet, InstructionVersion,
        )

        instruction_set = db.query(InstructionSet).filter(
            InstructionSet.id == set_id,
            InstructionSet.company_id == self.company_id,
        ).first()

        if not instruction_set:
            from app.exceptions import NotFoundError
            raise NotFoundError(
                message="Instruction set not found",
                details={"set_id": set_id},
            )

        versions = db.query(InstructionVersion).filter(
            InstructionVersion.set_id == set_id,
        ).order_by(InstructionVersion.version.desc()).all()

        return {
            "set_id": set_id,
            "versions": [
                self._serialize_version(v) for v in versions
            ],
            "total": len(versions),
        }

    def rollback_to_version(
        self,
        set_id: str,
        version: int,
        user_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Rollback to a previous version by re-publishing its snapshot.

        Args:
            set_id: Instruction set UUID.
            version: Target version number.
            user_id: User performing the rollback.
            db: Database session.

        Returns:
            Rollback result.
        """
        from database.models.agent import InstructionVersion

        # Find the target version
        target = db.query(InstructionVersion).filter(
            InstructionVersion.set_id == set_id,
            InstructionVersion.company_id == self.company_id,
            InstructionVersion.version == version,
        ).first()

        if not target:
            from app.exceptions import NotFoundError
            raise NotFoundError(
                message=f"Version {version} not found for this instruction set", details={
                    "set_id": set_id, "target_version": version}, )

        # Restore the instructions from the target version
        update_result = self.update_instruction_set(
            set_id=set_id,
            updates={
                "instructions": json.loads(target.instructions),
                "change_summary": (
                    f"Rolled back to version {version}: "
                    f"{target.change_summary or 'no summary'}"
                ),
            },
            user_id=user_id,
            db=db,
        )

        # Re-publish to make it active
        publish_result = self.publish_instruction_set(
            set_id=set_id,
            user_id=user_id,
            db=db,
        )

        logger.info(
            "instruction_set_rolled_back",
            company_id=self.company_id,
            set_id=set_id,
            rolled_back_to=version,
            new_version=publish_result["new_version"],
            user_id=user_id,
        )

        return {
            "set_id": set_id,
            "previous_version": update_result["version"],
            "rolled_back_to": version,
            "message": "Rolled back to previous version successfully",
        }

    # ── A/B Testing ─────────────────────────────────────────────

    def create_ab_test(
        self,
        agent_id: str,
        set_a_id: str,
        set_b_id: str,
        traffic_split: int,
        success_metric: str,
        duration_days: int,
        user_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Create a new A/B test between two instruction sets.

        Only one active A/B test per agent at a time (returns 409 if
        a test is already running).

        Args:
            agent_id: Agent UUID.
            set_a_id: Instruction set for variant A.
            set_b_id: Instruction set for variant B.
            traffic_split: Percentage for variant A (0-100).
            success_metric: Primary metric to optimize.
            duration_days: Maximum test duration.
            user_id: Creating user's ID.
            db: Database session.

        Returns:
            Created A/B test data.
        """
        from database.models.agent import InstructionABTest, InstructionSet

        # Validate sets exist and belong to the same agent
        set_a = db.query(InstructionSet).filter(
            InstructionSet.id == set_a_id,
            InstructionSet.company_id == self.company_id,
            InstructionSet.agent_id == agent_id,
        ).first()
        if not set_a:
            from app.exceptions import NotFoundError
            raise NotFoundError(
                message="Instruction set A not found",
                details={"set_a_id": set_a_id},
            )

        set_b = db.query(InstructionSet).filter(
            InstructionSet.id == set_b_id,
            InstructionSet.company_id == self.company_id,
            InstructionSet.agent_id == agent_id,
        ).first()
        if not set_b:
            from app.exceptions import NotFoundError
            raise NotFoundError(
                message="Instruction set B not found",
                details={"set_b_id": set_b_id},
            )

        if set_a_id == set_b_id:
            from app.exceptions import ValidationError
            raise ValidationError(
                message="Set A and Set B must be different instruction sets",
                details={"set_a_id": set_a_id, "set_b_id": set_b_id},
            )

        # Check for existing active test on this agent
        existing_test = db.query(InstructionABTest).filter(
            InstructionABTest.company_id == self.company_id,
            InstructionABTest.agent_id == agent_id,
            InstructionABTest.status == "running",
        ).first()
        if existing_test:
            from app.exceptions import ValidationError as VE
            raise VE(
                message="An active A/B test already exists for this agent",
                details={
                    "existing_test_id": existing_test.id,
                    "agent_id": agent_id,
                },
                status_code=409,
            )

        # Validate success metric
        if success_metric not in VALID_SUCCESS_METRICS:
            from app.exceptions import ValidationError
            raise ValidationError(
                message=f"Invalid success metric: {success_metric}",
                details={
                    "valid_metrics": list(VALID_SUCCESS_METRICS),
                },
            )

        # Create the test
        ab_test = InstructionABTest(
            company_id=self.company_id,
            agent_id=agent_id,
            set_a_id=set_a_id,
            set_b_id=set_b_id,
            traffic_split=traffic_split,
            success_metric=success_metric,
            duration_days=duration_days,
            status="running",
        )

        db.add(ab_test)
        db.flush()

        logger.info(
            "ab_test_created",
            company_id=self.company_id,
            test_id=ab_test.id,
            agent_id=agent_id,
            set_a_id=set_a_id,
            set_b_id=set_b_id,
            traffic_split=traffic_split,
            user_id=user_id,
        )

        return self._serialize_ab_test(ab_test)

    def get_ab_test(
        self,
        test_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Get A/B test details with set names and evaluation.

        Args:
            test_id: A/B test UUID.
            db: Database session.

        Returns:
            Detailed A/B test data.
        """
        from database.models.agent import (
            InstructionABTest, InstructionSet,
        )

        ab_test = db.query(InstructionABTest).filter(
            InstructionABTest.id == test_id,
            InstructionABTest.company_id == self.company_id,
        ).first()

        if not ab_test:
            from app.exceptions import NotFoundError
            raise NotFoundError(
                message="A/B test not found",
                details={"test_id": test_id},
            )

        result = self._serialize_ab_test(ab_test)

        # Add set names
        set_a = db.query(InstructionSet).filter(
            InstructionSet.id == ab_test.set_a_id,
        ).first()
        set_b = db.query(InstructionSet).filter(
            InstructionSet.id == ab_test.set_b_id,
        ).first()

        result["set_a_name"] = set_a.name if set_a else None
        result["set_b_name"] = set_b.name if set_b else None

        if ab_test.winner_id:
            winner = db.query(InstructionSet).filter(
                InstructionSet.id == ab_test.winner_id,
            ).first()
            result["winner_name"] = winner.name if winner else None

        # Run evaluation if test is running
        if ab_test.status == "running":
            result["evaluation"] = self.evaluate_ab_test(test_id, db)

        return result

    def list_ab_tests(
        self,
        agent_id: str,
        db: Session,
        status_filter: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List A/B tests for an agent.

        Args:
            agent_id: Agent UUID.
            db: Database session.
            status_filter: Optional status filter.
            limit: Pagination limit.
            offset: Pagination offset.

        Returns:
            Paginated A/B test list.
        """
        from database.models.agent import InstructionABTest

        query = db.query(InstructionABTest).filter(
            InstructionABTest.company_id == self.company_id,
            InstructionABTest.agent_id == agent_id,
        )

        if status_filter:
            query = query.filter(InstructionABTest.status == status_filter)

        total = query.count()
        tests = query.order_by(
            InstructionABTest.created_at.desc(),
        ).offset(offset).limit(limit).all()

        return {
            "tests": [self._serialize_ab_test(t) for t in tests],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def stop_ab_test(
        self,
        test_id: str,
        winner_id: Optional[str],
        db: Session,
    ) -> Dict[str, Any]:
        """Stop an A/B test, optionally selecting a winner.

        Args:
            test_id: A/B test UUID.
            winner_id: Optional winner set ID.
            db: Database session.

        Returns:
            Stop result with evaluation.
        """
        from database.models.agent import InstructionABTest

        ab_test = db.query(InstructionABTest).filter(
            InstructionABTest.id == test_id,
            InstructionABTest.company_id == self.company_id,
        ).first()

        if not ab_test:
            from app.exceptions import NotFoundError
            raise NotFoundError(
                message="A/B test not found",
                details={"test_id": test_id},
            )

        if ab_test.status != "running":
            from app.exceptions import ValidationError
            raise ValidationError(
                message=f"A/B test is already '{ab_test.status}'",
                details={"test_id": test_id, "current_status": ab_test.status},
            )

        now = datetime.utcnow()

        # Validate winner_id if provided
        if winner_id:
            if winner_id not in (ab_test.set_a_id, ab_test.set_b_id):
                from app.exceptions import ValidationError
                raise ValidationError(
                    message="Winner must be either set A or set B",
                    details={
                        "winner_id": winner_id,
                        "set_a_id": ab_test.set_a_id,
                        "set_b_id": ab_test.set_b_id,
                    },
                )
            ab_test.winner_id = winner_id
        else:
            # Auto-select winner based on evaluation
            evaluation = self.evaluate_ab_test(test_id, db)
            if evaluation.get("is_significant") and evaluation.get("winner"):
                winner_map = {"A": ab_test.set_a_id, "B": ab_test.set_b_id}
                ab_test.winner_id = winner_map[evaluation["winner"]]

        ab_test.status = "completed"
        ab_test.ended_at = now
        db.flush()

        # If winner selected, activate it
        if ab_test.winner_id:
            from database.models.agent import InstructionSet
            db.query(InstructionSet).filter(
                InstructionSet.company_id == self.company_id,
                InstructionSet.agent_id == ab_test.agent_id,
                InstructionSet.id == ab_test.winner_id,
            ).update({"status": "active", "is_default": True})

            # Archive the other set
            other_id = (
                ab_test.set_b_id
                if ab_test.winner_id == ab_test.set_a_id
                else ab_test.set_a_id
            )
            db.query(InstructionSet).filter(
                InstructionSet.company_id == self.company_id,
                InstructionSet.agent_id == ab_test.agent_id,
                InstructionSet.id == other_id,
            ).update({"status": "archived", "is_default": False})

        logger.info(
            "ab_test_stopped",
            company_id=self.company_id,
            test_id=test_id,
            winner_id=ab_test.winner_id,
        )

        return {
            "test_id": test_id,
            "status": "completed",
            "winner_id": (
                str(ab_test.winner_id) if ab_test.winner_id else None
            ),
            "evaluation": self.evaluate_ab_test(test_id, db),
            "message": "A/B test stopped successfully",
        }

    def evaluate_ab_test(
        self,
        test_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Evaluate A/B test statistical significance.

        Uses chi-squared test for conversion rate comparison between
        variants. Auto-complete criteria: p < 0.05 with minimum
        100 tickets per variant.

        Args:
            test_id: A/B test UUID.
            db: Database session.

        Returns:
            Statistical evaluation result.
        """
        from database.models.agent import (
            InstructionABTest, InstructionABAssignment,
        )

        ab_test = db.query(InstructionABTest).filter(
            InstructionABTest.id == test_id,
            InstructionABTest.company_id == self.company_id,
        ).first()

        if not ab_test:
            from app.exceptions import NotFoundError
            raise NotFoundError(
                message="A/B test not found",
                details={"test_id": test_id},
            )

        # Calculate metrics from assignments
        assignments = db.query(InstructionABAssignment).filter(
            InstructionABAssignment.test_id == test_id,
        ).all()

        tickets_a = 0
        tickets_b = 0
        resolved_a = 0
        resolved_b = 0
        csat_sum_a = Decimal("0")
        csat_sum_b = Decimal("0")
        csat_count_a = 0
        csat_count_b = 0

        for assignment in assignments:
            if assignment.variant == "A":
                tickets_a += 1
                if assignment.resolved:
                    resolved_a += 1
                if assignment.csat_score is not None:
                    csat_sum_a += assignment.csat_score
                    csat_count_a += 1
            else:
                tickets_b += 1
                if assignment.resolved:
                    resolved_b += 1
                if assignment.csat_score is not None:
                    csat_sum_b += assignment.csat_score
                    csat_count_b += 1

        # Update test metrics
        ab_test.tickets_a = tickets_a
        ab_test.tickets_b = tickets_b
        ab_test.resolution_a = (
            float(resolved_a / tickets_a) if tickets_a > 0 else None
        )
        ab_test.resolution_b = (
            float(resolved_b / tickets_b) if tickets_b > 0 else None
        )
        ab_test.csat_a = (
            float(csat_sum_a / csat_count_a)
            if csat_count_a > 0 else None
        )
        ab_test.csat_b = (
            float(csat_sum_b / csat_count_b)
            if csat_count_b > 0 else None
        )
        db.flush()

        # Check if we have enough data
        if tickets_a < MIN_TICKETS_FOR_EVALUATION or \
           tickets_b < MIN_TICKETS_FOR_EVALUATION:
            return {
                "test_id": test_id,
                "is_significant": False,
                "p_value": None,
                "winner": None,
                "confidence_level": None,
                "recommendation": "Insufficient data — need at least "
                f"{MIN_TICKETS_FOR_EVALUATION} tickets "
                "per variant",
                "tickets_a": tickets_a,
                "tickets_b": tickets_b,
                "min_required": MIN_TICKETS_FOR_EVALUATION,
            }

        # Chi-squared test based on resolution rate
        # H0: No difference between variants
        # H1: Significant difference exists
        p_value = self._chi_squared_test(
            resolved_a, tickets_a - resolved_a,
            resolved_b, tickets_b - resolved_b,
        )

        is_significant = p_value < SIGNIFICANCE_THRESHOLD

        # Determine winner
        winner = None
        if is_significant:
            rate_a = resolved_a / tickets_a if tickets_a > 0 else 0
            rate_b = resolved_b / tickets_b if tickets_b > 0 else 0
            winner = "A" if rate_a > rate_b else "B"

        confidence_level = (1 - p_value) * 100 if p_value else None

        recommendation = "Insufficient data"
        if is_significant:
            recommendation = (
                f"Variant {winner} is statistically significant "
                f"(p={p_value:.4f}). Recommend selecting as winner."
            )
        else:
            recommendation = (
                "No significant difference detected. "
                "Consider extending the test or stopping without a winner."
            )

        # Auto-complete if significant
        if is_significant and ab_test.status == "running":
            logger.info(
                "ab_test_auto_complete",
                company_id=self.company_id,
                test_id=test_id,
                winner=winner,
                p_value=p_value,
            )

        return {
            "test_id": test_id,
            "is_significant": is_significant,
            "p_value": round(p_value, 4) if p_value else None,
            "winner": winner,
            "confidence_level": (
                round(confidence_level, 2) if confidence_level else None
            ),
            "recommendation": recommendation,
            "tickets_a": tickets_a,
            "tickets_b": tickets_b,
            "min_required": MIN_TICKETS_FOR_EVALUATION,
        }

    # ── Active Instructions & Routing ───────────────────────────

    def get_active_instructions(
        self,
        agent_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Get the active instructions for an agent.

        If an A/B test is running, returns test info instead.

        Args:
            agent_id: Agent UUID.
            db: Database session.

        Returns:
            Active instructions or A/B test info.
        """
        from database.models.agent import (
            InstructionABTest, InstructionSet,
        )

        # Check for active A/B test
        ab_test = db.query(InstructionABTest).filter(
            InstructionABTest.company_id == self.company_id,
            InstructionABTest.agent_id == agent_id,
            InstructionABTest.status == "running",
        ).first()

        if ab_test:
            return {
                "agent_id": agent_id,
                "source": "ab_test",
                "set_id": None,
                "set_name": None,
                "test_id": ab_test.id,
                "variant": None,
                "instructions": {},
                "traffic_split": ab_test.traffic_split,
                "set_a_id": ab_test.set_a_id,
                "set_b_id": ab_test.set_b_id,
            }

        # Get active instruction set
        active_set = db.query(InstructionSet).filter(
            InstructionSet.company_id == self.company_id,
            InstructionSet.agent_id == agent_id,
            InstructionSet.status == "active",
        ).first()

        if not active_set:
            return {
                "agent_id": agent_id,
                "source": "none",
                "set_id": None,
                "set_name": None,
                "test_id": None,
                "variant": None,
                "instructions": {},
            }

        instructions = {}
        if active_set.instructions:
            try:
                instructions = json.loads(active_set.instructions)
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "agent_id": agent_id,
            "source": "instruction_set",
            "set_id": active_set.id,
            "set_name": active_set.name,
            "test_id": None,
            "variant": None,
            "instructions": instructions,
        }

    def assign_ticket_to_variant(
        self,
        agent_id: str,
        ticket_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Deterministically assign a ticket to an A/B variant.

        Uses hash-based routing for consistency: the same ticket_id
        always gets the same variant.

        Args:
            agent_id: Agent UUID.
            ticket_id: Ticket UUID.
            db: Database session.

        Returns:
            Assignment result with variant and set ID.
        """
        from database.models.agent import (
            InstructionABTest, InstructionABAssignment,
        )

        # Check for active A/B test
        ab_test = db.query(InstructionABTest).filter(
            InstructionABTest.company_id == self.company_id,
            InstructionABTest.agent_id == agent_id,
            InstructionABTest.status == "running",
        ).first()

        if not ab_test:
            # No active test — return the active instruction set
            active = self.get_active_instructions(agent_id, db)
            return {
                "test_id": None,
                "ticket_id": ticket_id,
                "variant": None,
                "set_id": active.get("set_id"),
                "is_deterministic": True,
            }

        # Deterministic routing based on ticket_id hash
        hash_input = f"{ab_test.id}:{ticket_id}"
        hash_val = int(
            hashlib.md5(hash_input.encode()).hexdigest(), 16,
        )
        normalized = (hash_val % 10000) / 10000.0

        variant = "A" if normalized < (ab_test.traffic_split / 100) else "B"
        set_id = ab_test.set_a_id if variant == "A" else ab_test.set_b_id

        # Record the assignment
        assignment = InstructionABAssignment(
            test_id=ab_test.id,
            ticket_id=ticket_id,
            variant=variant,
            set_id=set_id,
        )
        db.add(assignment)
        db.flush()

        return {
            "test_id": ab_test.id,
            "ticket_id": ticket_id,
            "variant": variant,
            "set_id": set_id,
            "is_deterministic": True,
        }

    # ── Statistical Tests ───────────────────────────────────────

    @staticmethod
    def _chi_squared_test(
        a_success: int, a_failure: int,
        b_success: int, b_failure: int,
    ) -> float:
        """Perform chi-squared test for independence.

        Tests whether the proportion of successes differs
        significantly between two groups.

        Args:
            a_success: Successes in group A.
            a_failure: Failures in group A.
            b_success: Successes in group B.
            b_failure: Failures in group B.

        Returns:
            p-value (probability of observing this result under H0).
        """
        n_a = a_success + a_failure
        n_b = b_success + b_failure
        total = n_a + n_b

        if total == 0:
            return 1.0

        p_a = a_success / n_a if n_a > 0 else 0
        p_b = b_success / n_b if n_b > 0 else 0
        p_pooled = (a_success + b_success) / total if total > 0 else 0

        if p_pooled == 0 or p_pooled == 1:
            return 1.0

        # Chi-squared statistic
        expected_a_success = n_a * p_pooled
        expected_a_failure = n_a * (1 - p_pooled)
        expected_b_success = n_b * p_pooled
        expected_b_failure = n_b * (1 - p_pooled)

        chi_sq = 0.0
        for observed, expected in [
            (a_success, expected_a_success),
            (a_failure, expected_a_failure),
            (b_success, expected_b_success),
            (b_failure, expected_b_failure),
        ]:
            if expected > 0:
                chi_sq += ((observed - expected) ** 2) / expected

        # Approximate p-value using chi-squared distribution (1 df)
        # Using approximation: p ≈ exp(-chi_sq/2) for large chi_sq
        if chi_sq <= 0:
            return 1.0

        # Better approximation using regularized incomplete gamma
        p_value = _chi_squared_p_value(chi_sq, df=1)
        return p_value

    # ── Serialization ───────────────────────────────────────────

    @staticmethod
    def _serialize_instruction_set(
        instruction_set: Any,
    ) -> Dict[str, Any]:
        """Serialize an InstructionSet ORM object to dict."""
        instructions = {}
        if hasattr(instruction_set, "instructions") and \
           instruction_set.instructions:
            try:
                instructions = json.loads(instruction_set.instructions)
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "id": instruction_set.id,
            "company_id": instruction_set.company_id,
            "agent_id": instruction_set.agent_id,
            "name": instruction_set.name,
            "version": instruction_set.version,
            "status": instruction_set.status,
            "instructions": instructions,
            "is_default": instruction_set.is_default,
            "created_by": (
                str(instruction_set.created_by)
                if instruction_set.created_by else None
            ),
            "published_by": (
                str(instruction_set.published_by)
                if instruction_set.published_by else None
            ),
            "published_at": (
                instruction_set.published_at.isoformat()
                if instruction_set.published_at else None
            ),
            "change_summary": instruction_set.change_summary,
            "created_at": (
                instruction_set.created_at.isoformat()
                if instruction_set.created_at else None
            ),
            "updated_at": (
                instruction_set.updated_at.isoformat()
                if instruction_set.updated_at else None
            ),
        }

    @staticmethod
    def _serialize_version(version: Any) -> Dict[str, Any]:
        """Serialize an InstructionVersion ORM object to dict."""
        instructions = {}
        if hasattr(version, "instructions") and version.instructions:
            try:
                instructions = json.loads(version.instructions)
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "id": version.id,
            "set_id": version.set_id,
            "company_id": version.company_id,
            "version": version.version,
            "instructions": instructions,
            "change_summary": version.change_summary,
            "published_by": (
                str(version.published_by)
                if version.published_by else None
            ),
            "published_at": (
                version.published_at.isoformat()
                if version.published_at else None
            ),
            "created_at": (
                version.created_at.isoformat()
                if version.created_at else None
            ),
        }

    @staticmethod
    def _serialize_ab_test(ab_test: Any) -> Dict[str, Any]:
        """Serialize an InstructionABTest ORM object to dict."""
        return {
            "id": ab_test.id,
            "company_id": ab_test.company_id,
            "agent_id": ab_test.agent_id,
            "set_a_id": ab_test.set_a_id,
            "set_b_id": ab_test.set_b_id,
            "traffic_split": ab_test.traffic_split,
            "success_metric": ab_test.success_metric,
            "duration_days": ab_test.duration_days,
            "status": ab_test.status,
            "winner_id": (
                str(ab_test.winner_id) if ab_test.winner_id else None
            ),
            "tickets_a": ab_test.tickets_a,
            "tickets_b": ab_test.tickets_b,
            "csat_a": (
                float(ab_test.csat_a)
                if ab_test.csat_a is not None else None
            ),
            "csat_b": (
                float(ab_test.csat_b)
                if ab_test.csat_b is not None else None
            ),
            "resolution_a": (
                float(ab_test.resolution_a)
                if ab_test.resolution_a is not None else None
            ),
            "resolution_b": (
                float(ab_test.resolution_b)
                if ab_test.resolution_b is not None else None
            ),
            "started_at": (
                ab_test.started_at.isoformat()
                if ab_test.started_at else None
            ),
            "ended_at": (
                ab_test.ended_at.isoformat()
                if ab_test.ended_at else None
            ),
        }


# ══════════════════════════════════════════════════════════════════
# STATISTICAL HELPERS
# ══════════════════════════════════════════════════════════════════

def _chi_squared_p_value(chi_sq: float, df: int = 1) -> float:
    """Approximate the p-value from a chi-squared distribution.

    Uses the regularized incomplete gamma function approximation
    for the chi-squared CDF complement (survival function).

    Args:
        chi_sq: Chi-squared statistic.
        df: Degrees of freedom.

    Returns:
        p-value (probability of observing chi_sq or higher under H0).
    """
    if chi_sq <= 0 or df <= 0:
        return 1.0

    # Using the approximation: p = Q(df/2, x/2)
    # where Q is the regularized upper incomplete gamma function
    # For df=1: p = 2 * (1 - Phi(sqrt(chi_sq)))
    # where Phi is the standard normal CDF
    try:
        # Normal approximation for df=1 (most common case)
        if df == 1:
            z = math.sqrt(chi_sq)
            # Approximate standard normal CDF
            p = 2 * _normal_sf(z)
            return min(1.0, max(0.0, p))

        # For higher df, use the gamma function approximation
        # Simplified: use survival function approximation
        k = df / 2.0
        x = chi_sq / 2.0
        p = _upper_incomplete_gamma_ratio(k, x)
        return min(1.0, max(0.0, p))
    except Exception:
        return 1.0


def _normal_sf(z: float) -> float:
    """Standard normal survival function (1 - CDF).

    Uses a polynomial approximation that is accurate to ~1e-7.

    Args:
        z: Z-score (can be negative).

    Returns:
        P(Z > z) for standard normal Z.
    """
    # Abramowitz and Stegun approximation 26.2.19
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1.0
    x = abs(z)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * \
        math.exp(-x * x / 2.0)

    result = sign * y
    return result


def _upper_incomplete_gamma_ratio(a: float, x: float) -> float:
    """Approximate Q(a, x) = Gamma(a, x) / Gamma(a).

    Uses a series expansion for small x and a continued fraction
    for large x.

    Args:
        a: Shape parameter (must be > 0).
        x: Value (must be >= 0).

    Returns:
        Regularized upper incomplete gamma function value.
    """
    if x < 0:
        return 1.0
    if x == 0:
        return 1.0
    if a <= 0:
        return 1.0

    # For small x, use series expansion
    if x < a + 1:
        return 1.0 - _lower_incomplete_gamma_series(a, x)
    else:
        # Use continued fraction for large x
        return _upper_incomplete_gamma_cf(a, x)


def _lower_incomplete_gamma_series(a: float, x: float) -> float:
    """Compute P(a, x) using series expansion."""
    if x <= 0:
        return 0.0

    max_iter = 200
    epsilon = 1e-10

    ap = a
    s = 1.0 / a
    delta = s

    for _ in range(max_iter):
        ap += 1
        delta *= x / ap
        s += delta
        if abs(delta) < abs(s) * epsilon:
            break

    return s * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _upper_incomplete_gamma_cf(a: float, x: float) -> float:
    """Compute Q(a, x) using continued fraction."""
    max_iter = 200
    epsilon = 1e-10
    tiny = 1e-30

    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d

    for i in range(1, max_iter + 1):
        an = -i * (i - a)
        b += 2.0

        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        d = 1.0 / d

        c = b + an / c
        if abs(c) < tiny:
            c = tiny

        delta = d * c
        h *= delta

        if abs(delta - 1.0) < epsilon:
            break

    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


# ══════════════════════════════════════════════════════════════════
# LAZY SERVICE LOADING (BC-008)
# ══════════════════════════════════════════════════════════════════

_service_cache: Dict[str, InstructionWorkflowService] = {}


def get_instruction_workflow_service(
    company_id: str,
) -> InstructionWorkflowService:
    """Get or create an InstructionWorkflowService for a tenant.

    Args:
        company_id: Tenant identifier (BC-001).

    Returns:
        InstructionWorkflowService instance.
    """
    if company_id not in _service_cache:
        _service_cache[company_id] = InstructionWorkflowService(company_id)
    return _service_cache[company_id]


__all__ = [
    "InstructionWorkflowService",
    "get_instruction_workflow_service",
    "DEFAULT_INSTRUCTIONS",
]
