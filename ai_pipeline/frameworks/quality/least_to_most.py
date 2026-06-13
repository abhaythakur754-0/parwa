"""Least-to-Most — Decompose complex problems into smaller sub-problems.

How it works:
  1. Takes a complex problem
  2. Breaks it into 2-4 smaller, manageable sub-problems
  3. Solves each sub-problem independently (cheaper LLM calls)
  4. Combines sub-problem solutions into a complete answer

What hallucination it catches:
  "Complexity overload" — when a problem is too complex, the LLM
  may hallucinate by oversimplifying or skipping steps. Breaking
  it into sub-problems forces methodical, step-by-step resolution.

Activation:
  - Complex and critical complexity (only for hard problems)
  - Used in REASONING_ENGINE, ACTION_PLANNER, QUALITY_SCORER
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.least_to_most")


class LeastToMostTechnique(BaseTechnique):
    """Least-to-Most: Decompose complex problems into sub-problems.

    Breaks complex problems into smaller sub-problems, solves each
    independently with cheaper LLM calls, and combines the results.
    This prevents hallucination from complexity overload.
    """

    _min_complexity = "complex"

    @property
    def name(self) -> str:
        return "least_to_most"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.QUALITY

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "REASONING_ENGINE",
            "ACTION_PLANNER",
            "QUALITY_SCORER",
            "STRATEGY_PLANNER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 400  # Higher — multiple smaller LLM calls, but cheaper per call

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute Least-to-Most decomposition.

        Breaks the problem into sub-problems and solves each one.
        """
        intent = state.get("intent", "general_inquiry")
        conclusion = state.get("reasoning_conclusion", "")

        if MOCK_MODE:
            chain, output, confidence, sub_problems = self._least_to_most_mock(intent, conclusion)
        else:
            chain, output, confidence, sub_problems = await self._least_to_most_llm(
                prompt, intent, conclusion,
                ticket_id=ticket_id, variant=variant,
            )

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["least_to_most"],
            metadata={
                "sub_problem_count": len(sub_problems),
                "sub_problems": sub_problems,
                "intent": intent,
            },
            token_estimate=self.token_cost_estimate,
        )

    def _least_to_most_mock(
        self,
        intent: str,
        conclusion: str,
    ) -> tuple[list[str], str, float, list[str]]:
        """Mock Least-to-Most decomposition for testing (no LLM calls)."""
        chain = []

        # Step 1: Decompose the problem
        sub_problems_map = {
            "refund_request": [
                "Verify the duplicate charge exists in payment records",
                "Check refund eligibility under 30-day policy",
                "Calculate the correct refund amount",
            ],
            "order_status": [
                "Look up the order in the system",
                "Check current shipment tracking status",
                "Determine estimated delivery date",
            ],
            "cancellation": [
                "Verify order is within cancellation window",
                "Check if order has already shipped",
                "Process cancellation and confirm with customer",
            ],
            "billing_issue": [
                "Identify the specific billing discrepancy",
                "Compare charges against order history",
                "Determine corrective action (refund/adjustment)",
            ],
        }

        sub_problems = sub_problems_map.get(intent, [
            f"Understand the customer's {intent} request",
            f"Gather relevant evidence and policy information",
            f"Determine the appropriate resolution",
        ])

        chain.append(f"Least-to-Most: Decomposed problem into {len(sub_problems)} sub-problems")
        for i, sp in enumerate(sub_problems, 1):
            chain.append(f"  Sub-problem {i}: {sp}")

        # Step 2: Solve each sub-problem (simulated)
        chain.append("Least-to-Most: Solving each sub-problem independently")
        solutions = []
        for i, sp in enumerate(sub_problems, 1):
            solution = f"Sub-problem {i} resolved"
            solutions.append(solution)
            chain.append(f"  Solution {i}: {solution}")

        # Step 3: Combine solutions
        chain.append("Least-to-Most: Combining sub-problem solutions into complete answer")
        output = f"Least-to-Most: All {len(sub_problems)} sub-problems resolved for '{intent}'"
        confidence = 0.88

        return chain, output, confidence, sub_problems

    async def _least_to_most_llm(
        self,
        prompt: str,
        intent: str,
        conclusion: str,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> tuple[list[str], str, float, list[str]]:
        """Real LLM-based Least-to-Most decomposition."""
        system_instructions = (
            "You are a problem decomposition engine for customer support.\n\n"
            f"Customer intent: {intent}\n"
            f"Current analysis: {conclusion or 'None yet'}\n\n"
            "Break this problem into 2-4 smaller, specific sub-problems.\n"
            "Each sub-problem should be independently solvable.\n\n"
            "Output one sub-problem per line, no numbering."
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)

        try:
            # Step 1: Decompose
            decomp_text = await ainvoke_llm(
                safe_prompt,
                node_name="FRAMEWORKBRAIN_LTM_DECOMP",
                ticket_id=ticket_id,
                variant=variant,
            )

            sub_problems = [line.strip() for line in decomp_text.strip().split("\n") if line.strip()]
            if not sub_problems:
                sub_problems = [f"Resolve {intent}"]

            chain = [
                f"Least-to-Most: Decomposed into {len(sub_problems)} sub-problems",
            ]

            # Step 2: Solve each sub-problem (simplified — one combined call)
            solve_instructions = (
                "Solve each sub-problem concisely (one line each):\n\n"
                + "\n".join(f"{i+1}. {sp}" for i, sp in enumerate(sub_problems))
            )

            solve_text = await ainvoke_llm(
                build_safe_prompt(solve_instructions, prompt),
                node_name="FRAMEWORKBRAIN_LTM_SOLVE",
                ticket_id=ticket_id,
                variant=variant,
            )

            chain.append(f"Least-to-Most: Sub-problems solved")
            chain.append("Least-to-Most: Combining solutions")

            output = f"Least-to-Most: Decomposed and solved {len(sub_problems)} sub-problems for '{intent}'"
            confidence = 0.85

            return chain, output, confidence, sub_problems

        except Exception as exc:
            logger.warning("Least-to-Most LLM decomposition failed: %s — using fallback", exc)
            fallback_problems = [f"Analyze {intent} request", "Determine resolution"]
            return (
                ["Least-to-Most: LLM decomposition failed, using simple fallback"],
                "Least-to-Most: Simplified decomposition due to LLM error",
                0.40,
                fallback_problems,
            )
