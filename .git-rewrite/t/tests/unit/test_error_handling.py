"""
Unit Tests for PARWA Error Handling Module
Tests for error classes, decorators, and retry logic
"""

import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add parent directory to path for imports
import sys
sys.path.insert(0, "/home/z/my-project")

from backend.core.error_handler import (
    PARWAError,
    ErrorSeverity,
    ErrorCategory,
    WebhookError,
    WebhookSignatureError,
    WebhookTimestampError,
    WebhookPayloadError,
    WebhookProcessingError,
    AuthenticationError,
    AuthorizationError,
    APIKeyError,
    ExternalAPIError,
    GoogleAIError,
    CerebrasError,
    GroqError,
    BrevoError,
    ShopifyAPIError,
    StripeAPIError,
    DatabaseError,
    RecordNotFoundError,
    DuplicateRecordError,
    ComplianceError,
    GDPRComplianceError,
    TCPAComplianceError,
    SLABreachError,
    RateLimitError,
    ConfigurationError,
    MissingConfigError,
    InvalidConfigError,
    handle_errors,
    with_retry,
    RetryConfig,
    ErrorResponseBuilder,
)


class TestPARWAError:
    """Tests for base PARWAError class"""
    
    def test_basic_error_creation(self):
        """Test creating a basic PARWA error"""
        error = PARWAError(
            message="Test error",
            error_code="TEST_ERROR"
        )
        assert error.message == "Test error"
        assert error.error_code == "TEST_ERROR"
        assert error.category == ErrorCategory.VALIDATION
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.retryable is False
    
    def test_error_with_all_parameters(self):
        """Test creating error with all parameters"""
        error = PARWAError(
            message="Complex error",
            error_code="COMPLEX_ERROR",
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            details={"key": "value"},
            retryable=True,
            company_id="comp_123"
        )
        assert error.category == ErrorCategory.DATABASE
        assert error.severity == ErrorSeverity.HIGH
        assert error.details == {"key": "value"}
        assert error.retryable is True
        assert error.company_id == "comp_123"
    
    def test_error_to_dict(self):
        """Test error serialization to dictionary"""
        error = PARWAError(
            message="Serialization test",
            error_code="SERIAL_ERROR",
            severity=ErrorSeverity.LOW,
            details={"test": True}
        )
        result = error.to_dict()
        
        assert result["error"] is True
        assert result["error_code"] == "SERIAL_ERROR"
        assert result["message"] == "Serialization test"
        assert result["severity"] == "low"
        assert result["details"]["test"] is True
        assert "timestamp" in result


class TestWebhookErrors:
    """Tests for webhook-related error classes"""
    
    def test_webhook_signature_error(self):
        """Test WebhookSignatureError creation"""
        error = WebhookSignatureError(source="shopify")
        
        assert error.message == "Invalid webhook signature"
        assert error.error_code == "WEBHOOK_SIGNATURE_INVALID"
        assert error.severity == ErrorSeverity.HIGH
        assert error.details["source"] == "shopify"
    
    def test_webhook_timestamp_error(self):
        """Test WebhookTimestampError creation"""
        error = WebhookTimestampError(timestamp_diff=450)
        
        assert error.error_code == "WEBHOOK_TIMESTAMP_EXPIRED"
        assert error.details["timestamp_diff_seconds"] == 450
    
    def test_webhook_payload_error(self):
        """Test WebhookPayloadError creation"""
        error = WebhookPayloadError(
            message="Invalid payload",
            validation_errors=["Missing field: id", "Invalid email"]
        )
        
        assert error.error_code == "WEBHOOK_PAYLOAD_INVALID"
        assert len(error.details["validation_errors"]) == 2
    
    def test_webhook_processing_error(self):
        """Test WebhookProcessingError creation"""
        error = WebhookProcessingError(
            message="Processing failed",
            event_type="order.created",
            retryable=True
        )
        
        assert error.error_code == "WEBHOOK_PROCESSING_ERROR"
        assert error.retryable is True
        assert error.details["event_type"] == "order.created"


class TestAuthenticationErrors:
    """Tests for authentication-related error classes"""
    
    def test_authentication_error(self):
        """Test AuthenticationError creation"""
        error = AuthenticationError("Invalid credentials")
        
        assert error.message == "Invalid credentials"
        assert error.error_code == "AUTH_FAILED"
        assert error.category == ErrorCategory.AUTHENTICATION
    
    def test_authorization_error(self):
        """Test AuthorizationError creation"""
        error = AuthorizationError(required_role="admin")
        
        assert error.error_code == "AUTH_FORBIDDEN"
        assert error.category == ErrorCategory.AUTHORIZATION
        assert error.details["required_role"] == "admin"
    
    def test_api_key_error(self):
        """Test APIKeyError creation"""
        error = APIKeyError(provider="google_ai")
        
        assert error.error_code == "API_KEY_INVALID"
        assert error.details["provider"] == "google_ai"


