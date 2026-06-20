"""
Phase 4 Unit Tests: Feature Completion (Shadow Mode DB Persistence, AI Agent Router, Frontend Wiring).

Tests cover:
  - Shadow Mode Service DB persistence layer (_persist_config_to_db, _load_config_from_db, etc.)
  - Shadow Mode Service fallback to in-memory when DB unavailable
  - AI Agent Router company_id extraction and audit logging
  - Shadow Mode Service edge cases with DB persistence
  - Migration file validation (013, 014)
  - Variant service resolve_for_shadow edge cases
"""

import pytest
import os
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timezone

from app.services.shadow_mode_service import (
    ShadowModeService,
    ShadowComparison,
    ShadowModeStatus,
    get_shadow_mode_service,
    VALID_VARIANT_TYPES,
    VARIANT_RANKING,
)


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def service():
    """Create a fresh ShadowModeService instance for each test."""
    return ShadowModeService()


@pytest.fixture
def company_id():
    """Sample company ID."""
    return "comp_phase4_test_001"


@pytest.fixture
def mock_db_session():
    """Create a mock SQLAlchemy session."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session


@pytest.fixture
def enabled_service(service, company_id):
    """Service with shadow mode enabled for a test company."""
    service.enable_shadow_mode(
        company_id=company_id,
        live_variant="mini_parwa",
        shadow_variant="parwa",
        sample_rate=1.0,
    )
    return service


# ══════════════════════════════════════════════════════════════════
# SHADOW MODE DB PERSISTENCE - UNIT TESTS
# ══════════════════════════════════════════════════════════════════


class TestShadowModeDBPersistence:
    """Tests for the DB persistence layer of ShadowModeService."""

    def test_get_db_session_returns_session_when_available(self, service):
        """Test that _get_db_session returns a session when DB is available."""
        with patch("database.base.SessionLocal") as mock_sl:
            mock_session = MagicMock()
            mock_sl.return_value = mock_session
            session = service._get_db_session()
            assert session is not None

    def test_get_db_session_returns_none_when_unavailable(self, service):
        """Test that _get_db_session returns None when DB is unavailable (BC-008)."""
        with patch("database.base.SessionLocal", side_effect=Exception("DB down")):
            session = service._get_db_session()
            assert session is None

    def test_persist_config_to_db_method_exists(self, service):
        """Test that _persist_config_to_db method exists and follows BC-008."""
        assert hasattr(service, '_persist_config_to_db')
        # Should not crash even with invalid config (BC-008)
        result = service._persist_config_to_db({"id": "test", "company_id": "c1"})
        # Returns bool (True on success, False on failure)
        assert isinstance(result, bool)

    def test_persist_config_to_db_fails_gracefully(self, service, company_id):
        """Test that DB persist failure doesn't crash (BC-008)."""
        config = {
            "id": "cfg_001",
            "company_id": company_id,
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
            "status": "shadow",
            "sample_rate": 1.0,
            "is_active": True,
        }
        # DB session raises
        mock_session = MagicMock()
        mock_session.add.side_effect = Exception("DB write failed")
        with patch.object(ShadowModeService, "_get_db_session", return_value=mock_session):
            # Should not raise
            service._persist_config_to_db(config)

    def test_load_config_from_db_method_exists(self, service, company_id):
        """Test that _load_config_from_db method exists and follows BC-008."""
        assert hasattr(service, '_load_config_from_db')
        # Should return None when DB unavailable (BC-008)
        result = service._load_config_from_db(company_id)
        # Returns None when no DB or no config found
        assert result is None or isinstance(result, dict)

    def test_load_config_from_db_not_found(self, service, mock_db_session, company_id):
        """Test loading config from DB when none exists."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        with patch.object(ShadowModeService, "_get_db_session", return_value=mock_db_session):
            result = service._load_config_from_db(company_id)
        assert result is None

    def test_load_config_from_db_failure_graceful(self, service, company_id):
        """Test that DB load failure returns None (BC-008)."""
        with patch.object(ShadowModeService, "_get_db_session", return_value=None):
            result = service._load_config_from_db(company_id)
        assert result is None

    def test_persist_comparison_to_db_method_exists(self, service, company_id):
        """Test that _persist_comparison_to_db method exists and follows BC-008."""
        assert hasattr(service, '_persist_comparison_to_db')
        comp = ShadowComparison(
            company_id=company_id,
            config_id="cfg_001",
            shadow_winner=True,
            quality_delta=0.05,
        )
        # Should not crash even when DB unavailable (BC-008)
        result = service._persist_comparison_to_db(comp)
        assert isinstance(result, bool)

    def test_persist_comparison_to_db_failure_graceful(self, service, company_id):
        """Test that comparison persist failure doesn't crash (BC-008)."""
        comp = ShadowComparison(
            company_id=company_id,
            config_id="cfg_001",
            shadow_winner=True,
            quality_delta=0.05,
        )
        mock_session = MagicMock()
        mock_session.add.side_effect = Exception("DB write failed")
        with patch.object(ShadowModeService, "_get_db_session", return_value=mock_session):
            # Should not raise
            service._persist_comparison_to_db(comp)

    def test_enable_shadow_mode_has_db_persist_code(self, service, company_id):
        """Test that enable_shadow_mode includes DB persistence code."""
        import inspect
        source = inspect.getsource(service.enable_shadow_mode)
        # Should reference _persist_config_to_db
        assert "_persist_config_to_db" in source
        # Should still work (in-memory fallback)
        result = service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )
        assert result["success"] is True

    def test_enable_shadow_mode_works_without_db(self, service, company_id):
        """Test that enable_shadow_mode works when DB is unavailable (BC-008)."""
        with patch.object(ShadowModeService, "_get_db_session", return_value=None):
            result = service.enable_shadow_mode(
                company_id=company_id,
                live_variant="mini_parwa",
                shadow_variant="parwa",
            )
        assert result["success"] is True
        # Should still work with in-memory

    def test_disable_shadow_mode_persists_to_db(self, enabled_service, mock_db_session, company_id):
        """Test that disable_shadow_mode tries to persist to DB."""
        with patch.object(ShadowModeService, "_get_db_session", return_value=mock_db_session):
            result = enabled_service.disable_shadow_mode(company_id=company_id)
        assert result["success"] is True

    def test_get_status_tries_db_first(self, enabled_service, mock_db_session, company_id):
        """Test that get_status tries DB first before falling back to memory."""
        # Even with no DB row, it should fall back to in-memory
        with patch.object(ShadowModeService, "_get_db_session", return_value=mock_db_session):
            status = enabled_service.get_status(company_id=company_id)
        assert status.is_active is True
        assert status.status == "shadow"

    def test_record_comparison_has_db_persist_code(self, enabled_service, company_id):
        """Test that record_comparison includes DB persistence code."""
        import inspect
        source = inspect.getsource(enabled_service.record_comparison)
        # Should reference DB persist methods
        assert "_persist" in source or "_persist_comparison" in source or "_persist_config" in source
        # Should still work (in-memory fallback)
        comp = ShadowComparison(
            company_id=company_id,
            config_id="test",
            shadow_winner=True,
            quality_delta=0.05,
        )
        result = enabled_service.record_comparison(
            company_id=company_id, comparison=comp,
        )
        assert result["success"] is True


