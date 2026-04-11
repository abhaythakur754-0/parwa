"""
Stub technique node implementations.

These are interface stubs with should_activate logic intact.
Full execute() implementations will be built during their
respective Week (8-12) when dependent features are ready.

Real implementations (replacing stubs):
  - CRPNode → app.core.techniques.crp (Day 16)
  - ReverseThinkingNode → app.core.techniques.reverse_thinking (Day 17)
  - StepBackNode → app.core.techniques.step_back (Day 17)
"""

from typing import TYPE_CHECKING

from app.core.technique_router import TechniqueID
from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
    GSDState,
    TECHNIQUE_NODES,
)

if TYPE_CHECKING:
    pass


class CRPNode(BaseTechniqueNode):
    """F-140: Concise Response Protocol — Tier 1 always-active.
    
    Note: CRP processing logic is in app.core.techniques.crp (CRPProcessor).
    This node wraps the CRPProcessor for pipeline integration.
    """

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.CRP

    async def should_activate(self, state: ConversationState) -> bool:
        return True  # Always active

    async def execute(self, state: ConversationState) -> ConversationState:
        from app.core.techniques.crp import CRPProcessor, CRPResult
        try:
            processor = CRPProcessor()
            result: CRPResult = await processor.process(
                state.query or "",
                complexity=state.signals.query_complexity,
            )
            state.technique_results["crp"] = {
                "status": "success",
                "result": result.to_dict(),
                "tokens_used": result.processed_tokens,
            }
            state.token_usage += result.processed_tokens
            if result.processed_text and not state.final_response:
                state.response_parts.append(result.processed_text)
        except Exception as exc:
            state.technique_results["crp"] = {
                "status": "error",
                "error": str(exc),
            }
        return state


class ReverseThinkingNodePlaceholder(BaseTechniqueNode):
    """Placeholder — real ReverseThinkingNode is in app.core.techniques.reverse_thinking"""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.REVERSE_THINKING

    async def should_activate(self, state: ConversationState) -> bool:
        from app.core.techniques.reverse_thinking import ReverseThinkingNode
        return await ReverseThinkingNode().should_activate(state)

    async def execute(self, state: ConversationState) -> ConversationState:
        from app.core.techniques.reverse_thinking import ReverseThinkingNode
        return await ReverseThinkingNode().execute(state)


class StepBackNodePlaceholder(BaseTechniqueNode):
    """Placeholder — real StepBackNode is in app.core.techniques.step_back"""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.STEP_BACK

    async def should_activate(self, state: ConversationState) -> bool:
        from app.core.techniques.step_back import StepBackNode
        return await StepBackNode().should_activate(state)

    async def execute(self, state: ConversationState) -> ConversationState:
        from app.core.techniques.step_back import StepBackNode
        return await StepBackNode().execute(state)


class ChainOfThoughtNode(BaseTechniqueNode):
    """Chain of Thought — Tier 2 conditional."""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.CHAIN_OF_THOUGHT

    async def should_activate(self, state: ConversationState) -> bool:
        return state.signals.query_complexity > 0.4

    async def execute(self, state: ConversationState) -> ConversationState:
        # TODO: Implement decomposition, step-by-step reasoning, synthesis
        # Week 8-9 implementation
        state.technique_results["chain_of_thought"] = {
            "status": "stub",
            "message": "CoT stub — full implementation in Week 8-9",
        }
        return state


class ReActNode(BaseTechniqueNode):
    """ReAct (Reasoning + Acting) — Tier 2 conditional."""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.REACT

    async def should_activate(self, state: ConversationState) -> bool:
        return state.signals.external_data_required

    async def execute(self, state: ConversationState) -> ConversationState:
        # TODO: Implement thought-action-observation loop
        # Week 9 implementation
        state.technique_results["react"] = {
            "status": "stub",
            "message": "ReAct stub — full implementation in Week 9",
        }
        return state


class ThreadOfThoughtNode(BaseTechniqueNode):
    """ThoT (Thread of Thought) — Tier 2 conditional."""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.THREAD_OF_THOUGHT

    async def should_activate(self, state: ConversationState) -> bool:
        return state.signals.turn_count > 5

    async def execute(self, state: ConversationState) -> ConversationState:
        # TODO: Implement thread extraction, continuity check
        # Week 10 implementation
        state.technique_results["thread_of_thought"] = {
            "status": "stub",
            "message": "ThoT stub — full implementation in Week 10",
        }
        return state


