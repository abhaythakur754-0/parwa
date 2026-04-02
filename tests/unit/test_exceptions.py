"""
Tests for PARWA Exception Classes (exceptions.py)

BC-012: All exceptions produce structured JSON error responses.
No stack traces are ever exposed to users.
Every subclass must have correct default status_code and error_code.
"""

from backend.app.exceptions import (
    AuthenticationError,
    AuthorizationError,
    InternalError,
    NotFoundError,
    ParwaBaseError,
    RateLimitError,
    ValidationError,
)


class TestParwaBaseError:
    """Test the base error class."""

    def test_default_message(self):
        """Default message is 'An error occurred'."""
        err = ParwaBaseError()
        assert err.message == "An error occurred"

    def test_default_error_code(self):
        """Default error code is 'INTERNAL_ERROR'."""
        err = ParwaBaseError()
        assert err.error_code == "INTERNAL_ERROR"

    def test_default_status_code(self):
        """Default status code is 500."""
        err = ParwaBaseError()
        assert err.status_code == 500

    def test_default_details_none(self):
        """Default details is None."""
        err = ParwaBaseError()
        assert err.details is None

    def test_custom_message(self):
        """Custom message overrides default."""
        err = ParwaBaseError(message="Something broke")
        assert err.message == "Something broke"

    def test_custom_error_code(self):
        """Custom error code overrides default."""
        err = ParwaBaseError(error_code="CUSTOM_CODE")
        assert err.error_code == "CUSTOM_CODE"

    def test_custom_status_code(self):
        """Custom status code overrides default."""
        err = ParwaBaseError(status_code=418)
        assert err.status_code == 418

    def test_custom_details_dict(self):
        """Details can be a dict."""
        details = {"field": "email", "issue": "invalid format"}
        err = ParwaBaseError(details=details)
        assert err.details == details

    def test_custom_details_list(self):
        """Details can be a list."""
        details = ["error1", "error2"]
        err = ParwaBaseError(details=details)
        assert err.details == details

    def test_custom_details_string(self):
        """Details can be a string."""
        err = ParwaBaseError(details="extra info")
        assert err.details == "extra info"

    def test_str_representation(self):
        """str(error) returns the message (used by super().__init__)."""
        err = ParwaBaseError(message="test message")
        assert str(err) == "test message"

    def test_is_exception_subclass(self):
        """ParwaBaseError inherits from Exception."""
        assert issubclass(ParwaBaseError, Exception)


class TestToDict:
    """Test to_dict() structured output (BC-012)."""

    def test_to_dict_structure(self):
        """to_dict returns {error: {code, message, details}}."""
        err = ParwaBaseError()
        result = err.to_dict()
        assert "error" in result
        assert "code" in result["error"]
        assert "message" in result["error"]
        assert "details" in result["error"]

    def test_to_dict_has_three_keys_only(self):
        """Error dict has exactly code, message, details — nothing else."""
        err = ParwaBaseError()
        error_obj = err.to_dict()["error"]
        assert set(error_obj.keys()) == {"code", "message", "details"}

    def test_to_dict_values_match_attributes(self):
        """to_dict values match the error's attributes."""
        err = ParwaBaseError(
            message="custom msg",
            error_code="CUSTOM",
            status_code=400,
            details={"key": "val"},
        )
        result = err.to_dict()
        assert result["error"]["code"] == "CUSTOM"
        assert result["error"]["message"] == "custom msg"
        assert result["error"]["details"] == {"key": "val"}

    def test_to_dict_details_none(self):
        """When details is None, to_dict still includes details key."""
        err = ParwaBaseError()
        result = err.to_dict()
        assert result["error"]["details"] is None

    def test_to_dict_no_stack_trace(self):
        """to_dict never includes traceback or stack info."""
        err = ParwaBaseError()
        result = err.to_dict()
        result_str = str(result).lower()
        assert "traceback" not in result_str
        assert "stack" not in result_str


# ── Subclass Tests ─────────────────────────────────────────────────────


class TestNotFoundError:
    """Test NotFoundError: 404, NOT_FOUND."""

    def test_default_status_404(self):
        assert NotFoundError().status_code == 404

    def test_default_code_not_found(self):
        assert NotFoundError().error_code == "NOT_FOUND"

    def test_default_message(self):
        assert NotFoundError().message == "Resource not found"

    def test_custom_message(self):
        err = NotFoundError(message="User not found")
        assert err.message == "User not found"
        assert err.status_code == 404

    def test_custom_details(self):
        err = NotFoundError(details={"resource": "ticket_123"})
        assert err.details == {"resource": "ticket_123"}


class TestValidationError:
    """Test ValidationError: 422, VALIDATION_ERROR."""

    def test_default_status_422(self):
        assert ValidationError().status_code == 422

    def test_default_code(self):
        assert ValidationError().error_code == "VALIDATION_ERROR"

    def test_default_message(self):
        assert ValidationError().message == "Validation failed"

    def test_custom_details_list(self):
        details = ["email: required field", "name: too short"]
        err = ValidationError(details=details)
        assert err.details == details
        assert err.status_code == 422


class TestAuthenticationError:
    """Test AuthenticationError: 401, AUTHENTICATION_ERROR."""

    def test_default_status_401(self):
        assert AuthenticationError().status_code == 401

    def test_default_code(self):
        assert AuthenticationError().error_code == "AUTHENTICATION_ERROR"

    def test_default_message(self):
        assert AuthenticationError().message == "Authentication required"


class TestAuthorizationError:
    """Test AuthorizationError: 403, AUTHORIZATION_ERROR."""

    def test_default_status_403(self):
        assert AuthorizationError().status_code == 403

    def test_default_code(self):
        assert AuthorizationError().error_code == "AUTHORIZATION_ERROR"

    def test_default_message(self):
        assert AuthorizationError().message == "Permission denied"


class TestRateLimitError:
    """Test RateLimitError: 429, RATE_LIMIT_EXCEEDED."""

    def test_default_status_429(self):
        assert RateLimitError().status_code == 429

    def test_default_code(self):
        assert RateLimitError().error_code == "RATE_LIMIT_EXCEEDED"

    def test_default_message(self):
        assert RateLimitError().message == "Rate limit exceeded"


class TestInternalError:
    """Test InternalError: 500, INTERNAL_ERROR."""

    def test_default_status_500(self):
        assert InternalError().status_code == 500

    def test_default_code(self):
        assert InternalError().error_code == "INTERNAL_ERROR"

    def test_default_message(self):
        assert InternalError().message == "An internal error occurred"

    def test_details_none_by_default(self):
        """InternalError details default to None (no internal leaks)."""
        assert InternalError().details is None


class TestAllSubclassesAreParwaBaseError:
    """All custom exceptions must inherit from ParwaBaseError."""

    def test_not_found_is_base(self):
        assert issubclass(NotFoundError, ParwaBaseError)

    def test_validation_is_base(self):
        assert issubclass(ValidationError, ParwaBaseError)

    def test_authentication_is_base(self):
        assert issubclass(AuthenticationError, ParwaBaseError)

    def test_authorization_is_base(self):
        assert issubclass(AuthorizationError, ParwaBaseError)

    def test_rate_limit_is_base(self):
        assert issubclass(RateLimitError, ParwaBaseError)

    def test_internal_is_base(self):
        assert issubclass(InternalError, ParwaBaseError)
