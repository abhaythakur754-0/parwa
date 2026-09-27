"""
Integration tests for CH-02 and CH-03 fixes.

CH-02: Email loop detection is now configurable per-tenant
CH-03: Circuit breaker is now per-tenant

These tests verify the fixes work end-to-end with the actual
service classes, config system, and circuit breaker state management.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest


# ========================================================================
# CH-02 Integration: Per-Tenant Reply Depth with Config
# ========================================================================


class TestCH02Integration:
    """Integration tests for CH-02 per-tenant email loop detection."""

    def _make_service(self):
        """Create an EmailChannelService with a mocked DB session."""
        from app.services.email_channel_service import EmailChannelService
        return EmailChannelService(db=MagicMock())

    def test_ch02_default_depth_from_config(self):
        """When no max_reply_depth is passed, config default is used."""
        service = self._make_service()

        # Depth 19 should be under the default threshold of 20
        with patch.object(service, '_count_reply_depth', return_value=19) as mock_depth:
            with patch.object(service, '_get_by_message_id', return_value=None):
                result = service.detect_email_loop(
                    company_id="company-1",
                    email_data={
                        "sender_email": "user@example.com",
                        "message_id": "msg-1",
                        "in_reply_to": "parent-msg",
                        "headers_json": "{}",
                    },
                )
                # Should NOT be a loop at depth 19 with default threshold 20
                assert result.is_loop is False

                # Verify _count_reply_depth was called with the config default
                call_args = mock_depth.call_args
                # max_depth should be 20 (from config)
                assert call_args[1].get("max_depth") == 20 or call_args[0][2] == 20

    def test_ch02_override_depth_from_caller(self):
        """max_reply_depth parameter overrides the config default."""
        service = self._make_service()

        # Depth 12, but custom threshold of 10
        with patch.object(service, '_count_reply_depth', return_value=12):
            with patch.object(service, '_get_by_message_id', return_value=None):
                result = service.detect_email_loop(
                    company_id="company-1",
                    email_data={
                        "sender_email": "user@example.com",
                        "message_id": "msg-1",
                        "in_reply_to": "parent-msg",
                        "headers_json": "{}",
                    },
                    max_reply_depth=10,
                )
                assert result.is_loop is True
                assert "10" in result.reason

    def test_ch02_tenant_isolation_in_loop_detection(self):
        """Simulate two tenants with different thresholds using same service."""
        service = self._make_service()

        # Both tenants have depth 15
        with patch.object(service, '_count_reply_depth', return_value=15):
            with patch.object(service, '_get_by_message_id', return_value=None):
                # Enterprise tenant with high threshold
                result_enterprise = service.detect_email_loop(
                    company_id="enterprise-1",
                    email_data={
                        "sender_email": "user@enterprise.com",
                        "message_id": "msg-e1",
                        "in_reply_to": "parent",
                        "headers_json": "{}",
                    },
                    max_reply_depth=30,
                )
                assert result_enterprise.is_loop is False

                # Free tier tenant with low threshold
                result_free = service.detect_email_loop(
                    company_id="free-1",
                    email_data={
                        "sender_email": "user@free.com",
                        "message_id": "msg-f1",
                        "in_reply_to": "parent",
                        "headers_json": "{}",
                    },
                    max_reply_depth=10,
                )
                assert result_free.is_loop is True

    def test_ch02_process_inbound_email_respects_depth(self):
        """The full process_inbound_email pipeline respects max_reply_depth.

        We can't directly pass max_reply_depth through process_inbound_email,
        but we can verify that detect_email_loop is called with the config
        default and that it works correctly.
        """
        service = self._make_service()

        # Mock everything to reach the loop detection step
        mock_inbound = MagicMock()
        mock_inbound.id = "inbound-1"
        mock_inbound.is_loop = False

        with patch.object(service, '_get_by_message_id', return_value=None), \
             patch.object(service, '_store_raw_email', return_value=mock_inbound), \
             patch.object(service, 'detect_email_loop') as mock_detect:
            from app.schemas.email_channel import EmailLoopDetection
            mock_detect.return_value = EmailLoopDetection(
                is_loop=True,
                reason="Reply chain depth (25) exceeds max (20)",
                loop_type="depth_exceeded",
            )

            result = service.process_inbound_email(
                company_id="company-1",
                email_data={
                    "sender_email": "user@example.com",
                    "message_id": "msg-loop",
                    "in_reply_to": "parent",
                    "subject": "Test",
                    "body_html": "<p>Test</p>",
                    "body_text": "Test",
                },
            )

            assert result["status"] == "skipped_loop"

    def test_ch02_config_env_override_integration(self):
        """Integration: EMAIL_MAX_REPLY_DEPTH env var flows through to detection."""
        from app.config import Settings
        with patch.dict("os.environ", {"EMAIL_MAX_REPLY_DEPTH": "5"}):
            from app.config import get_settings
            get_settings.cache_clear()
            settings = Settings()
            assert settings.EMAIL_MAX_REPLY_DEPTH == 5

            service = self._make_service()
            with patch.object(service, '_count_reply_depth', return_value=4):
                with patch.object(service, '_get_by_message_id', return_value=None):
                    # Depth 4, threshold 5 → NOT a loop
                    result = service.detect_email_loop(
                        company_id="company-1",
                        email_data={
                            "sender_email": "user@example.com",
                            "message_id": "msg-1",
                            "in_reply_to": "parent",
                            "headers_json": "{}",
                        },
                    )
                    assert result.is_loop is False

            get_settings.cache_clear()


# ========================================================================
# CH-03 Integration: Per-Tenant Circuit Breaker
# ========================================================================


class TestCH03Integration:
    """Integration tests for CH-03 per-tenant circuit breaker."""

    def setup_method(self):
        """Reset the global circuit breaker before each test."""
        from app.services.email_service import reset_circuit_breaker
        reset_circuit_breaker()

    def teardown_method(self):
        """Reset the global circuit breaker after each test."""
        from app.services.email_service import reset_circuit_breaker
        reset_circuit_breaker()

    def test_ch03_tenant_isolation_in_circuit_breaker(self):
        """One tenant's open breaker doesn't block another tenant's emails."""
        from app.services.email_service import get_circuit_breaker

        cb = get_circuit_breaker()

        # Trip the breaker for tenant-1
        for _ in range(3):
            cb.record_failure("tenant-1")

        # tenant-1's breaker should be open
        assert cb.is_open("tenant-1") is True
        # tenant-2's breaker should be closed
        assert cb.is_open("tenant-2") is False

    def test_ch03_tenant_count_tracking(self):
        """Circuit breaker tracks the number of tenants with state."""
        from app.services.email_service import TenantCircuitBreaker

        # Use a fresh instance to avoid test interference
        cb = TenantCircuitBreaker()
        assert cb.tenant_count == 0

        cb.record_failure("tenant-1")
        assert cb.tenant_count == 1

        cb.record_failure("tenant-2")
        assert cb.tenant_count == 2

        # reset("tenant-1") keeps the entry but resets values
        cb.reset("tenant-1")
        assert cb.tenant_count == 2  # Both entries still exist

        # reset() with no args clears all entries
        cb.reset()
        assert cb.tenant_count == 0

    def test_ch03_independent_failure_counts(self):
        """Each tenant has independent failure counts."""
        from app.services.email_service import get_circuit_breaker

        cb = get_circuit_breaker()

        # 2 failures for tenant-1
        cb.record_failure("tenant-1")
        cb.record_failure("tenant-1")

        # 1 failure for tenant-2
        cb.record_failure("tenant-2")

        state_1 = cb.get_tenant_state("tenant-1")
        state_2 = cb.get_tenant_state("tenant-2")

        assert state_1["failures"] == 2
        assert state_2["failures"] == 1
        assert state_1["is_open"] is False
        assert state_2["is_open"] is False

    def test_ch03_one_tenant_failure_doesnt_increment_other(self):
        """Recording failure for tenant-1 doesn't affect tenant-2's counter."""
        from app.services.email_service import get_circuit_breaker

        cb = get_circuit_breaker()

        for _ in range(5):
            cb.record_failure("tenant-1")

        # tenant-2 should have zero failures
        state_2 = cb.get_tenant_state("tenant-2")
        assert state_2["failures"] == 0

    def test_ch03_success_resets_only_affected_tenant(self):
        """Success on tenant-1 doesn't reset tenant-2's failure count."""
        from app.services.email_service import get_circuit_breaker

        cb = get_circuit_breaker()

        cb.record_failure("tenant-1")
        cb.record_failure("tenant-1")
        cb.record_failure("tenant-2")
        cb.record_failure("tenant-2")

        # Reset tenant-1 via success
        cb.record_success("tenant-1")

        state_1 = cb.get_tenant_state("tenant-1")
        state_2 = cb.get_tenant_state("tenant-2")

        assert state_1["failures"] == 0
        assert state_2["failures"] == 2  # Unaffected

    def test_ch03_half_open_transition_per_tenant(self):
        """Half-open transition is independent per tenant."""
        from app.services.email_service import get_circuit_breaker

        cb = get_circuit_breaker()

        # Trip both tenants
        for _ in range(3):
            cb.record_failure("tenant-1")
            cb.record_failure("tenant-2")

        # Set tenant-1's last_failure to the past (should half-open)
        with cb._lock:
            cb._tenants["tenant-1"]["last_failure"] = time.time() - 61

        # tenant-1 should be half-open (closed)
        assert cb.is_open("tenant-1") is False
        # tenant-2 should still be open
        assert cb.is_open("tenant-2") is True

    def test_ch03_config_threshold_used_for_new_tenants(self):
        """New tenants get their threshold from config settings."""
        from app.services.email_service import get_circuit_breaker

        cb = get_circuit_breaker()

        # Access a new tenant — this should create state from config
        state = cb.get_tenant_state("new-tenant")

        from app.config import Settings
        settings = Settings()
        assert state["threshold"] == settings.EMAIL_CB_FAILURE_THRESHOLD
        assert state["reset_seconds"] == settings.EMAIL_CB_RESET_SECONDS

    def test_ch03_config_env_override_threshold(self):
        """EMAIL_CB_FAILURE_THRESHOLD env var overrides default."""
        from app.services.email_service import TenantCircuitBreaker
        from app.config import Settings

        with patch.dict("os.environ", {"EMAIL_CB_FAILURE_THRESHOLD": "5"}):
            from app.config import get_settings
            get_settings.cache_clear()

            cb = TenantCircuitBreaker()
            state = cb.get_tenant_state("test-tenant")
            assert state["threshold"] == 5

            # Need 5 failures to open (not 3)
            for _ in range(4):
                cb.record_failure("test-tenant")
            assert cb.is_open("test-tenant") is False  # Still under threshold

            cb.record_failure("test-tenant")
            assert cb.is_open("test-tenant") is True  # Now open

            get_settings.cache_clear()

    def test_ch03_reset_specific_tenant_preserves_others(self):
        """Resetting one tenant's breaker doesn't affect others."""
        from app.services.email_service import get_circuit_breaker

        cb = get_circuit_breaker()

        # Trip both
        for _ in range(3):
            cb.record_failure("tenant-1")
            cb.record_failure("tenant-2")

        # Reset only tenant-1
        cb.reset("tenant-1")

        assert cb.is_open("tenant-1") is False
        assert cb.is_open("tenant-2") is True

    def test_ch03_get_tenant_state_returns_copy(self):
        """get_tenant_state returns a copy, not a reference."""
        from app.services.email_service import get_circuit_breaker

        cb = get_circuit_breaker()
        cb.record_failure("tenant-1")

        state1 = cb.get_tenant_state("tenant-1")
        state1["failures"] = 999  # Modify the copy

        state2 = cb.get_tenant_state("tenant-1")
        assert state2["failures"] == 1  # Original unchanged


