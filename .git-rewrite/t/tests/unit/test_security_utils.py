import hmac
import hashlib
import base64
import pytest
from security.kyc_aml import KYCCheck
from security.hmac_verification import verify_hmac

class TestKYCCheck:
    def test_validate_id_format_us_pass(self):
        assert KYCCheck.validate_id_format("US", "123-45-6789") is True

    def test_validate_id_format_us_fail(self):
        assert KYCCheck.validate_id_format("US", "123-456-789") is False
        assert KYCCheck.validate_id_format("US", "ABC-DE-FGHI") is False

    def test_validate_id_format_uk_pass(self):
        assert KYCCheck.validate_id_format("UK", "AB123456C") is True

    def test_validate_id_format_uk_fail(self):
        assert KYCCheck.validate_id_format("UK", "123456789") is False
        assert KYCCheck.validate_id_format("UK", "ABC12345D") is False

    def test_validate_id_format_invalid_country(self):
        with pytest.raises(ValueError) as exc:
            KYCCheck.validate_id_format("FR", "12345")
        assert "Country code 'FR' is not supported" in str(exc.value)

    def test_check_sanctions_list_safe(self):
        assert KYCCheck.check_sanctions_list("John Doe") is False
        assert KYCCheck.check_sanctions_list("Acme Corp") is False

    def test_check_sanctions_list_blocked(self):
        assert KYCCheck.check_sanctions_list("KNOWN_BAD_ACTOR") is True
        assert KYCCheck.check_sanctions_list("The SANCTIONED_CORP Group") is True


def test_verify_hmac_valid_hex():
    payload = b'{"event": "test"}'
    secret = "super-secret"
    signature = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    assert verify_hmac(payload, signature, secret) is True


def test_verify_hmac_valid_base64():
    payload = b'{"event": "test"}'
    secret = "super-secret"
    binary_hmac = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).digest()
    signature = base64.b64encode(binary_hmac).decode("utf-8")
    
    assert verify_hmac(payload, signature, secret) is True


def test_verify_hmac_invalid_signature():
    payload = b'{"event": "test"}'
    secret = "super-secret"
    signature = "invalid-signature"
    
    assert verify_hmac(payload, signature, secret) is False


def test_verify_hmac_tampered_payload():
    payload = b'{"event": "test"}'
    tampered_payload = b'{"event": "hacked"}'
    secret = "super-secret"
    signature = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    assert verify_hmac(tampered_payload, signature, secret) is False


def test_verify_hmac_empty_inputs():
    assert verify_hmac(b"", "", "secret") is False
    assert verify_hmac(b"payload", "sig", "") is False
