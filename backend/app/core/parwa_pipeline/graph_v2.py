"""
PARWA Pipeline V2 — Graph Definition (Phase 7: In-Graph Wiki Write-Back)

Wires all 8 nodes with LangGraph StateGraph.
Phase 7: Wiki write-back INSIDE the graph for both paths.

Flow:
  Node 1 (Ingest+Classify) → Node 2 (Smart Route)
    ├── simple_path  → Node 3 (Knowledge) → Node 7 (Simple Resolver)
    │                     ├── PASS → finalize_simple (wiki write) → END
    │                     └── auto_upgraded → Node 4 (Reasoning) path
    └── complex_path → Node 3 (Knowledge) → Node 4 (Reasoning)
                                                  → Node 5 (Act+Verify)
                                                  → Node 6 (Quality)
                                                    ├── PASS → wiki_finalize (wiki write) → END
                                                    ├── FAIL + loops < 2 → Node 4 (loop)
                                                    └── FAIL + loops >= 2 → Node 8 (Super Node)
                                                                          → END
"""

from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from app.core.parwa_pipeline.config import (
    MAX_QUALITY_LOOPS,
    PATH_COMPLEX,
    PATH_SIMPLE,
    QUALITY_LOOP_THRESHOLD,
    QUALITY_PASS_THRESHOLD,
)
from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify
from app.core.parwa_pipeline.nodes.node_2_smart_route import node_2_smart_route
from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import node_3_knowledge_fetch
from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import node_4_reasoning_engine
from app.core.parwa_pipeline.nodes.node_5_act_verify import node_5_act_verify
from app.core.parwa_pipeline.nodes.node_6_quality_format import node_6_quality_format
from app.core.parwa_pipeline.nodes.node_7_simple_resolver import node_7_simple_resolver
from app.core.parwa_pipeline.nodes.node_8_super_node import node_8_super_node
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.graph_v2")


# ── Edge Functions ────────────────────────────────────────────────


def _route_after_node_1(state: PipelineV2State) -> Literal["node_2", "__end__"]:
    """After Node 1: if rejected (shutdown) or paused, end early."""
    status = state.get("status", "")
    if status in ("rejected", "paused"):
        logger.info("Node 1 early exit: status=%s", status)
        return "__end__"
    return "node_2"


def _route_after_node_2(state: PipelineV2State) -> Literal["node_3", "__end__"]:
    """After Node 2: if paused/escalated by Jarvis flags, end early. Otherwise → Node 3."""
    status = state.get("status", "")
    if status in ("paused", "escalated"):
        logger.info("Node 2 early exit: status=%s", status)
        return "__end__"
    return "node_3"


def _route_after_node_3(state: PipelineV2State) -> Literal["node_7", "node_4"]:
    """After Node 3: simple path → Node 7, complex path → Node 4."""
    path = state.get("route_decision", state.get("current_path", "simple_path"))
    if path == "simple_path":
        return "node_7"
    return "node_4"


def _route_after_node_7(state: PipelineV2State) -> Literal["node_4", "__end__"]:
    """After Node 7: safety net check."""
    if state.get("auto_upgraded", False):
        logger.info("Node 7 safety net triggered → upgrading to Node 4 (complex path)")
        return "node_4"
    # Simple resolver passed — use its answer
    return "__end__"


def _route_after_node_6(state: PipelineV2State) -> Literal["node_4", "node_8", "wiki_finalize"]:
    """After Node 6: quality gate decision.

    Phase 7: PASS now goes to wiki_finalize (in-graph wiki write-back)
    instead of directly to __end__.

    PASS (quality >= 90%) → wiki_finalize → END (resolved)
    FAIL + loops < MAX → Node 4 (retry)
    FAIL + loops >= MAX → Node 8 (Super Node)
    """
    quality = state.get("quality_score", 0.0)
    loop_count = state.get("loop_count", 0)

    if quality >= QUALITY_PASS_THRESHOLD:
        logger.info(
            "Quality PASSED: score=%.4f >= %.2f → wiki_finalize",
            quality, QUALITY_PASS_THRESHOLD,
        )
        return "wiki_finalize"

    if loop_count < MAX_QUALITY_LOOPS:
        logger.info(
            "Quality FAILED: score=%.4f, loop=%d/%d → back to Node 4",
            quality, loop_count + 1, MAX_QUALITY_LOOPS,
        )
        return "node_4"

    logger.info(
        "Quality FAILED after %d loops: score=%.4f → Node 8 (Super Node)",
        MAX_QUALITY_LOOPS, quality,
    )
    return "node_8"


