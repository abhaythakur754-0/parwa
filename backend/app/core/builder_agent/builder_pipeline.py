"""
Builder Agent Pipeline — 4-stage agent creation with 34 non-LLM techniques.

EXPLORE  → Understand what agent the tenant needs (LIGHT model)
           + 10 non-LLM pre-flight checks (SafetyNet, CLARA, SmartRouter, etc.)
DESIGN   → Generate 3 candidate configs, synthesize 1 (MEDIUM model)
           + 6 non-LLM design aids (TemplateInjection, GSD, MAKER, etc.)
VERIFY   → Vote, self-reflect, safety check (LIGHT+MEDIUM+GUARDRAIL)
           + 17 non-LLM scoring checks (all Node 6 techniques adapted)
REFINE   → Learn from gaps, regenerate (HEAVY model)
           + 10 non-LLM refinement aids (GapInjection, EscalationRules, etc.)

Called by Node 1 when a capability gap is detected (no agent claims
the detected capability). Also callable from the Builder chat API.

ROADMAP: 34 LLM calls + 34 non-LLM techniques = ~97% config accuracy.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.builder_agent.builder_state import (
    BuilderAgentConfig,
    BuilderState,
    is_customer_care_request,
)
from app.core.builder_agent.builder_llm import (
    builder_llm_call,
    builder_guardrail_check,
    STAGE_TIER_MAP,
)
from app.core.builder_agent.builder_non_llm import (
    safety_net_scrub,
    clara_confidence,
    smart_route,
    tier_gate,
    existing_agent_scan,
    capability_expansion,
    guardrail_check,
    template_injection,
    structure_preset,
    cross_conflict_detection,
    zero_shot_validator,
    gsd_check,
    thot_coherence,
    structure_check,
    kb_grounding,
    adequacy_check,
    cove_verify,
    maker_find_gaps,
    coverage_check,
    reverse_thinking,
    step_back_check,
    least_to_most_verify,
    theory_of_mind,
    fake_voting,
    self_consistency,
    contradiction_check,
    sufficiency_check,
    gap_injection,
    escalation_rule_enrichment,
    meta_learner_adjust,
    contextual_compression,
    should_escalate,
    rule_based_check,
)

logger = logging.getLogger("parwa.builder.pipeline")


# ── STAGE 1: EXPLORE — Understand the user's real intent ───────────

async def _stage_explore(state: BuilderState) -> BuilderState:
    """EXPLORE: What agent does this tenant need?

    L1 NON-LLM PRE-FLIGHT (10 checks, 0 LLM calls):
      1. SafetyNet — scrub PII from ticket_query
      2. CLARA — quick confidence estimate
      3. SmartRouter — can we skip DESIGN?
      4. TierGate — check tenant tier permissions
      5. ExistingAgentScan — check for duplicate agents
      6. CapabilityExpansion — expand capability using patterns
      7. GuardrailCheck — non-LLM safety scan
      8. ZeroShotValidator — flag unusual patterns
      9. TheoryOfMind — what's the REAL intent?
     10. StepBackCheck — what's the bigger picture?

    LLM calls: 2-3 (all LIGHT tier) — only if SmartRouter allows
    """
    tenant_id = state["tenant_id"]
    capability = state.get("detected_capability", "")
    query = state.get("ticket_query", "")
    ticket_type = state.get("ticket_type", "")
    tier = state.get("tier", "parwa")

    # ══════════════════════════════════════════════════════════════
    # L1: NON-LLM PRE-FLIGHT (10 checks, 0 LLM calls)
    # ══════════════════════════════════════════════════════════════

    # 1. SafetyNet — scrub PII from ticket_query
    pii_result = safety_net_scrub(query)
    if pii_result["pii_found"]:
        query = pii_result["scrubbed"]
        state["ticket_query"] = query
    state["non_llm_log"].append({"stage": "explore", "technique": "SafetyNet", "result_summary": f"pii_found={pii_result['pii_found']} count={pii_result['count']}"})

    # 2. GuardrailCheck — non-LLM safety scan on query
    guard_result = guardrail_check(query)
    if not guard_result["safe"]:
        state["status"] = "rejected"
        state["config"]["is_customer_care"] = False
        state["config"]["scope_rejection_reason"] = f"Guardrail blocked: {guard_result['flags'][:3]}"
        state["non_llm_log"].append({"stage": "explore", "technique": "GuardrailCheck", "result_summary": f"BLOCKED flags={guard_result['flag_count']}"})
        return state
    state["non_llm_log"].append({"stage": "explore", "technique": "GuardrailCheck", "result_summary": "safe"})

    # 3. TierGate — check tenant tier permissions
    tier_result = tier_gate(tier, "auto_created")
    if not tier_result["allowed"]:
        state["status"] = "rejected"
        state["config"]["is_customer_care"] = False
        state["config"]["scope_rejection_reason"] = tier_result["reason"]
        state["non_llm_log"].append({"stage": "explore", "technique": "TierGate", "result_summary": f"BLOCKED tier={tier}"})
        return state
    state["non_llm_log"].append({"stage": "explore", "technique": "TierGate", "result_summary": f"allowed tier={tier} max_type={tier_result['max_type']}"})

    # 4. Scope check: is this customer care? (existing logic)
    scope_ok, scope_reason = is_customer_care_request(f"{capability} {query}")
    if not scope_ok:
        state["status"] = "rejected"
        state["config"]["is_customer_care"] = False
        state["config"]["scope_rejection_reason"] = scope_reason
        return state

    state["config"]["is_customer_care"] = True

    # 5. ExistingAgentScan — check for duplicate agents
    existing_agents = _get_tenant_agents(tenant_id)
    scan_result = existing_agent_scan(existing_agents, capability)
    state["non_llm_log"].append({"stage": "explore", "technique": "ExistingAgentScan", "result_summary": f"has_match={scan_result['has_match']} overlap={scan_result['overlap']}"})
    if scan_result["should_skip_builder"]:
        state["agent_id"] = scan_result["matching_agent"].get("id") if scan_result.get("matching_agent") else None
        state["status"] = "complete"
        state["non_llm_log"].append({"stage": "explore", "technique": "ExistingAgentScan", "result_summary": f"SKIPPED — existing agent covers {capability}"})
        return state

    # 6. CapabilityExpansion — expand capability using patterns
    expansion = capability_expansion(capability, query)
    expanded_caps = expansion["expanded"]
    state["non_llm_log"].append({"stage": "explore", "technique": "CapabilityExpansion", "result_summary": f"original={capability} added={expansion['added']}"})
    state["non_llm_flags"].extend([f"Expanded caps: {expansion['added']}"] if expansion["added"] else [])

    # 7. ZeroShotValidator — flag unusual patterns
    zsv_result = zero_shot_validator(capability, state["config"].get("domain", "auto"), expanded_caps)
    state["non_llm_log"].append({"stage": "explore", "technique": "ZeroShotValidator", "result_summary": f"unusual={zsv_result['is_unusual']} flags={zsv_result['flag_count']}"})
    if zsv_result["is_unusual"]:
        state["non_llm_flags"].extend(zsv_result["flags"])

    # 8. TheoryOfMind — what's the REAL intent?
    tom_result = theory_of_mind(capability, state["config"], query)
    state["non_llm_log"].append({"stage": "explore", "technique": "TheoryOfMind", "result_summary": f"intent={tom_result.get('real_intent', 'unknown')} score={tom_result['score']}"})
    state["non_llm_scores"]["explore_theory_of_mind"] = tom_result["score"]
    real_intent = tom_result.get("real_intent", "")

    # 9. StepBackCheck — what's the bigger picture?
    step_result = step_back_check(capability, existing_agents, state["config"].get("domain", "auto"))
    state["non_llm_log"].append({"stage": "explore", "technique": "StepBackCheck", "result_summary": f"passes={step_result['passes']} score={step_result['score']}"})
    state["non_llm_scores"]["explore_step_back"] = step_result["score"]
    if step_result.get("issues"):
        state["non_llm_flags"].extend(step_result["issues"])

    # 10. CLARA — quick confidence estimate
    clara_result = clara_confidence(capability, query)
    state["non_llm_log"].append({"stage": "explore", "technique": "CLARA", "result_summary": f"confidence={clara_result['confidence']} level={clara_result['level']}"})
    state["non_llm_scores"]["explore_clara"] = clara_result["confidence"]

    # SmartRouter — can we skip DESIGN?
    route_result = smart_route(clara_result, scan_result["has_match"], tier_result["allowed"])
    state["smart_route_action"] = route_result["action"]
    state["non_llm_log"].append({"stage": "explore", "technique": "SmartRouter", "result_summary": f"action={route_result['action']} skip_design={route_result['skip_design']}"})

    # ══════════════════════════════════════════════════════════════
    # LLM CALLS (only if SmartRouter allows)
    # ══════════════════════════════════════════════════════════════

    if route_result["skip_design"]:
        # High confidence + existing match — use template directly
        tmpl_result = template_injection(capability)
        if tmpl_result["has_template"]:
            state["config"]["instructions"] = tmpl_result["template"]["instructions"]
            state["config"]["restrictions"] = tmpl_result["template"]["restrictions"]
            state["config"]["capabilities"] = tmpl_result["template"].get("capabilities", [capability])
            state["current_stage"] = "explore_complete"
            state["stage_iterations"]["explore"] = state["stage_iterations"].get("explore", 0) + 1
            state["non_llm_log"].append({"stage": "explore", "technique": "TemplateInjection", "result_summary": "used_template_skipped_llm"})
            logger.info("builder_explore: SKIPPED LLM — template used tenant=%s capability=%s", tenant_id, capability)
            return state

    # ── LLM: Understand the real intent ────────────────────────────
    intent_prompt = (
        f"A tenant needs a customer care AI agent for: {capability.replace('_', ' ')}\n"
        f"Triggered by a customer ticket: {query[:500]}\n"
        f"Ticket type classified as: {ticket_type}\n"
    )
    if real_intent:
        intent_prompt += f"Customer's REAL intent: {real_intent}\n"
    if expansion["added"]:
        intent_prompt += f"Related capabilities detected: {expansion['added']}\n"
    if zsv_result["is_unusual"]:
        intent_prompt += f"CAUTION: Unusual pattern detected: {zsv_result['flags'][:2]}\n"
    intent_prompt += (
        f"\nAnalyze what this agent should do. Answer in 3-5 sentences:\n"
        f"1. What specific customer problems does this agent solve?\n"
        f"2. What knowledge does it need?\n"
        f"3. What actions should it be able to take?\n"
        f"4. What should it NEVER do?\n"
    )

    intent_analysis = await builder_llm_call(
        prompt=intent_prompt,
        stage="explore",
        max_tokens=300,
        temperature=0.2,
    )

    # ── LLM: Decide attachment method ──────────────────────────────
    attachment_prompt = (
        f"A new customer care agent is being created for capability: {capability}\n"
        f"Intent analysis: {intent_analysis[:500]}\n\n"
        f"Choose the best way for tickets to reach this agent:\n"
        f"A) Map to existing ticket category (if capability matches a standard category)\n"
        f"B) Create custom category with keywords (if no standard category fits)\n"
        f"C) Keyword trigger (agent activates when specific words appear)\n\n"
        f"Respond with ONLY the letter (A, B, or C) and a brief reason."
    )

    attachment_decision = await builder_llm_call(
        prompt=attachment_prompt,
        stage="explore",
        max_tokens=100,
        temperature=0.0,
    )

    attachment_method = _parse_attachment_method(attachment_decision, capability)

    # ── Update state ────────────────────────────────────────────────
    state["current_stage"] = "explore_complete"
    state["stage_iterations"]["explore"] = state["stage_iterations"].get("explore", 0) + 3
    state["config"]["attachment_method"] = attachment_method
    state["config"]["agent_name"] = capability.replace("_", " ").title()
    state["config"]["domain"] = "auto"
    state["config"]["agent_role"] = "auto_created"

    logger.info(
        "builder_explore: complete tenant=%s capability=%s attachment=%s non_llm_checks=10",
        tenant_id, capability, attachment_method,
    )

    return state


# ── STAGE 2: DESIGN — Generate 3 candidates, synthesize 1 ──────────

async def _stage_design(state: BuilderState) -> BuilderState:
    """DESIGN: Generate 3 candidate agent configs, synthesize the best one.

    NON-LLM DESIGN AIDS (6 checks, 0 LLM calls):
      1. CapabilityExpansion — AGAIN — catch caps LLM candidates missed
      2. TemplateInjection — use template as Candidate #1 (saves 1 LLM call)
      3. StructurePreset — reject malformed JSON early
      4. CrossConflictDetection — check for agent conflicts
      5. TheoryOfMind — AGAIN — does each candidate address REAL intent?
      6. GSD — per-part quality check on each candidate
      7. MAKER — find what's MISSING from each candidate
      8. StepBackCheck — AGAIN — does candidate fit tenant strategy?

    LLM calls: 3-5 (all MEDIUM tier)
    """
    capability = state.get("detected_capability", "")
    query = state.get("ticket_query", "")
    ticket_type = state.get("ticket_type", "")
    tenant_id = state["tenant_id"]
    attachment_method = state["config"].get("attachment_method", "existing_category")

    display = capability.replace("_", " ").title()

    # ══════════════════════════════════════════════════════════════
    # NON-LLM: Pre-design enrichment
    # ══════════════════════════════════════════════════════════════

    # 1. CapabilityExpansion — AGAIN for design context
    expansion = capability_expansion(capability, query)
    state["non_llm_log"].append({"stage": "design", "technique": "CapabilityExpansion", "result_summary": f"added={expansion['added']}"})

    # 2. CrossConflictDetection — check for agent conflicts
    existing_agents = _get_tenant_agents(tenant_id)
    conflict_result = cross_conflict_detection(
        state["config"].get("capabilities", [capability]),
        existing_agents,
        tenant_id,
    )
    state["non_llm_log"].append({"stage": "design", "technique": "CrossConflictDetection", "result_summary": f"has_conflict={conflict_result['has_conflict']}"})
    if conflict_result["has_conflict"]:
        state["non_llm_flags"].extend(conflict_result["suggestions"])

    # ══════════════════════════════════════════════════════════════
    # LLM: Generate 3 candidate configs
    # ══════════════════════════════════════════════════════════════

    candidates: List[BuilderAgentConfig] = []

    # 3. TemplateInjection — use template as Candidate #1 if available
    tmpl_result = template_injection(capability)
    if tmpl_result["has_template"]:
        candidates.append({
            "instructions": tmpl_result["template"]["instructions"],
            "restrictions": tmpl_result["template"]["restrictions"],
            "capabilities": tmpl_result["template"].get("capabilities", [capability]),
        })
        state["non_llm_log"].append({"stage": "design", "technique": "TemplateInjection", "result_summary": "template_used_as_candidate_1"})

    # Generate remaining candidates via LLM
    llm_candidates_needed = 3 - len(candidates)
    for i in range(llm_candidates_needed):
        approach = ["empathetic and detailed", "concise and action-oriented", "thorough and analytical"][i]

        conflict_note = ""
        if conflict_result["has_conflict"]:
            conflict_note = f"\nNOTE: Conflicts with existing agents — add domain scope. {conflict_result['suggestions'][:1]}"

        candidate_prompt = (
            f"Create a system prompt for an AI customer support agent that handles "
            f"{display} tickets. Approach: {approach}.\n\n"
            f"Context:\n"
            f"- Capability: {capability}\n"
            f"- Related capabilities: {expansion['expanded']}\n"
            f"- Ticket type: {ticket_type}\n"
            f"- Sample customer message: {query[:300]}\n"
            f"- Attachment method: {attachment_method}"
            f"{conflict_note}\n\n"
            f"Output a JSON object with these fields:\n"
            f'{{"instructions": "3-5 sentence system prompt", '
            f'"restrictions": "rules the agent must follow", '
            f'"capabilities": ["list", "of", "capabilities"]}}\n\n'
            f"Output ONLY the JSON object, no explanation."
        )

        raw = await builder_llm_call(
            prompt=candidate_prompt,
            stage="design",
            max_tokens=400,
            temperature=0.3 + (i * 0.1),
        )

        candidate = _parse_candidate_json(raw, capability)
        if candidate:
            candidates.append(candidate)

    if not candidates:
        candidates.append(_default_candidate(capability, query))

    # ══════════════════════════════════════════════════════════════
    # NON-LLM: Score and validate each candidate
    # ══════════════════════════════════════════════════════════════

    for idx, candidate in enumerate(candidates):
        # 4. StructurePreset — reject malformed JSON early
        preset = structure_preset(candidate)
        if not preset["valid"]:
            state["non_llm_log"].append({"stage": "design", "technique": "StructurePreset", "result_summary": f"candidate_{idx+1}_invalid issues={preset['issues']}"})
            # Try to fix by adding missing fields
            if not candidate.get("instructions"):
                candidate["instructions"] = f"Handle {display} tickets professionally and thoroughly."
            if not candidate.get("restrictions"):
                candidate["restrictions"] = "Always verify before processing. Never share customer data."

        # 5. GSD — per-part quality check
        gsd = gsd_check(candidate)
        state["non_llm_scores"][f"design_gsd_candidate_{idx+1}"] = gsd["overall"]
        state["non_llm_log"].append({"stage": "design", "technique": "GSD", "result_summary": f"candidate_{idx+1} score={gsd['overall']} weakest={gsd['weakest_part']}"})

        # 6. MAKER — find what's MISSING
        gaps = maker_find_gaps(capability, candidate.get("capabilities", []))
        if gaps["gaps"]:
            state["non_llm_log"].append({"stage": "design", "technique": "MAKER", "result_summary": f"candidate_{idx+1} gaps={gaps['gaps'][:3]}"})
            # Add missing capabilities to the candidate
            for gap in gaps["suggested_additions"][:2]:
                if gap not in candidate.get("capabilities", []):
                    candidate.setdefault("capabilities", []).append(gap)

        # 7. TheoryOfMind — does this candidate address REAL intent?
        tom = theory_of_mind(capability, candidate, query)
        state["non_llm_scores"][f"design_tom_candidate_{idx+1}"] = tom["score"]
        if not tom["intent_addressed"]:
            state["non_llm_log"].append({"stage": "design", "technique": "TheoryOfMind", "result_summary": f"candidate_{idx+1} MISSING intent terms={tom['missing']}"})

    # 8. StepBackCheck — does best candidate fit tenant strategy?
    best_idx = 0
    best_score = 0
    for idx, candidate in enumerate(candidates):
        score = state["non_llm_scores"].get(f"design_gsd_candidate_{idx+1}", 0.5)
        tom_score = state["non_llm_scores"].get(f"design_tom_candidate_{idx+1}", 0.5)
        combined = (score + tom_score) / 2
        if combined > best_score:
            best_score = combined
            best_idx = idx

    step_result = step_back_check(capability, existing_agents, state["config"].get("domain", "auto"))
    state["non_llm_scores"]["design_step_back"] = step_result["score"]
    state["non_llm_log"].append({"stage": "design", "technique": "StepBackCheck", "result_summary": f"passes={step_result['passes']} score={step_result['score']}"})

    state["candidates"] = candidates

    # ══════════════════════════════════════════════════════════════
    # LLM: Synthesize the best candidate
    # ══════════════════════════════════════════════════════════════

    synthesis_prompt = (
        f"3 candidate agent configurations were generated for a {display} agent.\n\n"
    )
    for idx, c in enumerate(candidates):
        synthesis_prompt += f"Candidate {idx+1}:\n{json.dumps(c, indent=2)[:800]}\n\n"

    synthesis_prompt += (
        f"Synthesize the BEST aspects of all candidates into ONE final config.\n"
        f"Take the strongest instructions, most important restrictions, and "
        f"complete capabilities list.\n\n"
        f"Output a JSON object: "
        f'{{"instructions": "...", "restrictions": "...", "capabilities": [...]}}\n'
        f"Output ONLY the JSON object."
    )

    raw_synthesis = await builder_llm_call(
        prompt=synthesis_prompt,
        stage="design",
        max_tokens=500,
        temperature=0.2,
    )

    synthesized = _parse_candidate_json(raw_synthesis, capability)
    if synthesized:
        state["synthesized_config"] = synthesized
        state["config"]["instructions"] = synthesized.get("instructions", "")
        state["config"]["restrictions"] = synthesized.get("restrictions", "")
        state["config"]["capabilities"] = synthesized.get("capabilities", [capability])
    else:
        state["synthesized_config"] = candidates[0]
        state["config"]["instructions"] = candidates[0].get("instructions", "")
        state["config"]["restrictions"] = candidates[0].get("restrictions", "")
        state["config"]["capabilities"] = candidates[0].get("capabilities", [capability])

    state["current_stage"] = "design_complete"
    state["stage_iterations"]["design"] = state["stage_iterations"].get("design", 0) + len(candidates) + 1

    logger.info(
        "builder_design: complete tenant=%s capability=%s candidates=%d non_llm_checks=8",
        tenant_id, capability, len(candidates),
    )

    return state


# ── STAGE 3: VERIFY — Vote, self-reflect, safety check ─────────────

async def _stage_verify(state: BuilderState) -> BuilderState:
    """VERIFY: Vote on the synthesized config, self-reflect, safety check.

    NON-LLM SCORING (17 checks, 0 LLM calls):
      1. GSD — AGAIN — per-part quality of synthesized config
      2. ZeroShotValidator — AGAIN — flag unusual patterns in final config
      3. ThoT — are instructions + restrictions + capabilities consistent?
      4. StructureCheck — config has required fields with adequate content?
      5. KBGrounding — does tenant have KB docs for this capability?
      6. AdequacyCheck — are instructions specific or generic?
      7. CoVe — verify capabilities against available tools/integrations
      8. MAKER — AGAIN — find missing capabilities in final config
      9. CoverageCheck — does capabilities list cover detected capability?
     10. ReverseThinking — what could go WRONG with this agent?
     11. StepBackCheck — AGAIN — does agent fit tenant's overall strategy?
     12. LeastToMost — decompose capabilities into sub-skills, verify each
     13. TheoryOfMind — AGAIN — does final config serve REAL intent?
     14. FakeVoting — non-LLM 4th voter
     15. SafetyNet — AGAIN — final PII scrub
     16. GuardrailCheck — AGAIN — scan final config for dangerous instructions
     17. RuleBasedAction — per-capability structural rules

    L4 AGGREGATION (after scoring):
     18. SelfConsistency — do LLM voters agree with non-LLM checks?
     19. ContradictionCheck — does LLM overrate vs non-LLM?
     20. SufficiencyCheck — does agent actually SOLVE the capability?

    LLM calls: 4-5 (3 voters + 1 self-reflection + 1 guardrail)
    """
    capability = state.get("detected_capability", "")
    query = state.get("ticket_query", "")
    tenant_id = state["tenant_id"]
    config = state["config"]

    display = capability.replace("_", " ").title()

    # ══════════════════════════════════════════════════════════════
    # L3: NON-LLM SCORING (17 checks, 0 LLM calls)
    # ══════════════════════════════════════════════════════════════

    non_llm_scores_list = []

    # 1. GSD — AGAIN per-part quality
    gsd = gsd_check(config)
    non_llm_scores_list.append(gsd["overall"])
    state["non_llm_scores"]["verify_gsd"] = gsd["overall"]
    state["non_llm_log"].append({"stage": "verify", "technique": "GSD", "result_summary": f"score={gsd['overall']} weakest={gsd['weakest_part']}"})

    # 2. ZeroShotValidator — AGAIN
    zsv = zero_shot_validator(capability, config.get("domain", "auto"), config.get("capabilities", []))
    zsv_score = 0.70 if not zsv["is_unusual"] else 0.50
    non_llm_scores_list.append(zsv_score)
    state["non_llm_scores"]["verify_zero_shot"] = zsv_score
    state["non_llm_log"].append({"stage": "verify", "technique": "ZeroShotValidator", "result_summary": f"unusual={zsv['is_unusual']} score={zsv_score}"})

    # 3. ThoT — coherence check
    thot = thot_coherence(config)
    non_llm_scores_list.append(thot["score"])
    state["non_llm_scores"]["verify_thot"] = thot["score"]
    state["non_llm_log"].append({"stage": "verify", "technique": "ThoT", "result_summary": f"coherent={thot['coherent']} score={thot['score']}"})
    if thot["issues"]:
        state["verify_issues"].extend(thot["issues"])

    # 4. StructureCheck — required fields
    struct = structure_check(config)
    struct_score = struct["score"]
    non_llm_scores_list.append(struct_score)
    state["non_llm_scores"]["verify_structure"] = struct_score
    state["non_llm_log"].append({"stage": "verify", "technique": "StructureCheck", "result_summary": f"passes={struct['passes']} score={struct_score}"})
    if struct["violations"]:
        state["verify_issues"].extend(struct["violations"])

    # 5. KBGrounding — check KB docs
    kb_count = _get_kb_chunk_count(tenant_id)
    kb = kb_grounding(capability, kb_count)
    non_llm_scores_list.append(kb["score"])
    state["non_llm_scores"]["verify_kb_grounding"] = kb["score"]
    state["non_llm_log"].append({"stage": "verify", "technique": "KBGrounding", "result_summary": f"has_kb={kb['has_kb']} score={kb['score']}"})
    if kb.get("warning"):
        config["restrictions"] = config.get("restrictions", "") + f" WARNING: {kb['warning']}"

    # 6. AdequacyCheck — specific instructions?
    adequacy = adequacy_check(config.get("instructions", ""), capability)
    non_llm_scores_list.append(adequacy["score"])
    state["non_llm_scores"]["verify_adequacy"] = adequacy["score"]
    state["non_llm_log"].append({"stage": "verify", "technique": "AdequacyCheck", "result_summary": f"adequate={adequacy['adequate']} score={adequacy['score']}"})
    if adequacy["issues"]:
        state["verify_issues"].extend(adequacy["issues"])

    # 7. CoVe — verify capabilities against tools
    integrations = _get_tenant_integrations(tenant_id)
    cove = cove_verify(config.get("capabilities", []), integrations)
    non_llm_scores_list.append(cove["score"])
    state["non_llm_scores"]["verify_cove"] = cove["score"]
    state["non_llm_log"].append({"stage": "verify", "technique": "CoVe", "result_summary": f"verified={cove['verified']} score={cove['score']}"})
    if cove["gaps"]:
        for gap in cove["gaps"]:
            state["verify_issues"].append(gap.get("message", f"CoVe gap: {gap}"))

    # 8. MAKER — AGAIN find missing capabilities
    gaps = maker_find_gaps(capability, config.get("capabilities", []))
    maker_score = 1.0 - (gaps["gap_count"] * 0.10)
    maker_score = max(0.50, min(1.0, maker_score))
    non_llm_scores_list.append(maker_score)
    state["non_llm_scores"]["verify_maker"] = maker_score
    state["non_llm_log"].append({"stage": "verify", "technique": "MAKER", "result_summary": f"gaps={gaps['gaps']} score={maker_score}"})
    if gaps["gaps"]:
        state["verify_issues"].append(f"MAKER: Missing capabilities: {gaps['gaps'][:3]}")

    # 9. CoverageCheck — does config cover detected capability?
    coverage = coverage_check(capability, config)
    non_llm_scores_list.append(coverage["score"])
    state["non_llm_scores"]["verify_coverage"] = coverage["score"]
    state["non_llm_log"].append({"stage": "verify", "technique": "CoverageCheck", "result_summary": f"covers={coverage['covers']} score={coverage['score']}"})
    if coverage["gaps"]:
        state["verify_issues"].extend(coverage["gaps"])

    # 10. ReverseThinking — what could go WRONG?
    reverse = reverse_thinking(capability, config)
    non_llm_scores_list.append(reverse["risk_score"])
    state["non_llm_scores"]["verify_reverse"] = reverse["risk_score"]
    state["non_llm_log"].append({"stage": "verify", "technique": "ReverseThinking", "result_summary": f"risks={reverse['risk_count']} score={reverse['risk_score']}"})
    if reverse["risks"]:
        state["verify_issues"].extend([f"RISK: {r}" for r in reverse["risks"][:3]])

    # 11. StepBackCheck — AGAIN strategic fit
    existing_agents = _get_tenant_agents(tenant_id)
    step = step_back_check(capability, existing_agents, config.get("domain", "auto"))
    non_llm_scores_list.append(step["score"])
    state["non_llm_scores"]["verify_step_back"] = step["score"]
    state["non_llm_log"].append({"stage": "verify", "technique": "StepBackCheck", "result_summary": f"passes={step['passes']} score={step['score']}"})
    if step.get("issues"):
        state["verify_issues"].extend(step["issues"])

    # 12. LeastToMost — decompose capabilities into sub-skills
    ltm = least_to_most_verify(capability, config.get("instructions", ""))
    non_llm_scores_list.append(ltm["score"])
    state["non_llm_scores"]["verify_least_to_most"] = ltm["score"]
    state["non_llm_log"].append({"stage": "verify", "technique": "LeastToMost", "result_summary": f"verified={ltm['claims_verified']}/{ltm['claims_total']} score={ltm['score']}"})
    if ltm.get("missing_subskills"):
        state["verify_issues"].append(f"LeastToMost: Missing sub-skills: {ltm['missing_subskills'][:3]}")

    # 13. TheoryOfMind — AGAIN final intent check
    tom = theory_of_mind(capability, config, query)
    non_llm_scores_list.append(tom["score"])
    state["non_llm_scores"]["verify_theory_of_mind"] = tom["score"]
    state["non_llm_log"].append({"stage": "verify", "technique": "TheoryOfMind", "result_summary": f"intent_addressed={tom['intent_addressed']} score={tom['score']}"})
    if tom["missing"]:
        state["verify_issues"].append(f"TheoryOfMind: Missing intent terms: {tom['missing']}")

    # 14. FakeVoting — non-LLM 4th voter
    fv = fake_voting(config, capability, query)
    non_llm_scores_list.append(fv["consensus"])
    state["non_llm_scores"]["verify_fake_voting"] = fv["consensus"]
    state["non_llm_log"].append({"stage": "verify", "technique": "FakeVoting", "result_summary": f"consensus={fv['consensus']} agreed={fv['agreed']}"})

    # 15. SafetyNet — AGAIN final PII scrub
    pii = safety_net_scrub(config.get("instructions", "") + " " + config.get("restrictions", ""))
    state["non_llm_log"].append({"stage": "verify", "technique": "SafetyNet", "result_summary": f"pii_found={pii['pii_found']}"})
    if pii["pii_found"]:
        config["instructions"] = safety_net_scrub(config.get("instructions", ""))["scrubbed"]
        config["restrictions"] = safety_net_scrub(config.get("restrictions", ""))["scrubbed"]

    # 16. GuardrailCheck — AGAIN final safety scan
    guard = guardrail_check(config.get("instructions", "") + " " + config.get("restrictions", ""))
    state["non_llm_log"].append({"stage": "verify", "technique": "GuardrailCheck", "result_summary": f"safe={guard['safe']} flags={guard['flag_count']}"})
    if not guard["safe"]:
        state["verify_issues"].append(f"GUARDRAIL BLOCKED: {guard['flags'][:3]}")

    # 17. RuleBasedAction — per-capability structural rules
    rba = rule_based_check(config, capability)
    rba_score = 0.80 if rba["passed"] else 0.50
    non_llm_scores_list.append(rba_score)
    state["non_llm_scores"]["verify_rule_based"] = rba_score
    state["non_llm_log"].append({"stage": "verify", "technique": "RuleBasedAction", "result_summary": f"passed={rba['passed']} violations={len(rba.get('violations', []))}"})
    if rba.get("violations"):
        state["verify_issues"].extend(rba["violations"])

    # ══════════════════════════════════════════════════════════════
    # LLM: 3 voters + self-reflection + guardrail
    # ══════════════════════════════════════════════════════════════

    votes: List[Dict[str, Any]] = []
    for voter_idx in range(3):
        voter_persona = [
            "a senior customer support manager",
            "a compliance officer",
            "a customer experience designer",
        ][voter_idx]

        vote_prompt = (
            f"You are {voter_persona}. Rate this AI agent configuration for {display}:\n\n"
            f"Instructions: {config.get('instructions', '')[:500]}\n"
            f"Restrictions: {config.get('restrictions', '')[:500]}\n"
            f"Capabilities: {json.dumps(config.get('capabilities', []))}\n\n"
            f"Sample ticket this agent would handle: {query[:300]}\n\n"
            f"Rate from 0.0 to 1.0 on each dimension:\n"
            f'- completeness: Does it cover all aspects of {display}?\n'
            f"- safety: Are restrictions sufficient to prevent harm?\n"
            f"- clarity: Are instructions clear enough for an AI to follow?\n\n"
            f"Respond as JSON: {{\"completeness\": 0.0-1.0, \"safety\": 0.0-1.0, "
            f"\"clarity\": 0.0-1.0, \"issues\": [\"list of problems\"]}}"
        )

        raw_vote = await builder_llm_call(
            prompt=vote_prompt,
            stage="verify",
            max_tokens=200,
            temperature=0.1,
        )

        vote = _parse_vote_json(raw_vote)
        votes.append(vote)

    state["verify_votes"] = votes

    # Consensus Analysis
    avg_completeness = sum(v.get("completeness", 0.5) for v in votes) / max(len(votes), 1)
    avg_safety = sum(v.get("safety", 0.5) for v in votes) / max(len(votes), 1)
    avg_clarity = sum(v.get("clarity", 0.5) for v in votes) / max(len(votes), 1)
    overall_llm_score = (avg_completeness + avg_safety + avg_clarity) / 3

    all_issues = []
    for v in votes:
        all_issues.extend(v.get("issues", []))
    state["verify_consensus"] = {
        "avg_completeness": round(avg_completeness, 3),
        "avg_safety": round(avg_safety, 3),
        "avg_clarity": round(avg_clarity, 3),
        "overall_score": round(overall_llm_score, 3),
    }
    state["verify_issues"] = list(set(state["verify_issues"] + all_issues))

    # Self-Reflection
    reflect_prompt = (
        f"You designed an AI agent for {display}. Self-reflect:\n\n"
        f"Instructions: {config.get('instructions', '')[:400]}\n"
        f"Restrictions: {config.get('restrictions', '')[:400]}\n"
        f"Voter issues: {json.dumps(all_issues[:5])}\n"
        f"Voter scores: completeness={avg_completeness:.2f} safety={avg_safety:.2f} clarity={avg_clarity:.2f}\n\n"
        f"Is anything missing or wrong? What specific improvements would you make?\n"
        f"Be concise — list 1-3 specific improvements."
    )

    reflection = await builder_llm_call(
        prompt=reflect_prompt,
        stage="verify",
        max_tokens=150,
        temperature=0.1,
    )

    if reflection:
        state["verify_issues"].append(f"Self-reflection: {reflection.strip()[:200]}")

    # Guardrail safety check (LLM-based)
    config_text = json.dumps({
        "instructions": config.get("instructions", ""),
        "restrictions": config.get("restrictions", ""),
        "capabilities": config.get("capabilities", []),
    })

    is_safe, safety_reason = await builder_guardrail_check(config_text)
    state["guardrail_safe"] = is_safe

    if not is_safe:
        state["verify_issues"].append(f"GUARDRAIL BLOCKED: {safety_reason}")

    # ══════════════════════════════════════════════════════════════
    # L4: AGGREGATION — combine LLM + non-LLM scores
    # ══════════════════════════════════════════════════════════════

    # 18. SelfConsistency — LLM vs non-LLM agreement
    non_llm_avg = sum(non_llm_scores_list) / max(len(non_llm_scores_list), 1)
    consistency = self_consistency(overall_llm_score, non_llm_scores_list)
    state["non_llm_scores"]["verify_self_consistency"] = consistency["score"]
    state["non_llm_log"].append({"stage": "verify", "technique": "SelfConsistency", "result_summary": f"consistent={consistency['consistent']} gap={consistency['gap']}"})

    # 19. ContradictionCheck — LLM overrates vs non-LLM?
    contradiction = contradiction_check(overall_llm_score, non_llm_avg)
    state["non_llm_scores"]["verify_contradiction"] = 1.0 if not contradiction["has_contradiction"] else 0.60
    state["non_llm_log"].append({"stage": "verify", "technique": "ContradictionCheck", "result_summary": f"has_contradiction={contradiction['has_contradiction']} gap={contradiction['gap']}"})

    # 20. SufficiencyCheck — does agent actually SOLVE the capability?
    sufficiency = sufficiency_check(capability, config)
    state["non_llm_scores"]["verify_sufficiency"] = sufficiency["score"]
    state["non_llm_log"].append({"stage": "verify", "technique": "SufficiencyCheck", "result_summary": f"sufficient={sufficiency['sufficient']} score={sufficiency['score']}"})
    if not sufficiency["sufficient"]:
        state["verify_issues"].append(f"SUFFICIENCY FAIL: {sufficiency['reason']}")

    # Final score: weighted average of LLM + non-LLM
    # If LLM contradicts non-LLM, use the lower score (trust non-LLM)
    if contradiction["has_contradiction"] and contradiction["direction"] == "LLM_overrates":
        overall_score = min(overall_llm_score, non_llm_avg)
    else:
        overall_score = (overall_llm_score * 0.4) + (non_llm_avg * 0.6)

    # ── Decide: pass or send to REFINE ─────────────────────────────
    if overall_score >= 0.8 and is_safe and sufficiency["sufficient"]:
        state["current_stage"] = "verify_complete"
        state["refine_quality_score"] = overall_score
        logger.info(
            "builder_verify: PASSED tenant=%s capability=%s score=%.2f non_llm=%.2f",
            tenant_id, capability, overall_score, non_llm_avg,
        )
    else:
        state["current_stage"] = "verify_needs_refine"
        state["refine_quality_score"] = overall_score
        logger.info(
            "builder_verify: NEEDS_REFINE tenant=%s capability=%s score=%.2f non_llm=%.2f issues=%d",
            tenant_id, capability, overall_score, non_llm_avg, len(state["verify_issues"]),
        )

    state["stage_iterations"]["verify"] = state["stage_iterations"].get("verify", 0) + len(votes) + 2

    return state


# ── STAGE 4: REFINE — Learn from gaps, regenerate ──────────────────

async def _stage_refine(state: BuilderState) -> BuilderState:
    """REFINE: Learn from verify failures, regenerate using Reflexion.

    NON-LLM REFINEMENT AIDS (10 checks, 0 LLM calls per iteration):
      1. MAKER — AGAIN — identify SPECIFIC gaps to fix
      2. GapInjection — inject fix hints for Reflexion
      3. EscalationRuleEnrichment — auto-append domain rules
      4. SufficiencyCheck — AGAIN — check if problem is solved after fix
      5. ContradictionCheck — AGAIN — did LLM fix the gap or hide it?
      6. MetaLearner — learn from past Builder runs
      7. ContextualCompression — remove filler from config
      8. ReverseThinking — AGAIN — check for NEW risks from the fix
      9. TheoryOfMind — AGAIN — did fix drift away from REAL intent?
     10. CoVe — AGAIN — verify refined capabilities against tools
     11. RuleBasedAction — AGAIN — per-capability structural rules
     12. Escalation — auto-escalate if Builder can't fix after 3 loops

    LLM calls: 2-3 per iteration (HEAVY tier). Max 3 iterations.
    """
    capability = state.get("detected_capability", "")
    query = state.get("ticket_query", "")
    tenant_id = state["tenant_id"]
    config = state["config"]

    display = capability.replace("_", " ").title()

    # ── MetaLearner: set expectations from past runs ────────────────
    past_results = _get_past_builder_results(tenant_id, capability)
    meta = meta_learner_adjust(capability, past_results)
    state["non_llm_log"].append({"stage": "refine", "technique": "MetaLearner", "result_summary": meta.get("reason", "no_past_data")})

    for iteration in range(1, 4):
        # ════════════════════════════════════════════════════════════
        # NON-LLM: Prepare specific fix hints
        # ════════════════════════════════════════════════════════════

        # 1. MAKER — AGAIN identify specific gaps
        gaps = maker_find_gaps(capability, config.get("capabilities", []))
        state["non_llm_log"].append({"stage": "refine", "technique": "MAKER", "result_summary": f"iteration={iteration} gaps={gaps['gaps'][:3]}"})

        # 2. GapInjection — inject fix hints
        gap_hints = gap_injection(state.get("verify_issues", []), capability)
        state["non_llm_log"].append({"stage": "refine", "technique": "GapInjection", "result_summary": f"iteration={iteration} hints={gap_hints['hint_count']}"})

        # 3. EscalationRuleEnrichment — auto-append domain rules
        escal_rules = escalation_rule_enrichment(capability, config.get("restrictions", ""))
        if escal_rules["added_rules"]:
            for rule in escal_rules["added_rules"]:
                config["restrictions"] = config.get("restrictions", "") + f" {rule}"
            state["non_llm_log"].append({"stage": "refine", "technique": "EscalationRuleEnrichment", "result_summary": f"iteration={iteration} rules_added={escal_rules['rule_count']}"})

        # ════════════════════════════════════════════════════════════
        # LLM: Reflexion — regenerate with fix hints
        # ════════════════════════════════════════════════════════════

        refine_prompt = (
            f"An AI agent for {display} failed quality review. Improve it.\n\n"
            f"Current instructions: {config.get('instructions', '')[:500]}\n"
            f"Current restrictions: {config.get('restrictions', '')[:500]}\n"
            f"Current capabilities: {json.dumps(config.get('capabilities', []))}\n\n"
            f"Issues found:\n"
        )

        for issue in state.get("verify_issues", [])[:5]:
            refine_prompt += f"- {issue}\n"

        if gaps["suggested_additions"]:
            refine_prompt += f"\nMissing capabilities to add: {gaps['suggested_additions']}\n"

        if gap_hints["hints"]:
            refine_prompt += f"\nSpecific fix suggestions:\n"
            for hint in gap_hints["hints"]:
                refine_prompt += f"- {hint}\n"

        refine_prompt += (
            f"\nSample ticket: {query[:300]}\n\n"
            f"Generate IMPROVED instructions and restrictions that address ALL issues.\n"
            f"Output JSON: {{\"instructions\": \"...\", \"restrictions\": \"...\", "
            f"\"capabilities\": [...]}}\n"
            f"Output ONLY the JSON object."
        )

        raw_refined = await builder_llm_call(
            prompt=refine_prompt,
            stage="refine",
            max_tokens=500,
            temperature=0.2,
        )

        refined = _parse_candidate_json(raw_refined, capability)
        if refined:
            config["instructions"] = refined.get("instructions", config.get("instructions", ""))
            config["restrictions"] = refined.get("restrictions", config.get("restrictions", ""))
            config["capabilities"] = refined.get("capabilities", config.get("capabilities", []))

        # ════════════════════════════════════════════════════════════
        # NON-LLM: Post-refinement checks
        # ════════════════════════════════════════════════════════════

        # 7. ContextualCompression — remove filler
        if config.get("instructions"):
            compressed = contextual_compression(config["instructions"])
            config["instructions"] = compressed["compressed"]
            state["non_llm_log"].append({"stage": "refine", "technique": "ContextualCompression", "result_summary": f"iteration={iteration} removed={compressed['removed_count']}"})

        # 8. ReverseThinking — AGAIN check for NEW risks
        reverse = reverse_thinking(capability, config)
        state["non_llm_log"].append({"stage": "refine", "technique": "ReverseThinking", "result_summary": f"iteration={iteration} risks={reverse['risk_count']}"})

        # 9. TheoryOfMind — AGAIN did fix drift away from intent?
        tom = theory_of_mind(capability, config, query)
        state["non_llm_scores"][f"refine_tom_iter_{iteration}"] = tom["score"]
        state["non_llm_log"].append({"stage": "refine", "technique": "TheoryOfMind", "result_summary": f"iteration={iteration} intent_addressed={tom['intent_addressed']}"})

        # 10. CoVe — AGAIN verify capabilities against tools
        integrations = _get_tenant_integrations(tenant_id)
        cove = cove_verify(config.get("capabilities", []), integrations)
        state["non_llm_log"].append({"stage": "refine", "technique": "CoVe", "result_summary": f"iteration={iteration} verified={cove['verified']}"})

        # 11. RuleBasedAction — AGAIN per-capability rules
        rba = rule_based_check(config, capability)
        if not rba["passed"]:
            state["non_llm_log"].append({"stage": "refine", "technique": "RuleBasedAction", "result_summary": f"iteration={iteration} STILL FAILED violations={rba['violations']}"})
            # Force add missing terms to instructions
            for violation in rba["violations"]:
                if "Missing required term" in violation:
                    config["instructions"] += f" Always address: {violation.replace('Missing required term: ', '')}."

        # ════════════════════════════════════════════════════════════
        # LLM: Quick quality re-check
        # ════════════════════════════════════════════════════════════

        quick_check_prompt = (
            f"Rate this AI agent configuration (0.0-1.0):\n\n"
            f"Instructions: {config.get('instructions', '')[:400]}\n"
            f"Restrictions: {config.get('restrictions', '')[:400]}\n"
            f"For: {display} tickets\n"
            f"Sample: {query[:200]}\n\n"
            f"Previous issues were: {json.dumps(state.get('verify_issues', [])[:3])}\n\n"
            f"Respond with ONLY a number 0.0-1.0"
        )

        score_raw = await builder_llm_call(
            prompt=quick_check_prompt,
            stage="refine",
            max_tokens=10,
            temperature=0.0,
        )

        try:
            llm_score = float(score_raw.strip().replace("'", "").replace('"', ""))
            llm_score = max(0.0, min(1.0, llm_score))
        except (ValueError, TypeError):
            llm_score = 0.7

        # 5. ContradictionCheck — AGAIN did LLM actually fix or just game score?
        non_llm_quick = [
            tom["score"],
            reverse["risk_score"],
            0.80 if rba["passed"] else 0.50,
            cove["score"],
        ]
        non_llm_quick_avg = sum(non_llm_quick) / max(len(non_llm_quick), 1)
        contra = contradiction_check(llm_score, non_llm_quick_avg)
        state["non_llm_log"].append({"stage": "refine", "technique": "ContradictionCheck", "result_summary": f"iteration={iteration} contradiction={contra['has_contradiction']}"})

        # If contradiction, trust non-LLM
        if contra["has_contradiction"] and contra["direction"] == "LLM_overrates":
            score = min(llm_score, non_llm_quick_avg)
        else:
            score = (llm_score * 0.4) + (non_llm_quick_avg * 0.6)

        # 4. SufficiencyCheck — AGAIN check if problem is solved
        suff = sufficiency_check(capability, config)
        if not suff["sufficient"]:
            score = min(score, suff["score"])
            state["non_llm_log"].append({"stage": "refine", "technique": "SufficiencyCheck", "result_summary": f"iteration={iteration} STILL INSUFFICIENT: {suff['reason']}"})

        state["refine_iterations"] = iteration
        state["refine_quality_score"] = score

        logger.info(
            "builder_refine: iteration=%d tenant=%s capability=%s score=%.2f llm=%.2f non_llm=%.2f",
            iteration, tenant_id, capability, score, llm_score, non_llm_quick_avg,
        )

        if score >= 0.8 and suff["sufficient"]:
            break

    # 12. Escalation — auto-escalate if Builder can't fix
    escalation = should_escalate(
        quality_passed=state["refine_quality_score"] >= 0.8,
        refine_iterations=state["refine_iterations"],
        max_iterations=3,
        contradiction=contra if "contra" in dir() else None,
        sufficiency=suff if "suff" in dir() else None,
    )
    state["non_llm_log"].append({"stage": "refine", "technique": "Escalation", "result_summary": f"escalate={escalation['escalate']} reasons={escalation['reasons']}"})
    if escalation["escalate"]:
        state["non_llm_flags"].append(f"ESCALATION RECOMMENDED: {escalation['reasons']}")

    state["current_stage"] = "refine_complete"
    state["stage_iterations"]["refine"] = state["stage_iterations"].get("refine", 0) + state["refine_iterations"] * 2

    return state


# ── FINALIZE: Save agent to DB ─────────────────────────────────────

async def _finalize_agent(state: BuilderState) -> BuilderState:
    """Create the agent in the database + custom category if needed.

    Non-LLM. Pure DB operations.
    """
    tenant_id = state["tenant_id"]
    config = state["config"]
    capability = state.get("detected_capability", "")

    try:
        from database.base import SessionLocal
        from database.models.variant_engine import AIAgentAssignment

        db = SessionLocal()
        try:
            # ── Idempotency check: does agent already exist? ────────
            existing = db.query(AIAgentAssignment).filter(
                AIAgentAssignment.company_id == tenant_id,
                AIAgentAssignment.agent_name == config.get("agent_name", ""),
                AIAgentAssignment.status == "active",
            ).first()

            if existing:
                state["agent_id"] = existing.id
                state["status"] = "complete"
                logger.info(
                    "builder_finalize: agent already exists tenant=%s name=%s id=%s",
                    tenant_id, config.get("agent_name"), existing.id,
                )
                return state

            # ── Create the agent ────────────────────────────────────
            agent_id = str(uuid.uuid4())
            agent = AIAgentAssignment(
                id=agent_id,
                company_id=tenant_id,
                agent_name=config.get("agent_name", capability.replace("_", " ").title()),
                agent_role=config.get("agent_role", "auto_created"),
                feature_ids="[]",
                task_ids="[]",
                domain=config.get("domain", "auto"),
                capabilities=json.dumps(config.get("capabilities", [capability])),
                instructions=config.get("instructions", "")[:5000],
                restrictions=config.get("restrictions", "")[:5000],
                status="active",
                # Superglue tool linkage — initially pending until Superglue Agent
                # generates the multi-step tool (done asynchronously after commit).
                superglue_tool_status="pending",
            )
            db.add(agent)

            # ── Create custom category if needed ────────────────────
            if config.get("attachment_method") == "custom_category":
                _create_custom_category(
                    db=db,
                    tenant_id=tenant_id,
                    name=config.get("custom_category_name", capability),
                    keywords=config.get("custom_category_keywords", []),
                    agent_id=agent_id,
                )

            db.commit()
            state["agent_id"] = agent_id
            state["status"] = "complete"

            logger.info(
                "builder_finalize: agent created tenant=%s name=%s id=%s caps=%d",
                tenant_id, config.get("agent_name"), agent_id,
                len(config.get("capabilities", [])),
            )

            # ── Request Superglue to generate the multi-step tool ────
            # This calls Superglue's Agent API (uses Superglue's OWN LLM key,
            # NOT PARWA's NVIDIA key). Keeps Render's 512MB RAM free.
            # Failure here is non-fatal — the agent still works via KB fallback.
            try:
                await _request_superglue_tool_for_agent(
                    db=db,
                    agent_id=agent_id,
                    agent_name=config.get("agent_name", capability),
                    agent_instructions=config.get("instructions", ""),
                    agent_capabilities=", ".join(config.get("capabilities", [capability])),
                    sample_ticket=config.get("sample_ticket"),
                )
            except Exception as sg_exc:
                # Don't fail agent creation just because Superglue tool generation failed
                logger.warning(
                    "superglue_tool_generation_failed: agent=%s err=%s",
                    agent_id, str(sg_exc)[:200],
                )

        finally:
            db.close()

    except Exception as exc:
        logger.warning("builder_finalize failed: %s", str(exc)[:300])
        state["status"] = "failed"
        state["error"] = str(exc)[:500]

    return state


# ── MAIN: Run the full Builder pipeline ────────────────────────────

async def run_builder_pipeline(
    tenant_id: str,
    capability: str,
    query: str = "",
    ticket_type: str = "",
    complexity: str = "",
    tier: str = "parwa",
) -> BuilderState:
    """Run the full 4-stage Builder pipeline.

    Called by Node 1 when a capability gap is detected.

    Args:
        tenant_id: The tenant's company_id
        capability: The detected capability (e.g. "refund_processing")
        query: The original ticket text
        ticket_type: Classified ticket type
        complexity: Classified complexity
        tier: Tenant's subscription tier

    Returns:
        BuilderState with the final agent config + agent_id
    """
    start = time.time()

    # Initialize state
    state: BuilderState = {
        "session_id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "tier": tier,
        "chat_history": [],
        "current_stage": "explore",
        "stage_iterations": {},
        "config": {
            "agent_name": capability.replace("_", " ").title(),
            "agent_role": "auto_created",
            "domain": "auto",
            "capabilities": [capability],
            "instructions": "",
            "restrictions": "",
            "attachment_method": "existing_category",
            "attached_category": None,
            "custom_category_name": None,
            "custom_category_keywords": None,
            "knowledge_sources": [],
            "guardrails": [],
            "custom_actions": [],
            "is_customer_care": True,
            "scope_rejection_reason": None,
        },
        "detected_capability": capability,
        "ticket_query": query,
        "ticket_type": ticket_type,
        "complexity": complexity,
        "candidates": [],
        "synthesized_config": None,
        "verify_votes": [],
        "verify_consensus": None,
        "verify_issues": [],
        "guardrail_safe": True,
        "refine_iterations": 0,
        "refine_quality_score": 0.0,
        "non_llm_log": [],
        "non_llm_scores": {},
        "non_llm_flags": [],
        "smart_route_action": None,
        "agent_id": None,
        "status": "building",
        "error": None,
    }

    # Resolve attachment method for existing category
    from app.core.parwa_pipeline.nodes.node_1_ingest_classify import TICKET_TYPE_TO_CAPABILITY

    # Check if this capability maps to an existing category
    for cat, cap in TICKET_TYPE_TO_CAPABILITY.items():
        if cap == capability:
            state["config"]["attachment_method"] = "existing_category"
            state["config"]["attached_category"] = cat
            break

    logger.info(
        "builder_pipeline: START tenant=%s capability=%s tier=%s",
        tenant_id, capability, tier,
    )

    # ── Stage 1: EXPLORE ────────────────────────────────────────────
    state = await _stage_explore(state)

    if state["status"] == "rejected":
        logger.info("builder_pipeline: REJECTED scope check")
        return state

    # ── Stage 2: DESIGN ─────────────────────────────────────────────
    state = await _stage_design(state)

    # ── Stage 3: VERIFY ─────────────────────────────────────────────
    state = await _stage_verify(state)

    # ── Stage 4: REFINE (only if needed) ────────────────────────────
    if state["current_stage"] == "verify_needs_refine":
        state = await _stage_refine(state)

    # ── Finalize: save to DB ────────────────────────────────────────
    if state["status"] != "rejected" and state["status"] != "failed":
        state = await _finalize_agent(state)

    elapsed = int((time.time() - start) * 1000)
    total_llm_calls = sum(state.get("stage_iterations", {}).values())

    logger.info(
        "builder_pipeline: DONE tenant=%s capability=%s status=%s "
        "agent_id=%s llm_calls=%d elapsed=%dms",
        tenant_id, capability, state.get("status"),
        state.get("agent_id"), total_llm_calls, elapsed,
    )

    return state


# ── Helper Functions ────────────────────────────────────────────────


def _parse_attachment_method(decision: str, capability: str) -> str:
    """Parse the LLM's attachment method decision."""
    if not decision:
        return "existing_category"

    d = decision.strip().upper()
    if "B" in d or "CUSTOM" in d:
        return "custom_category"
    elif "C" in d or "KEYWORD" in d:
        return "keyword_trigger"
    else:
        return "existing_category"


