"""Node 12: TREE_OF_THOUGHTS — Explores multiple solution paths and picks the best.

Reasoning Agent node. Creates 3-5 possible solution paths,
evaluates each, and selects the best one. Catches single-path bias.

Phase 2: Now uses FrameworkBrain with ToT technique for real
multi-path LLM exploration instead of hardcoded rule-based paths.
"""

from __future__ import annotations

from typing import Any

from parwa.state import ReasoningPath
from parwa.utils.llm import MOCK_MODE, get_mock_llm, get_llm
from parwa.utils.node_base import safe_node

import logging

logger = logging.getLogger("parwa.node.tree_of_thoughts")


def _explore_paths_rule_based(intent: str, conclusion: str) -> list[dict]:
    """Generate multiple solution paths based on intent. Returns list of ReasoningPath dicts."""
    if intent == "refund_request":
        paths = [
            ReasoningPath(path_id="path_1", description="Full refund to original payment method",
                          steps=["Verify duplicate charge", "Calculate total amount", "Process full refund"],
                          confidence=0.95, selected=True),
            ReasoningPath(path_id="path_2", description="Partial refund with explanation",
                          steps=["Verify charge", "Explain partial amount", "Process partial refund"],
                          confidence=0.40, selected=False),
            ReasoningPath(path_id="path_3", description="Store credit as alternative",
                          steps=["Offer store credit", "Apply credit to account", "Confirm with customer"],
                          confidence=0.30, selected=False),
        ]
    elif intent == "cancellation":
        paths = [
            ReasoningPath(path_id="path_1", description="Cancel order and confirm",
                          steps=["Verify order within cancellation window", "Cancel order", "Send confirmation"],
                          confidence=0.90, selected=True),
            ReasoningPath(path_id="path_2", description="Cancel and offer alternative",
                          steps=["Cancel current order", "Suggest replacement", "Process new order"],
                          confidence=0.45, selected=False),
            ReasoningPath(path_id="path_3", description="Delay cancellation for review",
                          steps=["Flag for review", "Contact customer for details", "Process after confirmation"],
                          confidence=0.25, selected=False),
        ]
    else:
        paths = [
            ReasoningPath(path_id="path_1", description="Direct resolution based on evidence",
                          steps=["Review available data", "Apply standard resolution", "Confirm with customer"],
                          confidence=0.85, selected=True),
            ReasoningPath(path_id="path_2", description="Escalate for specialized handling",
                          steps=["Gather details", "Escalate to specialist", "Follow up with customer"],
                          confidence=0.35, selected=False),
            ReasoningPath(path_id="path_3", description="Request more information",
                          steps=["Identify missing info", "Ask customer for details", "Process once complete"],
                          confidence=0.25, selected=False),
        ]

    return [p.model_dump() for p in paths]


async def _tot_with_brain(state: dict[str, Any]) -> tuple[list[dict], dict | None, list[str]]:
    """Tree of Thoughts using FrameworkBrain (Phase 2).

    Returns (paths, selected_path, frameworks_used).
    Falls back to rule-based on any failure.
    """
    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="TREE_OF_THOUGHTS", state=state)
        result = await brain.think_single(
            "tree_of_thoughts",
            prompt=state.get("reasoning_conclusion", ""),
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # Extract paths from metadata
        paths = result.metadata.get("paths", [])
        selected = result.metadata.get("selected_path")

        # If FrameworkBrain didn't produce paths, fall back
        if not paths:
            logger.debug("tree_of_thoughts: FrameworkBrain produced no paths, falling back to rule-based")
            intent = state.get("intent", "general_inquiry")
            conclusion = state.get("reasoning_conclusion", "")
            paths = _explore_paths_rule_based(intent, conclusion)
            selected = None
            for p in paths:
                if p.get("selected"):
                    selected = p
                    break
            if not selected and paths:
                selected = max(paths, key=lambda p: p.get("confidence", 0))

            return paths, selected, ["tree_of_thoughts"]

        return paths, selected, result.frameworks_used

    except Exception as exc:
        logger.warning(
            "tree_of_thoughts: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        intent = state.get("intent", "general_inquiry")
        conclusion = state.get("reasoning_conclusion", "")
        paths = _explore_paths_rule_based(intent, conclusion)
        selected = None
        for p in paths:
            if p.get("selected"):
                selected = p
                break
        if not selected and paths:
            selected = max(paths, key=lambda p: p.get("confidence", 0))

        return paths, selected, ["tree_of_thoughts"]


@safe_node("TREE_OF_THOUGHTS", fallback={"reasoning_paths": [], "selected_path": None, "active_frameworks": []})
async def tree_of_thoughts(state: dict[str, Any]) -> dict[str, Any]:
    """Explore multiple solution paths and select the best one (async).

    Phase 2: Uses FrameworkBrain with ToT technique for real multi-path
    exploration. Falls back to rule-based on failure.

    Reads: intent, reasoning_conclusion
    Writes: reasoning_paths, selected_path, active_frameworks (append)
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")

    # Guard: ensure types
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(conclusion, str):
        conclusion = str(conclusion) if conclusion else ""

    # Try FrameworkBrain first (Phase 2)
    paths, selected, frameworks = await _tot_with_brain(state)

    # Select the path with selected=True, or the highest confidence
    if not selected:
        best_confidence = 0.0
        for p in paths:
            if p.get("selected", False):
                selected = p
                break
            if p.get("confidence", 0) > best_confidence:
                best_confidence = p["confidence"]
                selected = p

    # Add framework tracking — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    # Ensure at least tree_of_thoughts is tracked
    if not new_frameworks and "tree_of_thoughts" not in existing:
        new_frameworks.append("tree_of_thoughts")

    return {
        "reasoning_paths": paths,
        "selected_path": selected,
        "active_frameworks": new_frameworks,
    }
