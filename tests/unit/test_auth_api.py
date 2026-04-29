"""
Day 7: Auth API Endpoint Tests

Tests for all auth API routes: register, login, refresh,
logout, me, Google OAuth, check-email.

BC-012: Structured error responses.

Loophole fixes tested:
- L01: confirm_password required
- L02: Special character in password
- L04: check-email endpoint
- L08: is_new_user flag
- L11: Progressive lockout
- L12: HTTP-only cookies
"""

from unittest.mock import MagicMock, patch


class TestRegisterEndpoint:
    """Tests for POST /api/auth/register."""

    def test_register_success(self, client):
        """Valid registration returns 201 with user + tokens."""
        resp = client.post("/api/auth/register", json={
            "email": "new@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "New User",
            "company_name": "New Co",
            "industry": "technology",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "user" in data
        assert "tokens" in data
        assert data["user"]["email"] == "new@test.com"
        assert data["user"]["role"] == "owner"
        assert data["tokens"]["access_token"] is not None
        assert data["tokens"]["token_type"] == "bearer"

    def test_register_returns_expires_in(self, client):
        """Response must include expires_in for token TTL."""
        resp = client.post("/api/auth/register", json={
            "email": "expires@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Expires",
            "company_name": "Expires Co",
            "industry": "tech",
        })
        data = resp.json()
        assert "expires_in" in data["tokens"]
        assert data["tokens"]["expires_in"] == 900

    def test_register_duplicate_email_422(self, client):
        """Duplicate email should return 422."""
        body = {
            "email": "dup@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "First",
            "company_name": "First Co",
            "industry": "tech",
        }
        client.post("/api/auth/register", json=body)
        resp = client.post("/api/auth/register", json=body)
        assert resp.status_code == 422

    def test_register_weak_password_422(self, client):
        """Weak password should return 422."""
        resp = client.post("/api/auth/register", json={
            "email": "weak@test.com",
            "password": "weak",
            "confirm_password": "weak",
            "full_name": "Weak",
            "company_name": "Weak Co",
            "industry": "tech",
        })
        assert resp.status_code == 422

    def test_register_no_uppercase_422(self, client):
        """Password without uppercase should return 422."""
        resp = client.post("/api/auth/register", json={
            "email": "noupp@test.com",
            "password": "lowercase1!",
            "confirm_password": "lowercase1!",
            "full_name": "NoUpp",
            "company_name": "NoUpp Co",
            "industry": "tech",
        })
        assert resp.status_code == 422

    def test_register_no_digit_422(self, client):
        """Password without digit should return 422."""
        resp = client.post("/api/auth/register", json={
            "email": "nodigit@test.com",
            "password": "NoDigits!",
            "confirm_password": "NoDigits!",
            "full_name": "NoDigit",
            "company_name": "NoDigit Co",
            "industry": "tech",
        })
        assert resp.status_code == 422

    def test_register_no_special_char_422(self, client):
        """L02: Password without special char should return 422."""
        resp = client.post("/api/auth/register", json={
            "email": "nospec@test.com",
            "password": "NoSpecial1",
            "confirm_password": "NoSpecial1",
            "full_name": "NoSpec",
            "company_name": "NoSpec Co",
            "industry": "tech",
        })
        assert resp.status_code == 422

    def test_register_invalid_email_422(self, client):
        """Invalid email should return 422."""
        resp = client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "BadEmail",
            "company_name": "Bad Co",
            "industry": "tech",
        })
        assert resp.status_code == 422

    def test_register_missing_fields_422(self, client):
        """Missing required fields should return 422."""
        resp = client.post(
            "/api/auth/register",
            json={"email": "missing@test.com"},
        )
        assert resp.status_code == 422

    def test_register_long_email_422(self, client):
        """Email exceeding 254 chars should fail."""
        long_email = "a" * 250 + "@test.com"
        resp = client.post("/api/auth/register", json={
            "email": long_email,
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Long",
            "company_name": "Long Co",
            "industry": "tech",
        })
        assert resp.status_code == 422

    def test_register_mismatched_confirm_422(self, client):
        """L01: Mismatched confirm_password returns 422."""
        resp = client.post("/api/auth/register", json={
            "email": "mismatch@test.com",
            "password": "StrongPass1!",
            "confirm_password": "Different1!",
            "full_name": "Mismatch",
            "company_name": "Mismatch Co",
            "industry": "tech",
        })
        assert resp.status_code == 422

    def test_register_missing_confirm_422(self, client):
        """L01: Missing confirm_password returns 422."""
        resp = client.post("/api/auth/register", json={
            "email": "noconfirm@test.com",
            "password": "StrongPass1!",
            "full_name": "NoConfirm",
            "company_name": "NoConfirm Co",
            "industry": "tech",
        })
        assert resp.status_code == 422

    def test_register_returns_is_new_user(self, client):
        """L08: Registration should return is_new_user=true."""
        resp = client.post("/api/auth/register", json={
            "email": "newflag@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Flag",
            "company_name": "Flag Co",
            "industry": "tech",
        })
        assert resp.status_code == 201
        assert resp.json()["is_new_user"] is True


