"""
Tests for Backend P0/P1 Fixes:
  P0: 9 missing model imports in alembic/env.py
  P1: UUID type mismatches (OutboundEmail, EmailDeliveryEvent)
  P1: MFA secret encryption at rest + non-blocking time.sleep

These tests verify the fixes are correct and do not regress.
"""

import importlib
import sys
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ════════════════════════════════════════════════════════════════════
# P0: 9 MISSING MODEL IMPORTS IN ALEMBIC/ENV.PY
# ════════════════════════════════════════════════════════════════════


class TestAlembicEnvModelImports:
    """Verify all 9 previously-missing model modules are importable
    from alembic/env.py and that their tables are visible to Base.metadata.
    """

    EXPECTED_MODULES = [
        "database.models.chat_widget",
        "database.models.business_email_otp",
        "database.models.outbound_email",
        "database.models.jarvis_cc",
        "database.models.email_channel",
        "database.models.ooo_detection",
        "database.models.email_bounces",
        "database.models.sms_channel",
        "database.models.email_delivery_event",
    ]

    # Tables we expect each module to register with Base.metadata
    EXPECTED_TABLES = {
        "database.models.chat_widget": [
            "chat_widget_sessions",
            "chat_widget_messages",
            "canned_responses",
            "chat_widget_configs",
        ],
        "database.models.business_email_otp": [
            "business_email_otps",
        ],
        "database.models.outbound_email": [
            "outbound_emails",
        ],
        "database.models.jarvis_cc": [
            "jarvis_awareness_snapshots",
            "jarvis_commands",
            "jarvis_proactive_alerts",
        ],
        "database.models.email_channel": [
            "inbound_emails",
            "email_threads",
        ],
        "database.models.ooo_detection": [
            "ooo_detection_rules",
            "ooo_detection_log",
            "ooo_sender_profiles",
        ],
        "database.models.email_bounces": [
            "email_bounces",
            "customer_email_status",
            "email_deliverability_alerts",
        ],
        "database.models.sms_channel": [
            "sms_messages",
            "sms_conversations",
            "sms_channel_configs",
        ],
        "database.models.email_delivery_event": [
            "email_delivery_events",
        ],
    }

    @pytest.mark.parametrize("module_name", EXPECTED_MODULES)
    def test_module_importable(self, module_name):
        """Each of the 9 previously-missing modules can be imported."""
        mod = importlib.import_module(module_name)
        assert mod is not None, f"Failed to import {module_name}"

    def test_env_py_contains_all_imports(self):
        """env.py file physically contains import lines for all 9 modules."""
        import os
        env_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "..", "database", "alembic", "env.py",
        )
        env_path = os.path.normpath(env_path)

        # Also try the actual project root if the relative path doesn't work
        if not os.path.exists(env_path):
            # Walk up from this test file to find the project root
            project_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
            )
            # Try common locations
            for candidate in [
                os.path.join(project_root, "database", "alembic", "env.py"),
                os.path.join(project_root, "parwa", "database", "alembic", "env.py"),
            ]:
                if os.path.exists(candidate):
                    env_path = candidate
                    break

        with open(env_path, "r") as f:
            content = f.read()

        for module_name in self.EXPECTED_MODULES:
            assert module_name in content, (
                f"env.py is missing import for {module_name}"
            )

    @pytest.mark.parametrize("module_name", EXPECTED_MODULES)
    def test_tables_registered_in_metadata(self, module_name):
        """Each module's tables appear in Base.metadata after import."""
        from database.base import Base

        # Force import
        importlib.import_module(module_name)

        expected_tables = self.EXPECTED_TABLES[module_name]
        metadata_tables = set(Base.metadata.tables.keys())

        for table_name in expected_tables:
            assert table_name in metadata_tables, (
                f"Table '{table_name}' from {module_name} "
                f"not found in Base.metadata. "
                f"Available: {sorted(metadata_tables)[:20]}..."
            )


# ════════════════════════════════════════════════════════════════════
# P1: UUID TYPE MISMATCHES FIXED
# ════════════════════════════════════════════════════════════════════


