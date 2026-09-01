"""
PARWA Pipeline V2 — Graph Definition (Phase 7: In-Graph Wiki Write-Back)
                              (Phase 8: Few-Shot + CoVe)
                              (Phase 11: Jarvis Awareness Bridge)

Wires all nodes with LangGraph StateGraph.
Phase 7: Wiki write-back INSIDE the graph for both paths.
Phase 8: Added Node 3.5 (Few-Shot Injection) and Node 4.5 (Chain-of-Verification)
         to make weak LLMs (Llama 3.1 8B) viable without paying for HEAVY models.
Phase 11: Added Jarvis Awareness node between Node 1 and routing.
          Reads Jarvis decisions (pause, red_alert, co-pilot) from Redis
          and injects them into pipeline state BEFORE routing.

Flow:
  Node 1 (Ingest+Classify) → Jarvis Awareness → routing
    ├── simple_path  → Node 3 (Knowledge)
    │                     → Node 3.5 (Few-Shot Injection)  ← Phase 8
    │                     → Node 7 (Simple Resolver)
    │                       ├── PASS → finalize_simple (wiki write) → END
    │                       └── auto_upgraded → Node 4 (Reasoning) path
    └── complex_path → Node 3 (Knowledge)
                          → Node 3.5 (Few-Shot Injection)  ← Phase 8
                          → Node 4 (Reasoning)
                              → Node 4.5 (Chain-of-Verification)  ← Phase 8
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

logger = logging.getLogger("parwa.pipeline.graph_v2")

# ── Global checkpointer singleton ──────────────────────────────────
# Shared between initial run and resume call so interrupt() state
# persists across ainvoke() calls. Uses PostgresSaver in production
# (DATABASE_URL set) so checkpoints survive backend restarts — required
# for the resume endpoint to work after Render redeploys. Falls back to
# MemorySaver in tests/local dev where no DB is available.
_global_checkpointer = None
_global_postgres_conn = None  # keep a reference so the connection isn't GC'd


def get_checkpointer():
    """Return the global checkpointer (singleton).

    Prefers PostgresSaver when DATABASE_URL is set; falls back to MemorySaver.
    """
    global _global_checkpointer, _global_postgres_conn
    if _global_checkpointer is not None:
        return _global_checkpointer

    import os
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            # PostgresSaver.from_conn_string is a context manager; we need a
            # long-lived instance. Use the underlying psycopg connection.
            import psycopg
            _global_postgres_conn = psycopg.connect(db_url, autocommit=True)
            _global_checkpointer = PostgresSaver(conn=_global_postgres_conn)
            # Create the checkpoint tables (idempotent)
            _global_checkpointer.setup()
            logger.info("pipeline_checkpointer_initialized (PostgresSaver)")
            return _global_checkpointer
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "pipeline_checkpointer_postgres_failed_falling_back_to_memory: %s",
                str(exc)[:200],
            )
            # Fall through to MemorySaver

    from langgraph.checkpoint.memory import MemorySaver
    _global_checkpointer = MemorySaver()
    logger.info("pipeline_checkpointer_initialized (MemorySaver)")
    return _global_checkpointer

from app.core.parwa_pipeline.pipeline_config import (
    MAX_QUALITY_LOOPS,
    PATH_COMPLEX,
    PATH_SIMPLE,
    QUALITY_LOOP_THRESHOLD,
    QUALITY_PASS_THRESHOLD,
)
from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify
from app.core.parwa_pipeline.nodes.node_2_smart_route import node_2_smart_route
from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import node_3_knowledge_fetch
from app.core.parwa_pipeline.nodes.node_3_5_few_shot import node_3_5_few_shot_injection  # Phase 8
from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import node_4_reasoning_engine
from app.core.parwa_pipeline.nodes.node_4_5_cove import node_4_5_chain_of_verification  # Phase 8
from app.core.parwa_pipeline.nodes.node_5_act_verify import node_5_act_verify
from app.core.parwa_pipeline.nodes.node_6_quality_format import node_6_quality_format
from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver
from app.core.parwa_pipeline.nodes.node_7_simple_resolver import node_7_simple_resolver
from app.core.parwa_pipeline.nodes.node_8_super_node import node_8_super_node
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.graph_v2")


# ── Jarvis Awareness Bridge (Phase 11) ────────────────────────────
# Async wrapper for the sync jarvis_awareness_injector_node.
# This node sits between Node 1 and routing to inject Jarvis
# decisions (pause AI, red alerts, co-pilot suggestions) into
# pipeline state BEFORE the routing decision is made.


async def _jarvis_awareness(state: PipelineV2State) -> dict:
    """Read Jarvis awareness from Redis and inject into pipeline state.

    Non-blocking: if Redis is unavailable or no Jarvis state exists,
    returns an empty update dict so the pipeline continues normally.
    """
    try:
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            jarvis_awareness_injector_node,
        )
        return jarvis_awareness_injector_node(state)
    except Exception as exc:
        logger.debug("jarvis_awareness_skipped: %s", str(exc)[:200])
        return {}


# ── Edge Functions ────────────────────────────────────────────────


def _route_after_jarvis_awareness(state: PipelineV2State) -> Literal["node_2", "node_7", "finalize_simple", "__end__"]:
    """After Jarvis Awareness: route based on status, lane, and Jarvis overrides.

    Commit 2: 3-Lane System
    - Lane FULL    → Node 2 (existing 8-node pipeline for new complex tickets)
    - Lane QUICK   → Node 7 (Simple Resolver, 0-3 LLM calls for follow-ups)
    - Lane INSTANT → finalize_simple (canned response, 0 LLM for gratitude)

    Phase 11: Jarvis can override routing:
    - If Jarvis set system_mode="paused" → early exit (human review)
    - If Jarvis set urgency="critical" → force FULL lane

    All 16 non-LLM techniques have already run in Node 1 regardless of lane.
    """
    # Status-based early exit (rejected/paused tickets)
    status = state.get("status", "")
    if status in ("rejected", "paused"):
        logger.info("Jarvis awareness early exit: status=%s", status)
        return "__end__"

    # Phase 11: Jarvis system_mode override
    system_mode = state.get("system_mode", "")
    if system_mode == "paused":
        logger.info(
            "Jarvis paused AI: ticket=%s → early exit (human review)",
            state.get("ticket_id", "?"),
        )
        return "__end__"

    # Lane-based routing (Commit 2)
    lane = state.get("lane", "FULL")
    if lane == "INSTANT":
        # Gratitude / simple questions — use canned response from Node 1
        logger.info(
            "Lane INSTANT: ticket=%s → finalize_simple (canned response)",
            state.get("ticket_id", "?"),
        )
        return "finalize_simple"
    if lane == "QUICK":
        # Follow-ups / clarifications → Simple Resolver (skips Nodes 2-6)
        logger.info(
            "Lane QUICK: ticket=%s → node_7 (Simple Resolver)",
            state.get("ticket_id", "?"),
        )
        return "node_7"

    # Lane FULL — new complex tickets → existing 8-node pipeline
    return "node_2"


def _route_after_node_2(state: PipelineV2State) -> Literal["node_3", "__end__"]:
    """After Node 2: if paused/escalated by Jarvis flags, end early. Otherwise → Node 3."""
    status = state.get("status", "")
    if status in ("paused", "escalated"):
        logger.info("Node 2 early exit: status=%s", status)
        return "__end__"
    return "node_3"


def _route_after_node_3(state: PipelineV2State) -> Literal["node_3_5", "node_3_5"]:
    """After Node 3: ALWAYS go to Node 3.5 (Few-Shot Injection) regardless of path.

    Phase 8: Node 3.5 runs for both simple and complex paths because both
    Node 4 (Reasoning) and Node 7 (Simple Resolver) benefit from few-shot
    examples. Node 3.5 is 0 LLM calls, so the cost is zero.
    """
    return "node_3_5"


def _route_after_node_3_5(state: PipelineV2State) -> Literal["node_7", "node_4"]:
    """After Node 3.5: simple path → Node 7, complex path → Node 4."""
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

    Phase 10: If cove_blocked=True, skip quality loop entirely —
    the safe fallback doesn't need quality checks, just deliver it.

    PASS (quality >= 90%) → wiki_finalize → END (resolved)
    COVE_BLOCKED → wiki_finalize → END (awaiting_human, safe fallback)
    FAIL + loops < MAX → Node 4 (retry)
    FAIL + loops >= MAX → Node 8 (Super Node)
    """
    # Phase 10: CoVe hard gate — if blocked, skip quality loop
    if state.get("cove_blocked", False):
        logger.info(
            "CoVe BLOCKED → skipping quality loop, going to wiki_finalize (safe fallback)"
        )
        return "wiki_finalize"

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




