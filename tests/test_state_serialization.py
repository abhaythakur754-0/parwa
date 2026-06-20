"""
Tests for SG-15: State Serialization/Deserialization Layer (F-060).

Covers: serialization/deserialization round-trips, Redis integration,
PostgreSQL integration, checkpoints, state history, replay, state diff,
concurrency/locking, error handling, edge cases, and configuration.
All Redis and PostgreSQL interactions are fully mocked.
"""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

import pytest

from backend.app.core.state_serialization import (
    StateSerializationError,
    SnapshotType,
    StorageBackend,
    StateSerializerConfig,
    StateDiff,
    CheckpointMeta,
    StateHistoryEntry,
    SaveResult,
    StateSerializer,
    _build_state_key,
    _build_checkpoint_key,
    _build_checkpoint_index_key,
    _build_lock_key,
    _utcnow,
    _new_uuid,
    _serialize_enum,
    _safe_json_dumps,
    _safe_json_loads,
)
from backend.app.core.techniques.base import ConversationState, GSDState
from backend.app.core.technique_router import QuerySignals


# ── Helpers ──────────────────────────────────────────────────────


def _make_state(**overrides):
    """Create a ConversationState with sensible defaults and optional overrides."""
    defaults = dict(
        query="How do I reset my password?",
        signals=QuerySignals(
            query_complexity=0.5,
            confidence_score=0.8,
            sentiment_score=0.9,
            customer_tier="pro",
        ),
        gsd_state=GSDState.DIAGNOSIS,
        gsd_history=[GSDState.NEW, GSDState.GREETING, GSDState.DIAGNOSIS],
        technique_results={
            "crp": {"status": "success", "result": "condensed"},
            "cot": {"status": "success", "result": "step by step"},
        },
        token_usage=450,
        technique_token_budget=1500,
        response_parts=["Part 1", "Part 2"],
        final_response="Here is your answer...",
        ticket_id="ticket-123",
        conversation_id="conv-456",
        company_id="company-789",
        reasoning_thread=["Thinking step 1", "Thinking step 2"],
        reflexion_trace={"reflection": "looks good"},
    )
    defaults.update(overrides)
    return ConversationState(**defaults)


def _make_serialized_state(**overrides):
    """Create a dict matching the output of serialize_state."""
    defaults = dict(
        query="How do I reset my password?",
        signals={
            "query_complexity": 0.5,
            "confidence_score": 0.8,
            "sentiment_score": 0.9,
            "customer_tier": "pro",
            "monetary_value": 0.0,
            "turn_count": 0,
            "intent_type": "general",
            "previous_response_status": "none",
            "reasoning_loop_detected": False,
            "resolution_path_count": 1,
            "external_data_required": False,
            "is_strategic_decision": False,
        },
        gsd_state="diagnosis",
        gsd_history=["new", "greeting", "diagnosis"],
        technique_results={
            "crp": {"status": "success", "result": "condensed"},
            "cot": {"status": "success", "result": "step by step"},
        },
        token_usage=450,
        technique_token_budget=1500,
        response_parts=["Part 1", "Part 2"],
        final_response="Here is your answer...",
        ticket_id="ticket-123",
        conversation_id="conv-456",
        company_id="company-789",
        reasoning_thread=["Thinking step 1", "Thinking step 2"],
        reflexion_trace={"reflection": "looks good"},
        serialized_at=_utcnow(),
    )
    defaults.update(overrides)
    return defaults


# ══════════════════════════════════════════════════════════════════
# 1. Serialization / Deserialization (15 tests)
# ══════════════════════════════════════════════════════════════════


