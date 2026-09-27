"""
Jarvis Lightweight Pipeline — 3 steps instead of 11 nodes.

PROBLEM: The full 11-node PARWA pipeline takes 20-30s per Jarvis message
(5-10 LLM calls). With multiple concurrent Jarvis users, the server freezes.

SOLUTION: A lightweight 3-step pipeline that keeps KB grounding + quality
check but only makes 2 LLM calls total:

  Step 1: KB FETCH (no LLM) — in-memory search + tenant KB vector search
  Step 2: GENERATE (1 LLM call, Groq, ~2s) — response with KB context
  Step 3: QUALITY CHECK (1 LLM call, Groq, ~1s) — hallucination check

Total: ~3-4s per Jarvis message (vs 20-30s with full pipeline).
With Semaphore(1), 3 concurrent users: ~4s + ~8s + ~12s = all finish in <15s.

The full 11-node pipeline is still used for TICKET processing (where
accuracy is critical — refunds, cancellations, billing disputes).
Jarvis chat is for onboarding conversations (pricing, features, general Q&A)
where speed matters more than multi-step reasoning.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("parwa.jarvis.lightweight")


async def run_lightweight_jarvis_pipeline(
    user_message: str,
    system_prompt: str,
    history: List[Dict[str, str]],
    context: Dict[str, Any],
    company_id: str = "",
) -> Tuple[str, str, Dict[str, Any], List[Dict[str, Any]]]:
    """Run the 3-step lightweight Jarvis pipeline.

    Args:
        user_message: The user's raw message.
        system_prompt: Base system prompt for Jarvis.
        history: Conversation history (list of {role, content}).
        context: Session context (industry, stage, variant_tier, etc.).
        company_id: Tenant ID for KB retrieval (BC-001).

    Returns:
        Tuple of (content, message_type, metadata, knowledge_used)
    """
    start = time.monotonic()
    knowledge: List[Dict[str, Any]] = []

    # ════════════════════════════════════════════════════════════════
    # STEP 1: KB FETCH (no LLM call — in-memory + DB vector search)
    # ════════════════════════════════════════════════════════════════
    kb_context = ""

    # 1a. Built-in knowledge base (pricing, variants, FAQ — in-memory, ~1ms)
    try:
        from app.services.jarvis_knowledge_service import (
            search_knowledge,
            build_context_knowledge,
        )
        kb_matches = search_knowledge(user_message, context)
        if kb_matches:
            for r in kb_matches[:3]:
                knowledge.append({
                    "file": r.get("source", "builtin"),
                    "score": r.get("score", 0.8),
                })
            kb_context = "\n\n".join([m.get("content", "") for m in kb_matches[:3]])

        # Add context-aware knowledge (industry, stage-specific)
        context_kb = build_context_knowledge(context)
        if context_kb:
            kb_context = (kb_context + "\n\n" + context_kb).strip()
    except Exception as exc:
        logger.debug("builtin_kb_fetch_failed: %s", str(exc)[:100])

    # 1b. Tenant-uploaded KB docs (vector search via NVIDIA embeddings, ~50ms)
    if company_id:
        try:
            from app.shared.knowledge_base.manager import KnowledgeBaseManager
            from database.base import SessionLocal

            _db = SessionLocal()
            try:
                kb_mgr = KnowledgeBaseManager(_db, company_id)
                tenant_results = kb_mgr.search(user_message, max_results=3)
                if tenant_results:
                    for r in tenant_results:
                        knowledge.append({
                            "file": r.get("document_title", "tenant_kb"),
                            "score": float(r.get("relevance_score", 0.7)),
                        })
                    tenant_kb = "\n\n".join([
                        r.get("content", "") for r in tenant_results
                    ])
                    kb_context = (kb_context + "\n\n" + tenant_kb).strip()
            finally:
                _db.close()
        except Exception as exc:
            logger.debug("tenant_kb_fetch_failed: %s", str(exc)[:100])

    step1_ms = round((time.monotonic() - start) * 1000, 2)
    logger.info(
        "jarvis_lightweight step1_kb_fetch: %dms, kb_chars=%d, sources=%d",
        step1_ms, len(kb_context), len(knowledge),
    )

    # ════════════════════════════════════════════════════════════════
    # STEP 2: GENERATE RESPONSE (1 LLM call — Groq llama-3.1-8b, ~2s)
    # ════════════════════════════════════════════════════════════════
    full_system = system_prompt
    if kb_context:
        full_system = (
            f"{system_prompt}\n\n"
            f"## Knowledge Base (use this to answer):\n{kb_context[:3000]}"
        )

    messages = [{"role": "system", "content": full_system}]
    for msg in history[-10:]:
        role = msg.get("role", "user")
        if role == "jarvis":
            role = "assistant"
        messages.append({"role": role, "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    from app.services.jarvis.chat import _try_ai_providers
    content = await _try_ai_providers(messages)

    if not content:
        from app.services.jarvis.chat import _get_stage_fallback
        content = _get_stage_fallback(context)

    step2_ms = round((time.monotonic() - start) * 1000, 2) - step1_ms
    logger.info(
        "jarvis_lightweight step2_generate: %dms, content_chars=%d",
        step2_ms, len(content),
    )

    # ════════════════════════════════════════════════════════════════
    # STEP 3: QUALITY CHECK (1 LLM call — Groq, ~1s)
    # ════════════════════════════════════════════════════════════════
    quality_score = 0.85
    quality_note = "skipped_no_kb"

    if kb_context and len(content) > 20:
        try:
            quality_prompt = f"""You are a quality checker. Is this response consistent with the knowledge base?

