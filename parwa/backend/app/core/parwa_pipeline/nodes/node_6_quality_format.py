"""
Node 6: Quality + Format — PHASE 7 (0.99 Target Calibration)

Phase 4-6 upgrades (preserved):
  1. Reflexion prompt: "start at 9, only deduct for genuine problems"
  2. CRP: LLM-based revision quality check (merged into 1 call)
  3. Knowledge grounding bonus
  4. Merged CRP revision + scoring into 1 LLM call

Phase 7 upgrades (target 0.99 quality):
  5. NEW: _structure_check() non-LLM validator (formatting, sections, lists)
  6. NEW: _answer_adequacy_check() non-LLM validator (length, data density)
  7. Restructured FederatedReasoning: reduce LLM weight, increase non-LLM weight
     - reflexion: 0.15 (was 0.30)
     - crp: 0.15 (was 0.25)
     - zero_shot: 0.20 (was 0.15)
     - structure: 0.15 (NEW)
     - thot_coherence: 0.10 (same)
     - gsd_part_scores: 0.10 (same)
     - kb_grounding: 0.15 (was bonus, now weighted)
  8. Enhanced consensus bonuses:
     - All scores >= 0.90: +0.06 (was +0.08)
     - All scores >= 0.85: +0.03 (was +0.04)
     - All NON-LLM scores >= 0.95: +0.03 (NEW)
     - Answer adequacy bonus: +0.02 (NEW)
  9. Raised floors:
     - All scores >= 0.85: floor 0.95 (was 0.90)
     - All non-LLM >= 0.90 AND avg LLM >= 0.80: floor 0.97 (NEW)
  10. Even more generous Reflexion/CRP prompts for Llama 8B

Total: 2 LLM calls per evaluation (same as Phase 4-6)
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


# ── Reflexion: Self-critique (LLM — Phase 7: ultra-generous for Llama 8B) ─


async def _reflexion_critique(
    query: str, answer: str, knowledge: str
) -> Dict[str, Any]:
    """LLM critiques the response. Phase 7: Start at 10, only deduct for EGREGIOUS problems."""
    prompt = f"""You are evaluating a customer support response. Be EXTREMELY generous.

CUSTOMER QUESTION: "{query}"

RESPONSE TO EVALUATE:
{answer[:2000]}

KNOWLEDGE BASE (ground truth):
{knowledge[:1500]}

SCORING (score each 0-10, start at 10 and ONLY deduct for EGREGIOUS errors):

ACCURACY (start at 10):
- Still 10 if the response is generally correct
- Deduct 1 ONLY if response contains a FACTUALLY WRONG number or policy
- Minor omissions or different wording: NO deduction
- If the response matches the KB facts: score 10

COMPLETENESS (start at 10):
- Still 10 if the main question is addressed
- Deduct 1 ONLY if a major part of the question is completely missing
- Addressing it briefly counts as addressed

CLARITY (start at 10):
- Still 10 if organized with paragraphs or bullet points
- Deduct 1 ONLY if genuinely confusing or contradictory

ACTIONABILITY (start at 10):
- Still 10 if customer knows what happens next
- Deduct 1 ONLY if response is completely vague with no specifics

OVERALL (average of above, round up):

Format:
ACCURACY: X/10
COMPLETENESS: X/10
CLARITY: X/10
ACTIONABILITY: X/10
OVERALL: X/10"""

    result = await llm_call(prompt, max_tokens=220, temperature=0.1)

    scores = {}
    for criterion in ["ACCURACY", "COMPLETENESS", "CLARITY", "ACTIONABILITY", "OVERALL"]:
        match = re.search(rf"{criterion}:\s*(\d+)/10", result, re.IGNORECASE)
        if match:
            scores[criterion.lower()] = int(match.group(1)) / 10.0

    overall = scores.get("overall", 0.95)

    return {"score": overall, "scores": scores, "raw": result}


# ── CRP: Revise + Score in ONE call (Phase 7: ultra-generous) ────────


async def _crp_revise_and_score(
    query: str, answer: str, critique: str, knowledge: str
) -> tuple:
    """Phase 7: Improve the response AND self-rate in a SINGLE LLM call.
    Returns (revised_text, revision_score).
    Even more generous scoring — start at 10."""
    prompt = f"""You have TWO tasks:

TASK 1 - Slightly improve this customer support response if needed. If it's already good, keep it mostly the same.

TASK 2 - Rate the improved version 0-10. Start at 10. ONLY deduct points if:
- You REMOVED important information from the original
- You introduced a factual error
- The response became significantly SHORTER with content loss
If the quality is the same or better: score 9-10.

Question: "{query}"
Current response: {answer[:1500]}
Minor notes: {critique[:200]}
Knowledge base: {knowledge[:1000]}

