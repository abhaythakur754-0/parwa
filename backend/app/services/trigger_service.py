"""
PARWA Trigger Service - Automated Trigger Rules (Day 33: MF08)

Implements MF08: Automated trigger rules with:
- Trigger CRUD operations
- Condition evaluation
- Action execution
- Trigger versioning

BC-001: All queries are tenant-isolated via company_id.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, ValidationError
from database.models.tickets import TicketTrigger, Ticket


class TriggerService:
    """Automated trigger rule management operations."""

    # Maximum triggers per company
    MAX_TRIGGERS_PER_COMPANY = 50

    # Valid trigger events
    VALID_EVENTS = [
        "ticket_created",
        "ticket_updated",
        "ticket_assigned",
        "ticket_resolved",
        "ticket_closed",
        "ticket_reopened",
        "message_added",
        "sla_warning",
        "sla_breached",
        "status_changed",
    ]

    # Valid trigger actions
    VALID_ACTIONS = [
        "change_status",
        "assign_to",
        "add_tag",
        "remove_tag",
        "set_priority",
        "send_notification",
        "escalate",
    ]

    # Valid condition operators
    VALID_OPERATORS = [
        "equals",
        "not_equals",
        "contains",
        "not_contains",
        "starts_with",
        "ends_with",
        "in",
        "not_in",
        "greater_than",
        "less_than",
    ]

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    # ── TRIGGER CRUD ────────────────────────────────────────────────────────

    def create_trigger(
        self,
        name: str,
        conditions: Dict[str, Any],
        action: Dict[str, Any],
        description: Optional[str] = None,
        priority_order: int = 0,
        created_by: Optional[str] = None,
    ) -> TicketTrigger:
        """Create a new trigger.

        Args:
            name: Trigger name
            conditions: Condition configuration with events and conditions
            action: Action configuration
            description: Optional description
            priority_order: Execution order (higher = earlier)
            created_by: User ID who created the trigger

        Returns:
            Created TicketTrigger object

        Raises:
            ValidationError: If validation fails or limit exceeded
        """
        # Check limit
        current_count = self.db.query(TicketTrigger).filter(
            TicketTrigger.company_id == self.company_id,
            TicketTrigger.is_active == True,
        ).count()

        if current_count >= self.MAX_TRIGGERS_PER_COMPANY:
            raise ValidationError(
                f"Maximum {self.MAX_TRIGGERS_PER_COMPANY} triggers per company"
            )

        # Validate name
        if not name or len(name.strip()) == 0:
            raise ValidationError("Trigger name is required")

        # Validate conditions
        self._validate_conditions(conditions)

        # Validate action
        self._validate_action(action)

        trigger = TicketTrigger(
            id=str(uuid.uuid4()),
            company_id=self.company_id,
            name=name.strip(),
            description=description,
            conditions=json.dumps(conditions),
            action=json.dumps(action),
            is_active=True,
            priority_order=priority_order,
            execution_count=0,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(trigger)
        self.db.commit()
        self.db.refresh(trigger)

        return trigger

    def _validate_conditions(self, conditions: Dict[str, Any]) -> None:
        """Validate trigger conditions structure."""
        if not isinstance(conditions, dict):
            raise ValidationError("Conditions must be a JSON object")

        # Validate events
        events = conditions.get("events", [])
        if not isinstance(events, list):
            raise ValidationError("conditions.events must be an array")

        for event in events:
            if event not in self.VALID_EVENTS:
                raise ValidationError(f"Invalid event type: {event}")

        # Validate condition rules
        condition_rules = conditions.get("conditions", [])
        if not isinstance(condition_rules, list):
            raise ValidationError("conditions.conditions must be an array")

        for rule in condition_rules:
            if not isinstance(rule, dict):
                raise ValidationError("Each condition rule must be an object")

            if "field" not in rule:
                raise ValidationError("Condition rule must have 'field'")

            operator = rule.get("operator")
            if operator not in self.VALID_OPERATORS:
                raise ValidationError(f"Invalid operator: {operator}")

    def _validate_action(self, action: Dict[str, Any]) -> None:
        """Validate trigger action structure."""
        if not isinstance(action, dict):
            raise ValidationError("Action must be a JSON object")

        action_type = action.get("action")
        if not action_type:
            raise ValidationError("Action must have 'action' type")

        if action_type not in self.VALID_ACTIONS:
            raise ValidationError(f"Invalid action type: {action_type}")

        # Validate action params based on type
        params = action.get("params", {})

        if action_type == "change_status":
            if "status" not in params:
                raise ValidationError("change_status action requires 'status' param")

        elif action_type == "assign_to":
            if "assignee_id" not in params:
                raise ValidationError("assign_to action requires 'assignee_id' param")

        elif action_type in ["add_tag", "remove_tag"]:
            if "tag" not in params:
                raise ValidationError(f"{action_type} action requires 'tag' param")

        elif action_type == "set_priority":
            if "priority" not in params:
                raise ValidationError("set_priority action requires 'priority' param")

    def get_trigger(self, trigger_id: str) -> TicketTrigger:
        """Get a trigger by ID.

        Args:
            trigger_id: Trigger ID

        Returns:
            TicketTrigger object

        Raises:
            NotFoundError: If trigger not found
        """
        trigger = self.db.query(TicketTrigger).filter(
            TicketTrigger.id == trigger_id,
            TicketTrigger.company_id == self.company_id,
        ).first()

        if not trigger:
            raise NotFoundError(f"Trigger {trigger_id} not found")

        return trigger

    def list_triggers(
        self,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[TicketTrigger], int]:
        """List triggers with filters.

        Args:
            is_active: Filter by active status
            search: Search in name and description
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (triggers list, total count)
        """
        query = self.db.query(TicketTrigger).filter(
            TicketTrigger.company_id == self.company_id,
        )

        # Apply filters
        if is_active is not None:
            query = query.filter(TicketTrigger.is_active == is_active)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    TicketTrigger.name.ilike(search_pattern),
                    TicketTrigger.description.ilike(search_pattern),
                )
            )

        # Count total
        total = query.count()

        # Sort by priority (descending) then created_at
        query = query.order_by(
            desc(TicketTrigger.priority_order),
            desc(TicketTrigger.created_at),
        )

        # Paginate
        offset = (page - 1) * page_size
        triggers = query.offset(offset).limit(page_size).all()

        return triggers, total

    def update_trigger(
        self,
        trigger_id: str,
        name: Optional[str] = None,
        conditions: Optional[Dict[str, Any]] = None,
        action: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        priority_order: Optional[int] = None,
    ) -> TicketTrigger:
        """Update a trigger.

        Args:
            trigger_id: Trigger ID
            name: New name
            conditions: New conditions
            action: New action
            description: New description
            priority_order: New priority order

        Returns:
            Updated TicketTrigger object
        """
        trigger = self.get_trigger(trigger_id)

        if name is not None:
            if not name.strip():
                raise ValidationError("Trigger name cannot be empty")
            trigger.name = name.strip()

        if conditions is not None:
            self._validate_conditions(conditions)
            trigger.conditions = json.dumps(conditions)

        if action is not None:
            self._validate_action(action)
            trigger.action = json.dumps(action)

        if description is not None:
            trigger.description = description

        if priority_order is not None:
            trigger.priority_order = priority_order

        trigger.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(trigger)

        return trigger

    def delete_trigger(self, trigger_id: str) -> bool:
        """Delete a trigger (soft delete).

        Args:
            trigger_id: Trigger ID

        Returns:
            True if deleted
        """
        trigger = self.get_trigger(trigger_id)

        trigger.is_active = False
        trigger.updated_at = datetime.now(timezone.utc)

        self.db.commit()

        return True

    def toggle_trigger(self, trigger_id: str, is_active: bool) -> TicketTrigger:
        """Enable or disable a trigger.

        Args:
            trigger_id: Trigger ID
            is_active: New active status

        Returns:
            Updated TicketTrigger object
        """
        trigger = self.get_trigger(trigger_id)
        trigger.is_active = is_active
        trigger.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(trigger)

        return trigger

    # ── TRIGGER EVALUATION ──────────────────────────────────────────────────

    def evaluate_triggers(
        self,
        ticket: Ticket,
        event_type: str,
    ) -> List[Dict[str, Any]]:
        """Evaluate all active triggers for a ticket event.

        Args:
            ticket: Ticket object
            event_type: Event that occurred

        Returns:
            List of triggered actions to execute
        """
        # Get all active triggers for this event
        triggers = self.db.query(TicketTrigger).filter(
            TicketTrigger.company_id == self.company_id,
            TicketTrigger.is_active == True,
        ).order_by(desc(TicketTrigger.priority_order)).all()

        executed_actions = []

        for trigger in triggers:
            conditions = json.loads(trigger.conditions or "{}")

            # Check if event matches
            events = conditions.get("events", [])
            if event_type not in events:
                continue

            # Evaluate conditions
            if self._evaluate_conditions(ticket, conditions.get("conditions", [])):
                # Mark as executed
                trigger.execution_count = (trigger.execution_count or 0) + 1
                trigger.last_executed_at = datetime.now(timezone.utc)

                action = json.loads(trigger.action or "{}")
                executed_actions.append({
                    "trigger_id": trigger.id,
                    "trigger_name": trigger.name,
                    "action": action,
                })

        self.db.commit()

        return executed_actions

    def _evaluate_conditions(
        self,
        ticket: Ticket,
        condition_rules: List[Dict[str, Any]],
    ) -> bool:
        """Evaluate condition rules against a ticket.

        Args:
            ticket: Ticket object
            condition_rules: List of condition rules

        Returns:
            True if all conditions match
        """
        if not condition_rules:
            return True

        for rule in condition_rules:
            field = rule.get("field")
            operator = rule.get("operator")
            value = rule.get("value")

            # Get ticket field value
            ticket_value = getattr(ticket, field, None)

            # Evaluate based on operator
            if not self._evaluate_operator(ticket_value, operator, value):
                return False

        return True

    def _evaluate_operator(
        self,
        ticket_value: Any,
        operator: str,
        condition_value: Any,
    ) -> bool:
        """Evaluate a single condition."""
        if operator == "equals":
            return ticket_value == condition_value

        elif operator == "not_equals":
            return ticket_value != condition_value

        elif operator == "contains":
            if ticket_value is None:
                return False
            return str(condition_value) in str(ticket_value)

        elif operator == "not_contains":
            if ticket_value is None:
                return True
            return str(condition_value) not in str(ticket_value)

        elif operator == "starts_with":
            if ticket_value is None:
                return False
            return str(ticket_value).startswith(str(condition_value))

        elif operator == "ends_with":
            if ticket_value is None:
                return False
            return str(ticket_value).endswith(str(condition_value))

        elif operator == "in":
            if ticket_value is None:
                return False
            return ticket_value in condition_value

        elif operator == "not_in":
            if ticket_value is None:
                return True
            return ticket_value not in condition_value

        elif operator == "greater_than":
            if ticket_value is None:
                return False
            return ticket_value > condition_value

        elif operator == "less_than":
            if ticket_value is None:
                return False
            return ticket_value < condition_value

        return False

    def get_execution_history(
        self,
        trigger_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Get execution history for a trigger.

        Args:
            trigger_id: Trigger ID
            page: Page number
            page_size: Items per page

        Returns:
            Dict with execution statistics
        """
        trigger = self.get_trigger(trigger_id)

        return {
            "trigger_id": trigger_id,
            "trigger_name": trigger.name,
            "total_executions": trigger.execution_count or 0,
            "last_executed_at": trigger.last_executed_at.isoformat() if trigger.last_executed_at else None,
        }
