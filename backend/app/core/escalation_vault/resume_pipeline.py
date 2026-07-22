"""
Resume Pipeline — Re-process Escalated Tickets with Human Guidance

When PARWA escalates a ticket to JARVIS and a human provides guidance,
this module picks up the escalation from the vault, incorporates the
human's input, re-runs reasoning, and produces an improved response.

Flow:
  1. Load escalation from vault (full pipeline state + human guidance)
  2. Build enriched context (original knowledge + human guidance)
  3. Run mini-pipeline:
     a. Incorporate human guidance into reasoning context
     b. Generate improved response (LLM: CoT + Reflexion)
     c. Validate against knowledge base (non-LLM)
     d. Quality check (must exceed original quality)
  4. Save result back to vault
  5. If CRM ticket exists, push result to CRM
  6. Update vault CRM status

Quality Threshold:
  - Original quality from Node 8: typically 0.70-0.85
  - Resume must achieve: >= 0.88 (higher than Node 8's threshold of 0.85)
  - If resume also fails: mark as "failed" → requires manual human handling
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("parwa.resume_pipeline")

# Resume quality threshold — must be higher than Node 8's 0.85
RESUME_QUALITY_THRESHOLD = 0.88


async def resume_escalated_ticket(
    escalation_id: str,
    tenant_id: str = "",
) -> Dict[str, Any]:
    """Resume an escalated ticket with human guidance.

    This is the main entry point called by the API endpoint.

    Returns:
        {
            "success": True/False,
            "escalation_id": "...",
            "reprocess_result": "improved response",
            "reprocess_quality": 0.92,
            "crm_push": {"success": True/False},
        }
    """
    start = time.time()
    logs: List[Dict[str, Any]] = []

    # ── Step 1: Load from vault ─────────────────────────────
    from app.core.escalation_vault.vault_manager import VaultManager

    escalation = await VaultManager.load_for_resume(escalation_id)
    if not escalation:
        return {
            "success": False,
            "escalation_id": escalation_id,
            "error": "Escalation not found or not eligible for resume",
        }

    tenant_id = tenant_id or escalation.get("tenant_id", "")
    original_quality = escalation.get("quality_score", 0.0)
    human_guidance = escalation.get("human_guidance", "")
    original_query = escalation.get("original_query", "")

    logs.append({
        "step": "load", "duration_ms": 0,
        "result": f"loaded escalation={escalation_id[:8]} quality={original_quality:.2f}",
    })

    logger.info(
        "Resume Pipeline: Starting escalation=%s original_quality=%.2f",
        escalation_id[:8], original_quality,
    )

    # ── Step 2: Build enriched context ─────────────────────
    knowledge_docs = escalation.get("knowledge_context", [])
    wiki_c = escalation.get("wiki_section_c", [])
    knowledge_str = "\n".join(d.get("content", "") if isinstance(d, dict) else str(d) for d in knowledge_docs)
    if wiki_c:
        knowledge_str += "\n\n" + "\n".join(
            d.get("content", "") if isinstance(d, dict) else str(d) for d in wiki_c
        )

    crm_data_str = str(escalation.get("crm_data", {}))
    customer_ctx = escalation.get("customer_context", {})
    previous_attempts = escalation.get("previous_attempts", [])
    failure_analysis = escalation.get("failure_analysis", "")
    ticket_type = escalation.get("ticket_type", "general")
    complexity = escalation.get("complexity", "complex")
    required_action = escalation.get("required_action", "provide_info")

    enriched_context = f"""HUMAN GUIDANCE (from support agent):
{human_guidance}

ORIGINAL KNOWLEDGE BASE:
{knowledge_str[:2000]}

CUSTOMER DATA:
{crm_data_str[:500]}

PREVIOUS ATTEMPTS THAT FAILED:
{'; '.join(previous_attempts[:3]) if previous_attempts else 'None'}

WHY PREVIOUS ATTEMPTS FAILED:
{failure_analysis[:500]}

