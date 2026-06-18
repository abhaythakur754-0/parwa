"""
Node 6: Quality + Format

Question: Is this answer GOOD ENOUGH?

Techniques (in order):
  1. Reflexion.critique()          — "Is this answer actually good?" (LLM)
  2. CRP.revise()                  — rewrite for clarity and accuracy (LLM)
  3. ZeroShotValidator.check()     — statistical check (non-LLM)
  4. GSD.check_parts()             — per-part quality (non-LLM)
  5. ThoT.coherence()              — logical coherence (non-LLM)
  6. ContextualCompression.compress() — remove filler (non-LLM)
  7. FederatedReasoning.aggregate()  — combined quality score (non-LLM)

Quality Score = reflexion*0.30 + crp*0.25 + zero_shot*0.20 + thot*0.15 + gsd*0.10

Decision:
  PASS (>90%)     → send
  FAIL (70-90%)   → loop back to Node 4 (max 2 loops)
  FAIL (after 2)  → Node 8 (Super Node)

LLM calls: 2 (Reflexion + CRP)
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict

from app.core.parwa_pipeline.llm_client import llm_call
from app.core.parwa_pipeline.config import (
    QUALITY_LOOP_THRESHOLD, QUALITY_PASS_THRESHOLD, QUALITY_WEIGHTS,
)
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_6")


# ── Reflexion: Self-critique (LLM) ────────────────────────────────


async def _reflexion_critique(
    query: str, answer: str, knowledge: str
) -> Dict[str, Any]:
    """LLM critiques its own output quality."""
    prompt = f"""You are a quality reviewer for customer support responses.

Original question: "{query}"
Proposed response: {answer}

Knowledge base: {knowledge[:2000]}

Critique this response on these criteria (score each 0-10):
1. ACCURACY: Does the response match the knowledge base?
2. COMPLETENESS: Does it fully address the question?
3. CLARITY: Is the response clear and easy to understand?
4. RELEVANCE: Does it avoid unnecessary information?
5. ACTIONABILITY: Can the customer act on this response?

Respond in format:
ACCURACY: <score>/10
COMPLETENESS: <score>/10
CLARITY: <score>/10
RELEVANCE: <score>/10
ACTIONABILITY: <score>/10
OVERALL: <score>/10
CRITIQUE: <one sentence summary of issues if any>"""

    result = await llm_call(prompt, max_tokens=300)

    # Parse scores
    scores = {}
    for criterion in ["ACCURACY", "COMPLETENESS", "CLARITY", "RELEVANCE", "ACTIONABILITY", "OVERALL"]:
        match = re.search(rf"{criterion}:\s*(\d+)/10", result, re.IGNORECASE)
        if match:
            scores[criterion.lower()] = int(match.group(1)) / 10.0

    overall = scores.get("overall", 0.7)
    critique = ""
    critique_match = re.search(r"CRITIQUE:\s*(.+?)(?:\n|$)", result, re.IGNORECASE)
    if critique_match:
        critique = critique_match.group(1).strip()

    return {"score": overall, "scores": scores, "critique": critique}


# ── CRP: Chain of Revision (LLM) ─────────────────────────────────


async def _crp_revise(
    query: str, answer: str, critique: str, knowledge: str
) -> str:
    """Rewrite the response incorporating the critique."""
    prompt = f"""Improve this customer support response based on the critique.

Original question: "{query}"
Current response: {answer}
Critique: {critique}
Knowledge: {knowledge[:1500]}

