"""
Unified Variant Pipeline — ONE graph, ALL tiers.

This replaces the three separate variant graphs (mini_parwa, parwa, parwa_high)
with a SINGLE unified LangGraph where `variant_tier` controls what each node
is ALLOWED to do, not whether the node exists.

Core Philosophy:
  - SAME capability/intelligence across all tiers
  - DIFFERENT restrictions on what actions are permitted
  - Mini ≈ 3-4 interns (can observe, suggest, needs approval)
  - Pro  ≈ junior CC employees (can act on routine, escalate complex)
  - High ≈ senior employees (can act on most things, escalate edge cases)

All 27 nodes exist in ONE graph. The tier controls:
  - Which deep enrichment agents run
  - Quality retry limits (0/1/2)
  - Whether DSPy optimization runs
  - Whether auto-fix/auto-action is allowed
  - Whether strategic_decision + peer_review run
  - Channel availability
  - Approval requirements

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from app.core.unified_variant.graph import (
    build_unified_variant_graph,
    UnifiedVariantPipeline,
    get_unified_pipeline,
)
from app.core.unified_variant.permission_config import (
    VariantTier,
    PermissionConfig,
    get_permission_config,
)

__all__ = [
    "build_unified_variant_graph",
    "UnifiedVariantPipeline",
    "get_unified_pipeline",
    "VariantTier",
    "PermissionConfig",
    "get_permission_config",
]