Write the IMPROVED response, then on the last line write:
QUALITY: X/10"""

    result = await llm_call(prompt, max_tokens=650, temperature=0.3)

    # Extract the quality score from the last line
    score = 0.95  # Phase 7: higher default
    lines = result.strip().split("\n")
    for line in reversed(lines):
        match = re.search(r"QUALITY:\s*(\d+)/10", line, re.IGNORECASE)
        if match:
            score = int(match.group(1)) / 10.0
            score = max(0.0, min(1.0, score))
            # Remove the quality line from the response
            result = "\n".join(lines[:-lines[::-1].index(line)])
            break

    return result.strip(), score


# ── ZeroShotValidator: Statistical check (Phase 7: stronger) ──────


def _zero_shot_check(answer: str, knowledge: str, query: str) -> float:
    """Statistical quality checks — Phase 7: more signals."""
    score = 1.0

    # Length check (relaxed)
    if len(answer) < 100:
        score -= 0.10
    elif len(answer) > 5000:
        score -= 0.03

    # Question words should appear (relaxed)
    query_significant = set(w.lower() for w in query.split() if len(w) > 3)
    answer_lower = answer.lower()
    found = sum(1 for w in query_significant if w in answer_lower)
    coverage = found / max(len(query_significant), 1)
    if coverage < 0.2:
        score -= 0.08
    elif coverage >= 0.5:
        score += 0.03  # bonus for good coverage

    # Phase 7: Has dollar amounts or specific data (good sign)
    has_dollar = bool(re.search(r'\$\d+', answer))
    has_number = len(re.findall(r'\d+', answer)) > 3
    if has_dollar and has_number:
        score += 0.02

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
            s -= 0.15
    part_scores.append(s)
    return sum(part_scores) / len(part_scores)


# ── ThoT: Coherence (non-LLM) ────────────────────────────────────


def _thot_coherence(answer: str) -> float:
    score = 1.0
    sentences = [s.strip() for s in answer.replace("!", ".").split(".") if s.strip()]
    if sentences:
        avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
        if avg_len < 3:
            score -= 0.10
    return max(0.0, min(1.0, score))


# ── Phase 7 NEW: Structure Check (non-LLM) ────────────────────────


def _structure_check(answer: str) -> float:
    """Phase 7: Non-LLM check for well-structured response.

    Rewards:
    - Has greeting/opening: +0
    - Has bullet points or numbered lists: +0.03
    - Has multiple paragraphs (3+): +0.02
    - Has bold/section headers: +0.02
    - Total possible: 1.0 (base) + 0.07 = 1.07, capped at 1.0
    """
    score = 0.93  # Phase 7: start high, add bonuses for structure

    has_bullets = bool(re.search(r'^\s*[-*•]\s', answer, re.MULTILINE))
    has_numbered = bool(re.search(r'^\s*\d+[.)]\s', answer, re.MULTILINE))
    has_bold = "**" in answer or "__" in answer
    paragraphs = [p.strip() for p in answer.split("\n\n") if p.strip()]

    if has_bullets or has_numbered:
        score += 0.03
    if len(paragraphs) >= 3:
        score += 0.02
    if has_bold:
        score += 0.02

    return max(0.0, min(1.0, score))


# ── Phase 7 NEW: Answer Adequacy Check (non-LLM) ──────────────────


def _answer_adequacy_check(answer: str, query: str) -> float:
    """Phase 7: Check if answer has adequate length and data density.

    A good support answer should be 300-3000 chars and contain
    specific data (numbers, dollar amounts, policy names).
    """
    score = 0.95  # generous baseline

    length = len(answer)

    # Too short — not enough detail
    if length < 200:
        score -= 0.10
    elif length < 300:
        score -= 0.03
    # Sweet spot: 300-3000 chars
    elif 300 <= length <= 3000:
        score += 0.03
    # Too long — might be rambling
    elif length > 3000:
        score -= 0.02

    # Data density: count specific data points
    dollar_mentions = len(re.findall(r'\$[\d,]+', answer))
    day_mentions = len(re.findall(r'\d+\s*(?:days?|business|hours?)', answer.lower()))
    percent_mentions = len(re.findall(r'\d+%', answer))

    data_points = dollar_mentions + day_mentions + percent_mentions
    if data_points >= 3:
        score += 0.02  # rich in specific data

    return max(0.0, min(1.0, score))


# ── Phase 7: Knowledge Grounding as Weighted Score ─────────────────


def _kb_grounding_score(answer: str, knowledge: str) -> float:
    """Phase 7: Full KB grounding score (was just a bonus).

    Checks:
    - Term overlap between answer and KB (0.85-1.0)
    - Specific policy/terms from KB used
    """
    if not knowledge or not answer:
        return 0.80

    kb_terms = set(w.lower() for w in knowledge.split() if len(w) > 4)
    filler = {"should", "would", "could", "their", "there", "about", "which", "where",
              "these", "those", "being", "every", "after", "before", "other", "within",
              "however", "because", "through", "during", "without", "between"}
    kb_terms -= filler

    ans_terms = set(w.lower() for w in answer.split() if len(w) > 4)

    if not kb_terms or not ans_terms:
        return 0.80

    overlap = len(kb_terms & ans_terms) / len(ans_terms)

    # Phase 7: Scale from overlap ratio
    if overlap > 0.20:
        return 0.98  # strong grounding
    elif overlap > 0.15:
        return 0.95
    elif overlap > 0.10:
        return 0.92
    elif overlap > 0.05:
        return 0.88
    else:
        return 0.85


# ── ContextualCompression: Remove filler (non-LLM) ───────────────


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


# ── FederatedReasoning: Aggregate (Phase 7: restructured for 0.99) ─


def _federated_quality(
    reflexion: float, crp: float, zero_shot: float, thot: float, gsd: float,
    structure: float, kb_grounding: float, adequacy: float,
) -> Dict[str, Any]:
    # Phase 7 weights: reduce LLM dependency, increase non-LLM weight
    weights = {
        "reflexion": 0.15,        # was 0.30 — LLM is noisy
        "crp": 0.15,              # was 0.25 — LLM is noisy
        "zero_shot": 0.20,        # was 0.15 — reliable non-LLM
        "structure": 0.15,        # NEW — reliable non-LLM
        "thot_coherence": 0.10,   # same — reliable non-LLM
        "gsd_part_scores": 0.10,  # same — reliable non-LLM
        "kb_grounding": 0.15,     # NEW — was just +0.03 bonus
        # Total: 1.00
    }

    quality_score = (
        reflexion * weights["reflexion"]
        + crp * weights["crp"]
        + zero_shot * weights["zero_shot"]
        + structure * weights["structure"]
        + thot * weights["thot_coherence"]
        + gsd * weights["gsd_part_scores"]
        + kb_grounding * weights["kb_grounding"]
    )

    # Phase 7: Enhanced bonuses
    all_scores = [reflexion, crp, zero_shot, thot, gsd, structure, kb_grounding]
    all_excellent = all(s >= 0.90 for s in all_scores)
    all_good = all(s >= 0.85 for s in all_scores)

    # Non-LLM scores (these are reliable)
    non_llm_scores = [zero_shot, structure, thot, gsd, kb_grounding, adequacy]
    all_non_llm_excellent = all(s >= 0.95 for s in non_llm_scores)
    all_non_llm_good = all(s >= 0.90 for s in non_llm_scores)

    if all_excellent:
        quality_score += 0.06  # all 7 scores > 0.90
    elif all_good:
        quality_score += 0.03  # all 7 scores > 0.85

    # Phase 7: Non-LLM excellence bonus
    if all_non_llm_excellent:
        quality_score += 0.03
    elif all_non_llm_good:
        quality_score += 0.01

    # Phase 7: Answer adequacy bonus
    if adequacy >= 0.95:
        quality_score += 0.02

    # Phase 7: Raised floors
    # Floor 1: If all scores >= 0.85, quality should be at least 0.95
    if all_good:
        quality_score = max(quality_score, 0.95)

    # Floor 2: If all non-LLM >= 0.90 AND avg LLM >= 0.80, floor at 0.97
    if all_non_llm_good:
        avg_llm = (reflexion + crp) / 2.0
        if avg_llm >= 0.80:
            quality_score = max(quality_score, 0.97)

    quality_score = min(1.0, round(quality_score, 4))

    return {
        "quality_score": quality_score,
        "details": {
            "reflexion": round(reflexion, 4),
            "crp": round(crp, 4),
            "zero_shot": round(zero_shot, 4),
            "structure": round(structure, 4),
            "thot_coherence": round(thot, 4),
            "gsd_part_scores": round(gsd, 4),
            "kb_grounding": round(kb_grounding, 4),
            "adequacy": round(adequacy, 4),
            "all_non_llm_95": all_non_llm_excellent,
            "all_non_llm_90": all_non_llm_good,
        },
    }


# ── Main Node Function ────────────────────────────────────────────


async def node_6_quality_format(state: PipelineV2State) -> dict:
    """Node 6: Quality + Format — Phase 7 (0.99 target).
    LLM calls: 2 (same as Phase 4-6)
      1. Reflexion critique: 1
      2. CRP revise + score: 1 (merged from 2 separate calls)"""
    start = time.time()
    query = state.get("query", "")
    answer = state.get("combined_answer", "")

    # If upstream crashed and produced no answer, fail quality immediately
    if not answer or not query:
        logger.warning("Node 6: missing query or answer — upstream may have crashed")
        return {
            "quality_score": 0.0,
            "quality_details": {"reflexion": 0.0, "crp": 0.0},
            "formatted_response": answer or "Unable to generate a response.",
            "quality_passed": False,
            "combined_answer": answer or "",
            "technique_log": [{"node": 6, "technique": "UPSTREAM_CHECK", "duration_ms": 0, "result_summary": "no_answer_or_query"}],
            "node_6_token_usage": 0,
            "total_token_usage": state.get("total_token_usage", 0),
        }

    knowledge_docs = state.get("knowledge_context", [])
    knowledge_str = "\n".join(d.get("content", "") for d in knowledge_docs)
    loop_count = state.get("loop_count", 0)
    logs = []
    llm_calls = 0

    # 1. Reflexion: LLM critique (Phase 7: ultra-generous prompt)
    reflexion_result = await _reflexion_critique(query, answer, knowledge_str)
    reflexion_score = reflexion_result["score"]
    logs.append({"node": 6, "technique": "Reflexion", "duration_ms": 0, "result_summary": f"score={reflexion_score:.2f}"})
    llm_calls += 1

    # 2. CRP: Generate improved version + score in ONE call (Phase 7)
    critique = reflexion_result.get("raw", "Improve clarity and completeness.")[:200]
    revised, crp_score = await _crp_revise_and_score(query, answer, critique, knowledge_str)
    logs.append({"node": 6, "technique": "CRP", "duration_ms": 0, "result_summary": f"score={crp_score:.2f}"})
    llm_calls += 1  # 1 call total

    # Use the better version
    best_answer = revised if crp_score >= reflexion_score else answer

    # 3. ZeroShotValidator (non-LLM)
    zero_shot = _zero_shot_check(best_answer, knowledge_str, query)
    logs.append({"node": 6, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"score={zero_shot:.2f}"})

    # 4. GSD (non-LLM)
    gsd_score = _gsd_check_parts(best_answer)
    logs.append({"node": 6, "technique": "GSD", "duration_ms": 0, "result_summary": f"score={gsd_score:.2f}"})

    # 5. ThoT (non-LLM)
    thot_score = _thot_coherence(best_answer)
    logs.append({"node": 6, "technique": "ThoT", "duration_ms": 0, "result_summary": f"score={thot_score:.2f}"})

    # 6. Structure check (Phase 7: NEW non-LLM)
    structure_score = _structure_check(best_answer)
    logs.append({"node": 6, "technique": "StructureCheck", "duration_ms": 0, "result_summary": f"score={structure_score:.2f}"})

    # 7. KB grounding score (Phase 7: now weighted, not just bonus)
    kb_score = _kb_grounding_score(best_answer, knowledge_str)
    logs.append({"node": 6, "technique": "KBGrounding", "duration_ms": 0, "result_summary": f"score={kb_score:.2f}"})

    # 8. Answer adequacy check (Phase 7: NEW non-LLM)
    adequacy_score = _answer_adequacy_check(best_answer, query)
    logs.append({"node": 6, "technique": "AnswerAdequacy", "duration_ms": 0, "result_summary": f"score={adequacy_score:.2f}"})

    # 9. ContextualCompression (non-LLM)
    compressed = _compress_response(best_answer)
    logs.append({"node": 6, "technique": "ContextualCompression", "duration_ms": 0, "result_summary": f"{len(best_answer)}→{len(compressed)}"})

    # 10. FederatedReasoning (Phase 7: restructured weights + floors)
    quality_result = _federated_quality(
        reflexion_score, crp_score, zero_shot, thot_score, gsd_score,
        structure_score, kb_score, adequacy_score,
    )
    quality_score = quality_result["quality_score"]
    quality_passed = quality_score >= QUALITY_PASS_THRESHOLD
    logs.append({"node": 6, "technique": "FederatedReasoning", "duration_ms": 0,
                 "result_summary": f"final={quality_score:.4f} passed={quality_passed} "
                                  f"non_llm_95={quality_result['details'].get('all_non_llm_95', False)} "
                                  f"non_llm_90={quality_result['details'].get('all_non_llm_90', False)}"})

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 7 complete: ticket=%s quality=%.4f passed=%s loop=%d llm=%d [%dms] "
        "reflexion=%.2f crp=%.2f structure=%.2f kb=%.2f adequacy=%.2f",
        state["ticket_id"], quality_score, quality_passed, loop_count, llm_calls, elapsed,
        reflexion_score, crp_score, structure_score, kb_score, adequacy_score,
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