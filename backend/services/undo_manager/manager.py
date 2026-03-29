"""
PARWA Undo Manager Service.

Main service for managing undo operations across the system.
Provides snapshot creation, action tracking, and restoration capabilities.

CRITICAL: Financial actions require special handling and cannot be simply undone.
Non-financial actions can be undone within a configurable time window.

Features:
- Create undo snapshots before risky actions
- Track action history with timestamps
- Support multiple undo levels
- Handle financial and non-financial actions differently
"""
from typing import Any, Dict, Optional, List, Callable, Awaitable
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from dataclasses import dataclass, field
from enum import Enum
import json
import asyncio
from functools import wraps

from shared.core_functions.logger import get_logger
from shared.core_functions.audit_trail import log_financial_action

logger = get_logger(__name__)


class ActionCategory(str, Enum):
    """Categories of actions for undo handling."""
    FINANCIAL = "financial"
    NON_FINANCIAL = "non_financial"
    SYSTEM = "system"


class ActionType(str, Enum):
    """Types of actions that can be tracked for undo."""
    # Financial actions (require approval, cannot be simply undone)
    REFUND = "refund"
    CHARGE = "charge"
    PAYMENT = "payment"
    SUBSCRIPTION_CHANGE = "subscription_change"
    CREDIT_ADJUSTMENT = "credit_adjustment"

    # Non-financial actions (can be undone)
    TICKET_STATUS_CHANGE = "ticket_status_change"
    TICKET_ASSIGNMENT = "ticket_assignment"
    KNOWLEDGE_UPDATE = "knowledge_update"
    NOTIFICATION_SEND = "notification_send"
    TAG_ADD = "tag_add"
    TAG_REMOVE = "tag_remove"
    AGENT_PROVISION = "agent_provision"
    CONFIG_UPDATE = "config_update"
    USER_ROLE_CHANGE = "user_role_change"
    SETTINGS_UPDATE = "settings_update"

    # System actions (special handling)
    BACKUP_CREATE = "backup_create"
    CACHE_CLEAR = "cache_clear"
    MAINTENANCE_MODE = "maintenance_mode"


