"""
PARWA Socket.io Server (BC-005, BC-001, BC-011)

Provides the Socket.io server with:
- Tenant-scoped rooms: tenant_{company_id} (BC-005, BC-001)
- Connection authentication — no anonymous connections (BC-011)
- Event emission with automatic event buffer storage (BC-005)
- Graceful degradation — Socket.io unavailable = dashboard still works (BC-005)

Room naming convention: tenant_{company_id}
- Every client joins ONLY their tenant's room
- Events are emitted to specific tenant rooms only
- No global rooms, no cross-tenant room access

Usage:
    from backend.app.core.socketio import (
        sio, get_socketio_server, get_tenant_room, emit_to_tenant
    )

    # In a route or service:
    await emit_to_tenant(
        company_id="acme",
        event_type="ticket:new",
        payload={"ticket_id": "123"},
    )
"""

from typing import Any, Dict

import socketio

from backend.app.logger import get_logger

logger = get_logger("socketio")

# Room naming prefix — BC-005
TENANT_ROOM_PREFIX = "tenant_"

# Maximum allowed length for company_id in room names
MAX_COMPANY_ID_LENGTH = 128


def get_tenant_room(company_id: str) -> str:
    """Build a tenant-scoped Socket.io room name.

    Room names follow the format: tenant_{company_id}
    BC-005: A client MUST NEVER join a global or cross-tenant room.

    Args:
        company_id: The tenant identifier.

    Returns:
        Room name string: tenant_{company_id}

    Raises:
        ValueError: If company_id is empty, too long, or has control chars.
    """
    if not company_id or not isinstance(company_id, str):
        raise ValueError(
            "company_id is required and must be a non-empty string (BC-005)"
        )
    company_id = company_id.strip()
    if not company_id:
        raise ValueError("company_id must not be whitespace-only (BC-005)")
    if len(company_id) > MAX_COMPANY_ID_LENGTH:
        raise ValueError(
            f"company_id exceeds max length {MAX_COMPANY_ID_LENGTH} (BC-005)"
        )
    if any(ord(c) < 32 for c in company_id):
        raise ValueError(
            "Invalid company_id: contains control characters (BC-005)"
        )
    return f"{TENANT_ROOM_PREFIX}{company_id}"


def _validate_company_id(company_id: Any) -> bool:
    """Validate company_id for room operations.

    Args:
        company_id: Value to validate.

    Returns:
        True if valid, False otherwise.
    """
    if not company_id or not isinstance(company_id, str):
        return False
    company_id = company_id.strip()
    if not company_id or len(company_id) > MAX_COMPANY_ID_LENGTH:
        return False
    if any(ord(c) < 32 for c in company_id):
        return False
    return True


# Create Async Socket.io server (attached to FastAPI in main.py)
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1_000_000,  # 1MB max message size
    transports=["websocket", "polling"],
)


def create_socketio_app() -> socketio.ASGIApp:
    """Create the Socket.io ASGI application (wrapped around sio server).

    Returns:
        Socket.io ASGIApp that can be mounted on FastAPI.
    """
    # Register connect/disconnect handlers
    _register_handlers()
    return socketio.ASGIApp(sio, socketio_path="/ws/socket.io")


def _register_handlers() -> None:
    """Register Socket.io connection lifecycle handlers."""

    @sio.event
    async def connect(sid, environ):
        """Handle new Socket.io connection.

        BC-011: Authentication is required. No anonymous connections.
        The auth middleware validates the token before this handler runs.
        """
        auth = environ.get("socketio_auth", {})
        company_id = auth.get("company_id")

        if not company_id or not _validate_company_id(company_id):
            logger.warning(
                "socketio_reject_unauthenticated",
                sid=sid,
                reason="missing_or_invalid_company_id",
            )
            return False  # Reject connection

        # Join the tenant room
        room = get_tenant_room(company_id)
        await sio.enter_room(sid, room)

        # Store company_id in session for disconnect
        await sio.save_session(sid, {"company_id": company_id})

        logger.info(
            "socketio_connected",
            sid=sid,
            company_id=company_id,
            room=room,
        )

    @sio.event
    async def disconnect(sid):
        """Handle Socket.io disconnection."""
        try:
            session = await sio.get_session(sid)
            company_id = session.get("company_id", "unknown")
            room = get_tenant_room(company_id)
            await sio.leave_room(sid, room)
            logger.info(
                "socketio_disconnected",
                sid=sid,
                company_id=company_id,
            )
        except Exception as exc:
            logger.warning(
                "socketio_disconnect_error",
                sid=sid,
                error=str(exc),
            )


async def emit_to_tenant(
    company_id: str,
    event_type: str,
    payload: Dict[str, Any],
) -> int:
    """Emit an event to all clients in a tenant's room.

    BC-005: Events are scoped to tenant rooms only.
    Also stores the event in the event buffer for reconnection recovery.

    Args:
        company_id: Tenant identifier (BC-001).
        event_type: Event type string (e.g., "ticket:new").
        payload: Event data dictionary.

    Returns:
        Number of clients that received the event.

    Raises:
        ValueError: If company_id is invalid.
    """
    if not _validate_company_id(company_id):
        raise ValueError(
            f"Invalid company_id for emit: {company_id!r} (BC-001)"
        )

    room = get_tenant_room(company_id)

    # Emit to the tenant room
    await sio.emit(
        event_type,
        payload,
        room=room,
    )

    # Store in event buffer for reconnection recovery (BC-005)
    try:
        from backend.app.core.event_buffer import store_event

        await store_event(
            company_id=company_id,
            event_type=event_type,
            payload=payload,
        )
    except Exception as exc:
        # Event buffer failure should not break the emit
        logger.warning(
            "event_buffer_store_failed",
            company_id=company_id,
            event_type=event_type,
            error=str(exc),
        )

    # Get room count for return value
    count = len(await sio.rooms(room)) if hasattr(sio, "rooms") else 0
    return count


async def emit_to_session(
    company_id: str,
    session_id: str,
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    """Emit an event to a specific client session within a tenant.

    Useful for sending responses to a specific user's browser tab.

    Args:
        company_id: Tenant identifier (BC-001).
        session_id: Socket.io session ID.
        event_type: Event type string.
        payload: Event data dictionary.
    """
    await sio.emit(event_type, payload, room=session_id)


def get_socketio_server() -> socketio.AsyncServer:
    """Get the Socket.io server instance.

    Returns:
        The shared Socket.io AsyncServer instance.
    """
    return sio


def get_connected_count() -> int:
    """Get the total number of connected Socket.io clients.

    Returns:
        Number of active connections (best-effort estimate).
    """
    return len(sio.manager.get_participants("/", None))