class TestExternalAPIErrors:
    """Tests for external API error classes"""
    
    def test_google_ai_error(self):
        """Test GoogleAIError creation"""
        error = GoogleAIError(status_code=429)
        
        assert error.message == "Google AI API error"
        assert error.details["provider"] == "google_ai"
        assert error.details["status_code"] == 429
        assert error.retryable is True
    
    def test_cerebras_error(self):
        """Test CerebrasError creation"""
        error = CerebrasError("Rate limit exceeded")
        
        assert error.message == "Rate limit exceeded"
        assert error.details["provider"] == "cerebras"
    
    def test_groq_error(self):
        """Test GroqError creation"""
        error = GroqError(status_code=500)
        
        assert error.details["provider"] == "groq"
    
    def test_brevo_error(self):
        """Test BrevoError creation"""
        error = BrevoError("Email delivery failed")
        
        assert error.message == "Email delivery failed"
        assert error.details["provider"] == "brevo"
    
    def test_shopify_api_error(self):
        """Test ShopifyAPIError creation"""
        error = ShopifyAPIError(status_code=401)
        
        assert error.details["provider"] == "shopify"
    
    def test_stripe_api_error(self):
        """Test StripeAPIError creation"""
        error = StripeAPIError("Card declined", status_code=402)
        
        assert error.message == "Card declined"


class TestDatabaseErrors:
    """Tests for database error classes"""
    
    def test_database_error(self):
        """Test DatabaseError creation"""
        error = DatabaseError(
            message="Connection failed",
            operation="read"
        )
        
        assert error.message == "Connection failed"
        assert error.category == ErrorCategory.DATABASE
        assert error.retryable is True
        assert error.details["operation"] == "read"
    
    def test_record_not_found_error(self):
        """Test RecordNotFoundError creation"""
        error = RecordNotFoundError(
            model="User",
            record_id="user_123"
        )
        
        assert error.message == "Record not found"
        assert error.severity == ErrorSeverity.LOW
        assert error.retryable is False
        assert error.details["model"] == "User"
        assert error.details["record_id"] == "user_123"
    
    def test_duplicate_record_error(self):
        """Test DuplicateRecordError creation"""
        error = DuplicateRecordError(field="email")
        
        assert error.message == "Record already exists"
        assert error.details["field"] == "email"


class TestComplianceErrors:
    """Tests for compliance error classes"""
    
    def test_gdpr_compliance_error(self):
        """Test GDPRComplianceError creation"""
        error = GDPRComplianceError(request_type="deletion")
        
        assert error.message == "GDPR compliance violation"
        assert error.error_code == "GDPR_VIOLATION"
        assert error.details["request_type"] == "deletion"
    
    def test_tcpa_compliance_error(self):
        """Test TCPAComplianceError creation"""
        error = TCPAComplianceError(phone_number="+1234567890")
        
        assert error.error_code == "TCPA_VIOLATION"
        assert error.severity == ErrorSeverity.CRITICAL
        # Phone should be masked
        assert error.details["phone_number"] == "+12345****"
    
    def test_sla_breach_error(self):
        """Test SLABreachError creation"""
        error = SLABreachError(sla_hours=24)
        
        assert error.message == "SLA breach detected"
        assert error.error_code == "SLA_BREACH"
        assert error.severity == ErrorSeverity.CRITICAL
        assert error.details["sla_hours"] == 24


class TestConfigurationErrors:
    """Tests for configuration error classes"""
    
    def test_missing_config_error(self):
        """Test MissingConfigError creation"""
        error = MissingConfigError("DATABASE_URL")
        
        assert "DATABASE_URL" in error.message
        assert error.details["config_key"] == "DATABASE_URL"
        assert error.severity == ErrorSeverity.CRITICAL
    
    def test_invalid_config_error(self):
        """Test InvalidConfigError creation"""
        error = InvalidConfigError(
            config_key="PORT",
            reason="must be a number between 1 and 65535"
        )
        
        assert "PORT" in error.message
        assert error.details["config_key"] == "PORT"


class TestRateLimitError:
    """Tests for rate limit error"""
    
    def test_rate_limit_error(self):
        """Test RateLimitError creation"""
        error = RateLimitError(
            limit=100,
            window=60,
            retry_after=30
        )
        
        assert error.error_code == "RATE_LIMIT_EXCEEDED"
        assert error.retryable is True
        assert error.details["limit"] == 100
        assert error.details["retry_after_seconds"] == 30


