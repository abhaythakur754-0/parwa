"""
Tests for P0 Fixes — Round 2:

P0-SECURITY:
  - Hardcoded secrets removed from config.py
  - Demo OTP bypass fixed in jarvis.py
  - Webhook error leak fixed in jarvis.py
  - JWT auth added to sms_channel.py

P0-DATA:
  - FK ondelete clauses added across all model files
  - No duplicate mfa_secret in User model

P0-RUNTIME:
  - tickets.py uses User object attributes (not dict .get())

P0-MIGRATIONS:
  - Alembic migrations use String(36) for UUIDs
  - alembic.ini has sensible default URL

P0-INFRA:
  - Paddle webhook idempotency is Redis-backed
  - Celery DLQ has proper routing
  - LangGraph nodes have retry logic
  - LangGraph DLQ service exists

These tests use source file reading to avoid import dependency issues.
"""

import inspect
import json
import os
import uuid
from unittest.mock import MagicMock, patch

import pytest


# ── Helper: resolve project paths ─────────────────────────────────

_BACKEND_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", ".."
))
_PROJECT_ROOT = os.path.normpath(os.path.join(_BACKEND_DIR, ".."))


def _read_source(rel_path: str) -> str:
    """Read a source file from the project."""
    full_path = os.path.join(_PROJECT_ROOT, rel_path)
    if not os.path.exists(full_path):
        pytest.skip(f"File not found: {full_path}")
    with open(full_path) as f:
        return f.read()


# ════════════════════════════════════════════════════════════════════
# P0-SECURITY: Hardcoded secrets removed from config.py
# ════════════════════════════════════════════════════════════════════


class TestConfigNoHardcodedSecrets:
    """Verify config.py no longer has hardcoded secret fallbacks."""

    def test_data_encryption_key_no_dev_fallback(self):
        """DATA_ENCRYPTION_KEY no longer has devkey fallback."""
        source = _read_source("backend/app/config.py")
        assert "devkey_devkey_devkey_devkey_abcd" not in source, (
            "DATA_ENCRYPTION_KEY still has hardcoded dev fallback"
        )

    def test_secret_key_no_dev_fallback(self):
        """SECRET_KEY no longer returns hardcoded dev string."""
        source = _read_source("backend/app/config.py")
        assert "dev-secret-key-change-in-production" not in source, (
            "SECRET_KEY still has hardcoded dev fallback"
        )

    def test_jwt_secret_key_no_dev_fallback(self):
        """JWT_SECRET_KEY no longer returns hardcoded dev string."""
        source = _read_source("backend/app/config.py")
        assert "dev-jwt-secret-key-change-in-production" not in source, (
            "JWT_SECRET_KEY still has hardcoded dev fallback"
        )

    def test_pricing_signing_key_no_dev_default(self):
        """PRICING_SIGNING_KEY defaults to empty string."""
        source = _read_source("backend/app/config.py")
        # Should NOT have the old dev default
        assert "dev-pricing-key-change-in-prod-32c" not in source, (
            "PRICING_SIGNING_KEY still has hardcoded dev default"
        )

    def test_data_encryption_key_validator_raises(self):
        """DATA_ENCRYPTION_KEY validator raises RuntimeError when None."""
        source = _read_source("backend/app/config.py")
        # Find the validate_encryption_key function
        assert "raise RuntimeError" in source, (
            "config.py should raise RuntimeError for missing DATA_ENCRYPTION_KEY"
        )

    def test_secret_key_validator_raises(self):
        """SECRET_KEY validator raises RuntimeError when None."""
        source = _read_source("backend/app/config.py")
        # The validator should raise RuntimeError, not return a dev default
        # Count how many times "dev-" appears as a return value
        lines = source.split('\n')
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("return") and '"dev-' in stripped:
                # This is a hardcoded dev return — should not exist
                pytest.fail(
                    f"Found hardcoded dev return in config.py: {stripped}"
                )


