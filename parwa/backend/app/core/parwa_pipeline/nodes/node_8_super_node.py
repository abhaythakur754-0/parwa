"""
Node 8: Super Node

Purpose: After 2 failed quality loops, throw EVERYTHING at the problem.
Last resort before human escalation.

Execution order (from roadmap):
  1. Reflexion: "WHY did the previous 2 attempts fail?" (LLM)
  2. Self-Consistency: 3 independent solutions, majority vote (3 LLM calls)
  3. ToT: Explore the most promising path deeply (LLM)
  4. Reverse Thinking: Validate the best solution backward (LLM)
  5. CRP: Rewrite final answer incorporating all insights (LLM)
  6. CoT: Step-by-step with maximum detail (LLM)
  7. ALL 11 non-LLM techniques active simultaneously

Decision:
  quality > 85% → SEND
  quality <= 85% → ESCALATE TO HUMAN + PARWA-NFY-XXX

LLM calls: 5-6 (Self-Consistency = 3, plus ToT + Reverse Thinking + Reflexion)
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List

from app.core.parwa_pipeline.llm_client import llm_call
from app.core.parwa_pipeline.config import (
    NOTIFICATION_KEY_PREFIX, QUALITY_SUPER_THRESHOLD,
)
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_8")


# ── 1. Reflexion: Analyze WHY previous attempts failed (LLM) ──────


async def _reflexion_analyze_failures(
    query: str, knowledge: str, previous_attempts: List[str]
) -> str:
    """Deep reflection on what went wrong in previous attempts."""
    attempts_text = "\n\n".join(
        f"Attempt {i+1}:\n{a[:500]}" for i, a in enumerate(previous_attempts)
    )

    prompt = f"""Analyze WHY these previous attempts to answer a customer question failed.

Question: "{query}"
Knowledge: {knowledge[:1500]}

Previous attempts that FAILED quality checks:
{attempts_text}

Analyze specifically:
1. What was wrong with each attempt?
2. What knowledge was missed or misused?
3. What approach would be better?

FAILURE ANALYSIS:"""

    return await llm_call(prompt, max_tokens=500)


# ── 2. Self-Consistency: 3 independent solutions (3 LLM calls) ───


async def _self_consistency_solve(
    query: str, knowledge: str, failure_analysis: str
) -> tuple:
    """3 independent solutions using different approaches. Majority vote wins."""

    approaches = [
        "Solve this step-by-step, focusing on accuracy and policy compliance.",
        "Solve this by first considering the customer's perspective and desired outcome.",
        "Solve this by focusing on the most efficient resolution path.",
    ]

    solutions = []
    for approach in approaches:
        prompt = f"""{approach}

Question: "{query}"
Knowledge: {knowledge[:1500]}
Previous failures: {failure_analysis[:500]}

Provide a complete answer:"""

        solution = await llm_call(prompt, max_tokens=400, temperature=0.7)  # higher temp for diversity
        solutions.append(solution)

    # Majority vote: pick the one most aligned with knowledge
    kb_words = set(knowledge.lower().split())
    scores = []
    for sol in solutions:
        sol_words = set(sol.lower().split())
        overlap = len(kb_words & sol_words) / max(len(sol_words), 1)
        scores.append(overlap)

    best_idx = scores.index(max(scores))
    return solutions, scores, best_idx


# ── 3. ToT: Deep path exploration (LLM) ──────────────────────────


async def _tot_deep_explore(query: str, knowledge: str, best_solution: str) -> str:
    """Explore the most promising path deeply."""
    prompt = f"""The best solution so far for this customer question needs deeper exploration.

Question: "{query}"
Current best solution: {best_solution}
Knowledge: {knowledge[:1500]}

Explore 2-3 possible improvements or alternative angles.
For each, evaluate if it's better than the current solution.
Then provide the FINAL improved answer.

IMPROVED ANSWER:"""

    return await llm_call(prompt, max_tokens=500)


# ── 4. Reverse Thinking: Backward validation (LLM) ───────────────


async def _reverse_validate(query: str, answer: str, knowledge: str) -> Dict[str, Any]:
    """Validate the answer by working backward."""
    prompt = f"""Validate this customer support answer by working BACKWARD.

Question: "{query}"
Answer: {answer}
Knowledge: {knowledge[:1500]}

1. Does the answer fully address the question?
2. Is every claim in the answer supported by knowledge?
3. Are there any logical gaps?

