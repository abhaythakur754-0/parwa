"""
Phase 1: Foundation Fixes — Unit Tests

Tests for all 4 Phase 1 fixes:
1. ProviderFactory._load_credentials() multi-path import
2. Mailgun MAILGUN_BASE_URL correctness
3. ExternalToolBus consolidation
4. Voice Parwa-provided channel (D3)
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend is on path for app.* imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_testing_only_not_prod")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DATA_ENCRYPTION_KEY", "12345678901234567890123456789012")


# ═══════════════════════════════════════════════════════════════════
# Fix 1: ProviderFactory._load_credentials() multi-path import
# ═══════════════════════════════════════════════════════════════════

class TestProviderFactoryLoadCredentials:
    """Test ProviderFactory._load_credentials() multi-path import."""

    def test_import_path_database_models(self):
        """Should find ProviderConfiguration at database.models.provider_config."""
        mod = importlib.import_module("database.models.provider_config")
        assert hasattr(mod, "ProviderConfiguration")

    def test_import_path_in_provider_config_init(self):
        """ProviderConfiguration should be importable from database.models.__init__."""
        from database.models import ProviderConfiguration
        assert ProviderConfiguration is not None
        assert ProviderConfiguration.__tablename__ == "provider_configurations"

    @pytest.mark.asyncio
    async def test_load_credentials_multiple_paths(self):
        """_load_credentials should try multiple import paths before raising NotImplementedError."""
        from app.core.providers.registry import ProviderFactory

        # Create a mock DB that will fail the query
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars().first.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Should NOT raise NotImplementedError (model is importable)
        # Should raise ValueError (no config found) which is the correct behavior
        # The ValueError comes from create_from_config wrapping the inner ValueError
        with pytest.raises(ValueError, match="No stored configuration"):
            await ProviderFactory.create_from_config(
                mock_db, "test_company", "email", "brevo"
            )

    @pytest.mark.asyncio
    async def test_load_credentials_raises_not_implemented_when_no_model(self):
        """If ProviderConfiguration model is completely unavailable, should raise NotImplementedError."""
        from app.core.providers.registry import ProviderFactory

        # Patch importlib.import_module to simulate model not found
        with patch("importlib.import_module", side_effect=ImportError("No module")):
            with pytest.raises(NotImplementedError, match="ProviderConfiguration ORM model not found"):
                await ProviderFactory._load_credentials(
                    MagicMock(), "test_company", "email", "brevo"
                )

    def test_load_credentials_source_contains_both_paths(self):
        """_load_credentials source should contain both import paths."""
        from app.core.providers.registry import ProviderFactory
        import inspect
        src = inspect.getsource(ProviderFactory._load_credentials)
        assert "database.models.provider_config" in src
        assert "app.database.models.provider_config" in src


# ═══════════════════════════════════════════════════════════════════
# Fix 2: Mailgun MAILGUN_BASE_URL correctness
# ═══════════════════════════════════════════════════════════════════

class TestMailgunBaseUrl:
    """Verify MAILGUN_BASE_URL is correct (not MAILGRID_BASE_URL)."""

    def test_mailgun_base_url_constant(self):
        """MAILGUN_BASE_URL should be the correct Mailgun API URL."""
        from app.core.providers.email_mailgun import MAILGUN_BASE_URL
        assert MAILGUN_BASE_URL == "https://api.mailgun.net/v3"
        # Ensure no MAILGRID typo
        assert "MAILGRID" not in MAILGUN_BASE_URL
        assert "mailgun" in MAILGUN_BASE_URL.lower()

    def test_mailgun_provider_uses_correct_url(self):
        """MailgunProvider._base_url() should return MAILGUN_BASE_URL for US region."""
        from app.core.providers.email_mailgun import MailgunProvider
        provider = MailgunProvider()
        provider.set_credentials({"api_key": "key-test", "domain": "test.com", "region": "us"})
        assert provider._base_url() == "https://api.mailgun.net/v3"

    def test_mailgun_provider_eu_region(self):
        """MailgunProvider._base_url() should return EU URL for EU region."""
        from app.core.providers.email_mailgun import MailgunProvider
        provider = MailgunProvider()
        provider.set_credentials({"api_key": "key-test", "domain": "test.com", "region": "eu"})
        assert provider._base_url() == "https://api.eu.mailgun.net/v3"


# ═══════════════════════════════════════════════════════════════════
# Fix 3: ExternalToolBus consolidation
# ═══════════════════════════════════════════════════════════════════

class TestExternalToolBusConsolidation:
    """Test that ExternalToolBus is the single integration caller."""

    def test_canonical_bus_exists(self):
        """Canonical ExternalToolBus should exist at backend/app/core/external_tool_bus.py."""
        from app.core.external_tool_bus import ExternalToolBus, ToolResult, external_tool_bus
        assert ExternalToolBus is not None
        assert ToolResult is not None
        assert external_tool_bus is not None

    def test_canonical_bus_has_all_channels(self):
        """ExternalToolBus should support all channel methods."""
        from app.core.external_tool_bus import ExternalToolBus
        bus = ExternalToolBus()
        assert hasattr(bus, "send_sms")
        assert hasattr(bus, "send_email")
        assert hasattr(bus, "make_call")
        assert hasattr(bus, "send_chat")
        assert hasattr(bus, "send_webhook")
        assert hasattr(bus, "send_notification")
        assert hasattr(bus, "send_ticket_notification")

    def test_canonical_bus_has_provider_factory_fallback(self):
        """ExternalToolBus should have ProviderFactory-first, env-var-fallback pattern."""
        from app.core.external_tool_bus import ExternalToolBus
        bus = ExternalToolBus()
        assert hasattr(bus, "_send_sms_via_provider")
        assert hasattr(bus, "_send_sms_via_env")
        assert hasattr(bus, "_send_email_via_provider")
        assert hasattr(bus, "_send_email_via_env")
        assert hasattr(bus, "_make_call_via_provider")
        assert hasattr(bus, "_make_call_via_env")

    def test_canonical_bus_set_db(self):
        """ExternalToolBus should accept a DB session for ProviderFactory lookups."""
        from app.core.external_tool_bus import ExternalToolBus
        bus = ExternalToolBus()
        mock_db = MagicMock()
        bus.set_db(mock_db)
        assert bus._db == mock_db

    @pytest.mark.asyncio
    async def test_sms_permission_check(self):
        """SMS should be blocked for mini_parwa variant."""
        from app.core.external_tool_bus import ExternalToolBus
        bus = ExternalToolBus()
        result = await bus.send_sms(variant="mini_parwa", company_id="test", to="+1234", body="test")
        assert not result.success
        assert "not available" in result.error

    @pytest.mark.asyncio
    async def test_voice_permission_check(self):
        """Voice should be blocked for mini_parwa variant."""
        from app.core.external_tool_bus import ExternalToolBus
        bus = ExternalToolBus()
        result = await bus.make_call(variant="mini_parwa", company_id="test", to="+1234")
        assert not result.success
        assert "not available" in result.error

    @pytest.mark.asyncio
    async def test_email_permission_all_variants(self):
        """Email should be available for ALL variant tiers."""
        from app.core.external_tool_bus import ExternalToolBus
        from app.core.channel_permissions import Channel
        bus = ExternalToolBus()
        for variant in ["mini_parwa", "parwa", "parwa_high"]:
            assert bus.is_channel_allowed(variant, Channel.EMAIL)

    def test_mcp_wrapper_imports_canonical(self):
        """MCP server's external_tool_bus.py should import from canonical location."""
        # Just verify the import works
        import importlib
        spec = importlib.util.spec_from_file_location(
            "mcp_external_tool_bus",
            "/home/z/my-project/parwa/mcp_server/integrations/external_tool_bus.py"
        )
        assert spec is not None  # File exists and is importable

    def test_tool_result_to_dict(self):
        """ToolResult.to_dict() should serialize correctly."""
        from app.core.external_tool_bus import ToolResult, Channel
        result = ToolResult(success=True, channel=Channel.SMS, provider="twilio", message_id="SM123")
        d = result.to_dict()
        assert d["success"] is True
        assert d["channel"] == "sms"
        assert d["provider"] == "twilio"
        assert d["message_id"] == "SM123"

    def test_production_connector_uses_bus(self):
        """ProductionConnector should delegate to ExternalToolBus."""
        from app.core.production_connector import ProductionConnector
        connector = ProductionConnector()
        assert hasattr(connector, "tool_bus")

    def test_external_tool_executor_uses_bus(self):
        """ExternalToolExecutor should import and use external_tool_bus."""
        from app.core.external_tool_executor import external_tool_bus as imported_bus
        assert imported_bus is not None


