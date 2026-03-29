# Undo Manager Service

## Overview

The Undo Manager Service provides comprehensive undo capability with snapshot-based state management. It supports multi-level undo, concurrent operations, and transaction-like semantics.

**Location:** `services/undo_manager.py`

**CRITICAL:** Financial actions CANNOT be undone - only non-money actions.

## Features

- **Snapshot Creation**: Capture state before changes
- **Multi-level Undo**: Undo up to N levels of changes
- **Concurrent Operation Safety**: Locking mechanism per company
- **Action Grouping**: Atomic multi-action undo
- **Conflict Detection**: Detect newer changes before undo
- **Audit Trail Integration**: Log all undo operations

## Undoable Actions

### Can Undo (Non-Financial)

| Action Type | Description |
|-------------|-------------|
| `ticket_status_change` | Ticket status updates |
| `ticket_assignment` | Ticket assignment changes |
| `knowledge_update` | Knowledge base updates |
| `notification_send` | Notification sends (can cancel pending) |
| `tag_add` | Tag additions |
| `tag_remove` | Tag removals |
| `agent_provision` | Agent provisioning |
| `config_update` | Configuration changes |
| `priority_change` | Priority updates |
| `category_change` | Category changes |

### Cannot Undo (Financial)

| Action Type | Reason |
|-------------|--------|
| `refund` | Financial transaction |
| `charge` | Financial transaction |
| `payment` | Financial transaction |
| `subscription_change` | Financial transaction |

## API Reference

### Classes

#### `UndoConfig`

Configuration for the Undo Manager.

```python
class UndoConfig(BaseModel):
    max_undo_levels: int = 10                  # Max undo history (1-100)
    default_undo_window_hours: int = 24        # Undo window in hours (1-168)
    max_snapshot_size_kb: int = 100            # Max snapshot size (1-10000)
    enable_auto_cleanup: bool = True           # Auto cleanup expired
    cleanup_interval_hours: int = 1            # Cleanup interval
    concurrent_undo_timeout_seconds: int = 30  # Lock timeout
```

#### `UndoSnapshot`

Snapshot of state before an action.

```python
@dataclass
class UndoSnapshot:
    snapshot_id: str                    # Unique snapshot ID
    action_type: UndoableActionType     # Type of action
    company_id: str                     # Company identifier
    performed_by: str                   # User who performed action
    created_at: datetime                # Creation timestamp
    state_before: Dict[str, Any]        # State before action
    state_after: Dict[str, Any]         # State after action
    can_undo: bool                      # Whether action can be undone
    undo_window_hours: int              # Hours until expiration
    status: SnapshotStatus              # Current status
    group_id: Optional[str]             # Group for atomic undo
    metadata: Dict[str, Any]            # Additional metadata
    
    @property
    def expires_at(self) -> datetime    # Expiration timestamp
    
    @property
    def is_expired(self) -> bool        # Check if expired
    
    @property
    def is_financial(self) -> bool      # Check if financial action
```

#### `UndoStatus`

Status of undo operations.

```python
class UndoStatus(str, Enum):
    PENDING = "pending"           # Undo in progress
    COMPLETED = "completed"       # Successfully undone
    FAILED = "failed"             # Undo failed
    NOT_UNDOABLE = "not_undoable" # Cannot be undone
    EXPIRED = "expired"           # Undo window passed
    CONFLICT = "conflict"         # Newer changes exist
```

### Main Class: `UndoManager`

#### Initialization

```python
from services.undo_manager import UndoManager, UndoConfig

manager = UndoManager(
    config=UndoConfig(max_undo_levels=20),
    restoration_handlers={
        "custom_handler": my_async_handler
    }
)
```

#### Methods

##### `create_snapshot()`

Create a snapshot before performing an action.

```python
snapshot = await manager.create_snapshot({
    "action_type": "ticket_status_change",   # Required
    "company_id": "company_123",             # Required
    "performed_by": "user_456",              # Required
    "state_before": {"status": "open"},      # Required
    "state_after": {"status": "resolved"},   # Required
    "metadata": {"ticket_id": "T-123"},      # Optional
    "group_id": "group_abc",                 # Optional
    "restoration_handler": "custom_handler", # Optional
    "undo_window_hours": 48,                 # Optional
})
```

**Returns:** `UndoSnapshot`

##### `undo()`

Undo an action by restoring from snapshot.