class UndoStatus(str, Enum):
    """Status of undo operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_UNDOABLE = "not_undoable"
    EXPIRED = "expired"


class SnapshotStatus(str, Enum):
    """Status of snapshots."""
    CREATED = "created"
    USED = "used"
    EXPIRED = "expired"
    DELETED = "deleted"


@dataclass
class ActionSnapshot:
    """Represents a snapshot of system state before an action."""
    snapshot_id: str
    action_id: str
    action_type: ActionType
    category: ActionCategory
    company_id: str
    created_at: datetime
    state_data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: SnapshotStatus = SnapshotStatus.CREATED
    expires_at: Optional[datetime] = None


@dataclass
class ActionHistory:
    """Represents a tracked action in history."""
    action_id: str
    action_type: ActionType
    category: ActionCategory
    company_id: str
    performed_by: str
    performed_at: datetime
    snapshot_id: Optional[str]
    can_undo: bool
    undo_window_hours: int
    undo_expires_at: datetime
    is_undone: bool = False
    undone_at: Optional[datetime] = None
    undone_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class UndoManager:
    """
    Main service for managing undo operations.

    CRITICAL: Financial actions require special handling.
    Non-financial actions can be undone within a configurable time window.

    Features:
    - Create undo snapshots before risky actions
    - Track action history with timestamps
    - Support multiple undo levels
    - Handle financial and non-financial actions differently

    Example:
        manager = UndoManager()

        # Create snapshot before risky action
        snapshot = await manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": "comp_123",
            "state_data": {"ticket_id": "t_456", "status": "open"},
        })

        # Track the action
        action = await manager.track_action({
            "action_type": "ticket_status_change",
            "company_id": "comp_123",
            "performed_by": "user_789",
            "snapshot_id": snapshot["snapshot_id"],
        })

        # Undo if needed
        result = await manager.undo_action(action["action_id"])
    """

    # Financial actions that cannot be simply undone
    FINANCIAL_ACTIONS = {
        ActionType.REFUND,
        ActionType.CHARGE,
        ActionType.PAYMENT,
        ActionType.SUBSCRIPTION_CHANGE,
        ActionType.CREDIT_ADJUSTMENT,
    }

    # Non-financial actions that can be undone
    NON_FINANCIAL_ACTIONS = {
        ActionType.TICKET_STATUS_CHANGE,
        ActionType.TICKET_ASSIGNMENT,
        ActionType.KNOWLEDGE_UPDATE,
        ActionType.NOTIFICATION_SEND,
        ActionType.TAG_ADD,
        ActionType.TAG_REMOVE,
        ActionType.AGENT_PROVISION,
        ActionType.CONFIG_UPDATE,
        ActionType.USER_ROLE_CHANGE,
        ActionType.SETTINGS_UPDATE,
    }

    # System actions with special handling
    SYSTEM_ACTIONS = {
        ActionType.BACKUP_CREATE,
        ActionType.CACHE_CLEAR,
        ActionType.MAINTENANCE_MODE,
    }

    # Default undo window in hours
    DEFAULT_UNDO_WINDOW_HOURS = 24

    # Maximum undo levels (undo history depth)
    MAX_UNDO_LEVELS = 50

    # Snapshot retention period in days
    SNAPSHOT_RETENTION_DAYS = 7

    def __init__(
        self,
        snapshot_storage: Optional[Any] = None,
        max_undo_levels: int = MAX_UNDO_LEVELS,
    ) -> None:
        """
        Initialize Undo Manager.

        Args:
            snapshot_storage: Optional storage backend for snapshots
            max_undo_levels: Maximum number of undo levels to maintain
        """
        self._snapshots: Dict[str, ActionSnapshot] = {}
        self._actions: Dict[str, ActionHistory] = {}
        self._company_actions: Dict[str, List[str]] = {}
        self._snapshot_storage = snapshot_storage
        self._max_undo_levels = max_undo_levels

        # Callbacks for custom undo handlers
        self._undo_handlers: Dict[ActionType, Callable[..., Awaitable[Dict[str, Any]]]] = {}

        logger.info({
            "event": "undo_manager_initialized",
            "max_undo_levels": max_undo_levels,
            "financial_actions": [a.value for a in self.FINANCIAL_ACTIONS],
            "non_financial_actions": [a.value for a in self.NON_FINANCIAL_ACTIONS],
        })

    def _get_action_category(self, action_type: ActionType) -> ActionCategory:
        """Determine the category of an action type."""
        if action_type in self.FINANCIAL_ACTIONS:
            return ActionCategory.FINANCIAL
        elif action_type in self.SYSTEM_ACTIONS:
            return ActionCategory.SYSTEM
        else:
            return ActionCategory.NON_FINANCIAL

    def _can_undo_action(self, action_type: ActionType) -> bool:
        """Check if an action type can be undone."""
        return action_type in self.NON_FINANCIAL_ACTIONS

    async def create_snapshot(
        self,
        snapshot_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a snapshot of system state before an action.

        This captures the current state so it can be restored if needed.

        Args:
            snapshot_data: Dict with:
                - action_type: Type of action being performed
                - company_id: Company identifier
                - state_data: Current state to capture
                - metadata: Additional context

        Returns:
            Dict with snapshot_id and metadata
        """
        snapshot_id = f"snap_{uuid4().hex[:16]}"
        action_id = f"action_{uuid4().hex[:16]}"
        created_at = datetime.now(timezone.utc)

        action_type_str = snapshot_data.get("action_type", "")
        try:
            action_type = ActionType(action_type_str)
        except ValueError:
            action_type = ActionType.CONFIG_UPDATE

        category = self._get_action_category(action_type)

        # Calculate expiration
        expires_at = created_at + timedelta(days=self.SNAPSHOT_RETENTION_DAYS)

        snapshot = ActionSnapshot(
            snapshot_id=snapshot_id,
            action_id=action_id,
            action_type=action_type,
            category=category,
            company_id=snapshot_data.get("company_id", ""),
            created_at=created_at,
            state_data=snapshot_data.get("state_data", {}),
            metadata=snapshot_data.get("metadata", {}),
            status=SnapshotStatus.CREATED,
            expires_at=expires_at,
        )

        self._snapshots[snapshot_id] = snapshot

        logger.info({
            "event": "snapshot_created",
            "snapshot_id": snapshot_id,
            "action_id": action_id,
            "action_type": action_type.value,
            "category": category.value,
            "company_id": snapshot.company_id,
            "expires_at": expires_at.isoformat(),
        })

        return {
            "snapshot_id": snapshot_id,
            "action_id": action_id,
            "action_type": action_type.value,
            "category": category.value,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

    async def track_action(
        self,
        action_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Track an action for potential undo.

        CRITICAL: Financial actions are tracked but cannot be simply undone.
        They require approval workflows.

        Args:
            action_data: Dict with:
                - action_id: Optional existing action ID
                - action_type: Type of action
                - company_id: Company identifier
                - performed_by: User who performed the action
                - snapshot_id: ID of associated snapshot
                - undo_window_hours: Hours until undo expires
                - metadata: Additional context

        Returns:
            Dict with action_id and undo capability info
        """
        # Use existing action_id or create new one
        action_id = action_data.get("action_id") or f"action_{uuid4().hex[:16]}"
        performed_at = datetime.now(timezone.utc)

        action_type_str = action_data.get("action_type", "")
        try:
            action_type = ActionType(action_type_str)
        except ValueError:
            action_type = ActionType.CONFIG_UPDATE

        category = self._get_action_category(action_type)
        can_undo = self._can_undo_action(action_type)

        undo_window_hours = action_data.get("undo_window_hours", self.DEFAULT_UNDO_WINDOW_HOURS)
        undo_expires_at = performed_at + timedelta(hours=undo_window_hours)

        action = ActionHistory(
            action_id=action_id,
            action_type=action_type,
            category=category,
            company_id=action_data.get("company_id", ""),
            performed_by=action_data.get("performed_by", ""),
            performed_at=performed_at,
            snapshot_id=action_data.get("snapshot_id"),
            can_undo=can_undo,
            undo_window_hours=undo_window_hours,
            undo_expires_at=undo_expires_at,
            metadata=action_data.get("metadata", {}),
        )

        self._actions[action_id] = action

        # Track by company for quick lookup
        company_id = action.company_id
        if company_id not in self._company_actions:
            self._company_actions[company_id] = []
        self._company_actions[company_id].append(action_id)

        # Enforce max undo levels
        await self._enforce_undo_limits(company_id)

        logger.info({
            "event": "action_tracked",
            "action_id": action_id,
            "action_type": action_type.value,
            "category": category.value,
            "company_id": company_id,
            "can_undo": can_undo,
            "undo_expires_at": undo_expires_at.isoformat(),
        })

        # Log financial actions to audit trail
        if category == ActionCategory.FINANCIAL:
            log_financial_action(
                action_type=action_type.value,
                amount=action_data.get("amount", 0.0),
                target_id=action_data.get("target_id", action_id),
                user_id=action.performed_by,
                metadata={
                    "note": "Financial action tracked - requires approval for undo",
                    **action.metadata,
                },
            )

        return {
            "action_id": action_id,
            "action_type": action_type.value,
            "category": category.value,
            "can_undo": can_undo,
            "undo_window_hours": undo_window_hours,
            "undo_expires_at": undo_expires_at.isoformat(),
            "is_financial": category == ActionCategory.FINANCIAL,
            "tracked_at": performed_at.isoformat(),
        }

    async def _enforce_undo_limits(self, company_id: str) -> None:
        """Enforce maximum undo levels per company."""
        if company_id not in self._company_actions:
            return

        action_ids = self._company_actions[company_id]
        if len(action_ids) > self._max_undo_levels:
            # Remove oldest actions beyond limit
            excess = len(action_ids) - self._max_undo_levels
            removed_ids = action_ids[:excess]

            for removed_id in removed_ids:
                # Mark associated snapshot as expired
                if removed_id in self._actions:
                    action = self._actions[removed_id]
                    if action.snapshot_id and action.snapshot_id in self._snapshots:
                        self._snapshots[action.snapshot_id].status = SnapshotStatus.EXPIRED
                    del self._actions[removed_id]

            self._company_actions[company_id] = action_ids[excess:]

            logger.debug({
                "event": "undo_limits_enforced",
                "company_id": company_id,
                "removed_count": excess,
            })

    async def undo_action(
        self,
        action_id: str,
        performed_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Undo a tracked action.

        CRITICAL:
        - Financial actions cannot be simply undone
        - Non-financial actions can be undone within time window

        Args:
            action_id: ID of action to undo
            performed_by: User performing the undo

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

        # Check if already undone
        if action.is_undone:
            return {
                "success": False,
                "status": UndoStatus.FAILED.value,
                "error": "Action has already been undone",
            }

        # CRITICAL: Check if action can be undone
        if not action.can_undo:
            logger.warning({
                "event": "undo_action_not_allowed",
                "action_id": action_id,
                "action_type": action.action_type.value,
                "category": action.category.value,
            })
            return {
                "success": False,
                "status": UndoStatus.NOT_UNDOABLE.value,
                "error": f"Action type {action.action_type.value} cannot be undone",
                "is_financial": action.category == ActionCategory.FINANCIAL,
            }

        # Check if within undo window
        now = datetime.now(timezone.utc)
        if now > action.undo_expires_at:
            logger.warning({
                "event": "undo_action_expired",
                "action_id": action_id,
                "undo_expires_at": action.undo_expires_at.isoformat(),
            })
            return {
                "success": False,
                "status": UndoStatus.EXPIRED.value,
                "error": f"Undo window expired at {action.undo_expires_at.isoformat()}",
            }

        # Perform the undo
        try:
            undo_result = await self._perform_undo(action, performed_by)

            # Update action status
            action.is_undone = True
            action.undone_at = now
            action.undone_by = performed_by

            logger.info({
                "event": "action_undone",
                "action_id": action_id,
                "action_type": action.action_type.value,
                "company_id": action.company_id,
                "undone_by": performed_by,
                "undone_at": now.isoformat(),
            })

            return {
                "success": True,
                "status": UndoStatus.COMPLETED.value,
                "action_id": action_id,
                "action_type": action.action_type.value,
                "restored_state": undo_result.get("restored_state"),
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
        action: ActionHistory,
        performed_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform the actual undo operation.

        Args:
            action: Action to undo
            performed_by: User performing the undo

        Returns:
            Undo result with restored state
        """
        # Get the snapshot for this action
        snapshot = None
        if action.snapshot_id:
            snapshot = self._snapshots.get(action.snapshot_id)

        # Check for custom handler
        if action.action_type in self._undo_handlers:
            handler = self._undo_handlers[action.action_type]
            return await handler(action, snapshot)

        # Default undo handling based on action type
        if snapshot:
            restored_state = snapshot.state_data
        else:
            restored_state = action.metadata.get("original_state", {})

        # Mark snapshot as used
        if snapshot:
            snapshot.status = SnapshotStatus.USED

        return {
            "restored_state": restored_state,
            "action_type": action.action_type.value,
        }

    def register_undo_handler(
        self,
        action_type: ActionType,
        handler: Callable[..., Awaitable[Dict[str, Any]]]
    ) -> None:
        """
        Register a custom undo handler for an action type.

        Args:
            action_type: Action type to handle
            handler: Async function to handle undo
        """
        self._undo_handlers[action_type] = handler
        logger.info({
            "event": "undo_handler_registered",
            "action_type": action_type.value,
        })

    async def get_action_history(
        self,
        company_id: str,
        limit: int = 50,
        include_financial: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get action history for a company.

        Args:
            company_id: Company identifier
            limit: Maximum number of actions to return
            include_financial: Whether to include financial actions

        Returns:
            List of action history entries
        """
        if company_id not in self._company_actions:
            return []

        action_ids = self._company_actions[company_id][-limit:]
        history = []

        for action_id in reversed(action_ids):
            action = self._actions.get(action_id)
            if not action:
                continue

            if not include_financial and action.category == ActionCategory.FINANCIAL:
                continue

            history.append({
                "action_id": action.action_id,
                "action_type": action.action_type.value,
                "category": action.category.value,
                "performed_by": action.performed_by,
                "performed_at": action.performed_at.isoformat(),
                "can_undo": action.can_undo and not action.is_undone,
                "is_undone": action.is_undone,
                "undo_expires_at": action.undo_expires_at.isoformat() if not action.is_undone else None,
                "summary": self._summarize_action(action),
            })

        return history

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
        undoable = []

        if company_id not in self._company_actions:
            return []

        for action_id in reversed(self._company_actions[company_id]):
            action = self._actions.get(action_id)
            if not action:
                continue

            # Check if can undo
            if not action.can_undo:
                continue

            # Check if already undone
            if action.is_undone:
                continue

            # Check if within window
            if now > action.undo_expires_at:
                continue

            undoable.append({
                "action_id": action.action_id,
                "action_type": action.action_type.value,
                "performed_by": action.performed_by,
                "performed_at": action.performed_at.isoformat(),
                "undo_expires_at": action.undo_expires_at.isoformat(),
                "can_undo": True,
                "summary": self._summarize_action(action),
            })

        return undoable

    def _summarize_action(self, action: ActionHistory) -> str:
        """Generate a human-readable summary of an action."""
        metadata = action.metadata

        summaries = {
            ActionType.TICKET_STATUS_CHANGE: lambda m: f"Status changed from {m.get('old_status', 'unknown')} to {m.get('new_status', 'unknown')}",
            ActionType.TICKET_ASSIGNMENT: lambda m: f"Assigned from {m.get('old_assignee', 'unassigned')} to {m.get('new_assignee', 'unassigned')}",
            ActionType.KNOWLEDGE_UPDATE: lambda m: f"Updated knowledge entry: {m.get('entry_title', 'unknown')}",
            ActionType.TAG_ADD: lambda m: f"Added tag: {m.get('tag', 'unknown')}",
            ActionType.TAG_REMOVE: lambda m: f"Removed tag: {m.get('tag', 'unknown')}",
            ActionType.CONFIG_UPDATE: lambda m: f"Updated configuration: {m.get('config_key', 'unknown')}",
            ActionType.REFUND: lambda m: f"Refund of ${m.get('amount', 0):.2f}",
            ActionType.CHARGE: lambda m: f"Charge of ${m.get('amount', 0):.2f}",
            ActionType.PAYMENT: lambda m: f"Payment of ${m.get('amount', 0):.2f}",
        }

        if action.action_type in summaries:
            return summaries[action.action_type](metadata)

        return action.action_type.value

    def is_action_financial(self, action_type: str) -> bool:
        """
        Check if an action type is financial.

        Args:
            action_type: Action type string

        Returns:
            True if financial, False otherwise
        """
        try:
            at = ActionType(action_type)
            return at in self.FINANCIAL_ACTIONS
        except ValueError:
            return False

    async def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a snapshot by ID.

        Args:
            snapshot_id: Snapshot identifier

        Returns:
            Snapshot data or None if not found
        """
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            return None

        return {
            "snapshot_id": snapshot.snapshot_id,
            "action_id": snapshot.action_id,
            "action_type": snapshot.action_type.value,
            "category": snapshot.category.value,
            "company_id": snapshot.company_id,
            "created_at": snapshot.created_at.isoformat(),
            "status": snapshot.status.value,
            "state_data": snapshot.state_data,
            "metadata": snapshot.metadata,
        }

    async def cleanup_expired(self) -> Dict[str, int]:
        """
        Clean up expired snapshots and actions.

        Returns:
            Dict with cleanup counts
        """
        now = datetime.now(timezone.utc)
        expired_snapshots = 0
        expired_actions = 0

        # Clean up expired snapshots
        for snapshot_id, snapshot in list(self._snapshots.items()):
            if snapshot.expires_at and now > snapshot.expires_at:
                snapshot.status = SnapshotStatus.EXPIRED
                expired_snapshots += 1

        # Clean up expired actions (just mark, don't delete for audit)
        for action_id, action in list(self._actions.items()):
            if not action.is_undone and now > action.undo_expires_at:
                expired_actions += 1

        logger.info({
            "event": "cleanup_expired",
            "expired_snapshots": expired_snapshots,
            "expired_actions": expired_actions,
        })

        return {
            "expired_snapshots": expired_snapshots,
            "expired_actions": expired_actions,
        }


# Decorator for automatic snapshot creation
def with_undo_snapshot(
    action_type: str,
    get_state_func: Callable[..., Dict[str, Any]]
):
    """
    Decorator to automatically create snapshot before action.

    Args:
        action_type: Type of action being performed
        get_state_func: Function to extract current state

    Example:
        @with_undo_snapshot("ticket_status_change", lambda self, ticket_id: {"ticket_id": ticket_id, "status": self.get_status(ticket_id)})
        async def change_ticket_status(self, ticket_id, new_status):
            ...
    """
    def decorator(func: Callable[..., Awaitable[Any]]):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # This would be implemented with the actual UndoManager instance
            # For now, just call the function
            return await func(self, *args, **kwargs)
        return wrapper
    return decorator


# Global instance for convenience
_undo_manager: Optional[UndoManager] = None


def get_undo_manager() -> UndoManager:
    """Get or create the global UndoManager instance."""
    global _undo_manager
    if _undo_manager is None:
        _undo_manager = UndoManager()
    return _undo_manager