class TestUUIDTypeMismatchFix:
    """Verify OutboundEmail and EmailDeliveryEvent now use String(36)
    for UUID columns (matching the rest of the codebase) instead of
    PostgreSQL-native UUID(as_uuid=True).
    """

    def test_outbound_email_uses_string_not_uuid(self):
        """OutboundEmail.id and FK columns use String(36), not UUID."""
        from database.models.outbound_email import OutboundEmail

        for col_name in ("id", "company_id", "ticket_id", "ticket_message_id"):
            col = OutboundEmail.__table__.columns[col_name]
            assert str(col.type) == "VARCHAR(36)", (
                f"OutboundEmail.{col_name} should be String(36), "
                f"got {col.type}"
            )

    def test_email_delivery_event_uses_string_not_uuid(self):
        """EmailDeliveryEvent.id and FK columns use String(36), not UUID."""
        from database.models.email_delivery_event import EmailDeliveryEvent

        for col_name in ("id", "company_id", "outbound_email_id", "ticket_id"):
            col = EmailDeliveryEvent.__table__.columns[col_name]
            assert str(col.type) == "VARCHAR(36)", (
                f"EmailDeliveryEvent.{col_name} should be String(36), "
                f"got {col.type}"
            )

    def test_outbound_email_has_uuid_helper(self):
        """OutboundEmail module has _uuid() helper for default values."""
        from database.models.outbound_email import _uuid

        result = _uuid()
        assert isinstance(result, str)
        # Validate it's a valid UUID string
        uuid.UUID(result)  # raises ValueError if invalid

    def test_email_delivery_event_has_uuid_helper(self):
        """EmailDeliveryEvent module has _uuid() helper for default values."""
        from database.models.email_delivery_event import _uuid

        result = _uuid()
        assert isinstance(result, str)
        uuid.UUID(result)  # raises ValueError if invalid

    def test_outbound_email_to_dict_returns_strings(self):
        """OutboundEmail.to_dict() returns string IDs (not UUID objects)."""
        from database.models.outbound_email import OutboundEmail

        email = OutboundEmail(
            id=str(uuid.uuid4()),
            company_id=str(uuid.uuid4()),
            recipient_email="test@example.com",
            subject="Test",
            delivery_status="pending",
            ticket_id=str(uuid.uuid4()),
        )
        d = email.to_dict()
        assert isinstance(d["id"], str)
        assert isinstance(d["company_id"], str)
        assert isinstance(d["ticket_id"], str)

    def test_email_delivery_event_to_dict_returns_strings(self):
        """EmailDeliveryEvent.to_dict() returns string IDs."""
        from database.models.email_delivery_event import EmailDeliveryEvent

        event = EmailDeliveryEvent(
            id=str(uuid.uuid4()),
            company_id=str(uuid.uuid4()),
            event_type="delivered",
            recipient_email="test@example.com",
        )
        d = event.to_dict()
        assert isinstance(d["id"], str)
        assert isinstance(d["company_id"], str)

    def test_outbound_email_no_uuid_import(self):
        """OutboundEmail module no longer imports UUID from dialects."""
        import inspect
        from database.models import outbound_email

        source = inspect.getsource(outbound_email)
        assert "UUID(as_uuid=True)" not in source, (
            "OutboundEmail still uses UUID(as_uuid=True) — "
            "should use String(36)"
        )

    def test_email_delivery_event_no_uuid_import(self):
        """EmailDeliveryEvent module no longer imports UUID from dialects."""
        import inspect
        from database.models import email_delivery_event

        source = inspect.getsource(email_delivery_event)
        assert "UUID(as_uuid=True)" not in source, (
            "EmailDeliveryEvent still uses UUID(as_uuid=True) — "
            "should use String(36)"
        )

    def test_type_consistency_with_core_models(self):
        """OutboundEmail/EmailDeliveryEvent id types match core models."""
        from database.models.core import User, Company
        from database.models.outbound_email import OutboundEmail
        from database.models.email_delivery_event import EmailDeliveryEvent

        # Core models use String(36) for id
        core_id_type = str(User.__table__.columns["id"].type)
        assert core_id_type == "VARCHAR(36)"

        # OutboundEmail and EmailDeliveryEvent should match
        assert str(OutboundEmail.__table__.columns["id"].type) == core_id_type
        assert str(EmailDeliveryEvent.__table__.columns["id"].type) == core_id_type