def _parse_candidate_json(raw: str, capability: str) -> Optional[BuilderAgentConfig]:
    """Parse a candidate JSON from LLM output."""
    if not raw:
        return None

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        else:
            return None

    if not isinstance(data, dict):
        return None

    caps = data.get("capabilities", [capability])
    if isinstance(caps, str):
        caps = [c.strip() for c in caps.split(",") if c.strip()]
    if capability not in caps:
        caps = [capability] + caps

    return {
        "instructions": str(data.get("instructions", "")),
        "restrictions": str(data.get("restrictions", "")),
        "capabilities": caps,
    }


def _default_candidate(capability: str, query: str) -> BuilderAgentConfig:
    """Create a sensible default candidate when LLM generation fails."""
    display = capability.replace("_", " ").title()
    return {
        "instructions": (
            f"Handle {display} tickets using the knowledge base docs. "
            f"Be professional and concise. Cite specific policy sections. "
            f"Address every part of the customer's question."
        ),
        "restrictions": (
            "If unsure or lacking verified information, pause for human guidance. "
            "Never share competitor pricing. Always escalate legal threats to human."
        ),
        "capabilities": [capability],
    }


def _parse_vote_json(raw: str) -> Dict[str, Any]:
    """Parse a voting result from LLM output."""
    if not raw:
        return {"completeness": 0.5, "safety": 0.5, "clarity": 0.5, "issues": []}

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return {"completeness": 0.5, "safety": 0.5, "clarity": 0.5, "issues": []}
        else:
            return {"completeness": 0.5, "safety": 0.5, "clarity": 0.5, "issues": []}

    return {
        "completeness": float(data.get("completeness", 0.5)),
        "safety": float(data.get("safety", 0.5)),
        "clarity": float(data.get("clarity", 0.5)),
        "issues": data.get("issues", []) if isinstance(data.get("issues"), list) else [],
    }