class GSTNode(BaseTechniqueNode):
    """F-143: GST (Guided Sequential Thinking) — Tier 3 premium."""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.GST

    async def should_activate(self, state: ConversationState) -> bool:
        return state.signals.is_strategic_decision

    async def execute(self, state: ConversationState) -> ConversationState:
        # TODO: Implement 5-checkpoint guided analysis
        # Week 18-19 (Phase 3) implementation
        state.technique_results["gst"] = {
            "status": "stub",
            "message": "GST stub — full implementation in Week 18-19",
        }
        return state


class UniverseOfThoughtsNode(BaseTechniqueNode):
    """F-144: UoT (Universe of Thoughts) — Tier 3 premium."""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.UNIVERSE_OF_THOUGHTS

    async def should_activate(self, state: ConversationState) -> bool:
        return (
            state.signals.customer_tier == "vip"
            or state.signals.sentiment_score < 0.3
            or state.signals.monetary_value > 100
        )

    async def execute(self, state: ConversationState) -> ConversationState:
        # TODO: Implement solution space generation, evaluation matrix
        # Week 13-14 (Phase 2) implementation
        state.technique_results["universe_of_thoughts"] = {
            "status": "stub",
            "message": "UoT stub — full implementation in Week 13-14",
        }
        return state


class TreeOfThoughtsNode(BaseTechniqueNode):
    """F-145: ToT (Tree of Thoughts) — Tier 3 premium."""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.TREE_OF_THOUGHTS

    async def should_activate(self, state: ConversationState) -> bool:
        return state.signals.resolution_path_count >= 3

    async def execute(self, state: ConversationState) -> ConversationState:
        # TODO: Implement tree generation, branch evaluation, pruning
        # Week 18-19 (Phase 3) implementation
        state.technique_results["tree_of_thoughts"] = {
            "status": "stub",
            "message": "ToT stub — full implementation in Week 18-19",
        }
        return state


class SelfConsistencyNode(BaseTechniqueNode):
    """F-146: Self-Consistency — Tier 3 premium."""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.SELF_CONSISTENCY

    async def should_activate(self, state: ConversationState) -> bool:
        return (
            state.signals.monetary_value > 100
            or state.signals.intent_type == "billing"
        )

    async def execute(self, state: ConversationState) -> ConversationState:
        # TODO: Implement multi-answer generation, consistency check
        # Week 13-14 (Phase 2) implementation
        state.technique_results["self_consistency"] = {
            "status": "stub",
            "message": "Self-Consistency stub — full implementation in Week 13-14",
        }
        return state


class ReflexionNode(BaseTechniqueNode):
    """F-147: Reflexion — Tier 3 premium."""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.REFLEXION

    async def should_activate(self, state: ConversationState) -> bool:
        return (
            state.signals.previous_response_status in ("rejected", "corrected")
            or state.signals.customer_tier == "vip"
        )

    async def execute(self, state: ConversationState) -> ConversationState:
        # TODO: Implement self-reflection, strategy adjustment
        # Week 13-14 (Phase 2) implementation
        state.technique_results["reflexion"] = {
            "status": "stub",
            "message": "Reflexion stub — full implementation in Week 13-14",
        }
        return state


class LeastToMostNode(BaseTechniqueNode):
    """F-148: Least-to-Most Decomposition — Tier 3 premium."""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.LEAST_TO_MOST

    async def should_activate(self, state: ConversationState) -> bool:
        return state.signals.query_complexity > 0.7

    async def execute(self, state: ConversationState) -> ConversationState:
        # TODO: Implement decomposition, dependency ordering, sequential solving
        # Week 18-19 (Phase 3) implementation
        state.technique_results["least_to_most"] = {
            "status": "stub",
            "message": "Least-to-Most stub — full implementation in Week 18-19",
        }
        return state


# ── Populate the node registry ────────────────────────────────────
# Real implementations (Day 16-17) are imported directly.
# Stubs remain for techniques not yet implemented.

TECHNIQUE_NODES.update({
    TechniqueID.CRP: CRPNode(),
    TechniqueID.REVERSE_THINKING: ReverseThinkingNodePlaceholder(),
    TechniqueID.STEP_BACK: StepBackNodePlaceholder(),
    TechniqueID.CHAIN_OF_THOUGHT: ChainOfThoughtNode(),
    TechniqueID.REACT: ReActNode(),
    TechniqueID.THREAD_OF_THOUGHT: ThreadOfThoughtNode(),
    TechniqueID.GST: GSTNode(),
    TechniqueID.UNIVERSE_OF_THOUGHTS: UniverseOfThoughtsNode(),
    TechniqueID.TREE_OF_THOUGHTS: TreeOfThoughtsNode(),
    TechniqueID.SELF_CONSISTENCY: SelfConsistencyNode(),
    TechniqueID.REFLEXION: ReflexionNode(),
    TechniqueID.LEAST_TO_MOST: LeastToMostNode(),
})