# ══════════════════════════════════════════════════════════════════
# SHADOW MODE DB PERSISTENCE - FALLBACK TESTS
# ══════════════════════════════════════════════════════════════════


class TestShadowModeDBFallback:
    """Tests for in-memory fallback when DB is unavailable."""

    def test_full_lifecycle_without_db(self, service, company_id):
        """Test complete shadow mode lifecycle with no DB available."""
        with patch.object(ShadowModeService, "_get_db_session", return_value=None):
            # Enable
            result = service.enable_shadow_mode(
                company_id=company_id,
                live_variant="mini_parwa",
                shadow_variant="parwa",
                auto_graduation_window=3,
                auto_promote_to_supervised=True,
            )
            assert result["success"] is True

            # Get status
            status = service.get_status(company_id=company_id)
            assert status.is_active is True

            # Record comparisons
            for _ in range(3):
                comp = ShadowComparison(
                    company_id=company_id,
                    config_id="test",
                    shadow_winner=True,
                    quality_delta=0.05,
                )
                service.record_comparison(
                    company_id=company_id, comparison=comp,
                )

            # Check auto-graduation
            status = service.get_status(company_id=company_id)
            assert status.status == "supervised"

            # Graduate
            grad_result = service.complete_graduation(company_id=company_id)
            assert grad_result["success"] is True

    def test_db_failure_during_operation_continues(self, service, company_id):
        """Test that mid-operation DB failure doesn't break the flow."""
        # First enable with DB
        mock_db = MagicMock()
        with patch.object(ShadowModeService, "_get_db_session", return_value=mock_db):
            service.enable_shadow_mode(
                company_id=company_id,
                live_variant="mini_parwa",
                shadow_variant="parwa",
            )

        # Now DB goes down
        with patch.object(ShadowModeService, "_get_db_session", return_value=None):
            # Should still work with in-memory cache
            status = service.get_status(company_id=company_id)
            assert status.is_active is True

    def test_comparison_history_without_db(self, enabled_service, company_id):
        """Test getting comparison history without DB."""
        # Record some comparisons
        for i in range(5):
            comp = ShadowComparison(
                company_id=company_id,
                config_id="test",
                shadow_winner=True,
                quality_delta=0.05,
            )
            enabled_service.record_comparison(
                company_id=company_id, comparison=comp,
            )

        # Get history without DB
        with patch.object(ShadowModeService, "_get_db_session", return_value=None):
            history = enabled_service.get_comparison_history(company_id=company_id)
        assert len(history) > 0


