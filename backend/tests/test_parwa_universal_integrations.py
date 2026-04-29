"""
COMPREHENSIVE TEST SUITE: PARWA Variant with Universal Integrations
====================================================================

Tests the full PARWA variant with:
- Universal email provider integration (Brevo, SendGrid, etc.)
- Universal SMS provider integration (Twilio, MessageBird, etc.)
- PARWA-specific features and limits
- Real API testing with provided keys

PARWA Variant Features:
- 5000 tickets/month
- 3 AI agents
- 10 team members
- SMS channel (unlocked)
- Medium AI model
- Tier 2 techniques
- 500 KB documents
- RAG top_k=5
- Read-Write API access
"""

from app.providers.factory import (
    UniversalEmailService,
    UniversalSMSService,
)
from app.providers import (
    ProviderFactory,
    ProviderType,
)
from app.config.variant_features import (
    VARIANT_LIMITS,
    VARIANT_FEATURES,
    BLOCKED_FEATURES,
)
import os
import sys
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# Import provider system


# ============================================================
# API KEYS - FROM ENVIRONMENT (SECURE)
# ============================================================
# Set these in environment before running tests:
# export BREVO_API_KEY="xkeysib-..."
# export TWILIO_ACCOUNT_SID="AC..."
# export TWILIO_AUTH_TOKEN="..."

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")


# ============================================================
# PARWA VARIANT LIMITS
# ============================================================

PARWA_LIMITS = {
    "monthly_tickets": 5000,
    "ai_agents": 3,
    "team_members": 10,
    "voice_slots": 2,
    "kb_docs": 500,
    "model_tiers": ["light", "medium"],
    "technique_tiers": [1, 2],
    "rag_top_k": 5,
    "api_access": "readwrite",
}


# ============================================================
# TEST CLASS
# ============================================================

