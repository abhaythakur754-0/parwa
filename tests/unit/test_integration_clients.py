"""
Unit tests for PARWA Integration Clients.

Tests for:
- ShopifyClient: E-commerce store integration
- PaddleClient: Merchant of Record with refund gate
- TwilioClient: SMS and Voice communication
- EmailClient: Transactional email via Brevo
- ZendeskClient: Ticketing system integration
- GitHubClient: Repository access for code-related support
- AfterShipClient: Shipment tracking
- EpicEHRClient: Healthcare EHR (read-only, BAA required)

CRITICAL: 
- Paddle refund gate tests ensure no refunds can be processed without approval.
- Epic EHR tests ensure BAA verification and read-only enforcement.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from shared.integrations.shopify_client import (
    ShopifyClient,
    ShopifyClientState,
)
from shared.integrations.paddle_client import (
    PaddleClient,
    PaddleClientState,
    PaddleEnvironment,
    PendingApproval,
)
from shared.integrations.twilio_client import (
    TwilioClient,
    TwilioClientState,
    MessageStatus,
    CallStatus,
)
from shared.integrations.email_client import (
    EmailClient,
    EmailClientState,
    EmailStatus,
    EmailPriority,
)
from shared.integrations.zendesk_client import (
    ZendeskClient,
    ZendeskClientState,
    TicketStatus,
    TicketPriority,
)
from shared.integrations.github_client import (
    GitHubClient,
    GitHubClientState,
)
from shared.integrations.aftership_client import (
    AfterShipClient,
    AfterShipClientState,
    TrackingStatus,
)
from shared.integrations.epic_ehr_client import (
    EpicEHRClient,
    EpicEHRClientState,
    EHRAccessLevel,
)


# ═══════════════════════════════════════════════════════════════════════════════
# SHOPIFY CLIENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestShopifyClient:
    """Tests for Shopify client."""

    @pytest.fixture
    def shopify_client(self):
        """Create a Shopify client instance."""
        return ShopifyClient(
            store_url="test-store.myshopify.com",
            api_key="test_api_key",
            api_secret="test_api_secret",
        )

    @pytest.mark.asyncio
    async def test_connect_success(self, shopify_client):
        """Test successful connection to Shopify."""
        result = await shopify_client.connect()
        assert result is True
        assert shopify_client.state == ShopifyClientState.CONNECTED
        assert shopify_client.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_missing_store_url(self):
        """Test connection fails without store URL."""
        client = ShopifyClient(store_url=None, api_key="test")
        result = await client.connect()
        assert result is False
        assert client.state == ShopifyClientState.ERROR

    @pytest.mark.asyncio
    async def test_connect_missing_api_key(self):
        """Test connection fails without API key."""
        with patch("shared.integrations.shopify_client.settings") as mock_settings:
            mock_settings.shopify_api_key = None
            mock_settings.shopify_api_secret = None
            client = ShopifyClient(store_url="test.myshopify.com", api_key=None)
            result = await client.connect()
            assert result is False
            assert client.state == ShopifyClientState.ERROR

    @pytest.mark.asyncio
    async def test_disconnect(self, shopify_client):
        """Test disconnection."""
        await shopify_client.connect()
        await shopify_client.disconnect()
        assert shopify_client.state == ShopifyClientState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_get_product(self, shopify_client):
        """Test getting a product by ID."""
        await shopify_client.connect()
        product = await shopify_client.get_product("12345")
        assert product["id"] == "12345"
        assert "title" in product
        assert "status" in product

    @pytest.mark.asyncio
    async def test_get_product_not_connected(self, shopify_client):
        """Test getting product fails when not connected."""
        with pytest.raises(ValueError, match="not connected"):
            await shopify_client.get_product("12345")

    @pytest.mark.asyncio
    async def test_get_product_missing_id(self, shopify_client):
        """Test getting product fails without ID."""
        await shopify_client.connect()
        with pytest.raises(ValueError, match="Product ID is required"):
            await shopify_client.get_product("")

    @pytest.mark.asyncio
    async def test_get_products(self, shopify_client):
        """Test getting products list."""
        await shopify_client.connect()
        products = await shopify_client.get_products(limit=10)
        assert isinstance(products, list)

    @pytest.mark.asyncio
    async def test_get_products_invalid_limit(self, shopify_client):
        """Test getting products with invalid limit."""
        await shopify_client.connect()
        with pytest.raises(ValueError, match="between 1 and 250"):
            await shopify_client.get_products(limit=0)
        with pytest.raises(ValueError, match="between 1 and 250"):
            await shopify_client.get_products(limit=500)

    @pytest.mark.asyncio
    async def test_get_order(self, shopify_client):
        """Test getting an order by ID."""
        await shopify_client.connect()
        order = await shopify_client.get_order("67890")
        assert order["id"] == "67890"
        assert "email" in order
        assert "financial_status" in order

    @pytest.mark.asyncio
    async def test_get_orders(self, shopify_client):
        """Test getting orders list."""
        await shopify_client.connect()
        orders = await shopify_client.get_orders(limit=10, status="open")
        assert isinstance(orders, list)

    @pytest.mark.asyncio
    async def test_get_orders_invalid_status(self, shopify_client):
        """Test getting orders with invalid status."""
        await shopify_client.connect()
        with pytest.raises(ValueError, match="Status must be one of"):
            await shopify_client.get_orders(status="invalid")

    @pytest.mark.asyncio
    async def test_get_customer(self, shopify_client):
        """Test getting a customer by ID."""
        await shopify_client.connect()
        customer = await shopify_client.get_customer("cust_123")
        assert customer["id"] == "cust_123"
        assert "email" in customer

    @pytest.mark.asyncio
    async def test_get_customer_by_email(self, shopify_client):
        """Test searching customer by email."""
        await shopify_client.connect()
        customer = await shopify_client.get_customer_by_email("test@example.com")
        # Returns None if not found in mock
        assert customer is None or "email" in customer

    @pytest.mark.asyncio
    async def test_get_inventory(self, shopify_client):
        """Test getting inventory levels."""
        await shopify_client.connect()
        inventory = await shopify_client.get_inventory(["item_1", "item_2"])
        assert isinstance(inventory, list)
        assert len(inventory) == 2

    def test_verify_webhook_valid(self, shopify_client):
        """Test webhook verification with valid signature."""
        payload = b'{"test": "data"}'
        # Create a valid signature
        import hmac
        import hashlib
        valid_signature = hmac.new(
            b"test_api_secret",
            payload,
            hashlib.sha256
        ).hexdigest()

        result = shopify_client.verify_webhook(payload, valid_signature)
        assert result is True

    def test_verify_webhook_invalid(self, shopify_client):
        """Test webhook verification with invalid signature."""
        payload = b'{"test": "data"}'
        result = shopify_client.verify_webhook(payload, "invalid_signature")
        assert result is False

    def test_verify_webhook_no_secret(self):
        """Test webhook verification fails without secret."""
        client = ShopifyClient(
            store_url="test.myshopify.com",
            api_key="test",
            api_secret=None,
        )
        result = client.verify_webhook(b"data", "sig")
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check(self, shopify_client):
        """Test health check."""
        await shopify_client.connect()
        health = await shopify_client.health_check()
        assert health["healthy"] is True
        assert health["state"] == ShopifyClientState.CONNECTED.value
        assert health["store_url"] == "test-store.myshopify.com"


# ═══════════════════════════════════════════════════════════════════════════════
# PADDLE CLIENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPaddleClient:
    """Tests for Paddle client with critical refund gate tests."""

    @pytest.fixture
    def paddle_client(self):
        """Create a Paddle client instance."""
        return PaddleClient(
            client_token="test_client_token",
            api_key="test_api_key",
            environment=PaddleEnvironment.SANDBOX,
        )

    @pytest.fixture
    def pending_approval(self):
        """Create a pending approval record."""
        return PendingApproval(
            approval_id="approval_123",
            transaction_id="txn_456",
            amount=99.99,
            currency="USD",
            reason="Customer request",
            requested_by="agent_1",
            created_at=datetime.now(timezone.utc),
            status="pending",
        )

    @pytest.mark.asyncio
    async def test_connect_success(self, paddle_client):
        """Test successful connection to Paddle."""
        result = await paddle_client.connect()
        assert result is True
        assert paddle_client.state == PaddleClientState.CONNECTED
        assert paddle_client.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_missing_api_key(self):
        """Test connection fails without API key."""
        client = PaddleClient(api_key=None)
        result = await client.connect()
        assert result is False
        assert client.state == PaddleClientState.ERROR

    @pytest.mark.asyncio
    async def test_disconnect(self, paddle_client):
        """Test disconnection."""
        await paddle_client.connect()
        await paddle_client.disconnect()
        assert paddle_client.state == PaddleClientState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_create_subscription(self, paddle_client):
        """Test creating a subscription."""
        await paddle_client.connect()
        subscription = await paddle_client.create_subscription(
            customer_id="cust_123",
            plan_id="plan_456",
            quantity=1,
        )
        assert subscription["customer_id"] == "cust_123"
        assert subscription["plan_id"] == "plan_456"
        assert subscription["status"] == "active"

    @pytest.mark.asyncio
    async def test_create_subscription_missing_customer(self, paddle_client):
        """Test subscription creation fails without customer ID."""
        await paddle_client.connect()
        with pytest.raises(ValueError, match="Customer ID is required"):
            await paddle_client.create_subscription("", "plan_456")

    @pytest.mark.asyncio
    async def test_create_subscription_invalid_quantity(self, paddle_client):
        """Test subscription creation fails with invalid quantity."""
        await paddle_client.connect()
        with pytest.raises(ValueError, match="Quantity must be at least 1"):
            await paddle_client.create_subscription("cust_123", "plan_456", quantity=0)

    @pytest.mark.asyncio
    async def test_get_subscription(self, paddle_client):
        """Test getting a subscription."""
        await paddle_client.connect()
        subscription = await paddle_client.get_subscription("sub_123")
        assert subscription["id"] == "sub_123"
        assert subscription["status"] == "active"

    @pytest.mark.asyncio
    async def test_cancel_subscription(self, paddle_client):
        """Test canceling a subscription."""
        await paddle_client.connect()
        result = await paddle_client.cancel_subscription(
            subscription_id="sub_123",
            effective_from="next_billing_period",
        )
        assert result["id"] == "sub_123"

    @pytest.mark.asyncio
    async def test_cancel_subscription_invalid_effective(self, paddle_client):
        """Test cancellation fails with invalid effective_from."""
        await paddle_client.connect()
        with pytest.raises(ValueError, match="effective_from must be one of"):
            await paddle_client.cancel_subscription("sub_123", effective_from="invalid")

    @pytest.mark.asyncio
    async def test_get_customer(self, paddle_client):
        """Test getting customer details."""
        await paddle_client.connect()
        customer = await paddle_client.get_customer("cust_123")
        assert customer["id"] == "cust_123"
        assert "email" in customer

    # CRITICAL REFUND GATE TESTS

    @pytest.mark.asyncio
    async def test_refund_gate_blocks_without_approval(self, paddle_client):
        """CRITICAL: Refund must be blocked without pending_approval."""
        await paddle_client.connect()

        with pytest.raises(ValueError, match="pending_approval record"):
            await paddle_client.process_refund(
                transaction_id="txn_123",
                amount=99.99,
                reason="Test",
                pending_approval=None,  # NO APPROVAL - MUST BE BLOCKED
            )

    @pytest.mark.asyncio
    async def test_refund_gate_blocks_with_denied_approval(self, paddle_client):
        """CRITICAL: Refund must be blocked if approval is denied."""
        await paddle_client.connect()

        denied_approval = PendingApproval(
            approval_id="approval_denied",
            transaction_id="txn_123",
            amount=99.99,
            currency="USD",
            reason="Test",
            requested_by="agent_1",
            created_at=datetime.now(timezone.utc),
            status="denied",  # DENIED - MUST BE BLOCKED
        )

        with pytest.raises(ValueError, match="pending_approval record"):
            await paddle_client.process_refund(
                transaction_id="txn_123",
                amount=99.99,
                reason="Test",
                pending_approval=denied_approval,
            )

    @pytest.mark.asyncio
    async def test_refund_gate_blocks_amount_mismatch(self, paddle_client, pending_approval):
        """CRITICAL: Refund must be blocked if amount doesn't match approval."""
        await paddle_client.connect()

        with pytest.raises(ValueError, match="Amount mismatch"):
            await paddle_client.process_refund(
                transaction_id="txn_456",
                amount=50.00,  # Different from approved amount (99.99)
                reason="Test",
                pending_approval=pending_approval,
            )

    @pytest.mark.asyncio
    async def test_refund_succeeds_with_valid_approval(self, paddle_client, pending_approval):
        """Refund succeeds with valid pending_approval."""
        await paddle_client.connect()

        result = await paddle_client.process_refund(
            transaction_id="txn_456",
            amount=99.99,  # Matches approved amount
            reason="Customer request",
            pending_approval=pending_approval,
        )

        assert result["transaction_id"] == "txn_456"
        assert result["status"] == "processed"
        assert result["amount"] == "99.99"

    @pytest.mark.asyncio
    async def test_refund_gate_with_approved_status(self, paddle_client):
        """Refund succeeds when approval status is 'approved'."""
        await paddle_client.connect()

        approved = PendingApproval(
            approval_id="approval_approved",
            transaction_id="txn_789",
            amount=50.00,
            currency="USD",
            reason="Test",
            requested_by="agent_1",
            created_at=datetime.now(timezone.utc),
            status="approved",  # APPROVED - SHOULD WORK
        )

        result = await paddle_client.process_refund(
            transaction_id="txn_789",
            amount=50.00,
            reason="Test",
            pending_approval=approved,
        )

        assert result["status"] == "processed"

    @pytest.mark.asyncio
    async def test_refund_invalid_amount(self, paddle_client, pending_approval):
        """Test refund fails with invalid amount."""
        await paddle_client.connect()

        with pytest.raises(ValueError, match="Amount must be positive"):
            await paddle_client.process_refund(
                transaction_id="txn_456",
                amount=0,
                reason="Test",
                pending_approval=pending_approval,
            )

    @pytest.mark.asyncio
    async def test_get_transaction(self, paddle_client):
        """Test getting transaction details."""
        await paddle_client.connect()
        transaction = await paddle_client.get_transaction("txn_123")
        assert transaction["id"] == "txn_123"
        assert transaction["status"] == "completed"

    @pytest.mark.asyncio
    async def test_list_transactions(self, paddle_client):
        """Test listing transactions."""
        await paddle_client.connect()
        transactions = await paddle_client.list_transactions(limit=10)
        assert isinstance(transactions, list)

    def test_verify_webhook(self, paddle_client):
        """Test webhook verification."""
        paddle_client._webhook_secret = "test_secret"
        payload = b'{"test": "data"}'

        import hmac
        import hashlib
        valid_signature = hmac.new(
            b"test_secret",
            payload,
            hashlib.sha256
        ).hexdigest()

        result = paddle_client.verify_webhook(payload, valid_signature)
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check(self, paddle_client):
        """Test health check."""
        await paddle_client.connect()
        health = await paddle_client.health_check()
        assert health["healthy"] is True
        assert health["environment"] == PaddleEnvironment.SANDBOX.value


