"""
Node 4: Reasoning Engine — The BRAIN

Question: What is the RIGHT answer?

4-Layer Architecture:
  Layer 1 — DECOMPOSE: GSD + Least-to-Most
  Layer 2 — SOLVE:     MAKER + CoT + ToT + GST
  Layer 3 — VALIDATE:  Reverse Thinking + ZeroShotValidator + UoT
  Layer 4 — COMBINE:   ThoT + FederatedReasoning + MetaLearner

LLM calls: 3-4 (CoT + Least-to-Most + ToT + Reverse Thinking + UoT)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from app.core.parwa_pipeline.llm_client import llm_call, parse_confidence
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_4")


# ── GSD: Goal Sub-Goal Decomposition (non-LLM) ───────────────────


def _gsd_decompose(query: str, ticket_type: str, knowledge: str) -> List[str]:
    """Break the problem into sub-problems.
    In production: uses technique from app.core.techniques.
    """
    # For complex tickets, decompose into logical sub-problems
    sub_problems = []

    # Generic decomposition based on ticket type
    if ticket_type == "refund_request":
        sub_problems = [
            "Verify refund eligibility based on policy",
            "Calculate the correct refund amount",
            "Determine the refund method and timeline",
        ]
    elif ticket_type == "billing":
        sub_problems = [
            "Identify the billing issue (charge, invoice, subscription)",
            "Verify the correct amount and billing cycle",
            "Determine the resolution (credit, adjustment, correction)",
        ]
    elif ticket_type == "technical":
        sub_problems = [
            "Identify the specific technical issue",
            "Determine the root cause",
            "Provide step-by-step resolution",
        ]
    elif ticket_type == "complaint":
        sub_problems = [
            "Acknowledge the complaint and customer's frustration",
            "Identify the specific issue behind the complaint",
            "Determine appropriate resolution or compensation",
        ]
    elif ticket_type == "account_change":
        sub_problems = [
            "Verify the requested change is allowed",
            "Identify what information is needed",
            "Execute or recommend the change",
        ]
    else:
        sub_problems = [
            "Understand the customer's question",
            "Find the relevant information",
            "Provide a clear answer",
        ]

    return sub_problems


# ── Least-to-Most: Order sub-problems easiest→hardest (LLM) ───────


async def _least_to_most_order(sub_problems: List[str], knowledge: str) -> List[str]:
    """Order sub-problems from easiest to hardest."""
    if len(sub_problems) <= 1:
        return sub_problems

    prompt = f"""Order these sub-problems from EASIEST to HARDEST to solve.
Consider: simpler verification tasks should come before complex reasoning.

Sub-problems:
{chr(10).join(f'{i+1}. {p}' for i, p in enumerate(sub_problems))}

Available knowledge:
{knowledge[:1000]}

Return the sub-problems in order (easiest first), one per line:"""

    result = await llm_call(prompt, max_tokens=200)
    ordered = [line.strip() for line in result.split("\n") if line.strip()]
    # If parsing fails, keep original order
    return ordered if len(ordered) == len(sub_problems) else sub_problems


# ── MAKER: Bridge knowledge gaps (non-LLM) ────────────────────────


def _maker_bridge(sub_problems: List[str], knowledge: str) -> Dict[str, str]:
    """Bridge knowledge gaps between sub-problems.
    Finds connections in the knowledge that link sub-problem solutions.
    """
    bridges = {}
    knowledge_lower = knowledge.lower()

    for sp in sub_problems:
        # Extract key terms from sub-problem
        words = [w for w in sp.lower().split() if len(w) > 4]
        # Find which knowledge sections mention these terms
        relevant_sections = []
        for i, line in enumerate(knowledge_lower.split(".")):
            if any(w in line for w in words):
                relevant_sections.append(f"Knowledge section {i}")
        bridges[sp] = " → ".join(relevant_sections) if relevant_sections else "no direct bridge found"

    return bridges


# ── CoT: Step-by-step reasoning (LLM) ─────────────────────────────


async def _cot_solve(sub_problem: str, knowledge: str, context: str) -> str:
    """Solve one sub-problem using Chain of Thought."""
    prompt = f"""You are a customer support AI. Solve this sub-problem step by step.

Sub-problem: {sub_problem}

Relevant knowledge:
{knowledge[:2000]}

Customer context:
{context[:500]}

Think step by step:
1."""  # noqa: E501

    return await llm_call(prompt, max_tokens=400)


# ── ToT: Explore multiple solution paths (LLM) ────────────────────


async def _tot_explore(sub_problem: str, knowledge: str, cot_solution: str) -> str:
    """Explore alternative paths if CoT solution might be incomplete."""
    prompt = f"""A sub-problem was solved with this reasoning:
Sub-problem: {sub_problem}

CoT Solution: {cot_solution}

Knowledge: {knowledge[:1500]}