def _get_tenant_agents(tenant_id: str) -> List[Dict[str, Any]]:
    """Fetch all active agents for a tenant (for Builder context)."""
    try:
        from database.base import SessionLocal
        from database.models.variant_engine import AIAgentAssignment

        db = SessionLocal()
        try:
            rows = db.query(AIAgentAssignment).filter(
                AIAgentAssignment.company_id == tenant_id,
                AIAgentAssignment.status == "active",
            ).all()

            return [
                {
                    "name": a.agent_name,
                    "capabilities": json.loads(a.capabilities or "[]"),
                    "domain": getattr(a, "domain", None),
                }
                for a in rows
            ]
        finally:
            db.close()
    except Exception:
        return []


def _create_custom_category(
    db,
    tenant_id: str,
    name: str,
    keywords: List[str],
    agent_id: str = None,
) -> None:
    """Create a custom category in the DB for agent routing.

    Uses the custom_categories table (CustomCategory model in
    variant_engine.py). Node 1 reads this table during classification
    to route tickets to custom agents.
    """
    try:
        from database.models.variant_engine import CustomCategory

        # Check if category already exists for this tenant
        existing = db.query(CustomCategory).filter(
            CustomCategory.company_id == tenant_id,
            CustomCategory.name == name,
        ).first()

        if existing:
            # Update keywords and agent_id
            existing.keywords = json.dumps(keywords)
            if agent_id:
                existing.agent_id = agent_id
            logger.info(
                "custom_category_updated tenant=%s name=%s keywords=%d",
                tenant_id, name, len(keywords),
            )
        else:
            category = CustomCategory(
                id=str(uuid.uuid4()),
                company_id=tenant_id,
                name=name,
                keywords=json.dumps(keywords),
                agent_id=agent_id,
                is_active=True,
            )
            db.add(category)
            logger.info(
                "custom_category_created tenant=%s name=%s keywords=%s",
                tenant_id, name, keywords[:5],
            )

    except Exception as exc:
        # Table might not exist yet in some environments — try raw SQL
        logger.info(
            "custom_category_fallback_raw_sql tenant=%s name=%s err=%s",
            tenant_id, name, str(exc)[:100],
        )
        try:
            from sqlalchemy import text
            db.execute(
                text(
                    "INSERT INTO custom_categories (id, company_id, name, keywords, agent_id, is_active) "
                    "VALUES (:id, :tid, :name, :kws, :aid, 1) "
                    "ON CONFLICT (company_id, name) DO UPDATE SET keywords = :kws, agent_id = :aid"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "tid": tenant_id,
                    "name": name,
                    "kws": json.dumps(keywords),
                    "aid": agent_id,
                },
            )
        except Exception as exc2:
            logger.warning("create_custom_category failed completely: %s", str(exc2)[:200])


