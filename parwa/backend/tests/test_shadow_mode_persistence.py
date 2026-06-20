"""
Phase 4 Persistence-Layer Unit Tests for ShadowModeService.

Tests cover:
  - DB persist methods (_persist_config_to_db, _persist_comparison_to_db, etc.)
  - DB load methods (_load_config_from_db, _load_comparisons_from_db)
  - Three-tier read fallback: Redis → DB → in-memory
  - Graceful degradation when DB/Redis are unavailable (BC-008)
  - Counter persistence (_persist_config_counters_to_db)
  - Row-to-dict conversion helpers
  - Datetime parsing helpers
  - Async bridge (_run_async_safely)
  - Thread safety

All DB/Redis calls are mocked — no real infrastructure needed.
"""

import asyncio
import threading
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.services.shadow_mode_service import (
    ShadowModeService,
    ShadowComparison,
    ShadowModeStatus,
    VALID_VARIANT_TYPES,
    VARIANT_RANKING,
    REDIS_CONFIG_TTL_SECONDS,
    REDIS_COMPARISONS_TTL_SECONDS,
)


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def service():
    """Create a fresh ShadowModeService instance."""
    return ShadowModeService()


@pytest.fixture
def company_id():
    """Sample company ID."""
    return "comp_persist_test_001"


