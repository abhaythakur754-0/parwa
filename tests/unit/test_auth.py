"""
Unit tests for PARWA Authentication API.
Tests cover registration, login, token refresh, logout, and profile endpoints.
Uses FastAPI dependency injection for mocking database and services.
"""
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Set environment before imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-characters-for-testing!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "development")


# --- Create Test App with Mocked Dependencies ---

def create_test_app():
    """Create a FastAPI test app with mocked dependencies."""
    from fastapi import FastAPI
    
    app = FastAPI()
    
    # Mock the get_db dependency
    async def mock_get_db():
        return AsyncMock()
    
    # We need to patch before importing auth
    with patch("backend.app.database.engine", MagicMock()):
        with patch("backend.app.database.AsyncSessionLocal", MagicMock()):
            from backend.api.auth import router
            app.include_router(router)
    
    return app


# --- Fixtures ---

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_user_dict():
    """Create mock user data."""
    return {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "password_hash": "$2b$12$test_hash",
        "role": "viewer",
        "company_id": uuid.uuid4(),
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    # Create app with mocked database
    app = FastAPI()
    
    # Mock get_db dependency
    async def override_get_db():
        return AsyncMock()
    
    # Import and include router
    from backend.api.auth import router
    app.include_router(router)
    
    # Override the dependency
    from backend.app.dependencies import get_db
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


# --- Tests ---

class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    def test_register_short_password(self, client):
        """Test registration with short password returns 422."""
        response = client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "short",
                "company_id": str(uuid.uuid4()),
                "role": "viewer"
            }
        )
        assert response.status_code == 422

    def test_register_invalid_email(self, client):
        """Test registration with invalid email returns 422."""
        response = client.post(
            "/auth/register",
            json={
                "email": "not-an-email",
                "password": "securepassword123",
                "company_id": str(uuid.uuid4()),
                "role": "viewer"
            }
        )
        assert response.status_code == 422

    def test_register_missing_fields(self, client):
        """Test registration with missing fields returns 422."""
        response = client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                # missing password
            }
        )
        assert response.status_code == 422

    def test_login_missing_fields(self, client):
        """Test login with missing fields returns 422."""
        response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                # missing password
            }
        )
        assert response.status_code == 422

    def test_refresh_missing_token(self, client):
        """Test refresh without token returns 422."""
        response = client.post(
            "/auth/refresh",
            json={}
        )
        assert response.status_code == 422

    def test_logout_missing_auth(self, client):
        """Test logout without auth header returns 401."""
        response = client.post("/auth/logout")
        assert response.status_code == 401

    def test_me_missing_auth(self, client):
        """Test profile endpoint without auth returns 401."""
        response = client.get("/auth/me")
        assert response.status_code == 401


