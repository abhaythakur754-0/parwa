"""
PARWA Paddle Client.

Paddle is a Merchant of Record (MoR) for SaaS businesses.
Handles: Payment processing, Tax compliance, Subscriptions, Chargebacks.

CRITICAL: Refund gate - Stripe/Paddle must NEVER be called without
a pending_approval record in the database. Any bypass is a critical bug.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import hashlib
import hmac
import asyncio
from enum import Enum
from dataclasses import dataclass

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class PaddleClientState(Enum):
    """Paddle Client state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class PaddleEnvironment(Enum):
    """Paddle environment types."""
    SANDBOX = "sandbox"
    PRODUCTION = "production"


@dataclass
class PendingApproval:
    """
    Required approval record for refund operations.

    CRITICAL: Paddle must NEVER be called without this record existing
    in the database. Any code path that reaches Paddle without this check
    is a critical bug.
    """
    approval_id: str
    transaction_id: str
    amount: float
    currency: str
    reason: str
    requested_by: str
    created_at: datetime
    status: str = "pending"  # pending, approved, denied


class PaddleClient:
    """
    Paddle Client for Merchant of Record operations.

    Features:
    - Subscription management (create, cancel, update)
    - Payment processing (via Paddle checkout)
    - Refund processing (REQUIRES approval gate)
    - Customer management
    - Webhook verification

    CRITICAL RULE:
    Stripe/Paddle must NEVER be called without a pending_approval record
    existing in the database. This rule cannot be overridden.
    """

    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3
    API_BASE_URL = "https://api.paddle.com"
    SANDBOX_API_BASE_URL = "https://sandbox-api.paddle.com"

    def __init__(
        self,
        client_token: Optional[str] = None,
        api_key: Optional[str] = None,
        environment: PaddleEnvironment = PaddleEnvironment.SANDBOX,
        timeout: int = DEFAULT_TIMEOUT
    ) -> None:
        """
        Initialize Paddle Client.

        Args:
            client_token: Paddle client token (reads from config if not provided)
            api_key: Paddle API key (reads from config if not provided)
            environment: Sandbox or Production
            timeout: Request timeout in seconds
        """
        self.client_token = client_token or (
            settings.paddle_client_token.get_secret_value()
            if settings.paddle_client_token else None
        )
        self.api_key = api_key or (
            settings.paddle_api_key.get_secret_value()
            if settings.paddle_api_key else None
        )
        self.environment = environment
        self.timeout = timeout
        self._state = PaddleClientState.DISCONNECTED
        self._last_request: Optional[datetime] = None
        self._webhook_secret = (
            settings.paddle_webhook_secret.get_secret_value()
            if settings.paddle_webhook_secret else None
        )

    @property
    def state(self) -> PaddleClientState:
        """Get current client state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._state == PaddleClientState.CONNECTED

    def _get_base_url(self) -> str:
        """Get the base API URL based on environment."""
        if self.environment == PaddleEnvironment.PRODUCTION:
            return self.API_BASE_URL
        return self.SANDBOX_API_BASE_URL

    def _validate_pending_approval(
        self,
        pending_approval: Optional[PendingApproval]
    ) -> bool:
        """
        Validate that a pending_approval record exists before refund.

        CRITICAL: This check must pass before any Paddle API call
        for refunds. Bypassing this check is a critical bug.

        Args:
            pending_approval: The approval record from database

        Returns:
            True if approval exists and is in pending/approved state
        """
        if pending_approval is None:
            logger.error({
                "event": "paddle_refund_gate_violation",
                "error": "No pending_approval record provided",
                "critical": True,
            })
            return False

        if pending_approval.status not in ("pending", "approved"):
            logger.error({
                "event": "paddle_refund_gate_invalid_status",
                "approval_id": pending_approval.approval_id,
                "status": pending_approval.status,
            })
            return False

        logger.info({
            "event": "paddle_refund_gate_passed",
            "approval_id": pending_approval.approval_id,
            "transaction_id": pending_approval.transaction_id,
        })

        return True

    async def connect(self) -> bool:
        """
        Connect to Paddle API.

        Validates credentials by fetching catalog info.

        Returns:
            True if connected successfully
        """
        if self._state == PaddleClientState.CONNECTED:
            return True

        self._state = PaddleClientState.CONNECTING

        if not self.api_key:
            self._state = PaddleClientState.ERROR
            logger.error({"event": "paddle_missing_api_key"})
            return False

        try:
            # Simulate connection validation
            await asyncio.sleep(0.1)

            self._state = PaddleClientState.CONNECTED
            self._last_request = datetime.now(timezone.utc)

            logger.info({
                "event": "paddle_client_connected",
                "environment": self.environment.value,
            })

            return True

        except Exception as e:
            self._state = PaddleClientState.ERROR
            logger.error({
                "event": "paddle_connection_failed",
                "error": str(e),
                "environment": self.environment.value,
            })
            return False

    async def disconnect(self) -> None:
        """Disconnect from Paddle API."""
        self._state = PaddleClientState.DISCONNECTED
        self._last_request = None

        logger.info({
            "event": "paddle_client_disconnected",
            "environment": self.environment.value,
        })

    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """
        Create a new subscription.

        Args:
            customer_id: Paddle customer ID
            plan_id: Paddle price/plan ID
            quantity: Number of seats/units

        Returns:
            Subscription data dictionary
        """
        if not self.is_connected:
            raise ValueError("Paddle client not connected")

        if not customer_id:
            raise ValueError("Customer ID is required")

        if not plan_id:
            raise ValueError("Plan ID is required")

        if quantity < 1:
            raise ValueError("Quantity must be at least 1")

        logger.info({
            "event": "paddle_subscription_create",
            "customer_id": customer_id,
            "plan_id": plan_id,
            "quantity": quantity,
        })

        # Simulated subscription creation
        return {
            "id": "sub_" + hashlib.md5(
                f"{customer_id}{plan_id}".encode()
            ).hexdigest()[:16],
            "customer_id": customer_id,
            "plan_id": plan_id,
            "quantity": quantity,
            "status": "active",
            "current_billing_period": {
                "starts_at": datetime.now(timezone.utc).isoformat(),
                "ends_at": datetime.now(timezone.utc).isoformat(),
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_subscription(
        self,
        subscription_id: str
    ) -> Dict[str, Any]:
        """
        Get subscription details.

        Args:
            subscription_id: Paddle subscription ID

        Returns:
            Subscription data dictionary
        """
        if not self.is_connected:
            raise ValueError("Paddle client not connected")

        if not subscription_id:
            raise ValueError("Subscription ID is required")

        logger.info({
            "event": "paddle_subscription_get",
            "subscription_id": subscription_id,
        })

        # Simulated subscription fetch
        return {
            "id": subscription_id,
            "status": "active",
            "current_billing_period": {
                "starts_at": datetime.now(timezone.utc).isoformat(),
                "ends_at": datetime.now(timezone.utc).isoformat(),
            },
            "items": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def cancel_subscription(
        self,
        subscription_id: str,
        effective_from: str = "next_billing_period"
    ) -> Dict[str, Any]:
        """
        Cancel a subscription.

        Args:
            subscription_id: Paddle subscription ID
            effective_from: When to cancel (immediately, next_billing_period)

        Returns:
            Cancellation result dictionary
        """
        if not self.is_connected:
            raise ValueError("Paddle client not connected")

        if not subscription_id:
            raise ValueError("Subscription ID is required")

        valid_effective = {"immediately", "next_billing_period"}
        if effective_from not in valid_effective:
            raise ValueError(
                f"effective_from must be one of: {valid_effective}"
            )

        logger.info({
            "event": "paddle_subscription_cancel",
            "subscription_id": subscription_id,
            "effective_from": effective_from,
        })

        # Simulated cancellation
        return {
            "id": subscription_id,
            "status": "canceled" if effective_from == "immediately" else "active",
            "scheduled_change": {
                "action": "cancel",
                "effective_at": datetime.now(timezone.utc).isoformat(),
            } if effective_from == "next_billing_period" else None,
            "canceled_at": (
                datetime.now(timezone.utc).isoformat()
                if effective_from == "immediately" else None
            ),
        }

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Get customer details.

        Args:
            customer_id: Paddle customer ID

        Returns:
            Customer data dictionary
        """
        if not self.is_connected:
            raise ValueError("Paddle client not connected")

        if not customer_id:
            raise ValueError("Customer ID is required")

        logger.info({
            "event": "paddle_customer_get",
            "customer_id": customer_id,
        })

        # Simulated customer fetch
        return {
            "id": customer_id,
            "email": "customer@example.com",
            "name": "John Doe",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def process_refund(
        self,
        transaction_id: str,
        amount: float,
        reason: str,
        pending_approval: Optional[PendingApproval] = None
    ) -> Dict[str, Any]:
        """
        Process a refund.

        CRITICAL: This method requires a pending_approval record.
        Calling without approval is a critical bug that must be prevented.

        Args:
            transaction_id: Paddle transaction ID
            amount: Refund amount (must match approval)
            reason: Refund reason
            pending_approval: REQUIRED approval record from database

        Returns:
            Refund result dictionary

        Raises:
            ValueError: If pending_approval is missing or invalid
        """
        if not self.is_connected:
            raise ValueError("Paddle client not connected")

        if not transaction_id:
            raise ValueError("Transaction ID is required")

        if amount <= 0:
            raise ValueError("Amount must be positive")

        # CRITICAL: Validate pending approval before ANY Paddle API call
        if not self._validate_pending_approval(pending_approval):
            raise ValueError(
                "CRITICAL: Refund cannot be processed without valid "
                "pending_approval record. This is a security violation."
            )

        # Additional validation: amount must match approval
        if pending_approval and pending_approval.amount != amount:
            raise ValueError(
                f"Amount mismatch: requested {amount}, "
                f"approved {pending_approval.amount}"
            )

        logger.info({
            "event": "paddle_refund_processed",
            "transaction_id": transaction_id,
            "amount": amount,
            "approval_id": pending_approval.approval_id if pending_approval else None,
        })

        # Simulated refund processing
        return {
            "id": "ref_" + hashlib.md5(transaction_id.encode()).hexdigest()[:16],
            "transaction_id": transaction_id,
            "amount": str(amount),
            "currency": pending_approval.currency if pending_approval else "USD",
            "status": "processed",
            "reason": reason,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_transaction(
        self,
        transaction_id: str
    ) -> Dict[str, Any]:
        """
        Get transaction details.

        Args:
            transaction_id: Paddle transaction ID

        Returns:
            Transaction data dictionary
        """
        if not self.is_connected:
            raise ValueError("Paddle client not connected")

        if not transaction_id:
            raise ValueError("Transaction ID is required")

        logger.info({
            "event": "paddle_transaction_get",
            "transaction_id": transaction_id,
        })

        # Simulated transaction fetch
        return {
            "id": transaction_id,
            "status": "completed",
            "amount": "99.99",
            "currency": "USD",
            "customer_id": "ctm_test",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def list_transactions(
        self,
        customer_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List transactions.

        Args:
            customer_id: Filter by customer ID
            subscription_id: Filter by subscription ID
            limit: Maximum results (max 200)

        Returns:
            List of transaction dictionaries
        """
        if not self.is_connected:
            raise ValueError("Paddle client not connected")

        if limit < 1 or limit > 200:
            raise ValueError("Limit must be between 1 and 200")

        logger.info({
            "event": "paddle_transactions_list",
            "customer_id": customer_id,
            "subscription_id": subscription_id,
            "limit": limit,
        })

        # Simulated transactions list
        return []

    def verify_webhook(
        self,
        payload: bytes,
        signature: str
    ) -> bool:
        """
        Verify webhook signature from Paddle.

        Args:
            payload: Raw webhook payload bytes
            signature: Paddle-Signature header value

        Returns:
            True if signature is valid
        """
        if not self._webhook_secret:
            logger.error({"event": "paddle_webhook_no_secret"})
            return False

        if not payload or not signature:
            return False

        try:
            # Paddle uses HMAC-SHA256 for webhook verification
            expected_signature = hmac.new(
                self._webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()

            is_valid = hmac.compare_digest(
                expected_signature,
                signature
            )

            logger.info({
                "event": "paddle_webhook_verification",
                "valid": is_valid,
            })

            return is_valid

        except Exception as e:
            logger.error({
                "event": "paddle_webhook_verification_error",
                "error": str(e),
            })
            return False

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Paddle connection.

        Returns:
            Health status dictionary
        """
        return {
            "healthy": self._state == PaddleClientState.CONNECTED,
            "state": self._state.value,
            "environment": self.environment.value,
            "last_request": (
                self._last_request.isoformat()
                if self._last_request else None
            ),
        }