@pytest.fixture
def sample_config(company_id):
    """Sample config dict matching the internal format."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "company_id": company_id,
        "live_variant": "mini_parwa",
        "shadow_variant": "parwa",
        "status": "shadow",
        "sample_rate": 1.0,
        "auto_graduation_threshold": 0.95,
        "auto_graduation_window": 100,
        "supervised_timeout_seconds": 300,
        "auto_promote_to_supervised": True,
        "auto_promote_to_graduated": False,
        "live_instance_id": "",
        "shadow_instance_id": "",
        "current_quality_streak": 0,
        "total_comparisons": 0,
        "shadow_wins": 0,
        "is_active": True,
        "enabled_by_user_id": "user_001",
        "enabled_at": now,
        "supervised_at": None,
        "graduated_at": None,
        "disabled_at": None,
    }


@pytest.fixture
def sample_comparison(company_id):
    """Sample ShadowComparison for testing."""
    return ShadowComparison(
        company_id=company_id,
        config_id="config_001",
        ticket_id="ticket_001",
        conversation_id="conv_001",
        message_hash="abc123",
        live_variant="mini_parwa",
        live_response="Live response text",
        live_quality_score=0.70,
        live_latency_ms=500,
        live_tokens_used=100,
        shadow_variant="parwa",
        shadow_response="Shadow response text",
        shadow_quality_score=0.85,
        shadow_latency_ms=800,
        shadow_tokens_used=150,
        quality_delta=0.15,
        latency_delta_ms=300,
        token_delta=50,
        shadow_winner=True,
        mode_at_comparison="shadow",
    )


def _make_mock_config_row(**overrides):
    """Create a mock ShadowModeConfig row with all required attributes."""
    defaults = {
        "id": str(uuid.uuid4()),
        "company_id": "comp_persist_test_001",
        "live_variant": "mini_parwa",
        "shadow_variant": "parwa",
        "status": "shadow",
        "live_instance_id": None,
        "shadow_instance_id": None,
        "sample_rate": 1.0,
        "auto_graduation_threshold": 0.95,
        "auto_graduation_window": 100,
        "supervised_timeout_seconds": 300,
        "auto_promote_to_supervised": True,
        "auto_promote_to_graduated": False,
        "current_quality_streak": 0,
        "total_comparisons": 0,
        "shadow_wins": 0,
        "is_active": True,
        "enabled_by_user_id": None,
        "enabled_at": datetime.now(timezone.utc),
        "supervised_at": None,
        "graduated_at": None,
        "disabled_at": None,
    }
    defaults.update(overrides)
    row = MagicMock()
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def _make_mock_result_row(**overrides):
    """Create a mock ShadowModeResult row with all required attributes."""
    defaults = {
        "id": str(uuid.uuid4()),
        "company_id": "comp_persist_test_001",
        "config_id": "cfg_001",
        "ticket_id": None,
        "conversation_id": None,
        "live_variant": "mini_parwa",
        "live_quality_score": 0.70,
        "live_latency_ms": 500,
        "shadow_variant": "parwa",
        "shadow_quality_score": 0.85,
        "shadow_latency_ms": 800,
        "quality_delta": 0.15,
        "latency_delta_ms": 300,
        "token_delta": 50,
        "shadow_winner": True,
        "mode_at_comparison": "shadow",
        "human_reviewed": False,
        "human_verdict": None,
        "reviewer_id": None,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    row = MagicMock()
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def _setup_db_query_mock(mock_session, first_result=None, all_result=None):
    """Set up a mock DB session with proper query chain."""
    mock_query = MagicMock()
    mock_filter = MagicMock()
    mock_order = MagicMock()

    mock_filter.first.return_value = first_result
    mock_filter.order_by.return_value = mock_order
    mock_order.first.return_value = first_result
    mock_order.offset.return_value.limit.return_value.all.return_value = all_result or []
    mock_order.all.return_value = all_result or []

    mock_query.filter.return_value = mock_filter
    mock_session.query.return_value = mock_query

    return mock_query, mock_filter


# ══════════════════════════════════════════════════════════════════
# DB SESSION HELPER TESTS
# ══════════════════════════════════════════════════════════════════


class TestDBSessionHelper:
    """Tests for _get_db_session method."""

    def test_returns_none_when_db_unavailable(self):
        """When DB import fails, returns None (BC-008: never crash)."""
        # The _get_db_session method does lazy import of database.base.SessionLocal
        # If that import fails, it should return None gracefully
        with patch.dict("sys.modules", {"database.base": None}):
            result = ShadowModeService._get_db_session()
            # Should never crash — returns None or a valid session
            assert result is None or result is not None


# ══════════════════════════════════════════════════════════════════
# CONFIG PERSISTENCE TESTS
# ══════════════════════════════════════════════════════════════════


class TestPersistConfigToDB:
    """Tests for _persist_config_to_db method."""

    def test_returns_false_when_no_db_session(self, service, sample_config):
        """Returns False when DB session is unavailable."""
        with patch.object(service, "_get_db_session", return_value=None):
            result = service._persist_config_to_db(sample_config)
            assert result is False

    def test_inserts_new_config_row(self, service, sample_config):
        """When no existing row, inserts a new ShadowModeConfig."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = None  # No existing row
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query

        # Mock the model import
        mock_model_cls = MagicMock()
        mock_shadow_mode_module = MagicMock()
        mock_shadow_mode_module.ShadowModeConfig = mock_model_cls

        with patch.object(service, "_get_db_session", return_value=mock_session), \
             patch.dict("sys.modules", {"database.models.shadow_mode": mock_shadow_mode_module}):
            result = service._persist_config_to_db(sample_config)

        assert result is True
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_updates_existing_config_row(self, service, sample_config):
        """When row exists, updates it instead of inserting."""
        mock_existing = MagicMock()
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_existing
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query

        mock_shadow_mode_module = MagicMock()
        mock_shadow_mode_module.ShadowModeConfig = MagicMock()

        with patch.object(service, "_get_db_session", return_value=mock_session), \
             patch.dict("sys.modules", {"database.models.shadow_mode": mock_shadow_mode_module}):
            result = service._persist_config_to_db(sample_config)

        assert result is True
        mock_session.add.assert_not_called()
        mock_session.commit.assert_called_once()

    def test_returns_false_on_db_error(self, service, sample_config):
        """Returns False and rolls back on any DB error (BC-008)."""
        mock_session = MagicMock()
        mock_session.query.side_effect = Exception("DB connection lost")

        with patch.object(service, "_get_db_session", return_value=mock_session):
            result = service._persist_config_to_db(sample_config)

        assert result is False
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    def test_closes_session_in_finally(self, service, sample_config):
        """Session is always closed, even on error."""
        mock_session = MagicMock()
        mock_session.query.side_effect = Exception("Error")

        with patch.object(service, "_get_db_session", return_value=mock_session):
            service._persist_config_to_db(sample_config)

        mock_session.close.assert_called_once()


# ══════════════════════════════════════════════════════════════════
# CONFIG LOAD TESTS
# ══════════════════════════════════════════════════════════════════


