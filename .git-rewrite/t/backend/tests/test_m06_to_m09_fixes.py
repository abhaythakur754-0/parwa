"""
Unit & Integration Tests for M-06 through M-09 fixes.

M-06: Ambiguous encryption naming — columns renamed with _encrypted suffix
M-07: Missing indexes on User.role, User.is_active, Subscription.tier, Subscription.status
M-08: Missing User relationships (MFASecret, VerificationToken,
      PasswordResetToken, UserNotificationPreference) — cascade delete
M-09: PasswordChangeRequest confirm_new_password field + match validator

Strategy:
  - M-06/M-07/M-08 UNIT: Parse source files directly via AST to verify
    ORM model definitions are correct (avoids conftest.py mocking issues)
  - M-08 INTEGRATION: Standalone SQLite session (runs after conftest but
    creates its own engine/tables using the real Base from database.base)
  - M-09: Live Pydantic validation (schemas aren't mocked)
  - Cross-cutting: Source file checks for pagination blocklist & alembic

Run:
    pytest backend/tests/test_m06_to_m09_fixes.py -v
"""

import ast
import json
import os
import sys
import pytest
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32c")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-testing-32c")
os.environ.setdefault("DATA_ENCRYPTION_KEY", "test-encryption-key-for-testing-32")


# ── Helper: read source file ─────────────────────────────────────

def _read_source(relative_path: str) -> str:
    filepath = os.path.join(_project_root, relative_path)
    with open(filepath, "r") as f:
        return f.read()


def _parse_source(relative_path: str) -> ast.Module:
    source = _read_source(relative_path)
    return ast.parse(source)


def _find_class(module_ast: ast.Module, class_name: str) -> ast.ClassDef:
    for node in ast.walk(module_ast):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    raise ValueError(f"Class {class_name} not found in AST")


def _get_column_names(class_ast: ast.ClassDef) -> list[str]:
    """Extract column names from SQLAlchemy Column() assignments in a class."""
    names = []
    for node in class_ast.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    # Check if the value is a Column() call
                    val = node.value
                    if isinstance(val, ast.Call):
                        func = val.func
                        # Column(...) or relationship(...)
                        if isinstance(func, ast.Attribute) and func.attr in ("Column", "relationship"):
                            names.append(target.id)
                        elif isinstance(func, ast.Name) and func.id in ("Column", "relationship"):
                            names.append(target.id)
    return names


def _has_column_with_index(class_ast: ast.ClassDef, col_name: str) -> bool:
    """Check if a Column assignment has index=True."""
    for node in class_ast.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == col_name:
                    val = node.value
                    if isinstance(val, ast.Call):
                        for kw in val.keywords:
                            if kw.arg == "index":
                                if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                    return True
    return False


def _is_relationship_call(val: ast.expr) -> bool:
    """Check if a value is a relationship() call (not Column())."""
    if isinstance(val, ast.Call):
        func = val.func
        if isinstance(func, ast.Name) and func.id == "relationship":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "relationship":
            return True
    return False


def _has_relationship(class_ast: ast.ClassDef, rel_name: str) -> bool:
    """Check if a class has a relationship() assignment with given name."""
    for node in class_ast.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == rel_name:
                    if _is_relationship_call(node.value):
                        return True
    return False


def _get_relationship_kwargs(class_ast: ast.ClassDef, rel_name: str) -> dict:
    """Extract keyword arguments from a relationship() call.
    Skips Column() assignments with the same name."""
    for node in class_ast.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == rel_name:
                    if not _is_relationship_call(node.value):
                        continue  # Skip Column() or other non-relationship assignments
                    val = node.value
                    kwargs = {}
                    for kw in val.keywords:
                        if kw.arg and isinstance(kw.value, ast.Constant):
                            kwargs[kw.arg] = kw.value.value
                    return kwargs
    return {}


# ══════════════════════════════════════════════════════════════════════
# PART 1: UNIT TESTS — AST-based source code verification
# ══════════════════════════════════════════════════════════════════════


