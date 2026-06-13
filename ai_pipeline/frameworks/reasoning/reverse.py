"""Reverse Thinking — Works backwards from conclusion to evidence.

How it works:
  1. Start from the proposed conclusion
  2. Trace backwards: conclusion → supporting evidence → source data
  3. If the trace can't reach source data → REJECT the conclusion
  4. If the trace is complete → CONFIRM the conclusion

What hallucination it catches:
  "Unsupported conclusions" — if the conclusion can't be traced back
  to actual evidence, it's a hallucination. This catches confident
  but baseless claims.

Activation:
  - Medium complexity and above
  - Used in REVERSE_THINKER node
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.reverse")


class ReverseThinkingTechnique(BaseTechnique):
    """Reverse Thinking reasoning technique.

    Validates conclusions by tracing backwards from the proposed
    answer to the evidence. If the trace fails, the conclusion
    is rejected as potentially hallucinated.
    """

    _min_complexity = "medium"  # Activates on medium+

    @property
    def name(self) -> str:
        return "reverse_thinking"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.REASONING

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "REVERSE_THINKER",
            "ACTION_VERIFIER",
            "QUALITY_SCORER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 200  # Moderate — one trace-back LLM call

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute Reverse Thinking validation.

        Traces from the conclusion backwards through evidence.
        """
        conclusion = state.get("reasoning_conclusion", "")
        kb_results = state.get("kb_results", [])
        integration_data = state.get("integration_data", {})

        if MOCK_MODE:
            chain, output, confidence, passed = self._reverse_mock(
                conclusion, kb_results, integration_data
            )
        else:
            chain, output, confidence, passed = await self._reverse_llm(
                prompt, conclusion, kb_results, integration_data,
                ticket_id=ticket_id, variant=variant
            )

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["reverse_thinking"],
            metadata={
                "passed": passed,
                "had_conclusion": bool(conclusion),
                "had_kb": bool(kb_results),
                "had_crm": bool(integration_data),
            },
            token_estimate=self.token_cost_estimate,
        )

    def _reverse_mock(
        self,
        conclusion: str,
        kb_results: list[dict],
        integration_data: dict,
    ) -> tuple[list[str], str, float, bool]:
        """Mock Reverse Thinking for testing."""
        chain = []
        evidence_found = True

        # Step 1: Start from the conclusion
        chain.append(f"TRACE: Starting from conclusion — {conclusion}")

        # Step 2: What evidence supports this conclusion?
        if kb_results and isinstance(kb_results, list) and len(kb_results) > 0:
            chain.append(f"TRACE: KB evidence found — {len(kb_results)} document(s)")
        else:
            chain.append("TRACE: No KB evidence found")
            evidence_found = False

        # Step 3: Does CRM data support this?
        if integration_data and isinstance(integration_data, dict) and len(integration_data) > 1:
            chain.append("TRACE: CRM data available for verification")
        else:
            chain.append("TRACE: Limited CRM data")
            # Don't fail on just this — some tickets don't need CRM data

        # Step 4: Final verdict
        if evidence_found:
            chain.append("TRACE: Evidence confirmed — PASSED")
            output = "Reverse trace complete: Conclusion is supported by evidence."
            confidence = 0.92
            passed = True
        else:
            chain.append("TRACE: Evidence insufficient — FAILED")
            output = "Reverse trace failed: Conclusion lacks supporting evidence."
            confidence = 0.30
            passed = False

        return chain, output, confidence, passed

    async def _reverse_llm(
        self,
        prompt: str,
        conclusion: str,
        kb_results: list[dict],
        integration_data: dict,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> tuple[list[str], str, float, bool]:
        """Real LLM-based Reverse Thinking."""
        # Build evidence summary
        evidence_parts = []
        if kb_results and isinstance(kb_results, list):
            for kb in kb_results[:3]:
                if isinstance(kb, dict):
                    evidence_parts.append(f"KB: {kb.get('content', '')[:100]}")
        if integration_data and isinstance(integration_data, dict):
            evidence_parts.append(f"CRM: {integration_data}")

        evidence = "\n".join(evidence_parts) if evidence_parts else "No data available."

        system_instructions = (
            "You are a reverse thinking validation engine.\n"
            "Given a conclusion, trace BACKWARDS to the evidence.\n\n"
            f"Proposed conclusion: {conclusion or 'None'}\n"
            f"Available evidence:\n{evidence}\n\n"
            "Trace each step from conclusion back to source data.\n"
            "If you CANNOT trace back to actual evidence, say: TRACE FAILED\n"
            "If the trace is complete, say: TRACE PASSED\n\n"
            "Format: TRACE: <each step>\nEnd with: TRACE PASSED or TRACE FAILED"
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)

        try:
            text = await ainvoke_llm(
                safe_prompt,
                node_name="FRAMEWORKBRAIN_REVERSE",
                ticket_id=ticket_id,
                variant=variant,
            )
            chain = [line.strip() for line in text.strip().split("\n") if line.strip()]

            passed = any("trace passed" in line.lower() for line in chain) and \
                     not any("trace failed" in line.lower() for line in chain)

            confidence = 0.85 if passed else 0.35
            output = "Reverse trace: PASSED" if passed else "Reverse trace: FAILED"

            return chain, output, confidence, passed

        except Exception as exc:
            logger.warning("Reverse Thinking LLM failed: %s — using fallback", exc)
            return (
                ["TRACE: LLM call failed — cannot verify"],
                "Reverse trace incomplete due to LLM error",
                0.20,
                False,
            )
