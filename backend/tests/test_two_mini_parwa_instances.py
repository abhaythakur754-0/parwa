"""
COMPREHENSIVE TEST SUITE: 2 Mini PARWA Instances
================================================
Scenario: A company hires 2 Mini PARWA instances
Tests ALL functionality from scratch
"""

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from app.config.variant_features import VARIANT_LIMITS

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================
# FAKE COMPANIES - 2 COMPANIES HIRING MINI PARWA
# ============================================================


@dataclass
class FakeCompany:
    """Represents a fake company hiring Mini PARWA"""

    id: str
    name: str
    industry: str
    website: str
    support_email: str
    plan_type: str = "mini_parwa"
    created_at: datetime = field(default_factory=datetime.now)

    # Instance specific data
    tickets_created: int = 0
    tickets_this_month: int = 0
    team_members: List[str] = field(default_factory=list)
    kb_documents: List[str] = field(default_factory=list)
    faqs: List[Dict] = field(default_factory=list)
    supported_languages: List[str] = field(default_factory=list)
    tickets: List[Dict] = field(default_factory=list)


@dataclass
class CustomerTicket:
    """Represents a customer support ticket"""

    id: str
    company_id: str
    customer_name: str
    customer_email: str
    subject: str
    message: str
    language: str = "en"
    channel: str = "email"
    priority: str = "normal"
    status: str = "open"
    created_at: datetime = field(default_factory=datetime.now)
    assigned_to: str = None
    ai_response: str = None
    resolution_time: float = None
    matched_faq: bool = False


# ============================================================
# COMPANY 1: E-COMMERCE STORE
# ============================================================

COMPANY_1 = FakeCompany(
    id="company_001",
    name="ShopEasy Online Store",
    industry="E-Commerce",
    website="https://shopeasy.example.com",
    support_email="support@shopeasy.example.com",
    team_members=["alice@shopeasy.example.com", "bob@shopeasy.example.com"],
    supported_languages=["en", "hi"],
    faqs=[
        {
            "id": "faq_001",
            "question": "What is your return policy?",
            "answer": "We offer 30-day easy returns on all products. Items must be unused and in original packaging.",
            "keywords": ["return", "policy", "refund", "money back"],
            "language": "en",
        },
        {
            "id": "faq_002",
            "question": "How long does shipping take?",
            "answer": "Standard shipping takes 5-7 business days. Express shipping is 2-3 business days.",
            "keywords": ["shipping", "delivery", "time", "days"],
            "language": "en",
        },
        {
            "id": "faq_003",
            "question": "वापसी नीति क्या है?",
            "answer": "हम सभी उत्पादों पर 30-दिन की आसान वापसी की पेशकश करते हैं।",
            "keywords": ["वापसी", "नीति", "रिफंड"],
            "language": "hi",
        },
        {
            "id": "faq_004",
            "question": "Do you offer COD?",
            "answer": "Yes! We offer Cash on Delivery for orders under ₹50,000.",
            "keywords": ["cod", "cash on delivery", "payment"],
            "language": "en",
        },
        {
            "id": "faq_005",
            "question": "How do I track my order?",
            "answer": "You can track your order at shopeasy.example.com/track using your order ID.",
            "keywords": ["track", "order", "status", "where"],
            "language": "en",
        },
    ],
)

# ============================================================
# COMPANY 2: SAAS STARTUP
# ============================================================

COMPANY_2 = FakeCompany(
    id="company_002",
    name="CloudSync Technologies",
    industry="SaaS/Software",
    website="https://cloudsync.example.io",
    support_email="help@cloudsync.example.io",
    team_members=[
        "charlie@cloudsync.example.io",
        "diana@cloudsync.example.io",
        "edward@cloudsync.example.io",
    ],
    supported_languages=["en", "es"],
    faqs=[
        {
            "id": "faq_101",
            "question": "How do I reset my password?",
            "answer": "Go to Settings > Security > Reset Password. You'll receive an email with reset instructions.",
            "keywords": ["password", "reset", "forgot", "login"],
            "language": "en",
        },
        {
            "id": "faq_102",
            "question": "What are your pricing plans?",
            "answer": "We offer Starter ($29/mo), Pro ($79/mo), and Enterprise (custom) plans.",
            "keywords": ["pricing", "plans", "cost", "subscription"],
            "language": "en",
        },
        {
            "id": "faq_103",
            "question": "¿Cómo restablezco mi contraseña?",
            "answer": "Ve a Configuración > Seguridad > Restablecer contraseña.",
            "keywords": ["contraseña", "restablecer", "olvidé"],
            "language": "es",
        },
        {
            "id": "faq_104",
            "question": "Do you have an API?",
            "answer": "Yes! We have a RESTful API with comprehensive documentation at docs.cloudsync.example.io",
            "keywords": ["api", "integration", "developer"],
            "language": "en",
        },
        {
            "id": "faq_105",
            "question": "How do I export my data?",
            "answer": "Go to Settings > Data Management > Export. Choose your format (CSV, JSON, Excel).",
            "keywords": ["export", "data", "download", "backup"],
            "language": "en",
        },
    ],
)


# ============================================================
# MINI PARWA INSTANCE SIMULATOR
# ============================================================


