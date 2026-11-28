"""Legacy plaintext and corrupt ciphertext must fail closed without raising."""
import importlib.util
from pathlib import Path

from cryptography.fernet import Fernet


def _load_token_encryption_module():
    backend_root = Path(__file__).resolve().parents[2]
    source = backend_root / "shared" / "utils" / "token_encryption.py"
    spec = importlib.util.spec_from_file_location("parwa_token_encryption_under_test", source)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_decrypt_plaintext_returns_none_without_logging_type_error(monkeypatch):
    token_encryption = _load_token_encryption_module()
    fernet = Fernet(Fernet.generate_key())
    monkeypatch.setattr(token_encryption, "get_fernet", lambda: fernet)

    assert token_encryption.decrypt_token("legacy-plaintext-token") is None


def test_decrypt_valid_fernet_token_still_succeeds(monkeypatch):
    token_encryption = _load_token_encryption_module()
    fernet = Fernet(Fernet.generate_key())
    monkeypatch.setattr(token_encryption, "get_fernet", lambda: fernet)
    ciphertext = fernet.encrypt(b"provider-access-token").decode("utf-8")

    assert token_encryption.decrypt_token(ciphertext) == "provider-access-token"
