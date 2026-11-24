import pytest

from app.config import Settings


def test_production_requires_persistent_encryption_key(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="DATA_ENCRYPTION_KEY"):
        Settings.validate_encryption_key(None)


def test_production_rejects_short_encryption_key(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="at least 32"):
        Settings.validate_encryption_key("too-short")


def test_production_requires_redis_password(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="REDIS_PASSWORD"):
        Settings.validate_redis_password("")


@pytest.mark.parametrize("value", [None, "", "dev-pricing-key", "short"])
def test_production_requires_strong_pricing_signing_key(monkeypatch, value):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="PRICING_SIGNING_KEY"):
        Settings.validate_pricing_signing_key(value)


def test_development_generates_encryption_key(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.warns(UserWarning, match="auto-generated for development"):
        key = Settings.validate_encryption_key(None)
    assert isinstance(key, str)
    assert len(key) >= 32


def test_development_allows_missing_pricing_key_with_warning(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.warns(UserWarning, match="pricing token signing is disabled"):
        assert Settings.validate_pricing_signing_key(None) is None
