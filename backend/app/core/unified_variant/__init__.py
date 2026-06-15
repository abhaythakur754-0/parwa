"""
Unified Variant Pipeline — ONE graph, ALL capabilities, tier-based restrictions.

Core Philosophy:
  - Mini, Pro, High have the SAME capability/intelligence
  - The ONLY difference is RESTRICTIONS on what they're allowed to do
  - Mini = 3-4 interns (restricted but smart)
  - Pro = junior employees (moderate restrictions)
  - High = senior employees (minimal restrictions)

This replaces the 3 separate graphs:
  - mini_parwa/graph.py (10 nodes)
  - parwa/graph.py (22 nodes)
  - parwa_high/graph.py (27 nodes)

With ONE unified graph that has ALL 27+ nodes, where variant_tier
controls what each node is ALLOWED to do, not whether it exists.
"""

from app.core.unified_variant.graph import (
    build_unified_variant_graph,
    UnifiedVariantPipeline,
    get_unified_pipeline,
)
from app.core.unified_variant.permissions import (
    get_permission_context,
    get_quality_threshold,
    get_max_quality_retries,
    get_restricted_actions,
)

__all__ = [
    "build_unified_variant_graph",
    "UnifiedVariantPipeline",
    "get_unified_pipeline",
    "get_permission_context",
    "get_quality_threshold",
    "get_max_quality_retries",
    "get_restricted_actions",
]
