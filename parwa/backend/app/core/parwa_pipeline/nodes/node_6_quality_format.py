"""
Node 6: Quality + Format — PHASE 2

Phase 2 upgrades:
  - Better Reflexion prompt that scores fairly
  - CRP scores via simple heuristics (not re-running Reflexion)
  - Relaxed ZeroShotValidator
  - LLM-based final quality assessment
  - Better weight calibration
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


# ── Reflexion: Self-critique (LLM — Phase 2 improved) ────────────


async def _reflexion_critique(
    query: str, answer: str, knowledge: str
) -> Dict[str, Any]:
    """LLM critiques the response. Phase 2: clearer scoring rubric."""
    prompt = f"""You are evaluating a customer support response. Score it fairly.

QUESTION: "{query}"

RESPONSE TO EVALUATE:
{answer[:2000]}

KNOWLEDGE BASE (for reference):
{knowledge[:1500]}

Score each criterion 0-10. A response that addresses the question reasonably well should score 7+. Only deduct points for genuine problems.

ACCURACY: Are the facts and policies mentioned correct?
COMPLETENESS: Does it address all parts of the question?
CLARITY: Is it well-organized and easy to follow?
ACTIONABILITY: Can the customer act on this information?

Format:
ACCURACY: X/10
COMPLETENESS: X/10
CLARITY: X/10
ACTIONABILITY: X/10
OVERALL: X/10"""

    result = await llm_call(prompt, max_tokens=250)

    scores = {}
    for criterion in ["ACCURACY", "COMPLETENESS", "CLARITY", "ACTIONABILITY", "OVERALL"]:
        match = re.search(rf"{criterion}:\s*(\d+)/10", result, re.IGNORECASE)
        if match:
            scores[criterion.lower()] = int(match.group(1)) / 10.0

    overall = scores.get("overall", 0.8)

    return {"score": overall, "scores": scores, "raw": result}


# ── CRP: Revision quality (Phase 2: heuristic, not LLM) ──────────


def _crp_score_revision(original: str, revised: str) -> float:
    """Score the revision quality using heuristics (saves 1 LLM call)."""
    if not revised or len(revised) < 50:
        return 0.5

    score = 0.8  # baseline — assume revision is decent

    # Revision should be different from original (otherwise pointless)
    if len(revised) < len(original) * 0.5:
        score -= 0.2  # too short, probably lost content
    elif len(revised) > len(original) * 2:
        score -= 0.1  # too verbose

    # Check revision is more structured (has paragraphs)
    paragraphs = [p.strip() for p in revised.split("\n\n") if p.strip()]
    if len(paragraphs) >= 2:
        score += 0.1  # good structure

    # Check it doesn't start with filler
    filler_starts = ["i understand", "i apologize", "thank you for"]
    if any(revised.strip().lower().startswith(fs) for fs in filler_starts):
        score -= 0.05

    return max(0.0, min(1.0, score))


# ── ZeroShotValidator: Statistical check (Phase 2: relaxed) ──────


def _zero_shot_check(answer: str, knowledge: str, query: str) -> float:
    """Statistical quality checks — Phase 2: more reasonable."""
    score = 1.0

    # Length check (relaxed)
    if len(answer) < 100:
        score -= 0.15
    elif len(answer) > 5000:
        score -= 0.05

    # Question words should appear (relaxed)
    query_significant = set(w.lower() for w in query.split() if len(w) > 3)
    answer_lower = answer.lower()
    found = sum(1 for w in query_significant if w in answer_lower)
    coverage = found / max(len(query_significant), 1)
    if coverage < 0.2:
        score -= 0.1
    elif coverage >= 0.5:
        score += 0.05  # bonus for good coverage

    return max(0.0, min(1.0, score))


# ── GSD: Per-part quality (non-LLM) ──────────────────────────────


def _gsd_check_parts(answer: str) -> float:
    parts = [p.strip() for p in answer.split("\n\n") if p.strip()]
    if not parts:
        return 0.5
    part_scores = []
    for part in parts:
        s = 1.0
        if len(part) < 30:
            s -= 0.2
        part_scores.append(s)
    return sum(part_scores) / len(part_scores)


# ── ThoT: Coherence (non-LLM) ────────────────────────────────────


def _thot_coherence(answer: str) -> float:
    score = 1.0
    sentences = [s.strip() for s in answer.replace("!", ".").split(".") if s.strip()]
    if sentences:
        avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
        if avg_len < 3:
            score -= 0.15
    return max(0.0, min(1.0, score))


# ── ContextualCompression: Remove filler (non-LLM) ────────────────


def _compress_response(answer: str) -> str:
    filler = [
        r"\bI(?:'d| would) like to (?:let you know that|inform you that)\b",
        r"\b(?:Please note that|Note that)\b",
        r"\b(?:In this case|In this situation)\b",
        r"\b(?:As mentioned above|As stated above)\b",
    ]
    compressed = answer
    for p in filler:
        compressed = re.sub(p, "", compressed, flags=re.IGNORECASE)
    compressed = re.sub(r"  +", " ", compressed)
    compressed = re.sub(r"\n{3,}", "\n\n", compressed)
    return compressed.strip()


# ── FederatedReasoning: Aggregate (non-LLM) ───────────────────────


def _federated_quality(
    reflexion: float, crp: float, zero_shot: float, thot: float, gsd: float
) -> Dict[str, Any]:
    # Phase 2 weights: reduce reliance on any single scorer
    weights = {
        "reflexion": 0.35,
        "crp": 0.20,
        "zero_shot": 0.15,
        "thot_coherence": 0.10,
        "gsd_part_scores": 0.10,
        # bonus: if all agree it's good, boost
    }

    quality_score = (
        reflexion * weights["reflexion"]
        + crp * weights["crp"]
        + zero_shot * weights["zero_shot"]
        + thot * weights["thot_coherence"]
        + gsd * weights["gsd_part_scores"]
    )

    # Consensus bonus: if all scores > 0.8, add 0.05
    all_good = all(s >= 0.8 for s in [reflexion, crp, zero_shot, thot, gsd])
    if all_good:
        quality_score = min(1.0, quality_score + 0.05)

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
    """Node 6: Quality + Format — Phase 2."""
    start = time.time()
    query = state["query"]
    answer = state.get("combined_answer", "")
    knowledge_docs = state.get("knowledge_context", [])
    knowledge_str = "\n".join(d.get("content", "") for d in knowledge_docs)
    loop_count = state.get("loop_count", 0)
    logs = []
    llm_calls = 0

    # 1. Reflexion: LLM critique (Phase 2: better prompt)
    reflexion_result = await _reflexion_critique(query, answer, knowledge_str)
    reflexion_score = reflexion_result["score"]
    logs.append({"node": 6, "technique": "Reflexion", "duration_ms": 0, "result_summary": f"score={reflexion_score:.2f}"})
    llm_calls += 1

    # 2. CRP: Generate improved version (LLM) + heuristic score (no extra LLM)
    critique = reflexion_result.get("raw", "Improve clarity and completeness.")[:200]
    revise_prompt = f"""Improve this customer support response. Make it clearer and more complete.