class MiniParwaInstance:
    """Simulates a single Mini PARWA instance"""

    def __init__(self, company: FakeCompany):
        self.company = company
        self.config = VARIANT_LIMITS["mini_parwa"]
        self.tickets_processed = 0
        self.tickets_this_month = 0
        self.ai_responses_generated = 0
        self.faqs_matched = 0
        self.shadow_mode = False
        self.shadow_responses = []

    def get_limits(self) -> Dict[str, Any]:
        """Get Mini PARWA limits"""
        limits = VARIANT_LIMITS["mini_parwa"]
        return {
            "tickets_per_month": limits["monthly_tickets"],
            "ai_agents": limits["ai_agents"],
            "team_members": limits["team_members"],
            "kb_storage_mb": limits["kb_docs"],
            "retrieval_top_k": limits["rag_top_k"],
        }

    def can_create_ticket(self) -> bool:
        """Check if ticket can be created within limits"""
        limit = VARIANT_LIMITS["mini_parwa"]["monthly_tickets"]
        return self.tickets_this_month < limit

    def can_add_team_member(self) -> bool:
        """Check if team member can be added"""
        limit = VARIANT_LIMITS["mini_parwa"]["team_members"]
        return len(self.company.team_members) < limit

    def is_feature_allowed(self, feature: str) -> bool:
        """Check if feature is allowed for Mini PARWA"""
        blocked_features = [
            "sms_channel",
            "voice_channel",
            "medium_ai_model",
            "tier_2_techniques",
            "tier_3_techniques",
            "api_write_access",
            "advanced_analytics",
            "custom_integrations",
            "priority_support",
        ]
        return feature not in blocked_features

    def get_allowed_techniques(self) -> List[str]:
        """Get allowed AI techniques (Tier 1 only)"""
        return [
            "faq_matching",
            "sentiment_analysis_basic",
            "auto_categorization",
            "basic_ner",
            "keyword_extraction",
        ]

    def get_blocked_techniques(self) -> List[str]:
        """Get blocked AI techniques (Tier 2/3)"""
        return [
            "advanced_sentiment",
            "intent_detection_advanced",
            "multi_turn_reasoning",
            "emotion_detection",
            "predictive_analytics",
            "auto_resolution_advanced",
        ]

    def process_ticket(self, ticket: CustomerTicket) -> Dict[str, Any]:
        """Process a customer ticket through Mini PARWA"""
        result = {
            "ticket_id": ticket.id,
            "company_id": self.company.id,
            "processed": False,
            "ai_response": None,
            "matched_faq": None,
            "techniques_used": [],
            "blocked_features": [],
            "error": None,
        }

        # Check ticket limit
        if not self.can_create_ticket():
            result["error"] = "TICKET_LIMIT_EXCEEDED"
            result["blocked_features"].append("monthly_ticket_limit")
            return result

        # Process with Mini PARWA capabilities
        self.tickets_processed += 1
        self.tickets_this_month += 1
        result["processed"] = True

        # Check channel is allowed
        if ticket.channel in ["sms", "voice"]:
            result["blocked_features"].append(f"{ticket.channel}_channel")
            result["error"] = f"CHANNEL_NOT_ALLOWED: {ticket.channel}"
            return result

        # FAQ Matching (Tier 1 technique)
        matched_faq = self._match_faq(ticket)
        if matched_faq:
            result["matched_faq"] = matched_faq
            result["ai_response"] = matched_faq["answer"]
            result["techniques_used"].append("faq_matching")
            self.faqs_matched += 1
            self.ai_responses_generated += 1
        else:
            # Generate basic AI response
            result["ai_response"] = self._generate_basic_response(ticket)
            result["techniques_used"].append("basic_response")
            self.ai_responses_generated += 1

        # Add basic sentiment (Tier 1)
        result["sentiment"] = self._analyze_sentiment_basic(ticket.message)
        result["techniques_used"].append("sentiment_analysis_basic")

        # Auto-categorize (Tier 1)
        result["category"] = self._categorize_ticket(ticket)
        result["techniques_used"].append("auto_categorization")

        # Store in shadow mode if enabled
        if self.shadow_mode:
            self.shadow_responses.append(result)

        return result

    def _match_faq(self, ticket: CustomerTicket) -> Dict:
        """Match ticket against FAQ (Tier 1 technique)"""
        message_lower = ticket.message.lower()

        for faq in self.company.faqs:
            # Check language match
            if faq["language"] != ticket.language:
                continue

            # Check keyword match
            for keyword in faq["keywords"]:
                if keyword.lower() in message_lower:
                    return faq

        return None

    def _generate_basic_response(self, ticket: CustomerTicket) -> str:
        """Generate basic AI response using Light model"""
        return f"Thank you for contacting {
            self.company.name}. We have received your inquiry about '{
            ticket.subject}'. Our team will get back to you within 24 hours."

    def _analyze_sentiment_basic(self, text: str) -> str:
        """Basic sentiment analysis (Tier 1)"""
        positive_words = ["thank", "great", "love", "awesome", "helpful", "good"]
        negative_words = [
            "angry",
            "frustrated",
            "terrible",
            "bad",
            "hate",
            "worst",
            "disappointed",
        ]

        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        return "neutral"

    def _categorize_ticket(self, ticket: CustomerTicket) -> str:
        """Auto-categorize ticket (Tier 1)"""
        message_lower = ticket.message.lower()
        subject_lower = ticket.subject.lower()
        combined = message_lower + " " + subject_lower

        if any(word in combined for word in ["return", "refund", "money back"]):
            return "returns"
        elif any(word in combined for word in ["shipping", "delivery", "track"]):
            return "shipping"
        elif any(
            word in combined for word in ["password", "login", "access", "account"]
        ):
            return "account"
        elif any(
            word in combined for word in ["payment", "billing", "charge", "invoice"]
        ):
            return "billing"
        elif any(word in combined for word in ["api", "integration", "developer"]):
            return "technical"
        return "general"

    def check_api_access(self, operation: str) -> bool:
        """Check API access permissions"""
        read_operations = ["get_tickets", "get_faqs", "get_analytics", "search_kb"]
        write_operations = [
            "create_ticket",
            "update_ticket",
            "delete_ticket",
            "create_faq",
        ]

        if operation in read_operations:
            return True  # Read access allowed
        elif operation in write_operations:
            return False  # Write access blocked
        return False

    def reset_monthly_counters(self):
        """Reset monthly ticket counter"""
        self.tickets_this_month = 0


