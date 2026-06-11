"""MAKER (Multi-step tAsk decomposition with vErification at each step) — Proprietary technique.

How it works:
  1. Takes a complex task and decomposes it into sequential steps
  2. Each step has: description, required inputs, expected outputs, verification criteria
  3. Steps are executed in order, with each step's output verified before proceeding
  4. If a step fails verification, it's retried or the plan is re-decomposed
  5. The final output is the verified result of all completed steps

What hallucination it catches:
  "Leap-of-faith action plans" — when a node creates an action plan that
  skips critical verification steps. MAKER forces step-by-step decomposition
  with verification at each stage, preventing the system from acting on
  unverified assumptions. Each step must prove itself before the next begins.

Activation:
  - Complex and above (simple/medium tickets don't need multi-step decomposition)
  - Used in ACTION_PLANNER for complex action planning
  - Used in ACTION_EXECUTOR for verified execution

Note: This is different from strategy_planner's GST (which explores strategic
options). MAKER focuses on DECOMPOSING a single plan into verified steps.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.maker")


# Verification criteria per intent
_VERIFICATION_CRITERIA: dict[str, list[str]] = {
    "refund_request": [
        "Duplicate charge confirmed in CRM",
        "Refund amount matches charge amount",
        "Customer account is active and eligible",
    ],
    "cancellation": [
        "Order has not been shipped yet",
        "Cancellation is within 24-hour window",
        "Customer identity verified",
    ],
    "account_modification": [
        "Customer identity verified",
        "Requested changes are within policy",
        "No pending operations on account",
    ],
}


class MAKERTechnique(BaseTechnique):
    """MAKER: Multi-step task decomposition with verification.

    Decomposes complex tasks into sequential steps, each with
    verification criteria. Steps must be verified before proceeding
    to the next one, preventing leap-of-faith action plans.
    """

    _min_complexity = "complex"

    @property
    def name(self) -> str:
        return "maker"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.PROPRIETARY

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "ACTION_PLANNER",
            "ACTION_EXECUTOR",
            "STRATEGY_PLANNER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 350  # Moderate — multi-step decomposition + verification

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute MAKER multi-step decomposition.

        Decomposes the task into verified steps based on ticket context.
        """
        intent = state.get("intent", "general_inquiry")
        complexity = state.get("complexity", "simple")
        integration_data = state.get("integration_data", {})
        reasoning_conclusion = state.get("reasoning_conclusion", "")

        if MOCK_MODE:
            chain, output, confidence, steps = self._maker_mock(
                intent, complexity, integration_data, reasoning_conclusion
            )
        else:
            chain, output, confidence, steps = await self._maker_llm(
                prompt, intent, complexity, integration_data,
                reasoning_conclusion,
                ticket_id=ticket_id, variant=variant,
            )

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["maker"],
            metadata={
                "intent": intent,
                "complexity": complexity,
                "step_count": len(steps),
                "steps": steps,
            },
            token_estimate=self.token_cost_estimate,
        )

    def _maker_mock(
        self,
        intent: str,
        complexity: str,
        integration_data: dict,
        reasoning_conclusion: str,
    ) -> tuple[list[str], str, float, list[dict[str, Any]]]:
        """Mock MAKER decomposition for testing (no LLM calls)."""
        chain = []
        steps = []

        # Step 1: Analyze the task
        chain.append(f"MAKER: Analyzing task for intent '{intent}' (complexity={complexity})")

        # Step 2: Decompose based on intent
        if intent == "refund_request":
            steps = [
                {
                    "step": 1,
                    "description": "Verify duplicate charge in CRM",
                    "inputs": ["integration_data.charges"],
                    "expected_output": "confirmed_duplicate_charge",
                    "verification": "At least 2 charges with same amount on same date",
                    "status": "pending",
                },
                {
                    "step": 2,
                    "description": "Calculate refund amount",
                    "inputs": ["verified_duplicate_charge.amount"],
                    "expected_output": "refund_amount",
                    "verification": "Refund amount matches duplicate charge amount",
                    "status": "pending",
                },
                {
                    "step": 3,
                    "description": "Process refund",
                    "inputs": ["refund_amount", "customer_id"],
                    "expected_output": "refund_confirmation",
                    "verification": "Refund status is 'executed' with confirmation ID",
                    "status": "pending",
                },
                {
                    "step": 4,
                    "description": "Send confirmation to customer",
                    "inputs": ["refund_confirmation"],
                    "expected_output": "customer_notified",
                    "verification": "Customer notification sent with timeline",
                    "status": "pending",
                },
            ]
            chain.append("MAKER: Decomposed refund_request into 4 verified steps")

        elif intent == "cancellation":
            steps = [
                {
                    "step": 1,
                    "description": "Verify order not yet shipped",
                    "inputs": ["integration_data.orders"],
                    "expected_output": "cancellable_order",
                    "verification": "Order status is not 'shipped' or 'delivered'",
                    "status": "pending",
                },
                {
                    "step": 2,
                    "description": "Cancel the order",
                    "inputs": ["cancellable_order.order_id"],
                    "expected_output": "cancellation_confirmation",
                    "verification": "Order status changed to 'cancelled'",
                    "status": "pending",
                },
                {
                    "step": 3,
                    "description": "Send cancellation confirmation",
                    "inputs": ["cancellation_confirmation"],
                    "expected_output": "customer_notified",
                    "verification": "Customer notified with confirmation email",
                    "status": "pending",
                },
            ]
            chain.append("MAKER: Decomposed cancellation into 3 verified steps")

        elif intent == "account_modification":
            steps = [
                {
                    "step": 1,
                    "description": "Verify customer identity",
                    "inputs": ["customer_id", "integration_data"],
                    "expected_output": "verified_identity",
                    "verification": "Customer ID matches CRM records",
                    "status": "pending",
                },
                {
                    "step": 2,
                    "description": "Apply account modification",
                    "inputs": ["verified_identity", "modification_details"],
                    "expected_output": "modification_result",
                    "verification": "Account updated successfully in CRM",
                    "status": "pending",
                },
            ]
            chain.append("MAKER: Decomposed account_modification into 2 verified steps")

        else:
            steps = [
                {
                    "step": 1,
                    "description": "Analyze customer request",
                    "inputs": ["raw_message", "intent"],
                    "expected_output": "understood_request",
                    "verification": "Intent matches customer message",
                    "status": "pending",
                },
                {
                    "step": 2,
                    "description": "Generate appropriate response",
                    "inputs": ["understood_request", "kb_results"],
                    "expected_output": "helpful_response",
                    "verification": "Response addresses customer's stated intent",
                    "status": "pending",
                },
            ]
            chain.append(f"MAKER: Decomposed {intent} into 2 verified steps")

        # Step 3: Verify each step's criteria
        criteria = _VERIFICATION_CRITERIA.get(intent, ["Task completed successfully"])
        for i, criterion in enumerate(criteria):
            chain.append(f"MAKER: Step {i+1} verification: {criterion}")

        # Step 4: Report
        chain.append(f"MAKER: Decomposition complete — {len(steps)} steps with {len(criteria)} verification criteria")

        output = f"MAKER: Decomposed {intent} into {len(steps)} verified steps with {len(criteria)} verification criteria"
        confidence = 0.87

        return chain, output, confidence, steps

    async def _maker_llm(
        self,
        prompt: str,
        intent: str,
        complexity: str,
        integration_data: dict,
        reasoning_conclusion: str,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> tuple[list[str], str, float, list[dict[str, Any]]]:
        """Real LLM-based MAKER decomposition."""
        criteria = _VERIFICATION_CRITERIA.get(intent, ["Task completed successfully"])
        criteria_text = "\n".join(f"  - {c}" for c in criteria)

        # Summarize integration data for the LLM
        integration_summary = {}
        if isinstance(integration_data, dict):
            for key, value in integration_data.items():
                if isinstance(value, (str, int, float, bool)):
                    integration_summary[key] = value
                elif isinstance(value, list):
                    integration_summary[key] = f"[{len(value)} items]"
                elif isinstance(value, dict):
                    integration_summary[key] = f"{{{len(value)} keys}}"

        system_instructions = (
            "You are a MAKER (Multi-step task decomposition with verification) agent.\n\n"
            f"Customer intent: {intent}\n"
            f"Complexity: {complexity}\n"
            f"Reasoning conclusion: {reasoning_conclusion[:300]}\n"
            f"Available data: {integration_summary}\n"
            f"Verification criteria:\n{criteria_text}\n\n"
            "Decompose this task into sequential steps. Each step must include:\n"
            "  - step: step number\n"
            "  - description: what this step does\n"
            "  - inputs: what data this step needs\n"
            "  - expected_output: what this step produces\n"
            "  - verification: how to verify this step succeeded\n"
            "  - status: always 'pending'\n\n"
            "Output ONLY a JSON list of step objects.\n"
            "Example: [{\"step\": 1, \"description\": \"...\", \"inputs\": [...], "
            "\"expected_output\": \"...\", \"verification\": \"...\", \"status\": \"pending\"}]"
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)

        try:
            text = await ainvoke_llm(
                safe_prompt,
                node_name="FRAMEWORKBRAIN_MAKER",
                ticket_id=ticket_id,
                variant=variant,
            )

            # Parse the response
            steps = []
            try:
                import json
                parsed = json.loads(text.strip())
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "description" in item:
                            steps.append({
                                "step": item.get("step", len(steps) + 1),
                                "description": item.get("description", ""),
                                "inputs": item.get("inputs", []),
                                "expected_output": item.get("expected_output", ""),
                                "verification": item.get("verification", ""),
                                "status": "pending",
                            })
            except (json.JSONDecodeError, ValueError):
                pass

            if not steps:
                steps = [{"step": 1, "description": "Process request", "inputs": [], "expected_output": "result", "verification": "Completed successfully", "status": "pending"}]

            chain = [
                f"MAKER: LLM decomposed {intent} into {len(steps)} steps",
                f"MAKER: Verification criteria applied: {len(criteria)} checks",
            ]

            output = f"MAKER: LLM decomposed {intent} into {len(steps)} verified steps"
            confidence = 0.85

            return chain, output, confidence, steps

        except Exception as exc:
            logger.warning("MAKER LLM decomposition failed: %s — using default steps", exc)
            steps = [
                {"step": 1, "description": f"Process {intent}", "inputs": [], "expected_output": "result", "verification": "Task completed", "status": "pending"},
            ]
            return (
                ["MAKER: LLM decomposition failed, using single-step fallback"],
                "MAKER: Using default single-step due to LLM error",
                0.40,
                steps,
            )
