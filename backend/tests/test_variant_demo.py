#!/usr/bin/env python3
"""
PARWA Variant Demo Test

Tests the variant-aware demo system that lets potential customers
test different PARWA tiers before purchasing.

Features tested:
1. Demo session creation for each variant
2. Variant-specific capabilities
3. AI chat with variant-specific prompts
4. Demo completion and results

Run: python backend/tests/test_variant_demo.py
"""

import sys

# Add backend to path
sys.path.insert(0, "/home/z/my-project/parwa/backend")


def test_demo_service():
    """Test the demo service with all variants."""
    print("\n" + "=" * 60)
    print("🧪 TEST: Demo Service - Variant Capabilities")
    print("=" * 60)

    try:
        from app.services.demo_service import (
            VARIANT_DEMO_CAPABILITIES,
            DemoVariant,
            get_demo_service,
        )

        demo_service = get_demo_service()

        # Test each variant
        for variant in [
            DemoVariant.MINI_PARWA,
            DemoVariant.PARWA,
            DemoVariant.HIGH_PARWA,
        ]:
            caps = VARIANT_DEMO_CAPABILITIES[variant]
            print(f"\n📦 {caps['display_name']} ({variant.value}):")
            print(f"   Price: ${caps['price_monthly']}/mo")
            print(f"   Max Demo Messages: {caps['max_demo_messages']}")
            print(f"   Features: {len(caps['features'])} features")
            print(f"   Voice Enabled: {caps['voice_enabled']}")
            print(f"   Web Search: {caps['web_search_enabled']}")

        print("\n✅ Demo service initialized successfully")
        return True

    except Exception as e:
        print(f"❌ Demo service test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_demo_session_creation():
    """Test demo session creation for each variant."""
    print("\n" + "=" * 60)
    print("🧪 TEST: Demo Session Creation")
    print("=" * 60)

    try:
        from app.services.demo_service import DemoVariant, get_demo_service

        demo_service = get_demo_service()

        # Test session creation for each variant
        for variant in [
            DemoVariant.MINI_PARWA,
            DemoVariant.PARWA,
            DemoVariant.HIGH_PARWA,
        ]:
            session = demo_service.create_demo_session(
                variant=variant,
                industry="ecommerce",
            )

            print(f"\n✅ Session created for {variant.value}:")
            print(f"   Session ID: {session.session_id[:20]}...")
            print(f"   Status: {session.status.value}")
            print(f"   Industry: {session.industry}")

        return True

    except Exception as e:
        print(f"❌ Session creation test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_demo_chat():
    """Test demo chat with variant-specific responses."""
    print("\n" + "=" * 60)
    print("🧪 TEST: Demo Chat Flow")
    print("=" * 60)

    try:
        from app.services.demo_service import DemoVariant, get_demo_service

        demo_service = get_demo_service()

        # Test with Parwa variant
        session = demo_service.create_demo_session(
            variant=DemoVariant.PARWA,
            industry="ecommerce",
        )

        print(f"\n📝 Session: {session.session_id[:20]}...")

        # Send test message
        result = demo_service.send_demo_message(
            session_id=session.session_id,
            message="Hi, I want to test PARWA's AI capabilities!",
        )

        print(f"\n🤖 AI Response ({result.latency_ms:.0f}ms):")
        print(f"   {result.ai_response[:200]}...")
        print(f"   Confidence: {result.confidence:.0%}")
        print(f"   Features Used: {', '.join(result.features_used)}")
        print(f"   Remaining Messages: {
                result.variant_capabilities.get(
                    'remaining_messages',
                    0)}")

        if result.success:
            print("\n✅ Demo chat working correctly")
            return True
        else:
            print(f"\n❌ Demo chat failed: {result.message}")
            return False

    except Exception as e:
        print(f"❌ Demo chat test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_variant_comparison():
    """Test variant comparison API."""
    print("\n" + "=" * 60)
    print("🧪 TEST: Variant Comparison")
    print("=" * 60)

    try:
        from app.services.demo_service import get_demo_service

        demo_service = get_demo_service()
        comparison = demo_service.get_variant_comparison()

        print("\n📊 Variant Comparison:")
        for variant_id, caps in comparison.items():
            print(f"\n   {caps['display_name']}:")
            print(f"      Price: ${caps['price_monthly']}/mo")
            print(f"      Max Demo Messages: {caps['max_demo_messages']}")
            print(f"      Features: {len(caps['features'])}")

        print("\n✅ Variant comparison working")
        return True

    except Exception as e:
        print(f"❌ Variant comparison test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_demo_scenarios():
    """Test demo scenarios retrieval."""
    print("\n" + "=" * 60)
    print("🧪 TEST: Demo Scenarios")
    print("=" * 60)

    try:
        from app.services.demo_service import DemoVariant, get_demo_service

        demo_service = get_demo_service()

        # Test scenarios for each variant
        for variant in [
            DemoVariant.MINI_PARWA,
            DemoVariant.PARWA,
            DemoVariant.HIGH_PARWA,
        ]:
            scenarios = demo_service.get_demo_scenarios(
                variant=variant,
                industry="ecommerce",
            )

            print(f"\n📋 {variant.value}: {len(scenarios)} scenarios available")
            for s in scenarios[:3]:
                print(f"   - {s.get('title', 'Unknown')}")

        print("\n✅ Demo scenarios working")
        return True

    except Exception as e:
        print(f"❌ Demo scenarios test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_demo_completion():
    """Test demo session completion."""
    print("\n" + "=" * 60)
    print("🧪 TEST: Demo Completion")
    print("=" * 60)

    try:
        from app.services.demo_service import DemoVariant, get_demo_service

        demo_service = get_demo_service()

        # Create and complete session
        session = demo_service.create_demo_session(
            variant=DemoVariant.PARWA,
            industry="saas",
        )

        # Send a few messages
        demo_service.send_demo_message(
            session_id=session.session_id,
            message="Hello, testing PARWA!",
        )

        # Complete session
        result = demo_service.complete_demo_session(session.session_id)

        print(f"\n✅ Demo completed: {result.get('message')}")
        print(f"   Variant tested: {
                result.get(
                    'summary',
                    {}).get('variant_tested')}")
        print(f"   Messages sent: {
                result.get(
                    'summary',
                    {}).get('messages_sent')}")

        return True

    except Exception as e:
        print(f"❌ Demo completion test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all demo tests."""
    print("\n" + "=" * 60)
    print("🎯 PARWA Variant Demo Test Suite")
    print("=" * 60)

    results = []

    # Test 1: Demo Service
    results.append(("Demo Service", test_demo_service()))

    # Test 2: Session Creation
    results.append(("Session Creation", test_demo_session_creation()))

    # Test 3: Demo Chat
    results.append(("Demo Chat", test_demo_chat()))

    # Test 4: Variant Comparison
    results.append(("Variant Comparison", test_variant_comparison()))

    # Test 5: Demo Scenarios
    results.append(("Demo Scenarios", test_demo_scenarios()))

    # Test 6: Demo Completion
    results.append(("Demo Completion", test_demo_completion()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {name}: {status}")

    print("-" * 40)
    print(f"   Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Demo system is ready!")
    else:
        print(f"\n⚠️  {total - passed} tests failed. Check errors above.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