class TestHandleErrorsDecorator:
    """Tests for handle_errors decorator"""
    
    def test_handle_errors_success(self):
        """Test decorator with successful function"""
        @handle_errors()
        def success_func():
            return "success"
        
        result = success_func()
        assert result == "success"
    
    def test_handle_errors_reraise_parwa_error(self):
        """Test decorator reraises PARWA errors"""
        @handle_errors(reraise=True)
        def error_func():
            raise WebhookSignatureError("test")
        
        with pytest.raises(WebhookSignatureError):
            error_func()
    
    def test_handle_errors_wraps_generic_error(self):
        """Test decorator wraps generic exceptions"""
        @handle_errors()
        def error_func():
            raise ValueError("Something went wrong")
        
        with pytest.raises(PARWAError) as exc_info:
            error_func()
        
        assert exc_info.value.error_code == "INTERNAL_ERROR"
    
    def test_handle_errors_return_error_dict(self):
        """Test decorator returning error dict instead of raising"""
        @handle_errors(return_error_dict=True)
        def error_func():
            raise WebhookSignatureError("test")
        
        result = error_func()
        assert result["error"] is True
        assert result["error_code"] == "WEBHOOK_SIGNATURE_INVALID"
    
    def test_handle_errors_async(self):
        """Test decorator with async function"""
        @handle_errors()
        async def async_error_func():
            raise DatabaseError("Connection failed")
        
        with pytest.raises(DatabaseError):
            asyncio.run(async_error_func())


class TestRetryLogic:
    """Tests for retry decorators and configuration"""
    
    def test_retry_config_defaults(self):
        """Test RetryConfig default values"""
        config = RetryConfig()
        
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
    
    def test_with_retry_success_after_retries(self):
        """Test retry succeeds after failures"""
        call_count = 0
        
        @with_retry(RetryConfig(max_retries=3, base_delay=0.1))
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ExternalAPIError("Temporary failure", provider="test")
            return "success"
        
        result = flaky_func()
        assert result == "success"
        assert call_count == 3
    
    def test_with_retry_max_retries_exceeded(self):
        """Test retry fails after max retries"""
        @with_retry(RetryConfig(max_retries=2, base_delay=0.1))
        def always_fail():
            raise ExternalAPIError("Permanent failure", provider="test")
        
        with pytest.raises(ExternalAPIError):
            always_fail()
    
    def test_with_retry_non_retryable_exception(self):
        """Test non-retryable exceptions are not retried"""
        call_count = 0
        
        @with_retry(RetryConfig(max_retries=3, base_delay=0.1))
        def validation_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Validation error")
        
        with pytest.raises(ValueError):
            validation_error()
        
        # Should only be called once (not retried)
        assert call_count == 1


class TestErrorResponseBuilder:
    """Tests for ErrorResponseBuilder"""
    
    def test_build_from_parwa_error(self):
        """Test building response from PARWA error"""
        error = WebhookSignatureError(source="stripe")
        response = ErrorResponseBuilder.build(error)
        
        assert response["error"] is True
        assert response["error_code"] == "WEBHOOK_SIGNATURE_INVALID"
        assert "timestamp" in response
    
    def test_build_from_generic_error(self):
        """Test building response from generic exception"""
        error = ValueError("Invalid value")
        response = ErrorResponseBuilder.build(error)
        
        assert response["error"] is True
        assert response["error_code"] == "INTERNAL_ERROR"
        assert response["message"] == "Invalid value"
    
    def test_build_with_trace(self):
        """Test building response with stack trace"""
        error = DatabaseError("Test error")
        response = ErrorResponseBuilder.build(error, include_trace=True)
        
        assert "trace" in response
    
    def test_validation_error_response(self):
        """Test validation error response builder"""
        response = ErrorResponseBuilder.validation_error(
            message="Invalid email format",
            field="email",
            value="invalid-email"
        )
        
        assert response["error"] is True
        assert response["error_code"] == "VALIDATION_ERROR"
        assert response["details"]["field"] == "email"
    
    def test_not_found_error_response(self):
        """Test not found error response builder"""
        response = ErrorResponseBuilder.not_found_error(
            resource="User",
            resource_id="user_123"
        )
        
        assert response["error"] is True
        assert response["error_code"] == "NOT_FOUND"
        assert response["message"] == "User not found"


class TestErrorSeverity:
    """Tests for error severity levels"""
    
    def test_severity_values(self):
        """Test error severity enum values"""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"


class TestErrorCategory:
    """Tests for error categories"""
    
    def test_category_values(self):
        """Test error category enum values"""
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.AUTHENTICATION.value == "authentication"
        assert ErrorCategory.WEBHOOK.value == "webhook"
        assert ErrorCategory.DATABASE.value == "database"
        assert ErrorCategory.COMPLIANCE.value == "compliance"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
