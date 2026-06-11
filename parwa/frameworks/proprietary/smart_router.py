"""Smart Router — Technique selection optimizer inside FrameworkBrain.

How it works:
  1. Evaluates which combination of techniques will produce the best result
     for the current ticket's complexity, intent, and variant
  2. Considers token budget remaining vs technique cost
  3. Selects the optimal technique activation order
  4. May skip expensive techniques when budget is tight

What hallucination it catches:
  "Expensive misrouting" — when a simple ticket gets ToT + GST + UoT
  (800+ tokens) when CoT alone (150 tokens) would suffice. Smart Router
  prevents wasting tokens on unnecessary techniques, and ensures critical
  tickets always get the full arsenal.

Relationship to Smart Router in llm.py:
  The Smart Router in llm.py selects the right LLM MODEL per node
  (gpt-4o-mini vs gpt-4o vs o1-preview). This technique selects the
  right TECHNIQUE combination inside FrameworkBrain. They're complementary:
  one picks the brain, the other picks the model.

Activation:
  - Medium complexity and above (simple tickets use default activation)
  - Used in REASONING_ENGINE, ACTION_PLANNER for budget-aware routing
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.smart_router")


class SmartRouterTechnique(BaseTechnique):
    """Smart Router: Budget-aware technique selection optimizer.

    Evaluates which techniques to activate based on ticket context
    and token budget. Prevents over-spending on simple tickets and
    under-spending on critical ones.
    """

    _min_complexity = "medium"

    @property
    def name(self) -> str:
        return "smart_router"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.PROPRIETARY

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "REASONING_ENGINE",
            "ACTION_PLANNER",
            "ACTION_EXECUTOR",
            "QUALITY_SCORER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 100  # Low — it's about routing, not generation

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute Smart Router technique selection.

        Evaluates the ticket context and token budget, then recommends
        the optimal technique activation order.
        """
        complexity = state.get("complexity", "simple")
        intent = state.get("intent", "general_inquiry")
        budget_remaining = state.get("token_budget_remaining", 5000)

        if MOCK_MODE:
            chain, output, confidence, recommended = self._smart_router_mock(
                complexity, intent, variant, budget_remaining
            )
        else:
            chain, output, confidence, recommended = await self._smart_router_llm(
                prompt, complexity, intent, variant, budget_remaining,
                ticket_id=ticket_id,
            )

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["smart_router"],
            metadata={
                "complexity": complexity,
                "intent": intent,
                "variant": variant,
                "budget_remaining": budget_remaining,
                "recommended_techniques": recommended,
            },
            token_estimate=self.token_cost_estimate,
        )

    def _smart_router_mock(
        self,
        complexity: str,
        intent: str,
        variant: str,
        budget_remaining: int,
    ) -> tuple[list[str], str, float, list[str]]:
        """Mock Smart Router for testing (no LLM calls)."""
        chain = []

        # Step 1: Analyze context
        chain.append(f"Smart Router: Complexity={complexity}, Intent={intent}, Variant={variant}")
        chain.append(f"Smart Router: Token budget remaining={budget_remaining}")

        # Step 2: Select techniques based on complexity
        if complexity == "simple":
            recommended = ["chain_of_thought"]
            chain.append("Smart Router: Simple ticket — CoT only")
        elif complexity == "medium":
            recommended = ["chain_of_thought", "react", "clara"]
            chain.append("Smart Router: Medium ticket — CoT + ReAct + CLARA")
        elif complexity == "complex":
            recommended = ["chain_of_thought", "react", "tree_of_thoughts", "reverse_thinking", "gsd"]
            chain.append("Smart Router: Complex ticket — CoT + ReAct + ToT + Reverse + GSD")
        else:  # critical
            recommended = [
                "chain_of_thought", "react", "tree_of_thoughts",
                "reverse_thinking", "graph_of_strategic_thought",
                "uncertainty_of_thought", "gsd", "maker",
            ]
            chain.append("Smart Router: Critical ticket — Full arsenal including UoT + MAKER + GSD")

        # Step 3: Budget check — trim expensive techniques if budget is tight
        if budget_remaining < 500:
            # Keep only essential techniques
            essential = ["chain_of_thought"]
            trimmed = [t for t in recommended if t in essential]
            if len(trimmed) < len(recommended):
                chain.append(f"Smart Router: Tight budget ({budget_remaining}), trimmed {len(recommended) - len(trimmed)} techniques")
                recommended = trimmed
        elif budget_remaining < 1500 and complexity in ("complex", "critical"):
            # Keep core techniques but skip expensive ones
            expensive = {"tree_of_thoughts", "uncertainty_of_thought", "graph_of_strategic_thought"}
            trimmed = [t for t in recommended if t not in expensive]
            if len(trimmed) < len(recommended):
                chain.append(f"Smart Router: Moderate budget ({budget_remaining}), skipping expensive techniques")
                recommended = trimmed

        # Step 4: Variant adjustment
        if variant == "mini":
            # Mini variant: fewer techniques to save tokens
            if len(recommended) > 2:
                recommended = recommended[:2]
                chain.append("Smart Router: Mini variant — limiting to 2 techniques for cost optimization")

        output = f"Smart Router: Recommended {len(recommended)} techniques for {complexity}/{intent}/{variant}: {recommended}"
        confidence = 0.92

        return chain, output, confidence, recommended

    async def _smart_router_llm(
        self,
        prompt: str,
        complexity: str,
        intent: str,
        variant: str,
        budget_remaining: int,
        *,
        ticket_id: str = "",
    ) -> tuple[list[str], str, float, list[str]]:
        """Real LLM-based Smart Router technique selection."""
        system_instructions = (
            "You are a Smart Router for customer support AI techniques.\n\n"
            f"Context:\n"
            f"  Complexity: {complexity}\n"
            f"  Intent: {intent}\n"
            f"  Variant: {variant}\n"
            f"  Token budget remaining: {budget_remaining}\n\n"
            "Available techniques and their token costs:\n"
            "  - chain_of_thought (150 tokens)\n"
            "  - react (300 tokens)\n"
            "  - tree_of_thoughts (500 tokens)\n"
            "  - reverse_thinking (200 tokens)\n"
            "  - uncertainty_of_thought (100 tokens)\n"
            "  - graph_of_strategic_thought (400 tokens)\n"
            "  - gsd (150 tokens)\n"
            "  - maker (350 tokens)\n"
            "  - clara (200 tokens)\n"
            "  - hyde (250 tokens)\n"
            "  - multi_query (300 tokens)\n"
            "  - step_back (200 tokens)\n"
            "  - reflexion (200 tokens)\n"
            "  - self_consistency (300 tokens)\n"
            "  - crp (150 tokens)\n\n"
            "Select the optimal technique combination that:\n"
            "  1. Matches the ticket complexity\n"
            "  2. Stays within the token budget\n"
            "  3. Prioritizes accuracy for critical tickets\n"
            "  4. Saves tokens for mini variant\n\n"
            "Output ONLY a JSON list of technique names.\n"
            "Example: [\"chain_of_thought\", \"react\", \"clara\"]"
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)

        try:
            text = await ainvoke_llm(
                safe_prompt,
                node_name="FRAMEWORKBRAIN_SMART_ROUTER",
                ticket_id=ticket_id,
                variant=variant,
            )

            # Parse the response
            recommended = ["chain_of_thought"]  # safe default
            try:
                import json
                parsed = json.loads(text.strip())
                if isinstance(parsed, list) and len(parsed) > 0:
                    recommended = [str(t) for t in parsed]
            except (json.JSONDecodeError, ValueError):
                pass

            chain = [
                f"Smart Router: LLM-selected techniques for {complexity}/{intent}",
                f"Smart Router: Recommended: {recommended}",
            ]

            output = f"Smart Router: LLM-optimized {len(recommended)} techniques for {complexity}/{intent}/{variant}"
            confidence = 0.88

            return chain, output, confidence, recommended

        except Exception as exc:
            logger.warning("Smart Router LLM failed: %s — using default routing", exc)
            # Fallback: complexity-based default
            if complexity == "simple":
                recommended = ["chain_of_thought"]
            elif complexity == "medium":
                recommended = ["chain_of_thought", "react"]
            else:
                recommended = ["chain_of_thought", "react", "tree_of_thoughts"]

            return (
                ["Smart Router: LLM routing failed, using complexity-based defaults"],
                "Smart Router: Using default routing due to LLM error",
                0.50,
                recommended,
            )