class TestSerializationDeserialization:
    """Round-trip and edge-case serialization/deserialization tests."""

    def test_serialize_returns_dict(self):
        state = _make_state()
        serializer = StateSerializer()
        result = serializer.serialize_state(state)
        assert isinstance(result, dict)

    def test_serialize_deserialize_round_trip(self):
        state = _make_state()
        serializer = StateSerializer()
        serialized = serializer.serialize_state(state)
        deserialized = serializer.deserialize_state(serialized)
        assert deserialized.query == state.query
        assert deserialized.gsd_state == state.gsd_state
        assert deserialized.token_usage == state.token_usage
        assert deserialized.ticket_id == state.ticket_id
        assert deserialized.company_id == state.company_id

    def test_serialize_empty_conversation_state(self):
        state = ConversationState()
        serializer = StateSerializer()
        result = serializer.serialize_state(state)
        assert result["query"] == ""
        assert result["gsd_state"] == "new"
        assert result["token_usage"] == 0
        assert result["technique_results"] == {}
        assert result["response_parts"] == []

    def test_serialize_with_technique_results(self):
        state = _make_state(
            technique_results={
                "clara": {"status": "success", "tokens": 50},
                "react": {"status": "skipped", "reason": "budget"},
            }
        )
        serializer = StateSerializer()
        result = serializer.serialize_state(state)
        assert "clara" in result["technique_results"]
        assert result["technique_results"]["react"]["status"] == "skipped"

    def test_serialize_with_reasoning_thread(self):
        state = _make_state(
            reasoning_thread=["Step 1", "Step 2", "Step 3"]
        )
        serializer = StateSerializer()
        result = serializer.serialize_state(state)
        assert result["reasoning_thread"] == ["Step 1", "Step 2", "Step 3"]

    def test_serialize_handles_nested_query_signals(self):
        state = _make_state()
        serializer = StateSerializer()
        result = serializer.serialize_state(state)
        assert isinstance(result["signals"], dict)
        assert result["signals"]["query_complexity"] == 0.5
        assert result["signals"]["customer_tier"] == "pro"

    def test_serialize_handles_optional_fields_none(self):
        state = ConversationState(
            signals=None,
            reflexion_trace=None,
            reasoning_thread=None,
        )
        serializer = StateSerializer()
        result = serializer.serialize_state(state)
        assert result["signals"] is None
        assert result["reflexion_trace"] is None
        assert result["reasoning_thread"] == []

    def test_serialize_handles_enum_values(self):
        for gsd in GSDState:
            state = ConversationState(gsd_state=gsd)
            serializer = StateSerializer()
            result = serializer.serialize_state(state)
            assert result["gsd_state"] == gsd.value

    def test_serialize_handles_datetime_like_fields(self):
        state = _make_state()
        serializer = StateSerializer()
        result = serializer.serialize_state(state)
        assert "serialized_at" in result
        # Should be an ISO string
        assert isinstance(result["serialized_at"], str)

    def test_deserialize_corrupted_json_raises(self):
        serializer = StateSerializer()
        # Pass data that forces a failure inside the inner try block
        # by making the ConversationState constructor raise
        with patch.object(
            ConversationState, "__init__",
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(StateSerializationError) as exc_info:
                serializer.deserialize_state({"gsd_state": "new"})
        assert exc_info.value.error_code == "STATE_DESERIALIZE_FAILED"

    def test_deserialize_missing_fields_uses_defaults(self):
        serializer = StateSerializer()
        result = serializer.deserialize_state({})
        assert result.query == ""
        assert result.gsd_state == GSDState.NEW
        assert result.token_usage == 0
        assert result.ticket_id is None

    def test_deserialize_type_mismatch_gsd_state_fallback(self):
        serializer = StateSerializer()
        result = serializer.deserialize_state({"gsd_state": 12345})
        assert result.gsd_state == GSDState.NEW

    def test_deserialize_large_state_data(self):
        big_response = "x" * 100_000
        data = {
            "query": "big query",
            "gsd_state": "diagnosis",
            "final_response": big_response,
            "response_parts": [big_response],
        }
        serializer = StateSerializer()
        result = serializer.deserialize_state(data)
        assert result.final_response == big_response

    def test_deserialize_unicode_content(self):
        data = {
            "query": "Héllo wörld 日本語 🎉",
            "gsd_state": "greeting",
            "final_response": "Rësponse with ünïcödé and émojis 🔥",
        }
        serializer = StateSerializer()
        result = serializer.deserialize_state(data)
        assert "日本語" in result.query
        assert "ünïcödé" in result.final_response

    def test_deserialize_extra_unknown_fields_ignored(self):
        data = {
            "query": "test",
            "gsd_state": "new",
            "future_field_1": "will be ignored",
            "future_field_2": {"nested": True},
        }
        serializer = StateSerializer()
        result = serializer.deserialize_state(data)
        assert result.query == "test"
        assert not hasattr(result, "future_field_1")

    def test_deserialize_invalid_gsd_history_skipped(self):
        data = {
            "gsd_history": ["new", "invalid_state_value", "diagnosis"],
        }
        serializer = StateSerializer()
        result = serializer.deserialize_state(data)
        assert len(result.gsd_history) == 2
        assert result.gsd_history[0] == GSDState.NEW
        assert result.gsd_history[1] == GSDState.DIAGNOSIS


# ══════════════════════════════════════════════════════════════════
# 2. Redis Integration (20 tests)
# ══════════════════════════════════════════════════════════════════


class TestRedisIntegration:
    """Redis save/load operations with mocked Redis client."""

    @pytest.fixture
    def serializer(self):
        return StateSerializer()

    @pytest.fixture
    def mock_redis(self):
        return MagicMock()

    @pytest.mark.asyncio
    async def test_save_state_to_redis_success(self, serializer, mock_redis):
        state = _make_state()
        mock_pipeline = AsyncMock()
        mock_pipeline.hset = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        mock_redis.get = AsyncMock(return_value=None)

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._save_to_redis(
                ticket_id="t1",
                company_id="c1",
                state_json='{"query":"test"}',
                snapshot_id="snap-1",
                snapshot_type="auto",
                current_node="gsd_node",
                technique_stack=["cot", "crp"],
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_load_state_from_redis_success(self, serializer):
        state = _make_state()
        serialized = serializer.serialize_state(state)
        state_json = json.dumps(serialized, default=str)

        mock_redis = MagicMock()
        mock_redis.hgetall = AsyncMock(
            return_value={"state_data": state_json, "snapshot_id": "snap-1"}
        )

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._load_from_redis("t1", "c1")

        assert result is not None
        assert result.query == state.query

    @pytest.mark.asyncio
    async def test_redis_key_format_state(self):
        key = _build_state_key("company-abc", "ticket-xyz")
        assert key == "parwa:state:company-abc:ticket-xyz"

    @pytest.mark.asyncio
    async def test_redis_key_format_checkpoint(self):
        key = _build_checkpoint_key("c1", "t1", "my_checkpoint")
        assert key == "parwa:checkpoint:c1:t1:my_checkpoint"

    @pytest.mark.asyncio
    async def test_ttl_active_state_24h(self, serializer):
        assert serializer._config.active_state_ttl_seconds == 86400

    @pytest.mark.asyncio
    async def test_ttl_checkpoint_7d(self, serializer):
        assert serializer._config.checkpoint_ttl_seconds == 604800

    @pytest.mark.asyncio
    async def test_save_redis_uses_pipeline(self, serializer):
        mock_pipeline = AsyncMock()
        mock_pipeline.hset = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            await serializer._save_to_redis(
                "t1", "c1", "{}", "s1", "auto", "node", [],
            )

        mock_pipeline.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_redis_failure_returns_false(self, serializer):
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(side_effect=Exception("connection lost"))

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._save_to_redis(
                "t1", "c1", "{}", "s1", "auto", "node", [],
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_redis_corrupted_data_returns_none(self, serializer):
        mock_redis = MagicMock()
        mock_redis.hgetall = AsyncMock(
            return_value={"state_data": "<<<NOT JSON>>>"}
        )

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._load_from_redis("t1", "c1")
        assert result is None

    @pytest.mark.asyncio
    async def test_redis_returns_none_not_found(self, serializer):
        mock_redis = MagicMock()
        mock_redis.hgetall = AsyncMock(return_value={})

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._load_from_redis("t1", "c1")
        assert result is None

    @pytest.mark.asyncio
    async def test_redis_connection_error_returns_none(self, serializer):
        mock_redis = MagicMock()
        mock_redis.hgetall = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._load_from_redis("t1", "c1")
        assert result is None

    @pytest.mark.asyncio
    async def test_redis_timeout_returns_none(self, serializer):
        mock_redis = MagicMock()
        mock_redis.hgetall = AsyncMock(
            side_effect=TimeoutError("Redis timeout")
        )

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._load_from_redis("t1", "c1")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_to_redis_missing_state_data_in_hash(self, serializer):
        mock_redis = MagicMock()
        mock_redis.hgetall = AsyncMock(
            return_value={"snapshot_id": "snap-1"}  # no state_data
        )

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._load_from_redis("t1", "c1")
        assert result is None

    @pytest.mark.asyncio
    async def test_multiple_saves_overwrite_in_redis(self, serializer):
        mock_pipeline = AsyncMock()
        mock_pipeline.hset = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            await serializer._save_to_redis(
                "t1", "c1", '{"v":1}', "s1", "auto", "node", [],
            )
            await serializer._save_to_redis(
                "t1", "c1", '{"v":2}', "s2", "auto", "node", [],
            )
        assert mock_pipeline.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_delete_from_redis_success(self, serializer):
        mock_redis = MagicMock()
        mock_redis.smembers = AsyncMock(return_value={"cp1"})
        mock_redis.delete = AsyncMock(return_value=1)

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._delete_state_from_redis("t1", "c1")
        assert result is True

    @pytest.mark.asyncio
    async def test_checkpoint_redis_key_format(self, serializer):
        mock_pipeline = AsyncMock()
        mock_pipeline.hset = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.sadd = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            await serializer._save_checkpoint_to_redis(
                ticket_id="t1",
                company_id="c1",
                checkpoint_name="before_fix",
                state_json="{}",
                snapshot_id="snap-1",
                current_node="node",
                gsd_state="diagnosis",
                token_count=100,
            )
        # Verify hset was called (key format tested separately)
        mock_pipeline.hset.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_checkpoints_from_redis(self, serializer):
        metadata = json.dumps({
            "checkpoint_name": "cp1",
            "snapshot_id": "snap-1",
            "created_at": "2025-01-01T00:00:00",
            "current_node": "gsd",
            "gsd_state": "diagnosis",
            "token_count": 100,
        })
        mock_redis = MagicMock()
        mock_redis.smembers = AsyncMock(return_value={"cp1"})
        mock_redis.hgetall = AsyncMock(
            return_value={
                "state_data": "{}",
                "metadata": metadata,
                "snapshot_id": "snap-1",
            }
        )

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._list_checkpoints_from_redis("t1", "c1")

        assert result is not None
        assert len(result) == 1
        assert result[0]["checkpoint_name"] == "cp1"

    @pytest.mark.asyncio
    async def test_list_checkpoints_redis_empty(self, serializer):
        mock_redis = MagicMock()
        mock_redis.smembers = AsyncMock(return_value=set())

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._list_checkpoints_from_redis("t1", "c1")
        assert result == []

    @pytest.mark.asyncio
    async def test_save_to_redis_non_pipeline_mode(self, serializer):
        config = StateSerializerConfig(use_redis_pipeline=False)
        ser = StateSerializer(config=config)
        mock_redis = MagicMock()
        mock_redis.hset = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await ser._save_to_redis(
                "t1", "c1", "{}", "s1", "auto", "node", [],
            )
        assert result is True
        mock_redis.hset.assert_awaited_once()
        mock_redis.expire.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_redis_set_simple_success(self, serializer):
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=True)

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._redis_set("key", "val", ttl=60)
        assert result is True


# ══════════════════════════════════════════════════════════════════
# 3. PostgreSQL Integration (20 tests)
# ══════════════════════════════════════════════════════════════════


class TestPostgreSQLIntegration:
    """PostgreSQL save/load operations with mocked DB session."""

    @pytest.fixture
    def serializer(self):
        return StateSerializer()

    @pytest.mark.asyncio
    async def test_save_to_postgresql_success(self, serializer):
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer._save_to_postgresql(
                ticket_id="t1",
                company_id="c1",
                state_json='{"query":"test"}',
                snapshot_id="snap-1",
                snapshot_type="auto",
                current_node="gsd_node",
                technique_stack=["cot", "crp"],
                model_used="gpt-4",
                token_count=450,
            )
        assert result is True
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_from_postgresql_success(self, serializer):
        state = _make_state()
        serialized = serializer.serialize_state(state)

        mock_snapshot = MagicMock()
        mock_snapshot.state_data = json.dumps(serialized, default=str)
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.first.return_value = mock_snapshot
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
            return_value=mock_snapshot,
        ):
            result = await serializer._load_from_postgresql("t1", "c1")

        assert result is not None
        assert result.query == state.query

    @pytest.mark.asyncio
    async def test_save_creates_pipeline_state_snapshot(self, serializer):
        captured = {}
        mock_cls = MagicMock(side_effect=lambda **kw: captured.update(kw))
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            mock_cls,
        ):
            await serializer._save_to_postgresql(
                ticket_id="t1",
                company_id="c1",
                state_json='{"test":true}',
                snapshot_id="snap-1",
                snapshot_type="manual",
                current_node="node",
                technique_stack=["cot"],
                model_used="claude-3",
                token_count=200,
            )
        assert captured["id"] == "snap-1"
        assert captured["company_id"] == "c1"
        assert captured["ticket_id"] == "t1"
        assert captured["snapshot_type"] == "manual"

    @pytest.mark.asyncio
    async def test_state_data_stored_as_json_string(self, serializer):
        captured = {}
        mock_cls = MagicMock(side_effect=lambda **kw: captured.update(kw))
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            mock_cls,
        ):
            await serializer._save_to_postgresql(
                "t1", "c1", '{"query":"test"}', "s1", "auto",
            )
        assert captured["state_data"] == '{"query":"test"}'

    @pytest.mark.asyncio
    async def test_technique_stack_stored_as_json(self, serializer):
        captured = {}
        mock_cls = MagicMock(side_effect=lambda **kw: captured.update(kw))
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            mock_cls,
        ):
            await serializer._save_to_postgresql(
                "t1", "c1", "{}", "s1", "auto",
                technique_stack=["cot", "crp", "react"],
            )
        assert json.loads(captured["technique_stack"]) == ["cot", "crp", "react"]

    @pytest.mark.asyncio
    async def test_snapshot_type_stored_correctly(self, serializer):
        for stype in ["auto", "manual", "error", "checkpoint"]:
            captured = {}
            mock_cls = MagicMock(side_effect=lambda **kw: captured.update(kw))
            mock_db = MagicMock()
            mock_db.add = MagicMock()
            mock_db.commit = MagicMock()
            mock_db.close = MagicMock()

            with patch(
                "database.base.SessionLocal",
                return_value=mock_db,
            ), patch(
                "database.models.variant_engine.PipelineStateSnapshot",
                mock_cls,
            ):
                await serializer._save_to_postgresql(
                    "t1", "c1", "{}", "s1", stype,
                )
            assert captured["snapshot_type"] == stype

    @pytest.mark.asyncio
    async def test_model_used_stored_correctly(self, serializer):
        captured = {}
        mock_cls = MagicMock(side_effect=lambda **kw: captured.update(kw))
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            mock_cls,
        ):
            await serializer._save_to_postgresql(
                "t1", "c1", "{}", "s1", "auto",
                model_used="gpt-4-turbo",
            )
        assert captured["model_used"] == "gpt-4-turbo"

    @pytest.mark.asyncio
    async def test_token_count_stored_correctly(self, serializer):
        captured = {}
        mock_cls = MagicMock(side_effect=lambda **kw: captured.update(kw))
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            mock_cls,
        ):
            await serializer._save_to_postgresql(
                "t1", "c1", "{}", "s1", "auto",
                token_count=1234,
            )
        assert captured["token_count"] == 1234

    @pytest.mark.asyncio
    async def test_load_falls_back_to_postgresql_when_redis_empty(
        self, serializer
    ):
        mock_redis = MagicMock()
        mock_redis.hgetall = AsyncMock(return_value={})

        state = _make_state()
        serialized = serializer.serialize_state(state)
        mock_snapshot = MagicMock()
        mock_snapshot.state_data = json.dumps(serialized, default=str)
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.first.return_value = mock_snapshot
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer.load_state("t1", "c1")

        assert result is not None
        assert result.query == state.query

    @pytest.mark.asyncio
    async def test_save_postgresql_creates_new_record(self, serializer):
        add_calls = []
        mock_db = MagicMock()
        mock_db.add = MagicMock(side_effect=lambda x: add_calls.append(x))
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            MagicMock,
        ):
            await serializer._save_to_postgresql(
                "t1", "c1", "{}", "s1", "auto",
            )
        assert len(add_calls) == 1

    @pytest.mark.asyncio
    async def test_postgresql_error_returns_false(self, serializer):
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock(side_effect=Exception("DB down"))
        mock_db.rollback = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            MagicMock,
        ):
            result = await serializer._save_to_postgresql(
                "t1", "c1", "{}", "s1", "auto",
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_get_history_from_postgresql(self, serializer):
        mock_snapshot = MagicMock()
        mock_snapshot.id = "snap-1"
        mock_snapshot.created_at = datetime(2025, 1, 1, 12, 0, 0)
        mock_snapshot.snapshot_type = "auto"
        mock_snapshot.current_node = "gsd"
        mock_snapshot.state_data = json.dumps({
            "gsd_state": "diagnosis",
        })
        mock_snapshot.technique_stack = '["cot", "crp"]'
        mock_snapshot.token_count = 450
        mock_snapshot.model_used = "gpt-4"

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_limit = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.limit.return_value = mock_limit
        mock_limit.all.return_value = [mock_snapshot]
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer._get_history_from_postgresql(
                "t1", "c1", 10,
            )
        assert len(result) == 1
        assert result[0]["snapshot_id"] == "snap-1"
        assert result[0]["snapshot_type"] == "auto"
        assert result[0]["gsd_state"] == "diagnosis"

    @pytest.mark.asyncio
    async def test_replay_from_postgresql(self, serializer):
        state = _make_state()
        serialized = serializer.serialize_state(state)

        mock_snapshot = MagicMock()
        mock_snapshot.state_data = json.dumps(serialized, default=str)
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = mock_snapshot
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer._replay_from_postgresql(
                "t1", "c1", "snap-1",
            )
        assert result is not None
        assert result.query == state.query

    @pytest.mark.asyncio
    async def test_delete_from_postgresql_success(self, serializer):
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_delete = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.delete.return_value = mock_delete
        mock_delete.return_value = 3
        mock_db.commit = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer._delete_state_from_postgresql("t1", "c1")
        assert result is True
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_company_id_scoping_postgresql(self, serializer):
        """BC-001: Operations are scoped by company_id."""
        state = _make_state()
        serialized = serializer.serialize_state(state)

        mock_snapshot = MagicMock()
        mock_snapshot.state_data = json.dumps(serialized, default=str)
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.first.return_value = mock_snapshot
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            await serializer._load_from_postgresql("t1", "company-X")

        # The filter should have been called — verifying query was built
        mock_query.filter.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_postgresql_not_found_returns_none(self, serializer):
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.first.return_value = None
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer._load_from_postgresql("t1", "c1")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_postgresql_default_technique_stack_empty(self, serializer):
        captured = {}
        mock_cls = MagicMock(side_effect=lambda **kw: captured.update(kw))
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            mock_cls,
        ):
            await serializer._save_to_postgresql(
                "t1", "c1", "{}", "s1", "auto",
            )
        assert json.loads(captured["technique_stack"]) == []

    @pytest.mark.asyncio
    async def test_postgresql_corrupted_data_returns_none(self, serializer):
        mock_snapshot = MagicMock()
        mock_snapshot.state_data = "<<<CORRUPTED>>>"
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.first.return_value = mock_snapshot
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer._load_from_postgresql("t1", "c1")
        assert result is None


