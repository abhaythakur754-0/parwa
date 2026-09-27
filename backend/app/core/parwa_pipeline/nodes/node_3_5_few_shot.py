"""
Node 3.5: Few-Shot Example Injection  (P1 — highest ROI for weak models)

WHY THIS EXISTS:
  Weak LLMs (Llama 3.1 8B) hallucinate less when shown 2-3 examples of similar
  resolved tickets. This is "in-context learning" — Brown et al. 2020 (GPT-3 paper).
  The model copies the PATTERN of the example instead of inventing facts.

WHAT IT DOES:
  1. Query the DB for the most recent 2-3 RESOLVED tickets in the SAME category
     as the current ticket (same tenant).
  2. For each, pull the customer's original message + the AI's response.
  3. Score each candidate by keyword overlap with the current query.
  4. Inject the top 2-3 as "examples" in the pipeline state — Node 4 will
     prepend them to the LLM prompt.

LLM CALLS: 0  (pure DB + string ops)
COST: 0  (no extra tokens)
INPUT: state.ticket_id, state.tenant_id, state.query, state.ticket_type
OUTPUT: state.few_shot_examples = [
    {"customer_message": "...", "ai_response": "...", "score": 0.85}, ...
]
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List

from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_3_5")


def _keyword_overlap_score(query: str, candidate: str) -> float:
    """Score how similar a candidate ticket is to the current query.

    Uses Jaccard-like overlap on significant words (len > 3).
    Returns 0.0-1.0.
    """
    if not query or not candidate:
        return 0.0
    q_words = {w.lower() for w in query.split() if len(w) > 3}
    c_words = {w.lower() for w in candidate.split() if len(w) > 3}
    if not q_words or not c_words:
        return 0.0
    intersection = q_words & c_words
    union = q_words | c_words
    return len(intersection) / len(union) if union else 0.0


def _fetch_resolved_tickets(
    db,
    tenant_id: str,
    category: str,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """Fetch the most recent resolved tickets in this category for this tenant.

    Returns list of dicts: {ticket_id, subject, category, first_customer_msg, ai_response}
    """
    from database.models.tickets import Ticket, TicketMessage, TicketStatus

    # Query resolved tickets in same category, same tenant, most recent first
    tickets_q = db.query(Ticket).filter(
        Ticket.company_id == tenant_id,
        Ticket.status == TicketStatus.resolved.value,
    )
    if category:
        tickets_q = tickets_q.filter(Ticket.category == category)
    tickets_q = tickets_q.order_by(Ticket.updated_at.desc().nullslast()).limit(limit)
    tickets = tickets_q.all()

    results: List[Dict[str, Any]] = []
    for t in tickets:
        # Get first customer message
        cust_msg = db.query(TicketMessage).filter(
            TicketMessage.ticket_id == t.id,
            TicketMessage.role == "customer",
        ).order_by(TicketMessage.created_at.asc()).first()

        # Get first AI response
        ai_msg = db.query(TicketMessage).filter(
            TicketMessage.ticket_id == t.id,
            TicketMessage.role == "ai",
        ).order_by(TicketMessage.created_at.asc()).first()

        if not cust_msg or not ai_msg:
            continue  # skip tickets without both sides of the conversation

        customer_text = (cust_msg.content or "").strip()
        ai_text = (ai_msg.content or "").strip()
        if len(customer_text) < 15 or len(ai_text) < 30:
            continue  # skip degenerate examples

        results.append({
            "ticket_id": t.id,
            "subject": t.subject or "",
            "category": t.category or "",
            "customer_message": customer_text[:600],   # truncate to keep prompt small
            "ai_response": ai_text[:900],              # truncate to keep prompt small
        })

    return results


def _select_top_examples(
    query: str,
    candidates: List[Dict[str, Any]],
    k: int = 3,
    min_score: float = 0.05,
) -> List[Dict[str, Any]]:
    """Pick the top-k most similar candidates to the query.

    If none reach min_score, return up to k most recent (still useful as
    generic examples of the response style).
    """
    if not candidates:
        return []

    scored: List[tuple[float, Dict[str, Any]]] = []
    for c in candidates:
        # Score against both subject and customer message
        score_subject = _keyword_overlap_score(query, c.get("subject", ""))
        score_msg = _keyword_overlap_score(query, c.get("customer_message", ""))
        # Take the max — if it matches either the subject or the body
        score = max(score_subject, score_msg)
        c["score"] = round(score, 3)
        scored.append((score, c))

    # Sort by score desc
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [c for s, c in scored[:k]]

    # If best score is below min_score, we still return them — even a low-similarity
    # example shows the model the response STYLE for this category. Better than nothing.
    if top and top[0]["score"] < min_score:
        logger.info(
            "Few-Shot: top candidate score=%.3f below min_score=%.3f — using as generic style example",
            top[0]["score"], min_score,
        )

    return top


async def node_3_5_few_shot_injection(state: PipelineV2State) -> dict:
    """Node 3.5: Few-Shot Example Injection.

    0 LLM calls. Pure DB + string ops.
    Reads: ticket_type, tenant_id, query
    Writes: few_shot_examples, technique_log
    """
    start = time.time()
    tenant_id = state.get("tenant_id", "")
    query = state.get("query", "")
    ticket_type = state.get("ticket_type", "")
    category = state.get("metadata", {}).get("category") or ticket_type

    if not tenant_id or not query:
        logger.warning("Node 3.5: missing tenant_id or query — skipping")
        return {
            "few_shot_examples": [],
            "technique_log": [{
                "node": "3.5",
                "technique": "FewShotInjection",
                "duration_ms": 0,
                "result_summary": "skipped_missing_inputs",
            }],
        }

    examples: List[Dict[str, Any]] = []
    try:
        from database.base import SessionLocal
        db = SessionLocal()
        try:
            candidates = _fetch_resolved_tickets(
                db=db,
                tenant_id=tenant_id,
                category=category if category else "",
                limit=8,
            )
            examples = _select_top_examples(query, candidates, k=3, min_score=0.05)
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        # Never crash the pipeline — Few-Shot is an enhancement, not a gate
        logger.warning("Node 3.5 failed (non-fatal): %s", exc, exc_info=True)
        return {
            "few_shot_examples": [],
            "technique_log": [{
                "node": "3.5",
                "technique": "FewShotInjection",
                "duration_ms": int((time.time() - start) * 1000),
                "result_summary": f"error: {type(exc).__name__}",
            }],
        }

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 3.5 complete: ticket=%s category=%s candidates=%d selected=%d top_score=%.3f [%dms]",
        state.get("ticket_id", "?"), category or "none",
        len(candidates) if "candidates" in dir() else 0,
        len(examples),
        examples[0]["score"] if examples else 0.0,
        elapsed,
    )

    return {
        "few_shot_examples": examples,
        "technique_log": [{
            "node": "3.5",
            "technique": "FewShotInjection",
            "duration_ms": elapsed,
            "result_summary": f"selected {len(examples)} examples (top_score={examples[0]['score'] if examples else 0:.3f})",
        }],
    }
