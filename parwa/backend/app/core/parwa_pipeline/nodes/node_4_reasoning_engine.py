"""
Node 4: Reasoning Engine — PHASE 2
The BRAIN — 4-Layer Architecture

Phase 2 upgrades:
  - LLM-based GSD decomposition (not just regex)
  - Better CoT prompts with knowledge grounding
  - LLM-based answer synthesis instead of fragment extraction
  - Reduced redundant calls
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List

from app.core.parwa_pipeline.llm_client import llm_call, parse_confidence
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_4")


# ── GSD: Goal Sub-Goal Decomposition (LLM — Phase 2) ────────────


async def _gsd_decompose(query: str, ticket_type: str, knowledge: str) -> List[str]:
    """LLM-based decomposition — understands the ACTUAL query."""
    prompt = f"""Break this customer support question into 2-4 specific sub-problems that need to be solved.
Each sub-problem should be actionable and addressable with the available knowledge.

Question: "{query}"
Type: {ticket_type}
Available knowledge areas: {knowledge[:500]}

List the sub-problems, one per line:"""

    result = await llm_call(prompt, max_tokens=200)
    problems = [line.strip() for line in result.split("\n") if line.strip() and len(line.strip()) > 10]
    # Remove numbering prefixes
    cleaned = [re.sub(r'^[\d.\)-]+\s*', '', p) for p in problems]
    return cleaned[:4] if cleaned else [
        "Understand the customer's core request",
        "Find the relevant information and policies",
        "Provide a clear, actionable answer",
    ]


# ── Least-to-Most: Order sub-problems (LLM) ───────────────────────


async def _least_to_most_order(sub_problems: List[str], knowledge: str) -> List[str]:
    """Order sub-problems from easiest to hardest."""
    if len(sub_problems) <= 1:
        return sub_problems

    prompt = f"""Order these sub-problems from EASIEST to HARDEST.
{chr(10).join(f'{i+1}. {p}' for i, p in enumerate(sub_problems))}

Return in order (easiest first), one per line:"""

    result = await llm_call(prompt, max_tokens=150)
    ordered = [line.strip() for line in result.split("\n") if line.strip()]
    return ordered if len(ordered) >= len(sub_problems) - 1 else sub_problems


# ── MAKER: Bridge knowledge gaps (non-LLM) ────────────────────────


def _maker_bridge(sub_problems: List[str], knowledge: str) -> Dict[str, str]:
    """Bridge knowledge gaps between sub-problems."""
    bridges = {}
    knowledge_lower = knowledge.lower()
    for sp in sub_problems:
        words = [w for w in sp.lower().split() if len(w) > 4]
        relevant = []
        for i, line in enumerate(knowledge_lower.split(".")):
            if any(w in line for w in words):
                relevant.append(f"section {i}")
        bridges[sp] = " → ".join(relevant) if relevant else "general knowledge"
    return bridges


# ── CoT: Step-by-step reasoning (LLM — Phase 2 improved) ─────────


async def _cot_solve(sub_problem: str, knowledge: str, context: str, query: str) -> str:
    """Solve one sub-problem with knowledge-grounded reasoning."""
    prompt = f"""You are a senior customer support agent. Solve this sub-problem using the available knowledge.

SUB-PROBLEM: {sub_problem}

ORIGINAL CUSTOMER QUESTION: "{query}"

KNOWLEDGE BASE:
{knowledge[:3000]}

CUSTOMER CONTEXT: {context[:300]}

Instructions:
- Reference specific policies, numbers, and timelines from the knowledge base
- Be thorough and specific — include exact amounts, timeframes, and processes
- Address the sub-problem completely

Solution:"""

    return await llm_call(prompt, max_tokens=500)


# ── ToT: Explore alternatives (LLM — Phase 2 simplified) ──────────


async def _tot_explore(sub_problem: str, knowledge: str, cot_solution: str) -> str:
    """Quick check if CoT solution missed anything important."""
    prompt = f"""Review this solution for completeness.

Sub-problem: {sub_problem}
Solution: {cot_solution}

Knowledge: {knowledge[:1500]}

Did the solution miss anything important? If it's complete, say "COMPLETE".
If something is missing, briefly state what's missing."""

    return await llm_call(prompt, max_tokens=150)


# ── GST: Track progress (non-LLM) ────────────────────────────────


