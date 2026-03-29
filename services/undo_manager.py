"""
PARWA Undo Manager Service.

Provides comprehensive undo capability with snapshot-based state management.
Supports multi-level undo, concurrent operations, and transaction-like semantics.

CRITICAL: Financial actions CANNOT be undone - only non-money actions.

Features:
- Snapshot creation before state changes
- Multi-level undo (up to N levels)
- Concurrent operation safety
- Action grouping for atomic operations
- Audit trail integration
"""
from typing import Any, Dict, Optional, List, Callable, Awaitable
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import hashlib

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger
from shared.core_functions.audit_trail import log_financial_action

logger = get_logger(__name__)


class UndoableActionType(str, Enum):
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
    PRIORITY_CHANGE = "priority_change"
    CATEGORY_CHANGE = "category_change"
    
    # Financial (CANNOT undo)
    REFUND = "refund"
    CHARGE = "charge"
    PAYMENT = "payment"
    SUBSCRIPTION_CHANGE = "subscription_change"


class UndoStatus(str, Enum):
    """Status of undo operations."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_UNDOABLE = "not_undoable"
    EXPIRED = "expired"
    CONFLICT = "conflict"


class SnapshotStatus(str, Enum):
    """Status of snapshots."""
    ACTIVE = "active"
    RESTORED = "restored"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class UndoConfig(BaseModel):
    """Configuration for Undo Manager."""
    max_undo_levels: int = Field(default=10, ge=1, le=100)
    default_undo_window_hours: int = Field(default=24, ge=1, le=168)
    max_snapshot_size_kb: int = Field(default=100, ge=1, le=10000)
    enable_auto_cleanup: bool = Field(default=True)
    cleanup_interval_hours: int = Field(default=1)
    concurrent_undo_timeout_seconds: int = Field(default=30)

    model_config = ConfigDict(use_enum_values=True)


@dataclass
class UndoSnapshot:
    """
    Snapshot of state before an action.
    
    Contains all information needed to restore the previous state.
    """
    snapshot_id: str
    action_type: UndoableActionType
    company_id: str
    performed_by: str
    created_at: datetime
    state_before: Dict[str, Any]
    state_after: Dict[str, Any]
    can_undo: bool
    undo_window_hours: int
    status: SnapshotStatus = SnapshotStatus.ACTIVE
    group_id: Optional[str] = None
    sequence_number: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    restoration_handler: Optional[str] = None
    
    @property
    def expires_at(self) -> datetime:
        """When this snapshot expires."""
        return self.created_at + timedelta(hours=self.undo_window_hours)
    
    @property
    def is_expired(self) -> bool:
        """Check if snapshot has expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_financial(self) -> bool:
        """Check if this is a financial action."""
        return self.action_type in {
            UndoableActionType.REFUND,
            UndoableActionType.CHARGE,
            UndoableActionType.PAYMENT,
            UndoableActionType.SUBSCRIPTION_CHANGE,
        }


@dataclass
class UndoGroup:
    """Group of related actions for atomic undo."""
    group_id: str
    company_id: str
    created_at: datetime
    snapshot_ids: List[str] = field(default_factory=list)
    description: Optional[str] = None