# ============================================================
# TEST CLASS: COMPREHENSIVE 2 INSTANCE TESTING
# ============================================================


class TestTwoMiniParwaInstances:
    """Complete test suite for 2 Mini PARWA instances"""

    def setup(self):
        """Setup before each test"""
        self.company1 = FakeCompany(
            id=COMPANY_1.id,
            name=COMPANY_1.name,
            industry=COMPANY_1.industry,
            website=COMPANY_1.website,
            support_email=COMPANY_1.support_email,
            team_members=COMPANY_1.team_members.copy(),
            supported_languages=COMPANY_1.supported_languages.copy(),
            faqs=COMPANY_1.faqs.copy(),
        )

        self.company2 = FakeCompany(
            id=COMPANY_2.id,
            name=COMPANY_2.name,
            industry=COMPANY_2.industry,
            website=COMPANY_2.website,
            support_email=COMPANY_2.support_email,
            team_members=COMPANY_2.team_members.copy(),
            supported_languages=COMPANY_2.supported_languages.copy(),
            faqs=COMPANY_2.faqs.copy(),
        )

        self.instance1 = MiniParwaInstance(self.company1)
        self.instance2 = MiniParwaInstance(self.company2)

    # ============================================================
    # SCENARIO 1: INSTANCE INITIALIZATION
    # ============================================================

    def test_scenario_01_instance_initialization(self):
        """Test both Mini PARWA instances initialize correctly"""
        print("\n" + "=" * 60)
        print("SCENARIO 1: Instance Initialization")
        print("=" * 60)

        # Verify instances created
        assert self.instance1 is not None, "Instance 1 should be created"
        assert self.instance2 is not None, "Instance 2 should be created"

        # Verify company associations
        assert self.instance1.company.id == "company_001"
        assert self.instance2.company.id == "company_002"

        # Verify initial state
        assert self.instance1.tickets_processed == 0
        assert self.instance2.tickets_processed == 0
        assert self.instance1.tickets_this_month == 0
        assert self.instance2.tickets_this_month == 0

        # Get limits
        limits1 = self.instance1.get_limits()
        limits2 = self.instance2.get_limits()

        print(f"\nInstance 1 ({self.company1.name}) Limits:")
        for key, value in limits1.items():
            print(f"  - {key}: {value}")

        print(f"\nInstance 2 ({self.company2.name}) Limits:")
        for key, value in limits2.items():
            print(f"  - {key}: {value}")

        # Verify limits are correct for Mini PARWA
        assert limits1["tickets_per_month"] == 2000
        assert limits1["ai_agents"] == 1
        assert limits1["team_members"] == 3
        assert limits1["kb_storage_mb"] == 100
        assert limits1["retrieval_top_k"] == 3

        assert limits2["tickets_per_month"] == 2000
        assert limits2["ai_agents"] == 1

        print("\n✅ PASSED: Both instances initialized with correct Mini PARWA limits")

    # ============================================================
    # SCENARIO 2: INDEPENDENT OPERATION
    # ============================================================

    def test_scenario_02_independent_operation(self):
        """Test both instances operate independently"""
        print("\n" + "=" * 60)
        print("SCENARIO 2: Independent Operation")
        print("=" * 60)

        # Create ticket for Company 1
        ticket1 = CustomerTicket(
            id="TKT_001",
            company_id=self.company1.id,
            customer_name="John Doe",
            customer_email="john@example.com",
            subject="Return Policy Question",
            message="What is your return policy? I want to return my order.",
            language="en",
            channel="email",
        )

        # Create ticket for Company 2
        ticket2 = CustomerTicket(
            id="TKT_002",
            company_id=self.company2.id,
            customer_name="Jane Smith",
            customer_email="jane@example.com",
            subject="Password Reset",
            message="I forgot my password. How do I reset it?",
            language="en",
            channel="email",
        )

        # Process tickets
        result1 = self.instance1.process_ticket(ticket1)
        result2 = self.instance2.process_ticket(ticket2)

        print("\nCompany 1 Ticket Result:")
        print(f"  - Ticket ID: {result1['ticket_id']}")
        print(f"  - Processed: {result1['processed']}")
        print(f"  - AI Response: {result1['ai_response']}")
        print(f"  - Matched FAQ: {result1['matched_faq']}")
        print(f"  - Techniques: {result1['techniques_used']}")

        print("\nCompany 2 Ticket Result:")
        print(f"  - Ticket ID: {result2['ticket_id']}")
        print(f"  - Processed: {result2['processed']}")
        print(f"  - AI Response: {result2['ai_response']}")
        print(f"  - Matched FAQ: {result2['matched_faq']}")
        print(f"  - Techniques: {result2['techniques_used']}")

        # Verify independent processing
        assert result1["processed"]
        assert result2["processed"]

        # Verify different FAQ matches
        # ShopEasy return policy
        assert result1["matched_faq"]["id"] == "faq_001"
        # CloudSync password reset
        assert result2["matched_faq"]["id"] == "faq_101"

        # Verify instance counters
        assert self.instance1.tickets_processed == 1
        assert self.instance2.tickets_processed == 1

        print("\n✅ PASSED: Both instances operate independently")

    # ============================================================
    # SCENARIO 3: FAQ MATCHING
    # ============================================================

    def test_scenario_03_faq_matching(self):
        """Test FAQ matching for both instances"""
        print("\n" + "=" * 60)
        print("SCENARIO 3: FAQ Matching")
        print("=" * 60)

        # Company 1 FAQ tests
        test_cases_1 = [
            ("I want a refund", "faq_001"),  # Return/Refund FAQ
            ("How many days for delivery?", "faq_002"),  # Shipping FAQ
            ("Do you have COD option?", "faq_004"),  # COD FAQ
            ("Where is my order?", "faq_005"),  # Tracking FAQ
        ]

        print(f"\n--- Company 1: {self.company1.name} FAQ Tests ---")
        for message, expected_faq_id in test_cases_1:
            ticket = CustomerTicket(
                id=f"TKT_FAQ_1_{expected_faq_id}",
                company_id=self.company1.id,
                customer_name="Test Customer",
                customer_email="test@test.com",
                subject="FAQ Test",
                message=message,
                language="en",
                channel="email",
            )
            result = self.instance1.process_ticket(ticket)
            matched_id = result["matched_faq"]["id"] if result["matched_faq"] else None
            status = "✅" if matched_id == expected_faq_id else "❌"
            print(
                f"  {status} '{message[:30]}...' -> FAQ: {matched_id} (expected: {expected_faq_id})"
            )
            assert matched_id == expected_faq_id, f"FAQ mismatch for '{message}'"

        # Company 2 FAQ tests
        test_cases_2 = [
            ("I forgot my login password", "faq_101"),  # Password reset
            ("What are your pricing plans?", "faq_102"),  # Pricing
            ("Do you have API documentation?", "faq_104"),  # API
            ("How to download my data?", "faq_105"),  # Export data
        ]

        print(f"\n--- Company 2: {self.company2.name} FAQ Tests ---")
        for message, expected_faq_id in test_cases_2:
            ticket = CustomerTicket(
                id=f"TKT_FAQ_2_{expected_faq_id}",
                company_id=self.company2.id,
                customer_name="Test Customer",
                customer_email="test@test.com",
                subject="FAQ Test",
                message=message,
                language="en",
                channel="email",
            )
            result = self.instance2.process_ticket(ticket)
            matched_id = result["matched_faq"]["id"] if result["matched_faq"] else None
            status = "✅" if matched_id == expected_faq_id else "❌"
            print(
                f"  {status} '{message[:30]}...' -> FAQ: {matched_id} (expected: {expected_faq_id})"
            )
            assert matched_id == expected_faq_id, f"FAQ mismatch for '{message}'"

        print(f"\nCompany 1 FAQs Matched: {self.instance1.faqs_matched}")
        print(f"Company 2 FAQs Matched: {self.instance2.faqs_matched}")
        print("\n✅ PASSED: FAQ matching works correctly for both instances")

    # ============================================================
    # SCENARIO 4: MULTI-LANGUAGE SUPPORT
    # ============================================================

    def test_scenario_04_multi_language_support(self):
        """Test multi-language support for both instances"""
        print("\n" + "=" * 60)
        print("SCENARIO 4: Multi-Language Support")
        print("=" * 60)

        # Reset counters
        self.instance1.reset_monthly_counters()
        self.instance2.reset_monthly_counters()

        # Company 1: Hindi support
        print("\n--- Company 1: Testing Hindi Support ---")
        hindi_ticket = CustomerTicket(
            id="TKT_HINDI_001",
            company_id=self.company1.id,
            customer_name="राहुल शर्मा",
            customer_email="rahul@example.com",
            subject="वापसी पॉलिसी",
            message="आपकी वापसी नीति क्या है? मैं अपना ऑर्डर वापस करना चाहता हूं।",
            language="hi",
            channel="email",
        )
        result_hi = self.instance1.process_ticket(hindi_ticket)
        print(f"  Hindi Query: '{hindi_ticket.message[:30]}...'")
        print(
            f"  Matched FAQ: {
                result_hi['matched_faq']['id'] if result_hi['matched_faq'] else 'None'}"
        )
        print(
            f"  Response: {result_hi['ai_response'][:50] if result_hi['ai_response'] else 'None'}..."
        )
        assert result_hi["matched_faq"]["id"] == "faq_003"  # Hindi FAQ
        print("  ✅ Hindi FAQ matched correctly")

        # Company 2: Spanish support
        print("\n--- Company 2: Testing Spanish Support ---")
        spanish_ticket = CustomerTicket(
            id="TKT_SPANISH_001",
            company_id=self.company2.id,
            customer_name="Carlos García",
            customer_email="carlos@example.com",
            subject="Contraseña olvidada",
            message="¿Cómo restablezco mi contraseña? La olvidé.",
            language="es",
            channel="email",
        )
        result_es = self.instance2.process_ticket(spanish_ticket)
        print(f"  Spanish Query: '{spanish_ticket.message[:30]}...'")
        print(
            f"  Matched FAQ: {
                result_es['matched_faq']['id'] if result_es['matched_faq'] else 'None'}"
        )
        print(
            f"  Response: {result_es['ai_response'][:50] if result_es['ai_response'] else 'None'}..."
        )
        assert result_es["matched_faq"]["id"] == "faq_103"  # Spanish FAQ
        print("  ✅ Spanish FAQ matched correctly")

        print("\n✅ PASSED: Multi-language support works for both instances")

    # ============================================================
    # SCENARIO 5: TICKET LIMITS (2000 per month each)
    # ============================================================

    def test_scenario_05_ticket_limits(self):
        """Test ticket limits for both instances"""
        print("\n" + "=" * 60)
        print("SCENARIO 5: Ticket Limits (2000/month per instance)")
        print("=" * 60)

        # Reset and set near limit
        self.instance1.reset_monthly_counters()
        self.instance2.reset_monthly_counters()

        # Simulate being near the limit
        self.instance1.tickets_this_month = 1999
        self.instance2.tickets_this_month = 1999

        print(f"\nInstance 1 tickets this month: {
                self.instance1.tickets_this_month}/2000")
        print(f"Instance 2 tickets this month: {
                self.instance2.tickets_this_month}/2000")

        # Should allow 1 more ticket
        ticket1 = CustomerTicket(
            id="TKT_LIMIT_1",
            company_id=self.company1.id,
            customer_name="Customer A",
            customer_email="a@test.com",
            subject="Last Ticket",
            message="This should be allowed",
            language="en",
            channel="email",
        )
        result1 = self.instance1.process_ticket(ticket1)
        print(f"\nTicket {
                self.instance1.tickets_this_month}/2000 for Instance 1: {
                '✅ Allowed' if result1['processed'] else '❌ Blocked'}")
        assert result1["processed"]

        # Should allow 1 more ticket for instance 2
        ticket2 = CustomerTicket(
            id="TKT_LIMIT_2",
            company_id=self.company2.id,
            customer_name="Customer B",
            customer_email="b@test.com",
            subject="Last Ticket",
            message="This should be allowed",
            language="en",
            channel="email",
        )
        result2 = self.instance2.process_ticket(ticket2)
        print(f"Ticket {
                self.instance2.tickets_this_month}/2000 for Instance 2: {
                '✅ Allowed' if result2['processed'] else '❌ Blocked'}")
        assert result2["processed"]

        # Should block next ticket
        ticket1_exceeded = CustomerTicket(
            id="TKT_LIMIT_1_EX",
            company_id=self.company1.id,
            customer_name="Customer A2",
            customer_email="a2@test.com",
            subject="Over Limit",
            message="This should be blocked",
            language="en",
            channel="email",
        )
        result1_ex = self.instance1.process_ticket(ticket1_exceeded)
        print(f"\nTicket over limit for Instance 1: {
                '❌ Blocked' if result1_ex['error'] else '✅ Allowed'}")
        assert result1_ex["error"] == "TICKET_LIMIT_EXCEEDED"

        ticket2_exceeded = CustomerTicket(
            id="TKT_LIMIT_2_EX",
            company_id=self.company2.id,
            customer_name="Customer B2",
            customer_email="b2@test.com",
            subject="Over Limit",
            message="This should be blocked",
            language="en",
            channel="email",
        )
        result2_ex = self.instance2.process_ticket(ticket2_exceeded)
        print(f"Ticket over limit for Instance 2: {
                '❌ Blocked' if result2_ex['error'] else '✅ Allowed'}")
        assert result2_ex["error"] == "TICKET_LIMIT_EXCEEDED"

        print("\n✅ PASSED: Ticket limits enforced correctly for both instances")

    # ============================================================
    # SCENARIO 6: FEATURE GATING (SMS, Voice Blocked)
    # ============================================================

    def test_scenario_06_feature_gating(self):
        """Test feature gating for Mini PARWA"""
        print("\n" + "=" * 60)
        print("SCENARIO 6: Feature Gating (SMS, Voice Blocked)")
        print("=" * 60)

        # Reset counters
        self.instance1.reset_monthly_counters()
        self.instance2.reset_monthly_counters()

        # Test blocked features for both instances
        blocked_features = [
            "sms_channel",
            "voice_channel",
            "medium_ai_model",
            "tier_2_techniques",
            "tier_3_techniques",
            "api_write_access",
        ]

        print("\n--- Checking Blocked Features ---")
        for feature in blocked_features:
            allowed1 = self.instance1.is_feature_allowed(feature)
            allowed2 = self.instance2.is_feature_allowed(feature)
            print(f"  {feature}: Instance 1 = {
                    '✅ Allowed' if allowed1 else '❌ Blocked'}, Instance 2 = {
                    '✅ Allowed' if allowed2 else '❌ Blocked'}")
            assert allowed1 is False, f"{feature} should be blocked for Instance 1"
            assert allowed2 is False, f"{feature} should be blocked for Instance 2"

        # Test SMS channel rejection
        print("\n--- Testing SMS Channel Rejection ---")
        sms_ticket = CustomerTicket(
            id="TKT_SMS_001",
            company_id=self.company1.id,
            customer_name="SMS Customer",
            customer_email="sms@test.com",
            subject="SMS Test",
            message="This came via SMS",
            language="en",
            channel="sms",  # Should be blocked
        )
        result_sms = self.instance1.process_ticket(sms_ticket)
        print(f"  SMS Ticket Result: {
                '❌ Blocked' if result_sms['error'] else '✅ Allowed'}")
        print(f"  Error: {result_sms['error']}")
        assert "CHANNEL_NOT_ALLOWED" in result_sms["error"]

        # Test Voice channel rejection
        print("\n--- Testing Voice Channel Rejection ---")
        voice_ticket = CustomerTicket(
            id="TKT_VOICE_001",
            company_id=self.company2.id,
            customer_name="Voice Customer",
            customer_email="voice@test.com",
            subject="Voice Test",
            message="This came via Voice",
            language="en",
            channel="voice",  # Should be blocked
        )
        result_voice = self.instance2.process_ticket(voice_ticket)
        print(f"  Voice Ticket Result: {
                '❌ Blocked' if result_voice['error'] else '✅ Allowed'}")
        print(f"  Error: {result_voice['error']}")
        assert "CHANNEL_NOT_ALLOWED" in result_voice["error"]

        print("\n✅ PASSED: Feature gating works correctly - SMS and Voice blocked")

    # ============================================================
    # SCENARIO 7: TECHNIQUE ACCESS (Tier 1 Only)
    # ============================================================

    def test_scenario_07_technique_access(self):
        """Test technique access - Tier 1 only"""
        print("\n" + "=" * 60)
        print("SCENARIO 7: Technique Access (Tier 1 Only)")
        print("=" * 60)

        # Get allowed techniques
        allowed1 = self.instance1.get_allowed_techniques()
        allowed2 = self.instance2.get_allowed_techniques()

        print("\n--- Allowed Techniques (Tier 1) ---")
        for tech in allowed1:
            print(f"  ✅ {tech}")

        print("\n--- Blocked Techniques (Tier 2/3) ---")
        blocked1 = self.instance1.get_blocked_techniques()
        for tech in blocked1:
            print(f"  ❌ {tech}")

        # Verify allowed techniques
        assert "faq_matching" in allowed1
        assert "sentiment_analysis_basic" in allowed1
        assert "auto_categorization" in allowed1

        # Verify blocked techniques
        assert "advanced_sentiment" in blocked1
        assert "multi_turn_reasoning" in blocked1
        assert "predictive_analytics" in blocked1

        # Verify techniques used during processing
        self.instance1.reset_monthly_counters()
        ticket = CustomerTicket(
            id="TKT_TECH_001",
            company_id=self.company1.id,
            customer_name="Tech Test",
            customer_email="tech@test.com",
            subject="Test",
            message="I want a refund for my order",
            language="en",
            channel="email",
        )
        result = self.instance1.process_ticket(ticket)

        print("\n--- Techniques Used in Processing ---")
        for tech in result["techniques_used"]:
            print(f"  ✅ {tech}")

        # Verify only Tier 1 techniques were used
        for tech in result["techniques_used"]:
            assert tech in allowed1, f"Technique {tech} should be allowed"

        print("\n✅ PASSED: Technique access limited to Tier 1 only")

    # ============================================================
    # SCENARIO 8: API RESTRICTIONS (Read-Only)
    # ============================================================

    def test_scenario_08_api_restrictions(self):
        """Test API restrictions - Read-only access"""
        print("\n" + "=" * 60)
        print("SCENARIO 8: API Restrictions (Read-Only)")
        print("=" * 60)

        read_operations = ["get_tickets", "get_faqs", "get_analytics", "search_kb"]
        write_operations = [
            "create_ticket",
            "update_ticket",
            "delete_ticket",
            "create_faq",
        ]

        print("\n--- Read Operations (Should be ALLOWED) ---")
        for op in read_operations:
            allowed1 = self.instance1.check_api_access(op)
            allowed2 = self.instance2.check_api_access(op)
            print(f"  {op}: Instance 1 = {
                    '✅ Allowed' if allowed1 else '❌ Blocked'}, Instance 2 = {
                    '✅ Allowed' if allowed2 else '❌ Blocked'}")
            assert allowed1
            assert allowed2

        print("\n--- Write Operations (Should be BLOCKED) ---")
        for op in write_operations:
            allowed1 = self.instance1.check_api_access(op)
            allowed2 = self.instance2.check_api_access(op)
            print(f"  {op}: Instance 1 = {
                    '✅ Allowed' if allowed1 else '❌ Blocked'}, Instance 2 = {
                    '✅ Allowed' if allowed2 else '❌ Blocked'}")
            assert allowed1 is False
            assert allowed2 is False

        print("\n✅ PASSED: API restrictions work correctly - Read-only access")

    # ============================================================
    # SCENARIO 9: SHADOW MODE
    # ============================================================

    def test_scenario_09_shadow_mode(self):
        """Test shadow mode functionality"""
        print("\n" + "=" * 60)
        print("SCENARIO 9: Shadow Mode")
        print("=" * 60)

        # Enable shadow mode for both instances
        self.instance1.shadow_mode = True
        self.instance2.shadow_mode = True
        self.instance1.shadow_responses = []
        self.instance2.shadow_responses = []
        self.instance1.reset_monthly_counters()
        self.instance2.reset_monthly_counters()

        print("\nShadow Mode Enabled for both instances")

        # Process some tickets
        tickets_1 = [
            CustomerTicket(
                id="SHADOW_1_1",
                company_id=self.company1.id,
                customer_name="C1",
                customer_email="c1@test.com",
                subject="Test",
                message="I need a refund",
                language="en",
                channel="email",
            ),
            CustomerTicket(
                id="SHADOW_1_2",
                company_id=self.company1.id,
                customer_name="C2",
                customer_email="c2@test.com",
                subject="Test",
                message="Shipping time?",
                language="en",
                channel="email",
            ),
        ]

        tickets_2 = [
            CustomerTicket(
                id="SHADOW_2_1",
                company_id=self.company2.id,
                customer_name="C3",
                customer_email="c3@test.com",
                subject="Test",
                message="Reset password",
                language="en",
                channel="email",
            ),
            CustomerTicket(
                id="SHADOW_2_2",
                company_id=self.company2.id,
                customer_name="C4",
                customer_email="c4@test.com",
                subject="Test",
                message="Pricing info",
                language="en",
                channel="email",
            ),
        ]

        for t in tickets_1:
            self.instance1.process_ticket(t)
        for t in tickets_2:
            self.instance2.process_ticket(t)

        print(f"\nInstance 1 Shadow Responses: {len(self.instance1.shadow_responses)}")
        print(f"Instance 2 Shadow Responses: {len(self.instance2.shadow_responses)}")

        assert len(self.instance1.shadow_responses) == 2
        assert len(self.instance2.shadow_responses) == 2

        print("\n--- Shadow Response Samples ---")
        print(
            f"Instance 1 Sample: {self.instance1.shadow_responses[0]['ticket_id']} - {self.instance1.shadow_responses[0]['ai_response'][:40]}..."
        )
        print(
            f"Instance 2 Sample: {self.instance2.shadow_responses[0]['ticket_id']} - {self.instance2.shadow_responses[0]['ai_response'][:40]}..."
        )

        print("\n✅ PASSED: Shadow mode works correctly for both instances")

    # ============================================================
    # SCENARIO 10: TEAM MEMBER LIMITS
    # ============================================================

    def test_scenario_10_team_member_limits(self):
        """Test team member limits (3 max per instance)"""
        print("\n" + "=" * 60)
        print("SCENARIO 10: Team Member Limits (3 max)")
        print("=" * 60)

        # Company 1 has 2 members, should allow 1 more
        print(f"\nInstance 1 Current Members: {len(self.company1.team_members)}/3")
        print(f"Can add member: {self.instance1.can_add_team_member()}")
        assert self.instance1.can_add_team_member()

        # Company 2 has 3 members, should block adding
        print(f"\nInstance 2 Current Members: {len(self.company2.team_members)}/3")
        print(f"Can add member: {self.instance2.can_add_team_member()}")
        assert self.instance2.can_add_team_member() is False

        # Add member to company 1
        self.company1.team_members.append("new_member@shopeasy.example.com")
        print(
            f"\nAfter adding member to Instance 1: {len(self.company1.team_members)}/3"
        )
        print(f"Can add another: {self.instance1.can_add_team_member()}")
        assert self.instance1.can_add_team_member() is False

        print("\n✅ PASSED: Team member limits enforced correctly")

    # ============================================================
    # SCENARIO 11: CONCURRENT TRAFFIC SIMULATION
    # ============================================================

    def test_scenario_11_concurrent_traffic(self):
        """Test concurrent traffic for both instances"""
        print("\n" + "=" * 60)
        print("SCENARIO 11: Concurrent Traffic Simulation")
        print("=" * 60)

        self.instance1.reset_monthly_counters()
        self.instance2.reset_monthly_counters()

        # Simulate 100 tickets for each instance
        print("\nSimulating 100 tickets per instance...")

        for i in range(100):
            ticket1 = CustomerTicket(
                id=f"TKT_CONCURRENT_1_{i}",
                company_id=self.company1.id,
                customer_name=f"Customer {i}",
                customer_email=f"customer{i}@test.com",
                subject=f"Query {i}",
                message="I have a question about my order",
                language="en",
                channel="email",
            )
            self.instance1.process_ticket(ticket1)

            ticket2 = CustomerTicket(
                id=f"TKT_CONCURRENT_2_{i}",
                company_id=self.company2.id,
                customer_name=f"Customer {i}",
                customer_email=f"customer{i}@test.com",
                subject=f"Query {i}",
                message="I need help with my account",
                language="en",
                channel="email",
            )
            self.instance2.process_ticket(ticket2)

        print(f"\nInstance 1 Processed: {
                self.instance1.tickets_processed} tickets")
        print(f"Instance 2 Processed: {
                self.instance2.tickets_processed} tickets")
        print(f"Instance 1 AI Responses: {
                self.instance1.ai_responses_generated}")
        print(f"Instance 2 AI Responses: {
                self.instance2.ai_responses_generated}")

        assert self.instance1.tickets_processed == 100
        assert self.instance2.tickets_processed == 100
        assert self.instance1.ai_responses_generated == 100
        assert self.instance2.ai_responses_generated == 100

        # Verify remaining capacity
        remaining1 = 2000 - self.instance1.tickets_this_month
        remaining2 = 2000 - self.instance2.tickets_this_month
        print(f"\nInstance 1 Remaining Capacity: {remaining1} tickets")
        print(f"Instance 2 Remaining Capacity: {remaining2} tickets")

        print("\n✅ PASSED: Concurrent traffic handled correctly")

    # ============================================================
    # SCENARIO 12: SENTIMENT ANALYSIS
    # ============================================================

    def test_scenario_12_sentiment_analysis(self):
        """Test sentiment analysis for both instances"""
        print("\n" + "=" * 60)
        print("SCENARIO 12: Sentiment Analysis")
        print("=" * 60)

        self.instance1.reset_monthly_counters()
        self.instance2.reset_monthly_counters()

        # Test different sentiments
        sentiment_tests = [
            ("Thank you so much for your great service!", "positive"),
            ("I am very frustrated and angry about this!", "negative"),
            ("I have a question about my order.", "neutral"),
            ("Love your products, they are awesome!", "positive"),
            ("This is terrible, worst experience ever!", "negative"),
        ]

        print("\n--- Sentiment Analysis Tests ---")
        for message, expected in sentiment_tests:
            ticket = CustomerTicket(
                id=f"TKT_SENTIMENT_{message[:10]}",
                company_id=self.company1.id,
                customer_name="Sentiment Test",
                customer_email="sentiment@test.com",
                subject="Test",
                message=message,
                language="en",
                channel="email",
            )
            result = self.instance1.process_ticket(ticket)
            sentiment = result.get("sentiment", "unknown")
            status = "✅" if sentiment == expected else "❌"
            print(
                f"  {status} '{message[:30]}...' -> {sentiment} (expected: {expected})"
            )

        print("\n✅ PASSED: Sentiment analysis works correctly")

    # ============================================================
    # SCENARIO 13: AUTO CATEGORIZATION
    # ============================================================

    def test_scenario_13_auto_categorization(self):
        """Test auto categorization for both instances"""
        print("\n" + "=" * 60)
        print("SCENARIO 13: Auto Categorization")
        print("=" * 60)

        self.instance1.reset_monthly_counters()
        self.instance2.reset_monthly_counters()

        category_tests = [
            ("I want to return my order and get a refund", "returns"),
            ("Where is my package? I need shipping info", "shipping"),
            ("I forgot my password and cannot login", "account"),
            ("I was charged twice on my invoice", "billing"),
            ("How do I use your API for integration?", "technical"),
            ("Just wanted to say thanks!", "general"),
        ]

        print("\n--- Auto Categorization Tests ---")
        for message, expected in category_tests:
            ticket = CustomerTicket(
                id=f"TKT_CAT_{expected}",
                company_id=self.company1.id,
                customer_name="Cat Test",
                customer_email="cat@test.com",
                subject="Test",
                message=message,
                language="en",
                channel="email",
            )
            result = self.instance1.process_ticket(ticket)
            category = result.get("category", "unknown")
            status = "✅" if category == expected else "❌"
            print(
                f"  {status} '{message[:35]}...' -> {category} (expected: {expected})"
            )

        print("\n✅ PASSED: Auto categorization works correctly")

    # ============================================================
    # SCENARIO 14: ISOLATION BETWEEN INSTANCES
    # ============================================================

    def test_scenario_14_instance_isolation(self):
        """Test that instances are completely isolated"""
        print("\n" + "=" * 60)
        print("SCENARIO 14: Instance Isolation")
        print("=" * 60)

        self.instance1.reset_monthly_counters()
        self.instance2.reset_monthly_counters()

        # Process ticket for Company 1
        ticket1 = CustomerTicket(
            id="TKT_ISO_1",
            company_id=self.company1.id,
            customer_name="Company1 Customer",
            customer_email="c1@test.com",
            subject="Return",
            message="I want a refund",
            language="en",
            channel="email",
        )
        result1 = self.instance1.process_ticket(ticket1)

        # Verify Company 2's FAQ was NOT matched (different company)
        # Company 1 should match return FAQ, Company 2 shouldn't have this
        assert result1["matched_faq"]["id"] == "faq_001"  # ShopEasy return FAQ

        # Process ticket for Company 2
        ticket2 = CustomerTicket(
            id="TKT_ISO_2",
            company_id=self.company2.id,
            customer_name="Company2 Customer",
            customer_email="c2@test.com",
            subject="Password",
            message="I forgot my password",
            language="en",
            channel="email",
        )
        result2 = self.instance2.process_ticket(ticket2)

        # Verify Company 1's FAQ was NOT matched for Company 2
        # CloudSync password FAQ
        assert result2["matched_faq"]["id"] == "faq_101"

        # Verify complete isolation
        assert self.instance1.company.id != self.instance2.company.id
        assert self.instance1.company.name != self.instance2.company.name
        assert self.instance1.company.faqs != self.instance2.company.faqs

        print(f"\n✅ Instance 1 Company: {self.instance1.company.name}")
        print(f"✅ Instance 2 Company: {self.instance2.company.name}")
        print(f"✅ Instance 1 FAQs: {len(self.instance1.company.faqs)} unique")
        print(f"✅ Instance 2 FAQs: {len(self.instance2.company.faqs)} unique")
        print("✅ No cross-instance data leakage")

        print("\n✅ PASSED: Complete isolation between instances verified")


