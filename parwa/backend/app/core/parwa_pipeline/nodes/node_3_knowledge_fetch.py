"""
Node 3: Knowledge Fetch + AI Wiki — PHASE 6 (Wiki Integration)

Phase 4 optimizations (preserved):
  - REMOVED HyDE, MultiQuery, StepBack (3 LLM calls saved)
  - Smarter knowledge filtering: score each doc by keyword relevance
  - CLARA re-evaluate simplified: non-LLM heuristic replaces 1 LLM call
  - Total: 5 LLM calls → 1 LLM call (CLARA gatekeep only)

Phase 6 upgrades (AI Wiki — all non-LLM, 0 extra calls):
  - _read_ai_wiki() now reads from real AI Wiki store
  - Section A: Similar ticket patterns from past resolutions
  - Section C: Company knowledge (admin-written policies)
  - Policy sync check: detects KB version changes, invalidates stale patterns
  - Wiki entries merged into knowledge_context for downstream nodes
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List

from app.core.parwa_pipeline.llm_client import llm_call
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_3")


# ── Rich Knowledge Base ──────────────────────────────────────────

KNOWLEDGE_BASE: Dict[str, List[Dict[str, str]]] = {
    "refund_request": [
        {
            "source": "refund_policy_v2",
            "content": "Refund Policy (Updated 2026): All customers are eligible for a full refund within 30 days of purchase, regardless of plan. After 30 days: Pro plan customers receive prorated refunds based on unused months. High plan customers receive prorated refunds minus a 5% early termination fee. Mini plan customers are not eligible for refunds after 14 days. Refunds are processed to the ORIGINAL payment method within 5-7 business days. For amounts exceeding $500, manager approval is required (typically 1-2 business days). Outstanding credits are applied BEFORE calculating the refund amount. Annual plan refunds: customer pays full year upfront, refund = annual price - (monthly rate × months used) - any applicable fees. Customer data is retained for 30 days after cancellation, then permanently deleted unless the customer requests data export within that window.",
            "section": "C",
        },
        {
            "source": "refund_process_v2",
            "content": "Refund Process Steps: 1) Verify customer identity (email + last 4 digits of payment method) 2) Check refund eligibility: plan type, purchase date, previous refunds 3) Calculate refund: start with annual price, subtract used portion at monthly rate, apply any outstanding credits, subtract early termination fee if applicable 4) For High plan: subtract 5% early termination fee 5) If amount > $500: route to finance team for manager approval 6) Process refund through Stripe/payment provider 7) Send confirmation email with refund ID and expected timeline 8) Update CRM with refund status. Average processing time: 3 business days for amounts under $500, 5-7 days for larger amounts.",
            "section": "C",
        },
        {
            "source": "credit_policy",
            "content": "Credit Policy: Billing error credits are applied to the next invoice. If the customer has an outstanding credit at the time of cancellation, the credit amount is ADDED to the refund. Credits do not expire and can be applied to any future purchase. To apply a credit: verify the credit was approved (check billing_audit_log), confirm the amount, apply to current transaction before processing refund. Credits from billing errors are typically equal to the overcharged amount.",
            "section": "C",
        },
        {
            "source": "data_retention_policy",
            "content": "Data Retention Policy: Upon account cancellation: all customer data is retained for 30 days in a read-only state. During this period, the customer can: 1) Reactivate their account (data restored fully), 2) Request a full data export (CSV/JSON format, provided within 24 hours), 3) Request immediate permanent deletion. After 30 days: data is permanently and irreversibly deleted from all systems including backups. Team member data follows the same policy. SSO configurations are preserved at the workspace level (not deleted with individual accounts).",
            "section": "C",
        },
    ],
    "billing": [
        {
            "source": "billing_policy_v2",
            "content": "Billing Policy (2026): Subscriptions billed monthly (1st of month) or annually (on anniversary). Upgrades: take effect immediately, customer charged prorated difference. Downgrades: take effect at end of current billing cycle, no prorated credit for partial month. Failed payments: 3 retry attempts over 7 days, then account suspended (not deleted). Invoices generated on 1st of each month, sent to billing email. Payment methods: credit card, ACH, wire transfer. Duplicate charges: if customer is charged twice in one cycle, the second charge is immediately refunded. If the duplicate was at a DIFFERENT plan rate, investigate whether an unauthorized plan change occurred. Pricing page discrepancies: all users on the same workspace should see the same pricing. If different users see different prices, check: 1) Are they on the same workspace? 2) Is there a custom enterprise agreement? 3) Cache issue — clear and recheck.",
            "section": "C",
        },
        {
            "source": "billing_dispute_process",
            "content": "Billing Dispute Resolution: 1) Acknowledge the dispute immediately 2) Pull the last 3 invoices for the account 3) Compare charged amounts with plan rates: Mini $999/mo, PARWA $2,499/mo, High $4,999/mo 4) If duplicate charge found: issue immediate refund for the duplicate 5) If wrong plan rate charged: refund the difference and correct the subscription 6) If pricing page shows wrong rate: this is a display bug, report to engineering, honor the lower price for the customer 7) Provide the customer with a detailed breakdown of all charges and corrections 8) Apply a 10% goodwill credit if the error was on our side. Resolution target: 24 hours for duplicate charges, 48 hours for pricing discrepancies.",
            "section": "C",
        },
        {
            "source": "plan_pricing",
            "content": "Current Plan Pricing (2026): Mini plan — $999/month or $9,999/year (17% savings). Includes: 1 agent, 500 tickets/month, email+chat channels. PARWA plan — $2,499/month or $24,999/year (17% savings). Includes: 3 agents, 2,000 tickets/month, all channels. High plan — $4,999/month or $49,999/year (17% savings). Includes: 10 agents, 10,000 tickets/month, all channels + priority support + custom integrations. All plans include: AI resolution, knowledge base, analytics dashboard. Add-ons: Extra agent seats ($99/seat/month), extra tickets ($0.50/ticket over limit), priority support ($499/month). Team member pricing: all team members on the same workspace share the same per-seat rate based on the workspace plan.",
            "section": "C",
        },
    ],
    "technical": [
        {
            "source": "tech_troubleshooting_v2",
            "content": "Technical Troubleshooting Guide: Login issues: 1) Check if password was recently changed (security log), 2) Check SSO sync status, 3) Clear browser cache/cookies, 4) Try incognito mode, 5) Check if account is locked (3 failed attempts = 15min lockout). SSO Issues: 1) Check last sync timestamp in admin panel, 2) Verify SSO provider status (Okta/Azure AD), 3) Check SSO certificate expiration, 4) Re-sync manually from admin panel. Unauthorized access: 1) Immediately lock the account, 2) Review audit log for all actions in the suspicious period, 3) Check for data exports during the period, 4) Remove any unauthorized users, 5) Force password reset, 6) Revoke all active sessions, 7) Notify the security team if financial data is involved. Data export check: go to Admin > Audit Log > filter by 'export' events in the relevant date range.",
            "section": "C",
        },
        {
            "source": "security_protocol",
            "content": "Security Incident Response Protocol: For suspected unauthorized access: Priority: CRITICAL. Step 1: Lock the affected account immediately (prevents further unauthorized actions). Step 2: Audit — pull the full session log for the past 7 days, note all login IPs, actions taken, data accessed. Step 3: Check for data exfiltration — look for export events, API key creation, webhook modifications. Step 4: Remove any unauthorized users added during the suspicious period. Step 5: Reset the account password and invalidate all sessions. Step 6: Fix SSO sync if broken — typical fix: re-authenticate with identity provider, check SCIM provisioning. Step 7: Notify the customer with a full incident report. Step 8: If financial data was accessed, escalate to the security team for GDPR/compliance review. Response time target: account lock within 5 minutes, full investigation within 2 hours.",
            "section": "C",
        },
    ],
    "faq": [
        {
            "source": "general_faq_v2",
            "content": "PARWA Platform FAQ: PARWA is an AI-powered customer support resolution platform. Plans: Mini ($999/mo), PARWA ($2,499/mo), High ($4,999/mo). All plans include 24/7 AI support. Platform supports: email, SMS, chat, phone, CRM integration (Salesforce, HubSpot), helpdesk integration (Zendesk, Intercom). Onboarding: 30-minute setup, 24-hour knowledge base import. Plan changes: upgrades immediate with prorated billing, downgrades at next cycle. Cancellation: 30-day refund window, data retained 30 days post-cancellation. Team members: can be added/removed from workspace settings. Each workspace has one billing owner.",
            "section": "C",
        },
        {
            "source": "plan_change_faq",
            "content": "Plan Change FAQ: Upgrading: Immediate effect, prorated charge for remainder of billing cycle. Downgrading: Takes effect at end of current billing cycle. No partial month credit on downgrade. Annual to monthly: At end of annual term, converts to monthly billing. Mid-year changes: If on annual plan and want to change mid-year, customer pays the difference (upgrade) or receives prorated credit (downgrade) calculated as: (annual price paid) - (monthly rate × months used) - early termination fee if applicable. Team splits: If some team members need different plans, create a second workspace under the same organization. Each workspace is billed independently. Prorated credits from the old plan can be applied to new workspace(s) as billing credits.",
            "section": "C",
        },
        {
            "source": "team_management_faq",
            "content": "Team Management FAQ: Adding team members: Admin goes to Settings > Team > Invite. Each seat costs based on the workspace plan. Removing team members: Their access is revoked immediately. They can be re-added later. If a team member has an open ticket when removed: the ticket remains assigned to the workspace and can be picked up by another member. No data is lost when a member is removed. Plan changes affecting teams: If workspace downgrades and has more seats than the new plan allows, excess members are moved to 'read-only' until seats are freed or plan is upgraded.",
            "section": "C",
        },
    ],
    "complaint": [
        {
            "source": "complaint_handling_v2",
            "content": "Complaint Handling Policy (2026): Priority tiers: Pro plan customers with 1+ year tenure get expedited resolution (target: 4 hours). High plan customers: immediate escalation to senior support. All complaints logged with timestamp, category, and sentiment score. Billing complaints: forwarded to finance team, customer notified within 1 hour. Service quality complaints: trigger interaction review, agent coaching if needed. Compensation guidelines: Mini plan: up to $50 credit or 1 free month. Pro plan: up to $200 credit or 1 free month. High plan: up to $500 credit, custom resolution with account manager. All complaints older than 48 hours without resolution are auto-escalated to management.",
            "section": "C",
        },
    ],
    "account_change": [
        {
            "source": "account_policy_v2",
            "content": "Account Change Policy (2026): Email changes: require verification of both old and new email addresses, 24-hour cooldown before taking effect. Password changes: invalidate all active sessions, require re-login on all devices. For security: if password was changed without user requesting it, treat as potential security incident (see security protocol). Plan upgrades: immediate with prorated billing for remainder of cycle. Plan downgrades: effective at next billing cycle, no mid-cycle credit. Account deletion: permanent after 30-day grace period, requires email confirmation, data export available before deletion. Team member additions: admin-only action, new member gets default permissions based on workspace plan. SSO configuration: managed at workspace level, not per-user. SSO sync runs every hour via SCIM. If sync fails, check: provider status, SCIM endpoint, certificate expiration.",
            "section": "C",
        },
        {
            "source": "workspace_management",
            "content": "Workspace Management: Each organization can have multiple workspaces. Each workspace has its own plan, team, and billing. To split a team across plans: 1) Create a new workspace under the same organization 2) Move team members to the appropriate workspace 3) Each workspace gets its own subscription. Prorated credit from the original workspace can be transferred as billing credit to the new workspace. Billing consolidation: available for organizations with 3+ workspaces. Contact sales@parwa.ai for consolidated billing setup. Open tickets: stay with the original workspace. They are not transferred when team members move.",
            "section": "C",
        },
    ],
}


# ── CLARA: Gatekeeper (LLM) — Phase 4: streamlined ──────────────


async def _clara_gatekeep(query: str, ticket_type: str) -> Dict[str, Any]:
    """CLARA identifies what knowledge is needed. Phase 4: concise prompt."""
    prompt = f"""What knowledge areas are needed to answer this {ticket_type} ticket?