def _consume_quota(state: PipelineV2State) -> None:
    """Increment ticket usage in UsageRecord for the tenant.

    Called from terminal nodes (finalize_simple, wiki_finalize) after
    successful resolution.  Non-blocking — failures are logged but
    never break the pipeline (BC-008).
    """
    try:
        tenant_id = state.get("tenant_id", "")
        if not tenant_id:
            return

        from app.services.usage_tracking_service import UsageTrackingService
        svc = UsageTrackingService()
        svc.increment_ticket_usage(tenant_id, count=1)

        tier = state.get("variant_tier_short", state.get("variant_tier", "?"))
        logger.info(
            "Quota consumed: tenant=%s tier=%s ticket=%s",
            tenant_id, tier, state.get("ticket_id", "?"),
        )
    except Exception as exc:
        logger.warning("Quota consumption failed (non-fatal): %s", exc)


def _finalize_simple(state: PipelineV2State) -> dict:
    """Set final response from simple resolver + wiki write-back + quota consume.

    BC-016 (v2): CRM push-back has been MOVED out of the finalize nodes and
    into Node 6.5 Deliver as phase 2. Order is now:
        finalize (wiki + quota) → Node 6.5 phase 1 (customer dispatch)
                                  → Node 6.5 phase 2 (CRM push, only if phase 1 ok)

    Rationale: CRM must NEVER be told "resolved" before the customer actually
    receives the answer. See BC-016 in CLAUDE.md.
    """
    _wiki_write_on_resolve(state, techniques=["Node7_SimpleResolver", "GSD", "MAKER", "FederatedReasoning"])
    _consume_quota(state)
    return {
        "final_response": state.get("simple_answer", ""),
        "status": "resolved",
        "formatted_response": state.get("simple_answer", ""),
        "quality_passed": True,
    }


