"""Legacy plaintext and corrupt ciphertext must fail closed without raising."""
from cryptography.fernet import Fernet

from shared.utils import token_encryption


def test_decrypt_plaintext_returns_none_without_logging_type_error(monkeypatch):
    fernet = Fernet(Fernet.generate_key())
    monkeypatch.setattr(token_encryption, "get_fernet", lambda: fernet)

    assert token_encryption.decrypt_token("legacy-plaintext-token") is None


def test_decrypt_valid_fernet_token_still_succeeds(monkeypatch):
    fernet = Fernet(Fernet.generate_key())
    monkeypatch.setattr(token_encryption, "get_fernet", lambda: fernet)
    ciphertext = fernet.encrypt(b"provider-access-token").decode("utf-8")

    assert token_encryption.decrypt_token(ciphertext) == "provider-access-token"
