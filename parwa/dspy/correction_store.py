"""Correction Store — Persistent JSON-based store for PARWA feedback corrections.

Phase 6: This is the backbone of the self-improving system. Every time a ticket
is rejected, approved with modifications, or generates escalation feedback, the
correction is recorded here. Agent Lightning reads from this store to inject
few-shot examples and learned rules into prompts.

Design decisions:
  - FILE-BASED (JSON): Simple, persistent, works without any database infra.
  - THREAD-SAFE: Uses atomic writes (write-to-temp + rename) to avoid corruption.
  - Append-friendly: Corrections are stored as a list; new ones are appended.
  - Pattern extraction: When >= 5 similar corrections exist, auto-extract rules.

Correction types:
  - "rejected": Ticket was rejected by the customer or quality gate.
  - "approved": Ticket was approved with modifications (positive signal).
  - "corrected": A human corrected the AI's response.
  - "escalation_feedback": Feedback from an escalation handler.

Storage: /home/z/my-project/parwa/parwa/dspy/corrections.json
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("parwa.dspy.correction_store")

# ─── Constants ──────────────────────────────────────────────────────────────────

CORRECTION_TYPES = frozenset({"rejected", "approved", "corrected", "escalation_feedback"})
PATTERN_RULE_MIN_CORRECTIONS = 5
DEFAULT_LIMIT = 50
MAX_FEW_SHOT = 3

# Default path for the correction store file
_STORE_DIR = Path(__file__).parent
STORE_PATH = _STORE_DIR / "corrections.json"

# ─── Thread lock for write operations ────────────────────────────────────────────

_write_lock = threading.Lock()


# ─── Data Schema ─────────────────────────────────────────────────────────────────

def _empty_store() -> dict[str, Any]:
    """Return an empty correction store structure."""
    return {
        "version": 1,
        "created_at": time.time(),
        "last_updated": time.time(),
        "corrections": [],
        "pattern_rules": [],
        "stats": {
            "total_corrections": 0,
            "by_type": {t: 0 for t in CORRECTION_TYPES},
            "by_intent": {},
        },
    }


# ─── File I/O (atomic writes) ────────────────────────────────────────────────────

def _load_store(path: Path | None = None) -> dict[str, Any]:
    """Load the correction store from disk. Returns empty store if missing/corrupt."""
    p = path or STORE_PATH
    if not p.exists():
        return _empty_store()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # Validate basic structure
        if "corrections" not in data:
            logger.warning("correction_store: missing 'corrections' key, reinitializing")
            return _empty_store()
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("correction_store: failed to load (%s), starting fresh", exc)
        return _empty_store()


def _save_store(store: dict[str, Any], path: Path | None = None) -> None:
    """Save the correction store to disk using atomic write (temp + rename).

    Atomic write prevents corruption if the process crashes mid-write.
    """
    p = path or STORE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)

    store["last_updated"] = time.time()

    try:
        # Write to a temporary file first, then atomically rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(p.parent), suffix=".tmp", prefix="corrections_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(store, f, indent=2, ensure_ascii=False)
            # Atomic rename (POSIX) — on Windows this may fail if dest exists
            os.replace(tmp_path, str(p))
        except BaseException:
            # Clean up temp file on any error
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError as exc:
        logger.error("correction_store: failed to save (%s)", exc)


# ─── Public API ──────────────────────────────────────────────────────────────────

def add_correction(
    ticket_id: str,
    intent: str,
    original_response: str,
    corrected_response: str,
    correction_type: str,
    metadata: dict[str, Any] | None = None,
    *,
    node_name: str = "",
    variant: str = "parwa",
    confidence: float = 0.0,
    path: Path | None = None,
) -> dict[str, Any]:
    """Add a correction to the store.

    Args:
        ticket_id: Unique ticket identifier.
        intent: The classified intent for this ticket.
        original_response: The AI's original response.
        corrected_response: The correct/desired response.
        correction_type: One of "rejected", "approved", "corrected", "escalation_feedback".
        metadata: Optional additional metadata dict.
        node_name: Which node generated the original response.
        variant: Which variant was used (mini/parwa/high).
        confidence: Confidence score of the original response.
        path: Override store file path (for testing).

    Returns:
        The created correction record.
    """
    if correction_type not in CORRECTION_TYPES:
        raise ValueError(
            f"Invalid correction_type '{correction_type}'. "
            f"Must be one of {sorted(CORRECTION_TYPES)}"
        )

    correction = {
        "id": f"corr_{int(time.time() * 1000)}_{hash(ticket_id) % 10000:04d}",
        "ticket_id": ticket_id,
        "intent": intent,
        "original_response": original_response,
        "corrected_response": corrected_response,
        "correction_type": correction_type,
        "node_name": node_name,
        "variant": variant,
        "confidence": confidence,
        "metadata": metadata or {},
        "timestamp": time.time(),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    with _write_lock:
        store = _load_store(path)
        store["corrections"].append(correction)

        # Update stats
        stats = store.setdefault("stats", {})
        stats["total_corrections"] = stats.get("total_corrections", 0) + 1
        by_type = stats.setdefault("by_type", {})
        by_type[correction_type] = by_type.get(correction_type, 0) + 1
        by_intent = stats.setdefault("by_intent", {})
        by_intent[intent] = by_intent.get(intent, 0) + 1

        _save_store(store, path)

    logger.info(
        "correction_store: added %s correction for ticket=%s intent=%s",
        correction_type, ticket_id, intent,
    )
    return correction


def get_corrections(
    intent: str | None = None,
    correction_type: str | None = None,
    node_name: str | None = None,
    limit: int = DEFAULT_LIMIT,
    *,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Query corrections from the store.

    Args:
        intent: Filter by intent (exact match).
        correction_type: Filter by correction type.
        node_name: Filter by node name.
        limit: Maximum number of corrections to return.
        path: Override store file path (for testing).

    Returns:
        List of correction records, most recent first.
    """
    store = _load_store(path)
    corrections = store.get("corrections", [])

    # Apply filters
    if intent is not None:
        corrections = [c for c in corrections if c.get("intent") == intent]
    if correction_type is not None:
        corrections = [c for c in corrections if c.get("correction_type") == correction_type]
    if node_name is not None:
        corrections = [c for c in corrections if c.get("node_name") == node_name]

    # Most recent first
    corrections.sort(key=lambda c: c.get("timestamp", 0), reverse=True)

    return corrections[:limit]


