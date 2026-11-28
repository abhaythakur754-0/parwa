"""Tests for the safe legacy OAuth token migration helper."""
import pytest

from scripts.migrate_oauth_credentials_encryption import migrate_oauth_token_value


def test_plaintext_oauth_token_is_encrypted():
    updated, migrated = migrate_oauth_token_value(
        "ya29.legacy-token",
        decrypt=lambda value: None,
        encrypt=lambda value: "fernet:" + value,
    )
    assert updated == "fernet:ya29.legacy-token"
    assert migrated is True


def test_existing_encrypted_oauth_token_is_not_reencrypted():
    updated, migrated = migrate_oauth_token_value(
        "gAAAAA-encrypted",
        decrypt=lambda value: "original-token",
        encrypt=lambda value: pytest.fail("must not re-encrypt"),
    )
    assert updated == "gAAAAA-encrypted"
    assert migrated is False


def test_unreadable_fernet_looking_token_aborts_migration():
    with pytest.raises(RuntimeError, match="cannot be decrypted"):
        migrate_oauth_token_value(
            "gAAAAA-corrupt",
            decrypt=lambda value: None,
            encrypt=lambda value: "double-encrypted",
        )


def test_empty_oauth_token_is_unchanged():
    updated, migrated = migrate_oauth_token_value(
        None,
        decrypt=lambda value: pytest.fail("empty values must not be decrypted"),
        encrypt=lambda value: pytest.fail("empty values must not be encrypted"),
    )
    assert updated is None
    assert migrated is False
