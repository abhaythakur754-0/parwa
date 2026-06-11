"""GSD (Get Stuff Done) — Aggressive state compression + focus technique.

How it works:
  1. Takes the full ticket state and identifies what the current node ACTUALLY needs
  2. Compresses everything else — only expand what matters for this node
  3. Creates a focused "working set" that the node can process efficiently
  4. Tracks what was compressed so downstream nodes can still access full state

What hallucination it catches:
  "Information overload confusion" — when a node receives 30+ state fields,
  it can get confused and hallucinate connections between unrelated data.
  GSD focuses the node on only what it needs, reducing noise-induced errors.

Relationship to gsd/ module:
  The gsd/ module is the INFRASTRUCTURE that compresses state between nodes
  (12,000→180 tokens). This technique is the BRAIN that decides WHEN and HOW
  to apply compression inside a node's thinking process. They work together:
  gsd/ compresses state passing, GSD technique compresses node attention.

Activation:
  - Medium complexity and above (simple tickets don't need compression)
  - Used in ACTION_PLANNER, ACTION_EXECUTOR, ACTION_VERIFIER for focused work
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.frameworks.gsd")


# What each node needs — focused working sets
_NODE_FOCUS_FIELDS: dict[str, list[str]] = {
    "ACTION_PLANNER": [
        "intent", "reasoning_conclusion", "strategy_plan",
        "integration_data", "kb_results", "complexity",
    ],
    "ACTION_EXECUTOR": [
        "action_plans", "variant", "quality_score", "recommendation",
    ],
    "ACTION_VERIFIER": [
        "execution_results", "recommendation", "action_plans",
    ],
    "RESPONSE_FORMATTER": [
        "intent", "reasoning_conclusion", "execution_results",
        "recommendation", "proactive_insights", "variant",
    ],
}


class GSDTechnique(BaseTechnique):
    """GSD: Get Stuff Done — aggressive focus technique for nodes.

    Instead of a node trying to process all 30+ state fields, GSD
    identifies what the node actually needs and focuses attention
    on the working set. This reduces noise, saves tokens, and
    prevents information-overload hallucinations.
    """

    _min_complexity = "medium"

    @property
    def name(self) -> str:
        return "gsd"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.PROPRIETARY

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "ACTION_PLANNER",
            "ACTION_EXECUTOR",
            "ACTION_VERIFIER",
            "RESPONSE_FORMATTER",
            "REASONING_ENGINE",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 150  # Low — it's about focus, not generation

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute GSD focus technique.

        Identifies the focused working set for the current node,
        compresses attention to relevant fields only.
        """
        # Determine which node we're in (from state or context)
        node_name = self._detect_node(state)

        if MOCK_MODE:
            chain, output, confidence, working_set = self._gsd_mock(
                node_name, state
            )
        else:
            chain, output, confidence, working_set = await self._gsd_llm(
                prompt, node_name, state,
                ticket_id=ticket_id, variant=variant,
            )

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["gsd"],
            metadata={
                "node": node_name,
                "working_set": working_set,
                "total_state_keys": len(state),
                "focus_ratio": len(working_set) / max(len(state), 1),
            },
            token_estimate=self.token_cost_estimate,
        )

    def _detect_node(self, state: dict[str, Any]) -> str:
        """Detect which node is currently running based on state fields.

        GSD is called from within a node, so we can infer which node
        by looking at which output fields are still empty.
        """
        # Check for node-specific state patterns
        if not state.get("action_plans") and state.get("reasoning_conclusion"):
            return "ACTION_PLANNER"
        if state.get("action_plans") and not state.get("execution_results"):
            return "ACTION_EXECUTOR"
        if state.get("execution_results") and not state.get("verification_passed"):
            return "ACTION_VERIFIER"
        if state.get("quality_score") and not state.get("final_response"):
            return "RESPONSE_FORMATTER"
        return "REASONING_ENGINE"

    def _gsd_mock(
        self,
        node_name: str,
        state: dict[str, Any],
    ) -> tuple[list[str], str, float, list[str]]:
        """Mock GSD focus for testing (no LLM calls)."""
        chain = []

        # Step 1: Identify focus fields for this node
        focus_fields = _NODE_FOCUS_FIELDS.get(node_name, ["intent", "raw_message"])
        chain.append(f"GSD: Identifying working set for {node_name}")
        chain.append(f"GSD: Full state has {len(state)} keys")
        chain.append(f"GSD: Focused working set: {focus_fields}")

        # Step 2: Build the working set
        working_set = [f for f in focus_fields if f in state]
        chain.append(f"GSD: {len(working_set)}/{len(focus_fields)} focus fields present in state")

        # Step 3: Report compression
        total_keys = len(state)
        focus_keys = len(working_set)
        ratio = focus_keys / max(total_keys, 1)
        chain.append(f"GSD: Focus ratio = {ratio:.1%} ({focus_keys}/{total_keys} keys)")

        # Step 4: Describe what was compressed away
        compressed_away = [k for k in state if k not in focus_fields]
        if compressed_away:
            chain.append(f"GSD: {len(compressed_away)} fields compressed away: {compressed_away[:5]}{'...' if len(compressed_away) > 5 else ''}")

        output = f"GSD: Node {node_name} focused on {len(working_set)} relevant fields, compressed {len(compressed_away)} irrelevant fields"
        confidence = 0.90

        return chain, output, confidence, working_set

    async def _gsd_llm(
        self,
        prompt: str,
        node_name: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> tuple[list[str], str, float, list[str]]:
        """Real LLM-based GSD focus technique."""
        focus_fields = _NODE_FOCUS_FIELDS.get(node_name, ["intent", "raw_message"])

        # Build state summary for LLM
        state_summary = {}
        for key in focus_fields:
            value = state.get(key)
            if isinstance(value, str):
                state_summary[key] = value[:200]
            elif isinstance(value, (int, float, bool)):
                state_summary[key] = value
            elif isinstance(value, list):
                state_summary[key] = f"[{len(value)} items]"
            elif isinstance(value, dict):
                state_summary[key] = f"{{{len(value)} keys}}"
            elif value is not None:
                state_summary[key] = str(value)[:100]

        system_instructions = (
            "You are a GSD (Get Stuff Done) focus optimizer for customer support.\n\n"
            f"Node: {node_name}\n"
            f"Available state fields: {list(state.keys())}\n"
            f"Default focus fields: {focus_fields}\n"
            f"State summary: {state_summary}\n\n"
            "Determine if the default focus fields are sufficient for this node, "
            "or if additional fields are needed based on the ticket context.\n\n"
            "Output ONLY a JSON list of field names that should be in the working set.\n"
            "Example: [\"intent\", \"reasoning_conclusion\", \"integration_data\"]"
        )

        safe_prompt = build_safe_prompt(system_instructions, prompt)

        try:
            text = await ainvoke_llm(
                safe_prompt,
                node_name="FRAMEWORKBRAIN_GSD",
                ticket_id=ticket_id,
                variant=variant,
            )

            # Parse the response
            working_set = focus_fields  # default
            try:
                import json
                parsed = json.loads(text.strip())
                if isinstance(parsed, list):
                    working_set = [str(f) for f in parsed if f in state]
            except (json.JSONDecodeError, ValueError):
                pass  # Use default focus fields

            chain = [
                f"GSD: LLM-optimized working set for {node_name}",
                f"GSD: Working set: {working_set}",
                f"GSD: Focus ratio: {len(working_set)}/{len(state)} keys",
            ]

            output = f"GSD: Focused {node_name} on {len(working_set)} fields via LLM optimization"
            confidence = 0.88

            return chain, output, confidence, working_set

        except Exception as exc:
            logger.warning("GSD LLM focus failed: %s — using default working set", exc)
            working_set = [f for f in focus_fields if f in state]
            return (
                ["GSD: LLM optimization failed, using default focus fields"],
                "GSD: Using default focus due to LLM error",
                0.50,
                working_set,
            )
