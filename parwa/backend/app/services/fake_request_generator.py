"""
PARWA Fake Request Generator — Simulated Customer Support Requests

Generates realistic fake customer support requests for testing and demo
purposes. These get converted into real tickets by the variant pipeline,
so you can see how the AI handles different types of customer issues.

The generator creates:
  - Realistic customer names and emails
  - Context-appropriate messages per category
  - Varied priority levels
  - Multiple channels (chat, email, SMS)

Usage:
  from app.services.fake_request_generator import generate_fake_requests
  requests = generate_fake_requests(count=5, category="mixed")

BC-001: company_id injected at execution layer, not here.
BC-008: Never crash — always return something usable.
BC-012: All timestamps UTC.
"""

import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("fake_request_generator")


# ══════════════════════════════════════════════════════════════════
# FAKE CUSTOMER DATA
# ══════════════════════════════════════════════════════════════════

CUSTOMER_NAMES = [
    "Sarah Johnson", "Mike Chen", "Priya Sharma", "David Kim",
    "Emma Wilson", "Carlos Rodriguez", "Aisha Patel", "Tom Anderson",
    "Lisa Wang", "James Brown", "Maria Garcia", "Alex Turner",
    "Rachel Green", "Omar Hassan", "Sophie Martin", "Kenji Tanaka",
    "Nina Petrova", "Chris Taylor", "Amara Okafor", "Ryan Murphy",
]

CUSTOMER_EMAIL_DOMAINS = [
    "gmail.com", "outlook.com", "yahoo.com", "protonmail.com",
    "icloud.com", "hotmail.com", "mail.com",
]

CHANNELS = ["chat", "email", "sms", "api"]


# ══════════════════════════════════════════════════════════════════
# REQUEST TEMPLATES BY CATEGORY
# ══════════════════════════════════════════════════════════════════