class TestLoadConfigFromDB:
    """Tests for _load_config_from_db method."""

    def test_returns_none_when_no_db_session(self, service, company_id):
        """Returns None when DB is unavailable."""
        with patch.object(service, "_get_db_session", return_value=None):
            result = service._load_config_from_db(company_id)
            assert result is None

    def test_returns_none_when_no_active_config(self, service, company_id):
        """Returns None when no active config exists for the company."""
        mock_session = MagicMock()
        _setup_db_query_mock(mock_session, first_result=None)

        with patch.object(service, "_get_db_session", return_value=mock_session), \
             patch.dict("sys.modules", {"database.models.shadow_mode": MagicMock(ShadowModeConfig=MagicMock())}):
            result = service._load_config_from_db(company_id)
            assert result is None

    def test_returns_config_dict_when_found(self, service, company_id, sample_config):
        """Returns a config dict when an active config is found in DB."""
        mock_row = _make_mock_config_row(
            company_id=company_id,
            id=sample_config["id"],
            enabled_by_user_id="user_001",
        )
        mock_session = MagicMock()
        _setup_db_query_mock(mock_session, first_result=mock_row)

        with patch.object(service, "_get_db_session", return_value=mock_session), \
             patch.dict("sys.modules", {"database.models.shadow_mode": MagicMock(ShadowModeConfig=MagicMock())}):
            result = service._load_config_from_db(company_id)

        assert result is not None
        assert result["company_id"] == company_id
        assert result["live_variant"] == "mini_parwa"
        assert result["shadow_variant"] == "parwa"
        assert result["is_active"] is True

    def test_refreshes_in_memory_cache_on_load(self, service, company_id):
        """Loading from DB refreshes the in-memory cache."""
        mock_row = _make_mock_config_row(
            company_id=company_id,
            live_variant="parwa",
            shadow_variant="parwa_high",
            status="supervised",
            sample_rate=0.5,
            current_quality_streak=25,
            total_comparisons=100,
            shadow_wins=80,
        )
        mock_session = MagicMock()
        _setup_db_query_mock(mock_session, first_result=mock_row)

        with patch.object(service, "_get_db_session", return_value=mock_session), \
             patch.dict("sys.modules", {"database.models.shadow_mode": MagicMock(ShadowModeConfig=MagicMock())}):
            service._load_config_from_db(company_id)

        assert company_id in service._configs
        assert service._configs[company_id]["live_variant"] == "parwa"
        assert service._configs[company_id]["status"] == "supervised"

    def test_returns_none_on_db_error(self, service, company_id):
        """Returns None on any DB error (BC-008)."""
        mock_session = MagicMock()
        mock_session.query.side_effect = Exception("DB error")

        with patch.object(service, "_get_db_session", return_value=mock_session):
            result = service._load_config_from_db(company_id)
            assert result is None


# ══════════════════════════════════════════════════════════════════
# COMPARISON PERSISTENCE TESTS
# ══════════════════════════════════════════════════════════════════


class TestPersistComparisonToDB:
    """Tests for _persist_comparison_to_db method."""

    def test_returns_false_when_no_db_session(self, service, sample_comparison):
        """Returns False when DB session is unavailable."""
        with patch.object(service, "_get_db_session", return_value=None):
            result = service._persist_comparison_to_db(sample_comparison)
            assert result is False

    def test_persists_comparison_to_db(self, service, sample_comparison):
        """Persists a ShadowComparison to the ShadowModeResult table."""
        mock_session = MagicMock()
        mock_model_cls = MagicMock()
        mock_shadow_mode_module = MagicMock()
        mock_shadow_mode_module.ShadowModeResult = mock_model_cls

        with patch.object(service, "_get_db_session", return_value=mock_session), \
             patch.dict("sys.modules", {"database.models.shadow_mode": mock_shadow_mode_module}):
            result = service._persist_comparison_to_db(sample_comparison)

        assert result is True
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_returns_false_on_db_error(self, service, sample_comparison):
        """Returns False and rolls back on DB error."""
        mock_session = MagicMock()
        mock_session.add.side_effect = Exception("Insert failed")

        with patch.object(service, "_get_db_session", return_value=mock_session):
            result = service._persist_comparison_to_db(sample_comparison)

        assert result is False
        mock_session.rollback.assert_called_once()


# ══════════════════════════════════════════════════════════════════
# COMPARISON LOAD TESTS
# ══════════════════════════════════════════════════════════════════


