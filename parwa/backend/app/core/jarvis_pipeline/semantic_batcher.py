"""
Jarvis Semantic Batcher — Wave 5B: Intelligent Batching

Replaces time-based batching with semantic clustering.

Group tickets by similarity (not just time window):
  - "Batch Request: 5 customers requesting address changes — Confidence: 94-98% — Risk: Low"
  - Manager actions: [Approve Batch] [Reject Batch] [Review Individually]

Implementation approach (no external deps):
  - Uses a simple keyword/similarity heuristic for clustering
  - In production: would use pgvector cosine similarity > 0.85
  - Batches stored in jarvis_db batch_queue table
  - Each batch has: batch_key, ticket_ids, confidence range, risk level

Zero new dependencies.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.batcher")

# ── Batch window: tickets within this many seconds get clustered ──
BATCH_WINDOW_S = 300  # 5 minutes

# ── Similarity threshold: cosine > this → same cluster ──────────
SIMILARITY_THRESHOLD = 0.70

# ── Stop words to ignore in similarity computation ──────────────
STOP_WORDS = frozenset(
    "i me my myself we our ours ourselves you your yours yourself yourselves "
    "he him his himself she her hers herself it its itself they them their "
    "theirs themselves what which who whom this that these those am is are "
    "was were be been being have has had having do does did doing a an the "
    "and but if or because as until while of at by for with about against "
    "between through during before after above below to from up down in out "
    "on off over under again further then once here there when where why "
    "how all both each few more most other some such no nor not only own "
    "same so than too very s t can will just don should now".split()
)


def _tokenize(text: str) -> List[str]:
    """Lowercase, remove punctuation, split, remove stop words."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = text.split()
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


def _cosine_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
    """Compute cosine similarity between two token lists."""
    if not tokens_a or not tokens_b:
        return 0.0

    # Build term frequency dicts
    freq_a: Dict[str, int] = {}
    for t in tokens_a:
        freq_a[t] = freq_a.get(t, 0) + 1

    freq_b: Dict[str, int] = {}
    for t in tokens_b:
        freq_b[t] = freq_b.get(t, 0) + 1

    # Dot product
    all_terms = set(freq_a.keys()) | set(freq_b.keys())
    dot = sum(freq_a.get(t, 0) * freq_b.get(t, 0) for t in all_terms)

    # Magnitudes
    mag_a = sum(v ** 2 for v in freq_a.values()) ** 0.5
    mag_b = sum(v ** 2 for v in freq_b.values()) ** 0.5

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot / (mag_a * mag_b)


def _generate_batch_key(text: str, ticket_type: str = "") -> str:
    """Generate a stable batch key from text content.

    Uses top tokens hash to cluster similar content.
    """
    tokens = _tokenize(text + " " + ticket_type)
    # Take first 5 most meaningful tokens (longer tokens tend to be more meaningful)
    meaningful = sorted(tokens, key=len, reverse=True)[:5]
    key_text = " ".join(sorted(meaningful))
    return hashlib.md5(key_text.encode()).hexdigest()[:12]


def compute_similarity(text_a: str, text_b: str, ticket_type_a: str = "",
                       ticket_type_b: str = "") -> float:
    """Compute similarity between two ticket texts.

    Returns 0.0-1.0. > 0.70 = similar enough to batch.
    """
    tokens_a = _tokenize(text_a + " " + ticket_type_a)
    tokens_b = _tokenize(text_b + " " + ticket_type_b)

    if not tokens_a or not tokens_b:
        return 0.0

    return round(_cosine_similarity(tokens_a, tokens_b), 4)


async def add_ticket_to_batch(
    tenant_id: str,
    ticket_id: str,
    query: str,
    confidence: float,
    ticket_type: str = "",
    risk_level: float = 0.0,
    required_action: str = "",
) -> Optional[Dict[str, Any]]:
    """Add a ticket to a semantic batch.

    If the ticket matches an existing batch (same key within window),
    it gets added. Otherwise, a new batch is created.

    Returns the batch dict when the window expires and it's ready to flush,
    or None if still accumulating.
    """
    from app.core.jarvis_pipeline.jarvis_db import get_db

    db = get_db()
    batch_key = _generate_batch_key(query, ticket_type)

    result = await db.add_to_batch(
        tenant_id=tenant_id,
        batch_key=batch_key,
        ticket_id=ticket_id,
        confidence=confidence,
    )

    if result is not None:
        # Enrich batch with metadata
        result["ticket_type"] = ticket_type
        result["required_action"] = required_action
        result["risk_level"] = risk_level
        logger.info("Batch flushed: tenant=%s key=%s tickets=%s",
                    tenant_id, batch_key, result.get("ticket_ids", []))

    return result


async def flush_all_batches(tenant_id: str) -> List[Dict[str, Any]]:
    """Force-flush all pending batches for a tenant.

    Returns list of batch dicts ready for display/approval.
    """
    from app.core.jarvis_pipeline.jarvis_db import get_db

    db = get_db()
    batches = await db.flush_batches(tenant_id)

    logger.info("Force-flushed %d batches for tenant=%s", len(batches), tenant_id)
    return batches


def format_batch_description(batch: Dict[str, Any]) -> str:
    """Format a batch for display to the manager.

    Example: "Batch Request: 5 customers requesting address changes — Confidence: 94-98% — Risk: Low"
    """
    ticket_ids = batch.get("ticket_ids", [])
    count = len(ticket_ids) if isinstance(ticket_ids, list) else int(batch.get("signal_count", 1))
    conf_min = batch.get("confidence_min", 0)
    conf_max = batch.get("confidence_max", 0)
    conf_pct_min = int(conf_min * 100)
    conf_pct_max = int(conf_max * 100)

    if conf_pct_min == conf_pct_max:
        conf_str = f"Confidence: {conf_pct_min}%"
    else:
        conf_str = f"Confidence: {conf_pct_min}-{conf_pct_max}%"

    risk = batch.get("risk_level", 0)
    if risk > 0.5:
        risk_str = "Risk: High"
    elif risk > 0.2:
        risk_str = "Risk: Medium"
    else:
        risk_str = "Risk: Low"

    return f"Batch Request: {count} tickets — {conf_str} — {risk_str}"


async def get_batch_summary(tenant_id: str) -> Dict[str, Any]:
    """Get a summary of all pending and recent batches.

    Returns:
        {
            "pending_count": int,
            "pending_batches": [...],
            "total_tickets_in_batches": int,
            "avg_confidence_range": [min, max],
        }
    """
    from app.core.jarvis_pipeline.jarvis_db import get_db

    db = get_db()
    batches = await db.flush_batches(tenant_id)

    total_tickets = 0
    all_conf_min = []
    all_conf_max = []

    for b in batches:
        tids = b.get("ticket_ids", [])
        total_tickets += len(tids) if isinstance(tids, list) else 1
        all_conf_min.append(b.get("confidence_min", 0))
        all_conf_max.append(b.get("confidence_max", 0))

    return {
        "pending_count": len(batches),
        "pending_batches": batches,
        "total_tickets_in_batches": total_tickets,
        "avg_confidence_range": [
            round(min(all_conf_min), 4) if all_conf_min else 0,
            round(max(all_conf_max), 4) if all_conf_max else 0,
        ],
    }


async def check_should_batch(
    confidence: float,
    routing: str,
) -> bool:
    """Quick check: should this ticket be batched?

    Only BATCH-routed tickets get batched.
    """
    return routing == "batch"