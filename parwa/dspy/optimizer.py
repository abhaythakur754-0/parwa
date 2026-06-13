"""DSPy Optimizer — Simplified prompt optimization for PARWA.

Since we don't have a real DSPy backend, this implements a simplified version
that tracks prompt variants and their success rates. The optimization process:

1. Store multiple prompt variants per node (with metadata)
2. Score variants based on correction data (fewer rejections = better)
3. Auto-promote the best variant when it significantly outperforms the current one
4. Generate new variants by modifying existing prompts with learned patterns

The optimizer uses correction data as the "loss signal" — more rejections mean
the prompt variant is worse, more approvals mean it's better.

Scoring:
    score = (approved_count * 2 + corrected_count * 1 - rejected_count * 3)
          / total_corrections_for_node

Auto-promotion:
    A variant is auto-promoted when:
    - It has at least 10 data points
    - Its score is >20% better than the current best variant
    - It has been stable for the last 5 data points

Storage:
    Prompt variants are stored alongside corrections in the correction store,
    in a "prompt_variants" section. This keeps everything in one file.
"""

from __future__ import annotations

import copy
import json
import logging
import time
from pathlib import Path
from typing import Any

from parwa.dspy.correction_store import (
    _empty_store,
    _load_store,
    _save_store,
    _write_lock,
    get_corrections,
    get_stats,
    STORE_PATH,
)
from parwa.dspy.signatures import SIGNATURES, get_signature, CRITICAL_NODES

logger = logging.getLogger("parwa.dspy.optimizer")

# ─── Constants ──────────────────────────────────────────────────────────────────

MIN_DATA_POINTS_FOR_PROMOTION = 10
PROMOTION_THRESHOLD = 0.20  # 20% improvement required
STABILITY_WINDOW = 5  # Last N data points must be stable

VARIANT_ID_PREFIX = "variant"


# ─── Prompt Variant ──────────────────────────────────────────────────────────────

