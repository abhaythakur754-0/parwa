"""
PARWA Day 6 Security Tests — Input Validation & Hardening

Tests for all 12 Day 6 findings:
  M-04: email-validator library usage in verification.py
  M-14: Pydantic schemas for ai_engine.py body:dict endpoints
  M-20: Password complexity (already done in Day 3, tested here)
  M-21: CSP hardening (nginx.conf tested for no unsafe-eval)
  M-23: MCP CORS wildcard fallback
  M-32: Celery task payload size limit
  M-34: Billing limit param le=50 constraint
  L-01: File magic-byte validation
  L-03: APIKeyScope enum usage (already done, verified)
  L-04: Rate limiter stale entry cleanup
  L-05: Circuit breaker threading locks
  L-06: Configurable Brevo IP ranges
"""

import os
import sys
import threading
import time
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ═══════════════════════════════════════════════════════════════════
# M-04: Email validator library tests
# ═══════════════════════════════════════════════════════════════════


class TestEmailValidationM04:
    """Tests for M-04: email-validator library usage in verification.py."""

    def test_valid_email_accepted(self):
        """Valid business emails should pass validation."""
        from pydantic import ValidationError as PydanticValidationError

        # We test the validator logic directly
        from email_validator import validate_email, EmailNotValidError

        # Valid emails
        for email in [
            "user@example.com",
            "user.name@company.co.uk",
            "admin+test@parwa.ai",
            "user@sub.domain.org",
        ]:
            result = validate_email(email, check_deliverability=False)
            assert result.email is not None

    def test_invalid_email_rejected(self):
        """Invalid emails should raise EmailNotValidError."""
        from email_validator import validate_email, EmailNotValidError

        invalid_emails = [
            "notanemail",
            "@nodomain.com",
            "user@",
            "user@.com",
            "user space@domain.com",
            "",
        ]
        for email in invalid_emails:
            with pytest.raises(EmailNotValidError):
                validate_email(email, check_deliverability=False)

    def test_email_normalization(self):
        """email-validator normalizes the email (domain lowercased)."""
        from email_validator import validate_email

        result = validate_email("User@Example.COM", check_deliverability=False)
        # Per RFC 5321, the local part is case-sensitive, domain is lowercased.
        # The normalized property returns the email with domain lowercased.
        assert result.normalized == "User@example.com"
        assert "@example.com" in result.normalized  # Domain is lowercased

    def test_send_otp_request_schema_rejects_invalid_email(self):
        """SendOTPRequest Pydantic model should reject invalid emails."""
        from pydantic import ValidationError as PydanticValidationError

        # Import the schema — may fail if backend not fully loadable
        try:
            from backend.app.api.verification import SendOTPRequest
        except ImportError:
            pytest.skip("verification module not importable in test env")

        with pytest.raises(PydanticValidationError):
            SendOTPRequest(email="not-an-email")

    def test_verify_otp_request_schema_rejects_invalid_email(self):
        """VerifyOTPRequest Pydantic model should reject invalid emails."""
        from pydantic import ValidationError as PydanticValidationError

        try:
            from backend.app.api.verification import VerifyOTPRequest
        except ImportError:
            pytest.skip("verification module not importable in test env")

        with pytest.raises(PydanticValidationError):
            VerifyOTPRequest(email="bad", otp_code="123456")


# ═══════════════════════════════════════════════════════════════════
# M-14: Pydantic schemas for ai_engine.py body:dict endpoints
# ═══════════════════════════════════════════════════════════════════


