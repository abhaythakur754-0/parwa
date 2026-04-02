"""
Tests for security/api_keys.py

Tests API key generation, hashing, scope validation, rotation (BC-011).
BC-001: API keys associated with company_id.
"""

import hashlib
import time

import pytest

from security.api_keys import (
    APIKey,
    APIKeyScope,
    APIKeyStatus,
    SCOPE_HIERARCHY,
    create_api_key,
    generate_raw_key,
    hash_api_key,
    rotate_api_key,
    validate_scopes,
    verify_api_key,
)


class TestAPIKeyScope:
    """Tests for APIKeyScope enum."""

    def test_read_value(self):
        assert APIKeyScope.READ.value == "read"

    def test_write_value(self):
        assert APIKeyScope.WRITE.value == "write"

    def test_admin_value(self):
        assert APIKeyScope.ADMIN.value == "admin"

    def test_approval_value(self):
        assert APIKeyScope.APPROVAL.value == "approval"

    def test_scope_count(self):
        assert len(APIKeyScope) == 4


class TestScopeHierarchy:
    """Tests for scope hierarchy (BC-011: read can't write, etc.)."""

    def test_read_only_has_read(self):
        assert APIKeyScope.READ in SCOPE_HIERARCHY[APIKeyScope.READ]
        assert len(SCOPE_HIERARCHY[APIKeyScope.READ]) == 1

    def test_write_includes_read(self):
        assert APIKeyScope.READ in SCOPE_HIERARCHY[APIKeyScope.WRITE]
        assert APIKeyScope.WRITE in SCOPE_HIERARCHY[APIKeyScope.WRITE]

    def test_admin_includes_all(self):
        admin_scopes = SCOPE_HIERARCHY[APIKeyScope.ADMIN]
        assert APIKeyScope.READ in admin_scopes
        assert APIKeyScope.WRITE in admin_scopes
        assert APIKeyScope.ADMIN in admin_scopes

    def test_approval_is_separate(self):
        """APPROVAL scope is not in READ/WRITE/ADMIN hierarchy."""
        approval_scopes = SCOPE_HIERARCHY[APIKeyScope.APPROVAL]
        assert APIKeyScope.APPROVAL in approval_scopes
        assert APIKeyScope.READ not in approval_scopes
        assert APIKeyScope.WRITE not in approval_scopes


class TestGenerateRawKey:
    """Tests for API key generation (BC-011: secure random)."""

    def test_returns_string(self):
        result = generate_raw_key()
        assert isinstance(result, str)

    def test_has_pk_prefix(self):
        result = generate_raw_key()
        assert result.startswith("pk_")

    def test_reasonable_length(self):
        result = generate_raw_key()
        assert len(result) >= 40

    def test_unique_keys(self):
        keys = {generate_raw_key() for _ in range(100)}
        assert len(keys) == 100

    def test_no_two_keys_equal(self):
        k1 = generate_raw_key()
        k2 = generate_raw_key()
        assert k1 != k2


class TestHashAPIKey:
    """Tests for API key hashing."""

    def test_returns_string(self):
        result = hash_api_key("test-key")
        assert isinstance(result, str)

    def test_sha256_length(self):
        result = hash_api_key("test-key")
        assert len(result) == 64  # SHA-256 hex = 64 chars

    def test_same_key_same_hash(self):
        h1 = hash_api_key("same-key")
        h2 = hash_api_key("same-key")
        assert h1 == h2

    def test_different_keys_different_hashes(self):
        h1 = hash_api_key("key-1")
        h2 = hash_api_key("key-2")
        assert h1 != h2

    def test_hash_matches_manual_sha256(self):
        raw = "test-key-123"
        expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert hash_api_key(raw) == expected