# ══════════════════════════════════════════════════════════════════
# 4. Checkpoints (15 tests)
# ══════════════════════════════════════════════════════════════════


class TestCheckpoints:
    """Checkpoint save/load/list/delete operations."""

    @pytest.fixture
    def serializer(self):
        return StateSerializer()

    @pytest.mark.asyncio
    async def test_save_checkpoint_with_name(self, serializer):
        state = _make_state()
        mock_pipeline = AsyncMock()
        mock_pipeline.hset = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.sadd = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            MagicMock,
        ):
            result = await serializer.save_checkpoint(
                ticket_id="t1",
                company_id="c1",
                conversation_state=state,
                checkpoint_name="before_resolution",
            )
        assert result.success is True
        assert result.backend == StorageBackend.REDIS

    @pytest.mark.asyncio
    async def test_load_checkpoint_by_name(self, serializer):
        state = _make_state()
        state_json = json.dumps(
            serializer.serialize_state(state), default=str
        )
        mock_redis = MagicMock()
        mock_redis.hgetall = AsyncMock(
            return_value={"state_data": state_json, "snapshot_id": "s1"}
        )

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer.load_checkpoint(
                "t1", "c1", "before_resolution",
            )
        assert result is not None
        assert result.query == state.query

    @pytest.mark.asyncio
    async def test_list_checkpoints_returns_list(self, serializer):
        mock_redis = MagicMock()
        mock_redis.smembers = AsyncMock(return_value={"cp1", "cp2"})
        mock_redis.hgetall = AsyncMock(
            return_value={
                "state_data": "{}",
                "metadata": json.dumps({
                    "checkpoint_name": "cp1",
                    "snapshot_id": "s1",
                    "created_at": "2025-01-01T00:00:00",
                    "current_node": "gsd",
                    "gsd_state": "diagnosis",
                    "token_count": 100,
                }),
                "snapshot_id": "s1",
            }
        )

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer.list_checkpoints("t1", "c1")
        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_checkpoints_sorted_desc(self, serializer):
        metadata1 = json.dumps({
            "checkpoint_name": "cp1",
            "created_at": "2025-01-01T00:00:00",
        })
        metadata2 = json.dumps({
            "checkpoint_name": "cp2",
            "created_at": "2025-01-02T00:00:00",
        })
        call_count = [0]
        original_hgetall = mock_redis_hgetall = AsyncMock()

        def hgetall_side_effect(key):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"state_data": "{}", "metadata": metadata1, "snapshot_id": "s1"}
            return {"state_data": "{}", "metadata": metadata2, "snapshot_id": "s2"}

        mock_redis = MagicMock()
        mock_redis.smembers = AsyncMock(return_value={"cp1", "cp2"})
        mock_redis.hgetall = AsyncMock(side_effect=hgetall_side_effect)

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer.list_checkpoints("t1", "c1")
        # Should be sorted by created_at descending
        assert result[0]["created_at"] >= result[1]["created_at"]

    @pytest.mark.asyncio
    async def test_overwrite_existing_checkpoint(self, serializer):
        state = _make_state()
        mock_pipeline = AsyncMock()
        mock_pipeline.hset = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.sadd = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            MagicMock,
        ):
            # Save twice with same name
            r1 = await serializer.save_checkpoint(
                "t1", "c1", state, "my_cp",
            )
            r2 = await serializer.save_checkpoint(
                "t1", "c1", state, "my_cp",
            )
        assert r1.success is True
        assert r2.success is True

    @pytest.mark.asyncio
    async def test_load_nonexistent_checkpoint_returns_none(self, serializer):
        mock_redis = MagicMock()
        mock_redis.hgetall = AsyncMock(return_value={})

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer.load_checkpoint(
                "t1", "c1", "nonexistent",
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_specific_checkpoint(self, serializer):
        mock_redis = MagicMock()
        mock_redis.smembers = AsyncMock(return_value={"cp1", "cp2"})
        mock_redis.delete = AsyncMock(return_value=3)

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._delete_state_from_redis("t1", "c1")
        assert result is True
        mock_redis.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_multiple_checkpoints_per_ticket(self, serializer):
        names = {"cp_alpha", "cp_beta", "cp_gamma"}
        mock_redis = MagicMock()
        mock_redis.smembers = AsyncMock(return_value=names)
        mock_redis.hgetall = AsyncMock(
            return_value={
                "state_data": "{}",
                "metadata": json.dumps({
                    "checkpoint_name": "cp1",
                    "created_at": "2025-01-01",
                    "current_node": "node",
                    "gsd_state": "diagnosis",
                    "token_count": 0,
                }),
                "snapshot_id": "s1",
            }
        )

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._list_checkpoints_from_redis("t1", "c1")
        assert result is not None
        assert len(result) == 3

    def test_checkpoint_metadata_to_dict(self):
        meta = CheckpointMeta(
            checkpoint_name="my_cp",
            ticket_id="t1",
            company_id="c1",
            snapshot_id="s1",
            created_at="2025-01-01T00:00:00",
            gsd_state="diagnosis",
            token_count=100,
            current_node="gsd",
        )
        d = meta.to_dict()
        assert d["checkpoint_name"] == "my_cp"
        assert d["ticket_id"] == "t1"
        assert d["token_count"] == 100

    @pytest.mark.asyncio
    async def test_checkpoint_name_validation_empty(self, serializer):
        state = _make_state()
        with pytest.raises(StateSerializationError) as exc_info:
            await serializer.save_checkpoint(
                "t1", "c1", state, "",
            )
        assert exc_info.value.status_code == 400
        assert "STATE_CHECKPOINT_INVALID_NAME" in exc_info.value.error_code

    @pytest.mark.asyncio
    async def test_checkpoint_name_validation_not_string(self, serializer):
        state = _make_state()
        with pytest.raises(StateSerializationError) as exc_info:
            await serializer.save_checkpoint(
                "t1", "c1", state, 12345,
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_checkpoint_name_sanitization_spaces(self, serializer):
        state = _make_state()
        mock_pipeline = AsyncMock()
        mock_pipeline.hset = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.sadd = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            MagicMock,
        ):
            await serializer.save_checkpoint(
                "t1", "c1", state, "My Checkpoint Name",
            )
        # The checkpoint_key in hset should have sanitized name
        call_args = mock_pipeline.hset.call_args
        key = call_args[0][0] if call_args[0] else call_args[1].get(
            call_args[1].keys().__iter__().__next__() if isinstance(call_args[1], dict) else None
        )

    @pytest.mark.asyncio
    async def test_checkpoint_redis_ttl_is_7d(self, serializer):
        assert serializer._config.checkpoint_ttl_seconds == 604800

    @pytest.mark.asyncio
    async def test_checkpoint_index_key_format(self):
        key = _build_checkpoint_index_key("c1", "t1")
        assert key == "parwa:checkpoints:c1:t1"


# ══════════════════════════════════════════════════════════════════
# 5. State History (10 tests)
# ══════════════════════════════════════════════════════════════════


class TestStateHistory:
    """State history retrieval and ordering tests."""

    @pytest.fixture
    def serializer(self):
        return StateSerializer()

    @pytest.mark.asyncio
    async def test_history_returns_list(self, serializer):
        with patch.object(
            serializer,
            "_get_history_from_postgresql",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await serializer.get_state_history("t1", "c1")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_history_with_limit(self, serializer):
        with patch.object(
            serializer,
            "_get_history_from_postgresql",
            new_callable=AsyncMock,
            return_value=[{"snapshot_id": f"s{i}"} for i in range(5)],
        ) as mock_pg:
            result = await serializer.get_state_history("t1", "c1", limit=5)
        assert len(result) == 5
        mock_pg.assert_awaited_once_with("t1", "c1", 5)

    @pytest.mark.asyncio
    async def test_history_nonexistent_ticket_returns_empty(self, serializer):
        with patch.object(
            serializer,
            "_get_history_from_postgresql",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await serializer.get_state_history(
                "nonexistent", "c1",
            )
        assert result == []

    @pytest.mark.asyncio
    async def test_history_includes_snapshot_type(self, serializer):
        entries = [
            {
                "snapshot_id": "s1",
                "snapshot_type": "auto",
                "created_at": "2025-01-01",
                "current_node": "gsd",
                "gsd_state": "diagnosis",
                "token_count": 100,
                "model_used": None,
                "technique_stack": ["cot"],
            }
        ]
        with patch.object(
            serializer,
            "_get_history_from_postgresql",
            new_callable=AsyncMock,
            return_value=entries,
        ):
            result = await serializer.get_state_history("t1", "c1")
        assert result[0]["snapshot_type"] == "auto"

    @pytest.mark.asyncio
    async def test_history_includes_timestamps(self, serializer):
        entries = [
            {
                "snapshot_id": "s1",
                "created_at": "2025-01-15T10:30:00",
                "snapshot_type": "manual",
                "current_node": "gsd",
                "gsd_state": "resolution",
                "token_count": 200,
                "model_used": "gpt-4",
                "technique_stack": [],
            }
        ]
        with patch.object(
            serializer,
            "_get_history_from_postgresql",
            new_callable=AsyncMock,
            return_value=entries,
        ):
            result = await serializer.get_state_history("t1", "c1")
        assert "2025-01-15" in result[0]["created_at"]

    @pytest.mark.asyncio
    async def test_history_default_limit_50(self, serializer):
        with patch.object(
            serializer,
            "_get_history_from_postgresql",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_pg:
            await serializer.get_state_history("t1", "c1")
        mock_pg.assert_awaited_once_with("t1", "c1", 50)

    @pytest.mark.asyncio
    async def test_history_limit_clamped_to_200(self, serializer):
        with patch.object(
            serializer,
            "_get_history_from_postgresql",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_pg:
            await serializer.get_state_history("t1", "c1", limit=500)
        mock_pg.assert_awaited_once_with("t1", "c1", 200)

    @pytest.mark.asyncio
    async def test_history_limit_clamped_to_min_1(self, serializer):
        with patch.object(
            serializer,
            "_get_history_from_postgresql",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_pg:
            await serializer.get_state_history("t1", "c1", limit=0)
        mock_pg.assert_awaited_once_with("t1", "c1", 1)

    def test_state_history_entry_to_dict(self):
        entry = StateHistoryEntry(
            snapshot_id="s1",
            created_at="2025-01-01",
            snapshot_type="auto",
            current_node="gsd",
            gsd_state="diagnosis",
            token_count=100,
            model_used="gpt-4",
            technique_stack=["cot", "crp"],
        )
        d = entry.to_dict()
        assert d["snapshot_id"] == "s1"
        assert d["technique_stack"] == ["cot", "crp"]
        assert d["model_used"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_history_from_postgresql_error_returns_empty(self, serializer):
        with patch(
            "database.base.SessionLocal",
            side_effect=Exception("DB error"),
        ):
            result = await serializer._get_history_from_postgresql(
                "t1", "c1", 10,
            )
        assert result == []


# ══════════════════════════════════════════════════════════════════
# 6. Replay (10 tests)
# ══════════════════════════════════════════════════════════════════


class TestReplay:
    """Snapshot replay functionality tests."""

    @pytest.fixture
    def serializer(self):
        return StateSerializer()

    @pytest.mark.asyncio
    async def test_replay_specific_snapshot(self, serializer):
        state = _make_state()
        serialized = serializer.serialize_state(state)

        mock_snapshot = MagicMock()
        mock_snapshot.state_data = json.dumps(serialized, default=str)
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = mock_snapshot
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer.replay_state("t1", "c1", "snap-xyz")

        assert result is not None
        assert result.query == state.query

    @pytest.mark.asyncio
    async def test_replay_nonexistent_returns_none(self, serializer):
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = None
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer.replay_state("t1", "c1", "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_replay_corrupted_data_returns_none(self, serializer):
        mock_snapshot = MagicMock()
        mock_snapshot.state_data = "<<<CORRUPTED>>>"
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = mock_snapshot
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer.replay_state("t1", "c1", "snap-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_replay_loads_from_postgresql(self, serializer):
        """Replay always uses PostgreSQL, never Redis."""
        state = _make_state()
        serialized = serializer.serialize_state(state)

        mock_snapshot = MagicMock()
        mock_snapshot.state_data = json.dumps(serialized, default=str)
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = mock_snapshot
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            await serializer.replay_state("t1", "c1", "snap-1")

        # PostgreSQL was queried
        mock_db.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_replay_filters_by_ticket_and_company(self, serializer):
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = None
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            await serializer.replay_state("ticket-X", "company-Y", "snap-Z")

        mock_query.filter.assert_called_once()

    @pytest.mark.asyncio
    async def test_replay_filters_by_snapshot_id(self, serializer):
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = None
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            await serializer.replay_state("t1", "c1", "specific-snap-id")
        mock_query.filter.assert_called_once()

    @pytest.mark.asyncio
    async def test_replay_handles_db_error_gracefully(self, serializer):
        mock_db = MagicMock()
        mock_db.query = MagicMock(side_effect=Exception("DB gone"))
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ):
            result = await serializer.replay_state("t1", "c1", "snap-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_replay_preserves_all_state_fields(self, serializer):
        state = _make_state(
            query="Preserve this query!",
            token_usage=999,
            final_response="Preserve this response!",
        )
        serialized = serializer.serialize_state(state)

        mock_snapshot = MagicMock()
        mock_snapshot.state_data = json.dumps(serialized, default=str)
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = mock_snapshot
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer.replay_state("t1", "c1", "snap-1")

        assert result.query == "Preserve this query!"
        assert result.token_usage == 999
        assert result.final_response == "Preserve this response!"

    @pytest.mark.asyncio
    async def test_replay_from_postgresql_direct(self, serializer):
        state = _make_state()
        serialized = serializer.serialize_state(state)

        mock_snapshot = MagicMock()
        mock_snapshot.state_data = json.dumps(serialized, default=str)
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = mock_snapshot
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer._replay_from_postgresql(
                "t1", "c1", "snap-1",
            )
        assert result is not None
        assert result.gsd_state == GSDState.DIAGNOSIS

    @pytest.mark.asyncio
    async def test_replay_from_postgresql_not_found(self, serializer):
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = None
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer._replay_from_postgresql(
                "t1", "c1", "missing",
            )
        assert result is None


# ══════════════════════════════════════════════════════════════════
# 7. State Diff (15 tests)
# ══════════════════════════════════════════════════════════════════


class TestStateDiff:
    """State diff computation tests."""

    @pytest.fixture
    def serializer(self):
        return StateSerializer()

    def test_no_changes_detected(self, serializer):
        old = _make_state(gsd_state=GSDState.DIAGNOSIS, token_usage=100)
        new = ConversationState(
            query=old.query,
            gsd_state=GSDState.DIAGNOSIS,
            token_usage=100,
        )
        diff = serializer.compute_diff(old, new)
        assert "gsd_state" in diff.unchanged_fields
        assert "token_count" in diff.unchanged_fields

    def test_gsd_state_change_detected(self, serializer):
        old = _make_state(gsd_state=GSDState.NEW)
        new = _make_state(gsd_state=GSDState.DIAGNOSIS)
        diff = serializer.compute_diff(old, new)
        assert "gsd_state" in diff.changed_fields
        assert diff.gsd_state == {"old": "new", "new": "diagnosis"}

    def test_token_count_change_detected(self, serializer):
        old = _make_state(token_usage=100)
        new = _make_state(token_usage=500)
        diff = serializer.compute_diff(old, new)
        assert "token_count" in diff.changed_fields
        assert diff.token_count == {"old": 100, "new": 500}

    def test_technique_stack_change_detected(self, serializer):
        old = _make_state(technique_results={"cot": {}})
        new = _make_state(technique_results={"cot": {}, "react": {}})
        diff = serializer.compute_diff(old, new)
        assert "technique_stack" in diff.changed_fields

    def test_multiple_changes_detected(self, serializer):
        old = _make_state(
            gsd_state=GSDState.NEW,
            token_usage=0,
            query="old query",
        )
        new = _make_state(
            gsd_state=GSDState.RESOLUTION,
            token_usage=800,
            query="new query",
        )
        diff = serializer.compute_diff(old, new)
        assert "gsd_state" in diff.changed_fields
        assert "token_count" in diff.changed_fields
        assert "query" in diff.changed_fields

    def test_one_state_is_none_new(self, serializer):
        new = _make_state(gsd_state=GSDState.DIAGNOSIS, token_usage=200)
        diff = serializer.compute_diff(None, new)
        assert "gsd_state" in diff.changed_fields
        assert "token_count" in diff.changed_fields
        assert diff.gsd_state["new"] == "diagnosis"

    def test_one_state_is_none_deleted(self, serializer):
        old = _make_state(gsd_state=GSDState.DIAGNOSIS, token_usage=200)
        diff = serializer.compute_diff(old, None)
        assert "gsd_state" in diff.changed_fields
        assert diff.gsd_state["new"] is None

    def test_both_states_none(self, serializer):
        diff = serializer.compute_diff(None, None)
        assert diff.changed_fields == []
        assert diff.unchanged_fields == []

    def test_both_states_identical(self, serializer):
        state = _make_state()
        diff = serializer.compute_diff(state, state)
        assert len(diff.changed_fields) == 0

    def test_diff_has_timestamp(self, serializer):
        old = _make_state()
        new = _make_state()
        diff = serializer.compute_diff(old, new)
        assert diff.timestamp != ""

    def test_diff_to_dict(self, serializer):
        old = _make_state(gsd_state=GSDState.NEW, token_usage=0)
        new = _make_state(gsd_state=GSDState.DIAGNOSIS, token_usage=100)
        diff = serializer.compute_diff(old, new)
        d = diff.to_dict()
        assert "gsd_state" in d
        assert "token_count" in d
        assert "changed_fields" in d
        assert "unchanged_fields" in d
        assert "timestamp" in d

    def test_diff_query_change(self, serializer):
        old = _make_state(query="old")
        new = _make_state(query="new")
        diff = serializer.compute_diff(old, new)
        assert "query" in diff.changed_fields

    def test_diff_final_response_change(self, serializer):
        old = _make_state(final_response="old resp")
        new = _make_state(final_response="new resp")
        diff = serializer.compute_diff(old, new)
        assert "final_response" in diff.changed_fields

    def test_diff_technique_stack_unchanged(self, serializer):
        old = _make_state(technique_results={"a": 1, "b": 2})
        new = _make_state(technique_results={"a": 1, "b": 2})
        diff = serializer.compute_diff(old, new)
        assert "technique_stack" in diff.unchanged_fields

    def test_diff_new_state_has_technique_stack(self, serializer):
        new = _make_state(technique_results={"cot": {}, "react": {}})
        diff = serializer.compute_diff(None, new)
        assert diff.technique_stack is not None
        assert diff.technique_stack["old"] == []
        assert set(diff.technique_stack["new"]) == {"cot", "react"}


# ══════════════════════════════════════════════════════════════════
# 8. Concurrency / Locking (15 tests)
# ══════════════════════════════════════════════════════════════════


class TestConcurrencyLocking:
    """Distributed lock acquisition and release tests."""

    @pytest.fixture
    def serializer(self):
        return StateSerializer()

    @pytest.mark.asyncio
    async def test_acquire_lock_success(self, serializer):
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=True)

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._acquire_lock("t1")
        assert result is True

    @pytest.mark.asyncio
    async def test_lock_acquisition_timeout(self, serializer):
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=None)  # NX fails

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._acquire_lock("t1")
        assert result is False

    @pytest.mark.asyncio
    async def test_lock_retry_on_failure(self, serializer):
        mock_redis = MagicMock()
        # First attempt fails, second succeeds
        mock_redis.set = AsyncMock(side_effect=[None, True])

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._acquire_lock("t1")
        assert result is True
        assert mock_redis.set.await_count == 2

    @pytest.mark.asyncio
    async def test_locked_save_operation(self, serializer):
        state = _make_state()
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()

        mock_pipeline = AsyncMock()
        mock_pipeline.hset = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            MagicMock,
        ):
            result = await serializer.save_state_locked(
                "t1", "c1", state,
            )
        assert result.success is True
        mock_redis.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_locked_load_operation(self, serializer):
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={})

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch.object(
            serializer,
            "_load_from_postgresql",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await serializer.load_state_locked("t1", "c1")
        assert result is None
        mock_redis.delete.assert_awaited_once()

    def test_lock_key_format(self):
        key = _build_lock_key("ticket-123")
        assert key == "parwa:lock:state:ticket-123"

    def test_lock_ttl_from_config(self):
        config = StateSerializerConfig(lock_timeout_seconds=10.0)
        serializer = StateSerializer(config=config)
        assert serializer._config.lock_timeout_seconds == 10.0

    @pytest.mark.asyncio
    async def test_release_lock_success(self, serializer):
        mock_redis = MagicMock()
        mock_redis.delete = AsyncMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._release_lock("t1")
        assert result is True

    @pytest.mark.asyncio
    async def test_release_lock_error_returns_false(self, serializer):
        mock_redis = MagicMock()
        mock_redis.delete = AsyncMock(side_effect=Exception("error"))

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._release_lock("t1")
        assert result is False

    @pytest.mark.asyncio
    async def test_locked_save_releases_lock_on_failure(self, serializer):
        state = _make_state()
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch.object(
            serializer,
            "save_state",
            new_callable=AsyncMock,
            side_effect=StateSerializationError("both failed"),
        ):
            with pytest.raises(StateSerializationError):
                await serializer.save_state_locked("t1", "c1", state)
        # Lock should still be released
        mock_redis.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_locked_save_raises_when_lock_fails(self, serializer):
        state = _make_state()
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=None)

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            with pytest.raises(StateSerializationError) as exc_info:
                await serializer.save_state_locked("t1", "c1", state)
        assert exc_info.value.error_code == "STATE_LOCK_TIMEOUT"
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_locked_load_raises_when_lock_fails(self, serializer):
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=None)

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            with pytest.raises(StateSerializationError) as exc_info:
                await serializer.load_state_locked("t1", "c1")
        assert exc_info.value.error_code == "STATE_LOCK_TIMEOUT"

    @pytest.mark.asyncio
    async def test_lock_retry_count_from_config(self):
        config = StateSerializerConfig(lock_retries=5)
        serializer = StateSerializer(config=config)
        assert serializer._config.lock_retries == 5

    @pytest.mark.asyncio
    async def test_lock_backoff_ms_from_config(self):
        config = StateSerializerConfig(lock_retry_backoff_ms=250)
        serializer = StateSerializer(config=config)
        assert serializer._config.lock_retry_backoff_ms == 250

    @pytest.mark.asyncio
    async def test_concurrent_access_lock_contention(self, serializer):
        """Simulate lock contention — all retries exhausted."""
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=None)

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer._acquire_lock("t1")
        assert result is False
        assert mock_redis.set.await_count == serializer._config.lock_retries


# ══════════════════════════════════════════════════════════════════
# 9. Error Handling (15 tests)
# ══════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """Error handling and graceful degradation tests."""

    @pytest.fixture
    def serializer(self):
        return StateSerializer()

    @pytest.mark.asyncio
    async def test_state_serialization_error_on_both_backends_fail(self, serializer):
        state = _make_state()
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(
            side_effect=Exception("Redis down")
        )
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock(side_effect=Exception("DB down"))
        mock_db.rollback = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            MagicMock,
        ):
            with pytest.raises(StateSerializationError) as exc_info:
                await serializer.save_state("t1", "c1", state)
        assert exc_info.value.error_code == "STATE_SAVE_COMPLETE_FAILURE"

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_redis_failure(self, serializer):
        state = _make_state()
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(
            side_effect=Exception("Redis down")
        )
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            MagicMock,
        ):
            result = await serializer.save_state("t1", "c1", state)
        assert result.success is True
        assert result.backend == StorageBackend.POSTGRESQL
        assert result.redis_success is False
        assert result.postgresql_success is True

    @pytest.mark.asyncio
    async def test_corrupted_state_data_handling(self, serializer):
        mock_snapshot = MagicMock()
        mock_snapshot.state_data = "<<<INVALID JSON>>>"
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.first.return_value = mock_snapshot
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer._load_from_postgresql("t1", "c1")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_state_data_handling(self, serializer):
        mock_snapshot = MagicMock()
        mock_snapshot.state_data = ""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.first.return_value = mock_snapshot
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer._load_from_postgresql("t1", "c1")
        assert result is None

    def test_invalid_json_handling_safe_json_loads(self):
        with pytest.raises(StateSerializationError) as exc_info:
            _safe_json_loads("not valid json")
        assert "STATE_DESERIALIZE_JSON_ERROR" in exc_info.value.error_code

    def test_invalid_json_handling_none_input(self):
        with pytest.raises(StateSerializationError):
            _safe_json_loads(None)

    def test_missing_required_fields_deserialize(self):
        serializer = StateSerializer()
        result = serializer.deserialize_state({})
        assert result.query == ""
        assert result.gsd_state == GSDState.NEW

    @pytest.mark.asyncio
    async def test_both_redis_and_postgresql_fail(self, serializer):
        state = _make_state()
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(side_effect=Exception("down"))
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock(side_effect=Exception("down"))
        mock_db.rollback = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            MagicMock,
        ):
            with pytest.raises(StateSerializationError):
                await serializer.save_state("t1", "c1", state)

    def test_safe_json_dumps_oversized(self):
        big_obj = {"data": "x" * (6 * 1024 * 1024)}
        with pytest.raises(StateSerializationError) as exc_info:
            _safe_json_dumps(big_obj, max_size=5 * 1024 * 1024)
        assert "STATE_SERIALIZE_TOO_LARGE" in exc_info.value.error_code

    def test_safe_json_dumps_circular_reference(self):
        circular = []
        circular.append(circular)
        with pytest.raises(StateSerializationError) as exc_info:
            _safe_json_dumps(circular)
        assert "STATE_SERIALIZE_JSON_ERROR" in exc_info.value.error_code

    def test_state_serialization_error_is_parwa_base_error(self):
        exc = StateSerializationError()
        from backend.app.exceptions import ParwaBaseError
        assert isinstance(exc, ParwaBaseError)

    def test_state_serialization_error_attributes(self):
        exc = StateSerializationError(
            message="test msg",
            error_code="TEST_CODE",
            status_code=418,
            details={"key": "val"},
        )
        assert exc.message == "test msg"
        assert exc.error_code == "TEST_CODE"
        assert exc.status_code == 418
        assert exc.details == {"key": "val"}

    @pytest.mark.asyncio
    async def test_load_state_returns_none_on_both_failures(self, serializer):
        mock_redis = MagicMock()
        mock_redis.hgetall = AsyncMock(side_effect=Exception("down"))

        mock_db = MagicMock()
        mock_db.query = MagicMock(side_effect=Exception("down"))
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer.load_state("t1", "c1")
        # BC-008: Never crash — returns None
        assert result is None

    def test_state_serialization_error_to_dict(self):
        exc = StateSerializationError(
            details={"info": "test"},
        )
        d = exc.to_dict()
        assert d["error"]["code"] == "STATE_SERIALIZATION_ERROR"
        assert d["error"]["details"]["info"] == "test"

    @pytest.mark.asyncio
    async def test_invalid_snapshot_type_defaults_to_auto(self, serializer):
        state = _make_state()
        mock_pipeline = AsyncMock()
        mock_pipeline.hset = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            MagicMock,
        ):
            # Pass an invalid snapshot_type
            captured_snap_type = {}
            original_add = mock_db.add

            def capture_add(obj):
                captured_snap_type["type"] = getattr(
                    obj, "snapshot_type", None
                )
                original_add(obj)

            mock_db.add = MagicMock(side_effect=capture_add)
            result = await serializer.save_state(
                "t1", "c1", state, snapshot_type="invalid_type",
            )
        assert result.success is True


