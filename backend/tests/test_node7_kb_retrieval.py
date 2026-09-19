"""
Node 7 KB retrieval — tests for the 2026-09-18 live bug:

A ticket solved in 17s on the fast path (Node 3 → 7) was SAFE but MISSED
the KB section "SUPPORT HOURS 24/7". Root cause: Node 7's non-LLM layers
(MAKER bridge → ThoT → compress) keep only the top-3 word-overlap
sentences, and the LLM synthesis prompt received ONLY that compressed
bullet list (turbo[:2000]) — the real KB chunks never reached the LLM.
If the customer's words didn't overlap a KB sentence, that sentence was
silently dropped before the reply was written.

Fix: _build_synthesis_knowledge() feeds the synthesis LLM the actual
retrieved KB docs (capped) plus cleaned matched highlights.

Run: cd backend && ../venv/bin/python -m pytest tests/test_node7_kb_retrieval.py -v
"""
from __future__ import annotations

import sys
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Pre-import: Stub out langgraph (same pattern as test_parwa_v2_unit) ──
if "langgraph" not in sys.modules:
    sys.modules["langgraph"] = MagicMock()
    sys.modules["langgraph.graph"] = MagicMock()
    sys.modules["langgraph.graph"].END = "__end__"
    sys.modules["langgraph.graph"].StateGraph = MagicMock

from app.core.parwa_pipeline.nodes.node_7_simple_resolver import (  # noqa: E402
    _build_synthesis_knowledge,
    node_7_simple_resolver,
)

KB_DOC = (
    "PARWA SUPPORT HOURS 24/7: Our support team never closes. "
    "Email and chat are answered around the clock, every day of the year. "
    "Average first reply time is under 5 minutes."
)

QUERY_WITHOUT_OVERLAP = "hey, if I write to you late at night on a Sunday, will someone get back to me?"


# ── 1. Helper unit tests ─────────────────────────────────────────────


def test_builder_includes_kb_doc_missing_from_highlights():
    """The regression: KB content that word-overlap extraction dropped
    must STILL reach the synthesis prompt."""
    # highlights deliberately contain nothing from the KB doc
    highlights = "- Information not available in knowledge base for: availability"
    block = _build_synthesis_knowledge(
        [{"content": KB_DOC, "source": "tenant_kb:doc-1"}], highlights
    )
    assert "SUPPORT HOURS 24/7" in block
    assert "never closes" in block


def test_builder_labels_kb_docs_and_highlights():
    docs = [
        {"content": "Refund window is 30 days.", "source": "tenant_kb:a"},
        {"content": "Refunds go to the original payment method.", "source": "tenant_kb:b"},
    ]
    block = _build_synthesis_knowledge(docs, "- Refund window is 30 days")
    assert "[KB 1]" in block and "[KB 2]" in block
    assert "Matched highlights:" in block


def test_builder_drops_not_available_junk():
    highlights = (
        "- Our support team never closes.\n"
        "- Information not available in knowledge base for: What is the pricing?\n"
        "- Refunds take 5 business days."
    )
    block = _build_synthesis_knowledge([], highlights)
    assert "not available" not in block.lower()
    assert "support team never closes" in block
    assert "Refunds take 5 business days" in block


def test_builder_caps_kb_budget():
    huge_doc = "x" * 10_000
    block = _build_synthesis_knowledge([{"content": huge_doc, "source": "s"}], "")
    # 4000 chars KB budget + separators/highlights must stay bounded
    assert len(block) <= 4200


def test_builder_empty_docs_keeps_highlights():
    highlights = "- Refund window is 30 days."
    block = _build_synthesis_knowledge([], highlights)
    assert "Refund window is 30 days." in block


def test_builder_skips_empty_doc_content():
    docs = [
        {"content": "", "source": "s1"},
        {"content": None, "source": "s2"},
        {"content": "Real content here.", "source": "s3"},
    ]
    block = _build_synthesis_knowledge(docs, "")
    assert "Real content here." in block
    assert "[KB 3]" in block  # numbering still reflects doc order


