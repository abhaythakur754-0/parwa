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


def test_production_requires_mcp_auth_token(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="MCP_AUTH_TOKEN"):
        Settings.validate_mcp_auth_token("")


def test_production_rejects_placeholder_mcp_auth_token(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings.validate_mcp_auth_token("your_mcp_token_here")


def test_production_accepts_strong_mcp_auth_token(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    token = "mcp-" + ("x" * 40)
    assert Settings.validate_mcp_auth_token(token) == token


def test_development_allows_missing_mcp_auth_token_with_warning(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.warns(UserWarning, match="MCP_AUTH_TOKEN is empty"):
        assert Settings.validate_mcp_auth_token("") == ""


def test_production_requires_authenticated_redis_url(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="REDIS_URL"):
        Settings.validate_production_redis_auth("redis://localhost:6379/0")


@pytest.mark.parametrize(
    "url",
    [
        "redis://default:random-long-test-password@redis.example:6379/0",
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


def test_production_requires_application_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings.validate_secret_key(None)


def test_production_rejects_short_application_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="at least 32"):
        Settings.validate_secret_key("short")


def test_production_requires_refresh_token_pepper(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="REFRESH_TOKEN_PEPPER"):
        Settings.validate_refresh_token_pepper("")


def test_production_rejects_sample_encryption_key(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="DATA_ENCRYPTION_KEY"):
        Settings.validate_encryption_key("your_32_character_encryption_key_here")


def test_production_rejects_sample_jwt_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings.validate_jwt_key("your_jwt_secret_key_here")


def test_production_rejects_sample_redis_password(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="Redis credentials"):
        Settings.validate_production_redis_auth("redis://:your_redis_password@localhost:6379/0")


def test_production_rejects_sample_pricing_key(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="PRICING_SIGNING_KEY"):
        Settings.validate_pricing_signing_key("change-this-to-a-random-64-char-string")


def test_production_rejects_repository_default_redis_password(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="REDIS_URL"):
        Settings.validate_production_redis_auth("redis://:parwa_redis@localhost:6379/0")


def test_production_rejects_jwt_secret_shorter_than_32_characters(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="at least 32"):
        Settings.validate_jwt_key("a" * 31)


def test_production_accepts_32_character_jwt_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert Settings.validate_jwt_key("a" * 32) == "a" * 32


def test_production_rejects_placeholder_separate_redis_password_even_if_url_has_one(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REDIS_PASSWORD", "parwa_redis")
    with pytest.raises(ValueError, match="Redis credentials"):
        Settings.validate_production_redis_auth(
            "redis://default:real-url-password@redis.example:6379/0"
        )


def test_backend_cors_rejects_wildcard_with_credentials():
    with pytest.raises(ValueError, match="cannot contain"):
        Settings.validate_cors_origins("*")


def test_backend_cors_accepts_explicit_origins():
    value = "https://parwa.buzz,https://parwa.vercel.app"
    assert Settings.validate_cors_origins(value) == value


def test_mcp_server_requires_strong_production_token(monkeypatch):
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from mcp_server.config import MCPSettings

    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="at least 32 characters"):
        MCPSettings(MCP_AUTH_TOKEN="short")


def test_mcp_server_accepts_strong_production_token(monkeypatch):
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from mcp_server.config import MCPSettings

    monkeypatch.setenv("ENVIRONMENT", "production")
    token = "mcp-" + ("x" * 40)
    assert MCPSettings(MCP_AUTH_TOKEN=token).MCP_AUTH_TOKEN == token


def test_mcp_server_cors_rejects_explicit_wildcard():
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from mcp_server.config import MCPSettings

    with pytest.raises(ValueError, match="cannot contain"):
        MCPSettings(CORS_ORIGINS="*").cors_origin_list


def test_postgres_sslmode_prevents_explicit_downgrade():
    from database.base import _enforce_postgres_sslmode

    assert _enforce_postgres_sslmode("postgresql://db/app") == "postgresql://db/app?sslmode=require"
    assert _enforce_postgres_sslmode("postgresql://db/app?sslmode=disable").endswith("sslmode=require")
    assert _enforce_postgres_sslmode("postgresql://db/app?sslmode=prefer").endswith("sslmode=require")
    assert _enforce_postgres_sslmode("postgresql://db/app?sslmode=verify-full").endswith("sslmode=verify-full")
    assert _enforce_postgres_sslmode("sqlite:///./app.db") == "sqlite:///./app.db"