# ═══════════════════════════════════════════════════════════════════════════════
# TWILIO CLIENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTwilioClient:
    """Tests for Twilio client."""

    @pytest.fixture
    def twilio_client(self):
        """Create a Twilio client instance."""
        return TwilioClient(
            account_sid="ACtest123",
            auth_token="test_auth_token",
            api_key="test_api_key",
            phone_number="+1234567890",
        )

    @pytest.mark.asyncio
    async def test_connect_success(self, twilio_client):
        """Test successful connection to Twilio."""
        result = await twilio_client.connect()
        assert result is True
        assert twilio_client.state == TwilioClientState.CONNECTED

    @pytest.mark.asyncio
    async def test_connect_missing_account_sid(self):
        """Test connection fails without Account SID."""
        with patch("shared.integrations.twilio_client.settings") as mock_settings:
            mock_settings.twilio_account_sid = None
            mock_settings.twilio_auth_token = None
            mock_settings.twilio_api_key = None
            mock_settings.twilio_phone_number = None
            client = TwilioClient(account_sid=None, auth_token="test")
            result = await client.connect()
            assert result is False
            assert client.state == TwilioClientState.ERROR

    @pytest.mark.asyncio
    async def test_connect_missing_auth_token(self):
        """Test connection fails without Auth Token."""
        with patch("shared.integrations.twilio_client.settings") as mock_settings:
            mock_settings.twilio_account_sid = "ACtest"
            mock_settings.twilio_auth_token = None
            mock_settings.twilio_api_key = None
            mock_settings.twilio_phone_number = None
            client = TwilioClient(account_sid="ACtest", auth_token=None)
            result = await client.connect()
            assert result is False
            assert client.state == TwilioClientState.ERROR

    @pytest.mark.asyncio
    async def test_send_sms(self, twilio_client):
        """Test sending SMS."""
        await twilio_client.connect()
        result = await twilio_client.send_sms(
            to="+19876543210",
            body="Test message",
        )
        assert result["to"] == "+19876543210"
        assert result["body"] == "Test message"
        assert result["status"] == MessageStatus.QUEUED.value
        assert result["sid"].startswith("SM")

    @pytest.mark.asyncio
    async def test_send_sms_missing_recipient(self, twilio_client):
        """Test SMS fails without recipient."""
        await twilio_client.connect()
        with pytest.raises(ValueError, match="Recipient phone number"):
            await twilio_client.send_sms(to="", body="Test")

    @pytest.mark.asyncio
    async def test_send_sms_missing_body(self, twilio_client):
        """Test SMS fails without body."""
        await twilio_client.connect()
        with pytest.raises(ValueError, match="Message body"):
            await twilio_client.send_sms(to="+19876543210", body="")

    @pytest.mark.asyncio
    async def test_send_sms_body_too_long(self, twilio_client):
        """Test SMS fails if body exceeds limit."""
        await twilio_client.connect()
        with pytest.raises(ValueError, match="exceeds 1600 characters"):
            await twilio_client.send_sms(to="+19876543210", body="x" * 1601)

    @pytest.mark.asyncio
    async def test_send_sms_missing_from_number(self):
        """Test SMS fails without sender number."""
        with patch("shared.integrations.twilio_client.settings") as mock_settings:
            mock_settings.twilio_account_sid = "ACtest"
            mock_settings.twilio_auth_token = MagicMock()
            mock_settings.twilio_auth_token.get_secret_value = MagicMock(
                return_value="test_token"
            )
            mock_settings.twilio_api_key = None
            mock_settings.twilio_phone_number = None
            client = TwilioClient(
                account_sid="ACtest",
                auth_token="test",
                phone_number=None,
            )
            await client.connect()
            with pytest.raises(ValueError, match="Sender phone number"):
                await client.send_sms(to="+19876543210", body="Test")

    @pytest.mark.asyncio
    async def test_get_message_status(self, twilio_client):
        """Test getting message status."""
        await twilio_client.connect()
        status = await twilio_client.get_message_status("SM123")
        assert status["sid"] == "SM123"
        assert status["status"] in [s.value for s in MessageStatus]

    @pytest.mark.asyncio
    async def test_send_whatsapp(self, twilio_client):
        """Test sending WhatsApp message."""
        await twilio_client.connect()
        result = await twilio_client.send_whatsapp(
            to="+19876543210",
            body="WhatsApp test",
        )
        assert result["to"] == "whatsapp:+19876543210"
        assert result["from"] == "whatsapp:+1234567890"

    @pytest.mark.asyncio
    async def test_make_call(self, twilio_client):
        """Test initiating a voice call."""
        await twilio_client.connect()
        result = await twilio_client.make_call(
            to="+19876543210",
            url="https://example.com/twiml",
        )
        assert result["to"] == "+19876543210"
        assert result["status"] == CallStatus.QUEUED.value
        assert result["sid"].startswith("CA")

    @pytest.mark.asyncio
    async def test_make_call_missing_url(self, twilio_client):
        """Test call fails without TwiML URL."""
        await twilio_client.connect()
        with pytest.raises(ValueError, match="TwiML URL"):
            await twilio_client.make_call(to="+19876543210", url="")

    @pytest.mark.asyncio
    async def test_make_call_invalid_timeout(self, twilio_client):
        """Test call fails with invalid timeout."""
        await twilio_client.connect()
        with pytest.raises(ValueError, match="between 1 and 600"):
            await twilio_client.make_call(
                to="+19876543210",
                url="https://example.com/twiml",
                timeout=700,
            )

    @pytest.mark.asyncio
    async def test_get_call_status(self, twilio_client):
        """Test getting call status."""
        await twilio_client.connect()
        status = await twilio_client.get_call_status("CA123")
        assert status["sid"] == "CA123"

    @pytest.mark.asyncio
    async def test_validate_phone_number(self, twilio_client):
        """Test phone number validation."""
        await twilio_client.connect()
        result = await twilio_client.validate_phone_number("+1234567890")
        assert "valid" in result
        assert "carrier" in result

    @pytest.mark.asyncio
    async def test_list_messages(self, twilio_client):
        """Test listing messages."""
        await twilio_client.connect()
        messages = await twilio_client.list_messages(limit=10)
        assert isinstance(messages, list)

    @pytest.mark.asyncio
    async def test_health_check(self, twilio_client):
        """Test health check."""
        await twilio_client.connect()
        health = await twilio_client.health_check()
        assert health["healthy"] is True
        assert health["phone_number"] == "+1234567890"


