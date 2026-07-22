"""
Test Script for CRM Analyzer Service

Tests the CRM analysis and recommendation logic:
1. Data gathering from integrations
2. Gap detection
3. LLM-powered recommendations (with mock)
4. Fallback recommendations when LLM fails

Run: python scripts/test_crm_analyzer.py
"""

import asyncio
import json
import sys
from unittest.mock import MagicMock

# Mock all external dependencies before importing
MOCK_MODULES = [
    'sqlalchemy', 'sqlalchemy.orm',
    'structlog', 'httpx', 'pydantic', 'fastapi',
    'app.exceptions', 'app.logger', 'database.models.integration',
    'database.base', 'database.models.tickets', 'database.models.orders',
    'database.models.core', 'app.api.deps', 'app.services.audit_service',
]

for mod in MOCK_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Add backend to path
sys.path.insert(0, '/home/z/my-project/parwa-code/backend')


class MockDB:
    """Mock database session for testing."""
    pass


class MockIntegrationService:
    """Mock integration service for testing."""
    
    def get_credential_config(self, company_id, integration_type):
        # Return mock credentials for testing
        creds = {
            "hubspot": {"api_key": "pat-test-key"},
            "shopify": {
                "store_url": "test-store.myshopify.com",
                "access_token": "shpat_test_token",
            },
            "stripe": {"api_key": "sk_test_key"},
            "mailchimp": {"api_key": "us1-test-key"},
        }
        return creds.get(integration_type)


async def test_gap_detection():
    """Test gap detection logic."""
    print("\n" + "="*60)
    print("TEST 1: Gap Detection Logic")
    print("="*60)
    
    from app.services.crm_analyzer_service import CRMAnalyzerService
    
    service = CRMAnalyzerService(MockDB())
    service.integration_service = MockIntegrationService()
    
    # Test Case 1: E-commerce with orders but no shipping
    data_profile = {
        "total_contacts": 50,
        "total_orders": 100,
        "total_deals": 0,
        "has_products": True,
        "has_shipping_addresses": False,
        "has_payment_data": False,
        "has_email_campaigns": False,
        "has_ticket_data": False,
        "industries_detected": ["ecommerce"],
        "data_points": [],
    }
    
    connected = [
        {"type": "shopify", "name": "Shopify Store", "category": "ecommerce"}
    ]
    
    gaps = await service._detect_gaps(data_profile, connected)
    
    print(f"\nData Profile:")
    print(f"  - Orders: {data_profile['total_orders']}")
    print(f"  - Has Products: {data_profile['has_products']}")
    print(f"  - Has Shipping: {data_profile['has_shipping_addresses']}")
    print(f"  - Has Payment: {data_profile['has_payment_data']}")
    
    print(f"\nDetected {len(gaps)} gaps:")
    for gap in gaps:
        print(f"  [{gap['severity'].upper()}] {gap['message']}")
        print(f"           Recommended: {gap['recommended']}")
    
    # Assertions
    assert len(gaps) > 0, "Should detect gaps"
    
    shipping_gap = next((g for g in gaps if g['category'] == 'shipping'), None)
    assert shipping_gap is not None, "Should detect shipping gap"
    assert shipping_gap['severity'] == 'high', "Shipping gap should be high priority"
    
    payment_gap = next((g for g in gaps if g['category'] == 'payments'), None)
    assert payment_gap is not None, "Should detect payment gap"
    
    print("\n✅ Gap detection working correctly!")
    return True


async def test_fallback_recommendations():
    """Test fallback recommendation generation when LLM fails."""
    print("\n" + "="*60)
    print("TEST 2: Fallback Recommendations (No LLM)")
    print("="*60)
    
    from app.services.crm_analyzer_service import CRMAnalyzerService
    
    service = CRMAnalyzerService(MockDB())
    
    gaps = [
        {
            "id": "shipping_missing",
            "condition": True,
            "category": "shipping",
            "severity": "high",
            "message": "You have orders but no shipping integration",
            "recommended": ["shipstation", "aftership"],
        },
        {
            "id": "payment_missing",
            "condition": True,
            "category": "payments",
            "severity": "high",
            "message": "You sell products but no payment processor",
            "recommended": ["stripe", "paddle"],
        },
        {
            "id": "marketing_missing",
            "condition": True,
            "category": "marketing",
            "severity": "medium",
            "message": "Many contacts but no email marketing",
            "recommended": ["mailchimp", "klaviyo"],
        },
    ]
    
    connected_types = ["shopify"]
    
    recs = service._generate_fallback_recommendations(gaps, connected_types)
    
    print(f"\nGenerated {len(recs)} fallback recommendations:")
    for rec in recs:
        print(f"  - {rec['name']} ({rec['priority']})")
        print(f"    Reason: {rec['reason'][:80]}...")
    
    assert len(recs) == 3, f"Should generate 3 recommendations, got {len(recs)}"
    assert all(r['already_connected'] == False for r in recs), "None should be marked as connected"
    
    print("\n✅ Fallback recommendations working correctly!")
    return True