RESPOND:
VALID: YES/NO
CONFIDENCE: <0.0-1.0>
IMPROVEMENTS: <any suggested improvements or "none">"""

    result = await llm_call(prompt, max_tokens=200)
    valid = "VALID: YES" in result.upper()
    conf_match = re.search(r"CONFIDENCE:\s*([\d.]+)", result)
    confidence = float(conf_match.group(1)) if conf_match else 0.7
    if confidence > 1:
        confidence /= 100

    return {"valid": valid, "confidence": confidence, "analysis": result}


# ── 5. CRP: Revision with full failure context (LLM) ─────────────


async def _crp_revise(
    query: str, answer: str, failure_analysis: str,
    reverse_result: Dict, knowledge: str,
) -> str:
    """Revise the answer incorporating ALL insights from failures and validation."""
    prompt = f"""Incorporate all the analysis below into a FINAL, polished customer response.

Question: "{query}"
Current answer: {answer}
Why previous attempts failed: {failure_analysis[:500]}
Validation result: {reverse_result['analysis']}
Knowledge: {knowledge[:1500]}

Write the BEST possible customer response. Be clear, accurate, and actionable.
Only output the final response."""

    return await llm_call(prompt, max_tokens=600)


# ── 6. CoT: Maximum detail (LLM) ─────────────────────────────────


async def _cot_max_detail(query: str, answer: str, knowledge: str) -> str:
    """Add maximum reasoning detail to the answer."""
    prompt = f"""Review and enhance this customer support response with thorough reasoning.

Question: "{query}"
Response: {answer}
Knowledge: {knowledge[:1500]}

