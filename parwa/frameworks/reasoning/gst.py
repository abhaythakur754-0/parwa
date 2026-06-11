"""Graph of Strategic Thought (GST) — Models reasoning as interconnected decisions.

How it works:
  1. Instead of a linear chain (CoT) or parallel paths (ToT),
     GST models reasoning as a GRAPH of interconnected decisions
  2. Each decision node can branch and reconnect
  3. Dependencies between decisions are explicit
  4. Good for complex, multi-factor tickets where different
     aspects of the problem affect each other

What hallucination it catches:
  "Linear thinking bias" — some problems have interdependencies
  that linear reasoning misses. GST forces the system to model
  those connections explicitly.

Activation:
  - Complex and Critical tickets
  - Used in STRATEGY_PLANNER node
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.gst")


class GraphOfStrategicThoughtTechnique(BaseTechnique):
    """Graph of Strategic Thought reasoning technique.

    Models reasoning as a graph of interconnected strategic decisions
    rather than a linear chain or parallel paths. Each decision node
    can branch and reconnect, capturing interdependencies.
    """

    _min_complexity = "complex"  # Only activates on complex+

    @property
    def name(self) -> str:
        return "graph_of_strategic_thought"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.REASONING

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "STRATEGY_PLANNER",
            "REASONING_ENGINE",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 400  # Higher — models a graph of decisions

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute Graph of Strategic Thought reasoning."""
        intent = state.get("intent", "general_inquiry")
        conclusion = state.get("reasoning_conclusion", "")
        selected_path = state.get("selected_path")

        if MOCK_MODE:
            plan, chain, confidence = self._gst_mock(intent, conclusion, selected_path)
        else:
            plan, chain, confidence = await self._gst_llm(
                prompt, intent, conclusion, selected_path,
                ticket_id=ticket_id, variant=variant
            )

        return TechniqueResult(
            output="; ".join(plan) if plan else "",
            chain=chain,
            confidence=confidence,
            frameworks_used=["graph_of_strategic_thought"],
            metadata={
                "plan_steps": plan,  # The actual plan list, not a count
                "plan_count": len(plan),
                "intent": intent,
                "had_selected_path": bool(selected_path),
            },
            token_estimate=self.token_cost_estimate,
        )

    def _gst_mock(
        self,
        intent: str,
        conclusion: str,
        selected_path: dict | None,
    ) -> tuple[list[str], list[str], float]:
        """Mock GST for testing."""
        chain = ["GST: Building strategic decision graph"]

        # If ToT selected a path, use its steps as a starting point
        if selected_path and isinstance(selected_path, dict) and selected_path.get("steps"):
            base_steps = selected_path["steps"]
            chain.append(f"GST: Using selected path as base — {selected_path.get('description', '')}")
        else:
            base_steps = None
            chain.append("GST: No prior path selected — generating from intent")

        # Build decision graph based on intent
        if intent == "refund_request":
            plan = [
                "[Decision: Verify charge] → Check CRM for duplicate",
                "[Decision: Check policy] → Verify 30-day window",
                "[Decision: Calculate amount] → Depends on: Verify charge",
                "[Decision: Determine authority] → Depends on: variant permissions",
                "[Decision: Execute or Recommend] → Depends on: Determine authority",
            ]
            confidence = 0.90
        elif intent == "cancellation":
            plan = [
                "[Decision: Check order status] → Has it shipped?",
                "[Decision: Verify window] → Within cancellation policy?",
                "[Decision: Process cancel] → Depends on: Check order status + Verify window",
                "[Decision: Confirm with customer] → Depends on: Process cancel",
            ]
            confidence = 0.88
        else:
            plan = [
                "[Decision: Gather evidence] → What data is available?",
                "[Decision: Determine action] → Depends on: Gather evidence",
                "[Decision: Execute or escalate] → Depends on: Determine action",
                "[Decision: Confirm resolution] → Depends on: Execute or escalate",
            ]
            confidence = 0.75

        chain.append(f"GST: Graph has {len(plan)} decision nodes")
        chain.append(f"GST: Strategy confidence — {confidence}")

        return plan, chain, confidence

    async def _gst_llm(
        self,
        prompt: str,
        intent: str,
        conclusion: str,
        selected_path: dict | None,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> tuple[list[str], list[str], float]:
        """Real LLM-based GST reasoning."""
        path_context = ""
        if selected_path and isinstance(selected_path, dict):
            path_context = f"\nPrior selected path: {selected_path.get('description', '')}\nPath steps: {selected_path.get('steps', [])}"

        system_instructions = (
            "You are a Graph of Strategic Thought planning engine.\n"
            "Model the solution as a graph of interconnected decisions.\n\n"
            f"Intent: {intent}\n"
            f"Current conclusion: {conclusion or 'None yet'}\n"
            f"{path_context}\n"
            "Rules:\n"
            "- Each decision should explicitly state its dependencies\n"
            "- Format: [Decision: <name>] → <action> (depends on: <other decisions>)\n"
            "- Capture interdependencies between decisions\n"
            "- Order decisions so dependencies come before dependents"
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)

        try:
            text = await ainvoke_llm(
                safe_prompt,
                node_name="FRAMEWORKBRAIN_GST",
                ticket_id=ticket_id,
                variant=variant,
            )
            plan = [line.strip() for line in text.strip().split("\n") if line.strip() and line.strip().startswith("[")]
            chain = [f"GST: Generated {len(plan)} decision nodes via LLM"]

            if not plan:
                plan = ["[Decision: Review and resolve] → Standard resolution"]
                chain.append("GST: No structured decisions found, using fallback")

            confidence = 0.80
            chain.append(f"GST: Strategy confidence — {confidence}")

            return plan, chain, confidence

        except Exception as exc:
            logger.warning("GST LLM reasoning failed: %s — using fallback", exc)
            plan = ["[Decision: Review evidence] → Standard resolution", "[Decision: Act] → Execute or recommend"]
            chain = ["GST: LLM failed, using 2-step fallback plan"]
            return plan, chain, 0.30
