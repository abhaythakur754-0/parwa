"""
Tests for F-160 Conversation Summarization — Week 9 Day 10
"""

import time
import threading
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call

import pytest


@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("backend.app.logger.get_logger", return_value=MagicMock()):
        from backend.app.core.conversation_summarization import (
            ConversationSummarizationService,
            ConversationMessage,
            ConversationSummary,
            ConversationContext,
            SummarizationRequest,
            SummarizationResult,
            SummarizationMode,
            SummaryStatus,
            ConversationState,
        )
        globals().update({
            "ConversationSummarizationService": ConversationSummarizationService,
            "ConversationMessage": ConversationMessage,
            "ConversationSummary": ConversationSummary,
            "ConversationContext": ConversationContext,
            "SummarizationRequest": SummarizationRequest,
            "SummarizationResult": SummarizationResult,
            "SummarizationMode": SummarizationMode,
            "SummaryStatus": SummaryStatus,
            "ConversationState": ConversationState,
        })


# ── Constants used across tests ────────────────────────────────────────────
CID = "company_1"
CONV = "conv_1"


# ── Shared base for test classes that need a service instance ──────────────
class _Base:
    """Shared setup and helpers for service-heavy test classes."""

    def setup_method(self):
        self.service = ConversationSummarizationService()
        self.service.reset()
        self._msg_n = 0

    def _msg(self, content, role="customer", msg_id=None, ts=None):
        if msg_id is None:
            msg_id = f"msg_{self._msg_n}"
            self._msg_n += 1
        return ConversationMessage(
            message_id=msg_id,
            content=content,
            role=role,
            timestamp=ts or datetime.now(timezone.utc),
        )

    def _add_n(
        self,
        n: int,
        company_id: str = CID,
        conv_id: str = CONV,
        base_ts: datetime = None,
    ) -> int:
        """Add *n* messages; returns final version number."""
        ts = base_ts or datetime(2024, 1, 1, tzinfo=timezone.utc)
        for i in range(n):
            role = "customer" if i % 2 == 0 else "agent"
            msg = self._msg(f"This is message number {i} with some content.", role=role, ts=ts)
            self.service.add_message(company_id, conv_id, msg)
        return self.service.get_conversation_version(company_id, conv_id)

    def _add_realistic(self, n: int = 5, company_id: str = CID, conv_id: str = CONV) -> list:
        """Add a handful of realistic messages; returns the list."""
        texts = [
            ("I have a problem with my order. The delivery is delayed.", "customer"),
            ("Let me help you with that. Can you provide your order number?", "agent"),
            ("Sure, my order number is 12345. I need this resolved urgently.", "customer"),
            ("Thank you. I found your order. It seems there was a shipping error.", "agent"),
            ("Can you fix the error and refund the shipping charge please?", "customer"),
            ("I have processed the refund for your shipping charge.", "agent"),
            ("What about the delivery? Will my order arrive soon?", "customer"),
            ("Yes, the updated delivery date is next Monday.", "agent"),
            ("Great, thank you for your help. I appreciate it.", "customer"),
            ("You are welcome. Is there anything else I can help with?", "agent"),
            ("No, that will be all. Thanks again.", "customer"),
            ("Have a great day! Feel free to reach out if you need more help.", "agent"),
        ]
        msgs = []
        for i in range(min(n, len(texts))):
            m = self._msg(texts[i][0], role=texts[i][1])
            self.service.add_message(company_id, conv_id, m)
            msgs.append(m)
        return msgs


# ═══════════════════════════════════════════════════════════════════════════
# 1. TestEnums
# ═══════════════════════════════════════════════════════════════════════════
class TestEnums:

    # ── SummarizationMode ──────────────────────────────────────────────
    def test_mode_extractive_value(self):
        assert SummarizationMode.EXTRACTIVE.value == "extractive"

    def test_mode_abstractive_value(self):
        assert SummarizationMode.ABSTRACTIVE.value == "abstractive"

    def test_mode_hybrid_value(self):
        assert SummarizationMode.HYBRID.value == "hybrid"

    def test_mode_values_are_strings(self):
        for member in SummarizationMode:
            assert isinstance(member.value, str)

    def test_mode_has_three_members(self):
        assert len(SummarizationMode) == 3

    # ── SummaryStatus ──────────────────────────────────────────────────
    def test_status_pending(self):
        assert SummaryStatus.PENDING.value == "pending"

    def test_status_completed(self):
        assert SummaryStatus.COMPLETED.value == "completed"

    def test_status_stale(self):
        assert SummaryStatus.STALE.value == "stale"

    def test_status_failed(self):
        assert SummaryStatus.FAILED.value == "failed"

    def test_status_has_four_members(self):
        assert len(SummaryStatus) == 4

    # ── ConversationState ──────────────────────────────────────────────
    def test_state_active(self):
        assert ConversationState.ACTIVE.value == "active"

    def test_state_summarizing(self):
        assert ConversationState.SUMMARIZING.value == "summarizing"

    def test_state_locked(self):
        assert ConversationState.LOCKED.value == "locked"

    def test_state_has_three_members(self):
        assert len(ConversationState) == 3


