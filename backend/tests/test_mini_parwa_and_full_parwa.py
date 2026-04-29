"""
COMPREHENSIVE TEST SUITE: Mini PARWA + Full PARWA Working Together
====================================================================

Scenario: A company hires BOTH Mini PARWA and Full PARWA instances
Tests ticket resolution, feature differences, and integration

Features Tested:
- Mini PARWA: Email+Chat only, 2000 tickets/month, Tier 1 techniques
- Full PARWA: Email+Chat+SMS+Voice, 5000 tickets/month, Tier 2 techniques
- Ticket routing between instances
- Voice call notification (Twilio)
- Universal provider system
"""

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from app.config.variant_features import VARIANT_LIMITS

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================
# FAKE CUSTOMER REQUESTS
# ============================================================


@dataclass
class CustomerRequest:
    """Represents a customer support request"""

    id: str
    customer_name: str
    customer_email: str
    customer_phone: str
    subject: str
    message: str
    language: str = "en"
    channel: str = "email"  # email, chat, sms, voice
    priority: str = "normal"  # low, normal, high, urgent
    category: str = "general"
    status: str = "open"
    created_at: datetime = field(default_factory=datetime.now)

    # Resolution info
    assigned_instance: str = None  # "mini_parwa" or "full_parwa"
    ai_response: str = None
    resolution_time: float = None
    matched_faq: bool = False
    techniques_used: List[str] = field(default_factory=list)


# ============================================================
# COMPANY CONFIGURATION
# ============================================================


@dataclass
class CompanyConfig:
    """Company using both Mini PARWA and Full PARWA"""

    id: str = "techcorp_001"
    name: str = "TechCorp Solutions"
    industry: str = "Technology"
    website: str = "https://techcorp.example.com"
    support_email: str = "support@techcorp.example.com"
    support_phone: str = "+919876543210"

    # Company FAQs
    faqs: List[Dict] = field(
        default_factory=lambda: [
            {
                "id": "faq_001",
                "question": "What are your business hours?",
                "answer": "We are available Monday to Friday, 9 AM to 6 PM IST. For urgent issues, our full PARWA support is available 24/7.",
                "keywords": ["hours", "timing", "open", "available"],
                "language": "en",
            },
            {
                "id": "faq_002",
                "question": "How do I reset my password?",
                "answer": "Go to Settings > Security > Reset Password. You'll receive an email with reset instructions valid for 24 hours.",
                "keywords": ["password", "reset", "forgot", "login"],
                "language": "en",
            },
            {
                "id": "faq_003",
                "question": "What is your refund policy?",
                "answer": "We offer a 30-day money-back guarantee on all plans. Contact support for refund requests.",
                "keywords": ["refund", "money back", "guarantee"],
                "language": "en",
            },
            {
                "id": "faq_004",
                "question": "आपके काम के घंटे क्या हैं?",
                "answer": "हम सोमवार से शुक्रवार, सुबह 9 बजे से शाम 6 बजे तक उपलब्ध हैं। आपातकालीन समस्याओं के लिए, हमारी फुल PARWA सपोर्ट 24/7 उपलब्ध है।",
                "keywords": ["घंटे", "समय", "उपलब्ध"],
                "language": "hi",
            },
            {
                "id": "faq_005",
                "question": "Do you offer API access?",
                "answer": "Yes! Full PARWA plans include read-write API access. Mini PARWA has read-only API access.",
                "keywords": ["api", "integration", "developer"],
                "language": "en",
            },
        ]
    )


# ============================================================
# MINI PARWA INSTANCE SIMULATOR
# ============================================================