```python
result = await manager.undo(
    snapshot_id="snap_abc123",
    force=False  # Force bypass conflict detection
)
```

**Returns:**

```python
{
    "success": True,
    "status": "completed",
    "snapshot_id": "snap_abc123",
    "action_type": "ticket_status_change",
    "restored_state": {"status": "open"},
    "restored_at": "2024-01-15T10:30:00Z",
    "restoration_result": {...}
}
```

##### `undo_multi_level()`

Undo multiple actions in sequence.

```python
results = await manager.undo_multi_level(
    company_id="company_123",
    levels=3  # Undo last 3 actions
)
```

**Returns:** `List[Dict[str, Any]]` - Results for each undo

##### `undo_group()`

Undo all actions in a group atomically.

```python
results = await manager.undo_group(group_id="group_abc")
```

**Returns:** `List[Dict[str, Any]]` - Results for each action in group

##### `create_group()`

Create a new action group for atomic operations.

```python
group_id = manager.create_group(
    company_id="company_123",
    description="Multi-step ticket update"
)
```

**Returns:** `str` - Group ID to use in snapshots

##### `get_undoable_actions()`

Get actions that can still be undone.

```python
actions = manager.get_undoable_actions(
    company_id="company_123",
    limit=10
)
```

**Returns:**

```python
[
    {
        "snapshot_id": "snap_123",
        "action_type": "ticket_status_change",
        "performed_by": "user_456",
        "performed_at": "2024-01-15T10:00:00Z",
        "expires_at": "2024-01-16T10:00:00Z",
        "summary": "Status: open → resolved",
        "can_undo": True
    },
    # ... more actions
]
```

##### `register_restoration_handler()`

Register a custom restoration handler.

```python
async def my_handler(state: dict) -> dict:
    # Custom restoration logic
    return {"restored": True}

manager.register_restoration_handler("my_handler", my_handler)
```

##### `get_stats()`

Get undo manager statistics.

```python
stats = manager.get_stats()
# Returns:
# {
#     "total_snapshots": 100,
#     "active_snapshots": 50,
#     "total_groups": 5,
#     "undo_stacks": {"company_123": 10, "company_456": 5},
#     "config": {...}
# }
```

##### `cleanup_expired()`

Remove expired snapshots.

```python
cleaned = await manager.cleanup_expired()
```

**Returns:** `int` - Number of snapshots cleaned

##### `is_action_financial()`

Check if an action type is financial.

```python
is_financial = manager.is_action_financial("refund")  # True
is_financial = manager.is_action_financial("ticket_status_change")  # False
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_undo_levels` | int | 10 | Maximum undo history per company |
| `default_undo_window_hours` | int | 24 | Hours until snapshot expires |
| `max_snapshot_size_kb` | int | 100 | Maximum snapshot size |
| `enable_auto_cleanup` | bool | True | Enable automatic cleanup |
| `cleanup_interval_hours` | int | 1 | Cleanup interval |
| `concurrent_undo_timeout_seconds` | int | 30 | Lock acquisition timeout |

## Usage Examples

### Basic Undo Flow

```python
from services.undo_manager import UndoManager

manager = UndoManager()

# Before changing ticket status
snapshot = await manager.create_snapshot({
    "action_type": "ticket_status_change",
    "company_id": "company_123",
    "performed_by": "agent_456",
    "state_before": {"status": "open", "ticket_id": "T-123"},
    "state_after": {"status": "resolved", "ticket_id": "T-123"},
})

# Perform the actual status change
await update_ticket_status("T-123", "resolved")

# Later, if needed, undo
result = await manager.undo(snapshot.snapshot_id)

if result["success"]:
    print(f"Restored to: {result['restored_state']}")
```

### Multi-Level Undo

```python
# Perform multiple actions
await manager.create_snapshot({
    "action_type": "ticket_status_change",
    "company_id": "company_123",
    "performed_by": "user_456",
    "state_before": {"status": "open"},
    "state_after": {"status": "in_progress"},
})

await manager.create_snapshot({
    "action_type": "ticket_assignment",
    "company_id": "company_123",
    "performed_by": "user_456",
    "state_before": {"assignee": None},
    "state_after": {"assignee": "agent_123"},
})

await manager.create_snapshot({
    "action_type": "priority_change",
    "company_id": "company_123",
    "performed_by": "user_456",
    "state_before": {"priority": "low"},
    "state_after": {"priority": "high"},
})

# Undo last 2 actions
results = await manager.undo_multi_level("company_123", levels=2)
```

