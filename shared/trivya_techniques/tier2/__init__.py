"""
PARWA TRIVYA Tier 2 Techniques.

Tier 2 techniques are conditional advanced reasoning methods that fire
only when the query complexity or type requires deeper analysis.

T2 Techniques:
- trigger_detector: Determines which T2 techniques to apply
- chain_of_thought: Step-by-step reasoning for complex problems
- react: Reason + Act loop for tool-using scenarios
- reverse_thinking: Work backward from goal to solution
- step_back: Abstract the problem before solving
- thread_of_thought: Structured exploration of topics
"""

from shared.trivya_techniques.tier2.trigger_detector import (
    TriggerDetector,
    TriggerResult,
    TriggerType,
)
from shared.trivya_techniques.tier2.chain_of_thought import (
    ChainOfThought,
    CoTResult,
    CoTConfig,
)
from shared.trivya_techniques.tier2.react import (
    ReActTechnique,
    ReActResult,
    ReActConfig,
)
from shared.trivya_techniques.tier2.reverse_thinking import (
    ReverseThinking,
    ReverseThinkingResult,
    ReverseThinkingConfig,
)
from shared.trivya_techniques.tier2.step_back import (
    StepBack,
    StepBackResult,
    StepBackConfig,
)
from shared.trivya_techniques.tier2.thread_of_thought import (
    ThreadOfThought,
    ToTResult,
    ToTConfig,
)

__all__ = [
    # Trigger Detector
    "TriggerDetector",
    "TriggerResult",
    "TriggerType",
    # Chain of Thought
    "ChainOfThought",
    "CoTResult",
    "CoTConfig",
    # ReAct
    "ReActTechnique",
    "ReActResult",
    "ReActConfig",
    # Reverse Thinking
    "ReverseThinking",
    "ReverseThinkingResult",
    "ReverseThinkingConfig",
    # Step Back
    "StepBack",
    "StepBackResult",
    "StepBackConfig",
    # Thread of Thought
    "ThreadOfThought",
    "ToTResult",
    "ToTConfig",
]