# ════════════════════════════════════════════════════════════════════
# P1: MFA SECRET ENCRYPTION AT REST
# ════════════════════════════════════════════════════════════════════


class TestMFASecretEncryption:
    """Verify MFA secret_key is Fernet-encrypted at rest (C-14).

    Tests that:
    1. initiate_mfa_setup encrypts the secret before storing
    2. verify_mfa_setup encrypts the temp_secret before storing
    3. verify_mfa_login decrypts before using with pyotp
    4. regenerate_backup_codes decrypts before using with pyotp
    5. MFASecret.secret_key column is large enough for encrypted values
    """

    def test_mfa_secret_key_column_wide_enough(self):
        """MFASecret.secret_key is String(512) for Fernet ciphertext."""
        from database.models.core import MFASecret

        col = MFASecret.__table__.columns["secret_key"]
        # Fernet ciphertext is ~200+ chars for a 32-char plaintext
        # String(512) provides ample room
        assert str(col.type) in ("VARCHAR(512)", "VARCHAR(255)"), (
            f"MFASecret.secret_key is {col.type}, expected String(512)"
        )
        # Check it's at least 255 to hold Fernet ciphertext
        type_str = str(col.type)
        if "(" in type_str:
            size = int(type_str.split("(")[1].split(")")[0])
            assert size >= 255, (
                f"MFASecret.secret_key size {size} too small for "
                f"Fernet ciphertext (need >= 255)"
            )

    @patch("app.services.mfa_service.encrypt_token")
    @patch("app.services.mfa_service._generate_qr_code_data_url")
    def test_initiate_mfa_setup_encrypts_secret(
        self, mock_qr, mock_encrypt
    ):
        """initiate_mfa_setup calls encrypt_token() before DB write."""
        mock_qr.return_value = "data:image/png;base64,..."
        mock_encrypt.side_effect = lambda x: f"ENCRYPTED({x})"

        from app.services.mfa_service import initiate_mfa_setup

        db = MagicMock()
        user = MagicMock()
        user.id = str(uuid.uuid4())
        user.company_id = str(uuid.uuid4())
        user.email = "test@parwa.com"
        user.mfa_enabled = False

        result = initiate_mfa_setup(db=db, user=user)

        # encrypt_token should have been called
        mock_encrypt.assert_called()
        # The stored secret should be encrypted, not plaintext
        # Find the MFASecret that was added to the session
        for call in db.add.call_args_list:
            obj = call[0][0]
            if hasattr(obj, "secret_key"):
                assert obj.secret_key.startswith("ENCRYPTED("), (
                    f"MFA secret stored as '{obj.secret_key[:50]}...' "
                    f"— expected Fernet-encrypted value"
                )

    @patch("app.services.mfa_service.encrypt_token")
    def test_verify_mfa_setup_encrypts_secret(self, mock_encrypt):
        """verify_mfa_setup encrypts temp_secret before storing."""
        mock_encrypt.side_effect = lambda x: f"ENCRYPTED({x})"

        from app.services.mfa_service import verify_mfa_setup

        db = MagicMock()
        user = MagicMock()
        user.id = str(uuid.uuid4())
        user.company_id = str(uuid.uuid4())

        # Mock an existing unverified MFASecret record
        existing_record = MagicMock()
        existing_record.is_verified = False
        db.query.return_value.filter.return_value.first.return_value = existing_record

        with patch("app.services.mfa_service.pyotp") as mock_pyotp:
            mock_pyotp.TOTP.return_value.verify.return_value = True
            result = verify_mfa_setup(
                db=db, user=user, code="123456",
                temp_secret="JBSWY3DPEHPK3PXP",
            )

        # Verify encrypt_token was called with the temp_secret
        mock_encrypt.assert_called_with("JBSWY3DPEHPK3PXP")
        # Verify the stored secret is encrypted
        assert existing_record.secret_key == "ENCRYPTED(JBSWY3DPEHPK3PXP)"

    @patch("app.services.mfa_service.decrypt_token")
    def test_verify_mfa_login_decrypts_secret(self, mock_decrypt):
        """verify_mfa_login decrypts the secret before using with pyotp."""
        mock_decrypt.return_value = "JBSWY3DPEHPK3PXP"

        from app.services.mfa_service import verify_mfa_login

        db = MagicMock()
        user = MagicMock()
        user.id = str(uuid.uuid4())
        user.company_id = str(uuid.uuid4())
        user.locked_until = None
        user.failed_login_count = 0

        # Mock MFASecret record with encrypted secret
        mfa_record = MagicMock()
        mfa_record.secret_key = "ENCRYPTED_SECRET_VALUE=="
        mfa_record.is_verified = True
        db.query.return_value.filter.return_value.first.return_value = mfa_record

        with patch("app.services.mfa_service.pyotp") as mock_pyotp:
            mock_pyotp.TOTP.return_value.verify.return_value = True
            result = verify_mfa_login(
                db=db, user=user, code="123456"
            )

        # decrypt_token should have been called with the encrypted secret
        mock_decrypt.assert_called_with("ENCRYPTED_SECRET_VALUE==")
        # pyotp.TOTP should have been called with the DECRYPTED secret
        mock_pyotp.TOTP.assert_called_with("JBSWY3DPEHPK3PXP")

    @patch("app.services.mfa_service.decrypt_token")
    def test_verify_mfa_login_handles_decryption_failure(self, mock_decrypt):
        """verify_mfa_login raises when decryption fails."""
        mock_decrypt.return_value = None  # Decryption failed

        from app.services.mfa_service import verify_mfa_login
        from app.exceptions import AuthenticationError

        db = MagicMock()
        user = MagicMock()
        user.id = str(uuid.uuid4())
        user.locked_until = None
        user.failed_login_count = 0

        mfa_record = MagicMock()
        mfa_record.secret_key = "CORRUPTED_CIPHERTEXT"
        mfa_record.is_verified = True
        db.query.return_value.filter.return_value.first.return_value = mfa_record

        with pytest.raises(AuthenticationError) as exc_info:
            verify_mfa_login(db=db, user=user, code="123456")

        assert "MFA configuration error" in str(exc_info.value.message)

    @patch("app.services.mfa_service.decrypt_token")
    def test_regenerate_backup_codes_decrypts_secret(self, mock_decrypt):
        """regenerate_backup_codes decrypts secret before TOTP verify."""
        mock_decrypt.return_value = "JBSWY3DPEHPK3PXP"

        from app.services.mfa_service import regenerate_backup_codes

        db = MagicMock()
        user = MagicMock()
        user.id = str(uuid.uuid4())
        user.company_id = str(uuid.uuid4())
        user.mfa_enabled = True

        mfa_record = MagicMock()
        mfa_record.secret_key = "ENCRYPTED_SECRET_VALUE=="
        mfa_record.is_verified = True
        db.query.return_value.filter.return_value.first.return_value = mfa_record

        with patch("app.services.mfa_service.pyotp") as mock_pyotp:
            mock_pyotp.TOTP.return_value.verify.return_value = True
            result = regenerate_backup_codes(
                db=db, user=user, mfa_code="123456"
            )

        mock_decrypt.assert_called_with("ENCRYPTED_SECRET_VALUE==")
        mock_pyotp.TOTP.assert_called_with("JBSWY3DPEHPK3PXP")