class UndoManager:
    """
    Comprehensive Undo Manager with snapshot-based state management.
    
    Features:
    - Snapshot creation before state changes
    - Multi-level undo (up to N levels)
    - Concurrent operation safety with locking
    - Action grouping for atomic operations
    - Audit trail integration
    
    Example:
        manager = UndoManager()
        
        # Create snapshot before action
        snapshot = await manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": "comp_123",
            "state_before": {"status": "open"},
            "state_after": {"status": "resolved"},
        })
        
        # Undo if needed
        result = await manager.undo(snapshot.snapshot_id)
        
        # Multi-level undo
        results = await manager.undo_multi_level(company_id, levels=3)
    """
    
    # Actions that CAN be undone
    UNDOABLE_ACTIONS = {
        UndoableActionType.TICKET_STATUS_CHANGE,
        UndoableActionType.TICKET_ASSIGNMENT,
        UndoableActionType.KNOWLEDGE_UPDATE,
        UndoableActionType.NOTIFICATION_SEND,
        UndoableActionType.TAG_ADD,
        UndoableActionType.TAG_REMOVE,
        UndoableActionType.AGENT_PROVISION,
        UndoableActionType.CONFIG_UPDATE,
        UndoableActionType.PRIORITY_CHANGE,
        UndoableActionType.CATEGORY_CHANGE,
    }
    
    # Actions that CANNOT be undone (financial)
    NON_UNDOABLE_ACTIONS = {
        UndoableActionType.REFUND,
        UndoableActionType.CHARGE,
        UndoableActionType.PAYMENT,
        UndoableActionType.SUBSCRIPTION_CHANGE,
    }
    
    def __init__(
        self,
        config: Optional[UndoConfig] = None,
        restoration_handlers: Optional[Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]]] = None
    ) -> None:
        """
        Initialize Undo Manager.
        
        Args:
            config: Undo configuration
            restoration_handlers: Optional handlers for specific action types
        """
        self.config = config or UndoConfig()
        self._snapshots: Dict[str, UndoSnapshot] = {}
        self._groups: Dict[str, UndoGroup] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._restoration_handlers = restoration_handlers or {}
        self._undo_stack: Dict[str, List[str]] = {}  # company_id -> list of snapshot_ids
        
        logger.info({
            "event": "undo_manager_initialized",
            "max_undo_levels": self.config.max_undo_levels,
            "undo_window_hours": self.config.default_undo_window_hours,
        })
    
    async def create_snapshot(
        self,
        action: Dict[str, Any]
    ) -> UndoSnapshot:
        """
        Create a snapshot before performing an action.
        
        Args:
            action: Dict with:
                - action_type: Action type string
                - company_id: Company identifier
                - performed_by: User who performed the action
                - state_before: State before action
                - state_after: State after action
                - metadata: Additional context
                - group_id: Optional group for atomic operations
                - restoration_handler: Optional handler name for restoration
        
        Returns:
            UndoSnapshot with snapshot details
        """
        snapshot_id = f"snap_{uuid4().hex[:16]}"
        created_at = datetime.now(timezone.utc)
        
        action_type_str = action.get("action_type", "")
        try:
            action_type = UndoableActionType(action_type_str)
        except ValueError:
            action_type = UndoableActionType.TICKET_STATUS_CHANGE
        
        company_id = action.get("company_id", "")
        can_undo = action_type in self.UNDOABLE_ACTIONS
        undo_window = action.get("undo_window_hours", self.config.default_undo_window_hours)
        
        snapshot = UndoSnapshot(
            snapshot_id=snapshot_id,
            action_type=action_type,
            company_id=company_id,
            performed_by=action.get("performed_by", ""),
            created_at=created_at,
            state_before=action.get("state_before", {}),
            state_after=action.get("state_after", {}),
            can_undo=can_undo,
            undo_window_hours=undo_window,
            group_id=action.get("group_id"),
            metadata=action.get("metadata", {}),
            restoration_handler=action.get("restoration_handler"),
        )
        
        self._snapshots[snapshot_id] = snapshot
        
        # Add to undo stack for this company
        if company_id not in self._undo_stack:
            self._undo_stack[company_id] = []
        self._undo_stack[company_id].append(snapshot_id)
        
        # Trim stack to max levels
        if len(self._undo_stack[company_id]) > self.config.max_undo_levels:
            removed_id = self._undo_stack[company_id].pop(0)
            if removed_id in self._snapshots:
                self._snapshots[removed_id].status = SnapshotStatus.SUPERSEDED
        
        # Add to group if specified
        if snapshot.group_id:
            if snapshot.group_id not in self._groups:
                self._groups[snapshot.group_id] = UndoGroup(
                    group_id=snapshot.group_id,
                    company_id=company_id,
                    created_at=created_at,
                )
            self._groups[snapshot.group_id].snapshot_ids.append(snapshot_id)
        
        logger.info({
            "event": "snapshot_created",
            "snapshot_id": snapshot_id,
            "action_type": action_type.value,
            "company_id": company_id,
            "can_undo": can_undo,
            "is_financial": snapshot.is_financial,
        })
        
        # Log financial actions for audit
        if snapshot.is_financial:
            log_financial_action(
                action_type=action_type.value,
                amount=action.get("amount", 0.0),
                target_id=action.get("target_id", snapshot_id),
                user_id=snapshot.performed_by,
                metadata={"note": "Financial action - NOT undoable"},
            )
        
        return snapshot
    
    async def undo(
        self,
        snapshot_id: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Undo an action by restoring from snapshot.
        
        Args:
            snapshot_id: Snapshot to restore
            force: Force undo even if conflicts detected
        
        Returns:
            Dict with undo result
        """
        snapshot = self._snapshots.get(snapshot_id)
        
        if not snapshot:
            logger.warning({
                "event": "undo_snapshot_not_found",
                "snapshot_id": snapshot_id,
            })
            return {
                "success": False,
                "status": UndoStatus.FAILED.value,
                "error": f"Snapshot {snapshot_id} not found",
            }
        
        # Check if can undo
        if not snapshot.can_undo:
            logger.warning({
                "event": "undo_not_allowed",
                "snapshot_id": snapshot_id,
                "action_type": snapshot.action_type.value,
                "reason": "Financial action cannot be undone",
            })
            return {
                "success": False,
                "status": UndoStatus.NOT_UNDOABLE.value,
                "error": f"Action type {snapshot.action_type.value} cannot be undone",
                "is_financial": True,
            }
        
        # Check if expired
        if snapshot.is_expired:
            snapshot.status = SnapshotStatus.EXPIRED
            logger.warning({
                "event": "undo_expired",
                "snapshot_id": snapshot_id,
                "expires_at": snapshot.expires_at.isoformat(),
            })
            return {
                "success": False,
                "status": UndoStatus.EXPIRED.value,
                "error": f"Snapshot expired at {snapshot.expires_at.isoformat()}",
            }
        
        # Check if already restored
        if snapshot.status == SnapshotStatus.RESTORED:
            return {
                "success": False,
                "status": UndoStatus.FAILED.value,
                "error": "Snapshot already restored",
            }
        
        # Get or create lock for this company
        company_id = snapshot.company_id
        if company_id not in self._locks:
            self._locks[company_id] = asyncio.Lock()
        
        try:
            async with asyncio.timeout(self.config.concurrent_undo_timeout_seconds):
                async with self._locks[company_id]:
                    result = await self._perform_restoration(snapshot, force)
                    return result
        except asyncio.TimeoutError:
            logger.error({
                "event": "undo_timeout",
                "snapshot_id": snapshot_id,
                "company_id": company_id,
            })
            return {
                "success": False,
                "status": UndoStatus.CONFLICT.value,
                "error": "Timeout waiting for concurrent operation lock",
            }
    
    async def _perform_restoration(
        self,
        snapshot: UndoSnapshot,
        force: bool
    ) -> Dict[str, Any]:
        """Perform the actual state restoration."""
        now = datetime.now(timezone.utc)
        
        try:
            # Check for conflicts (newer snapshots in same group or entity)
            if not force:
                conflicts = self._check_conflicts(snapshot)
                if conflicts:
                    return {
                        "success": False,
                        "status": UndoStatus.CONFLICT.value,
                        "error": "Newer changes detected",
                        "conflicts": conflicts,
                    }
            
            # Perform restoration
            restoration_result = await self._restore_state(snapshot)
            
            # Update snapshot status
            snapshot.status = SnapshotStatus.RESTORED
            
            # Remove from undo stack
            if snapshot.company_id in self._undo_stack:
                try:
                    self._undo_stack[snapshot.company_id].remove(snapshot.snapshot_id)
                except ValueError:
                    pass
            
            logger.info({
                "event": "undo_completed",
                "snapshot_id": snapshot.snapshot_id,
                "action_type": snapshot.action_type.value,
                "company_id": snapshot.company_id,
                "restored_at": now.isoformat(),
            })
            
            return {
                "success": True,
                "status": UndoStatus.COMPLETED.value,
                "snapshot_id": snapshot.snapshot_id,
                "action_type": snapshot.action_type.value,
                "restored_state": snapshot.state_before,
                "restored_at": now.isoformat(),
                "restoration_result": restoration_result,
            }
            
        except Exception as e:
            logger.error({
                "event": "undo_failed",
                "snapshot_id": snapshot.snapshot_id,
                "error": str(e),
            })
            return {
                "success": False,
                "status": UndoStatus.FAILED.value,
                "error": str(e),
            }
    
    def _check_conflicts(
        self,
        snapshot: UndoSnapshot
    ) -> List[Dict[str, Any]]:
        """Check for conflicts with newer snapshots."""
        conflicts = []
        
        # Get entity identifier from snapshot
        entity_id = snapshot.state_before.get("entity_id") or snapshot.state_after.get("entity_id")
        if not entity_id:
            return conflicts
        
        # Check for newer snapshots affecting same entity
        for snap_id in self._undo_stack.get(snapshot.company_id, []):
            other = self._snapshots.get(snap_id)
            if not other or other.snapshot_id == snapshot.snapshot_id:
                continue
            
            if other.created_at > snapshot.created_at:
                other_entity = other.state_before.get("entity_id") or other.state_after.get("entity_id")
                if other_entity == entity_id:
                    conflicts.append({
                        "snapshot_id": other.snapshot_id,
                        "action_type": other.action_type.value,
                        "created_at": other.created_at.isoformat(),
                    })
        
        return conflicts
    
    async def _restore_state(
        self,
        snapshot: UndoSnapshot
    ) -> Dict[str, Any]:
        """Restore state from snapshot."""
        # Use custom handler if registered
        if snapshot.restoration_handler and snapshot.restoration_handler in self._restoration_handlers:
            handler = self._restoration_handlers[snapshot.restoration_handler]
            return await handler(snapshot.state_before)
        
        # Default restoration logic based on action type
        if snapshot.action_type == UndoableActionType.TICKET_STATUS_CHANGE:
            return {
                "entity_type": "ticket",
                "entity_id": snapshot.state_before.get("ticket_id") or snapshot.state_before.get("entity_id"),
                "field": "status",
                "restored_value": snapshot.state_before.get("status"),
            }
        
        elif snapshot.action_type == UndoableActionType.TICKET_ASSIGNMENT:
            return {
                "entity_type": "ticket",
                "entity_id": snapshot.state_before.get("ticket_id") or snapshot.state_before.get("entity_id"),
                "field": "assignee",
                "restored_value": snapshot.state_before.get("assignee"),
            }
        
        elif snapshot.action_type == UndoableActionType.KNOWLEDGE_UPDATE:
            return {
                "entity_type": "knowledge_entry",
                "entity_id": snapshot.state_before.get("entry_id") or snapshot.state_before.get("entity_id"),
                "restored_content": snapshot.state_before.get("content"),
            }
        
        elif snapshot.action_type == UndoableActionType.TAG_ADD:
            return {
                "action": "tag_removed",
                "tag": snapshot.state_after.get("tag"),
                "entity_id": snapshot.state_before.get("entity_id"),
            }
        
        elif snapshot.action_type == UndoableActionType.TAG_REMOVE:
            return {
                "action": "tag_restored",
                "tag": snapshot.state_before.get("tag"),
                "entity_id": snapshot.state_before.get("entity_id"),
            }
        
        elif snapshot.action_type == UndoableActionType.PRIORITY_CHANGE:
            return {
                "entity_type": "ticket",
                "entity_id": snapshot.state_before.get("ticket_id") or snapshot.state_before.get("entity_id"),
                "field": "priority",
                "restored_value": snapshot.state_before.get("priority"),
            }
        
        elif snapshot.action_type == UndoableActionType.CATEGORY_CHANGE:
            return {
                "entity_type": "ticket",
                "entity_id": snapshot.state_before.get("ticket_id") or snapshot.state_before.get("entity_id"),
                "field": "category",
                "restored_value": snapshot.state_before.get("category"),
            }
        
        elif snapshot.action_type == UndoableActionType.CONFIG_UPDATE:
            return {
                "action": "config_restored",
                "restored_config": snapshot.state_before,
            }
        
        elif snapshot.action_type == UndoableActionType.AGENT_PROVISION:
            return {
                "action": "agent_deprovisioned",
                "agent_id": snapshot.state_after.get("agent_id"),
            }
        
        return {"restored": True, "state": snapshot.state_before}
    
    async def undo_multi_level(
        self,
        company_id: str,
        levels: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Undo multiple actions in sequence.
        
        Args:
            company_id: Company to undo for
            levels: Number of actions to undo (default 1)
        
        Returns:
            List of undo results
        """
        results = []
        
        if company_id not in self._undo_stack:
            return results
        
        stack = self._undo_stack[company_id]
        levels = min(levels, len(stack))
        
        # Undo from most recent to oldest
        for _ in range(levels):
            if not stack:
                break
            
            snapshot_id = stack[-1]  # Get most recent
            result = await self.undo(snapshot_id)
            results.append(result)
            
            if not result.get("success"):
                break
        
        return results
    
    async def undo_group(
        self,
        group_id: str
    ) -> List[Dict[str, Any]]:
        """
        Undo all actions in a group atomically.
        
        Args:
            group_id: Group to undo
        
        Returns:
            List of undo results
        """
        results = []
        
        group = self._groups.get(group_id)
        if not group:
            return results
        
        # Get all snapshots in group, reverse order
        snapshots = [
            self._snapshots[sid]
            for sid in reversed(group.snapshot_ids)
            if sid in self._snapshots
        ]
        
        for snapshot in snapshots:
            if snapshot.status == SnapshotStatus.ACTIVE and snapshot.can_undo:
                result = await self.undo(snapshot.snapshot_id)
                results.append(result)
                
                if not result.get("success"):
                    break
        
        return results
    
    def get_undoable_actions(
        self,
        company_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get actions that can still be undone.
        
        Args:
            company_id: Company to get actions for
            limit: Maximum number to return
        
        Returns:
            List of undoable action details
        """
        actions = []
        
        if company_id not in self._undo_stack:
            return actions
        
        for snapshot_id in reversed(self._undo_stack[company_id][-limit:]):
            snapshot = self._snapshots.get(snapshot_id)
            if not snapshot:
                continue
            
            if not snapshot.can_undo:
                continue
            
            if snapshot.status != SnapshotStatus.ACTIVE:
                continue
            
            if snapshot.is_expired:
                continue
            
            actions.append({
                "snapshot_id": snapshot.snapshot_id,
                "action_type": snapshot.action_type.value,
                "performed_by": snapshot.performed_by,
                "performed_at": snapshot.created_at.isoformat(),
                "expires_at": snapshot.expires_at.isoformat(),
                "summary": self._summarize_snapshot(snapshot),
                "can_undo": True,
            })
        
        return actions
    
    def _summarize_snapshot(
        self,
        snapshot: UndoSnapshot
    ) -> str:
        """Generate human-readable summary."""
        if snapshot.action_type == UndoableActionType.TICKET_STATUS_CHANGE:
            old = snapshot.state_before.get("status", "?")
            new = snapshot.state_after.get("status", "?")
            return f"Status: {old} → {new}"
        
        elif snapshot.action_type == UndoableActionType.TICKET_ASSIGNMENT:
            old = snapshot.state_before.get("assignee", "?")
            new = snapshot.state_after.get("assignee", "?")
            return f"Assigned: {old} → {new}"
        
        elif snapshot.action_type == UndoableActionType.PRIORITY_CHANGE:
            old = snapshot.state_before.get("priority", "?")
            new = snapshot.state_after.get("priority", "?")
            return f"Priority: {old} → {new}"
        
        elif snapshot.action_type == UndoableActionType.TAG_ADD:
            return f"Tag added: {snapshot.state_after.get('tag', '?')}"
        
        elif snapshot.action_type == UndoableActionType.TAG_REMOVE:
            return f"Tag removed: {snapshot.state_before.get('tag', '?')}"
        
        elif snapshot.action_type == UndoableActionType.KNOWLEDGE_UPDATE:
            return "Knowledge base updated"
        
        elif snapshot.action_type == UndoableActionType.CONFIG_UPDATE:
            return "Configuration changed"
        
        return snapshot.action_type.value
    
    def create_group(
        self,
        company_id: str,
        description: Optional[str] = None
    ) -> str:
        """
        Create a new action group for atomic operations.
        
        Args:
            company_id: Company for the group
            description: Optional description
        
        Returns:
            Group ID
        """
        group_id = f"group_{uuid4().hex[:12]}"
        
        self._groups[group_id] = UndoGroup(
            group_id=group_id,
            company_id=company_id,
            created_at=datetime.now(timezone.utc),
            description=description,
        )
        
        return group_id
    
    def register_restoration_handler(
        self,
        name: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]
    ) -> None:
        """
        Register a custom restoration handler.
        
        Args:
            name: Handler name
            handler: Async function to restore state
        """
        self._restoration_handlers[name] = handler
        logger.info({
            "event": "restoration_handler_registered",
            "handler_name": name,
        })
    
    def get_stats(self) -> Dict[str, Any]:
        """Get undo manager statistics."""
        active_snapshots = sum(
            1 for s in self._snapshots.values()
            if s.status == SnapshotStatus.ACTIVE and not s.is_expired
        )
        
        return {
            "total_snapshots": len(self._snapshots),
            "active_snapshots": active_snapshots,
            "total_groups": len(self._groups),
            "undo_stacks": {
                cid: len(stack)
                for cid, stack in self._undo_stack.items()
            },
            "config": self.config.model_dump(),
        }
    
    async def cleanup_expired(self) -> int:
        """
        Remove expired snapshots.
        
        Returns:
            Number of snapshots cleaned up
        """
        now = datetime.now(timezone.utc)
        cleaned = 0
        
        for snapshot in list(self._snapshots.values()):
            if snapshot.is_expired and snapshot.status == SnapshotStatus.ACTIVE:
                snapshot.status = SnapshotStatus.EXPIRED
                cleaned += 1
        
        logger.info({
            "event": "expired_snapshots_cleaned",
            "count": cleaned,
        })
        
        return cleaned
    
    def is_action_financial(
        self,
        action_type: str
    ) -> bool:
        """Check if an action type is financial (cannot be undone)."""
        try:
            at = UndoableActionType(action_type)
            return at in self.NON_UNDOABLE_ACTIONS
        except ValueError:
            return False
