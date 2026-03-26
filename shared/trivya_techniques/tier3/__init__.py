"""
PARWA TRIVYA Tier 3 Techniques.

Advanced reasoning techniques for high-stakes scenarios.
T3 only activates when: VIP customer + transaction > $100 + anger > 80%

Available Techniques:
- TriggerDetector: Detects when T3 should fire
- GST (Generated Step-by-step Thought): Structured reasoning
- UniverseOfThoughts: Multiple solution path exploration
- TreeOfThoughts: Tree-structured reasoning
- SelfConsistency: Majority voting across paths
- Reflexion: Self-improvement through reflection
- LeastToMost: Complex query decomposition
"""
from shared.trivya_techniques.tier3.trigger_detector import (
    T3TriggerDetector,
    T3TriggerConfig,
    T3TriggerResult,
    T3TriggerType,
    HighStakesIndicator,
)
from shared.trivya_techniques.tier3.gst import (
    GeneratedStepByStepThought,
    GSTConfig,
    GSTResult,
    ThoughtStep,
    StepStatus,
)
from shared.trivya_techniques.tier3.universe_of_thoughts import (
    UniverseOfThoughts,
    UniverseConfig,
    UniverseResult,
    ThoughtPath,
    PathType,
    PathStatus,
)
from shared.trivya_techniques.tier3.tree_of_thoughts import (
    TreeOfThoughts,
    TreeConfig,
    TreeResult,
    ThoughtNode,
    NodeStatus,
    SearchStrategy,
)
from shared.trivya_techniques.tier3.self_consistency import (
    SelfConsistency,
    SelfConsistencyConfig,
    ConsensusResult,
    ReasoningChain,
    VoteStrategy,
)
from shared.trivya_techniques.tier3.reflexion import (
    Reflexion,
    ReflexionConfig,
    ReflexionResult,
    ReflectionIteration,
    ReflectionStatus,
)
from shared.trivya_techniques.tier3.least_to_most import (
    LeastToMost,
    LeastToMostConfig,
    LeastToMostResult,
    SubQuestion,
    SubQuestionStatus,
    Difficulty,
)


__all__ = [
    # Trigger Detector
    "T3TriggerDetector",
    "T3TriggerConfig",
    "T3TriggerResult",
    "T3TriggerType",
    "HighStakesIndicator",
    # GST
    "GeneratedStepByStepThought",
    "GSTConfig",
    "GSTResult",
    "ThoughtStep",
    "StepStatus",
    # Universe of Thoughts
    "UniverseOfThoughts",
    "UniverseConfig",
    "UniverseResult",
    "ThoughtPath",
    "PathType",
    "PathStatus",
    # Tree of Thoughts
    "TreeOfThoughts",
    "TreeConfig",
    "TreeResult",
    "ThoughtNode",
    "NodeStatus",
    "SearchStrategy",
    # Self Consistency
    "SelfConsistency",
    "SelfConsistencyConfig",
    "ConsensusResult",
    "ReasoningChain",
    "VoteStrategy",
    # Reflexion
    "Reflexion",
    "ReflexionConfig",
    "ReflexionResult",
    "ReflectionIteration",
    "ReflectionStatus",
    # Least to Most
    "LeastToMost",
    "LeastToMostConfig",
    "LeastToMostResult",
    "SubQuestion",
    "SubQuestionStatus",
    "Difficulty",
]
