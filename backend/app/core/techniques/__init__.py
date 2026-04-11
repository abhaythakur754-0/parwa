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

# Real technique node implementations (Day 16-17)
from app.core.techniques.reverse_thinking import ReverseThinkingNode  # noqa: F401
from app.core.techniques.step_back import StepBackNode  # noqa: F401

# Real technique node implementations (Day 18)
from app.core.techniques.chain_of_thought import ChainOfThoughtNode  # noqa: F401
from app.core.techniques.react import ReActNode  # noqa: F401
from app.core.techniques.thread_of_thought import ThreadOfThoughtNode  # noqa: F401
from app.core.techniques.gst import GSTNode  # noqa: F401

# Real technique node implementations (Day 19)
from app.core.techniques.universe_of_thoughts import (  # noqa: F401
    UniverseOfThoughtsNode,
    UoTProcessor,
)
from app.core.techniques.self_consistency import (  # noqa: F401
    SelfConsistencyNode,
    SelfConsistencyProcessor,
)
from app.core.techniques.reflexion import (  # noqa: F401
    ReflexionNode,
    ReflexionProcessor,
)
from app.core.techniques.tree_of_thoughts import (  # noqa: F401
    TreeOfThoughtsNode,
    ToTProcessor,
)
from app.core.techniques.least_to_most import (  # noqa: F401
    LeastToMostNode,
    LeastToMostProcessor,
)

# Stub nodes — placeholder delegates and CRPNode
from app.core.techniques.stub_nodes import (  # noqa: F401
    CRPNode,
    ReverseThinkingNodePlaceholder,
    StepBackNodePlaceholder,
    ChainOfThoughtNodePlaceholder,
    ReActNodePlaceholder,
    ThreadOfThoughtNodePlaceholder,
    GSTNodePlaceholder,
    UniverseOfThoughtsNodePlaceholder,
    TreeOfThoughtsNodePlaceholder,
    SelfConsistencyNodePlaceholder,
    ReflexionNodePlaceholder,
    LeastToMostNodePlaceholder,
)