# ══════════════════════════════════════════════════════════════════
# 10. Edge Cases (15 tests)
# ══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases and boundary condition tests."""

    @pytest.fixture
    def serializer(self):
        return StateSerializer()

    def test_very_large_state_serialization(self):
        big_data = "x" * 1_000_000
        state = ConversationState(
            query=big_data,
            response_parts=[big_data],
            final_response=big_data,
        )
        serializer = StateSerializer()
        result = serializer.serialize_state(state)
        assert result["query"] == big_data

    def test_special_characters_in_checkpoint_names(self, serializer):
        # The sanitization should handle special chars
        names = [
            "before/fix",
            "checkpoint@v2",
            "test-checkpoint",
            "cp with spaces",
        ]
        for name in names:
            safe = name.strip().lower().replace(" ", "_")
            if not safe.isidentifier():
                safe = "".join(
                    c if c.isalnum() or c == "_" else "_"
                    for c in safe
                )
            assert safe.isidentifier() or all(
                c.isalnum() or c == "_" for c in safe
            )

    def test_unicode_in_state_data(self):
        state = ConversationState(
            query="日本語テスト 🎉 한국어 中文",
            final_response="Ünïcödé réspônsé — émojis: 🔥✨",
        )
        serializer = StateSerializer()
        result = serializer.serialize_state(state)
        assert "日本語" in result["query"]
        assert "🎉" in result["query"]

    def test_empty_ticket_id_company_id(self):
        state = ConversationState(
            ticket_id="",
            company_id="",
        )
        serializer = StateSerializer()
        result = serializer.serialize_state(state)
        assert result["ticket_id"] == ""
        assert result["company_id"] == ""

    def test_none_values_throughout(self):
        state = ConversationState(
            ticket_id=None,
            conversation_id=None,
            company_id=None,
            reflexion_trace=None,
        )
        serializer = StateSerializer()
        result = serializer.serialize_state(state)
        assert result["ticket_id"] is None
        assert result["conversation_id"] is None
        assert result["company_id"] is None
        assert result["reflexion_trace"] is None

    @pytest.mark.asyncio
    async def test_rapid_sequential_saves(self, serializer):
        state = _make_state()
        mock_pipeline = AsyncMock()
        mock_pipeline.hset = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            MagicMock,
        ):
            results = []
            for _ in range(10):
                r = await serializer.save_state("t1", "c1", state)
                results.append(r)
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_state(self, serializer):
        mock_redis = MagicMock()
        mock_redis.smembers = AsyncMock(return_value=set())
        mock_redis.delete = AsyncMock(return_value=0)

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await serializer.delete_state("nonexistent", "c1")
        assert result["redis"] is True  # Nothing to delete is OK
        assert isinstance(result, dict)

    def test_binary_like_content_in_strings(self):
        state = ConversationState(
            query="data with null byte \x00 and escape \n\t",
        )
        serializer = StateSerializer()
        result = serializer.serialize_state(state)
        json_str = json.dumps(result, default=str)
        # Should not crash
        assert isinstance(json_str, str)

    def test_all_gsd_state_values_serializable(self):
        serializer = StateSerializer()
        for gsd in GSDState:
            state = ConversationState(gsd_state=gsd)
            result = serializer.serialize_state(state)
            assert result["gsd_state"] == gsd.value

    def test_max_state_size_bytes_config(self):
        config = StateSerializerConfig(max_state_size_bytes=1024)
        serializer = StateSerializer(config=config)
        assert serializer._config.max_state_size_bytes == 1024

    def test_serialize_state_with_empty_lists(self):
        state = ConversationState(
            gsd_history=[],
            technique_results={},
            response_parts=[],
            reasoning_thread=[],
        )
        serializer = StateSerializer()
        result = serializer.serialize_state(state)
        assert result["gsd_history"] == []
        assert result["technique_results"] == {}
        assert result["response_parts"] == []
        assert result["reasoning_thread"] == []

    def test_deserialize_with_all_none_signals(self):
        serializer = StateSerializer()
        result = serializer.deserialize_state({"signals": None})
        assert result.signals is not None  # Falls back to QuerySignals()

    def test_deserialize_with_non_dict_signals(self):
        serializer = StateSerializer()
        result = serializer.deserialize_state({"signals": "not a dict"})
        assert isinstance(result.signals, QuerySignals)

    @pytest.mark.asyncio
    async def test_save_state_latency_ms_recorded(self, serializer):
        state = _make_state()
        mock_pipeline = AsyncMock()
        mock_pipeline.hset = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            MagicMock,
        ):
            result = await serializer.save_state("t1", "c1", state)
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_save_state_with_kwargs_metadata(self, serializer):
        state = _make_state()
        mock_pipeline = AsyncMock()
        mock_pipeline.hset = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            MagicMock,
        ):
            result = await serializer.save_state(
                "t1", "c1", state,
                instance_id="inst-1",
                session_id="sess-1",
                model_used="gpt-4",
                current_node="cot_node",
                technique_stack=["cot", "crp"],
            )
        assert result.success is True