TICKET TYPE: {ticket_type}
COMPLEXITY: {complexity}
REQUIRED ACTION: {required_action}"""

    logs.append({"step": "enrich", "duration_ms": 0, "result": "context_built"})

    # ── Step 3: Run mini-pipeline ──────────────────────────

    # 3a. Generate improved response with CoT (LLM call #1)
    try:
        from app.core.parwa_pipeline.llm_client import llm_call

        cot_prompt = f"""You are a customer support AI that previously failed to answer a customer's question.
A human support agent has now provided guidance. Use this guidance PLUS the knowledge base to produce the BEST possible response.

Customer's Question: "{original_query}"

{enriched_context}

Instructions:
1. Start with the human agent's guidance as your primary direction
2. Cross-reference with the knowledge base to ensure accuracy
3. Address each part of the customer's question clearly
4. Be specific with any amounts, dates, or steps
5. If the guidance conflicts with knowledge base, prefer the human guidance (they have more context)

Write the complete customer response:"""

        improved_response = await llm_call(cot_prompt, max_tokens=600)
        logs.append({"step": "cot_reasoning", "duration_ms": 0, "result": "response_generated"})
        llm_calls = 1
    except Exception as e:
        logger.error("Resume Pipeline: CoT generation failed: %s", e)
        # Fallback: craft a safe wrapper around human guidance
        improved_response = (
            f"Thank you for your patience. Based on our review of your request:\n\n"
            f"{human_guidance}\n\n"
            f"If you need further assistance, please don't hesitate to reach out."
        )
        logs.append({"step": "cot_reasoning", "duration_ms": 0, "result": f"fallback: {str(e)[:100]}", "fallback_used": True})
        llm_calls = 0

    # 3b. Reflexion: Validate the improved response (LLM call #2)
    try:
        reflexion_prompt = f"""Review this customer support response for quality.

Customer Question: "{original_query}"
Response: {improved_response}
Human Guidance Used: {human_guidance}
Knowledge: {knowledge_str[:1000]}

Evaluate:
1. Does the response fully address the customer's question?
2. Is it consistent with the human agent's guidance?
3. Are there any factual errors or inconsistencies?