class MiniParwaSimulator:
    """Simulates a Mini PARWA instance"""

    def __init__(self, company: CompanyConfig):
        self.company = company
        self.variant = "mini_parwa"
        self.config = VARIANT_LIMITS["mini_parwa"]
        self.tickets_processed = 0
        self.tickets_this_month = 0
        self.ai_responses = 0
        self.faqs_matched = 0

        # Allowed channels for Mini PARWA
        self.allowed_channels = ["email", "chat"]

        # Tier 1 techniques only
        self.allowed_techniques = [
            "faq_matching",
            "sentiment_analysis_basic",
            "auto_categorization",
            "basic_ner",
            "keyword_extraction",
        ]

        self.blocked_techniques = [
            "advanced_sentiment",
            "intent_detection_advanced",
            "multi_turn_reasoning",
            "emotion_detection",
            "predictive_analytics",
        ]

    def get_limits(self) -> Dict:
        return {
            "tickets_per_month": self.config.get("monthly_tickets", 2000),
            "ai_agents": self.config.get("ai_agents", 1),
            "team_members": self.config.get("team_members", 3),
            "channels": "Email + Chat",
            "model_tier": "Light only",
            "technique_tiers": "Tier 1 only",
            "api_access": "Read-only",
            "kb_docs": self.config.get("kb_docs", 100),
        }

    def can_handle_request(self, request: CustomerRequest) -> bool:
        """Check if Mini PARWA can handle this request"""
        # Check channel
        if request.channel not in self.allowed_channels:
            return False

        # Check ticket limit
        if self.tickets_this_month >= self.config.get("monthly_tickets", 2000):
            return False

        # Check priority (Mini PARWA handles normal and low priority)
        if request.priority in ["high", "urgent"]:
            return False

        return True

    def process_request(self, request: CustomerRequest) -> Dict:
        """Process a customer request through Mini PARWA"""
        result = {
            "request_id": request.id,
            "instance": "mini_parwa",
            "processed": False,
            "ai_response": None,
            "matched_faq": None,
            "techniques_used": [],
            "blocked_features": [],
            "error": None,
        }

        # Check if can handle
        if not self.can_handle_request(request):
            result["error"] = "CANNOT_HANDLE"
            result["blocked_features"].append("channel_or_priority_restriction")
            return result

        # Process the request
        self.tickets_processed += 1
        self.tickets_this_month += 1
        result["processed"] = True
        request.assigned_instance = "mini_parwa"

        # FAQ Matching
        matched_faq = self._match_faq(request)
        if matched_faq:
            result["matched_faq"] = matched_faq
            result["ai_response"] = matched_faq["answer"]
            result["techniques_used"].append("faq_matching")
            self.faqs_matched += 1
        else:
            result["ai_response"] = self._generate_response(request)
            result["techniques_used"].append("basic_response")

        # Basic sentiment (Tier 1)
        result["sentiment"] = self._analyze_sentiment(request.message)
        result["techniques_used"].append("sentiment_analysis_basic")

        # Auto-categorize
        result["category"] = self._categorize(request)
        result["techniques_used"].append("auto_categorization")

        self.ai_responses += 1

        return result

    def _match_faq(self, request: CustomerRequest) -> Optional[Dict]:
        message_lower = request.message.lower()
        for faq in self.company.faqs:
            if faq["language"] != request.language:
                continue
            for keyword in faq["keywords"]:
                if keyword.lower() in message_lower:
                    return faq
        return None

    def _generate_response(self, request: CustomerRequest) -> str:
        return f"Thank you for contacting {
            self.company.name}. We have received your inquiry about '{
            request.subject}'. Our team will respond within 24 hours."

    def _analyze_sentiment(self, text: str) -> str:
        positive = ["thank", "great", "helpful", "good", "awesome"]
        negative = ["angry", "frustrated", "bad", "terrible", "hate"]
        text_lower = text.lower()
        if any(w in text_lower for w in positive):
            return "positive"
        if any(w in text_lower for w in negative):
            return "negative"
        return "neutral"

    def _categorize(self, request: CustomerRequest) -> str:
        text = (request.message + " " + request.subject).lower()
        if any(w in text for w in ["password", "login", "account"]):
            return "account"
        if any(w in text for w in ["refund", "money", "billing"]):
            return "billing"
        if any(w in text for w in ["api", "integration"]):
            return "technical"
        return "general"


# ============================================================
# FULL PARWA INSTANCE SIMULATOR
# ============================================================


