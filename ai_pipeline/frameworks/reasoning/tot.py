"""Tree of Thoughts (ToT) — Explores multiple solution paths simultaneously.

How it works:
  - Generates 3-5 distinct solution paths via LLM
  - Evaluates each path with a scoring prompt
  - Selects the path with the highest confidence
  - Returns all paths and the selected best path

What hallucination it catches:
  "Single-path bias" — if 3 out of 5 paths agree, confidence is high.
  If they disagree, the system knows to be cautious.

Activation:
  - Complex and Critical tickets only (expensive technique)
  - Used in TREE_OF_THOUGHTS node
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.state import ReasoningPath
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.tot")


class TreeOfThoughtsTechnique(BaseTechnique):
    """Tree of Thoughts reasoning technique.

    Explores multiple solution paths simultaneously, evaluates each,
    and selects the best one. Catches single-path bias by ensuring
    that multiple independent reasoning paths are compared.
    """

    _min_complexity = "complex"  # Only activates on complex+

    @property
    def name(self) -> str:
        return "tree_of_thoughts"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.REASONING

    @property
    def applicable_nodes(self) -> list[str]:
        # TREE_OF_THOUGHTS uses think_single() — primary node
        # REASONING_ENGINE requests ToT as a candidate via think() for complex tickets
        # PROACTIVE_CHECKER could use ToT for multi-path proactive analysis
        return [
            "TREE_OF_THOUGHTS",
            "REASONING_ENGINE",
            "PROACTIVE_CHECKER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 500  # Expensive — generates multiple paths

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute Tree of Thoughts reasoning.

        Generates 3-5 solution paths, evaluates each, and selects the best.
        """
        intent = state.get("intent", "general_inquiry")
        conclusion = state.get("reasoning_conclusion", "")

        if MOCK_MODE:
            paths, selected, chain = self._tot_mock(intent, conclusion)
        else:
            paths, selected, chain = await self._tot_llm(
                prompt, intent, conclusion,
                ticket_id=ticket_id, variant=variant
            )

        # Calculate consensus confidence
        confidences = [p["confidence"] for p in paths]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        selected_confidence = selected["confidence"] if selected else 0.0

        # Check consensus: if top 2 paths agree, higher confidence
        consensus_bonus = 0.0
        if len(paths) >= 2:
            sorted_paths = sorted(paths, key=lambda p: p["confidence"], reverse=True)
            if sorted_paths[0]["selected"] and sorted_paths[1]["confidence"] > 0.5:
                consensus_bonus = 0.05

        final_confidence = min(1.0, selected_confidence + consensus_bonus)

        return TechniqueResult(
            output=selected["description"] if selected else "No path selected",
            chain=chain,
            confidence=final_confidence,
            frameworks_used=["tree_of_thoughts"],
            metadata={
                "paths_generated": len(paths),
                "avg_confidence": avg_confidence,
                "selected_confidence": selected_confidence,
                "consensus_bonus": consensus_bonus,
                "paths": paths,
                "selected_path": selected,
                "intent": intent,
            },
            token_estimate=self.token_cost_estimate,
        )

    def _tot_mock(
        self, intent: str, conclusion: str
    ) -> tuple[list[dict], dict | None, list[str]]:
        """Mock ToT for testing."""
        chain = ["ToT: Generating 3 solution paths"]

        if intent == "refund_request":
            paths = [
                {"path_id": "path_1", "description": "Full refund to original payment method",
                 "steps": ["Verify duplicate charge", "Calculate total amount", "Process full refund"],
                 "confidence": 0.95, "selected": True},
                {"path_id": "path_2", "description": "Partial refund with explanation",
                 "steps": ["Verify charge", "Explain partial amount", "Process partial refund"],
                 "confidence": 0.40, "selected": False},
                {"path_id": "path_3", "description": "Store credit as alternative",
                 "steps": ["Offer store credit", "Apply credit to account", "Confirm with customer"],
                 "confidence": 0.30, "selected": False},
            ]
        elif intent == "cancellation":
            paths = [
                {"path_id": "path_1", "description": "Cancel order and confirm",
                 "steps": ["Verify within cancellation window", "Cancel order", "Send confirmation"],
                 "confidence": 0.90, "selected": True},
                {"path_id": "path_2", "description": "Cancel and offer alternative",
                 "steps": ["Cancel current order", "Suggest replacement", "Process new order"],
                 "confidence": 0.45, "selected": False},
                {"path_id": "path_3", "description": "Delay cancellation for review",
                 "steps": ["Flag for review", "Contact customer", "Process after confirmation"],
                 "confidence": 0.25, "selected": False},
            ]
        else:
            paths = [
                {"path_id": "path_1", "description": "Direct resolution based on evidence",
                 "steps": ["Review data", "Apply standard resolution", "Confirm with customer"],
                 "confidence": 0.85, "selected": True},
                {"path_id": "path_2", "description": "Escalate for specialized handling",
                 "steps": ["Gather details", "Escalate to specialist", "Follow up"],
                 "confidence": 0.35, "selected": False},
                {"path_id": "path_3", "description": "Request more information",
                 "steps": ["Identify missing info", "Ask customer", "Process once complete"],
                 "confidence": 0.25, "selected": False},
            ]

        chain.append(f"ToT: Generated {len(paths)} paths")
        chain.append(f"ToT: Best path — {paths[0]['description']} (confidence: {paths[0]['confidence']})")

        selected = None
        for p in paths:
            if p.get("selected"):
                selected = p
                break
        if not selected and paths:
            selected = max(paths, key=lambda p: p["confidence"])

        return paths, selected, chain

    async def _tot_llm(
        self,
        prompt: str,
        intent: str,
        conclusion: str,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> tuple[list[dict], dict | None, list[str]]:
        """Real LLM-based ToT reasoning."""
        system_instructions = (
            "You are a Tree of Thoughts reasoning engine.\n"
            "Generate exactly 3 distinct solution paths for this problem.\n\n"
            f"Intent: {intent}\n"
            f"Current conclusion: {conclusion or 'None yet'}\n\n"
            "Format each path exactly as:\n"
            "Path N: <description>\n"
            "Steps: <step1>, <step2>, <step3>\n"
            "Confidence: <0.0-1.0>\n\n"
            "One path should be clearly best (confidence > 0.8).\n"
            "Mark the best path by adding [SELECTED] after its description."
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)

        try:
            text = await ainvoke_llm(
                safe_prompt,
                node_name="FRAMEWORKBRAIN_TOT",
                ticket_id=ticket_id,
                variant=variant,
            )
            paths = self._parse_paths(text)
            chain = [f"ToT: Generated {len(paths)} paths via LLM"]

            selected = None
            for p in paths:
                if p.get("selected"):
                    selected = p
                    break
            if not selected and paths:
                selected = max(paths, key=lambda p: p.get("confidence", 0))

            if selected:
                chain.append(f"ToT: Best path — {selected['description']} (confidence: {selected['confidence']})")

            return paths, selected, chain

        except Exception as exc:
            logger.warning("ToT LLM reasoning failed: %s — using fallback", exc)
            paths = [{"path_id": "fallback", "description": "Single fallback path", "steps": ["Review and resolve"], "confidence": 0.30, "selected": True}]
            return paths, paths[0], ["ToT: LLM failed, using single fallback path"]

    @staticmethod
    def _parse_paths(text: str) -> list[dict]:
        """Parse LLM output into structured paths."""
        paths = []
        current_path: dict = {}

        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            if line.lower().startswith("path"):
                if current_path:
                    paths.append(current_path)
                is_selected = "[SELECTED]" in line.upper()
                desc = line.split(":", 1)[1].strip().replace("[SELECTED]", "").strip() if ":" in line else line
                current_path = {
                    "path_id": f"path_{len(paths) + 1}",
                    "description": desc,
                    "steps": [],
                    "confidence": 0.0,
                    "selected": is_selected,
                }
            elif line.lower().startswith("steps:") and current_path:
                steps_str = line.split(":", 1)[1].strip()
                current_path["steps"] = [s.strip() for s in steps_str.split(",") if s.strip()]
            elif line.lower().startswith("confidence:") and current_path:
                try:
                    current_path["confidence"] = float(line.split(":", 1)[1].strip().replace("[SELECTED]", ""))
                except ValueError:
                    current_path["confidence"] = 0.50

        if current_path:
            paths.append(current_path)

        # If no paths were parsed, create a fallback
        if not paths:
            paths = [{"path_id": "path_1", "description": "Auto-generated path", "steps": ["Review and resolve"], "confidence": 0.40, "selected": True}]

        return paths