class TestPydanticSchemasM14:
    """Tests for M-14: Pydantic schemas replace raw body:dict."""

    def test_update_capability_request_requires_variant_type(self):
        """UpdateCapabilityRequest should require variant_type."""
        from pydantic import ValidationError as PydanticValidationError

        try:
            from backend.app.api.ai_engine import UpdateCapabilityRequest
        except ImportError:
            pytest.skip("ai_engine module not importable in test env")

        # Missing required field
        with pytest.raises(PydanticValidationError):
            UpdateCapabilityRequest()

        # Valid
        req = UpdateCapabilityRequest(
            variant_type="parwa",
            config={"key": "value"},
        )
        assert req.variant_type == "parwa"
        assert req.config == {"key": "value"}
        assert req.instance_id is None

    def test_batch_capability_update_request(self):
        """BatchCapabilityUpdateRequest should validate items."""
        from pydantic import ValidationError as PydanticValidationError

        try:
            from backend.app.api.ai_engine import (
                BatchCapabilityUpdateRequest,
                BatchCapabilityUpdateItem,
            )
        except ImportError:
            pytest.skip("ai_engine module not importable in test env")

        # Empty list should fail (min_length=1)
        with pytest.raises(PydanticValidationError):
            BatchCapabilityUpdateRequest(updates=[])

        # Valid
        item = BatchCapabilityUpdateItem(
            feature_id="feat_1",
            variant_type="parwa",
            is_enabled=True,
        )
        req = BatchCapabilityUpdateRequest(updates=[item])
        assert len(req.updates) == 1
        assert req.updates[0].feature_id == "feat_1"

    def test_create_instance_request_field_validation(self):
        """CreateInstanceRequest should validate instance_name bounds."""
        from pydantic import ValidationError as PydanticValidationError

        try:
            from backend.app.api.ai_engine import CreateInstanceRequest
        except ImportError:
            pytest.skip("ai_engine module not importable in test env")

        # Empty name should fail
        with pytest.raises(PydanticValidationError):
            CreateInstanceRequest(instance_name="", variant_type="parwa")

        # Missing required should fail
        with pytest.raises(PydanticValidationError):
            CreateInstanceRequest()

        # Valid
        req = CreateInstanceRequest(
            instance_name="My Instance",
            variant_type="parwa_high",
            channel_assignment=["email", "chat"],
        )
        assert req.instance_name == "My Instance"
        assert len(req.channel_assignment) == 2

    def test_route_ticket_request(self):
        """RouteTicketRequest should require ticket_id."""
        from pydantic import ValidationError as PydanticValidationError

        try:
            from backend.app.api.ai_engine import RouteTicketRequest
        except ImportError:
            pytest.skip("ai_engine module not importable in test env")

        with pytest.raises(PydanticValidationError):
            RouteTicketRequest()

        req = RouteTicketRequest(ticket_id="tkt_123", strategy="round_robin")
        assert req.ticket_id == "tkt_123"
        assert req.strategy == "round_robin"

    def test_instance_override_request_all_required(self):
        """InstanceOverrideRequest should require all 4 fields."""
        from pydantic import ValidationError as PydanticValidationError

        try:
            from backend.app.api.ai_engine import InstanceOverrideRequest
        except ImportError:
            pytest.skip("ai_engine module not importable in test env")

        with pytest.raises(PydanticValidationError):
            InstanceOverrideRequest(feature_id="f1")

        req = InstanceOverrideRequest(
            feature_id="f1",
            variant_type="parwa",
            instance_id="inst_1",
            is_enabled=True,
            config_json={"key": "val"},
        )
        assert req.is_enabled is True

    def test_batch_entitlement_check_request_min_items(self):
        """BatchEntitlementCheckRequest should enforce min_length on feature_ids."""
        from pydantic import ValidationError as PydanticValidationError

        try:
            from backend.app.api.ai_engine import BatchEntitlementCheckRequest
        except ImportError:
            pytest.skip("ai_engine module not importable in test env")

        with pytest.raises(PydanticValidationError):
            BatchEntitlementCheckRequest(
                feature_ids=[],
                variant_type="parwa",
            )

    def test_reset_budget_request_default(self):
        """ResetBudgetRequest should default to 'daily'."""
        try:
            from backend.app.api.ai_engine import ResetBudgetRequest
        except ImportError:
            pytest.skip("ai_engine module not importable in test env")

        req = ResetBudgetRequest()
        assert req.budget_type == "daily"

        req_monthly = ResetBudgetRequest(budget_type="monthly")
        assert req_monthly.budget_type == "monthly"


# ═══════════════════════════════════════════════════════════════════
# M-21: CSP hardening
# ═══════════════════════════════════════════════════════════════════