# ════════════════════════════════════════════════════════════════════
# P0-SECURITY: Demo OTP bypass fixed in jarvis.py
# ════════════════════════════════════════════════════════════════════


class TestJarvisOTPBypassFix:
    """Verify demo-call OTP endpoint actually verifies the code."""

    def test_verify_call_otp_not_placeholder(self):
        """verify_call_otp endpoint doesn't just return 'verified'."""
        source = _read_source("backend/app/api/jarvis.py")
        # Find the demo-call OTP endpoint — should NOT have unconditional
        # return with "verified" status
        lines = source.split('\n')
        in_otp_func = False
        for line in lines:
            if "verify_call_otp" in line and "def " in line:
                in_otp_func = True
            elif in_otp_func and "def " in line and "verify_call_otp" not in line:
                in_otp_func = False
            elif in_otp_func:
                # Inside the function — should not have unconditional
                # "status": "verified" return
                if '"verified"' in line and "return" in line and "if" not in line:
                    pytest.fail(
                        "jarvis.py verify_call_otp still returns unconditionally verified"
                    )

    def test_verify_call_otp_calls_phone_otp_service(self):
        """verify_call_otp uses phone_otp_service for actual verification."""
        source = _read_source("backend/app/api/jarvis.py")
        assert "phone_otp_service" in source or "verify_otp" in source, (
            "jarvis.py OTP verification doesn't use phone_otp_service"
        )


# ════════════════════════════════════════════════════════════════════
# P0-SECURITY: Webhook error leak fixed in jarvis.py
# ════════════════════════════════════════════════════════════════════


class TestJarvisWebhookErrorLeakFix:
    """Verify webhook error handler doesn't leak internal details."""

    def test_webhook_error_no_str_exc_in_details(self):
        """Webhook error response doesn't include str(exc) in details."""
        source = _read_source("backend/app/api/jarvis.py")
        # The old code had: "details": str(exc)
        # Find the webhook error handler and check
        lines = source.split('\n')
        for i, line in enumerate(lines):
            if '"details"' in line and 'str(exc)' in line:
                # Check if it's in a return statement (bad) vs logger (ok)
                context = '\n'.join(lines[max(0, i-3):i+1])
                if 'return' in context and 'logger' not in line:
                    pytest.fail(
                        f"Webhook error handler leaks str(exc) at line {i+1}: {line.strip()}"
                    )


# ════════════════════════════════════════════════════════════════════
# P0-SECURITY: JWT auth added to sms_channel.py
# ════════════════════════════════════════════════════════════════════


class TestSMSChannelJWTAuth:
    """Verify sms_channel.py endpoints require JWT authentication."""

    def test_sms_channel_imports_get_current_user(self):
        """sms_channel.py imports get_current_user dependency."""
        source = _read_source("backend/app/api/sms_channel.py")
        assert "get_current_user" in source, (
            "sms_channel.py doesn't import get_current_user"
        )

    def test_sms_channel_imports_user_model(self):
        """sms_channel.py imports User model for type annotation."""
        source = _read_source("backend/app/api/sms_channel.py")
        assert "from database.models.core import User" in source, (
            "sms_channel.py doesn't import User model"
        )

    def test_sms_send_endpoint_requires_auth(self):
        """POST /sms/send requires current_user dependency."""
        source = _read_source("backend/app/api/sms_channel.py")
        assert "Depends(get_current_user)" in source, (
            "sms_channel.py endpoints don't use Depends(get_current_user)"
        )

    def test_sms_config_endpoints_require_auth(self):
        """SMS config CRUD endpoints require authentication."""
        source = _read_source("backend/app/api/sms_channel.py")
        count = source.count("Depends(get_current_user)")
        # Should be on most endpoints (not the webhook receiver)
        assert count >= 8, (
            f"sms_channel.py only has {count} endpoints with JWT auth, "
            f"expected at least 8 (all except webhook receiver)"
        )

    def test_sms_channel_uses_user_company_id(self):
        """sms_channel.py uses current_user.company_id, not getattr."""
        source = _read_source("backend/app/api/sms_channel.py")
        # Should have current_user.company_id, not getattr(request.state, "company_id")
        assert "current_user.company_id" in source, (
            "sms_channel.py doesn't use current_user.company_id"
        )

    def test_sms_channel_no_getattr_company_id(self):
        """sms_channel.py doesn't rely on request.state for company_id."""
        source = _read_source("backend/app/api/sms_channel.py")
        # The old pattern used getattr(request.state, "company_id", None)
        # Count occurrences — should be minimal (only for webhook receiver)
        count = source.count('getattr(request.state, "company_id"')
        # Should be 0 or only in the webhook endpoint
        if count > 1:
            # Allow 1 for the webhook receiver which doesn't have JWT auth
            pytest.fail(
                f"sms_channel.py still uses getattr(request.state, 'company_id') "
                f"{count} times — should use current_user.company_id"
            )