def _wiki_finalize_complex(state: PipelineV2State) -> dict:
    """Phase 7: Wiki write-back for complex path + set final response + quota consume.

    This node is called AFTER Node 6 quality passes on the complex path.
    Previously wiki write-back was only in run_parwa_pipeline() wrapper,
    which tests bypassed via compiled.ainvoke().

    BC-016 (v2): CRM push-back moved to Node 6.5 phase 2 — see _finalize_simple docstring.

    Phase 10: CoVe Hard Gate — if cove_blocked=True, the response has been
    replaced with a safe fallback by Node 4.5, and the ticket status is set
    to "awaiting_human" instead of "resolved". The customer still gets a
    response (the safe fallback), but a human agent is flagged to follow up.
    """
    _wiki_write_on_resolve(state)
    response = state.get("formatted_response", "") or state.get("combined_answer", "")
    cove_blocked = state.get("cove_blocked", False)
    _consume_quota(state)

    if cove_blocked:
        # CoVe blocked this response — escalate to human, don't mark as resolved
        logger.info(
            "wiki_finalize: CoVe BLOCKED ticket=%s — using safe fallback, status=awaiting_human",
            state.get("ticket_id", "?"),
        )
        return {
            "final_response": response,
            "status": "awaiting_human",
            "cove_blocked": True,
        }

    return {
        "final_response": response,
        "status": "resolved",
    }


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
    # Compile WITH global checkpointer so nodes can interrupt() and resume.
    compiled = graph.compile(checkpointer=get_checkpointer())

    async def _run():
        # ── Session continuity: acquire lock (BC-008: non-blocking) ──
        _scm = None
        try:
            from app.core.session_continuity import SessionContinuityManager
            _scm = SessionContinuityManager()
            _scm.acquire_lock(
                company_id=initial_state.get("tenant_id", ""),
                ticket_id=initial_state.get("ticket_id", ""),
                agent_id="parwa_pipeline",
            )
        except Exception:
            pass  # BC-008: never crash

        # ── Call lifecycle: start (BC-008: non-blocking) ──
        _lifecycle_id = None
        _clm = None
        try:
            from app.core.call_lifecycle import CallLifecycleManager
            _clm = CallLifecycleManager()
            _lifecycle_id = _clm.start_lifecycle(
                company_id=initial_state.get("tenant_id", ""),
                ticket_id=initial_state.get("ticket_id", ""),
                variant=initial_state.get("variant_tier", "parwa"),
            )
        except Exception:
            pass  # BC-008: never crash

        config = {"configurable": {"thread_id": initial_state.get("ticket_id", "default")}}
        result = None
        pipeline_exc = None

        try:
            result = await compiled.ainvoke(initial_state, config=config)
        except Exception as exc:
            # Don't swallow GraphInterrupt — let it propagate
            try:
                from langgraph.errors import GraphInterrupt
                if isinstance(exc, GraphInterrupt):
                    raise
            except ImportError:
                pass
            if type(exc).__name__ in ("GraphInterrupt", "GraphBubbleUp"):
                raise
            pipeline_exc = exc

        if pipeline_exc is not None:
            # Call lifecycle: mark failed
            try:
                if _lifecycle_id and _clm:
                    _clm.fail_lifecycle(
                        company_id=initial_state.get("tenant_id", ""),
                        lifecycle_id=_lifecycle_id,
                        error=str(pipeline_exc)[:2000],
                    )
            except Exception:
                pass  # BC-008

            # Partial failure: return degraded response
            try:
                from app.core.partial_failure import PartialFailureHandler, PipelineContext
                _pfh = PartialFailureHandler()
                _pf_ctx = PipelineContext(
                    company_id=initial_state.get("tenant_id", ""),
                    ticket_id=initial_state.get("ticket_id", ""),
                    variant=initial_state.get("variant_tier", "parwa"),
                    intent=initial_state.get("ticket_type", "general"),
                )
                degraded = _pfh.generate_degraded_response(_pf_ctx)
                logger.warning(
                    "pipeline_failed_returning_degraded_response ticket=%s error=%s",
                    initial_state.get("ticket_id", ""), str(pipeline_exc)[:200],
                )
                result = {
                    "final_response": degraded,
                    "status": "degraded",
                    "errors": [{"node": "pipeline", "error": str(pipeline_exc), "type": type(pipeline_exc).__name__}],
                    "degradation_level": _pfh.get_degradation_level(_pf_ctx),
                }
            except Exception:
                logger.exception("partial_failure_handler_crashed ticket=%s", initial_state.get("ticket_id", ""))
                result = {
                    "final_response": "We're experiencing processing difficulties. A team member will assist you shortly.",
                    "status": "error",
                    "errors": [{"node": "pipeline", "error": str(pipeline_exc), "type": type(pipeline_exc).__name__}],
                }
        else:
            # Call lifecycle: mark completed
            try:
                if _lifecycle_id and _clm:
                    _clm.complete_lifecycle(
                        company_id=initial_state.get("tenant_id", ""),
                        lifecycle_id=_lifecycle_id,
                    )
            except Exception:
                pass  # BC-008

        # ── Session continuity: release lock (BC-008: non-blocking) ──
        try:
            if _scm:
                _scm.release_lock(
                    company_id=initial_state.get("tenant_id", ""),
                    ticket_id=initial_state.get("ticket_id", ""),
                    agent_id="parwa_pipeline",
                )
        except Exception:
            pass  # BC-008: never crash

        # ── Handle interrupt (node paused to ask a question) ──────
        # When a node calls interrupt(), ainvoke returns a dict with
        # "__interrupt__" key. The pipeline is PAUSED — not finished.
        # We mark the ticket as awaiting_human so the escalations page
        # can show the question + guidance textarea.
        if isinstance(result, dict) and "__interrupt__" in result:
            interrupt_data = result["__interrupt__"]
            logger.info(
                "pipeline_interrupted ticket=%s — node paused to ask a question",
                initial_state.get("ticket_id", ""),
            )
            # Extract the question from the interrupt value
            question_text = ""
            if isinstance(interrupt_data, list) and interrupt_data:
                val = interrupt_data[0].value if hasattr(interrupt_data[0], 'value') else interrupt_data[0]
                if isinstance(val, dict):
                    question_text = val.get("question", str(val))
                else:
                    question_text = str(val)
            result["pipeline_interrupted"] = True
            result["interrupt_question"] = question_text
            result["status"] = "awaiting_human"
            return result

        # Phase 6: Wiki write-back for complex path resolutions
        # (simple path is handled in _finalize_simple)
        quality_passed = result.get("quality_passed", False) if result else False
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
                # CRITICAL: LangGraph's interrupt() raises GraphInterrupt.
                # We must NOT catch it — let it propagate so the graph pauses.
                try:
                    from langgraph.errors import GraphInterrupt
                    if isinstance(exc, GraphInterrupt):
                        logger.info("%s interrupt() raised — pausing graph", node_name)
                        raise
                except ImportError:
                    pass
                # Also check by name (fallback if import fails)
                if type(exc).__name__ in ("GraphInterrupt", "GraphBubbleUp"):
                    logger.info("%s interrupt (by name) — pausing graph", node_name)
                    raise
                logger.error(
                    "%s CRASHED (%s): %s", node_name, type(exc).__name__, exc,
                    exc_info=True,
                )
                # DLQ: persist failure (BC-008: non-blocking)
                try:
                    from app.services.langgraph_dlq_service import LanggraphDLQService
                    _dlq_svc = LanggraphDLQService()
                    await _dlq_svc.record_failure(
                        company_id=state.get("tenant_id", ""),
                        thread_id=state.get("ticket_id", ""),
                        error=exc,
                        state_snapshot={"node": node_name, "status": state.get("status", "")},
                        graph_id=state.get("ticket_id", ""),
                    )
                except Exception:
                    pass  # BC-008: never crash
                # Return a minimal safe state so downstream nodes don't KeyError
                return {
                    "errors": [{"node": node_name, "error": str(exc), "type": type(exc).__name__}],
                    "technique_log": [{"node": node_name.replace("node_", ""), "technique": "CRASH_RECOVERY", "duration_ms": 0, "result_summary": f"recovered from {type(exc).__name__}"}],
                    "status": "stuck",
                }
        return wrapper

    graph.add_node("node_1", _safe_node(node_1_ingest_classify, "node_1"))
    graph.add_node("jarvis_awareness", _jarvis_awareness)  # Phase 11: Jarvis bridge
    graph.add_node("node_2", _safe_node(node_2_smart_route, "node_2"))
    graph.add_node("node_3", _safe_node(node_3_knowledge_fetch, "node_3"))
    graph.add_node("node_3_5", _safe_node(node_3_5_few_shot_injection, "node_3_5"))  # Phase 8: Few-Shot
    graph.add_node("node_4", _safe_node(node_4_reasoning_engine, "node_4"))
    graph.add_node("node_4_5", _safe_node(node_4_5_chain_of_verification, "node_4_5"))  # Phase 8: CoVe
    graph.add_node("node_5", _safe_node(node_5_act_verify, "node_5"))
    graph.add_node("node_6", _safe_node(node_6_quality_format, "node_6"))
    graph.add_node("node_6_5", _safe_node(node_6_5_deliver, "node_6_5"))  # BC-015: customer delivery
    graph.add_node("node_7", _safe_node(node_7_simple_resolver, "node_7"))
    graph.add_node("node_8", _safe_node(node_8_super_node, "node_8"))
    graph.add_node("increment_loop", _increment_loop)
    graph.add_node("finalize_simple", _finalize_simple)
    graph.add_node("wiki_finalize", _wiki_finalize_complex)  # Phase 7: in-graph wiki write

    # ── Add Edges ─────────────────────────────────────────────────

    # Entry → Node 1
    graph.set_entry_point("node_1")

    # Node 1 → Jarvis Awareness (Phase 11: inject Jarvis decisions before routing)
    graph.add_edge("node_1", "jarvis_awareness")

    # Jarvis Awareness → SPLIT: rejected/paused → END, INSTANT → finalize, QUICK → node_7, FULL → node_2
    # Commit 2: 3-lane routing — Node 1 sets state["lane"] which controls
    # which nodes run next. Jarvis can override via system_mode/urgency.
    graph.add_conditional_edges("jarvis_awareness", _route_after_jarvis_awareness, {
        "node_2": "node_2",
        "node_7": "node_7",
        "finalize_simple": "finalize_simple",
        "__end__": "__end__",
    })

    # Node 2 → SPLIT: paused → END, normal → Node 3
    graph.add_conditional_edges("node_2", _route_after_node_2, {
        "node_3": "node_3",
        "__end__": "__end__",
    })

    # Node 3 → Node 3.5 (Phase 8: always — Few-Shot runs for both paths)
    graph.add_conditional_edges("node_3", _route_after_node_3, {
        "node_3_5": "node_3_5",
    })

    # Node 3.5 → SPLIT: simple → Node 7, complex → Node 4
    graph.add_conditional_edges("node_3_5", _route_after_node_3_5, {
        "node_7": "node_7",
        "node_4": "node_4",
    })

    # Node 7 (Simple Resolver) → SPLIT: pass → finalize, safety net → Node 4
    graph.add_conditional_edges("node_7", _route_after_node_7, {
        "node_4": "node_4",
        "__end__": "finalize_simple",
    })

    # Node 4 (Reasoning) → Node 4.5 (Phase 8: Chain-of-Verification)
    graph.add_edge("node_4", "node_4_5")

    # Node 4.5 (CoVe) → Node 5
    graph.add_edge("node_4_5", "node_5")

    # Node 5 (Act+Verify) → Node 6
    graph.add_edge("node_5", "node_6")

    # Node 6 (Quality) → SPLIT: pass → wiki write, fail → loop or super
    # Phase 7: pass now goes to wiki_finalize (in-graph wiki write-back)
    graph.add_conditional_edges("node_6", _route_after_node_6, {
        "wiki_finalize": "wiki_finalize",
        "node_4": "increment_loop",
        "node_8": "node_8",
    })

    # Wiki finalize (complex path) → Node 6.5 Deliver → END (BC-015)
    graph.add_edge("wiki_finalize", "node_6_5")

    # Increment loop counter → back to Node 4
    graph.add_edge("increment_loop", "node_4")

    # Node 8 (Super Node) → Node 6.5 Deliver → END (BC-015)
    graph.add_edge("node_8", "node_6_5")

    # Finalize simple → Node 6.5 Deliver → END (BC-015)
    graph.add_edge("finalize_simple", "node_6_5")

    # Node 6.5 Deliver → END (single terminal delivery node for all paths)
    graph.add_edge("node_6_5", "__end__")

    logger.info(
        "PARWA Pipeline V2 built: 12 nodes (incl. Node 3.5 Few-Shot, Node 4.5 CoVe, Node 6.5 Deliver, Jarvis Awareness), "
        "dual path, quality loop (max %d), Phase 7 in-graph wiki write-back, Phase 8 hallucination reduction, Phase 11 Jarvis bridge",
        MAX_QUALITY_LOOPS,
    )

    return graph