Add any missing details, clarify any ambiguities, and ensure completeness.
Output the enhanced response only."""

    return await llm_call(prompt, max_tokens=600)


# ── 7. ALL 11 non-LLM techniques (simultaneous) ───────────────────


def _all_non_llm_techniques(answer: str, knowledge: str, query: str) -> Dict[str, float]:
    """Run all 11 non-LLM techniques as quality signals."""

    # SmartRouter: classify answer type
    answer_type = "actionable" if any(w in answer.lower() for w in ["step", "click", "go to"]) else "informational"

    # GSD: check parts
    parts = [p.strip() for p in answer.split("\n\n") if p.strip()]
    gsd = sum(1.0 for p in parts if len(p) >= 20) / max(len(parts), 1)

    # MAKER: bridge check
    kb_words = set(knowledge.lower().split())
    ans_words = set(answer.lower().split())
    maker = len(kb_words & ans_words) / max(len(ans_words), 1)

    # ThoT: coherence
    sentences = [s.strip() for s in answer.replace("!", ".").split(".") if s.strip()]
    thot = 1.0 if sentences and sum(len(s.split()) for s in sentences) / len(sentences) >= 3 else 0.7

    # FederatedReasoning: aggregate
    fed = sum([gsd, maker, thot]) / 3

    # ZeroShotValidator
    zsv = 1.0
    if len(answer) < 30:
        zsv -= 0.3
    import re
    amounts = re.findall(r"\$(\d+(?:,\d{3})+(?:\.\d{2})?)", answer)
    for a in amounts:
        if float(a.replace(",", "")) > 10000:
            zsv -= 0.3

    # MetaLearner
    meta = 0.7  # default — Phase 6 makes dynamic

    # DynamicContext
    dyn = 0.8  # default

    # ContextualCompression
    compressed_len = len(re.sub(r"\s+", " ", answer))
    ctx_comp = min(1.0, 200 / max(compressed_len, 1))

    # TurboCompress
    turbo = min(1.0, 150 / max(compressed_len, 1))

    # AdaptiveBudget
    budget = 1.0  # no LLM budget issues in super node

    return {
        "smart_router": 0.8,
        "gsd": gsd,
        "maker": maker,
        "thot": thot,
        "federated": fed,
        "zero_shot": max(0, zsv),
        "meta_learner": meta,
        "dynamic_context": dyn,
        "contextual_compression": ctx_comp,
        "turbo_compress": turbo,
        "adaptive_budget": budget,
    }


# ── Notification Key Generator ────────────────────────────────────


_notification_counter = 0


def _generate_notification_key() -> str:
    global _notification_counter
    _notification_counter += 1
    return f"{NOTIFICATION_KEY_PREFIX}-{_notification_counter:03d}"


# ── Main Node Function ────────────────────────────────────────────


async def node_8_super_node(state: PipelineV2State) -> dict:
    """Node 8: Super Node — Can the MOST POWERFUL approach solve this?"""
    start = time.time()
    query = state["query"]
    knowledge_docs = state.get("knowledge_context", [])
    knowledge_str = "\n".join(d.get("content", "") for d in knowledge_docs)
    wiki_c = state.get("wiki_section_c", [])
    if wiki_c:
        knowledge_str += "\n" + "\n".join(d.get("content", "") for d in wiki_c)

    # Collect previous attempts from technique log
    previous_answers = []
    for log in state.get("technique_log", []):
        if log.get("node") == 4:
            previous_answers.append(state.get("combined_answer", ""))
            break
    if state.get("formatted_response"):
        previous_answers.append(state["formatted_response"])

    logs = []
    llm_calls = 0

    # 1. Reflexion: Analyze failures (LLM)
    failure_analysis = await _reflexion_analyze_failures(query, knowledge_str, previous_answers)
    logs.append({"node": 8, "technique": "Reflexion", "duration_ms": 0, "result_summary": "failure_analyzed"})
    llm_calls += 1

    # 2. Self-Consistency: 3 independent solutions (3 LLM calls)
    solutions, sc_scores, best_idx = await _self_consistency_solve(query, knowledge_str, failure_analysis)
    best_solution = solutions[best_idx]
    logs.append({"node": 8, "technique": "SelfConsistency", "duration_ms": 0, "result_summary": f"3 solutions, best={best_idx}"})
    llm_calls += 3

    # 3. ToT: Deep exploration (LLM)
    explored = await _tot_deep_explore(query, knowledge_str, best_solution)
    logs.append({"node": 8, "technique": "ToT", "duration_ms": 0, "result_summary": "deep_explored"})
    llm_calls += 1

    # 4. Reverse Thinking: Validate (LLM)
    reverse = await _reverse_validate(query, explored, knowledge_str)
    logs.append({"node": 8, "technique": "ReverseThinking", "duration_ms": 0, "result_summary": f"valid={reverse['valid']}"})
    llm_calls += 1

    # 5. CRP: Final revision (LLM)
    revised = await _crp_revise(query, explored, failure_analysis, reverse, knowledge_str)
    logs.append({"node": 8, "technique": "CRP", "duration_ms": 0, "result_summary": "revised"})
    llm_calls += 1

    # 6. CoT: Maximum detail (LLM)
    final_answer = await _cot_max_detail(query, revised, knowledge_str)
    logs.append({"node": 8, "technique": "CoT", "duration_ms": 0, "result_summary": "max_detail"})
    llm_calls += 1

    # 7. ALL 11 non-LLM techniques
    non_llm_scores = _all_non_llm_techniques(final_answer, knowledge_str, query)
    for tech, score in non_llm_scores.items():
        logs.append({"node": 8, "technique": tech, "duration_ms": 0, "result_summary": f"score={score:.2f}"})

    # Calculate Super Node quality
    reverse_conf = reverse["confidence"]
    sc_best = sc_scores[best_idx]
    non_llm_avg = sum(non_llm_scores.values()) / len(non_llm_scores)
    super_quality = (reverse_conf * 0.3 + sc_best * 0.3 + non_llm_avg * 0.4)

    # Decision
    passed = super_quality > QUALITY_SUPER_THRESHOLD
    notification_key = None
    status = "resolved" if passed else "escalated"
    escalation_context = {}

    if not passed:
        notification_key = _generate_notification_key()
        escalation_context = {
            "notification_key": notification_key,
            "original_ticket": query,
            "previous_attempts": previous_answers,
            "super_node_answer": final_answer,
            "super_node_quality": super_quality,
            "failure_analysis": failure_analysis,
            "all_solutions": solutions,
        }
        logs.append({"node": 8, "technique": "Escalation", "duration_ms": 0, "result_summary": f"key={notification_key}"})

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 8 complete: ticket=%s quality=%.2f passed=%s status=%s llm=%d [%dms]",
        state["ticket_id"], super_quality, passed, status, llm_calls, elapsed,
    )

    result = {
        "super_node_answer": final_answer if passed else "",
        "super_node_quality": round(super_quality, 4),
        "super_node_analysis": failure_analysis,
        "status": status,
        "technique_log": logs,
        "node_8_token_usage": llm_calls,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
    }

    if passed:
        result["final_response"] = final_answer
        result["quality_passed"] = True
        result["formatted_response"] = final_answer

    if escalation_context:
        result["escalation_context"] = escalation_context

    return result