class TestCSPHardeningM21:
    """Tests for M-21: CSP no longer contains unsafe-eval."""

    def test_nginx_conf_no_unsafe_eval_in_script_src(self):
        """nginx.conf CSP should NOT have unsafe-eval in script-src."""
        nginx_conf_path = os.path.join(
            os.path.dirname(__file__), "..", "nginx", "nginx.conf"
        )
        if not os.path.exists(nginx_conf_path):
            pytest.skip("nginx.conf not found")

        with open(nginx_conf_path, "r") as f:
            content = f.read()

        # Find the CSP line
        for line in content.split("\n"):
            if "Content-Security-Policy" in line:
                # Extract the directive value
                if "script-src" in line:
                    # Extract the script-src portion
                    script_src_start = line.index("script-src")
                    script_src_end = line.index(";", script_src_start)
                    script_src = line[script_src_start:script_src_end]
                    assert "unsafe-eval" not in script_src, (
                        "CSP script-src must not contain 'unsafe-eval'"
                    )
                    return

        pytest.fail("Content-Security-Policy header not found in nginx.conf")

    def test_nginx_conf_has_object_src_none(self):
        """nginx.conf CSP should include object-src 'none'."""
        nginx_conf_path = os.path.join(
            os.path.dirname(__file__), "..", "nginx", "nginx.conf"
        )
        if not os.path.exists(nginx_conf_path):
            pytest.skip("nginx.conf not found")

        with open(nginx_conf_path, "r") as f:
            content = f.read()

        assert "object-src 'none'" in content, (
            "CSP should include object-src 'none'"
        )

    def test_nginx_conf_has_base_uri_self(self):
        """nginx.conf CSP should include base-uri 'self'."""
        nginx_conf_path = os.path.join(
            os.path.dirname(__file__), "..", "nginx", "nginx.conf"
        )
        if not os.path.exists(nginx_conf_path):
            pytest.skip("nginx.conf not found")

        with open(nginx_conf_path, "r") as f:
            content = f.read()

        assert "base-uri 'self'" in content, (
            "CSP should include base-uri 'self'"
        )


# ═══════════════════════════════════════════════════════════════════
# M-23: MCP CORS wildcard fallback
# ═══════════════════════════════════════════════════════════════════


class TestMCPCORSM23:
    """Tests for M-23: MCP server never falls back to ['*']."""

    def test_mcp_main_no_wildcard_fallback(self):
        """mcp_server/main.py should not have fallback to ['*'] in code."""
        mcp_main_path = os.path.join(
            os.path.dirname(__file__), "..", "mcp_server", "main.py"
        )
        if not os.path.exists(mcp_main_path):
            pytest.skip("mcp_server/main.py not found")

        with open(mcp_main_path, 'r') as f:
            lines = f.readlines()

        # Skip docstrings and comments — only check code lines
        in_docstring = False
        code_lines = []
        for line in lines:
            stripped = line.strip()
            if '"""' in stripped:
                in_docstring = not in_docstring
                continue
            if not in_docstring and not stripped.startswith("#"):
                code_lines.append(stripped)

        code_content = "\n".join(code_lines)

        # Should NOT have the old pattern of falling back to ["*"]
        assert '_cors_origins = ["*"]' not in code_content, (
            "MCP CORS should never fall back to ['*'] in code"
        )
        # Should have the fail-closed pattern
        assert "_cors_origins = []" in code_content, (
            "MCP CORS should fail closed with empty list"
        )


# ═══════════════════════════════════════════════════════════════════
# M-32: Celery task payload size limit
# ═══════════════════════════════════════════════════════════════════


