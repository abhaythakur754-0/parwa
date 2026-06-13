"""
Phase 1: Foundation Fixes — Integration Tests

Tests that Phase 1 fixes work WITH the rest of the system:
- ProviderFactory + DB credential loading
- ExternalToolBus end-to-end routing
- VoiceChannelService DB operations
- MCP server → ExternalToolBus delegation
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# ── Environment setup BEFORE any app imports ──────────────────────
# Must be set before importing anything that triggers get_settings()
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_testing_only_not_prod")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DATA_ENCRYPTION_KEY", "12345678901234567890123456789012")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_not_prod")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

# Ensure backend is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


# ═══════════════════════════════════════════════════════════════════
# 1. ProviderFactory + DB Integration
# ═══════════════════════════════════════════════════════════════════

class TestProviderFactoryDBIntegration:
    """Integration: ProviderFactory._load_credentials with real ORM model."""

    def test_provider_configuration_model_has_decrypt(self):
        """ProviderConfiguration model should have decrypt_credentials method."""
        from database.models.provider_config import ProviderConfiguration
        assert hasattr(ProviderConfiguration, "decrypt_credentials")
        assert hasattr(ProviderConfiguration, "encrypt_and_set_credentials")

    def test_provider_configuration_encrypt_decrypt_roundtrip(self):
        """Encrypt and decrypt should return the same credentials."""
        # Reset cached fernet instance so test env key is used
        import shared.utils.token_encryption as _te
        _te._fernet_instance = None

        from database.models.provider_config import ProviderConfiguration
        config = ProviderConfiguration(
            company_id="test_co",
            category="email",
            provider_type="brevo",
            credentials_encrypted="placeholder",
        )
        test_creds = {"api_key": "xkeysib-test123", "from_email": "test@example.com"}
        config.encrypt_and_set_credentials(test_creds)

        # Verify encrypted value is different from plaintext
        assert config.credentials_encrypted != "placeholder"
        assert "xkeysib-test123" not in config.credentials_encrypted

        # Verify decrypt returns the same
        decrypted = config.decrypt_credentials()
        assert decrypted["api_key"] == "xkeysib-test123"
        assert decrypted["from_email"] == "test@example.com"

    def test_provider_configuration_to_dict_no_secrets(self):
        """to_dict should never expose credentials."""
        from database.models.provider_config import ProviderConfiguration
        config = ProviderConfiguration(
            company_id="test_co",
            category="email",
            provider_type="brevo",
            credentials_encrypted="encrypted_blob",
        )
        d = config.to_dict()
        assert "credentials_encrypted" not in d
        assert d["has_credentials"] is True
        assert d["category"] == "email"
        assert d["provider_type"] == "brevo"


# ═══════════════════════════════════════════════════════════════════
# 2. ExternalToolBus End-to-End Routing
# ═══════════════════════════════════════════════════════════════════

class TestExternalToolBusEndToEnd:
    """Integration: ExternalToolBus routing through the full call chain."""

    @pytest.mark.asyncio
    async def test_sms_returns_error_without_env_vars(self):
        """SMS should return error when Twilio env vars are missing."""
        from app.core.external_tool_bus import ExternalToolBus, Channel

        # Create bus without env vars set
        with patch.dict(os.environ, {}, clear=True):
            bus = ExternalToolBus()
            # Override provider config to simulate missing env vars
            from app.core.external_tool_bus import ProviderConfig
            bus._providers[Channel.SMS] = ProviderConfig(
                name="twilio_sms", channel=Channel.SMS,
                configured=False, missing_env_vars=["TWILIO_ACCOUNT_SID"]
            )
            result = await bus.send_sms(
                variant="parwa", company_id="test_co", to="+1234567890", body="Test"
            )
            assert not result.success
            assert "not configured" in result.error.lower() or "missing" in result.error.lower()

    @pytest.mark.asyncio
    async def test_email_returns_error_without_env_vars(self):
        """Email should return error when Brevo env var is missing."""
        from app.core.external_tool_bus import ExternalToolBus, Channel

        bus = ExternalToolBus()
        from app.core.external_tool_bus import ProviderConfig
        bus._providers[Channel.EMAIL] = ProviderConfig(
            name="brevo", channel=Channel.EMAIL,
            configured=False, missing_env_vars=["BREVO_API_KEY"]
        )
        result = await bus.send_email(
            variant="parwa", company_id="test_co", to="test@example.com",
            subject="Test", body="Test body"
        )
        assert not result.success
        assert "not configured" in result.error.lower() or "missing" in result.error.lower()

    @pytest.mark.asyncio
    async def test_webhook_sends_successfully(self):
        """Webhook should work (just HTTP POST, no external dependencies)."""
        from app.core.external_tool_bus import ExternalToolBus

        bus = ExternalToolBus()
        # Mock httpx.AsyncClient to avoid real HTTP calls
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client_instance):
            result = await bus.send_webhook(
                variant="parwa_high", company_id="test_co",
                url="https://example.com/webhook", payload={"event": "test"},
            )
            assert result.success

    @pytest.mark.asyncio
    async def test_provider_factory_fallback_to_env(self):
        """When ProviderFactory has no DB, should fall through to env-var path."""
        from app.core.external_tool_bus import ExternalToolBus

        bus = ExternalToolBus()
        # No DB set — should skip ProviderFactory and try env-var path
        assert bus._db is None

        # SMS without env vars should fail gracefully
        from app.core.external_tool_bus import ProviderConfig, Channel
        bus._providers[Channel.SMS] = ProviderConfig(
            name="twilio_sms", channel=Channel.SMS,
            configured=False, missing_env_vars=["TWILIO_ACCOUNT_SID"]
        )
        result = await bus.send_sms(
            variant="parwa", company_id="test_co", to="+1234", body="test"
        )
        assert not result.success  # Expected to fail since no Twilio config

    @pytest.mark.asyncio
    async def test_mini_parwa_sms_blocked(self):
        """SMS should be blocked for mini_parwa variant (permission check)."""
        from app.core.external_tool_bus import ExternalToolBus

        bus = ExternalToolBus()
        result = await bus.send_sms(
            variant="mini_parwa", company_id="test_co", to="+1234", body="test"
        )
        assert not result.success
        assert "not available" in result.error

    @pytest.mark.asyncio
    async def test_mini_parwa_voice_blocked(self):
        """Voice should be blocked for mini_parwa variant (permission check)."""
        from app.core.external_tool_bus import ExternalToolBus

        bus = ExternalToolBus()
        result = await bus.make_call(
            variant="mini_parwa", company_id="test_co", to="+1234"
        )
        assert not result.success
        assert "not available" in result.error

    @pytest.mark.asyncio
    async def test_chat_succeeds_for_all_variants(self):
        """Chat should work for all variants (template fallback)."""
        from app.core.external_tool_bus import ExternalToolBus

        bus = ExternalToolBus()
        for variant in ["mini_parwa", "parwa", "parwa_high"]:
            # Mock the backend call to return None (simulates backend unavailable)
            # This tests the template fallback path in send_chat()
            with patch.object(bus, "_send_chat_via_backend", return_value=None):
                result = await bus.send_chat(
                    variant=variant, company_id="test_co", message="Hello"
                )
                assert result.success, f"Chat failed for variant {variant}"
                assert result.provider == "parwa_chat"

    def test_bus_provider_status_returns_all_channels(self):
        """get_provider_status should return all configured channels."""
        from app.core.external_tool_bus import ExternalToolBus

        bus = ExternalToolBus()
        status = bus.get_provider_status()
        assert "sms" in status
        assert "email" in status
        assert "voice" in status
        assert "chat" in status
        assert "webhook" in status
        # Chat and webhook should always be configured
        assert status["chat"]["configured"] is True
        assert status["webhook"]["configured"] is True


# ═══════════════════════════════════════════════════════════════════
# 3. VoiceChannelService + DB Integration
# ═══════════════════════════════════════════════════════════════════

class TestVoiceChannelDBIntegration:
    """Integration: VoiceChannelService DB operations with new D3 fields."""

    def test_voice_channel_config_parwa_provided_mode(self):
        """VoiceChannelConfig should support parwa_provided mode with nullable Twilio fields."""
        from database.models.voice_channel import VoiceChannelConfig

        config = VoiceChannelConfig(
            company_id="test_co",
            number_source="parwa_provided",
            # Twilio fields are nullable for parwa_provided mode
            twilio_account_sid=None,
            twilio_auth_token_encrypted=None,
            twilio_phone_number=None,
            parwa_phone_number="+1234567890",
            parwa_number_sid="PN123",
            caller_id_name="Test Company",
            greeting_style="friendly",
            language_preference="en-US",
            is_enabled=True,
            default_variant="parwa",
        )

        # Verify model accepts None for twilio fields
        assert config.number_source == "parwa_provided"
        assert config.twilio_account_sid is None
        assert config.caller_id_name == "Test Company"
        assert config.greeting_style == "friendly"
        assert config.parwa_phone_number == "+1234567890"

    def test_voice_channel_config_bring_own_mode(self):
        """VoiceChannelConfig should support bring_own mode with required Twilio fields."""
        from database.models.voice_channel import VoiceChannelConfig

        config = VoiceChannelConfig(
            company_id="test_co",
            number_source="bring_own",
            twilio_account_sid="AC123456",
            twilio_auth_token_encrypted="encrypted_token",
            twilio_phone_number="+1987654321",
            caller_id_name="My Company",
            greeting_style="professional",
            language_preference="en-IN",
            is_enabled=True,
            default_variant="parwa",
        )

        assert config.number_source == "bring_own"
        assert config.twilio_account_sid == "AC123456"
        assert config.twilio_phone_number == "+1987654321"

    def test_voice_config_to_dict_masks_parwa_provided(self):
        """to_dict should mask account SID for parwa_provided mode."""
        from database.models.voice_channel import VoiceChannelConfig

        config = VoiceChannelConfig(
            company_id="test_co",
            number_source="parwa_provided",
            twilio_account_sid="AC1234567890abcdef",
            twilio_auth_token_encrypted="encrypted",
            twilio_phone_number="+1234567890",
            parwa_phone_number="+1234567890",
            parwa_number_sid="PN123",
            is_enabled=True,
            default_variant="parwa",
        )

        d = config.to_dict()
        # Account SID should be masked
        assert d["twilio_account_sid"] != "AC1234567890abcdef"
        assert "cdef" in d["twilio_account_sid"]  # Last 4 chars visible
        assert d["number_source"] == "parwa_provided"
        assert d["parwa_phone_number"] == "+1234567890"

    def test_voice_config_to_dict_bring_own(self):
        """to_dict should show client's phone number for bring_own mode."""
        from database.models.voice_channel import VoiceChannelConfig

        config = VoiceChannelConfig(
            company_id="test_co",
            number_source="bring_own",
            twilio_account_sid="AC9876543210",
            twilio_auth_token_encrypted="encrypted",
            twilio_phone_number="+1987654321",
            is_enabled=True,
            default_variant="parwa",
        )

        d = config.to_dict()
        # Short SID (< 8 chars) gets fully masked
        assert d["twilio_account_sid"] != "AC9876543210"
        assert d["twilio_phone_number"] == "+1987654321"
        assert d["number_source"] == "bring_own"

    def test_voice_config_column_nullable_twilio_fields(self):
        """Twilio columns should be nullable to support parwa_provided mode."""
        from database.models.voice_channel import VoiceChannelConfig

        table = VoiceChannelConfig.__table__
        assert table.c.twilio_account_sid.nullable is True
        assert table.c.twilio_auth_token_encrypted.nullable is True
        assert table.c.twilio_phone_number.nullable is True

    def test_voice_service_has_provision_method(self):
        """VoiceChannelService should have provision_parwa_number method."""
        from app.services.voice_channel_service import VoiceChannelService
        assert hasattr(VoiceChannelService, "provision_parwa_number")

    def test_voice_service_has_release_method(self):
        """VoiceChannelService should have release_parwa_number method."""
        from app.services.voice_channel_service import VoiceChannelService
        assert hasattr(VoiceChannelService, "release_parwa_number")