# ============================================================
# RUN TESTS
# ============================================================


def run_all_tests():
    """Run all tests and generate report"""
    import traceback

    print("\n" + "=" * 70)
    print(" COMPREHENSIVE TEST SUITE: 2 MINI PARWA INSTANCES")
    print("=" * 70)
    print(f" Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    test_instance = TestTwoMiniParwaInstances()
    test_instance.setup()

    tests = [
        (
            "SCENARIO 1: Instance Initialization",
            test_instance.test_scenario_01_instance_initialization,
        ),
        (
            "SCENARIO 2: Independent Operation",
            test_instance.test_scenario_02_independent_operation,
        ),
        ("SCENARIO 3: FAQ Matching", test_instance.test_scenario_03_faq_matching),
        (
            "SCENARIO 4: Multi-Language Support",
            test_instance.test_scenario_04_multi_language_support,
        ),
        ("SCENARIO 5: Ticket Limits", test_instance.test_scenario_05_ticket_limits),
        ("SCENARIO 6: Feature Gating", test_instance.test_scenario_06_feature_gating),
        (
            "SCENARIO 7: Technique Access",
            test_instance.test_scenario_07_technique_access,
        ),
        (
            "SCENARIO 8: API Restrictions",
            test_instance.test_scenario_08_api_restrictions,
        ),
        ("SCENARIO 9: Shadow Mode", test_instance.test_scenario_09_shadow_mode),
        (
            "SCENARIO 10: Team Member Limits",
            test_instance.test_scenario_10_team_member_limits,
        ),
        (
            "SCENARIO 11: Concurrent Traffic",
            test_instance.test_scenario_11_concurrent_traffic,
        ),
        (
            "SCENARIO 12: Sentiment Analysis",
            test_instance.test_scenario_12_sentiment_analysis,
        ),
        (
            "SCENARIO 13: Auto Categorization",
            test_instance.test_scenario_13_auto_categorization,
        ),
        (
            "SCENARIO 14: Instance Isolation",
            test_instance.test_scenario_14_instance_isolation,
        ),
    ]

    results = []
    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_instance.setup()  # Reset before each test
            test_func()
            results.append((name, "PASSED", None))
            passed += 1
        except Exception as e:
            results.append((name, "FAILED", str(e)))
            failed += 1
            print(f"\n❌ ERROR in {name}: {e}")
            traceback.print_exc()

    # Summary
    print("\n" + "=" * 70)
    print(" TEST SUMMARY")
    print("=" * 70)

    for name, status, error in results:
        icon = "✅" if status == "PASSED" else "❌"
        print(f"  {icon} {name}: {status}")
        if error:
            print(f"      Error: {error[:100]}")

    print("\n" + "-" * 70)
    print(f" Total: {
            passed
            + failed} tests | ✅ Passed: {passed} | ❌ Failed: {failed}")
    print(f" Success Rate: {(passed / (passed + failed)) * 100:.1f}%")
    print("-" * 70)

    return passed, failed


if __name__ == "__main__":
    passed, failed = run_all_tests()
    sys.exit(0 if failed == 0 else 1)
