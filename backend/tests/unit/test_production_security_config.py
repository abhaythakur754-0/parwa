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


def test_production_requires_authenticated_redis_url(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="REDIS_URL"):
        Settings.validate_production_redis_auth("redis://localhost:6379/0")


@pytest.mark.parametrize(
    "url",
    [
        "redis://default:secret@redis.example:6379/0",
        "redis://localhost:6379/0",
    ],
)
def test_production_accepts_redis_url_or_separate_password(monkeypatch, url):
    monkeypatch.setenv("ENVIRONMENT", "production")
    if "@" not in url:
        monkeypatch.setenv("REDIS_PASSWORD", "configured-secret")
    else:
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    assert Settings.validate_production_redis_auth(url) == url


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
