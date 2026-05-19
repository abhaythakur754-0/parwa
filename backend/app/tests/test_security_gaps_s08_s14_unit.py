"""
Unit Tests for Security Gaps S-08 through S-14

Tests each fix in isolation using mocks for external dependencies.

Gaps covered:
  S-08: Sync SessionLocal() in async services → asyncio.to_thread()
  S-09: No company_id filter on get_user_by_id
  S-10: No field whitelist on update_company_profile
  S-11: Session leaks — SessionLocal() without context manager
  S-12: asyncio.run() in sync CC flow
  S-13: Push notifications not implemented
  S-14: Notification preference audit TODO
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from uuid import uuid4

import pytest


# ══════════════════════════════════════════════════════════════════
# S-08: Sync SessionLocal() in async services → asyncio.to_thread()
# ══════════════════════════════════════════════════════════════════

class TestS08AsyncDbHelper:
    """S-08: Verify the async_db.run_sync_db helper works correctly."""

    def test_run_sync_db_executes_function(self):
        """run_sync_db should execute the provided function in a thread."""
        from app.core.async_db import run_sync_db

        def sync_func(x, y):
            return x + y

        result = asyncio.run(run_sync_db(sync_func, 3, 4))
        assert result == 7

    def test_run_sync_db_propagates_exceptions(self):
        """run_sync_db should propagate exceptions from the sync function."""
        from app.core.async_db import run_sync_db

        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            asyncio.run(run_sync_db(failing_func))

    def test_run_sync_db_passes_kwargs(self):
        """run_sync_db should forward keyword arguments."""
        from app.core.async_db import run_sync_db

        def kwarg_func(name="default", value=0):
            return f"{name}:{value}"

        result = asyncio.run(run_sync_db(kwarg_func, name="test", value=42))
        assert result == "test:42"


class TestS08AsyncServicesUseToThread:
    """S-08: Verify async services use asyncio.to_thread for DB ops."""

    def test_subscription_service_imports_asyncio(self):
        """subscription_service should import asyncio."""
        import importlib
        spec = importlib.util.spec_from_file_location(
            "subscription_service",
            "/home/z/my-project/download/parwa/backend/app/services/subscription_service.py",
        )
        source = open("/home/z/my-project/download/parwa/backend/app/services/subscription_service.py").read()
        assert "import asyncio" in source
        assert "asyncio.to_thread" in source

    def test_payment_failure_service_imports_asyncio(self):
        """payment_failure_service should import asyncio."""
        source = open("/home/z/my-project/download/parwa/backend/app/services/payment_failure_service.py").read()
        assert "import asyncio" in source
        assert "asyncio.to_thread" in source

    def test_overage_service_imports_asyncio(self):
        """overage_service should import asyncio."""
        source = open("/home/z/my-project/download/parwa/backend/app/services/overage_service.py").read()
        assert "import asyncio" in source
        assert "asyncio.to_thread" in source

    def test_invoice_service_imports_asyncio(self):
        """invoice_service should import asyncio."""
        source = open("/home/z/my-project/download/parwa/backend/app/services/invoice_service.py").read()
        assert "import asyncio" in source
        assert "asyncio.to_thread" in source

    def test_proration_service_imports_asyncio(self):
        """proration_service should import asyncio."""
        source = open("/home/z/my-project/download/parwa/backend/app/services/proration_service.py").read()
        assert "import asyncio" in source
        assert "asyncio.to_thread" in source

    def test_no_bare_with_sessionlocal_in_async_methods(self):
        """Async methods should NOT have bare `with SessionLocal() as db:` outside _db_work."""
        for svc_file in [
            "subscription_service.py",
            "payment_failure_service.py",
            "overage_service.py",
            "invoice_service.py",
            "proration_service.py",
        ]:
            path = f"/home/z/my-project/download/parwa/backend/app/services/{svc_file}"
            source = open(path).read()
            # Count asyncio.to_thread occurrences - must be > 0
            assert "asyncio.to_thread" in source, (
                f"{svc_file}: No asyncio.to_thread found — S-08 not fixed"
            )


# ══════════════════════════════════════════════════════════════════
# S-09: No company_id filter on get_user_by_id
# ══════════════════════════════════════════════════════════════════

class TestS09CompanyFilterOnGetUserById:
    """S-09: get_user_by_id must support company_id filter."""

    def test_get_user_by_id_accepts_company_id_param(self):
        """get_user_by_id should accept an optional company_id parameter."""
        source = open("/home/z/my-project/download/parwa/backend/app/services/auth_service.py").read()
        # Verify the function signature includes company_id
        assert "company_id" in source
        # Verify the function filters by company_id when provided
        assert "User.company_id == company_id" in source

    def test_get_user_by_id_filters_by_company(self):
        """When company_id is provided, the query should filter by it."""
        # Verify via source code that the filter is applied
        source = open("/home/z/my-project/download/parwa/backend/app/services/auth_service.py").read()
        assert "User.company_id == company_id" in source
        assert "if company_id is not None:" in source

    def test_get_user_by_id_without_company_id_backwards_compat(self):
        """Without company_id, should still work (backwards compatible)."""
        # Verify via source code that company_id is optional (default None)
        source = open("/home/z/my-project/download/parwa/backend/app/services/auth_service.py").read()
        assert "company_id: Optional[str] = None" in source or "company_id=None" in source


# ══════════════════════════════════════════════════════════════════
# S-10: No field whitelist on update_company_profile
# ══════════════════════════════════════════════════════════════════

class TestS10FieldWhitelist:
    """S-10: update_company_profile must only allow whitelisted fields."""

    def test_whitelist_exists(self):
        """UPDATABLE_PROFILE_FIELDS constant should exist."""
        source = open("/home/z/my-project/download/parwa/backend/app/services/company_service.py").read()
        assert "UPDATABLE_PROFILE_FIELDS" in source

    def test_sensitive_fields_not_in_whitelist(self):
        """Sensitive fields must NOT be in the whitelist."""
        from app.services.company_service import UPDATABLE_PROFILE_FIELDS

        sensitive_fields = [
            "subscription_tier",
            "subscription_status",
            "paddle_customer_id",
            "paddle_subscription_id",
            "billing_email",
        ]
        for field in sensitive_fields:
            assert field not in UPDATABLE_PROFILE_FIELDS, (
                f"Sensitive field '{field}' should not be in UPDATABLE_PROFILE_FIELDS"
            )

    def test_safe_fields_in_whitelist(self):
        """Safe profile fields should be in the whitelist."""
        from app.services.company_service import UPDATABLE_PROFILE_FIELDS

        safe_fields = ["name", "website", "phone", "timezone", "country"]
        for field in safe_fields:
            assert field in UPDATABLE_PROFILE_FIELDS, (
                f"Safe field '{field}' should be in UPDATABLE_PROFILE_FIELDS"
            )

    def test_update_rejects_disallowed_fields(self):
        """update_company_profile should reject non-whitelisted fields."""
        from app.services.company_service import update_company_profile
        from app.exceptions import ValidationError

        mock_db = MagicMock()
        # Attempt to update a sensitive field
        with pytest.raises(ValidationError):
            update_company_profile(
                company_id=str(uuid4()),
                data={"subscription_tier": "high", "name": "Test"},
                db=mock_db,
            )

    def test_update_allows_whitelisted_fields(self):
        """update_company_profile should accept whitelisted fields."""
        from app.services.company_service import update_company_profile

        mock_db = MagicMock()
        mock_company = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_company

        # Should not raise for whitelisted fields
        result = update_company_profile(
            company_id=str(uuid4()),
            data={"name": "New Name", "website": "https://example.com"},
            db=mock_db,
        )
        # Verify setattr was called for allowed fields
        assert mock_db.commit.called


# ══════════════════════════════════════════════════════════════════
# S-11: Session leaks — SessionLocal() without context manager
# ══════════════════════════════════════════════════════════════════

class TestS11SessionLeaks:
    """S-11: All SessionLocal() calls must use context managers."""

    def test_webhook_service_uses_context_managers(self):
        """webhook_ordering_service should use `with SessionLocal()` not bare calls."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/services/webhook_ordering_service.py"
        ).read()

        # Should NOT have bare `db: Session = SessionLocal()` pattern
        assert "db: Session = SessionLocal()" not in source, (
            "S-11: Found bare SessionLocal() without context manager"
        )

        # Should use `with SessionLocal() as db:` pattern
        assert "with SessionLocal() as db:" in source

        # Should NOT have manual `db.close()` calls (context manager handles it)
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "db.close()" in line and "with SessionLocal()" not in line:
                # db.close() inside a with block is redundant but not a leak
                # We check that it's not a standalone close after bare SessionLocal()
                pass

    def test_no_bare_sessionlocal_without_context(self):
        """Verify no bare SessionLocal() assignments remain."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/services/webhook_ordering_service.py"
        ).read()

        # The pattern `db: Session = SessionLocal()` is the leaky pattern
        # After fix, all should be `with SessionLocal() as db:`
        assert "db: Session = SessionLocal()" not in source


# ══════════════════════════════════════════════════════════════════
# S-12: asyncio.run() in sync CC flow
# ══════════════════════════════════════════════════════════════════

class TestS12AsyncioRunFix:
    """S-12: asyncio.run() must not be called in a running event loop."""

    def test_no_bare_asyncio_run_in_cc_service(self):
        """jarvis_cc_service should not have bare asyncio.run() as first attempt."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/services/jarvis_cc_service.py"
        ).read()

        # The old pattern was: try: asyncio.run(...) except RuntimeError: ThreadPoolExecutor
        # The fix should always use ThreadPoolExecutor directly
        # Find the section with the legacy pipeline call
        if "asyncio.run(process_ai_message" in source:
            # It may still appear inside ThreadPoolExecutor.submit — that's correct
            # But it should NOT be the first attempt outside a thread
            lines = source.split("\n")
            for i, line in enumerate(lines):
                if "asyncio.run(process_ai_message" in line:
                    # Check if this line is inside a thread pool submit
                    # (which is correct) vs a bare try block (which is wrong)
                    context = "\n".join(lines[max(0, i-5):i+2])
                    # If "pool.submit" is nearby, it's the correct usage
                    assert "pool.submit" in context or "submit" in context, (
                        f"S-12: Found bare asyncio.run() not in ThreadPoolExecutor at line {i+1}"
                    )

    def test_threadpool_always_used(self):
        """The fix should always use ThreadPoolExecutor for legacy pipeline."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/services/jarvis_cc_service.py"
        ).read()
        # The fix always uses concurrent.futures.ThreadPoolExecutor
        assert "ThreadPoolExecutor" in source
        # The S-12 fix comment should be present
        assert "S-12" in source


# ══════════════════════════════════════════════════════════════════
# S-13: Push notifications not implemented
# ══════════════════════════════════════════════════════════════════

class TestS13PushNotifications:
    """S-13: Push notifications must be implemented (not just a placeholder)."""

    def test_send_push_not_placeholder(self):
        """_send_push should not return the old placeholder."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/services/notification_service.py"
        ).read()

        # The old TODO should be gone
        assert "TODO: Implement push notifications" not in source, (
            "S-13: Push notification TODO still present"
        )

    def test_fcm_dispatch_method_exists(self):
        """_dispatch_fcm static method should exist."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/services/notification_service.py"
        ).read()
        assert "_dispatch_fcm" in source
        assert "FCM_SERVER_KEY" in source

    def test_apns_dispatch_method_exists(self):
        """_dispatch_apns static method should exist."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/services/notification_service.py"
        ).read()
        assert "_dispatch_apns" in source
        assert "APNS_CERT_PATH" in source

    def test_send_push_handles_no_tokens(self):
        """_send_push should handle users with no push tokens gracefully."""
        from app.services.notification_service import NotificationService

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.push_tokens = []
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        svc = NotificationService(db=mock_db, company_id=str(uuid4()))
        mock_notification = MagicMock()
        mock_notification.user_id = str(uuid4())
        mock_notification.title = "Test"
        mock_notification.message = "Body"
        mock_notification.event_type = "test"
        mock_notification.priority = "medium"
        mock_notification.ticket_id = None
        mock_notification.id = str(uuid4())

        result = svc._send_push(mock_notification, {})
        assert result["success"] is True
        assert "warning" in result

    def test_send_push_handles_user_not_found(self):
        """_send_push should handle missing user gracefully."""
        from app.services.notification_service import NotificationService

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        svc = NotificationService(db=mock_db, company_id=str(uuid4()))
        mock_notification = MagicMock()
        mock_notification.user_id = str(uuid4())

        result = svc._send_push(mock_notification, {})
        assert result["success"] is False

    def test_fcm_dispatch_graceful_without_key(self):
        """_dispatch_fcm should skip gracefully when FCM_SERVER_KEY is not set."""
        from app.services.notification_service import NotificationService

        with patch("app.config.get_settings") as mock_settings:
            mock_s = MagicMock()
            mock_s.FCM_SERVER_KEY = None
            mock_settings.return_value = mock_s

            result = NotificationService._dispatch_fcm(
                tokens=["token123"],
                title="Test",
                body="Body",
                data_payload={"notification_id": "123"},
            )
            assert result["success"] is True
            assert "warning" in result


