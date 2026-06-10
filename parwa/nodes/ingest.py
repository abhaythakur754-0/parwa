"""Node 1: INGEST — Receives raw ticket from any channel.

Router Agent node. Entry point of the PARWA pipeline.
Validates channel availability for the variant and generates a ticket ID.
"""

from __future__ import annotations

import uuid
from typing import Any

from parwa.config import get_variant_channels
from parwa.state import TicketChannel
from parwa.utils.node_base import safe_node


@safe_node("INGEST")
def ingest(state: dict[str, Any]) -> dict[str, Any]:
    """Receive and validate a raw ticket.

    Reads: raw_message, customer_id, channel, variant
    Writes: ticket_id, raw_message, customer_id, channel, variant
    """
    ticket_id = state.get("ticket_id") or f"TKT-{uuid.uuid4().hex[:8].upper()}"
    raw_message = state.get("raw_message", "")
    customer_id = state.get("customer_id", "")
    channel = state.get("channel", "email")
    variant = state.get("variant", "parwa")

    # Validate channel is available for this variant
    try:
        allowed_channels = get_variant_channels(variant)
        # Convert to string values for comparison
        allowed_str = {ch.value if hasattr(ch, "value") else ch for ch in allowed_channels}
        if channel not in allowed_str:
            # Fall back to first available channel
            first = allowed_channels[0]
            channel = first.value if hasattr(first, "value") else first
    except ValueError:
        variant = "parwa"  # fallback

    return {
        "ticket_id": ticket_id,
        "raw_message": raw_message,
        "customer_id": customer_id,
        "channel": channel,
        "variant": variant,
    }