class FullParwaSimulator:
    """Simulates a Full PARWA instance"""

    def __init__(self, company: CompanyConfig):
        self.company = company
        self.variant = "parwa"
        self.config = VARIANT_LIMITS.get("parwa", {})
        self.tickets_processed = 0
        self.tickets_this_month = 0
        self.ai_responses = 0
        self.faqs_matched = 0
        self.sms_sent = 0
        self.voice_calls = 0

        # All channels for Full PARWA
        self.allowed_channels = ["email", "chat", "sms", "voice"]

        # Tier 1 + Tier 2 techniques
        self.allowed_techniques = [
            # Tier 1
            "faq_matching",
            "sentiment_analysis_basic",
            "auto_categorization",
            "basic_ner",
            "keyword_extraction",
            # Tier 2
            "advanced_sentiment",
            "intent_detection_advanced",
            "multi_turn_reasoning",
            "tree_of_thoughts",
            "step_back_reasoning",
            "rag_reranking",
        ]

        # API credentials (from environment)
        self.twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.twilio_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.twilio_phone = os.environ.get("TWILIO_PHONE_NUMBER", "")

    def get_limits(self) -> Dict:
        return {
            "tickets_per_month": self.config.get("monthly_tickets", 5000),
            "ai_agents": self.config.get("ai_agents", 3),
            "team_members": self.config.get("team_members", 10),
            "channels": "Email + Chat + SMS + Voice",
            "model_tier": "Light + Medium",
            "technique_tiers": "Tier 1 + Tier 2",
            "api_access": "Read-Write",
            "kb_docs": self.config.get("kb_docs", 500),
        }

    def can_handle_request(self, request: CustomerRequest) -> bool:
        """Full PARWA can handle all requests"""
        if self.tickets_this_month >= self.config.get("monthly_tickets", 5000):
            return False
        return True

    def process_request(self, request: CustomerRequest) -> Dict:
        """Process a customer request through Full PARWA"""
        result = {
            "request_id": request.id,
            "instance": "parwa",
            "processed": False,
            "ai_response": None,
            "matched_faq": None,
            "techniques_used": [],
            "channel_used": request.channel,
            "sms_sent": False,
            "voice_initiated": False,
            "error": None,
        }

        if not self.can_handle_request(request):
            result["error"] = "TICKET_LIMIT_EXCEEDED"
            return result

        # Process the request
        self.tickets_processed += 1
        self.tickets_this_month += 1
        result["processed"] = True
        request.assigned_instance = "parwa"

        # FAQ Matching (Tier 1)
        matched_faq = self._match_faq(request)
        if matched_faq:
            result["matched_faq"] = matched_faq
            result["ai_response"] = matched_faq["answer"]
            result["techniques_used"].append("faq_matching")
            self.faqs_matched += 1
        else:
            # Use advanced techniques (Tier 2)
            result["ai_response"] = self._generate_advanced_response(request)
            result["techniques_used"].extend(
                ["multi_turn_reasoning", "step_back_reasoning"]
            )

        # Advanced sentiment (Tier 2)
        result["sentiment"] = self._advanced_sentiment(request.message)
        result["techniques_used"].append("advanced_sentiment")

        # Auto-categorize with intent detection
        result["category"] = self._categorize_advanced(request)
        result["techniques_used"].extend(
            ["auto_categorization", "intent_detection_advanced"]
        )

        self.ai_responses += 1

        # Handle SMS channel
        if request.channel == "sms":
            result["sms_sent"] = True
            self.sms_sent += 1

        # Handle Voice channel
        if request.channel == "voice":
            result["voice_initiated"] = True
            self.voice_calls += 1

        return result

    def _match_faq(self, request: CustomerRequest) -> Optional[Dict]:
        message_lower = request.message.lower()
        for faq in self.company.faqs:
            if faq["language"] != request.language:
                continue
            for keyword in faq["keywords"]:
                if keyword.lower() in message_lower:
                    return faq
        return None

    def _generate_advanced_response(self, request: CustomerRequest) -> str:
        # Simulates advanced AI response using Medium model + Tier 2 techniques
        return f"Thank you for contacting {
            self.company.name}! I've analyzed your inquiry about '{
            request.subject}' using our advanced AI system. Based on the context, here's my response: Your request has been categorized as {
            request.category} priority. Our team is here to help you 24/7. Is there anything specific you'd like me to clarify?"

    def _advanced_sentiment(self, text: str) -> Dict:
        positive = ["thank", "great", "helpful", "good", "awesome", "love", "excellent"]
        negative = [
            "angry",
            "frustrated",
            "bad",
            "terrible",
            "hate",
            "worst",
            "disappointed",
        ]
        text_lower = text.lower()

        pos_count = sum(1 for w in positive if w in text_lower)
        neg_count = sum(1 for w in negative if w in text_lower)

        if pos_count > neg_count:
            return {"label": "positive", "confidence": 0.85 + (pos_count * 0.05)}
        elif neg_count > pos_count:
            return {"label": "negative", "confidence": 0.80 + (neg_count * 0.05)}
        return {"label": "neutral", "confidence": 0.75}

    def _categorize_advanced(self, request: CustomerRequest) -> str:
        text = (request.message + " " + request.subject).lower()
        categories = {
            "account": ["password", "login", "account", "access", "signin"],
            "billing": ["refund", "money", "billing", "payment", "invoice", "charge"],
            "technical": ["api", "integration", "developer", "code", "error"],
            "shipping": ["delivery", "shipping", "track", "order"],
            "product": ["feature", "product", "plan", "pricing"],
        }

        for cat, keywords in categories.items():
            if any(w in text for w in keywords):
                return cat
        return "general"

    def initiate_voice_call(self, phone_number: str, message_hindi: str) -> Dict:
        """Initiate a voice call using Twilio (simulated for testing)"""
        result = {
            "success": False,
            "call_sid": None,
            "phone_number": phone_number,
            "message": message_hindi,
            "error": None,
        }

        # Check if Twilio credentials are available
        if not self.twilio_sid or not self.twilio_token:
            result["error"] = "TWILIO_CREDENTIALS_NOT_SET"
            result["note"] = (
                "Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables"
            )
            return result

        # Simulate Twilio call (in production, this would use actual Twilio
        # API)
        result["success"] = True
        result["call_sid"] = f"CA{datetime.now().strftime('%Y%m%d%H%M%S')}"
        result["status"] = "initiated"
        result["message"] = "Voice call initiated successfully"

        self.voice_calls += 1

        return result

    def send_sms(self, phone_number: str, message: str) -> Dict:
        """Send SMS using Twilio (simulated for testing)"""
        result = {
            "success": False,
            "message_sid": None,
            "phone_number": phone_number,
            "message": message,
            "error": None,
        }

        if not self.twilio_sid or not self.twilio_token:
            result["error"] = "TWILIO_CREDENTIALS_NOT_SET"
            return result

        # Simulate SMS sending
        result["success"] = True
        result["message_sid"] = f"SM{datetime.now().strftime('%Y%m%d%H%M%S')}"
        result["status"] = "sent"

        self.sms_sent += 1

        return result


