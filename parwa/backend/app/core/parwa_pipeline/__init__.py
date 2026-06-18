"""
PARWA Pipeline V2 — 8-Node Architecture

Replaces the old 19-node + subgraph pipeline with a focused 8-node design.
Techniques are imported from app.core.techniques (built once, called from multiple nodes).

Nodes:
  1. Ingest + Classify  — WHAT is this ticket?
  2. Smart Route        — WHO handles it + WHERE does it go?
  3. Knowledge Fetch    — What do we KNOW about this problem?
  4. Reasoning Engine   — What is the RIGHT answer? (4-layer)
  5. Act + Verify       — Did we DO the right thing?
  6. Quality + Format   — Is this answer GOOD ENOUGH?
  7. Simple/Medium Resolver — Can we solve this WITHOUT LLM?
  8. Super Node         — Can the MOST POWERFUL approach solve this?
"""

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline  # noqa: F401
from app.core.parwa_pipeline.state_v2 import PipelineV2State  # noqa: F401

__all__ = ["build_parwa_pipeline", "PipelineV2State"]