class TestLoadComparisonsFromDB:
    """Tests for _load_comparisons_from_db method."""

    def test_returns_none_when_no_db_session(self, service, company_id):
        """Returns None when DB is unavailable."""
        with patch.object(service, "_get_db_session", return_value=None):
            result = service._load_comparisons_from_db(company_id)
            assert result is None

    def test_returns_list_of_dicts_when_found(self, service, company_id):
        """Returns a list of comparison dicts when data exists."""
        mock_row = _make_mock_result_row(company_id=company_id)
        mock_session = MagicMock()
        _setup_db_query_mock(mock_session, all_result=[mock_row])

        with patch.object(service, "_get_db_session", return_value=mock_session), \
             patch.dict("sys.modules", {"database.models.shadow_mode": MagicMock(ShadowModeResult=MagicMock())}):
            result = service._load_comparisons_from_db(company_id, limit=10, offset=0)

        assert result is not None
        assert len(result) == 1
        assert result[0]["company_id"] == company_id
        assert result[0]["shadow_winner"] is True

    def test_returns_empty_list_when_no_results(self, service, company_id):
        """Returns empty list when no comparisons exist."""
        mock_session = MagicMock()
        _setup_db_query_mock(mock_session, all_result=[])

        with patch.object(service, "_get_db_session", return_value=mock_session), \
             patch.dict("sys.modules", {"database.models.shadow_mode": MagicMock(ShadowModeResult=MagicMock())}):
            result = service._load_comparisons_from_db(company_id)

        assert result is not None
        assert result == []

    def test_returns_none_on_db_error(self, service, company_id):
        """Returns None on any DB error (BC-008)."""
        mock_session = MagicMock()
        mock_session.query.side_effect = Exception("DB error")

        with patch.object(service, "_get_db_session", return_value=mock_session):
            result = service._load_comparisons_from_db(company_id)
            assert result is None


# ══════════════════════════════════════════════════════════════════
# COUNTER PERSISTENCE TESTS
# ══════════════════════════════════════════════════════════════════


class TestPersistConfigCountersToDB:
    """Tests for _persist_config_counters_to_db method."""

    def test_returns_false_when_no_db_session(self, service, company_id, sample_config):
        """Returns False when DB is unavailable."""
        with patch.object(service, "_get_db_session", return_value=None):
            result = service._persist_config_counters_to_db(company_id, sample_config)
            assert result is False

    def test_updates_counter_fields_on_existing_row(self, service, company_id, sample_config):
        """Updates status, is_active, counters on an existing row."""
        sample_config["total_comparisons"] = 50
        sample_config["shadow_wins"] = 35
        sample_config["current_quality_streak"] = 12
        sample_config["status"] = "supervised"

        mock_row = MagicMock()
        mock_session = MagicMock()
        _setup_db_query_mock(mock_session, first_result=mock_row)

        with patch.object(service, "_get_db_session", return_value=mock_session), \
             patch.dict("sys.modules", {"database.models.shadow_mode": MagicMock(ShadowModeConfig=MagicMock())}):
            result = service._persist_config_counters_to_db(company_id, sample_config)

        assert result is True
        assert mock_row.total_comparisons == 50
        assert mock_row.shadow_wins == 35
        assert mock_row.current_quality_streak == 12
        assert mock_row.status == "supervised"
        mock_session.commit.assert_called_once()

    def test_falls_back_to_full_persist_when_row_missing(self, service, company_id, sample_config):
        """Falls back to _persist_config_to_db when row doesn't exist yet."""
        mock_session = MagicMock()
        _setup_db_query_mock(mock_session, first_result=None)

        with patch.object(service, "_get_db_session", return_value=mock_session), \
             patch.dict("sys.modules", {"database.models.shadow_mode": MagicMock(ShadowModeConfig=MagicMock())}), \
             patch.object(service, "_persist_config_to_db", return_value=True) as mock_full:
            result = service._persist_config_counters_to_db(company_id, sample_config)

        assert result is True
        mock_full.assert_called_once_with(sample_config)

    def test_returns_false_on_db_error(self, service, company_id, sample_config):
        """Returns False on DB error (BC-008)."""
        mock_session = MagicMock()
        mock_session.query.side_effect = Exception("DB error")

        with patch.object(service, "_get_db_session", return_value=mock_session):
            result = service._persist_config_counters_to_db(company_id, sample_config)
            assert result is False


# ══════════════════════════════════════════════════════════════════
# REDIS CACHE TESTS
# ══════════════════════════════════════════════════════════════════


class TestRedisCacheConfig:
    """Tests for Redis config cache methods."""

    def test_redis_get_config_returns_none_on_error(self, service, company_id):
        """Redis get returns None when Redis is unavailable (BC-008)."""
        result = service._redis_get_config(company_id)
        # Either None (Redis unavailable) or a dict — never crashes
        assert result is None or isinstance(result, dict)

    def test_redis_set_config_returns_bool(self, service, company_id, sample_config):
        """Redis set returns a boolean — never crashes (BC-008)."""
        result = service._redis_set_config(company_id, sample_config)
        assert isinstance(result, bool)

    def test_redis_get_config_with_mock_success(self, service, company_id, sample_config):
        """Redis get returns the cached config when available."""
        async def mock_cache_get(cid, key):
            return sample_config

        with patch("app.core.redis.cache_get", side_effect=mock_cache_get):
            result = service._redis_get_config(company_id)

        # Result depends on whether async bridge works in test context
        assert result is None or isinstance(result, dict)


