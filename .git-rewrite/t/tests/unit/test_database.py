"""
Unit tests for backend/app/database.py.
Focuses on the engine creation and session dependency behavior.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import sqlalchemy

# To test module-level code properly where get_settings() is called on import,
# we need to mock it before importing backend.app.database
@pytest.fixture(autouse=True)
def mock_settings():
    from shared.core_functions.config import Settings
    settings = Settings(
        ENVIRONMENT="development",
        SECRET_KEY="test_secret",
        POSTGRES_USER="test_user",
        POSTGRES_PASSWORD="test_password",
        POSTGRES_DB="test_db",
        DATABASE_URL="postgresql://test_user:test_password@localhost/test_db",
        REDIS_URL="redis://localhost:6379",
        JWT_SECRET_KEY="test_jwt_secret",
        OPENROUTER_API_KEY="test_key",
        OPENROUTER_BASE_URL="https://test.com",
        AI_LIGHT_MODEL="light",
        AI_MEDIUM_MODEL="medium",
        AI_HEAVY_MODEL="heavy",
        AI_FAILOVER_MODEL="failover",
        STRIPE_SECRET_KEY="sk_test_123",
        STRIPE_PUBLISHABLE_KEY="pk_test_123",
        STRIPE_WEBHOOK_SECRET="whsec_test",
        TWILIO_ACCOUNT_SID="AC123",
        TWILIO_AUTH_TOKEN="auth_token",
        TWILIO_PHONE_NUMBER="+1234567890",
        TWILIO_VOICE_WEBHOOK_URL="https://test.com/voice",
        SHOPIFY_API_KEY="shopify_key",
        SHOPIFY_API_SECRET="shopify_secret",
        SHOPIFY_WEBHOOK_SECRET="shopify_webhook_secret",
        MCP_SERVER_URL="https://test.com",
        MCP_AUTH_TOKEN="mcp_token",
        QDRANT_URL="https://test.com",
        QDRANT_API_KEY="qdrant_key",
        SENTRY_DSN="https://test.com",
        GRAFANA_API_KEY="grafana_key",
        SENDGRID_API_KEY="sendgrid_key",
        FROM_EMAIL="test@test.com",
        NEXT_PUBLIC_API_URL="https://test.com",
        NEXT_PUBLIC_STRIPE_KEY="pk_test_123",
        FEATURE_FLAGS_PATH="feature_flags",
        MODEL_REGISTRY_PATH="models",
        COLAB_WEBHOOK_URL="https://test.com",
        DATA_ENCRYPTION_KEY="12345678901234567890123456789012"
    )
    with patch("shared.core_functions.config.get_settings", return_value=settings):
        yield settings


def test_engine_created_with_asyncpg():
    """Verify that the engine forces the driver to asyncpg."""
    # Since database.py is evaluated on import and get_settings() runs, 
    # we just assert that engine was created (which uses the real .env or mock depending on import order)
    from backend.app.database import engine
    
    assert engine is not None
    assert "asyncpg" in engine.url.drivername


@pytest.mark.asyncio
async def test_get_db_session_yields_session_commits_and_closes():
    """Simulate a successful request using the get_db dependency."""
    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    
    with patch("backend.app.database.AsyncSessionLocal", mock_session_factory):
        from backend.app.database import get_db
        
        db_gen = get_db()
        
        # Get the yielded session
        session = await db_gen.__anext__()
        assert session is mock_session
        
        # Advance to completion
        with pytest.raises(StopAsyncIteration):
            await db_gen.__anext__()
            
        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()
        mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_session_rolls_back_on_exception():
    """Simulate a failed request where the route raises an exception."""
    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    
    with patch("backend.app.database.AsyncSessionLocal", mock_session_factory):
        from backend.app.database import get_db
        
        db_gen = get_db()
        session = await db_gen.__anext__()
        assert session is mock_session
        
        # Simulate exception raised in route handler
        try:
            await db_gen.athrow(ValueError("Simulated route error"))
        except ValueError:
            pass
            
        mock_session.commit.assert_not_awaited()
        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_db_connection_success():
    """Test the healthcheck function returns True when query succeeds."""
    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    
    with patch("backend.app.database.engine", mock_engine):
        from backend.app.database import check_db_connection
        result = await check_db_connection()
        
        assert result is True
        mock_conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_db_connection_failure():
    """Test the healthcheck function returns False and catches exception."""
    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.execute.side_effect = sqlalchemy.exc.OperationalError(
        "statement", "params", "orig"
    )
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    
    with patch("backend.app.database.engine", mock_engine):
        from backend.app.database import check_db_connection
        result = await check_db_connection()
        
        assert result is False