def _gst_track(sub_problems: List[str], solutions: List[str]) -> str:
    solved = sum(1 for s in solutions if s and "cannot" not in s.lower() and len(s) > 50)
    return f"{solved}/{len(sub_problems)} sub-problems solved"


# ── Reverse Thinking: Validate backward (LLM) ─────────────────────


async def _reverse_thinking_validate(query: str, combined_answer: str, knowledge: str) -> Dict[str, Any]:
    """Work backward from answer to validate."""
    prompt = f"""Validate this customer support answer.

Question: "{query}"
Answer: {combined_answer[:1500]}

Knowledge: {knowledge[:1000]}

Does the answer correctly address the question using the knowledge?
Is anything factually wrong or missing?

VALID: YES/NO
CONFIDENCE: <0.0-1.0>"""

    result = await llm_call(prompt, max_tokens=100)
    valid = "VALID: YES" in result.upper()
    confidence = parse_confidence(result, default=0.8)
    return {"valid": valid, "confidence": confidence, "analysis": result}


# ── ZeroShotValidator: Statistical check (non-LLM) ────────────────


def _zero_shot_validate(answer: str, knowledge: str) -> float:
    score = 1.0
    if len(answer) < 50:
        score -= 0.2
    if len(answer) > 5000:
        score -= 0.05
    # Check for suspicious amounts (relaxed)
    amounts = re.findall(r"\$(\d+(?:,\d{3})*(?:\.\d{2})?)", answer)
    for amt_str in amounts:
        amt = float(amt_str.replace(",", ""))
        if amt > 100000:
            score -= 0.2
    return max(0.0, min(1.0, score))


# ── ThoT: Thread solutions (non-LLM) ──────────────────────────────


def _thot_thread(sub_problems: List[str], solutions: List[str]) -> str:
    parts = []
    for sp, sol in zip(sub_problems, solutions):
        if sol:
            parts.append(f"**{sp}**\n{sol}")
    return "\n\n".join(parts)


# ── FederatedReasoning: Aggregate (non-LLM) ───────────────────────


def _federated_aggregate(scores: Dict[str, float]) -> float:
    if not scores:
        return 0.5
    return sum(scores.values()) / len(scores)


# ── MetaLearner: Adjust weights (non-LLM) ─────────────────────────


def _meta_learner_adjust(combined_answer: str, ticket_type: str) -> Dict[str, float]:
    return {"cot_weight": 0.5, "tot_weight": 0.2, "reverse_weight": 0.3}


# ── PHASE 2: LLM-based Answer Synthesis ──────────────────────────


async def _synthesize_final_answer(
    query: str, sub_problems: List[str], solutions: List[str],
    knowledge: str, context: str, ticket_type: str
) -> str:
    """Use LLM to synthesize a proper customer-facing response."""
    solutions_text = "\n".join(f"- {sp}: {sol[:400]}" for sp, sol in zip(sub_problems, solutions))

    prompt = f"""You are a professional customer support agent. Write a complete, helpful response to this customer.

CUSTOMER QUESTION: "{query}"
TYPE: {ticket_type}

Your research found these sub-problem solutions:
{solutions_text}

Relevant policies: {knowledge[:2000]}
Customer context: {context[:300]}

Write a professional response that:
1. Acknowledges the customer's specific situation
2. Addresses EVERY part of their question with specific details (amounts, timelines, processes)
3. Is clear, concise, and actionable
4. Uses a warm but professional tone
5. Ends with next steps

Response:"""

    return await llm_call(prompt, max_tokens=600)


# ── Main Node Function ────────────────────────────────────────────


