"""Node 19: CONTEXT_MANAGER — Manages conversation history and unresolved issues.

Knowledge Agent node. Loads relevant prior context instead of full chat history,
improving continuity and saving tokens.
"""

from __future__ import annotations

from typing import Any

from parwa.utils.node_base import safe_node


@safe_node("CONTEXT_MANAGER", fallback={"context_history": []})
async def context_manager(state: dict[str, Any]) -> dict[str, Any]:
    """Manage conversation context and history (async).

    Reads: customer_id, raw_message
    Writes: context_history
    """
    # In production, this would query a conversation store
    # For now, initialize with the current message as the first interaction
    # If there's existing context_history, append; otherwise start fresh

    existing_history = state.get("context_history", [])
    raw_message = state.get("raw_message", "")

    # Build context entry for this message
    current_entry = {
        "role": "customer",
        "content": raw_message,
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }

    # Keep the last 10 entries max to avoid context bloat
    updated_history = list(existing_history) + [current_entry]
    if len(updated_history) > 10:
        updated_history = updated_history[-10:]

    return {"context_history": updated_history}