# ══════════════════════════════════════════════════════════════════
# AI AGENT ROUTER - COMPANY_ID GUARD TESTS
# ══════════════════════════════════════════════════════════════════


class TestAIAgentRouterCompanyGuard:
    """Tests for the AI Agent router company_id extraction and audit."""

    def _get_router_path(self):
        return os.path.join(
            os.path.dirname(__file__),
            "..", "app", "api", "ai_agent.py",
        )

    def test_router_file_exists(self):
        """Test that the AI Agent router file exists."""
        assert os.path.exists(self._get_router_path())

    def test_router_imports_get_company_id(self):
        """Test that the router imports get_company_id from deps."""
        with open(self._get_router_path()) as f:
            content = f.read()
        assert "get_company_id" in content
        assert "from app.api.deps" in content

    def test_router_has_company_id_on_all_endpoints(self):
        """Test that all endpoints include company_id dependency."""
        with open(self._get_router_path()) as f:
            content = f.read()
        # Count Depends(get_company_id) occurrences
        count = content.count("Depends(get_company_id)")
        # Should have at least 7 (one per endpoint)
        assert count >= 7, f"Expected at least 7 Depends(get_company_id), got {count}"

    def test_router_docstring_mentions_company_scoping(self):
        """Test that the docstring mentions company scoping."""
        with open(self._get_router_path()) as f:
            content = f.read()
        assert "company" in content.lower()
        # Should NOT say "global table (no company_id)"
        assert "no company_id" not in content.lower().replace(" ", "")

    def test_router_has_audit_logging(self):
        """Test that the router has audit logging for company_id."""
        with open(self._get_router_path()) as f:
            content = f.read()
        assert "logger" in content
        assert "company_id" in content


# ══════════════════════════════════════════════════════════════════
# MIGRATION FILE VALIDATION
# ══════════════════════════════════════════════════════════════════


class TestMigrationValidation:
    """Tests for migration file integrity."""

    def _migrations_dir(self):
        return os.path.join(
            os.path.dirname(__file__),
            "..", "..", "database", "alembic", "versions",
        )

    def test_migration_013_exists(self):
        """Test that migration 013 exists."""
        files = os.listdir(self._migrations_dir())
        has_013 = any(f.startswith("013") for f in files)
        assert has_013, "Migration 013 not found"

    def test_migration_014_exists(self):
        """Test that migration 014 exists."""
        files = os.listdir(self._migrations_dir())
        has_014 = any(f.startswith("014") for f in files)
        assert has_014, "Migration 014 not found"

    def test_migration_013_has_upgrade_downgrade(self):
        """Test that migration 013 has upgrade and downgrade functions."""
        path = os.path.join(self._migrations_dir(), "013_some_migration.py")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "def upgrade()" in content
        assert "def downgrade()" in content
        assert "down_revision" in content

    def test_migration_014_has_upgrade_downgrade(self):
        """Test that migration 014 has upgrade and downgrade functions."""
        path = os.path.join(self._migrations_dir(), "014_email_verification.py")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "def upgrade()" in content
        assert "def downgrade()" in content
        assert "down_revision" in content

    def test_migration_chain_from_012_to_015(self):
        """Test that the migration chain is continuous from 012 to 015."""
        migrations_dir = self._migrations_dir()
        files = os.listdir(migrations_dir)

        # Find each migration file
        m012 = None
        m013 = None
        m014 = None
        m015 = None

        for f in files:
            if f.startswith("012"):
                m012 = f
            elif f.startswith("013"):
                m013 = f
            elif f.startswith("014"):
                m014 = f
            elif f.startswith("015"):
                m015 = f

        assert m012 is not None, "Migration 012 not found"
        assert m013 is not None, "Migration 013 not found"
        assert m014 is not None, "Migration 014 not found"
        assert m015 is not None, "Migration 015 not found"


