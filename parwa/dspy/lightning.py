"""Agent Lightning V1 — Few-shot injection system for PARWA.

Agent Lightning makes PARWA self-improving by injecting lessons from past
mistakes into prompts. Instead of hoping the model gets better, we EXPLICITLY
tell it what went wrong before and how to avoid it.

How it works:
  1. Correction Store records every rejection, correction, and escalation feedback
  2. When a prompt is built for a node, Lightning checks the correction store
  3. Relevant few-shot examples are injected into the prompt
  4. Pattern rules (extracted from 5+ similar corrections) are also injected
  5. The model sees "PREVIOUS MISTAKE" warnings and "LEARNED RULE" constraints

Format for few-shot injection:
    PREVIOUS MISTAKE (similar ticket): You said "X" but correct answer was "Y" because "Z"
    Avoid making the same error.

Format for pattern rules:
    LEARNED RULE: Always check CRM first before processing refunds
                  (extracted from 15 rejected tickets)

Variant-aware budget:
    - mini: 1 example max, no pattern rules
    - parwa: 2 examples max, 1 pattern rule
    - high: 3 examples max, 2 pattern rules

This is PROMPT-LEVEL optimization (not model weights) — works with any LLM.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from parwa.dspy.correction_store import get_few_shot_examples, get_pattern_rules
from parwa.dspy.signatures import get_signature, CRITICAL_NODES

logger = logging.getLogger("parwa.dspy.lightning")

# ─── Constants ────────────────────────────────────────────────────────────────────

VARIANT_BUDGETS: dict[str, dict[str, int]] = {
    "mini":  {"max_examples": 1, "max_rules": 0},
    "parwa": {"max_examples": 2, "max_rules": 1},
    "high":  {"max_examples": 3, "max_rules": 2},
}

# Injection markers for parsing
FEW_SHOT_MARKER = "PREVIOUS MISTAKE"
RULE_MARKER = "LEARNED RULE"
LIGHTNING_BLOCK_START = "\n\n--- AGENT LIGHTNING (self-improving) ---\n"
LIGHTNING_BLOCK_END = "\n--- END AGENT LIGHTNING ---\n\n"


# ─── Few-Shot Injection ───────────────────────────────────────────────────────────

def inject_few_shot_examples(
    prompt: str,
    intent: str,
    node_name: str,
    variant: str = "parwa",
    *,
    path: Path | None = None,
) -> str:
    """Inject relevant past corrections into the prompt as few-shot examples.

    Each example is formatted as a "PREVIOUS MISTAKE" warning that tells the
    model what it got wrong and what the correct answer was.

    Args:
        prompt: The base prompt to inject into.
        intent: The current ticket's intent.
        node_name: The node being executed (e.g. "INTENT_CLASSIFIER").
        variant: Current variant for budget allocation (mini/parwa/high).
        path: Override store file path (for testing).

    Returns:
        The prompt with few-shot examples injected, or the original prompt
        if no relevant examples exist.
    """
    budget = VARIANT_BUDGETS.get(variant, VARIANT_BUDGETS["parwa"])
    max_examples = budget["max_examples"]

    # Get relevant corrections
    examples = get_few_shot_examples(
        intent=intent,
        limit=max_examples,
        path=path,
    )

    if not examples:
        return prompt

    # Build the few-shot injection block
    injection_lines: list[str] = []
    injection_lines.append(LIGHTNING_BLOCK_START)

    for i, example in enumerate(examples, 1):
        original = example.get("original_response", "")
        corrected = example.get("corrected_response", "")
        correction_type = example.get("correction_type", "unknown")
        ticket_id = example.get("ticket_id", "unknown")

        # Truncate long responses for token budget
        orig_short = _truncate(original, 120)
        corr_short = _truncate(corrected, 120)

        # Build the reason (from metadata or inferred from type)
        reason = _infer_reason(example)

        injection_lines.append(
            f"{FEW_SHOT_MARKER} (similar ticket #{i}, {correction_type}): "
            f'You said "{orig_short}" but correct answer was "{corr_short}" '
            f'because {reason}'
        )
        injection_lines.append("Avoid making the same error.\n")

    injection_lines.append(LIGHTNING_BLOCK_END)

    injection_block = "\n".join(injection_lines)

    logger.debug(
        "lightning: injected %d few-shot examples for intent=%s node=%s variant=%s",
        len(examples), intent, node_name, variant,
    )

    return prompt + injection_block


# ─── Pattern Rule Injection ───────────────────────────────────────────────────────

def inject_pattern_rules(
    prompt: str,
    intent: str,
    node_name: str,
    variant: str = "parwa",
    *,
    path: Path | None = None,
) -> str:
    """Inject auto-extracted pattern rules into the prompt.

    Pattern rules are extracted when >= 5 similar corrections exist. They
    represent common mistakes and the correct behavior for a given intent.

    Args:
        prompt: The base prompt to inject into.
        intent: The current ticket's intent.
        node_name: The node being executed.
        variant: Current variant for budget allocation.
        path: Override store file path (for testing).

    Returns:
        The prompt with pattern rules injected, or the original prompt
        if no rules exist.
    """
    budget = VARIANT_BUDGETS.get(variant, VARIANT_BUDGETS["parwa"])
    max_rules = budget["max_rules"]

    if max_rules == 0:
        return prompt

    # Get pattern rules for this intent (and cross-node rules with intent="*")
    rules = get_pattern_rules(intent=intent, path=path)
    cross_rules = get_pattern_rules(intent="*", path=path)
    all_rules = rules + cross_rules

    if not all_rules:
        return prompt

    # Sort by support count (most evidence first) and take top N
    all_rules.sort(key=lambda r: r.get("support_count", 0), reverse=True)
    all_rules = all_rules[:max_rules]

    # Build the rule injection block
    injection_lines: list[str] = []
    injection_lines.append(LIGHTNING_BLOCK_START)

    for rule in all_rules:
        rule_text = rule.get("rule_text", "No rule text available")
        support_count = rule.get("support_count", 0)
        rule_intent = rule.get("intent", "unknown")

        # Format as a LEARNED RULE
        if rule_intent == intent:
            injection_lines.append(
                f"{RULE_MARKER}: {rule_text} "
                f"(extracted from {support_count} corrections)"
            )
        else:
            injection_lines.append(
                f"{RULE_MARKER} (general): {rule_text} "
                f"(extracted from {support_count} corrections across intents)"
            )
        injection_lines.append("")

    injection_lines.append(LIGHTNING_BLOCK_END)

    injection_block = "\n".join(injection_lines)

    logger.debug(
        "lightning: injected %d pattern rules for intent=%s node=%s variant=%s",
        len(all_rules), intent, node_name, variant,
    )

    return prompt + injection_block


# ─── Full Lightning Prompt Builder ─────────────────────────────────────────────────

async def build_lightning_prompt(
    base_prompt: str,
    state: dict[str, Any],
    node_name: str,
    *,
    path: Path | None = None,
) -> str:
    """Build the full prompt with Agent Lightning additions.

    This is the main entry point for Lightning. It takes a base prompt,
    checks the correction store for relevant examples and rules, and
    injects them into the prompt.

    Async-compatible: works with PARWA's async pipeline. The actual
    file reads in the correction store are synchronous (JSON file),
    but this function is async for pipeline compatibility.

    Args:
        base_prompt: The base prompt for the node.
        state: The current ticket state dict.
        node_name: The node being executed (e.g. "INTENT_CLASSIFIER").
        path: Override store file path (for testing).

    Returns:
        The enhanced prompt with Lightning additions.
    """
    intent = state.get("intent", "general_inquiry")
    variant = state.get("variant", "parwa")

    # Guard types
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(variant, str) or variant not in VARIANT_BUDGETS:
        variant = "parwa"

    # Check if this node benefits from Lightning (skip for low-value nodes)
    if not _should_inject(node_name, variant):
        return base_prompt

    prompt = base_prompt

    # Step 1: Inject pattern rules (higher priority, goes first)
    prompt = inject_pattern_rules(prompt, intent, node_name, variant, path=path)

    # Step 2: Inject few-shot examples
    prompt = inject_few_shot_examples(prompt, intent, node_name, variant, path=path)

    # Track injection in state for audit/monitoring
    lightning_meta = state.get("_lightning_meta", {})
    lightning_meta[node_name] = {
        "intent": intent,
        "variant": variant,
        "injected": True,
    }
    # Note: we don't mutate state here — the caller should handle that

    return prompt


def build_lightning_prompt_sync(
    base_prompt: str,
    state: dict[str, Any],
    node_name: str,
    *,
    path: Path | None = None,
) -> str:
    """Synchronous version of build_lightning_prompt.

    Since all file I/O in the correction store is synchronous,
    this just calls the internal implementation directly.
    """
    try:
        return _build_lightning_prompt_impl(base_prompt, state, node_name, path=path)
    except Exception as exc:
        logger.warning("lightning: failed to build prompt (%s), using base", exc)
        return base_prompt


def _build_lightning_prompt_impl(
    base_prompt: str,
    state: dict[str, Any],
    node_name: str,
    *,
    path: Path | None = None,
) -> str:
    """Internal synchronous implementation of build_lightning_prompt."""
    intent = state.get("intent", "general_inquiry")
    variant = state.get("variant", "parwa")

    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(variant, str) or variant not in VARIANT_BUDGETS:
        variant = "parwa"

    if not _should_inject(node_name, variant):
        return base_prompt

    prompt = base_prompt
    prompt = inject_pattern_rules(prompt, intent, node_name, variant, path=path)
    prompt = inject_few_shot_examples(prompt, intent, node_name, variant, path=path)
    return prompt


# ─── Lightning Statistics ──────────────────────────────────────────────────────────

def get_lightning_stats(
    state: dict[str, Any],
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    """Get statistics about Lightning injections for the current ticket.

    Args:
        state: The current ticket state dict.
        path: Override store file path (for testing).

    Returns:
        Dict with injection stats.
    """
    meta = state.get("_lightning_meta", {})
    from parwa.dspy.correction_store import get_stats
    store_stats = get_stats(path=path)

    return {
        "nodes_injected": len(meta),
        "injection_details": meta,
        "correction_store_stats": store_stats,
        "variant_budgets": VARIANT_BUDGETS,
    }


# ─── Internal Helpers ─────────────────────────────────────────────────────────────

def _should_inject(node_name: str, variant: str) -> bool:
    """Decide if Lightning should inject for this node+variant combination.

    - mini variant: Only inject for critical nodes
    - parwa/high: Inject for all nodes that have signatures
    """
    node_upper = node_name.upper()

    if variant == "mini":
        return node_upper in CRITICAL_NODES

    # For parwa and high, inject for any node that has a signature
    sig = get_signature(node_upper)
    return sig is not None


def _truncate(text: str, max_len: int = 120) -> str:
    """Truncate text to max_len, adding ellipsis if needed."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def _infer_reason(example: dict[str, Any]) -> str:
    """Infer the reason for a correction from the example data.

    Uses metadata if available, otherwise infers from correction type.
    """
    metadata = example.get("metadata", {})

    # Check for explicit reason in metadata
    if "reason" in metadata:
        return str(metadata["reason"])
    if "correction_reason" in metadata:
        return str(metadata["correction_reason"])

    # Infer from correction type
    correction_type = example.get("correction_type", "unknown")
    intent = example.get("intent", "unknown")

    reason_map = {
        "rejected": "the response did not adequately address the customer's concern",
        "corrected": "the response contained inaccuracies that needed correction",
        "approved": "the response was improved for clarity and completeness",
        "escalation_feedback": "the issue required human review after escalation",
    }

    base_reason = reason_map.get(
        correction_type,
        "the response could be improved based on this correction",
    )

    # Add intent-specific context
    intent_context = {
        "refund_request": " — always verify refund eligibility first",
        "order_status": " — always fetch live order data",
        "billing_inquiry": " — always verify charges against CRM",
        "complaint": " — always acknowledge frustration first",
    }

    extra = intent_context.get(intent, "")
    return base_reason + extra
