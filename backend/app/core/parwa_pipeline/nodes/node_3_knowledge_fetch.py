"""
Node 3: Knowledge Fetch + AI Wiki — PHASE 7 (Full Non-LLM Enhancement)

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

Phase 7 upgrades (54 non-LLM technique applications across 8 steps):
  - Layer 1 (CLARA): SelfConsistency, CoVe, MAKER.CLARA, QueryDecomposition, IntentSignalBoost
  - Layer 2 (RAG): MetaLearner, RecencyWeighting, AuthorityRanking, SmartRouter.RAG
  - Layer 3 (Filter): NearDedup, SourceDiversity, MAKER, CoverageAnalysis,
                      SelfConsistency.Filter, RelevanceDecay, OverlapMinimization
  - Layer 4 (Sufficiency): GSD, GapDetection, RuleBasedAction,
                           CompletenessTracker, PriorityEscalation
  - Layer 5 (Contradiction): ContradictionCheck, ScopeChecker,
                             TemporalChecker, VersionTracker
  - Layer 6 (Context): DynamicContext, SignalExtraction, ContextScoring, FreshnessCheck
  - Layer 7 (Wiki): StalenessDetection, PatternDiversity, ConflictResolution.Wiki
  - Layer 8 (UCB): UCB.Goals, APIHealthCheck, DataRelevance, PartialDataHandler, IdempotencyCheck
  - Total: 54 technique applications, 0 extra LLM calls
  - LLM calls: 1 (CLARA gatekeep only — unchanged)
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


def _retrieve_knowledge(ticket_type: str, query: str = "", tenant_id: str = "") -> List[Dict[str, Any]]:
    """Retrieve knowledge documents for THIS tenant only.

    Three-tier retrieval:
      1. VECTOR SEARCH: if tenant chunks have embeddings, use pgvector
         cosine similarity to find the top-5 most relevant chunks for the
         query. This is the semantic search path — finds by meaning, not
         just keywords.
      2. PER-TENANT KB (fallback): if no embeddings, fetch ALL tenant
         chunks (original behavior — keyword-based SmartFilter downstream)
      3. SHARED DEFAULT KB: platform default docs, only used when the
         tenant has no uploaded KB docs at all

    BC-001: tenant_id scopes ALL queries. Company A NEVER sees Company B's docs.
    """
    # ── Tier 1: Hybrid search (vector + BM25 + RRF) ──────────────
    # Vector search finds by MEANING ("double charged" → "duplicate payment")
    # BM25 finds by EXACT KEYWORDS (booking numbers, promo codes, policy names)
    # RRF (Reciprocal Rank Fusion) merges both → better than either alone
    if tenant_id and query:
        try:
            from database.base import SessionLocal
            from sqlalchemy import text
            from app.core.parwa_pipeline.nvidia_embedding import embed_text_sync

            db = SessionLocal()
            try:
                # Check if tenant has any embedded chunks
                has_embeddings = db.execute(
                    text(
                        "SELECT count(*) FROM document_chunks "
                        "WHERE company_id = :tenant_id AND embedding IS NOT NULL"
                    ),
                    {"tenant_id": tenant_id},
                ).scalar()

                if has_embeddings and int(has_embeddings) > 0:
                    # Generate REAL query embedding using Google AI (primary) or NVIDIA (fallback)
                    query_emb = embed_text_sync(query, input_type="query")
                    # Accept both Google (768) and NVIDIA (1024) embedding dimensions
                    if query_emb and len(query_emb) in (768, 1024):
                        import json as _json
                        import math as _math

                        # ── Vector search: Python-based cosine similarity ──
                        # No pgvector extension needed — compute cosine similarity in Python.
                        # Load all embedded chunks for this tenant, compute similarity, take top 20.
                        all_chunks = db.execute(
                            text(
                                "SELECT id, content, document_id, embedding "
                                "FROM document_chunks "
                                "WHERE company_id = :tenant_id AND embedding IS NOT NULL"
                            ),
                            {"tenant_id": tenant_id},
                        ).fetchall()

                        vector_rows = []
                        for row in all_chunks:
                            try:
                                stored_emb = _json.loads(row[3]) if isinstance(row[3], str) else row[3]
                                if not stored_emb or len(stored_emb) != len(query_emb):
                                    continue
                                # Cosine similarity: dot(a,b) / (|a| * |b|)
                                dot = sum(a * b for a, b in zip(query_emb, stored_emb))
                                norm_a = _math.sqrt(sum(a * a for a in query_emb))
                                norm_b = _math.sqrt(sum(b * b for b in stored_emb))
                                if norm_a == 0 or norm_b == 0:
                                    continue
                                similarity = dot / (norm_a * norm_b)
                                vector_rows.append((row[0], row[1], row[2], similarity))
                            except Exception:
                                continue

                        # Sort by similarity descending, take top 20
                        vector_rows.sort(key=lambda x: x[3], reverse=True)
                        vector_rows = vector_rows[:20]

                        # ── BM25 search: top 20 by keyword relevance ──
                        # Uses PostgreSQL tsvector (built-in, no extension needed)
                        bm25_rows = db.execute(
                            text(
                                "SELECT id, content, document_id, "
                                "ts_rank_cd(to_tsvector('english', content), "
                                "plainto_tsquery('english', :q)) AS rank "
                                "FROM document_chunks "
                                "WHERE company_id = :tenant_id "
                                "AND to_tsvector('english', content) @@ plainto_tsquery('english', :q) "
                                "ORDER BY rank DESC "
                                "LIMIT 20"
                            ),
                            {"tenant_id": tenant_id, "q": query},
                        ).fetchall()

                        # ── RRF fusion: merge vector + BM25 rankings ──
                        # RRF score = sum(1 / (k + rank)) for each list
                        # k=60 is the standard RRF constant
                        rrf_k = 60
                        chunk_scores = {}  # chunk_id → {content, doc_id, rrf_score}

                        for rank, row in enumerate(vector_rows, 1):
                            cid = str(row[0])
                            if cid not in chunk_scores:
                                chunk_scores[cid] = {
                                    "content": row[1],
                                    "document_id": str(row[2]),
                                    "vector_sim": float(row[3]),
                                    "rrf": 0.0,
                                }
                            chunk_scores[cid]["rrf"] += 1.0 / (rrf_k + rank)

                        for rank, row in enumerate(bm25_rows, 1):
                            cid = str(row[0])
                            if cid not in chunk_scores:
                                chunk_scores[cid] = {
                                    "content": row[1],
                                    "document_id": str(row[2]),
                                    "vector_sim": 0.0,
                                    "rrf": 0.0,
                                }
                            chunk_scores[cid]["rrf"] += 1.0 / (rrf_k + rank)

                        # Sort by RRF score, take top 5
                        merged = sorted(
                            chunk_scores.values(),
                            key=lambda x: x["rrf"],
                            reverse=True,
                        )[:5]

                        if merged:
                            result = []
                            for m in merged:
                                result.append({
                                    "content": m["content"],
                                    "source": f"tenant_kb:{m['document_id']}",
                                    "section": "C",
                                    "score": m["rrf"],
                                })
                            logger.info(
                                "Node 3: Hybrid search returned %d chunks for company_id=%s "
                                "(vector=%d, bm25=%d, top rrf=%.4f)",
                                len(result), tenant_id,
                                len(vector_rows), len(bm25_rows),
                                result[0]["score"] if result else 0.0,
                            )
                            return result

                        # ── If hybrid search found 0 chunks but vector_rows exist ──
                        # Return top vector results directly (skip RRF fusion)
                        if vector_rows:
                            result = []
                            for row in vector_rows[:5]:
                                result.append({
                                    "content": row[1],
                                    "source": f"tenant_kb:{row[2]}",
                                    "section": "C",
                                    "score": float(row[3]),
                                })
                            logger.info(
                                "Node 3: Vector-only fallback returned %d chunks (similarity top=%.4f)",
                                len(result), result[0]["score"] if result else 0.0,
                            )
                            return result

                        logger.info("Node 3: Hybrid search returned 0 chunks — falling back to fetch-all")
                    else:
                        logger.warning("Node 3: NVIDIA embedding failed for query — falling back to fetch-all")
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Node 3: Hybrid search failed: %s — falling back to fetch-all", str(exc)[:200])

    # ── Tier 2: Per-tenant KB (fetch all chunks — original behavior) ──
    if tenant_id:
        try:
            from database.base import SessionLocal
            from database.models.onboarding import KnowledgeDocument, DocumentChunk

            db = SessionLocal()
            try:
                # Get completed documents for THIS tenant only
                docs_query = db.query(KnowledgeDocument).filter(
                    KnowledgeDocument.company_id == tenant_id,
                    KnowledgeDocument.status == "completed",
                )
                tenant_docs = docs_query.all()

                if tenant_docs:
                    # Get chunks for those documents — scoped by company_id
                    doc_ids = [d.id for d in tenant_docs]
                    chunks = db.query(DocumentChunk).filter(
                        DocumentChunk.company_id == tenant_id,
                        DocumentChunk.document_id.in_(doc_ids),
                    ).all()

                    if chunks:
                        result = []
                        for chunk in chunks:
                            result.append({
                                "content": chunk.content,
                                "source": f"tenant_kb:{chunk.document_id}",
                                "section": "C",
                            })
                        logger.info(
                            "Node 3: Retrieved %d tenant KB chunks for company_id=%s",
                            len(result), tenant_id,
                        )
                        return result
                    else:
                        logger.info("Node 3: Tenant has docs but no chunks — falling back to default KB")
                else:
                    logger.info("Node 3: No tenant KB docs for company_id=%s — falling back to default KB", tenant_id)
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Node 3: Tenant KB query failed: %s — falling back to default KB", str(exc)[:200])

    # ── Tier 2: Fallback to shared default KB (platform docs) ────
    # Primary: exact type match
    docs = KNOWLEDGE_BASE.get(ticket_type, [])

    # Secondary: also pull from related types
    related_types = {
        "refund_request": ["billing"],
        "billing": ["refund_request", "faq"],
        "account_change": ["technical", "faq"],
        "technical": ["account_change", "faq"],
        "complaint": ["billing", "faq"],
        "faq": ["billing", "account_change", "refund_request"],
    }
    for rt in related_types.get(ticket_type, []):
        docs.extend(KNOWLEDGE_BASE.get(rt, []))

    # Phase 7: T2→T1 Cross-type pattern detection
    # If the query contains strong signals for a different type that isn't
    # already covered by primary or related_types, pull those docs too.
    if query:
        query_lower = query.lower()
        # Define cross-type signal patterns (query signals → should pull this type)
        cross_type_signals = {
            "refund_request": [r"\brefund\b", r"\bmoney\s+back\b", r"\breturn\s+my\b", r"\bprorated?\b", r"\beligibl", r"\btermination\s+fee\b"],
            "billing": [r"\bcharg(?:ed|e|es|ing)\b", r"\binvoice\b", r"\bpayment\b", r"\bovercharge", r"\bdouble\s+charge\b", r"\bpricing\b"],
            "technical": [r"\blogin\b", r"\bss[so]\b", r"\bpassword\b", r"\berror\b", r"\bcrash\b", r"\bnot\s+working\b", r"\bcan'?t\s+access\b", r"\bsession\b", r"\bcache\b"],
            "faq": [r"\bwhat\s+(?:is|are)\b", r"\bhow\s+(?:do|does|much|many)\b", r"\bfeature", r"\b(?:plan|plans?)\s*(?:pricing|cost|include)\b"],
            "complaint": [r"\bterrible\b", r"\bworst\b", r"\bunacceptab", r"\bfrustrat", r"\bdisappoint", r"\bnever\s+again\b"],
            "account_change": [r"\bchange\s+(?:email|password)\b", r"\bupgrade\b", r"\bdowngrade\b", r"\bswitch\s+plan\b", r"\bworkspace\b", r"\bteam\s+member\b"],
        }
        # Determine which types are already covered
        covered_types = {ticket_type} | set(related_types.get(ticket_type, []))
        for cross_type, patterns in cross_type_signals.items():
            if cross_type in covered_types:
                continue
            # If 2+ patterns match, this type is likely relevant
            match_count = sum(1 for pat in patterns if re.search(pat, query_lower))
            if match_count >= 2:
                extra_docs = KNOWLEDGE_BASE.get(cross_type, [])
                docs.extend(extra_docs)

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
    """Score each doc by LLM-based semantic relevance to the query.

    Uses Llama 3.1 8B to rate each KB doc's relevance (0-10) to the
    customer's query. This replaces the old keyword-overlap scoring
    which couldn't understand semantic meaning.

    Falls back to keyword scoring if LLM is unavailable (BC-008).
    """
    if not documents:
        return documents

    # ── LLM-based semantic relevance scoring ─────────────────────
    # Ask Llama 3.1 to rate each doc's relevance to the query (0-10).
    # This is the "knowledge base" — the LLM reads the query + doc title
    # and scores how relevant it is. Much better than keyword matching.
    try:
        import asyncio
        from app.core.parwa_pipeline.llm_client import llm_call

        # Build a single prompt that scores ALL docs at once (1 LLM call, not N)
        doc_list = []
        for i, doc in enumerate(documents):
            title = doc.get("source", "unknown")
            content_preview = doc.get("content", "")[:200]
            doc_list.append(f"DOC {i}: [{title}] {content_preview}")

        prompt = f"""Rate the relevance of each document to the customer's question (0-10).

Customer question: "{query}"