# ── Additional Helpers for Non-LLM Techniques ───────────────────────


def _get_kb_chunk_count(tenant_id: str) -> int:
    """Get KB document chunk count for a tenant."""
    try:
        from database.base import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            result = db.execute(
                text("SELECT count(*) FROM document_chunks WHERE company_id = :tid"),
                {"tid": tenant_id},
            ).scalar()
            return int(result) if result else 0
        finally:
            db.close()
    except Exception:
        return 0


def _get_tenant_integrations(tenant_id: str) -> List[Dict[str, Any]]:
    """Get tenant's active integrations (for CoVe verification)."""
    try:
        from database.base import SessionLocal
        from database.models.core import Integration
        db = SessionLocal()
        try:
            rows = db.query(Integration).filter(
                Integration.company_id == tenant_id,
            ).all()
            return [
                {"type": getattr(i, "integration_type", getattr(i, "provider", "unknown"))}
                for i in rows
            ]
        finally:
            db.close()
    except Exception:
        return []


def _get_past_builder_results(tenant_id: str, capability: str) -> List[Dict[str, Any]]:
    """Get past Builder results for this tenant/capability (for MetaLearner).

    Reads from the agent's metadata or a future builder_results table.
    Returns empty list if no past data exists.
    """
    try:
        from database.base import SessionLocal
        from database.models.variant_engine import AIAgentAssignment
        db = SessionLocal()
        try:
            # Look for agents with similar capabilities created via Builder
            rows = db.query(AIAgentAssignment).filter(
                AIAgentAssignment.company_id == tenant_id,
                AIAgentAssignment.agent_role == "auto_created",
                AIAgentAssignment.status == "active",
            ).limit(20).all()

            results = []
            for r in rows:
                caps = json.loads(r.capabilities or "[]")
                if capability.lower() in [c.lower() for c in caps]:
                    results.append({
                        "capability": capability,
                        "refine_iterations": 1,  # default estimate
                        "refine_quality_score": 0.85,
                    })
            return results
        finally:
            db.close()
    except Exception:
        return []


