"""PARWA DSPy Module — Self-improving prompt optimization and Agent Lightning.

Phase 6: Makes the system self-improving by:
  1. Capturing corrections from rejected/approved tickets (Correction Store)
  2. Optimizing prompts based on correction data (DSPy Optimizer)
  3. Injecting few-shot examples from past mistakes into prompts (Agent Lightning)
  4. Persisting correction data across restarts (JSON file-based store)

Architecture:
  - Correction Store: File-based (JSON), thread-safe, atomic writes
  - DSPy Signatures: Input/output contracts for all 28 pipeline nodes
  - Agent Lightning: Prompt-level few-shot injection (not model weights)
  - Optimizer: Simplified variant tracking with auto-promotion

Usage:
    # Add a correction when a ticket is rejected
    from parwa.dspy import add_correction
    add_correction(
        ticket_id="T-123",
        intent="refund_request",
        original_response="Your refund has been processed.",
        corrected_response="I've checked your order and unfortunately the refund window has closed.",
        correction_type="rejected",
        metadata={"reason": "Refund window had expired"},
        node_name="REASONING_ENGINE",
    )

    # Build a Lightning-enhanced prompt (async)
    from parwa.dspy import build_lightning_prompt
    prompt = await build_lightning_prompt(base_prompt, state, "INTENT_CLASSIFIER")

    # Run an optimization cycle
    from parwa.dspy import run_optimization_cycle
    summary = await run_optimization_cycle()
"""

from __future__ import annotations

# ─── Correction Store ─────────────────────────────────────────────────────────────

from parwa.dspy.correction_store import (
    add_correction,
    clear_store,
    get_corrections,
    get_few_shot_examples,
    get_pattern_rules,
    get_stats,
    extract_pattern_rules,
    CORRECTION_TYPES,
    STORE_PATH,
)

# ─── Signatures ───────────────────────────────────────────────────────────────────

from parwa.dspy.signatures import (
    SIGNATURES,
    PIPELINE_ORDER,
    CRITICAL_NODES,
    AGENT_GROUPS,
    NodeSignature,
    get_signature,
    get_signatures_for_agent,
    get_critical_signatures,
    list_all_metrics,
)

# ─── Agent Lightning V1 ───────────────────────────────────────────────────────────

from parwa.dspy.lightning import (
    build_lightning_prompt,
    build_lightning_prompt_sync,
    inject_few_shot_examples,
    inject_pattern_rules,
    get_lightning_stats,
    VARIANT_BUDGETS,
    FEW_SHOT_MARKER,
    RULE_MARKER,
)

# ─── DSPy Optimizer ───────────────────────────────────────────────────────────────

from parwa.dspy.optimizer import (
    PromptVariant,
    register_prompt_variant,
    get_optimized_prompt,
    get_all_variants,
    evaluate_prompt_variant,
    optimize_prompt,
    run_optimization_cycle,
    generate_variant_from_rules,
    get_optimization_status,
)

__all__ = [
    # Correction Store
    "add_correction",
    "clear_store",
    "get_corrections",
    "get_few_shot_examples",
    "get_pattern_rules",
    "get_stats",
    "extract_pattern_rules",
    "CORRECTION_TYPES",
    "STORE_PATH",
    # Signatures
    "SIGNATURES",
    "PIPELINE_ORDER",
    "CRITICAL_NODES",
    "AGENT_GROUPS",
    "NodeSignature",
    "get_signature",
    "get_signatures_for_agent",
    "get_critical_signatures",
    "list_all_metrics",
    # Lightning
    "build_lightning_prompt",
    "build_lightning_prompt_sync",
    "inject_few_shot_examples",
    "inject_pattern_rules",
    "get_lightning_stats",
    "VARIANT_BUDGETS",
    "FEW_SHOT_MARKER",
    "RULE_MARKER",
    # Optimizer
    "PromptVariant",
    "register_prompt_variant",
    "get_optimized_prompt",
    "get_all_variants",
    "evaluate_prompt_variant",
    "optimize_prompt",
    "run_optimization_cycle",
    "generate_variant_from_rules",
    "get_optimization_status",
]