class TestVerifyAPIKey:
    """Tests for API key verification (BC-011: constant-time compare)."""

    def test_correct_key(self):
        raw = generate_raw_key()
        key_hash = hash_api_key(raw)
        assert verify_api_key(raw, key_hash) is True

    def test_wrong_key(self):
        raw1 = generate_raw_key()
        raw2 = generate_raw_key()
        key_hash = hash_api_key(raw1)
        assert verify_api_key(raw2, key_hash) is False

    def test_empty_key(self):
        assert verify_api_key("", hash_api_key("test")) is False


class TestValidateScopes:
    """Tests for scope validation (BC-011: scope isolation)."""

    def test_read_granted_read_required(self):
        assert validate_scopes(["read"], "read") is True

    def test_write_granted_read_required(self):
        """WRITE includes READ."""
        assert validate_scopes(["write"], "read") is True

    def test_admin_granted_read_required(self):
        """ADMIN includes READ."""
        assert validate_scopes(["admin"], "read") is True

    def test_read_granted_write_required_fails(self):
        """READ does NOT include WRITE."""
        assert validate_scopes(["read"], "write") is False

    def test_admin_granted_write_required(self):
        """ADMIN includes WRITE."""
        assert validate_scopes(["admin"], "write") is True

    def test_read_granted_admin_required_fails(self):
        """READ does NOT include ADMIN."""
        assert validate_scopes(["read"], "admin") is False

    def test_write_granted_admin_required_fails(self):
        """WRITE does NOT include ADMIN."""
        assert validate_scopes(["write"], "admin") is False

    def test_approval_granted_approval_required(self):
        assert validate_scopes(["approval"], "approval") is True

    def test_read_granted_approval_required_fails(self):
        """READ does NOT include APPROVAL."""
        assert validate_scopes(["read"], "approval") is False

    def test_admin_granted_approval_required_fails(self):
        """ADMIN does NOT include APPROVAL (separate scope)."""
        assert validate_scopes(["admin"], "approval") is False

    def test_empty_scopes_fails(self):
        assert validate_scopes([], "read") is False

    def test_invalid_scope_required(self):
        assert validate_scopes(["read"], "nonexistent") is False

    def test_multi_scope_read_plus_approval(self):
        assert validate_scopes(["read", "approval"], "approval") is True
        assert validate_scopes(["read", "approval"], "read") is True


class TestCreateAPIKey:
    """Tests for API key creation."""

    def test_returns_tuple(self):
        result = create_api_key(company_id="comp-1", scopes=["read"])
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_raw_key_is_string(self):
        raw_key, _ = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        assert isinstance(raw_key, str)
        assert raw_key.startswith("pk_")

    def test_api_key_object(self):
        _, api_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        assert isinstance(api_key, APIKey)
        assert api_key.company_id == "comp-1"
        assert api_key.scopes == ["read"]

    def test_key_hash_matches_raw_key(self):
        raw_key, api_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        assert api_key.key_hash == hash_api_key(raw_key)

    def test_key_prefix_is_first_12_chars(self):
        raw_key, api_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        assert api_key.key_prefix == raw_key[:12]

    def test_company_id_set(self):
        """BC-001: API key has company_id."""
        _, api_key = create_api_key(
            company_id="comp-abc", scopes=["write"]
        )
        assert api_key.company_id == "comp-abc"

    def test_invalid_scope_raises(self):
        with pytest.raises(ValueError, match="Invalid scope"):
            create_api_key(
                company_id="comp-1", scopes=["nonexistent"]
            )

    def test_expiration_set(self):
        _, api_key = create_api_key(
            company_id="comp-1", scopes=["read"],
            expires_in_seconds=3600,
        )
        assert api_key.expires_at is not None
        assert api_key.expires_at > time.time()

    def test_no_expiration_default(self):
        _, api_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        assert api_key.expires_at is None

    def test_name_set(self):
        _, api_key = create_api_key(
            company_id="comp-1", scopes=["read"],
            name="My API Key",
        )
        assert api_key.name == "My API Key"

    def test_created_by_set(self):
        _, api_key = create_api_key(
            company_id="comp-1", scopes=["read"],
            created_by="user-123",
        )
        assert api_key.created_by == "user-123"

    def test_id_is_set(self):
        _, api_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        assert api_key.id is not None
        assert len(api_key.id) == 16  # 8 bytes hex