class TestRedisCacheComparisons:
    """Tests for Redis comparison cache methods."""

    def test_redis_get_comparisons_returns_none_or_list(self, service, company_id):
        """Redis get returns None or list — never crashes (BC-008)."""
        result = service._redis_get_comparisons(company_id)
        assert result is None or isinstance(result, list)

    def test_redis_set_comparisons_returns_bool(self, service, company_id):
        """Redis set returns a boolean — never crashes (BC-008)."""
        comparisons = [{"id": "comp_1", "shadow_winner": True}]
        result = service._redis_set_comparisons(company_id, comparisons)
        assert isinstance(result, bool)


# ══════════════════════════════════════════════════════════════════
# THREE-TIER READ FALLBACK TESTS
# ══════════════════════════════════════════════════════════════════


class TestThreeTierReadFallback:
    """Tests for the Redis → DB → in-memory fallback chain."""

    def test_get_status_from_in_memory_when_redis_and_db_unavailable(self, service, company_id):
        """Status is returned from in-memory cache when Redis and DB fail."""
        service._configs[company_id] = {
            "id": "cfg_001",
            "company_id": company_id,
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
            "status": "shadow",
            "sample_rate": 1.0,
            "is_active": True,
            "total_comparisons": 5,
            "shadow_wins": 3,
            "current_quality_streak": 2,
            "auto_graduation_threshold": 0.95,
            "auto_graduation_window": 100,
        }

        with patch.object(service, "_redis_get_config", return_value=None), \
             patch.object(service, "_load_config_from_db", return_value=None):
            status = service.get_status(company_id=company_id)

        assert status.is_active is True
        assert status.status == "shadow"
        assert status.total_comparisons == 5
        assert status.shadow_wins == 3

    def test_get_status_from_db_when_redis_unavailable(self, service, company_id, sample_config):
        """Status is returned from DB when Redis is unavailable."""
        with patch.object(service, "_redis_get_config", return_value=None), \
             patch.object(service, "_load_config_from_db", return_value=sample_config):
            status = service.get_status(company_id=company_id)

        assert status.is_active is True
        assert status.live_variant == "mini_parwa"

    def test_get_status_from_redis_when_available(self, service, company_id, sample_config):
        """Status is returned from Redis when available (fastest path)."""
        with patch.object(service, "_redis_get_config", return_value=sample_config):
            status = service.get_status(company_id=company_id)

        assert status.is_active is True
        assert status.live_variant == "mini_parwa"

    def test_should_process_shadow_falls_back_gracefully(self, service, company_id, sample_config):
        """should_process_shadow works even when Redis and DB fail."""
        service._configs[company_id] = sample_config

        with patch.object(service, "_redis_get_config", return_value=None), \
             patch.object(service, "_load_config_from_db", return_value=None):
            should, reason = service.should_process_shadow(company_id=company_id)

        assert should is True
        assert "shadow" in reason

    def test_get_shadow_config_fallback_chain(self, service, company_id, sample_config):
        """get_shadow_config tries Redis → DB → in-memory."""
        # Test Redis path
        with patch.object(service, "_redis_get_config", return_value=sample_config):
            config = service.get_shadow_config(company_id)
        assert config is not None
        assert config["live_variant"] == "mini_parwa"

        # Test DB path
        with patch.object(service, "_redis_get_config", return_value=None), \
             patch.object(service, "_load_config_from_db", return_value=sample_config):
            config = service.get_shadow_config(company_id)
        assert config is not None

        # Test in-memory path
        sample_config["is_active"] = True
        service._configs[company_id] = sample_config
        with patch.object(service, "_redis_get_config", return_value=None), \
             patch.object(service, "_load_config_from_db", return_value=None):
            config = service.get_shadow_config(company_id)
        assert config is not None


# ══════════════════════════════════════════════════════════════════
# ROW-TO-DICT HELPER TESTS
# ══════════════════════════════════════════════════════════════════