# ═══════════════════════════════════════════════════════════════════
# 4. MCP server → ExternalToolBus Delegation
# ═══════════════════════════════════════════════════════════════════

class TestMCPExternalToolBusDelegation:
    """Integration: MCP thin wrapper correctly delegates to canonical bus."""

    def test_mcp_wrapper_re_exports_canonical_bus(self):
        """MCP wrapper should re-export ExternalToolBus from canonical location."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "mcp_external_tool_bus",
            os.path.join(
                os.path.dirname(__file__), '..', '..', 'mcp_server',
                'integrations', 'external_tool_bus.py'
            )
        )
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Verify re-exports
        assert hasattr(mod, "ExternalToolBus")
        assert hasattr(mod, "ToolResult")
        assert hasattr(mod, "ProviderConfig")
        assert hasattr(mod, "Channel")
        assert hasattr(mod, "external_tool_bus")

    def test_mcp_wrapper_bus_is_same_class(self):
        """MCP wrapper's ExternalToolBus should be the same class as canonical."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "mcp_external_tool_bus",
            os.path.join(
                os.path.dirname(__file__), '..', '..', 'mcp_server',
                'integrations', 'external_tool_bus.py'
            )
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        from app.core.external_tool_bus import ExternalToolBus as CanonicalBus
        assert mod.ExternalToolBus is CanonicalBus