class TestAPIKey:
    """Tests for APIKey class methods."""

    def test_is_active_true(self):
        _, api_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        assert api_key.is_active() is True

    def test_is_active_false_when_revoked(self):
        _, api_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        api_key.status = APIKeyStatus.REVOKED.value
        assert api_key.is_active() is False

    def test_is_active_false_when_rotated(self):
        _, api_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        api_key.status = APIKeyStatus.ROTATED.value
        assert api_key.is_active() is False

    def test_is_active_false_when_expired(self):
        _, api_key = create_api_key(
            company_id="comp-1", scopes=["read"],
            expires_in_seconds=-1,  # Already expired
        )
        assert api_key.is_active() is False

    def test_has_scope_true(self):
        _, api_key = create_api_key(
            company_id="comp-1", scopes=["write"]
        )
        assert api_key.has_scope("read") is True  # write includes read

    def test_has_scope_false(self):
        _, api_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        assert api_key.has_scope("write") is False

    def test_has_scope_false_when_inactive(self):
        _, api_key = create_api_key(
            company_id="comp-1", scopes=["admin"]
        )
        api_key.status = APIKeyStatus.REVOKED.value
        assert api_key.has_scope("admin") is False

    def test_to_dict_no_raw_key(self):
        _, api_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        d = api_key.to_dict()
        # Never expose raw key or hash in to_dict
        assert "raw_key" not in d
        assert d["company_id"] == "comp-1"
        assert "key_prefix" in d
        assert "scopes" in d


class TestRotateAPIKey:
    """Tests for API key rotation (BC-011: immediate invalidation)."""

    def test_returns_tuple_of_3(self):
        _, old_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        result = rotate_api_key(old_key)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_old_key_marked_rotated(self):
        _, old_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        _, _, updated_old = rotate_api_key(old_key)
        assert updated_old.status == APIKeyStatus.ROTATED.value

    def test_old_key_rotated_at_set(self):
        before = time.time()
        _, old_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        _, _, updated_old = rotate_api_key(old_key)
        assert updated_old.rotated_at is not None
        assert updated_old.rotated_at >= before

    def test_new_key_is_active(self):
        _, old_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        _, new_key, _ = rotate_api_key(old_key)
        assert new_key.status == APIKeyStatus.ACTIVE.value

    def test_new_key_different_from_old(self):
        raw_old, old_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        raw_new, new_key, _ = rotate_api_key(old_key)
        assert raw_new != raw_old
        assert new_key.key_hash != old_key.key_hash

    def test_new_key_same_company_id(self):
        _, old_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        _, new_key, _ = rotate_api_key(old_key)
        assert new_key.company_id == old_key.company_id

    def test_new_key_same_scopes_default(self):
        _, old_key = create_api_key(
            company_id="comp-1", scopes=["read", "write"]
        )
        _, new_key, _ = rotate_api_key(old_key)
        assert set(new_key.scopes) == set(old_key.scopes)

    def test_new_key_custom_scopes(self):
        _, old_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        _, new_key, _ = rotate_api_key(
            old_key, new_scopes=["admin"]
        )
        assert new_key.scopes == ["admin"]

    def test_new_key_custom_name(self):
        _, old_key = create_api_key(
            company_id="comp-1", scopes=["read"],
            name="Old Name",
        )
        _, new_key, _ = rotate_api_key(old_key, name="New Name")
        assert new_key.name == "New Name"

    def test_old_key_no_longer_active(self):
        _, old_key = create_api_key(
            company_id="comp-1", scopes=["read"]
        )
        rotate_api_key(old_key)
        assert old_key.is_active() is False