### Atomic Group Undo

```python
# Create a group for related actions
group_id = manager.create_group(
    company_id="company_123",
    description="Ticket escalation workflow"
)

# All snapshots in group will undo together
await manager.create_snapshot({
    "action_type": "ticket_status_change",
    "company_id": "company_123",
    "performed_by": "user_456",
    "state_before": {"status": "open"},
    "state_after": {"status": "escalated"},
    "group_id": group_id,
})

await manager.create_snapshot({
    "action_type": "priority_change",
    "company_id": "company_123",
    "performed_by": "user_456",
    "state_before": {"priority": "low"},
    "state_after": {"priority": "urgent"},
    "group_id": group_id,
})

# Undo entire group atomically
results = await manager.undo_group(group_id)
```

### Custom Restoration Handler

```python
async def ticket_restoration_handler(state: dict) -> dict:
    """Custom handler for ticket restoration."""
    ticket_id = state.get("ticket_id")
    # Call actual API to restore state
    await ticket_api.update(ticket_id, state)
    return {"ticket_id": ticket_id, "restored": True}

manager.register_restoration_handler("ticket_restore", ticket_restoration_handler)

# Use the handler
snapshot = await manager.create_snapshot({
    "action_type": "ticket_status_change",
    "company_id": "company_123",
    "performed_by": "user_456",
    "state_before": {"ticket_id": "T-123", "status": "open"},
    "state_after": {"ticket_id": "T-123", "status": "resolved"},
    "restoration_handler": "ticket_restore",
})
```

### Conflict Detection

```python
# Create first change
snapshot1 = await manager.create_snapshot({
    "action_type": "ticket_status_change",
    "company_id": "company_123",
    "performed_by": "user_456",
    "state_before": {"status": "open", "entity_id": "T-123"},
    "state_after": {"status": "resolved", "entity_id": "T-123"},
})

# Create newer change (same entity)
snapshot2 = await manager.create_snapshot({
    "action_type": "ticket_status_change",
    "company_id": "company_123",
    "performed_by": "user_456",
    "state_before": {"status": "resolved", "entity_id": "T-123"},
    "state_after": {"status": "closed", "entity_id": "T-123"},
})

# Try to undo older change - will detect conflict
result = await manager.undo(snapshot1.snapshot_id)
# result["status"] == "conflict"

# Force undo to bypass conflict check
result = await manager.undo(snapshot1.snapshot_id, force=True)
# result["success"] == True
```

## Error Handling

### Error Statuses

| Status | Cause | Resolution |
|--------|-------|------------|
| `failed` | Snapshot not found | Check snapshot_id |
| `not_undoable` | Financial action | Cannot undo financial transactions |
| `expired` | Undo window passed | Increase `undo_window_hours` |
| `conflict` | Newer changes exist | Use `force=True` to override |

### Error Example

```python
result = await manager.undo(snapshot_id)

if not result["success"]:
    status = result["status"]
    
    if status == "not_undoable":
        print("Cannot undo financial transaction")
    elif status == "expired":
        print(f"Expired at: {result.get('expires_at')}")
    elif status == "conflict":
        print(f"Conflicts: {result.get('conflicts')}")
    else:
        print(f"Error: {result.get('error')}")
```

## Concurrency Model

### Per-Company Locking

Each company has its own asyncio lock for undo operations:

```python
# These run in parallel (different companies)
await manager.undo(snap1)  # company_123
await manager.undo(snap2)  # company_456

# These run sequentially (same company)
await manager.undo(snap3)  # company_123
await manager.undo(snap4)  # company_123
```

### Timeout Handling

```python
# If lock acquisition times out
result = await manager.undo(snapshot_id)
# result["status"] == "conflict"
# result["error"] == "Timeout waiting for concurrent operation lock"
```

## Best Practices

1. **Always create snapshot before changes**: Capture state before modifications
2. **Use groups for related actions**: Enable atomic multi-step undo
3. **Check can_undo**: Verify action is undoable before relying on it
4. **Handle conflicts gracefully**: Ask user before force-undoing
5. **Set appropriate windows**: Match undo window to business needs
6. **Register custom handlers**: For complex restoration logic

## Integration Points

- **Audit Trail**: Financial actions are logged automatically
- **Knowledge Base**: Restore KB content changes
- **Ticket System**: Restore ticket state
- **Configuration**: Restore config changes
