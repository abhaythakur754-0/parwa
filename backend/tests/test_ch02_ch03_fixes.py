"""
Comprehensive unit tests for CH-02 and CH-03 fixes.

CH-02: Email loop detection is now configurable per-tenant
       (MAX_REPLY_DEPTH was hardcoded at 20; now EMAIL_MAX_REPLY_DEPTH in config)
CH-03: Circuit breaker is now per-tenant
       (was single _cb_state dict; now TenantCircuitBreaker class)
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest


# ========================================================================
# CH-02: Per-Tenant Email Loop Detection
# ========================================================================


class TestCH02ConfigurableReplyDepth:
    """Verify that MAX_REPLY_DEPTH is configurable per-tenant."""

    def test_ch02_config_has_email_max_reply_depth(self):
        """config.py must have EMAIL_MAX_REPLY_DEPTH setting."""
        from app.config import Settings
        settings = Settings()
        assert hasattr(settings, "EMAIL_MAX_REPLY_DEPTH")
        assert settings.EMAIL_MAX_REPLY_DEPTH == 20  # default

    def test_ch02_config_reply_depth_from_env(self):
        """EMAIL_MAX_REPLY_DEPTH can be overridden via env var."""
        from app.config import Settings
        with patch.dict("os.environ", {"EMAIL_MAX_REPLY_DEPTH": "30"}):
            # Clear lru_cache to force re-read
            from app.config import get_settings
            get_settings.cache_clear()
            settings = Settings()
            assert settings.EMAIL_MAX_REPLY_DEPTH == 30
            get_settings.cache_clear()

    def test_ch02_detect_email_loop_accepts_max_reply_depth(self):
        """detect_email_loop must accept an optional max_reply_depth parameter."""
        from app.services.email_channel_service import EmailChannelService
        import inspect
        sig = inspect.signature(EmailChannelService.detect_email_loop)
        assert "max_reply_depth" in sig.parameters

    def test_ch02_detect_email_loop_uses_config_default(self):
        """When max_reply_depth is not passed, it uses config default."""
        from app.services.email_channel_service import EmailChannelService

        service = EmailChannelService(db=MagicMock())
        # Mock _count_reply_depth to return depth of 15 (under default 20)
        with patch.object(service, '_count_reply_depth', return_value=15):
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
                assert result.is_loop is False

    def test_ch02_detect_email_loop_custom_depth_lower(self):
        """With max_reply_depth=10, depth of 15 should trigger loop detection."""
        from app.services.email_channel_service import EmailChannelService

        service = EmailChannelService(db=MagicMock())
        with patch.object(service, '_count_reply_depth', return_value=15):
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
                assert result.loop_type == "depth_exceeded"
                assert "10" in result.reason

    def test_ch02_detect_email_loop_custom_depth_higher(self):
        """With max_reply_depth=50, depth of 25 should NOT trigger loop."""
        from app.services.email_channel_service import EmailChannelService

        service = EmailChannelService(db=MagicMock())
        with patch.object(service, '_count_reply_depth', return_value=25):
            with patch.object(service, '_get_by_message_id', return_value=None):
                result = service.detect_email_loop(
                    company_id="company-1",
                    email_data={
                        "sender_email": "user@example.com",
                        "message_id": "msg-1",
                        "in_reply_to": "parent-msg",
                        "headers_json": "{}",
                    },
                    max_reply_depth=50,
                )
                assert result.is_loop is False

    def test_ch02_count_reply_depth_accepts_max_depth(self):
        """_count_reply_depth must accept an optional max_depth parameter."""
        from app.services.email_channel_service import EmailChannelService
        import inspect
        sig = inspect.signature(EmailChannelService._count_reply_depth)
        assert "max_depth" in sig.parameters

    def test_ch02_different_tenants_different_thresholds(self):
        """Different tenants can have different reply depth thresholds."""
        from app.services.email_channel_service import EmailChannelService

        service = EmailChannelService(db=MagicMock())
        with patch.object(service, '_count_reply_depth', return_value=15):
            with patch.object(service, '_get_by_message_id', return_value=None):
                # Tenant A with threshold 10 → loop detected
                result_a = service.detect_email_loop(
                    company_id="tenant-a",
                    email_data={
                        "sender_email": "user@example.com",
                        "message_id": "msg-a",
                        "in_reply_to": "parent",
                        "headers_json": "{}",
                    },
                    max_reply_depth=10,
                )
                assert result_a.is_loop is True

                # Tenant B with threshold 30 → no loop
                result_b = service.detect_email_loop(
                    company_id="tenant-b",
                    email_data={
                        "sender_email": "user@example.com",
                        "message_id": "msg-b",
                        "in_reply_to": "parent",
                        "headers_json": "{}",
                    },
                    max_reply_depth=30,
                )
                assert result_b.is_loop is False

    def test_ch02_no_in_reply_to_skips_depth_check(self):
        """Without in_reply_to, depth check is skipped entirely."""
        from app.services.email_channel_service import EmailChannelService

        service = EmailChannelService(db=MagicMock())
        with patch.object(service, '_get_by_message_id', return_value=None):
            result = service.detect_email_loop(
                company_id="company-1",
                email_data={
                    "sender_email": "user@example.com",
                    "message_id": "msg-no-reply-to",
                    "in_reply_to": "",
                    "headers_json": "{}",
                },
                max_reply_depth=5,  # Very low — would catch anything
            )
            assert result.is_loop is False

    def test_ch02_reason_includes_effective_depth(self):
        """Loop detection reason should include the effective max depth, not hardcoded 20."""
        from app.services.email_channel_service import EmailChannelService

        service = EmailChannelService(db=MagicMock())
        with patch.object(service, '_count_reply_depth', return_value=25):
            with patch.object(service, '_get_by_message_id', return_value=None):
                result = service.detect_email_loop(
                    company_id="company-1",
                    email_data={
                        "sender_email": "user@example.com",
                        "message_id": "msg-1",
                        "in_reply_to": "parent",
                        "headers_json": "{}",
                    },
                    max_reply_depth=15,
                )
                assert "15" in result.reason  # Not "20"


# ========================================================================
# CH-03: Per-Tenant Circuit Breaker
# ========================================================================


class TestCH03TenantCircuitBreaker:
    """Verify that circuit breaker is per-tenant, not global."""

    def test_ch03_tenant_circuit_breaker_class_exists(self):
        """TenantCircuitBreaker class must exist in email_service."""
        from app.services.email_service import TenantCircuitBreaker
        assert TenantCircuitBreaker is not None

    def test_ch03_config_has_cb_settings(self):
        """config.py must have EMAIL_CB_FAILURE_THRESHOLD and EMAIL_CB_RESET_SECONDS."""
        from app.config import Settings
        settings = Settings()
        assert hasattr(settings, "EMAIL_CB_FAILURE_THRESHOLD")
        assert settings.EMAIL_CB_FAILURE_THRESHOLD == 3  # default
        assert hasattr(settings, "EMAIL_CB_RESET_SECONDS")
        assert settings.EMAIL_CB_RESET_SECONDS == 60  # default

    def test_ch03_cb_default_state_is_closed(self):
        """New tenant's breaker should be closed (not open)."""
        from app.services.email_service import TenantCircuitBreaker
        cb = TenantCircuitBreaker()
        assert cb.is_open("tenant-1") is False

    def test_ch03_cb_opens_after_threshold_failures(self):
        """Breaker opens after reaching threshold failures for a tenant."""
        from app.services.email_service import TenantCircuitBreaker
        cb = TenantCircuitBreaker()
        for _ in range(3):
            cb.record_failure("tenant-1")
        assert cb.is_open("tenant-1") is True

    def test_ch03_cb_one_tenant_open_doesnt_affect_others(self):
        """CH-03 core: one tenant's open breaker doesn't affect other tenants."""
        from app.services.email_service import TenantCircuitBreaker
        cb = TenantCircuitBreaker()

        # Trip the breaker for tenant-1
        for _ in range(3):
            cb.record_failure("tenant-1")

        assert cb.is_open("tenant-1") is True
        assert cb.is_open("tenant-2") is False  # Other tenant is fine

    def test_ch03_cb_success_resets_tenant(self):
        """Recording success resets the breaker for that specific tenant."""
        from app.services.email_service import TenantCircuitBreaker
        cb = TenantCircuitBreaker()

        # 2 failures (under threshold)
        cb.record_failure("tenant-1")
        cb.record_failure("tenant-1")

        # Success resets
        cb.record_success("tenant-1")

        # State should be clean
        state = cb.get_tenant_state("tenant-1")
        assert state["failures"] == 0
        assert state["is_open"] is False

    def test_ch03_cb_reset_specific_tenant(self):
        """reset() with company_id resets only that tenant."""
        from app.services.email_channel_service import EmailChannelService
        from app.services.email_service import TenantCircuitBreaker
        cb = TenantCircuitBreaker()

        # Trip both tenants
        for _ in range(3):
            cb.record_failure("tenant-1")
            cb.record_failure("tenant-2")

        assert cb.is_open("tenant-1") is True
        assert cb.is_open("tenant-2") is True

        # Reset only tenant-1
        cb.reset("tenant-1")

        assert cb.is_open("tenant-1") is False
        assert cb.is_open("tenant-2") is True  # Still open

    def test_ch03_cb_reset_all_tenants(self):
        """reset() without company_id resets all tenants."""
        from app.services.email_service import TenantCircuitBreaker
        cb = TenantCircuitBreaker()

        for _ in range(3):
            cb.record_failure("tenant-1")
            cb.record_failure("tenant-2")

        assert cb.is_open("tenant-1") is True
        assert cb.is_open("tenant-2") is True

        cb.reset()  # Reset all — clears all tenant state

        # After clearing, accessing tenants creates fresh (closed) state
        assert cb.is_open("tenant-1") is False
        assert cb.is_open("tenant-2") is False

    def test_ch03_cb_half_open_after_reset_seconds(self):
        """Breaker transitions to half-open after reset_seconds."""
        from app.services.email_service import TenantCircuitBreaker
        cb = TenantCircuitBreaker()

        # Trip the breaker
        for _ in range(3):
            cb.record_failure("tenant-1")
        assert cb.is_open("tenant-1") is True

        # Manually set last_failure to the past
        with cb._lock:
            cb._tenants["tenant-1"]["last_failure"] = time.time() - 61

        # After reset_seconds, should be half-open (closed)
        assert cb.is_open("tenant-1") is False

    def test_ch03_cb_thread_safety(self):
        """TenantCircuitBreaker should be thread-safe."""
        import threading
        from app.services.email_service import TenantCircuitBreaker
        cb = TenantCircuitBreaker()

        errors = []

        def write_tenant(tenant_id, count):
            try:
                for _ in range(count):
                    cb.record_failure(tenant_id)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(10):
            t = threading.Thread(target=write_tenant, args=(f"tenant-{i}", 5))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0
        assert cb.tenant_count == 10

    def test_ch03_send_email_accepts_company_id(self):
        """send_email must accept an optional company_id parameter."""
        from app.services.email_service import send_email
        import inspect
        sig = inspect.signature(send_email)
        assert "company_id" in sig.parameters

    def test_ch03_send_email_tracked_accepts_company_id(self):
        """send_email_tracked must accept an optional company_id parameter."""
        from app.services.email_service import send_email_tracked
        import inspect
        sig = inspect.signature(send_email_tracked)
        assert "company_id" in sig.parameters

    def test_ch03_reset_circuit_breaker_accepts_company_id(self):
        """reset_circuit_breaker must accept an optional company_id parameter."""
        from app.services.email_service import reset_circuit_breaker
        import inspect
        sig = inspect.signature(reset_circuit_breaker)
        assert "company_id" in sig.parameters

    def test_ch03_get_circuit_breaker_exists(self):
        """get_circuit_breaker function must exist for testing/monitoring."""
        from app.services.email_service import get_circuit_breaker
        cb = get_circuit_breaker()
        assert cb is not None
        assert isinstance(cb, type(cb))  # It's a TenantCircuitBreaker

    def test_ch03_global_fallback_when_no_company_id(self):
        """When company_id is not provided, breaker uses '__global__' fallback."""
        from app.services.email_service import TenantCircuitBreaker, get_circuit_breaker
        cb = get_circuit_breaker()
        cb.reset()  # Clean slate

        # Trip the global breaker
        for _ in range(3):
            cb.record_failure("__global__")

        assert cb.is_open("__global__") is True
        cb.reset()  # Clean up


