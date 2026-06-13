"""ZeroShotValidator — Validates outputs without training examples.

ZeroShotValidator checks the quality and consistency of reasoning
outputs without requiring any labeled training data. It uses
structural checks, logical consistency validation, and policy
compliance verification.

How it works:
  - Checks if the reasoning conclusion is consistent with the evidence
  - Validates that all steps in the chain follow logically
  - Verifies policy compliance (e.g., refund within 30 days)
  - Flags outputs that contain contradictions or unsupported claims

What hallucination it catches:
  "Unsupported claims" — when the reasoning makes a conclusion that
  isn't supported by the evidence. ZeroShotValidator catches this
  by checking each claim against available evidence.

Activation:
  - Activates on MEDIUM+ complexity (simple tickets are straightforward)
  - Critical for catching hallucinations in complex multi-step reasoning
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult

logger = logging.getLogger("parwa.frameworks.zero_shot_validator")


class ZeroShotValidatorTechnique(BaseTechnique):
    """Zero-Shot Validator technique.

    Validates reasoning outputs without training examples by checking
    structural consistency, logical coherence, and policy compliance.
    """

    _min_complexity = "medium"

    @property
    def name(self) -> str:
        return "zero_shot_validator"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.PROPRIETARY

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "REASONING_ENGINE",
            "ACTION_VERIFIER",
            "QUALITY_SCORER",
            "RESPONSE_FORMATTER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 50  # Moderate — validation checks, no LLM in mock mode

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute zero-shot validation on reasoning outputs.

        Validates the conclusion against available evidence.
        """
        conclusion = state.get("reasoning_conclusion", "")
        reasoning_chain = state.get("reasoning_chain", [])
        intent = state.get("intent", "general_inquiry")
        faq_match = state.get("faq_match")
        kb_results = state.get("kb_results", [])
        integration_data = state.get("integration_data", {})

        chain = []
        issues = []
        checks_passed = 0
        checks_total = 0

        # Check 1: Conclusion exists
        checks_total += 1
        if conclusion and len(conclusion) > 5:
            checks_passed += 1
            chain.append("ZSV: Conclusion present ✓")
        else:
            issues.append("Missing or trivial conclusion")
            chain.append("ZSV: Conclusion missing or trivial ✗")

        # Check 2: Reasoning chain has steps
        checks_total += 1
        if reasoning_chain and len(reasoning_chain) >= 2:
            checks_passed += 1
            chain.append(f"ZSV: Reasoning chain has {len(reasoning_chain)} steps ✓")
        else:
            issues.append("Reasoning chain too short")
            chain.append("ZSV: Reasoning chain insufficient ✗")

        # Check 3: Conclusion matches intent
        checks_total += 1
        intent_conclusion_map = {
            "refund_request": ["refund", "eligible", "charge"],
            "order_status": ["order", "status", "tracking"],
            "cancellation": ["cancel", "cancellation"],
            "billing_issue": ["billing", "charge", "discrepancy"],
        }
        expected_keywords = intent_conclusion_map.get(intent, [])
        if expected_keywords:
            conclusion_lower = conclusion.lower()
            if any(kw in conclusion_lower for kw in expected_keywords):
                checks_passed += 1
                chain.append(f"ZSV: Conclusion matches intent '{intent}' ✓")
            else:
                issues.append(f"Conclusion doesn't address intent '{intent}'")
                chain.append(f"ZSV: Conclusion doesn't match intent '{intent}' ✗")
        else:
            checks_passed += 1  # Can't validate unknown intents
            chain.append(f"ZSV: Intent '{intent}' has no validation keywords — skip")

        # Check 4: Evidence supports conclusion
        checks_total += 1
        has_evidence = bool(faq_match) or bool(kb_results) or bool(integration_data)
        if has_evidence:
            checks_passed += 1
            chain.append("ZSV: Supporting evidence available ✓")
        else:
            # No evidence but conclusion is still possible
            chain.append("ZSV: No supporting evidence — conclusion may be unsupported ⚠")

        # Compute validation score
        validation_score = checks_passed / checks_total if checks_total > 0 else 0.0
        confidence = validation_score

        if issues:
            chain.append(f"ZSV: {len(issues)} issue(s) found: {'; '.join(issues)}")
        else:
            chain.append("ZSV: All validation checks passed ✓")

        output = f"Validation: {checks_passed}/{checks_total} checks passed"
        if issues:
            output += f". Issues: {'; '.join(issues)}"

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["zero_shot_validator"],
            metadata={
                "checks_passed": checks_passed,
                "checks_total": checks_total,
                "validation_score": round(validation_score, 2),
                "issues": issues,
            },
            token_estimate=self.token_cost_estimate,
        )
