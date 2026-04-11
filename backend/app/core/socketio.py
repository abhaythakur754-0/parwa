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
    from app.core.socketio import (
        sio, get_socketio_server, get_tenant_room, emit_to_tenant
    )

    # In a route or service:
    await emit_to_tenant(
        company_id="acme",
        event_type="ticket:new",
        payload={"ticket_id": "123"},
    )
"""

import os
from typing import Any, Dict

from app.logger import get_logger

logger = get_logger("socketio")

# Graceful degradation: python-socketio may not be installed in test
# environments or lightweight deployments.  We still need this module
# importable so that ``unittest.mock.patch`` can resolve it.
try:
    import socketio as _socketio_pkg
except ImportError:
    _socketio_pkg = None  # type: ignore[assignment]

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


def _extract_token_from_qs(query_string: str) -> str:
    """Extract JWT token from query string.

    Args:
        query_string: The raw QUERY_STRING from environ.

    Returns:
        Token string or empty string if not found.
    """
    if not query_string:
        return ""
    for part in query_string.split("&"):
        if part.startswith("token="):
            return part[6:]
    return ""


# Create Async Socket.io server (attached to FastAPI in main.py)
if _socketio_pkg is not None:
    sio = _socketio_pkg.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins=[origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if origin.strip()],
        ping_timeout=60,
        ping_interval=25,
        max_http_buffer_size=1_000_000,  # 1MB max message size
        transports=["websocket", "polling"],
    )
else:
    sio = None  # type: ignore[assignment]


def create_socketio_app():
    """Create the Socket.io ASGI application (wrapped around sio server).

    Returns:
        Socket.io ASGIApp that can be mounted on FastAPI.

    Raises:
        RuntimeError: If python-socketio is not installed.
    """
    if _socketio_pkg is None:
        raise RuntimeError(
            "python-socketio is not installed. "
            "Install it with: pip install python-socketio"
        )
    # Register connect/disconnect handlers
    _register_handlers()
    return _socketio_pkg.ASGIApp(sio, socketio_path="/ws/socket.io")


def _register_handlers() -> None:
    """Register Socket.io connection lifecycle handlers."""

    @sio.event
    async def connect(sid, environ):
        """Handle new Socket.io connection.

        BC-011: Authentication is required. No anonymous connections.
        S02: JWT token from query params is verified.
        Backward compat: socketio_auth dict still supported for tests.
        """
        company_id = None
        user_id = None

        # S02: Try JWT from query params first
        query_string = environ.get("QUERY_STRING", "")
        token = _extract_token_from_qs(query_string)

        if token:
            try:
                from app.core.auth import (
                    verify_access_token,
                )
                payload = verify_access_token(token)
                company_id = payload.get("company_id")
                user_id = payload.get("sub")
            except Exception:
                logger.warning(
                    "socketio_reject_invalid_jwt",
                    sid=sid,
                    reason="invalid_or_expired_jwt",
                )
                return False
        else:
            # Backward compat: check socketio_auth dict
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

        # Store company_id and user_id in session
        session_data = {"company_id": company_id}
        if user_id:
            session_data["user_id"] = user_id
        await sio.save_session(sid, session_data)

        logger.info(
            "socketio_connected",
            sid=sid,
            company_id=company_id,
            user_id=user_id,
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
        from app.core.event_buffer import store_event

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


def get_socketio_server():
    """Get the Socket.io server instance.

    Returns:
        The shared Socket.io AsyncServer instance,
        or None if python-socketio is not installed.
    """
    return sio


def get_connected_count() -> int:
    """Get the total number of connected Socket.io clients.

    Returns:
        Number of active connections (best-effort estimate).
    """
    return len(sio.manager.get_participants("/", None))


def register_business_handlers() -> None:
    """Register business event handlers on the Socket.io server.

    These handlers are called when clients SEND events to the server.
    They validate event types against the registry and manage
    client-side event subscriptions.

    BC-001: All handlers enforce tenant isolation.
    BC-005: Subscription management for targeted event delivery.
    """

    @sio.on("event:subscribe")
    async def handle_event_subscribe(sid, data):
        """Client subscribes to specific event types.

        Validates requested event types against the registry
        and stores valid subscriptions in the session.
        """
        try:
            session = await sio.get_session(sid)
            company_id = session.get("company_id")
            if not company_id:
                return {"error": "unauthenticated"}

            event_types = data.get("event_types", []) if data else []
            registry = None
            try:
                from app.core.events import get_event_registry
                registry = get_event_registry()
            except Exception:
                logger.debug("event_registry_import_failed")

            valid_types = []
            for et in event_types:
                if registry and registry.get(et):
                    valid_types.append(et)

            session["subscriptions"] = valid_types
            await sio.save_session(sid, session)

            logger.info(
                "event_subscribed",
                sid=sid,
                company_id=company_id,
                subscriptions=valid_types,
            )
            return {"subscribed": valid_types}
        except Exception as exc:
            logger.warning(
                "event_subscribe_error", sid=sid, error=str(exc)
            )
            return {"error": "subscription_failed"}

    @sio.on("event:unsubscribe")
    async def handle_event_unsubscribe(sid, data):
        """Client unsubscribes from specific event types."""
        try:
            session = await sio.get_session(sid)
            company_id = session.get("company_id")
            if not company_id:
                return {"error": "unauthenticated"}

            event_types = data.get("event_types", []) if data else []
            current = session.get("subscriptions", [])
            session["subscriptions"] = [
                t for t in current if t not in event_types
            ]
            await sio.save_session(sid, session)

            logger.info(
                "event_unsubscribed",
                sid=sid,
                event_types=event_types,
            )
            return {"unsubscribed": event_types}
        except Exception as exc:
            logger.warning(
                "event_unsubscribe_error", sid=sid, error=str(exc)
            )
            return {"error": "unsubscription_failed"}

    @sio.on("ping")
    async def handle_ping(sid):
        """Client heartbeat ping — respond with pong and server time.

        BC-011: Auth is verified on every handler, not just connect.
        A ping without a valid session is rejected to prevent abuse.
        """
        try:
            session = await sio.get_session(sid)
            if not session.get("company_id"):
                logger.warning("ping_rejected_unauthenticated", sid=sid)
                return {"error": "unauthenticated"}
        except Exception:
            return {"error": "unauthenticated"}
        import time as _time
        return {
            "pong": True,
            "server_time": _time.time(),
        }


# Auto-register business handlers when module is imported
try:
    if sio is not None:
        register_business_handlers()
except Exception as _sio_init_exc:
    logger.warning(
        "socketio_business_handlers_registration_failed error=%s",
        _sio_init_exc,
    )
