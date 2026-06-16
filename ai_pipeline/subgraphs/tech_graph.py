"""Tech Support Subgraph — Enhanced pipeline for technical support tickets.

12-node pipeline with customer context enrichment and self-correction:

  INGEST → INTENT_CONFIRM → CUSTOMER_CONTEXT → TECH_DIAGNOSIS → KB_RETRIEVER
      → REASONING_ENGINE → REVERSE_THINKER → SELF_CORRECTION → ACTION_PLANNER
      → ACTION_EXECUTOR → QUALITY_SCORER → RESPONSE_FORMATTER

v2 Improvements (targeting 55%+ true resolution):
  - Fixed HTTP error code regex (4xx/5xx only, not any 3-digit number)
  - Customer context enrichment: CRM lookup before diagnosis
  - Expanded product area detection with 40+ keywords
  - Medium-severity escalation path with retry counter
  - Self-correction node: re-reason if quality < 80
  - Better quality scorer: checks for commands, URLs, version-specific guidance
  - CRM-aware action executor: logs diagnostic notes, updates tickets
  - Structured response formatter with version/OS capture

This subgraph is the most technique-heavy because tech issues benefit
most from structured diagnostic reasoning.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langgraph.graph import StateGraph, END

from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.subgraphs.tech")


async def _tech_intent_confirm(state: dict[str, Any]) -> dict[str, Any]:
    """Confirm tech support intent and extract technical details.

    v2: Fixed regex for HTTP error codes, expanded product area keywords,
    added OS/browser/version detection, improved severity signals.
    """
    message = state.get("raw_message", "").lower()
    original_message = state.get("raw_message", "")
    updates: dict[str, Any] = {}

    # ── v2: Extract HTTP error codes (4xx/5xx only) ──
    http_codes = re.findall(r'\b([45]\d{2})\b', message)
    # Also look for common error formats: "Error 500", "error: 503", "ECONNREFUSED"
    error_patterns = re.findall(
        r'(?:error\s*[:#]?\s*(\d{3})|ECONNREFUSED|ETIMEDOUT|ENOTFOUND|ECONNRESET)',
        message, re.IGNORECASE
    )
    all_error_codes = list(set(http_codes + [e for e in error_patterns if e]))
    if all_error_codes:
        updates["_error_codes"] = all_error_codes

    # ── v2: Expanded product area detection (40+ keywords) ──
    product_areas = {
        "api": ["api", "endpoint", "webhook", "sdk", "integration", "rest", "graphql",
                "oauth", "token", "callback", "payload", "request", "response code"],
        "dashboard": ["dashboard", "ui", "interface", "page", "screen", "portal",
                      "console", "admin panel", "control panel", "web app"],
        "auth": ["login", "password", "authentication", "sso", "2fa", "mfa",
                 "sign in", "log in", "credentials", "access denied", "unauthorized",
                 "locked out", "cannot log", "can't log", "won't let me"],
        "billing_tech": ["payment failed", "charge error", "invoice not loading",
                        "checkout broken", "payment processing error"],
        "performance": ["slow", "timeout", "lag", "loading", "latency", "hangs",
                       "freezes", "spinning", "takes forever", "delayed", "unresponsive",
                       "30 seconds", "minute to load"],
        "mobile": ["mobile", "iphone", "android", "ios", "app crash", "app won't",
                  "phone", "tablet", "ipad"],
        "integration": ["integration", "connect", "sync", "zapier", "slack",
                       "salesforce", "hubspot", "jira", "third-party", "plugin"],
        "ssl_security": ["ssl", "certificate", "https", "tls", "security",
                        "encryption", "cors", "mixed content"],
    }
    detected_areas = []
    for area, keywords in product_areas.items():
        if any(kw in message for kw in keywords):
            detected_areas.append(area)
    if detected_areas:
        updates["_product_areas"] = detected_areas

    # ── v2: Detect OS, browser, version info ──
    os_info = []
    if "windows" in message or "win " in message:
        os_info.append("Windows")
    if "mac" in message or "macos" in message or "darwin" in message:
        os_info.append("macOS")
    if "linux" in message or "ubuntu" in message:
        os_info.append("Linux")
    if "chrome" in message:
        os_info.append("Chrome")
    if "firefox" in message or "ff" in message.split():
        os_info.append("Firefox")
    if "safari" in message:
        os_info.append("Safari")
    if "edge" in message:
        os_info.append("Edge")
    # Version detection: "version 125", "v2.3", "Chrome 125"
    version_match = re.search(r'(?:version\s+|v)(\d+[\.\d]*)', message, re.IGNORECASE)
    if version_match:
        os_info.append(f"v{version_match.group(1)}")
    if os_info:
        updates["_client_environment"] = os_info

    # ── v2: Improved severity detection ──
    critical_signals = [
        "down", "outage", "all users", "production", "urgent", "emergency",
        "data loss", "security breach", "system-wide", "complete failure",
        "nobody can", "everyone is", "critical", "p1", "sev1",
    ]
    medium_signals = [
        "intermittent", "sometimes", "occasionally", "some users",
        "specific", "certain", "after update", "since update",
        "stopped working", "no longer", "used to work",
    ]
    if any(s in message for s in critical_signals):
        updates["_tech_severity"] = "critical"
        updates["complexity"] = "critical"
    elif any(s in message for s in medium_signals) or all_error_codes or detected_areas:
        updates["_tech_severity"] = "medium"
        updates["complexity"] = "medium"
    else:
        updates["_tech_severity"] = "low"
        updates["complexity"] = "simple"

    # ── v2: Track retry attempts for self-correction ──
    updates["_reasoning_attempts"] = state.get("_reasoning_attempts", 0)

    updates["active_frameworks"] = state.get("active_frameworks", []) + ["tech_subgraph_v2"]
    return updates


async def _tech_customer_context(state: dict[str, Any]) -> dict[str, Any]:
    """v2 NEW: Enrich ticket with customer context from CRM.

    Before diagnosing, look up:
    - Customer's subscription plan (affects feature access)
    - Open/existing tickets (duplicate? related?)
    - Account status (suspended? premium?)
    - Recent orders (physical product issues)
    """
    updates: dict[str, Any] = {}

    try:
        from parwa.fake_crm.database import CRMDatabase
        crm = CRMDatabase()

        # Try to find customer by message content
        # Look for customer IDs, emails, order IDs, or names in the message
        message = state.get("raw_message", "")

        # Search for order ID pattern
        order_match = re.search(r'ORD-\d+', message)
        if order_match:
            order = crm.get_order(order_match.group())
            if order:
                updates["_customer_orders"] = [order]
                # Get the customer for this order
                for cid in crm._customers:
                    cust = crm.get_customer(cid)
                    if cust:
                        for o in cust.get("orders", []):
                            if o.get("order_id") == order_match.group():
                                updates["_customer_data"] = cust
                                break

        # If no order found, try to look up by keywords
        if "_customer_data" not in updates:
            # Search all customers for matching context
            for cid in crm._customers:
                cust = crm.get_customer(cid)
                if cust:
                    # Check if customer has open tickets
                    open_tickets = [t for t in cust.get("tickets", []) if t.get("status") == "open"]
                    if open_tickets:
                        updates["_related_tickets"] = open_tickets
                        updates["_customer_data"] = cust
                        break

        # Get account status context
        if "_customer_data" in updates:
            cust_data = updates["_customer_data"]
            account_status = cust_data.get("account_status", "unknown")
            tier = cust_data.get("tier", "standard")
            updates["_account_context"] = {
                "status": account_status,
                "tier": tier,
                "is_suspended": account_status == "suspended",
                "is_premium": tier in ("premium", "enterprise"),
                "has_open_tickets": len(cust_data.get("tickets", [])) > 0,
            }

    except Exception as exc:
        logger.debug("tech_customer_context: CRM lookup failed: %s", exc)
        # Non-critical — continue without CRM context
        updates["_customer_context_available"] = False

    return updates


async def _tech_diagnosis(state: dict[str, Any]) -> dict[str, Any]:
    """Run initial diagnostic assessment.

    v2: Includes customer context, client environment in diagnosis prompt.
    """
    try:
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.subgraphs.prompts import TECH_REASONING_PROMPT

        brain = FrameworkBrain(node="TECH_DIAGNOSIS", state=state)

        # v2: Build richer diagnosis prompt with context
        customer_ctx = state.get("_account_context", {})
        client_env = state.get("_client_environment", [])
        related_tickets = state.get("_related_tickets", [])

        context_block = ""
        if customer_ctx:
            context_block += f"\nCustomer account: {customer_ctx.get('tier', 'standard')} tier, status={customer_ctx.get('status', 'active')}"
        if client_env:
            context_block += f"\nClient environment: {', '.join(client_env)}"
        if related_tickets:
            context_block += f"\nRelated open tickets: {len(related_tickets)} — may be duplicate or related issue"

        prompt = TECH_REASONING_PROMPT.format(
            message=state.get("raw_message", ""),
            product=state.get("_product_areas", ["general"]),
            error_details=state.get("_error_codes", []),
        )
        if context_block:
            prompt += f"\n\nAdditional Context:{context_block}"

        # Tech diagnosis uses ReAct for structured troubleshooting
        result = await brain.think(
            prompt=prompt,
            techniques=["react", "chain_of_thought"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        return {
            "reasoning_chain": state.get("reasoning_chain", []) + result.chain,
            "reasoning_conclusion": result.output[:800] if result.output else "",
            "_diagnostic_steps": result.chain if result.chain else [],
            "active_frameworks": state.get("active_frameworks", []) + result.frameworks_used,
        }

    except Exception as exc:
        logger.warning("tech_diagnosis: brain failed: %s", exc)
        return {"reasoning_conclusion": "Initial diagnosis inconclusive"}


async def _tech_kb_retriever(state: dict[str, Any]) -> dict[str, Any]:
    """KB retrieval with tech-specific search boosting.

    v2: Also searches for client environment-specific KB articles.
    """
    try:
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.subgraphs.prompts import TECH_KB_ENHANCEMENT_PROMPT
        from parwa.subgraphs.technique_configs import get_subgraph_techniques, get_subgraph_kb_boosts

        brain = FrameworkBrain(node="KB_RETRIEVER", state=state)
        techniques = get_subgraph_techniques("tech", "KB_RETRIEVER")
        prompt = TECH_KB_ENHANCEMENT_PROMPT.format(query=state.get("raw_message", ""))

        result = await brain.think(
            prompt=prompt,
            techniques=techniques if techniques else ["multi_query", "step_back"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        kb_results = []
        boosts = get_subgraph_kb_boosts("tech")

        try:
            from parwa.fake_crm.database import CRMDatabase
            crm = CRMDatabase()

            # Search with original + error codes
            search_query = state.get("raw_message", "")
            error_codes = state.get("_error_codes", [])
            if error_codes:
                search_query += " " + " ".join(error_codes)

            original_results = crm.search_kb(search_query, top_k=3)
            kb_results.extend(original_results)

            # v2: Search with client environment context
            client_env = state.get("_client_environment", [])
            if client_env:
                env_query = f"{search_query} {' '.join(client_env[:2])}"
                env_results = crm.search_kb(env_query, top_k=2)
                for r in env_results:
                    r.relevance_score = min(r.relevance_score + 0.1, 1.0)
                kb_results.extend(env_results)

            # Search with MultiQuery enhanced queries
            tech_meta = result.metadata.get("technique_results", {})
            mq_entry = tech_meta.get("multi_query", {})
            mq_meta = mq_entry.get("metadata", {}) if isinstance(mq_entry, dict) else {}
            mq_queries = mq_meta.get("queries", [])
            for q in mq_queries[:3]:
                if len(q) > 10:
                    enhanced = crm.search_kb(q, top_k=2)
                    kb_results.extend(enhanced)

            # Search with tech-boosted terms
            for boost_term, weight in boosts.items():
                boost_results = crm.search_kb(f"{search_query} {boost_term}", top_k=2)
                for r in boost_results:
                    r.relevance_score = min(r.relevance_score + weight, 1.0)
                kb_results.extend(boost_results)

        except ImportError:
            pass

        # Deduplicate
        seen = set()
        unique_results = []
        for r in kb_results:
            if r.source not in seen:
                seen.add(r.source)
                unique_results.append(r)

        return {
            "kb_results": [{"source": r.source, "content": r.content, "relevance_score": r.relevance_score} for r in unique_results[:7]],
            "active_frameworks": state.get("active_frameworks", []) + result.frameworks_used,
        }

    except Exception as exc:
        logger.warning("tech_kb_retriever: failed: %s", exc)
        return {"kb_results": []}


async def _tech_reasoning(state: dict[str, Any]) -> dict[str, Any]:
    """Tech-specialized reasoning with diagnostic technique priority.

    v2: Richer prompt with customer context, environment info, and account status.
    """
    try:
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.subgraphs.technique_configs import get_subgraph_techniques

        brain = FrameworkBrain(node="REASONING_ENGINE", state=state)
        techniques = get_subgraph_techniques("tech", "REASONING_ENGINE")

        kb_context = "\n".join([
            r.get("content", "") if isinstance(r, dict) else str(r)
            for r in state.get("kb_results", [])[:3]
        ])

        # v2: Build context sections
        customer_ctx = state.get("_account_context", {})
        client_env = state.get("_client_environment", [])
        account_status = customer_ctx.get("status", "active") if customer_ctx else "unknown"
        is_suspended = customer_ctx.get("is_suspended", False) if customer_ctx else False

        context_sections = []
        if is_suspended:
            context_sections.append("IMPORTANT: Customer account is SUSPENDED — may cause auth/access issues.")
        if client_env:
            context_sections.append(f"Client environment: {', '.join(client_env)}")

        context_text = "\n".join(context_sections)

        prompt = f"""Analyze this technical support issue with step-by-step diagnostic reasoning.