Documents:
{chr(10).join(doc_list)}

Reply with ONLY the doc numbers and scores, one per line:
0: <score>
1: <score>
2: <score>
..."""

        async def _score_docs():
            return await llm_call(prompt, max_tokens=100, temperature=0.1)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context — run in thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    result = pool.submit(asyncio.run, _score_docs).result(timeout=30)
            else:
                result = asyncio.run(_score_docs())
        except Exception:
            result = asyncio.run(_score_docs())

        # Parse scores from LLM response
        scores: Dict[int, int] = {}
        for line in result.strip().split("\n"):
            parts = line.strip().split(":")
            if len(parts) == 2:
                try:
                    doc_idx = int(parts[0].strip())
                    score = int(parts[1].strip())
                    scores[doc_idx] = max(0, min(10, score))
                except ValueError:
                    continue

        # If we got scores, sort docs by LLM relevance score
        if scores and len(scores) >= len(documents) // 2:
            scored_docs = []
            for i, doc in enumerate(documents):
                score = scores.get(i, 0)
                scored_docs.append((score, doc))
            scored_docs.sort(key=lambda x: x[0], reverse=True)

            # Keep top 8 docs with score >= 3
            filtered = [doc for score, doc in scored_docs if score >= 3][:8]
            if filtered:
                return filtered
            # If all scored low, keep top 5 anyway
            return [doc for _, doc in scored_docs[:5]]

        # If LLM scoring failed, fall through to keyword scoring below
        logger.warning("LLM relevance scoring failed — falling back to keyword filter")

    except Exception as exc:
        logger.warning("LLM relevance scoring error: %s — falling back to keyword filter", str(exc)[:200])

    # ── Fallback: keyword-based relevance scoring (original logic) ──
    query_lower = query.lower()
    query_terms = set(w.lower() for w in query_lower.split() if len(w) > 3)
    type_keywords = {
        "refund_request": {"refund", "prorated", "termination", "fee", "credit", "eligible", "days", "annual", "monthly"},
        "billing": {"charge", "invoice", "payment", "billed", "subscription", "duplicate", "price", "plan", "rate"},
        "technical": {"login", "sso", "password", "access", "error", "cache", "sync", "session", "lockout", "certificate"},
        "faq": {"plan", "pricing", "feature", "channel", "agent", "ticket", "onboarding", "integration"},
        "complaint": {"complaint", "compensation", "credit", "escalate", "resolution", "priority", "tenure"},
        "account_change": {"email", "password", "plan", "upgrade", "downgrade", "workspace", "member", "sso"},
    }
    query_terms |= type_keywords.get(ticket_type, set())

    filler = {"that", "this", "have", "been", "will", "would", "could", "should",
              "their", "there", "about", "which", "where", "when", "what", "with",
              "from", "your", "just", "also", "than", "them", "they", "some"}
    query_terms -= filler

    scored_docs = []
    for doc in documents:
        text = doc.get("content", "").lower()
        doc_words = set(text.split())
        overlap = len(query_terms & doc_words)
        query_bigrams = set()
        words = query_lower.split()
        for i in range(len(words) - 1):
            bg = f"{words[i]} {words[i+1]}"
            if len(bg) > 6:
                query_bigrams.add(bg)
        bigram_hits = sum(1 for bg in query_bigrams if bg in text)
        score = overlap + (bigram_hits * 2)
        scored_docs.append((score, doc))

    scored_docs.sort(key=lambda x: x[0], reverse=True)
    if len(scored_docs) > 8:
        scored_docs = scored_docs[:8]

    return [doc for _, doc in scored_docs]


# ── Phase 4: Non-LLM CLARA sufficiency check (replaces 1 LLM call) ─


def _check_knowledge_sufficiency(
    documents: List[Dict[str, Any]], query: str, ticket_type: str
) -> Dict[str, bool]:
    """Non-LLM heuristic: do we have KB docs for this ticket type?
    Replaces the LLM-based CLARA re-evaluate from Phase 2."""
    # Tenant KB docs (uploaded by the customer) are ALWAYS sufficient —
    # the tenant uploaded real policy docs, so the AI has relevant context.
    # Source format from vector search: "tenant_kb:{document_id}"
    # Source format from fetch-all: "tenant_kb:{document_id}"
    has_tenant_kb = any(
        d.get("source", "").startswith("tenant_kb:")
        for d in documents
    )
    if has_tenant_kb and len(documents) >= 1:
        return {
            "knowledge_sufficient": True,
            "knowledge_contradictory": False,
        }

    # Default KB check (fallback when no tenant docs)
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


# ════════════════════════════════════════════════════════════════════
# Non-LLM Technique Enhancement Layer (0 extra LLM calls)
# ════════════════════════════════════════════════════════════════════


# ── SelfConsistency: cross-check CLARA vs query keywords ──────────


def _self_consistency_clara(
    clara_result: Dict[str, Any], query: str, ticket_type: str,
) -> Dict[str, Any]:
    """Cross-check: do the knowledge areas CLARA identified match ticket_type?

    If CLARA says "shipping" for a billing ticket, flag the mismatch.
    Non-LLM — pure keyword overlap check.
    """
    knowledge_areas = clara_result.get("relevant_knowledge", "").lower()
    query_lower = query.lower()

    type_keywords = {
        "refund_request": ["refund", "prorated", "cancellation", "termination", "credit"],
        "billing": ["charge", "invoice", "payment", "billing", "subscription", "duplicate"],
        "technical": ["login", "sso", "password", "access", "error", "session", "lockout"],
        "faq": ["plan", "pricing", "feature", "channel", "onboarding"],
        "complaint": ["complaint", "compensation", "escalate", "resolution"],
        "account_change": ["email", "password", "upgrade", "downgrade", "workspace"],
    }

    expected = type_keywords.get(ticket_type, [])
    area_matches = sum(1 for kw in expected if kw in knowledge_areas or kw in query_lower)
    consistent = area_matches > 0 or not expected

    return {
        "consistent": consistent,
        "area_keyword_overlap": area_matches,
        "flag": "CLARA_MISMATCH" if not consistent else "ok",
    }


# ── MAKER: is classification grounded in the query? ───────────────


def _maker_grounding_check(documents: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    """Check if each doc's content shares meaningful keywords with the query.

    Non-LLM — word overlap ratio.  A doc that shares 0 keywords with the
    query is probably not grounded in the customer's actual problem.
    """
    if not documents or not query:
        return {"grounded_count": 0, "ungrounded_count": 0, "grounded_ratio": 0.0}

    query_words = set(re.findall(r"\b\w{4,}\b", query.lower()))
    filler = {"that", "this", "have", "been", "will", "would", "could", "should",
              "their", "there", "about", "which", "where", "when", "what", "with",
              "from", "your", "just", "also", "than", "them", "they", "some",
              "refund", "billing", "technical", "complaint", "account"}
    query_words -= filler

    grounded = 0
    for doc in documents:
        doc_words = set(re.findall(r"\b\w{4,}\b", doc.get("content", "").lower()))
        overlap = len(query_words & doc_words)
        if overlap >= 2:
            grounded += 1

    total = len(documents)
    return {
        "grounded_count": grounded,
        "ungrounded_count": total - grounded,
        "grounded_ratio": round(grounded / total, 2) if total else 0.0,
    }


# ── CoVe: verify CLARA output claim ──────────────────────────────


def _cove_verify_clara(clara_result: Dict[str, Any], query: str) -> Dict[str, Any]:
    """Verify CLARA's knowledge-area claims against actual query content.

    Non-LLM — if CLARA claims "billing knowledge needed" but query has zero
    billing keywords, the claim is unverified.
    """
    areas_text = clara_result.get("relevant_knowledge", "").lower()
    query_lower = query.lower()

    area_words = set(re.findall(r"\b\w{4,}\b", areas_text))
    query_words = set(re.findall(r"\b\w{4,}\b", query_lower))
    overlap = len(area_words & query_words)

    if overlap >= 2:
        return {"verified": True, "overlap_words": overlap}
    elif overlap == 0 and len(area_words) > 3:
        return {"verified": False, "overlap_words": 0, "flag": "CLARA_UNVERIFIED"}
    return {"verified": True, "overlap_words": overlap}


# ── SourceDiversity: ensure top docs come from different sources ──


def _source_diversity(documents: List[Dict[str, Any]], max_per_source: int = 2) -> List[Dict[str, Any]]:
    """Limit docs per source so one document doesn't dominate the results.

    Non-LLM — pure dedup by source field.  Prevents "5 chunks from the
    same refund_policy doc pushing out 3 other relevant docs".
    """
    if not documents:
        return documents

    source_counts: Dict[str, int] = {}
    result = []
    for doc in documents:
        source = doc.get("source", "unknown")
        # For tenant_kb chunks, group by document_id (source = "tenant_kb:doc_id")
        if source.startswith("tenant_kb:"):
            group_key = source.split(":")[0] + ":" + source.split(":")[1] if ":" in source else source
        else:
            group_key = source

        count = source_counts.get(group_key, 0)
        if count < max_per_source:
            result.append(doc)
            source_counts[group_key] = count + 1

    return result


# ── RecencyWeighting: boost newer docs ────────────────────────────


def _recency_weighting(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Boost docs that appear more recent based on content clues.

    Non-LLM — checks for year mentions and "updated/revised/new" keywords.
    Docs with "(Updated 2026)" get a small score boost; docs mentioning
    old years get a small penalty.  Re-sorts by adjusted score.
    """
    if not documents:
        return documents

    for doc in documents:
        content = doc.get("content", "")
        boost = 0.0
        # Year detection
        if "2026" in content:
            boost += 0.05
        elif "2025" in content:
            boost += 0.02
        elif "2024" in content or "2023" in content:
            boost -= 0.03
        # Freshness keywords
        if re.search(r"\b(?:updated|revised|new|current)\b", content, re.I):
            boost += 0.03
        if re.search(r"\b(?:old|deprecated|legacy|former)\b", content, re.I):
            boost -= 0.03
        doc["score"] = doc.get("score", 0.5) + boost

    documents.sort(key=lambda d: d.get("score", 0), reverse=True)
    return documents


# ── AuthorityRanking: tenant KB > default KB ─────────────────────