Write an improved version that addresses the critique. Be concise and actionable.
Only output the improved response, nothing else."""

    return await llm_call(prompt, max_tokens=500)


# ── ZeroShotValidator: Statistical check (non-LLM) ────────────────


def _zero_shot_check(answer: str, knowledge: str, query: str) -> float:
    """Statistical quality checks on the response."""
    score = 1.0

    # Length check
    if len(answer) < 30:
        score -= 0.3
    elif len(answer) > 5000:
        score -= 0.1  # too verbose

    # Knowledge grounding check
    kb_words = set(knowledge.lower().split())
    ans_words = set(answer.lower().split())
    overlap = len(kb_words & ans_words) / max(len(ans_words), 1)
    if overlap < 0.05:
        score -= 0.3  # answer doesn't use knowledge at all
    elif overlap < 0.15:
        score -= 0.1

    # Repetition check
    sentences = answer.split(".")
    if len(sentences) > 5:
        unique_starts = len(set(s.strip()[:10] for s in sentences if s.strip()))
        if unique_starts < len(sentences) * 0.5:
            score -= 0.1  # repetitive

    # Question address check
    query_words = set(query.lower().split())
    q_overlap = len(query_words & ans_words) / max(len(query_words), 1)
    if q_overlap < 0.1:
        score -= 0.15  # doesn't seem to address the question

    return max(0.0, min(1.0, score))


# ── GSD: Per-part quality check (non-LLM) ─────────────────────────


def _gsd_check_parts(answer: str) -> float:
    """Check quality of each part of a multi-part answer."""
    parts = [p.strip() for p in answer.split("\n\n") if p.strip()]
    if not parts:
        return 0.5

    part_scores = []
    for part in parts:
        score = 1.0
        if len(part) < 20:
            score -= 0.3
        if "?" in part and not any(c in part for c in [".", "!"]):
            score -= 0.2  # question without answer
        part_scores.append(score)

    return sum(part_scores) / len(part_scores)


# ── ThoT: Coherence check (non-LLM) ──────────────────────────────


def _thot_coherence(answer: str) -> float:
    """Check logical coherence of the response."""
    score = 1.0

    # Check for contradictions
    sentences = [s.strip() for s in answer.replace("!", ".").split(".") if s.strip()]

    # Simple heuristic: if "but" or "however" appears, check both sides
    contradiction_words = ["but", "however", "although", "on the other hand"]
    for i, sent in enumerate(sentences):
        for cw in contradiction_words:
            if cw in sent.lower() and i > 0:
                # There's a contrast — check both sides use consistent terms
                prev_words = set(sentences[i - 1].lower().split())
                curr_words = set(sent.lower().split())
                # Not a real contradiction check — Phase 2 will use LLM
                break

    # Check for sentence fragments
    if sentences:
        avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
        if avg_len < 3:
            score -= 0.2

    return max(0.0, min(1.0, score))


# ── ContextualCompression: Remove filler (non-LLM) ────────────────


def _compress_response(answer: str) -> str:
    """Remove filler words and phrases from the response."""
    filler_patterns = [
        r"\bI(?:'d| would) like to (?:let you know that|inform you that)\b",
        r"\b(?:Please note that|Note that)\b",
        r"\b(?:In this case|In this situation)\b",
        r"\b(?:As mentioned above|As stated above)\b",
        r"\b(?:If you have any (?:further|other) (?:questions|concerns))\b[^.]*\.",
        r"\b(?:We (?:are|would be) happy to (?:help|assist) you)\b[^.]*\.",
    ]

    compressed = answer
    for pattern in filler_patterns:
        compressed = re.sub(pattern, "", compressed, flags=re.IGNORECASE)

    # Clean up multiple spaces and blank lines
    compressed = re.sub(r"  +", " ", compressed)
    compressed = re.sub(r"\n{3,}", "\n\n", compressed)
    return compressed.strip()


# ── FederatedReasoning: Aggregate quality signals (non-LLM) ───────


def _federated_quality(
    reflexion: float, crp: float, zero_shot: float, thot: float, gsd: float
) -> Dict[str, Any]:
    """Aggregate quality signals using weighted average."""
    weights = QUALITY_WEIGHTS
    quality_score = (
        reflexion * weights["reflexion"]
        + crp * weights["crp"]
        + zero_shot * weights["zero_shot"]
        + thot * weights["thot_coherence"]
        + gsd * weights["gsd_part_scores"]
    )

    return {
        "quality_score": round(quality_score, 4),
        "details": {
            "reflexion": round(reflexion, 4),
            "crp": round(crp, 4),
            "zero_shot": round(zero_shot, 4),
            "thot_coherence": round(thot, 4),
            "gsd_part_scores": round(gsd, 4),
        },
    }


# ── Main Node Function ────────────────────────────────────────────


async def node_6_quality_format(state: PipelineV2State) -> dict:
    """Node 6: Quality + Format — Is this answer GOOD ENOUGH?"""
    start = time.time()
    query = state["query"]
    answer = state.get("combined_answer", "")
    knowledge_docs = state.get("knowledge_context", [])
    knowledge_str = "\n".join(d.get("content", "") for d in knowledge_docs)
    loop_count = state.get("loop_count", 0)
    logs = []
    llm_calls = 0

    # 1. Reflexion: self-critique (LLM)
    reflexion_result = await _reflexion_critique(query, answer, knowledge_str)
    reflexion_score = reflexion_result["score"]
    logs.append({"node": 6, "technique": "Reflexion", "duration_ms": 0, "result_summary": f"score={reflexion_score:.2f}"})
    llm_calls += 1

    # 2. CRP: revise based on critique (LLM)
    revised = await _crp_revise(query, answer, reflexion_result["critique"], knowledge_str)
    # Score the revised version
    crp_result = await _reflexion_critique(query, revised, knowledge_str)
    crp_score = crp_result["score"]
    logs.append({"node": 6, "technique": "CRP", "duration_ms": 0, "result_summary": f"score={crp_score:.2f}"})
    llm_calls += 2  # one for revise, one for scoring

    # Use the better version
    best_answer = revised if crp_score > reflexion_score else answer

    # 3. ZeroShotValidator: statistical check (non-LLM)
    zero_shot = _zero_shot_check(best_answer, knowledge_str, query)
    logs.append({"node": 6, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"score={zero_shot:.2f}"})

    # 4. GSD: per-part quality (non-LLM)
    gsd_score = _gsd_check_parts(best_answer)
    logs.append({"node": 6, "technique": "GSD", "duration_ms": 0, "result_summary": f"score={gsd_score:.2f}"})

    # 5. ThoT: coherence check (non-LLM)
    thot_score = _thot_coherence(best_answer)
    logs.append({"node": 6, "technique": "ThoT", "duration_ms": 0, "result_summary": f"score={thot_score:.2f}"})

    # 6. ContextualCompression: remove filler (non-LLM)
    compressed = _compress_response(best_answer)
    logs.append({"node": 6, "technique": "ContextualCompression", "duration_ms": 0, "result_summary": f"{len(best_answer)}→{len(compressed)}"})

    # 7. FederatedReasoning: aggregate quality score (non-LLM)
    quality_result = _federated_quality(reflexion_score, crp_score, zero_shot, thot_score, gsd_score)
    quality_score = quality_result["quality_score"]
    quality_passed = quality_score >= QUALITY_PASS_THRESHOLD
    logs.append({"node": 6, "technique": "FederatedReasoning", "duration_ms": 0, "result_summary": f"final={quality_score:.2f} passed={quality_passed}"})

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 6 complete: ticket=%s quality=%.2f passed=%s loop=%d llm=%d [%dms]",
        state["ticket_id"], quality_score, quality_passed, loop_count, llm_calls, elapsed,
    )

    return {
        "quality_score": quality_score,
        "quality_details": quality_result["details"],
        "formatted_response": compressed,
        "quality_passed": quality_passed,
        "combined_answer": compressed,  # update with best version
        "technique_log": logs,
        "node_6_token_usage": llm_calls,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
    }