# ── 2. Node-level integration: prompt really gets the KB ────────────


@pytest.mark.asyncio
async def test_synthesis_prompt_contains_full_kb_doc():
    """End-to-end through node_7: the KB section the customer's words do
    NOT overlap must still appear in the LLM synthesis prompt."""
    state: Dict[str, Any] = {
        "ticket_id": "TKT-KB-RETRIEVAL-1",
        "tenant_id": "tenant_kb_test",
        "query": QUERY_WITHOUT_OVERLAP,
        "ticket_type": "faq",
        "required_action": "provide_info",
        "action_details": {},
        "variant_tier": "parwa",
        "customer_context": {"customer_name": "Alex"},
        "knowledge_context": [
            {"content": KB_DOC, "source": "tenant_kb:hours-doc"},
        ],
        "wiki_section_c": [],
    }

    with patch(
        "app.core.parwa_pipeline.llm_client.llm_call", new_callable=AsyncMock
    ) as mock_llm:
        mock_llm.return_value = (
            "Hi Alex! Yes — our support team is available 24/7, so someone "
            "will get back to you even late on a Sunday."
        )
        result = await node_7_simple_resolver(state)
        prompt = mock_llm.call_args[0][0]

    assert "SUPPORT HOURS 24/7" in prompt, (
        "the real KB doc must reach the synthesis prompt, "
        "not just the word-overlap highlights"
    )
    # and the LLM's synthesized answer is what the customer receives
    assert "available 24/7" in result["simple_answer"]


@pytest.mark.asyncio
async def test_synthesis_prompt_has_no_not_available_junk():
    state: Dict[str, Any] = {
        "ticket_id": "TKT-KB-RETRIEVAL-2",
        "tenant_id": "tenant_kb_test",
        "query": "what is your refund window?",
        "ticket_type": "refund_request",
        "required_action": "provide_info",
        "action_details": {},
        "variant_tier": "parwa",
        "customer_context": {"customer_name": "Sam"},
        "knowledge_context": [
            {"content": "Refunds are processed within 30 days of purchase.", "source": "tenant_kb:r"},
        ],
        "wiki_section_c": [],
    }

    with patch(
        "app.core.parwa_pipeline.llm_client.llm_call", new_callable=AsyncMock
    ) as mock_llm:
        mock_llm.return_value = "Hi Sam! Refunds are processed within 30 days of purchase."
        result = await node_7_simple_resolver(state)
        prompt = mock_llm.call_args[0][0]

    assert "not available" not in prompt.lower()
    assert "30 days" in prompt
    assert result["simple_answer"].startswith("Hi Sam!")


@pytest.mark.asyncio
async def test_fallback_to_raw_kb_when_llm_fails():
    """If the synthesis LLM call dies, the raw compressed KB (turbo) is
    still delivered — existing safety behaviour must not regress."""
    state: Dict[str, Any] = {
        "ticket_id": "TKT-KB-RETRIEVAL-3",
        "tenant_id": "tenant_kb_test",
        "query": "do you offer support on weekends?",
        "ticket_type": "faq",
        "required_action": "provide_info",
        "action_details": {},
        "variant_tier": "parwa",
        "customer_context": {"customer_name": "Rae"},
        "knowledge_context": [
            {"content": KB_DOC, "source": "tenant_kb:hours-doc"},
        ],
        "wiki_section_c": [],
    }

    with patch(
        "app.core.parwa_pipeline.llm_client.llm_call", new_callable=AsyncMock
    ) as mock_llm:
        mock_llm.side_effect = RuntimeError("provider down")
        result = await node_7_simple_resolver(state)

    assert result["simple_answer"], "fallback answer must not be empty"
    assert "24/7" in result["simple_answer"] or "SUPPORT" in result["simple_answer"].upper()