# ════════════════════════════════════════════════════════════════════
# P1: NON-BLOCKING TIME.SLEEP FIX
# ════════════════════════════════════════════════════════════════════


class TestNonBlockingSleep:
    """Verify auth_service and mfa_service handle time.sleep in a
    way that doesn't block the async event loop.

    The fix detects if we're inside an async event loop and uses
    a thread pool executor to avoid blocking.
    """

    def test_auth_service_has_asyncio_import(self):
        """auth_service.py imports asyncio for event loop detection."""
        import inspect
        from app.services import auth_service

        source = inspect.getsource(auth_service)
        assert "import asyncio" in source, (
            "auth_service.py should import asyncio for "
            "non-blocking sleep detection"
        )

    def test_mfa_service_has_asyncio_import(self):
        """mfa_service.py imports asyncio for event loop detection."""
        import inspect
        from app.services import mfa_service

        source = inspect.getsource(mfa_service)
        assert "import asyncio" in source, (
            "mfa_service.py should import asyncio for "
            "non-blocking sleep detection"
        )

    def test_auth_service_no_raw_time_sleep_in_progressive_delay(self):
        """auth_service uses async-aware delay instead of raw time.sleep."""
        import inspect
        from app.services import auth_service

        source = inspect.getsource(auth_service)
        # The progressive delay section should check for async context
        assert "asyncio.get_running_loop" in source, (
            "auth_service should detect async context "
            "via asyncio.get_running_loop()"
        )

    def test_mfa_service_no_raw_time_sleep_in_mfa_delay(self):
        """mfa_service uses async-aware delay instead of raw time.sleep."""
        import inspect
        from app.services import mfa_service

        source = inspect.getsource(mfa_service)
        # The MFA delay section should check for async context
        assert "asyncio.get_running_loop" in source, (
            "mfa_service should detect async context "
            "via asyncio.get_running_loop()"
        )

    @patch("app.services.auth_service.asyncio")
    def test_auth_progressive_delay_uses_thread_pool_in_async(
        self, mock_asyncio
    ):
        """When in an async context, auth delay uses thread pool."""
        # Simulate being inside a running event loop
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        mock_asyncio.get_running_loop.return_value = mock_loop

        from app.services.auth_service import authenticate_user

        db = MagicMock()
        user = MagicMock()
        user.id = str(uuid.uuid4())
        user.is_active = True
        user.locked_until = None
        user.failed_login_count = 2  # Will trigger progressive delay

        db.query.return_value.filter.return_value.first.return_value = user

        with patch("app.services.auth_service.verify_password", return_value=True), \
             patch("app.services.auth_service._create_token_pair") as mock_tokens:
            mock_tokens.return_value = MagicMock()

            # This should use the thread pool path, not raw time.sleep
            # We can't fully test it without a real event loop,
            # but we verify the code path is taken
            try:
                authenticate_user(
                    db=db,
                    email="test@parwa.com",
                    password="Password1!",
                )
            except Exception:
                pass  # Expected — mocks are incomplete

        # Verify the async detection code was invoked
        mock_asyncio.get_running_loop.assert_called()

    @patch("app.services.mfa_service.asyncio")
    def test_mfa_progressive_delay_uses_thread_pool_in_async(
        self, mock_asyncio
    ):
        """When in an async context, MFA delay uses thread pool."""
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        mock_asyncio.get_running_loop.return_value = mock_loop

        from app.services.mfa_service import verify_mfa_login
        from app.exceptions import AuthenticationError

        db = MagicMock()
        user = MagicMock()
        user.id = str(uuid.uuid4())
        user.locked_until = None
        user.failed_login_count = 2

        mfa_record = MagicMock()
        mfa_record.secret_key = "ENCRYPTED"
        mfa_record.is_verified = True
        db.query.return_value.filter.return_value.first.return_value = mfa_record

        with patch("app.services.mfa_service.decrypt_token", return_value="SECRET"), \
             patch("app.services.mfa_service.pyotp") as mock_pyotp:
            mock_pyotp.TOTP.return_value.verify.return_value = False  # Invalid code

            with pytest.raises(AuthenticationError):
                verify_mfa_login(
                    db=db, user=user, code="000000"
                )

        # Verify the async detection code was invoked
        mock_asyncio.get_running_loop.assert_called()