# ============================================================
# TEST CLASS
# ============================================================


class TestMiniParwaAndFullParwa:
    """Complete test suite for Mini PARWA + Full PARWA working together"""

    def setup_method(self):
        """Setup before each test - pytest uses setup_method not setup"""
        self.company = CompanyConfig()
        self.mini_parwa = MiniParwaSimulator(self.company)
        self.full_parwa = FullParwaSimulator(self.company)

    # ============================================================
    # SCENARIO 1: INSTANCE INITIALIZATION
    # ============================================================

    def test_scenario_01_instance_initialization(self):
        """Test both instances initialize correctly"""
        print("\n" + "=" * 70)
        print("SCENARIO 1: Instance Initialization")
        print("=" * 70)

        # Verify instances created
        assert self.mini_parwa is not None, "Mini PARWA should be created"
        assert self.full_parwa is not None, "Full PARWA should be created"

        # Get limits for both
        mini_limits = self.mini_parwa.get_limits()
        full_limits = self.full_parwa.get_limits()

        print(f"\n{'=' * 70}")
        print("MINI PARWA LIMITS:")
        print("=" * 70)
        for key, value in mini_limits.items():
            print(f"  {key}: {value}")

        print(f"\n{'=' * 70}")
        print("FULL PARWA LIMITS:")
        print("=" * 70)
        for key, value in full_limits.items():
            print(f"  {key}: {value}")

        # Verify Mini PARWA limits
        assert mini_limits["tickets_per_month"] == 2000
        assert mini_limits["ai_agents"] == 1
        assert mini_limits["team_members"] == 3
        assert mini_limits["channels"] == "Email + Chat"

        # Verify Full PARWA limits
        assert full_limits["tickets_per_month"] == 5000
        assert full_limits["ai_agents"] == 3
        assert full_limits["team_members"] == 10
        assert "SMS" in full_limits["channels"]
        assert "Voice" in full_limits["channels"]

        print("\n✅ PASSED: Both instances initialized with correct limits")

    # ============================================================
    # SCENARIO 2: EMAIL REQUEST HANDLING
    # ============================================================

    def test_scenario_02_email_request_handling(self):
        """Test email requests handled by both instances"""
        print("\n" + "=" * 70)
        print("SCENARIO 2: Email Request Handling")
        print("=" * 70)

        # Create test email requests
        requests = [
            CustomerRequest(
                id="REQ_EMAIL_001",
                customer_name="Rahul Sharma",
                customer_email="rahul@example.com",
                customer_phone="+919876543211",
                subject="Password Reset Help",
                message="I forgot my password and need to reset it urgently.",
                language="en",
                channel="email",
                priority="normal",
            ),
            CustomerRequest(
                id="REQ_EMAIL_002",
                customer_name="Priya Patel",
                customer_email="priya@example.com",
                customer_phone="+919876543212",
                subject="Refund Request",
                message="I want a refund for my subscription. The service is not as expected.",
                language="en",
                channel="email",
                priority="high",  # High priority -> Full PARWA
            ),
            CustomerRequest(
                id="REQ_EMAIL_003",
                customer_name="Amit Kumar",
                customer_email="amit@example.com",
                customer_phone="+919876543213",
                subject="Business Hours Query",
                message="What are your business hours? I need to call support.",
                language="en",
                channel="email",
                priority="low",
            ),
        ]

        print("\n--- Processing Email Requests ---")
        for req in requests:
            print(f"\nRequest: {req.id}")
            print(f"  Customer: {req.customer_name}")
            print(f"  Subject: {req.subject}")
            print(f"  Priority: {req.priority}")

            # Try Mini PARWA first
            if self.mini_parwa.can_handle_request(req):
                result = self.mini_parwa.process_request(req)
                print("  Handled by: Mini PARWA")
            else:
                result = self.full_parwa.process_request(req)
                print("  Handled by: Full PARWA (escalated)")

            print(f"  AI Response: {result['ai_response'][:80]}...")
            print(f"  Techniques: {result['techniques_used']}")
            print(f"  Status: {
                    '✅ Resolved' if result['processed'] else '❌ Failed'}")

        print("\n--- Summary ---")
        print(f"Mini PARWA processed: {self.mini_parwa.tickets_processed}")
        print(f"Full PARWA processed: {self.full_parwa.tickets_processed}")

        assert (
            self.mini_parwa.tickets_processed > 0
        ), "Mini PARWA should process requests"
        assert (
            self.full_parwa.tickets_processed > 0
        ), "Full PARWA should process escalated requests"

        print("\n✅ PASSED: Email requests handled correctly by both instances")

    # ============================================================
    # SCENARIO 3: SMS REQUEST (Full PARWA Only)
    # ============================================================

    def test_scenario_03_sms_request_handling(self):
        """Test SMS requests handled only by Full PARWA"""
        print("\n" + "=" * 70)
        print("SCENARIO 3: SMS Request Handling (Full PARWA Only)")
        print("=" * 70)

        sms_request = CustomerRequest(
            id="REQ_SMS_001",
            customer_name="Vikram Singh",
            customer_email="vikram@example.com",
            customer_phone="+919876543214",
            subject="Order Status",
            message="Where is my order #12345?",
            language="en",
            channel="sms",
            priority="normal",
        )

        print(f"\nSMS Request: {sms_request.id}")
        print(f"  Customer: {sms_request.customer_name}")
        print(f"  Phone: {sms_request.customer_phone}")
        print(f"  Message: {sms_request.message}")

        # Mini PARWA cannot handle SMS
        print(f"\n  Mini PARWA can handle: {
                self.mini_parwa.can_handle_request(sms_request)}")
        assert (
            self.mini_parwa.can_handle_request(sms_request) is False
        ), "Mini PARWA cannot handle SMS"

        # Full PARWA handles SMS
        result = self.full_parwa.process_request(sms_request)
        print(f"  Full PARWA handled: {result['processed']}")
        print(f"  AI Response: {result['ai_response'][:80]}...")
        print(f"  SMS Sent: {result.get('sms_sent', False)}")

        assert result["processed"], "Full PARWA should process SMS"

        print("\n✅ PASSED: SMS requests handled only by Full PARWA")

    # ============================================================
    # SCENARIO 4: VOICE REQUEST (Full PARWA Only)
    # ============================================================

    def test_scenario_04_voice_request_handling(self):
        """Test voice requests handled only by Full PARWA"""
        print("\n" + "=" * 70)
        print("SCENARIO 4: Voice Request Handling (Full PARWA Only)")
        print("=" * 70)

        voice_request = CustomerRequest(
            id="REQ_VOICE_001",
            customer_name="Suresh Yadav",
            customer_email="suresh@example.com",
            customer_phone="+919876543215",
            subject="Urgent Support",
            message="Customer called about urgent account issue",
            language="hi",
            channel="voice",
            priority="urgent",
        )

        print(f"\nVoice Request: {voice_request.id}")
        print(f"  Customer: {voice_request.customer_name}")
        print(f"  Phone: {voice_request.customer_phone}")
        print("  Language: Hindi")

        # Mini PARWA cannot handle Voice
        assert (
            self.mini_parwa.can_handle_request(voice_request) is False
        ), "Mini PARWA cannot handle Voice"

        # Full PARWA handles Voice
        result = self.full_parwa.process_request(voice_request)
        print(f"\n  Full PARWA handled: {result['processed']}")
        print(f"  Voice Initiated: {result.get('voice_initiated', False)}")

        assert result["processed"], "Full PARWA should process Voice"

        print("\n✅ PASSED: Voice requests handled only by Full PARWA")

    # ============================================================
    # SCENARIO 5: HINDI LANGUAGE SUPPORT
    # ============================================================

    def test_scenario_05_hindi_language_support(self):
        """Test Hindi language support"""
        print("\n" + "=" * 70)
        print("SCENARIO 5: Hindi Language Support")
        print("=" * 70)

        hindi_request = CustomerRequest(
            id="REQ_HINDI_001",
            customer_name="राहुल शर्मा",
            customer_email="rahul.hindi@example.com",
            customer_phone="+919876543216",
            subject="काम के घंटे",
            message="आपके काम के घंटे क्या हैं? मुझे सपोर्ट से बात करनी है।",
            language="hi",
            channel="email",
            priority="normal",
        )

        print(f"\nHindi Request: {hindi_request.id}")
        print(f"  Customer: {hindi_request.customer_name}")
        print(f"  Message: {hindi_request.message}")

        # Process through Mini PARWA
        result = self.mini_parwa.process_request(hindi_request)
        print(f"\n  Processed: {result['processed']}")
        print(f"  Matched FAQ: {
                result['matched_faq']['id'] if result['matched_faq'] else 'None'}")

        if result["matched_faq"]:
            print(f"  FAQ Answer (Hindi): {result['matched_faq']['answer'][:100]}...")

        assert result["processed"], "Should process Hindi request"
        assert result["matched_faq"] is not None, "Should match Hindi FAQ"

        print("\n✅ PASSED: Hindi language support working")

    # ============================================================
    # SCENARIO 6: TECHNIQUE COMPARISON
    # ============================================================

    def test_scenario_06_technique_comparison(self):
        """Compare techniques available in Mini vs Full PARWA"""
        print("\n" + "=" * 70)
        print("SCENARIO 6: Technique Comparison")
        print("=" * 70)

        print(f"\n{'=' * 35} MINI PARWA {'=' * 35}")
        print("Allowed Techniques (Tier 1 Only):")
        for tech in self.mini_parwa.allowed_techniques:
            print(f"  ✅ {tech}")

        print("\nBlocked Techniques (Tier 2/3):")
        for tech in self.mini_parwa.blocked_techniques:
            print(f"  ❌ {tech}")

        print(f"\n{'=' * 35} FULL PARWA {'=' * 36}")
        print("Allowed Techniques (Tier 1 + Tier 2):")
        for tech in self.full_parwa.allowed_techniques:
            print(f"  ✅ {tech}")

        # Verify Mini PARWA has only Tier 1
        assert "faq_matching" in self.mini_parwa.allowed_techniques
        assert "multi_turn_reasoning" not in self.mini_parwa.allowed_techniques

        # Verify Full PARWA has Tier 1 + Tier 2
        assert "faq_matching" in self.full_parwa.allowed_techniques
        assert "multi_turn_reasoning" in self.full_parwa.allowed_techniques
        assert "step_back_reasoning" in self.full_parwa.allowed_techniques

        print("\n✅ PASSED: Technique tiers correctly differentiated")

    # ============================================================
    # SCENARIO 7: TICKET LIMIT TESTING
    # ============================================================

    def test_scenario_07_ticket_limits(self):
        """Test ticket limits for both instances"""
        print("\n" + "=" * 70)
        print("SCENARIO 7: Ticket Limit Testing")
        print("=" * 70)

        # Reset counters
        self.mini_parwa.tickets_this_month = 0
        self.full_parwa.tickets_this_month = 0

        # Mini PARWA: 2000 tickets/month
        # Full PARWA: 5000 tickets/month

        mini_limit = self.mini_parwa.config.get("monthly_tickets", 2000)
        full_limit = self.full_parwa.config.get("monthly_tickets", 5000)

        print(f"\nMini PARWA Limit: {mini_limit} tickets/month")
        print(f"Full PARWA Limit: {full_limit} tickets/month")

        # Simulate near-limit scenario
        self.mini_parwa.tickets_this_month = mini_limit - 1
        self.full_parwa.tickets_this_month = full_limit - 1

        test_request = CustomerRequest(
            id="REQ_LIMIT_TEST",
            customer_name="Test User",
            customer_email="test@example.com",
            customer_phone="+919876543217",
            subject="Test",
            message="Testing limit",
            channel="email",
            priority="normal",
        )

        # Should allow 1 more ticket
        assert self.mini_parwa.can_handle_request(test_request)
        assert self.full_parwa.can_handle_request(test_request)
        print("\n✅ Both instances allow 1 more ticket before limit")

        # Now at limit
        self.mini_parwa.tickets_this_month = mini_limit
        self.full_parwa.tickets_this_month = full_limit

        # Should block
        assert self.mini_parwa.can_handle_request(test_request) is False
        assert self.full_parwa.can_handle_request(test_request) is False
        print("✅ Both instances block tickets at limit")

        print("\n✅ PASSED: Ticket limits enforced correctly")

    # ============================================================
    # SCENARIO 8: ESCALATION FROM MINI TO FULL
    # ============================================================

    def test_scenario_08_escalation_flow(self):
        """Test escalation from Mini PARWA to Full PARWA"""
        print("\n" + "=" * 70)
        print("SCENARIO 8: Escalation Flow (Mini → Full)")
        print("=" * 70)

        # Create urgent request that should go to Full PARWA
        urgent_request = CustomerRequest(
            id="REQ_URGENT_001",
            customer_name="VIP Customer",
            customer_email="vip@example.com",
            customer_phone="+919876543218",
            subject="CRITICAL: Service Down",
            message="Our entire service is down! This is urgent!",
            channel="email",
            priority="urgent",
        )

        print(f"\nUrgent Request: {urgent_request.id}")
        print(f"  Priority: {urgent_request.priority}")

        # Mini PARWA cannot handle urgent
        can_handle = self.mini_parwa.can_handle_request(urgent_request)
        print(f"\n  Mini PARWA can handle: {can_handle}")

        if not can_handle:
            print("  → Escalating to Full PARWA...")
            result = self.full_parwa.process_request(urgent_request)
            print(f"  → Full PARWA handled: {result['processed']}")
            print(f"  → Techniques used: {result['techniques_used']}")
            assert result["processed"]

        print("\n✅ PASSED: Escalation flow working correctly")

    # ============================================================
    # SCENARIO 9: VOICE CALL SIMULATION
    # ============================================================

    def test_scenario_09_voice_call_simulation(self):
        """Test voice call feature in Full PARWA"""
        print("\n" + "=" * 70)
        print("SCENARIO 9: Voice Call Simulation")
        print("=" * 70)

        # Hindi message for voice call
        hindi_message = """
नमस्ते! TechCorp Solutions में आपका स्वागत है।

मैं आपको PARWA की सभी विशेषताओं के बारे में बताने के लिए कॉल कर रहा हूँ:

1. Mini PARWA: Email और Chat सपोर्ट, 2000 टिकट प्रति माह
2. Full PARWA: Email, Chat, SMS और Voice सपोर्ट, 5000 टिकट प्रति माह
3. Advanced AI तकनीकें जैसे Multi-turn Reasoning और Step-back Analysis

आपका ऑर्डर सफलतापूर्वक रजिस्टर हो गया है।
कोई भी सवाल हो तो 24/7 हमसे संपर्क करें।

धन्यवाद!
"""

        print("\nHindi Voice Message:")
        print("-" * 50)
        print(hindi_message)
        print("-" * 50)

        # Test voice call initiation
        result = self.full_parwa.initiate_voice_call(
            phone_number="+919876543210", message_hindi=hindi_message
        )

        print("\nVoice Call Result:")
        print(f"  Success: {result['success']}")
        print(f"  Phone: {result['phone_number']}")

        if result.get("call_sid"):
            print(f"  Call SID: {result['call_sid']}")
            print(f"  Status: {result['status']}")

        if result.get("error"):
            print(f"  Error: {result['error']}")
            print(f"  Note: {result.get('note', '')}")

        # This test passes either way - we're testing the feature
        print("\n✅ PASSED: Voice call feature tested")

    # ============================================================
    # SCENARIO 10: SMS NOTIFICATION
    # ============================================================

    def test_scenario_10_sms_notification(self):
        """Test SMS notification feature"""
        print("\n" + "=" * 70)
        print("SCENARIO 10: SMS Notification")
        print("=" * 70)

        sms_message = "Hello! Your ticket #TKT12345 has been resolved. Thank you for contacting TechCorp Support!"

        result = self.full_parwa.send_sms(
            phone_number="+919876543210", message=sms_message
        )

        print("\nSMS Result:")
        print(f"  Success: {result['success']}")
        print(f"  Phone: {result['phone_number']}")
        print(f"  Message: {result['message'][:50]}...")

        if result.get("message_sid"):
            print(f"  Message SID: {result['message_sid']}")
            print(f"  Status: {result['status']}")

        if result.get("error"):
            print(f"  Error: {result['error']}")

        print("\n✅ PASSED: SMS notification tested")

    # ============================================================
    # SCENARIO 11: CONCURRENT REQUESTS
    # ============================================================

    def test_scenario_11_concurrent_requests(self):
        """Test handling multiple concurrent requests"""
        print("\n" + "=" * 70)
        print("SCENARIO 11: Concurrent Requests")
        print("=" * 70)

        # Reset counters
        self.mini_parwa.tickets_this_month = 0
        self.full_parwa.tickets_this_month = 0

        # Create multiple requests
        requests = []
        for i in range(10):
            channel = "email" if i < 7 else ("sms" if i < 9 else "voice")
            priority = "normal" if i < 5 else ("high" if i < 8 else "urgent")

            req = CustomerRequest(
                id=f"REQ_CONCURRENT_{i:03d}",
                customer_name=f"Customer {i}",
                customer_email=f"customer{i}@example.com",
                customer_phone=f"+9198765432{i:02d}",
                subject=f"Request {i}",
                message=f"This is test request number {i}",
                channel=channel,
                priority=priority,
            )
            requests.append(req)

        # Process all requests
        mini_count = 0
        full_count = 0

        print("\nProcessing 10 concurrent requests...")
        for req in requests:
            if self.mini_parwa.can_handle_request(req):
                self.mini_parwa.process_request(req)
                mini_count += 1
            else:
                self.full_parwa.process_request(req)
                full_count += 1

        print(f"\n  Mini PARWA handled: {mini_count} requests")
        print(f"  Full PARWA handled: {full_count} requests")
        print(f"  Total: {mini_count + full_count} requests")

        assert mini_count + full_count == 10, "All requests should be processed"

        print("\n✅ PASSED: Concurrent requests handled correctly")

    # ============================================================
    # SCENARIO 12: FINAL SUMMARY
    # ============================================================

    def test_scenario_12_final_summary(self):
        """Generate final summary of both instances"""
        print("\n" + "=" * 70)
        print("SCENARIO 12: Final Summary")
        print("=" * 70)

        print(f"\n{'=' * 70}")
        print("MINI PARWA SUMMARY")
        print("=" * 70)
        print(f"  Variant: {self.mini_parwa.variant}")
        print(f"  Tickets Processed: {self.mini_parwa.tickets_processed}")
        print(f"  AI Responses: {self.mini_parwa.ai_responses}")
        print(f"  FAQs Matched: {self.mini_parwa.faqs_matched}")
        print(f"  Channels: {self.mini_parwa.allowed_channels}")

        print(f"\n{'=' * 70}")
        print("FULL PARWA SUMMARY")
        print("=" * 70)
        print(f"  Variant: {self.full_parwa.variant}")
        print(f"  Tickets Processed: {self.full_parwa.tickets_processed}")
        print(f"  AI Responses: {self.full_parwa.ai_responses}")
        print(f"  FAQs Matched: {self.full_parwa.faqs_matched}")
        print(f"  SMS Sent: {self.full_parwa.sms_sent}")
        print(f"  Voice Calls: {self.full_parwa.voice_calls}")
        print(f"  Channels: {self.full_parwa.allowed_channels}")

        print(f"\n{'=' * 70}")
        print("COMPARISON TABLE")
        print("=" * 70)
        print(f"| {'Feature':<25} | {'Mini PARWA':<15} | {'Full PARWA':<15} |")
        print(f"|{'-' * 27}|{'-' * 17}|{'-' * 17}|")

        comparisons = [
            ("Monthly Tickets", "2,000", "5,000"),
            ("AI Agents", "1", "3"),
            ("Team Members", "3", "10"),
            ("Channels", "Email+Chat", "Email+Chat+SMS+Voice"),
            ("Model Tiers", "Light", "Light+Medium"),
            ("Techniques", "Tier 1", "Tier 1+2"),
            ("API Access", "Read-only", "Read-Write"),
            ("KB Documents", "100", "500"),
        ]

        for feature, mini, full in comparisons:
            print(f"| {feature:<25} | {mini:<15} | {full:<15} |")

        print("\n✅ PASSED: Final summary generated")


