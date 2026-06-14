# Phase 4: Jarvis↔Variant LangGraph Integration Bridge

## Task ID: phase4-jarvis-variant-bridge
## Agent: code-agent
## Date: 2024-03-04

## Summary

Created the Phase 4 Jarvis↔Variant LangGraph Integration bridge that makes Jarvis TRULY multi-agentic by connecting two previously separate LangGraph systems: the Main CC Pipeline (19+ nodes, ParwaGraphState) and the Jarvis Command Graph (7+ nodes, JarvisCommandState).

## Files Created

### 1. `backend/app/services/jarvis_agents/variant_bridge.py`
The BIDIRECTIONAL bridge between Jarvis Command Graph and Main CC Pipeline.

**Key Functions:**
- `inject_jarvis_state_into_pipeline()` — Writes JarvisCommandState fields into ParwaGraphState via Redis
- `read_pipeline_state_for_jarvis()` — Reads ParwaGraphState GROUP 14/15/20 fields from Redis (falls back to DB)
- `sync_awareness_to_pipeline()` — Pushes awareness snapshot into Redis for pipeline consumption
- `get_variant_aware_command_config()` — Returns tier-appropriate command config (mini_parwa: notify_only, parwa: standard, parwa_high: full_autonomy)
- `check_jarvis_approval_needed()` — Determines if a Jarvis action needs human approval based on variant_tier
- `apply_command_to_pipeline_state()` — Writes command execution result back to ParwaGraphState (Redis + DB)

**Redis Key Pattern:** `parwa:{company_id}:jarvis:bridge:{session_id}` (BC-001 compliant)

### 2. `backend/app/services/jarvis_agents/nodes/jarvis_awareness_injector.py`
LangGraph node for the MAIN CC pipeline. Reads Jarvis awareness from the bridge and injects it into ParwaGraphState GROUP 14/15/20 fields.

**Key Behaviors:**
- If `ai_paused=True` → sets `system_mode="paused"` and `proposed_action="escalate"`
- If `emergency_state` is "red_alert" or "full_stop" → sets `urgency="critical"` and `legal_threat_detected=True`
- Injects `co_pilot_suggestion` and `jarvis_feed_entry` from bridge
- Falls back gracefully if Redis unavailable

### 3. `backend/app/services/jarvis_agents/nodes/approval_gate.py`
LangGraph node for human-in-the-loop approval of Jarvis actions. Sits between specialist agents and command executor.

**Approval Rules:**
- mini_parwa: ALL actions need approval (observe mode)
- parwa: Only escalation + monetary actions need approval
- parwa_high: Only emergency actions need approval

**If approval needed:** Sets `execution_status="pending_approval"`, creates approval request in DB
**If auto-approved:** Sets `execution_status="approved"`, passes through to executor

### 4. `backend/app/services/jarvis_agents/nodes/pipeline_query_agent.py`
NEW specialist agent that queries the variant pipeline mid-execution. This is the agent-to-agent communication channel.

**Example Queries:**
- "What's the current quality score?"
- "How many tickets are in the refund queue?"
- "Is the technical agent overloaded?"

Uses ZAI SDK to interpret queries, falls back to rule-based keyword matching.

### 5. `backend/app/services/jarvis_agents/pipeline_feedback.py`
Handles the feedback loop from command execution back to the pipeline. Writes to Redis (real-time) AND DB (durable).

**Feedback Mapping:**
- AI paused → pipeline routes to human
- Quality recovery → pipeline adjusts technique
- SLA protection → pipeline prioritizes at-risk tickets
- Escalation → pipeline knows escalation is in progress

## Files Modified

### 6. `backend/app/services/jarvis_agents/command_graph.py`
- Added `approval_gate` node between specialist agents and command_executor
- Added `pipeline_query_agent` node as new specialist agent
- Added `_approval_selector` conditional edge (routes to executor or END based on approval status)
- Updated graph topology: `START → command_router → specialist → approval_gate → command_executor → END`
- Added Phase 4 feedback loop: after command execution, calls `pipeline_feedback.apply_command_feedback_sync()`
- Updated manual execution path to include approval gate

### 7. `backend/app/services/jarvis_agents/zai_client.py`
- Added `pipeline_query_agent` system prompt
- Added `pipeline_query_agent` rule-based fallback
- Updated `command_router` system prompt to include pipeline_query_agent
- Added pipeline query routing rules to command_router fallback

### 8. `backend/app/services/jarvis_agents/nodes/command_router.py`
- Added `pipeline_query_agent` to valid agents set
- Updated regex agent mapping to route quality/volume/agent/drift queries to pipeline_query_agent

### 9. `backend/app/services/jarvis_agents/nodes/__init__.py`
- Added imports for `approval_gate_node`, `pipeline_query_agent_node`, `jarvis_awareness_injector_node`

### 10. `backend/app/services/jarvis_agents/__init__.py`
- Added Phase 4 bridge and feedback imports
- Updated module docstring to describe Phase 4 architecture

## Architecture Impact

### Before Phase 4
```
Jarvis Awareness Engine → Jarvis Command Graph → command_executor → (disconnected)
Main CC Pipeline → 19 nodes → (no Jarvis awareness mid-execution)
```

### After Phase 4
```
Jarvis Awareness Engine → Jarvis Command Graph → specialist_agent
    → approval_gate → command_executor
        → pipeline_feedback → Redis/DB (writes back)
            → jarvis_awareness_injector (reads in main pipeline)
                → Main CC Pipeline (now sees Jarvis state)

Main CC Pipeline:
    ... → jarvis_awareness_injector_node → router_agent → ...
```

## Compliance
- BC-001: company_id first parameter on all public methods ✓
- BC-008: Every public method wrapped in try/except ✓
- BC-012: All timestamps UTC ✓
- ZAI SDK used for LLM calls (not direct HTTP) ✓
- Uses `from app.logger import get_logger` for logging ✓
- Redis keys follow `parwa:{company_id}:jarvis:*` pattern ✓
