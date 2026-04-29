"""
Technique node registry and placeholder delegates.

Real implementations are in their own modules:
  - CRPNode → app.core.techniques.crp (Day 16)
  - ReverseThinkingNode → app.core.techniques.reverse_thinking (Day 17)
  - StepBackNode → app.core.techniques.step_back (Day 17)
  - ChainOfThoughtNode → app.core.techniques.chain_of_thought (Day 18)
  - ReActNode → app.core.techniques.react (Day 18)
  - ThreadOfThoughtNode → app.core.techniques.thread_of_thought (Day 18)
  - GSTNode → app.core.techniques.gst (Day 18)
  - UniverseOfThoughtsNode → app.core.techniques.universe_of_thoughts (Day 19)
  - TreeOfThoughtsNode → app.core.techniques.tree_of_thoughts (Day 19)
  - SelfConsistencyNode → app.core.techniques.self_consistency (Day 19)
  - ReflexionNode → app.core.techniques.reflexion (Day 19)
  - LeastToMostNode → app.core.techniques.least_to_most (Day 19)
"""

from typing import TYPE_CHECKING

from app.core.technique_router import TechniqueID
from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
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


class ChainOfThoughtNodePlaceholder(BaseTechniqueNode):
    """Placeholder — real ChainOfThoughtNode is in app.core.techniques.chain_of_thought"""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.CHAIN_OF_THOUGHT

    async def should_activate(self, state: ConversationState) -> bool:
        from app.core.techniques.chain_of_thought import ChainOfThoughtNode

        return await ChainOfThoughtNode().should_activate(state)

    async def execute(self, state: ConversationState) -> ConversationState:
        from app.core.techniques.chain_of_thought import ChainOfThoughtNode

        return await ChainOfThoughtNode().execute(state)


class ReActNodePlaceholder(BaseTechniqueNode):
    """Placeholder — real ReActNode is in app.core.techniques.react"""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.REACT

    async def should_activate(self, state: ConversationState) -> bool:
        from app.core.techniques.react import ReActNode

        return await ReActNode().should_activate(state)

    async def execute(self, state: ConversationState) -> ConversationState:
        from app.core.techniques.react import ReActNode

        return await ReActNode().execute(state)


class ThreadOfThoughtNodePlaceholder(BaseTechniqueNode):
    """Placeholder — real ThreadOfThoughtNode is in app.core.techniques.thread_of_thought"""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.THREAD_OF_THOUGHT

    async def should_activate(self, state: ConversationState) -> bool:
        from app.core.techniques.thread_of_thought import ThreadOfThoughtNode

        return await ThreadOfThoughtNode().should_activate(state)

    async def execute(self, state: ConversationState) -> ConversationState:
        from app.core.techniques.thread_of_thought import ThreadOfThoughtNode

        return await ThreadOfThoughtNode().execute(state)


class GSTNodePlaceholder(BaseTechniqueNode):
    """Placeholder — real GSTNode is in app.core.techniques.gst"""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.GST

    async def should_activate(self, state: ConversationState) -> bool:
        from app.core.techniques.gst import GSTNode

        return await GSTNode().should_activate(state)

    async def execute(self, state: ConversationState) -> ConversationState:
        from app.core.techniques.gst import GSTNode

        return await GSTNode().execute(state)


class UniverseOfThoughtsNodePlaceholder(BaseTechniqueNode):
    """Placeholder — real UniverseOfThoughtsNode is in app.core.techniques.universe_of_thoughts"""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.UNIVERSE_OF_THOUGHTS

    async def should_activate(self, state: ConversationState) -> bool:
        from app.core.techniques.universe_of_thoughts import UniverseOfThoughtsNode

        return await UniverseOfThoughtsNode().should_activate(state)

    async def execute(self, state: ConversationState) -> ConversationState:
        from app.core.techniques.universe_of_thoughts import UniverseOfThoughtsNode

        return await UniverseOfThoughtsNode().execute(state)


class TreeOfThoughtsNodePlaceholder(BaseTechniqueNode):
    """Placeholder — real TreeOfThoughtsNode is in app.core.techniques.tree_of_thoughts"""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.TREE_OF_THOUGHTS

    async def should_activate(self, state: ConversationState) -> bool:
        from app.core.techniques.tree_of_thoughts import TreeOfThoughtsNode

        return await TreeOfThoughtsNode().should_activate(state)

    async def execute(self, state: ConversationState) -> ConversationState:
        from app.core.techniques.tree_of_thoughts import TreeOfThoughtsNode

        return await TreeOfThoughtsNode().execute(state)


class SelfConsistencyNodePlaceholder(BaseTechniqueNode):
    """Placeholder — real SelfConsistencyNode is in app.core.techniques.self_consistency"""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.SELF_CONSISTENCY

    async def should_activate(self, state: ConversationState) -> bool:
        from app.core.techniques.self_consistency import SelfConsistencyNode

        return await SelfConsistencyNode().should_activate(state)

    async def execute(self, state: ConversationState) -> ConversationState:
        from app.core.techniques.self_consistency import SelfConsistencyNode

        return await SelfConsistencyNode().execute(state)


class ReflexionNodePlaceholder(BaseTechniqueNode):
    """Placeholder — real ReflexionNode is in app.core.techniques.reflexion"""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.REFLEXION

    async def should_activate(self, state: ConversationState) -> bool:
        from app.core.techniques.reflexion import ReflexionNode

        return await ReflexionNode().should_activate(state)

    async def execute(self, state: ConversationState) -> ConversationState:
        from app.core.techniques.reflexion import ReflexionNode

        return await ReflexionNode().execute(state)


class LeastToMostNodePlaceholder(BaseTechniqueNode):
    """Placeholder — real LeastToMostNode is in app.core.techniques.least_to_most"""

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.LEAST_TO_MOST

    async def should_activate(self, state: ConversationState) -> bool:
        from app.core.techniques.least_to_most import LeastToMostNode

        return await LeastToMostNode().should_activate(state)

    async def execute(self, state: ConversationState) -> ConversationState:
        from app.core.techniques.least_to_most import LeastToMostNode

        return await LeastToMostNode().execute(state)


# ── Populate the node registry ────────────────────────────────────
# All implementations are real (no stubs remaining).
# Day 19: UoT, ToT, Self-Consistency, Reflexion, Least-to-Most.

TECHNIQUE_NODES.update(
    {
        TechniqueID.CRP: CRPNode(),
        TechniqueID.REVERSE_THINKING: ReverseThinkingNodePlaceholder(),
        TechniqueID.STEP_BACK: StepBackNodePlaceholder(),
        TechniqueID.CHAIN_OF_THOUGHT: ChainOfThoughtNodePlaceholder(),
        TechniqueID.REACT: ReActNodePlaceholder(),
        TechniqueID.THREAD_OF_THOUGHT: ThreadOfThoughtNodePlaceholder(),
        TechniqueID.GST: GSTNodePlaceholder(),
        TechniqueID.UNIVERSE_OF_THOUGHTS: UniverseOfThoughtsNodePlaceholder(),
        TechniqueID.TREE_OF_THOUGHTS: TreeOfThoughtsNodePlaceholder(),
        TechniqueID.SELF_CONSISTENCY: SelfConsistencyNodePlaceholder(),
        TechniqueID.REFLEXION: ReflexionNodePlaceholder(),
        TechniqueID.LEAST_TO_MOST: LeastToMostNodePlaceholder(),
    }
)