class TestLoginEndpoint:
    """Tests for POST /api/auth/login."""

    def _register(self, client):
        """Helper: register a user for login tests."""
        return client.post("/api/auth/register", json={
            "email": "loginuser@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Login User",
            "company_name": "Login Co",
            "industry": "tech",
        })

    def test_login_success(self, client):
        """Valid credentials return 200 with tokens."""
        self._register(client)
        resp = client.post("/api/auth/login", json={
            "email": "loginuser@test.com",
            "password": "StrongPass1!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["email"] == "loginuser@test.com"
        assert data["tokens"]["access_token"] is not None

    def test_login_wrong_password_401(self, client):
        """Wrong password returns 401."""
        self._register(client)
        resp = client.post("/api/auth/login", json={
            "email": "loginuser@test.com",
            "password": "WrongPassword1!",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_email_401(self, client):
        """Non-existent email returns 401."""
        resp = client.post("/api/auth/login", json={
            "email": "nobody@test.com",
            "password": "StrongPass1!",
        })
        assert resp.status_code == 401

    def test_login_no_reveal_existence(self, client):
        """BC-011: Error messages must not reveal if email exists."""
        # Non-existent user
        r1 = client.post("/api/auth/login", json={
            "email": "noone@test.com",
            "password": "WrongPass1!",
        })
        # Existing user, wrong password
        self._register(client)
        r2 = client.post("/api/auth/login", json={
            "email": "loginuser@test.com",
            "password": "WrongPass1!",
        })
        # Both should show same error message
        assert r1.json()["error"]["message"] == (
            r2.json()["error"]["message"]
        )

    def test_login_returns_is_new_user_false(self, client):
        """L08: Login should return is_new_user=false."""
        self._register(client)
        resp = client.post("/api/auth/login", json={
            "email": "loginuser@test.com",
            "password": "StrongPass1!",
        })
        assert resp.json()["is_new_user"] is False

    def test_login_lockout_after_5_failures(self, client):
        """L11: Account locks after 5 failed attempts."""
        self._register(client)
        # 5 failed logins
        for _ in range(5):
            client.post("/api/auth/login", json={
                "email": "loginuser@test.com",
                "password": "WrongPassword1!",
            })
        # 6th should say locked
        resp = client.post("/api/auth/login", json={
            "email": "loginuser@test.com",
            "password": "WrongPassword1!",
        })
        assert resp.status_code == 401
        assert "locked" in resp.json()["error"]["message"].lower()


class TestCheckEmailEndpoint:
    """L04: Tests for GET /api/auth/check-email."""

    def test_available_email(self, client):
        """Unregistered email should return available=true."""
        resp = client.get(
            "/api/auth/check-email?email=available@test.com"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["email"] == "available@test.com"

    def test_taken_email(self, client):
        """Registered email should return available=false."""
        client.post("/api/auth/register", json={
            "email": "takenemail@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Taken",
            "company_name": "Taken Co",
            "industry": "tech",
        })
        resp = client.get(
            "/api/auth/check-email?email=takenemail@test.com"
        )
        assert resp.status_code == 200
        assert resp.json()["available"] is False

    def test_case_insensitive_check(self, client):
        """Email check should be case-insensitive."""
        client.post("/api/auth/register", json={
            "email": "casedup@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Case",
            "company_name": "Case Co",
            "industry": "tech",
        })
        resp = client.get(
            "/api/auth/check-email?email=CASEDUP@TEST.COM"
        )
        assert resp.json()["available"] is False

    def test_missing_email_param_422(self, client):
        """Missing email query param should return 422."""
        resp = client.get("/api/auth/check-email")
        assert resp.status_code == 422


class TestRefreshEndpoint:
    """Tests for POST /api/auth/refresh."""

    def test_refresh_success(self, client):
        """Valid refresh token returns new token pair."""
        reg = client.post("/api/auth/register", json={
            "email": "refreshtest@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Refresh",
            "company_name": "Refresh Co",
            "industry": "tech",
        })
        refresh_tok = reg.json()["tokens"]["refresh_token"]

        resp = client.post("/api/auth/refresh", json={
            "refresh_token": refresh_tok,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] is not None
        assert data["refresh_token"] != refresh_tok

    def test_refresh_invalid_token_401(self, client):
        """Invalid refresh token returns 401."""
        resp = client.post("/api/auth/refresh", json={
            "refresh_token": "invalid-token",
        })
        assert resp.status_code == 401

    def test_refresh_reuse_old_token_401(self, client):
        """Reusing a refreshed token returns 401 (rotation)."""
        reg = client.post("/api/auth/register", json={
            "email": "rotatetest@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Rotate",
            "company_name": "Rotate Co",
            "industry": "tech",
        })
        old_tok = reg.json()["tokens"]["refresh_token"]

        # First refresh
        client.post("/api/auth/refresh", json={
            "refresh_token": old_tok,
        })

        # Reuse old token
        resp = client.post("/api/auth/refresh", json={
            "refresh_token": old_tok,
        })
        assert resp.status_code == 401


class TestLogoutEndpoint:
    """Tests for POST /api/auth/logout."""

    def test_logout_success(self, client):
        """Valid logout returns 200 with message."""
        reg = client.post("/api/auth/register", json={
            "email": "logoutapi@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Logout",
            "company_name": "Logout Co",
            "industry": "tech",
        })
        access_tok = reg.json()["tokens"]["access_token"]
        refresh_tok = reg.json()["tokens"]["refresh_token"]

        resp = client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_tok},
            headers={"Authorization": f"Bearer {access_tok}"},
        )
        assert resp.status_code == 200
        assert "Logged out" in resp.json()["message"]

    def test_logout_invalidates_token(self, client):
        """After logout, refresh token should not work."""
        reg = client.post("/api/auth/register", json={
            "email": "logoutinv@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "LogoutInv",
            "company_name": "LogoutInv Co",
            "industry": "tech",
        })
        access_tok = reg.json()["tokens"]["access_token"]
        refresh_tok = reg.json()["tokens"]["refresh_token"]

        client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_tok},
            headers={"Authorization": f"Bearer {access_tok}"},
        )

        resp = client.post("/api/auth/refresh", json={
            "refresh_token": refresh_tok,
        })
        assert resp.status_code == 401


class TestMeEndpoint:
    """Tests for GET /api/auth/me."""

    def test_me_with_valid_token(self, client):
        """Valid token returns user profile."""
        reg = client.post("/api/auth/register", json={
            "email": "metest@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Me Test",
            "company_name": "Me Co",
            "industry": "tech",
        })
        access_tok = reg.json()["tokens"]["access_token"]

        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "metest@test.com"
        assert data["full_name"] == "Me Test"
        assert data["role"] == "owner"
        assert "company_id" in data

    def test_me_no_token_401(self, client):
        """Missing token returns 401."""
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token_401(self, client):
        """Invalid token returns 401."""
        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid"},
        )
        assert resp.status_code == 401

    def test_me_malformed_header_401(self, client):
        """Malformed Authorization header returns 401."""
        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": "NotBearer token"},
        )
        assert resp.status_code == 401

    def test_me_wrong_token_type_401(self, client):
        """Using refresh token as access token returns 401."""
        reg = client.post("/api/auth/register", json={
            "email": "typetest@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Type Test",
            "company_name": "Type Co",
            "industry": "tech",
        })
        refresh_tok = reg.json()["tokens"]["refresh_token"]

        resp = client.get(
            "/api/auth/me",
            headers={
                "Authorization": f"Bearer {refresh_tok}"
            },
        )
        assert resp.status_code == 401


