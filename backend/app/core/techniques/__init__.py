"""
AI Techniques Module — Base interfaces and technique implementations.

Each technique is implemented as a LangGraph node within the PARWA
AI pipeline (F-060). The base interface defines the contract all
techniques must follow.

Technique execution order: Tier 1 → Tier 2 → Tier 3 (sequential).

Parent Framework: TRIVYA Optimization Framework (AI Technique Framework v1.0)
"""

from backend.app.core.techniques.base import (  # noqa: F401
    BaseTechniqueNode,
    ConversationState,
    GSDState,
    TECHNIQUE_NODES,
)

# Stub nodes — full implementations in their respective weeks
from backend.app.core.techniques.stub_nodes import (  # noqa: F401
    CRPNode,
    ReverseThinkingNode,
    StepBackNode,
    ChainOfThoughtNode,
    ReActNode,
    ThreadOfThoughtNode,
    GSTNode,
    UniverseOfThoughtsNode,
    TreeOfThoughtsNode,
    SelfConsistencyNode,
    ReflexionNode,
    LeastToMostNode,
)