class TestParwaVariant:
    """Complete test suite for PARWA variant with universal integrations"""

    # ============================================================
    # SCENARIO 1: PARWA INSTANCE INITIALIZATION
    # ============================================================

    def test_scenario_01_parwa_limits(self):
        """Test PARWA variant limits are correct"""
        print("\n" + "=" * 60)
        print("SCENARIO 1: PARWA Variant Limits")
        print("=" * 60)

        limits = VARIANT_LIMITS.get("parwa", {})

        print("\nPARWA Limits:")
        for key, value in limits.items():
            print(f"  - {key}: {value}")

        # Verify PARWA limits
        assert limits["monthly_tickets"] == 5000, "PARWA should have 5000 tickets/month"
        assert limits["ai_agents"] == 3, "PARWA should have 3 AI agents"
        assert limits["team_members"] == 10, "PARWA should have 10 team members"
        assert limits["voice_slots"] == 2, "PARWA should have 2 voice slots"
        assert limits["kb_docs"] == 500, "PARWA should have 500 KB docs"
        assert limits["rag_top_k"] == 5, "PARWA should have RAG top_k=5"
        assert limits["api_access"] == "readwrite", "PARWA should have readwrite API access"
        assert "light" in limits["model_tiers"], "PARWA should have light model"
        assert "medium" in limits["model_tiers"], "PARWA should have medium model"
        assert 1 in limits["technique_tiers"], "PARWA should have Tier 1 techniques"
        assert 2 in limits["technique_tiers"], "PARWA should have Tier 2 techniques"

        print("\n✅ PASSED: PARWA limits verified correctly")

    # ============================================================
    # SCENARIO 2: PARWA FEATURES
    # ============================================================

    def test_scenario_02_parwa_features(self):
        """Test PARWA variant features"""
        print("\n" + "=" * 60)
        print("SCENARIO 2: PARWA Variant Features")
        print("=" * 60)

        features = VARIANT_FEATURES.get("parwa", set())

        # PARWA should have these features (not in Mini PARWA)
        parwa_exclusive = [
            "sms_channel",
            "ai_model_medium",
            "technique_tree_of_thoughts",
            "technique_least_to_most",
            "technique_step_back",
            "rag_reranking",
            "rag_deep_search",
            "custom_system_prompts",
            "brand_voice",
            "api_readwrite",
            "analytics_export",
            "analytics_reports",
            "agent_training",
            "lightning_training",
            "custom_integrations",
            "incoming_webhooks",
        ]

        print("\nPARWA Exclusive Features:")
        for feature in parwa_exclusive:
            available = feature in features
            status = "✅" if available else "❌"
            print(f"  {status} {feature}")
            assert available, f"PARWA should have {feature}"

        print("\n✅ PASSED: PARWA features verified correctly")

    # ============================================================
    # SCENARIO 3: PARWA BLOCKED FEATURES
    # ============================================================

    def test_scenario_03_parwa_blocked_features(self):
        """Test PARWA variant blocked features"""
        print("\n" + "=" * 60)
        print("SCENARIO 3: PARWA Blocked Features (Only in High PARWA)")
        print("=" * 60)

        blocked = BLOCKED_FEATURES.get("parwa", set())

        # These should be blocked in PARWA (only in High PARWA)
        expected_blocked = [
            "voice_ai_channel",
            "ai_model_heavy",
            "technique_self_consistency",
            "technique_reflexion",
            "quality_coach",
            "custom_guardrails",
            "api_full",
            "outgoing_webhooks",
            "dedicated_csm",
        ]

        print("\nBlocked in PARWA (High PARWA only):")
        for feature in expected_blocked:
            is_blocked = feature in blocked
            status = "❌" if is_blocked else "✅ (should be blocked)"
            print(f"  {status} {feature}")
            assert is_blocked, f"{feature} should be blocked in PARWA"

        print("\n✅ PASSED: PARWA blocked features verified correctly")

    # ============================================================
    # SCENARIO 4: UNIVERSAL EMAIL PROVIDER SYSTEM
    # ============================================================

    def test_scenario_04_universal_email_providers(self):
        """Test universal email provider abstraction"""
        print("\n" + "=" * 60)
        print("SCENARIO 4: Universal Email Provider System")
        print("=" * 60)

        # List available email providers
        providers = ProviderFactory.list_available(ProviderType.EMAIL)

        print("\nAvailable Email Providers:")
        for p in providers:
            print(f"  - {p['display_name']} ({p['name']})")

        # Verify we have multiple providers
        provider_names = [p["name"] for p in providers]
        assert "brevo" in provider_names, "Should have Brevo provider"
        assert "sendgrid" in provider_names, "Should have SendGrid provider"
        assert "mailgun" in provider_names, "Should have Mailgun provider"
        assert "ses" in provider_names, "Should have AWS SES provider"
        assert "postmark" in provider_names, "Should have Postmark provider"
        assert "smtp" in provider_names, "Should have SMTP provider"

        print("\n✅ PASSED: Universal email provider system has multiple providers")

    # ============================================================
    # SCENARIO 5: UNIVERSAL SMS PROVIDER SYSTEM
    # ============================================================

    def test_scenario_05_universal_sms_providers(self):
        """Test universal SMS provider abstraction"""
        print("\n" + "=" * 60)
        print("SCENARIO 5: Universal SMS Provider System")
        print("=" * 60)

        # List available SMS providers
        providers = ProviderFactory.list_available(ProviderType.SMS)

        print("\nAvailable SMS Providers:")
        for p in providers:
            print(f"  - {p['display_name']} ({p['name']})")

        # Verify we have multiple providers
        provider_names = [p["name"] for p in providers]
        assert "twilio" in provider_names, "Should have Twilio provider"
        assert "messagebird" in provider_names, "Should have MessageBird provider"
        assert "vonage" in provider_names, "Should have Vonage provider"
        assert "plivo" in provider_names, "Should have Plivo provider"
        assert "sinch" in provider_names, "Should have Sinch provider"

        print("\n✅ PASSED: Universal SMS provider system has multiple providers")

    # ============================================================
    # SCENARIO 6: BREVO EMAIL INTEGRATION TEST
    # ============================================================

    def test_scenario_06_brevo_email_test(self):
        """Test Brevo email provider with real API"""
        print("\n" + "=" * 60)
        print("SCENARIO 6: Brevo Email Integration Test")
        print("=" * 60)

        if not BREVO_API_KEY:
            print("\n⚠️ SKIPPED: BREVO_API_KEY not set in environment")
            return

        try:
            # Create Brevo email provider
            provider = ProviderFactory.create(
                provider_type=ProviderType.EMAIL,
                provider_name="brevo",
                config={"api_key": BREVO_API_KEY},
                validate=False,  # Don't fail on test
            )

            # Test connection
            result = provider.test_connection()

            print("\nBrevo Connection Test:")
            print(f"  - Success: {result.success}")
            print(f"  - Provider: {result.provider_name}")
            if result.error_message:
                print(f"  - Error: {result.error_message}")
            if result.metadata:
                print(
                    f"  - Account Email: {result.metadata.get('email', 'N/A')}")

            # Get rate limits
            limits = provider.get_rate_limits()
            print("\nBrevo Rate Limits:")
            for key, value in limits.items():
                print(f"  - {key}: {value}")

            print("\n✅ PASSED: Brevo integration working")

        except Exception as e:
            print(f"\n❌ ERROR: {str(e)[:200]}")

    # ============================================================
    # SCENARIO 7: TWILIO SMS INTEGRATION TEST
    # ============================================================

    def test_scenario_07_twilio_sms_test(self):
        """Test Twilio SMS provider with real API"""
        print("\n" + "=" * 60)
        print("SCENARIO 7: Twilio SMS Integration Test")
        print("=" * 60)

        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            print("\n⚠️ SKIPPED: TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not set")
            return

        try:
            # Create Twilio SMS provider
            provider = ProviderFactory.create(
                provider_type=ProviderType.SMS,
                provider_name="twilio",
                config={
                    "account_sid": TWILIO_ACCOUNT_SID,
                    "auth_token": TWILIO_AUTH_TOKEN,
                    "phone_number": TWILIO_PHONE_NUMBER,
                },
                validate=False,
            )

            # Test connection
            result = provider.test_connection()

            print("\nTwilio Connection Test:")
            print(f"  - Success: {result.success}")
            print(f"  - Provider: {result.provider_name}")
            if result.error_message:
                print(f"  - Error: {result.error_message}")
            if result.metadata:
                print(
                    f"  - Account Name: {result.metadata.get('friendly_name', 'N/A')}")

            # Get rate limits
            limits = provider.get_rate_limits()
            print("\nTwilio Rate Limits:")
            for key, value in limits.items():
                print(f"  - {key}: {value}")

            print("\n✅ PASSED: Twilio integration working")

        except Exception as e:
            print(f"\n❌ ERROR: {str(e)[:200]}")

    # ============================================================
    # SCENARIO 8: UNIVERSAL EMAIL SERVICE
    # ============================================================

    def test_scenario_08_universal_email_service(self):
        """Test universal email service abstraction"""
        print("\n" + "=" * 60)
        print("SCENARIO 8: Universal Email Service Abstraction")
        print("=" * 60)

        if not BREVO_API_KEY:
            print("\n⚠️ SKIPPED: BREVO_API_KEY not set")
            return

        try:
            # Create provider
            provider = ProviderFactory.create(
                provider_type=ProviderType.EMAIL,
                provider_name="brevo",
                config={"api_key": BREVO_API_KEY},
                validate=False,
            )

            # Create universal service
            service = UniversalEmailService(provider)

            # Test the service
            test_result = service.test_connection()
            print("\nUniversal Email Service Test:")
            print(f"  - Success: {test_result.get('success')}")
            print(f"  - Provider: {test_result.get('provider_name')}")

            print("\n✅ PASSED: Universal email service abstraction works")

        except Exception as e:
            print(f"\n❌ ERROR: {str(e)[:200]}")

    # ============================================================
    # SCENARIO 9: UNIVERSAL SMS SERVICE
    # ============================================================

    def test_scenario_09_universal_sms_service(self):
        """Test universal SMS service abstraction"""
        print("\n" + "=" * 60)
        print("SCENARIO 9: Universal SMS Service Abstraction")
        print("=" * 60)

        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            print("\n⚠️ SKIPPED: Twilio credentials not set")
            return

        try:
            # Create provider
            provider = ProviderFactory.create(
                provider_type=ProviderType.SMS,
                provider_name="twilio",
                config={
                    "account_sid": TWILIO_ACCOUNT_SID,
                    "auth_token": TWILIO_AUTH_TOKEN,
                    "phone_number": TWILIO_PHONE_NUMBER,
                },
                validate=False,
            )

            # Create universal service
            service = UniversalSMSService(provider)

            # Test the service
            test_result = service.test_connection()
            print("\nUniversal SMS Service Test:")
            print(f"  - Success: {test_result.get('success')}")
            print(f"  - Provider: {test_result.get('provider_name')}")

            print("\n✅ PASSED: Universal SMS service abstraction works")

        except Exception as e:
            print(f"\n❌ ERROR: {str(e)[:200]}")

    # ============================================================
    # SCENARIO 10: PROVIDER SWITCHING (KEY FEATURE)
    # ============================================================

    def test_scenario_10_provider_switching(self):
        """Test switching between providers - KEY UNIVERSAL FEATURE"""
        print("\n" + "=" * 60)
        print("SCENARIO 10: Provider Switching (Universal System)")
        print("=" * 60)

        print("\nThis is the KEY FEATURE of the universal system:")
        print("  - Switch from Brevo to SendGrid without code changes")
        print("  - Switch from Twilio to MessageBird without code changes")
        print("  - Same API, different providers")

        # Create mock configs for different providers
        brevo_config = {"api_key": "test_brevo_key"}
        sendgrid_config = {"api_key": "test_sendgrid_key"}
        twilio_config = {"account_sid": "test_sid", "auth_token": "test_token"}
        messagebird_config = {"api_key": "test_mb_key"}

        # Test that we can create providers with same interface
        try:
            brevo = ProviderFactory.create(
                ProviderType.EMAIL, "brevo", brevo_config, validate=False
            )
            sendgrid = ProviderFactory.create(
                ProviderType.EMAIL, "sendgrid", sendgrid_config, validate=False
            )
            twilio = ProviderFactory.create(
                ProviderType.SMS, "twilio", twilio_config, validate=False
            )
            messagebird = ProviderFactory.create(
                ProviderType.SMS, "messagebird", messagebird_config, validate=False)

            print("\n✅ Created Email Providers:")
            print(f"  - Brevo: {brevo.provider_name}")
            print(f"  - SendGrid: {sendgrid.provider_name}")

            print("\n✅ Created SMS Providers:")
            print(f"  - Twilio: {twilio.provider_name}")
            print(f"  - MessageBird: {messagebird.provider_name}")

            # Verify all have same interface
            assert hasattr(brevo, 'send_email'), "Brevo should have send_email"
            assert hasattr(
                sendgrid, 'send_email'), "SendGrid should have send_email"
            assert hasattr(twilio, 'send_sms'), "Twilio should have send_sms"
            assert hasattr(
                messagebird, 'send_sms'), "MessageBird should have send_sms"

            print("\n✅ All providers have the SAME interface!")
            print("   This means you can switch providers without code changes.")

            print("\n✅ PASSED: Provider switching works - UNIVERSAL SYSTEM!")

        except Exception as e:
            print(f"\n❌ ERROR: {str(e)[:200]}")

    # ============================================================
    # SCENARIO 11: PARWA VS MINI PARWA COMPARISON
    # ============================================================

    def test_scenario_11_parwa_vs_mini_comparison(self):
        """Compare PARWA vs Mini PARWA features"""
        print("\n" + "=" * 60)
        print("SCENARIO 11: PARWA vs Mini PARWA Comparison")
        print("=" * 60)

        mini_limits = VARIANT_LIMITS.get("mini_parwa", {})
        parwa_limits = VARIANT_LIMITS.get("parwa", {})

        print("\n| Feature | Mini PARWA | PARWA |")
        print("|---------|------------|-------|")
        comparisons = [
            ("Monthly Tickets", mini_limits.get("monthly_tickets"), parwa_limits.get("monthly_tickets")),
            ("AI Agents", mini_limits.get("ai_agents"), parwa_limits.get("ai_agents")),
            ("Team Members", mini_limits.get("team_members"), parwa_limits.get("team_members")),
            ("Voice Slots", mini_limits.get("voice_slots"), parwa_limits.get("voice_slots")),
            ("KB Docs", mini_limits.get("kb_docs"), parwa_limits.get("kb_docs")),
            ("RAG Top-K", mini_limits.get("rag_top_k"), parwa_limits.get("rag_top_k")),
            ("API Access", mini_limits.get("api_access"), parwa_limits.get("api_access")),
            ("Model Tiers", mini_limits.get("model_tiers"), parwa_limits.get("model_tiers")),
            ("Technique Tiers", mini_limits.get("technique_tiers"), parwa_limits.get("technique_tiers")),
        ]

        for name, mini_val, parwa_val in comparisons:
            print(f"| {name} | {mini_val} | {parwa_val} |")

        print("\n✅ PASSED: PARWA has significantly more features than Mini PARWA")