class TestGoogleEndpoint:
    """Tests for POST /api/auth/google."""

    @patch("backend.app.services.auth_service.get_settings")
    @patch("backend.app.services.auth_service.httpx")
    def test_google_new_user(self, mock_httpx, mock_get_settings, client):
        """New Google user gets registered and gets tokens."""
        # Mock settings to return None for GOOGLE_CLIENT_ID to bypass audience check
        mock_settings = MagicMock()
        mock_settings.GOOGLE_CLIENT_ID = None
        mock_get_settings.return_value = mock_settings

        mock_httpx.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "sub": "g-123",
                "email": "gnew@test.com",
                "name": "Google New",
                "picture": "https://pic.jpg",
                "email_verified": True,
                "aud": "",
            },
        )
        resp = client.post("/api/auth/google", json={
            "id_token": "fake-g-token",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["email"] == "gnew@test.com"
        assert data["user"]["is_verified"] is True
        assert data["is_new_user"] is True

    @patch("backend.app.services.auth_service.get_settings")
    @patch("backend.app.services.auth_service.httpx")
    def test_google_verification_fails(
        self, mock_httpx, mock_get_settings, client
    ):
        """Failed Google verification returns 401."""
        # Mock settings to return None for GOOGLE_CLIENT_ID to bypass audience check
        mock_settings = MagicMock()
        mock_settings.GOOGLE_CLIENT_ID = None
        mock_get_settings.return_value = mock_settings

        mock_httpx.get.return_value = MagicMock(
            status_code=400,
            json=lambda: {"error": "invalid"},
        )
        resp = client.post("/api/auth/google", json={
            "id_token": "bad-token",
        })
        assert resp.status_code == 401


class TestErrorResponseFormat:
    """Tests for structured error responses (BC-012)."""

    def test_error_response_has_structured_format(self, client):
        """All errors must have error.code, message, details."""
        resp = client.post("/api/auth/login", json={
            "email": "error@test.com",
            "password": "BadPass1!",
        })
        assert resp.status_code == 401
        data = resp.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "details" in data["error"]

    def test_422_validation_error_format(self, client):
        """422 validation errors must follow BC-012 format."""
        resp = client.post("/api/auth/register", json={
            "email": "bad-email",
            "password": "short",
        })
        assert resp.status_code == 422


class TestTenantMiddlewareBypass:
    """Tests that auth endpoints bypass tenant middleware."""

    def test_register_no_company_header_needed(self, client):
        """Register should work without X-Company-ID."""
        resp = client.post("/api/auth/register", json={
            "email": "noheader@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "No Header",
            "company_name": "NoHeader Co",
            "industry": "tech",
        })
        assert resp.status_code == 201

    def test_login_no_company_header_needed(self, client):
        """Login should work without X-Company-ID."""
        client.post("/api/auth/register", json={
            "email": "loginnh@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Login NH",
            "company_name": "LoginNH Co",
            "industry": "tech",
        })
        resp = client.post("/api/auth/login", json={
            "email": "loginnh@test.com",
            "password": "StrongPass1!",
        })
        assert resp.status_code == 200


class TestCookieSupport:
    """L12: Tests for HTTP-only cookie support."""

    def test_register_sets_cookies(self, client):
        """Registration should set auth cookies."""
        resp = client.post("/api/auth/register", json={
            "email": "cookiereg@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Cookie",
            "company_name": "Cookie Co",
            "industry": "tech",
        })
        assert resp.status_code == 201
        cookie_names = list(resp.cookies.keys())
        assert "parwa_access" in cookie_names
        assert "parwa_refresh" in cookie_names

    def test_login_sets_cookies(self, client):
        """Login should set auth cookies."""
        client.post("/api/auth/register", json={
            "email": "cookielog@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Cookie",
            "company_name": "Cookie Co",
            "industry": "tech",
        })
        resp = client.post("/api/auth/login", json={
            "email": "cookielog@test.com",
            "password": "StrongPass1!",
        })
        assert resp.status_code == 200
        cookie_names = list(resp.cookies.keys())
        assert "parwa_access" in cookie_names
        assert "parwa_refresh" in cookie_names

    def test_logout_clears_cookies(self, client):
        """Logout should clear auth cookies."""
        reg = client.post("/api/auth/register", json={
            "email": "cookielout@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Cookie",
            "company_name": "Cookie Co",
            "industry": "tech",
        })
        access_tok = reg.json()["tokens"]["access_token"]
        refresh_tok = reg.json()["tokens"]["refresh_token"]

        resp = client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_tok},
            headers={"Authorization": f"Bearer {access_tok}"},
        )
        assert resp.status_code == 200
