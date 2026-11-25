import hashlib
import hmac
from types import SimpleNamespace

from app.services import business_email_otp_service as otp_service


def test_otp_hash_uses_persistent_encryption_secret(monkeypatch):
    monkeypatch.setattr(
        otp_service,
        "get_settings",
        lambda: SimpleNamespace(DATA_ENCRYPTION_KEY="stable-test-pepper"),
    )
    expected = hmac.new(
        b"stable-test-pepper",
        b"123456",
        hashlib.sha256,
    ).hexdigest()
    assert otp_service._hash_otp("123456") == expected