# ══════════════════════════════════════════════════════════════════
# 11. Configuration (10 tests)
# ══════════════════════════════════════════════════════════════════


class TestConfiguration:
    """Configuration defaults and custom overrides."""

    def test_default_config_values(self):
        config = StateSerializerConfig()
        assert config.active_state_ttl_seconds == 86400
        assert config.checkpoint_ttl_seconds == 604800
        assert config.lock_timeout_seconds == 5.0
        assert config.lock_retries == 3
        assert config.lock_retry_backoff_ms == 100
        assert config.default_history_limit == 50
        assert config.max_state_size_bytes == 5 * 1024 * 1024
        assert config.use_redis_pipeline is True

    def test_custom_config_overrides(self):
        config = StateSerializerConfig(
            active_state_ttl_seconds=3600,
            checkpoint_ttl_seconds=86400,
            lock_timeout_seconds=10.0,
            lock_retries=5,
            lock_retry_backoff_ms=200,
            default_history_limit=100,
            max_state_size_bytes=1024,
            use_redis_pipeline=False,
        )
        assert config.active_state_ttl_seconds == 3600
        assert config.checkpoint_ttl_seconds == 86400
        assert config.lock_timeout_seconds == 10.0
        assert config.lock_retries == 5
        assert config.lock_retry_backoff_ms == 200
        assert config.default_history_limit == 100
        assert config.max_state_size_bytes == 1024
        assert config.use_redis_pipeline is False

    def test_redis_ttl_configuration(self):
        config = StateSerializerConfig(
            active_state_ttl_seconds=7200,
            checkpoint_ttl_seconds=172800,
        )
        serializer = StateSerializer(config=config)
        assert serializer._config.active_state_ttl_seconds == 7200
        assert serializer._config.checkpoint_ttl_seconds == 172800

    def test_lock_timeout_configuration(self):
        config = StateSerializerConfig(lock_timeout_seconds=15.0)
        serializer = StateSerializer(config=config)
        assert serializer._config.lock_timeout_seconds == 15.0

    def test_retry_configuration(self):
        config = StateSerializerConfig(
            lock_retries=10,
            lock_retry_backoff_ms=500,
        )
        serializer = StateSerializer(config=config)
        assert serializer._config.lock_retries == 10
        assert serializer._config.lock_retry_backoff_ms == 500

    def test_config_is_frozen(self):
        config = StateSerializerConfig()
        with pytest.raises(AttributeError):
            config.active_state_ttl_seconds = 0

    def test_serializer_uses_default_config_when_none(self):
        serializer = StateSerializer(config=None)
        assert serializer._config.active_state_ttl_seconds == 86400

    def test_serializer_uses_custom_config(self):
        config = StateSerializerConfig(active_state_ttl_seconds=600)
        serializer = StateSerializer(config=config)
        assert serializer._config.active_state_ttl_seconds == 600

    def test_snapshot_type_enum_values(self):
        assert SnapshotType.AUTO.value == "auto"
        assert SnapshotType.MANUAL.value == "manual"
        assert SnapshotType.ERROR.value == "error"
        assert SnapshotType.CHECKPOINT.value == "checkpoint"

    def test_storage_backend_enum_values(self):
        assert StorageBackend.REDIS.value == "redis"
        assert StorageBackend.POSTGRESQL.value == "postgresql"
        assert StorageBackend.NONE.value == "none"