# ═══════════════════════════════════════════════════════════════════════════════
# EMAIL CLIENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmailClient:
    """Tests for Email client (Brevo)."""

    @pytest.fixture
    def email_client(self):
        """Create an Email client instance."""
        return EmailClient(
            api_key="test_brevo_api_key",
            from_email="support@parwa.ai",
            from_name="PARWA Support",
        )

    @pytest.mark.asyncio
    async def test_connect_success(self, email_client):
        """Test successful connection to Brevo."""
        result = await email_client.connect()
        assert result is True
        assert email_client.state == EmailClientState.CONNECTED

    @pytest.mark.asyncio
    async def test_connect_missing_api_key(self):
        """Test connection fails without API key."""
        client = EmailClient(api_key=None)
        result = await client.connect()
        assert result is False
        assert client.state == EmailClientState.ERROR

    @pytest.mark.asyncio
    async def test_send_email(self, email_client):
        """Test sending an email."""
        await email_client.connect()
        result = await email_client.send_email(
            to="recipient@example.com",
            subject="Test Subject",
            html_content="<p>Test content</p>",
        )
        assert result["to"] == ["recipient@example.com"]
        assert result["subject"] == "Test Subject"
        assert result["status"] == EmailStatus.QUEUED.value
        assert result["message_id"] is not None

    @pytest.mark.asyncio
    async def test_send_email_multiple_recipients(self, email_client):
        """Test sending email to multiple recipients."""
        await email_client.connect()
        result = await email_client.send_email(
            to=["user1@example.com", "user2@example.com"],
            subject="Multi-recipient",
            html_content="<p>Content</p>",
        )
        assert len(result["to"]) == 2

    @pytest.mark.asyncio
    async def test_send_email_missing_recipient(self, email_client):
        """Test email fails without recipient."""
        await email_client.connect()
        with pytest.raises(ValueError, match="Recipient email"):
            await email_client.send_email(
                to="",
                subject="Test",
                html_content="<p>Content</p>",
            )

    @pytest.mark.asyncio
    async def test_send_email_missing_subject(self, email_client):
        """Test email fails without subject."""
        await email_client.connect()
        with pytest.raises(ValueError, match="subject"):
            await email_client.send_email(
                to="test@example.com",
                subject="",
                html_content="<p>Content</p>",
            )

    @pytest.mark.asyncio
    async def test_send_email_missing_content(self, email_client):
        """Test email fails without content."""
        await email_client.connect()
        with pytest.raises(ValueError, match="content"):
            await email_client.send_email(
                to="test@example.com",
                subject="Test",
                html_content="",
            )

    @pytest.mark.asyncio
    async def test_send_email_invalid_email(self, email_client):
        """Test email fails with invalid email format."""
        await email_client.connect()
        with pytest.raises(ValueError, match="Invalid email"):
            await email_client.send_email(
                to="not-an-email",
                subject="Test",
                html_content="<p>Content</p>",
            )

    @pytest.mark.asyncio
    async def test_send_template_email(self, email_client):
        """Test sending template email."""
        await email_client.connect()
        result = await email_client.send_template_email(
            to="test@example.com",
            template_id=123,
            params={"name": "John"},
        )
        assert result["template_id"] == 123
        assert result["status"] == EmailStatus.QUEUED.value

    @pytest.mark.asyncio
    async def test_send_template_email_missing_template(self, email_client):
        """Test template email fails without template ID."""
        await email_client.connect()
        with pytest.raises(ValueError, match="Template ID"):
            await email_client.send_template_email(
                to="test@example.com",
                template_id=None,
            )

    @pytest.mark.asyncio
    async def test_get_email_status(self, email_client):
        """Test getting email status."""
        await email_client.connect()
        status = await email_client.get_email_status("msg_123")
        assert status["message_id"] == "msg_123"
        assert status["status"] in [s.value for s in EmailStatus]

    @pytest.mark.asyncio
    async def test_send_bulk_email(self, email_client):
        """Test sending bulk emails."""
        await email_client.connect()
        recipients = [
            {"email": "user1@example.com", "name": "User 1"},
            {"email": "user2@example.com", "name": "User 2"},
        ]
        result = await email_client.send_bulk_email(
            recipients=recipients,
            subject="Bulk Test",
            html_content="<p>Content</p>",
        )
        assert result["recipient_count"] == 2
        assert result["batch_id"] is not None

    @pytest.mark.asyncio
    async def test_send_bulk_email_too_many(self, email_client):
        """Test bulk email fails with too many recipients."""
        await email_client.connect()
        recipients = [{"email": f"user{i}@example.com"} for i in range(10001)]
        with pytest.raises(ValueError, match="Maximum 10,000"):
            await email_client.send_bulk_email(
                recipients=recipients,
                subject="Test",
                html_content="<p>Content</p>",
            )

    @pytest.mark.asyncio
    async def test_create_contact(self, email_client):
        """Test creating a contact."""
        await email_client.connect()
        result = await email_client.create_contact(
            email="new@example.com",
            attributes={"FIRSTNAME": "John", "LASTNAME": "Doe"},
        )
        assert result["email"] == "new@example.com"
        assert result["id"] is not None

    @pytest.mark.asyncio
    async def test_get_templates(self, email_client):
        """Test getting email templates."""
        await email_client.connect()
        templates = await email_client.get_templates()
        assert isinstance(templates, list)

    def test_validate_email_format_valid(self, email_client):
        """Test email validation with valid emails."""
        assert email_client._validate_email_format("test@example.com") is True
        assert email_client._validate_email_format("user.name@domain.co.uk") is True

    def test_validate_email_format_invalid(self, email_client):
        """Test email validation with invalid emails."""
        assert email_client._validate_email_format("") is False
        assert email_client._validate_email_format("not-an-email") is False
        assert email_client._validate_email_format("missing@domain") is False
        assert email_client._validate_email_format("@nodomain.com") is False

    @pytest.mark.asyncio
    async def test_health_check(self, email_client):
        """Test health check."""
        await email_client.connect()
        health = await email_client.health_check()
        assert health["healthy"] is True
        assert health["from_email"] == "support@parwa.ai"