Ticket: "{query}"

List 2-4 specific knowledge areas needed (one line each, no explanation):"""

    result = await llm_call(prompt, max_tokens=150)
    return {
        "relevant_knowledge": result,
        "knowledge_sufficient": False,
        "knowledge_contradictory": False,
    }


# ── Knowledge Retrieval (type-based, non-LLM) ────────────────────


def _retrieve_knowledge(ticket_type: str) -> List[Dict[str, Any]]:
    """Retrieve knowledge documents based on ticket type.
    Phase 4: Cleaner, no unused query parameters."""
    # Primary: exact type match
    docs = KNOWLEDGE_BASE.get(ticket_type, [])

    # Secondary: also pull from related types
    related_types = {
        "refund_request": ["billing"],
        "billing": ["refund_request", "faq"],
        "account_change": ["technical", "faq"],
        "technical": ["account_change", "faq"],
        "complaint": ["billing", "faq"],
        "faq": ["billing", "account_change"],
    }
    for rt in related_types.get(ticket_type, []):
        docs.extend(KNOWLEDGE_BASE.get(rt, []))

    # Deduplicate by source
    seen = set()
    unique_docs = []
    for d in docs:
        if d["source"] not in seen:
            seen.add(d["source"])
            unique_docs.append({
                "content": d["content"],
                "source": d["source"],
                "section": d.get("section", "C"),
            })

    return unique_docs


# ── Phase 4: Smart knowledge filtering (non-LLM) ─────────────────


def _filter_relevant_docs(
    documents: List[Dict[str, Any]], query: str, ticket_type: str
) -> List[Dict[str, Any]]:
    """Score each doc by keyword relevance to query, keep top results.
    This ensures only the most relevant KB chunks go to downstream nodes."""
    if not documents:
        return documents

    query_lower = query.lower()
    # Extract significant query terms
    query_terms = set(w.lower() for w in query_lower.split() if len(w) > 3)
    # Also add ticket-type-specific key terms
    type_keywords = {
        "refund_request": {"refund", "prorated", "termination", "fee", "credit", "eligible", "days", "annual", "monthly"},
        "billing": {"charge", "invoice", "payment", "billed", "subscription", "duplicate", "price", "plan", "rate"},
        "technical": {"login", "sso", "password", "access", "error", "cache", "sync", "session", "lockout", "certificate"},
        "faq": {"plan", "pricing", "feature", "channel", "agent", "ticket", "onboarding", "integration"},
        "complaint": {"complaint", "compensation", "credit", "escalate", "resolution", "priority", "tenure"},
        "account_change": {"email", "password", "plan", "upgrade", "downgrade", "workspace", "member", "sso"},
    }
    query_terms |= type_keywords.get(ticket_type, set())

    # Remove common filler
    filler = {"that", "this", "have", "been", "will", "would", "could", "should",
              "their", "there", "about", "which", "where", "when", "what", "with",
              "from", "your", "just", "also", "than", "them", "they", "some"}
    query_terms -= filler

    # Score each document
    scored_docs = []
    for doc in documents:
        text = doc.get("content", "").lower()
        doc_words = set(text.split())
        overlap = len(query_terms & doc_words)
        # Also check for query phrase presence (bigrams)
        query_bigrams = set()
        words = query_lower.split()
        for i in range(len(words) - 1):
            bg = f"{words[i]} {words[i+1]}"
            if len(bg) > 6:
                query_bigrams.add(bg)
        bigram_hits = sum(1 for bg in query_bigrams if bg in text)

        score = overlap + (bigram_hits * 2)  # bigrams worth more
        scored_docs.append((score, doc))

    # Sort by relevance, keep all (but order matters for downstream truncation)
    scored_docs.sort(key=lambda x: x[0], reverse=True)

    # If we have more than 8 docs, trim to top 8 (reduces downstream token waste)
    if len(scored_docs) > 8:
        scored_docs = scored_docs[:8]

    return [doc for _, doc in scored_docs]


# ── Phase 4: Non-LLM CLARA sufficiency check (replaces 1 LLM call) ─


def _check_knowledge_sufficiency(
    documents: List[Dict[str, Any]], query: str, ticket_type: str
) -> Dict[str, bool]:
    """Non-LLM heuristic: do we have KB docs for this ticket type?
    Replaces the LLM-based CLARA re-evaluate from Phase 2."""
    has_primary = any(d.get("source", "") in {
        "refund_policy_v2", "billing_policy_v2", "tech_troubleshooting_v2",
        "general_faq_v2", "complaint_handling_v2", "account_policy_v2",
    } for d in documents)

    # If we have docs for the primary type, knowledge is likely sufficient
    type_doc_counts = {
        "refund_request": 4, "billing": 3, "technical": 2,
        "faq": 3, "complaint": 1, "account_change": 2,
    }
    expected = type_doc_counts.get(ticket_type, 2)
    sufficient = len(documents) >= max(expected - 1, 1) and has_primary

    return {
        "knowledge_sufficient": sufficient,
        "knowledge_contradictory": False,  # our KB is internally consistent
    }


# ── Helpers ────────────────────────────────────────────────────────


def _check_contradictions(documents: List[Dict[str, Any]]) -> bool:
    """Quick keyword-level contradiction check."""
    if len(documents) < 2:
        return False
    all_numbers = {}
    for doc in documents:
        text = doc.get("content", "")
        for match in re.finditer(r"(\d+)%", text):
            num = int(match.group(1))
            context = text[max(0, match.start()-30):match.end()+30].lower()
            for keyword in ["refund", "fee", "credit", "discount"]:
                if keyword in context:
                    if keyword in all_numbers and all_numbers[keyword] != num:
                        return True
                    all_numbers[keyword] = num
    return False


def _read_ai_wiki(tenant_id: str, ticket_type: str, query: str, tier: str = "parwa") -> tuple:
    """Phase 6: Read AI Wiki Sections A, B, C from real store.
    
    Returns (section_a_entries, section_b_entries, section_c_entries)
    as lists of dicts in node format (same shape as KB docs).
    All non-LLM — keyword search only.
    """
    from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store
    
    wiki = get_wiki_store()
    wiki_a_raw = []
    wiki_b_raw = []
    wiki_c_raw = []
    
    try:
        # Section A: Search for similar ticket patterns (top 3)
        wiki_a_raw = wiki.search(
            tenant_id=tenant_id, section="A", query=query,
            ticket_type=ticket_type, tier=tier, max_results=3,
        )
        
        # Section B: Read admin behavior patterns (all, max 2)
        wiki_b_raw = wiki.read(tenant_id=tenant_id, section="B", tier=tier)
        wiki_b_raw = wiki_b_raw[:2]  # limit for context window
        
        # Section C: Read company knowledge (all, max 3)
        wiki_c_raw = wiki.read(tenant_id=tenant_id, section="C", tier=tier)
        wiki_c_raw = wiki_c_raw[:3]
    except Exception as e:
        logger.warning("Wiki read error (non-fatal): %s", e)
    
    # Convert to node format (same shape as KB docs)
    wiki_a = [e.to_node_format() for e in wiki_a_raw]
    wiki_b = [e.to_node_format() for e in wiki_b_raw]
    wiki_c = [e.to_node_format() for e in wiki_c_raw]
    
    # Build wiki summary for similar patterns found
    wiki_patterns = []
    for entry in wiki_a_raw:
        c = entry.content
        wiki_patterns.append({
            "entry_key": entry.entry_key,
            "techniques_that_worked": c.get("techniques_that_worked", []),
            "quality_achieved": c.get("quality_achieved", 0),
            "answer_summary": c.get("answer_summary", "")[:200],
            "historical_success_rate": round(entry.success_count / max(entry.usage_count, 1), 3),
        })
    
    return wiki_a, wiki_b, wiki_c, wiki_patterns


def _fetch_crm_data(tenant_id: str, customer_context: Dict) -> Dict:
    """Fetch CRM data via UCB. Mock for Phase 7."""
    return {
        "subscription_status": customer_context.get("account_tier", "free"),
        "recent_interactions": customer_context.get("recent_ticket_count", 0),
        "billing_email": customer_context.get("billing_email", "on file"),
    }


# ── Main Node Function ────────────────────────────────────────────


async def node_3_knowledge_fetch(state: PipelineV2State) -> dict:
    """Node 3: Knowledge Fetch — Phase 4 optimized.
    LLM calls: 1 (was 5) — removed HyDE, MultiQuery, StepBack, CLARA re-evaluate."""
    start = time.time()
    query = state.get("query", "")
    tenant_id = state.get("tenant_id", "")
    ticket_type = state.get("ticket_type", "general")
    logs = []
    llm_calls = 0

    # 1. CLARA: Gatekeeper (LLM) — the ONLY LLM call in Node 3 now
    clara_result = await _clara_gatekeep(query, ticket_type)
    logs.append({"node": 3, "technique": "CLARA", "duration_ms": 0, "result_summary": "gatekeep_done"})
    llm_calls += 1

    # 2. RAG Retrieval (non-LLM, type-based)
    documents = _retrieve_knowledge(ticket_type)
    logs.append({"node": 3, "technique": "RAG", "duration_ms": 0, "result_summary": f"{len(documents)} docs"})

    # 3. Smart knowledge filtering (Phase 4: non-LLM relevance ranking)
    filtered = _filter_relevant_docs(documents, query, ticket_type)
    logs.append({"node": 3, "technique": "SmartFilter", "duration_ms": 0, "result_summary": f"{len(documents)}→{len(filtered)}"})

    # 4. Knowledge sufficiency check (Phase 4: non-LLM, replaces CLARA re-evaluate LLM call)
    sufficiency = _check_knowledge_sufficiency(filtered, query, ticket_type)
    clara_result["knowledge_sufficient"] = sufficiency["knowledge_sufficient"]
    clara_result["knowledge_contradictory"] = sufficiency["knowledge_contradictory"]
    logs.append({"node": 3, "technique": "SufficiencyCheck", "duration_ms": 0,
                 "result_summary": f"sufficient={sufficiency['knowledge_sufficient']}"})

    # 5. Contradiction check (non-LLM)
    has_contradiction = _check_contradictions(filtered)
    if has_contradiction:
        clara_result["knowledge_contradictory"] = True
        logs.append({"node": 3, "technique": "ContradictionCheck", "duration_ms": 0, "result_summary": "CONTRADICTION_FOUND"})

    # 6. DynamicContext (non-LLM)
    dynamic_ctx = state.get("customer_context", {})
    logs.append({"node": 3, "technique": "DynamicContext", "duration_ms": 0, "result_summary": "context_pulled"})

    # 7. AI Wiki (Phase 6: real store reads)
    tier = state.get("variant_tier", "parwa")
    wiki_a, wiki_b, wiki_c, wiki_patterns = _read_ai_wiki(tenant_id, ticket_type, query, tier)
    wiki_log_msg = f"A={len(wiki_a)} B={len(wiki_b)} C={len(wiki_c)}"
    if wiki_patterns:
        wiki_log_msg += f" patterns_found={len(wiki_patterns)}"
    logs.append({"node": 3, "technique": "AIWiki", "duration_ms": 0,
                 "result_summary": wiki_log_msg})
    
    # 7b. Policy sync check (Phase 6: detect version changes)
    sync_status = {"synced": True, "version": "v2.0", "previous_version": None}
    try:
        from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store
        wiki_store = get_wiki_store()
        current_policy_version = state.get("policy_version", "v2.0")
        sync_status = wiki_store.check_policy_sync(tenant_id, current_policy_version)
        if not sync_status["synced"]:
            logs.append({
                "node": 3, "technique": "PolicySyncCheck",
                "duration_ms": 0,
                "result_summary": f"POLICY_CHANGED {sync_status['previous_version']} → {sync_status['version']} ({sync_status.get('patterns_invalidated', 0)} invalidated)",
            })
    except Exception as e:
        logger.warning("Policy sync check failed (non-fatal): %s", e)

    # 8. CRM via UCB (mock)
    crm_data = _fetch_crm_data(tenant_id, dynamic_ctx)
    logs.append({"node": 3, "technique": "UCB", "duration_ms": 0, "result_summary": "crm_fetched"})

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 3 complete: ticket=%s docs=%d sufficient=%s llm=%d [%dms]",
        state["ticket_id"], len(filtered), clara_result["knowledge_sufficient"], llm_calls, elapsed,
    )

    return {
        "knowledge_context": filtered,
        "wiki_section_a": wiki_a,
        "wiki_section_b": wiki_b,
        "wiki_section_c": wiki_c,
        "wiki_patterns": wiki_patterns,  # Phase 6: similar patterns for downstream nodes
        "crm_data": crm_data,
        "knowledge_sufficient": clara_result["knowledge_sufficient"],
        "knowledge_contradictory": clara_result["knowledge_contradictory"],
        "policy_version": "v2.0",
        "policy_sync_status": sync_status,  # Phase 6: sync status
        "technique_log": logs,
        "node_3_token_usage": llm_calls,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
    }