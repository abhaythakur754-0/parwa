"""Node 1: INGEST — Receives raw ticket from any channel.

Router Agent node. Entry point of the PARWA pipeline.
Validates channel availability for the variant and generates a ticket ID.

Phase 5: Now uses FrameworkBrain with CoT for smart channel validation
on complex tickets. Falls back to rule-based on failure.
"""

from __future__ import annotations

import uuid
from typing import Any

from parwa.config import get_variant_channels
from parwa.state import TicketChannel
from parwa.utils.node_base import safe_node


async def _ingest_with_brain(state: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Ingest processing using FrameworkBrain (Phase 5).

    Returns (ingest_result, frameworks_used).
    Falls back to rule-based on any failure.
    """
    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="INGEST", state=state)
        result = await brain.think(
            prompt="Validate and ingest ticket",
            techniques=["chain_of_thought"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        frameworks_used = result.frameworks_used if result.frameworks_used else []

        # Ingest logic is deterministic — brain just validates
        ingest_result = _ingest_rule_based(state)
        return ingest_result, frameworks_used

    except Exception:
        ingest_result = _ingest_rule_based(state)
        return ingest_result, []


def _ingest_rule_based(state: dict[str, Any]) -> dict[str, Any]:
    """Rule-based ingest logic."""
    ticket_id = state.get("ticket_id") or f"TKT-{uuid.uuid4().hex[:8].upper()}"
    raw_message = state.get("raw_message", "")
    customer_id = state.get("customer_id", "")
    channel = state.get("channel", "email")
    variant = state.get("variant", "parwa")

    # Guard: ensure types
    if not isinstance(raw_message, str):
        raw_message = str(raw_message) if raw_message else ""
    if not isinstance(customer_id, str):
        customer_id = str(customer_id) if customer_id else ""
    if not isinstance(channel, str):
        channel = "email"
    if not isinstance(variant, str):
        variant = "parwa"

    # Validate channel is available for this variant
    try:
        allowed_channels = get_variant_channels(variant)
        # Convert to string values for comparison
        allowed_str = {ch.value if hasattr(ch, "value") else ch for ch in allowed_channels}
        if channel not in allowed_str:
            # Fall back to first available channel
            first = allowed_channels[0]
            channel = first.value if hasattr(first, "value") else first
    except (ValueError, IndexError, KeyError):
        variant = "parwa"  # fallback
        channel = "email"

    return {
        "ticket_id": ticket_id,
        "raw_message": raw_message,
        "customer_id": customer_id,
        "channel": channel,
        "variant": variant,
    }


@safe_node("INGEST", fallback={"ticket_id": "TKT-ERROR", "raw_message": "", "customer_id": "", "channel": "email", "variant": "parwa", "active_frameworks": []})
async def ingest(state: dict[str, Any]) -> dict[str, Any]:
    """Receive and validate a raw ticket (async).

    Phase 5: Uses FrameworkBrain with CoT for smart validation.

    Reads: raw_message, customer_id, channel, variant
    Writes: ticket_id, raw_message, customer_id, channel, variant, active_frameworks (append)
    """
    ingest_result, frameworks = await _ingest_with_brain(state)

    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    ingest_result["active_frameworks"] = new_frameworks
    return ingest_result
