"""
PARWA Jarvis Pipeline Query Agent Node (Phase 4)

A specialist agent that can QUERY the variant pipeline mid-execution.
When Jarvis needs to know "what's the current quality score of the
refund agent?" or "how many tickets is the technical agent processing?",
this agent asks the pipeline.

This is the agent-to-agent communication channel. The pipeline_query_agent
is how Jarvis ASKS the variant agents about their state.

HOW IT WORKS:
  1. Jarvis receives a query command (e.g., "check quality score")
  2. Command router routes to pipeline_query_agent
  3. Agent reads the latest pipeline state from Redis/DB
  4. Agent uses ZAI SDK to interpret the query against the state
  5. Returns a structured answer that Jarvis can relay to the user

EXAMPLE QUERIES:
  - "What's the current quality score across all agents?"
  - "How many tickets are in the refund queue?"
  - "Is the technical agent currently overloaded?"
  - "Show me the drift score for the last hour"
  - "Are there any active emergency alerts?"

The pipeline_query_agent NEVER takes action — it only reads and reports.
This makes it safe for all variant tiers (including mini_parwa where
Jarvis can only observe).

BC-008: Never crash — if query fails, return an error message, not an exception.
BC-012: All timestamps UTC.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger
from app.services.jarvis_agents.zai_client import get_zai_client

logger = get_logger("jarvis_pipeline_query_agent")


def pipeline_query_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Query the variant LangGraph pipeline for real-time status.

    This is how Jarvis ASKS the variant agents about their state.
    It's the agent-to-agent communication channel.

    Example queries:
    - "What's the current quality score across all agents?"
    - "How many tickets are in the refund queue?"
    - "Is the technical agent currently overloaded?"

    Uses ZAI SDK to interpret the query and format the response.

    Args:
        state: Current JarvisCommandState dict.

    Returns:
        Dict with updated AGENT group fields including the query result.
    """
    start_time = time.monotonic()

    try:
        company_id = state.get("company_id", "")
        session_id = state.get("session_id", "")
        variant_tier = state.get("variant_tier", "mini_parwa")
        raw_input = state.get("raw_input", "")
        awareness = state.get("awareness_snapshot", {})

        # ── Step 1: Read current pipeline state ──
        pipeline_state = _read_pipeline_state(company_id, session_id)

        # ── Step 2: Read awareness data ──
        if not awareness:
            awareness = _read_awareness_data(company_id, session_id)

        # ── Step 3: Interpret the query using ZAI SDK ──
        query_result = _interpret_query(
            raw_input=raw_input,
            pipeline_state=pipeline_state,
            awareness=awareness,
            variant_tier=variant_tier,
            company_id=company_id,
        )

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = {
            "agent_type": "pipeline_query",
            "agent_action": "query_pipeline",
            "agent_decision": query_result,
            "agent_reasoning": query_result.get("reasoning", ""),
            "agent_source": query_result.get("_source", "unknown"),
            "node_outputs": {"pipeline_query_agent": query_result},
            "audit_trail": [{
                "step": "pipeline_query_agent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "query_pipeline",
                "query_type": query_result.get("query_type", "general"),
                "source": query_result.get("_source", "unknown"),
                "elapsed_ms": elapsed_ms,
            }],
        }

        logger.info(
            "pipeline_query_agent: company=%s, query_type=%s, "
            "source=%s, ms=%.1f",
            company_id, query_result.get("query_type", "general"),
            query_result.get("_source", "unknown"), elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("pipeline_query_agent_error: ms=%.1f", elapsed_ms)
        return {
            "agent_type": "pipeline_query",
            "agent_action": "query_pipeline",
            "agent_decision": {
                "action": "query_pipeline",
                "result": "Error querying pipeline state",
                "error": str(e)[:200],
            },
            "agent_reasoning": f"Error fallback: {str(e)[:200]}",
            "agent_source": "error_fallback",
            "errors": [f"pipeline_query_agent: {str(e)[:200]}"],
            "node_outputs": {"pipeline_query_agent": {"error": str(e)[:200]}},
        }


# ══════════════════════════════════════════════════════════════════
# PIPELINE STATE READERS
# ══════════════════════════════════════════════════════════════════


def _read_pipeline_state(company_id: str, session_id: str) -> Dict[str, Any]:
    """Read the current pipeline state from Redis bridge.

    Falls back to DB if Redis is unavailable.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.

    Returns:
        Dict with pipeline state, or empty dict on failure.
    """
    try:
        import asyncio

        async def _read():
            try:
                from app.services.jarvis_agents.variant_bridge import (
                    read_pipeline_state_for_jarvis,
                )
                return await read_pipeline_state_for_jarvis(
                    company_id, session_id,
                )
            except Exception:
                return {}

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _read())
                return future.result(timeout=5)
        except RuntimeError:
            return asyncio.run(_read())

    except Exception as e:
        logger.debug(
            "pipeline_state_read_failed: company=%s, session=%s, error=%s",
            company_id, session_id, str(e)[:200],
        )
        return {}