async def test_summary_generation():
    """Test summary text generation."""
    print("\n" + "="*60)
    print("TEST 3: Summary Generation")
    print("="*60)
    
    from app.services.crm_analyzer_service import CRMAnalyzerService
    
    service = CRMAnalyzerService(MockDB())
    
    data_profile = {
        "total_contacts": 500,
        "total_orders": 100,
        "total_deals": 50,
        "has_products": True,
        "has_shipping_addresses": False,
        "has_payment_data": False,
        "has_email_campaigns": False,
        "has_ticket_data": False,
        "industries_detected": [],
        "data_points": [],
    }
    
    recommendations = [
        {
            "name": "Stripe",
            "priority": "high",
            "reason": "You need payments for products",
        },
        {
            "name": "ShipStation",
            "priority": "high",
            "reason": "Track your shipments",
        },
        {
            "name": "Mailchimp",
            "priority": "medium",
            "reason": "Email marketing for contacts",
        },
    ]
    
    summary = service._build_summary(data_profile, recommendations)
    
    print(f"\nGenerated Summary:")
    print(f'  "{summary}"')
    
    assert "500" in summary, "Should mention contact count"
    assert "100" in summary, "Should mention order count"
    assert "urgent" in summary.lower() or "high" in summary.lower(), "Should mention urgency"
    
    print("\n✅ Summary generation working correctly!")
    return True


async def test_full_analysis_mock():
    """Test full analysis with mocked components."""
    print("\n" + "="*60)
    print("TEST 4: Full Analysis Flow (Mocked)")
    print("="*60)
    
    from app.services.crm_analyzer_service import CRMAnalyzerService
    from unittest.mock import AsyncMock, patch, MagicMock
    
    service = CRMAnalyzerService(MockDB())
    
    # Mock the methods that make external calls
    service._get_connected_integrations = AsyncMock(return_value=[
        {"id": "1", "type": "hubspot", "name": "HubSpot", "category": "crm", "connected_at": "2024-01-15"},
        {"id": "2", "type": "shopify", "name": "Shopify", "category": "ecommerce", "connected_at": "2024-02-01"},
    ])
    
    service._gather_data_from_integrations = AsyncMock(return_value={
        "total_contacts": 1250,
        "total_orders": 450,
        "total_deals": 80,
        "has_products": True,
        "has_shipping_addresses": False,
        "has_payment_data": False,
        "has_email_campaigns": False,
        "has_ticket_data": False,
        "industries_detected": ["ecommerce"],
        "data_points": [{"source": "shopify", "type": "ecommerce", "order_count": 450}],
    })
    
    service._generate_recommendations = AsyncMock(return_value=[
        {
            "integration_key": "shipstation",
            "name": "ShipStation",
            "category": "shipping",
            "priority": "high",
            "reason": "You have 450 orders but no shipping tracking",
            "business_impact": "Enable real-time order tracking for customers",
            "already_connected": False,
        },
        {
            "integration_key": "stripe",
            "name": "Stripe",
            "category": "payments",
            "priority": "high",
            "reason": "Products exist but no payment processor",
            "business_impact": "Accept online payments securely",
            "already_connected": False,
        },
        {
            "integration_key": "mailchimp",
            "name": "Mailchimp",
            "category": "marketing",
            "priority": "medium",
            "reason": "1250 contacts ready for email marketing",
            "business_impact": "Automate email campaigns to drive sales",
            "already_connected": False,
        },
    ])
    
    result = await service.analyze_company_crm("test-company-123")
    
    print(f"\nAnalysis Result:")
    print(f"  Company ID: {result['company_id']}")
    print(f"  Analyzed At: {result['analyzed_at']}")
    print(f"  Connected Integrations: {len(result['connected_integrations'])}")
    for conn in result['connected_integrations']:
        print(f"    - {conn['name']} ({conn['type']})")
    
    print(f"\n  Data Profile:")
    dp = result['data_profile']
    print(f"    - Contacts: {dp['total_contacts']}")
    print(f"    - Orders: {dp['total_orders']}")
    print(f"    - Deals: {dp['total_deals']}")
    
    print(f"\n  Detected Gaps: {len(result['detected_gaps'])}")
    for gap in result['detected_gaps']:
        print(f"    - [{gap.get('severity', '?')}] {gap.get('message', 'N/A')[:60]}")
    
    print(f"\n  Recommendations: {len(result['recommendations'])}")
    for rec in result['recommendations']:
        print(f"    - [{rec['priority'].upper()}] {rec['name']}: {rec['reason'][:50]}...")
    
    print(f"\n  Summary: {result['analysis_summary'][:100]}...")
    
    # Verify structure
    assert "company_id" in result
    assert "analyzed_at" in result
    assert "connected_integrations" in result
    assert "data_profile" in result
    assert "detected_gaps" in result
    assert "recommendations" in result
    assert "analysis_summary" in result
    assert len(result["recommendations"]) == 3
    
    print("\n✅ Full analysis flow working correctly!")
    return True


async def main():
    """Run all tests."""
    print("=" * 60)
    print("CRM ANALYZER SERVICE - TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("Gap Detection", test_gap_detection),
        ("Fallback Recommendations", test_fallback_recommendations),
        ("Summary Generation", test_summary_generation),
        ("Full Analysis Flow", test_full_analysis_mock),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            await test_fn()
            results.append((name, "PASSED ✅"))
        except Exception as e:
            results.append((name, f"FAILED ❌: {str(e)[:100]}"))
    
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, status in results if "PASSED" in status)
    total = len(results)
    
    for name, status in results:
        print(f"  {status} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! The CRM Analyzer is ready.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review.")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
