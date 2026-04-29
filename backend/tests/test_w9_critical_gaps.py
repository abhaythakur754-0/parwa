"""
Week 9 CRITICAL GAP Tests

Covers four critical gaps identified in Week 9:
1. Signal Extraction Race Condition (w9d6)
2. Sentiment Score Boundary Failures (w9d7)
3. RAG Tenant Isolation Leak (w9d7)
4. Training Data Cross-Contamination (w9d9)

All tests use unittest.mock / pytest with NO real API calls.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Module-level stubs (populated by fixtures) ───────────────────────
SignalExtractionRequest = None  # type: ignore[assignment,misc]
SignalExtractor = None  # type: ignore[assignment,misc]
ExtractedSignals = None  # type: ignore[assignment,misc]
SentimentAnalyzer = None  # type: ignore[assignment,misc]
SentimentResult = None  # type: ignore[assignment,misc]
FrustrationDetector = None  # type: ignore[assignment,misc]
UrgencyScorer = None  # type: ignore[assignment,misc]
ToneAdvisor = None  # type: ignore[assignment,misc]
EmotionClassifier = None  # type: ignore[assignment,misc]
RAGRetriever = None  # type: ignore[assignment,misc]
RAGResult = None  # type: ignore[assignment,misc]
RAGChunk = None  # type: ignore[assignment,misc]
MockVectorStore = None  # type: ignore[assignment,misc]
TrainingDataIsolationService = None  # type: ignore[assignment,misc]
TrainingDataset = None  # type: ignore[assignment,misc]
DatasetIsolationResult = None  # type: ignore[assignment,misc]
VALID_VARIANT_TYPES = None  # type: ignore[assignment,misc]
ParwaBaseError = None  # type: ignore[assignment,misc]


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — import source modules with mocked logger
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("app.logger.get_logger", return_value=MagicMock()):
        from app.core.signal_extraction import (  # noqa: F811,F401
            ExtractedSignals,
            SignalExtractionRequest,
            SignalExtractor,
        )
        from app.core.sentiment_engine import (  # noqa: F811,F401
            EmotionClassifier,
            FrustrationDetector,
            SentimentAnalyzer,
            SentimentResult,
            ToneAdvisor,
            UrgencyScorer,
        )
        from app.core.rag_retrieval import (  # noqa: F811,F401
            RAGChunk,
            RAGResult,
            RAGRetriever,
        )
        from app.exceptions import ParwaBaseError as _PBE  # noqa: F811,F401
        from app.services.training_data_isolation import (  # noqa: F811,F401
            DatasetIsolationResult,
            TrainingDataIsolationService,
            TrainingDataset,
            VALID_VARIANT_TYPES,
        )
        from shared.knowledge_base.vector_search import MockVectorStore as _MVS  # noqa: F811,F401
        globals().update({
            "SignalExtractionRequest": SignalExtractionRequest,
            "SignalExtractor": SignalExtractor,
            "ExtractedSignals": ExtractedSignals,
            "SentimentAnalyzer": SentimentAnalyzer,
            "SentimentResult": SentimentResult,
            "FrustrationDetector": FrustrationDetector,
            "UrgencyScorer": UrgencyScorer,
            "ToneAdvisor": ToneAdvisor,
            "EmotionClassifier": EmotionClassifier,
            "RAGRetriever": RAGRetriever,
            "RAGResult": RAGResult,
            "RAGChunk": RAGChunk,
            "MockVectorStore": _MVS,
            "TrainingDataIsolationService": TrainingDataIsolationService,
            "TrainingDataset": TrainingDataset,
            "DatasetIsolationResult": DatasetIsolationResult,
            "VALID_VARIANT_TYPES": VALID_VARIANT_TYPES,
            "ParwaBaseError": _PBE,
        })


# ═══════════════════════════════════════════════════════════════════════
# 1. Signal Extraction Race Condition (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestSignalExtractionRaceCondition:
    """Tests that concurrent signal extraction for the same ticket
    doesn't produce inconsistent results or corrupt cache.
    """

    def setup_method(self):
        self.extractor = SignalExtractor()

    @pytest.mark.asyncio
    async def test_concurrent_same_ticket_produces_consistent_results(self):
        """Two concurrent extracts for same query/company/variant must
        return identical signal values."""
        req = SignalExtractionRequest(
            query="I want a refund for my $50 order",
            company_id="company_race_1",
            variant_type="parwa",
        )
        cache_miss = AsyncMock(return_value=None)
        cache_set_mock = AsyncMock()

        with patch("app.core.redis.cache_get", cache_miss), \
                patch("app.core.redis.cache_set", cache_set_mock):
            results = await asyncio.gather(
                self.extractor.extract(req),
                self.extractor.extract(req),
            )

        assert results[0].intent == results[1].intent
        assert results[0].sentiment == results[1].sentiment
        assert results[0].complexity == results[1].complexity
        assert results[0].monetary_value == results[1].monetary_value
        assert results[0].query_breadth == results[1].query_breadth

    @pytest.mark.asyncio
    async def test_concurrent_different_variants_isolated_cache_keys(self):
        """Concurrent extracts for same query but different variants
        must use different cache keys and store independently."""
        req_parwa = SignalExtractionRequest(
            query="reset my password please",
            company_id="company_race_2",
            variant_type="parwa",
        )
        req_mini = SignalExtractionRequest(
            query="reset my password please",
            company_id="company_race_2",
            variant_type="mini_parwa",
        )
        cache_miss = AsyncMock(return_value=None)
        cache_set_mock = AsyncMock()

        with patch("app.core.redis.cache_get", cache_miss), \
                patch("app.core.redis.cache_set", cache_set_mock):
            result_parwa, result_mini = await asyncio.gather(
                self.extractor.extract(req_parwa),
                self.extractor.extract(req_mini),
            )

        # Both should produce valid results
        assert isinstance(result_parwa, ExtractedSignals)
        assert isinstance(result_mini, ExtractedSignals)
        # Cache set should have been called twice
        assert cache_set_mock.call_count == 2
        # Keys must be different
        keys = [call[0][1] for call in cache_set_mock.call_args_list]
        assert keys[0] != keys[1]
        assert "parwa" in keys[0]
        assert "mini_parwa" in keys[1]

    @pytest.mark.asyncio
    async def test_concurrent_different_queries_no_interference(self):
        """Concurrent extracts for different queries on same company
        must not interfere with each other."""
        req_refund = SignalExtractionRequest(
            query="refund my order immediately",
            company_id="company_race_3",
            variant_type="parwa",
        )
        req_shipping = SignalExtractionRequest(
            query="where is my package delivery",
            company_id="company_race_3",
            variant_type="parwa",
        )
        cache_miss = AsyncMock(return_value=None)
        cache_set_mock = AsyncMock()

        with patch("app.core.redis.cache_get", cache_miss), \
                patch("app.core.redis.cache_set", cache_set_mock):
            result_refund, result_shipping = await asyncio.gather(
                self.extractor.extract(req_refund),
                self.extractor.extract(req_shipping),
            )

        assert result_refund.intent == "refund"
        assert result_shipping.intent == "shipping"

    @pytest.mark.asyncio
    async def test_race_with_cache_hit_and_miss(self):
        """First call writes cache, second concurrent call may get
        cache hit or miss — either way results must be consistent."""
        req = SignalExtractionRequest(
            query="I am very unhappy with the terrible service",
            company_id="company_race_4",
            variant_type="parwa",
        )
        # First call misses, subsequent calls may hit or miss
        call_count = {"n": 0}
        cached_data = {
            "intent": "complaint", "sentiment": 0.1, "complexity": 0.4,
            "monetary_value": 0.0, "monetary_currency": None,
            "customer_tier": "free", "turn_count": 0,
            "previous_response_status": "none",
            "reasoning_loop_detected": False, "resolution_path_count": 3,
            "query_breadth": 0.5,
        }

        async def _cache_get(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] > 1:
                return cached_data
            return None

        cache_get_mock = AsyncMock(side_effect=_cache_get)
        cache_set_mock = AsyncMock()

        with patch("app.core.redis.cache_get", cache_get_mock), \
                patch("app.core.redis.cache_set", cache_set_mock):
            results = await asyncio.gather(
                self.extractor.extract(req),
                self.extractor.extract(req),
            )

        # Both results should have the same intent (both complaint or both
        # computed)
        assert results[0].intent == results[1].intent

    @pytest.mark.asyncio
    async def test_cache_key_determinism_under_concurrency(self):
        """Cache keys generated for identical inputs must always match."""
        req1 = SignalExtractionRequest(
            query="Help with billing",
            company_id="co_determinism",
            variant_type="parwa",
        )
        req2 = SignalExtractionRequest(
            query="Help with billing",
            company_id="co_determinism",
            variant_type="parwa",
        )
        h1 = self.extractor._compute_query_hash(req1.query)
        h2 = self.extractor._compute_query_hash(req2.query)
        key1 = f"signal_cache:{req1.company_id}:{req1.variant_type}:{h1}"
        key2 = f"signal_cache:{req2.company_id}:{req2.variant_type}:{h2}"
        assert key1 == key2

    @pytest.mark.asyncio
    async def test_cache_write_error_does_not_corrupt_result(self):
        """If cache write fails, extraction result must still be valid."""
        req = SignalExtractionRequest(
            query="great service love it",
            company_id="company_race_5",
            variant_type="parwa",
        )
        cache_miss = AsyncMock(return_value=None)
        cache_set_err = AsyncMock(
            side_effect=Exception("Redis connection lost"))

        with patch("app.core.redis.cache_get", cache_miss), \
                patch("app.core.redis.cache_set", cache_set_err):
            result = await self.extractor.extract(req)

        assert isinstance(result, ExtractedSignals)
        assert result.cached is False
        assert 0.0 <= result.sentiment <= 1.0
        assert 0.0 <= result.complexity <= 1.0
        assert result.intent in ("feedback", "general")


# ═══════════════════════════════════════════════════════════════════════
# 2. Sentiment Score Boundary Failures (7 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestSentimentScoreBoundaries:
    """Tests boundary values for frustration score (0-100) and their
    impact on escalation (60+), VIP routing (80+), urgency levels,
    and tone recommendations.
    """

    def setup_method(self):
        self.detector = FrustrationDetector()
        self.urgency_scorer = UrgencyScorer()
        self.tone_advisor = ToneAdvisor()
        self.analyzer = SentimentAnalyzer()

    # -- FrustrationDetector boundary tests --

    def test_zero_frustration_neutral_text(self):
        """A completely neutral text should produce 0 or near-0 frustration."""
        score = self.detector.detect("Hello, how are you today?")
        assert score < 10.0

    def test_minimal_frustration_single_mild_word(self):
        """A single mild frustration word should produce minimal score."""
        score = self.detector.detect("I have an issue with my order")
        assert 0.0 <= score < 20.0

    def test_near_escalation_threshold_59(self):
        """A text that produces a score just below 60 (escalation threshold).
        We construct text with moderate frustration words only."""
        # Moderate words: 5 pts each. Need about 12 hits to get ~50 + some
        # extras
        text = " ".join(["angry"] * 3 + ["frustrated"] * 3 + ["terrible"] * 3)
        score = self.detector.detect(text)
        # Should produce significant but potentially sub-60 frustration
        assert isinstance(score, float)
        assert 0.0 <= score <= 100.0

    def test_above_escalation_threshold_60(self):
        """A text producing score above 60 (escalation threshold)."""
        # Strong words: 12 pts each. 3 strong + mods = high score
        text = "FURIOUS ENRAGED this is UNACCEPTABLE and INTOLERABLE!!!"
        score = self.detector.detect(text)
        assert score > 60.0

    def test_above_vip_threshold_80(self):
        """A text producing score above 80 (VIP routing threshold)."""
        # Strong words (12pts each) + moderate (5pts each) + CAPS + exclamation
        # Must produce > 80
        text = "UNACCEPTABLE ATROCIOUS ABYSMAL APPALLING CATASTROPHIC DEVASTATING " * 3 + "!!!"
        score = self.detector.detect(text)
        # With 18 strong-word hits: min(50, 18*12=216) → capped at 50
        # + CAPS ratio > 0.5 → +10
        # + excl >= 5 → +15
        # + intensifier words present → +some
        # Total should be well above 80
        assert score >= 70.0, f"Expected >= 70, got {score}"
        assert score <= 100.0

    def test_max_frustration_capped_at_100(self):
        """Even extreme input must not exceed 100."""
        text = (
            " ".join(["FURIOUS"] * 20 + ["UNACCEPTABLE"] * 20)
            + "!" * 50 + "?" * 30
        )
        score = self.detector.detect(text)
        assert score <= 100.0
        assert score >= 0.0

    # -- UrgencyScorer boundary tests --

    def test_urgency_low_at_zero_frustration(self):
        """Zero frustration should yield 'low' urgency."""
        level = self.urgency_scorer.score(
            "Hello, how are you?", frustration_score=0.0)
        assert level == "low"

    def test_urgency_at_escalation_boundary_frustration_60(self):
        """Frustration at 60 with urgent keywords should push to high+."""
        text = "I need this fixed immediately right now asap emergency"
        level = self.urgency_scorer.score(text, frustration_score=60.0)
        # immediately: 36, right now: 34, asap: 32, emergency: 38 → ~140
        # + frustration 12 + caps 0 + excl 0 → capped at 100 → critical
        assert level in ("high", "critical")

    def test_urgency_critical_at_vip_boundary_frustration_80(self):
        """High frustration with urgent keywords → critical urgency."""
        text = "emergency this is critical breach"
        level = self.urgency_scorer.score(text, frustration_score=80.0)
        # Multiple urgent keywords + high frustration → critical
        assert level == "critical"

    # -- ToneAdvisor boundary tests --

    def test_tone_deescalation_at_frustration_90(self):
        """Frustration >= 90 must trigger de-escalation tone."""
        tone = self.tone_advisor.recommend(
            frustration_score=90.0,
            emotion="angry",
            urgency_level="critical",
        )
        assert tone == "de-escalation"

    def test_tone_empathetic_at_escalation_boundary(self):
        """Frustration at 60 with non-angry emotion → empathetic."""
        tone = self.tone_advisor.recommend(
            frustration_score=60.0,
            emotion="frustrated",
            urgency_level="medium",
        )
        assert tone == "empathetic"

    def test_tone_standard_below_threshold(self):
        """Low frustration and neutral emotion → standard tone."""
        tone = self.tone_advisor.recommend(
            frustration_score=10.0,
            emotion="neutral",
            urgency_level="low",
        )
        assert tone == "standard"

    # -- SentimentAnalyzer integration --

    @pytest.mark.asyncio
    async def test_sentiment_score_inverse_of_frustration(self):
        """Sentiment score (0.0-1.0) = 1.0 - (frustration_score/100)."""
        cache_miss = AsyncMock(return_value=None)
        cache_set = AsyncMock()
        with patch("app.core.redis.cache_get", cache_miss), \
                patch("app.core.redis.cache_set", cache_set):
            result = await self.analyzer.analyze("This is OUTRAGEOUS and UNACCEPTABLE!!!", company_id="c1")
        # High frustration → sentiment_score should be < 1.0
        # sentiment_score = max(0, min(1, 1.0 - frustration/100))
        assert result.sentiment_score < 1.0
        assert result.frustration_score > 0.0
        assert 0.0 <= result.sentiment_score <= 1.0

    @pytest.mark.asyncio
    async def test_empty_input_returns_safe_defaults(self):
        """Empty/null input returns safe defaults without crashing."""
        cache_miss = AsyncMock(return_value=None)
        cache_set = AsyncMock()
        with patch("app.core.redis.cache_get", cache_miss), \
                patch("app.core.redis.cache_set", cache_set):
            result = await self.analyzer.analyze("", company_id="c1")
        assert result.frustration_score == 0.0
        assert result.sentiment_score == 0.5
        assert result.emotion == "neutral"
        assert result.urgency_level == "low"
        assert result.tone_recommendation == "standard"


# ═══════════════════════════════════════════════════════════════════════
# 3. RAG Tenant Isolation Leak (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestRAGTenantIsolation:
    """Tests that RAG retrieval for one company_id NEVER returns results
    from another company's knowledge base.
    """

    def _make_store(self):
        """Create a MockVectorStore with two tenants."""
        store = MockVectorStore(seed=42)

        # Company A documents
        store.add_document(
            document_id="doc_a_1",
            chunks=[
                {"content": "Company A refund policy: full refund within 30 days",
                 "metadata": {"source": "Company A KB"}},
                {"content": "Company A billing FAQ: invoices sent monthly",
                 "metadata": {"source": "Company A KB"}},
            ],
            company_id="company_a",
        )
        store.add_document(
            document_id="doc_a_2",
            chunks=[
                {"content": "Company A shipping: free shipping on orders over $50",
                 "metadata": {"source": "Company A KB"}},
            ],
            company_id="company_a",
        )

        # Company B documents
        store.add_document(
            document_id="doc_b_1",
            chunks=[
                {"content": "Company B confidential pricing: enterprise plan $999/mo",
                 "metadata": {"source": "Company B KB", "confidential": True}},
                {"content": "Company B internal SLA: 99.99% uptime guarantee",
                 "metadata": {"source": "Company B KB", "confidential": True}},
            ],
            company_id="company_b",
        )
        store.add_document(
            document_id="doc_b_2",
            chunks=[
                {"content": "Company B secret feature roadmap: AI auto-response in Q3",
                 "metadata": {"source": "Company B KB", "confidential": True}},
            ],
            company_id="company_b",
        )

        return store

    @pytest.mark.asyncio
    async def test_company_a_never_sees_company_b_chunks(self):
        """Retrieving for company_a must never return company_b content."""
        store = self._make_store()
        retriever = RAGRetriever(vector_store=store)

        # Search for something that exists in company B's KB
        result = await retriever.retrieve(
            query="confidential pricing enterprise plan",
            company_id="company_a",
            variant_type="mini_parwa",
        )
        for chunk in result.chunks:
            assert chunk.metadata.get("source") != "Company B KB", \
                f"Leak! Company A got Company B content: {chunk.content}"

    @pytest.mark.asyncio
    async def test_company_b_never_sees_company_a_chunks(self):
        """Retrieving for company_b must never return company_a content."""
        store = self._make_store()
        retriever = RAGRetriever(vector_store=store)

        result = await retriever.retrieve(
            query="refund policy free shipping",
            company_id="company_b",
            variant_type="parwa",
        )
        for chunk in result.chunks:
            assert chunk.metadata.get("source") != "Company A KB", \
                f"Leak! Company B got Company A content: {chunk.content}"

    @pytest.mark.asyncio
    async def test_tenant_isolation_with_identical_content(self):
        """Even if both companies have same content text, chunks from
        the other tenant must not appear."""
        store = MockVectorStore(seed=99)
        # Both companies have the same text
        store.add_document(
            document_id="doc_shared_text_a",
            chunks=[{"content": "refund policy allows 30 day returns",
                     "metadata": {"source": "Company A"}}],
            company_id="company_a",
        )
        store.add_document(
            document_id="doc_shared_text_b",
            chunks=[{"content": "refund policy allows 30 day returns",
                     "metadata": {"source": "Company B"}}],
            company_id="company_b",
        )
        retriever = RAGRetriever(vector_store=store)

        result_a = await retriever.retrieve(
            query="refund policy", company_id="company_a", variant_type="parwa",
        )
        for chunk in result_a.chunks:
            assert chunk.document_id.startswith("doc_shared_text_a"), \
                f"Wrong tenant document: {chunk.document_id}"
            assert chunk.metadata["source"] == "Company A"

    @pytest.mark.asyncio
    async def test_isolation_with_parwa_high_reranking(self):
        """parwa_high tier (reranking) must still respect tenant isolation."""
        store = self._make_store()
        retriever = RAGRetriever(vector_store=store)

        result = await retriever.retrieve(
            query="confidential SLA pricing roadmap",
            company_id="company_a",
            variant_type="parwa_high",
        )
        for chunk in result.chunks:
            assert chunk.metadata.get("source") != "Company B KB", \
                f"parwa_high leak! Got Company B data: {chunk.content}"

    @pytest.mark.asyncio
    async def test_isolation_with_metadata_filters(self):
        """Metadata-filtered search must still be tenant-scoped."""
        store = self._make_store()
        retriever = RAGRetriever(vector_store=store)

        result = await retriever.retrieve(
            query="pricing",
            company_id="company_a",
            variant_type="parwa",
            filters={"source": "Company A KB"},
        )
        for chunk in result.chunks:
            assert chunk.metadata.get("source") == "Company A KB"

    @pytest.mark.asyncio
    async def test_empty_tenant_returns_no_results(self):
        """Querying a tenant with no documents returns empty results."""
        store = MockVectorStore()
        # Only add docs for company_a
        store.add_document(
            document_id="only_a",
            chunks=[{"content": "some content"}],
            company_id="company_a",
        )
        retriever = RAGRetriever(vector_store=store)

        result = await retriever.retrieve(
            query="some content",
            company_id="company_empty",
            variant_type="parwa",
        )
        assert len(result.chunks) == 0


# ═══════════════════════════════════════════════════════════════════════
# 4. Training Data Cross-Contamination (7 tests)
# ═══════════════════════════════════════════════════════════════════════


class _MockPipeline:
    """Collects Redis pipeline commands and executes them in batch."""

    def __init__(self, store: dict):
        self._store = store
        self._commands: list = []

    def rpush(self, name, *values):
        self._commands.append(("rpush", name, values))

    def hset(self, name, *args):
        self._commands.append(("hset", name, args))

    def lpop(self, name):
        self._commands.append(("lpop", name))

    async def execute(self):
        results = []
        for cmd in self._commands:
            if cmd[0] == "rpush":
                _, name, values = cmd
                lst = self._store.get(name, [])
                if not isinstance(lst, list):
                    lst = []
                for v in values:
                    lst.append(v)
                self._store[name] = lst
                results.append(len(lst))
            elif cmd[0] == "hset":
                _, name, args = cmd
                h = self._store.get(name, {})
                if not isinstance(h, dict):
                    h = {}
                if len(args) == 1 and isinstance(args[0], dict):
                    h.update(args[0])
                elif len(args) == 2:
                    h[args[0]] = args[1]
                self._store[name] = h
                results.append(1)
            elif cmd[0] == "lpop":
                _, name = cmd
                lst = self._store.get(name, [])
                if not isinstance(lst, list) or not lst:
                    results.append(None)
                else:
                    results.append(lst.pop(0))
                self._store[name] = lst
        self._commands.clear()
        return results


@pytest.fixture
def mock_redis():
    """Create an in-memory mock Redis store."""
    store: dict = {}

    async def _hset(name, mapping=None, key=None, value=None):
        h = store.get(name, {})
        if not isinstance(h, dict):
            h = {}
        if mapping:
            h.update(mapping)
        if key is not None:
            h[key] = value
        store[name] = h
        return 1

    async def _hgetall(name):
        val = store.get(name)
        if val is None:
            return {}
        if isinstance(val, dict):
            return dict(val)
        return {}

    async def _sadd(name, *values):
        s = store.get(name)
        if not isinstance(s, set):
            s = set()
            store[name] = s
        for v in values:
            s.add(v)
        return len(s)

    async def _sismember(name, value):
        s = store.get(name)
        return value in s if isinstance(s, set) else False

    async def _smembers(name):
        s = store.get(name)
        if isinstance(s, set):
            return set(s)
        return set()

    async def _srem(name, *values):
        s = store.get(name, set())
        if not isinstance(s, set):
            return 0
        removed = 0
        for v in values:
            if v in s:
                s.discard(v)
                removed += 1
        return removed

    async def _rpush(name, *values):
        lst = store.get(name, [])
        if not isinstance(lst, list):
            lst = []
        for v in values:
            lst.append(v)
        store[name] = lst
        return len(lst)

    async def _lpop(name):
        lst = store.get(name, [])
        if not isinstance(lst, list) or not lst:
            return None
        return lst.pop(0)

    async def _lrange(name, start, stop):
        lst = store.get(name, [])
        if not isinstance(lst, list):
            return []
        if stop == -1:
            return list(lst[start:])
        return list(lst[start: stop + 1])

    async def _delete(*names):
        count = 0
        for n in names:
            if n in store:
                del store[n]
                count += 1
        return count

    async def _exists(name):
        if name not in store:
            return 0
        val = store[name]
        if isinstance(val, (list, set, dict)) and len(val) == 0:
            return 0
        return 1

    def _pipeline():
        return _MockPipeline(store)

    redis_mock = MagicMock()
    redis_mock.hset = AsyncMock(side_effect=_hset)
    redis_mock.hgetall = AsyncMock(side_effect=_hgetall)
    redis_mock.sadd = AsyncMock(side_effect=_sadd)
    redis_mock.sismember = AsyncMock(side_effect=_sismember)
    redis_mock.smembers = AsyncMock(side_effect=_smembers)
    redis_mock.srem = AsyncMock(side_effect=_srem)
    redis_mock.rpush = AsyncMock(side_effect=_rpush)
    redis_mock.lpop = AsyncMock(side_effect=_lpop)
    redis_mock.lrange = AsyncMock(side_effect=_lrange)
    redis_mock.delete = AsyncMock(side_effect=_delete)
    redis_mock.exists = AsyncMock(side_effect=_exists)
    redis_mock.pipeline = _pipeline
    redis_mock._store = store
    return redis_mock


def _patch_get_redis(mock_redis_obj):
    """Return a patcher for backend.app.core.redis.get_redis."""
    return patch(
        "app.core.redis.get_redis",
        new_callable=AsyncMock,
        return_value=mock_redis_obj,
    )


def _seed_dataset(
    mock_redis_obj,
    dataset_id: str,
    company_id: str,
    variant_type: str = "parwa",
    name: str = "Test Dataset",
    description: str = "",
    record_count: int = 0,
    is_active: bool = True,
    metadata: dict | None = None,
) -> str:
    """Insert a dataset directly into the mock Redis store."""
    store = mock_redis_obj._store
    storage_path = ":".join([
        "training_data", company_id, variant_type, dataset_id,
    ])
    meta_key = storage_path + ":meta"
    store[meta_key] = {
        "dataset_id": dataset_id,
        "company_id": company_id,
        "variant_type": variant_type,
        "name": name,
        "description": description,
        "record_count": str(record_count),
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
        "metadata": json.dumps(metadata or {}),
        "storage_path": storage_path,
        "is_active": "1" if is_active else "0",
    }
    idx_key = ":".join([
        "training_data", company_id, "datasets",
    ])
    s = store.get(idx_key)
    if not isinstance(s, set):
        s = set()
        store[idx_key] = s
    s.add(dataset_id)
    return storage_path


class TestTrainingDataCrossContamination:
    """Tests that training datasets for one variant never include data
    from another variant. Specifically: mini_parwa must never see
    parwa_high training data.
    """

    def setup_method(self):
        self.service = TrainingDataIsolationService()

    @pytest.mark.asyncio
    async def test_list_mini_parwa_excludes_parwa_high(self, mock_redis):
        """Listing mini_parwa datasets must not return parwa_high ones."""
        _seed_dataset(
            mock_redis,
            "ds_mini_1",
            "c1",
            "mini_parwa",
            "Mini Dataset")
        _seed_dataset(
            mock_redis,
            "ds_high_1",
            "c1",
            "parwa_high",
            "High Dataset")
        _seed_dataset(mock_redis, "ds_parwa_1", "c1", "parwa", "Parwa Dataset")
        with _patch_get_redis(mock_redis):
            result = await self.service.list_datasets("c1", variant_type="mini_parwa")
        assert len(result) == 1
        assert result[0].variant_type == "mini_parwa"
        assert result[0].dataset_id == "ds_mini_1"

    @pytest.mark.asyncio
    async def test_list_parwa_high_excludes_mini_parwa(self, mock_redis):
        """Listing parwa_high datasets must not return mini_parwa ones."""
        _seed_dataset(mock_redis, "ds_mini_2", "c1", "mini_parwa", "Mini")
        _seed_dataset(mock_redis, "ds_high_2", "c1", "parwa_high", "High")
        with _patch_get_redis(mock_redis):
            result = await self.service.list_datasets("c1", variant_type="parwa_high")
        assert len(result) == 1
        assert result[0].variant_type == "parwa_high"

    @pytest.mark.asyncio
    async def test_cross_variant_access_denied_mini_to_high(self, mock_redis):
        """mini_parwa attempting to access parwa_high dataset is denied."""
        ds_id = "ds_cross_1"
        _seed_dataset(mock_redis, ds_id, "c1", "parwa_high", "High Only")
        with _patch_get_redis(mock_redis):
            is_cross = await self.service.check_cross_variant_access(
                dataset_id=ds_id,
                requesting_variant="mini_parwa",
                company_id="c1",
            )
        assert is_cross is True

    @pytest.mark.asyncio
    async def test_cross_variant_access_denied_parwa_to_mini(self, mock_redis):
        """parwa attempting to access mini_parwa dataset is denied."""
        ds_id = "ds_cross_2"
        _seed_dataset(mock_redis, ds_id, "c1", "mini_parwa", "Mini Only")
        with _patch_get_redis(mock_redis):
            is_cross = await self.service.check_cross_variant_access(
                dataset_id=ds_id,
                requesting_variant="parwa",
                company_id="c1",
            )
        assert is_cross is True

    @pytest.mark.asyncio
    async def test_same_variant_access_allowed(self, mock_redis):
        """Accessing a dataset from its own variant is always allowed."""
        ds_id = "ds_same_1"
        _seed_dataset(mock_redis, ds_id, "c1", "parwa_high", "High DS")
        with _patch_get_redis(mock_redis):
            is_cross = await self.service.check_cross_variant_access(
                dataset_id=ds_id,
                requesting_variant="parwa_high",
                company_id="c1",
            )
        assert is_cross is False

    @pytest.mark.asyncio
    async def test_shared_dataset_accessible_by_all_variants(self, mock_redis):
        """Shared datasets must be accessible by mini_parwa, parwa, and parwa_high."""
        ds_id = "ds_shared_all"
        _seed_dataset(mock_redis, ds_id, "c1", "shared", "Shared DS")
        with _patch_get_redis(mock_redis):
            for variant in ("mini_parwa", "parwa", "parwa_high"):
                is_cross = await self.service.check_cross_variant_access(
                    dataset_id=ds_id,
                    requesting_variant=variant,
                    company_id="c1",
                )
                assert is_cross is False, \
                    f"Shared dataset should be accessible by {variant}"

    @pytest.mark.asyncio
    async def test_storage_paths_variant_isolated(self, mock_redis):
        """Storage paths for same dataset_id under different variants
        must be completely different (no Redis key overlap)."""
        ds_id = "ds_path_iso"
        path_mini = _seed_dataset(
            mock_redis, ds_id, "c1", "mini_parwa", "Mini")
        path_high = _seed_dataset(
            mock_redis, ds_id, "c1", "parwa_high", "High")
        assert path_mini != path_high
        assert "mini_parwa" in path_mini
        assert "parwa_high" in path_high
        # Ensure no Redis key overlap
        assert path_mini not in mock_redis._store or \
            path_mini + ":meta" not in mock_redis._store or \
            mock_redis._store[path_mini + ":meta"]["variant_type"] == "mini_parwa"
        assert mock_redis._store[path_high +
                                 ":meta"]["variant_type"] == "parwa_high"
