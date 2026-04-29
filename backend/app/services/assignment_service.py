"""
PARWA Assignment Service - Score-Based Ticket Assignment (Day 28)

Implements F-050: Ticket assignment with:
- Rule-based routing: category → department → agent pool → round-robin
- Assignment rules engine with conditions and actions
- Score-based assignment (AI stub for Week 9)
- Auto-assignment on ticket create
- Manual reassignment support

BC-001: All queries are tenant-isolated via company_id.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc
from sqlalchemy.orm import Session

from database.models.tickets import (
    Ticket,
    TicketAssignment,
    AssignmentRule,
    TicketStatus,
)
from database.models.core import User
from app.exceptions import NotFoundError, ValidationError


class AssigneeType:
    """Assignee type constants."""

    AI = "ai"
    HUMAN = "human"
    SYSTEM = "system"


class AssignmentService:
    """Score-based ticket assignment service.

    Week 4: Rule-based assignment with round-robin.
    Week 9: Will be enhanced with AI scoring.
    """

    # Default assignment rules
    DEFAULT_RULES = [
        {
            "name": "Critical to Senior Agent",
            "conditions": {"priority": ["critical"]},
            "action": {"assign_to_pool": "senior", "assignee_type": "human"},
            "priority_order": 1,
        },
        {
            "name": "Billing to Finance Team",
            "conditions": {"category": ["billing", "refund"]},
            "action": {"assign_to_pool": "billing", "assignee_type": "human"},
            "priority_order": 10,
        },
        {
            "name": "Technical to Tech Support",
            "conditions": {"category": ["tech_support", "technical"]},
            "action": {"assign_to_pool": "technical", "assignee_type": "human"},
            "priority_order": 20,
        },
        {
            "name": "Feature Requests to Product",
            "conditions": {"category": ["feature_request"]},
            "action": {"assign_to_pool": "product", "assignee_type": "human"},
            "priority_order": 30,
        },
        {
            "name": "Complaints to Customer Success",
            "conditions": {"category": ["complaint"]},
            "action": {"assign_to_pool": "customer_success", "assignee_type": "human"},
            "priority_order": 5,
        },
        {
            "name": "Default to AI Agent",
            "conditions": {},
            "action": {"assign_to_pool": "ai", "assignee_type": "ai"},
            "priority_order": 100,
        },
    ]

    # Max rules per company
    MAX_RULES_PER_COMPANY = 50

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    # ── AUTO ASSIGNMENT ─────────────────────────────────────────────────────

    def auto_assign(
        self,
        ticket_id: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Auto-assign a ticket based on rules.

        Args:
            ticket_id: Ticket ID to assign
            user_id: User triggering assignment

        Returns:
            Assignment result with assignee and rule matched

        Raises:
            NotFoundError: If ticket not found
        """
        # Get ticket
        ticket = (
            self.db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == self.company_id,
            )
            .first()
        )

        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        # Get all active rules, sorted by priority
        rules = (
            self.db.query(AssignmentRule)
            .filter(
                AssignmentRule.company_id == self.company_id,
                AssignmentRule.is_active,
            )
            .order_by(AssignmentRule.priority_order)
            .all()
        )

        # If no rules, create defaults
        if not rules:
            rules = self._create_default_rules()

        # Find matching rule
        matched_rule = None
        for rule in rules:
            if self._rule_matches(rule, ticket):
                matched_rule = rule
                break

        if not matched_rule:
            # Should not happen as DEFAULT_RULES has a catch-all
            return {
                "ticket_id": ticket_id,
                "assigned": False,
                "reason": "No matching rule found",
            }

        # Execute rule action
        action = (
            json.loads(matched_rule.action)
            if isinstance(matched_rule.action, str)
            else matched_rule.action
        )

        assignee_id, assignee_type = self._execute_action(action, ticket)

        # Create assignment record
        assignment = TicketAssignment(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            company_id=self.company_id,
            assignee_type=assignee_type,
            assignee_id=assignee_id,
            reason=f"Auto-assigned by rule: {matched_rule.name}",
            assigned_at=datetime.now(timezone.utc),
        )
        self.db.add(assignment)

        # Update ticket
        ticket.assigned_to = assignee_id
        if ticket.status == TicketStatus.open.value:
            ticket.status = TicketStatus.assigned.value
        ticket.updated_at = datetime.now(timezone.utc)

        self.db.commit()

        return {
            "ticket_id": ticket_id,
            "assigned": True,
            "assignee_id": assignee_id,
            "assignee_type": assignee_type,
            "rule_id": matched_rule.id,
            "rule_name": matched_rule.name,
        }

    def get_assignment_scores(
        self,
        ticket_id: str,
        use_ai_scoring: bool = True,
    ) -> Dict[str, Any]:
        """Get assignment scores for all candidates.

        Uses real 5-factor AI scoring algorithm:
        1. Expertise Match (40 pts) - Category/intent matches agent specialty
        2. Workload Balance (30 pts) - Fewer open tickets = higher score
        3. Performance History (20 pts) - Resolution rate, CSAT, confidence
        4. Response Time History (15 pts) - SLA compliance rate
        5. Availability (10 pts) - Online/active status

        Args:
            ticket_id: Ticket ID
            use_ai_scoring: Use AI scoring (default True). False falls back to rule-based.

        Returns:
            Dict with candidate scores and recommendation
        """
        # Get ticket for validation
        ticket = (
            self.db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == self.company_id,
            )
            .first()
        )

        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        if use_ai_scoring:
            # Use real AI scoring
            try:
                from app.services.assignment_scoring_service import (
                    get_assignment_scoring_service,
                )

                scoring_svc = get_assignment_scoring_service(self.db, self.company_id)
                return scoring_svc.calculate_scores(ticket_id)
            except Exception as exc:
                # Fall back to rule-based on error
                import logging

                logging.getLogger(__name__).warning(
                    f"AI scoring failed, falling back to rule-based: {exc}"
                )

        # Rule-based fallback (legacy)
        agents = self._get_available_agents()

        scores = {}
        for agent in agents:
            score = self._calculate_agent_score(agent, ticket)
            scores[agent.id] = {
                "user_id": agent.id,
                "name": getattr(agent, "full_name", None) or agent.email,
                "score": score,
                "current_tickets": self._get_agent_ticket_count(agent.id),
            }

        sorted_candidates = sorted(
            scores.values(),
            key=lambda x: x["score"],
            reverse=True,
        )

        best_match = sorted_candidates[0] if sorted_candidates else None

        return {
            "ticket_id": ticket_id,
            "candidates": sorted_candidates,
            "recommended_assignee": best_match,
            "scoring_method": "rule-based",
        }

    # ── RULE MANAGEMENT ─────────────────────────────────────────────────────

    def create_rule(
        self,
        name: str,
        conditions: Dict[str, Any],
        action: Dict[str, Any],
        priority_order: int = 0,
        is_active: bool = True,
    ) -> AssignmentRule:
        """Create an assignment rule.

        Args:
            name: Rule name
            conditions: Condition filters (category, priority, channel)
            action: Action to take (assign_to_pool, assign_to_user)
            priority_order: Order of evaluation (lower = higher priority)
            is_active: Whether rule is active

        Returns:
            Created AssignmentRule

        Raises:
            ValidationError: If max rules exceeded or invalid conditions
        """
        # Check max rules
        current_count = (
            self.db.query(AssignmentRule)
            .filter(
                AssignmentRule.company_id == self.company_id,
            )
            .count()
        )

        if current_count >= self.MAX_RULES_PER_COMPANY:
            raise ValidationError(f"Maximum {
                    self.MAX_RULES_PER_COMPANY} rules allowed per company")

        # Validate conditions
        self._validate_conditions(conditions)

        # Validate action
        self._validate_action(action)

        rule = AssignmentRule(
            id=str(uuid.uuid4()),
            company_id=self.company_id,
            name=name,
            conditions=json.dumps(conditions),
            action=json.dumps(action),
            priority_order=priority_order,
            is_active=is_active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)

        return rule

    def update_rule(
        self,
        rule_id: str,
        name: Optional[str] = None,
        conditions: Optional[Dict[str, Any]] = None,
        action: Optional[Dict[str, Any]] = None,
        priority_order: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> AssignmentRule:
        """Update an assignment rule.

        Args:
            rule_id: Rule ID
            name: New name
            conditions: New conditions
            action: New action
            priority_order: New priority order
            is_active: New active status

        Returns:
            Updated AssignmentRule

        Raises:
            NotFoundError: If rule not found
            ValidationError: If invalid conditions/action
        """
        rule = (
            self.db.query(AssignmentRule)
            .filter(
                AssignmentRule.id == rule_id,
                AssignmentRule.company_id == self.company_id,
            )
            .first()
        )

        if not rule:
            raise NotFoundError(f"Rule {rule_id} not found")

        if name is not None:
            rule.name = name

        if conditions is not None:
            self._validate_conditions(conditions)
            rule.conditions = json.dumps(conditions)

        if action is not None:
            self._validate_action(action)
            rule.action = json.dumps(action)

        if priority_order is not None:
            rule.priority_order = priority_order

        if is_active is not None:
            rule.is_active = is_active

        rule.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(rule)

        return rule

    def delete_rule(
        self,
        rule_id: str,
    ) -> bool:
        """Delete an assignment rule.

        Args:
            rule_id: Rule ID

        Returns:
            True if deleted

        Raises:
            NotFoundError: If rule not found
        """
        rule = (
            self.db.query(AssignmentRule)
            .filter(
                AssignmentRule.id == rule_id,
                AssignmentRule.company_id == self.company_id,
            )
            .first()
        )

        if not rule:
            raise NotFoundError(f"Rule {rule_id} not found")

        self.db.delete(rule)
        self.db.commit()

        return True

    def list_rules(
        self,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        """List all assignment rules.

        Args:
            include_inactive: Include inactive rules

        Returns:
            List of rules
        """
        query = self.db.query(AssignmentRule).filter(
            AssignmentRule.company_id == self.company_id,
        )

        if not include_inactive:
            query = query.filter(AssignmentRule.is_active)

        rules = query.order_by(AssignmentRule.priority_order).all()

        results = []
        for rule in rules:
            results.append(
                {
                    "id": rule.id,
                    "name": rule.name,
                    "conditions": (
                        json.loads(rule.conditions)
                        if isinstance(rule.conditions, str)
                        else rule.conditions
                    ),
                    "action": (
                        json.loads(rule.action)
                        if isinstance(rule.action, str)
                        else rule.action
                    ),
                    "priority_order": rule.priority_order,
                    "is_active": rule.is_active,
                    "created_at": (
                        rule.created_at.isoformat() if rule.created_at else None
                    ),
                    "updated_at": (
                        rule.updated_at.isoformat() if rule.updated_at else None
                    ),
                }
            )

        return results

    # ── MANUAL ASSIGNMENT ───────────────────────────────────────────────────

    def assign_to_user(
        self,
        ticket_id: str,
        assignee_id: str,
        reason: Optional[str] = None,
        assigned_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Manually assign ticket to a specific user.

        Args:
            ticket_id: Ticket ID
            assignee_id: User ID to assign to
            reason: Reason for assignment
            assigned_by: User ID making assignment

        Returns:
            Assignment result

        Raises:
            NotFoundError: If ticket or user not found
        """
        # Get ticket
        ticket = (
            self.db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == self.company_id,
            )
            .first()
        )

        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        # Verify user exists and is in same company
        user = (
            self.db.query(User)
            .filter(
                User.id == assignee_id,
                User.company_id == self.company_id,
            )
            .first()
        )

        if not user:
            raise NotFoundError(f"User {assignee_id} not found in company")

        previous_assignee = ticket.assigned_to

        # Create assignment record
        assignment = TicketAssignment(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            company_id=self.company_id,
            assignee_type=AssigneeType.HUMAN,
            assignee_id=assignee_id,
            reason=reason or "Manual assignment",
            assigned_at=datetime.now(timezone.utc),
        )
        self.db.add(assignment)

        # Update ticket
        ticket.assigned_to = assignee_id
        if ticket.status == TicketStatus.open.value:
            ticket.status = TicketStatus.assigned.value
        ticket.updated_at = datetime.now(timezone.utc)

        self.db.commit()

        return {
            "ticket_id": ticket_id,
            "previous_assignee": previous_assignee,
            "new_assignee": assignee_id,
            "assigned_at": ticket.updated_at.isoformat(),
        }

    def unassign(
        self,
        ticket_id: str,
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Unassign a ticket.

        Args:
            ticket_id: Ticket ID
            reason: Reason for unassignment
            user_id: User ID performing unassignment

        Returns:
            Unassignment result

        Raises:
            NotFoundError: If ticket not found
        """
        ticket = (
            self.db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == self.company_id,
            )
            .first()
        )

        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        previous_assignee = ticket.assigned_to

        # Create unassignment record
        assignment = TicketAssignment(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            company_id=self.company_id,
            assignee_type=AssigneeType.HUMAN,
            assignee_id=None,
            reason=reason or "Unassigned",
            assigned_at=datetime.now(timezone.utc),
        )
        self.db.add(assignment)

        # Update ticket
        ticket.assigned_to = None
        ticket.status = TicketStatus.open.value
        ticket.updated_at = datetime.now(timezone.utc)

        self.db.commit()

        return {
            "ticket_id": ticket_id,
            "previous_assignee": previous_assignee,
            "unassigned": True,
        }

    # ── ASSIGNMENT HISTORY ──────────────────────────────────────────────────

    def get_assignment_history(
        self,
        ticket_id: str,
    ) -> List[Dict[str, Any]]:
        """Get assignment history for a ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            List of assignment records
        """
        assignments = (
            self.db.query(TicketAssignment)
            .filter(
                TicketAssignment.ticket_id == ticket_id,
                TicketAssignment.company_id == self.company_id,
            )
            .order_by(desc(TicketAssignment.assigned_at))
            .all()
        )

        results = []
        for a in assignments:
            results.append(
                {
                    "id": a.id,
                    "assignee_type": a.assignee_type,
                    "assignee_id": a.assignee_id,
                    "reason": a.reason,
                    "score": float(a.score) if a.score else None,
                    "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
                }
            )

        return results

    # ── PRIVATE HELPERS ─────────────────────────────────────────────────────

    def _create_default_rules(self) -> List[AssignmentRule]:
        """Create default assignment rules for company."""
        rules = []
        for rule_data in self.DEFAULT_RULES:
            rule = AssignmentRule(
                id=str(uuid.uuid4()),
                company_id=self.company_id,
                name=rule_data["name"],
                conditions=json.dumps(rule_data["conditions"]),
                action=json.dumps(rule_data["action"]),
                priority_order=rule_data["priority_order"],
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.db.add(rule)
            rules.append(rule)

        self.db.commit()
        return rules

    def _rule_matches(self, rule: AssignmentRule, ticket: Ticket) -> bool:
        """Check if a rule matches a ticket.

        Args:
            rule: Assignment rule
            ticket: Ticket to check

        Returns:
            True if rule matches
        """
        conditions = (
            json.loads(rule.conditions)
            if isinstance(rule.conditions, str)
            else rule.conditions
        )

        if not conditions:
            # Empty conditions = match all (catch-all rule)
            return True

        # Check priority condition
        if "priority" in conditions:
            priorities = conditions["priority"]
            if isinstance(priorities, str):
                priorities = [priorities]
            if ticket.priority not in priorities:
                return False

        # Check category condition
        if "category" in conditions:
            categories = conditions["category"]
            if isinstance(categories, str):
                categories = [categories]
            if ticket.category not in categories:
                return False

        # Check channel condition
        if "channel" in conditions:
            channels = conditions["channel"]
            if isinstance(channels, str):
                channels = [channels]
            if ticket.channel not in channels:
                return False

        # Check status condition
        if "status" in conditions:
            statuses = conditions["status"]
            if isinstance(statuses, str):
                statuses = [statuses]
            if ticket.status not in statuses:
                return False

        return True

    def _execute_action(
        self,
        action: Dict[str, Any],
        ticket: Ticket,
    ) -> Tuple[Optional[str], str]:
        """Execute assignment action.

        Args:
            action: Action configuration
            ticket: Ticket being assigned

        Returns:
            Tuple of (assignee_id, assignee_type)
        """
        assignee_type = action.get("assignee_type", AssigneeType.HUMAN)

        # Direct user assignment
        if "assign_to_user" in action:
            return action["assign_to_user"], assignee_type

        # Pool-based assignment (round-robin)
        if "assign_to_pool" in action:
            pool = action["assign_to_pool"]

            if pool == "ai":
                # AI assignment - return None for now (AI agent ID would be
                # configured)
                return None, AssigneeType.AI

            # Get agents in pool and assign round-robin
            agent = self._get_next_agent_in_pool(pool)
            if agent:
                return agent.id, assignee_type

        # No specific assignment - return None
        return None, assignee_type

    def _get_available_agents(self) -> List[User]:
        """Get all available agents for assignment."""
        return (
            self.db.query(User)
            .filter(
                User.company_id == self.company_id,
                User.is_active,
            )
            .all()
        )

    def _get_next_agent_in_pool(self, pool: str) -> Optional[User]:
        """Get next agent in pool using round-robin.

        Args:
            pool: Pool name (senior, billing, technical, etc.)

        Returns:
            Next agent or None
        """
        # In a real implementation, this would use agent pools/teams
        # For now, we use round-robin across all agents

        agents = self._get_available_agents()
        if not agents:
            return None

        # Get agent with least current tickets (simplest load balancing)
        agent_counts = {}
        for agent in agents:
            agent_counts[agent.id] = self._get_agent_ticket_count(agent.id)

        # Return agent with lowest count
        return min(agents, key=lambda a: agent_counts.get(a.id, 0))

    def _get_agent_ticket_count(self, agent_id: str) -> int:
        """Get current open ticket count for an agent.

        Args:
            agent_id: Agent user ID

        Returns:
            Count of open tickets
        """
        return (
            self.db.query(Ticket)
            .filter(
                Ticket.company_id == self.company_id,
                Ticket.assigned_to == agent_id,
                Ticket.status.in_(
                    [
                        TicketStatus.open.value,
                        TicketStatus.assigned.value,
                        TicketStatus.in_progress.value,
                        TicketStatus.awaiting_client.value,
                    ]
                ),
            )
            .count()
        )

    def _calculate_agent_score(self, agent: User, ticket: Ticket) -> float:
        """Calculate assignment score for an agent.

        Week 4: Rule-based scoring.
        Week 9: Will use AI scoring.

        Args:
            agent: Agent user
            ticket: Ticket to assign

        Returns:
            Score between 0 and 1
        """
        score = 0.5  # Base score

        # Factor: current workload (lower is better)
        ticket_count = self._get_agent_ticket_count(agent.id)
        workload_factor = max(0, 1 - (ticket_count / 20))  # Max 20 tickets
        score += workload_factor * 0.3

        # Factor: match ticket category with agent skills (would need skill model)
        # For now, use random factor
        score += 0.2

        return min(score, 1.0)

    def _validate_conditions(self, conditions: Dict[str, Any]) -> None:
        """Validate rule conditions.

        Args:
            conditions: Conditions to validate

        Raises:
            ValidationError: If invalid conditions
        """
        valid_keys = {"priority", "category", "channel", "status"}

        for key in conditions:
            if key not in valid_keys:
                raise ValidationError(f"Invalid condition key: {key}")

    def _validate_action(self, action: Dict[str, Any]) -> None:
        """Validate rule action.

        Args:
            action: Action to validate

        Raises:
            ValidationError: If invalid action
        """
        valid_keys = {"assign_to_user", "assign_to_pool", "assignee_type"}

        for key in action:
            if key not in valid_keys:
                raise ValidationError(f"Invalid action key: {key}")

        if "assign_to_user" not in action and "assign_to_pool" not in action:
            raise ValidationError(
                "Action must have either 'assign_to_user' or 'assign_to_pool'"
            )