class TestCeleryPayloadM32:
    """Tests for M-32: Celery config has payload/worker limits."""

    def test_celery_config_has_max_tasks_per_child(self):
        """Celery config should set worker_max_tasks_per_child."""
        celery_path = os.path.join(
            os.path.dirname(__file__), "..",
            "backend", "app", "tasks", "celery_app.py"
        )
        if not os.path.exists(celery_path):
            pytest.skip("celery_app.py not found")

        with open(celery_path, "r") as f:
            content = f.read()

        assert "worker_max_tasks_per_child" in content, (
            "Celery config should set worker_max_tasks_per_child"
        )
        assert "worker_max_memory_per_child" in content, (
            "Celery config should set worker_max_memory_per_child"
        )

    def test_celery_max_payload_constant_defined(self):
        """MAX_TASK_PAYLOAD_BYTES constant should be defined."""
        try:
            from backend.app.tasks.celery_app import MAX_TASK_PAYLOAD_BYTES
        except ImportError:
            pytest.skip("celery_app module not importable")

        assert MAX_TASK_PAYLOAD_BYTES == 1 * 1024 * 1024  # 1 MB


# ═══════════════════════════════════════════════════════════════════
# M-34: Billing limit le=50 constraint
# ═══════════════════════════════════════════════════════════════════


class TestBillingLimitM34:
    """Tests for M-34: Billing proration history limit le=50."""

    def test_billing_history_limit_has_le_50(self):
        """get_proration_history should have le=50 constraint on limit."""
        billing_path = os.path.join(
            os.path.dirname(__file__), "..",
            "backend", "app", "api", "billing.py"
        )
        if not os.path.exists(billing_path):
            pytest.skip("billing.py not found")

        with open(billing_path, "r") as f:
            content = f.read()

        # Should have Query parameter with le=50
        assert 'le=50' in content, (
            "Billing proration history limit should have le=50 constraint"
        )


# ═══════════════════════════════════════════════════════════════════
# L-01: File magic-byte validation
# ═══════════════════════════════════════════════════════════════════


class TestMagicByteValidationL01:
    """Tests for L-01: File magic-byte validation."""

    def test_detect_pdf_magic_bytes(self):
        """Should detect PDF from magic bytes %PDF."""
        try:
            from backend.app.core.storage import _detect_mime_type
        except ImportError:
            pytest.skip("storage module not importable")

        pdf_content = b"%PDF-1.4 fake pdf content"
        result = _detect_mime_type(pdf_content)
        assert result == "application/pdf"

    def test_detect_docx_magic_bytes(self):
        """Should detect DOCX from PK ZIP magic bytes."""
        try:
            from backend.app.core.storage import _detect_mime_type
        except ImportError:
            pytest.skip("storage module not importable")

        # Minimal ZIP/DOCX header
        docx_content = b"PK\x03\x04\x14\x00\x00\x00\x08\x00"
        result = _detect_mime_type(docx_content)
        assert "wordprocessingml" in result or "zip" in result

    def test_detect_html_magic_bytes(self):
        """Should detect HTML from <!DOCTYPE or <!DOC."""
        try:
            from backend.app.core.storage import _detect_mime_type
        except ImportError:
            pytest.skip("storage module not importable")

        html_content = b"<!DOCTYPE html><html><body>test</body></html>"
        result = _detect_mime_type(html_content)
        assert result == "text/html"

    def test_detect_csv_magic_bytes(self):
        """Should detect CSV from comma-separated first line."""
        try:
            from backend.app.core.storage import _detect_mime_type
        except ImportError:
            pytest.skip("storage module not importable")

        csv_content = b"name,email,phone\nJohn,john@example.com,555"
        result = _detect_mime_type(csv_content)
        assert result == "text/csv"

    def test_unknown_magic_bytes_returns_none(self):
        """Should return None for unrecognized content."""
        try:
            from backend.app.core.storage import _detect_mime_type
        except ImportError:
            pytest.skip("storage module not importable")

        random_content = b"\x00\x01\x02\x03\x04\x05"
        result = _detect_mime_type(random_content)
        assert result is None

    def test_empty_content_returns_none(self):
        """Should return None for empty content."""
        try:
            from backend.app.core.storage import _detect_mime_type
        except ImportError:
            pytest.skip("storage module not importable")

        assert _detect_mime_type(b"") is None

    def test_validate_magic_bytes_rejects_mismatch(self):
        """Should reject file when magic bytes don't match extension."""
        try:
            from backend.app.core.storage import _validate_magic_bytes
        except ImportError:
            pytest.skip("storage module not importable")

        # EXE content pretending to be PDF
        exe_content = b"\x4D\x5A\x90\x00"  # MZ header (PE executable)
        with pytest.raises(ValueError, match="File content does not match"):
            _validate_magic_bytes(exe_content, "application/pdf", ".pdf")

    def test_validate_magic_bytes_allows_match(self):
        """Should not raise when magic bytes match."""
        try:
            from backend.app.core.storage import _validate_magic_bytes
        except ImportError:
            pytest.skip("storage module not importable")

        pdf_content = b"%PDF-1.4 fake pdf content"
        # Should not raise
        _validate_magic_bytes(pdf_content, "application/pdf", ".pdf")

    def test_validate_file_upload_has_content_param(self):
        """validate_file_upload should accept optional content parameter."""
        try:
            from backend.app.core.storage import validate_file_upload
        except ImportError:
            pytest.skip("storage module not importable")

        import inspect
        sig = inspect.signature(validate_file_upload)
        assert "content" in sig.parameters

    def test_extension_magic_map_exists(self):
        """_EXTENSION_MAGIC_MAP should exist with expected entries."""
        try:
            from backend.app.core.storage import _EXTENSION_MAGIC_MAP
        except ImportError:
            pytest.skip("storage module not importable")

        assert ".pdf" in _EXTENSION_MAGIC_MAP
        assert ".docx" in _EXTENSION_MAGIC_MAP
        assert ".html" in _EXTENSION_MAGIC_MAP
        assert ".csv" in _EXTENSION_MAGIC_MAP