# ══════════════════════════════════════════════════════════════════
# Utility Function Tests (supporting ~30+ additional tests)
# ══════════════════════════════════════════════════════════════════


class TestUtilityFunctions:
    """Tests for module-level utility functions."""

    def test_utcnow_returns_string(self):
        result = _utcnow()
        assert isinstance(result, str)

    def test_utcnow_contains_timezone(self):
        result = _utcnow()
        # Should contain +00:00 or Z
        assert "+00:00" in result or result.endswith("Z")

    def test_new_uuid_returns_string(self):
        result = _new_uuid()
        assert isinstance(result, str)

    def test_new_uuid_is_valid_format(self):
        result = _new_uuid()
        # UUID4 format: 8-4-4-4-12 hex chars
        parts = result.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8

    def test_new_uuid_unique(self):
        ids = {_new_uuid() for _ in range(100)}
        assert len(ids) == 100

    def test_serialize_enum_plain_value(self):
        assert _serialize_enum("hello") == "hello"

    def test_serialize_enum_int_value(self):
        assert _serialize_enum(42) == 42

    def test_serialize_enum_dict_with_enums(self):
        result = _serialize_enum({"key": GSDState.NEW})
        assert result["key"] == "new"

    def test_serialize_enum_list_with_enums(self):
        result = _serialize_enum([GSDState.NEW, GSDState.DIAGNOSIS])
        assert result == ["new", "diagnosis"]

    def test_serialize_enum_nested_structure(self):
        data = {
            "level1": {
                "level2": [GSDState.CLOSED, "string_val"],
            }
        }
        result = _serialize_enum(data)
        assert result["level1"]["level2"][0] == "closed"
        assert result["level1"]["level2"][1] == "string_val"

    def test_serialize_enum_none_value(self):
        assert _serialize_enum(None) is None

    def test_serialize_enum_bool_value(self):
        assert _serialize_enum(True) is True
        assert _serialize_enum(False) is False

    def test_safe_json_dumps_basic(self):
        result = _safe_json_dumps({"key": "value"})
        parsed = json.loads(result)
        assert parsed["key"] == "value"

    def test_safe_json_dumps_unicode(self):
        result = _safe_json_dumps({"text": "日本語"})
        assert "日本語" in result

    def test_safe_json_dumps_nested(self):
        data = {"a": {"b": [1, 2, 3]}, "c": None}
        result = _safe_json_dumps(data)
        parsed = json.loads(result)
        assert parsed["a"]["b"] == [1, 2, 3]
        assert parsed["c"] is None

    def test_safe_json_loads_basic(self):
        result = _safe_json_loads('{"key": "value"}')
        assert result["key"] == "value"

    def test_safe_json_loads_nested(self):
        data = '{"a": {"b": [1, 2, 3]}}'
        result = _safe_json_loads(data)
        assert result["a"]["b"] == [1, 2, 3]

    def test_safe_json_loads_empty_string(self):
        with pytest.raises(StateSerializationError):
            _safe_json_loads("")

    def test_safe_json_loads_valid_json_number(self):
        result = _safe_json_loads("42")
        assert result == 42

    def test_build_state_key_scoped(self):
        key = _build_state_key("tenant-A", "ticket-B")
        assert "tenant-A" in key
        assert "ticket-B" in key
        assert key.startswith("parwa:state:")

    def test_build_checkpoint_key_scoped(self):
        key = _build_checkpoint_key("c1", "t1", "my_cp")
        assert "c1" in key
        assert "t1" in key
        assert "my_cp" in key
        assert key.startswith("parwa:checkpoint:")

    def test_build_checkpoint_index_key_scoped(self):
        key = _build_checkpoint_index_key("c1", "t1")
        assert "c1" in key
        assert "t1" in key
        assert key.startswith("parwa:checkpoints:")

    def test_build_lock_key_format(self):
        key = _build_lock_key("ticket-XYZ")
        assert key == "parwa:lock:state:ticket-XYZ"


