"""RAG (Retrieval-Augmented Generation) techniques for PARWA.

Phase 3 implements 4 RAG techniques:
  - CLARA: Confidence-driven retrieval with clarifying questions
  - HyDE: Hypothetical Document Embedding for better KB matching
  - Multi-Query: Multiple query variations merged for better coverage
  - Step-Back: Broader concept search applied to specific cases
"""

from parwa.frameworks.rag.clara import ClaraTechnique
from parwa.frameworks.rag.hyde import HyDETechnique
from parwa.frameworks.rag.multi_query import MultiQueryTechnique
from parwa.frameworks.rag.step_back import StepBackTechnique

__all__ = [
    "ClaraTechnique",
    "HyDETechnique",
    "MultiQueryTechnique",
    "StepBackTechnique",
]
