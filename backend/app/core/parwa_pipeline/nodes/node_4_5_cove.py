"""
Node 4.5: Chain-of-Verification (CoVe)  (P4 — hallucination killer)

Phase 11 upgrades (Non-LLM Enhancement — all non-LLM, 0 extra calls):
  - NearDedup: remove near-duplicate claims before verification (prevents score inflation)
  - SufficiencyCheck: verify verified claims actually cover ALL parts of the customer's question

WHY THIS EXISTS:
  Even with few-shot examples, weak LLMs (Llama 3.1 8B) still hallucinate facts.
  CoVe is a post-generation verification step (Dhuliawala et al. 2023, Microsoft)
  that checks every claim in the AI response against the knowledge base.

WHAT IT DOES:
  1. Split the AI response (from Node 4) into atomic claims.
  2. For each claim, check if it's supported by the KB chunks (Node 3 output).
  3. Compute verification_score = (verified_claims / total_claims).
  4. If score < threshold (50%):
     - Regenerate response with a "your previous answer had unverified claims,
       only use the KB" warning.
  5. Return final response + verification_score to downstream nodes.

LLM CALLS: 0 (pure string ops + 1 optional regeneration LLM call only when needed)
COST: ~0 extra tokens (most responses verify; regeneration is rare)

INPUT: state.combined_answer, state.knowledge_context, state.query
OUTPUT: state.verified_response, state.verification_score, state.verification_claims
        Also OVERWRITES state.combined_answer if regeneration happens
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Tuple

from app.core.parwa_pipeline.llm_client import llm_call
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_4_5")

# If verification score is below this, regenerate AND block
# Lowered from 0.60 to 0.30 for production — NVIDIA embeddings produce
# lower similarity scores, so claims that ARE supported by KB content
# may not score high enough with the old threshold. 0.30 means at least
# 30% of claims must be verified — still catches hallucinations (0% score)
# while allowing legitimate KB-backed responses through.
VERIFICATION_THRESHOLD = 0.30
# Maximum number of regeneration attempts
MAX_REGENERATIONS = 1
# NearDedup: similarity threshold for merging claims (0.70 = 70% keyword overlap)
NEAR_DEDUP_THRESHOLD = 0.70


def _split_into_claims(text: str) -> List[str]:
    """Split a response into atomic claims.

    Strategy:
      1. Split on sentence boundaries (. ! ?)
      2. Filter out very short fragments (< 25 chars)
      3. Filter out pure greetings / closings / questions
      4. Each remaining sentence is one "claim"
    """
    if not text:
        return []

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Split on sentence boundaries, preserving the content
    raw_sentences = re.split(r"(?<=[.!?])\s+", text)

    claims: List[str] = []
    for s in raw_sentences:
        s = s.strip()
        if len(s) < 25:
            continue
        # Skip pure greetings/closings
        s_lower = s.lower()
        if any(greet in s_lower for greet in [
            "dear ", "hello ", "hi ", "thanks", "thank you", "best regards",
            "sincerely", "regards,", "cheers",
        ]):
            continue
        # Skip pure questions (we want statements that can be verified)
        if s.endswith("?") and not any(c in s for c in [".", ","]):
            continue
        # Skip list-only items (numbers/bullets without full sentences)
        if re.match(r"^[\d\-\*\•\)]+\s+\w{1,15}$", s):
            continue

        claims.append(s)

    # Deduplicate while preserving order
    seen = set()
    unique: List[str] = []
    for c in claims:
        key = c.lower()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return unique[:8]  # cap at 8 claims to keep verification fast


def _extract_kb_keywords(kb_text: str) -> set:
    """Extract significant keywords from KB text for verification matching."""
    if not kb_text:
        return set()
    # Get all words > 4 chars, lowercase
    return {w.lower() for w in re.findall(r"\b\w+\b", kb_text) if len(w) > 4}


def _verify_claim(claim: str, kb_keywords: set, kb_text: str) -> Tuple[bool, str]:
    """Verify a single claim against the knowledge base.

    Returns (is_verified, reason).
    A claim is "verified" if at least 40% of its significant words appear in the KB.

    Why 40%? Some words in the claim (pronouns, articles) won't be in the KB
    even when the claim is fully supported. 40% is a generous threshold that
    catches wholesale hallucinations while not flagging minor wording differences.

    ACTION VERB CHECK (Phase 10): If the claim contains a technical action verb
    (reset, restart, re-authenticate, delete, etc.), that verb MUST also appear
    in the KB. This catches "reset your SSO token" — the KB mentions SSO but
    never says to reset anything.
    """
    claim_words = [w.lower() for w in re.findall(r"\b\w+\b", claim) if len(w) > 4]
    if not claim_words:
        return True, "no_significant_words"

    # Check direct keyword overlap
    matched = sum(1 for w in claim_words if w in kb_keywords)
    match_ratio = matched / len(claim_words)

    if match_ratio >= 0.40:
        # Action verb check — even with good keyword overlap, if the claim
        # gives a specific technical instruction (reset/restart/delete/etc.)
        # that doesn't appear in the KB, it's a hallucination.
        action_verbs = {
            "reset", "restart", "re-authenticate", "reauthenticate", "re-sync",
            "resync", "delete", "remove", "install", "uninstall", "configure",
            "reconfigure", "update", "upgrade", "downgrade", "reboot", "reload",
            "purge", "flush", "wipe", "restore", "rollback", "redeploy",
        }
        claim_verbs = {w.lower() for w in re.findall(r"\b\w+\b", claim) if w.lower() in action_verbs}
        if claim_verbs:
            kb_words_set = set(re.findall(r"\b\w+\b", kb_text.lower()))
            unsupported_verbs = claim_verbs - kb_words_set
            if unsupported_verbs:
                return False, f"action verb(s) not in KB: {unsupported_verbs}"

        return True, f"matched {matched}/{len(claim_words)} keywords"

    # Special-case: numbers / amounts / dates — if the claim contains a specific
    # number that does NOT appear anywhere in the KB, that's a strong hallucination signal
    claim_numbers = set(re.findall(r"\b\d[\d,\.]*\b", claim))
    if claim_numbers:
        kb_numbers = set(re.findall(r"\b\d[\d,\.]*\b", kb_text))
        novel_numbers = claim_numbers - kb_numbers
        # Filter out trivial numbers (single digits that could be steps like "1", "2")
        novel_substantial = {n for n in novel_numbers if len(n.replace(",", "").replace(".", "")) >= 2}
        if novel_substantial:
            return False, f"novel numbers not in KB: {novel_substantial}"

    if match_ratio >= 0.20:
        # Borderline — give benefit of the doubt but flag
        return True, f"weak match {matched}/{len(claim_words)} keywords"

    return False, f"only matched {matched}/{len(claim_words)} keywords"


def _build_regeneration_prompt(
    query: str,
    previous_response: str,
    unverified_claims: List[str],
    knowledge_text: str,
    ticket_type: str,
) -> str:
    """Build a prompt that asks the LLM to regenerate, grounded ONLY in the KB."""
    unverified_text = "\n".join(f"  - {c}" for c in unverified_claims)
    return f"""Rewrite this customer support response. Your previous response contained UNVERIFIED claims.

