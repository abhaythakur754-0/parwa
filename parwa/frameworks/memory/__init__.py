"""Memory techniques for PARWA.

Phase 4 implements 3 memory techniques:
  - ThoT: Thread of Thought — continuous reasoning thread across nodes
  - Dynamic Context: Dynamically adjust context window based on complexity/budget
  - Contextual Compression: Compress retrieved docs before feeding to LLM
"""

from parwa.frameworks.memory.thot import ThreadOfThoughtTechnique
from parwa.frameworks.memory.dynamic_context import DynamicContextTechnique
from parwa.frameworks.memory.contextual_compression import ContextualCompressionTechnique

__all__ = [
    "ThreadOfThoughtTechnique",
    "DynamicContextTechnique",
    "ContextualCompressionTechnique",
]
