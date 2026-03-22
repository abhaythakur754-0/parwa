"""
PARWA Webhook Error Handlers
Error handling middleware and utilities for webhooks
"""

import hashlib
import hmac
import time
import logging
from typing import Optional, Callable, Dict, Any
from functools import wraps
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

from backend.core.error_handler import (
    WebhookError,
    WebhookSignatureError,
    WebhookTimestampError,
    WebhookPayloadError,
    WebhookProcessingError,
    RateLimitError,
    with_retry,
    RetryConfig,
    ErrorResponseBuilder,
    PARWAError,
)

logger = logging.getLogger(__name__)


# ============================================================================
# HMAC Signature Verification
# ============================================================================

class HMACVerifier:
    """HMAC signature verification for webhooks"""
    
    def __init__(self, secret: str, algorithm: str = "sha256"):
        """
        Initialize HMAC verifier.
        
        Args:
            secret: Webhook signing secret
            algorithm: Hash algorithm (sha256, sha1, sha512)
        """
        self.secret = secret.encode("utf-8") if isinstance(secret, str) else secret
        self.algorithm = algorithm
    
    def verify_shopify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Shopify webhook signature.
        
        Shopify uses base64-encoded HMAC-SHA256.
        
        Args:
            payload: Raw request body bytes
            signature: X-Shopify-Hmac-SHA256 header value
        
        Returns:
            True if signature is valid
        """
        import base64
        
        if not signature:
            raise WebhookSignatureError(
                message="Missing Shopify webhook signature",
                source="shopify"
            )
        
        try:
            expected_signature = base64.b64encode(
                hmac.new(self.secret, payload, hashlib.sha256).digest()
            ).decode()
            
            if not hmac.compare_digest(expected_signature, signature):
                raise WebhookSignatureError(
                    message="Invalid Shopify webhook signature",
                    source="shopify"
                )
            
            return True
        except Exception as e:
            if isinstance(e, WebhookSignatureError):
                raise
            raise WebhookSignatureError(
                message=f"Error verifying Shopify signature: {str(e)}",
                source="shopify"
            )
    
    def verify_stripe_signature(
        self,
        payload: bytes,
        signature: str,
        tolerance: int = 300
    ) -> Dict[str, Any]:
        """
        Verify Stripe webhook signature.
        
        Stripe uses a special format: t=<timestamp>,v1=<signature>
        
        Args:
            payload: Raw request body bytes
            signature: Stripe-Signature header value
            tolerance: Maximum timestamp difference in seconds
        
        Returns:
            Dict with timestamp and valid status
        """
        if not signature:
            raise WebhookSignatureError(
                message="Missing Stripe webhook signature",
                source="stripe"
            )
        
        try:
            # Parse signature header
            elements = {}
            for item in signature.split(","):
                key, value = item.split("=", 1)
                elements[key] = value
            
            timestamp = elements.get("t")
            v1_signature = elements.get("v1")
            
            if not timestamp or not v1_signature:
                raise WebhookSignatureError(
                    message="Invalid Stripe signature format",
                    source="stripe"
                )
            
            # Check timestamp
            current_time = int(time.time())
            webhook_time = int(timestamp)
            time_diff = abs(current_time - webhook_time)
            
            if time_diff > tolerance:
                raise WebhookTimestampError(
                    message=f"Stripe webhook timestamp expired (diff: {time_diff}s)",
                    timestamp_diff=time_diff
                )
            
            # Verify signature
            signed_payload = f"{timestamp}.{payload.decode()}"
            expected_signature = hmac.new(
                self.secret,
                signed_payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(expected_signature, v1_signature):
                raise WebhookSignatureError(
                    message="Invalid Stripe webhook signature",
                    source="stripe"
                )
            
            return {
                "valid": True,
                "timestamp": webhook_time,
                "time_diff": time_diff
            }
            
        except WebhookSignatureError:
            raise
        except Exception as e:
            raise WebhookSignatureError(
                message=f"Error verifying Stripe signature: {str(e)}",
                source="stripe"
            )


# ============================================================================
# Webhook Error Middleware
# ============================================================================

async def webhook_error_handler(request: Request, call_next):
    """
    Middleware for handling webhook errors.
    
    Catches all webhook-related exceptions and returns standardized error responses.
    """
    try:
        response = await call_next(request)
        return response
    
    except WebhookSignatureError as e:
        logger.warning(f"Webhook signature error: {e.message}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=ErrorResponseBuilder.build(e)
        )
    
    except WebhookTimestampError as e:
        logger.warning(f"Webhook timestamp error: {e.message}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponseBuilder.build(e)
        )
    
    except WebhookPayloadError as e:
        logger.warning(f"Webhook payload error: {e.message}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponseBuilder.build(e)
        )
    
    except WebhookProcessingError as e:
        logger.error(f"Webhook processing error: {e.message}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponseBuilder.build(e)
        )
    
    except RateLimitError as e:
        logger.warning(f"Rate limit exceeded: {e.message}")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=ErrorResponseBuilder.build(e)
        )
    
    except PARWAError as e:
        logger.error(f"PARWA error in webhook: {e.message}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponseBuilder.build(e)
        )
    
    except Exception as e:
        logger.exception(f"Unexpected error in webhook: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponseBuilder.build(e)
        )


# ============================================================================
# Webhook Retry Handler
# ============================================================================

class WebhookRetryHandler:
    """Handler for processing webhooks with retry logic"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0
    ):
        self.retry_config = RetryConfig(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay
        )
    
    @with_retry()
    async def process_with_retry(
        self,
        processor: Callable,
        payload: Dict[str, Any],
        event_type: str
    ) -> Any:
        """
        Process webhook with automatic retry on transient failures.
        
        Args:
            processor: Async function to process the webhook
            payload: Webhook payload
            event_type: Type of webhook event
        
        Returns:
            Result from processor
        """
        try:
            return await processor(payload, event_type)
        except Exception as e:
            # Wrap in WebhookProcessingError for retry logic
            raise WebhookProcessingError(
                message=f"Error processing {event_type}: {str(e)}",
                event_type=event_type,
                retryable=True
            )


