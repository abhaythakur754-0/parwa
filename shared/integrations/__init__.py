"""
PARWA Integrations Module.

External service clients for e-commerce, communications, and support.

Available Clients:
- ShopifyClient: E-commerce store integration
- PaddleClient: Merchant of Record (payments, subscriptions, refunds)
- TwilioClient: SMS and Voice communication
- EmailClient: Transactional email via Brevo
- ZendeskClient: Ticketing system integration
- GitHubClient: Repository access for code-related support
- AfterShipClient: Shipment tracking
- EpicEHRClient: Healthcare EHR (read-only, BAA required)
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
    # GitHub
    "GitHubClient",
    "GitHubClientState",
    # AfterShip
    "AfterShipClient",
    "AfterShipClientState",
    "TrackingStatus",
    # Epic EHR
    "EpicEHRClient",
    "EpicEHRClientState",
    "EHRAccessLevel",
]