REQUEST_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "tech_support": [
        {
            "subject": "App keeps crashing on startup",
            "message": (
                "Hi, I've been trying to use the app for the past two days but it "
                "keeps crashing every time I open it. I've tried restarting my phone "
                "and reinstalling the app but nothing works. I'm on iPhone 14 with "
                "iOS 17.2. Can you help me figure out what's going on?"
            ),
            "priority": "high",
        },
        {
            "subject": "Login not working after password reset",
            "message": (
                "I reset my password yesterday but I still can't log in. Every time "
                "I enter my new credentials it says 'invalid username or password'. "
                "I've tried clearing my browser cache and using incognito mode. My "
                "email is the same one I signed up with. This is really frustrating."
            ),
            "priority": "high",
        },
        {
            "subject": "Integration with Slack stopped working",
            "message": (
                "Our Slack integration has been down since Monday. Notifications "
                "aren't coming through to our channel anymore. I've checked the API "
                "key and reconnected the integration but it's still not working. We "
                "rely on this for our support team's workflow."
            ),
            "priority": "critical",
        },
        {
            "subject": "Dashboard loading very slowly",
            "message": (
                "The dashboard takes about 30 seconds to load now. It used to be "
                "almost instant. This started happening after the last update. I've "
                "tried different browsers and the issue persists. It's making it hard "
                "to monitor our support queue efficiently."
            ),
            "priority": "medium",
        },
        {
            "subject": "API returning 500 errors intermittently",
            "message": (
                "We're getting random 500 errors from the API about 10% of the time. "
                "Our monitoring shows it started around 3 PM today. The requests that "
                "succeed work fine, but the failures are causing issues for our "
                "automated workflows. Can someone check the server status?"
            ),
            "priority": "critical",
        },
        {
            "subject": "Can't export my data to CSV",
            "message": (
                "When I try to export my ticket data to CSV, the download starts but "
                "then fails with an error message. I've tried smaller date ranges but "
                "it still doesn't work. I need this data for our weekly review meeting "
                "tomorrow morning."
            ),
            "priority": "medium",
        },
    ],
    "billing": [
        {
            "subject": "Charged twice for this month",
            "message": (
                "I noticed I was charged twice on my credit card statement for this "
                "month's subscription. The charge appeared on the 1st and again on "
                "the 3rd. Can you please look into this and refund the duplicate "
                "charge? I've been a loyal customer for over a year."
            ),
            "priority": "high",
        },
        {
            "subject": "Need to update payment method",
            "message": (
                "My credit card expired and I need to update my payment information. "
                "Where can I do this? I've looked in the billing section but can't "
                "find the option to change my card details. Don't want my service "
                "interrupted."
            ),
            "priority": "medium",
        },
        {
            "subject": "Question about usage limits on my plan",
            "message": (
                "I'm on the Pro plan and I want to understand the usage limits better. "
                "How many AI conversations am I allowed per month? And what happens if "
                "I go over? I'm considering upgrading but need to understand the "
                "pricing tiers first."
            ),
            "priority": "low",
        },
        {
            "subject": "Invoice doesn't match my subscription",
            "message": (
                "The invoice I received shows a different amount than what I agreed to "
                "when I signed up. I was told the plan costs a certain amount per "
                "month but the invoice is higher. Can you explain the discrepancy?"
            ),
            "priority": "high",
        },
    ],
    "returns_refunds": [
        {
            "subject": "Want to return a damaged product",
            "message": (
                "I received my order yesterday and the product was damaged in transit. "
                "The box was crushed and the item inside has a visible dent. I have "
                "photos I can share. I'd like a full refund or a replacement sent "
                "immediately please."
            ),
            "priority": "high",
        },
        {
            "subject": "Requesting refund for subscription cancellation",
            "message": (
                "I cancelled my subscription last week but I was still charged for "
                "this month. The cancellation was effective immediately according to "
                "the confirmation email I received. Please process the refund for the "
                "unused portion of this billing cycle."
            ),
            "priority": "medium",
        },
        {
            "subject": "Wrong item delivered, need exchange",
            "message": (
                "You sent me the wrong size. I ordered a Medium but received a Large. "
                "I need the correct size shipped out ASAP for an event this weekend. "
                "How do I arrange the exchange? Do I need to pay for return shipping?"
            ),
            "priority": "high",
        },
        {
            "subject": "Partial refund for service outage",
            "message": (
                "Your service was down for most of last Thursday, which is one of our "
                "busiest days. We lost several customer interactions because of it. "
                "I'd like to discuss a partial refund or credit for the downtime. Our "
                "SLA guarantees 99.9% uptime."
            ),
            "priority": "medium",
        },
    ],
    "order_tracking": [
        {
            "subject": "Order hasn't arrived after 2 weeks",
            "message": (
                "I placed an order two weeks ago and it still hasn't arrived. The "
                "tracking number shows 'label created' but no movement since then. "
                "My order number is ORD-28491. Can you check what's happening with "
                "the shipment?"
            ),
            "priority": "high",
        },
        {
            "subject": "Tracking link not working",
            "message": (
                "The tracking link in my shipping confirmation email doesn't work. "
                "It takes me to a page that says 'tracking information not available'. "
                "It's been 3 days since I got the shipping notification. Can you "
                "provide an updated tracking link?"
            ),
            "priority": "medium",
        },
        {
            "subject": "Need to change delivery address",
            "message": (
                "I moved last week and need my upcoming delivery sent to my new "
                "address instead. I tried updating it in my account but the order is "
                "already being processed. Can you intercept the shipment or update "
                "the delivery address?"
            ),
            "priority": "medium",
        },
    ],
    "delivery_issues": [
        {
            "subject": "Delivery driver left package in the rain",
            "message": (
                "The delivery person left my package outside in the rain and now "
                "everything is soaked. The products inside are damaged. This is not "
                "acceptable. I want a replacement sent with better delivery "
                "instructions. I specifically requested 'leave at door with cover'."
            ),
            "priority": "high",
        },
        {
            "subject": "Package delivered to wrong address",
            "message": (
                "The tracking shows my package was delivered but I never received it. "
                "My neighbor told me they saw the delivery driver leave it at a house "
                "two blocks away. Can you contact the carrier and get this sorted out? "
                "I need my items."
            ),
            "priority": "critical",
        },
        {
            "subject": "Missing items from my order",
            "message": (
                "I ordered 5 items but only 3 were in the box. The packing slip shows "
                "all 5 items but two are missing. Can you check if they were shipped "
                "separately or if there was a mistake? I need the remaining items ASAP."
            ),
            "priority": "high",
        },
    ],
    "account_management": [
        {
            "subject": "Can't access my account after email change",
            "message": (
                "I changed my email address in my account settings and now I can't "
                "log in. The password reset email isn't coming to my new email address "
                "and I no longer have access to the old one. I need to get back into "
                "my account urgently."
            ),
            "priority": "high",
        },
        {
            "subject": "Need to add team members to our account",
            "message": (
                "We're expanding our team and I need to add 5 new members to our "
                "account. What's the process? Will this affect our billing? Also, "
                "can I set different permission levels for different team members?"
            ),
            "priority": "medium",
        },
        {
            "subject": "Want to close my account",
            "message": (
                "I'd like to close my account permanently. Can you guide me through "
                "the process? I want to make sure all my data is properly deleted. "
                "Also, will there be any charges for early termination on my annual plan?"
            ),
            "priority": "medium",
        },
        {
            "subject": "Two-factor authentication not working",
            "message": (
                "I lost my phone and can't access my authenticator app for 2FA. I "
                "have the backup codes but they're not working either. I'm completely "
                "locked out of my account and I have urgent work to do. Please help!"
            ),
            "priority": "critical",
        },
    ],
    "complaint": [
        {
            "subject": "Terrible customer service experience",
            "message": (
                "I've been waiting for a response to my ticket for 3 days now. This is "
                "the worst support experience I've ever had. I was promised a 24-hour "
                "response time but nobody has gotten back to me. I'm seriously "
                "considering switching to a competitor."
            ),
            "priority": "high",
        },
        {
            "subject": "Product doesn't match what was advertised",
            "message": (
                "The features you advertised on your website are not what I'm seeing "
                "in the actual product. The AI assistant was supposed to handle complex "
                "queries but it can barely answer basic questions. This feels like "
                "false advertising. I want a full refund."
            ),
            "priority": "high",
        },
        {
            "subject": "Being charged for features I didn't sign up for",
            "message": (
                "I'm seeing charges on my bill for add-on features that I never "
                "requested. This is completely unacceptable. I want these charges "
                "removed and an explanation of how this happened. I'm also filing "
                "a complaint with consumer protection."
            ),
            "priority": "critical",
        },
    ],
    "feature_request": [
        {
            "subject": "Would love a mobile app",
            "message": (
                "Do you have plans to build a mobile app? I need to manage my support "
                "queue on the go and the mobile web experience isn't great. A native "
                "app with push notifications would be amazing. Thanks!"
            ),
            "priority": "low",
        },
        {
            "subject": "Request for WhatsApp integration",
            "message": (
                "Can you add WhatsApp as a supported channel? Most of our customers "
                "prefer messaging us on WhatsApp. We're losing potential support "
                "interactions because we can't offer that channel yet."
            ),
            "priority": "medium",
        },
        {
            "subject": "Need custom reporting dashboard",
            "message": (
                "The current reports are too basic for our needs. We need custom "
                "dashboards where we can create our own metrics and charts. Our "
                "management team needs specific KPIs that aren't in the standard "
                "reports. Is this on your roadmap?"
            ),
            "priority": "medium",
        },
    ],
}


