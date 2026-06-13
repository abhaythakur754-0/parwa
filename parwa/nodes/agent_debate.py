"""Node: AGENT_DEBATE — Two agents argue for/against the conclusion before consensus.

P1 NEW NODE: Creates a structured debate between two AI "agents":
  - ADVOCATE: Argues FOR the conclusion (finds supporting evidence)
  - SKEPTIC: Argues AGAINST the conclusion (finds contradicting evidence)
  - JUDGE: Evaluates both arguments and decides the final position

This is fundamentally different from:
  - Red Team: Red team ATTACKS. Debate EXPLORES both sides.
  - Reverse Thinker: Reverse traces evidence. Debate ARGUES positions.
  - Self-Consistency: Checks if outputs agree. Debate forces disagreement.

The debate surfaces evidence and reasoning that single-path analysis misses.
It catches:
  - Hidden assumptions the advocate makes
  - Missing evidence the skeptic reveals
  - Edge cases that neither side considered alone
  - Overconfident conclusions that don't survive scrutiny

Debate outcome:
  - ADVOCATE_WINS: Conclusion is well-supported, proceed
  - SKEPTIC_WINS: Conclusion is flawed, loop back for re-reasoning
  - PARTIAL: Some concerns, add caveats and proceed

Variant behavior:
  - mini: No debate (too expensive) — just passes through
  - parwa: Single-round debate (advocate + skeptic + judge)
  - high: Two-round debate (advocate + skeptic + rebuttal + judge)
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.node_base import safe_node
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.node.agent_debate")


def _debate_rule_based(
    conclusion: str,
    evidence_chain: list[dict],
    intent: str,
) -> dict[str, Any]:
    """Quick rule-based debate analysis (no LLM).

    Used for mini variant and as fallback when LLM is unavailable.
    Simulates the debate by checking evidence balance.
    """
    # Count supporting vs undermining evidence
    supporting = 0
    undermining = 0
    support_evidence = []
    undermine_evidence = []

    for entry in evidence_chain:
        if not isinstance(entry, dict):
            continue
        claim = entry.get("claim", "").lower()
        conf = entry.get("confidence", 0.5)

        # Positive signals
        if any(kw in claim for kw in ["passed", "eligible", "confirmed", "approved", "verified"]):
            supporting += 1
            support_evidence.append(claim[:80])
        # Negative signals
        elif any(kw in claim for kw in ["failed", "insufficient", "denied", "not eligible", "vulnerability"]):
            undermining += 1
            undermine_evidence.append(claim[:80])
        # High confidence = supporting, low = undermining
        elif conf >= 0.7:
            supporting += 1
            support_evidence.append(claim[:80])
        elif conf < 0.4:
            undermining += 1
            undermine_evidence.append(claim[:80])

    # Determine debate outcome
    if undermining == 0 and supporting > 0:
        outcome = "advocate_wins"
        confidence = min(0.9, 0.6 + supporting * 0.05)
    elif undermining > supporting:
        outcome = "skeptic_wins"
        confidence = min(0.9, 0.4 + undermining * 0.05)
    elif undermining > 0:
        outcome = "partial"
        confidence = 0.5
    else:
        outcome = "partial"  # No evidence either way
        confidence = 0.3

    return {
        "outcome": outcome,
        "confidence": confidence,
        "advocate_points": support_evidence[:5],
        "skeptic_points": undermine_evidence[:5],
        "advocate_score": supporting,
        "skeptic_score": undermining,
        "technique": "rule_based",
        "rounds": 0,
    }


async def _debate_round(
    role: str,
    conclusion: str,
    evidence_summary: str,
    intent: str,
    raw_message: str,
    opponent_argument: str = "",
    *,
    ticket_id: str = "",
    variant: str = "parwa",
) -> str:
    """Run a single debate round for one side (advocate or skeptic).

    Args:
        role: "advocate" or "skeptic"
        conclusion: The conclusion being debated
        evidence_summary: Summary of available evidence
        intent: Customer intent
        raw_message: Original customer message
        opponent_argument: The other side's previous argument (for rebuttal)

    Returns:
        The debater's argument text.
    """
    if role == "advocate":
        system_instructions = (
            "You are the ADVOCATE in a debate about an AI customer support decision.\n"
            "Your job: Argue FOR the conclusion. Find ALL supporting evidence.\n"
            "Be thorough but HONEST — don't fabricate support that doesn't exist.\n\n"
            f"Customer intent: {intent}\n"
            f"Customer message: {raw_message[:300]}\n\n"
            f"CONCLUSION BEING DEBATED:\n{conclusion}\n\n"
            f"AVAILABLE EVIDENCE:\n{evidence_summary}\n\n"
        )
        if opponent_argument:
            system_instructions += (
                f"THE SKEPTIC ARGUES:\n{opponent_argument}\n\n"
                "REBUT the skeptic's points. Show why the conclusion still stands.\n"
            )
        system_instructions += (
            "Write 3-5 bullet points arguing FOR the conclusion. "
            "Cite specific evidence. Be concise."
        )
    else:
        system_instructions = (
            "You are the SKEPTIC in a debate about an AI customer support decision.\n"
            "Your job: Argue AGAINST the conclusion. Find flaws, gaps, and risks.\n"
            "Be aggressive but HONEST — don't fabricate problems that don't exist.\n\n"
            f"Customer intent: {intent}\n"
            f"Customer message: {raw_message[:300]}\n\n"
            f"CONCLUSION BEING DEBATED:\n{conclusion}\n\n"
            f"AVAILABLE EVIDENCE:\n{evidence_summary}\n\n"
        )
        if opponent_argument:
            system_instructions += (
                f"THE ADVOCATE ARGUES:\n{opponent_argument}\n\n"
                "COUNTER the advocate's points. Show why the conclusion is flawed.\n"
            )
        system_instructions += (
            "Write 3-5 bullet points arguing AGAINST the conclusion. "
            "Cite specific evidence gaps or risks. Be concise."
        )

    prompt = f"{'Rebut' if opponent_argument else 'Present'} your {'rebuttal' if opponent_argument else 'argument'} as the {role}."

    try:
        safe_prompt = build_safe_prompt(system_instructions, prompt)
        text = await ainvoke_llm(
            safe_prompt,
            node_name=f"AGENT_DEBATE_{role.upper()}",
            ticket_id=ticket_id,
            variant=variant,
            # max_tokens removed — uses generous default
        )
        return text.strip()
    except Exception as exc:
        logger.warning("agent_debate: %s round failed (%s)", role, exc)
        return f"[{role} failed to produce argument: {exc}]"


async def _judge_debate(
    conclusion: str,
    advocate_argument: str,
    skeptic_argument: str,
    evidence_summary: str,
    *,
    ticket_id: str = "",
    variant: str = "parwa",
) -> dict[str, Any]:
    """Judge the debate and determine the outcome.

    Returns:
        Debate result with outcome, confidence, and key points from both sides.
    """
    system_instructions = (
        "You are the JUDGE in a debate about an AI customer support decision.\n\n"
        f"CONCLUSION BEING DEBATED:\n{conclusion}\n\n"
        f"ADVOCATE'S ARGUMENT (FOR):\n{advocate_argument}\n\n"
        f"SKEPTIC'S ARGUMENT (AGAINST):\n{skeptic_argument}\n\n"
        f"AVAILABLE EVIDENCE:\n{evidence_summary}\n\n"
        "Decide the debate outcome. Be FAIR but STRICT.\n\n"
        "Reply in this EXACT format:\n"
        "OUTCOME: ADVOCATE_WINS|SKEPTIC_WINS|PARTIAL\n"
        "CONFIDENCE: 0.0-1.0\n"
        "REASONING: <1-2 sentences explaining your decision>\n"
        "KEY_SUPPORT: <strongest point for the conclusion>\n"
        "KEY_CONCERN: <strongest point against the conclusion>"
    )

    try:
        safe_prompt = build_safe_prompt(system_instructions, "Judge this debate.")
        text = await ainvoke_llm(
            safe_prompt,
            node_name="AGENT_DEBATE_JUDGE",
            ticket_id=ticket_id,
            variant=variant,
            # max_tokens removed — uses generous default
        )

        # Parse judge response
        outcome = "partial"
        confidence = 0.5
        reasoning = ""
        key_support = ""
        key_concern = ""

        for line in text.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("OUTCOME:"):
                outcome_text = line.split(":", 1)[1].strip().upper()
                outcome_map = {
                    "ADVOCATE_WINS": "advocate_wins",
                    "SKEPTIC_WINS": "skeptic_wins",
                    "PARTIAL": "partial",
                }
                outcome = outcome_map.get(outcome_text, "partial")
            elif line.upper().startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                    confidence = max(0.0, min(1.0, confidence))
                except ValueError:
                    confidence = 0.5
            elif line.upper().startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()
            elif line.upper().startswith("KEY_SUPPORT:"):
                key_support = line.split(":", 1)[1].strip()
            elif line.upper().startswith("KEY_CONCERN:"):
                key_concern = line.split(":", 1)[1].strip()

        return {
            "outcome": outcome,
            "confidence": confidence,
            "reasoning": reasoning,
            "key_support": key_support,
            "key_concern": key_concern,
            "technique": "llm_debate",
        }

    except Exception as exc:
        logger.warning("agent_debate: judge failed (%s), using rule-based", exc)
        return {
            "outcome": "partial",
            "confidence": 0.5,
            "reasoning": f"Judge LLM failed: {exc}",
            "key_support": "",
            "key_concern": "",
            "technique": "judge_fallback",
        }


@safe_node("AGENT_DEBATE", fallback={
    "debate_result": {"outcome": "partial", "confidence": 0.5, "technique": "fallback"},
    "active_frameworks": [],
    "should_loop_back": False,
    "evidence_chain": [],
})
async def agent_debate(state: dict[str, Any]) -> dict[str, Any]:
    """Structured debate between advocate and skeptic before consensus (async).

    P1 NEW NODE: Creates a debate between two AI agents:
      - Advocate argues FOR the conclusion
      - Skeptic argues AGAINST the conclusion
      - Judge evaluates both and decides

    Variant behavior:
      - mini: No debate (passes through, rule-based analysis only)
      - parwa: Single-round debate (advocate → skeptic → judge)
      - high: Two-round debate (advocate → skeptic → rebuttal → judge)

    Reads: reasoning_conclusion, evidence_chain, intent, raw_message, variant
    Writes: debate_result, active_frameworks (append), should_loop_back, evidence_chain (append)
    """
    conclusion = state.get("reasoning_conclusion", "")
    evidence_chain = state.get("evidence_chain", [])
    intent = state.get("intent", "general_inquiry")
    raw_message = state.get("raw_message", "")
    variant = state.get("variant", "parwa")

    # Guard types
    if not isinstance(conclusion, str):
        conclusion = str(conclusion) if conclusion else ""
    if not isinstance(evidence_chain, list):
        evidence_chain = []
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(variant, str):
        variant = "parwa"

    # Mini variant: no expensive debate, just rule-based analysis
    if variant == "mini":
        result = _debate_rule_based(conclusion, evidence_chain, intent)

        new_frameworks = []
        existing = state.get("active_frameworks", [])
        if "agent_debate" not in existing:
            new_frameworks.append("agent_debate")

        new_evidence = [{
            "claim": f"Debate (rule-based): {result['outcome']} — "
                     f"advocate={result['advocate_score']} skeptic={result['skeptic_score']}",
            "sources": result.get("advocate_points", [])[:2] + result.get("skeptic_points", [])[:2],
            "confidence": result["confidence"],
            "technique": "agent_debate",
            "category": "debate",
            "node": "AGENT_DEBATE",
            "outcome": result["outcome"],
        }]

        should_loop = result["outcome"] == "skeptic_wins"

        return {
            "debate_result": result,
            "active_frameworks": new_frameworks,
            "should_loop_back": should_loop,
            "evidence_chain": new_evidence,
        }

    # Parwa / High variant: LLM-powered debate
    if MOCK_MODE or not conclusion:
        # Mock mode or no conclusion: use rule-based
        result = _debate_rule_based(conclusion, evidence_chain, intent)

        new_frameworks = []
        existing = state.get("active_frameworks", [])
        if "agent_debate" not in existing:
            new_frameworks.append("agent_debate")

        new_evidence = [{
            "claim": f"Debate (mock/rule-based): {result['outcome']}",
            "sources": [],
            "confidence": result["confidence"],
            "technique": "agent_debate",
            "category": "debate",
            "node": "AGENT_DEBATE",
            "outcome": result["outcome"],
        }]

        should_loop = result["outcome"] == "skeptic_wins"

        return {
            "debate_result": result,
            "active_frameworks": new_frameworks,
            "should_loop_back": should_loop,
            "evidence_chain": new_evidence,
        }

    # Build evidence summary for debaters
    evidence_summary_parts = []
    for i, entry in enumerate(evidence_chain[:8], 1):
        if isinstance(entry, dict):
            claim = entry.get("claim", "")
            conf = entry.get("confidence", 0)
            evidence_summary_parts.append(f"  {i}. {claim[:100]} (conf: {conf:.2f})")
    evidence_summary = "\n".join(evidence_summary_parts) if evidence_summary_parts else "Limited evidence available."

    ticket_id = state.get("ticket_id", "")

    # Round 1: Advocate argues, then Skeptic argues
    advocate_arg = await _debate_round(
        "advocate", conclusion, evidence_summary, intent, raw_message,
        ticket_id=ticket_id, variant=variant,
    )

    skeptic_arg = await _debate_round(
        "skeptic", conclusion, evidence_summary, intent, raw_message,
        opponent_argument=advocate_arg,
        ticket_id=ticket_id, variant=variant,
    )

    # Round 2 (high variant only): Rebuttal round
    if variant == "high":
        advocate_rebuttal = await _debate_round(
            "advocate", conclusion, evidence_summary, intent, raw_message,
            opponent_argument=skeptic_arg,
            ticket_id=ticket_id, variant=variant,
        )
        # Combine advocate arguments
        advocate_arg = f"{advocate_arg}\n\nREBUTTAL:\n{advocate_rebuttal}"

    # Judge the debate
    judge_result = await _judge_debate(
        conclusion, advocate_arg, skeptic_arg, evidence_summary,
        ticket_id=ticket_id, variant=variant,
    )

    # Build final debate result
    debate_result = {
        "outcome": judge_result.get("outcome", "partial"),
        "confidence": judge_result.get("confidence", 0.5),
        "reasoning": judge_result.get("reasoning", ""),
        "key_support": judge_result.get("key_support", ""),
        "key_concern": judge_result.get("key_concern", ""),
        "advocate_argument": advocate_arg[:300],
        "skeptic_argument": skeptic_arg[:300],
        "technique": "llm_debate",
        "rounds": 2 if variant == "high" else 1,
    }

    # Should loop back? Skeptic wins = loop back
    loop_count = state.get("loop_count", 0)
    max_loops = state.get("max_loops", 2)
    should_loop = (
        debate_result["outcome"] == "skeptic_wins"
        and loop_count < max_loops
    )

    # Track frameworks
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    if "agent_debate" not in existing:
        new_frameworks.append("agent_debate")

    # Build evidence chain entry
    new_evidence = [{
        "claim": f"Debate verdict: {debate_result['outcome'].upper()} — "
                 f"{debate_result.get('reasoning', '')[:100]}",
        "sources": [
            debate_result.get("key_support", "")[:80],
            debate_result.get("key_concern", "")[:80],
        ],
        "confidence": debate_result["confidence"],
        "technique": "agent_debate",
        "category": "debate",
        "node": "AGENT_DEBATE",
        "outcome": debate_result["outcome"],
        "rounds": debate_result["rounds"],
    }]

    logger.info(
        "agent_debate: outcome=%s confidence=%.2f should_loop=%s variant=%s rounds=%d",
        debate_result["outcome"], debate_result["confidence"],
        should_loop, variant, debate_result["rounds"],
    )

    return {
        "debate_result": debate_result,
        "active_frameworks": new_frameworks,
        "should_loop_back": should_loop,
        "evidence_chain": new_evidence,
    }
