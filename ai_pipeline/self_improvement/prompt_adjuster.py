"""Prompt Adjuster — Automatically adjusts subgraph prompts based on failure patterns.

When the PatternLearner identifies that a subgraph has a low resolution rate,
the PromptAdjuster modifies the system prompt to address the specific failure mode.

For example:
  - If refund tickets with "subscription" keyword keep failing → add subscription
    refund rules to the refund system prompt
  - If tech tickets with "integration" keep getting escalated → add more
    integration troubleshooting steps to the tech system prompt

This is NOT fine-tuning. We change the instructions, not the model weights.
Research shows that prompt engineering outperforms fine-tuning for CoT reasoning.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from parwa.self_improvement.pattern_learner import FailurePattern

logger = logging.getLogger("parwa.self_improvement.prompt_adjuster")


@dataclass
class PromptAdjustment:
    """A prompt adjustment derived from a failure pattern.

    Attributes:
        adjustment_id: Unique identifier.
        subgraph: Which subgraph's prompt to adjust.
        pattern_id: The failure pattern that triggered this adjustment.
        adjustment_type: Type of adjustment (add_rule, add_example, modify_instruction).
        content: The actual content to add/modify.
        confidence: How confident we are this adjustment will help (0-1).
        status: Current status (pending, applied, verified, rejected).
    """
    adjustment_id: str = ""
    subgraph: str = ""
    pattern_id: str = ""
    adjustment_type: str = "add_rule"  # add_rule, add_example, modify_instruction
    content: str = ""
    confidence: float = 0.5
    status: str = "pending"  # pending, applied, verified, rejected


# ─── Prompt Adjustment Rules ──────────────────────────────────────────────────

_KEYWORD_ADJUSTMENTS: dict[str, dict[str, str]] = {
    "subscription": {
        "subgraph": "refund",
        "adjustment_type": "add_rule",
        "content": "IMPORTANT: For subscription refunds, always calculate the prorated amount from the cancellation date. Check if the subscription is annual or monthly. Annual subscriptions may have different proration rules.",
    },
    "integration": {
        "subgraph": "tech",
        "adjustment_type": "add_rule",
        "content": "IMPORTANT: For integration issues, always check these in order: 1) API key validity, 2) Webhook URL reachability, 3) Rate limit status, 4) Payload format validation, 5) SSL certificate validity. Do NOT skip steps.",
    },
    "invoice": {
        "subgraph": "billing",
        "adjustment_type": "add_rule",
        "content": "IMPORTANT: When discussing invoices, always reference specific line items. Show the charge date, description, and amount for each item in question. Never discuss charges vaguely.",
    },
    "cancel": {
        "subgraph": "refund",
        "adjustment_type": "add_example",
        "content": "Example cancellation handling: 'I understand you'd like to cancel. Your subscription will remain active until [end of billing period], and any unused portion will be refunded within 5-7 business days.'",
    },
    "api": {
        "subgraph": "tech",
        "adjustment_type": "add_example",
        "content": "Example API troubleshooting: 'Let's check your API setup step by step. First, can you confirm your API key starts with \"pk_live_\"? If it starts with \"pk_test_\", you may be hitting the test endpoint instead of production.'",
    },
}

_SUBGRAPH_LOW_RES_ADJUSTMENTS: dict[str, str] = {
    "refund": (
        "\n\nADDITIONAL GUIDANCE (auto-adjusted based on failure patterns):\n"
        "- Always explicitly state the refund policy tier that applies\n"
        "- If the purchase date is unclear, ask the customer before proceeding\n"
        "- For partial refunds, explain the reasoning clearly\n"
        "- Never assume the customer knows our refund policy"
    ),
    "tech": (
        "\n\nADDITIONAL GUIDANCE (auto-adjusted based on failure patterns):\n"
        "- Start with the simplest fix, even if it seems obvious\n"
        "- Ask the customer to confirm their product version before troubleshooting\n"
        "- If the first fix doesn't work, try one more before escalating\n"
        "- Always include a 'when to escalate' statement in your response"
    ),
    "billing": (
        "\n\nADDITIONAL GUIDANCE (auto-adjusted based on failure patterns):\n"
        "- Always show specific line items from the invoice\n"
        "- If the customer mentions an amount, verify it against the plan\n"
        "- Explain proration clearly if a plan change occurred\n"
        "- For disputed charges, offer to escalate before denying"
    ),
    "general": (
        "\n\nADDITIONAL GUIDANCE (auto-adjusted based on failure patterns):\n"
        "- If you're not sure of the answer, say so honestly\n"
        "- For complaints, acknowledge the emotion before addressing the issue\n"
        "- Always end with an offer for further help"
    ),
}


class PromptAdjuster:
    """Generates prompt adjustments from failure patterns.

    Usage:
        adjuster = PromptAdjuster()
        adjustments = adjuster.generate_adjustments(patterns)
        for adj in adjustments:
            if adj.confidence > 0.6:
                adjuster.apply(adj)
    """

    def __init__(self, storage_path: str | None = None) -> None:
        self._adjustments: list[PromptAdjustment] = []
        self._storage_path = storage_path
        self._applied_adjustments: dict[str, str] = {}  # subgraph → accumulated prompt additions

        if storage_path and os.path.exists(storage_path):
            self._load()

    def generate_adjustments(self, patterns: list[FailurePattern]) -> list[PromptAdjustment]:
        """Generate prompt adjustments from identified failure patterns.

        Args:
            patterns: Failure patterns from the PatternLearner.

        Returns:
            List of proposed prompt adjustments.
        """
        adjustments: list[PromptAdjustment] = []

        for pattern in patterns:
            # Keyword-based adjustments
            if pattern.pattern_id.startswith("keyword_"):
                keyword = pattern.pattern_id.replace("keyword_", "")
                if keyword in _KEYWORD_ADJUSTMENTS:
                    rule = _KEYWORD_ADJUSTMENTS[keyword]
                    adjustments.append(PromptAdjustment(
                        adjustment_id=f"prompt_{pattern.pattern_id}",
                        subgraph=rule["subgraph"],
                        pattern_id=pattern.pattern_id,
                        adjustment_type=rule["adjustment_type"],
                        content=rule["content"],
                        confidence=min(0.4 + (pattern.frequency * 0.1), 0.9),
                        status="pending",
                    ))

            # Subgraph-specific low resolution rate adjustments
            elif pattern.pattern_id.startswith("subgraph_low_res_"):
                subgraph = pattern.pattern_id.replace("subgraph_low_res_", "")
                if subgraph in _SUBGRAPH_LOW_RES_ADJUSTMENTS:
                    adjustments.append(PromptAdjustment(
                        adjustment_id=f"prompt_{pattern.pattern_id}",
                        subgraph=subgraph,
                        pattern_id=pattern.pattern_id,
                        adjustment_type="modify_instruction",
                        content=_SUBGRAPH_LOW_RES_ADJUSTMENTS[subgraph],
                        confidence=min(0.5 + (pattern.impact * 0.02), 0.9),
                        status="pending",
                    ))

            # Technique gap adjustments
            elif pattern.pattern_id.startswith("technique_gap_"):
                adjustments.append(PromptAdjustment(
                    adjustment_id=f"prompt_{pattern.pattern_id}",
                    subgraph="multiple",
                    pattern_id=pattern.pattern_id,
                    adjustment_type="add_rule",
                    content=f"When the initial approach doesn't resolve the issue, try an alternative reasoning strategy. {pattern.suggested_fix}",
                    confidence=0.5,
                    status="pending",
                ))

            # Low KB retrieval adjustments
            elif pattern.pattern_id == "low_kb_retrieval":
                for subgraph in ("refund", "tech", "billing", "general"):
                    adjustments.append(PromptAdjustment(
                        adjustment_id=f"prompt_low_kb_{subgraph}",
                        subgraph=subgraph,
                        pattern_id=pattern.pattern_id,
                        adjustment_type="add_rule",
                        content="If the knowledge base doesn't have a direct answer, try rephrasing the customer's question and searching again. Use broader terms if specific ones don't return results.",
                        confidence=0.6,
                        status="pending",
                    ))

            # Complexity mismatch adjustments
            elif pattern.pattern_id == "complexity_mismatch":
                adjustments.append(PromptAdjustment(
                    adjustment_id="prompt_complexity_mismatch",
                    subgraph="multiple",
                    pattern_id=pattern.pattern_id,
                    adjustment_type="add_rule",
                    content="Before classifying a ticket as simple, verify that there are no underlying complexities. If the customer mentions multiple issues or shows frustration, consider upgrading the complexity level.",
                    confidence=0.7,
                    status="pending",
                ))

        self._adjustments.extend(adjustments)

        logger.info(
            "prompt_adjuster: generated %d adjustments from %d patterns",
            len(adjustments), len(patterns),
        )

        return adjustments

    def apply(self, adjustment: PromptAdjustment) -> None:
        """Apply a prompt adjustment to the subgraph's system prompt.

        In production, this would update the prompt template. For now,
        it stores the adjustment for the next pipeline run.
        """
        if adjustment.subgraph not in self._applied_adjustments:
            self._applied_adjustments[adjustment.subgraph] = ""

        self._applied_adjustments[adjustment.subgraph] += f"\n{adjustment.content}"
        adjustment.status = "applied"

        logger.info(
            "prompt_adjuster: applied %s to subgraph=%s",
            adjustment.adjustment_id, adjustment.subgraph,
        )

        if self._storage_path:
            self._save()

    def get_adjusted_prompt(self, subgraph: str, base_prompt: str) -> str:
        """Get the adjusted system prompt for a subgraph.

        Args:
            subgraph: The subgraph name.
            base_prompt: The original system prompt.

        Returns:
            The base prompt with any applied adjustments appended.
        """
        additions = self._applied_adjustments.get(subgraph, "")
        if additions:
            return base_prompt + additions
        return base_prompt

    def get_pending(self) -> list[PromptAdjustment]:
        """Get all pending (not yet applied) adjustments."""
        return [a for a in self._adjustments if a.status == "pending"]

    def get_applied(self) -> list[PromptAdjustment]:
        """Get all applied adjustments."""
        return [a for a in self._adjustments if a.status == "applied"]

    def summary(self) -> dict[str, Any]:
        """Get a summary of prompt adjustments."""
        return {
            "total_adjustments": len(self._adjustments),
            "pending": len(self.get_pending()),
            "applied": len(self.get_applied()),
            "subgraphs_adjusted": list(self._applied_adjustments.keys()),
        }

    def _save(self) -> None:
        """Persist adjustments to JSON."""
        if not self._storage_path:
            return
        try:
            data = {
                "adjustments": [
                    {"id": a.adjustment_id, "subgraph": a.subgraph, "status": a.status, "content": a.content}
                    for a in self._adjustments
                ],
                "applied_adjustments": self._applied_adjustments,
            }
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            with open(self._storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            logger.warning("prompt_adjuster: failed to save: %s", exc)

    def _load(self) -> None:
        """Load adjustments from JSON."""
        if not self._storage_path or not os.path.exists(self._storage_path):
            return
        try:
            with open(self._storage_path) as f:
                data = json.load(f)
            self._applied_adjustments = data.get("applied_adjustments", {})
            logger.info("prompt_adjuster: loaded adjustments for subgraphs: %s", list(self._applied_adjustments.keys()))
        except Exception as exc:
            logger.warning("prompt_adjuster: failed to load: %s", exc)
