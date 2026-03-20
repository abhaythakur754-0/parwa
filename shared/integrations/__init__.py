"""
PARWA Integrations Module.

External service clients for e-commerce, communications, and support.

Available Clients:
- ShopifyClient: E-commerce store integration
- PaddleClient: Merchant of Record (payments, subscriptions, refunds)
- TwilioClient: SMS and Voice communication
- EmailClient: Transactional email via Brevo
- ZendeskClient: Ticketing system integration
"""

from shared.integrations.shopify_client import ShopifyClient, ShopifyClientState
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

__all__ = [
    # Shopify
    "ShopifyClient",
    "ShopifyClientState",
    # Paddle
    "PaddleClient",
    "PaddleClientState",
    "PaddleEnvironment",
    "PendingApproval",
    # Twilio
    "TwilioClient",
    "TwilioClientState",
    "MessageStatus",
    "CallStatus",
    # Email
    "EmailClient",
    "EmailClientState",
    "EmailStatus",
    "EmailPriority",
    # Zendesk
    "ZendeskClient",
    "ZendeskClientState",
    "TicketStatus",
    "TicketPriority",
]