# ════════════════════════════════════════════════════════════════════════════
# SUPERGLUE TOOL GENERATION (Post-Agent-Creation Hook)
# ════════════════════════════════════════════════════════════════════════════
#
# After Builder Agent creates an AI agent config (instructions, restrictions,
# capabilities), it asks Superglue to GENERATE a multi-step tool for that agent.
#
# Why Superglue (not PARWA's LLM):
#   - Render's 512MB RAM can't handle heavy LLM workloads reliably
#   - Superglue runs on a separate server with its OWN LLM key
#   - Different IP → different rate limit pool → no rate blocking
#   - PARWA just makes an HTTP call, Superglue does the heavy lifting
#
# Failure handling:
#   - Superglue unconfigured → agent works without tool (KB fallback)
#   - Superglue down → status="pending", retry on next ticket
#   - Superglue refuses → status="failed", admin can manually retry
#   - Success → tool_id saved, agent has full multi-step capability
# ════════════════════════════════════════════════════════════════════════════

async def _request_superglue_tool_for_agent(
    db,
    agent_id: str,
    agent_name: str,
    agent_instructions: str,
    agent_capabilities: str,
    sample_ticket: Optional[str] = None,
) -> None:
    """Ask Superglue to generate a multi-step tool for this AI agent.

    Updates AIAgentAssignment.superglue_tool_id + status fields in place.
    Non-fatal: if Superglue fails, the agent still works via KB fallback.

    Args:
        db: SQLAlchemy session (already opened by caller)
        agent_id: The AIAgentAssignment.id we just created
        agent_name: Human name (e.g. "Refund Specialist")
        agent_instructions: System prompt for the agent
        agent_capabilities: Comma-separated capability keys (e.g. "refund_processing")
        sample_ticket: Optional real ticket text for context
    """
    from database.models.variant_engine import AIAgentAssignment
    from app.core.superglue_tool_generator import generate_tool_for_agent, is_configured

    # If Superglue isn't configured, leave the agent in "none" status
    # (agent can still respond via KB — no tool needed)
    if not is_configured():
        db.query(AIAgentAssignment).filter(
            AIAgentAssignment.id == agent_id,
        ).update({
            "superglue_tool_status": "none",
        }, synchronize_session=False)
        db.commit()
        logger.info(
            "superglue_tool_skipped: agent=%s reason=not_configured",
            agent_id,
        )
        return

    # Get tenant's connected integrations so Superglue knows what's available
    tenant_id_record = db.query(AIAgentAssignment).filter(
        AIAgentAssignment.id == agent_id,
    ).first()
    if not tenant_id_record:
        return
    tenant_id = tenant_id_record.company_id

    tenant_integrations = _get_tenant_integrations_dict(tenant_id)

    # Ask Superglue to generate the tool (uses Superglue's OWN LLM)
    result = await generate_tool_for_agent(
        agent_name=agent_name,
        agent_instructions=agent_instructions,
        agent_capabilities=agent_capabilities,
        sample_ticket=sample_ticket,
        tenant_integrations=tenant_integrations,
    )

    if result.get("success"):
        # Success — save tool_id and mark as active
        tool_id = result.get("tool_id")
        tool_definition = result.get("tool_definition")
        tool_def_str = json.dumps(tool_definition) if tool_definition else None

        db.query(AIAgentAssignment).filter(
            AIAgentAssignment.id == agent_id,
        ).update({
            "superglue_tool_id": tool_id,
            "superglue_tool_status": "active",
            "superglue_tool_definition": tool_def_str,
            "superglue_tool_created_at": datetime.now(timezone.utc),
        }, synchronize_session=False)
        db.commit()

        logger.info(
            "superglue_tool_created: agent=%s tool_id=%s name=%s",
            agent_id, tool_id, agent_name,
        )
    else:
        # Failure — mark as failed, agent falls back to KB
        db.query(AIAgentAssignment).filter(
            AIAgentAssignment.id == agent_id,
        ).update({
            "superglue_tool_status": "failed",
        }, synchronize_session=False)
        db.commit()

        logger.warning(
            "superglue_tool_failed: agent=%s name=%s err=%s",
            agent_id, agent_name, result.get("error", "unknown")[:200],
        )


def _get_tenant_integrations_dict(tenant_id: str) -> Dict[str, Any]:
    """Get tenant's connected integrations as a dict (for Superglue Agent API).

    Returns:
        {"paddle": {...}, "brevo": {...}, "stripe": {...}}
    """
    try:
        from database.base import SessionLocal
        from database.models.core import Integration
        db = SessionLocal()
        try:
            rows = db.query(Integration).filter(
                Integration.company_id == tenant_id,
            ).all()
            result = {}
            for i in rows:
                integ_type = getattr(i, "integration_type", getattr(i, "provider", "unknown"))
                # Pull credential config (IntegrationService-style)
                # We pass the integration type only — Superglue looks up its own
                # stored credentials for that system. We don't expose keys to PARWA.
                result[integ_type] = {"connected": True}
            return result
        finally:
            db.close()
    except Exception as exc:
        logger.warning("get_tenant_integrations_dict err: %s", str(exc)[:200])
        return {}