class TestAuthLoginWithMocks:
    """Test login endpoint with mocked services."""

    @patch("backend.api.auth.RateLimiter")
    @patch("backend.api.auth.verify_password")
    @patch("backend.api.auth.create_access_token")
    def test_login_success(
        self,
        mock_create_token,
        mock_verify_password,
        mock_rate_limiter_class,
        mock_db,
        mock_user_dict
    ):
        """Test successful user login."""
        from fastapi import FastAPI
        from backend.api.auth import router
        from backend.app.dependencies import get_db
        
        # Setup mocks
        mock_verify_password.return_value = True
        mock_create_token.return_value = "mock.jwt.token"
        
        mock_rate_limiter = AsyncMock()
        mock_rate_limiter.is_allowed.return_value = True
        mock_rate_limiter.close = AsyncMock()
        mock_rate_limiter_class.return_value = mock_rate_limiter
        
        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.email = mock_user_dict["email"]
        mock_user.password_hash = mock_user_dict["password_hash"]
        mock_user.role = MagicMock()
        mock_user.role.value = mock_user_dict["role"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        # Create app with dependency override
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: mock_db
        
        with TestClient(app) as client:
            response = client.post(
                "/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "correctpassword"
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @patch("backend.api.auth.RateLimiter")
    def test_login_user_not_found(self, mock_rate_limiter_class, mock_db):
        """Test login with non-existent user returns 401."""
        from fastapi import FastAPI
        from backend.api.auth import router
        from backend.app.dependencies import get_db
        
        mock_rate_limiter = AsyncMock()
        mock_rate_limiter.is_allowed.return_value = True
        mock_rate_limiter.close = AsyncMock()
        mock_rate_limiter_class.return_value = mock_rate_limiter
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: mock_db
        
        with TestClient(app) as client:
            response = client.post(
                "/auth/login",
                json={
                    "email": "nonexistent@example.com",
                    "password": "anypassword"
                }
            )
        
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    @patch("backend.api.auth.RateLimiter")
    def test_login_rate_limited(self, mock_rate_limiter_class, mock_db):
        """Test login rate limiting returns 429."""
        from fastapi import FastAPI
        from backend.api.auth import router
        from backend.app.dependencies import get_db
        
        mock_rate_limiter = AsyncMock()
        mock_rate_limiter.is_allowed.return_value = False
        mock_rate_limiter.close = AsyncMock()
        mock_rate_limiter_class.return_value = mock_rate_limiter
        
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: mock_db
        
        with TestClient(app) as client:
            response = client.post(
                "/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "anypassword"
                }
            )
        
        assert response.status_code == 429
        assert "too many" in response.json()["detail"].lower()


class TestTokenRefresh:
    """Test token refresh endpoint."""

    @patch("backend.api.auth.is_token_blacklisted")
    @patch("backend.api.auth.decode_access_token")
    @patch("backend.api.auth.create_access_token")
    def test_refresh_token_success(
        self,
        mock_create_token,
        mock_decode_token,
        mock_is_blacklisted,
        mock_db,
        mock_user_dict
    ):
        """Test successful token refresh."""
        from fastapi import FastAPI
        from backend.api.auth import router
        from backend.app.dependencies import get_db
        
        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
            "type": "refresh",
        }
        
        mock_decode_token.return_value = valid_payload
        mock_create_token.return_value = "new.access.token"
        mock_is_blacklisted.return_value = False
        
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.email = mock_user_dict["email"]
        mock_user.role = MagicMock()
        mock_user.role.value = mock_user_dict["role"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: mock_db
        
        with TestClient(app) as client:
            response = client.post(
                "/auth/refresh",
                json={"refresh_token": "valid.refresh.token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["access_token"] == "new.access.token"

    @patch("backend.api.auth.decode_access_token")
    def test_refresh_token_invalid(self, mock_decode_token, mock_db):
        """Test refresh with invalid token returns 401."""
        from fastapi import FastAPI
        from backend.api.auth import router
        from backend.app.dependencies import get_db
        
        mock_decode_token.side_effect = ValueError("Invalid token")
        
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: mock_db
        
        with TestClient(app) as client:
            response = client.post(
                "/auth/refresh",
                json={"refresh_token": "invalid.token"}
            )
        
        assert response.status_code == 401


class TestLogout:
    """Test logout endpoint."""

    @patch("backend.api.auth.blacklist_token")
    @patch("backend.api.auth.is_token_blacklisted")
    @patch("backend.api.auth.decode_access_token")
    def test_logout_success(
        self,
        mock_decode_token,
        mock_is_blacklisted,
        mock_blacklist_token,
        mock_db,
        mock_user_dict
    ):
        """Test successful logout."""
        from fastapi import FastAPI
        from backend.api.auth import router
        from backend.app.dependencies import get_db
        
        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }
        
        mock_decode_token.return_value = valid_payload
        mock_is_blacklisted.return_value = False
        mock_blacklist_token.return_value = True
        
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.email = mock_user_dict["email"]
        mock_user.is_active = True
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: mock_db
        
        with TestClient(app) as client:
            response = client.post(
                "/auth/logout",
                headers={"Authorization": "Bearer valid.access.token"}
            )
        
        assert response.status_code == 200
        assert "logged out" in response.json()["message"].lower()


class TestProfile:
    """Test profile endpoint."""

    @patch("backend.api.auth.is_token_blacklisted")
    @patch("backend.api.auth.decode_access_token")
    def test_get_profile_success(
        self,
        mock_decode_token,
        mock_is_blacklisted,
        mock_db,
        mock_user_dict
    ):
        """Test successful profile retrieval."""
        from fastapi import FastAPI
        from backend.api.auth import router
        from backend.app.dependencies import get_db
        
        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }
        
        mock_decode_token.return_value = valid_payload
        mock_is_blacklisted.return_value = False
        
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.email = mock_user_dict["email"]
        mock_user.role = MagicMock()
        mock_user.role.value = mock_user_dict["role"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True
        mock_user.created_at = mock_user_dict["created_at"]
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: mock_db
        
        with TestClient(app) as client:
            response = client.get(
                "/auth/me",
                headers={"Authorization": "Bearer valid.access.token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == mock_user_dict["email"]
        assert data["role"] == mock_user_dict["role"]
        assert data["is_active"] is True

    @patch("backend.api.auth.is_token_blacklisted")
    @patch("backend.api.auth.decode_access_token")
    def test_get_profile_blacklisted_token(
        self,
        mock_decode_token,
        mock_is_blacklisted,
        mock_db,
        mock_user_dict
    ):
        """Test profile with blacklisted token returns 401."""
        from fastapi import FastAPI
        from backend.api.auth import router
        from backend.app.dependencies import get_db
        
        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }
        
        mock_decode_token.return_value = valid_payload
        mock_is_blacklisted.return_value = True  # Token is blacklisted
        
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: mock_db
        
        with TestClient(app) as client:
            response = client.get(
                "/auth/me",
                headers={"Authorization": "Bearer blacklisted.token"}
            )
        
        assert response.status_code == 401
        assert "revoked" in response.json()["detail"].lower()


# --- Helper Function Tests ---

@pytest.mark.asyncio
async def test_blacklist_token_helper():
    """Test blacklist_token helper function."""
    with patch("shared.utils.cache.Cache") as mock_cache_class:
        mock_cache = AsyncMock()
        mock_cache.set.return_value = True
        mock_cache.close = AsyncMock()
        mock_cache_class.return_value = mock_cache
        
        from backend.api.auth import blacklist_token
        result = await blacklist_token("test.token")
        
        assert result is True
        mock_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_is_token_blacklisted_helper():
    """Test is_token_blacklisted helper function."""
    with patch("shared.utils.cache.Cache") as mock_cache_class:
        mock_cache = AsyncMock()
        mock_cache.exists.return_value = True
        mock_cache.close = AsyncMock()
        mock_cache_class.return_value = mock_cache
        
        from backend.api.auth import is_token_blacklisted
        result = await is_token_blacklisted("blacklisted.token")
        
        assert result is True