# ══════════════════════════════════════════════════════════════════
# GENERATOR
# ══════════════════════════════════════════════════════════════════


def generate_fake_requests(
    count: int = 5,
    category: str = "mixed",
    company_id: str = "",
) -> List[Dict[str, Any]]:
    """Generate realistic fake customer support requests.

    These are NOT real customers — they're simulated for testing and
    demonstration. Each request contains all the info needed to create
    a real ticket in the system.

    Args:
        count: Number of requests to generate (1-25, default 5).
        category: Type of requests. 'mixed' for variety.
        company_id: Tenant ID for scoping (optional, used in IDs).

    Returns:
        List of dicts, each with:
          - subject, message, customer_name, customer_email
          - priority, category, channel
          - is_fake: True (marks it as generated data)
    """
    try:
        # Clamp count
        count = max(1, min(25, count))

        # Determine which categories to use
        if category == "mixed":
            categories = list(REQUEST_TEMPLATES.keys())
        elif category in REQUEST_TEMPLATES:
            categories = [category]
        else:
            categories = list(REQUEST_TEMPLATES.keys())

        requests = []
        used_names = set()

        for i in range(count):
            # Pick a random category (weighted distribution for realism)
            chosen_category = random.choice(categories)

            # Pick a random template from that category
            templates = REQUEST_TEMPLATES.get(chosen_category, [])
            if not templates:
                continue

            template = random.choice(templates)

            # Generate a unique customer
            name = _pick_unique_name(used_names)
            used_names.add(name)

            email = _generate_email(name)

            # Pick a channel (chat is most common)
            channel = random.choices(
                CHANNELS,
                weights=[0.5, 0.25, 0.15, 0.10],
                k=1,
            )[0]

            # Occasionally vary the priority from the template
            priority = template.get("priority", "medium")
            if random.random() < 0.2:  # 20% chance to vary
                priority = random.choice(["low", "medium", "high", "critical"])

            request = {
                "subject": template["subject"],
                "message": template["message"],
                "customer_name": name,
                "customer_email": email,
                "priority": priority,
                "category": _map_category(chosen_category),
                "channel": channel,
                "is_fake": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

            requests.append(request)

        logger.info(
            "fake_requests_generated: count=%d, category=%s, company=%s",
            len(requests), category, company_id,
        )

        return requests

    except Exception:
        logger.exception("generate_fake_requests_error")
        # Return at least one simple request so we never fail completely
        return [
            {
                "subject": "Test support request",
                "message": "This is a test request generated for demonstration purposes.",
                "customer_name": "Test User",
                "customer_email": "test.user@example.com",
                "priority": "medium",
                "category": "general",
                "channel": "chat",
                "is_fake": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        ]


def _pick_unique_name(used: set) -> str:
    """Pick a customer name not yet used in this batch."""
    available = [n for n in CUSTOMER_NAMES if n not in used]
    if not available:
        # All used — add a suffix
        base = random.choice(CUSTOMER_NAMES)
        return f"{base} {random.randint(2, 99)}"
    return random.choice(available)


def _generate_email(name: str) -> str:
    """Generate a realistic email from a name."""
    parts = name.lower().split()
    domain = random.choice(CUSTOMER_EMAIL_DOMAINS)
    style = random.choice(["dot", "underscore", "plus"])
    if style == "dot":
        local = ".".join(parts)
    elif style == "underscore":
        local = "_".join(parts)
    else:
        local = parts[0] + "+" + str(random.randint(1, 999))
    return f"{local}@{domain}"


def _map_category(template_category: str) -> str:
    """Map our template categories to the ticket model's category enum."""
    mapping = {
        "tech_support": "tech_support",
        "billing": "billing",
        "returns_refunds": "returns_refunds",
        "order_tracking": "order_tracking",
        "delivery_issues": "delivery_issues",
        "account_management": "account_management",
        "complaint": "complaint",
        "feature_request": "feature_request",
    }
    return mapping.get(template_category, "general")


# ══════════════════════════════════════════════════════════════════
# QUICK STATS
# ══════════════════════════════════════════════════════════════════


def get_available_categories() -> List[str]:
    """Get list of available request categories for generation."""
    return list(REQUEST_TEMPLATES.keys())


def get_template_count() -> Dict[str, int]:
    """Get count of templates per category."""
    return {cat: len(templates) for cat, templates in REQUEST_TEMPLATES.items()}


__all__ = [
    "generate_fake_requests",
    "get_available_categories",
    "get_template_count",
]