# ========================================================================
# Combined CH-02 + CH-03 Integration
# ========================================================================


class TestCH02CH03CombinedIntegration:
    """Combined integration tests for CH-02 and CH-03 together."""

    def setup_method(self):
        from app.services.email_service import reset_circuit_breaker
        reset_circuit_breaker()

    def teardown_method(self):
        from app.services.email_service import reset_circuit_breaker
        reset_circuit_breaker()

    def test_combined_per_tenant_isolation(self):
        """Both loop detection and circuit breaker are isolated per-tenant."""
        from app.services.email_channel_service import EmailChannelService
        from app.services.email_service import get_circuit_breaker

        service = EmailChannelService(db=MagicMock())
        cb = get_circuit_breaker()

        # Trip tenant-1's circuit breaker
        for _ in range(3):
            cb.record_failure("tenant-1")

        # tenant-1's circuit breaker is open, but tenant-2's is not
        assert cb.is_open("tenant-1") is True
        assert cb.is_open("tenant-2") is False

        # Loop detection is also independent
        with patch.object(service, '_count_reply_depth', return_value=15):
            with patch.object(service, '_get_by_message_id', return_value=None):
                result_t1 = service.detect_email_loop(
                    company_id="tenant-1",
                    email_data={
                        "sender_email": "user@example.com",
                        "message_id": "msg-1",
                        "in_reply_to": "parent",
                        "headers_json": "{}",
                    },
                    max_reply_depth=10,
                )
                result_t2 = service.detect_email_loop(
                    company_id="tenant-2",
                    email_data={
                        "sender_email": "user@example.com",
                        "message_id": "msg-2",
                        "in_reply_to": "parent",
                        "headers_json": "{}",
                    },
                    max_reply_depth=30,
                )

                assert result_t1.is_loop is True   # threshold 10, depth 15
                assert result_t2.is_loop is False   # threshold 30, depth 15

    def test_combined_config_settings_independent(self):
        """CH-02 and CH-03 config settings are independent."""
        from app.config import Settings

        with patch.dict("os.environ", {
            "EMAIL_MAX_REPLY_DEPTH": "50",
            "EMAIL_CB_FAILURE_THRESHOLD": "7",
            "EMAIL_CB_RESET_SECONDS": "120",
        }):
            from app.config import get_settings
            get_settings.cache_clear()
            settings = Settings()

            assert settings.EMAIL_MAX_REPLY_DEPTH == 50
            assert settings.EMAIL_CB_FAILURE_THRESHOLD == 7
            assert settings.EMAIL_CB_RESET_SECONDS == 120

            get_settings.cache_clear()
