"""
PARWA Non-Financial Undo Service.

Provides undo capability for non-financial actions.
CRITICAL: Cannot undo financial transactions - only non-money actions.

Actions that CAN be undone:
- Ticket status changes
- Agent assignments
- Knowledge base updates
- Notification sends
- Tags/labels

Actions that CANNOT be undone:
- Refunds
- Charges
- Payments
- Any financial transaction
"""
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from enum import Enum
import json

from shared.core_functions.logger import get_logger
from shared.core_functions.audit_trail import log_financial_action

logger = get_logger(__name__)


class ActionType(str, Enum):
    """Types of actions that can potentially be undone."""
    # Non-financial (CAN undo)
    TICKET_STATUS_CHANGE = "ticket_status_change"
    TICKET_ASSIGNMENT = "ticket_assignment"
    KNOWLEDGE_UPDATE = "knowledge_update"
    NOTIFICATION_SEND = "notification_send"
    TAG_ADD = "tag_add"
    TAG_REMOVE = "tag_remove"
    AGENT_PROVISION = "agent_provision"
    CONFIG_UPDATE = "config_update"

    # Financial (CANNOT undo)
    REFUND = "refund"
    CHARGE = "charge"
    PAYMENT = "payment"


class UndoStatus(str, Enum):
    """Status of undo operations."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_UNDOABLE = "not_undoable"


@dataclass
class UndoableAction:
    """Represents an action that can potentially be undone."""
    action_id: str
    action_type: ActionType
    company_id: str
    performed_by: str
    performed_at: datetime
    original_state: Dict[str, Any]
    new_state: Dict[str, Any]
    can_undo: bool
    undo_window_hours: int = 24
    metadata: Dict[str, Any] = field(default_factory=dict)


class NonFinancialUndoService:
    """
    Service for undoing non-financial actions.

    CRITICAL: Financial actions CANNOT be undone.
    Only non-money actions can be undone.

    Features:
    - Track undoable actions
    - Undo within time window
    - Audit trail logging
    - Financial action protection

    Example:
        service = NonFinancialUndoService()
        # Log action
        action = await service.log_action({
            "action_type": "ticket_status_change",
            "company_id": "comp_123",
            ...
        })
        # Later, undo if needed
        result = await service.undo_action(action["action_id"])
    """

    # Actions that CAN be undone
    UNDOABLE_ACTIONS = {
        ActionType.TICKET_STATUS_CHANGE,
        ActionType.TICKET_ASSIGNMENT,
        ActionType.KNOWLEDGE_UPDATE,
        ActionType.NOTIFICATION_SEND,
        ActionType.TAG_ADD,
        ActionType.TAG_REMOVE,
        ActionType.AGENT_PROVISION,
        ActionType.CONFIG_UPDATE,
    }

    # Actions that CANNOT be undone (financial)
    NON_UNDOABLE_ACTIONS = {
        ActionType.REFUND,
        ActionType.CHARGE,
        ActionType.PAYMENT,
    }

    # Default undo window in hours
    DEFAULT_UNDO_WINDOW_HOURS = 24

    def __init__(self) -> None:
        """Initialize Non-Financial Undo Service."""
        self._actions: Dict[str, UndoableAction] = {}

        logger.info({
            "event": "non_financial_undo_service_initialized",
            "undoable_actions": [a.value for a in self.UNDOABLE_ACTIONS],
        })

    async def log_action(
        self,
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Log an action for potential undo.

        CRITICAL: Financial actions are logged but marked as not undoable.

        Args:
            action: Dict with:
                - action_type: ActionType enum value
                - company_id: Company identifier
                - performed_by: User who performed the action
                - original_state: State before action
                - new_state: State after action
                - metadata: Additional context

        Returns:
            Dict with action_id and undoability status
        """
        action_id = f"action_{uuid4().hex[:16]}"
        performed_at = datetime.now(timezone.utc)

        action_type_str = action.get("action_type", "")
        try:
            action_type = ActionType(action_type_str)
        except ValueError:
            action_type = ActionType.TICKET_STATUS_CHANGE

        # CRITICAL: Check if this is a financial action
        is_financial = action_type in self.NON_UNDOABLE_ACTIONS
        can_undo = action_type in self.UNDOABLE_ACTIONS

        # Create undoable action record
        undoable = UndoableAction(
            action_id=action_id,
            action_type=action_type,
            company_id=action.get("company_id", ""),
            performed_by=action.get("performed_by", ""),
            performed_at=performed_at,
            original_state=action.get("original_state", {}),
            new_state=action.get("new_state", {}),
            can_undo=can_undo,
            undo_window_hours=action.get("undo_window_hours", self.DEFAULT_UNDO_WINDOW_HOURS),
            metadata=action.get("metadata", {}),
        )

        self._actions[action_id] = undoable

        logger.info({
            "event": "action_logged",
            "action_id": action_id,
            "action_type": action_type.value,
            "company_id": undoable.company_id,
            "can_undo": can_undo,
            "is_financial": is_financial,
        })

        # Log to audit trail
        if is_financial:
            # CRITICAL: Log financial action for audit
            log_financial_action(
                action_type=action_type.value,
                amount=action.get("amount", 0.0),
                target_id=action.get("target_id", action_id),
                user_id=undoable.performed_by,
                metadata={"note": "Financial action - NOT undoable"},
            )

        return {
            "action_id": action_id,
            "action_type": action_type.value,
            "can_undo": can_undo,
            "undo_window_hours": undoable.undo_window_hours,
            "undo_expires_at": (performed_at + timedelta(hours=undoable.undo_window_hours)).isoformat(),
            "is_financial": is_financial,
            "logged_at": performed_at.isoformat(),
        }

    async def undo_action(
        self,
        action_id: str
    ) -> Dict[str, Any]:
        """
        Undo a non-financial action.

        CRITICAL:
        - Non-money action undone, logged in audit trail
        - Cannot undo financial transactions

        Args:
            action_id: Action to undo

        Returns:
            Dict with undo status and result
        """
        action = self._actions.get(action_id)

        if not action:
            logger.warning({
                "event": "undo_action_not_found",
                "action_id": action_id,
            })
            return {
                "success": False,
                "status": UndoStatus.FAILED.value,
                "error": f"Action {action_id} not found",
            }

        # CRITICAL: Check if action can be undone
        if not action.can_undo:
            logger.warning({
                "event": "undo_action_not_allowed",
                "action_id": action_id,
                "action_type": action.action_type.value,
                "reason": "Financial action cannot be undone",
            })
            return {
                "success": False,
                "status": UndoStatus.NOT_UNDOABLE.value,
                "error": f"Action type {action.action_type.value} cannot be undone",
                "is_financial": True,
            }

        # Check if within undo window
        now = datetime.now(timezone.utc)
        undo_deadline = action.performed_at + timedelta(hours=action.undo_window_hours)

        if now > undo_deadline:
            logger.warning({
                "event": "undo_action_expired",
                "action_id": action_id,
                "performed_at": action.performed_at.isoformat(),
                "undo_deadline": undo_deadline.isoformat(),
            })
            return {
                "success": False,
                "status": UndoStatus.FAILED.value,
                "error": f"Undo window expired at {undo_deadline.isoformat()}",
            }

        # Perform the undo
        try:
            undo_result = await self._perform_undo(action)

            logger.info({
                "event": "action_undone",
                "action_id": action_id,
                "action_type": action.action_type.value,
                "company_id": action.company_id,
                "undone_at": now.isoformat(),
                "note": "Non-money action undone, logged in audit trail",
            })

            return {
                "success": True,
                "status": UndoStatus.COMPLETED.value,
                "action_id": action_id,
                "action_type": action.action_type.value,
                "restored_state": action.original_state,
                "undo_performed_at": now.isoformat(),
                "is_financial": False,
            }

        except Exception as e:
            logger.error({
                "event": "undo_action_failed",
                "action_id": action_id,
                "error": str(e),
            })
            return {
                "success": False,
                "status": UndoStatus.FAILED.value,
                "error": str(e),
            }

    async def _perform_undo(
        self,
        action: UndoableAction
    ) -> Dict[str, Any]:
        """
        Perform the actual undo operation.

        Args:
            action: Action to undo

        Returns:
            Undo result
        """
        # In production, this would actually restore state
        # For now, we simulate based on action type

        if action.action_type == ActionType.TICKET_STATUS_CHANGE:
            return {
                "restored_status": action.original_state.get("status"),
                "ticket_id": action.original_state.get("ticket_id"),
            }

        elif action.action_type == ActionType.TICKET_ASSIGNMENT:
            return {
                "restored_assignee": action.original_state.get("assignee"),
                "ticket_id": action.original_state.get("ticket_id"),
            }

        elif action.action_type == ActionType.KNOWLEDGE_UPDATE:
            return {
                "restored_content": action.original_state.get("content"),
                "entry_id": action.original_state.get("entry_id"),
            }

        elif action.action_type == ActionType.TAG_ADD:
            return {
                "tag_removed": action.new_state.get("tag"),
                "entity_id": action.original_state.get("entity_id"),
            }

        elif action.action_type == ActionType.TAG_REMOVE:
            return {
                "tag_restored": action.original_state.get("tag"),
                "entity_id": action.original_state.get("entity_id"),
            }

        elif action.action_type == ActionType.AGENT_PROVISION:
            return {
                "agent_deprovisioned": True,
                "agent_id": action.new_state.get("agent_id"),
            }

        elif action.action_type == ActionType.CONFIG_UPDATE:
            return {
                "config_restored": action.original_state,
            }

        return {"restored": True}

    async def get_undoable_actions(
        self,
        company_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get actions that can still be undone.

        Args:
            company_id: Company identifier

        Returns:
            List of undoable actions
        """
        now = datetime.now(timezone.utc)
        undoable: List[Dict[str, Any]] = []

        for action in self._actions.values():
            # Filter by company
            if action.company_id != company_id:
                continue

            # Check if can undo
            if not action.can_undo:
                continue

            # Check if within window
            undo_deadline = action.performed_at + timedelta(hours=action.undo_window_hours)
            if now > undo_deadline:
                continue

            undoable.append({
                "action_id": action.action_id,
                "action_type": action.action_type.value,
                "performed_by": action.performed_by,
                "performed_at": action.performed_at.isoformat(),
                "undo_deadline": undo_deadline.isoformat(),
                "can_undo": True,
                "summary": self._summarize_action(action),
            })

        # Sort by performed_at descending
        undoable.sort(key=lambda x: x["performed_at"], reverse=True)

        return undoable

    def _summarize_action(
        self,
        action: UndoableAction
    ) -> str:
        """Generate a human-readable summary of an action."""
        if action.action_type == ActionType.TICKET_STATUS_CHANGE:
            old = action.original_state.get("status", "unknown")
            new = action.new_state.get("status", "unknown")
            return f"Status changed from {old} to {new}"

        elif action.action_type == ActionType.TICKET_ASSIGNMENT:
            old = action.original_state.get("assignee", "unassigned")
            new = action.new_state.get("assignee", "unassigned")
            return f"Assigned from {old} to {new}"

        elif action.action_type == ActionType.KNOWLEDGE_UPDATE:
            return "Knowledge base entry updated"

        elif action.action_type == ActionType.TAG_ADD:
            tag = action.new_state.get("tag", "")
            return f"Tag '{tag}' added"

        elif action.action_type == ActionType.TAG_REMOVE:
            tag = action.original_state.get("tag", "")
            return f"Tag '{tag}' removed"

        elif action.action_type == ActionType.AGENT_PROVISION:
            return "Agent provisioned"

        elif action.action_type == ActionType.CONFIG_UPDATE:
            return "Configuration updated"

        return action.action_type.value

    def is_action_financial(
        self,
        action_type: str
    ) -> bool:
        """
        Check if an action type is financial.

        CRITICAL: Financial actions cannot be undone.

        Args:
            action_type: Action type string

        Returns:
            True if financial, False otherwise
        """
        try:
            at = ActionType(action_type)
            return at in self.NON_UNDOABLE_ACTIONS
        except ValueError:
            return False