# ═══════════════════════════════════════════════════════════════════
# 5. ExternalToolExecutor Integration
# ═══════════════════════════════════════════════════════════════════

class TestExternalToolExecutorIntegration:
    """Integration: ExternalToolExecutor delegates to ExternalToolBus correctly."""

    @pytest.mark.asyncio
    async def test_execute_pipeline_actions_empty(self):
        """execute_pipeline_actions should return empty dict when no actions."""
        from app.core.external_tool_executor import execute_pipeline_actions

        result = await execute_pipeline_actions(
            variant_tier="parwa",
            company_id="test_co",
            pipeline_result={"step_outputs": {}},
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_execute_pipeline_actions_no_auto_action(self):
        """Should handle pipeline result without auto_action key."""
        from app.core.external_tool_executor import execute_pipeline_actions

        result = await execute_pipeline_actions(
            variant_tier="parwa",
            company_id="test_co",
            pipeline_result={"step_outputs": {"auto_action": {}}},
        )
        assert result == {}

    def test_action_tool_map_covers_all_channels(self):
        """ACTION_TOOL_MAP should map actions to all 4 channel types."""
        from app.core.external_tool_executor import ACTION_TOOL_MAP
        from app.core.channel_permissions import Channel

        channels_in_map = set(ACTION_TOOL_MAP.values())
        assert Channel.EMAIL in channels_in_map
        assert Channel.SMS in channels_in_map
        assert Channel.VOICE in channels_in_map
        assert Channel.CHAT in channels_in_map

    def test_get_variant_channels_uses_bus(self):
        """get_variant_channels should use ExternalToolBus provider status."""
        from app.core.external_tool_executor import get_variant_channels

        result = get_variant_channels("parwa")
        assert result["variant"] == "parwa"
        assert "channels" in result
        assert result["channels"]["email"]["allowed"] is True
        assert result["channels"]["sms"]["allowed"] is True
        assert result["channels"]["voice"]["allowed"] is True
        assert result["channels"]["chat"]["allowed"] is True
        # push and webhook are NOT allowed for parwa
        assert result["channels"]["push"]["allowed"] is False
        assert result["channels"]["webhook"]["allowed"] is False

    def test_production_connector_uses_bus(self):
        """ProductionConnector should delegate to ExternalToolBus."""
        from app.core.production_connector import ProductionConnector
        connector = ProductionConnector()
        assert hasattr(connector, "tool_bus")