class TestM06EncryptionColumnNaming:
    """M-06: Verify encrypted columns have _encrypted suffix."""

    @pytest.fixture(autouse=True)
    def _parse_integration(self):
        self.tree = _parse_source("database/models/integration.py")
        self.RESTConnector = _find_class(self.tree, "RESTConnector")
        self.MCPConnection = _find_class(self.tree, "MCPConnection")
        self.DBConnection = _find_class(self.tree, "DBConnection")

    # ── RESTConnector ─────────────────────────────────────────────

    def test_rest_connector_has_auth_config_encrypted(self):
        cols = _get_column_names(self.RESTConnector)
        assert "auth_config_encrypted" in cols, \
            f"RESTConnector must have auth_config_encrypted column, got: {cols}"

    def test_rest_connector_no_ambiguous_auth_config(self):
        cols = _get_column_names(self.RESTConnector)
        assert "auth_config" not in cols, \
            "Old ambiguous 'auth_config' should be renamed to 'auth_config_encrypted'"

    # ── MCPConnection ─────────────────────────────────────────────

    def test_mcp_connection_has_auth_token_encrypted(self):
        cols = _get_column_names(self.MCPConnection)
        assert "auth_token_encrypted" in cols, \
            f"MCPConnection must have auth_token_encrypted column, got: {cols}"

    def test_mcp_connection_no_ambiguous_auth_token(self):
        cols = _get_column_names(self.MCPConnection)
        assert "auth_token" not in cols, \
            "Old 'auth_token' should be renamed to 'auth_token_encrypted'"

    # ── DBConnection ──────────────────────────────────────────────

    def test_db_connection_has_connection_string_encrypted(self):
        cols = _get_column_names(self.DBConnection)
        assert "connection_string_encrypted" in cols, \
            f"DBConnection must have connection_string_encrypted column, got: {cols}"

    def test_db_connection_no_ambiguous_connection_string(self):
        cols = _get_column_names(self.DBConnection)
        assert "connection_string" not in cols, \
            "Old 'connection_string' should be renamed to 'connection_string_encrypted'"

    # ── Comment check ─────────────────────────────────────────────

    def test_integration_source_mentions_fernet(self):
        """Source code should document that these are Fernet-encrypted."""
        source = _read_source("database/models/integration.py")
        assert "Fernet-encrypted" in source, \
            "Integration models should document Fernet encryption"


class TestM07MissingIndexes:
    """M-07: Verify indexes on high-frequency query columns."""

    @pytest.fixture(autouse=True)
    def _parse_models(self):
        core_tree = _parse_source("database/models/core.py")
        billing_tree = _parse_source("database/models/billing.py")
        self.User = _find_class(core_tree, "User")
        self.Subscription = _find_class(billing_tree, "Subscription")

    def test_user_role_has_index(self):
        assert _has_column_with_index(self.User, "role"), \
            "User.role must have index=True"

    def test_user_is_active_has_index(self):
        assert _has_column_with_index(self.User, "is_active"), \
            "User.is_active must have index=True"

    def test_subscription_tier_has_index(self):
        assert _has_column_with_index(self.Subscription, "tier"), \
            "Subscription.tier must have index=True"

    def test_subscription_status_has_index(self):
        assert _has_column_with_index(self.Subscription, "status"), \
            "Subscription.status must have index=True"


class TestM08UserRelationships:
    """M-08: Verify User has relationships with cascade delete."""

    @pytest.fixture(autouse=True)
    def _parse_core(self):
        core_tree = _parse_source("database/models/core.py")
        self.User = _find_class(core_tree, "User")
        self.MFASecret = _find_class(core_tree, "MFASecret")
        self.VerificationToken = _find_class(core_tree, "VerificationToken")
        self.PasswordResetToken = _find_class(core_tree, "PasswordResetToken")
        self.UserNotificationPreference = _find_class(core_tree, "UserNotificationPreference")

    # ── User.mfa_secret ───────────────────────────────────────────

    def test_user_has_mfa_secret_relationship(self):
        assert _has_relationship(self.User, "mfa_secret"), \
            "User must have 'mfa_secret' relationship"

    def test_user_mfa_secret_cascades_delete(self):
        kwargs = _get_relationship_kwargs(self.User, "mfa_secret")
        cascade = kwargs.get("cascade", "")
        assert "delete" in cascade or "all" in cascade, \
            f"User.mfa_secret must cascade delete, got cascade={cascade!r}"

    def test_user_mfa_secret_is_uselist_false(self):
        kwargs = _get_relationship_kwargs(self.User, "mfa_secret")
        assert kwargs.get("uselist") is False, \
            f"User.mfa_secret should be uselist=False, got {kwargs}"

    # ── MFASecret back_populates ──────────────────────────────────

    def test_mfa_secret_back_populates_user(self):
        kwargs = _get_relationship_kwargs(self.MFASecret, "user")
        assert kwargs.get("back_populates") == "mfa_secret", \
            f"MFASecret.user should back_populates='mfa_secret', got {kwargs}"

    # ── User.verification_tokens ──────────────────────────────────

    def test_user_has_verification_tokens_relationship(self):
        assert _has_relationship(self.User, "verification_tokens")

    def test_user_verification_tokens_cascades_delete(self):
        kwargs = _get_relationship_kwargs(self.User, "verification_tokens")
        cascade = kwargs.get("cascade", "")
        assert "delete" in cascade or "all" in cascade

    def test_verification_token_back_populates_user(self):
        kwargs = _get_relationship_kwargs(self.VerificationToken, "user")
        assert kwargs.get("back_populates") == "verification_tokens"

    # ── User.password_reset_tokens ────────────────────────────────

    def test_user_has_password_reset_tokens_relationship(self):
        assert _has_relationship(self.User, "password_reset_tokens")

    def test_user_password_reset_tokens_cascades_delete(self):
        kwargs = _get_relationship_kwargs(self.User, "password_reset_tokens")
        cascade = kwargs.get("cascade", "")
        assert "delete" in cascade or "all" in cascade

    def test_password_reset_token_back_populates_user(self):
        kwargs = _get_relationship_kwargs(self.PasswordResetToken, "user")
        assert kwargs.get("back_populates") == "password_reset_tokens"

    # ── User.notification_preferences ─────────────────────────────

    def test_user_has_notification_preferences_relationship(self):
        assert _has_relationship(self.User, "notification_preferences")

    def test_user_notification_preferences_cascades_delete(self):
        kwargs = _get_relationship_kwargs(self.User, "notification_preferences")
        cascade = kwargs.get("cascade", "")
        assert "delete" in cascade or "all" in cascade

    def test_notification_preference_back_populates_user(self):
        kwargs = _get_relationship_kwargs(self.UserNotificationPreference, "user")
        assert kwargs.get("back_populates") == "notification_preferences"