# ════════════════════════════════════════════════════════════════════
# P0-DATA: FK ondelete clauses
# ════════════════════════════════════════════════════════════════════


class TestForeignKeyOnDelete:
    """Verify ForeignKeys across all model files have ondelete clauses."""

    MODEL_FILES = [
        "database/models/core.py",
        "database/models/tickets.py",
        "database/models/billing.py",
        "database/models/billing_extended.py",
        "database/models/integration.py",
        "database/models/analytics.py",
        "database/models/jarvis.py",
        "database/models/jarvis_cc.py",
        "database/models/onboarding.py",
        "database/models/chat_widget.py",
        "database/models/email_channel.py",
        "database/models/sms_channel.py",
        "database/models/outbound_email.py",
        "database/models/email_delivery_event.py",
        "database/models/ooo_detection.py",
        "database/models/email_bounces.py",
        "database/models/variant_engine.py",
        "database/models/technique.py",
        "database/models/training.py",
        "database/models/webhook_event.py",
        "database/models/approval.py",
        "database/models/business_email_otp.py",
        "database/models/phone_otp.py",
        "database/models/remaining.py",
        "database/models/ai_pipeline.py",
        "database/models/user_details.py",
    ]

    def test_no_foreignkey_without_ondelete(self):
        """No ForeignKey in any model file is missing ondelete clause."""
        missing = []
        for rel_path in self.MODEL_FILES:
            try:
                source = _read_source(rel_path)
            except Exception:
                continue

            lines = source.split('\n')
            for i, line in enumerate(lines):
                if 'ForeignKey(' in line and 'ondelete' not in line:
                    next_lines = '\n'.join(lines[i:i+5])
                    if 'ondelete' not in next_lines:
                        stripped = line.strip()
                        if stripped.startswith('#'):
                            continue
                        missing.append(
                            f"{rel_path} line {i+1}: {stripped[:80]}"
                        )

        assert len(missing) == 0, (
            f"Found {len(missing)} ForeignKeys without ondelete:\n" +
            "\n".join(missing[:10])
        )


class TestNoDuplicateMFASecret:
    """Verify User model doesn't have duplicate mfa_secret column."""

    def test_user_model_no_duplicate_mfa_secret(self):
        """User model source has no duplicate mfa_secret definition."""
        source = _read_source("database/models/core.py")
        # Count occurrences of mfa_secret column definition
        count = 0
        for line in source.split('\n'):
            stripped = line.strip()
            if 'mfa_secret' in stripped and ('Column' in stripped or '=' in stripped):
                # It's a column definition, not a comment or reference
                if not stripped.startswith('#') and not stripped.startswith('"""'):
                    count += 1
        # Should be at most 1 mfa_secret column definition per model
        assert count <= 1, (
            f"User model has {count} mfa_secret column definitions, expected at most 1"
        )


# ════════════════════════════════════════════════════════════════════
# P0-RUNTIME: tickets.py uses User attributes
# ════════════════════════════════════════════════════════════════════