Is there a better alternative approach? If the CoT solution is solid, say "CONFIRMED: {sub_problem}".
If there's a better path, provide it briefly."""

    return await llm_call(prompt, max_tokens=300)


# ── GST: Track progress toward solution (LLM) ─────────────────────


async def _gst_track(sub_problems: List[str], solutions: List[str]) -> str:
    """Track which sub-problems are solved and what remains."""
    solved = sum(1 for s in solutions if s and "cannot" not in s.lower() and "unsure" not in s.lower())
    total = len(sub_problems)
    return f"{solved}/{total} sub-problems solved"


# ── Reverse Thinking: Validate backward (LLM) ─────────────────────


async def _reverse_thinking_validate(
    query: str, combined_answer: str, knowledge: str
) -> Dict[str, Any]:
    """Work backward from the answer to validate it."""
    prompt = f"""Validate this answer by working BACKWARD.

Original question: "{query}"
Proposed answer: {combined_answer}

Knowledge base: {knowledge[:1500]}

Check:
1. Does the answer actually address the question?
2. Is any part of the answer unsupported by the knowledge?
3. Are there logical gaps in the reasoning?

Respond in this format:
VALID: YES/NO
ISSUES: <list any issues or "none">
CONFIDENCE: <0.0-1.0>"""

    result = await llm_call(prompt, max_tokens=200)

    valid = "VALID: YES" in result.upper()
    confidence = 0.7
    import re
    conf_match = re.search(r"CONFIDENCE:\s*([\d.]+)", result)
    if conf_match:
        confidence = float(conf_match.group(1))
        if confidence > 1:
            confidence = confidence / 100

    return {"valid": valid, "confidence": confidence, "analysis": result}


# ── ZeroShotValidator: Statistical anomaly check (non-LLM) ────────


def _zero_shot_validate(answer: str, knowledge: str) -> float:
    """Flag statistically unusual outputs.
    Checks: answer length, knowledge overlap, action amounts."""
    score = 1.0

    # Check answer isn't empty or too short
    if len(answer) < 20:
        score -= 0.3

    # Check answer mentions concepts from knowledge
    knowledge_words = set(knowledge.lower().split())
    answer_words = set(answer.lower().split())
    overlap = len(knowledge_words & answer_words) / max(len(answer_words), 1)
    if overlap < 0.1:
        score -= 0.2

    # Check for suspicious dollar amounts
    import re
    amounts = re.findall(r"\$(\d+(?:,\d{3})*(?:\.\d{2})?)", answer)
    for amt_str in amounts:
        amt = float(amt_str.replace(",", ""))
        if amt > 10000:
            score -= 0.3

    return max(0.0, min(1.0, score))


# ── ThoT: Thread solutions coherently (non-LLM) ───────────────────


def _thot_thread(sub_problems: List[str], solutions: List[str]) -> str:
    """Thread multiple solutions together without contradictions."""
    parts = []
    for sp, sol in zip(sub_problems, solutions):
        if sol:
            parts.append(f"For {sp}: {sol}")
    return "\n\n".join(parts)


# ── FederatedReasoning: Aggregate like voting (non-LLM) ───────────


def _federated_aggregate(scores: Dict[str, float]) -> float:
    """Aggregate multiple validation scores like a voting ensemble."""
    if not scores:
        return 0.5
    return sum(scores.values()) / len(scores)


# ── MetaLearner: Adjust weights (non-LLM) ─────────────────────────


def _meta_learner_adjust(combined_answer: str, ticket_type: str) -> Dict[str, float]:
    """Adjust combination weights based on past success.
    In production: reads from AI Wiki Section A historical data."""
    # Default weights — Phase 6 will make these dynamic
    return {"cot_weight": 0.4, "tot_weight": 0.3, "reverse_weight": 0.3}


# ── Main Node Function ────────────────────────────────────────────


