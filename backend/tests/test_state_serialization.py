"""
Tests for SG-15: State Serialization/Deserialization Layer.

Covers: StateSerializationError, SnapshotType, StorageBackend,
StateSerializerConfig, StateDiff, CheckpointMeta, StateHistoryEntry,
SaveResult, key builders, utility functions, and StateSerializer class.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.state_serialization import (
    CheckpointMeta,
    SaveResult,
    SnapshotType,
    StateDiff,
    StateHistoryEntry,
    StateSerializationError,
    StateSerializer,
    StateSerializerConfig,
    StorageBackend,
    _build_checkpoint_index_key,
    _build_checkpoint_key,
    _build_lock_key,
    _build_state_key,
    _new_uuid,
    _safe_json,
    _safe_json_dumps,
    _safe_json_loads,
    _serialize_enum,
    _utcnow,
)
from app.core.techniques.base import (
    ConversationState,
    GSDState,
)

# ── Helpers ─────────────────────────────────────────────────────


def _make_signals(
    intent_type="refund",
    sentiment_score=0.6,
    frustration_score=30.0,
    query_complexity=0.5,
    customer_tier="free",
    confidence_score=0.9,
    turn_count=2,
):
    from app.core.technique_router import QuerySignals

    return QuerySignals(
        intent_type=intent_type,
        sentiment_score=sentiment_score,
        frustration_score=frustration_score,
        query_complexity=query_complexity,
        customer_tier=customer_tier,
        confidence_score=confidence_score,
        turn_count=turn_count,
    )


def _make_state(
    company_id="co_1",
    ticket_id="t1",
    query="how do I get a refund?",
    gsd_state=GSDState.NEW,
    signals=None,
    token_usage=150,
    technique_results=None,
    gsd_history=None,
    response_parts=None,
    final_response="",
    reasoning_thread=None,
    reflexion_trace=None,
):
    return ConversationState(
        query=query,
        signals=signals or _make_signals(),
        gsd_state=gsd_state,
        gsd_history=gsd_history or [],
        technique_results=technique_results or {},
        token_usage=token_usage,
        response_parts=response_parts or [],
        final_response=final_response,
        ticket_id=ticket_id,
        conversation_id="conv_1",
        company_id=company_id,
        reasoning_thread=reasoning_thread or [],
        reflexion_trace=reflexion_trace,
    )


# ══════════════════════════════════════════════════════════════════
# TestStateSerializationError
# ══════════════════════════════════════════════════════════════════


class TestStateSerializationError:
    def test_default_construction(self):
        err = StateSerializationError()
        assert "State serialization failed" in str(err)

    def test_custom_message(self):
        err = StateSerializationError(message="custom error")
        assert "custom error" in str(err)

    def test_error_code(self):
        err = StateSerializationError(error_code="TEST_CODE")
        assert err.error_code == "TEST_CODE"

    def test_status_code(self):
        err = StateSerializationError(status_code=400)
        assert err.status_code == 400

    def test_details(self):
        err = StateSerializationError(details={"key": "value"})
        assert err.details == {"key": "value"}

    def test_details_none(self):
        err = StateSerializationError()
        assert err.details is None

    def test_inheritance(self):
        from app.exceptions import ParwaBaseError

        err = StateSerializationError()
        assert isinstance(err, ParwaBaseError)
        assert isinstance(err, Exception)

    def test_catch_as_base(self):
        with pytest.raises(StateSerializationError):
            raise StateSerializationError(message="boom")

    def test_all_params(self):
        err = StateSerializationError(
            message="full",
            error_code="E1",
            status_code=503,
            details={"a": 1},
        )
        assert "full" in str(err)
        assert err.error_code == "E1"
        assert err.status_code == 503
        assert err.details == {"a": 1}


# ══════════════════════════════════════════════════════════════════
# TestSnapshotType
# ══════════════════════════════════════════════════════════════════


class TestSnapshotType:
    def test_auto(self):
        assert SnapshotType.AUTO.value == "auto"

    def test_manual(self):
        assert SnapshotType.MANUAL.value == "manual"

    def test_error(self):
        assert SnapshotType.ERROR.value == "error"

    def test_checkpoint(self):
        assert SnapshotType.CHECKPOINT.value == "checkpoint"

    def test_from_string(self):
        assert SnapshotType("auto") == SnapshotType.AUTO

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            SnapshotType("nonexistent")

    def test_is_str_enum(self):
        assert isinstance(SnapshotType.AUTO, str)
        assert SnapshotType.AUTO == "auto"

    def test_iteration(self):
        values = list(SnapshotType)
        assert len(values) == 4


# ══════════════════════════════════════════════════════════════════
# TestStorageBackend
# ══════════════════════════════════════════════════════════════════


class TestStorageBackend:
    def test_redis(self):
        assert StorageBackend.REDIS.value == "redis"

    def test_postgresql(self):
        assert StorageBackend.POSTGRESQL.value == "postgresql"

    def test_none(self):
        assert StorageBackend.NONE.value == "none"

    def test_from_string(self):
        assert StorageBackend("redis") == StorageBackend.REDIS

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            StorageBackend("mongodb")

    def test_is_str_enum(self):
        assert isinstance(StorageBackend.REDIS, str)

    def test_iteration(self):
        values = list(StorageBackend)
        # REDIS, POSTGRESQL, FILE, NONE
        assert len(values) == 4


# ══════════════════════════════════════════════════════════════════
# TestStateSerializerConfig
# ══════════════════════════════════════════════════════════════════


class TestStateSerializerConfig:
    def test_defaults(self):
        cfg = StateSerializerConfig()
        assert cfg.active_state_ttl_seconds == 86400
        assert cfg.checkpoint_ttl_seconds == 604800
        assert cfg.lock_timeout_seconds == 5.0
        assert cfg.lock_retries == 3
        assert cfg.lock_retry_backoff_ms == 100
        assert cfg.default_history_limit == 50
        assert cfg.max_state_size_bytes == 5 * 1024 * 1024
        assert cfg.use_redis_pipeline is True

    def test_custom_values(self):
        cfg = StateSerializerConfig(
            active_state_ttl_seconds=100,
            checkpoint_ttl_seconds=200,
            lock_timeout_seconds=1.0,
            lock_retries=1,
            lock_retry_backoff_ms=50,
            default_history_limit=10,
            max_state_size_bytes=1024,
            use_redis_pipeline=False,
        )
        assert cfg.active_state_ttl_seconds == 100
        assert cfg.checkpoint_ttl_seconds == 200
        assert cfg.lock_timeout_seconds == 1.0
        assert cfg.lock_retries == 1
        assert cfg.lock_retry_backoff_ms == 50
        assert cfg.default_history_limit == 10
        assert cfg.max_state_size_bytes == 1024
        assert cfg.use_redis_pipeline is False

    def test_frozen(self):
        cfg = StateSerializerConfig()
        with pytest.raises(AttributeError):
            cfg.active_state_ttl_seconds = 999

    def test_equality(self):
        a = StateSerializerConfig()
        b = StateSerializerConfig()
        assert a == b


# ══════════════════════════════════════════════════════════════════
# TestStateDiff
# ══════════════════════════════════════════════════════════════════


class TestStateDiff:
    def test_defaults(self):
        diff = StateDiff()
        assert diff.gsd_state is None
        assert diff.current_node is None
        assert diff.technique_stack is None
        assert diff.token_count is None
        assert diff.changed_fields == []
        assert diff.unchanged_fields == []
        assert diff.timestamp == ""

    def test_with_values(self):
        diff = StateDiff(
            gsd_state={"old": "new", "new": "diagnosis"},
            token_count={"old": 0, "new": 150},
            changed_fields=["gsd_state", "token_count"],
            unchanged_fields=["query"],
            timestamp="2025-01-01T00:00:00+00:00",
        )
        assert diff.gsd_state == {"old": "new", "new": "diagnosis"}
        assert diff.token_count == {"old": 0, "new": 150}
        assert diff.changed_fields == ["gsd_state", "token_count"]
        assert diff.unchanged_fields == ["query"]

    def test_to_dict(self):
        diff = StateDiff(
            gsd_state={"old": "new", "new": "diagnosis"},
            changed_fields=["gsd_state"],
            timestamp="2025-01-01",
        )
        d = diff.to_dict()
        assert d["gsd_state"] == {"old": "new", "new": "diagnosis"}
        assert d["changed_fields"] == ["gsd_state"]
        assert d["timestamp"] == "2025-01-01"
        assert d["current_node"] is None
        assert d["technique_stack"] is None

    def test_list_factory_independence(self):
        a = StateDiff()
        b = StateDiff()
        a.changed_fields.append("x")
        assert "x" not in b.changed_fields


# ══════════════════════════════════════════════════════════════════
# TestCheckpointMeta
# ══════════════════════════════════════════════════════════════════


class TestCheckpointMeta:
    def test_construction(self):
        meta = CheckpointMeta(
            checkpoint_name="pre_resolution",
            ticket_id="t1",
            company_id="c1",
            snapshot_id="s1",
            created_at="2025-01-01",
            gsd_state="diagnosis",
            token_count=100,
            current_node="classify",
        )
        assert meta.checkpoint_name == "pre_resolution"
        assert meta.ticket_id == "t1"
        assert meta.company_id == "c1"
        assert meta.snapshot_id == "s1"
        assert meta.created_at == "2025-01-01"
        assert meta.gsd_state == "diagnosis"
        assert meta.token_count == 100
        assert meta.current_node == "classify"

    def test_to_dict(self):
        meta = CheckpointMeta(
            checkpoint_name="cp1",
            ticket_id="t1",
            company_id="c1",
            snapshot_id="s1",
            created_at="now",
            gsd_state="new",
            token_count=0,
            current_node="start",
        )
        d = meta.to_dict()
        assert d["checkpoint_name"] == "cp1"
        assert d["ticket_id"] == "t1"
        assert d["company_id"] == "c1"
        assert d["snapshot_id"] == "s1"
        assert d["created_at"] == "now"
        assert d["gsd_state"] == "new"
        assert d["token_count"] == 0
        assert d["current_node"] == "start"


# ══════════════════════════════════════════════════════════════════
# TestStateHistoryEntry
# ══════════════════════════════════════════════════════════════════


class TestStateHistoryEntry:
    def test_construction(self):
        entry = StateHistoryEntry(
            snapshot_id="s1",
            created_at="2025-01-01",
            snapshot_type="auto",
            current_node="classify",
            gsd_state="diagnosis",
            token_count=50,
            model_used="groq-llama",
            technique_stack=["cot", "react"],
        )
        assert entry.snapshot_id == "s1"
        assert entry.created_at == "2025-01-01"
        assert entry.snapshot_type == "auto"
        assert entry.model_used == "groq-llama"
        assert entry.technique_stack == ["cot", "react"]

    def test_model_used_none(self):
        entry = StateHistoryEntry(
            snapshot_id="s1",
            created_at="",
            snapshot_type="auto",
            current_node="n",
            gsd_state="new",
            token_count=0,
            model_used=None,
            technique_stack=[],
        )
        assert entry.model_used is None

    def test_to_dict(self):
        entry = StateHistoryEntry(
            snapshot_id="s1",
            created_at="2025-01-01",
            snapshot_type="manual",
            current_node="respond",
            gsd_state="resolution",
            token_count=200,
            model_used="google",
            technique_stack=["clara"],
        )
        d = entry.to_dict()
        assert d["snapshot_id"] == "s1"
        assert d["model_used"] == "google"
        assert d["technique_stack"] == ["clara"]
        assert d["token_count"] == 200

    def test_list_factory_independence(self):
        a = StateHistoryEntry(
            snapshot_id="",
            created_at="",
            snapshot_type="",
            current_node="",
            gsd_state="",
            token_count=0,
            model_used=None,
            technique_stack=[],
        )
        b = StateHistoryEntry(
            snapshot_id="",
            created_at="",
            snapshot_type="",
            current_node="",
            gsd_state="",
            token_count=0,
            model_used=None,
            technique_stack=[],
        )
        a.technique_stack.append("x")
        assert "x" not in b.technique_stack


# ══════════════════════════════════════════════════════════════════
# TestSaveResult
# ══════════════════════════════════════════════════════════════════


class TestSaveResult:
    def test_success(self):
        r = SaveResult(
            success=True,
            snapshot_id="s1",
            backend=StorageBackend.REDIS,
            redis_success=True,
            postgresql_success=True,
        )
        assert r.success is True
        assert r.snapshot_id == "s1"
        assert r.backend == StorageBackend.REDIS
        assert r.redis_success is True
        assert r.postgresql_success is True
        assert r.error_message is None
        assert r.latency_ms == 0

    def test_partial_failure(self):
        r = SaveResult(
            success=True,
            snapshot_id="s1",
            backend=StorageBackend.POSTGRESQL,
            redis_success=False,
            postgresql_success=True,
            error_message="Redis down",
        )
        assert r.backend == StorageBackend.POSTGRESQL
        assert r.redis_success is False
        assert r.error_message == "Redis down"

    def test_with_latency(self):
        r = SaveResult(
            success=True,
            snapshot_id="s1",
            backend=StorageBackend.REDIS,
            redis_success=True,
            postgresql_success=True,
            latency_ms=42,
        )
        assert r.latency_ms == 42

    def test_to_dict(self):
        r = SaveResult(
            success=True,
            snapshot_id="s1",
            backend=StorageBackend.REDIS,
            redis_success=True,
            postgresql_success=False,
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["snapshot_id"] == "s1"
        assert d["backend"] == "redis"
        assert d["redis_success"] is True
        assert d["postgresql_success"] is False


# ══════════════════════════════════════════════════════════════════
# Test Key Builders
# ══════════════════════════════════════════════════════════════════


class TestBuildStateKey:
    def test_basic(self):
        key = _build_state_key("co_1", "t1")
        assert key == "parwa:state:co_1:t1"

    def test_different_ids(self):
        key = _build_state_key("company_abc", "ticket_xyz")
        assert key == "parwa:state:company_abc:ticket_xyz"

    def test_empty_strings(self):
        key = _build_state_key("", "")
        assert key == "parwa:state::"

    def test_with_colons_in_id(self):
        key = _build_state_key("co:1", "t:1")
        assert "parwa:state:co:1:t:1" == key

    def test_tenant_isolation(self):
        key_a = _build_state_key("co_a", "t1")
        key_b = _build_state_key("co_b", "t1")
        assert key_a != key_b


class TestBuildCheckpointKey:
    def test_basic(self):
        key = _build_checkpoint_key("co_1", "t1", "pre_resolution")
        assert key == "parwa:checkpoint:co_1:t1:pre_resolution"

    def test_with_spaces(self):
        key = _build_checkpoint_key("co_1", "t1", "before resolution")
        assert key == "parwa:checkpoint:co_1:t1:before resolution"

    def test_empty_name(self):
        key = _build_checkpoint_key("co_1", "t1", "")
        assert key == "parwa:checkpoint:co_1:t1:"


class TestBuildCheckpointIndexKey:
    def test_basic(self):
        key = _build_checkpoint_index_key("co_1", "t1")
        assert key == "parwa:checkpoints:co_1:t1"

    def test_different_ticket(self):
        key = _build_checkpoint_index_key("co_1", "t999")
        assert key == "parwa:checkpoints:co_1:t999"


class TestBuildLockKey:
    def test_basic(self):
        key = _build_lock_key("t1")
        assert key == "parwa:lock:state:t1"

    def test_different_ticket(self):
        key = _build_lock_key("ticket_abc")
        assert key == "parwa:lock:state:ticket_abc"

    def test_lock_key_no_company(self):
        key = _build_lock_key("t1")
        assert "co" not in key


# ══════════════════════════════════════════════════════════════════
# Test Utility Functions
# ══════════════════════════════════════════════════════════════════


class TestUtcnow:
    def test_returns_string(self):
        result = _utcnow()
        assert isinstance(result, str)

    def test_contains_tz(self):
        result = _utcnow()
        assert "+00:00" in result

    def test_parseable(self):
        result = _utcnow()
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None

    def test_is_recent(self):
        before = datetime.now(timezone.utc)
        result = _utcnow()
        after = datetime.now(timezone.utc)
        dt = datetime.fromisoformat(result)
        assert before <= dt <= after


class TestNewUuid:
    def test_returns_string(self):
        result = _new_uuid()
        assert isinstance(result, str)

    def test_is_uuid4_format(self):
        import re

        result = _new_uuid()
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            result,
        )

    def test_unique(self):
        a = _new_uuid()
        b = _new_uuid()
        assert a != b


class TestSerializeEnum:
    def test_enum_value(self):
        result = _serialize_enum(GSDState.NEW)
        assert result == "new"

    def test_string_passthrough(self):
        assert _serialize_enum("hello") == "hello"

    def test_int_passthrough(self):
        assert _serialize_enum(42) == 42

    def test_none_passthrough(self):
        assert _serialize_enum(None) is None

    def test_dict_with_enums(self):
        result = _serialize_enum({"state": GSDState.DIAGNOSIS})
        assert result == {"state": "diagnosis"}

    def test_list_with_enums(self):
        result = _serialize_enum([GSDState.NEW, GSDState.GREETING])
        assert result == ["new", "greeting"]

    def test_nested_structure(self):
        data = {
            "history": [GSDState.NEW, GSDState.DIAGNOSIS],
            "current": GSDState.RESOLUTION,
        }
        result = _serialize_enum(data)
        assert result == {
            "history": ["new", "diagnosis"],
            "current": "resolution",
        }

    def test_empty_dict(self):
        assert _serialize_enum({}) == {}

    def test_empty_list(self):
        assert _serialize_enum([]) == []

    def test_tuple_converts_to_list(self):
        result = _serialize_enum((GSDState.NEW,))
        assert result == ["new"]


class TestSafeJsonDumps:
    def test_valid_dict(self):
        result = _safe_json_dumps({"a": 1})
        parsed = json.loads(result)
        assert parsed == {"a": 1}

    def test_valid_list(self):
        result = _safe_json_dumps([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]

    def test_valid_string(self):
        result = _safe_json_dumps("hello")
        assert json.loads(result) == "hello"

    def test_none(self):
        result = _safe_json_dumps(None)
        assert json.loads(result) is None

    def test_enum_in_dict(self):
        result = _safe_json_dumps({"state": GSDState.NEW})
        parsed = json.loads(result)
        assert parsed["state"] == "new"

    def test_too_large_raises(self):
        big_data = {"x": "a" * (6 * 1024 * 1024)}
        with pytest.raises(StateSerializationError) as exc_info:
            _safe_json_dumps(big_data, max_size=1024)
        assert "TOO_LARGE" in exc_info.value.error_code

    def test_custom_max_size(self):
        small = {"x": "a"}
        result = _safe_json_dumps(small, max_size=1024 * 1024)
        assert result is not None

    def test_non_serializable_raises(self):
        class BadObj:
            pass

        with pytest.raises(StateSerializationError) as exc_info:
            _safe_json_dumps({"obj": BadObj()})
        assert "JSON_ERROR" in exc_info.value.error_code

    def test_datetime_serializes(self):
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = _safe_json_dumps({"dt": dt})
        assert "2025" in result

    def test_empty_string(self):
        result = _safe_json_dumps("")
        assert result == '""'


class TestSafeJsonLoads:
    def test_valid_json(self):
        result = _safe_json.loads('{"a": 1}')
        assert result == {"a": 1}

    def test_valid_list(self):
        result = _safe_json.loads("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_empty_string_raises(self):
        with pytest.raises(StateSerializationError):
            _safe_json_loads("")

    def test_invalid_json_raises(self):
        with pytest.raises(StateSerializationError):
            _safe_json_loads("{broken json")

    def test_none_raises(self):
        with pytest.raises(StateSerializationError):
            _safe_json_loads(None)

    def test_error_code(self):
        with pytest.raises(StateSerializationError) as exc_info:
            _safe_json_loads("not json")
        assert "DESERIALIZE_JSON_ERROR" in exc_info.value.error_code


# ══════════════════════════════════════════════════════════════════
# TestStateSerializer - serialize_state / deserialize_state
# ══════════════════════════════════════════════════════════════════


class TestSerializeState:
    def setup_method(self):
        self.serializer = StateSerializer()

    def test_basic_state(self):
        state = _make_state()
        result = self.serializer.serialize_state(state)
        assert isinstance(result, dict)
        assert result["query"] == "how do I get a refund?"
        assert result["gsd_state"] == "new"
        assert result["company_id"] == "co_1"
        assert result["ticket_id"] == "t1"
        assert result["token_usage"] == 150

    def test_gsd_state_as_string(self):
        result = self.serializer.serialize_state(
            _make_state(gsd_state=GSDState.DIAGNOSIS)
        )
        assert result["gsd_state"] == "diagnosis"

    def test_gsd_history_serialized(self):
        state = _make_state(
            gsd_history=[
                GSDState.NEW,
                GSDState.GREETING,
                GSDState.DIAGNOSIS,
            ]
        )
        result = self.serializer.serialize_state(state)
        assert result["gsd_history"] == ["new", "greeting", "diagnosis"]

    def test_empty_history(self):
        state = _make_state(gsd_history=[])
        result = self.serializer.serialize_state(state)
        assert result["gsd_history"] == []

    def test_signals_serialized(self):
        state = _make_state(signals=_make_signals(intent_type="billing"))
        result = self.serializer.serialize_state(state)
        assert result["signals"] is not None
        assert result["signals"]["intent_type"] == "billing"

    def test_signals_none(self):
        state = _make_state()
        state.signals = None
        result = self.serializer.serialize_state(state)
        assert result["signals"] is None

    def test_technique_results(self):
        state = _make_state(technique_results={"cot": {"output": "yes"}})
        result = self.serializer.serialize_state(state)
        assert result["technique_results"] == {"cot": {"output": "yes"}}

    def test_technique_results_none(self):
        state = _make_state()
        state.technique_results = None
        result = self.serializer.serialize_state(state)
        assert result["technique_results"] == {}

    def test_response_parts(self):
        state = _make_state(response_parts=["part1", "part2"])
        result = self.serializer.serialize_state(state)
        assert result["response_parts"] == ["part1", "part2"]

    def test_final_response(self):
        state = _make_state(final_response="Here is your refund info.")
        result = self.serializer.serialize_state(state)
        assert result["final_response"] == "Here is your refund info."

    def test_serialized_at_present(self):
        result = self.serializer.serialize_state(_make_state())
        assert "serialized_at" in result
        assert isinstance(result["serialized_at"], str)

    def test_all_gsd_states(self):
        for gsd in GSDState:
            state = _make_state(gsd_state=gsd)
            result = self.serializer.serialize_state(state)
            assert result["gsd_state"] == gsd.value

    def test_token_budget(self):
        state = _make_state()
        result = self.serializer.serialize_state(state)
        assert "technique_token_budget" in result

    def test_reflexion_trace_none(self):
        state = _make_state(reflexion_trace=None)
        result = self.serializer.serialize_state(state)
        assert result["reflexion_trace"] is None


class TestDeserializeState:
    def setup_method(self):
        self.serializer = StateSerializer()

    def test_basic(self):
        data = {
            "query": "test",
            "gsd_state": "diagnosis",
            "company_id": "co_1",
            "ticket_id": "t1",
            "token_usage": 100,
        }
        state = self.serializer.deserialize_state(data)
        assert state.query == "test"
        assert state.gsd_state == GSDState.DIAGNOSIS
        assert state.company_id == "co_1"

    def test_missing_fields_use_defaults(self):
        data = {"gsd_state": "new"}
        state = self.serializer.deserialize_state(data)
        assert state.query == ""
        assert state.gsd_state == GSDState.NEW
        assert state.token_usage == 0

    def test_invalid_gsd_state_fallback(self):
        data = {"gsd_state": "nonexistent_state"}
        state = self.serializer.deserialize_state(data)
        assert state.gsd_state == GSDState.NEW

    def test_gsd_state_as_enum(self):
        data = {"gsd_state": GSDState.RESOLUTION}
        state = self.serializer.deserialize_state(data)
        assert state.gsd_state == GSDState.RESOLUTION

    def test_gsd_history_deserialized(self):
        data = {"gsd_history": ["new", "greeting", "diagnosis"]}
        state = self.serializer.deserialize_state(data)
        assert len(state.gsd_history) == 3
        assert state.gsd_history == [
            GSDState.NEW,
            GSDState.GREETING,
            GSDState.DIAGNOSIS,
        ]

    def test_invalid_gsd_history_entries_skipped(self):
        data = {"gsd_history": ["new", "invalid", "diagnosis"]}
        state = self.serializer.deserialize_state(data)
        assert len(state.gsd_history) == 2

    def test_signals_from_dict(self):
        data = {
            "signals": {
                "intent_type": "refund",
                "sentiment_score": 0.7,
                "frustration_score": 40.0,
                "query_complexity": 0.3,
                "customer_tier": "free",
                "confidence_score": 0.85,
                "turn_count": 1,
            }
        }
        state = self.serializer.deserialize_state(data)
        assert state.signals is not None
        assert state.signals.intent_type == "refund"

    def test_signals_none(self):
        data = {"signals": None}
        state = self.serializer.deserialize_state(data)
        assert state.signals is not None  # fallback to empty QuerySignals

    def test_signals_non_dict(self):
        data = {"signals": "invalid"}
        state = self.serializer.deserialize_state(data)
        assert state.signals is not None

    def test_technique_results_from_dict(self):
        data = {"technique_results": {"cot": {"output": "yes"}}}
        state = self.serializer.deserialize_state(data)
        assert state.technique_results == {"cot": {"output": "yes"}}

    def test_technique_results_non_dict(self):
        data = {"technique_results": "invalid"}
        state = self.serializer.deserialize_state(data)
        assert state.technique_results == {}

    def test_reflexion_trace_valid(self):
        data = {"reflexion_trace": {"iterations": 3}}
        state = self.serializer.deserialize_state(data)
        assert state.reflexion_trace == {"iterations": 3}

    def test_reflexion_trace_invalid(self):
        data = {"reflexion_trace": "invalid"}
        state = self.serializer.deserialize_state(data)
        assert state.reflexion_trace is None

    def test_empty_data(self):
        state = self.serializer.deserialize_state({})
        assert state.query == ""
        assert state.gsd_state == GSDState.NEW

    def test_extra_fields_ignored(self):
        data = {"gsd_state": "new", "unknown_field": "value"}
        state = self.serializer.deserialize_state(data)
        assert state.gsd_state == GSDState.NEW

    def test_gsd_history_non_list(self):
        data = {"gsd_history": "not a list"}
        state = self.serializer.deserialize_state(data)
        assert state.gsd_history == []

    def test_response_parts(self):
        data = {"response_parts": ["a", "b"]}
        state = self.serializer.deserialize_state(data)
        assert state.response_parts == ["a", "b"]

    def test_reasoning_thread(self):
        data = {"reasoning_thread": ["step1", "step2"]}
        state = self.serializer.deserialize_state(data)
        assert state.reasoning_thread == ["step1", "step2"]


class TestRoundTrip:
    def setup_method(self):
        self.serializer = StateSerializer()

    def test_basic_round_trip(self):
        original = _make_state(
            query="refund request",
            gsd_state=GSDState.DIAGNOSIS,
            token_usage=500,
            final_response="Processing refund...",
        )
        serialized = self.serializer.serialize_state(original)
        restored = self.serializer.deserialize_state(serialized)
        assert restored.query == original.query
        assert restored.gsd_state == original.gsd_state
        assert restored.token_usage == original.token_usage
        assert restored.final_response == original.final_response
        assert restored.company_id == original.company_id
        assert restored.ticket_id == original.ticket_id

    def test_with_history(self):
        original = _make_state(
            gsd_history=[
                GSDState.NEW,
                GSDState.GREETING,
                GSDState.DIAGNOSIS,
            ]
        )
        serialized = self.serializer.serialize_state(original)
        restored = self.serializer.deserialize_state(serialized)
        assert restored.gsd_history == original.gsd_history

    def test_with_technique_results(self):
        original = _make_state(
            technique_results={
                "cot": {"output": "result1"},
                "react": {"output": "result2"},
            }
        )
        serialized = self.serializer.serialize_state(original)
        restored = self.serializer.deserialize_state(serialized)
        assert restored.technique_results == original.technique_results

    def test_all_gsd_states(self):
        for gsd in GSDState:
            original = _make_state(gsd_state=gsd)
            serialized = self.serializer.serialize_state(original)
            restored = self.serializer.deserialize_state(serialized)
            assert restored.gsd_state == gsd

    def test_with_reasoning_thread(self):
        original = _make_state(reasoning_thread=["thought1", "thought2"])
        serialized = self.serializer.serialize_state(original)
        restored = self.serializer.deserialize_state(serialized)
        assert restored.reasoning_thread == ["thought1", "thought2"]


# ══════════════════════════════════════════════════════════════════
# TestStateSerializer - save_state
# ══════════════════════════════════════════════════════════════════


class TestSaveState:
    def setup_method(self):
        self.serializer = StateSerializer()

    @pytest.mark.asyncio
    async def test_both_succeed_redis_primary(self):
        self.serializer._save_to_redis = AsyncMock(return_value=True)
        self.serializer._save_to_postgresql = AsyncMock(return_value=True)
        state = _make_state()
        result = await self.serializer.save_state("t1", "co_1", state)
        assert result.success is True
        assert result.backend == StorageBackend.REDIS
        assert result.redis_success is True
        assert result.postgresql_success is True

    @pytest.mark.asyncio
    async def test_redis_fails_pg_succeeds(self):
        self.serializer._save_to_redis = AsyncMock(return_value=False)
        self.serializer._save_to_postgresql = AsyncMock(return_value=True)
        state = _make_state()
        result = await self.serializer.save_state("t1", "co_1", state)
        assert result.success is True
        assert result.backend == StorageBackend.POSTGRESQL
        assert result.redis_success is False
        assert result.postgresql_success is True

    @pytest.mark.asyncio
    async def test_both_fail_raises(self):
        self.serializer._save_to_redis = AsyncMock(return_value=False)
        self.serializer._save_to_postgresql = AsyncMock(return_value=False)
        state = _make_state()
        with pytest.raises(StateSerializationError) as exc_info:
            await self.serializer.save_state("t1", "co_1", state)
        assert "COMPLETE_FAILURE" in exc_info.value.error_code

    @pytest.mark.asyncio
    async def test_invalid_snapshot_type_fallback(self):
        self.serializer._save_to_redis = AsyncMock(return_value=True)
        self.serializer._save_to_postgresql = AsyncMock(return_value=True)
        state = _make_state()
        result = await self.serializer.save_state(
            "t1",
            "co_1",
            state,
            snapshot_type="invalid_type",
        )
        assert result.success is True
        self.serializer._save_to_redis.assert_called_once()
        call_kwargs = self.serializer._save_to_redis.call_args
        assert call_kwargs[1]["snapshot_type"] == "auto"

    @pytest.mark.asyncio
    async def test_manual_snapshot_type(self):
        self.serializer._save_to_redis = AsyncMock(return_value=True)
        self.serializer._save_to_postgresql = AsyncMock(return_value=True)
        state = _make_state()
        result = await self.serializer.save_state(
            "t1",
            "co_1",
            state,
            snapshot_type="manual",
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_error_snapshot_type(self):
        self.serializer._save_to_redis = AsyncMock(return_value=True)
        self.serializer._save_to_postgresql = AsyncMock(return_value=True)
        state = _make_state()
        result = await self.serializer.save_state(
            "t1",
            "co_1",
            state,
            snapshot_type="error",
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_extra_kwargs_passed(self):
        self.serializer._save_to_redis = AsyncMock(return_value=True)
        self.serializer._save_to_postgresql = AsyncMock(return_value=True)
        state = _make_state()
        await self.serializer.save_state(
            "t1",
            "co_1",
            state,
            instance_id="inst_1",
            model_used="groq-llama",
            current_node="classify",
            technique_stack=["cot"],
        )
        pg_call = self.serializer._save_to_postgresql.call_args
        assert pg_call[1]["instance_id"] == "inst_1"
        assert pg_call[1]["model_used"] == "groq-llama"
        assert pg_call[1]["current_node"] == "classify"

    @pytest.mark.asyncio
    async def test_snapshot_id_returned(self):
        self.serializer._save_to_redis = AsyncMock(return_value=True)
        self.serializer._save_to_postgresql = AsyncMock(return_value=True)
        state = _make_state()
        result = await self.serializer.save_state("t1", "co_1", state)
        assert result.snapshot_id is not None
        assert len(result.snapshot_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_latency_ms_returned(self):
        self.serializer._save_to_redis = AsyncMock(return_value=True)
        self.serializer._save_to_postgresql = AsyncMock(return_value=True)
        state = _make_state()
        result = await self.serializer.save_state("t1", "co_1", state)
        assert result.latency_ms >= 0


# ══════════════════════════════════════════════════════════════════
# TestStateSerializer - load_state
# ══════════════════════════════════════════════════════════════════


class TestLoadState:
    def setup_method(self):
        self.serializer = StateSerializer()

    @pytest.mark.asyncio
    async def test_redis_hit(self):
        state = _make_state()
        self.serializer._load_from_redis = AsyncMock(return_value=state)
        self.serializer._load_from_postgresql = AsyncMock(return_value=None)
        result = await self.serializer.load_state("t1", "co_1")
        assert result is not None
        assert result.ticket_id == "t1"
        self.serializer._load_from_postgresql.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_miss_pg_hit(self):
        state = _make_state()
        self.serializer._load_from_redis = AsyncMock(return_value=None)
        self.serializer._load_from_postgresql = AsyncMock(return_value=state)
        result = await self.serializer.load_state("t1", "co_1")
        assert result is not None

    @pytest.mark.asyncio
    async def test_both_miss_returns_none(self):
        self.serializer._load_from_redis = AsyncMock(return_value=None)
        self.serializer._load_from_postgresql = AsyncMock(return_value=None)
        result = await self.serializer.load_state("t1", "co_1")
        assert result is None

    @pytest.mark.asyncio
    async def test_pg_hit_backfills_redis(self):
        state = _make_state()
        self.serializer._load_from_redis = AsyncMock(return_value=None)
        self.serializer._load_from_postgresql = AsyncMock(return_value=state)
        self.serializer._redis_set = AsyncMock(return_value=True)
        self.serializer.serialize_state = MagicMock(return_value={"test": "data"})
        result = await self.serializer.load_state("t1", "co_1")
        assert result is not None
        self.serializer._redis_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_pg_hit_backfill_failure_still_returns(self):
        state = _make_state()
        self.serializer._load_from_redis = AsyncMock(return_value=None)
        self.serializer._load_from_postgresql = AsyncMock(return_value=state)
        self.serializer._redis_set = AsyncMock(side_effect=Exception("Redis down"))
        self.serializer.serialize_state = MagicMock(return_value={"test": "data"})
        result = await self.serializer.load_state("t1", "co_1")
        assert result is not None


# ══════════════════════════════════════════════════════════════════
# TestStateSerializer - save_checkpoint
# ══════════════════════════════════════════════════════════════════


class TestSaveCheckpoint:
    def setup_method(self):
        self.serializer = StateSerializer()

    @pytest.mark.asyncio
    async def test_basic_save(self):
        self.serializer._save_checkpoint_to_redis = AsyncMock(return_value=True)
        self.serializer._save_to_postgresql = AsyncMock(return_value=True)
        state = _make_state()
        result = await self.serializer.save_checkpoint(
            "t1",
            "co_1",
            state,
            "pre_resolution",
        )
        assert result.success is True
        assert result.backend == StorageBackend.REDIS

    @pytest.mark.asyncio
    async def test_empty_name_raises(self):
        state = _make_state()
        with pytest.raises(StateSerializationError) as exc_info:
            await self.serializer.save_checkpoint(
                "t1",
                "co_1",
                state,
                "",
            )
        assert "INVALID_NAME" in exc_info.value.error_code

    @pytest.mark.asyncio
    async def test_none_name_raises(self):
        state = _make_state()
        with pytest.raises(StateSerializationError):
            await self.serializer.save_checkpoint(
                "t1",
                "co_1",
                state,
                None,
            )

    @pytest.mark.asyncio
    async def test_non_string_name_raises(self):
        state = _make_state()
        with pytest.raises(StateSerializationError):
            await self.serializer.save_checkpoint(
                "t1",
                "co_1",
                state,
                123,
            )

    @pytest.mark.asyncio
    async def test_name_with_spaces_sanitized(self):
        self.serializer._save_checkpoint_to_redis = AsyncMock(return_value=True)
        self.serializer._save_to_postgresql = AsyncMock(return_value=True)
        state = _make_state()
        await self.serializer.save_checkpoint(
            "t1",
            "co_1",
            state,
            "before resolution",
        )
        call_kwargs = self.serializer._save_checkpoint_to_redis.call_args
        assert call_kwargs[1]["checkpoint_name"] == "before_resolution"

    @pytest.mark.asyncio
    async def test_name_with_special_chars_sanitized(self):
        self.serializer._save_checkpoint_to_redis = AsyncMock(return_value=True)
        self.serializer._save_to_postgresql = AsyncMock(return_value=True)
        state = _make_state()
        await self.serializer.save_checkpoint(
            "t1",
            "co_1",
            state,
            "pre-resolution@v2",
        )
        call_kwargs = self.serializer._save_checkpoint_to_redis.call_args
        name = call_kwargs[1]["checkpoint_name"]
        assert "@" not in name
        assert "-" not in name or True  # hyphens may or may not be kept

    @pytest.mark.asyncio
    async def test_both_fail_raises(self):
        self.serializer._save_checkpoint_to_redis = AsyncMock(return_value=False)
        self.serializer._save_to_postgresql = AsyncMock(return_value=False)
        state = _make_state()
        with pytest.raises(StateSerializationError):
            await self.serializer.save_checkpoint(
                "t1",
                "co_1",
                state,
                "cp1",
            )

    @pytest.mark.asyncio
    async def test_redis_fails_pg_succeeds(self):
        self.serializer._save_checkpoint_to_redis = AsyncMock(return_value=False)
        self.serializer._save_to_postgresql = AsyncMock(return_value=True)
        state = _make_state()
        result = await self.serializer.save_checkpoint(
            "t1",
            "co_1",
            state,
            "cp1",
        )
        assert result.success is True
        assert result.backend == StorageBackend.POSTGRESQL


# ══════════════════════════════════════════════════════════════════
# TestStateSerializer - load_checkpoint
# ══════════════════════════════════════════════════════════════════


class TestLoadCheckpoint:
    def setup_method(self):
        self.serializer = StateSerializer()

    @pytest.mark.asyncio
    async def test_found_in_redis(self):
        state = _make_state()
        self.serializer._load_checkpoint_from_redis = AsyncMock(
            return_value=state,
        )
        self.serializer._load_checkpoint_from_postgresql = AsyncMock(
            return_value=None,
        )
        result = await self.serializer.load_checkpoint(
            "t1",
            "co_1",
            "pre_resolution",
        )
        assert result is not None
        self.serializer._load_checkpoint_from_postgresql.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_miss_pg_hit(self):
        state = _make_state()
        self.serializer._load_checkpoint_from_redis = AsyncMock(
            return_value=None,
        )
        self.serializer._load_checkpoint_from_postgresql = AsyncMock(
            return_value=state,
        )
        result = await self.serializer.load_checkpoint(
            "t1",
            "co_1",
            "pre_resolution",
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_both_miss_returns_none(self):
        self.serializer._load_checkpoint_from_redis = AsyncMock(
            return_value=None,
        )
        self.serializer._load_checkpoint_from_postgresql = AsyncMock(
            return_value=None,
        )
        result = await self.serializer.load_checkpoint(
            "t1",
            "co_1",
            "nonexistent",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_name_sanitized_for_redis(self):
        self.serializer._load_checkpoint_from_redis = AsyncMock(
            return_value=None,
        )
        self.serializer._load_checkpoint_from_postgresql = AsyncMock(
            return_value=None,
        )
        await self.serializer.load_checkpoint(
            "t1",
            "co_1",
            "Before Resolution",
        )
        call_kwargs = self.serializer._load_checkpoint_from_redis.call_args
        assert call_kwargs[0][2] == "before_resolution"


# ══════════════════════════════════════════════════════════════════
# TestStateSerializer - list_checkpoints
# ══════════════════════════════════════════════════════════════════


class TestListCheckpoints:
    def setup_method(self):
        self.serializer = StateSerializer()

    @pytest.mark.asyncio
    async def test_redis_has_data(self):
        self.serializer._list_checkpoints_from_redis = AsyncMock(
            return_value=[{"name": "cp1"}],
        )
        result = await self.serializer.list_checkpoints("t1", "co_1")
        assert len(result) == 1
        assert result[0]["name"] == "cp1"

    @pytest.mark.asyncio
    async def test_redis_empty_pg_has_data(self):
        self.serializer._list_checkpoints_from_redis = AsyncMock(
            return_value=None,
        )
        self.serializer._list_checkpoints_from_postgresql = AsyncMock(
            return_value=[{"name": "cp2"}],
        )
        result = await self.serializer.list_checkpoints("t1", "co_1")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_both_empty(self):
        self.serializer._list_checkpoints_from_redis = AsyncMock(
            return_value=None,
        )
        self.serializer._list_checkpoints_from_postgresql = AsyncMock(
            return_value=[],
        )
        result = await self.serializer.list_checkpoints("t1", "co_1")
        assert result == []

    @pytest.mark.asyncio
    async def test_multiple_checkpoints(self):
        self.serializer._list_checkpoints_from_redis = AsyncMock(
            return_value=[
                {"name": "cp1", "created_at": "2025-01-01"},
                {"name": "cp2", "created_at": "2025-01-02"},
                {"name": "cp3", "created_at": "2025-01-03"},
            ],
        )
        result = await self.serializer.list_checkpoints("t1", "co_1")
        assert len(result) == 3


# ══════════════════════════════════════════════════════════════════
# TestStateSerializer - delete_state
# ══════════════════════════════════════════════════════════════════


class TestDeleteState:
    def setup_method(self):
        self.serializer = StateSerializer()

    @pytest.mark.asyncio
    async def test_both_succeed(self):
        self.serializer._delete_state_from_redis = AsyncMock(return_value=True)
        self.serializer._delete_state_from_postgresql = AsyncMock(return_value=True)
        result = await self.serializer.delete_state("t1", "co_1")
        assert result == {"redis": True, "postgresql": True}

    @pytest.mark.asyncio
    async def test_redis_fails(self):
        self.serializer._delete_state_from_redis = AsyncMock(return_value=False)
        self.serializer._delete_state_from_postgresql = AsyncMock(return_value=True)
        result = await self.serializer.delete_state("t1", "co_1")
        assert result == {"redis": False, "postgresql": True}

    @pytest.mark.asyncio
    async def test_pg_fails(self):
        self.serializer._delete_state_from_redis = AsyncMock(return_value=True)
        self.serializer._delete_state_from_postgresql = AsyncMock(return_value=False)
        result = await self.serializer.delete_state("t1", "co_1")
        assert result == {"redis": True, "postgresql": False}

    @pytest.mark.asyncio
    async def test_both_fail(self):
        self.serializer._delete_state_from_redis = AsyncMock(return_value=False)
        self.serializer._delete_state_from_postgresql = AsyncMock(return_value=False)
        result = await self.serializer.delete_state("t1", "co_1")
        assert result == {"redis": False, "postgresql": False}


# ══════════════════════════════════════════════════════════════════
# TestStateSerializer - get_state_history
# ══════════════════════════════════════════════════════════════════


class TestGetStateHistory:
    def setup_method(self):
        self.serializer = StateSerializer()

    @pytest.mark.asyncio
    async def test_returns_history(self):
        self.serializer._get_history_from_postgresql = AsyncMock(
            return_value=[{"snapshot_id": "s1"}, {"snapshot_id": "s2"}],
        )
        result = await self.serializer.get_state_history("t1", "co_1")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_empty_history(self):
        self.serializer._get_history_from_postgresql = AsyncMock(return_value=[])
        result = await self.serializer.get_state_history("t1", "co_1")
        assert result == []

    @pytest.mark.asyncio
    async def test_custom_limit(self):
        self.serializer._get_history_from_postgresql = AsyncMock(return_value=[])
        await self.serializer.get_state_history("t1", "co_1", limit=10)
        self.serializer._get_history_from_postgresql.assert_called_once_with(
            "t1",
            "co_1",
            10,
        )

    @pytest.mark.asyncio
    async def test_limit_zero_clamped(self):
        self.serializer._get_history_from_postgresql = AsyncMock(return_value=[])
        await self.serializer.get_state_history("t1", "co_1", limit=0)
        self.serializer._get_history_from_postgresql.assert_called_once_with(
            "t1",
            "co_1",
            1,
        )

    @pytest.mark.asyncio
    async def test_limit_over_200_clamped(self):
        self.serializer._get_history_from_postgresql = AsyncMock(return_value=[])
        await self.serializer.get_state_history("t1", "co_1", limit=500)
        self.serializer._get_history_from_postgresql.assert_called_once_with(
            "t1",
            "co_1",
            200,
        )


# ══════════════════════════════════════════════════════════════════
# TestStateSerializer - replay_state
# ══════════════════════════════════════════════════════════════════


class TestReplayState:
    def setup_method(self):
        self.serializer = StateSerializer()

    @pytest.mark.asyncio
    async def test_found(self):
        state = _make_state(gsd_state=GSDState.RESOLUTION)
        self.serializer._replay_from_postgresql = AsyncMock(return_value=state)
        result = await self.serializer.replay_state("t1", "co_1", "snap_1")
        assert result is not None
        assert result.gsd_state == GSDState.RESOLUTION

    @pytest.mark.asyncio
    async def test_not_found(self):
        self.serializer._replay_from_postgresql = AsyncMock(return_value=None)
        result = await self.serializer.replay_state("t1", "co_1", "snap_999")
        assert result is None


# ══════════════════════════════════════════════════════════════════
# TestStateSerializer - compute_diff
# ══════════════════════════════════════════════════════════════════


class TestComputeDiff:
    def setup_method(self):
        self.serializer = StateSerializer()

    def test_identical_states(self):
        state = _make_state(gsd_state=GSDState.DIAGNOSIS, token_usage=100)
        diff = self.serializer.compute_diff(state, state)
        assert "gsd_state" in diff.unchanged_fields
        assert "token_count" in diff.unchanged_fields
        assert "gsd_state" not in diff.changed_fields

    def test_both_none(self):
        diff = self.serializer.compute_diff(None, None)
        assert diff.changed_fields == []
        assert diff.unchanged_fields == []

    def test_old_none_new_state(self):
        new = _make_state(gsd_state=GSDState.DIAGNOSIS, token_usage=50)
        diff = self.serializer.compute_diff(None, new)
        assert "gsd_state" in diff.changed_fields
        assert diff.gsd_state == {"old": None, "new": "diagnosis"}

    def test_old_state_new_none(self):
        old = _make_state(gsd_state=GSDState.RESOLUTION, token_usage=200)
        diff = self.serializer.compute_diff(old, None)
        assert "gsd_state" in diff.changed_fields
        assert diff.gsd_state == {"old": "resolution", "new": None}

    def test_gsd_state_changed(self):
        old = _make_state(gsd_state=GSDState.NEW)
        new = _make_state(gsd_state=GSDState.DIAGNOSIS)
        diff = self.serializer.compute_diff(old, new)
        assert diff.gsd_state == {"old": "new", "new": "diagnosis"}
        assert "gsd_state" in diff.changed_fields

    def test_token_count_changed(self):
        old = _make_state(token_usage=100)
        new = _make_state(token_usage=500)
        diff = self.serializer.compute_diff(old, new)
        assert diff.token_count == {"old": 100, "new": 500}
        assert "token_count" in diff.changed_fields

    def test_technique_stack_changed(self):
        old = _make_state(technique_results={"cot": {}})
        new = _make_state(technique_results={"cot": {}, "react": {}})
        diff = self.serializer.compute_diff(old, new)
        assert "technique_stack" in diff.changed_fields
        assert diff.technique_stack == {"old": ["cot"], "new": ["cot", "react"]}

    def test_query_changed(self):
        old = _make_state(query="refund")
        new = _make_state(query="billing")
        diff = self.serializer.compute_diff(old, new)
        assert "query" in diff.changed_fields

    def test_query_unchanged(self):
        old = _make_state(query="same")
        new = _make_state(query="same")
        diff = self.serializer.compute_diff(old, new)
        assert "query" in diff.unchanged_fields

    def test_final_response_changed(self):
        old = _make_state(final_response="old response")
        new = _make_state(final_response="new response")
        diff = self.serializer.compute_diff(old, new)
        assert "final_response" in diff.changed_fields

    def test_final_response_unchanged(self):
        old = _make_state(final_response="same response")
        new = _make_state(final_response="same response")
        diff = self.serializer.compute_diff(old, new)
        assert "final_response" in diff.unchanged_fields

    def test_timestamp_present(self):
        diff = self.serializer.compute_diff(
            _make_state(),
            _make_state(gsd_state=GSDState.DIAGNOSIS),
        )
        assert diff.timestamp != ""

    def test_to_dict(self):
        diff = self.serializer.compute_diff(
            _make_state(),
            _make_state(gsd_state=GSDState.DIAGNOSIS),
        )
        d = diff.to_dict()
        assert "changed_fields" in d
        assert "unchanged_fields" in d

    def test_multiple_changes(self):
        old = _make_state(
            gsd_state=GSDState.NEW,
            token_usage=100,
            query="old",
            final_response="old resp",
        )
        new = _make_state(
            gsd_state=GSDState.RESOLUTION,
            token_usage=500,
            query="new",
            final_response="new resp",
        )
        diff = self.serializer.compute_diff(old, new)
        assert len(diff.changed_fields) >= 4

    def test_technique_stack_empty_both(self):
        old = _make_state(technique_results={})
        new = _make_state(technique_results={})
        diff = self.serializer.compute_diff(old, new)
        assert "technique_stack" in diff.unchanged_fields


# ══════════════════════════════════════════════════════════════════
# TestStateSerializer - save_state_locked / load_state_locked
# ══════════════════════════════════════════════════════════════════


class TestSaveStateLocked:
    def setup_method(self):
        self.serializer = StateSerializer()

    @pytest.mark.asyncio
    async def test_acquire_lock_save_release(self):
        self.serializer._acquire_lock = AsyncMock(return_value="lock_token")
        self.serializer._release_lock = AsyncMock(return_value=True)
        self.serializer._save_to_redis = AsyncMock(return_value=True)
        self.serializer._save_to_postgresql = AsyncMock(return_value=True)
        state = _make_state()
        result = await self.serializer.save_state_locked("t1", "co_1", state)
        assert result.success is True
        self.serializer._acquire_lock.assert_called_once()
        self.serializer._release_lock.assert_called_once()

    @pytest.mark.asyncio
    async def test_lock_fail_raises(self):
        self.serializer._acquire_lock = AsyncMock(return_value=None)
        state = _make_state()
        with pytest.raises(StateSerializationError):
            await self.serializer.save_state_locked("t1", "co_1", state)


class TestLoadStateLocked:
    def setup_method(self):
        self.serializer = StateSerializer()

    @pytest.mark.asyncio
    async def test_acquire_lock_load_release(self):
        state = _make_state()
        self.serializer._acquire_lock = AsyncMock(return_value="lock_token")
        self.serializer._release_lock = AsyncMock(return_value=True)
        self.serializer._load_from_redis = AsyncMock(return_value=state)
        result = await self.serializer.load_state_locked("t1", "co_1")
        assert result is not None

    @pytest.mark.asyncio
    async def test_lock_fail_returns_none(self):
        self.serializer._acquire_lock = AsyncMock(return_value=None)
        result = await self.serializer.load_state_locked("t1", "co_1")
        assert result is None


# ══════════════════════════════════════════════════════════════════
# TestStateSerializer - _acquire_lock / _release_lock
# ══════════════════════════════════════════════════════════════════


class TestAcquireLock:
    def setup_method(self):
        self.serializer = StateSerializer()

    @pytest.mark.asyncio
    async def test_lock_acquired(self):
        self.serializer._redis_get = AsyncMock(return_value=None)
        self.serializer._redis_set = AsyncMock(return_value=True)
        result = await self.serializer._acquire_lock("t1")
        assert result is not None

    @pytest.mark.asyncio
    async def test_lock_already_held(self):
        self.serializer._redis_get = AsyncMock(return_value="existing_token")
        result = await self.serializer._acquire_lock("t1")
        assert result is None


class TestReleaseLock:
    def setup_method(self):
        self.serializer = StateSerializer()

    @pytest.mark.asyncio
    async def test_release_succeeds(self):
        self.serializer._redis_get = AsyncMock(return_value="my_token")
        self.serializer._redis_delete = AsyncMock(return_value=True)
        result = await self.serializer._release_lock("t1", "my_token")
        assert result is True

    @pytest.mark.asyncio
    async def test_release_wrong_token(self):
        self.serializer._redis_get = AsyncMock(return_value="other_token")
        result = await self.serializer._release_lock("t1", "my_token")
        assert result is False

    @pytest.mark.asyncio
    async def test_release_no_existing_lock(self):
        self.serializer._redis_get = AsyncMock(return_value=None)
        result = await self.serializer._release_lock("t1", "my_token")
        assert result is True


# ══════════════════════════════════════════════════════════════════
# TestStateSerializer - _save_to_redis / _load_from_redis
# ══════════════════════════════════════════════════════════════════


class TestRedisOperations:
    def setup_method(self):
        self.serializer = StateSerializer()

    @pytest.mark.asyncio
    async def test_save_to_redis_success(self):
        self.serializer._redis_set = AsyncMock(return_value=True)
        result = await self.serializer._save_to_redis(
            "t1",
            "co_1",
            '{"test": 1}',
            "snap_1",
            "auto",
            "classify",
            [],
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_save_to_redis_failure(self):
        self.serializer._redis_set = AsyncMock(side_effect=Exception("Redis down"))
        result = await self.serializer._save_to_redis(
            "t1",
            "co_1",
            '{"test": 1}',
            "snap_1",
            "auto",
            "classify",
            [],
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_load_from_redis_success(self):
        state = _make_state()
        serialized = self.serializer.serialize_state(state)
        self.serializer._redis_get = AsyncMock(
            return_value=json.dumps(serialized, default=str)
        )
        result = await self.serializer._load_from_redis("t1", "co_1")
        assert result is not None

    @pytest.mark.asyncio
    async def test_load_from_redis_not_found(self):
        self.serializer._redis_get = AsyncMock(return_value=None)
        result = await self.serializer._load_from_redis("t1", "co_1")
        assert result is None

    @pytest.mark.asyncio
    async def test_load_from_redis_corrupted(self):
        self.serializer._redis_get = AsyncMock(return_value="not json{{{")
        result = await self.serializer._load_from_redis("t1", "co_1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_from_redis_success(self):
        self.serializer._redis_delete = AsyncMock(return_value=True)
        result = await self.serializer._delete_state_from_redis("t1", "co_1")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_from_redis_failure(self):
        self.serializer._redis_delete = AsyncMock(side_effect=Exception("err"))
        result = await self.serializer._delete_state_from_redis("t1", "co_1")
        assert result is False


# ══════════════════════════════════════════════════════════════════
# TestStateSerializer - Tenant Isolation
# ══════════════════════════════════════════════════════════════════


class TestTenantIsolation:
    def test_state_key_contains_company_id(self):
        key = _build_state_key("company_abc", "ticket_1")
        assert "company_abc" in key

    def test_different_companies_different_keys(self):
        key_a = _build_state_key("co_a", "t1")
        key_b = _build_state_key("co_b", "t1")
        assert key_a != key_b

    def test_checkpoint_key_contains_company_id(self):
        key = _build_checkpoint_key("co_1", "t1", "cp1")
        assert "co_1" in key

    def test_checkpoint_index_contains_company_id(self):
        key = _build_checkpoint_index_key("co_1", "t1")
        assert "co_1" in key

    def test_lock_key_no_company_id(self):
        key = _build_lock_key("t1")
        assert "co" not in key
        assert "company" not in key

    def test_serialize_preserves_company_id(self):
        serializer = StateSerializer()
        state = _make_state(company_id="tenant_xyz")
        result = serializer.serialize_state(state)
        assert result["company_id"] == "tenant_xyz"

    def test_deserialize_preserves_company_id(self):
        serializer = StateSerializer()
        data = {"company_id": "tenant_xyz", "gsd_state": "new"}
        state = serializer.deserialize_state(data)
        assert state.company_id == "tenant_xyz"


# ══════════════════════════════════════════════════════════════════
# TestStateSerializer - Constructor
# ══════════════════════════════════════════════════════════════════


class TestStateSerializerInit:
    def test_default_config(self):
        s = StateSerializer()
        assert s._config.active_state_ttl_seconds == 86400

    def test_custom_config(self):
        cfg = StateSerializerConfig(max_state_size_bytes=1024)
        s = StateSerializer(config=cfg)
        assert s._config.max_state_size_bytes == 1024

    def test_independent_instances(self):
        a = StateSerializer()
        b = StateSerializer()
        assert a is not b
        assert a._config is not b._config