def _read_awareness_data(company_id: str, session_id: str) -> Dict[str, Any]:
    """Read awareness data from DB (fallback for missing awareness_snapshot).

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.

    Returns:
        Dict with awareness data, or empty dict on failure.
    """
    try:
        from database.base import SessionLocal
        from database.models.jarvis_cc import JarvisAwarenessSnapshot

        db = SessionLocal()
        try:
            snapshot = (
                db.query(JarvisAwarenessSnapshot)
                .filter(
                    JarvisAwarenessSnapshot.session_id == session_id,
                    JarvisAwarenessSnapshot.company_id == company_id,
                )
                .order_by(JarvisAwarenessSnapshot.created_at.desc())
                .first()
            )

            if snapshot and snapshot.raw_state_json:
                return json.loads(snapshot.raw_state_json)
            return {}
        finally:
            db.close()

    except Exception as e:
        logger.debug(
            "awareness_db_read_failed: company=%s, session=%s, error=%s",
            company_id, session_id, str(e)[:200],
        )
        return {}


# ══════════════════════════════════════════════════════════════════
# QUERY INTERPRETATION
# ══════════════════════════════════════════════════════════════════


def _interpret_query(
    raw_input: str,
    pipeline_state: Dict[str, Any],
    awareness: Dict[str, Any],
    variant_tier: str,
    company_id: str,
) -> Dict[str, Any]:
    """Interpret the user's query against the current pipeline state.

    Uses ZAI SDK (LLM) to understand the query and extract the
    relevant information from the pipeline state. Falls back to
    rule-based interpretation if LLM fails.

    Args:
        raw_input: The user's raw query text.
        pipeline_state: Current pipeline state from bridge.
        awareness: Current awareness snapshot data.
        variant_tier: Current variant tier.
        company_id: Company ID for BC-001.

    Returns:
        Dict with query_type, answer, and reasoning.
    """
    # Merge all available state for the LLM to reason about
    full_context = {
        "pipeline_state": pipeline_state,
        "awareness": awareness,
        "variant_tier": variant_tier,
        "company_id": company_id,
        "queried_at": datetime.now(timezone.utc).isoformat(),
    }

    # ── Try ZAI SDK first ──
    try:
        zai = get_zai_client()
        user_message = (
            f"User is asking about the current pipeline state:\n"
            f"  Query: '{raw_input}'\n\n"
            f"Current pipeline data:\n"
            f"  System health: {awareness.get('system_health', 'unknown')}\n"
            f"  Quality score: {awareness.get('quality_score', 'unknown')}\n"
            f"  Drift score: {awareness.get('drift_score', 'unknown')}\n"
            f"  Drift status: {awareness.get('drift_status', 'unknown')}\n"
            f"  Ticket volume today: {awareness.get('ticket_volume_today', 0)}\n"
            f"  Ticket volume avg: {awareness.get('ticket_volume_avg', 0)}\n"
            f"  Active agents: {awareness.get('active_agents', 0)}\n"
            f"  Agent pool utilization: {awareness.get('agent_pool_utilization', 'unknown')}%\n"
            f"  Training running: {awareness.get('training_running', False)}\n"
            f"  Training mistakes: {awareness.get('training_mistake_count', 0)}\n"
            f"  Emergency state: {pipeline_state.get('emergency_state', 'normal')}\n"
            f"  AI paused: {pipeline_state.get('ai_paused', False)}\n"
            f"  Variant tier: {variant_tier}\n\n"
            f"Provide a concise, accurate answer to the query based on this data.\n"
            f"Respond in JSON: "
            f'{{"query_type": "quality|volume|agent|drift|emergency|general", '
            f'"answer": "your answer", "reasoning": "why", '
            f'"data_points": {{"key": "value"}}}}'
        )

        result = zai.chat("pipeline_query_agent", user_message, full_context)

        # Ensure required fields
        result.setdefault("query_type", "general")
        result.setdefault("answer", "")
        result.setdefault("reasoning", "")
        result.setdefault("data_points", {})

        return result

    except Exception as e:
        logger.debug(
            "zai_query_interpret_failed: error=%s, using_rule_based",
            str(e)[:200],
        )
        return _rule_based_query_interpretation(
            raw_input, pipeline_state, awareness, variant_tier,
        )