# ============================================================================
# Payload Validation
# ============================================================================

class WebhookPayloadValidator:
    """Validator for webhook payloads"""
    
    @staticmethod
    def validate_shopify_order(payload: Dict[str, Any]) -> bool:
        """Validate Shopify order webhook payload"""
        required_fields = ["id", "email", "created_at"]
        errors = []
        
        for field in required_fields:
            if field not in payload:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            raise WebhookPayloadError(
                message="Invalid Shopify order payload",
                validation_errors=errors
            )
        
        return True
    
    @staticmethod
    def validate_shopify_customer(payload: Dict[str, Any]) -> bool:
        """Validate Shopify customer webhook payload"""
        required_fields = ["id"]
        errors = []
        
        for field in required_fields:
            if field not in payload:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            raise WebhookPayloadError(
                message="Invalid Shopify customer payload",
                validation_errors=errors
            )
        
        return True
    
    @staticmethod
    def validate_stripe_event(payload: Dict[str, Any]) -> bool:
        """Validate Stripe event webhook payload"""
        required_fields = ["id", "type", "data"]
        errors = []
        
        for field in required_fields:
            if field not in payload:
                errors.append(f"Missing required field: {field}")
        
        if "data" in payload and "object" not in payload.get("data", {}):
            errors.append("Missing data.object in Stripe event")
        
        if errors:
            raise WebhookPayloadError(
                message="Invalid Stripe event payload",
                validation_errors=errors
            )
        
        return True
    
    @staticmethod
    def validate_generic(payload: Dict[str, Any], required_fields: list) -> bool:
        """Validate generic payload with required fields"""
        errors = []
        
        for field in required_fields:
            if field not in payload:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            raise WebhookPayloadError(
                message="Invalid payload",
                validation_errors=errors
            )
        
        return True


# ============================================================================
# Error Logging Decorator
# ============================================================================

def log_webhook_errors(source: str):
    """
    Decorator to log webhook errors with context.
    
    Args:
        source: Webhook source (shopify, stripe, etc.)
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except WebhookError as e:
                logger.error(
                    f"[{source.upper()}] Webhook error: {e.error_code} - {e.message}",
                    extra={
                        "source": source,
                        "error_code": e.error_code,
                        "severity": e.severity.value,
                        "details": e.details
                    }
                )
                raise
            except Exception as e:
                logger.exception(
                    f"[{source.upper()}] Unexpected error: {str(e)}",
                    extra={"source": source}
                )
                raise WebhookProcessingError(
                    message=str(e),
                    event_type=source,
                    retryable=True
                )
        return wrapper
    return decorator


# ============================================================================
# Webhook Response Helpers
# ============================================================================

def success_response(message: str = "Webhook processed successfully") -> Dict[str, Any]:
    """Return success response for webhook"""
    return {
        "success": True,
        "message": message
    }


def pending_approval_response(
    event_id: str,
    event_type: str,
    reason: str
) -> Dict[str, Any]:
    """Return pending approval response for HITL workflows"""
    return {
        "success": True,
        "status": "pending_approval",
        "event_id": event_id,
        "event_type": event_type,
        "reason": reason,
        "message": "Event queued for human approval"
    }


def error_response(
    error: Exception,
    include_details: bool = False
) -> Dict[str, Any]:
    """Return error response for webhook"""
    if isinstance(error, PARWAError):
        response = error.to_dict()
        if not include_details:
            response.pop("details", None)
        return response
    
    return {
        "success": False,
        "error": str(error)
    }