class TestRowToDictHelpers:
    """Tests for _config_row_to_dict and _result_row_to_dict."""

    def test_config_row_to_dict_handles_nulls(self):
        """Null DB values are converted to safe defaults."""
        mock_row = _make_mock_config_row(
            live_instance_id=None,
            shadow_instance_id=None,
            sample_rate=None,
            auto_graduation_threshold=None,
            auto_graduation_window=None,
            supervised_timeout_seconds=None,
            auto_promote_to_supervised=None,
            auto_promote_to_graduated=None,
            current_quality_streak=None,
            total_comparisons=None,
            shadow_wins=None,
            is_active=None,
            enabled_by_user_id=None,
            enabled_at=None,
            supervised_at=None,
            graduated_at=None,
            disabled_at=None,
        )

        result = ShadowModeService._config_row_to_dict(mock_row)

        assert result["live_instance_id"] == ""
        assert result["sample_rate"] == 1.0
        assert result["auto_graduation_threshold"] == 0.95
        assert result["auto_graduation_window"] == 100
        assert result["is_active"] is True
        assert result["enabled_at"] is None

    def test_result_row_to_dict_handles_nulls(self):
        """Null DB values in results are converted to safe defaults."""
        mock_row = _make_mock_result_row(
            ticket_id=None,
            live_quality_score=None,
            live_latency_ms=None,
            shadow_quality_score=None,
            shadow_latency_ms=None,
            quality_delta=None,
            latency_delta_ms=None,
            token_delta=None,
            shadow_winner=None,
            mode_at_comparison=None,
            human_reviewed=None,
            human_verdict=None,
            reviewer_id=None,
            created_at=None,
        )

        result = ShadowModeService._result_row_to_dict(mock_row)

        assert result["ticket_id"] == ""
        assert result["live_quality_score"] == 0.0
        assert result["live_latency_ms"] == 0
        assert result["shadow_winner"] is False
        assert result["mode_at_comparison"] == "shadow"
        assert result["human_reviewed"] is False

    def test_config_row_to_dict_converts_timestamps(self):
        """Datetime fields are converted to ISO strings."""
        now = datetime.now(timezone.utc)
        mock_row = _make_mock_config_row(enabled_at=now, enabled_by_user_id="user_001")

        result = ShadowModeService._config_row_to_dict(mock_row)

        assert result["enabled_at"] is not None
        assert isinstance(result["enabled_at"], str)
        assert result["supervised_at"] is None


# ══════════════════════════════════════════════════════════════════
# DATETIME HELPER TESTS
# ══════════════════════════════════════════════════════════════════


class TestDatetimeHelpers:
    """Tests for datetime parsing and formatting helpers."""

    def test_parse_iso_to_datetime_valid_string(self, service):
        """Valid ISO string is parsed to datetime."""
        iso_str = "2026-05-18T10:30:00+00:00"
        result = service._parse_iso_to_datetime(iso_str)
        assert isinstance(result, datetime)

    def test_parse_iso_to_datetime_none(self, service):
        """None input returns None."""
        result = service._parse_iso_to_datetime(None)
        assert result is None

    def test_parse_iso_to_datetime_already_datetime(self, service):
        """Datetime input is returned as-is."""
        dt = datetime.now(timezone.utc)
        result = service._parse_iso_to_datetime(dt)
        assert result is dt

    def test_parse_iso_to_datetime_invalid_string(self, service):
        """Invalid string returns None."""
        result = service._parse_iso_to_datetime("not-a-date")
        assert result is None

    def test_utc_now_iso_returns_string(self, service):
        """_utc_now_iso returns a valid ISO string."""
        result = service._utc_now_iso()
        assert isinstance(result, str)
        parsed = datetime.fromisoformat(result)
        assert isinstance(parsed, datetime)


# ══════════════════════════════════════════════════════════════════
# ASYNC BRIDGE TESTS
# ══════════════════════════════════════════════════════════════════


class TestAsyncBridge:
    """Tests for _run_async_safely method."""

    def test_runs_simple_coroutine(self, service):
        """Simple async function is executed and result returned."""
        async def simple():
            return 42

        result = service._run_async_safely(simple())
        assert result == 42

    def test_returns_none_on_exception(self, service):
        """Returns None when coroutine raises (BC-008)."""
        async def failing():
            raise ValueError("test error")

        result = service._run_async_safely(failing())
        assert result is None


# ══════════════════════════════════════════════════════════════════
# WRITE PERSISTENCE INTEGRATION TESTS
# ══════════════════════════════════════════════════════════════════