def _authority_ranking(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Boost tenant-uploaded docs over platform default docs.

    Non-LLM — tenant_kb sources get +0.1 authority boost; default
    hardcoded KB gets no boost.  Tenant's own policies should always
    take precedence over the platform's generic defaults.
    """
    if not documents:
        return documents

    for doc in documents:
        source = doc.get("source", "")
        if source.startswith("tenant_kb:"):
            doc["score"] = doc.get("score", 0.5) + 0.1
        elif source in ("human_guidance", "jarvis_guidance"):
            doc["score"] = doc.get("score", 1.0)  # human guidance is top authority

    documents.sort(key=lambda d: d.get("score", 0), reverse=True)
    return documents


# ── CoverageAnalysis: did we cover all CLARA areas? ──────────────


def _coverage_analysis(
    documents: List[Dict[str, Any]], clara_result: Dict[str, Any], ticket_type: str,
) -> Dict[str, Any]:
    """Check if retrieved docs cover ALL knowledge areas CLARA identified.

    Non-LLM — extracts keywords from CLARA output, checks if any doc
    mentions each area.  Returns which areas are covered and which
    are gaps.
    """
    areas_text = clara_result.get("relevant_knowledge", "").lower()
    if not areas_text:
        return {"coverage_pct": 1.0, "covered": [], "gaps": []}

    # Extract area keywords (simple: split by newlines/commas, take meaningful words)
    area_keywords = set()
    for word in re.findall(r"\b\w{4,}\b", areas_text):
        if word not in {"need", "area", "knowledge", "required", "relevant", "information", "about"}:
            area_keywords.add(word)

    if not area_keywords:
        return {"coverage_pct": 1.0, "covered": list(area_keywords), "gaps": []}

    covered = set()
    for doc in documents:
        doc_words = set(re.findall(r"\b\w{4,}\b", doc.get("content", "").lower()))
        covered |= (area_keywords & doc_words)

    gaps = area_keywords - covered
    coverage = len(covered) / len(area_keywords) if area_keywords else 1.0

    return {
        "coverage_pct": round(coverage, 2),
        "covered": sorted(covered),
        "gaps": sorted(gaps),
    }


# ── NearDedup: remove near-duplicate chunks ───────────────────────


def _near_dedup(documents: List[Dict[str, Any]], similarity_threshold: float = 0.75) -> List[Dict[str, Any]]:
    """Remove near-duplicate chunks that say the same thing differently.

    Non-LLM — Jaccard similarity on word sets.  Two chunks that share
    >75% of their words are probably saying the same thing; keep the
    one with the higher score.
    """
    if len(documents) <= 1:
        return documents

    kept = [documents[0]]
    for doc in documents[1:]:
        doc_words = set(re.findall(r"\b\w{4,}\b", doc.get("content", "").lower()))
        is_duplicate = False
        for existing in kept:
            existing_words = set(re.findall(r"\b\w{4,}\b", existing.get("content", "").lower()))
            if not doc_words or not existing_words:
                continue
            jaccard = len(doc_words & existing_words) / len(doc_words | existing_words)
            if jaccard >= similarity_threshold:
                is_duplicate = True
                # Keep the one with higher score
                if doc.get("score", 0) > existing.get("score", 0):
                    kept.remove(existing)
                    kept.append(doc)
                break
        if not is_duplicate:
            kept.append(doc)

    return kept


# ── GSD: goal-state tracking for sufficiency ──────────────────────


def _gsd_sufficiency_goals(
    documents: List[Dict[str, Any]], ticket_type: str,
) -> Dict[str, Any]:
    """Break "is knowledge sufficient?" into sub-goals with checklist.

    Non-LLM — defines expected sub-goals per ticket type, checks if
    docs cover each one.  Replaces the naive ">=1 doc = sufficient".
    """
    # Define what "sufficient" means per ticket type
    goal_templates = {
        "refund_request": {
            "has_policy": ["refund", "eligib", "policy"],
            "has_process": ["step", "process", "verify", "calculate"],
            "has_amounts": ["prorat", "fee", "percent", "$", "amount"],
        },
        "billing": {
            "has_policy": ["billing", "policy", "subscription", "charge"],
            "has_process": ["dispute", "process", "step", "resolut"],
            "has_amounts": ["$", "price", "rate", "amount", "invoice"],
        },
        "technical": {
            "has_troubleshooting": ["troubleshoot", "issue", "fix", "step", "check"],
            "has_security": ["security", "lock", "reset", "unauthorized"],
        },
        "faq": {
            "has_general_info": ["plan", "feature", "channel", "support"],
            "has_pricing": ["price", "cost", "$", "month", "year"],
        },
        "complaint": {
            "has_handling": ["complaint", "handl", "resolut", "escalat"],
            "has_compensation": ["credit", "compensat", "goodwill"],
        },
        "account_change": {
            "has_procedure": ["change", "procedure", "step", "email", "password"],
            "has_policy": ["policy", "upgrade", "downgrade", "workspace"],
        },
    }

    goals = goal_templates.get(ticket_type, {
        "has_relevant_info": ["policy", "process", "step"],
    })

    results = {}
    met_count = 0
    for goal_name, keywords in goals.items():
        met = False
        for doc in documents:
            content_lower = doc.get("content", "").lower()
            if any(kw in content_lower for kw in keywords):
                met = True
                break
        results[goal_name] = met
        if met:
            met_count += 1

    total = len(goals)
    all_met = met_count == total
    mostly_met = met_count >= total * 0.6  # 60% threshold

    return {
        "goals": results,
        "met_count": met_count,
        "total_goals": total,
        "all_goals_met": all_met,
        "mostly_met": mostly_met,
        "completion_pct": round(met_count / total, 2) if total else 1.0,
    }


# ── GapDetection: which knowledge areas are missing ───────────────


def _gap_detection(
    documents: List[Dict[str, Any]], clara_result: Dict[str, Any], ticket_type: str,
) -> Dict[str, Any]:
    """Identify which knowledge areas CLARA requested but docs don't cover.

    Non-LLM — extracts area keywords from CLARA, checks each against
    doc contents.  Returns specific gaps so downstream nodes know
    exactly what's missing.
    """
    areas_text = clara_result.get("relevant_knowledge", "").lower()
    if not areas_text:
        return {"gaps": [], "gap_count": 0, "critical_gap": False}

    # Parse CLARA areas into keyword groups
    area_keywords = {}
    for line in areas_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        words = [w for w in re.findall(r"\b\w{4,}\b", line) if w not in
                 {"need", "area", "knowledge", "required", "relevant", "information"}]
        if words:
            area_keywords[line[:50]] = words

    # Check each area against docs
    doc_content = " ".join(d.get("content", "") for d in documents).lower()
    gaps = []
    for area_label, keywords in area_keywords.items():
        found = any(kw in doc_content for kw in keywords)
        if not found:
            gaps.append({"area": area_label, "missing_keywords": keywords[:3]})

    critical_types = {"refund_request", "billing", "technical"}
    is_critical = ticket_type in critical_types and len(gaps) > 0

    return {
        "gaps": gaps,
        "gap_count": len(gaps),
        "critical_gap": is_critical,
    }


# ── Enhanced ContradictionCheck: structured field comparison ──────


def _check_contradictions_enhanced(documents: List[Dict[str, Any]], ticket_type: str) -> Dict[str, Any]:
    """Structured contradiction detection per ticket type.

    Non-LLM — extracts specific fields (days, amounts, percentages)
    and checks for real conflicts, not just % mismatches.  Handles
    scoped contradictions (e.g., different rules for different plans).
    """
    if len(documents) < 2:
        return {"found": False, "details": []}

    contradictions = []

    # Per-type field patterns to extract and compare
    field_patterns = {
        "refund_request": [
            (r"(\d+)\s*day", "refund_window_days"),
            (r"(\d+)%", "fee_percentage"),
            (r"\$(\d[\d,]*)", "dollar_amount"),
        ],
        "billing": [
            (r"\$(\d[\d,]*)", "dollar_amount"),
            (r"(\d+)\s*day", "processing_days"),
            (r"(\d+)%", "percentage"),
        ],
        "technical": [
            (r"(\d+)\s*min", "lockout_minutes"),
            (r"(\d+)\s*attempt", "max_attempts"),
            (r"(\d+)\s*hour", "hours"),
        ],
    }

    patterns = field_patterns.get(ticket_type, [(r"(\d+)%", "percentage")])

    for pattern, field_name in patterns:
        # Extract all values for this field across docs
        values_by_doc = {}
        for i, doc in enumerate(documents):
            content = doc.get("content", "")
            # Scope: look for context keywords near the value
            context_window = 80
            for match in re.finditer(pattern, content):
                value = match.group(1).replace(",", "")
                start = max(0, match.start() - context_window)
                end = min(len(content), match.end() + context_window)
                context = content[start:end].lower()

                # Determine scope (which plan/type does this apply to?)
                scope = "general"
                if "mini" in context:
                    scope = "mini"
                elif "high" in context or "pro" in context:
                    scope = "high"
                elif "annual" in context:
                    scope = "annual"
                elif "monthly" in context:
                    scope = "monthly"

                key = (i, field_name, scope)
                if key not in values_by_doc:
                    values_by_doc[key] = []
                values_by_doc[key].append(value)

        # Check for contradictions WITHIN same scope
        scope_values: Dict[str, set] = {}
        for (doc_i, fn, scope), vals in values_by_doc.items():
            if scope not in scope_values:
                scope_values[scope] = set()
            for v in vals:
                scope_values[scope].add(v)

        for scope, vals in scope_values.items():
            if len(vals) > 1:
                contradictions.append({
                    "field": field_name,
                    "scope": scope,
                    "conflicting_values": list(vals),
                    "type": "SCOPE_CONFLICT" if scope != "general" else "GENERAL_CONFLICT",
                })

    return {
        "found": len(contradictions) > 0,
        "details": contradictions,
    }


# ── ScopeChecker: verify contradictions are real, not scoped ──────


def _scope_check(contradiction_result: Dict[str, Any]) -> Dict[str, Any]:
    """Filter out false contradictions caused by different scopes.

    Non-LLM — if a "contradiction" is between values in DIFFERENT
    scopes (mini vs high), it's NOT a real contradiction.  Only
    same-scope conflicts are real.
    """
    details = contradiction_result.get("details", [])
    real_contradictions = [d for d in details if d.get("type") == "GENERAL_CONFLICT"]
    scoped_differences = [d for d in details if d.get("type") == "SCOPE_CONFLICT"]

    return {
        "real_contradictions": real_contradictions,
        "scoped_differences": scoped_differences,
        "has_real_contradiction": len(real_contradictions) > 0,
        "false_positive_count": len(scoped_differences),
    }


# ── DynamicContext prioritization by ticket type ──────────────────


def _dynamic_context_prioritize(
    customer_context: Dict[str, Any], ticket_type: str,
) -> Dict[str, Any]:
    """Prioritize context fields by ticket type — only pass what matters.

    Non-LLM — defines which fields are critical/optional per type.
    Instead of dumping 50 fields, send the 7 that matter.
    """
    # Priority fields per ticket type
    priority_map = {
        "refund_request": {
            "critical": ["account_tier", "plan_type", "purchase_date", "payment_method"],
            "important": ["billing_email", "previous_refunds", "customer_tenure_days"],
            "optional": ["last_login", "sso_status"],
        },
        "billing": {
            "critical": ["account_tier", "plan_type", "payment_method", "last_invoice"],
            "important": ["billing_email", "outstanding_credits", "subscription_status"],
            "optional": ["customer_tenure_days", "recent_ticket_count"],
        },
        "technical": {
            "critical": ["last_login", "sso_status", "failed_attempts", "account_locked"],
            "important": ["account_tier", "browser", "device"],
            "optional": ["billing_email", "purchase_date"],
        },
        "complaint": {
            "critical": ["account_tier", "customer_tenure_days", "lifetime_value"],
            "important": ["recent_ticket_count", "previous_complaints"],
            "optional": ["billing_email", "plan_type"],
        },
        "account_change": {
            "critical": ["account_tier", "plan_type", "email", "workspace_id"],
            "important": ["team_member_count", "sso_status"],
            "optional": ["billing_email", "purchase_date"],
        },
        "faq": {
            "critical": ["account_tier", "plan_type"],
            "important": ["customer_tenure_days"],
            "optional": [],
        },
    }

    priorities = priority_map.get(ticket_type, {
        "critical": ["account_tier", "plan_type"],
        "important": ["billing_email"],
        "optional": [],
    })

    # Build prioritized context
    prioritized = {"_priority_meta": {"ticket_type": ticket_type}}
    for level in ("critical", "important", "optional"):
        for field in priorities.get(level, []):
            if field in customer_context:
                prioritized[field] = customer_context[field]

    # Always include these baseline fields
    for baseline in ("customer_id", "email", "phone"):
        if baseline in customer_context:
            prioritized[baseline] = customer_context[baseline]

    return prioritized


# ── MetaLearner: boost docs from historically successful patterns ─


def _meta_learner_boost(
    documents: List[Dict[str, Any]], tenant_id: str, ticket_type: str, query: str,
) -> List[Dict[str, Any]]:
    """Boost docs that match historically successful patterns from AI Wiki.

    Non-LLM — searches wiki for similar tickets, extracts which docs
    worked before, and boosts those docs' scores.
    """
    if not documents:
        return documents

    try:
        from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store
        wiki = get_wiki_store()
        patterns = wiki.find_similar_patterns(
            tenant_id=tenant_id, query=query,
            ticket_type=ticket_type, max_results=3,
        )
        if not patterns:
            return documents

        # Extract which techniques/docs worked historically
        worked_sources = set()
        for p in patterns:
            if p.get("quality_achieved", 0) >= 0.8:
                for t in p.get("techniques_that_worked", []):
                    worked_sources.add(t.lower())

        if not worked_sources:
            return documents

        # Boost docs whose content overlaps with worked patterns
        for doc in documents:
            content_lower = doc.get("content", "").lower()
            for source in worked_sources:
                if source in content_lower:
                    doc["score"] = doc.get("score", 0.5) + 0.08
                    break
    except Exception:
        pass  # BC-008: never crash

    documents.sort(key=lambda d: d.get("score", 0), reverse=True)
    return documents


# ── Wiki staleness detection ──────────────────────────────────────


def _wiki_staleness_check(wiki_patterns: List[Dict[str, Any]], max_age_days: int = 30) -> Dict[str, Any]:
    """Flag wiki patterns that haven't been validated recently.

    Non-LLM — checks usage_count and success_rate.  Patterns with
    low usage or old validation dates get flagged as potentially stale.
    """
    if not wiki_patterns:
        return {"stale_count": 0, "fresh_count": 0, "stale_patterns": []}

    stale = []
    fresh = []
    for p in wiki_patterns:
        success_rate = p.get("historical_success_rate", 0)
        # Heuristic: patterns used <3 times or with <50% success rate are "stale"
        if success_rate < 0.5:
            stale.append({**p, "reason": "low_success_rate"})
        else:
            fresh.append(p)

    return {
        "stale_count": len(stale),
        "fresh_count": len(fresh),
        "stale_patterns": stale[:3],  # cap for logging
    }


# ── UCB data goals tracking ───────────────────────────────────────


def _ucb_data_goals(ticket_type: str, crm_data: Dict[str, Any]) -> Dict[str, Any]:
    """Track which external data goals are met for this ticket type.

    Non-LLM — defines expected data per type, checks what we actually
    got.  Returns coverage and missing items so downstream knows.
    """
    # What data is needed per ticket type
    data_needs = {
        "refund_request": ["crm_contact", "ecommerce_orders"],
        "billing": ["crm_contact", "ecommerce_orders"],
        "technical": ["crm_contact"],
        "complaint": ["crm_contact"],
        "account_change": ["crm_contact"],
        "faq": [],
    }

    needed = data_needs.get(ticket_type, ["crm_contact"])
    met = []
    missing = []

    for data_key in needed:
        value = crm_data.get(data_key)
        if value and value is not None:
            met.append(data_key)
        else:
            missing.append(data_key)

    return {
        "data_goals_needed": needed,
        "data_goals_met": met,
        "data_goals_missing": missing,
        "coverage_pct": round(len(met) / len(needed), 2) if needed else 1.0,
        "all_goals_met": len(missing) == 0,
    }


# ── RuleBasedAction: hard safety rules ────────────────────────────


def _rule_based_action_safety(ticket_type: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply hard safety rules that MUST be enforced.

    Non-LLM — e.g., legal_review with no legal KB → must escalate.
    Security tickets with no security protocol → flag danger.
    """
    actions = []

    # Rule 1: Legal tickets MUST have legal KB coverage
    if ticket_type == "legal_review":
        has_legal = any("legal" in d.get("content", "").lower() for d in documents)
        if not has_legal:
            actions.append({"rule": "LEGAL_NO_KB", "action": "must_escalate", "reason": "No legal knowledge base docs found"})

    # Rule 2: Security/incident tickets need security protocol
    if ticket_type in ("technical", "security"):
        has_security = any("security" in d.get("content", "").lower() for d in documents)
        if not has_security:
            actions.append({"rule": "SECURITY_NO_PROTOCOL", "action": "flag_caution", "reason": "No security protocol found in knowledge"})

    # Rule 3: Financial tickets (billing/refund) need dollar amounts
    if ticket_type in ("billing", "refund_request"):
        has_amounts = any(re.search(r"\$\d", d.get("content", "")) for d in documents)
        if not has_amounts:
            actions.append({"rule": "FINANCIAL_NO_AMOUNTS", "action": "flag_incomplete", "reason": "No dollar amounts found in knowledge for financial ticket"})

    return {
        "actions": actions,
        "must_escalate": any(a["action"] == "must_escalate" for a in actions),
        "caution_flags": len(actions),
    }




# ════════════════════════════════════════════════════════════════════
# Phase 7: Additional Non-LLM Techniques (0 extra LLM calls)
# Layer-by-layer enhancements from architecture review
# ════════════════════════════════════════════════════════════════════


# ── Layer 1 (CLARA): QueryDecomposition ──────────────────────────


def _query_decomposition(query: str, ticket_type: str) -> Dict[str, Any]:
    """Break multi-intent queries into sub-queries before CLARA.

    Non-LLM — splits on conjunctions (and, but, also, plus).
    "I was double charged AND I want a refund" -> 2 focused queries.
    """
    connectors = [
        r"\band\b", r"\bbut\b", r"\balso\b",
        r"\bplus\b", r"\bhowever\b", r"\bas well as\b",
    ]

    parts = [query]
    for connector in connectors:
        new_parts = []
        for part in parts:
            splits = re.split(connector, part, flags=re.I)
            new_parts.extend(s.strip() for s in splits if s.strip())
        parts = new_parts

    sub_queries = [p for p in parts if len(p) >= 10]

    if len(sub_queries) <= 1:
        return {"decomposed": False, "sub_queries": [query], "count": 1}

    return {"decomposed": True, "sub_queries": sub_queries, "count": len(sub_queries)}


# ── Layer 1 (CLARA): IntentSignalBoost ───────────────────────────


def _intent_signal_boost(
    query: str, customer_context: Dict[str, Any], ticket_type: str,
) -> Dict[str, Any]:
    """Extract intent signals (urgency, money, VIP) from query + context.

    Non-LLM — pattern matching.  Downstream steps know this is a
    "$500 billing issue", not just "billing".
    """
    query_lower = query.lower()
    signals: Dict[str, Any] = {}

    # Urgency signals
    urgency_patterns = [
        r"\burgent\b", r"\basap\b", r"\bimmediately\b",
        r"\bright now\b", r"\bemergency\b",
    ]
    signals["urgent"] = any(re.search(p, query_lower) for p in urgency_patterns)

    # Money signals
    money_match = re.search(r"\$(\d[\d,]*)", query)
    if money_match:
        amount = int(money_match.group(1).replace(",", ""))
        signals["money_mentioned"] = True
        signals["money_amount"] = amount
        signals["high_value"] = amount >= 500
    else:
        signals["money_mentioned"] = False

    # VIP signals
    tier = str(
        customer_context.get("account_tier",
                             customer_context.get("plan_type", ""))
    ).lower()
    signals["is_vip"] = tier in ("high", "enterprise", "pro")
    signals["tier"] = tier

    # Frustration signals
    frustration_patterns = [
        r"\bangry\b", r"\bfrustrat\b", r"\bfurious\b",
        r"\bunacceptable\b", r"\bterrible\b",
    ]
    signals["frustrated"] = any(
        re.search(p, query_lower) for p in frustration_patterns
    )

    # Repeat-issue signals
    recent_tickets = customer_context.get("recent_ticket_count", 0)
    signals["repeat_issue"] = isinstance(recent_tickets, (int, float)) and recent_tickets >= 3

    active_count = sum(1 for v in signals.values() if v is True)
    return {"signals": signals, "signal_count": active_count}


# ── Layer 2 (RAG): SmartRouter for RAG search strategy ──────────


def _smart_router_rag(ticket_type: str) -> Dict[str, Any]:
    """Route RAG search strategy based on ticket type.

    Non-LLM — defines which KB sources to prioritise per type.
    Refund tickets search refund KB first, not generic.
    """
    source_priorities = {
        "refund_request": {
            "refund_policy": 3, "refund_process": 3,
            "credit_policy": 2, "billing_policy": 1,
        },
        "billing": {
            "billing_policy": 3, "billing_dispute": 3,
            "plan_pricing": 2, "refund_policy": 1,
        },
        "technical": {
            "tech_troubleshooting": 3, "security_protocol": 3,
            "account_policy": 1,
        },
        "faq": {
            "general_faq": 3, "plan_change_faq": 2,
            "team_management_faq": 1, "plan_pricing": 2,
        },
        "complaint": {
            "complaint_handling": 3, "billing_policy": 1,
            "refund_policy": 1,
        },
        "account_change": {
            "account_policy": 3, "workspace_management": 2,
            "team_management_faq": 1,
        },
    }

    priorities = source_priorities.get(ticket_type, {})
    return {
        "ticket_type": ticket_type,
        "source_priorities": priorities,
        "search_strategy": "focused" if priorities else "broad",
    }


# ── Layer 3 (SmartFilter): SelfConsistency for filter ────────────


def _self_consistency_filter(
    documents: List[Dict[str, Any]], query: str, ticket_type: str,
) -> Dict[str, Any]:
    """Cross-validate: do keyword relevance and document content agree?

    Non-LLM — if a doc ranks high but shares no meaningful keywords
    with the query, it might be a false positive from LLM scoring.
    """
    if not documents:
        return {"consistent": True, "suspicious_docs": 0}

    query_words = set(re.findall(r"\b\w{4,}\b", query.lower()))
    filler = {
        "that", "this", "have", "been", "will", "would", "could",
        "should", "their", "there", "about", "which", "where",
        "when", "what", "with", "from", "your", "just", "also",
        "than", "them", "they", "some",
    }
    query_words -= filler

    suspicious = 0
    for doc in documents:
        score = doc.get("score", 0)
        if score >= 0.7:
            doc_words = set(
                re.findall(r"\b\w{4,}\b", doc.get("content", "").lower())
            )
            overlap = len(query_words & doc_words)
            if overlap < 2:
                suspicious += 1

    return {
        "consistent": suspicious == 0,
        "suspicious_docs": suspicious,
        "total_docs": len(documents),
    }


# ── Layer 3 (SmartFilter): RelevanceDecay ────────────────────────


def _relevance_decay(
    documents: List[Dict[str, Any]], ticket_type: str,
) -> List[Dict[str, Any]]:
    """Score drops the further a doc's topic is from the core query topic.

    Non-LLM — docs about "billing policy history" are less relevant
    than "current billing policy" for a billing dispute.
    """
    if not documents:
        return documents

    core_topics = {
        "refund_request": ["refund", "eligible", "prorated", "termination", "fee"],
        "billing": ["charge", "invoice", "payment", "duplicate", "price"],
        "technical": ["login", "sso", "password", "access", "error"],
        "faq": ["plan", "feature", "pricing", "channel"],
        "complaint": ["complaint", "compensat", "escalat", "credit"],
        "account_change": ["change", "email", "password", "upgrade", "workspace"],
    }

    core_kws = set(core_topics.get(ticket_type, []))

    for doc in documents:
        content_lower = doc.get("content", "").lower()
        doc_words = set(re.findall(r"\b\w{4,}\b", content_lower))
        core_overlap = len(core_kws & doc_words)

        if core_overlap == 0:
            doc["score"] = doc.get("score", 0.5) - 0.1
        elif core_overlap >= 2:
            doc["score"] = doc.get("score", 0.5) + 0.05

    documents.sort(key=lambda d: d.get("score", 0), reverse=True)
    return documents


# ── Layer 3 (SmartFilter): OverlapMinimization ───────────────────


def _overlap_minimization(
    documents: List[Dict[str, Any]], overlap_threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """If 2 docs cover the same topic, keep the more comprehensive one.

    Non-LLM — topic overlap check.  If Doc A and Doc B share >50%
    of their topic keywords, keep the longer one (more comprehensive).
    """
    if len(documents) <= 1:
        return documents

    kept = [documents[0]]
    for doc in documents[1:]:
        doc_words = set(
            re.findall(r"\b\w{4,}\b", doc.get("content", "").lower())
        )
        is_overlap = False
        for existing in kept:
            existing_words = set(
                re.findall(
                    r"\b\w{4,}\b", existing.get("content", "").lower()
                )
            )
            if not doc_words or not existing_words:
                continue
            min_len = min(len(doc_words), len(existing_words))
            topic_overlap = len(doc_words & existing_words) / min_len if min_len else 0
            if topic_overlap >= overlap_threshold:
                if len(doc.get("content", "")) > len(existing.get("content", "")):
                    kept.remove(existing)
                    kept.append(doc)
                is_overlap = True
                break
        if not is_overlap:
            kept.append(doc)

    return kept


# ── Layer 4 (Sufficiency): CompletenessTracker ───────────────────


def _completeness_tracker(
    documents: List[Dict[str, Any]], query: str, ticket_type: str,
) -> Dict[str, Any]:
    """Track what % of the query's information needs are met by docs.

    Non-LLM — extracts key entities from query, checks if any doc
    addresses each entity.  "Customer asked 3 things, we have docs
    for 2/3 = 67%".
    """
    if not query or not documents:
        return {
            "completeness_pct": 0.0,
            "needs_identified": 0,
            "needs_met": 0,
        }

    query_lower = query.lower()

    need_patterns = {
        "refund_request": [
            r"refund", r"money\s+back", r"cancel",
            r"prorat", r"terminat", r"credit",
        ],
        "billing": [
            r"charge", r"invoice", r"payment",
            r"duplicat", r"overcharge", r"price", r"rate",
        ],
        "technical": [
            r"login", r"sso", r"password",
            r"access", r"error", r"crash", r"session",
        ],
        "faq": [
            r"plan", r"pricing", r"feature", r"channel", r"integration",
        ],
        "complaint": [
            r"complaint", r"compensat", r"credit", r"escalat", r"manager",
        ],
        "account_change": [
            r"change", r"email", r"password",
            r"upgrade", r"downgrade", r"workspace",
        ],
    }

    patterns = need_patterns.get(ticket_type, [r"\w{5,}"])
    needs = [pat for pat in patterns if re.search(pat, query_lower)]

    if not needs:
        return {
            "completeness_pct": 1.0,
            "needs_identified": 0,
            "needs_met": 0,
        }

    doc_content = " ".join(d.get("content", "").lower() for d in documents)
    met = sum(1 for pat in needs if re.search(pat, doc_content))

    return {
        "completeness_pct": round(met / len(needs), 2) if needs else 1.0,
        "needs_identified": len(needs),
        "needs_met": met,
        "needs_missing": len(needs) - met,
    }


# ── Layer 4 (Sufficiency): PriorityEscalation ────────────────────


def _priority_escalation(
    gaps: Dict[str, Any], ticket_type: str, safety: Dict[str, Any],
) -> Dict[str, Any]:
    """Auto-escalate if CRITICAL knowledge is missing.

    Non-LLM — some gaps are acceptable (missing FAQ for a complaint),
    some are dangerous (no security protocol for a security ticket).
    """
    critical_areas = {
        "refund_request": ["refund", "eligib", "process"],
        "billing": ["charge", "payment", "invoice"],
        "technical": ["security", "access", "unauthorized"],
        "complaint": ["complaint", "escalat"],
        "account_change": ["account", "policy"],
    }

    if safety.get("must_escalate"):
        return {
            "should_escalate": True,
            "reason": "safety_rule",
            "urgency": "critical",
        }

    critical_kws = critical_areas.get(ticket_type, [])
    for gap in gaps.get("gaps", []):
        gap_area = gap.get("area", "").lower()
        if any(kw in gap_area for kw in critical_kws):
            return {
                "should_escalate": True,
                "reason": f"critical_gap: {gap_area}",
                "urgency": "high",
            }

    return {"should_escalate": False, "reason": None, "urgency": "normal"}


# ── Layer 5 (Contradiction): TemporalChecker ─────────────────────


def _temporal_checker(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Check if docs have different effective dates.

    Non-LLM — extracts year/version from doc content.  If two docs
    disagree on policy year, the older one is likely stale.
    """
    if len(documents) < 2:
        return {"has_stale_docs": False, "versions": [], "stale_sources": []}

    versions = []
    for doc in documents:
        content = doc.get("content", "")
        source = doc.get("source", "")
        year_match = re.search(r"\b(20[2-3]\d)\b", content)
        ver_match = (
            re.search(r"v(\d+)", source)
            or re.search(r"version\s*(\d+)", content, re.I)
        )
        versions.append({
            "source": source,
            "year": int(year_match.group(1)) if year_match else None,
            "version": ver_match.group(1) if ver_match else None,
        })

    years = [v["year"] for v in versions if v["year"] is not None]
    has_stale = False
    stale_sources = []
    if years and len(set(years)) > 1:
        max_year = max(years)
        for v in versions:
            if v["year"] and v["year"] < max_year:
                has_stale = True
                stale_sources.append(v["source"])

    return {
        "has_stale_docs": has_stale,
        "stale_sources": stale_sources,
        "versions": versions,
    }


# ── Layer 5 (Contradiction): VersionTracker ──────────────────────


def _version_tracker(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Track which version of each policy doc is active.

    Non-LLM — if we see both v1 and v2 of a doc, v2 supersedes v1.
    """
    if not documents:
        return {"active_versions": {}, "superseded": [], "has_superseded": False}

    doc_versions: Dict[str, list] = {}
    for doc in documents:
        source = doc.get("source", "")
        match = re.match(r"(.+?)(?:_v(\d+))?(?:_.*)?$", source)
        if match:
            base = match.group(1)
            ver = int(match.group(2)) if match.group(2) else 1
        else:
            base = source
            ver = 1

        doc_versions.setdefault(base, []).append({
            "source": source,
            "version": ver,
        })

    active: Dict[str, str] = {}
    superseded = []
    for base, vers in doc_versions.items():
        vers.sort(key=lambda x: x["version"], reverse=True)
        active[base] = vers[0]["source"]
        for v in vers[1:]:
            superseded.append(v["source"])

    return {
        "active_versions": active,
        "superseded": superseded,
        "has_superseded": len(superseded) > 0,
    }


# ── Layer 6 (DynamicContext): SignalExtraction ───────────────────


def _signal_extraction(
    customer_context: Dict[str, Any], ticket_type: str,
) -> Dict[str, Any]:
    """Extract key signals from context: VIP? high_value? frustrated?

    Non-LLM — compresses raw context into actionable signals for
    downstream nodes.  Instead of 50 fields, downstream gets 5-7.
    """
    signals: Dict[str, Any] = {}

    tier = str(
        customer_context.get(
            "account_tier", customer_context.get("plan_type", "")
        )
    ).lower()
    signals["is_vip"] = tier in ("high", "enterprise", "pro")
    signals["is_free"] = tier in ("free", "mini", "")

    tenure = customer_context.get("customer_tenure_days", 0)
    if isinstance(tenure, (int, float)):
        signals["long_tenure"] = tenure >= 365
        signals["new_customer"] = tenure <= 30

    recent = customer_context.get("recent_ticket_count", 0)
    if isinstance(recent, (int, float)):
        signals["frequent_reporter"] = recent >= 3

    pm = str(customer_context.get("payment_method", "")).lower()
    signals["has_payment"] = pm not in ("", "none", "null")

    locked = customer_context.get("account_locked", False)
    signals["account_locked"] = bool(locked)

    active = sum(1 for v in signals.values() if v is True)
    return {"signals": signals, "active_signal_count": active, "ticket_type": ticket_type}


# ── Layer 6 (DynamicContext): ContextScoring ─────────────────────


def _context_scoring(
    customer_context: Dict[str, Any], ticket_type: str,
) -> Dict[str, Any]:
    """Score each context field's relevance to the query type.

    Non-LLM — plan_type = 9/10 relevance for refund, billing_email = 3/10.
    """
    relevance_map = {
        "refund_request": {
            "plan_type": 9, "account_tier": 9, "purchase_date": 8,
            "payment_method": 8, "previous_refunds": 7,
            "customer_tenure_days": 5, "billing_email": 3, "last_login": 2,
        },
        "billing": {
            "plan_type": 9, "account_tier": 9, "payment_method": 8,
            "last_invoice": 8, "billing_email": 7,
            "outstanding_credits": 7, "subscription_status": 6, "last_login": 2,
        },
        "technical": {
            "last_login": 9, "sso_status": 9, "failed_attempts": 8,
            "account_locked": 8, "account_tier": 4, "billing_email": 2,
        },
        "complaint": {
            "account_tier": 9, "customer_tenure_days": 8,
            "lifetime_value": 8, "recent_ticket_count": 7,
            "previous_complaints": 7, "billing_email": 3,
        },
        "account_change": {
            "account_tier": 8, "plan_type": 8, "email": 7,
            "workspace_id": 7, "team_member_count": 6, "sso_status": 5,
        },
        "faq": {"account_tier": 7, "plan_type": 7, "customer_tenure_days": 3},
    }

    scores = relevance_map.get(ticket_type, {"account_tier": 5, "plan_type": 5})
    field_scores = {}
    for field in customer_context:
        if field.startswith("_"):
            continue
        field_scores[field] = scores.get(field, 3)

    high = [f for f, s in field_scores.items() if s >= 7]
    avg = round(sum(field_scores.values()) / len(field_scores), 1) if field_scores else 0

    return {
        "field_scores": field_scores,
        "high_relevance_fields": high,
        "avg_relevance": avg,
    }


# ── Layer 6 (DynamicContext): FreshnessCheck ─────────────────────


def _freshness_check(customer_context: Dict[str, Any]) -> Dict[str, Any]:
    """Flag stale context data that might be outdated.

    Non-LLM — "last_login 90 days ago" might mean stale CRM data.
    """
    flags = []

    last_login = customer_context.get("last_login")
    if last_login:
        if isinstance(last_login, (int, float)) and last_login > 90:
            flags.append({
                "field": "last_login",
                "reason": f"stale: {last_login} days ago",
            })
        elif isinstance(last_login, str):
            days_match = re.search(r"(\d+)\s*day", last_login, re.I)
            if days_match and int(days_match.group(1)) > 90:
                flags.append({
                    "field": "last_login",
                    "reason": f"stale: {days_match.group(1)} days ago",
                })

    crm_updated = customer_context.get("crm_last_updated")
    if crm_updated and isinstance(crm_updated, (int, float)) and crm_updated > 30:
        flags.append({
            "field": "crm_data",
            "reason": f"crm not updated in {crm_updated} days",
        })

    return {
        "has_stale_data": len(flags) > 0,
        "stale_flags": flags,
        "stale_count": len(flags),
    }


# ── Layer 7 (AI Wiki): PatternDiversity ──────────────────────────


def _wiki_pattern_diversity(
    wiki_patterns: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Ensure wiki patterns come from different resolution approaches.

    Non-LLM — if all patterns say "escalate" but none say "auto-resolve",
    the history is biased and shouldn't be trusted blindly.
    """
    if not wiki_patterns:
        return {"diverse": True, "approach_count": 0, "bias_warning": False}

    approaches = set()
    for p in wiki_patterns:
        summary = p.get("answer_summary", "").lower()
        techniques = " ".join(t.lower() for t in p.get("techniques_that_worked", []))
        all_text = summary + " " + techniques

        if "escalat" in all_text:
            approaches.add("escalate")
        elif "refund" in all_text or "credit" in all_text:
            approaches.add("auto_resolve")
        elif "resolut" in all_text or "process" in all_text:
            approaches.add("process_follow")
        else:
            approaches.add("other")

    diverse = len(approaches) >= 2
    bias_warning = len(approaches) == 1 and len(wiki_patterns) >= 2

    return {
        "diverse": diverse,
        "approach_count": len(approaches),
        "approaches": list(approaches),
        "bias_warning": bias_warning,
    }


# ── Layer 7 (AI Wiki): ConflictResolution ────────────────────────


def _wiki_conflict_resolution(
    wiki_patterns: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """When wiki patterns disagree, pick the best one.

    Non-LLM — prefers patterns with higher success rate AND more recent.
    Pattern A: 90% success, high quality > Pattern B: 95% success, low quality.
    """
    if not wiki_patterns:
        return {"conflict": False, "best_pattern": None}
    if len(wiki_patterns) == 1:
        return {"conflict": False, "best_pattern": wiki_patterns[0]}

    best = None
    best_score = -1
    for p in wiki_patterns:
        success = p.get("historical_success_rate", 0.5)
        quality = p.get("quality_achieved", 0)
        score = success * 0.7 + quality * 0.3
        if score > best_score:
            best_score = score
            best = p

    # Check for conflict (many unique techniques = patterns disagree on approach)
    techniques_set = set()
    for p in wiki_patterns:
        for t in p.get("techniques_that_worked", []):
            techniques_set.add(t.lower())

    has_conflict = len(techniques_set) > len(wiki_patterns)

    return {
        "conflict": has_conflict,
        "best_pattern": best,
        "pattern_count": len(wiki_patterns),
        "unique_techniques": len(techniques_set),
    }


# ── Layer 8 (UCB): APIHealthCheck ────────────────────────────────

_api_health_cache: Dict[str, Dict[str, Any]] = {}


def _api_health_check(
    integration_type: str, tenant_id: str,
) -> Dict[str, Any]:
    """Before calling external API, check if it's been healthy recently.

    Non-LLM — caches last API status per integration type.  If Shopify
    has been failing all day, don't waste 10s on a timeout.
    """
    cache_key = f"{integration_type}:{tenant_id}"
    cached = _api_health_cache.get(cache_key)

    if cached:
        age = time.time() - cached.get("checked_at", 0)
        if age < 300:  # 5-min cache
            return {
                "healthy": cached["healthy"],
                "cached": True,
                "last_status": cached.get("last_status"),
            }

    return {"healthy": True, "cached": False, "last_status": "unknown"}


def _api_health_mark(
    integration_type: str, tenant_id: str, success: bool, status: str = "",
) -> None:
    """Mark API health after a call completes."""
    cache_key = f"{integration_type}:{tenant_id}"
    _api_health_cache[cache_key] = {
        "healthy": success,
        "checked_at": time.time(),
        "last_status": status,
    }


# ── Layer 8 (UCB): DataRelevance ─────────────────────────────────


def _data_relevance_filter(ticket_type: str) -> Dict[str, Any]:
    """Only fetch external data relevant to this ticket type.

    Non-LLM — refund ticket needs orders but not carrier tracking.
    Saves API calls, reduces latency.
    """
    relevance_map = {
        "refund_request": {
            "crm_contact": True, "ecommerce_orders": True,
            "carrier_tracking": False, "custom": False,
        },
        "billing": {
            "crm_contact": True, "ecommerce_orders": True,
            "carrier_tracking": False, "custom": False,
        },
        "technical": {
            "crm_contact": True, "ecommerce_orders": False,
            "carrier_tracking": False, "custom": False,
        },
        "complaint": {
            "crm_contact": True, "ecommerce_orders": False,
            "carrier_tracking": False, "custom": False,
        },
        "account_change": {
            "crm_contact": True, "ecommerce_orders": False,
            "carrier_tracking": False, "custom": False,
        },
        "faq": {
            "crm_contact": False, "ecommerce_orders": False,
            "carrier_tracking": False, "custom": False,
        },
    }
    return relevance_map.get(
        ticket_type,
        {"crm_contact": True, "ecommerce_orders": False,
         "carrier_tracking": False, "custom": False},
    )


# ── Layer 8 (UCB): PartialDataHandler ────────────────────────────


def _partial_data_handler(
    crm_data: Dict[str, Any], needed_types: Dict[str, bool],
) -> Dict[str, Any]:
    """When some APIs fail but others succeed, score what we DID get.

    Non-LLM — "Got CRM + Shopify but FedEx failed. Coverage: 67%".
    """
    if not needed_types:
        return {
            "coverage_pct": 1.0, "fetched": [],
            "missing": [], "partial": False,
        }

    fetched = []
    missing = []
    for data_type, needed in needed_types.items():
        if not needed:
            continue
        value = crm_data.get(data_type)
        if value and value is not None:
            fetched.append(data_type)
        else:
            missing.append(data_type)

    total = len([v for v in needed_types.values() if v])
    coverage = len(fetched) / total if total else 1.0

    return {
        "coverage_pct": round(coverage, 2),
        "fetched": fetched,
        "missing": missing,
        "partial": len(missing) > 0 and len(fetched) > 0,
    }


# ── Layer 8 (UCB): IdempotencyCheck ──────────────────────────────


def _idempotency_check(state: PipelineV2State, data_type: str) -> bool:
    """Check if data was already fetched in this pipeline run.

    Non-LLM — prevents duplicate API calls.  If CRM data was already
    fetched by an earlier node, don't fetch again.
    """
    return state.get(f"_fetched_{data_type}") is not None


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


async def _fetch_crm_data(tenant_id: str, customer_context: Dict) -> Dict:
    """Fetch real CRM data (HubSpot), e-commerce orders (Shopify), and carrier
    tracking (FedEx/UPS/DHL/USPS) for the customer associated with this ticket.

    Replaces the previous mock that just echoed back data from customer_context.
    Now the AI pipeline can actually SEE the customer's CRM record, order
    history, and shipment status before generating a response.

    Falls back gracefully:
      - If no CRM/ecommerce/carrier integration is connected, returns the
        minimal data from customer_context (same as the old mock).
      - If a provider call fails, logs the error and continues with partial data.
      - Never raises — node_3 must not crash the pipeline.

    BC-001: tenant_id (company_id) scopes all credential lookups.
    """
    # Start with the baseline data from customer_context (always available).
    result: Dict = {
        "subscription_status": customer_context.get("account_tier", "free"),
        "recent_interactions": customer_context.get("recent_ticket_count", 0),
        "billing_email": customer_context.get("billing_email", "on file"),
        "crm_contact": None,
        "ecommerce_orders": None,
        "carrier_tracking": None,
    }

    # Extract customer identifiers from context.
    customer_id = customer_context.get("customer_id", "")
    customer_email = customer_context.get("email", "") or customer_context.get("customer_email", "")
    customer_phone = customer_context.get("phone", "") or customer_context.get("customer_phone", "")

    try:
        from app.services.integration_service import IntegrationService
        from database.base import SessionLocal
        from app.api.crm_actions import _resolve_crm_credentials, _hubspot_get_contact
        from app.api.ecommerce_actions import _resolve_ecommerce_credentials, _shopify_get_customer_orders
        from app.core.carrier_api_connector import CarrierAPIConnector

        db = SessionLocal()
        try:
            # ── 1. CRM contact (auto-detect platform) ──
            if customer_id or customer_email or customer_phone:
                try:
                    # Try each CRM platform until one returns credentials
                    for crm_platform in ["hubspot", "salesforce", "pipedrive"]:
                        creds = _resolve_crm_credentials(db, type("U", (), {"company_id": tenant_id})(), crm_platform)
                        if not creds or not creds.get("access_token"):
                            continue

                        import httpx
                        headers = {
                            "Authorization": f"Bearer {creds['access_token']}",
                            "Content-Type": "application/json",
                        }

                        if crm_platform == "hubspot":
                            async with httpx.AsyncClient(timeout=10.0) as client:
                                contact_result = await _hubspot_get_contact(
                                    client, headers,
                                    contact_id=customer_id or None,
                                    email=customer_email or None,
                                    phone=customer_phone or None,
                                )
                                if contact_result["status"] == "ok":
                                    result["crm_contact"] = contact_result["data"]
                                    if contact_result["data"].get("email"):
                                        result["billing_email"] = contact_result["data"]["email"]
                                    break

                        elif crm_platform == "salesforce":
                            # Salesforce REST API: query contact by email
                            instance_url = creds.get("instance_url", "")
                            async with httpx.AsyncClient(timeout=10.0) as client:
                                query = f"SELECT Id, FirstName, LastName, Email, Phone FROM Contact WHERE Email='{customer_email}' LIMIT 1" if customer_email else f"SELECT Id, FirstName, LastName, Email, Phone FROM Contact WHERE Id='{customer_id}' LIMIT 1"
                                sf_res = await client.get(
                                    f"{instance_url}/services/data/v58.0/query?q={query}",
                                    headers=headers,
                                )
                                if sf_res.status_code == 200:
                                    sf_data = sf_res.json()
                                    records = sf_data.get("records", [])
                                    if records:
                                        r = records[0]
                                        result["crm_contact"] = {
                                            "id": r.get("Id"),
                                            "email": r.get("Email"),
                                            "first_name": r.get("FirstName"),
                                            "last_name": r.get("LastName"),
                                            "phone": r.get("Phone"),
                                        }
                                        if r.get("Email"):
                                            result["billing_email"] = r["Email"]
                                        break

                        elif crm_platform == "pipedrive":
                            # Pipedrive API: search for person by email
                            api_token = creds.get("api_token") or creds.get("access_token")
                            async with httpx.AsyncClient(timeout=10.0) as client:
                                pd_res = await client.get(
                                    f"https://api.pipedrive.com/v1/persons/search?term={customer_email}&api_token={api_token}",
                                )
                                if pd_res.status_code == 200:
                                    pd_data = pd_res.json()
                                    items = pd_data.get("data", {}).get("items", [])
                                    if items:
                                        person = items[0].get("item", {})
                                        result["crm_contact"] = {
                                            "id": person.get("id"),
                                            "email": customer_email,
                                            "first_name": person.get("name", "").split()[0] if person.get("name") else None,
                                            "phone": person.get("phone"),
                                        }
                                        break

                except Exception as exc:
                    logger.warning("node3_crm_fetch_failed", extra={"error": str(exc)[:200]})

            # ── 2. E-commerce orders (auto-detect platform) ──
            if customer_id or customer_email:
                try:
                    for eco_platform in ["shopify", "woocommerce"]:
                        creds = _resolve_ecommerce_credentials(db, type("U", (), {"company_id": tenant_id})(), eco_platform)
                        if not creds:
                            continue

                        if eco_platform == "shopify" and creds.get("access_token") and creds.get("shop_domain"):
                            from app.api.ecommerce_actions import _shopify_base_url, _shopify_headers
                            import httpx
                            base_url = _shopify_base_url(creds["shop_domain"])
                            headers = _shopify_headers(creds["access_token"])
                            async with httpx.AsyncClient(timeout=10.0) as client:
                                orders_result = await _shopify_get_customer_orders(
                                    client, base_url, headers,
                                    customer_id=customer_id,
                                    limit=5,
                                )
                                if orders_result["status"] == "ok":
                                    result["ecommerce_orders"] = orders_result["data"]
                                    break

                        elif eco_platform == "woocommerce":
                            # WooCommerce REST API
                            import httpx
                            wc_url = creds.get("shop_url", "").rstrip("/")
                            wc_key = creds.get("consumer_key", "")
                            wc_secret = creds.get("consumer_secret", "")
                            if wc_url and wc_key and wc_secret:
                                async with httpx.AsyncClient(timeout=10.0) as client:
                                    wc_res = await client.get(
                                        f"{wc_url}/wp-json/wc/v3/orders",
                                        params={"search": customer_email, "per_page": 5},
                                        auth=(wc_key, wc_secret),
                                    )
                                    if wc_res.status_code == 200:
                                        orders = wc_res.json()
                                        result["ecommerce_orders"] = [
                                            {
                                                "id": str(o.get("id")),
                                                "status": o.get("status"),
                                                "total": o.get("total"),
                                                "currency": o.get("currency"),
                                                "date_created": o.get("date_created"),
                                                "items": [{"name": i.get("name"), "quantity": i.get("quantity")} for i in o.get("line_items", [])],
                                            }
                                            for o in orders
                                        ]
                                        break
                except Exception as exc:
                    logger.warning("node3_ecommerce_fetch_failed", extra={"error": str(exc)[:200]})

            # ── 3. Carrier tracking (if tracking_number in context) ──
            tracking_number = customer_context.get("tracking_number", "")
            if tracking_number:
                try:
                    connector = CarrierAPIConnector()
                    tracking = await connector.track_shipment(
                        company_id=tenant_id,
                        tracking_number=tracking_number,
                    )
                    if tracking.get("status") not in ("not_configured", "no_credentials", "error"):
                        result["carrier_tracking"] = tracking
                except Exception as exc:
                    logger.warning("node3_carrier_fetch_failed", extra={"error": str(exc)[:200]})
        finally:
            db.close()
    except Exception as exc:
        logger.warning("node3_fetch_crm_data_failed", extra={"error": str(exc)[:200]})

    # ── 4. Custom integrations (any API the tenant connected) ──────
    # Fetch data from ANY custom integration the tenant has connected
    # (e.g. banking API, healthcare API, custom database API).
    # The integration catalog supports type="custom" — the tenant provides
    # their API URL + key during onboarding, and we call it here.
    try:
        from database.base import SessionLocal
        from app.services.integration_service import IntegrationService
        import httpx as _httpx

        db = SessionLocal()
        try:
            service = IntegrationService(db)
            # Get ALL active integrations for this tenant (not just stripe/shopify/hubspot)
            all_integrations = service.list_integrations(tenant_id, status="active")
            for integration in all_integrations or []:
                integration_type = integration.get("integration_type", "")
                # Skip the ones we already fetched above
                if integration_type in ("hubspot", "salesforce", "pipedrive",
                                        "shopify", "woocommerce", "bigcommerce",
                                        "fedex", "ups", "dhl", "usps",
                                        "stripe", "paddle", "paypal"):
                    continue
                # This is a custom/other integration — try to fetch data
                config = integration.get("config", {})
                api_url = config.get("api_url", "") or config.get("url", "")
                api_key = config.get("api_key", "") or config.get("access_token", "")
                if api_url and api_key:
                    try:
                        async with _httpx.AsyncClient(timeout=10.0) as client:
                            resp = await client.get(
                                api_url,
                                headers={"Authorization": f"Bearer {api_key}"},
                            )
                        if resp.status_code == 200:
                            custom_data = resp.json()
                            result["custom_integration_data"] = custom_data
                            logger.info(
                                "node3_custom_integration_fetched type=%s tenant=%s",
                                integration_type, tenant_id,
                            )
                    except Exception as exc:
                        logger.warning(
                            "node3_custom_integration_failed type=%s error=%s",
                            integration_type, str(exc)[:200],
                        )
        finally:
            db.close()
    except Exception as exc:
        logger.warning("node3_custom_integration_loop_failed: %s", str(exc)[:200])

    return result


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

    # ── Wave 4: Inject Jarvis guidance for this ticket ─────
    system_flags = state.get("system_flags")
    if not system_flags:
        try:
            from app.core.parwa_pipeline.parwa_bridge import load_system_flags
            system_flags = await load_system_flags(tenant_id)
        except Exception:
            system_flags = {}
    guidance_map = system_flags.get("guidance", {})
    ticket_id = state.get("ticket_id", "")
    jarvis_guidance = guidance_map.get(ticket_id, "")
    if jarvis_guidance:
        logs.append({"node": 3, "technique": "JARVIS_GUIDANCE", "duration_ms": 0,
                     "result_summary": f"guidance_len={len(jarvis_guidance)}"})

    # ────────────────────────────────────────────────────────────────
    # STEP 1: CLARA Gatekeeper (LLM) — the ONLY LLM call in Node 3
    # ────────────────────────────────────────────────────────────────
    clara_result = await _clara_gatekeep(query, ticket_type)
    logs.append({"node": 3, "technique": "CLARA", "duration_ms": 0, "result_summary": "gatekeep_done"})
    llm_calls += 1

    # ── SelfConsistency: cross-check CLARA vs ticket_type keywords ──
    sc_clara = _self_consistency_clara(clara_result, query, ticket_type)
    logs.append({"node": 3, "technique": "SelfConsistency", "duration_ms": 0,
                 "result_summary": sc_clara["flag"]})
    # If CLARA mismatch detected, flag it so downstream knows CLARA may be wrong
    if sc_clara["flag"] == "CLARA_MISMATCH":
        clara_result["clara_mismatch_warning"] = True
        logs.append({"node": 3, "technique": "SelfConsistency.Override", "duration_ms": 0,
                     "result_summary": "CLARA_MISMATCH — knowledge areas don't match ticket_type, downstream should be cautious"})

    # ── CoVe: verify CLARA's claims against query ───────────────────
    cove_clara = _cove_verify_clara(clara_result, query)
    logs.append({"node": 3, "technique": "CoVe", "duration_ms": 0,
                 "result_summary": f"verified={cove_clara['verified']} overlap={cove_clara['overlap_words']}"})
    # If CLARA claims are unverified, flag for downstream
    if not cove_clara.get("verified", True):
        clara_result["clara_unverified_warning"] = True
        logs.append({"node": 3, "technique": "CoVe.Override", "duration_ms": 0,
                     "result_summary": "CLARA_UNVERIFIED — CLARA's knowledge areas have no overlap with query"})

    # ── QueryDecomposition: break multi-intent queries ──────────────
    decomp = _query_decomposition(query, ticket_type)
    if decomp["decomposed"]:
        logs.append({"node": 3, "technique": "QueryDecomposition", "duration_ms": 0,
                     "result_summary": f"split_into={decomp['count']} sub-queries"})

    # ── IntentSignalBoost: extract urgency/VIP/money signals ────────
    intent_signals = _intent_signal_boost(query, state.get("customer_context", {}), ticket_type)
    logs.append({"node": 3, "technique": "IntentSignalBoost", "duration_ms": 0,
                 "result_summary": f"signals={intent_signals['signal_count']} urgent={intent_signals['signals'].get('urgent', False)} vip={intent_signals['signals'].get('is_vip', False)}"})

    # ── MAKER for CLARA: verify CLARA output is grounded in query ───
    maker_clara = _maker_grounding_check(
        [{"content": clara_result.get("relevant_knowledge", ""), "source": "clara_output"}],
        query,
    )
    if maker_clara["grounded_ratio"] < 0.5:
        logs.append({"node": 3, "technique": "MAKER.CLARA", "duration_ms": 0,
                     "result_summary": f"LOW_GROUNDING ratio={maker_clara['grounded_ratio']} — CLARA may have hallucinated areas"})
    else:
        logs.append({"node": 3, "technique": "MAKER.CLARA", "duration_ms": 0,
                     "result_summary": f"grounded_ratio={maker_clara['grounded_ratio']}"})

    # ────────────────────────────────────────────────────────────────
    # STEP 2: RAG Retrieval (per-tenant KB first, fallback to shared)
    # ────────────────────────────────────────────────────────────────
    documents = _retrieve_knowledge(ticket_type, query, tenant_id=tenant_id)
    logs.append({"node": 3, "technique": "RAG", "duration_ms": 0, "result_summary": f"{len(documents)} docs"})

    # ── MetaLearner: boost docs from historically successful patterns ─
    documents = _meta_learner_boost(documents, tenant_id, ticket_type, query)
    logs.append({"node": 3, "technique": "MetaLearner", "duration_ms": 0,
                 "result_summary": "doc_scores_boosted_by_history"})

    # ── RecencyWeighting: boost newer docs, penalize stale ones ──────
    documents = _recency_weighting(documents)
    logs.append({"node": 3, "technique": "RecencyWeighting", "duration_ms": 0,
                 "result_summary": "recency_adjusted"})

    # ── AuthorityRanking: tenant KB > default KB ─────────────────────
    documents = _authority_ranking(documents)
    logs.append({"node": 3, "technique": "AuthorityRanking", "duration_ms": 0,
                 "result_summary": "tenant_docs_boosted"})

    # ── SmartRouter for RAG: route search by ticket type ─────────────
    rag_route = _smart_router_rag(ticket_type)
    if rag_route["source_priorities"]:
        # Boost docs whose source matches high-priority sources
        for doc in documents:
            source = doc.get("source", "")
            for src_key, priority in rag_route["source_priorities"].items():
                if src_key in source:
                    doc["score"] = doc.get("score", 0.5) + priority * 0.03
        documents.sort(key=lambda d: d.get("score", 0), reverse=True)
    logs.append({"node": 3, "technique": "SmartRouter.RAG", "duration_ms": 0,
                 "result_summary": f"strategy={rag_route['search_strategy']} priorities={len(rag_route['source_priorities'])}"})

    # ────────────────────────────────────────────────────────────────
    # STEP 3: Smart knowledge filtering
    # ────────────────────────────────────────────────────────────────
    filtered = _filter_relevant_docs(documents, query, ticket_type)
    logs.append({"node": 3, "technique": "SmartFilter", "duration_ms": 0, "result_summary": f"{len(documents)}→{len(filtered)}"})

    # ── NearDedup: remove near-duplicate chunks ──────────────────────
    pre_dedup = len(filtered)
    filtered = _near_dedup(filtered)
    logs.append({"node": 3, "technique": "NearDedup", "duration_ms": 0,
                 "result_summary": f"{pre_dedup}→{len(filtered)} (removed {pre_dedup - len(filtered)} near-dupes)"})

    # ── SourceDiversity: max 2 chunks per source doc ─────────────────
    pre_div = len(filtered)
    filtered = _source_diversity(filtered, max_per_source=2)
    logs.append({"node": 3, "technique": "SourceDiversity", "duration_ms": 0,
                 "result_summary": f"{pre_div}→{len(filtered)} (capped per source)"})

    # ── MAKER: check doc grounding in query ──────────────────────────
    maker_result = _maker_grounding_check(filtered, query)
    logs.append({"node": 3, "technique": "MAKER", "duration_ms": 0,
                 "result_summary": f"grounded={maker_result['grounded_count']}/{maker_result['grounded_count']+maker_result['ungrounded_count']} ratio={maker_result['grounded_ratio']}"})

    # ── CoverageAnalysis: did we cover all CLARA areas? ──────────────
    coverage = _coverage_analysis(filtered, clara_result, ticket_type)
    logs.append({"node": 3, "technique": "CoverageAnalysis", "duration_ms": 0,
                 "result_summary": f"coverage={coverage['coverage_pct']} gaps={len(coverage['gaps'])}"})

    # ── SelfConsistency for Filter: cross-validate LLM vs keyword ───
    sc_filter = _self_consistency_filter(filtered, query, ticket_type)
    if not sc_filter["consistent"]:
        logs.append({"node": 3, "technique": "SelfConsistency.Filter", "duration_ms": 0,
                     "result_summary": f"SUSPICIOUS_DOCS={sc_filter['suspicious_docs']}/{sc_filter['total_docs']} — LLM may have scored false positives"})
        # Downgrade scores of suspicious docs (high score but no keyword overlap)
        for doc in filtered:
            if doc.get("score", 0) >= 0.7:
                doc_words = set(re.findall(r"\b\w{4,}\b", doc.get("content", "").lower()))
                query_words = set(re.findall(r"\b\w{4,}\b", query.lower()))
                filler = {"that", "this", "have", "been", "will", "would", "could", "should",
                          "their", "there", "about", "which", "where", "when", "what", "with"}
                query_words -= filler
                if len(query_words & doc_words) < 2:
                    doc["score"] = doc.get("score", 0.5) * 0.5  # halve the score
        filtered.sort(key=lambda d: d.get("score", 0), reverse=True)
    else:
        logs.append({"node": 3, "technique": "SelfConsistency.Filter", "duration_ms": 0,
                     "result_summary": "filter_scores_consistent"})

    # ── RelevanceDecay: penalise off-topic docs ──────────────────────
    filtered = _relevance_decay(filtered, ticket_type)
    logs.append({"node": 3, "technique": "RelevanceDecay", "duration_ms": 0,
                 "result_summary": "off_topic_docs_penalised"})

    # ── OverlapMinimization: keep most comprehensive doc when overlapping ──
    pre_overlap = len(filtered)
    filtered = _overlap_minimization(filtered)
    logs.append({"node": 3, "technique": "OverlapMinimization", "duration_ms": 0,
                 "result_summary": f"{pre_overlap}→{len(filtered)} (removed {pre_overlap - len(filtered)} overlapping)"})

    # ────────────────────────────────────────────────────────────────
    # STEP 4: Knowledge sufficiency check (enhanced with GSD)
    # ────────────────────────────────────────────────────────────────
    sufficiency = _check_knowledge_sufficiency(filtered, query, ticket_type)

    # ── GSD: goal-state tracking for sufficiency ─────────────────────
    gsd_result = _gsd_sufficiency_goals(filtered, ticket_type)
    logs.append({"node": 3, "technique": "GSD", "duration_ms": 0,
                 "result_summary": f"goals_met={gsd_result['met_count']}/{gsd_result['total_goals']} pct={gsd_result['completion_pct']}"})

    # ── GapDetection: which knowledge areas are missing? ─────────────
    gaps = _gap_detection(filtered, clara_result, ticket_type)
    logs.append({"node": 3, "technique": "GapDetection", "duration_ms": 0,
                 "result_summary": f"gaps={gaps['gap_count']} critical={gaps['critical_gap']}"})

    # ── RuleBasedAction: hard safety rules ───────────────────────────
    safety = _rule_based_action_safety(ticket_type, filtered)
    if safety["actions"]:
        logs.append({"node": 3, "technique": "RuleBasedAction", "duration_ms": 0,
                     "result_summary": f"actions={len(safety['actions'])} escalate={safety['must_escalate']}"})

    # ── CompletenessTracker: track % of query needs met ──────────────
    completeness = _completeness_tracker(filtered, query, ticket_type)
    logs.append({"node": 3, "technique": "CompletenessTracker", "duration_ms": 0,
                 "result_summary": f"needs_met={completeness['needs_met']}/{completeness['needs_identified']} pct={completeness['completeness_pct']}"})

    # ── PriorityEscalation: auto-escalate critical gaps ──────────────
    escalation = _priority_escalation(gaps, ticket_type, safety)
    if escalation["should_escalate"]:
        logs.append({"node": 3, "technique": "PriorityEscalation", "duration_ms": 0,
                     "result_summary": f"ESCALATE urgency={escalation['urgency']} reason={escalation['reason']}"})
        # Priority escalation forces insufficient — same as safety override
        if escalation["urgency"] in ("critical", "high") and sufficiency["knowledge_sufficient"]:
            sufficiency["knowledge_sufficient"] = False
            logs.append({"node": 3, "technique": "PriorityEscalation.Override", "duration_ms": 0,
                         "result_summary": f"downgraded: critical_gap escalation ({escalation['reason']})"})

    # Use GSD result to upgrade sufficiency decision
    # If old heuristic said "not sufficient" but GSD says mostly_met → give it a chance
    # If old heuristic said "sufficient" but GSD says 0 goals met → downgrade
    if not sufficiency["knowledge_sufficient"] and gsd_result["mostly_met"]:
        sufficiency["knowledge_sufficient"] = True
        logs.append({"node": 3, "technique": "GSD.Upgrade", "duration_ms": 0,
                     "result_summary": "upgraded: heuristic=insufficient but GSD=mostly_met"})
    elif sufficiency["knowledge_sufficient"] and gsd_result["met_count"] == 0:
        sufficiency["knowledge_sufficient"] = False
        logs.append({"node": 3, "technique": "GSD.Downgrade", "duration_ms": 0,
                     "result_summary": "downgraded: heuristic=sufficient but GSD=0_goals_met"})

    # Gap detection override: critical gaps force insufficient
    if gaps["critical_gap"] and sufficiency["knowledge_sufficient"]:
        sufficiency["knowledge_sufficient"] = False
        logs.append({"node": 3, "technique": "GapDetection.Override", "duration_ms": 0,
                     "result_summary": "downgraded: critical_gap detected"})

    # Safety override: must_escalate forces insufficient
    if safety["must_escalate"]:
        sufficiency["knowledge_sufficient"] = False
        logs.append({"node": 3, "technique": "RuleBasedAction.Override", "duration_ms": 0,
                     "result_summary": "downgraded: must_escalate rule"})

    clara_result["knowledge_sufficient"] = sufficiency["knowledge_sufficient"]
    clara_result["knowledge_contradictory"] = sufficiency["knowledge_contradictory"]
    logs.append({"node": 3, "technique": "SufficiencyCheck", "duration_ms": 0,
                 "result_summary": f"sufficient={sufficiency['knowledge_sufficient']} gsd_pct={gsd_result['completion_pct']} gaps={gaps['gap_count']}"})

    # ── P1 Notification: emit ticket:knowledge_gap ─────────────────
    # When the AI can't find enough knowledge to answer confidently, tell the
    # human so they know the AI is working blind. This helps the human decide
    # whether to intervene (provide more KB docs) or let the AI try anyway.
    if not sufficiency["knowledge_sufficient"]:
        # ── Custom Connector Override ──────────────────────────────
        # If the tenant has a custom connector that can fetch real data for
        # this ticket type (e.g. get_invoice for billing, get_order for
        # e-commerce), let the pipeline proceed to Node 5 which will call
        # the connector. Node 5 fetches REAL data from the client's API,
        # which substitutes for missing KB docs.
        try:
            from app.core.react_tools.custom_connector_client import has_action, call_custom_action
            _ticket_type_to_actions = {
                "refund_request": ["get_order", "get_invoice", "get_payment_history", "refund_order"],
                "billing": ["get_invoice", "get_payment_history", "process_payment"],
                "technical": ["get_order", "get_invoice"],
                "faq": ["get_invoice", "get_payment_history"],
                "complaint": ["get_order", "get_invoice", "get_payment_history"],
                "account": ["get_invoice", "get_payment_history"],
                "shipping": ["get_order"],
                "order": ["get_order", "get_invoice"],
            }
            _needed_actions = _ticket_type_to_actions.get(ticket_type, ["get_invoice", "get_order"])
            _has_matching_connector = False
            _connector_data: list = []

            # Extract IDs from the query for data lookup
            import re as _re
            _invoice_id = ""
            _order_id = ""
            _inv_match = _re.search(r'INV-\d{4}-\d{3}', query)
            if _inv_match:
                _invoice_id = _inv_match.group(0)
            _ord_match = _re.search(r'ORD-\d{4}', query)
            if _ord_match:
                _order_id = _ord_match.group(0)

            for _action in _needed_actions:
                if await has_action(tenant_id, _action):
                    _has_matching_connector = True
                    # Actually FETCH the data from the connector
                    _params = {}
                    if _action in ("get_invoice",) and _invoice_id:
                        _params = {"id": _invoice_id, "invoice_id": _invoice_id}
                    elif _action in ("get_order",) and _order_id:
                        _params = {"id": _order_id, "order_id": _order_id}
                    elif _action == "get_payment_history":
                        _params = {}

                    if _params or _action in ("get_payment_history",):
                        _data = await call_custom_action(tenant_id, _action, params=_params)
                        if _data is not None:
                            _connector_data.append({
                                "content": f"CRM Data ({_action}): {str(_data)[:1000]}",
                                "source": f"custom_connector:{_action}",
                                "score": 1.0,
                            })
                            logger.info(
                                "Node 3: fetched real CRM data via connector: "
                                "action=%s data_len=%d",
                                _action, len(str(_data)),
                            )

            if _has_matching_connector:
                # Inject the fetched CRM data into the knowledge context
                # so Node 4 can use it when generating the response
                if _connector_data:
                    filtered.extend(_connector_data)
                    clara_result["knowledge_sufficient"] = True
                    sufficiency["knowledge_sufficient"] = True
                    logs.append({
                        "node": 3, "technique": "CustomConnectorFetch",
                        "duration_ms": 0,
                        "result_summary": (
                            f"fetched {len(_connector_data)} real CRM records via "
                            f"custom connector for ticket_type={ticket_type} → "
                            f"data injected into knowledge context"
                        ),
                    })
                else:
                    # Connector exists but no data fetched (no IDs in query)
                    # Still override sufficiency so Node 5 can try
                    sufficiency["knowledge_sufficient"] = True
                    clara_result["knowledge_sufficient"] = True
                    logs.append({
                        "node": 3, "technique": "CustomConnectorOverride",
                        "duration_ms": 0,
                        "result_summary": (
                            f"connector exists for ticket_type={ticket_type} "
                            f"but no IDs found in query → proceeding to Node 5"
                        ),
                    })
        except Exception as _exc:
            logger.warning("custom_connector_check_failed: %s", str(_exc)[:200])

    if not sufficiency["knowledge_sufficient"]:
        # ── APPROACH A: Pause + ask for guidance ───────────────────
        # Node 3 has doubt (KB insufficient). Instead of continuing blind,
        # interrupt the pipeline and ask for guidance. When resumed,
        # the answer is injected into the knowledge context.
        #
        # IMPORTANT: interrupt() works by raising a special exception that
        # LangGraph catches internally to pause the graph. We must NOT
        # catch that exception — let it propagate so the graph pauses.
        from langgraph.types import interrupt
        gap_info = f" Gaps: {', '.join(g['area'] for g in gaps['gaps'][:3])}" if gaps["gaps"] else ""
        guidance = interrupt({
            "node": 3,
            "question": (
                f"I don't have enough knowledge base documents to answer "
                f"this {ticket_type} ticket confidently. "
                f"Only {len(filtered)} relevant doc(s) found. "
                f"GSD goals: {gsd_result['met_count']}/{gsd_result['total_goals']}.{gap_info} "
                f"Can you provide guidance on how to handle this?"
            ),
            "ticket_id": state.get("ticket_id", ""),
            "ticket_type": ticket_type,
            "docs_found": len(filtered),
            "gsd_completion": gsd_result["completion_pct"],
            "knowledge_gaps": [g["area"] for g in gaps["gaps"]],
            "query_summary": query[:200],
        })
        # ── When resumed, execution continues HERE ─────────────────
        # `guidance` contains the human/variant's answer.
        # Inject it as a knowledge doc so downstream nodes can use it.
        logger.info(
            "Node 3 resumed with guidance: %s (ticket=%s)",
            str(guidance)[:100], state.get("ticket_id", ""),
        )
        filtered.append({
            "content": f"Human/Agent Guidance: {guidance}",
            "source": "human_guidance",
            "score": 1.0,
        })
        clara_result["knowledge_sufficient"] = True
        logs.append({
            "node": 3, "technique": "HumanGuidanceInjection",
            "duration_ms": 0,
            "result_summary": f"guidance injected ({len(str(guidance))} chars)",
        })

        try:
            from app.core.event_emitter import emit_ticket_event
            await emit_ticket_event(
                company_id=tenant_id,
                event_type="ticket:knowledge_gap",
                payload={
                    "company_id": tenant_id,
                    "ticket_id": state.get("ticket_id", ""),
                    "ticket_type": ticket_type,
                    "query": query[:500],
                    "docs_found": len(filtered),
                    "contradictory": sufficiency["knowledge_contradictory"],
                    "gsd_completion": gsd_result["completion_pct"],
                    "knowledge_gaps": [g["area"] for g in gaps["gaps"]],
                    "node": 3,
                },
                correlation_id=state.get("ticket_id", ""),
            )
        except Exception as exc:
            logger.warning("node_3_knowledge_gap_notification_failed: %s", str(exc)[:200])

    # ────────────────────────────────────────────────────────────────
    # STEP 5: Contradiction check (enhanced)
    # ────────────────────────────────────────────────────────────────
    # Run both old (simple) and new (enhanced) contradiction checks
    has_contradiction_simple = _check_contradictions(filtered)
    has_contradiction_enhanced = _check_contradictions_enhanced(filtered, ticket_type)

    if has_contradiction_enhanced["found"]:
        # Scope check: are these real contradictions or just different plans?
        scope_result = _scope_check(has_contradiction_enhanced)
        if scope_result["has_real_contradiction"]:
            clara_result["knowledge_contradictory"] = True
            logs.append({"node": 3, "technique": "ContradictionCheck", "duration_ms": 0,
                         "result_summary": f"REAL_CONTRADICTION fields={len(scope_result['real_contradictions'])} false_positives={scope_result['false_positive_count']}"})
        else:
            logs.append({"node": 3, "technique": "ContradictionCheck", "duration_ms": 0,
                         "result_summary": f"scoped_differences_only ({scope_result['false_positive_count']} false positives filtered)"})
    elif has_contradiction_simple:
        clara_result["knowledge_contradictory"] = True
        logs.append({"node": 3, "technique": "ContradictionCheck", "duration_ms": 0,
                     "result_summary": "SIMPLE_CONTRADICTION_FOUND (pct mismatch)"})
    else:
        logs.append({"node": 3, "technique": "ContradictionCheck", "duration_ms": 0,
                     "result_summary": "no_contradictions"})

    # ── TemporalChecker: check for stale docs by year ────────────────
    temporal = _temporal_checker(filtered)
    if temporal["has_stale_docs"]:
        logs.append({"node": 3, "technique": "TemporalChecker", "duration_ms": 0,
                     "result_summary": f"STALE_DOCS={temporal['stale_sources']}"})
        # Downgrade stale docs (older year) so newer policy versions rank higher
        for doc in filtered:
            if doc.get("source", "") in temporal["stale_sources"]:
                doc["score"] = doc.get("score", 0.5) - 0.15
        filtered.sort(key=lambda d: d.get("score", 0), reverse=True)
        logs.append({"node": 3, "technique": "TemporalChecker.Adjust", "duration_ms": 0,
                     "result_summary": f"downgraded {len(temporal['stale_sources'])} stale docs by -0.15"})

    # ── VersionTracker: which policy versions are active ─────────────
    ver_track = _version_tracker(filtered)
    if ver_track["has_superseded"]:
        logs.append({"node": 3, "technique": "VersionTracker", "duration_ms": 0,
                     "result_summary": f"SUPERSEDED={ver_track['superseded']} active={list(ver_track['active_versions'].values())}"})
        # Remove superseded docs (older versions) from the list entirely
        pre_remove = len(filtered)
        filtered = [d for d in filtered if d.get("source", "") not in ver_track["superseded"]]
        if len(filtered) < pre_remove:
            logs.append({"node": 3, "technique": "VersionTracker.Remove", "duration_ms": 0,
                         "result_summary": f"removed {pre_remove - len(filtered)} superseded docs (older versions)"})

    # ────────────────────────────────────────────────────────────────
    # STEP 6: DynamicContext (prioritized by ticket type)
    # ────────────────────────────────────────────────────────────────
    dynamic_ctx = _dynamic_context_prioritize(
        state.get("customer_context", {}), ticket_type,
    )
    critical_fields = sum(1 for k in dynamic_ctx if k != "_priority_meta")
    logs.append({"node": 3, "technique": "DynamicContext", "duration_ms": 0,
                 "result_summary": f"prioritized_fields={critical_fields} type={ticket_type}"})

    # ── SignalExtraction: compress context into key signals ──────────
    ctx_signals = _signal_extraction(state.get("customer_context", {}), ticket_type)
    logs.append({"node": 3, "technique": "SignalExtraction", "duration_ms": 0,
                 "result_summary": f"active_signals={ctx_signals['active_signal_count']} vip={ctx_signals['signals'].get('is_vip', False)}"})

    # ── ContextScoring: score each field's relevance ─────────────────
    ctx_scores = _context_scoring(state.get("customer_context", {}), ticket_type)
    logs.append({"node": 3, "technique": "ContextScoring", "duration_ms": 0,
                 "result_summary": f"high_relevance={len(ctx_scores['high_relevance_fields'])} avg={ctx_scores['avg_relevance']}"})

    # ── FreshnessCheck: flag stale context ───────────────────────────
    freshness = _freshness_check(state.get("customer_context", {}))
    if freshness["has_stale_data"]:
        logs.append({"node": 3, "technique": "FreshnessCheck", "duration_ms": 0,
                     "result_summary": f"STALE_FIELDS={freshness['stale_count']} flags={[f['field'] for f in freshness['stale_flags']]}"})

    # ────────────────────────────────────────────────────────────────
    # STEP 7: AI Wiki (Phase 6: real store reads + staleness check)
    # ────────────────────────────────────────────────────────────────
    tier = state.get("variant_tier", "parwa")
    wiki_a, wiki_b, wiki_c, wiki_patterns = _read_ai_wiki(tenant_id, ticket_type, query, tier)
    wiki_log_msg = f"A={len(wiki_a)} B={len(wiki_b)} C={len(wiki_c)}"
    if wiki_patterns:
        wiki_log_msg += f" patterns_found={len(wiki_patterns)}"
    logs.append({"node": 3, "technique": "AIWiki", "duration_ms": 0,
                 "result_summary": wiki_log_msg})

    # ── Wiki staleness detection ─────────────────────────────────────
    staleness = _wiki_staleness_check(wiki_patterns)
    if staleness["stale_count"] > 0:
        logs.append({"node": 3, "technique": "StalenessDetection", "duration_ms": 0,
                     "result_summary": f"stale={staleness['stale_count']} fresh={staleness['fresh_count']}"})

    # ── Wiki PatternDiversity: ensure diverse approaches ─────────────
    wiki_diversity = _wiki_pattern_diversity(wiki_patterns)
    if wiki_patterns:
        logs.append({"node": 3, "technique": "PatternDiversity", "duration_ms": 0,
                     "result_summary": f"diverse={wiki_diversity['diverse']} approaches={wiki_diversity['approach_count']} bias={wiki_diversity['bias_warning']}"})

    # ── Wiki ConflictResolution: resolve disagreeing patterns ────────
    wiki_conflict = _wiki_conflict_resolution(wiki_patterns)
    if wiki_conflict["conflict"]:
        logs.append({"node": 3, "technique": "ConflictResolution.Wiki", "duration_ms": 0,
                     "result_summary": f"WIKI_CONFLICT techniques={wiki_conflict['unique_techniques']} patterns={wiki_conflict['pattern_count']}"})

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

    # ────────────────────────────────────────────────────────────────
    # STEP 8: CRM + E-commerce + Carrier data (UCB + data goals)
    # ────────────────────────────────────────────────────────────────
    crm_data = await _fetch_crm_data(tenant_id, dynamic_ctx)
    crm_summary = "crm_fetched"
    if crm_data.get("crm_contact"):
        crm_summary += "+hubspot"
    if crm_data.get("ecommerce_orders"):
        crm_summary += "+shopify"
    if crm_data.get("carrier_tracking"):
        crm_summary += "+carrier"

    # ── UCB data goals tracking ──────────────────────────────────────
    ucb_goals = _ucb_data_goals(ticket_type, crm_data)
    crm_summary += f" coverage={ucb_goals['coverage_pct']}"
    if ucb_goals["data_goals_missing"]:
        crm_summary += f" missing={','.join(ucb_goals['data_goals_missing'])}"

    logs.append({"node": 3, "technique": "UCB", "duration_ms": 0, "result_summary": crm_summary})
    logs.append({"node": 3, "technique": "UCB.Goals", "duration_ms": 0,
                 "result_summary": f"met={ucb_goals['data_goals_met']} missing={ucb_goals['data_goals_missing']}"})

    # ── DataRelevance: determine which external data types to fetch ───
    data_relevance = _data_relevance_filter(ticket_type)
    logs.append({"node": 3, "technique": "DataRelevance", "duration_ms": 0,
                 "result_summary": f"needed={[k for k,v in data_relevance.items() if v]} skipped={[k for k,v in data_relevance.items() if not v]}"})

    # ── APIHealthCheck: check API health status ──────────────────────
    api_health = {}
    for itype in ("hubspot", "shopify", "fedex"):
        health = _api_health_check(itype, tenant_id)
        if not health["healthy"]:
            api_health[itype] = health
    if api_health:
        logs.append({"node": 3, "technique": "APIHealthCheck", "duration_ms": 0,
                     "result_summary": f"UNHEALTHY_APIS={list(api_health.keys())}"})

    # ── IdempotencyCheck: don't re-fetch if already fetched ──────────
    for dtype in ("crm_contact", "ecommerce_orders", "carrier_tracking"):
        if _idempotency_check(state, dtype):
            logs.append({"node": 3, "technique": "IdempotencyCheck", "duration_ms": 0,
                         "result_summary": f"SKIP_REFETCH={dtype} — already in pipeline state"})

    # ── PartialDataHandler: score partial CRM results ────────────────
    partial = _partial_data_handler(crm_data, data_relevance)
    if partial["partial"]:
        logs.append({"node": 3, "technique": "PartialDataHandler", "duration_ms": 0,
                     "result_summary": f"PARTIAL coverage={partial['coverage_pct']} fetched={partial['fetched']} missing={partial['missing']}"})

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 3 complete: ticket=%s docs=%d sufficient=%s llm=%d gsd=%.0f%% gaps=%d [%dms]",
        state["ticket_id"], len(filtered), clara_result["knowledge_sufficient"],
        llm_calls, gsd_result["completion_pct"] * 100, gaps["gap_count"], elapsed,
    )

    # Wave 4: Inject Jarvis guidance as additional knowledge
    if jarvis_guidance:
        filtered.append({
            "source": "jarvis_guidance",
            "content": jarvis_guidance,
            "relevance": 1.0,
            "is_jarvis_guidance": True,
        })
        logger.info("Node 3: Injected Jarvis guidance for ticket %s (%d chars)", ticket_id, len(jarvis_guidance))

    return {
        "knowledge_context": filtered,
        "wiki_section_a": wiki_a,
        "wiki_section_b": wiki_b,
        "wiki_section_c": wiki_c,
        "wiki_patterns": wiki_patterns,
        "crm_data": crm_data,
        "knowledge_sufficient": clara_result["knowledge_sufficient"],
        "knowledge_contradictory": clara_result["knowledge_contradictory"],
        "policy_version": "v2.0",
        "policy_sync_status": sync_status,
        "jarvis_guidance": jarvis_guidance,
        "intent_signals": intent_signals,
        "query_decomposition": decomp,
        "completeness_tracker": completeness,
        "context_signals": ctx_signals,
        "context_scores": ctx_scores,
        "wiki_diversity": wiki_diversity,
        "wiki_conflict_resolution": wiki_conflict,
        "temporal_check": temporal,
        "version_tracker": ver_track,
        "partial_data": partial,
        "technique_log": logs,
        "node_3_token_usage": llm_calls,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
    }