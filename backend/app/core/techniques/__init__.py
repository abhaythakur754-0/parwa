"""
AI Techniques Module — Base interfaces and technique implementations.

Each technique is implemented as a LangGraph node within the PARWA
AI pipeline (F-060). The base interface defines the contract all
techniques must follow.

Technique execution order: Tier 1 → Tier 2 → Tier 3 (sequential).

Parent Framework: TRIVYA Optimization Framework (AI Technique Framework v1.0)
"""

from app.core.techniques.base import (  # noqa: F401
    BaseTechniqueNode,
    ConversationState,
    GSDState,
    TECHNIQUE_NODES,
)

# Real technique node implementations (Day 17)
from app.core.techniques.reverse_thinking import ReverseThinkingNode  # noqa: F401
from app.core.techniques.step_back import StepBackNode  # noqa: F401

# Stub nodes — full implementations in their respective weeks
from app.core.techniques.stub_nodes import (  # noqa: F401
    CRPNode,
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
