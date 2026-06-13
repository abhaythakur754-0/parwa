"""Uncertainty of Thought (UoT) — Detects and handles model uncertainty.

How it works:
  1. Checks confidence levels of prior reasoning steps
  2. Detects conflicting evidence or low-confidence conclusions
  3. If uncertain → triggers deeper analysis OR escalation
  4. If confident → passes through without modification

What hallucination it catches:
  "Overconfident wrong answers" — UoT detects when the model is
  uncertain but acting confident. It forces the system to acknowledge
  uncertainty instead of guessing.

Activation:
  - CRITICAL complexity only (this is the emergency brake)
  - Used in REASONING_ENGINE alongside CoT and ReAct
  - Also activates when loop_count > 0 (re-processing)
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.uot")


# Thresholds for uncertainty detection
LOW_CONFIDENCE_THRESHOLD = 0.40
CONFLICT_THRESHOLD = 0.30  # If top 2 path confidences differ by less than this


class UncertaintyOfThoughtTechnique(BaseTechnique):
    """Uncertainty of Thought reasoning technique.

    Detects when the model is uncertain about its conclusions and
    triggers appropriate handling — either deeper analysis or escalation.
    This is the "emergency brake" that prevents overconfident wrong answers.
    """

    _min_complexity = "critical"  # Only activates on critical complexity

    @property
    def name(self) -> str:
        return "uncertainty_of_thought"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.REASONING

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "REASONING_ENGINE",
            "ESCALATION_DECISION",
            "QUALITY_SCORER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 100  # Light — mostly analysis, short LLM call

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute Uncertainty of Thought analysis.

        Checks for uncertainty signals and recommends handling.
        """
        conclusion = state.get("reasoning_conclusion", "")
        intent_confidence = state.get("intent_confidence", 0.0)
        reasoning_paths = state.get("reasoning_paths", [])
        loop_count = state.get("loop_count", 0)
        quality_score = state.get("quality_score", 0.0)

        if MOCK_MODE:
            chain, output, confidence, is_uncertain, recommendation = self._uot_mock(
                conclusion, intent_confidence, reasoning_paths, loop_count, quality_score
            )
        else:
            chain, output, confidence, is_uncertain, recommendation = await self._uot_llm(
                prompt, conclusion, intent_confidence, reasoning_paths,
                loop_count, quality_score,
                ticket_id=ticket_id, variant=variant
            )

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["uncertainty_of_thought"],
            metadata={
                "is_uncertain": is_uncertain,
                "recommendation": recommendation,
                "intent_confidence": intent_confidence,
                "loop_count": loop_count,
                "quality_score": quality_score,
            },
            token_estimate=self.token_cost_estimate,
        )

    def _uot_mock(
        self,
        conclusion: str,
        intent_confidence: float,
        reasoning_paths: list,
        loop_count: int,
        quality_score: float,
    ) -> tuple[list[str], str, float, bool, str]:
        """Mock UoT for testing."""
        chain = []
        uncertainty_signals = []

        # Check 1: Intent confidence
        chain.append(f"UoT: Checking intent confidence — {intent_confidence:.2f}")
        if intent_confidence < LOW_CONFIDENCE_THRESHOLD:
            uncertainty_signals.append("low_intent_confidence")
            chain.append(f"UoT: WARNING — Intent confidence below {LOW_CONFIDENCE_THRESHOLD}")

        # Check 2: Path consensus (if ToT was run)
        if reasoning_paths and isinstance(reasoning_paths, list) and len(reasoning_paths) >= 2:
            confidences = []
            for p in reasoning_paths:
                if isinstance(p, dict):
                    confidences.append(p.get("confidence", 0))
                else:
                    confidences.append(0.5)
            if len(confidences) >= 2:
                sorted_c = sorted(confidences, reverse=True)
                if sorted_c[0] - sorted_c[1] < CONFLICT_THRESHOLD:
                    uncertainty_signals.append("path_conflict")
                    chain.append("UoT: WARNING — Top reasoning paths have similar confidence (no clear winner)")

        # Check 3: Loop count (re-processing = previous answer wasn't good enough)
        chain.append(f"UoT: Checking loop count — {loop_count}")
        if loop_count > 0:
            uncertainty_signals.append("reprocessing")
            chain.append("UoT: NOTE — Ticket is being re-processed (previous attempt may have been uncertain)")

        # Check 4: Quality score (if available)
        if quality_score > 0 and quality_score < 80:
            uncertainty_signals.append("low_quality")
            chain.append(f"UoT: WARNING — Quality score {quality_score} is below threshold (80)")

        # Determine uncertainty level and recommendation
        is_uncertain = len(uncertainty_signals) >= 1

        if not is_uncertain:
            chain.append("UoT: No uncertainty detected — conclusion is reliable")
            output = "UoT analysis: No uncertainty signals detected. Conclusion is reliable."
            confidence = 0.90
            recommendation = "proceed"
        elif len(uncertainty_signals) == 1:
            chain.append(f"UoT: Minor uncertainty detected — {uncertainty_signals[0]}")
            output = f"UoT analysis: Minor uncertainty ({uncertainty_signals[0]}). Recommend additional verification."
            confidence = 0.55
            recommendation = "verify"
        else:
            chain.append(f"UoT: SIGNIFICANT uncertainty — {len(uncertainty_signals)} signals: {uncertainty_signals}")
            output = f"UoT analysis: Significant uncertainty detected. Recommend escalation or deeper analysis."
            confidence = 0.25
            recommendation = "escalate"

        return chain, output, confidence, is_uncertain, recommendation

    async def _uot_llm(
        self,
        prompt: str,
        conclusion: str,
        intent_confidence: float,
        reasoning_paths: list,
        loop_count: int,
        quality_score: float,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> tuple[list[str], str, float, bool, str]:
        """Real LLM-based UoT analysis."""
        system_instructions = (
            "You are an uncertainty detection engine.\n"
            "Analyze the following reasoning result for uncertainty signals.\n\n"
            f"Conclusion: {conclusion or 'None'}\n"
            f"Intent confidence: {intent_confidence:.2f}\n"
            f"Loop count: {loop_count}\n"
            f"Quality score: {quality_score}\n"
            f"Number of reasoning paths: {len(reasoning_paths) if reasoning_paths else 0}\n\n"
            "Check for:\n"
            "1. Is the conclusion vague or hedging?\n"
            "2. Is there conflicting evidence?\n"
            "3. Is the confidence too low for the claim?\n\n"
            "Respond with:\n"
            "UNCERTAINTY: <none/minor/significant>\n"
            "RECOMMENDATION: <proceed/verify/escalate>\n"
            "REASON: <brief explanation>"
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)

        try:
            text = await ainvoke_llm(
                safe_prompt,
                node_name="FRAMEWORKBRAIN_UOT",
                ticket_id=ticket_id,
                variant=variant,
            )
            chain = [line.strip() for line in text.strip().split("\n") if line.strip()]

            is_uncertain = not any("uncertainty: none" in line.lower() for line in chain)
            if "minor" in text.lower():
                recommendation = "verify"
                confidence = 0.55
            elif "significant" in text.lower():
                recommendation = "escalate"
                confidence = 0.25
            else:
                recommendation = "proceed"
                confidence = 0.90
                is_uncertain = False

            return chain, text.strip(), confidence, is_uncertain, recommendation

        except Exception as exc:
            logger.warning("UoT LLM analysis failed: %s — using fallback", exc)
            return (
                ["UoT: LLM call failed — assuming minor uncertainty as precaution"],
                "UoT: Analysis incomplete, recommending verification as precaution",
                0.40,
                True,
                "verify",
            )