# ═══════════════════════════════════════════════════════════════════════════════
# ZENDESK CLIENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestZendeskClient:
    """Tests for Zendesk client."""

    @pytest.fixture
    def zendesk_client(self):
        """Create a Zendesk client instance."""
        return ZendeskClient(
            subdomain="testcompany",
            email="agent@testcompany.zendesk.com",
            api_key="test_zendesk_api_key",
        )

    @pytest.mark.asyncio
    async def test_connect_success(self, zendesk_client):
        """Test successful connection to Zendesk."""
        result = await zendesk_client.connect()
        assert result is True
        assert zendesk_client.state == ZendeskClientState.CONNECTED

    @pytest.mark.asyncio
    async def test_connect_missing_subdomain(self):
        """Test connection fails without subdomain."""
        client = ZendeskClient(subdomain=None, email="test", api_key="test")
        result = await client.connect()
        assert result is False
        assert client.state == ZendeskClientState.ERROR

    @pytest.mark.asyncio
    async def test_connect_missing_email(self):
        """Test connection fails without email."""
        client = ZendeskClient(subdomain="test", email=None, api_key="test")
        result = await client.connect()
        assert result is False
        assert client.state == ZendeskClientState.ERROR

    @pytest.mark.asyncio
    async def test_connect_missing_api_key(self):
        """Test connection fails without API key."""
        client = ZendeskClient(subdomain="test", email="test", api_key=None)
        result = await client.connect()
        assert result is False
        assert client.state == ZendeskClientState.ERROR

    @pytest.mark.asyncio
    async def test_create_ticket(self, zendesk_client):
        """Test creating a ticket."""
        await zendesk_client.connect()
        result = await zendesk_client.create_ticket(
            subject="Test Ticket",
            comment="This is a test ticket",
            requester_email="customer@example.com",
            priority=TicketPriority.HIGH,
        )
        assert result["subject"] == "Test Ticket"
        assert result["status"] == TicketStatus.NEW.value
        assert result["priority"] == TicketPriority.HIGH.value
        assert result["id"] is not None

    @pytest.mark.asyncio
    async def test_create_ticket_missing_subject(self, zendesk_client):
        """Test ticket creation fails without subject."""
        await zendesk_client.connect()
        with pytest.raises(ValueError, match="subject"):
            await zendesk_client.create_ticket(
                subject="",
                comment="Test",
                requester_email="test@example.com",
            )

    @pytest.mark.asyncio
    async def test_create_ticket_missing_comment(self, zendesk_client):
        """Test ticket creation fails without comment."""
        await zendesk_client.connect()
        with pytest.raises(ValueError, match="comment"):
            await zendesk_client.create_ticket(
                subject="Test",
                comment="",
                requester_email="test@example.com",
            )

    @pytest.mark.asyncio
    async def test_create_ticket_missing_requester(self, zendesk_client):
        """Test ticket creation fails without requester email."""
        await zendesk_client.connect()
        with pytest.raises(ValueError, match="Requester email"):
            await zendesk_client.create_ticket(
                subject="Test",
                comment="Test comment",
                requester_email="",
            )

    @pytest.mark.asyncio
    async def test_get_ticket(self, zendesk_client):
        """Test getting a ticket."""
        await zendesk_client.connect()
        result = await zendesk_client.get_ticket(12345)
        assert result["id"] == 12345
        assert "subject" in result
        assert "status" in result

    @pytest.mark.asyncio
    async def test_update_ticket(self, zendesk_client):
        """Test updating a ticket."""
        await zendesk_client.connect()
        result = await zendesk_client.update_ticket(
            ticket_id=12345,
            comment="Adding a comment",
            status=TicketStatus.PENDING,
        )
        assert result["id"] == 12345
        assert result["status"] == TicketStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_update_ticket_missing_id(self, zendesk_client):
        """Test ticket update fails without ID."""
        await zendesk_client.connect()
        with pytest.raises(ValueError, match="Ticket ID"):
            await zendesk_client.update_ticket(ticket_id=None)

    @pytest.mark.asyncio
    async def test_add_comment(self, zendesk_client):
        """Test adding comment to ticket."""
        await zendesk_client.connect()
        result = await zendesk_client.add_comment(
            ticket_id=12345,
            comment="This is a new comment",
            public=True,
        )
        assert result["ticket_id"] == 12345
        assert result["body"] == "This is a new comment"
        assert result["public"] is True

    @pytest.mark.asyncio
    async def test_add_comment_missing_text(self, zendesk_client):
        """Test comment fails without text."""
        await zendesk_client.connect()
        with pytest.raises(ValueError, match="Comment is required"):
            await zendesk_client.add_comment(ticket_id=12345, comment="")

    @pytest.mark.asyncio
    async def test_search_tickets(self, zendesk_client):
        """Test searching tickets."""
        await zendesk_client.connect()
        results = await zendesk_client.search_tickets(
            query="refund",
            status=TicketStatus.OPEN,
        )
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_tickets_missing_query(self, zendesk_client):
        """Test search fails without query."""
        await zendesk_client.connect()
        with pytest.raises(ValueError, match="query"):
            await zendesk_client.search_tickets(query="")

    @pytest.mark.asyncio
    async def test_get_user(self, zendesk_client):
        """Test getting a user."""
        await zendesk_client.connect()
        result = await zendesk_client.get_user(12345)
        assert result["id"] == 12345
        assert "email" in result

    @pytest.mark.asyncio
    async def test_get_user_by_email(self, zendesk_client):
        """Test getting user by email."""
        await zendesk_client.connect()
        result = await zendesk_client.get_user_by_email("test@example.com")
        assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_create_or_update_user(self, zendesk_client):
        """Test creating or updating a user."""
        await zendesk_client.connect()
        result = await zendesk_client.create_or_update_user(
            email="newuser@example.com",
            name="New User",
        )
        assert result["email"] == "newuser@example.com"
        assert result["name"] == "New User"

    @pytest.mark.asyncio
    async def test_get_ticket_comments(self, zendesk_client):
        """Test getting ticket comments."""
        await zendesk_client.connect()
        comments = await zendesk_client.get_ticket_comments(12345)
        assert isinstance(comments, list)

    @pytest.mark.asyncio
    async def test_get_articles(self, zendesk_client):
        """Test getting knowledge base articles."""
        await zendesk_client.connect()
        articles = await zendesk_client.get_articles(query="how to")
        assert isinstance(articles, list)

    @pytest.mark.asyncio
    async def test_health_check(self, zendesk_client):
        """Test health check."""
        await zendesk_client.connect()
        health = await zendesk_client.health_check()
        assert health["healthy"] is True
        assert health["subdomain"] == "testcompany"


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegrationClientsIntegration:
    """Integration tests for all clients working together."""

    @pytest.mark.asyncio
    async def test_all_clients_initialize(self):
        """Test that all clients can be initialized without errors."""
        shopify = ShopifyClient(
            store_url="test.myshopify.com",
            api_key="test",
            api_secret="test",
        )
        paddle = PaddleClient(
            client_token="test",
            api_key="test",
        )
        twilio = TwilioClient(
            account_sid="ACtest",
            auth_token="test",
        )
        email = EmailClient(
            api_key="test",
            from_email="test@test.com",
        )
        zendesk = ZendeskClient(
            subdomain="test",
            email="test@test.com",
            api_key="test",
        )

        # All should connect successfully
        assert await shopify.connect() is True
        assert await paddle.connect() is True
        assert await twilio.connect() is True
        assert await email.connect() is True
        assert await zendesk.connect() is True

        # All health checks should pass
        assert (await shopify.health_check())["healthy"] is True
        assert (await paddle.health_check())["healthy"] is True
        assert (await twilio.health_check())["healthy"] is True
        assert (await email.health_check())["healthy"] is True
        assert (await zendesk.health_check())["healthy"] is True

    @pytest.mark.asyncio
    async def test_refund_gate_cannot_be_bypassed(self):
        """CRITICAL: Ensure refund gate cannot be bypassed under any circumstances."""
        paddle = PaddleClient(
            client_token="test",
            api_key="test",
        )
        await paddle.connect()

        # Test 1: No approval at all
        with pytest.raises(ValueError):
            await paddle.process_refund(
                transaction_id="txn_123",
                amount=100.00,
                reason="Test",
                pending_approval=None,
            )

        # Test 2: Approval with wrong status
        wrong_status = PendingApproval(
            approval_id="appr_1",
            transaction_id="txn_123",
            amount=100.00,
            currency="USD",
            reason="Test",
            requested_by="agent_1",
            created_at=datetime.now(timezone.utc),
            status="expired",
        )
        with pytest.raises(ValueError):
            await paddle.process_refund(
                transaction_id="txn_123",
                amount=100.00,
                reason="Test",
                pending_approval=wrong_status,
            )

        # Test 3: Amount mismatch
        correct_approval = PendingApproval(
            approval_id="appr_2",
            transaction_id="txn_123",
            amount=50.00,  # Different amount
            currency="USD",
            reason="Test",
            requested_by="agent_1",
            created_at=datetime.now(timezone.utc),
            status="pending",
        )
        with pytest.raises(ValueError):
            await paddle.process_refund(
                transaction_id="txn_123",
                amount=100.00,  # Doesn't match
                reason="Test",
                pending_approval=correct_approval,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# GITHUB CLIENT TESTS (Day 3)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGitHubClient:
    """Tests for GitHub client."""

    @pytest.fixture
    def github_client(self):
        """Create a GitHub client instance."""
        return GitHubClient(token="test_github_token")

    @pytest.mark.asyncio
    async def test_connect_success(self, github_client):
        """Test successful connection to GitHub."""
        result = await github_client.connect()
        assert result is True
        assert github_client.state == GitHubClientState.CONNECTED
        assert github_client.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_missing_token(self):
        """Test connection fails without token."""
        client = GitHubClient(token=None)
        result = await client.connect()
        assert result is False
        assert client.state == GitHubClientState.ERROR

    @pytest.mark.asyncio
    async def test_disconnect(self, github_client):
        """Test disconnection."""
        await github_client.connect()
        await github_client.disconnect()
        assert github_client.state == GitHubClientState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_get_repository(self, github_client):
        """Test getting repository info."""
        await github_client.connect()
        repo = await github_client.get_repository("owner", "repo")
        assert repo["name"] == "repo"
        assert repo["owner"]["login"] == "owner"
        assert "stars" in repo

    @pytest.mark.asyncio
    async def test_get_repository_not_connected(self, github_client):
        """Test getting repo fails when not connected."""
        with pytest.raises(ValueError, match="not connected"):
            await github_client.get_repository("owner", "repo")

    @pytest.mark.asyncio
    async def test_get_repository_missing_owner(self, github_client):
        """Test getting repo fails without owner."""
        await github_client.connect()
        with pytest.raises(ValueError, match="Owner and repo name are required"):
            await github_client.get_repository("", "repo")

    @pytest.mark.asyncio
    async def test_get_issue(self, github_client):
        """Test getting an issue."""
        await github_client.connect()
        issue = await github_client.get_issue("owner", "repo", 123)
        assert issue["number"] == 123
        assert issue["state"] == "open"
        assert "title" in issue

    @pytest.mark.asyncio
    async def test_get_issue_invalid_number(self, github_client):
        """Test getting issue fails with invalid number."""
        await github_client.connect()
        with pytest.raises(ValueError, match="Valid issue number"):
            await github_client.get_issue("owner", "repo", 0)

    @pytest.mark.asyncio
    async def test_search_issues(self, github_client):
        """Test searching issues."""
        await github_client.connect()
        results = await github_client.search_issues("owner", "repo", "bug", limit=10)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_issues_invalid_limit(self, github_client):
        """Test search fails with invalid limit."""
        await github_client.connect()
        with pytest.raises(ValueError, match="between 1 and 100"):
            await github_client.search_issues("owner", "repo", "bug", limit=200)

    @pytest.mark.asyncio
    async def test_get_pull_request(self, github_client):
        """Test getting a PR."""
        await github_client.connect()
        pr = await github_client.get_pull_request("owner", "repo", 456)
        assert pr["number"] == 456
        assert "head" in pr
        assert "base" in pr

    @pytest.mark.asyncio
    async def test_get_commit(self, github_client):
        """Test getting a commit."""
        await github_client.connect()
        commit = await github_client.get_commit("owner", "repo", "abc123def")
        assert "sha" in commit
        assert "message" in commit
        assert "author" in commit

    @pytest.mark.asyncio
    async def test_list_branches(self, github_client):
        """Test listing branches."""
        await github_client.connect()
        branches = await github_client.list_branches("owner", "repo")
        assert isinstance(branches, list)
        assert len(branches) > 0

    @pytest.mark.asyncio
    async def test_get_release(self, github_client):
        """Test getting release info."""
        await github_client.connect()
        release = await github_client.get_release("owner", "repo", "v1.0.0")
        assert release["tag_name"] == "v1.0.0"

    @pytest.mark.asyncio
    async def test_health_check(self, github_client):
        """Test health check."""
        await github_client.connect()
        health = await github_client.health_check()
        assert health["healthy"] is True
        assert health["state"] == GitHubClientState.CONNECTED.value


# ═══════════════════════════════════════════════════════════════════════════════
# AFTERSHIP CLIENT TESTS (Day 3)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAfterShipClient:
    """Tests for AfterShip tracking client."""

    @pytest.fixture
    def aftership_client(self):
        """Create an AfterShip client instance."""
        return AfterShipClient(api_key="test_aftership_key")

    @pytest.mark.asyncio
    async def test_connect_success(self, aftership_client):
        """Test successful connection to AfterShip."""
        result = await aftership_client.connect()
        assert result is True
        assert aftership_client.state == AfterShipClientState.CONNECTED

    @pytest.mark.asyncio
    async def test_connect_missing_api_key(self):
        """Test connection fails without API key."""
        client = AfterShipClient(api_key=None)
        result = await client.connect()
        assert result is False
        assert client.state == AfterShipClientState.ERROR

    @pytest.mark.asyncio
    async def test_disconnect(self, aftership_client):
        """Test disconnection."""
        await aftership_client.connect()
        await aftership_client.disconnect()
        assert aftership_client.state == AfterShipClientState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_track_shipment(self, aftership_client):
        """Test tracking a shipment."""
        await aftership_client.connect()
        tracking = await aftership_client.track_shipment("TRK123456789")
        assert tracking["tracking_number"] == "TRK123456789"
        assert "status" in tracking
        assert "checkpoint" in tracking

    @pytest.mark.asyncio
    async def test_track_shipment_not_connected(self, aftership_client):
        """Test tracking fails when not connected."""
        with pytest.raises(ValueError, match="not connected"):
            await aftership_client.track_shipment("TRK123")

    @pytest.mark.asyncio
    async def test_track_shipment_missing_number(self, aftership_client):
        """Test tracking fails without tracking number."""
        await aftership_client.connect()
        with pytest.raises(ValueError, match="Tracking number is required"):
            await aftership_client.track_shipment("")

    @pytest.mark.asyncio
    async def test_create_tracking(self, aftership_client):
        """Test creating a tracking."""
        await aftership_client.connect()
        result = await aftership_client.create_tracking(
            tracking_number="TRK999",
            carrier="fedex",
            title="Test Package"
        )
        assert result["tracking_number"] == "TRK999"
        assert result["carrier"] == "fedex"

    @pytest.mark.asyncio
    async def test_get_couriers(self, aftership_client):
        """Test getting supported couriers."""
        await aftership_client.connect()
        couriers = await aftership_client.get_couriers()
        assert isinstance(couriers, list)
        assert len(couriers) > 0

    @pytest.mark.asyncio
    async def test_detect_carrier(self, aftership_client):
        """Test carrier detection."""
        await aftership_client.connect()
        carriers = await aftership_client.detect_carrier("TRK123456789")
        assert isinstance(carriers, list)

    @pytest.mark.asyncio
    async def test_get_last_checkpoint(self, aftership_client):
        """Test getting last checkpoint."""
        await aftership_client.connect()
        checkpoint = await aftership_client.get_last_checkpoint("TRK123")
        assert "checkpoint" in checkpoint

    @pytest.mark.asyncio
    async def test_list_trackings(self, aftership_client):
        """Test listing trackings."""
        await aftership_client.connect()
        result = await aftership_client.list_trackings(page=1, limit=10)
        assert "trackings" in result
        assert "page" in result

    @pytest.mark.asyncio
    async def test_list_trackings_invalid_limit(self, aftership_client):
        """Test listing fails with invalid limit."""
        await aftership_client.connect()
        with pytest.raises(ValueError, match="between 1 and 100"):
            await aftership_client.list_trackings(limit=200)

    @pytest.mark.asyncio
    async def test_health_check(self, aftership_client):
        """Test health check."""
        await aftership_client.connect()
        health = await aftership_client.health_check()
        assert health["healthy"] is True
        assert "supported_carriers" in health


# ═══════════════════════════════════════════════════════════════════════════════
# EPIC EHR CLIENT TESTS (Day 3)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEpicEHRClient:
    """Tests for Epic EHR client with BAA enforcement."""

    @pytest.fixture
    def epic_client(self):
        """Create an Epic EHR client instance with BAA verified."""
        return EpicEHRClient(
            client_id="test_client_id",
            client_secret="test_client_secret",
            fhir_base_url="https://fhir.epic.com",
            baa_verified=True
        )

    @pytest.fixture
    def epic_client_no_baa(self):
        """Create an Epic EHR client without BAA."""
        return EpicEHRClient(
            client_id="test_client_id",
            client_secret="test_client_secret",
            baa_verified=False
        )

    @pytest.mark.asyncio
    async def test_connect_success(self, epic_client):
        """Test successful connection to Epic EHR."""
        result = await epic_client.connect()
        assert result is True
        assert epic_client.state == EpicEHRClientState.CONNECTED

    @pytest.mark.asyncio
    async def test_connect_without_baa_blocked(self, epic_client_no_baa):
        """CRITICAL: Connection must fail without BAA verification."""
        result = await epic_client_no_baa.connect()
        assert result is False
        assert epic_client_no_baa.state == EpicEHRClientState.BAA_REQUIRED

    @pytest.mark.asyncio
    async def test_connect_missing_credentials(self):
        """Test connection fails without credentials."""
        client = EpicEHRClient(client_id=None, client_secret=None, baa_verified=True)
        result = await client.connect()
        assert result is False
        assert client.state == EpicEHRClientState.ERROR

    @pytest.mark.asyncio
    async def test_disconnect(self, epic_client):
        """Test disconnection."""
        await epic_client.connect()
        await epic_client.disconnect()
        assert epic_client.state == EpicEHRClientState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_get_patient_by_mrn(self, epic_client):
        """Test getting patient by MRN."""
        await epic_client.connect()
        patient = await epic_client.get_patient_by_mrn("MRN123456")
        assert patient["resourceType"] == "Patient"
        assert "mrn" in patient

    @pytest.mark.asyncio
    async def test_get_patient_phi_redacted(self, epic_client):
        """CRITICAL: PHI must be redacted in responses."""
        await epic_client.connect()
        patient = await epic_client.get_patient_by_mrn("MRN123456")
        # Sensitive fields should be redacted
        assert patient["name"] == "[REDACTED]"
        assert patient["dob"] == "[REDACTED]"
        assert patient["phone"] == "[REDACTED]"

    @pytest.mark.asyncio
    async def test_get_patient_missing_mrn(self, epic_client):
        """Test getting patient fails without MRN."""
        await epic_client.connect()
        with pytest.raises(ValueError, match="MRN is required"):
            await epic_client.get_patient_by_mrn("")

    @pytest.mark.asyncio
    async def test_get_patient_visits(self, epic_client):
        """Test getting patient visits."""
        await epic_client.connect()
        visits = await epic_client.get_patient_visits("patient_123")
        assert isinstance(visits, list)

    @pytest.mark.asyncio
    async def test_get_patient_medications(self, epic_client):
        """Test getting patient medications."""
        await epic_client.connect()
        meds = await epic_client.get_patient_medications("patient_123")
        assert isinstance(meds, list)

    @pytest.mark.asyncio
    async def test_get_patient_allergies(self, epic_client):
        """Test getting patient allergies."""
        await epic_client.connect()
        allergies = await epic_client.get_patient_allergies("patient_123")
        assert isinstance(allergies, list)

    @pytest.mark.asyncio
    async def test_get_lab_results(self, epic_client):
        """Test getting lab results."""
        await epic_client.connect()
        labs = await epic_client.get_lab_results("patient_123")
        assert isinstance(labs, list)

    @pytest.mark.asyncio
    async def test_get_conditions(self, epic_client):
        """Test getting patient conditions."""
        await epic_client.connect()
        conditions = await epic_client.get_conditions("patient_123")
        assert isinstance(conditions, list)

    # CRITICAL READ-ONLY ENFORCEMENT TESTS

    @pytest.mark.asyncio
    async def test_create_patient_blocked(self, epic_client):
        """CRITICAL: Patient creation must be blocked (read-only)."""
        await epic_client.connect()
        with pytest.raises(PermissionError, match="READ-ONLY"):
            await epic_client.create_patient()

    @pytest.mark.asyncio
    async def test_update_patient_blocked(self, epic_client):
        """CRITICAL: Patient updates must be blocked (read-only)."""
        await epic_client.connect()
        with pytest.raises(PermissionError, match="READ-ONLY"):
            await epic_client.update_patient()

    @pytest.mark.asyncio
    async def test_delete_patient_blocked(self, epic_client):
        """CRITICAL: Patient deletion must be blocked (read-only)."""
        await epic_client.connect()
        with pytest.raises(PermissionError, match="READ-ONLY"):
            await epic_client.delete_patient()

    @pytest.mark.asyncio
    async def test_create_order_blocked(self, epic_client):
        """CRITICAL: Order creation must be blocked (read-only)."""
        await epic_client.connect()
        with pytest.raises(PermissionError, match="READ-ONLY"):
            await epic_client.create_order()

    @pytest.mark.asyncio
    async def test_is_read_only(self, epic_client):
        """Test that client reports read-only status."""
        await epic_client.connect()
        assert epic_client.is_read_only is True

    @pytest.mark.asyncio
    async def test_baa_verified_property(self, epic_client):
        """Test BAA verification property."""
        assert epic_client.baa_verified is True

    def test_redact_phi(self, epic_client):
        """Test PHI redaction functionality."""
        text = "SSN: 123-45-6789, Phone: 555-123-4567"
        redacted = epic_client._redact_phi(text)
        assert "123-45-6789" not in redacted
        assert "555-123-4567" not in redacted
        assert "[SSN_REDACTED]" in redacted
        assert "[PHONE_REDACTED]" in redacted

    @pytest.mark.asyncio
    async def test_health_check(self, epic_client):
        """Test health check."""
        await epic_client.connect()
        health = await epic_client.health_check()
        assert health["healthy"] is True
        assert health["read_only"] is True
        assert health["baa_verified"] is True
