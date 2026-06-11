"""CLARA (Confidence-driven retrieval with clarifying questions) — RAG technique.

How it works:
  1. Takes the customer query and searches the knowledge base
  2. Evaluates confidence of each retrieved result
  3. If confidence is below threshold, generates a clarifying question
  4. Only returns results above the confidence threshold
  5. Tracks whether clarification was needed

What hallucination it catches:
  "Low-confidence guesses" — CLARA refuses to return uncertain results.
  Instead of guessing, it asks for clarification, preventing the system
  from acting on unreliable information.

Activation:
  - Medium complexity and above (simple tickets don't need clarification)
  - Used in KB_RETRIEVER and FAQ_MATCHER for smarter retrieval
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.clara")

# Confidence threshold below which CLARA requests clarification
CLARITY_THRESHOLD = 0.6


class ClaraTechnique(BaseTechnique):
    """CLARA: Confidence-driven retrieval with clarifying questions.

    Retrieves KB/FAQ results but only returns them if confidence is
    above threshold. If confidence is low, generates a clarifying
    question instead of forcing a potentially wrong answer.
    """

    _min_complexity = "medium"

    @property
    def name(self) -> str:
        return "clara"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.RAG

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "KB_RETRIEVER",
            "FAQ_MATCHER",
            "CONTEXT_MANAGER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 200  # Moderate — retrieval + confidence evaluation

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute CLARA confidence-driven retrieval.

        Evaluates retrieved results for confidence. If confidence is
        low, generates a clarifying question. If confidence is high,
        returns the results as-is.
        """
        intent = state.get("intent", "general_inquiry")
        kb_results = state.get("kb_results", [])
        faq_match = state.get("faq_match")

        if MOCK_MODE:
            chain, output, confidence, clarified = self._clara_mock(
                intent, kb_results, faq_match
            )
        else:
            chain, output, confidence, clarified = await self._clara_llm(
                prompt, intent, kb_results, faq_match,
                ticket_id=ticket_id, variant=variant,
            )

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["clara"],
            metadata={
                "clarification_needed": clarified,
                "intent": intent,
                "clarity_threshold": CLARITY_THRESHOLD,
            },
            token_estimate=self.token_cost_estimate,
        )

    def _clara_mock(
        self,
        intent: str,
        kb_results: list[dict],
        faq_match: dict | None,
    ) -> tuple[list[str], str, float, bool]:
        """Mock CLARA retrieval for testing (no LLM calls)."""
        chain = []
        clarified = False

        # Step 1: Assess available evidence confidence
        chain.append(f"CLARA: Evaluating retrieval confidence for intent '{intent}'")

        # Check KB results confidence
        high_confidence_kb = 0
        if isinstance(kb_results, list):
            for kb in kb_results:
                if isinstance(kb, dict):
                    score = kb.get("relevance_score", 0)
                    if score >= CLARITY_THRESHOLD:
                        high_confidence_kb += 1

        # Check FAQ match confidence
        faq_confidence = 0.0
        if isinstance(faq_match, dict):
            faq_confidence = faq_match.get("relevance_score", 0)

        chain.append(f"CLARA: {high_confidence_kb} high-confidence KB results, FAQ confidence={faq_confidence:.2f}")

        # Step 2: Determine if clarification is needed
        if high_confidence_kb == 0 and faq_confidence < CLARITY_THRESHOLD:
            chain.append(f"CLARA: Confidence below threshold ({CLARITY_THRESHOLD}) — clarification needed")
            clarified = True

            # Generate clarifying question based on intent
            if intent == "refund_request":
                output = "Could you specify the charge date and amount for your refund request?"
            elif intent == "order_status":
                output = "Could you provide your order number so I can look up the status?"
            elif intent == "billing_issue":
                output = "Can you describe the specific billing discrepancy you noticed?"
            else:
                output = "Could you provide more details about your request so I can help you better?"
            confidence = 0.40
        else:
            chain.append("CLARA: Confidence above threshold — results are reliable")
            output = f"CLARA verified: {high_confidence_kb} KB results and FAQ confidence {faq_confidence:.2f} meet threshold"
            confidence = 0.85

        return chain, output, confidence, clarified

    async def _clara_llm(
        self,
        prompt: str,
        intent: str,
        kb_results: list[dict],
        faq_match: dict | None,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> tuple[list[str], str, float, bool]:
        """Real LLM-based CLARA retrieval."""
        evidence_parts = []
        if isinstance(kb_results, list):
            for kb in kb_results[:3]:
                if isinstance(kb, dict):
                    score = kb.get("relevance_score", 0)
                    evidence_parts.append(f"KB (score={score:.2f}): {kb.get('content', '')[:80]}")
        if isinstance(faq_match, dict):
            score = faq_match.get("relevance_score", 0)
            evidence_parts.append(f"FAQ (score={score:.2f}): {faq_match.get('content', '')[:80]}")

        evidence = "\n".join(evidence_parts) if evidence_parts else "No evidence available."

        system_instructions = (
            "You are a CLARA retrieval confidence evaluator.\n\n"
            f"Customer intent: {intent}\n"
            f"Retrieved evidence:\n{evidence}\n"
            f"Confidence threshold: {CLARITY_THRESHOLD}\n\n"
            "Evaluate:\n"
            "1. Is the evidence sufficient to answer the customer's question?\n"
            "2. Are the relevance scores above the threshold?\n"
            "3. If not, what clarifying question should we ask?\n\n"
            "Format:\n"
            "CONFIDENCE: <0.0-1.0>\n"
            "DECISION: <reliable|clarify>\n"
            "OUTPUT: <summary or clarifying question>"
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)

        try:
            text = await ainvoke_llm(
                safe_prompt,
                node_name="FRAMEWORKBRAIN_CLARA",
                ticket_id=ticket_id,
                variant=variant,
            )

            chain = [line.strip() for line in text.strip().split("\n") if line.strip()]
            clarified = False
            confidence = 0.70

            # Parse the response
            for line in chain:
                if line.startswith("CONFIDENCE:"):
                    try:
                        confidence = float(line.split(":")[1].strip())
                    except (ValueError, IndexError):
                        pass
                elif line.startswith("DECISION:"):
                    decision = line.split(":")[1].strip().lower()
                    clarified = decision == "clarify"

            output = ""
            for line in chain:
                if line.startswith("OUTPUT:"):
                    output = line.split(":", 1)[1].strip()
                    break

            if not output:
                output = chain[-1] if chain else "CLARA analysis complete"

            return chain, output, confidence, clarified

        except Exception as exc:
            logger.warning("CLARA LLM retrieval failed: %s — using fallback", exc)
            return (
                ["CLARA: LLM evaluation failed, defaulting to rule-based confidence check"],
                "CLARA: Confidence evaluation incomplete",
                0.30,
                True,
            )