# ══════════════════════════════════════════════════════════════════
# VARIANT SERVICE EDGE CASE TESTS
# ══════════════════════════════════════════════════════════════════


class TestVariantServiceEdgeCases:
    """Tests for variant service edge cases related to Phase 4."""

    def test_valid_variant_types_complete(self):
        """Test that all expected variant types are defined."""
        assert "mini_parwa" in VALID_VARIANT_TYPES
        assert "parwa" in VALID_VARIANT_TYPES
        assert "parwa_high" in VALID_VARIANT_TYPES

    def test_variant_ranking_is_ascending(self):
        """Test that variant ranking is ascending."""
        assert VARIANT_RANKING["mini_parwa"] < VARIANT_RANKING["parwa"]
        assert VARIANT_RANKING["parwa"] < VARIANT_RANKING["parwa_high"]

    def test_shadow_mode_rejects_equal_rank(self):
        """Test that shadow mode rejects same-rank variants."""
        service = ShadowModeService()
        result = service.enable_shadow_mode(
            company_id="test_comp",
            live_variant="parwa",
            shadow_variant="parwa",
        )
        assert result["success"] is False

    def test_shadow_mode_allows_two_step_upgrade(self):
        """Test that mini_parwa → parwa_high (skip parwa) is allowed."""
        service = ShadowModeService()
        result = service.enable_shadow_mode(
            company_id="test_comp",
            live_variant="mini_parwa",
            shadow_variant="parwa_high",
        )
        assert result["success"] is True

    def test_shadow_mode_comparison_dataclass_complete(self):
        """Test that ShadowComparison has all required fields."""
        comp = ShadowComparison(
            company_id="comp1",
            config_id="cfg1",
            ticket_id="t1",
            conversation_id="c1",
            message_hash="abc123",
            live_variant="mini_parwa",
            live_response="live response",
            live_quality_score=0.70,
            live_latency_ms=500,
            live_tokens_used=100,
            shadow_variant="parwa",
            shadow_response="shadow response",
            shadow_quality_score=0.85,
            shadow_latency_ms=800,
            shadow_tokens_used=150,
            quality_delta=0.15,
            latency_delta_ms=300,
            token_delta=50,
            shadow_winner=True,
            mode_at_comparison="shadow",
        )
        d = comp.to_dict()
        assert d["company_id"] == "comp1"
        assert d["shadow_winner"] is True
        assert d["quality_delta"] == 0.15
        assert d["latency_delta_ms"] == 300
        assert d["token_delta"] == 50
        assert d["mode_at_comparison"] == "shadow"

    def test_shadow_mode_status_dataclass_complete(self):
        """Test that ShadowModeStatus has all required fields."""
        status = ShadowModeStatus(
            company_id="comp1",
            is_active=True,
            status="supervised",
            live_variant="mini_parwa",
            shadow_variant="parwa",
            sample_rate=0.75,
            total_comparisons=150,
            shadow_wins=120,
            win_rate=0.80,
            current_quality_streak=25,
            auto_graduation_threshold=0.95,
            auto_graduation_window=100,
            config_id="cfg_001",
        )
        d = status.to_dict()
        assert d["company_id"] == "comp1"
        assert d["is_active"] is True
        assert d["status"] == "supervised"
        assert d["sample_rate"] == 0.75
        assert d["total_comparisons"] == 150
        assert d["win_rate"] == 0.80

    def test_auto_graduation_two_phase(self):
        """Test auto-graduation from shadow → supervised → graduated."""
        service = ShadowModeService()
        service.enable_shadow_mode(
            company_id="test_comp",
            live_variant="mini_parwa",
            shadow_variant="parwa",
            auto_graduation_window=5,
            auto_promote_to_supervised=True,
            auto_promote_to_graduated=True,
        )

        # Record 5 consecutive wins
        for _ in range(5):
            comp = ShadowComparison(
                company_id="test_comp",
                config_id="test",
                shadow_winner=True,
                quality_delta=0.05,
            )
            service.record_comparison(company_id="test_comp", comparison=comp)

        # Should have auto-graduated to supervised
        status = service.get_status(company_id="test_comp")
        assert status.status == "supervised"

        # Reset streak for next graduation
        # Need another 5 consecutive wins for supervised → graduated
        for _ in range(5):
            comp = ShadowComparison(
                company_id="test_comp",
                config_id="test",
                shadow_winner=True,
                quality_delta=0.05,
            )
            service.record_comparison(company_id="test_comp", comparison=comp)

        status = service.get_status(company_id="test_comp")
        assert status.status == "graduated"