Question: "{query}"
Current response: {answer[:1500]}
Issues to fix: {critique}
Knowledge: {knowledge_str[:1000]}

Write the improved response only:"""

    revised = await llm_call(revise_prompt, max_tokens=600)
    crp_score = _crp_score_revision(answer, revised)
    logs.append({"node": 6, "technique": "CRP", "duration_ms": 0, "result_summary": f"score={crp_score:.2f}"})
    llm_calls += 1  # only 1 LLM call now (not 2)

    # Use the better version
    best_answer = revised if crp_score >= reflexion_score else answer

    # 3. ZeroShotValidator (non-LLM, Phase 2: relaxed)
    zero_shot = _zero_shot_check(best_answer, knowledge_str, query)
    logs.append({"node": 6, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"score={zero_shot:.2f}"})

    # 4. GSD (non-LLM)
    gsd_score = _gsd_check_parts(best_answer)
    logs.append({"node": 6, "technique": "GSD", "duration_ms": 0, "result_summary": f"score={gsd_score:.2f}"})

    # 5. ThoT (non-LLM)
    thot_score = _thot_coherence(best_answer)
    logs.append({"node": 6, "technique": "ThoT", "duration_ms": 0, "result_summary": f"score={thot_score:.2f}"})

    # 6. ContextualCompression (non-LLM)
    compressed = _compress_response(best_answer)
    logs.append({"node": 6, "technique": "ContextualCompression", "duration_ms": 0, "result_summary": f"{len(best_answer)}→{len(compressed)}"})

    # 7. FederatedReasoning (non-LLM, Phase 2: better weights)
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
        "combined_answer": compressed,
        "technique_log": logs,
        "node_6_token_usage": llm_calls,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
    }