def _route_after_node_8(state: PipelineV2State) -> Literal["__end__"]:
    """After Node 8: always end (either resolved or escalated)."""
    return "__end__"


# ── State Updater for Quality Loop ─────────────────────────────────


def _increment_loop(state: PipelineV2State) -> dict:
    """Increment loop counter when looping back to Node 4."""
    return {"loop_count": state.get("loop_count", 0) + 1}




# ── Wave 4: Load Jarvis flags at graph entry ────────────────

async def _load_jarvis_flags(state: PipelineV2State) -> dict:
    """Load all active Jarvis system flags into state.

    Called as the first node in the graph so all subsequent nodes
    have access to the flags without individual DB calls.
    """
    from app.core.parwa_pipeline.parwa_bridge import load_system_flags

    tenant_id = state.get("tenant_id", "")
    flags = await load_system_flags(tenant_id)

    return {
        "system_flags": flags,
        "technique_log": [{"node": 0, "technique": "JARVIS_FLAG_LOAD", "duration_ms": 0,
                           "result_summary": f"flags={len(flags.get('all_flags', []))} shutdown={flags.get('global_shutdown')}"}],
    }

def _finalize_simple(state: PipelineV2State) -> dict:
    """Set final response from simple resolver + wiki write-back + CRM push-back."""
    _wiki_write_on_resolve(state, techniques=["Node7_SimpleResolver", "GSD", "MAKER", "FederatedReasoning"])
    _crm_push_on_resolve(state, response=state.get("simple_answer", ""))
    return {
        "final_response": state.get("simple_answer", ""),
        "status": "resolved",
        "formatted_response": state.get("simple_answer", ""),
        "quality_passed": True,
    }


def _wiki_finalize_complex(state: PipelineV2State) -> dict:
    """Phase 7: Wiki write-back for complex path + set final response + CRM push-back.

    This node is called AFTER Node 6 quality passes on the complex path.
    Previously wiki write-back was only in run_parwa_pipeline() wrapper,
    which tests bypassed via compiled.ainvoke().
    """
    _wiki_write_on_resolve(state)
    response = state.get("formatted_response", "") or state.get("combined_answer", "")
    _crm_push_on_resolve(state, response=response)
    return {
        "final_response": response,
        "status": "resolved",
    }


def _crm_push_on_resolve(state: PipelineV2State, response: str = "") -> None:
    """Push resolved response back to CRM if a CRM ticket exists.

    Non-blocking. Failures are silently logged — never breaks the pipeline.
    Called from both _finalize_simple and _wiki_finalize_complex.
    """
    try:
        metadata = state.get("metadata", {})
        crm_ticket_id = metadata.get("crm_ticket_id", "")
        crm_provider = metadata.get("crm_provider", "")

        if not crm_ticket_id or not crm_provider:
            return  # No CRM ticket — nothing to push

        from app.core.crm_bridge.crm_bridge import CRMBridge

        quality = state.get("quality_score", 0.0)
        if state.get("simple_confidence"):
            quality = max(quality, state["simple_confidence"])
        if state.get("super_node_quality"):
            quality = max(quality, state["super_node_quality"])

        # Build internal note with AI classification
        internal_note = (
            f"Ticket Type: {state.get('ticket_type', 'unknown')} | "
            f"Complexity: {state.get('complexity', 'unknown')} | "
            f"Path: {state.get('route_decision', state.get('current_path', '?'))} | "
            f"Quality: {quality:.2f} | "
            f"Techniques: {', '.join(state.get('techniques_used', [])[:5])}"
        )

        # Use asyncio to run the async CRM push
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async graph — schedule as task
            asyncio.ensure_future(
                CRMBridge.push_response(
                    provider=crm_provider,
                    ticket_id=crm_ticket_id,
                    response=response,
                    status="resolved",
                    internal_note=internal_note,
                )
            )
        else:
            loop.run_until_complete(
                CRMBridge.push_response(
                    provider=crm_provider,
                    ticket_id=crm_ticket_id,
                    response=response,
                    status="resolved",
                    internal_note=internal_note,
                )
            )

        logger.info(
            "CRM push-back: ticket=%s provider=%s",
            crm_ticket_id, crm_provider,
        )
    except Exception as e:
        logger.warning("CRM push-back failed (non-fatal): %s", e)