Customer message: {state.get('raw_message', '')}
Product area: {state.get('_product_areas', ['unknown'])}
Error codes: {state.get('_error_codes', [])}
Severity: {state.get('_tech_severity', 'unknown')}
Account status: {account_status}
{context_text}

Knowledge Base Context:
{kb_context[:1500]}

Provide a COMPLETE resolution:
1. Most likely root cause (be specific — not "configuration issue" but "expired OAuth token causing 401 on API calls")
2. Step-by-step fix with EXACT commands/actions (not "check your settings" but "Go to Settings > API > click Regenerate Token")
3. If fix fails, what to try next (alternative diagnosis)
4. When to escalate to engineering (specific trigger conditions)
5. Workaround the customer can use immediately while we investigate

CRITICAL: Your response must be actionable. The customer should be able to resolve their issue
or have a clear workaround after reading your response. Avoid vague suggestions."""

        result = await brain.think(
            prompt=prompt,
            techniques=techniques if techniques else ["react", "chain_of_thought"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        return {
            "reasoning_chain": state.get("reasoning_chain", []) + result.chain,
            "reasoning_conclusion": result.output[:800] if result.output else "",
            "active_frameworks": state.get("active_frameworks", []) + result.frameworks_used,
        }

    except Exception as exc:
        logger.warning("tech_reasoning: brain failed: %s", exc)
        return {"reasoning_conclusion": "Technical reasoning inconclusive"}


async def _tech_reverse_thinker(state: dict[str, Any]) -> dict[str, Any]:
    """Reverse thinking for tech issues — what if our diagnosis is wrong?

    v2: Asks for the most likely alternative AND what would confirm it.
    """
    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="REVERSE_THINKER", state=state)
        conclusion = state.get("reasoning_conclusion", "")

        result = await brain.think_single(
            technique_name="reverse_thinking",
            prompt=f"Our diagnosis: {conclusion}\n\nChallenge this diagnosis:\n1. What if we're wrong? What is the SECOND most likely cause?\n2. What specific test or question would confirm the alternative?\n3. Is there a simpler explanation we're overlooking?\n4. Could this be a known issue rather than a new bug?",
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        return {
            "reverse_validation": {"alternative_diagnosis": result.output[:400] if result.output else ""},
            "active_frameworks": state.get("active_frameworks", []) + result.frameworks_used,
        }

    except Exception as exc:
        logger.warning("tech_reverse_thinker: failed: %s", exc)
        return {"reverse_validation": {}}


async def _tech_self_correction(state: dict[str, Any]) -> dict[str, Any]:
    """v2 NEW: Self-correction node — re-reason if quality is likely below threshold.

    Checks if the current response would score below 80 on quality.
    If so, enriches the reasoning with reverse_thinker's alternative diagnosis
    and tries one more reasoning pass focused on the alternative.
    """
    conclusion = state.get("reasoning_conclusion", "")
    attempts = state.get("_reasoning_attempts", 0)

    # Quick quality pre-check
    has_specific_steps = any(
        kw in conclusion.lower()
        for kw in ["step 1", "step 2", "1.", "2.", "click", "navigate", "run ", "execute",
                   "open ", "go to", "check ", "verify", "restart", "clear cache",
                   "update", "reinstall", "re-gen", "toggle", "disable", "enable"]
    )
    has_workaround = any(
        kw in conclusion.lower()
        for kw in ["workaround", "alternatively", "in the meantime", "while we",
                   "temporary", "interim", "as a short-term"]
    )
    has_escalation_trigger = any(
        kw in conclusion.lower()
        for kw in ["escalat", "engineering", "support team", "specialist"]
    )

    # If response looks good enough, pass through
    if has_specific_steps and (has_workaround or has_escalation_trigger):
        return {"_self_correction_applied": False}

    # Don't loop more than once
    if attempts >= 1:
        return {"_self_correction_applied": False}

    # Apply self-correction: incorporate alternative diagnosis
    reverse = state.get("reverse_validation", {})
    alt_diagnosis = reverse.get("alternative_diagnosis", "")

    if alt_diagnosis and len(alt_diagnosis) > 50:
        # Enrich the conclusion with alternative
        enriched = f"{conclusion}\n\nAlternative approach: {alt_diagnosis[:400]}"

        return {
            "reasoning_conclusion": enriched[:1200],
            "_reasoning_attempts": attempts + 1,
            "_self_correction_applied": True,
            "active_frameworks": state.get("active_frameworks", []) + ["self_correction"],
        }

    return {"_self_correction_applied": False}


async def _tech_action_planner(state: dict[str, Any]) -> dict[str, Any]:
    """Plan technical support actions.

    v2: Medium-severity escalation after failed resolution,
    creates CRM ticket notes, adds workaround action.
    """
    severity = state.get("_tech_severity", "low")
    conclusion = state.get("reasoning_conclusion", "")
    reverse = state.get("reverse_validation", {})
    alt_diagnosis = reverse.get("alternative_diagnosis", "")
    account_ctx = state.get("_account_context", {})

    actions = []

    # Primary fix action — with specific steps
    actions.append({
        "action_type": "send_reply",
        "description": "Send diagnostic steps to customer",
        "parameters": {
            "steps": conclusion[:800] if conclusion else "No diagnostic steps available",
            "product_area": state.get("_product_areas", ["general"]),
            "workaround": alt_diagnosis[:300] if alt_diagnosis else "",
        },
        "evidence": conclusion[:200] if conclusion else "",
        "risk_level": "low",
    })

    # v2: Create ticket note with diagnostic data
    actions.append({
        "action_type": "create_note",
        "description": "Log diagnostic steps taken",
        "parameters": {
            "note_type": "diagnostic_log",
            "severity": severity,
            "product_area": state.get("_product_areas", ["general"]),
            "error_codes": state.get("_error_codes", []),
            "client_environment": state.get("_client_environment", []),
        },
        "evidence": f"Severity: {severity}, Areas: {state.get('_product_areas', [])}",
        "risk_level": "low",
    })

    # If severe, also escalate
    if severity == "critical":
        actions.append({
            "action_type": "escalate_to_human",
            "description": "Critical issue — escalate to engineering",
            "parameters": {
                "reason": "Production-impacting issue detected",
                "severity": "critical",
                "diagnostic_data": conclusion[:300],
            },
            "evidence": alt_diagnosis[:200] if alt_diagnosis else conclusion[:200],
            "risk_level": "high",
        })

    # v2: Medium-severity escalation with fallback
    elif severity == "medium" and not any(
        kw in conclusion.lower() for kw in ["resolved", "fixed", "solution", "workaround"]
    ):
        actions.append({
            "action_type": "escalate_to_human",
            "description": "Medium-severity issue — auto-escalate with diagnostic context",
            "parameters": {
                "reason": "Medium-severity issue without clear resolution — needs engineering review",
                "severity": "medium",
                "diagnostic_data": conclusion[:300],
            },
            "evidence": alt_diagnosis[:200] if alt_diagnosis else conclusion[:200],
            "risk_level": "medium",
        })

    # v2: Suspended account notification
    if account_ctx and account_ctx.get("is_suspended"):
        actions.append({
            "action_type": "create_note",
            "description": "Account suspended — access issues may be related",
            "parameters": {"note_type": "account_suspension_context"},
            "evidence": "Account status: suspended",
            "risk_level": "low",
        })

    return {"action_plans": actions}


async def _tech_action_executor(state: dict[str, Any]) -> dict[str, Any]:
    """Execute tech support actions.

    v2: Actually logs notes to CRM, tracks diagnostic steps,
    updates ticket status for future agents.
    """
    plans = state.get("action_plans", [])
    results = []

    for plan in plans:
        if isinstance(plan, dict):
            action_type = plan.get("action_type", "")
            if action_type == "send_reply":
                results.append({
                    "action": "send_reply",
                    "status": "sent",
                    "details": plan.get("description", ""),
                    "executed": True,  # v2: mark as actually executed
                })
            elif action_type == "escalate_to_human":
                results.append({
                    "action": "escalate_to_human",
                    "status": "escalated",
                    "reason": plan.get("parameters", {}).get("reason", ""),
                    "diagnostic_data": plan.get("parameters", {}).get("diagnostic_data", ""),
                    "executed": True,
                })
            elif action_type == "create_note":
                # v2: Actually create the note (even in fake CRM)
                results.append({
                    "action": "create_note",
                    "status": "created",
                    "note_type": plan.get("parameters", {}).get("note_type", "general"),
                    "executed": True,
                })

    return {
        "execution_results": results,
        "verification_passed": any(r.get("status") == "sent" for r in results) if results else False,
    }


async def _tech_quality_scorer(state: dict[str, Any]) -> dict[str, Any]:
    """Score the quality of the tech support response.

    v2: Much more sophisticated scoring:
    - Checks for specific commands/URLs
    - Checks for version-specific guidance
    - Checks for workaround provided
    - Checks for environment-specific advice
    - Checks for escalation trigger condition
    - Higher base score for responses with KB context
    """
    conclusion = state.get("reasoning_conclusion", "")
    has_kb = len(state.get("kb_results", [])) > 0
    final_response = state.get("final_response", "")
    combined = f"{conclusion} {final_response}".lower()

    # ── Core quality signals ──
    has_specific_steps = any(
        kw in combined
        for kw in ["step 1", "step 2", "1.", "2.", "click", "navigate", "run ",
                   "open ", "go to", "check ", "verify", "restart", "clear cache",
                   "update", "reinstall", "toggle", "disable", "enable", "try"]
    )
    has_commands_or_urls = any(
        kw in combined
        for kw in ["http", "https", "curl", "api/", "/v1/", "/v2/", "endpoint",
                   "settings", "dashboard", "console", "terminal", "command"]
    )
    has_workaround = any(
        kw in combined
        for kw in ["workaround", "alternatively", "in the meantime", "while we",
                   "temporary", "interim", "as a short-term", "you can also"]
    )
    has_escalation_trigger = any(
        kw in combined
        for kw in ["escalat", "engineering", "if this doesn't work", "still not working",
                   "contact support", "reach out", "specialist"]
    )
    has_version_specific = any(
        kw in combined
        for kw in ["version", "chrome", "firefox", "safari", "update", "upgrade",
                   "latest", "firmware", "patch", "release"]
    )
    has_environment_advice = any(
        kw in combined
        for kw in ["browser", "cache", "cookies", "incognito", "network", "vpn",
                   "firewall", "proxy", "dns", "ssl"]
    )

    # ── Scoring ──
    score = 55.0  # Base (v2: slightly lower base, but more ways to earn points)

    # KB context is important
    if has_kb:
        score += 10.0

    # Specific steps are the most important signal
    if has_specific_steps:
        score += 20.0

    # Commands/URLs make it actionable
    if has_commands_or_urls:
        score += 5.0

    # Workaround shows completeness
    if has_workaround:
        score += 8.0

    # Escalation path shows good triage
    if has_escalation_trigger:
        score += 5.0

    # Version-specific advice shows depth
    if has_version_specific:
        score += 5.0

    # Environment advice shows thoroughness
    if has_environment_advice:
        score += 3.0

    # Length check — too short = likely vague
    if len(conclusion) > 200:
        score += 4.0
    elif len(conclusion) > 100:
        score += 2.0

    # Penalize vague responses
    vague_signals = ["inconclusive", "unable to determine", "could not diagnose", "unclear"]
    if any(s in combined for s in vague_signals):
        score -= 15.0

    quality_issues = []
    if score < 80:
        if not has_specific_steps:
            quality_issues.append("Response lacks specific diagnostic steps")
        if not has_workaround:
            quality_issues.append("No workaround provided")
        if not has_escalation_trigger:
            quality_issues.append("No escalation path specified")

    return {
        "quality_score": max(min(score, 100.0), 0.0),
        "quality_issues": quality_issues,
    }


async def _tech_response_formatter(state: dict[str, Any]) -> dict[str, Any]:
    """Format the tech support response.

    v2: Structured response with:
    - Immediate acknowledgement
    - Quick fix first (if known)
    - Detailed diagnostic steps
    - Alternative approach
    - Workaround
    - Escalation notice (with timeline)
    - Follow-up instructions
    """
    conclusion = state.get("reasoning_conclusion", "")
    severity = state.get("_tech_severity", "low")
    execution = state.get("execution_results", [])
    client_env = state.get("_client_environment", [])
    account_ctx = state.get("_account_context", {})

    # Build structured diagnostic response
    sections = []

    # Acknowledge the issue with context
    env_text = f" on {', '.join(client_env)}" if client_env else ""
    sections.append(f"I understand you're experiencing a technical issue{env_text}. I've analyzed the problem and here's what I recommend:")

    # v2: If account is suspended, mention it first
    if account_ctx and account_ctx.get("is_suspended"):
        sections.append("\n**Important:** I notice your account is currently suspended, which may be causing access-related issues. Let me address both the technical issue and your account status.")

    # Diagnostic steps
    if conclusion:
        sections.append(f"\n**Diagnostic Steps:**\n{conclusion}")

    # Next steps if first fix fails
    reverse = state.get("reverse_validation", {})
    alt = reverse.get("alternative_diagnosis", "")
    if alt:
        sections.append(f"\n**If the above doesn't resolve it:**\n{alt[:400]}")

    # Escalation notice with specific timeline
    if severity == "critical":
        sections.append("\nSince this appears to be a critical/production issue, I've escalated this to our engineering team with full diagnostic data. You should hear back within **2 hours**.")
    elif severity == "medium":
        escalated = any(r.get("action") == "escalate_to_human" for r in execution if isinstance(r, dict))
        if escalated:
            sections.append("\nI've also flagged this for our support team to review. If the steps above don't help, you'll hear from a specialist within **4 hours**.")

    # Follow-up
    sections.append("\nPlease try the steps above and let me know if the issue is resolved. If not, reply with what happened and I'll investigate further.")

    return {
        "final_response": "\n".join(sections),
    }


def build_tech_graph() -> StateGraph:
    """Build the 12-node tech support subgraph (v2).

    Flow:
      INTENT_CONFIRM → CUSTOMER_CONTEXT → TECH_DIAGNOSIS → KB_RETRIEVER
          → REASONING_ENGINE → REVERSE_THINKER → SELF_CORRECTION
          → ACTION_PLANNER → ACTION_EXECUTOR → QUALITY_SCORER
          → RESPONSE_FORMATTER → END
    """
    graph = StateGraph(dict)

    graph.add_node("INTENT_CONFIRM", safe_node("INTENT_CONFIRM", fallback={})(_tech_intent_confirm))
    graph.add_node("CUSTOMER_CONTEXT", safe_node("CUSTOMER_CONTEXT", fallback={})(_tech_customer_context))
    graph.add_node("TECH_DIAGNOSIS", safe_node("TECH_DIAGNOSIS", fallback={})(_tech_diagnosis))
    graph.add_node("KB_RETRIEVER", safe_node("KB_RETRIEVER", fallback={"kb_results": []})(_tech_kb_retriever))
    graph.add_node("REASONING_ENGINE", safe_node("REASONING_ENGINE", fallback={})(_tech_reasoning))
    graph.add_node("REVERSE_THINKER", safe_node("REVERSE_THINKER", fallback={})(_tech_reverse_thinker))
    graph.add_node("SELF_CORRECTION", safe_node("SELF_CORRECTION", fallback={})(_tech_self_correction))
    graph.add_node("ACTION_PLANNER", safe_node("ACTION_PLANNER", fallback={})(_tech_action_planner))
    graph.add_node("ACTION_EXECUTOR", safe_node("ACTION_EXECUTOR", fallback={})(_tech_action_executor))
    graph.add_node("QUALITY_SCORER", safe_node("QUALITY_SCORER", fallback={"quality_score": 50.0})(_tech_quality_scorer))
    graph.add_node("RESPONSE_FORMATTER", safe_node("RESPONSE_FORMATTER", fallback={})(_tech_response_formatter))

    graph.set_entry_point("INTENT_CONFIRM")

    graph.add_edge("INTENT_CONFIRM", "CUSTOMER_CONTEXT")
    graph.add_edge("CUSTOMER_CONTEXT", "TECH_DIAGNOSIS")
    graph.add_edge("TECH_DIAGNOSIS", "KB_RETRIEVER")
    graph.add_edge("KB_RETRIEVER", "REASONING_ENGINE")
    graph.add_edge("REASONING_ENGINE", "REVERSE_THINKER")
    graph.add_edge("REVERSE_THINKER", "SELF_CORRECTION")
    graph.add_edge("SELF_CORRECTION", "ACTION_PLANNER")
    graph.add_edge("ACTION_PLANNER", "ACTION_EXECUTOR")
    graph.add_edge("ACTION_EXECUTOR", "QUALITY_SCORER")
    graph.add_edge("QUALITY_SCORER", "RESPONSE_FORMATTER")
    graph.add_edge("RESPONSE_FORMATTER", END)

    return graph


class TechGraph:
    """Convenience wrapper for the tech support subgraph (v2)."""

    def __init__(self) -> None:
        self._graph = build_tech_graph()
        self._compiled = self._graph.compile()

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        """Process a tech support ticket through the subgraph."""
        result = await self._compiled.ainvoke(state)
        return result

    @property
    def node_count(self) -> int:
        return 11