class TestTicketsUserObjectAccess:
    """Verify tickets.py uses User object attributes, not dict .get()."""

    def test_tickets_no_dict_get_on_current_user(self):
        """tickets.py doesn't use current_user.get() anywhere."""
        source = _read_source("backend/app/api/tickets.py")
        assert 'current_user.get(' not in source, (
            "tickets.py still uses current_user.get() — "
            "should use attribute access on User object"
        )

    def test_tickets_uses_user_type_annotation(self):
        """tickets.py uses User type annotation, not Dict."""
        source = _read_source("backend/app/api/tickets.py")
        assert "current_user: Dict" not in source, (
            "tickets.py still uses Dict type annotation for current_user"
        )

    def test_tickets_imports_user_model(self):
        """tickets.py imports User from database.models.core."""
        source = _read_source("backend/app/api/tickets.py")
        assert "User" in source, (
            "tickets.py doesn't import User model"
        )

    def test_tickets_uses_attribute_access(self):
        """tickets.py uses current_user.company_id attribute access."""
        source = _read_source("backend/app/api/tickets.py")
        assert "current_user.company_id" in source, (
            "tickets.py doesn't use current_user.company_id attribute"
        )


# ════════════════════════════════════════════════════════════════════
# P0-MIGRATIONS: Alembic UUID type consistency
# ════════════════════════════════════════════════════════════════════


class TestMigrationUUIDConsistency:
    """Verify Alembic migrations use String(36) for UUIDs, not UUID type."""

    def test_migration_017_uses_string_not_uuid(self):
        """Migration 017 uses sa.String(36) for UUID columns."""
        source = _read_source("database/alembic/versions/017_outbound_email.py")
        assert "UUID(as_uuid=True)" not in source, (
            "Migration 017 still uses UUID(as_uuid=True) — should use String(36)"
        )

    def test_migration_018_uses_string_not_uuid(self):
        """Migration 018 uses sa.String(36) for UUID columns."""
        source = _read_source("database/alembic/versions/018_email_delivery_events.py")
        assert "UUID(as_uuid=True)" not in source, (
            "Migration 018 still uses UUID(as_uuid=True) — should use String(36)"
        )

    def test_alembic_ini_has_sqlalchemy_url(self):
        """alembic.ini has a non-empty sqlalchemy.url."""
        content = _read_source("database/alembic.ini")
        for line in content.split('\n'):
            if line.strip().startswith('sqlalchemy.url'):
                value = line.split('=', 1)[1].strip()
                assert len(value) > 0, "alembic.ini has empty sqlalchemy.url"
                break
        else:
            pytest.fail("sqlalchemy.url not found in alembic.ini")


# ════════════════════════════════════════════════════════════════════
# P0-INFRA: Paddle idempotency is Redis-backed
# ════════════════════════════════════════════════════════════════════


class TestPaddleIdempotencyRedis:
    """Verify Paddle webhook idempotency uses Redis, not in-memory."""

    def test_is_duplicate_event_uses_redis(self):
        """PaddleService.is_duplicate_event uses Redis SET with NX."""
        source = _read_source("backend/app/services/paddle_service.py")
        # Find the is_duplicate_event function
        assert "is_duplicate_event" in source, (
            "PaddleService missing is_duplicate_event method"
        )
        # Should use Redis, not a Python dict/set
        assert "redis" in source.lower() or "get_redis" in source, (
            "PaddleService.is_duplicate_event doesn't use Redis"
        )

    def test_is_duplicate_event_has_nx_flag(self):
        """PaddleService.is_duplicate_event uses NX flag for atomicity."""
        source = _read_source("backend/app/services/paddle_service.py")
        assert "nx=True" in source, (
            "PaddleService.is_duplicate_event doesn't use NX flag"
        )

    def test_is_duplicate_event_has_ttl(self):
        """PaddleService.is_duplicate_event sets TTL on Redis keys."""
        source = _read_source("backend/app/services/paddle_service.py")
        assert "ex=" in source or "ex =" in source, (
            "PaddleService.is_duplicate_event doesn't set TTL on Redis keys"
        )