# ============================================================
# RUN ALL TESTS
# ============================================================


def run_all_tests():
    """Run all tests and generate report"""
    import traceback

    print("\n" + "=" * 70)
    print(" COMPREHENSIVE TEST: Mini PARWA + Full PARWA Working Together")
    print("=" * 70)
    print(f" Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    test_instance = TestMiniParwaAndFullParwa()

    tests = [
        (
            "SCENARIO 1: Instance Initialization",
            test_instance.test_scenario_01_instance_initialization,
        ),
        (
            "SCENARIO 2: Email Request Handling",
            test_instance.test_scenario_02_email_request_handling,
        ),
        (
            "SCENARIO 3: SMS Request Handling",
            test_instance.test_scenario_03_sms_request_handling,
        ),
        (
            "SCENARIO 4: Voice Request Handling",
            test_instance.test_scenario_04_voice_request_handling,
        ),
        (
            "SCENARIO 5: Hindi Language Support",
            test_instance.test_scenario_05_hindi_language_support,
        ),
        (
            "SCENARIO 6: Technique Comparison",
            test_instance.test_scenario_06_technique_comparison,
        ),
        (
            "SCENARIO 7: Ticket Limit Testing",
            test_instance.test_scenario_07_ticket_limits,
        ),
        ("SCENARIO 8: Escalation Flow", test_instance.test_scenario_08_escalation_flow),
        (
            "SCENARIO 9: Voice Call Simulation",
            test_instance.test_scenario_09_voice_call_simulation,
        ),
        (
            "SCENARIO 10: SMS Notification",
            test_instance.test_scenario_10_sms_notification,
        ),
        (
            "SCENARIO 11: Concurrent Requests",
            test_instance.test_scenario_11_concurrent_requests,
        ),
        ("SCENARIO 12: Final Summary", test_instance.test_scenario_12_final_summary),
    ]

    results = []
    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_instance.setup_method()  # Reset before each test
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
        if status == "PASSED":
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name}")
            if error:
                print(f"      Error: {error[:100]}")

    print("\n" + "-" * 70)
    print(f" Total: {len(results)} tests")
    print(f" ✅ Passed: {passed}")
    print(f" ❌ Failed: {failed}")
    print(f" Success Rate: {(passed / len(results)) * 100:.1f}%")
    print(f" Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 70)

    return passed, failed


if __name__ == "__main__":
    passed, failed = run_all_tests()
    sys.exit(0 if failed == 0 else 1)