def _wiki_write_on_resolve(state: PipelineV2State, techniques: list = None) -> None:
    """Phase 6: Write resolution pattern to Wiki Section A.
    
    Called after successful resolution (both simple and complex paths).
    This is the LEARNING part — PARWA remembers what worked.
    Non-LLM, non-blocking — failures are silently logged.
    """
    try:
        from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store
        
        tenant_id = state.get("tenant_id", "")
        if not tenant_id:
            return
        
        ticket_type = state.get("ticket_type", "general")
        query = state.get("query", "")
        complexity = state.get("complexity", "unknown")
        tier = state.get("variant_tier", "parwa")
        
        # Get quality score
        quality = state.get("quality_score", 0.0)
        if state.get("simple_confidence"):
            quality = max(quality, state["simple_confidence"])
        if state.get("super_node_quality"):
            quality = max(quality, state["super_node_quality"])
        
        # Get answer summary
        answer = state.get("formatted_response", "") or state.get("final_response", "") or state.get("combined_answer", "")
        
        # Get techniques used
        if techniques is None:
            techniques = state.get("techniques_used", [])
        
        # Write to wiki
        wiki = get_wiki_store()
        entry = wiki.write_ticket_pattern(
            tenant_id=tenant_id,
            ticket_type=ticket_type,
            query=query,
            complexity=complexity,
            techniques_used=techniques,
            quality_score=quality,
            answer_summary=answer,
            tier=tier,
        )
        
        if entry:
            logger.info(
                "Wiki WRITE: ticket=%s type=%s quality=%.2f → key=%s",
                state.get("ticket_id", "?"), ticket_type, quality, entry.entry_key,
            )
    except Exception as e:
        logger.warning("Wiki write-back failed (non-fatal): %s", e)


# ── Build Graph ───────────────────────────────────────────────────


def run_parwa_pipeline(initial_state: PipelineV2State) -> PipelineV2State:
    """Run the pipeline and handle Phase 6 wiki write-back.
    
    Wraps the compiled graph to add wiki learning after resolution.
    Safe to call from sync or async context.
    """
    import asyncio
    
    graph = build_parwa_pipeline()
    compiled = graph.compile()
    
    async def _run():
        result = await compiled.ainvoke(initial_state)
        
        # Phase 6: Wiki write-back for complex path resolutions
        # (simple path is handled in _finalize_simple)
        quality_passed = result.get("quality_passed", False)
        if quality_passed:
            _wiki_write_on_resolve(result)
        
        return result
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop and loop.is_running():
        # Already in async context — create a new thread with its own event loop
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, _run()).result()
    else:
        return asyncio.run(_run())