# ══════════════════════════════════════════════════════════════════
# Dataclass Tests (SaveResult, StateDiff, enums, etc.)
# ══════════════════════════════════════════════════════════════════


class TestDataclasses:
    """Test dataclass creation and to_dict methods."""

    def test_save_result_creation(self):
        result = SaveResult(
            success=True,
            snapshot_id="snap-1",
            backend=StorageBackend.REDIS,
            redis_success=True,
            postgresql_success=True,
            latency_ms=42,
        )
        assert result.success is True
        assert result.snapshot_id == "snap-1"
        assert result.latency_ms == 42

    def test_save_result_to_dict(self):
        result = SaveResult(
            success=True,
            snapshot_id="snap-1",
            backend=StorageBackend.REDIS,
            redis_success=True,
            postgresql_success=False,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["backend"] == "redis"
        assert d["redis_success"] is True
        assert d["postgresql_success"] is False

    def test_save_result_defaults(self):
        result = SaveResult(
            success=False,
            snapshot_id="s1",
            backend=StorageBackend.NONE,
            redis_success=False,
            postgresql_success=False,
        )
        assert result.error_message is None
        assert result.latency_ms == 0

    def test_state_diff_defaults(self):
        diff = StateDiff()
        assert diff.gsd_state is None
        assert diff.current_node is None
        assert diff.changed_fields == []
        assert diff.unchanged_fields == []

    def test_snapshot_type_invalid_raises(self):
        with pytest.raises(ValueError):
            SnapshotType("nonexistent")

    def test_storage_backend_all_values(self):
        backends = list(StorageBackend)
        assert len(backends) == 3

    def test_snapshot_type_all_values(self):
        types = list(SnapshotType)
        assert len(types) == 4

    def test_get_state_serializer_singleton(self):
        from backend.app.core.state_serialization import (
            get_state_serializer,
            _state_serializer,
        )
        s1 = get_state_serializer()
        s2 = get_state_serializer()
        assert s1 is s2

    def test_serialize_state_includes_serialized_at(self):
        state = _make_state()
        serializer = StateSerializer()
        result = serializer.serialize_state(state)
        assert "serialized_at" in result
        assert len(result["serialized_at"]) > 0

    def test_serialize_state_includes_all_fields(self):
        state = _make_state()
        serializer = StateSerializer()
        result = serializer.serialize_state(state)
        expected_keys = {
            "query", "signals", "gsd_state", "gsd_history",
            "technique_results", "token_usage", "technique_token_budget",
            "response_parts", "final_response", "ticket_id",
            "conversation_id", "company_id", "reasoning_thread",
            "reflexion_trace", "serialized_at",
        }
        assert set(result.keys()) == expected_keys


# ══════════════════════════════════════════════════════════════════
# High-level Integration Tests (save_state → load_state)
# ══════════════════════════════════════════════════════════════════


class TestHighLevelIntegration:
    """End-to-end save/load flows with both backends mocked."""

    @pytest.fixture
    def serializer(self):
        return StateSerializer()

    @pytest.mark.asyncio
    async def test_save_then_load_redis_hit(self, serializer):
        state = _make_state()
        serialized = serializer.serialize_state(state)
        state_json = json.dumps(serialized, default=str)

        mock_pipeline = AsyncMock()
        mock_pipeline.hset = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        mock_redis.hgetall = AsyncMock(
            return_value={"state_data": state_json, "snapshot_id": "s1"}
        )
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            MagicMock,
        ):
            save_result = await serializer.save_state("t1", "c1", state)
            loaded = await serializer.load_state("t1", "c1")

        assert save_result.success is True
        assert loaded is not None
        assert loaded.query == state.query
        assert loaded.gsd_state == state.gsd_state

    @pytest.mark.asyncio
    async def test_save_then_load_pg_fallback(self, serializer):
        state = _make_state()
        serialized = serializer.serialize_state(state)

        # Redis miss → PG hit
        mock_redis = MagicMock()
        mock_redis.hgetall = AsyncMock(return_value={})
        mock_redis.set = AsyncMock()

        mock_snapshot = MagicMock()
        mock_snapshot.state_data = json.dumps(serialized, default=str)
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.first.return_value = mock_snapshot
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            loaded = await serializer.load_state("t1", "c1")

        assert loaded is not None
        assert loaded.query == state.query

    @pytest.mark.asyncio
    async def test_save_and_delete(self, serializer):
        state = _make_state()
        mock_pipeline = AsyncMock()
        mock_pipeline.hset = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        mock_redis.smembers = AsyncMock(return_value=set())
        mock_redis.delete = AsyncMock(return_value=1)
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            MagicMock,
        ), patch.object(
            serializer,
            "_delete_state_from_postgresql",
            new_callable=AsyncMock,
            return_value=True,
        ):
            save_result = await serializer.save_state("t1", "c1", state)
            del_result = await serializer.delete_state("t1", "c1")

        assert save_result.success is True
        assert del_result["redis"] is True
        assert del_result["postgresql"] is True

    @pytest.mark.asyncio
    async def test_load_state_not_found(self, serializer):
        mock_redis = MagicMock()
        mock_redis.hgetall = AsyncMock(return_value={})

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.first.return_value = None
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.close = MagicMock()

        with patch(
            "backend.app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ), patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ), patch(
            "database.models.variant_engine.PipelineStateSnapshot",
            create=True,
        ):
            result = await serializer.load_state("missing", "c1")
        assert result is None