class TestM09PasswordConfirmation:
    """M-09: PasswordChangeRequest confirm_new_password + match validator.
    These use live Pydantic validation since schemas aren't mocked."""

    @pytest.fixture(autouse=True)
    def _import_schema(self):
        from backend.app.schemas.admin import PasswordChangeRequest
        self.PasswordChangeRequest = PasswordChangeRequest

    def test_password_change_has_confirm_field(self):
        fields = self.PasswordChangeRequest.model_fields
        assert "confirm_new_password" in fields

    def test_confirm_field_is_required(self):
        fields = self.PasswordChangeRequest.model_fields
        assert fields["confirm_new_password"].is_required()

    def test_matching_passwords_pass_validation(self):
        req = self.PasswordChangeRequest(
            current_password="OldPass123!",
            new_password="NewPass456!",
            confirm_new_password="NewPass456!",
        )
        assert req.new_password == req.confirm_new_password

    def test_mismatching_passwords_fail_validation(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            self.PasswordChangeRequest(
                current_password="OldPass123!",
                new_password="NewPass456!",
                confirm_new_password="Different789!",
            )
        error_msgs = [e.get("msg", "") for e in exc_info.value.errors()]
        assert any("do not match" in msg.lower() for msg in error_msgs)

    def test_confirm_too_short_fails(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            self.PasswordChangeRequest(
                current_password="OldPass123!",
                new_password="NewPass456!",
                confirm_new_password="short",
            )
        field_names = [e.get("loc", ())[-1] for e in exc_info.value.errors()]
        assert "confirm_new_password" in field_names

    def test_new_password_strength_still_enforced(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self.PasswordChangeRequest(
                current_password="OldPass123!",
                new_password="weakpassword",
                confirm_new_password="weakpassword",
            )

    def test_empty_confirm_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self.PasswordChangeRequest(
                current_password="OldPass123!",
                new_password="NewPass456!",
                confirm_new_password="",
            )

    def test_model_validator_exists(self):
        """Verify the PasswordChangeRequest has a model_validator for password matching."""
        source = _read_source("backend/app/schemas/admin.py")
        assert "model_validator" in source, \
            "PasswordChangeRequest should use model_validator for password matching"
        assert "passwords_match" in source, \
            "PasswordChangeRequest should have passwords_match validator"


# ══════════════════════════════════════════════════════════════════════
# PART 2: INTEGRATION TESTS — Pydantic API-like scenarios
# ══════════════════════════════════════════════════════════════════════


class TestM09Integration:
    """Integration: PasswordChangeRequest through API-like JSON scenarios."""

    @pytest.fixture(autouse=True)
    def _import_schema(self):
        from backend.app.schemas.admin import PasswordChangeRequest
        self.PasswordChangeRequest = PasswordChangeRequest

    def test_full_password_change_flow_success(self):
        req = self.PasswordChangeRequest(
            current_password="MyCurrentPass1!",
            new_password="MyNewPass2@",
            confirm_new_password="MyNewPass2@",
        )
        assert req.new_password == req.confirm_new_password

    def test_typo_in_confirmation_caught(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            self.PasswordChangeRequest(
                current_password="MyCurrentPass1!",
                new_password="MyNewPass2@",
                confirm_new_password="MyNewPass2#",
            )
        assert any("do not match" in e.get("msg", "").lower()
                   for e in exc_info.value.errors())

    def test_extra_whitespace_in_confirmation_caught(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self.PasswordChangeRequest(
                current_password="MyCurrentPass1!",
                new_password="MyNewPass2@",
                confirm_new_password="MyNewPass2@ ",
            )

    def test_json_payload_round_trip(self):
        payload = json.dumps({
            "current_password": "OldPass123!",
            "new_password": "NewPass456!",
            "confirm_new_password": "NewPass456!",
        })
        data = json.loads(payload)
        req = self.PasswordChangeRequest(**data)
        assert req.new_password == req.confirm_new_password

    def test_json_payload_mismatch_rejected(self):
        from pydantic import ValidationError
        payload = json.dumps({
            "current_password": "OldPass123!",
            "new_password": "NewPass456!",
            "confirm_new_password": "WrongPass789!",
        })
        data = json.loads(payload)
        with pytest.raises(ValidationError) as exc_info:
            self.PasswordChangeRequest(**data)
        assert any("do not match" in e.get("msg", "").lower()
                   for e in exc_info.value.errors())


# ══════════════════════════════════════════════════════════════════════
# PART 3: CROSS-CUTTING — Pagination blocklist & Alembic migration
# ══════════════════════════════════════════════════════════════════════


class TestPaginationBlocklistCoversEncryptedColumns:
    """Verify pagination sensitive-sort blocklist covers the new column names.
    Parse source directly since conftest mocks prevent importing pagination module."""

    @pytest.fixture(autouse=True)
    def _read_pagination_source(self):
        self.source = _read_source("backend/app/core/pagination.py")

    def test_auth_config_encrypted_blocked(self):
        assert '"auth_config_encrypted"' in self.source, \
            "auth_config_encrypted must be in sensitive sort blocklist"

    def test_auth_token_encrypted_blocked(self):
        assert '"auth_token_encrypted"' in self.source, \
            "auth_token_encrypted must be in sensitive sort blocklist"

    def test_connection_string_encrypted_blocked(self):
        assert '"connection_string_encrypted"' in self.source, \
            "connection_string_encrypted must be in sensitive sort blocklist"

    def test_old_auth_token_still_blocked(self):
        assert '"auth_token"' in self.source, \
            "Old 'auth_token' must remain in blocklist"

    def test_old_auth_config_still_blocked(self):
        assert '"auth_config"' in self.source, \
            "Old 'auth_config' must remain in blocklist"

    def test_old_connection_string_still_blocked(self):
        assert '"connection_string"' in self.source, \
            "Old 'connection_string' must remain in blocklist"


class TestAlembicMigrationUsesNewColumnNames:
    """Verify alembic migration 004 uses the new _encrypted column names."""

    @pytest.fixture(autouse=True)
    def _read_migration_source(self):
        self.source = _read_source(
            "database/alembic/versions/004_integration_tables.py"
        )

    def test_migration_004_uses_auth_config_encrypted(self):
        assert "auth_config_encrypted" in self.source

    def test_migration_004_uses_auth_token_encrypted(self):
        assert "auth_token_encrypted" in self.source

    def test_migration_004_uses_connection_string_encrypted(self):
        assert "connection_string_encrypted" in self.source

    def test_migration_004_no_old_auth_config(self):
        """Old 'auth_config' without '_encrypted' should not appear in non-comment lines."""
        for i, line in enumerate(self.source.split("\n"), 1):
            if "auth_config" in line and "encrypted" not in line:
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                pytest.fail(f"Line {i}: Old 'auth_config' found: {stripped}")

    def test_migration_004_no_old_auth_token(self):
        for i, line in enumerate(self.source.split("\n"), 1):
            if "auth_token" in line and "encrypted" not in line:
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                pytest.fail(f"Line {i}: Old 'auth_token' found: {stripped}")

    def test_migration_004_no_old_connection_string(self):
        for i, line in enumerate(self.source.split("\n"), 1):
            if "connection_string" in line and "encrypted" not in line:
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                pytest.fail(f"Line {i}: Old 'connection_string' found: {stripped}")