async def node_4_reasoning_engine(state: PipelineV2State) -> dict:
    """Node 4: Reasoning Engine — What is the RIGHT answer?

    4-Layer: Decompose → Solve → Validate → Combine
    """
    start = time.time()
    query = state["query"]
    ticket_type = state["ticket_type"]
    knowledge_docs = state.get("knowledge_context", [])
    customer_ctx = state.get("customer_context", {})
    wiki_c = state.get("wiki_section_c", [])
    crm_data = state.get("crm_data", {})
    logs = []
    llm_calls = 0

    # Build knowledge string
    knowledge_str = "\n".join(d.get("content", "") for d in knowledge_docs)
    if wiki_c:
        knowledge_str += "\n\nCompany Policies:\n" + "\n".join(d.get("content", "") for d in wiki_c)
    context_str = str(customer_ctx) + "\n" + str(crm_data)

    # ── LAYER 1: DECOMPOSE ────────────────────────────────────────
    sub_problems = _gsd_decompose(query, ticket_type, knowledge_str)
    logs.append({"node": 4, "technique": "GSD", "duration_ms": 0, "result_summary": f"{len(sub_problems)} sub-problems"})

    ordered_problems = await _least_to_most_order(sub_problems, knowledge_str)
    logs.append({"node": 4, "technique": "LeastToMost", "duration_ms": 0, "result_summary": "ordered"})
    llm_calls += 1

    # ── LAYER 2: SOLVE ────────────────────────────────────────────
    bridges = _maker_bridge(ordered_problems, knowledge_str)
    logs.append({"node": 4, "technique": "MAKER", "duration_ms": 0, "result_summary": f"{len(bridges)} bridges"})

    solutions = []
    for sp in ordered_problems:
        sol = await _cot_solve(sp, knowledge_str, context_str)
        solutions.append(sol)
        logs.append({"node": 4, "technique": "CoT", "duration_ms": 0, "result_summary": f"solved: {sp[:40]}"})
        llm_calls += 1

    # ToT: explore alternatives for complex problems
    if len(ordered_problems) > 1:
        for i, (sp, sol) in enumerate(zip(ordered_problems, solutions)):
            alt = await _tot_explore(sp, knowledge_str, sol)
            if "CONFIRMED" not in alt:
                solutions[i] = alt  # use better path if found
            logs.append({"node": 4, "technique": "ToT", "duration_ms": 0, "result_summary": f"explored: {sp[:40]}"})
            llm_calls += 1

    # GST: track progress
    progress = await _gst_track(ordered_problems, solutions)
    logs.append({"node": 4, "technique": "GST", "duration_ms": 0, "result_summary": progress})
    llm_calls += 1

    # ── LAYER 3: VALIDATE ─────────────────────────────────────────
    combined = _thot_thread(ordered_problems, solutions)
    logs.append({"node": 4, "technique": "ThoT", "duration_ms": 0, "result_summary": "threaded"})

    reverse_result = await _reverse_thinking_validate(query, combined, knowledge_str)
    logs.append({"node": 4, "technique": "ReverseThinking", "duration_ms": 0, "result_summary": f"valid={reverse_result['valid']}"})
    llm_calls += 1

    zero_shot_score = _zero_shot_validate(combined, knowledge_str)
    logs.append({"node": 4, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"score={zero_shot_score:.2f}"})

    # UoT: measure reasoning confidence (LLM)
    uot_prompt = f"""Rate your confidence in this answer (0.0-1.0):
Question: "{query}"
Answer: {combined[:1000]}

Respond with ONLY a number."""
    try:
        uot_text = await llm_call(uot_prompt, max_tokens=10, temperature=0.0)
        uot_conf = parse_confidence(uot_text, default=0.7)
    except Exception:
        uot_conf = 0.7
    logs.append({"node": 4, "technique": "UoT", "duration_ms": 0, "result_summary": f"confidence={uot_conf:.2f}"})
    llm_calls += 1

    # ── LAYER 4: COMBINE ──────────────────────────────────────────
    # FederatedReasoning: aggregate all confidence signals
    aggregated = _federated_aggregate({
        "reverse": reverse_result["confidence"],
        "zero_shot": zero_shot_score,
        "uot": uot_conf,
    })
    logs.append({"node": 4, "technique": "FederatedReasoning", "duration_ms": 0, "result_summary": f"aggregated={aggregated:.2f}"})

    # MetaLearner: adjust weights
    weights = _meta_learner_adjust(combined, ticket_type)
    logs.append({"node": 4, "technique": "MetaLearner", "duration_ms": 0, "result_summary": f"weights={weights}"})

    # Final confidence
    reasoning_confidence = aggregated

    # Format the combined answer for customer
    formatted = _format_answer(query, ordered_problems, solutions, combined, ticket_type)

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 4 complete: ticket=%s sub_problems=%d confidence=%.2f llm=%d [%dms]",
        state["ticket_id"], len(ordered_problems), reasoning_confidence, llm_calls, elapsed,
    )

    return {
        "sub_problems": ordered_problems,
        "sub_solutions": [{"problem": p, "solution": s} for p, s in zip(ordered_problems, solutions)],
        "combined_answer": formatted,
        "reasoning_confidence": reasoning_confidence,
        "technique_log": logs,
        "node_4_token_usage": llm_calls,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
    }


def _format_answer(
    query: str, sub_problems: List[str], solutions: List[str], threaded: str, ticket_type: str
) -> str:
    """Format the combined answer into a customer-friendly response."""
    # Clean up the threaded answer — extract just the solutions
    clean_parts = []
    for sp, sol in zip(sub_problems, solutions):
        # Take the last few lines of each solution (the actual answer part)
        lines = sol.strip().split("\n")
        answer_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith(("1.", "2.", "3.", "4.", "5.", "Step", "Based"))]
        if answer_lines:
            clean_parts.append(" ".join(answer_lines[-3:]))  # last 3 meaningful lines

    return "\n\n".join(clean_parts) if clean_parts else threaded[:2000]