---
Task ID: 1
Agent: Main Agent
Task: Fix all critical Jarvis bugs — unified variant graph, inter-node communication, Jarvis as manager, notification CRM

Work Log:
- Read all 6 LangGraph graphs (main CC pipeline, mini_parwa, parwa, parwa_high, command_graph, orchestrator)
- Read variant bridge, state definitions, edge routing, and node implementations
- Identified core problems: 3 separate variant graphs, nodes not communicating, MAKER without LLM in variants, no auto-fix in Mini, Jarvis not managing
- Created unified variant graph at /home/z/my-project/backend/app/core/unified_variant/ with 29 nodes, permission-driven architecture
- Created permission_config.py with tier-based restrictions (Mini/Pro/High same capability, different restrictions)
- Created Notification CRM system at /home/z/my-project/backend/app/services/notification_crm/
- Created Jarvis Manager at /home/z/my-project/backend/app/services/jarvis_manager/
- Created and ran integration test with complicated ticket
- Fixed async/sync node compatibility issues
- Fixed VariantTier enum lookup issue

Stage Summary:
- **Unified Variant Pipeline**: 29-node graph replaces 3 separate graphs (10+22+27). variant_tier controls permissions, not topology.
- **Inter-node Communication**: Nodes now pass rich context via unified_context + step_outputs. Every node records what it did for downstream nodes.
- **MAKER with LLM**: All tiers now use MAKER validator with LLM (Mini=1, Pro=3, High=5 solutions)
- **Auto-fix in ALL tiers**: Mini now has auto-fix capability
- **Jarvis as Manager**: Monitor watches pipeline, Intervention acts on issues, Notification CRM alerts clients
- **Notification CRM**: Type-based notifications (refund, confusion, ask-client, etc.), similar requests merged into batches, refunds shown first, click→Jarvis chat with full context, knowledge base from resolutions
- **Ask-when-unsure**: Confidence-based mechanism where variants ask clients via Jarvis when confidence is low
- **Refund batching**: Same-type refunds merged, shown to users first in batch

Files Created:
- /home/z/my-project/backend/app/core/unified_variant/__init__.py
- /home/z/my-project/backend/app/core/unified_variant/graph.py (29-node unified graph)
- /home/z/my-project/backend/app/core/unified_variant/permission_config.py (tier restrictions)
- /home/z/my-project/backend/app/services/notification_crm/__init__.py
- /home/z/my-project/backend/app/services/notification_crm/models.py
- /home/z/my-project/backend/app/services/notification_crm/merger.py
- /home/z/my-project/backend/app/services/notification_crm/manager.py
- /home/z/my-project/backend/app/services/notification_crm/knowledge_base.py
- /home/z/my-project/backend/app/services/jarvis_manager/__init__.py
- /home/z/my-project/backend/app/services/jarvis_manager/monitor.py
- /home/z/my-project/backend/app/services/jarvis_manager/intervention.py
- /home/z/my-project/backend/app/services/jarvis_manager/manager.py
- /home/z/my-project/backend/tests/integration_test_complicated_ticket.py