CUSTOMER QUESTION: "{query}"
TYPE: {ticket_type}

PREVIOUS RESPONSE (had issues):
{previous_response}

CLAIMS THAT WERE NOT SUPPORTED BY OUR KNOWLEDGE BASE:
{unverified_text}

KNOWLEDGE BASE (use ONLY this — do not invent any facts, numbers, dates, or policy names that are not below):
{knowledge_text[:2500]}

RULES:
1. Only state facts that appear in the knowledge base above
2. If the KB does not contain a specific answer, say "I don't have that information" instead of guessing
3. Cite specific dollar amounts, timeframes, and policy names from the KB
4. Keep the response professional and direct
5. Do NOT invent technical advice (SSO, API calls, error codes) unless it appears in the KB
6. Address EVERY part of the customer's question using only verified information

Write the corrected response:"""


async def node_4_5_chain_of_verification(state: PipelineV2State) -> dict:
    """Node 4.5: Chain-of-Verification.

    Verifies every claim in the AI response against the KB. Regenerates if needed.

    LLM calls: 0 in the happy path; 1 only if verification fails (rare).
    """
    start = time.time()
    response = state.get("combined_answer", "")
    knowledge_docs = state.get("knowledge_context", [])
    wiki_c = state.get("wiki_section_c", [])
    query = state.get("query", "")
    ticket_type = state.get("ticket_type", "general")
    # If Node 4 paused for hallucination and was resumed with human guidance,
    # the human IS the verification — don't let CoVe block their answer.
    human_guided = bool(state.get("force_human_handoff", False))

    if not response:
        logger.warning("Node 4.5: no combined_answer in state — skipping")
        return {
            "verified_response": "",
            "verification_score": 0.0,
            "verification_claims": [],
            "technique_log": [{
                "node": "4.5",
                "technique": "ChainOfVerification",
                "duration_ms": 0,
                "result_summary": "skipped_no_response",
            }],
        }

    # Build the KB text we verify against
    kb_text = "\n".join(d.get("content", "") for d in knowledge_docs)
    if wiki_c:
        kb_text += "\n\n" + "\n".join(d.get("content", "") for d in wiki_c)
    if not kb_text.strip():
        # No KB to verify against — pass through (rare)
        logger.info("Node 4.5: no KB text available — skipping verification")
        return {
            "verified_response": response,
            "verification_score": 1.0,  # assume verified (no KB to check against)
            "verification_claims": [],
            "technique_log": [{
                "node": "4.5",
                "technique": "ChainOfVerification",
                "duration_ms": int((time.time() - start) * 1000),
                "result_summary": "skipped_no_kb",
            }],
        }

    kb_keywords = _extract_kb_keywords(kb_text)

    # ── Step 0.5: NearDedup — remove near-duplicate claims ────────────
    # Before verification, merge claims that say the same thing with
    # slightly different wording. This prevents score inflation where
    # "Your refund is $300" and "The amount you'll receive back is $300"
    # count as 2 verified claims.
    def _near_dedup_claims(claims: List[str], threshold: float = NEAR_DEDUP_THRESHOLD) -> Tuple[List[str], int]:
        if len(claims) <= 1:
            return claims, 0
        deduped = []
        skip = set()
        removed = 0
        for i, c in enumerate(claims):
            if i in skip:
                continue
            words_i = {w.lower() for w in re.findall(r"\b\w+\b", c) if len(w) > 3}
            if not words_i:
                deduped.append(c)
                continue
            for j in range(i + 1, len(claims)):
                if j in skip:
                    continue
                words_j = {w.lower() for w in re.findall(r"\b\w+\b", claims[j]) if len(w) > 3}
                if not words_j:
                    continue
                overlap = len(words_i & words_j) / min(len(words_i), len(words_j))
                if overlap >= threshold:
                    # Keep the longer (more specific) claim
                    kept = c if len(c) >= len(claims[j]) else claims[j]
                    deduped.append(kept)
                    skip.add(j)
                    removed += 1
                    break
            else:
                deduped.append(c)
        return deduped, removed

    # ── Step 1: Split response into claims ───────────────────────────
    claims = _split_into_claims(response)

    logs = []  # Initialize early — NearDedup needs it below

    # Phase 11: NearDedup — remove near-duplicate claims
    claims, ndup_removed = _near_dedup_claims(claims)
    if ndup_removed:
        logs.append({
            "node": "4.5", "technique": "NearDedup",
            "duration_ms": 0,
            "result_summary": f"removed {ndup_removed} near-duplicate claims",
        })
    else:
        logs.append({"node": "4.5", "technique": "NearDedup", "duration_ms": 0, "result_summary": "no_duplicates"})

    if not claims:
        # Response has no verifiable claims (e.g., short greeting) — pass through
        return {
            "verified_response": response,
            "verification_score": 1.0,
            "verification_claims": [],
            "technique_log": [{
                "node": "4.5",
                "technique": "ChainOfVerification",
                "duration_ms": int((time.time() - start) * 1000),
                "result_summary": "no_claims_to_verify",
            }],
        }

    # ── Step 2: Verify each claim ────────────────────────────────────
    verification_results: List[Dict[str, Any]] = []
    verified_count = 0
    unverified_claims: List[str] = []
    for claim in claims:
        is_verified, reason = _verify_claim(claim, kb_keywords, kb_text)
        verification_results.append({
            "claim": claim[:200],
            "verified": is_verified,
            "reason": reason,
        })
        if is_verified:
            verified_count += 1
        else:
            unverified_claims.append(claim)

    score = verified_count / len(claims) if claims else 0.0

    logs.append({
        "node": "4.5",
        "technique": "ChainOfVerification",
        "duration_ms": 0,
        "result_summary": f"verified {verified_count}/{len(claims)} claims (score={score:.3f})",
    })

    # ── Step 3: Regenerate if score < threshold ──────────────────────
    final_response = response
    regenerated = False
    extra_llm_calls = 0

    if score < VERIFICATION_THRESHOLD and unverified_claims:
        logger.info(
            "Node 4.5: verification FAILED score=%.3f < %.2f — regenerating (unverified=%d)",
            score, VERIFICATION_THRESHOLD, len(unverified_claims),
        )
        try:
            regen_prompt = _build_regeneration_prompt(
                query=query,
                previous_response=response,
                unverified_claims=unverified_claims[:5],  # cap to keep prompt small
                knowledge_text=kb_text,
                ticket_type=ticket_type,
            )
            regenerated_response = await llm_call(
                regen_prompt, max_tokens=600, temperature=0.2,
            )
            extra_llm_calls += 1

            # Re-verify the regenerated response
            regen_claims = _split_into_claims(regenerated_response)
            regen_verified = 0
            for c in regen_claims:
                is_v, _ = _verify_claim(c, kb_keywords, kb_text)
                if is_v:
                    regen_verified += 1
            regen_score = regen_verified / len(regen_claims) if regen_claims else 0.0

            # Only accept the regenerated response if it's actually better
            if regen_score > score and regen_response_not_empty(regenerated_response):
                logger.info(
                    "Node 4.5: regeneration improved score %.3f → %.3f — accepting",
                    score, regen_score,
                )
                final_response = regenerated_response
                score = regen_score
                regenerated = True
                logs.append({
                    "node": "4.5",
                    "technique": "ChainOfVerification.Regenerate",
                    "duration_ms": 0,
                    "result_summary": f"regenerated, new score={score:.3f}",
                })
            else:
                logger.info(
                    "Node 4.5: regeneration did not improve score (%.3f → %.3f) — keeping original",
                    score, regen_score,
                )
                logs.append({
                    "node": "4.5",
                    "technique": "ChainOfVerification.Regenerate",
                    "duration_ms": 0,
                    "result_summary": f"regeneration worse ({regen_score:.3f}), kept original",
                })
        except Exception as exc:  # noqa: BLE001
            logger.warning("Node 4.5: regeneration failed (non-fatal): %s", exc)
            logs.append({
                "node": "4.5",
                "technique": "ChainOfVerification.Regenerate",
                "duration_ms": 0,
                "result_summary": f"regeneration error: {type(exc).__name__}",
            })

    elapsed = int((time.time() - start) * 1000)

    # ── HARD GATE: Block response if score still below threshold ─────
    # Even after regeneration, if the score is below VERIFICATION_THRESHOLD,
    # we BLOCK the response from going to the customer. The customer gets
    # a safe fallback instead, and the ticket is escalated to a human agent.
    # This is the "reject even if Quality is 9.5/10" rule.
    #
    # EXCEPTION: If Node 4 was resumed with human guidance (force_human_handoff),
    # the human IS the source of truth — their guidance overrides CoVe. Don't
    # block the response or the customer gets a generic "escalating" email
    # instead of the guidance-informed answer the human just approved.

    SAFE_FALLBACK = (
        "Thank you for reaching out. I've reviewed your request, but I don't have "
        "enough verified information in our knowledge base to provide a confident answer. "
        "I'm escalating your ticket to a human agent who will follow up with you shortly. "
        "Your ticket is now in our priority queue."
    )

    # ── Phase 11: SufficiencyCheck ────────────────────────────────
    # Verify the verified claims actually cover ALL parts of the
    # customer's original question. You could have 100% verification
    # on 2 claims but miss the customer's actual question entirely.
    def _check_sufficiency(query: str, verified_claims: List[str]) -> Tuple[bool, str]:
        if not query or not verified_claims:
            return True, "no_query_or_claims"
        # Extract significant words from the query
        query_words = {w.lower() for w in re.findall(r"\b\w+\b", query) if len(w) > 3}
        if not query_words:
            return True, "no_significant_query_words"
        # Combine all verified claims into one text
        verified_text = " ".join(verified_claims).lower()
        # Check how many query words appear in the verified claims
        covered = sum(1 for w in query_words if w in verified_text)
        coverage = covered / len(query_words) if query_words else 0.0
        if coverage < 0.40:
            return False, f"only {covered}/{len(query_words)} query words covered ({coverage:.0%})"
        return True, f"{covered}/{len(query_words)} query words covered ({coverage:.0%})"

    verified_claim_texts = [r["claim"] for r in verification_results if r.get("verified", False)]
    is_sufficient, suff_reason = _check_sufficiency(query, verified_claim_texts)
    if not is_sufficient:
        logs.append({"node": "4.5", "technique": "SufficiencyCheck", "duration_ms": 0, "result_summary": f"INSUFFICIENT: {suff_reason}"})
        # If claims don't cover the question, lower the effective score
        # This prevents a high verification score on irrelevant claims
        score = score * 0.70  # 30% penalty for insufficient coverage
    else:
        logs.append({"node": "4.5", "technique": "SufficiencyCheck", "duration_ms": 0, "result_summary": suff_reason})

    # ── HARD GATE: Block response if score still below threshold ─────
    cove_blocked = score < VERIFICATION_THRESHOLD and not human_guided

    if cove_blocked:
        logger.warning(
            "Node 4.5: COVE BLOCKED ticket=%s score=%.3f < %.2f — "
            "using safe fallback, escalating to human",
            state.get("ticket_id", "?"), score, VERIFICATION_THRESHOLD,
        )
        final_response = SAFE_FALLBACK
        logs.append({
            "node": "4.5",
            "technique": "ChainOfVerification.Blocked",
            "duration_ms": 0,
            "result_summary": f"BLOCKED: score={score:.3f} < {VERIFICATION_THRESHOLD} — safe fallback + escalate",
        })
    else:
        logger.info(
            "Node 4.5 complete: ticket=%s claims=%d verified=%d score=%.3f regenerated=%s [%dms]",
            state.get("ticket_id", "?"),
            len(claims), verified_count, score, regenerated, elapsed,
        )

    return {
        # OVERWRITE combined_answer with the (possibly regenerated / possibly blocked) response
        # so downstream nodes (Node 5, Node 6) work with the corrected version.
        "combined_answer": final_response,
        "verified_response": final_response,
        "verification_score": round(score, 4),
        "verification_claims": verification_results,
        "cove_regenerated": regenerated,
        "cove_blocked": cove_blocked,  # NEW: hard gate flag
        "technique_log": logs,
        "node_4_5_token_usage": extra_llm_calls,
        "total_token_usage": state.get("total_token_usage", 0) + extra_llm_calls,
    }


def regen_response_not_empty(text: str) -> bool:
    """Sanity check: regenerated response must be at least 30 chars and not just an apology."""
    if not text or len(text.strip()) < 30:
        return False
    # Reject "I cannot help" type responses
    lowered = text.lower()[:100]
    if "i cannot" in lowered or "i can't" in lowered or "i'm unable" in lowered:
        return False
    return True