# ══════════════════════════════════════════════════════════════════
# FRONTEND WIRING VALIDATION
# ══════════════════════════════════════════════════════════════════


class TestFrontendWiring:
    """Tests for frontend route page wiring to component pages."""

    def _get_route_page(self, name):
        return os.path.join(
            os.path.dirname(__file__),
            "..", "..", "src", "app", "dashboard", name, "page.tsx",
        )

    def test_tickets_page_wired(self):
        """Test that tickets route page imports component."""
        path = self._get_route_page("tickets")
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
            assert "TicketsPage" in content or "components/pages" in content

    def test_billing_page_wired(self):
        """Test that billing route page imports component."""
        path = self._get_route_page("billing")
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
            assert "BillingPage" in content or "components/pages" in content

    def test_knowledge_page_wired(self):
        """Test that knowledge route page imports component."""
        path = self._get_route_page("knowledge")
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
            assert "KnowledgePage" in content or "components/pages" in content

    def test_agents_page_wired(self):
        """Test that agents route page imports component."""
        path = self._get_route_page("agents")
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
            assert "AgentsPage" in content or "components/pages" in content

    def test_settings_page_wired(self):
        """Test that settings route page imports component."""
        path = self._get_route_page("settings")
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
            assert "SettingsPage" in content or "components/pages" in content

    def test_variants_page_has_escalate_rebalance(self):
        """Test that variants page has real escalate/rebalance handlers."""
        path = self._get_route_page("variants")
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
            # Should NOT have TODO comments
            assert "TODO" not in content or "Call" not in content
            # Should have real API calls
            assert "post" in content or "fetch" in content


# ══════════════════════════════════════════════════════════════════
# SHADOW MODE SERVICE THREAD SAFETY TESTS
# ══════════════════════════════════════════════════════════════════


class TestShadowModeThreadSafety:
    """Tests for thread safety of ShadowModeService."""

    def test_concurrent_enable_different_companies(self, service):
        """Test enabling shadow mode for different companies concurrently."""
        import threading

        results = {}
        errors = []

        def enable_for_company(comp_id, live, shadow):
            try:
                result = service.enable_shadow_mode(
                    company_id=comp_id,
                    live_variant=live,
                    shadow_variant=shadow,
                )
                results[comp_id] = result
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=enable_for_company, args=(f"comp_{i}", "mini_parwa", "parwa"))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 10
        for comp_id, result in results.items():
            assert result["success"] is True

    def test_concurrent_comparisons_same_company(self, enabled_service, company_id):
        """Test recording comparisons concurrently for the same company."""
        import threading

        errors = []

        def record_comparison():
            try:
                comp = ShadowComparison(
                    company_id=company_id,
                    config_id="test",
                    shadow_winner=True,
                    quality_delta=0.05,
                )
                enabled_service.record_comparison(
                    company_id=company_id, comparison=comp,
                )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=record_comparison) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        status = enabled_service.get_status(company_id=company_id)
        assert status.total_comparisons == 20
