"""
Unified Variant Engine — One graph, all capabilities, tier-based restrictions.

This package replaces the 3 separate variant graphs (mini_parwa, parwa, parwa_high)
with a SINGLE unified graph where variant_tier controls WHAT ACTIONS are allowed,
not HOW SMART the agent is.

Architecture:
  - tier_permissions.py: Defines what each tier CAN and CANNOT do
  - unified_graph.py: ONE LangGraph with ALL 27 nodes
  - unified_router.py: Single routing logic — all variants go through full pipeline

Philosophy:
  - Mini > 3-4 interns combined
  - Pro > group of junior CC employees
  - High > senior employees
  - All have SAME intelligence, DIFFERENT restrictions

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
"""