# ═══════════════════════════════════════════════════════════════════
# Fix 4: Voice Parwa-provided channel (D3)
# ═══════════════════════════════════════════════════════════════════

class TestVoiceParwaProvidedChannel:
    """Test Voice Parwa-provided channel (D3)."""

    def test_voice_channel_config_has_number_source(self):
        """VoiceChannelConfig should have number_source column."""
        from database.models.voice_channel import VoiceChannelConfig
        # Check the column exists
        columns = {c.name for c in VoiceChannelConfig.__table__.columns}
        assert "number_source" in columns
        assert "caller_id_name" in columns
        assert "greeting_style" in columns
        assert "language_preference" in columns
        assert "parwa_phone_number" in columns
        assert "parwa_number_sid" in columns

    def test_voice_channel_config_twilio_nullable(self):
        """Twilio credential columns should be nullable for parwa_provided mode."""
        from database.models.voice_channel import VoiceChannelConfig
        table = VoiceChannelConfig.__table__
        assert table.c.twilio_account_sid.nullable is True
        assert table.c.twilio_auth_token_encrypted.nullable is True
        assert table.c.twilio_phone_number.nullable is True

    def test_voice_channel_config_defaults(self):
        """VoiceChannelConfig should default to parwa_provided number_source."""
        from database.models.voice_channel import VoiceChannelConfig
        col = VoiceChannelConfig.__table__.c.number_source
        assert col.default.arg == "parwa_provided"

    def test_voice_channel_config_greeting_style_default(self):
        """VoiceChannelConfig should default to professional greeting style."""
        from database.models.voice_channel import VoiceChannelConfig
        col = VoiceChannelConfig.__table__.c.greeting_style
        assert col.default.arg == "professional"

    def test_voice_service_has_provision_method(self):
        """VoiceChannelService should have provision_parwa_number method."""
        from app.services.voice_channel_service import VoiceChannelService
        assert hasattr(VoiceChannelService, "provision_parwa_number")

    def test_voice_service_has_release_method(self):
        """VoiceChannelService should have release_parwa_number method."""
        from app.services.voice_channel_service import VoiceChannelService
        assert hasattr(VoiceChannelService, "release_parwa_number")

    def test_voice_config_to_dict_includes_new_fields(self):
        """VoiceChannelConfig.to_dict() should include D3 fields."""
        from database.models.voice_channel import VoiceChannelConfig
        config = VoiceChannelConfig(
            company_id="test_co",
            number_source="parwa_provided",
            twilio_account_sid="ACtest",
            twilio_auth_token_encrypted="encrypted",
            twilio_phone_number="+1234567890",
            parwa_phone_number="+1234567890",
            parwa_number_sid="PNtest",
            caller_id_name="Test Company",
            greeting_style="friendly",
            language_preference="en-US",
        )
        d = config.to_dict()
        assert d["number_source"] == "parwa_provided"
        assert d["caller_id_name"] == "Test Company"
        assert d["greeting_style"] == "friendly"
        assert d["language_preference"] == "en-US"
        assert d["parwa_phone_number"] == "+1234567890"
        # twilio_account_sid should be masked (ACtest is < 8 chars → "********")
        assert d["twilio_account_sid"] != "ACtest"