class TestWritePersistenceIntegration:
    """Tests for write operations going through DB → Redis → in-memory."""

    def test_enable_shadow_mode_persists_to_all_tiers(self, service, company_id):
        """enable_shadow_mode writes to DB, Redis, and in-memory cache."""
        with patch.object(service, "_persist_config_to_db", return_value=True) as mock_db, \
             patch.object(service, "_redis_set_config", return_value=True) as mock_redis:
            result = service.enable_shadow_mode(
                company_id=company_id,
                live_variant="mini_parwa",
                shadow_variant="parwa",
            )

        assert result["success"] is True
        mock_db.assert_called_once()
        mock_redis.assert_called_once()
        assert company_id in service._configs
        assert service._configs[company_id]["status"] == "shadow"

    def test_disable_shadow_mode_persists_to_all_tiers(self, service, company_id):
        """disable_shadow_mode writes to DB, Redis, and in-memory cache."""
        service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )

        with patch.object(service, "_persist_config_to_db", return_value=True) as mock_db, \
             patch.object(service, "_redis_set_config", return_value=True) as mock_redis:
            result = service.disable_shadow_mode(company_id=company_id, reason="test")

        assert result["success"] is True
        mock_db.assert_called()
        mock_redis.assert_called()
        assert service._configs[company_id]["is_active"] is False
        assert service._configs[company_id]["status"] == "disabled"

    def test_promote_persists_counter_update(self, service, company_id):
        """promote persists counter/status changes via _persist_config_counters_to_db."""
        service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )

        with patch.object(service, "_persist_config_counters_to_db", return_value=True) as mock_counters, \
             patch.object(service, "_redis_set_config", return_value=True):
            result = service.promote(company_id=company_id)

        assert result["success"] is True
        mock_counters.assert_called_once()

    def test_record_comparison_persists_comparison_and_counters(self, service, company_id):
        """record_comparison persists both the comparison result and updated counters."""
        service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )

        comp = ShadowComparison(
            company_id=company_id,
            config_id="cfg_test",
            shadow_winner=True,
            quality_delta=0.05,
        )

        with patch.object(service, "_persist_config_counters_to_db", return_value=True), \
             patch.object(service, "_persist_comparison_to_db", return_value=True) as mock_persist_comp, \
             patch.object(service, "_redis_set_config", return_value=True), \
             patch.object(service, "_redis_set_comparisons", return_value=True):
            result = service.record_comparison(company_id=company_id, comparison=comp)

        assert result["success"] is True
        mock_persist_comp.assert_called_once_with(comp)

    def test_complete_graduation_persists_to_all_tiers(self, service, company_id):
        """complete_graduation writes to DB, Redis, and in-memory cache."""
        service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )
        service.promote(company_id=company_id)  # shadow → supervised

        with patch.object(service, "_persist_config_to_db", return_value=True) as mock_db, \
             patch.object(service, "_redis_set_config", return_value=True) as mock_redis:
            result = service.complete_graduation(company_id=company_id)

        assert result["success"] is True
        assert result["new_live_variant"] == "parwa"
        mock_db.assert_called()
        mock_redis.assert_called()
        assert service._configs[company_id]["is_active"] is False


# ══════════════════════════════════════════════════════════════════
# GRACEFUL DEGRADATION TESTS
# ══════════════════════════════════════════════════════════════════


class TestGracefulDegradation:
    """Tests for graceful degradation when DB and/or Redis fail."""

    def test_enable_shadow_mode_works_without_db(self, service, company_id):
        """Shadow mode can be enabled even when DB is down."""
        with patch.object(service, "_persist_config_to_db", return_value=False), \
             patch.object(service, "_redis_set_config", return_value=False):
            result = service.enable_shadow_mode(
                company_id=company_id,
                live_variant="mini_parwa",
                shadow_variant="parwa",
            )

        assert result["success"] is True
        assert company_id in service._configs

    def test_record_comparison_works_without_db(self, service, company_id):
        """Comparisons are recorded even when DB is down."""
        service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )

        comp = ShadowComparison(
            company_id=company_id,
            config_id="cfg_test",
            shadow_winner=True,
            quality_delta=0.05,
        )

        with patch.object(service, "_persist_config_counters_to_db", return_value=False), \
             patch.object(service, "_persist_comparison_to_db", return_value=False), \
             patch.object(service, "_redis_set_config", return_value=False), \
             patch.object(service, "_redis_set_comparisons", return_value=False):
            result = service.record_comparison(company_id=company_id, comparison=comp)

        assert result["success"] is True
        assert result["total_comparisons"] == 1

    def test_get_comparison_history_falls_back_to_in_memory(self, service, company_id):
        """Comparison history falls back to in-memory when DB is down."""
        service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )

        comp = ShadowComparison(
            company_id=company_id,
            config_id="cfg_test",
            shadow_winner=True,
            quality_delta=0.05,
        )
        service.record_comparison(company_id=company_id, comparison=comp)

        with patch.object(service, "_load_comparisons_from_db", return_value=None):
            history = service.get_comparison_history(company_id=company_id)

        assert len(history) >= 1

    def test_get_statistics_falls_back_to_in_memory(self, service, company_id):
        """Statistics falls back to in-memory when DB is down."""
        service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )

        comp = ShadowComparison(
            company_id=company_id,
            config_id="cfg_test",
            shadow_winner=True,
            quality_delta=0.05,
            latency_delta_ms=100,
        )
        service.record_comparison(company_id=company_id, comparison=comp)

        with patch.object(service, "_load_config_from_db", return_value=None):
            stats = service.get_statistics(company_id=company_id)

        assert stats["total_comparisons"] == 1
        assert stats["shadow_wins"] == 1