def build_parwa_pipeline() -> StateGraph:
    """Build the 8-node PARWA pipeline graph.

    Usage:
        graph = build_parwa_pipeline()
        compiled = graph.compile()
        result = await compiled.ainvoke(initial_state)
    """
    graph = StateGraph(PipelineV2State)

    # ── Add Nodes ─────────────────────────────────────────────────
    # Wrap each node with crash resilience — any unhandled exception is
    # caught, logged, and converted to a safe fallback so the pipeline
    # NEVER crashes.  The error is recorded in state["errors"] for debugging.
    import functools

    def _safe_node(fn, node_name: str):
        """Wrap a node function so unhandled exceptions become safe fallbacks."""
        @functools.wraps(fn)
        async def wrapper(state: PipelineV2State) -> dict:
            try:
                return await fn(state)
            except Exception as exc:
                logger.error(
                    "%s CRASHED (%s): %s", node_name, type(exc).__name__, exc,
                    exc_info=True,
                )
                # Return a minimal safe state so downstream nodes don't KeyError
                return {
                    "errors": [{"node": node_name, "error": str(exc), "type": type(exc).__name__}],
                    "technique_log": [{"node": node_name.replace("node_", ""), "technique": "CRASH_RECOVERY", "duration_ms": 0, "result_summary": f"recovered from {type(exc).__name__}"}],
                    "status": "stuck",
                }
        return wrapper

    graph.add_node("node_1", _safe_node(node_1_ingest_classify, "node_1"))
    graph.add_node("node_2", _safe_node(node_2_smart_route, "node_2"))
    graph.add_node("node_3", _safe_node(node_3_knowledge_fetch, "node_3"))
    graph.add_node("node_4", _safe_node(node_4_reasoning_engine, "node_4"))
    graph.add_node("node_5", _safe_node(node_5_act_verify, "node_5"))
    graph.add_node("node_6", _safe_node(node_6_quality_format, "node_6"))
    graph.add_node("node_7", _safe_node(node_7_simple_resolver, "node_7"))
    graph.add_node("node_8", _safe_node(node_8_super_node, "node_8"))
    graph.add_node("increment_loop", _increment_loop)
    graph.add_node("finalize_simple", _finalize_simple)
    graph.add_node("wiki_finalize", _wiki_finalize_complex)  # Phase 7: in-graph wiki write

    # ── Add Edges ─────────────────────────────────────────────────

    # Entry → Node 1
    graph.set_entry_point("node_1")

    # Node 1 → SPLIT: rejected/paused → END, normal → Node 2
    graph.add_conditional_edges("node_1", _route_after_node_1, {
        "node_2": "node_2",
        "__end__": "__end__",
    })

    # Node 2 → SPLIT: paused → END, normal → Node 3
    graph.add_conditional_edges("node_2", _route_after_node_2, {
        "node_3": "node_3",
        "__end__": "__end__",
    })

    # Node 3 → SPLIT: simple → Node 7, complex → Node 4
    graph.add_conditional_edges("node_3", _route_after_node_3, {
        "node_7": "node_7",
        "node_4": "node_4",
    })

    # Node 7 (Simple Resolver) → SPLIT: pass → finalize, safety net → Node 4
    graph.add_conditional_edges("node_7", _route_after_node_7, {
        "node_4": "node_4",
        "__end__": "finalize_simple",
    })

    # Node 4 (Reasoning) → Node 5
    graph.add_edge("node_4", "node_5")

    # Node 5 (Act+Verify) → Node 6
    graph.add_edge("node_5", "node_6")

    # Node 6 (Quality) → SPLIT: pass → wiki write, fail → loop or super
    # Phase 7: pass now goes to wiki_finalize (in-graph wiki write-back)
    graph.add_conditional_edges("node_6", _route_after_node_6, {
        "wiki_finalize": "wiki_finalize",
        "node_4": "increment_loop",
        "node_8": "node_8",
    })

    # Wiki finalize (complex path) → END
    graph.add_edge("wiki_finalize", "__end__")

    # Increment loop counter → back to Node 4
    graph.add_edge("increment_loop", "node_4")

    # Node 8 (Super Node) → END
    graph.add_edge("node_8", "__end__")

    # Finalize simple → END
    graph.add_edge("finalize_simple", "__end__")

    logger.info("PARWA Pipeline V2 built: 8 nodes, dual path, quality loop (max %d), Phase 7 in-graph wiki write-back", MAX_QUALITY_LOOPS)

    return graph