def get_few_shot_examples(
    intent: str,
    limit: int = MAX_FEW_SHOT,
    *,
    correction_types: tuple[str, ...] | None = None,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Get relevant past corrections for few-shot injection into prompts.

    Prioritizes "rejected" and "corrected" types as they provide the most
    learning signal. Returns the most recent, high-signal examples.

    Args:
        intent: The intent to find examples for.
        limit: Max examples to return (default 3, token budget).
        correction_types: Filter to specific correction types.
        path: Override store file path (for testing).

    Returns:
        List of correction records suitable for few-shot injection.
    """
    store = _load_store(path)
    corrections = store.get("corrections", [])

    # Filter to matching intent
    matching = [c for c in corrections if c.get("intent") == intent]

    # Filter to specified correction types (default: rejected + corrected — most signal)
    if correction_types is None:
        correction_types = ("rejected", "corrected", "escalation_feedback")
    matching = [c for c in matching if c.get("correction_type") in correction_types]

    # Sort by recency (most recent first)
    matching.sort(key=lambda c: c.get("timestamp", 0), reverse=True)

    return matching[:limit]


def get_pattern_rules(
    intent: str | None = None,
    *,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Get auto-extracted pattern rules from the correction store.

    Pattern rules are extracted when >= 5 similar corrections exist.
    They represent common mistakes and their corrections.

    Args:
        intent: Filter rules by intent. None returns all rules.
        path: Override store file path (for testing).

    Returns:
        List of pattern rule dicts.
    """
    store = _load_store(path)
    rules = store.get("pattern_rules", [])

    if intent is not None:
        rules = [r for r in rules if r.get("intent") == intent or r.get("intent") == "*"]

    return rules


def extract_pattern_rules(
    *,
    force: bool = False,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Analyze corrections and extract common patterns as rules.

    When we have >= PATTERN_RULE_MIN_CORRECTIONS (5) corrections for the same
    (intent, node_name) pair, we extract a pattern rule. The rule summarizes
    the common mistake and the correct behavior.

    Args:
        force: If True, re-extract rules even if they already exist.
        path: Override store file path (for testing).

    Returns:
        List of newly extracted pattern rules.
    """
    with _write_lock:
        store = _load_store(path)
        corrections = store.get("corrections", [])

        # Group corrections by (intent, node_name)
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for c in corrections:
            key = (c.get("intent", "unknown"), c.get("node_name", "unknown"))
            groups.setdefault(key, []).append(c)

        # Also group by just intent (cross-node patterns)
        intent_groups: dict[str, list[dict[str, Any]]] = {}
        for c in corrections:
            intent_groups.setdefault(c.get("intent", "unknown"), []).append(c)

        existing_rules = store.get("pattern_rules", [])
        existing_keys = {
            (r.get("intent"), r.get("node_name")) for r in existing_rules
        }

        new_rules: list[dict[str, Any]] = []

        # Extract rules from (intent, node_name) groups
        for (intent, node_name), group in groups.items():
            if len(group) < PATTERN_RULE_MIN_CORRECTIONS:
                continue
            if not force and (intent, node_name) in existing_keys:
                continue

            # Count correction types in this group
            type_counts: dict[str, int] = {}
            for c in group:
                ct = c.get("correction_type", "unknown")
                type_counts[ct] = type_counts.get(ct, 0) + 1

            # Build rule description
            dominant_type = max(type_counts, key=type_counts.get)  # type: ignore[arg-type]
            rule_text = _build_rule_text(intent, node_name, type_counts, len(group))

            rule = {
                "id": f"rule_{int(time.time())}_{hash(f'{intent}_{node_name}') % 10000:04d}",
                "intent": intent,
                "node_name": node_name,
                "rule_text": rule_text,
                "support_count": len(group),
                "type_distribution": type_counts,
                "dominant_correction_type": dominant_type,
                "extracted_at": time.time(),
                "extracted_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            new_rules.append(rule)

        # Extract cross-node intent rules (when many corrections for same intent)
        for intent, group in intent_groups.items():
            if len(group) < PATTERN_RULE_MIN_CORRECTIONS * 2:
                continue
            cross_key = (intent, "*")
            if not force and cross_key in existing_keys:
                continue

            type_counts: dict[str, int] = {}
            for c in group:
                ct = c.get("correction_type", "unknown")
                type_counts[ct] = type_counts.get(ct, 0) + 1

            rule_text = _build_cross_node_rule_text(intent, type_counts, len(group))

            rule = {
                "id": f"rule_cross_{int(time.time())}_{hash(intent) % 10000:04d}",
                "intent": intent,
                "node_name": "*",
                "rule_text": rule_text,
                "support_count": len(group),
                "type_distribution": type_counts,
                "dominant_correction_type": max(type_counts, key=type_counts.get),  # type: ignore[arg-type]
                "extracted_at": time.time(),
                "extracted_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            new_rules.append(rule)

        if new_rules:
            # Replace existing rules for the same keys
            new_keys = {(r["intent"], r["node_name"]) for r in new_rules}
            filtered_existing = [
                r for r in existing_rules
                if (r.get("intent"), r.get("node_name")) not in new_keys
            ]
            store["pattern_rules"] = filtered_existing + new_rules
            _save_store(store, path)

            logger.info(
                "correction_store: extracted %d new pattern rules",
                len(new_rules),
            )

    return new_rules


def get_stats(*, path: Path | None = None) -> dict[str, Any]:
    """Return stats about the correction store.

    Returns:
        Dict with total_corrections, by_type, by_intent, pattern_rules_count, etc.
    """
    store = _load_store(path)
    corrections = store.get("corrections", [])
    rules = store.get("pattern_rules", [])

    # Re-compute stats from actual data (more accurate than stored stats)
    by_type: dict[str, int] = {}
    by_intent: dict[str, int] = {}
    by_node: dict[str, int] = {}

    for c in corrections:
        ct = c.get("correction_type", "unknown")
        by_type[ct] = by_type.get(ct, 0) + 1
        intent = c.get("intent", "unknown")
        by_intent[intent] = by_intent.get(intent, 0) + 1
        node = c.get("node_name", "unknown")
        by_node[node] = by_node.get(node, 0) + 1

    return {
        "total_corrections": len(corrections),
        "total_pattern_rules": len(rules),
        "by_type": by_type,
        "by_intent": by_intent,
        "by_node": by_node,
        "store_version": store.get("version", 0),
        "created_at": store.get("created_at"),
        "last_updated": store.get("last_updated"),
    }


def clear_store(*, path: Path | None = None) -> None:
    """Clear all corrections and rules. Mainly for testing."""
    with _write_lock:
        _save_store(_empty_store(), path)
    logger.info("correction_store: cleared")


# ─── Internal Helpers ─────────────────────────────────────────────────────────────

def _build_rule_text(
    intent: str,
    node_name: str,
    type_counts: dict[str, int],
    total: int,
) -> str:
    """Build a human-readable rule text from correction statistics."""
    rejected = type_counts.get("rejected", 0)
    corrected = type_counts.get("corrected", 0)

    parts = []
    if rejected > 0:
        parts.append(f"{rejected} rejected tickets")
    if corrected > 0:
        parts.append(f"{corrected} corrected responses")

    signal_desc = " and ".join(parts) if parts else f"{total} corrections"

    # Intent-specific advice
    intent_advice = _get_intent_specific_advice(intent)

    rule = (
        f"For intent '{intent}' at {node_name}: "
        f"Based on {signal_desc}, {intent_advice}"
    )
    return rule


def _build_cross_node_rule_text(
    intent: str,
    type_counts: dict[str, int],
    total: int,
) -> str:
    """Build a cross-node rule text."""
    rejected = type_counts.get("rejected", 0)
    corrected = type_counts.get("corrected", 0)

    intent_advice = _get_intent_specific_advice(intent)

    return (
        f"For intent '{intent}' (across all nodes): "
        f"Based on {rejected} rejections and {corrected} corrections "
        f"(total {total}), {intent_advice}"
    )


def _get_intent_specific_advice(intent: str) -> str:
    """Return intent-specific advice based on known patterns."""
    advice_map = {
        "refund_request": "always check CRM order status first and verify refund eligibility before processing",
        "order_status": "always fetch live order data before providing status updates",
        "billing_inquiry": "always verify billing details against CRM records before explaining charges",
        "cancel_order": "always confirm cancellation policy and check order fulfillment status first",
        "product_issue": "always gather specific error details and check known issues KB before troubleshooting",
        "complaint": "always acknowledge the frustration first before offering solutions",
        "escalation": "always verify the customer's issue cannot be resolved at current tier before escalating",
        "general_inquiry": "always check KB and FAQ before generating a response",
    }
    return advice_map.get(
        intent,
        "review the correction history to avoid repeating past mistakes",
    )