def _rule_based_query_interpretation(
    raw_input: str,
    pipeline_state: Dict[str, Any],
    awareness: Dict[str, Any],
    variant_tier: str,
) -> Dict[str, Any]:
    """Rule-based query interpretation when ZAI SDK is unavailable.

    Uses keyword matching to determine query type and extract
    relevant data from the pipeline/awareness state.

    Args:
        raw_input: The user's raw query text.
        pipeline_state: Current pipeline state.
        awareness: Current awareness data.
        variant_tier: Current variant tier.

    Returns:
        Dict with query_type, answer, reasoning, and data_points.
    """
    query_lower = raw_input.lower()
    now = datetime.now(timezone.utc).isoformat()

    # ── Quality-related queries ──
    if any(kw in query_lower for kw in ("quality", "score", "accuracy")):
        quality_score = awareness.get("quality_score", "N/A")
        drift_status = awareness.get("drift_status", "none")
        drift_score = awareness.get("drift_score", "N/A")
        return {
            "_source": "rule_based_fallback",
            "_agent_type": "pipeline_query_agent",
            "_parsed_at": now,
            "query_type": "quality",
            "action": "query_pipeline",
            "answer": (
                f"Current quality score: {quality_score}. "
                f"Drift status: {drift_status} (score: {drift_score}). "
                f"Variant tier: {variant_tier}."
            ),
            "reasoning": "Rule-based quality query interpretation",
            "data_points": {
                "quality_score": quality_score,
                "drift_status": drift_status,
                "drift_score": drift_score,
                "variant_tier": variant_tier,
            },
        }

    # ── Volume-related queries ──
    if any(kw in query_lower for kw in ("volume", "ticket", "queue", "load")):
        volume_today = awareness.get("ticket_volume_today", 0)
        volume_avg = awareness.get("ticket_volume_avg", 0)
        spike = awareness.get("ticket_volume_spike", False)
        return {
            "_source": "rule_based_fallback",
            "_agent_type": "pipeline_query_agent",
            "_parsed_at": now,
            "query_type": "volume",
            "action": "query_pipeline",
            "answer": (
                f"Ticket volume today: {volume_today} "
                f"(avg: {volume_avg}, spike: {spike}). "
                f"Variant tier: {variant_tier}."
            ),
            "reasoning": "Rule-based volume query interpretation",
            "data_points": {
                "ticket_volume_today": volume_today,
                "ticket_volume_avg": volume_avg,
                "ticket_volume_spike": spike,
                "variant_tier": variant_tier,
            },
        }

    # ── Agent-related queries ──
    if any(kw in query_lower for kw in ("agent", "overload", "utilization", "capacity")):
        active_agents = awareness.get("active_agents", 0)
        capacity = awareness.get("agent_pool_capacity", 0)
        utilization = awareness.get("agent_pool_utilization", "N/A")
        return {
            "_source": "rule_based_fallback",
            "_agent_type": "pipeline_query_agent",
            "_parsed_at": now,
            "query_type": "agent",
            "action": "query_pipeline",
            "answer": (
                f"Active agents: {active_agents}/{capacity}. "
                f"Utilization: {utilization}%. "
                f"Variant tier: {variant_tier}."
            ),
            "reasoning": "Rule-based agent query interpretation",
            "data_points": {
                "active_agents": active_agents,
                "agent_pool_capacity": capacity,
                "agent_pool_utilization": utilization,
                "variant_tier": variant_tier,
            },
        }

    # ── Emergency/status queries ──
    if any(kw in query_lower for kw in ("emergency", "alert", "pause", "status", "health")):
        system_health = awareness.get("system_health", "unknown")
        emergency_state = pipeline_state.get("emergency_state", "normal")
        ai_paused = pipeline_state.get("ai_paused", False)
        return {
            "_source": "rule_based_fallback",
            "_agent_type": "pipeline_query_agent",
            "_parsed_at": now,
            "query_type": "emergency",
            "action": "query_pipeline",
            "answer": (
                f"System health: {system_health}. "
                f"Emergency state: {emergency_state}. "
                f"AI paused: {ai_paused}. "
                f"Variant tier: {variant_tier}."
            ),
            "reasoning": "Rule-based emergency/status query interpretation",
            "data_points": {
                "system_health": system_health,
                "emergency_state": emergency_state,
                "ai_paused": ai_paused,
                "variant_tier": variant_tier,
            },
        }

    # ── Default: General system overview ──
    return {
        "_source": "rule_based_fallback",
        "_agent_type": "pipeline_query_agent",
        "_parsed_at": now,
        "query_type": "general",
        "action": "query_pipeline",
        "answer": (
            f"System overview: Health={awareness.get('system_health', 'unknown')}, "
            f"Quality={awareness.get('quality_score', 'N/A')}, "
            f"Volume={awareness.get('ticket_volume_today', 0)}/"
            f"{awareness.get('ticket_volume_avg', 0)} avg, "
            f"Agents={awareness.get('active_agents', 0)}/"
            f"{awareness.get('agent_pool_capacity', 0)}, "
            f"Drift={awareness.get('drift_status', 'none')}, "
            f"Tier={variant_tier}."
        ),
        "reasoning": "Rule-based general system overview",
        "data_points": {
            "system_health": awareness.get("system_health", "unknown"),
            "quality_score": awareness.get("quality_score", "N/A"),
            "ticket_volume_today": awareness.get("ticket_volume_today", 0),
            "ticket_volume_avg": awareness.get("ticket_volume_avg", 0),
            "active_agents": awareness.get("active_agents", 0),
            "agent_pool_capacity": awareness.get("agent_pool_capacity", 0),
            "drift_status": awareness.get("drift_status", "none"),
            "variant_tier": variant_tier,
        },
    }