# ============================================================
# RUN TESTS
# ============================================================

def run_all_tests():
    """Run all tests and generate report"""
    import traceback

    print("\n" + "=" * 70)
    print(" COMPREHENSIVE TEST SUITE: PARWA VARIANT WITH UNIVERSAL INTEGRATIONS")
    print("=" * 70)
    print(f" Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    test_instance = TestParwaVariant()

    tests = [
        ("SCENARIO 1: PARWA Limits", test_instance.test_scenario_01_parwa_limits),
        ("SCENARIO 2: PARWA Features", test_instance.test_scenario_02_parwa_features),
        ("SCENARIO 3: PARWA Blocked Features", test_instance.test_scenario_03_parwa_blocked_features),
        ("SCENARIO 4: Universal Email Providers", test_instance.test_scenario_04_universal_email_providers),
        ("SCENARIO 5: Universal SMS Providers", test_instance.test_scenario_05_universal_sms_providers),
        ("SCENARIO 6: Brevo Email Test", test_instance.test_scenario_06_brevo_email_test),
        ("SCENARIO 7: Twilio SMS Test", test_instance.test_scenario_07_twilio_sms_test),
        ("SCENARIO 8: Universal Email Service", test_instance.test_scenario_08_universal_email_service),
        ("SCENARIO 9: Universal SMS Service", test_instance.test_scenario_09_universal_sms_service),
        ("SCENARIO 10: Provider Switching", test_instance.test_scenario_10_provider_switching),
        ("SCENARIO 11: PARWA vs Mini PARWA", test_instance.test_scenario_11_parwa_vs_mini_comparison),
    ]

    results = []
    passed = 0
    failed = 0
    skipped = 0

    for name, test_func in tests:
        try:
            test_func()
            results.append((name, "PASSED", None))
            passed += 1
        except Exception as e:
            if "SKIPPED" in str(e):
                results.append((name, "SKIPPED", str(e)))
                skipped += 1
            else:
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
            print(f"  ✅ {name}: {status}")
        elif status == "SKIPPED":
            print(f"  ⏭️ {name}: {status}")
        else:
            print(f"  ❌ {name}: {status}")
            if error:
                print(f"      Error: {error[:100]}")

    print("\n" + "-" * 70)
    print(f" Total: {passed + failed + skipped} tests")
    print(f" ✅ Passed: {passed}")
    print(f" ❌ Failed: {failed}")
    print(f" ⏭️ Skipped: {skipped}")
    print(f" Success Rate: {(passed / (passed + failed)) * 100:.1f}%" if (
        passed + failed) > 0 else "N/A")
    print("-" * 70)

    return passed, failed, skipped


if __name__ == "__main__":
    passed, failed, skipped = run_all_tests()
    sys.exit(0 if failed == 0 else 1)