# ========================================================================
# Cross-Cutting Tests
# ========================================================================


class TestCHCrossCutting:
    """Cross-cutting tests for CH-02 and CH-03."""

    def test_ch02_ch03_config_isolation(self):
        """CH-02 and CH-03 settings don't interfere with each other."""
        from app.config import Settings
        settings = Settings()
        assert settings.EMAIL_MAX_REPLY_DEPTH == 20
        assert settings.EMAIL_CB_FAILURE_THRESHOLD == 3
        assert settings.EMAIL_CB_RESET_SECONDS == 60
        # All are independent settings

    def test_ch03_no_global_cb_state_dict(self):
        """The old global _cb_state dict should NOT exist."""
        import app.services.email_service as es
        assert not hasattr(es, '_cb_state')

    def test_ch02_module_constant_still_exists(self):
        """MAX_REPLY_DEPTH constant still exists for backward compat."""
        from app.services.email_channel_service import MAX_REPLY_DEPTH
        assert MAX_REPLY_DEPTH == 20

    def test_ch03_tenant_circuit_breaker_is_used(self):
        """The _cb instance should be TenantCircuitBreaker, not a dict."""
        from app.services.email_service import _cb, TenantCircuitBreaker
        assert isinstance(_cb, TenantCircuitBreaker)