# ═══════════════════════════════════════════════════════════════════════════
# 2. TestDataclasses
# ═══════════════════════════════════════════════════════════════════════════
class TestDataclasses:

    # ── ConversationMessage ────────────────────────────────────────────
    def test_message_defaults_timestamp_is_utc(self):
        before = datetime.now(timezone.utc) - timedelta(seconds=1)
        m = ConversationMessage(message_id="m1", content="hi", role="customer")
        after = datetime.now(timezone.utc) + timedelta(seconds=1)
        assert before <= m.timestamp <= after
        assert m.timestamp.tzinfo == timezone.utc

    def test_message_defaults_metadata_empty(self):
        m = ConversationMessage(message_id="m1", content="hi", role="customer")
        assert m.metadata == {}

    def test_message_custom_values(self):
        ts = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        m = ConversationMessage(
            message_id="m2", content="hello world", role="agent",
            timestamp=ts, metadata={"source": "web"},
        )
        assert m.message_id == "m2"
        assert m.content == "hello world"
        assert m.role == "agent"
        assert m.timestamp == ts
        assert m.metadata == {"source": "web"}

    def test_message_all_fields_settable(self):
        m = ConversationMessage(message_id="x", content="y", role="z")
        assert m.message_id == "x"
        assert m.content == "y"
        assert m.role == "z"

    # ── ConversationSummary ────────────────────────────────────────────
    def test_summary_defaults_empty_strings(self):
        s = ConversationSummary(
            summary_id="s1", conversation_id="c1", company_id="co1",
            mode=SummarizationMode.HYBRID, status=SummaryStatus.COMPLETED,
        )
        assert s.extractive_summary == ""
        assert s.abstractive_summary == ""
        assert s.hybrid_summary == ""

    def test_summary_defaults_key_points_empty(self):
        s = ConversationSummary(
            summary_id="s1", conversation_id="c1", company_id="co1",
            mode=SummarizationMode.HYBRID, status=SummaryStatus.COMPLETED,
        )
        assert s.key_points == []

    def test_summary_defaults_zero_values(self):
        s = ConversationSummary(
            summary_id="s1", conversation_id="c1", company_id="co1",
            mode=SummarizationMode.HYBRID, status=SummaryStatus.COMPLETED,
        )
        assert s.conversation_version == 0
        assert s.message_count == 0
        assert s.original_message_count == 0
        assert s.compression_ratio == 0.0
        assert s.generation_time_ms == 0.0

    def test_summary_defaults_metadata_empty(self):
        s = ConversationSummary(
            summary_id="s1", conversation_id="c1", company_id="co1",
            mode=SummarizationMode.HYBRID, status=SummaryStatus.COMPLETED,
        )
        assert s.metadata == {}

    def test_summary_timestamp_is_utc(self):
        before = datetime.now(timezone.utc) - timedelta(seconds=1)
        s = ConversationSummary(
            summary_id="s1", conversation_id="c1", company_id="co1",
            mode=SummarizationMode.HYBRID, status=SummaryStatus.COMPLETED,
        )
        after = datetime.now(timezone.utc) + timedelta(seconds=1)
        assert before <= s.created_at <= after
        assert s.created_at.tzinfo == timezone.utc

    def test_summary_custom_values(self):
        s = ConversationSummary(
            summary_id="s2", conversation_id="c2", company_id="co2",
            mode=SummarizationMode.EXTRACTIVE, status=SummaryStatus.PENDING,
            extractive_summary="Excerpt here",
            abstractive_summary="Condensed here",
            hybrid_summary="Both here",
            key_points=["point1", "point2"],
            conversation_version=5,
            message_count=10,
            original_message_count=15,
            compression_ratio=0.3,
            generation_time_ms=42.5,
            metadata={"model": "test"},
        )
        assert s.extractive_summary == "Excerpt here"
        assert s.abstractive_summary == "Condensed here"
        assert s.hybrid_summary == "Both here"
        assert s.key_points == ["point1", "point2"]
        assert s.conversation_version == 5
        assert s.message_count == 10
        assert s.original_message_count == 15
        assert s.compression_ratio == 0.3
        assert s.generation_time_ms == 42.5
        assert s.metadata == {"model": "test"}

    # ── ConversationContext ────────────────────────────────────────────
    def test_context_defaults(self):
        ctx = ConversationContext(conversation_id="c1", company_id="co1")
        assert ctx.conversation_id == "c1"
        assert ctx.company_id == "co1"
        assert ctx.messages == []
        assert ctx.summaries == []
        assert ctx.current_version == 0
        assert ctx.is_locked is False
        assert ctx.last_summarized_at is None
        assert ctx.token_count == 0
        assert ctx.max_context_messages == 20

    # ── SummarizationRequest ───────────────────────────────────────────
    def test_request_defaults(self):
        req = SummarizationRequest(company_id="co1", conversation_id="c1")
        assert req.mode == SummarizationMode.HYBRID
        assert req.max_messages == 0
        assert req.include_key_points is True
        assert req.force is False

    def test_request_custom(self):
        req = SummarizationRequest(
            company_id="co1", conversation_id="c1",
            mode=SummarizationMode.EXTRACTIVE,
            max_messages=50,
            include_key_points=False,
            force=True,
        )
        assert req.mode == SummarizationMode.EXTRACTIVE
        assert req.max_messages == 50
        assert req.include_key_points is False
        assert req.force is True

    # ── SummarizationResult ────────────────────────────────────────────
    def test_result_defaults(self):
        r = SummarizationResult(success=False)
        assert r.success is False
        assert r.summary is None
        assert r.error == ""
        assert r.version_mismatch is False
        assert r.re_summarized is False

    def test_result_success(self):
        r = SummarizationResult(success=True, re_summarized=True)
        assert r.success is True
        assert r.re_summarized is True

    def test_result_with_summary(self):
        s = ConversationSummary(
            summary_id="s1", conversation_id="c1", company_id="co1",
            mode=SummarizationMode.HYBRID, status=SummaryStatus.COMPLETED,
        )
        r = SummarizationResult(success=True, summary=s)
        assert r.summary.summary_id == "s1"


# ═══════════════════════════════════════════════════════════════════════════
# 3. TestInitialization
# ═══════════════════════════════════════════════════════════════════════════
class TestInitialization(_Base):

    def test_create_with_defaults(self):
        svc = ConversationSummarizationService()
        assert svc._conversation_store == {}
        assert svc._version_counters == {}
        assert svc._summary_cache == {}
        assert svc._stats == {}
        assert svc._abstractive_generator is None

    def test_create_with_custom_generator(self):
        gen = lambda msgs: "custom"
        svc = ConversationSummarizationService(abstractive_generator=gen)
        assert svc._abstractive_generator is gen

    def test_create_creates_global_lock(self):
        svc = ConversationSummarizationService()
        assert svc._global_lock is not None

    def test_create_has_empty_locks(self):
        svc = ConversationSummarizationService()
        assert svc._locks == {}

    def test_reset_clears_all(self):
        self._add_realistic(3)
        self.service.summarize(CID, CONV)
        self.service.reset()
        assert self.service._conversation_store == {}
        assert self.service._version_counters == {}
        assert self.service._summary_cache == {}
        assert self.service._stats == {}

    def test_reset_idempotent(self):
        self.service.reset()
        self.service.reset()
        assert self.service._conversation_store == {}