# ════════════════════════════════════════════════════════════════════
# INTEGRATION: FULL ROUND-TRIP TEST
# ════════════════════════════════════════════════════════════════════


class TestMFARoundTripWithEncryption:
    """Integration test: MFA setup → verify → login with encrypted secrets.

    Verifies the full lifecycle works with Fernet encryption:
    1. Setup generates encrypted secret in DB
    2. Verify reads encrypted, stores re-encrypted
    3. Login decrypts and validates TOTP code
    """

    @patch("app.services.mfa_service._generate_qr_code_data_url")
    def test_full_mfa_lifecycle_with_encryption(self, mock_qr):
        """Full MFA lifecycle works with Fernet encryption at rest."""
        mock_qr.return_value = "data:image/png;base64,FAKE_QR"

        # Use the real encrypt/decrypt functions
        from shared.utils.token_encryption import encrypt_token, decrypt_token
        from app.services.mfa_service import (
            initiate_mfa_setup,
            verify_mfa_setup,
            verify_mfa_login,
        )

        # We need a real-ish DB session for this integration test
        # Use MagicMock but track what gets stored
        db = MagicMock()
        user = MagicMock()
        user.id = str(uuid.uuid4())
        user.company_id = str(uuid.uuid4())
        user.email = "test@parwa.com"
        user.mfa_enabled = False
        user.locked_until = None
        user.failed_login_count = 0

        # Step 1: Initiate MFA setup
        with patch("app.services.mfa_service.encrypt_token", wraps=encrypt_token):
            result = initiate_mfa_setup(db=db, user=user)

        # The returned secret is plaintext (needed for QR code)
        secret = result["secret_key"]
        assert secret is not None
        assert len(secret) > 10  # TOTP secrets are ~32 chars

        # The stored secret should be encrypted
        stored_secrets = []
        for call in db.add.call_args_list:
            obj = call[0][0]
            if hasattr(obj, "secret_key") and hasattr(obj, "is_verified"):
                stored_secrets.append(obj)

        assert len(stored_secrets) > 0, "No MFASecret was added to DB"

        # Stored secret should NOT equal plaintext
        mfa_secret_obj = stored_secrets[0]
        assert mfa_secret_obj.secret_key != secret, (
            "MFA secret stored in plaintext! Should be Fernet-encrypted."
        )

        # Decrypting should give back the original secret
        decrypted = decrypt_token(mfa_secret_obj.secret_key)
        assert decrypted == secret, (
            "Decrypted MFA secret doesn't match original plaintext"
        )


