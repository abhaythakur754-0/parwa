"""
Node 3: Knowledge Fetch + AI Wiki

Question: What do we KNOW about this problem?

Every ticket — simple or complex — goes through this node.
You cannot answer any ticket without evidence.

Techniques (in order):
  1. CLARA.gatekeep()           — relevant? enough? contradictory? (LLM)
  2. HyDE.generate()             — hypothetical answer as search query (LLM)
  3. MultiQuery.rewrite()        — 3 different phrasings (LLM)
  4. StepBack.zoom_out()         — broader principles (LLM)
  5. RAG retrieval               — from vector store
  6. ContextualCompression       — remove irrelevant paragraphs (non-LLM)
  7. DynamicContext.pull()       — conversation history (non-LLM)
  8. AI Wiki Section A/B/C read  — per client, isolated
  9. CRM data fetch via UCB      — customer data from connected tools

LLM calls: 3-4 (CLARA + HyDE + Multi-Query + Step-Back)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from app.core.parwa_pipeline.llm_client import llm_call
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_3")


# ── CLARA: Gatekeeper (LLM) ───────────────────────────────────────


async def _clara_gatekeep(query: str, ticket_type: str) -> Dict[str, Any]:
    """CLARA asks 3 questions:
    1. Is this knowledge RELEVANT to the ticket?
    2. Do we have ENOUGH knowledge to answer?
    3. Is this knowledge CONTRADICTORY?

    Returns dict with gate results.
    """
    prompt = f"""You are a knowledge quality gatekeeper (CLARA).

Ticket: "{query}"
Type: {ticket_type}

Answer these 3 questions with YES or NO:
1. RELEVANT: Based on the ticket type, what kind of knowledge is needed to answer this?
2. ENOUGH: What specific information is required?
3. GAPS: What information might be MISSING that would help answer better?

Format:
RELEVANT_KNOWLEDGE: <what knowledge areas are needed>
REQUIRED_INFO: <what specific info is needed>
POSSIBLE_GAPS: <what might be missing>"""

    result = await llm_call(prompt, max_tokens=300)

    return {
        "relevant_knowledge": result,
        "knowledge_sufficient": False,  # Will be updated after retrieval
        "knowledge_contradictory": False,
    }


# ── HyDE: Hypothetical Document Embedding (LLM) ──────────────────


async def _hyde_generate(query: str, ticket_type: str) -> str:
    """Generate a hypothetical answer to use as a better search query."""
    prompt = f"""Generate a hypothetical answer to this {ticket_type} support question.
The answer should be detailed and factual-sounding, as if from a knowledge base article.

Question: "{query}"

Hypothetical Answer:"""

    return await llm_call(prompt, max_tokens=200)


# ── Multi-Query: Rewrite question 3 ways (LLM) ───────────────────


async def _multi_query_rewrite(query: str) -> List[str]:
    """Rewrite the user's question in 3 different ways for better retrieval."""
    prompt = f"""Rewrite this customer support question in 3 different ways.
Each rewrite should capture the same intent but use different words/structure.

Original: "{query}"

Provide exactly 3 rewrites, one per line, numbered:"""

    result = await llm_call(prompt, max_tokens=200)
    queries = [line.strip() for line in result.split("\n") if line.strip() and line.strip()[0].isdigit()]
    return queries[:3] if queries else [query]


# ── Step-Back: Zoom out to broader principles (LLM) ───────────────


async def _step_back(query: str, ticket_type: str) -> str:
    """Step back to find broader principles related to the ticket."""
    prompt = f"""A customer asked: "{query}" (type: {ticket_type})

Instead of answering directly, what broader principles or policies are relevant?
Think about the general category this falls under and what rules typically apply.

Broader Principles:"""

    return await llm_call(prompt, max_tokens=200)


# ── ContextualCompression (non-LLM) ──────────────────────────────