VALID: YES/NO
CONFIDENCE: <0.0-1.0>
ISSUES: <any issues found or "none">"""

        reflexion_result = await llm_call(reflexion_prompt, max_tokens=200)
        valid = "VALID: YES" in reflexion_result.upper()

        import re
        conf_match = re.search(r"CONFIDENCE:\s*([\d.]+)", reflexion_result)
        reflexion_confidence = float(conf_match.group(1)) if conf_match else 0.8
        if reflexion_confidence > 1:
            reflexion_confidence /= 100

        logs.append({
            "step": "reflexion",
            "duration_ms": 0,
            "result": f"valid={valid} conf={reflexion_confidence:.2f}",
        })
        llm_calls += 1
    except Exception as e:
        logger.error("Resume Pipeline: Reflexion failed: %s", e)
        reflexion_confidence = 0.8
        valid = True
        logs.append({"step": "reflexion", "duration_ms": 0, "result": f"error: {str(e)[:100]}"})

    # 3c. Non-LLM quality checks
    import re as re_mod

    # GSD: Check answer has substantive parts
    parts = [p.strip() for p in improved_response.split("\n\n") if p.strip()]
    gsd_score = sum(1.0 for p in parts if len(p) >= 20) / max(len(parts), 1)

    # Knowledge alignment: How much of the response uses KB terms
    kb_words = set(knowledge_str.lower().split())
    ans_words = set(improved_response.lower().split())
    kb_alignment = len(kb_words & ans_words) / max(len(ans_words), 1)

    # Guidance incorporation: Check if human guidance terms are in response
    guidance_words = set(human_guidance.lower().split())
    guidance_alignment = len(guidance_words & ans_words) / max(len(guidance_words), 1)

    # ThoT: Coherence check
    sentences = [s.strip() for s in improved_response.replace("!", ".").split(".") if s.strip()]
    coherence = 1.0 if sentences and sum(len(s.split()) for s in sentences) / len(sentences) >= 3 else 0.7

    # Length check
    length_ok = 1.0 if len(improved_response) >= 50 else 0.5

    logs.append({
        "step": "non_llm_quality",
        "duration_ms": 0,
        "result": f"gsd={gsd_score:.2f} kb={kb_alignment:.2f} guide={guidance_alignment:.2f} coherence={coherence:.2f}",
    })

    # 3d. Calculate overall quality
    resume_quality = (
        reflexion_confidence * 0.35 +  # LLM validation is most important
        gsd_score * 0.20 +              # Good structure
        kb_alignment * 0.15 +           # Uses knowledge base
        guidance_alignment * 0.20 +     # Incorporates human guidance
        coherence * 0.10                # Coherent sentences
    )

    passed = resume_quality >= RESUME_QUALITY_THRESHOLD

    logs.append({
        "step": "quality_check",
        "duration_ms": 0,
        "result": f"quality={resume_quality:.4f} threshold={RESUME_QUALITY_THRESHOLD} passed={passed}",
    })

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Resume Pipeline: Complete escalation=%s quality=%.4f passed=%s [%dms] llm=%d",
        escalation_id[:8], resume_quality, passed, elapsed, llm_calls,
    )

    # ── Step 4: Save result to vault ─────────────────────────
    if passed:
        await VaultManager.save_resume_result(
            escalation_id=escalation_id,
            result=improved_response,
            quality_score=resume_quality,
            technique_log=logs,
        )
    else:
        # Mark as failed — human needs to handle directly
        from app.core.escalation_vault.vault_db import REPROCESS_FAILED, get_vault_db
        vault_db = get_vault_db()
        # Save the result first, then override reprocess_status to FAILED
        await vault_db.update_reprocess_result(
            escalation_id, improved_response, resume_quality, logs
        )
        # Properly persist REPROCESS_FAILED status to storage
        await vault_db.update_reprocess_status_direct(
            escalation_id, REPROCESS_FAILED
        )

    # ── Step 5: Push to CRM if applicable ───────────────────
    crm_push = {"success": False, "reason": "no_crm_ticket"}
    crm_ticket_id = escalation.get("crm_ticket_id", "")
    crm_provider = escalation.get("crm_provider", "")

    if crm_ticket_id and crm_provider and passed:
        try:
            from app.core.crm_bridge.crm_bridge import CRMBridge

            crm_push = await CRMBridge.push_resume_result(
                provider=crm_provider,
                ticket_id=crm_ticket_id,
                response=improved_response,
                quality_score=resume_quality,
                human_guidance=human_guidance,
            )

            # Update vault CRM status
            await VaultManager.update_crm_push_back(
                escalation_id=escalation_id,
                status="updated" if crm_push.get("success") else "failed",
                crm_response=crm_push,
            )
        except Exception as e:
            logger.error("Resume Pipeline: CRM push failed: %s", e)
            crm_push = {"success": False, "reason": str(e)}

    return {
        "success": passed,
        "escalation_id": escalation_id,
        "original_ticket_id": escalation.get("original_ticket_id", ""),
        "reprocess_result": improved_response if passed else "",
        "reprocess_quality": round(resume_quality, 4),
        "quality_passed": passed,
        "llm_calls": llm_calls,
        "technique_log": logs,
        "crm_push": crm_push,
        "crm_ticket_id": crm_ticket_id,
        "elapsed_ms": elapsed,
    }


async def auto_resume_pending(tenant_id: str) -> Dict[str, Any]:
    """Auto-resume all escalations that have human guidance pending reprocess.

    Called by a scheduled job or API endpoint.
    """
    from app.core.escalation_vault.vault_manager import VaultManager

    pending = await VaultManager.get_pending_resumes(tenant_id)
    results = []
    for esc in pending:
        result = await resume_escalated_ticket(esc["escalation_id"], tenant_id)
        results.append(result)

    return {
        "tenant_id": tenant_id,
        "total_pending": len(pending),
        "results": results,
        "resolved": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
    }
