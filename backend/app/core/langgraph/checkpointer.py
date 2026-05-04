"""
PARWA LangGraph Checkpointer — State Persistence

Provides PostgresSaver-based checkpointer for LangGraph state
persistence across interrupts (human-in-the-loop approvals).

When the Control System node sets approval_decision to
"needs_human_approval", LangGraph interrupts the graph execution
and persists the state via the checkpointer. When the human
approves/rejects, the graph resumes from the saved state.

Fallback Chain:
  1. PostgresSaver (production) — persists to PostgreSQL
  2. MemorySaver (development) — in-memory, not durable
  3. None (no persistence) — state lost on interrupt

BC-008: Never crash — if checkpointer creation fails, return None.
BC-001: Checkpointer uses tenant-scoped thread IDs.
"""

from __future__ import annotations

from typing import Any, Optional

from app.logger import get_logger

logger = get_logger("langgraph_checkpointer")

# Singleton checkpointer instance
_checkpointer_instance: Optional[Any] = None


def get_checkpointer() -> Optional[Any]:
    """
    Get or create the singleton checkpointer instance.

    Tries to create a PostgresSaver connected to the application's
    PostgreSQL database. Falls back to MemorySaver if PostgresSaver
    is unavailable.

    Returns:
        Checkpointer instance (PostgresSaver, MemorySaver, or None)
    """
    global _checkpointer_instance

    if _checkpointer is not None:
        return _checkpointer_instance

    # Try PostgresSaver
    _checkpointer_instance = _create_postgres_checkpointer()
    if _checkpointer_instance is not None:
        return _checkpointer_instance

    # Try MemorySaver
    _checkpointer_instance = _create_memory_checkpointer()
    if _checkpointer_instance is not None:
        return _checkpointer_instance

    logger.warning("no_checkpointer_available")
    return None


def _create_postgres_checkpointer() -> Optional[Any]:
    """
    Create a PostgresSaver checkpointer.

    Uses the application's DATABASE_URL from config.py.

    Returns:
        PostgresSaver instance, or None if unavailable
    """
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from app.config import settings

        # Get database URL from app settings
        database_url = getattr(settings, "DATABASE_URL", None) or \
                       getattr(settings, "SQLALCHEMY_DATABASE_URI", None)

        if not database_url:
            logger.info("no_database_url_for_checkpointer")
            return None

        # Create async connection for PostgresSaver
        import psycopg

        # PostgresSaver requires a connection string
        checkpointer = PostgresSaver.from_conn_string(database_url)

        # Initialize the checkpointer tables
        checkpointer.setup()

        logger.info(
            "postgres_checkpointer_created",
            has_database_url=bool(database_url),
        )

        return checkpointer

    except ImportError as exc:
        logger.info(
            "postgres_checkpointer_import_failed",
            error=str(exc),
            message="langgraph-checkpoint-postgres not installed",
        )
        return None

    except Exception as exc:
        logger.warning(
            "postgres_checkpointer_creation_failed",
            error=str(exc),
        )
        return None


def _create_memory_checkpointer() -> Optional[Any]:
    """
    Create a MemorySaver checkpointer (development/testing only).

    State is stored in memory and lost on process restart.
    Suitable for local development and unit tests.

    Returns:
        MemorySaver instance, or None if unavailable
    """
    try:
        from langgraph.checkpoint.memory import MemorySaver

        logger.info("memory_checkpointer_created")
        return MemorySaver()

    except ImportError as exc:
        logger.info(
            "memory_checkpointer_import_failed",
            error=str(exc),
            message="langgraph checkpoint memory not available",
        )
        return None


def reset_checkpointer() -> None:
    """
    Reset the singleton checkpointer instance.

    Used for testing or when database connection needs to be
    re-established.
    """
    global _checkpointer_instance
    _checkpointer_instance = None
    logger.info("checkpointer_reset")


def get_thread_id(tenant_id: str, session_id: str = "") -> str:
    """
    Generate a thread ID for LangGraph checkpoint scoping.

    Thread IDs are tenant-scoped to ensure multi-tenant isolation.
    Format: {tenant_id}_{session_id} or {tenant_id}_{uuid} if
    no session_id is provided.

    Args:
        tenant_id: Tenant identifier (BC-001)
        session_id: Optional session identifier

    Returns:
        Thread ID string
    """
    if session_id:
        return f"{tenant_id}_{session_id}"

    import uuid
    return f"{tenant_id}_{uuid.uuid4().hex[:8]}"