# ═══════════════════════════════════════════════════════════════════
# L-03: APIKeyScope enum usage (verification test)
# ═══════════════════════════════════════════════════════════════════


class TestAPIKeyScopeEnumL03:
    """Tests for L-03: APIKeyScope enum exists and is used."""

    def test_api_key_scope_enum_exists(self):
        """APIKeyScope enum should exist with expected values."""
        from security.api_keys import APIKeyScope

        assert APIKeyScope.READ.value == "read"
        assert APIKeyScope.WRITE.value == "write"
        assert APIKeyScope.ADMIN.value == "admin"
        assert APIKeyScope.APPROVAL.value == "approval"

    def test_validate_scopes_uses_enum(self):
        """validate_scopes should use APIKeyScope enum internally."""
        from security.api_keys import validate_scopes, APIKeyScope

        # READ scope with admin key
        assert validate_scopes(["admin"], "read") is True
        # WRITE scope with read-only key
        assert validate_scopes(["read"], "write") is False
        # APPROVAL scope
        assert validate_scopes(["read", "approval"], "approval") is True
        assert validate_scopes(["read"], "approval") is False


# ═══════════════════════════════════════════════════════════════════
# L-04: Rate limiter stale entry cleanup
# ═══════════════════════════════════════════════════════════════════


