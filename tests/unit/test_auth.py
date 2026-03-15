"""
Unit tests for PARWA Authentication API.
Tests cover registration, login, token refresh, logout, and profile endpoints.
All external dependencies (database, Redis) are mocked for CI compatibility.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.app.dependencies import get_db


# Create a test FastAPI app with the auth router
# We import the router from the auth module
app = FastAPI()

# Import the router after app creation to avoid circular imports
from backend.api.auth import router
app.include_router(router)
client = TestClient(app)


# --- Fixtures ---

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_user_dict():
    """Create a mock user as a dictionary to avoid SQLAlchemy issues."""
    return {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "password_hash": "salt:hash",
        "role": "viewer",
        "company_id": uuid.uuid4(),
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


# --- Registration Tests ---

@pytest.mark.skip(reason="Requires integration test with real database - SQLAlchemy model mocking not feasible")
@patch("backend.api.auth.create_access_token")
@patch("backend.api.auth.hash_password")
def test_register_success(
    mock_hash_password,
    mock_create_token,
    mock_db,
):
    """Test successful user registration.
    
    Note: This test is skipped in unit tests because SQLAlchemy model 
    instantiation requires proper database setup. Run integration tests 
    for full coverage.
    """
    pass


def test_register_duplicate_email(mock_db, mock_user_dict):
    """Test registration with duplicate email returns 409."""
    # Create a mock user that will be returned by the query
    mock_user = MagicMock()
    mock_user.id = mock_user_dict["id"]
    mock_user.email = mock_user_dict["email"]

    # Mock database to return existing user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Override dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    # Make request
    response = client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "password": "securepassword123",
            "company_id": str(uuid.uuid4()),
            "role": "viewer"
        }
    )

    # Cleanup
    app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"].lower()


def test_register_short_password(mock_db):
    """Test registration with short password returns 422."""
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.post(
        "/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "short",
            "company_id": str(uuid.uuid4()),
            "role": "viewer"
        }
    )

    app.dependency_overrides.clear()

    assert response.status_code == 422


def test_register_invalid_email(mock_db):
    """Test registration with invalid email returns 422."""
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.post(
        "/auth/register",
        json={
            "email": "not-an-email",
            "password": "securepassword123",
            "company_id": str(uuid.uuid4()),
            "role": "viewer"
        }
    )

    app.dependency_overrides.clear()

    assert response.status_code == 422


# --- Login Tests ---

@patch("backend.api.auth.RateLimiter")
@patch("backend.api.auth.verify_password")
@patch("backend.api.auth.create_access_token")
def test_login_success(
    mock_create_token,
    mock_verify_password,
    mock_rate_limiter_class,
    mock_db,
    mock_user_dict
):
    """Test successful user login."""
    # Setup mocks
    mock_verify_password.return_value = True
    mock_create_token.return_value = "mock.jwt.token"

    # Mock rate limiter
    mock_rate_limiter = AsyncMock()
    mock_rate_limiter.is_allowed.return_value = True
    mock_rate_limiter.close = AsyncMock()
    mock_rate_limiter_class.return_value = mock_rate_limiter

    # Create a mock user
    mock_user = MagicMock()
    mock_user.id = mock_user_dict["id"]
    mock_user.email = mock_user_dict["email"]
    mock_user.password_hash = mock_user_dict["password_hash"]
    mock_user.role = MagicMock()
    mock_user.role.value = mock_user_dict["role"]
    mock_user.company_id = mock_user_dict["company_id"]
    mock_user.is_active = True

    # Mock database query
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Override dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    # Make request
    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "correctpassword"
        }
    )

    # Cleanup
    app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@patch("backend.api.auth.RateLimiter")
def test_login_user_not_found(mock_rate_limiter_class, mock_db):
    """Test login with non-existent user returns 401."""
    # Mock rate limiter
    mock_rate_limiter = AsyncMock()
    mock_rate_limiter.is_allowed.return_value = True
    mock_rate_limiter.close = AsyncMock()
    mock_rate_limiter_class.return_value = mock_rate_limiter

    # Mock database to return no user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    # Override dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    # Make request
    response = client.post(
        "/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "anypassword"
        }
    )

    # Cleanup
    app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


@patch("backend.api.auth.RateLimiter")
@patch("backend.api.auth.verify_password")
def test_login_wrong_password(
    mock_verify_password,
    mock_rate_limiter_class,
    mock_db,
    mock_user_dict
):
    """Test login with wrong password returns 401."""
    # Setup mocks
    mock_verify_password.return_value = False

    # Mock rate limiter
    mock_rate_limiter = AsyncMock()
    mock_rate_limiter.is_allowed.return_value = True
    mock_rate_limiter.close = AsyncMock()
    mock_rate_limiter_class.return_value = mock_rate_limiter

    # Create a mock user
    mock_user = MagicMock()
    mock_user.id = mock_user_dict["id"]
    mock_user.email = mock_user_dict["email"]
    mock_user.password_hash = mock_user_dict["password_hash"]
    mock_user.is_active = True

    # Mock database query
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Override dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    # Make request
    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "wrongpassword"
        }
    )

    # Cleanup
    app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 401


@patch("backend.api.auth.RateLimiter")
def test_login_rate_limited(mock_rate_limiter_class, mock_db):
    """Test login rate limiting returns 429."""
    # Mock rate limiter to deny request
    mock_rate_limiter = AsyncMock()
    mock_rate_limiter.is_allowed.return_value = False
    mock_rate_limiter.close = AsyncMock()
    mock_rate_limiter_class.return_value = mock_rate_limiter

    # Override dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    # Make request
    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "anypassword"
        }
    )

    # Cleanup
    app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 429
    assert "too many" in response.json()["detail"].lower()


# --- Token Refresh Tests ---

@patch("backend.api.auth.is_token_blacklisted")
@patch("backend.api.auth.decode_access_token")
@patch("backend.api.auth.create_access_token")
def test_refresh_token_success(
    mock_create_token,
    mock_decode_token,
    mock_is_blacklisted,
    mock_db,
    mock_user_dict
):
    """Test successful token refresh."""
    # Create a valid token payload
    valid_token_payload = {
        "sub": str(mock_user_dict["id"]),
        "email": mock_user_dict["email"],
        "role": mock_user_dict["role"],
        "company_id": str(mock_user_dict["company_id"]),
        "type": "refresh",
    }

    # Setup mocks
    mock_decode_token.return_value = valid_token_payload
    mock_create_token.return_value = "new.access.token"
    mock_is_blacklisted.return_value = False

    # Create a mock user
    mock_user = MagicMock()
    mock_user.id = mock_user_dict["id"]
    mock_user.email = mock_user_dict["email"]
    mock_user.role = MagicMock()
    mock_user.role.value = mock_user_dict["role"]
    mock_user.company_id = mock_user_dict["company_id"]
    mock_user.is_active = True

    # Mock database query
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Override dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    # Make request
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "valid.refresh.token"}
    )

    # Cleanup
    app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["access_token"] == "new.access.token"


@patch("backend.api.auth.decode_access_token")
def test_refresh_token_invalid(mock_decode_token, mock_db):
    """Test refresh with invalid token returns 401."""
    # Setup mock to raise error
    mock_decode_token.side_effect = ValueError("Invalid token")

    # Override dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    # Make request
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid.token"}
    )

    # Cleanup
    app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 401


@patch("backend.api.auth.is_token_blacklisted")
@patch("backend.api.auth.decode_access_token")
def test_refresh_token_wrong_type(
    mock_decode_token,
    mock_is_blacklisted,
    mock_db,
    mock_user_dict
):
    """Test refresh with access token (not refresh token) returns 401."""
    # Create a token payload without "type": "refresh"
    valid_token_payload = {
        "sub": str(mock_user_dict["id"]),
        "email": mock_user_dict["email"],
        "role": mock_user_dict["role"],
        "company_id": str(mock_user_dict["company_id"]),
        # No "type": "refresh"
    }

    # Setup mocks
    mock_decode_token.return_value = valid_token_payload
    mock_is_blacklisted.return_value = False

    # Override dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    # Make request
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "access.token.not.refresh"}
    )

    # Cleanup
    app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 401
    assert "invalid token type" in response.json()["detail"].lower()


# --- Logout Tests ---

@patch("backend.api.auth.blacklist_token")
@patch("backend.api.auth.is_token_blacklisted")
@patch("backend.api.auth.decode_access_token")
def test_logout_success(
    mock_decode_token,
    mock_is_blacklisted,
    mock_blacklist_token,
    mock_db,
    mock_user_dict
):
    """Test successful logout."""
    # Create a valid token payload
    valid_token_payload = {
        "sub": str(mock_user_dict["id"]),
        "email": mock_user_dict["email"],
        "role": mock_user_dict["role"],
        "company_id": str(mock_user_dict["company_id"]),
    }

    # Setup mocks
    mock_decode_token.return_value = valid_token_payload
    mock_is_blacklisted.return_value = False
    mock_blacklist_token.return_value = True

    # Create a mock user
    mock_user = MagicMock()
    mock_user.id = mock_user_dict["id"]
    mock_user.email = mock_user_dict["email"]
    mock_user.is_active = True

    # Mock database query
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Override dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    # Make request with Bearer token
    response = client.post(
        "/auth/logout",
        headers={"Authorization": "Bearer valid.access.token"}
    )

    # Cleanup
    app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 200
    assert "logged out" in response.json()["message"].lower()


@patch("backend.api.auth.blacklist_token")
@patch("backend.api.auth.is_token_blacklisted")
@patch("backend.api.auth.decode_access_token")
def test_logout_blacklist_failure(
    mock_decode_token,
    mock_is_blacklisted,
    mock_blacklist_token,
    mock_db,
    mock_user_dict
):
    """Test logout with blacklist failure returns 500."""
    # Create a valid token payload
    valid_token_payload = {
        "sub": str(mock_user_dict["id"]),
        "email": mock_user_dict["email"],
        "role": mock_user_dict["role"],
        "company_id": str(mock_user_dict["company_id"]),
    }

    # Setup mocks
    mock_decode_token.return_value = valid_token_payload
    mock_is_blacklisted.return_value = False
    mock_blacklist_token.return_value = False  # Blacklist failed

    # Create a mock user
    mock_user = MagicMock()
    mock_user.id = mock_user_dict["id"]
    mock_user.email = mock_user_dict["email"]
    mock_user.is_active = True

    # Mock database query
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Override dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    # Make request
    response = client.post(
        "/auth/logout",
        headers={"Authorization": "Bearer valid.access.token"}
    )

    # Cleanup
    app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 500


def test_logout_missing_token(mock_db):
    """Test logout without token returns 401/403."""
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.post("/auth/logout")

    app.dependency_overrides.clear()

    # FastAPI returns 401 or 403 for missing auth credentials depending on configuration
    assert response.status_code in [401, 403]


# --- Profile Tests ---

@patch("backend.api.auth.is_token_blacklisted")
@patch("backend.api.auth.decode_access_token")
def test_get_profile_success(
    mock_decode_token,
    mock_is_blacklisted,
    mock_db,
    mock_user_dict
):
    """Test successful profile retrieval."""
    # Create a valid token payload
    valid_token_payload = {
        "sub": str(mock_user_dict["id"]),
        "email": mock_user_dict["email"],
        "role": mock_user_dict["role"],
        "company_id": str(mock_user_dict["company_id"]),
    }

    # Setup mocks
    mock_decode_token.return_value = valid_token_payload
    mock_is_blacklisted.return_value = False

    # Create a mock user
    mock_user = MagicMock()
    mock_user.id = mock_user_dict["id"]
    mock_user.email = mock_user_dict["email"]
    mock_user.role = MagicMock()
    mock_user.role.value = mock_user_dict["role"]
    mock_user.company_id = mock_user_dict["company_id"]
    mock_user.is_active = True
    mock_user.created_at = mock_user_dict["created_at"]

    # Mock database query
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Override dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    # Make request
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer valid.access.token"}
    )

    # Cleanup
    app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == mock_user_dict["email"]
    assert data["role"] == mock_user_dict["role"]
    assert data["is_active"] is True


@patch("backend.api.auth.is_token_blacklisted")
@patch("backend.api.auth.decode_access_token")
def test_get_profile_inactive_user(
    mock_decode_token,
    mock_is_blacklisted,
    mock_db,
    mock_user_dict
):
    """Test profile retrieval for inactive user returns 403."""
    # Create a valid token payload
    valid_token_payload = {
        "sub": str(mock_user_dict["id"]),
        "email": mock_user_dict["email"],
        "role": mock_user_dict["role"],
        "company_id": str(mock_user_dict["company_id"]),
    }

    # Setup mocks
    mock_decode_token.return_value = valid_token_payload
    mock_is_blacklisted.return_value = False

    # Create a mock user that's inactive
    mock_user = MagicMock()
    mock_user.id = mock_user_dict["id"]
    mock_user.email = mock_user_dict["email"]
    mock_user.is_active = False

    # Mock database query
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Override dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    # Make request
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer valid.access.token"}
    )

    # Cleanup
    app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 403


@patch("backend.api.auth.is_token_blacklisted")
@patch("backend.api.auth.decode_access_token")
def test_get_profile_blacklisted_token(
    mock_decode_token,
    mock_is_blacklisted,
    mock_db,
    mock_user_dict
):
    """Test profile retrieval with blacklisted token returns 401."""
    # Create a valid token payload
    valid_token_payload = {
        "sub": str(mock_user_dict["id"]),
        "email": mock_user_dict["email"],
        "role": mock_user_dict["role"],
        "company_id": str(mock_user_dict["company_id"]),
    }

    # Setup mocks
    mock_decode_token.return_value = valid_token_payload
    mock_is_blacklisted.return_value = True  # Token is blacklisted

    # Override dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    # Make request
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer blacklisted.token"}
    )

    # Cleanup
    app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 401
    assert "revoked" in response.json()["detail"].lower()


# --- Helper Function Tests ---

@pytest.mark.asyncio
@patch("shared.utils.cache.Cache")
async def test_blacklist_token_success(mock_cache_class):
    """Test successful token blacklisting."""
    from backend.api.auth import blacklist_token

    # Setup mock
    mock_cache = AsyncMock()
    mock_cache.set.return_value = True
    mock_cache.close = AsyncMock()
    mock_cache_class.return_value = mock_cache

    result = await blacklist_token("test.token")

    assert result is True
    mock_cache.set.assert_called_once()


@pytest.mark.asyncio
@patch("shared.utils.cache.Cache")
async def test_is_token_blacklisted_true(mock_cache_class):
    """Test checking if token is blacklisted returns True."""
    from backend.api.auth import is_token_blacklisted

    # Setup mock
    mock_cache = AsyncMock()
    mock_cache.exists.return_value = True
    mock_cache.close = AsyncMock()
    mock_cache_class.return_value = mock_cache

    result = await is_token_blacklisted("blacklisted.token")

    assert result is True


@pytest.mark.asyncio
@patch("shared.utils.cache.Cache")
async def test_is_token_blacklisted_false(mock_cache_class):
    """Test checking if token is blacklisted returns False."""
    from backend.api.auth import is_token_blacklisted

    # Setup mock
    mock_cache = AsyncMock()
    mock_cache.exists.return_value = False
    mock_cache.close = AsyncMock()
    mock_cache_class.return_value = mock_cache

    result = await is_token_blacklisted("valid.token")

    assert result is False