Knowledge Base excerpt:
{kb_context[:1500]}

Response to check:
{content[:800]}

Respond with ONLY a JSON object:
{{"consistent": true_or_false, "reason": "one sentence"}}

If the response makes claims NOT supported by the KB, mark consistent=false."""

            quality_messages = [{"role": "user", "content": quality_prompt}]
            quality_result = await _try_ai_providers(quality_messages)

            if quality_result:
                import json as _json
                import re
                json_match = re.search(r'\{.*\}', quality_result, re.DOTALL)
                if json_match:
                    q_data = _json.loads(json_match.group())
                    is_consistent = q_data.get("consistent", True)
                    reason = q_data.get("reason", "")
                    if is_consistent:
                        quality_score = 0.90
                        quality_note = f"passed: {reason[:80]}"
                    else:
                        quality_score = 0.50
                        quality_note = f"hallucination_detected: {reason[:80]}"
                        logger.warning(
                            "jarvis_lightquality_check_flagged: reason=%s",
                            reason[:100],
                        )
        except Exception as exc:
            logger.debug("quality_check_failed: %s", str(exc)[:100])
            quality_note = f"check_error: {str(exc)[:50]}"

    step3_ms = round((time.monotonic() - start) * 1000, 2) - step2_ms - step1_ms
    total_ms = round((time.monotonic() - start) * 1000, 2)

    from app.services.jarvis.chat import _determine_message_type
    stage = context.get("detected_stage", "welcome")
    message_type, metadata = _determine_message_type(stage, context)

    metadata["pipeline"] = "jarvis_lightweight_3step"
    metadata["quality_score"] = quality_score
    metadata["quality_note"] = quality_note
    metadata["kb_sources"] = len(knowledge)
    metadata["total_latency_ms"] = total_ms
    metadata["step1_kb_ms"] = step1_ms
    metadata["step2_generate_ms"] = step2_ms
    metadata["step3_quality_ms"] = step3_ms

    logger.info(
        "jarvis_lightweight_complete: total=%dms, quality=%.2f, kb_sources=%d, "
        "step1=%dms step2=%dms step3=%dms",
        total_ms, quality_score, len(knowledge),
        step1_ms, step2_ms, step3_ms,
    )

    return content, message_type, metadata, knowledge