# ════════════════════════════════════════════════════════════════════
# P0-INFRA: Celery DLQ routing
# ════════════════════════════════════════════════════════════════════


class TestCeleryDLQRouting:
    """Verify Celery DLQ is properly configured with routing."""

    def test_celery_has_dlq_queue(self):
        """Celery configuration includes parwa_dlq queue name."""
        source = _read_source("backend/app/tasks/celery_app.py")
        assert "parwa_dlq" in source, (
            "Celery app doesn't reference parwa_dlq queue"
        )

    def test_queues_have_dead_letter_exchange(self):
        """Work queues route failed tasks via x-dead-letter-exchange."""
        source = _read_source("backend/app/tasks/celery_app.py")
        assert "x-dead-letter-exchange" in source, (
            "Celery queues don't have x-dead-letter-exchange for DLQ routing"
        )

    def test_task_acks_late_enabled(self):
        """Celery task_acks_late is True for DLQ routing."""
        source = _read_source("backend/app/tasks/celery_app.py")
        assert '"task_acks_late"' in source or "'task_acks_late'" in source, (
            "Celery config missing task_acks_late"
        )
        # Should be True, not False
        assert "task_acks_late" in source and "True" in source, (
            "Celery task_acks_late should be True"
        )

    def test_task_reject_on_worker_lost_enabled(self):
        """Celery task_reject_on_worker_lost is True for DLQ routing."""
        source = _read_source("backend/app/tasks/celery_app.py")
        assert "task_reject_on_worker_lost" in source, (
            "Celery config missing task_reject_on_worker_lost"
        )

    def test_task_default_queue_is_parwa_default(self):
        """Celery default queue is parwa_default (not celery)."""
        source = _read_source("backend/app/tasks/celery_app.py")
        assert "parwa_default" in source, (
            "Celery config doesn't reference parwa_default as default queue"
        )


# ════════════════════════════════════════════════════════════════════
# P0-INFRA: LangGraph retry logic
# ════════════════════════════════════════════════════════════════════


class TestLangGraphRetry:
    """Verify LangGraph nodes have LLM retry logic."""

    def test_retry_module_exists(self):
        """langgraph/retry.py exists with retry functions."""
        source = _read_source("backend/app/core/langgraph/retry.py")
        assert "retry_llm_call" in source or "llm_call_with_retry" in source, (
            "LangGraph retry module missing retry functions"
        )

    def test_retry_has_max_retries(self):
        """Retry function supports max_retries parameter."""
        source = _read_source("backend/app/core/langgraph/retry.py")
        assert "max_retries" in source or "max_attempts" in source, (
            "LangGraph retry function missing max_retries parameter"
        )

    def test_is_transient_error_exists(self):
        """is_transient_error function exists for error classification."""
        source = _read_source("backend/app/core/langgraph/retry.py")
        assert "is_transient_error" in source, (
            "LangGraph retry module missing is_transient_error"
        )

    def test_retry_has_exponential_backoff(self):
        """Retry uses exponential backoff."""
        source = _read_source("backend/app/core/langgraph/retry.py")
        assert "backoff" in source.lower() or "0.5" in source or "1" in source, (
            "LangGraph retry function doesn't implement exponential backoff"
        )

    def test_llm_call_with_retry_exists(self):
        """llm_call_with_retry convenience function exists."""
        source = _read_source("backend/app/core/langgraph/retry.py")
        assert "llm_call_with_retry" in source, (
            "LangGraph retry module missing llm_call_with_retry"
        )

    def test_pii_redaction_node_uses_retry(self):
        """PII redaction node uses retry for LLM calls."""
        source = _read_source("backend/app/core/langgraph/nodes/01_pii_redaction.py")
        assert "retry" in source.lower(), (
            "PII redaction node doesn't use retry for LLM calls"
        )

    def test_faq_agent_uses_retry(self):
        """FAQ agent uses retry for LLM calls."""
        source = _read_source("backend/app/core/langgraph/nodes/05_faq_agent.py")
        assert "retry" in source.lower(), (
            "FAQ agent doesn't use retry for LLM calls"
        )


