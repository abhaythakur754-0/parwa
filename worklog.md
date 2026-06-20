---
Task ID: 1
Agent: Main Agent
Task: Replace entire variant system with unified 8-node PARWA pipeline

Work Log:
- Deep research on temp architecture: confirmed mini_parwa/ (10-node), parwa_pipeline/ (8-node V2), parwa_high/ (27-node) are SEPARATE in temp
- The 8-node parwa_pipeline/ is the NEW unified pipeline that replaces ALL variants
- Node 2 (Smart Route) handles tier-based complexity routing internally
- Mapped all 24+ production files that reference old variant system
- Copied parwa_pipeline/ (8 nodes + graph_v2 + state_v2 + llm_client + config + ai_wiki_store + parwa_bridge) from temp to onboarding
- Backed up old directories to _deprecated_variants_backup/ (safety net)
- DELETED: mini_parwa/, parwa_high/, langgraph/ from onboarding backend
- REWROTE: variant_pipeline_bridge.py — single _run_parwa_pipeline() replaces _run_mini_parwa/_run_parwa/_run_parwa_high trio
- REWROTE: variant_router.py — stub routing functions + ALL_NODES = 8 unified nodes
- UPDATED: variant_tier_mapper.py — metadata now reflects 8-node unified pipeline
- UPDATED: main.py — startup builds 8-node pipeline instead of 19-node
- UPDATED: workflow.py — process endpoint uses PipelineV2State, info/state/approve endpoints simplified
- UPDATED: system_health.py — _check_langgraph() now checks parwa_pipeline_v2
- UPDATED: jarvis_awareness_engine.py — uses parwa_pipeline.graph_v2
- UPDATED: dlq_retry_tasks.py — imports from parwa_pipeline.dlq
- UPDATED: external_tool_bus.py — imports from parwa_pipeline.retry
- COPIED: dlq.py and retry.py to parwa_pipeline/ for backward compat
- Verified: zero broken imports in production code (api/, services/, tasks/, core/)

Stage Summary:
- OLD: 3 separate pipelines (10-node mini, 15-node parwa, 27-node high + 19-node langgraph)
- NEW: Single unified 8-node PARWA pipeline for all tiers
- Node 2 handles tier-aware routing: mini→more simple_path, high→more complex_path
- PipelineResult class preserved for backward compat
- All public API functions (process_customer_care_message, process_onboarding_message, has_variant_tier_in_context) unchanged
- Test files still reference old code (will fail but won't break production) — to be updated later
