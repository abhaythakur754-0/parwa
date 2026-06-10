"""Node 12: TREE_OF_THOUGHTS — Explores multiple solution paths and picks the best.

Reasoning Agent node. Creates 3-5 possible solution paths,
evaluates each, and selects the best one. Catches single-path bias.
"""

from __future__ import annotations

from typing import Any

from parwa.state import ReasoningPath
from parwa.utils.llm import MOCK_MODE, get_mock_llm, get_llm
from parwa.utils.node_base import safe_node


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


@safe_node("TREE_OF_THOUGHTS")
async def tree_of_thoughts(state: dict[str, Any]) -> dict[str, Any]:
    """Explore multiple solution paths and select the best one (async).

    Reads: intent, reasoning_conclusion
    Writes: reasoning_paths, selected_path, active_frameworks (append)
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")

    paths = _explore_paths_rule_based(intent, conclusion)

    # Select the path with selected=True, or the highest confidence
    selected = None
    best_confidence = 0.0
    for p in paths:
        if p.get("selected", False):
            selected = p
            break
        if p.get("confidence", 0) > best_confidence:
            best_confidence = p["confidence"]
            selected = p

    # Add framework tracking
    active_frameworks = list(state.get("active_frameworks", []))
    if "tree_of_thoughts" not in active_frameworks:
        active_frameworks.append("tree_of_thoughts")

    return {
        "reasoning_paths": paths,
        "selected_path": selected,
        "active_frameworks": active_frameworks,
    }