def _compress_context(documents: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Remove paragraphs irrelevant to the query.
    Simple keyword-based compression for Phase 1."""
    query_words = set(query.lower().split())
    compressed = []

    for doc in documents:
        text = doc.get("content", "").lower()
        # Score relevance by keyword overlap
        doc_words = set(text.split())
        overlap = len(query_words & doc_words)
        if overlap > 0:
            compressed.append(doc)

    return compressed if compressed else documents


# ── Mock knowledge retrieval (replaced by real RAG in Phase 2) ─────

# For testing: returns mock knowledge based on ticket type
MOCK_KNOWLEDGE: Dict[str, List[Dict[str, str]]] = {
    "refund_request": [
        {
            "source": "refund_policy",
            "content": "Refund Policy: Customers on Pro plan are eligible for a full refund within 30 days of purchase. Customers on Free plan are not eligible for refunds. Refunds are processed to the original payment method within 5-7 business days. Partial refunds are available for unused portions of annual plans. All refund requests are reviewed and may require manager approval for amounts exceeding $500.",
            "section": "C",
        },
        {
            "source": "refund_process",
            "content": "Refund Process: 1) Verify customer identity and purchase details 2) Check refund eligibility based on plan and time 3) Calculate refund amount 4) Process through payment provider 5) Send confirmation email to customer. Refund status can be tracked in the customer portal.",
            "section": "C",
        },
    ],
    "billing": [
        {
            "source": "billing_policy",
            "content": "Billing Policy: Subscriptions are billed monthly or annually based on the selected plan. Upgrades take effect immediately with prorated charges. Downgrades take effect at the end of the current billing cycle. Failed payment attempts result in a 7-day grace period before account suspension. Invoices are generated on the 1st of each month and sent to the billing email on file.",
            "section": "C",
        },
    ],
    "technical": [
        {
            "source": "tech_faq",
            "content": "Common Technical Issues: If you cannot log in, try resetting your password via the 'Forgot Password' link. If the app is not loading, clear your browser cache and cookies. API errors (404, 500) should be reported to the technical team with the error code and timestamp. WebSocket connections require a stable internet connection.",
            "section": "C",
        },
    ],
    "faq": [
        {
            "source": "general_faq",
            "content": "General FAQ: PARWA is an AI-powered customer support platform. We offer three plans: Mini ($999/mo), PARWA ($2,499/mo), and High ($4,999/mo). All plans include 24/7 AI support resolution. The platform integrates with email, SMS, chat, CRM, and helpdesk tools. Onboarding takes approximately 30 minutes.",
            "section": "C",
        },
    ],
    "complaint": [
        {
            "source": "complaint_handling",
            "content": "Complaint Handling: All complaints are taken seriously. Priority customers (Pro plan, 1+ year tenure) receive expedited resolution. Complaints about billing are forwarded to the finance team. Service quality complaints trigger a review of the interaction. Compensation may be offered at the discretion of the support agent within tier limits. All complaints are logged for quality improvement.",
            "section": "C",
        },
    ],
    "account_change": [
        {
            "source": "account_policy",
            "content": "Account Change Policy: Email changes require verification of both old and new email addresses. Password changes invalidate all active sessions. Plan upgrades are immediate with prorated billing. Plan downgrades take effect at next billing cycle. Account deletion is permanent and requires confirmation. Data export is available before deletion.",
            "section": "C",
        },
    ],
}


# ── Main Node Function ────────────────────────────────────────────


async def node_3_knowledge_fetch(state: PipelineV2State) -> dict:
    """Node 3: Knowledge Fetch — What do we KNOW?

    Runs: CLARA → HyDE → Multi-Query → Step-Back → RAG → Compress → Wiki → UCB
    """
    start = time.time()
    query = state["query"]
    tenant_id = state["tenant_id"]
    ticket_type = state["ticket_type"]
    logs = []
    llm_calls = 0

    # 1. CLARA: Gatekeeper — what knowledge is needed? (LLM)
    clara_result = await _clara_gatekeep(query, ticket_type)
    logs.append({"node": 3, "technique": "CLARA", "duration_ms": 0, "result_summary": "gatekeep_done"})
    llm_calls += 1

    # 2. HyDE: Generate hypothetical answer as search query (LLM)
    hypothetical = await _hyde_generate(query, ticket_type)
    logs.append({"node": 3, "technique": "HyDE", "duration_ms": 0, "result_summary": "hypothetical_generated"})
    llm_calls += 1

    # 3. Multi-Query: Rewrite question 3 ways (LLM)
    rewrites = await _multi_query_rewrite(query)
    logs.append({"node": 3, "technique": "MultiQuery", "duration_ms": 0, "result_summary": f"{len(rewrites)} rewrites"})
    llm_calls += 1

    # 4. Step-Back: Broader principles (LLM)
    broader = await _step_back(query, ticket_type)
    logs.append({"node": 3, "technique": "StepBack", "duration_ms": 0, "result_summary": "broader_principles"})
    llm_calls += 1

    # 5. RAG Retrieval — search with all queries
    all_queries = [query, hypothetical] + rewrites + [broader]
    documents = _retrieve_knowledge(all_queries, ticket_type, tenant_id)
    logs.append({"node": 3, "technique": "RAG", "duration_ms": 0, "result_summary": f"{len(documents)} docs"})

    # 6. CLARA: Re-evaluate — is knowledge sufficient now?
    clara_result["knowledge_sufficient"] = len(documents) >= 1
    clara_result["knowledge_contradictory"] = _check_contradictions(documents)
    logs.append({"node": 3, "technique": "CLARA.reevaluate", "duration_ms": 0, "result_summary": f"sufficient={clara_result['knowledge_sufficient']}"})

    # 7. ContextualCompression (non-LLM)
    compressed = _compress_context(documents, query)
    logs.append({"node": 3, "technique": "ContextualCompression", "duration_ms": 0, "result_summary": f"{len(documents)}→{len(compressed)}"})

    # 8. DynamicContext: conversation history (non-LLM)
    dynamic_ctx = state.get("customer_context", {})
    logs.append({"node": 3, "technique": "DynamicContext", "duration_ms": 0, "result_summary": "context_pulled"})

    # 9. AI Wiki reads (mock — wired in Phase 6)
    wiki_a, wiki_b, wiki_c = _read_ai_wiki(tenant_id, ticket_type)
    logs.append({"node": 3, "technique": "AIWiki", "duration_ms": 0, "result_summary": f"A={len(wiki_a)} B={len(wiki_b)} C={len(wiki_c)}"})

    # 10. CRM data fetch via UCB (mock — wired in Phase 7)
    crm_data = _fetch_crm_data(tenant_id, dynamic_ctx)
    logs.append({"node": 3, "technique": "UCB", "duration_ms": 0, "result_summary": "crm_fetched"})

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 3 complete: ticket=%s docs=%d llm_calls=%d [%dms]",
        state["ticket_id"], len(compressed), llm_calls, elapsed,
    )

    return {
        "knowledge_context": compressed,
        "wiki_section_a": wiki_a,
        "wiki_section_b": wiki_b,
        "wiki_section_c": wiki_c,
        "crm_data": crm_data,
        "knowledge_sufficient": clara_result["knowledge_sufficient"],
        "knowledge_contradictory": clara_result["knowledge_contradictory"],
        "policy_version": "v1.0",
        "technique_log": logs,
        "node_3_token_usage": llm_calls,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
    }


# ── Helpers ────────────────────────────────────────────────────────


def _retrieve_knowledge(
    queries: List[str], ticket_type: str, tenant_id: str
) -> List[Dict[str, Any]]:
    """Retrieve knowledge documents. Mock for Phase 1."""
    docs = MOCK_KNOWLEDGE.get(ticket_type, MOCK_KNOWLEDGE.get("faq", []))
    # In production: vector store search with tenant scoping
    return [{"content": d["content"], "source": d["source"], "section": d.get("section", "C")} for d in docs]


def _check_contradictions(documents: List[Dict[str, Any]]) -> bool:
    """Check for contradictory knowledge. Simple check for Phase 1."""
    if len(documents) < 2:
        return False
    # In production: LLM-based contradiction detection
    return False


def _read_ai_wiki(
    tenant_id: str, ticket_type: str
) -> tuple:
    """Read AI Wiki Sections A, B, C. Mock for Phase 6."""
    return [], [], []


def _fetch_crm_data(tenant_id: str, customer_context: Dict) -> Dict:
    """Fetch CRM data via UCB. Mock for Phase 7."""
    return {
        "subscription_status": customer_context.get("account_tier", "free"),
        "recent_interactions": customer_context.get("recent_ticket_count", 0),
    }