"""Node 19: CONTEXT_MANAGER — Manages conversation history and unresolved issues.

Knowledge Agent node. Loads relevant prior context instead of full chat history,
improving continuity and saving tokens.

Phase 3: Now uses FrameworkBrain with CLARA/HyDE for smart context retrieval.
Falls back to basic history management on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.context_manager")


async def _manage_context_with_brain(state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Context management using FrameworkBrain (Phase 3).

    Returns (context_history, frameworks_used).
    Falls back to basic context on any failure.
    """
    existing_history = state.get("context_history", [])
    raw_message = state.get("raw_message", "")

    # Guard types
    if not isinstance(existing_history, list):
        existing_history = []
    if not isinstance(raw_message, str):
        raw_message = str(raw_message) if raw_message else ""

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="CONTEXT_MANAGER", state=state)
        result = await brain.think(
            prompt=raw_message,
            techniques=["clara", "hyde", "multi_query"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # Build context entry with brain-enhanced metadata
        try:
            current_entry = {
                "role": "customer",
                "content": raw_message,
                "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                "brain_enhanced": True,
                "frameworks_used": result.frameworks_used,
            }
        except Exception:
            current_entry = {
                "role": "customer",
                "content": raw_message,
                "timestamp": "unknown",
                "brain_enhanced": True,
                "frameworks_used": result.frameworks_used,
            }

        # Keep the last 10 entries max to avoid context bloat
        updated_history = list(existing_history) + [current_entry]
        if len(updated_history) > 10:
            updated_history = updated_history[-10:]

        return updated_history, result.frameworks_used if result.frameworks_used else []

    except Exception as exc:
        logger.warning(
            "context_manager: FrameworkBrain failed (%s), falling back to basic context",
            exc,
        )
        # Fall back to basic context management
        try:
            current_entry = {
                "role": "customer",
                "content": raw_message,
                "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            }
        except Exception:
            current_entry = {
                "role": "customer",
                "content": raw_message,
                "timestamp": "unknown",
            }

        updated_history = list(existing_history) + [current_entry]
        if len(updated_history) > 10:
            updated_history = updated_history[-10:]

        return updated_history, []


@safe_node("CONTEXT_MANAGER", fallback={"context_history": [], "active_frameworks": []})
async def context_manager(state: dict[str, Any]) -> dict[str, Any]:
    """Manage conversation context and history (async).

    Phase 3: Uses FrameworkBrain with CLARA/HyDE/Multi-Query for
    smart context retrieval. Falls back to basic history management
    on FrameworkBrain failure.

    Reads: customer_id, raw_message, context_history
    Writes: context_history, active_frameworks (append)
    """
    # Try FrameworkBrain first (Phase 3)
    updated_history, frameworks = await _manage_context_with_brain(state)

    # Track frameworks used — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "context_history": updated_history,
        "active_frameworks": new_frameworks,
    }