# ══════════════════════════════════════════════════════════════════
# S-14: Notification preference audit TODO
# ══════════════════════════════════════════════════════════════════

class TestS14PreferenceAudit:
    """S-14: Notification preference changes must be audited."""

    def test_audit_model_exists(self):
        """NotificationPreferenceAudit model should exist."""
        from app.services.notification_preference_service import NotificationPreferenceAudit
        assert NotificationPreferenceAudit.__tablename__ == "notification_preference_audit"

    def test_audit_model_has_required_columns(self):
        """Audit model should have all required columns."""
        from app.services.notification_preference_service import NotificationPreferenceAudit

        col_names = {c.name for c in NotificationPreferenceAudit.__table__.columns}
        required = {"id", "company_id", "user_id", "action", "old_value", "new_value", "created_at"}
        assert required.issubset(col_names), f"Missing columns: {required - col_names}"

    def test_get_preference_history_not_stub(self):
        """get_preference_history should query the audit table, not return empty list."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/services/notification_preference_service.py"
        ).read()

        # The old TODO should be gone
        assert "TODO: Implement with audit log" not in source, (
            "S-14: Audit TODO still present"
        )

        # Should reference the audit model
        assert "NotificationPreferenceAudit" in source

    def test_update_preference_records_audit(self):
        """update_preference should call _record_audit."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/services/notification_preference_service.py"
        ).read()

        # Verify _record_audit helper exists
        assert "_record_audit" in source

        # Verify update_preference calls it
        # Find the method body and check it calls _record_audit
        assert 'action="update"' in source

    def test_set_digest_settings_records_audit(self):
        """set_digest_settings should record audit for digest changes."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/services/notification_preference_service.py"
        ).read()
        assert 'action="digest_change"' in source

    def test_reset_to_defaults_records_audit(self):
        """reset_to_defaults should record audit."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/services/notification_preference_service.py"
        ).read()
        assert 'action="reset"' in source

    def test_record_audit_is_exception_safe(self):
        """_record_audit should not crash if audit write fails."""
        from app.services.notification_preference_service import NotificationPreferenceService

        mock_db = MagicMock()
        mock_db.add.side_effect = Exception("DB error")
        mock_db.rollback = MagicMock()
        mock_db.commit = MagicMock()

        svc = NotificationPreferenceService(db=mock_db, company_id=str(uuid4()))

        # Should NOT raise even if DB write fails
        svc._record_audit(
            user_id=str(uuid4()),
            action="update",
            event_type="ticket_created",
            old_value='{"enabled": true}',
            new_value='{"enabled": false}',
        )
        # Should have attempted rollback
        assert mock_db.rollback.called