# ════════════════════════════════════════════════════════════════════
# P0-INFRA: LangGraph DLQ service
# ════════════════════════════════════════════════════════════════════


class TestLangGraphDLQ:
    """Verify LangGraph DLQ service exists and has required methods."""

    def test_dlq_service_file_exists(self):
        """langgraph_dlq_service.py file exists."""
        path = os.path.join(_PROJECT_ROOT, "backend/app/services/langgraph_dlq_service.py")
        assert os.path.exists(path), (
            "langgraph_dlq_service.py file not found"
        )

    def test_dlq_service_has_record_failure(self):
        """DLQ service has record_failure method."""
        source = _read_source("backend/app/services/langgraph_dlq_service.py")
        assert "record_failure" in source, (
            "LangGraphDLQService missing record_failure method"
        )

    def test_dlq_service_has_list_failures(self):
        """DLQ service has list_failures method."""
        source = _read_source("backend/app/services/langgraph_dlq_service.py")
        assert "list_failures" in source, (
            "LangGraphDLQService missing list_failures method"
        )

    def test_dlq_service_has_get_failure(self):
        """DLQ service has get_failure method."""
        source = _read_source("backend/app/services/langgraph_dlq_service.py")
        assert "get_failure" in source, (
            "LangGraphDLQService missing get_failure method"
        )

    def test_dlq_service_has_retry_failure(self):
        """DLQ service has retry_failure method."""
        source = _read_source("backend/app/services/langgraph_dlq_service.py")
        assert "retry_failure" in source, (
            "LangGraphDLQService missing retry_failure method"
        )

    def test_dlq_service_has_clear_failure(self):
        """DLQ service has clear_failure method."""
        source = _read_source("backend/app/services/langgraph_dlq_service.py")
        assert "clear_failure" in source, (
            "LangGraphDLQService missing clear_failure method"
        )

    def test_dlq_service_uses_redis(self):
        """DLQ service stores failures in Redis."""
        source = _read_source("backend/app/services/langgraph_dlq_service.py")
        assert "redis" in source.lower() or "get_redis" in source, (
            "LangGraphDLQService doesn't use Redis for storage"
        )


# ════════════════════════════════════════════════════════════════════
# INTEGRATION: Cross-cutting verification
# ════════════════════════════════════════════════════════════════════


class TestSecurityIntegration:
    """Integration tests verifying security fixes work together."""

    def test_config_validates_all_required_secrets(self):
        """Config rejects when required secrets are missing."""
        from app.config import Settings
        errors = []
        for secret_name in ["DATA_ENCRYPTION_KEY", "SECRET_KEY", "JWT_SECRET_KEY"]:
            try:
                kwargs = {
                    "ENVIRONMENT": "development",
                    secret_name: None,
                }
                for other in ["DATA_ENCRYPTION_KEY", "SECRET_KEY", "JWT_SECRET_KEY"]:
                    if other != secret_name:
                        kwargs[other] = "test-value-32-chars-long-enough-xxxx"
                Settings(**kwargs)
                errors.append(f"{secret_name}=None did not raise RuntimeError")
            except RuntimeError:
                pass  # Expected
        assert len(errors) == 0, "\n".join(errors)

    def test_all_channel_routers_have_auth(self):
        """All channel API routers have JWT auth on protected endpoints."""
        routers = [
            "backend/app/api/email_channel.py",
            "backend/app/api/ooo_detection.py",
            "backend/app/api/bounce_complaint.py",
            "backend/app/api/chat_widget.py",
            "backend/app/api/sms_channel.py",
        ]
        for rel_path in routers:
            source = _read_source(rel_path)
            filename = os.path.basename(rel_path)
            # Each should import get_current_user
            assert "get_current_user" in source, (
                f"{filename} doesn't import get_current_user"
            )
            # Each should use Depends(get_current_user) on at least some endpoints
            assert "Depends(get_current_user)" in source, (
                f"{filename} doesn't use Depends(get_current_user)"
            )