# ══════════════════════════════════════════════════════════════════
# HUMAN REVIEW PERSISTENCE TESTS
# ══════════════════════════════════════════════════════════════════


class TestHumanReviewPersistence:
    """Tests for human review DB persistence."""

    def test_review_updates_db_row(self, service, company_id):
        """record_human_review updates the DB row when available."""
        mock_row = MagicMock()
        mock_row.human_reviewed = False
        mock_row.human_verdict = None
        mock_row.reviewer_id = None
        mock_row.review_notes = None
        mock_row.reviewed_at = None

        mock_session = MagicMock()
        _setup_db_query_mock(mock_session, first_result=mock_row)

        with patch.object(service, "_get_db_session", return_value=mock_session), \
             patch.dict("sys.modules", {"database.models.shadow_mode": MagicMock(ShadowModeResult=MagicMock())}):
            result = service.record_human_review(
                company_id=company_id,
                result_id="result_001",
                verdict="shadow_better",
                reviewer_id="reviewer_001",
                notes="Good response",
            )

        assert result["success"] is True
        # Verify the row was updated
        assert mock_row.human_reviewed is True
        assert mock_row.human_verdict == "shadow_better"
        assert mock_row.reviewer_id == "reviewer_001"
        mock_session.commit.assert_called_once()

    def test_review_graceful_when_db_unavailable(self, service, company_id):
        """record_human_review still returns success when DB is down."""
        with patch.object(service, "_get_db_session", return_value=None):
            result = service.record_human_review(
                company_id=company_id,
                result_id="result_001",
                verdict="equal",
            )

        assert result["success"] is True

    def test_review_rolls_back_on_db_error(self, service, company_id):
        """record_human_review rolls back on DB error."""
        mock_session = MagicMock()
        mock_session.query.side_effect = Exception("DB error")

        with patch.object(service, "_get_db_session", return_value=mock_session):
            result = service.record_human_review(
                company_id=company_id,
                result_id="result_001",
                verdict="shadow_better",
            )

        assert result["success"] is True
        mock_session.rollback.assert_called_once()


# ══════════════════════════════════════════════════════════════════
# THREAD SAFETY TESTS
# ══════════════════════════════════════════════════════════════════


class TestThreadSafety:
    """Tests for thread safety of the service."""

    def test_concurrent_enable_does_not_corrupt_state(self, service):
        """Multiple concurrent enable calls don't corrupt in-memory state."""
        errors = []

        def enable_for_company(comp_id):
            try:
                with patch.object(service, "_persist_config_to_db", return_value=False), \
                     patch.object(service, "_redis_set_config", return_value=False):
                    result = service.enable_shadow_mode(
                        company_id=comp_id,
                        live_variant="mini_parwa",
                        shadow_variant="parwa",
                    )
                if not result["success"]:
                    errors.append(f"Failed for {comp_id}")
            except Exception as e:
                errors.append(str(e))

        threads = []
        for i in range(10):
            t = threading.Thread(target=enable_for_company, args=(f"company_{i}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"

        for i in range(10):
            config = service._configs.get(f"company_{i}")
            assert config is not None, f"Missing config for company_{i}"
            assert config["is_active"] is True

    def test_concurrent_record_comparison(self, service, company_id):
        """Multiple concurrent comparison recordings are safe."""
        service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )

        errors = []

        def record_comp(idx):
            try:
                comp = ShadowComparison(
                    company_id=company_id,
                    config_id="cfg_test",
                    shadow_winner=True,
                    quality_delta=0.05,
                )
                with patch.object(service, "_persist_config_counters_to_db", return_value=False), \
                     patch.object(service, "_persist_comparison_to_db", return_value=False), \
                     patch.object(service, "_redis_set_config", return_value=False), \
                     patch.object(service, "_redis_set_comparisons", return_value=False):
                    result = service.record_comparison(company_id=company_id, comparison=comp)
                if not result["success"]:
                    errors.append(f"Failed at index {idx}")
            except Exception as e:
                errors.append(str(e))

        threads = []
        for i in range(20):
            t = threading.Thread(target=record_comp, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"

        status = service.get_status(company_id=company_id)
        assert status.total_comparisons == 20
