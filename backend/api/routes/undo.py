"""
PARWA Undo API Routes.

Provides endpoints for snapshot creation and state restoration.
"""
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.services.undo_manager import UndoManager, SnapshotType
from shared.core_functions.logger import get_logger

# Initialize router and logger
router = APIRouter(prefix="/undo", tags=["Undo"])
logger = get_logger(__name__)

# Service instance
_undo_manager = UndoManager()


# --- Pydantic Schemas ---

class CreateSnapshotRequest(BaseModel):
    """Request schema for creating a snapshot."""
    client_id: str = Field(..., description="Client identifier")
    snapshot_type: str = Field(
        default="configuration",
        description="Type of snapshot (configuration, knowledge_base, client_settings, user_data, workflow)"
    )
    state_data: Dict[str, Any] = Field(..., description="State data to snapshot")
    description: str = Field(default="", description="Human-readable description")
    created_by: str = Field(default="", description="User creating the snapshot")
    ttl_hours: int = Field(default=72, description="Time-to-live in hours")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SnapshotResponse(BaseModel):
    """Response schema for snapshot creation."""
    snapshot_id: str
    client_id: str
    snapshot_type: str
    description: str
    created_at: str
    created_by: str
    status: str
    ttl_hours: int


class RestoreResponse(BaseModel):
    """Response schema for restore operation."""
    success: bool
    snapshot_id: str
    restored_at: str
    restored_state: Dict[str, Any] = {}
    errors: List[str] = []


class HistoryItem(BaseModel):
    """Schema for a history item."""
    snapshot_id: str
    client_id: str
    snapshot_type: str
    description: str
    created_at: str
    status: str
    is_expired: bool


class HistoryResponse(BaseModel):
    """Response schema for history."""
    client_id: str
    snapshots: List[HistoryItem]
    total: int


# --- API Endpoints ---

@router.post(
    "",
    response_model=SnapshotResponse,
    status_code=status.HTTP_200_OK,
    summary="Create undo snapshot",
    description="Create a new snapshot for potential undo operations."
)
async def create_snapshot(
    request: CreateSnapshotRequest
) -> SnapshotResponse:
    """
    Create a new state snapshot.

    Creates a snapshot of the provided state data that can be restored later.

    Args:
        request: Snapshot creation request with state data.

    Returns:
        SnapshotResponse with snapshot details.

    Raises:
        HTTPException: 400 if snapshot type is invalid.
    """
    # Validate snapshot type
    valid_types = [t.value for t in SnapshotType]
    if request.snapshot_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid snapshot type. Must be one of: {valid_types}",
        )

    try:
        snapshot = await _undo_manager.create_snapshot({
            "client_id": request.client_id,
            "snapshot_type": request.snapshot_type,
            "state_data": request.state_data,
            "description": request.description,
            "created_by": request.created_by,
            "ttl_hours": request.ttl_hours,
            "metadata": request.metadata or {},
        })

        logger.info({
            "event": "snapshot_created_endpoint",
            "snapshot_id": snapshot.snapshot_id,
            "client_id": snapshot.client_id,
            "snapshot_type": snapshot.snapshot_type.value,
        })

        return SnapshotResponse(
            snapshot_id=snapshot.snapshot_id,
            client_id=snapshot.client_id,
            snapshot_type=snapshot.snapshot_type.value,
            description=snapshot.description,
            created_at=snapshot.created_at.isoformat(),
            created_by=snapshot.created_by,
            status=snapshot.status.value,
            ttl_hours=snapshot.ttl_hours,
        )

    except Exception as e:
        logger.error({
            "event": "snapshot_create_endpoint_error",
            "error": str(e),
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create snapshot: {str(e)}",
        )


@router.post(
    "/{snapshot_id}/restore",
    response_model=RestoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore to snapshot",
    description="Restore state to a previous snapshot."
)
async def restore_snapshot(
    snapshot_id: str
) -> RestoreResponse:
    """
    Restore to a previous snapshot.

    Args:
        snapshot_id: ID of the snapshot to restore.

    Returns:
        RestoreResponse with restoration result.

    Raises:
        HTTPException: 404 if snapshot not found, 400 if cannot restore.
    """
    result = await _undo_manager.restore_snapshot(snapshot_id)

    if not result.success:
        if "not found" in str(result.errors):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.errors[0],
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.errors[0] if result.errors else "Cannot restore snapshot",
            )

    logger.info({
        "event": "snapshot_restored_endpoint",
        "snapshot_id": snapshot_id,
        "success": result.success,
    })

    return RestoreResponse(
        success=result.success,
        snapshot_id=result.snapshot_id,
        restored_at=result.restored_at.isoformat(),
        restored_state=result.restored_state,
        errors=result.errors,
    )


@router.get(
    "/{client_id}/history",
    response_model=HistoryResponse,
    summary="Get undo history",
    description="Get snapshot history for a client."
)
async def get_undo_history(
    client_id: str,
    snapshot_type: Optional[str] = None,
    limit: int = 20
) -> HistoryResponse:
    """
    Get snapshot history for a client.

    Args:
        client_id: Client identifier.
        snapshot_type: Filter by snapshot type (optional).
        limit: Maximum number of results (default 20).

    Returns:
        HistoryResponse with list of snapshots.
    """
    history = await _undo_manager.get_history(
        client_id,
        snapshot_type=snapshot_type,
        limit=limit
    )

    logger.info({
        "event": "history_endpoint_called",
        "client_id": client_id,
        "snapshot_count": len(history),
    })

    snapshots = [
        HistoryItem(
            snapshot_id=item["snapshot_id"],
            client_id=item["client_id"],
            snapshot_type=item["snapshot_type"],
            description=item["description"],
            created_at=item["created_at"],
            status=item["status"],
            is_expired=item["is_expired"],
        )
        for item in history
    ]

    return HistoryResponse(
        client_id=client_id,
        snapshots=snapshots,
        total=len(snapshots),
    )
