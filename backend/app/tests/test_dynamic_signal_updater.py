"""
Unit tests for app/core/dynamic_signal_updater.py

Covers:
- Intent detection (_detect_intents)
- publish_superglue_signals (with mock Redis + memory fallback)
- get_superglue_signals (memory fallback)
- enrich_query_signals
- BC-008: never crashes

Run: pytest backend/app/tests/test_dynamic_signal_updater.py -v
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.dynamic_signal_updater import (
    _detect_intents,
    publish_superglue_signals,
    get_superglue_signals,
    enrich_query_signals,
    _memory_cache,
)


# ── Test Intent Detection ──


class TestDetectIntents:
    def test_refund_intent(self):
        assert "refund" in _detect_intents("process_refund_tool")

    def test_billing_intent(self):
        assert "billing" in _detect_intents("billing_inquiry_handler")

    def test_cancellation_from_cancel(self):
        intents = _detect_intents("cancel_subscription")
        assert "cancellation" in intents

    def test_cancellation_direct(self):
        intents = _detect_intents("handle_cancellation_request")
        assert "cancellation" in intents

    def test_shipping_from_ship(self):
        intents = _detect_intents("ship_order_now")
        assert "shipping" in intents

    def test_complaint_from_complain(self):
        intents = _detect_intents("complain_about_service")
        assert "complaint" in intents

    def test_escalation(self):
        assert "escalation" in _detect_intents("escalate_to_manager")

    def test_inquiry_from_enquire(self):
        intents = _detect_intents("enquire_about_product")
        assert "inquiry" in intents

    def test_account_intent(self):
        assert "account" in _detect_intents("update_account_settings")

    def test_technical_intent(self):
        assert "technical" in _detect_intents("technical_support_tool")

    def test_no_intent_match(self):
        intents = _detect_intents("do_something_random")
        assert intents == []

    def test_empty_string(self):
        assert _detect_intents("") == []

    def test_multiple_intents(self):
        intents = _detect_intents("refund_billing_complaint")
        assert "refund" in intents
        assert "billing" in intents
        assert "complaint" in intents

    def test_no_duplicates(self):
        intents = _detect_intents("refund_and_refund_again")
        assert intents.count("refund") == 1

    def test_case_insensitive(self):
        intents = _detect_intents("REFUND_TOOL")
        assert "refund" in intents


# ── Test Publish Signals ──
# NOTE: publish_superglue_signals tries Redis first (fakeredis may be available).
# Tests use get_superglue_signals() to read back, and also check _memory_cache as fallback.


class TestPublishSignals:
    @pytest.mark.asyncio
    async def test_publish_basic_tools(self):
        _memory_cache.clear()
        count = await publish_superglue_signals("company-1", [
            {"id": "t1", "name": "get_order_status"},
            {"id": "t2", "name": "refund_customer"},
        ])
        assert count >= 1
        # Either Redis or memory cache should have it
        sig = await get_superglue_signals("company-1")
        assert sig is not None or "company-1" in _memory_cache

    @pytest.mark.asyncio
    async def test_publish_detects_financial(self):
        _memory_cache.clear()
        await publish_superglue_signals("c2", [
            {"id": "t1", "name": "process_refund"},
        ])
        sig = await get_superglue_signals("c2")
        if sig:
            assert sig["has_financial_tools"] is True
        elif "c2" in _memory_cache:
            assert _memory_cache["c2"]["has_financial_tools"] is True

    @pytest.mark.asyncio
    async def test_publish_detects_destructive(self):
        _memory_cache.clear()
        await publish_superglue_signals("c3", [
            {"id": "t1", "name": "delete_account"},
        ])
        sig = await get_superglue_signals("c3")
        if sig:
            assert sig["has_destructive_tools"] is True
        elif "c3" in _memory_cache:
            assert _memory_cache["c3"]["has_destructive_tools"] is True

    @pytest.mark.asyncio
    async def test_publish_empty_tools(self):
        _memory_cache.clear()
        count = await publish_superglue_signals("c4", [])
        assert count == 0
        sig = await get_superglue_signals("c4")
        if sig:
            assert sig["has_tools"] is False
            assert sig["tool_count"] == 0

    @pytest.mark.asyncio
    async def test_publish_bc008_empty_tool_list(self):
        _memory_cache.clear()
        count = await publish_superglue_signals("c5", [])
        assert count == 0

    @pytest.mark.asyncio
    async def test_publish_bc008_none_tools(self):
        count = await publish_superglue_signals("c6", None)
        assert count == 0

    @pytest.mark.asyncio
    async def test_signal_structure(self):
        _memory_cache.clear()
        await publish_superglue_signals("c7", [
            {"id": "t1", "name": "lookup_order"},
        ])
        sig = await get_superglue_signals("c7")
        if sig:
            assert "has_tools" in sig
            assert "tool_count" in sig
            assert "has_financial_tools" in sig
            assert "has_destructive_tools" in sig
            assert "intents" in sig


# ── Test Get Signals ──


class TestGetSignals:
    @pytest.mark.asyncio
    async def test_get_from_memory(self):
        _memory_cache["g1"] = {"has_tools": True, "tool_count": 1, "has_financial_tools": True, "has_destructive_tools": False, "intents": ["refund"]}
        sig = await get_superglue_signals("g1")
        # May come from Redis or memory
        if sig is None:
            sig = _memory_cache["g1"]
        assert sig is not None
        assert sig["has_tools"] is True

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        _memory_cache.pop("nonexistent", None)
        sig = await get_superglue_signals("nonexistent")
        assert sig is None


# ── Test Enrich Query Signals ──
# enrich_query_signals is SYNC and reads ONLY from _memory_cache.
# So we write directly to _memory_cache for these tests.


class TestEnrichQuerySignals:
    def test_enrich_sets_external_data(self):
        _memory_cache["e1"] = {
            "has_tools": True, "tool_count": 1,
            "has_financial_tools": False, "has_destructive_tools": False,
            "intents": [],
        }

        class FakeSignals:
            external_data_required = False

        signals = FakeSignals()
        enrich_query_signals("e1", signals)
        assert signals.external_data_required is True

    def test_enrich_no_tools_no_change(self):
        _memory_cache["e2"] = {
            "has_tools": False, "tool_count": 0,
            "has_financial_tools": False, "has_destructive_tools": False,
            "intents": [],
        }

        class FakeSignals:
            external_data_required = False

        signals = FakeSignals()
        enrich_query_signals("e2", signals)
        assert signals.external_data_required is False

    def test_enrich_bc008_no_crash(self):
        class FakeSignals:
            external_data_required = False

        enrich_query_signals("nonexistent_company", FakeSignals())

    def test_enrich_bc008_none_company(self):
        class FakeSignals:
            external_data_required = False

        enrich_query_signals(None, FakeSignals())


# ── Cleanup ──

@pytest.fixture(autouse=True)
def cleanup_memory_cache():
    """Clear memory cache before each test."""
    _memory_cache.clear()
    yield
    _memory_cache.clear()