async def node_4_reasoning_engine(state: PipelineV2State) -> dict:
    """Node 4: Reasoning Engine — Phase 2."""
    start = time.time()
    query = state["query"]
    ticket_type = state["ticket_type"]
    knowledge_docs = state.get("knowledge_context", [])
    customer_ctx = state.get("customer_context", {})
    wiki_c = state.get("wiki_section_c", [])
    crm_data = state.get("crm_data", {})
    logs = []
    llm_calls = 0

    knowledge_str = "\n".join(d.get("content", "") for d in knowledge_docs)
    if wiki_c:
        knowledge_str += "\n\n" + "\n".join(d.get("content", "") for d in wiki_c)
    context_str = str(customer_ctx) + "\n" + str(crm_data)

    # ── LAYER 1: DECOMPOSE ────────────────────────────────────────
    sub_problems = await _gsd_decompose(query, ticket_type, knowledge_str)
    logs.append({"node": 4, "technique": "GSD", "duration_ms": 0, "result_summary": f"{len(sub_problems)} sub-problems"})
    llm_calls += 1

    ordered = await _least_to_most_order(sub_problems, knowledge_str)
    logs.append({"node": 4, "technique": "LeastToMost", "duration_ms": 0, "result_summary": "ordered"})
    llm_calls += 1

    # ── LAYER 2: SOLVE ────────────────────────────────────────────
    bridges = _maker_bridge(ordered, knowledge_str)
    logs.append({"node": 4, "technique": "MAKER", "duration_ms": 0, "result_summary": f"{len(bridges)} bridges"})

    solutions = []
    for sp in ordered:
        sol = await _cot_solve(sp, knowledge_str, context_str, query)
        solutions.append(sol)
        logs.append({"node": 4, "technique": "CoT", "duration_ms": 0, "result_summary": f"solved: {sp[:40]}"})
        llm_calls += 1

    # ToT: quick completeness check
    for i, (sp, sol) in enumerate(zip(ordered, solutions)):
        check = await _tot_explore(sp, knowledge_str, sol)
        logs.append({"node": 4, "technique": "ToT", "duration_ms": 0, "result_summary": f"explored: {sp[:40]}"})
        llm_calls += 1

    # GST
    progress = _gst_track(ordered, solutions)
    logs.append({"node": 4, "technique": "GST", "duration_ms": 0, "result_summary": progress})

    # ── LAYER 3: VALIDATE ─────────────────────────────────────────
    threaded = _thot_thread(ordered, solutions)
    logs.append({"node": 4, "technique": "ThoT", "duration_ms": 0, "result_summary": "threaded"})

    reverse_result = await _reverse_thinking_validate(query, threaded, knowledge_str)
    logs.append({"node": 4, "technique": "ReverseThinking", "duration_ms": 0, "result_summary": f"valid={reverse_result['valid']}"})
    llm_calls += 1

    zero_shot_score = _zero_shot_validate(threaded, knowledge_str)
    logs.append({"node": 4, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"score={zero_shot_score:.2f}"})

    # UoT: confidence
    uot_prompt = f"""Rate your confidence in this answer (0.0-1.0):
Question: "{query}"
Answer: {threaded[:800]}
Reply with ONLY a number between 0.0 and 1.0."""
    try:
        uot_text = await llm_call(uot_prompt, max_tokens=10, temperature=0.0)
        uot_conf = parse_confidence(uot_text, default=0.8)
    except Exception:
        uot_conf = 0.8
    logs.append({"node": 4, "technique": "UoT", "duration_ms": 0, "result_summary": f"confidence={uot_conf:.2f}"})
    llm_calls += 1

    # ── LAYER 4: COMBINE ──────────────────────────────────────────
    aggregated = _federated_aggregate({
        "reverse": reverse_result["confidence"],
        "zero_shot": zero_shot_score,
        "uot": uot_conf,
    })
    logs.append({"node": 4, "technique": "FederatedReasoning", "duration_ms": 0, "result_summary": f"aggregated={aggregated:.2f}"})

    weights = _meta_learner_adjust(threaded, ticket_type)
    logs.append({"node": 4, "technique": "MetaLearner", "duration_ms": 0, "result_summary": f"weights={weights}"})

    # PHASE 2: LLM-based answer synthesis
    formatted = await _synthesize_final_answer(query, ordered, solutions, knowledge_str, context_str, ticket_type)
    logs.append({"node": 4, "technique": "AnswerSynthesis", "duration_ms": 0, "result_summary": f"synthesized {len(formatted)} chars"})
    llm_calls += 1

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 4 complete: ticket=%s sub=%d conf=%.2f llm=%d [%dms]",
        state["ticket_id"], len(ordered), aggregated, llm_calls, elapsed,
    )

    return {
        "sub_problems": ordered,
        "sub_solutions": [{"problem": p, "solution": s} for p, s in zip(ordered, solutions)],
        "combined_answer": formatted,
        "reasoning_confidence": aggregated,
        "technique_log": logs,
        "node_4_token_usage": llm_calls,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
    }