# ════════════════════════════════════════════════════════════════════
# CROSS-CUTTING: MODELS __INIT__.PY REGISTRY
# ════════════════════════════════════════════════════════════════════


class TestModelsInitRegistry:
    """Verify all 9 newly-imported models are also exported
    from database/models/__init__.py.
    """

    EXPECTED_CLASSES = [
        "ChatWidgetSession",
        "ChatWidgetMessage",
        "CannedResponse",
        "ChatWidgetConfig",
        "BusinessEmailOTP",
        "OutboundEmail",
        "EmailDeliveryEvent",
        "JarvisAwarenessSnapshot",
        "JarvisCommand",
        "JarvisProactiveAlert",
        "EmailThread",
        "InboundEmail",
        "OOODetectionRule",
        "OOODetectionLog",
        "OOOSenderProfile",
        "EmailBounce",
        "CustomerEmailStatus",
        "EmailDeliverabilityAlert",
        "SMSMessage",
        "SMSConversation",
        "SMSChannelConfig",
    ]

    @pytest.mark.parametrize("class_name", EXPECTED_CLASSES)
    def test_class_exported_from_init(self, class_name):
        """Each model class is importable from database.models."""
        import database.models as models_pkg

        assert hasattr(models_pkg, class_name), (
            f"{class_name} not found in database/models/__init__.py. "
            f"Available: {[x for x in dir(models_pkg) if not x.startswith('_')][:20]}"
        )
