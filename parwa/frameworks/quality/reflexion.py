"""Reflexion — Self-reflective improvement after generating output.

How it works:
  1. Takes the generated response/reasoning
  2. Reviews it critically for weaknesses
  3. Identifies specific problems (unsupported claims, gaps, contradictions)
  4. If problems found, suggests improvements
  5. Returns the critique and improvement suggestions

What hallucination it catches:
  "Obvious errors" — the model reads its own output and catches
  unsupported claims, logical gaps, factual contradictions, and
  missing information that it missed during generation.

Activation:
  - Medium complexity and above
  - Used in QUALITY_SCORER and RESPONSE_FORMATTER
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.reflexion")


class ReflexionTechnique(BaseTechnique):
    """Reflexion: Self-reflective improvement of generated output.

    Reviews the system's own reasoning and response for weaknesses,
    unsupported claims, and logical gaps. Suggests improvements
    before the response is sent to the customer.
    """

    _min_complexity = "medium"

    @property
    def name(self) -> str:
        return "reflexion"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.QUALITY

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "QUALITY_SCORER",
            "RESPONSE_FORMATTER",
            "REASONING_ENGINE",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 200  # Moderate — one reflection pass

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute Reflexion self-review.

        Reviews the current reasoning/response for weaknesses
        and suggests improvements.
        """
        intent = state.get("intent", "general_inquiry")
        conclusion = state.get("reasoning_conclusion", "")
        verification_passed = state.get("verification_passed", False)

        if MOCK_MODE:
            chain, output, confidence, issues = self._reflexion_mock(
                intent, conclusion, verification_passed
            )
        else:
            chain, output, confidence, issues = await self._reflexion_llm(
                prompt, intent, conclusion, verification_passed,
                ticket_id=ticket_id, variant=variant,
            )

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["reflexion"],
            metadata={
                "issues_found": len(issues),
                "issues": issues,
                "intent": intent,
            },
            token_estimate=self.token_cost_estimate,
        )

    def _reflexion_mock(
        self,
        intent: str,
        conclusion: str,
        verification_passed: bool,
    ) -> tuple[list[str], str, float, list[str]]:
        """Mock Reflexion self-review for testing (no LLM calls)."""
        chain = []
        issues = []

        # Step 1: Review the reasoning conclusion
        chain.append("Reflexion: Reviewing reasoning conclusion for weaknesses")

        if not conclusion:
            chain.append("Reflexion: ISSUE — No reasoning conclusion present")
            issues.append("no_conclusion")
        else:
            chain.append(f"Reflexion: Conclusion found — '{conclusion[:80]}...'")

            # Check for unsupported claims
            if "eligible" in conclusion.lower() and not verification_passed:
                chain.append("Reflexion: ISSUE — Claims eligibility without verification")
                issues.append("unverified_eligibility_claim")

            # Check for vague language
            vague_terms = ["maybe", "possibly", "might", "perhaps", "i think"]
            if any(term in conclusion.lower() for term in vague_terms):
                chain.append("Reflexion: ISSUE — Contains vague/uncertain language")
                issues.append("vague_language")

        # Step 2: Review verification status
        if not verification_passed:
            chain.append("Reflexion: ISSUE — Verification has not passed")
            issues.append("verification_not_passed")
        else:
            chain.append("Reflexion: Verification passed — conclusion is grounded")

        # Step 3: Generate improvement suggestions
        if issues:
            chain.append(f"Reflexion: Found {len(issues)} issue(s) — improvement needed")
            output = f"Reflexion: {len(issues)} issue(s) identified — {'; '.join(issues)}"
            confidence = 0.60
        else:
            chain.append("Reflexion: No issues found — response is sound")
            output = "Reflexion: Response passed self-review — no improvements needed"
            confidence = 0.92

        return chain, output, confidence, issues

    async def _reflexion_llm(
        self,
        prompt: str,
        intent: str,
        conclusion: str,
        verification_passed: bool,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> tuple[list[str], str, float, list[str]]:
        """Real LLM-based Reflexion self-review."""
        system_instructions = (
            "You are a Reflexion reviewer for customer support responses.\n\n"
            f"Customer intent: {intent}\n"
            f"Current conclusion: {conclusion or 'None'}\n"
            f"Verification passed: {verification_passed}\n\n"
            "Critically review this conclusion for:\n"
            "1. Unsupported claims (claims without evidence)\n"
            "2. Logical gaps (missing steps in reasoning)\n"
            "3. Vague language (uncertain hedging)\n"
            "4. Factual errors (contradictions with known data)\n\n"
            "Format:\n"
            "ISSUES: <count>\n"
            "ISSUE_1: <description>\n"
            "...\n"
            "VERDICT: <sound|needs_improvement>\n"
            "SUGGESTION: <how to improve>"
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)

        try:
            text = await ainvoke_llm(
                safe_prompt,
                node_name="FRAMEWORKBRAIN_REFLEXION",
                ticket_id=ticket_id,
                variant=variant,
            )

            chain = [line.strip() for line in text.strip().split("\n") if line.strip()]
            issues = []
            confidence = 0.70

            for line in chain:
                if line.startswith("ISSUE_"):
                    issue_desc = line.split(":", 1)[1].strip() if ":" in line else line
                    issues.append(issue_desc)
                elif line.startswith("VERDICT:"):
                    verdict = line.split(":")[1].strip().lower()
                    if verdict == "sound":
                        confidence = 0.90
                    else:
                        confidence = 0.55

            output = chain[-1] if chain else "Reflexion review complete"

            return chain, output, confidence, issues

        except Exception as exc:
            logger.warning("Reflexion LLM review failed: %s — using fallback", exc)
            return (
                ["Reflexion: LLM review failed, using basic checks"],
                "Reflexion: Basic review — cannot perform deep reflection",
                0.40,
                ["llm_reflection_unavailable"],
            )