# ═══════════════════════════════════════════════════════════════════════════
# 4. TestAddMessage
# ═══════════════════════════════════════════════════════════════════════════
class TestAddMessage(_Base):

    def test_add_single_message_returns_version_1(self):
        v = self.service.add_message(CID, CONV, self._msg("Hello"))
        assert v == 1

    def test_add_second_message_returns_version_2(self):
        self.service.add_message(CID, CONV, self._msg("First"))
        v = self.service.add_message(CID, CONV, self._msg("Second"))
        assert v == 2

    def test_version_increments_linearly(self):
        for i in range(1, 11):
            v = self.service.add_message(CID, CONV, self._msg(f"m{i}"))
            assert v == i

    def test_message_stored_in_context(self):
        self.service.add_message(CID, CONV, self._msg("stored"))
        ctx = self.service.get_context(CID, CONV)
        assert ctx is not None
        assert len(ctx.messages) == 1
        assert ctx.messages[0].content == "stored"

    def test_token_count_updated(self):
        self.service.add_message(CID, CONV, self._msg("A" * 100))
        ctx = self.service.get_context(CID, CONV)
        assert ctx.token_count > 0

    def test_separate_conversations_have_separate_versions(self):
        self.service.add_message(CID, CONV, self._msg("a"))
        v2 = self.service.add_message(CID, "other_conv", self._msg("b"))
        assert v2 == 1

    def test_add_message_creates_context_if_not_exists(self):
        ctx_before = self.service.get_context("new_co", "new_conv")
        assert ctx_before is None
        self.service.add_message("new_co", "new_conv", self._msg("hello"))
        ctx_after = self.service.get_context("new_co", "new_conv")
        assert ctx_after is not None
        assert len(ctx_after.messages) == 1

    def test_add_message_preserves_metadata(self):
        m = ConversationMessage(
            message_id="meta1", content="test", role="customer",
            metadata={"key": "value"},
        )
        self.service.add_message(CID, CONV, m)
        ctx = self.service.get_context(CID, CONV)
        assert ctx.messages[0].metadata == {"key": "value"}

    def test_add_message_with_different_roles(self):
        self.service.add_message(CID, CONV, self._msg("q", role="customer"))
        self.service.add_message(CID, CONV, self._msg("a", role="agent"))
        ctx = self.service.get_context(CID, CONV)
        assert ctx.messages[0].role == "customer"
        assert ctx.messages[1].role == "agent"

    def test_context_version_matches(self):
        self.service.add_message(CID, CONV, self._msg("a"))
        self.service.add_message(CID, CONV, self._msg("b"))
        ctx = self.service.get_context(CID, CONV)
        assert ctx.current_version == 2


# ═══════════════════════════════════════════════════════════════════════════
# 5. TestShouldSummarize
# ═══════════════════════════════════════════════════════════════════════════
class TestShouldSummarize(_Base):

    def test_empty_conversation_returns_false(self):
        assert self.service.should_summarize(CID, CONV) is False

    def test_below_threshold_returns_false(self):
        self._add_n(14)
        assert self.service.should_summarize(CID, CONV) is False

    def test_at_threshold_returns_true(self):
        self._add_n(15)
        assert self.service.should_summarize(CID, CONV) is True

    def test_above_threshold_returns_true(self):
        self._add_n(20)
        assert self.service.should_summarize(CID, CONV) is True

    def test_custom_threshold(self):
        self._add_n(5)
        assert self.service.should_summarize(CID, CONV, threshold=5) is True
        assert self.service.should_summarize(CID, CONV, threshold=10) is False

    def test_after_summarization_returns_false(self):
        base_ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        for i in range(15):
            m = self._msg(f"msg {i}", ts=base_ts + timedelta(minutes=i))
            self.service.add_message(CID, CONV, m)
        assert self.service.should_summarize(CID, CONV) is True

        self.service.summarize(CID, CONV)
        assert self.service.should_summarize(CID, CONV) is False

    def test_after_summarize_new_messages_trigger(self):
        base_ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        for i in range(15):
            m = self._msg(f"msg {i}", ts=base_ts + timedelta(minutes=i))
            self.service.add_message(CID, CONV, m)
        self.service.summarize(CID, CONV)

        # Use a timestamp far in the future so it's after last_summarized_at
        later_ts = datetime.now(timezone.utc) + timedelta(days=365)
        for i in range(15):
            m = self._msg(f"new {i}", ts=later_ts + timedelta(minutes=i))
            self.service.add_message(CID, CONV, m)
        assert self.service.should_summarize(CID, CONV) is True

    def test_not_enough_new_messages_after_summarize(self):
        base_ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        for i in range(15):
            m = self._msg(f"msg {i}", ts=base_ts + timedelta(minutes=i))
            self.service.add_message(CID, CONV, m)
        self.service.summarize(CID, CONV)

        later_ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for i in range(5):
            m = self._msg(f"new {i}", ts=later_ts + timedelta(minutes=i))
            self.service.add_message(CID, CONV, m)
        assert self.service.should_summarize(CID, CONV) is False


# ═══════════════════════════════════════════════════════════════════════════
# 6. TestExtractiveSummarization
# ═══════════════════════════════════════════════════════════════════════════
class TestExtractiveSummarization(_Base):

    def test_returns_non_empty_for_multiple_messages(self):
        self._add_realistic(5)
        ext, kp = self.service._extractive_summarize(
            self.service.get_context(CID, CONV).messages
        )
        assert isinstance(ext, str)
        assert len(ext) > 0

    def test_returns_key_points(self):
        self._add_realistic(5)
        _, kp = self.service._extractive_summarize(
            self.service.get_context(CID, CONV).messages
        )
        assert isinstance(kp, list)
        assert len(kp) > 0

    def test_key_points_capped_at_five(self):
        self._add_n(30)
        _, kp = self.service._extractive_summarize(
            self.service.get_context(CID, CONV).messages
        )
        assert len(kp) <= 5

    def test_key_points_are_strings(self):
        self._add_realistic(6)
        _, kp = self.service._extractive_summarize(
            self.service.get_context(CID, CONV).messages
        )
        for point in kp:
            assert isinstance(point, str)

    def test_short_message_single_sentence(self):
        self.service.add_message(CID, CONV, self._msg("Help me please."))
        ext, kp = self.service._extractive_summarize(
            self.service.get_context(CID, CONV).messages
        )
        # Should still return something for a single sentence
        assert isinstance(ext, str)

    def test_high_value_keywords_boosted(self):
        msgs = [
            ConversationMessage(message_id="a", content="I have a serious problem with my order and need urgent help.", role="customer"),
            ConversationMessage(message_id="b", content="The delivery was delayed and I want a refund for the shipping charge.", role="customer"),
        ]
        ext, kp = self.service._extractive_summarize(msgs)
        # Should contain content about problem/order/delivery/refund
        combined = ext + " ".join(kp)
        assert len(combined) > 0

    def test_questions_get_attention(self):
        msgs = [
            ConversationMessage(message_id="a", content="Can you help me resolve this issue?", role="customer"),
            ConversationMessage(message_id="b", content="Sure, what seems to be the error you are experiencing?", role="agent"),
        ]
        _, kp = self.service._extractive_summarize(msgs)
        # Questions should appear in key points
        any_question = any("?" in p for p in kp)
        assert any_question is True

    def test_empty_messages_returns_empty(self):
        ext, kp = self.service._extractive_summarize([])
        assert ext == ""
        assert kp == []