class TestRateLimiterCleanupL04:
    """Tests for L-04: Periodic cleanup of stale rate limit entries."""

    @pytest.fixture(autouse=True)
    def _patch_logger(self):
        """Patch the structlog dependency for rate_limiter module."""
        import types as _types
        _mock_get_logger = lambda name: __import__('logging').getLogger(name)
        _mock_logger = _types.ModuleType("mock_logger")
        _mock_logger.get_logger = _mock_get_logger
        sys.modules["backend.app.logger"] = _mock_logger
        sys.modules["backend.app"] = _types.ModuleType("backend.app")
        sys.modules["backend.app"].logger = _mock_logger

    def test_sliding_window_cleanup_removes_expired(self):
        """cleanup_stale_entries should remove expired window entries."""
        from security.rate_limiter import SlidingWindowCounter

        counter = SlidingWindowCounter(
            requests_per_window=5,
            window_seconds=1,  # 1 second window for fast test
        )

        # Add entries that are already expired
        key = counter._make_key("company_1", "1.2.3.4")
        old_time = time.time() - 10  # 10 seconds ago
        counter._windows[key] = [
            (old_time, 1),
            (old_time, 1),
        ]

        removed = counter.cleanup_stale_entries()
        assert removed == 2
        assert key not in counter._windows

    def test_sliding_window_cleanup_keeps_valid(self):
        """cleanup_stale_entries should keep valid window entries."""
        from security.rate_limiter import SlidingWindowCounter

        counter = SlidingWindowCounter(
            requests_per_window=5,
            window_seconds=60,
        )

        # Add current entries
        key = counter._make_key("company_1", "1.2.3.4")
        counter._windows[key] = [
            (time.time(), 1),
            (time.time(), 1),
        ]

        removed = counter.cleanup_stale_entries()
        assert removed == 0
        assert key in counter._windows

    def test_progressive_lockout_cleanup(self):
        """ProgressiveLockout.cleanup_stale_entries should remove old records."""
        from security.rate_limiter import ProgressiveLockout

        lockout = ProgressiveLockout(decay_seconds=10)

        # Add old violation
        key = lockout._make_key("company_1", "1.2.3.4")
        lockout._violations[key] = {
            "level": 2,
            "last_violation": time.time() - 100,  # 100 seconds ago (3x decay)
        }

        removed = lockout.cleanup_stale_entries()
        assert removed == 1
        assert key not in lockout._violations

    def test_rate_limiter_has_cleanup_thread(self):
        """RateLimiter should start a cleanup daemon thread."""
        from security.rate_limiter import RateLimiter

        limiter = RateLimiter()
        try:
            assert limiter._cleanup_thread is not None
            assert limiter._cleanup_thread.daemon is True
            assert limiter._cleanup_thread.is_alive()
        finally:
            limiter.stop_cleanup()

    def test_rate_limiter_stop_cleanup(self):
        """stop_cleanup should stop the cleanup thread."""
        from security.rate_limiter import RateLimiter

        limiter = RateLimiter()
        limiter.stop_cleanup()
        # After stopping, the thread should not be alive
        # (or already finished since it's daemon)
        assert limiter._cleanup_stop.is_set()


# ═══════════════════════════════════════════════════════════════════
# L-05: Circuit breaker threading locks
# ═══════════════════════════════════════════════════════════════════