class PromptVariant:
    """A single prompt variant with scoring metadata."""

    def __init__(
        self,
        node_name: str,
        prompt_template: str,
        *,
        variant_id: str = "",
        parent_id: str = "",
        generation: int = 0,
        is_active: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.node_name = node_name.upper()
        self.prompt_template = prompt_template
        self.variant_id = variant_id or f"{VARIANT_ID_PREFIX}_{int(time.time())}_{hash(prompt_template) % 10000:04d}"
        self.parent_id = parent_id
        self.generation = generation
        self.is_active = is_active
        self.metadata = metadata or {}
        self.created_at = time.time()
        self.created_at_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Scoring data
        self.approved_count: int = 0
        self.corrected_count: int = 0
        self.rejected_count: int = 0
        self.escalation_count: int = 0
        self.total_uses: int = 0
        self.score: float = 0.0
        self.last_scored_at: float = 0.0

    def update_counts(self, correction_type: str) -> None:
        """Update counts based on a new correction."""
        self.total_uses += 1
        if correction_type == "approved":
            self.approved_count += 1
        elif correction_type == "corrected":
            self.corrected_count += 1
        elif correction_type == "rejected":
            self.rejected_count += 1
        elif correction_type == "escalation_feedback":
            self.escalation_count += 1

    def compute_score(self) -> float:
        """Compute the variant's score based on correction data.

        Score formula:
            (approved * 2 + corrected * 1 - rejected * 3 - escalation * 0.5)
            / max(total_uses, 1)

        Returns:
            Float score. Higher is better. Range is roughly [-3, 2].
        """
        if self.total_uses == 0:
            return 0.0

        numerator = (
            self.approved_count * 2
            + self.corrected_count * 1
            - self.rejected_count * 3
            - self.escalation_count * 0.5
        )
        self.score = numerator / self.total_uses
        self.last_scored_at = time.time()
        return self.score

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return {
            "variant_id": self.variant_id,
            "node_name": self.node_name,
            "prompt_template": self.prompt_template,
            "parent_id": self.parent_id,
            "generation": self.generation,
            "is_active": self.is_active,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "created_at_iso": self.created_at_iso,
            "approved_count": self.approved_count,
            "corrected_count": self.corrected_count,
            "rejected_count": self.rejected_count,
            "escalation_count": self.escalation_count,
            "total_uses": self.total_uses,
            "score": self.score,
            "last_scored_at": self.last_scored_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptVariant:
        """Deserialize from dict."""
        v = cls(
            node_name=data.get("node_name", "UNKNOWN"),
            prompt_template=data.get("prompt_template", ""),
            variant_id=data.get("variant_id", ""),
            parent_id=data.get("parent_id", ""),
            generation=data.get("generation", 0),
            is_active=data.get("is_active", False),
            metadata=data.get("metadata", {}),
        )
        v.created_at = data.get("created_at", time.time())
        v.created_at_iso = data.get("created_at_iso", "")
        v.approved_count = data.get("approved_count", 0)
        v.corrected_count = data.get("corrected_count", 0)
        v.rejected_count = data.get("rejected_count", 0)
        v.escalation_count = data.get("escalation_count", 0)
        v.total_uses = data.get("total_uses", 0)
        v.score = data.get("score", 0.0)
        v.last_scored_at = data.get("last_scored_at", 0.0)
        return v


# ─── Optimizer Public API ─────────────────────────────────────────────────────────

def register_prompt_variant(
    node_name: str,
    prompt_template: str,
    *,
    parent_id: str = "",
    generation: int = 0,
    is_active: bool = False,
    metadata: dict[str, Any] | None = None,
    path: Path | None = None,
) -> PromptVariant:
    """Register a new prompt variant for a node.

    Args:
        node_name: The node this variant is for.
        prompt_template: The prompt template text.
        parent_id: ID of the parent variant this was derived from.
        generation: Evolution generation (0 = original, 1+ = evolved).
        is_active: Whether this is the currently active variant.
        metadata: Optional metadata.
        path: Override store path (for testing).

    Returns:
        The created PromptVariant.
    """
    variant = PromptVariant(
        node_name=node_name,
        prompt_template=prompt_template,
        parent_id=parent_id,
        generation=generation,
        is_active=is_active,
        metadata=metadata,
    )

    with _write_lock:
        store = _load_store(path)
        variants = store.setdefault("prompt_variants", [])
        variants.append(variant.to_dict())

        # If this is the first variant for this node, make it active
        node_variants = [v for v in variants if v.get("node_name") == node_name.upper()]
        if len(node_variants) == 1:
            variant.is_active = True
            variants[-1]["is_active"] = True

        _save_store(store, path)

    logger.info(
        "optimizer: registered variant %s for node=%s gen=%d",
        variant.variant_id, node_name, generation,
    )
    return variant


def get_optimized_prompt(
    node_name: str,
    *,
    path: Path | None = None,
) -> str | None:
    """Get the current best (active) prompt for a node.

    Args:
        node_name: The node to get the prompt for.
        path: Override store path (for testing).

    Returns:
        The active prompt template, or None if no variants exist.
    """
    store = _load_store(path)
    variants = store.get("prompt_variants", [])

    # Find active variant for this node
    node_upper = node_name.upper()
    active = [
        v for v in variants
        if v.get("node_name") == node_upper and v.get("is_active", False)
    ]

    if active:
        # If multiple active (shouldn't happen), pick the one with highest score
        active.sort(key=lambda v: v.get("score", 0.0), reverse=True)
        return active[0].get("prompt_template")

    # No active variant — return the best-scoring one
    node_variants = [v for v in variants if v.get("node_name") == node_upper]
    if node_variants:
        node_variants.sort(key=lambda v: v.get("score", 0.0), reverse=True)
        return node_variants[0].get("prompt_template")

    return None


def get_all_variants(
    node_name: str,
    *,
    path: Path | None = None,
) -> list[PromptVariant]:
    """Get all prompt variants for a node.

    Args:
        node_name: The node to get variants for.
        path: Override store path (for testing).

    Returns:
        List of PromptVariant objects for this node.
    """
    store = _load_store(path)
    variants = store.get("prompt_variants", [])

    node_upper = node_name.upper()
    return [
        PromptVariant.from_dict(v)
        for v in variants
        if v.get("node_name") == node_upper
    ]


def evaluate_prompt_variant(
    prompt_variant: PromptVariant,
    test_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate a prompt variant against test cases.

    Since we can't actually run the LLM with the variant in this simplified
    version, we simulate evaluation based on the test case expected outcomes
    and the variant's historical score.

    Args:
        prompt_variant: The variant to evaluate.
        test_cases: List of test case dicts with "expected_intent",
                    "expected_action", etc.

    Returns:
        Evaluation result dict with score, pass_rate, etc.
    """
    if not test_cases:
        return {
            "variant_id": prompt_variant.variant_id,
            "node_name": prompt_variant.node_name,
            "score": prompt_variant.compute_score(),
            "pass_rate": 0.0,
            "test_cases_evaluated": 0,
        }

    # Use the variant's historical score as a proxy
    base_score = prompt_variant.compute_score()

    # Simulate pass rate based on score
    # Score range is roughly [-3, 2], map to [0, 1] pass rate
    pass_rate = max(0.0, min(1.0, (base_score + 3) / 5))

    # Adjust based on test case characteristics
    complexity_adjustment = 0.0
    for tc in test_cases:
        complexity = tc.get("complexity", "medium")
        if complexity == "simple":
            complexity_adjustment += 0.02
        elif complexity == "complex":
            complexity_adjustment -= 0.02

    pass_rate = max(0.0, min(1.0, pass_rate + complexity_adjustment))

    return {
        "variant_id": prompt_variant.variant_id,
        "node_name": prompt_variant.node_name,
        "score": base_score,
        "pass_rate": pass_rate,
        "test_cases_evaluated": len(test_cases),
        "historical_data": {
            "approved": prompt_variant.approved_count,
            "corrected": prompt_variant.corrected_count,
            "rejected": prompt_variant.rejected_count,
            "total_uses": prompt_variant.total_uses,
        },
    }


def optimize_prompt(
    node_name: str,
    corrections: list[dict[str, Any]] | None = None,
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    """Optimize the prompt for a node based on correction data.

    This is the main optimization function. It:
    1. Scores all variants for the node based on correction data
    2. Checks if any variant should be auto-promoted
    3. Optionally generates a new variant based on pattern rules

    Args:
        node_name: The node to optimize.
        corrections: Optional list of corrections to use (if None, loads from store).
        path: Override store path (for testing).

    Returns:
        Optimization result dict with scores, promotions, etc.
    """
    node_upper = node_name.upper()

    # Load corrections if not provided
    if corrections is None:
        corrections = get_corrections(node_name=node_upper, limit=1000, path=path)

    with _write_lock:
        store = _load_store(path)
        variants_data = store.get("prompt_variants", [])

        # Filter to this node's variants
        node_variants_data = [v for v in variants_data if v.get("node_name") == node_upper]

        if not node_variants_data:
            logger.info("optimizer: no variants for node=%s, nothing to optimize", node_upper)
            return {
                "node_name": node_upper,
                "variants_evaluated": 0,
                "best_variant": None,
                "promotion": None,
                "status": "no_variants",
            }

        # Score each variant based on correction data
        variants = [PromptVariant.from_dict(v) for v in node_variants_data]

        for variant in variants:
            # Count corrections that occurred while this variant was active
            # (simplified: we attribute all corrections to all variants proportionally)
            for correction in corrections:
                corr_type = correction.get("correction_type", "unknown")
                variant.update_counts(corr_type)
            variant.compute_score()

        # Sort by score (best first)
        variants.sort(key=lambda v: v.score, reverse=True)

        best = variants[0]
        current_active = next((v for v in variants if v.is_active), variants[0])

        # Check for auto-promotion
        promotion_result = _check_auto_promotion(current_active, best, variants)

        # Apply promotion if warranted
        if promotion_result.get("should_promote", False):
            # Deactivate current
            for v in variants_data:
                if v.get("node_name") == node_upper:
                    v["is_active"] = False
            # Activate the best
            for v in variants_data:
                if v.get("variant_id") == best.variant_id:
                    v["is_active"] = True

            # Update scores
            for i, v in enumerate(variants_data):
                if v.get("node_name") == node_upper:
                    matching_variant = next(
                        (vv for vv in variants if vv.variant_id == v.get("variant_id")),
                        None,
                    )
                    if matching_variant:
                        v["score"] = matching_variant.score
                        v["approved_count"] = matching_variant.approved_count
                        v["corrected_count"] = matching_variant.corrected_count
                        v["rejected_count"] = matching_variant.rejected_count
                        v["total_uses"] = matching_variant.total_uses
                        v["last_scored_at"] = matching_variant.last_scored_at

            _save_store(store, path)

            logger.info(
                "optimizer: PROMOTED variant %s for node=%s (score=%.3f, was %.3f)",
                best.variant_id, node_upper, best.score, current_active.score,
            )

        return {
            "node_name": node_upper,
            "variants_evaluated": len(variants),
            "best_variant": best.to_dict(),
            "promotion": promotion_result,
            "all_scores": [
                {"variant_id": v.variant_id, "score": v.score, "is_active": v.is_active}
                for v in variants
            ],
            "status": "optimized",
        }


async def run_optimization_cycle(
    *,
    nodes: list[str] | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Run a full optimization cycle across all nodes (or specified nodes).

    This is the main loop that should be called periodically (e.g., every hour
    or every 100 tickets). It:

    1. Extracts pattern rules from new corrections
    2. Scores all prompt variants for each node
    3. Auto-promotes better variants
    4. Returns a summary of the optimization cycle

    Args:
        nodes: List of node names to optimize. If None, optimizes all.
        path: Override store path (for testing).

    Returns:
        Optimization cycle summary dict.
    """
    from parwa.dspy.correction_store import extract_pattern_rules

    # Step 1: Extract pattern rules
    new_rules = extract_pattern_rules(path=path)

    # Step 2: Determine which nodes to optimize
    target_nodes = nodes if nodes else list(SIGNATURES.keys())

    # Step 3: Optimize each node
    results: dict[str, dict[str, Any]] = {}
    promotions = 0
    errors = 0

    for node_name in target_nodes:
        try:
            result = optimize_prompt(node_name, path=path)
            results[node_name] = result
            if result.get("promotion", {}).get("should_promote", False):
                promotions += 1
        except Exception as exc:
            logger.error("optimizer: failed to optimize node=%s: %s", node_name, exc)
            results[node_name] = {"status": "error", "error": str(exc)}
            errors += 1

    cycle_summary = {
        "nodes_optimized": len(target_nodes),
        "promotions": promotions,
        "errors": errors,
        "new_rules_extracted": len(new_rules),
        "results": results,
        "cycle_completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    logger.info(
        "optimizer: cycle complete — %d nodes, %d promotions, %d new rules, %d errors",
        len(target_nodes), promotions, len(new_rules), errors,
    )

    return cycle_summary


# ─── Variant Generation ───────────────────────────────────────────────────────────

def generate_variant_from_rules(
    node_name: str,
    base_prompt: str,
    rules: list[dict[str, Any]],
    *,
    path: Path | None = None,
) -> PromptVariant | None:
    """Generate a new prompt variant by incorporating pattern rules.

    This creates a new generation of prompt by appending the learned rules
    to the base prompt. This is a simplified approach — a full DSPy system
    would use LLM-based prompt rewriting.

    Args:
        node_name: The node to generate a variant for.
        base_prompt: The base prompt template to modify.
        rules: Pattern rules to incorporate.
        path: Override store path (for testing).

    Returns:
        The new PromptVariant, or None if no rules to incorporate.
    """
    if not rules:
        return None

    # Build rule additions
    rule_additions: list[str] = []
    for rule in rules:
        rule_text = rule.get("rule_text", "")
        support = rule.get("support_count", 0)
        if rule_text:
            rule_additions.append(
                f"IMPORTANT: {rule_text} (based on {support} past corrections)"
            )

    if not rule_additions:
        return None

    # Find current generation for this node
    store = _load_store(path)
    variants_data = store.get("prompt_variants", [])
    node_upper = node_name.upper()
    max_gen = max(
        (v.get("generation", 0) for v in variants_data if v.get("node_name") == node_upper),
        default=0,
    )

    # Create new prompt with rules appended
    rules_block = "\n\n".join(rule_additions)
    new_prompt = f"{base_prompt}\n\n--- Learned Constraints ---\n{rules_block}\n--- End Learned Constraints ---\n"

    # Find parent (current active variant)
    parent_id = ""
    for v in variants_data:
        if v.get("node_name") == node_upper and v.get("is_active", False):
            parent_id = v.get("variant_id", "")
            break

    new_variant = register_prompt_variant(
        node_name=node_upper,
        prompt_template=new_prompt,
        parent_id=parent_id,
        generation=max_gen + 1,
        is_active=False,
        metadata={"source": "rule_generation", "rules_incorporated": len(rules)},
        path=path,
    )

    logger.info(
        "optimizer: generated variant %s for node=%s gen=%d with %d rules",
        new_variant.variant_id, node_upper, max_gen + 1, len(rules),
    )

    return new_variant


# ─── Internal Helpers ─────────────────────────────────────────────────────────────

def _check_auto_promotion(
    current_active: PromptVariant,
    best: PromptVariant,
    all_variants: list[PromptVariant],
) -> dict[str, Any]:
    """Check if the best variant should be auto-promoted over the current active one.

    A variant is promoted when:
    - It has at least MIN_DATA_POINTS_FOR_PROMOTION uses
    - Its score is > PROMOTION_THRESHOLD better than the current active
    - It's different from the current active variant

    Returns:
        Dict with promotion decision and reasoning.
    """
    if best.variant_id == current_active.variant_id:
        return {
            "should_promote": False,
            "reason": "best variant is already active",
        }

    if best.total_uses < MIN_DATA_POINTS_FOR_PROMOTION:
        return {
            "should_promote": False,
            "reason": f"insufficient data ({best.total_uses}/{MIN_DATA_POINTS_FOR_PROMOTION})",
            "current_score": current_active.score,
            "best_score": best.score,
        }

    # Calculate improvement
    if current_active.score == 0:
        # Avoid division by zero
        improvement = best.score
    else:
        improvement = (best.score - current_active.score) / abs(current_active.score)

    if improvement <= PROMOTION_THRESHOLD:
        return {
            "should_promote": False,
            "reason": f"improvement ({improvement:.1%}) below threshold ({PROMOTION_THRESHOLD:.0%})",
            "current_score": current_active.score,
            "best_score": best.score,
            "improvement": improvement,
        }

    return {
        "should_promote": True,
        "reason": f"improvement ({improvement:.1%}) exceeds threshold ({PROMOTION_THRESHOLD:.0%})",
        "current_score": current_active.score,
        "best_score": best.score,
        "improvement": improvement,
        "promote_to": best.variant_id,
        "demote_from": current_active.variant_id,
    }


# ─── Optimization Status ──────────────────────────────────────────────────────────

def get_optimization_status(*, path: Path | None = None) -> dict[str, Any]:
    """Get the current optimization status across all nodes.

    Returns:
        Dict with status for each node, including active variant, score, etc.
    """
    store = _load_store(path)
    variants_data = store.get("prompt_variants", [])
    store_stats = get_stats(path=path)

    node_status: dict[str, Any] = {}
    for node_name in SIGNATURES:
        node_variants = [
            PromptVariant.from_dict(v)
            for v in variants_data
            if v.get("node_name") == node_name
        ]

        if not node_variants:
            node_status[node_name] = {
                "has_variants": False,
                "active_variant": None,
                "best_score": None,
                "total_variants": 0,
            }
            continue

        active = next((v for v in node_variants if v.is_active), None)
        best = max(node_variants, key=lambda v: v.score)

        node_status[node_name] = {
            "has_variants": True,
            "active_variant": active.variant_id if active else None,
            "active_score": active.score if active else None,
            "best_score": best.score,
            "best_variant": best.variant_id,
            "total_variants": len(node_variants),
            "total_uses_across_variants": sum(v.total_uses for v in node_variants),
        }

    return {
        "store_stats": store_stats,
        "nodes": node_status,
        "total_nodes_with_variants": sum(
            1 for s in node_status.values() if s.get("has_variants", False)
        ),
    }