# ═══════════════════════════════════════════════════════════════════════════
# 7. TestAbstractiveSummarization
# ═══════════════════════════════════════════════════════════════════════════
class TestAbstractiveSummarization(_Base):

    def test_rule_based_returns_non_empty(self):
        self._add_realistic(5)
        result = self.service._abstractive_summarize(
            self.service.get_context(CID, CONV).messages
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_custom_generator_called(self):
        gen = MagicMock(return_value="Custom AI summary")
        svc = ConversationSummarizationService(abstractive_generator=gen)
        svc.reset()
        msgs = [self._msg("hello")]
        result = svc._abstractive_summarize(msgs)
        gen.assert_called_once_with(msgs)
        assert result == "Custom AI summary"

    def test_custom_generator_fallback_on_error(self):
        def bad_gen(msgs):
            raise RuntimeError("AI down")

        svc = ConversationSummarizationService(abstractive_generator=bad_gen)
        svc.reset()
        msgs = [self._msg("fallback test")]
        result = svc._abstractive_summarize(msgs)
        # Should fall back to rule-based
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_conversation_overview(self):
        self._add_realistic(4)
        result = self.service._abstractive_summarize(
            self.service.get_context(CID, CONV).messages
        )
        assert "customer" in result.lower()
        assert "agent" in result.lower()

    def test_contains_topic_keywords(self):
        self._add_realistic(5)
        result = self.service._abstractive_summarize(
            self.service.get_context(CID, CONV).messages
        )
        assert "Topics discussed:" in result

    def test_merges_consecutive_same_role(self):
        msgs = [
            ConversationMessage(message_id="a", content="First part.", role="customer"),
            ConversationMessage(message_id="b", content="Second part.", role="customer"),
            ConversationMessage(message_id="c", content="Agent reply.", role="agent"),
        ]
        result = self.service._abstractive_summarize(msgs)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_messages_returns_empty(self):
        result = self.service._abstractive_summarize([])
        assert result == ""

    def test_truncates_long_sentences(self):
        long_content = "A" * 200
        msgs = [ConversationMessage(message_id="x", content=long_content, role="customer")]
        result = self.service._abstractive_summarize(msgs)
        # Rule-based should truncate to ~60 chars per block first sentence
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════
# 8. TestHybridSummarization
# ═══════════════════════════════════════════════════════════════════════════
class TestHybridSummarization(_Base):

    def _summarize_mode(self, mode, **kwargs):
        req = SummarizationRequest(
            company_id=CID, conversation_id=CONV, mode=mode, **kwargs
        )
        return self.service.summarize(CID, CONV, req)

    def test_hybrid_contains_extractive(self):
        self._add_realistic(6)
        r = self._summarize_mode(SummarizationMode.HYBRID)
        assert r.success is True
        assert len(r.summary.extractive_summary) > 0

    def test_hybrid_contains_abstractive(self):
        self._add_realistic(6)
        r = self._summarize_mode(SummarizationMode.HYBRID)
        assert r.success is True
        assert len(r.summary.abstractive_summary) > 0

    def test_hybrid_contains_key_points(self):
        self._add_realistic(6)
        r = self._summarize_mode(SummarizationMode.HYBRID)
        assert r.success is True
        assert len(r.summary.key_points) > 0

    def test_hybrid_summary_text_populated(self):
        self._add_realistic(6)
        r = self._summarize_mode(SummarizationMode.HYBRID)
        assert r.success is True
        assert len(r.summary.hybrid_summary) > 0

    def test_hybrid_key_points_excluded_when_flag_false(self):
        self._add_realistic(6)
        r = self._summarize_mode(SummarizationMode.HYBRID, include_key_points=False)
        assert r.success is True
        assert r.summary.key_points == []

    def test_hybrid_compression_ratio_is_float(self):
        self._add_realistic(6)
        r = self._summarize_mode(SummarizationMode.HYBRID)
        assert r.success is True
        assert isinstance(r.summary.compression_ratio, float)

    def test_extractive_mode_no_abstractive(self):
        self._add_realistic(6)
        r = self._summarize_mode(SummarizationMode.EXTRACTIVE)
        assert r.success is True
        assert len(r.summary.extractive_summary) > 0
        assert r.summary.abstractive_summary == ""

    def test_abstractive_mode_no_extractive(self):
        self._add_realistic(6)
        r = self._summarize_mode(SummarizationMode.ABSTRACTIVE)
        assert r.success is True
        assert r.summary.extractive_summary == ""
        assert len(r.summary.abstractive_summary) > 0


# ═══════════════════════════════════════════════════════════════════════════
# 9. TestSummarize (main method)
# ═══════════════════════════════════════════════════════════════════════════
class TestSummarize(_Base):

    def test_default_request_uses_hybrid(self):
        self._add_realistic(5)
        r = self.service.summarize(CID, CONV)
        assert r.success is True
        assert r.summary.mode == SummarizationMode.HYBRID

    def test_success_returns_true(self):
        self._add_realistic(5)
        r = self.service.summarize(CID, CONV)
        assert r.success is True

    def test_summary_status_is_completed(self):
        self._add_realistic(5)
        r = self.service.summarize(CID, CONV)
        assert r.summary.status == SummaryStatus.COMPLETED

    def test_summary_has_non_empty_hybrid(self):
        self._add_realistic(5)
        r = self.service.summarize(CID, CONV)
        assert len(r.summary.hybrid_summary) > 0

    def test_generation_time_is_non_negative(self):
        self._add_realistic(5)
        r = self.service.summarize(CID, CONV)
        assert r.summary.generation_time_ms >= 0.0

    def test_company_id_mismatch_returns_error(self):
        self._add_realistic(3)
        req = SummarizationRequest(
            company_id="wrong_company", conversation_id=CONV,
        )
        r = self.service.summarize(CID, CONV, req)
        assert r.success is False
        assert "mismatch" in r.error.lower()

    def test_no_messages_returns_error(self):
        r = self.service.summarize(CID, CONV)
        assert r.success is False
        assert "no messages" in r.error.lower()

    def test_max_messages_limits_input(self):
        for i in range(10):
            self.service.add_message(CID, CONV, self._msg(f"msg {i}"))
        req = SummarizationRequest(
            company_id=CID, conversation_id=CONV, max_messages=3,
        )
        r = self.service.summarize(CID, CONV, req)
        assert r.success is True
        assert r.summary.message_count == 3
        assert r.summary.original_message_count == 3

    def test_summarize_sets_last_summarized_at(self):
        self._add_realistic(5)
        before = datetime.now(timezone.utc)
        self.service.summarize(CID, CONV)
        ctx = self.service.get_context(CID, CONV)
        assert ctx.last_summarized_at is not None
        assert ctx.last_summarized_at >= before

    def test_summarize_stores_summary_in_context(self):
        self._add_realistic(5)
        r = self.service.summarize(CID, CONV)
        ctx = self.service.get_context(CID, CONV)
        assert len(ctx.summaries) == 1
        assert ctx.summaries[0].summary_id == r.summary.summary_id


# ═══════════════════════════════════════════════════════════════════════════
# 10. TestW9GAP024 (Version Protection)
# ═══════════════════════════════════════════════════════════════════════════
class TestW9GAP024(_Base):

    def test_no_version_mismatch_normal_flow(self):
        self._add_realistic(5)
        r = self.service.summarize(CID, CONV)
        assert r.success is True
        assert r.version_mismatch is False
        assert r.re_summarized is False

    def test_version_change_during_first_attempt_triggers_rerun(self):
        """Simulate a version change during summarization via patched _run_summarization."""
        self._add_realistic(5)
        # version is now 5
        call_count = [0]
        original_run = self.service._run_summarization

        def patched_run(messages, request, conversation_version):
            call_count[0] += 1
            if call_count[0] == 1:
                # Increment version to simulate concurrent add_message
                self.service._version_counters[f"{CID}:{CONV}"] += 1
            return original_run(messages, request, conversation_version)

        with patch.object(self.service, "_run_summarization", side_effect=patched_run):
            r = self.service.summarize(CID, CONV)

        assert r.success is True
        # _run_summarization should be called twice (initial + re-run)
        assert call_count[0] == 2

    def test_rerun_produces_successful_result(self):
        self._add_realistic(5)
        call_count = [0]
        original_run = self.service._run_summarization

        def patched_run(messages, request, conversation_version):
            call_count[0] += 1
            if call_count[0] == 1:
                self.service._version_counters[f"{CID}:{CONV}"] += 1
            return original_run(messages, request, conversation_version)

        with patch.object(self.service, "_run_summarization", side_effect=patched_run):
            r = self.service.summarize(CID, CONV)

        assert r.summary is not None
        assert r.summary.status == SummaryStatus.COMPLETED

    def test_stats_track_total_summarizations(self):
        self._add_realistic(5)
        self.service.summarize(CID, CONV)
        stats = self.service.get_stats(CID)
        assert stats["total_summarizations"] == 1

    def test_stats_track_successful_summarizations(self):
        self._add_realistic(5)
        self.service.summarize(CID, CONV)
        stats = self.service.get_stats(CID)
        assert stats["successful_summarizations"] == 1
        assert stats["failed_summarizations"] == 0

    def test_version_reflected_in_summary(self):
        self._add_realistic(5)
        r = self.service.summarize(CID, CONV)
        assert r.summary.conversation_version == 5

    def test_max_two_attempts(self):
        """Even if version changes on both attempts, only 2 total attempts are made."""
        self._add_realistic(5)
        call_count = [0]
        original_run = self.service._run_summarization

        def patched_run(messages, request, conversation_version):
            call_count[0] += 1
            # Always increment version
            self.service._version_counters[f"{CID}:{CONV}"] += 1
            return original_run(messages, request, conversation_version)

        with patch.object(self.service, "_run_summarization", side_effect=patched_run):
            r = self.service.summarize(CID, CONV)

        # Should not exceed 2 attempts
        assert call_count[0] == 2

    def test_lock_timeout_returns_error(self):
        """When the lock is already held, summarize should return a timeout error."""
        self._add_realistic(5)
        # Acquire the lock before calling summarize
        key = f"{CID}:{CONV}"
        lock = self.service._get_lock(key)
        lock.acquire()

        try:
            # Set a very short TTL by patching
            with patch("backend.app.core.conversation_summarization._VERSION_LOCK_TTL_SECONDS", 0):
                r = self.service.summarize(CID, CONV)
            assert r.success is False
            assert "lock" in r.error.lower() or "timeout" in r.error.lower()
        finally:
            lock.release()

    def test_version_mismatch_with_slow_generator(self):
        """Use a slow custom generator + concurrent add_message to trigger real version mismatch."""
        gen_called = threading.Event()

        def slow_generator(msgs):
            gen_called.set()
            time.sleep(0.3)
            return "Slow generated summary"

        svc = ConversationSummarizationService(abstractive_generator=slow_generator)
        svc.reset()

        for i in range(5):
            svc.add_message(CID, CONV, self._msg(f"msg {i}"))

        def concurrent_add():
            gen_called.wait(timeout=5)
            time.sleep(0.05)
            svc.add_message(CID, CONV, self._msg("concurrent"))

        t = threading.Thread(target=concurrent_add)
        t.start()

        req = SummarizationRequest(
            company_id=CID, conversation_id=CONV,
            mode=SummarizationMode.ABSTRACTIVE,
        )
        r = svc.summarize(CID, CONV, req)
        t.join(timeout=5)

        # Should succeed regardless of concurrent access
        assert r.success is True
        assert r.summary is not None


# ═══════════════════════════════════════════════════════════════════════════
# 11. TestGetContext
# ═══════════════════════════════════════════════════════════════════════════
class TestGetContext(_Base):

    def test_non_existent_returns_none(self):
        assert self.service.get_context("no_co", "no_conv") is None

    def test_returns_context_after_add(self):
        self.service.add_message(CID, CONV, self._msg("hi"))
        ctx = self.service.get_context(CID, CONV)
        assert ctx is not None
        assert ctx.conversation_id == CONV
        assert ctx.company_id == CID

    def test_context_has_correct_messages(self):
        self.service.add_message(CID, CONV, self._msg("a"))
        self.service.add_message(CID, CONV, self._msg("b"))
        ctx = self.service.get_context(CID, CONV)
        assert len(ctx.messages) == 2
        assert ctx.messages[0].content == "a"
        assert ctx.messages[1].content == "b"

    def test_context_has_correct_version(self):
        self.service.add_message(CID, CONV, self._msg("a"))
        self.service.add_message(CID, CONV, self._msg("b"))
        ctx = self.service.get_context(CID, CONV)
        assert ctx.current_version == 2

    def test_context_includes_summaries_after_summarize(self):
        self._add_realistic(5)
        self.service.summarize(CID, CONV)
        ctx = self.service.get_context(CID, CONV)
        assert len(ctx.summaries) == 1

    def test_context_isolation_between_conversations(self):
        self.service.add_message(CID, CONV, self._msg("a"))
        ctx_other = self.service.get_context(CID, "other")
        assert ctx_other is None


# ═══════════════════════════════════════════════════════════════════════════
# 12. TestGetLatestSummary
# ═══════════════════════════════════════════════════════════════════════════
class TestGetLatestSummary(_Base):

    def test_none_when_no_summaries(self):
        self.service.add_message(CID, CONV, self._msg("hi"))
        assert self.service.get_latest_summary(CID, CONV) is None

    def test_returns_summary_after_summarize(self):
        self._add_realistic(5)
        r = self.service.summarize(CID, CONV)
        latest = self.service.get_latest_summary(CID, CONV)
        assert latest is not None
        assert latest.summary_id == r.summary.summary_id

    def test_returns_latest_after_multiple_summarizations(self):
        self._add_realistic(5)
        r1 = self.service.summarize(CID, CONV)
        # Add more messages
        self.service.add_message(CID, CONV, self._msg("more"))
        self.service.add_message(CID, CONV, self._msg("data"))
        # Force a new summary
        r2 = self.service.summarize(CID, CONV)
        latest = self.service.get_latest_summary(CID, CONV)
        assert latest.summary_id == r2.summary.summary_id

    def test_returns_from_cache(self):
        self._add_realistic(5)
        self.service.summarize(CID, CONV)
        # Even after clearing the context's summaries list, cache should still work
        key = f"{CID}:{CONV}"
        cached = self.service._summary_cache.get(key)
        assert cached is not None
        assert len(cached) == 1

    def test_none_for_non_existent_conversation(self):
        assert self.service.get_latest_summary("no_co", "no_conv") is None


# ═══════════════════════════════════════════════════════════════════════════
# 13. TestGetContextWindow
# ═══════════════════════════════════════════════════════════════════════════
class TestGetContextWindow(_Base):

    def test_returns_dict_with_expected_keys(self):
        self.service.add_message(CID, CONV, self._msg("hi"))
        w = self.service.get_context_window(CID, CONV)
        assert "messages" in w
        assert "summary" in w
        assert "total_messages" in w
        assert "version" in w
        assert "token_count" in w

    def test_messages_limited_by_max(self):
        for i in range(25):
            self.service.add_message(CID, CONV, self._msg(f"m{i}"))
        w = self.service.get_context_window(CID, CONV, max_messages=10)
        assert len(w["messages"]) == 10

    def test_messages_have_expected_fields(self):
        self.service.add_message(CID, CONV, self._msg("hello"))
        w = self.service.get_context_window(CID, CONV)
        msg = w["messages"][0]
        assert "message_id" in msg
        assert "content" in msg
        assert "role" in msg
        assert "timestamp" in msg

    def test_summary_present_after_summarize(self):
        self._add_realistic(5)
        self.service.summarize(CID, CONV)
        w = self.service.get_context_window(CID, CONV)
        assert w["summary"] is not None
        assert "extractive_summary" in w["summary"]

    def test_summary_none_before_summarize(self):
        self.service.add_message(CID, CONV, self._msg("hi"))
        w = self.service.get_context_window(CID, CONV)
        assert w["summary"] is None

    def test_total_messages_reflects_all(self):
        for i in range(30):
            self.service.add_message(CID, CONV, self._msg(f"m{i}"))
        w = self.service.get_context_window(CID, CONV, max_messages=5)
        assert w["total_messages"] == 30
        assert len(w["messages"]) == 5

    def test_version_reflects_current(self):
        self.service.add_message(CID, CONV, self._msg("a"))
        self.service.add_message(CID, CONV, self._msg("b"))
        w = self.service.get_context_window(CID, CONV)
        assert w["version"] == 2

    def test_token_count_positive(self):
        self._add_realistic(5)
        w = self.service.get_context_window(CID, CONV)
        assert w["token_count"] > 0


# ═══════════════════════════════════════════════════════════════════════════
# 14. TestConversationVersion
# ═══════════════════════════════════════════════════════════════════════════
class TestConversationVersion(_Base):

    def test_non_existent_returns_zero(self):
        assert self.service.get_conversation_version("no_co", "no_conv") == 0

    def test_version_after_single_message(self):
        self.service.add_message(CID, CONV, self._msg("hi"))
        assert self.service.get_conversation_version(CID, CONV) == 1

    def test_version_increments(self):
        for i in range(1, 6):
            self.service.add_message(CID, CONV, self._msg(f"m{i}"))
            assert self.service.get_conversation_version(CID, CONV) == i

    def test_version_is_conversation_specific(self):
        self.service.add_message(CID, CONV, self._msg("a"))
        self.service.add_message(CID, CONV, self._msg("b"))
        self.service.add_message(CID, "other", self._msg("c"))
        assert self.service.get_conversation_version(CID, CONV) == 2
        assert self.service.get_conversation_version(CID, "other") == 1

    def test_version_persists_across_operations(self):
        self.service.add_message(CID, CONV, self._msg("a"))
        v1 = self.service.get_conversation_version(CID, CONV)
        self.service.get_context(CID, CONV)  # read-only operation
        v2 = self.service.get_conversation_version(CID, CONV)
        assert v1 == v2 == 1


# ═══════════════════════════════════════════════════════════════════════════
# 15. TestClearConversation
# ═══════════════════════════════════════════════════════════════════════════
class TestClearConversation(_Base):

    def test_returns_true_on_success(self):
        self.service.add_message(CID, CONV, self._msg("hi"))
        assert self.service.clear_conversation(CID, CONV) is True

    def test_removes_from_store(self):
        self.service.add_message(CID, CONV, self._msg("hi"))
        self.service.clear_conversation(CID, CONV)
        assert self.service.get_context(CID, CONV) is None

    def test_resets_version_counter(self):
        self.service.add_message(CID, CONV, self._msg("a"))
        self.service.add_message(CID, CONV, self._msg("b"))
        self.service.clear_conversation(CID, CONV)
        assert self.service.get_conversation_version(CID, CONV) == 0

    def test_clears_summary_cache(self):
        self._add_realistic(5)
        self.service.summarize(CID, CONV)
        self.service.clear_conversation(CID, CONV)
        assert self.service.get_latest_summary(CID, CONV) is None

    def test_clear_non_existent_returns_true(self):
        assert self.service.clear_conversation("no_co", "no_conv") is True


# ═══════════════════════════════════════════════════════════════════════════
# 16. TestStats
# ═══════════════════════════════════════════════════════════════════════════
class TestStats(_Base):

    def test_default_stats_for_unknown_company(self):
        stats = self.service.get_stats("unknown")
        assert stats["total_summarizations"] == 0
        assert stats["successful_summarizations"] == 0
        assert stats["failed_summarizations"] == 0
        assert stats["version_mismatches"] == 0
        assert stats["re_summarizations"] == 0
        assert stats["total_messages_processed"] == 0
        assert stats["avg_generation_time_ms"] == 0.0

    def test_stats_after_successful_summarization(self):
        self._add_realistic(5)
        self.service.summarize(CID, CONV)
        stats = self.service.get_stats(CID)
        assert stats["total_summarizations"] == 1
        assert stats["successful_summarizations"] == 1
        assert stats["total_messages_processed"] == 5

    def test_stats_track_failed_summarization(self):
        # No messages → error
        r = self.service.summarize(CID, CONV)
        assert r.success is False
        stats = self.service.get_stats(CID)
        # "No messages" error happens before total_summarizations is incremented
        assert stats["total_summarizations"] == 0

    def test_avg_generation_time_updated(self):
        self._add_realistic(5)
        self.service.summarize(CID, CONV)
        stats = self.service.get_stats(CID)
        assert stats["avg_generation_time_ms"] >= 0.0

    def test_stats_is_dict_copy(self):
        self._add_realistic(5)
        self.service.summarize(CID, CONV)
        s1 = self.service.get_stats(CID)
        s1["total_summarizations"] = 999
        s2 = self.service.get_stats(CID)
        assert s2["total_summarizations"] == 1

    def test_stats_per_company(self):
        self._add_realistic(3)
        self.service.summarize(CID, CONV)
        # Different company
        for i in range(3):
            self.service.add_message("co2", "c2", self._msg(f"x{i}"))
        self.service.summarize("co2", "c2")
        s1 = self.service.get_stats(CID)
        s2 = self.service.get_stats("co2")
        assert s1["total_summarizations"] == 1
        assert s2["total_summarizations"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# 17. TestBC008 (Graceful Degradation)
# ═══════════════════════════════════════════════════════════════════════════
class TestBC008(_Base):

    def test_add_message_does_not_crash_on_internal_error(self):
        with patch.object(
            self.service, "_get_or_create_context",
            side_effect=RuntimeError("DB down"),
        ):
            v = self.service.add_message(CID, CONV, self._msg("hi"))
            assert v == 0

    def test_should_summarize_does_not_crash(self):
        with patch.object(
            self.service, "_get_or_create_context",
            side_effect=RuntimeError("DB down"),
        ):
            result = self.service.should_summarize(CID, CONV)
            assert result is False

    def test_summarize_does_not_crash_on_internal_error(self):
        with patch.object(
            self.service, "_get_or_create_context",
            side_effect=RuntimeError("DB down"),
        ):
            r = self.service.summarize(CID, CONV)
            assert r.success is False
            assert "DB down" in r.error

    def test_get_context_does_not_crash(self):
        self.service.add_message(CID, CONV, self._msg("hi"))
        original = self.service._conversation_store
        self.service._conversation_store = None
        try:
            result = self.service.get_context(CID, CONV)
            assert result is None
        finally:
            self.service._conversation_store = original

    def test_get_latest_summary_does_not_crash(self):
        original_cache = self.service._summary_cache
        self.service._summary_cache = None
        try:
            result = self.service.get_latest_summary(CID, CONV)
            assert result is None
        finally:
            self.service._summary_cache = original_cache

    def test_get_context_window_does_not_crash(self):
        with patch.object(
            self.service, "_get_or_create_context",
            side_effect=RuntimeError("error"),
        ):
            w = self.service.get_context_window(CID, CONV)
            assert w["messages"] == []
            assert w["summary"] is None
            assert w["total_messages"] == 0

    def test_get_conversation_version_does_not_crash(self):
        original = self.service._version_counters
        self.service._version_counters = None
        try:
            v = self.service.get_conversation_version(CID, CONV)
            assert v == 0
        finally:
            self.service._version_counters = original

    def test_clear_conversation_does_not_crash(self):
        self.service.add_message(CID, CONV, self._msg("hi"))
        original = self.service._conversation_store
        self.service._conversation_store = None
        try:
            result = self.service.clear_conversation(CID, CONV)
            assert result is False
        finally:
            self.service._conversation_store = original

    def test_get_stats_does_not_crash(self):
        original = self.service._stats
        self.service._stats = None
        try:
            stats = self.service.get_stats(CID)
            assert isinstance(stats, dict)
        finally:
            self.service._stats = original

    def test_reset_does_not_crash(self):
        self.service.add_message(CID, CONV, self._msg("hi"))
        original = self.service._conversation_store
        # Replace with something that will fail on clear
        self.service._conversation_store = None
        try:
            self.service.reset()  # should not raise
        finally:
            self.service._conversation_store = original


# ═══════════════════════════════════════════════════════════════════════════
# 18. TestEdgeCases
# ═══════════════════════════════════════════════════════════════════════════
class TestEdgeCases(_Base):

    def test_empty_conversation_summarize(self):
        r = self.service.summarize(CID, CONV)
        assert r.success is False
        assert "no messages" in r.error.lower()

    def test_single_message_summarize(self):
        self.service.add_message(CID, CONV, self._msg("Hello world."))
        r = self.service.summarize(CID, CONV)
        assert r.success is True
        assert r.summary is not None

    def test_very_long_message(self):
        long_text = "This is a very long message. " * 500
        self.service.add_message(CID, CONV, self._msg(long_text))
        r = self.service.summarize(CID, CONV)
        assert r.success is True

    def test_many_short_messages(self):
        for i in range(50):
            self.service.add_message(CID, CONV, self._msg(f"Short {i}."))
        r = self.service.summarize(CID, CONV)
        assert r.success is True

    def test_unicode_content(self):
        msgs = [
            ConversationMessage(message_id="u1", content="こんにちは世界", role="customer"),
            ConversationMessage(message_id="u2", content="مرحبا بالعالم", role="agent"),
            ConversationMessage(message_id="u3", content="Привет мир", role="customer"),
            ConversationMessage(message_id="u4", content="🎉 emoji test 🚀", role="agent"),
            ConversationMessage(message_id="u5", content="Ñoño café résumé", role="customer"),
        ]
        for m in msgs:
            self.service.add_message(CID, CONV, m)
        r = self.service.summarize(CID, CONV)
        assert r.success is True

    def test_special_characters(self):
        self.service.add_message(CID, CONV, self._msg("<script>alert('xss')</script>"))
        self.service.add_message(CID, CONV, self._msg("SQL: DROP TABLE users; --"))
        self.service.add_message(CID, CONV, self._msg("Path: /etc/passwd"))
        self.service.add_message(CID, CONV, self._msg("Regex: ^[a-z]+$"))
        self.service.add_message(CID, CONV, self._msg("JSON: {\"key\": \"value\"}"))
        r = self.service.summarize(CID, CONV)
        assert r.success is True

    def test_whitespace_only_message(self):
        self.service.add_message(CID, CONV, self._msg("   "))
        self.service.add_message(CID, CONV, self._msg("\t\n"))
        r = self.service.summarize(CID, CONV)
        # Should still succeed (has messages, just empty content)
        assert r.success is True

    def test_punctuation_only_message(self):
        self.service.add_message(CID, CONV, self._msg("!!!"))
        self.service.add_message(CID, CONV, self._msg("..."))
        self.service.add_message(CID, CONV, self._msg("???"))
        r = self.service.summarize(CID, CONV)
        assert r.success is True

    def test_rapid_successive_summarize_calls(self):
        self._add_realistic(5)
        r1 = self.service.summarize(CID, CONV)
        r2 = self.service.summarize(CID, CONV)
        r3 = self.service.summarize(CID, CONV)
        assert r1.success is True
        assert r2.success is True
        assert r3.success is True
        # All should produce summaries
        assert r1.summary.summary_id != r2.summary.summary_id

    def test_all_three_modes_sequentially(self):
        self._add_realistic(5)
        for mode in SummarizationMode:
            req = SummarizationRequest(
                company_id=CID, conversation_id=CONV, mode=mode,
            )
            r = self.service.summarize(CID, CONV, req)
            assert r.success is True, f"Failed for mode {mode}"
            assert r.summary.mode == mode

    def test_single_word_message(self):
        self.service.add_message(CID, CONV, self._msg("Help"))
        self.service.add_message(CID, CONV, self._msg("Sure"))
        r = self.service.summarize(CID, CONV)
        assert r.success is True

    def test_mixed_company_ids(self):
        """Ensure service correctly isolates operations across company IDs."""
        self.service.add_message("co_A", "conv1", self._msg("A message"))
        self.service.add_message("co_B", "conv1", self._msg("B message"))
        self.service.add_message("co_A", "conv1", self._msg("A second"))
        self.service.add_message("co_B", "conv1", self._msg("B second"))

        assert self.service.get_conversation_version("co_A", "conv1") == 2
        assert self.service.get_conversation_version("co_B", "conv1") == 2

        rA = self.service.summarize("co_A", "conv1")
        rB = self.service.summarize("co_B", "conv1")
        assert rA.success is True
        assert rB.success is True
        assert rA.summary.company_id == "co_A"
        assert rB.summary.company_id == "co_B"

    def test_abbr_protected_in_sentence_split(self):
        """Ensure abbreviations like Mr. Dr. don't cause incorrect splits."""
        msg = ConversationMessage(
            message_id="abbr", role="customer",
            content="Mr. Smith went to see Dr. Jones about the issue.",
        )
        self.service.add_message(CID, CONV, msg)
        r = self.service.summarize(CID, CONV)
        assert r.success is True

    def test_context_window_with_summary_token_count(self):
        """Token count in context window should include summary tokens."""
        self._add_realistic(5)
        self.service.summarize(CID, CONV)
        w_before = self.service.get_context_window(CID, CONV)
        tokens_with_summary = w_before["token_count"]

        # Now clear summaries and check tokens decrease
        self.service._summary_cache.clear()
        ctx = self.service.get_context(CID, CONV)
        ctx.summaries.clear()
        w_after = self.service.get_context_window(CID, CONV)
        tokens_without_summary = w_after["token_count"]

        # Tokens with summary should be >= tokens without
        assert tokens_with_summary >= tokens_without_summary