class TestCircuitBreakerLocksL05:
    """Tests for L-05: Threading locks for circuit breaker."""

    def test_circuit_breaker_has_lock(self):
        """CircuitBreaker should have a _lock attribute."""
        from security.circuit_breaker import CircuitBreaker

        breaker = CircuitBreaker("test_breaker")
        assert hasattr(breaker, "_lock")
        assert isinstance(breaker._lock, type(threading.RLock()))

    def test_concurrent_record_failure(self):
        """Concurrent record_failure calls should not corrupt state."""
        from security.circuit_breaker import CircuitBreaker

        breaker = CircuitBreaker(
            "concurrent_test",
            failure_threshold=100,
        )

        def record_n_failures(n):
            for _ in range(n):
                breaker.record_failure()

        threads = [
            threading.Thread(target=record_n_failures, args=(50,))
            for _ in range(4)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have exactly 200 failures
        assert breaker.failure_count == 200
        assert breaker.state.value == "open"

    def test_concurrent_state_transitions(self):
        """Concurrent success/failure should maintain consistent state."""
        from security.circuit_breaker import CircuitBreaker

        breaker = CircuitBreaker(
            "concurrent_state_test",
            failure_threshold=5,
            recovery_timeout=0,  # Immediate recovery for test
        )

        def mix_success_failure():
            for i in range(100):
                if i % 2 == 0:
                    breaker.record_failure()
                else:
                    breaker.record_success()

        threads = [
            threading.Thread(target=mix_success_failure)
            for _ in range(4)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # State should be valid (closed, open, or half_open)
        assert breaker.state.value in ("closed", "open", "half_open")


# ═══════════════════════════════════════════════════════════════════
# L-06: Configurable Brevo IP ranges
# ═══════════════════════════════════════════════════════════════════


class TestBrevoIPConfigurableL06:
    """Tests for L-06: Brevo IP ranges are configurable."""

    def test_default_brevo_ips(self):
        """Should use default IPs when env var is not set."""
        try:
            from backend.app.security.hmac_verification import (
                _get_brevo_ips,
                DEFAULT_BREVO_IPS,
            )
        except ImportError:
            pytest.skip("hmac_verification module not importable")

        # Ensure env var is not set
        os.environ.pop("BREVO_IP_RANGES", None)
        ips = _get_brevo_ips()
        assert ips == DEFAULT_BREVO_IPS

    def test_custom_brevo_ips_from_env(self):
        """Should read IPs from BREVO_IP_RANGES env var."""
        try:
            from backend.app.security.hmac_verification import _get_brevo_ips
        except ImportError:
            pytest.skip("hmac_verification module not importable")

        custom_ips = "10.0.0.0/8,172.16.0.0/12"
        os.environ["BREVO_IP_RANGES"] = custom_ips
        try:
            ips = _get_brevo_ips()
            assert "10.0.0.0/8" in ips
            assert "172.16.0.0/12" in ips
        finally:
            os.environ.pop("BREVO_IP_RANGES", None)

    def test_invalid_env_falls_back_to_defaults(self):
        """Should fall back to defaults when env var has invalid CIDR."""
        try:
            from backend.app.security.hmac_verification import (
                _get_brevo_ips,
                DEFAULT_BREVO_IPS,
            )
        except ImportError:
            pytest.skip("hmac_verification module not importable")

        os.environ["BREVO_IP_RANGES"] = "not-a-valid-cidr,999.999.999.999/32"
        try:
            ips = _get_brevo_ips()
            assert ips == DEFAULT_BREVO_IPS
        finally:
            os.environ.pop("BREVO_IP_RANGES", None)

    def test_verify_brevo_ip_uses_configurable_ranges(self):
        """verify_brevo_ip should use env-configured ranges."""
        try:
            from backend.app.security.hmac_verification import verify_brevo_ip
        except ImportError:
            pytest.skip("hmac_verification module not importable")

        os.environ["BREVO_IP_RANGES"] = "192.168.1.0/24"
        try:
            # IP in the custom range
            assert verify_brevo_ip("192.168.1.100") is True
            # IP not in the custom range
            assert verify_brevo_ip("10.0.0.1") is False
        finally:
            os.environ.pop("BREVO_IP_RANGES", None)

    def test_verify_brevo_ip_explicit_override(self):
        """verify_brevo_ip should accept explicit allowed_ips override."""
        try:
            from backend.app.security.hmac_verification import verify_brevo_ip
        except ImportError:
            pytest.skip("hmac_verification module not importable")

        # Custom list, no env var
        os.environ.pop("BREVO_IP_RANGES", None)
        assert verify_brevo_ip(
            "10.0.0.1",
            allowed_ips=["10.0.0.0/8"],
        ) is True
        assert verify_brevo_ip(
            "192.168.1.1",
            allowed_ips=["10.0.0.0/8"],
        ) is False


# ═══════════════════════════════════════════════════════════════════
# M-20: Password complexity (regression test)
# ═══════════════════════════════════════════════════════════════════


class TestPasswordComplexityM20:
    """Regression tests for M-20: Password complexity (implemented Day 3)."""

    def test_weak_password_rejected(self):
        """Passwords without uppercase/number/special should be rejected."""
        try:
            from backend.app.api.auth.register import validatePasswordStrength
        except ImportError:
            pytest.skip("Cannot import validatePasswordStrength")

        # All weak passwords
        weak = ["abcdef", "ABCDEFGH", "12345678", "Abcdefg1"]
        for pw in weak:
            result = validatePasswordStrength(pw)
            # At least one of these should fail
            if pw == "abcdef":
                assert not result["valid"]
            elif pw == "12345678":
                assert not result["valid"]
            elif pw == "ABCDEFGH":
                assert not result["valid"]
            elif pw == "Abcdefg1":
                assert not result["valid"]

    def test_strong_password_accepted(self):
        """Passwords meeting all criteria should be accepted."""
        try:
            from backend.app.api.auth.register import validatePasswordStrength
        except ImportError:
            pytest.skip("Cannot import validatePasswordStrength")

        strong = ["Abcdefg1!", "MyP@ss2024!", "C0mpl3x#Pass"]
        for pw in strong:
            result = validatePasswordStrength(pw)
            assert result["valid"], f"Password '{pw}' should be valid: {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
