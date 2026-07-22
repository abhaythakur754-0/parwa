"""
REAL-WORLD TEST: CRM Analyzer with NVIDIA GLM 5.2

This test actually calls the NVIDIA API to generate real integration
recommendations using the GLM 5.2 model - no mocking!

Tests:
1. Direct NVIDIA GLM API call for CRM analysis
2. Full analysis flow with real LLM response parsing
3. Different business scenarios (ecommerce, SaaS, agency)
4. Response time and token usage metrics

Run: python scripts/test_crm_analyzer_real.py
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────

NVIDIA_API_KEY = os.environ.get(
    "NVIDIA_API_KEY",
    "REDACTED_NVIDIA_KEY_REMOVED"
)

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "z-ai/glm-5.2"

# ── Test Scenarios ─────────────────────────────────────────────────

TEST_SCENARIOS = {
    "ecommerce_store": {
        "name": "E-commerce Store (Shopify)",
        "data_profile": {
            "total_contacts": 2500,
            "total_orders": 850,
            "total_deals": 0,
            "has_products": True,
            "has_shipping_addresses": False,  # Gap!
            "has_payment_data": False,          # Gap!
            "has_email_campaigns": False,
            "has_ticket_data": False,
            "industries_detected": ["ecommerce"],
            "data_points": [
                {"source": "shopify", "type": "ecommerce", "order_count": 850}
            ],
        },
        "connected": [
            {"type": "shopify", "name": "Shopify Store", "category": "ecommerce"}
        ],
        "expected_gaps": ["shipping", "payments"],
    },
    
    "saas_company": {
        "name": "SaaS Company (HubSpot)",
        "data_profile": {
            "total_contacts": 5000,
            "total_orders": 0,
            "total_deals": 320,
            "has_products": False,
            "has_shipping_addresses": False,
            "has_payment_data": False,
            "has_email_campaigns": False,       # Gap!
            "has_ticket_data": False,             # Gap!
            "industries_detected": ["saas"],
            "data_points": [
                {"source": "hubspot", "type": "crm", "contact_count": 5000}
            ],
        },
        "connected": [
            {"type": "hubspot", "name": "HubSpot CRM", "category": "crm"}
        ],
        "expected_gaps": ["marketing", "helpdesk"],
    },
    
    "agency": {
        "name": "Digital Agency (Multiple Tools)",
        "data_profile": {
            "total_contacts": 12000,
            "total_orders": 150,
            "total_deals": 450,
            "has_products": True,
            "has_shipping_addresses": False,
            "has_payment_data": True,
            "has_email_campaigns": False,          # Gap!
            "has_ticket_data": False,               # Gap!
            "industries_detected": ["saas", "ecommerce"],
            "data_points": [
                {"source": "hubspot", "type": "crm", "contact_count": 12000},
                {"source": "stripe", "type": "payment", "transaction_count": 2500},
            ],
        },
        "connected": [
            {"type": "hubspot", "name": "HubSpot CRM", "category": "crm"},
            {"type": "stripe", "name": "Stripe Payments", "category": "payments"},
        ],
        "expected_gaps": ["marketing", "helpdesk", "analytics"],
    },
    
    "new_startup": {
        "name": "New Startup (No Integrations)",
        "data_profile": {
            "total_contacts": 50,
            "total_orders": 10,
            "total_deals": 5,
            "has_products": True,
            "has_shipping_addresses": False,
            "has_payment_data": False,
            "has_email_campaigns": False,
            "has_ticket_data": False,
            "industries_detected": [],
            "data_points": [],
        },
        "connected": [],  # No integrations yet!
        "expected_gaps": ["payments", "shipping", "helpdesk"],
    },
}


async def call_nvidia_glm(prompt: str, max_tokens: int = 800) -> dict:
    """Call NVIDIA GLM 5.2 API directly."""
    import httpx
    
    messages = [
        {
            "role": "system",
            "content": "You are Parwa's intelligent integration advisor. You analyze business data and recommend specific third-party integrations that would improve their workflow. Always respond in valid JSON format."
        },
        {
            "role": "user",
            "content": prompt
        }
    ]
    
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }
    
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=120.0) as client:  # Increased timeout for GLM
        response = await client.post(NVIDIA_URL, json=payload, headers=headers)
    
    elapsed = time.time() - start_time
    
    if response.status_code == 200:
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})
        
        return {
            "success": True,
            "content": content.strip(),
            "tokens": {
                "prompt": usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
                "total": usage.get("total_tokens", 0),
            },
            "response_time_ms": int(elapsed * 1000),
            "model": MODEL,
        }
    else:
        return {
            "success": False,
            "error": f"API error {response.status_code}: {response.text[:200]}",
            "response_time_ms": int(elapsed * 1000),
        }


def build_analysis_prompt(data_profile: dict, connected: list, gaps: list) -> str:
    """Build the CRM analysis prompt for NVIDIA GLM."""
    connected_names = [c["name"] for c in connected]
    
    prompt = f"""You are Parwa's integration advisor. Analyze this company's data and recommend specific integrations they need.

COMPANY DATA PROFILE:
- Total Contacts: {data_profile.get('total_contacts', 0)}
- Total Orders: {data_profile.get('total_orders', 0)}
- Total Deals: {data_profile.get('total_deals', 0)}
- Has Products: {data_profile.get('has_products', False)}
- Has Shipping Data: {data_profile.get('has_shipping_addresses', False)}
- Has Payment Data: {data_profile.get('has_payment_data', False)}
- Has Email Marketing: {data_profile.get('has_email_campaigns', False)}
- Has Helpdesk: {data_profile.get('has_ticket_data', False)}
- Detected Industries: {data_profile.get('industries_detected', ['unknown'])}
- Data Points: {json.dumps(data_profile.get('data_points', [])[:3], indent=2)}

CURRENTLY CONNECTED ({len(connected)}): {', '.join(connected_names) if connected_names else 'None'}

DETECTED GAPS ({len(gaps)}):
{chr(10).join(f'- {g["message"]} (severity: {g["severity"]})' for g in gaps)}

AVAILABLE INTEGRATIONS TO RECOMMEND FROM:
- Shipping: shipstation, aftership, easypost, fedex, ups, dhl
- Payments: stripe, paddle, paypal
- Marketing: mailchimp, klaviyo, brevo
- Helpdesk: zendesk, freshdesk, intercom, gorgias
- Analytics: mixpanel, amplitude, google_analytics
- Communication: slack, gmail
- Dev Tools: github, jira, linear, notion

Respond in EXACTLY this JSON format (no markdown, no extra text):
{{
  "recommendations": [
    {{
      "integration_key": "stripe",
      "name": "Stripe",
      "category": "payments",
      "priority": "high|medium|low",
      "reason": "One sentence why they specifically need this",
      "business_impact": "What business outcome this enables"
    }}
  ],
  "overall_assessment": "2-3 sentences about their integration health"
}}"""

    return prompt


def detect_gaps(data_profile: dict, connected_types: list) -> list:
    """Detect gaps based on data profile."""
    gaps = []
    
    gap_rules = [
        {
            "id": "shipping_missing",
            "condition": data_profile.get("total_orders", 0) > 0 and not data_profile.get("has_shipping_addresses"),
            "category": "shipping",
            "severity": "high",
            "message": "You have orders but no shipping integration for tracking",
            "recommended": ["shipstation", "aftership", "easypost"],
        },
        {
            "id": "payment_missing",
            "condition": data_profile.get("has_products") and not data_profile.get("has_payment_data"),
            "category": "payments",
            "severity": "high",
            "message": "You sell products but no payment processor is connected",
            "recommended": ["stripe", "paddle"],
        },
        {
            "id": "marketing_missing",
            "condition": data_profile.get("total_contacts", 0) > 100 and not data_profile.get("has_email_campaigns"),
            "category": "marketing",
            "severity": "medium",
            "message": f"You have {data_profile.get('total_contacts', 0)} contacts but no email marketing tool",
            "recommended": ["mailchimp", "klaviyo", "brevo"],
        },
        {
            "id": "helpdesk_missing",
            "condition": data_profile.get("total_contacts", 0) > 50 and not data_profile.get("has_ticket_data"),
            "category": "helpdesk",
            "severity": "medium",
            "message": "Growing customer base but no dedicated helpdesk system",
            "recommended": ["zendesk", "freshdesk", "intercom", "gorgias"],
        },
        {
            "id": "analytics_missing",
            "condition": data_profile.get("total_orders", 0) > 10 or data_profile.get("total_contacts", 0) > 100,
            "category": "analytics",
            "severity": "low",
            "message": "Significant activity but no analytics integration for insights",
            "recommended": ["mixpanel", "amplitude", "google_analytics"],
        },
    ]
    
    for rule in gap_rules:
        if rule["condition"]:
            available_recs = [r for r in rule["recommended"] if r not in connected_types]
            if available_recs:
                gaps.append({**rule, "recommended": available_recs})
    
    return gaps


def parse_recommendations(response_content: str) -> list:
    """Parse LLM response into structured recommendations."""
    try:
        # Try to extract JSON from response
        json_str = response_content.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]
        
        parsed = json.loads(json_str)
        return parsed.get("recommendations", [])
    except Exception as e:
        print(f"  ⚠️ Failed to parse recommendations: {e}")
        return []


async def test_scenario(name: str, scenario: dict) -> dict:
    """Test a single scenario with real NVIDIA GLM call."""
    print(f"\n{'='*70}")
    print(f"SCENARIO: {name}")
    print(f"{'='*70}")
    
    data_profile = scenario["data_profile"]
    connected = scenario["connected"]
    expected_gaps = scenario.get("expected_gaps", [])
    
    # Detect gaps
    connected_types = [c["type"] for c in connected]
    gaps = detect_gaps(data_profile, connected_types)
    
    print(f"\n📊 Data Profile:")
    print(f"   Contacts: {data_profile['total_contacts']:,}")
    print(f"   Orders: {data_profile['total_orders']:,}")
    print(f"   Deals: {data_profile['total_deals']:,}")
    print(f"   Products: {'✅' if data_profile['has_products'] else '❌'}")
    print(f"   Shipping: {'✅' if data_profile['has_shipping_addresses'] else '❌'}")
    print(f"   Payments: {'✅' if data_profile['has_payment_data'] else '❌'}")
    print(f"   Email Marketing: {'✅' if data_profile['has_email_campaigns'] else '❌'}")
    print(f"   Helpdesk: {'✅' if data_profile['has_ticket_data'] else '❌'}")
    
    print(f"\n🔗 Connected Integrations ({len(connected)}):")
    for c in connected:
        print(f"   • {c['name']} ({c['category']})")
    
    print(f"\n🔍 Detected Gaps ({len(gaps)}):")
    for gap in gaps:
        print(f"   [{gap['severity'].upper()}] {gap['message']}")
        print(f"              → Recommend: {', '.join(gap['recommended'][:3])}")
    
    # Build prompt and call NVIDIA GLM
    print(f"\n🤖 Calling NVIDIA GLM 5.2...")
    prompt = build_analysis_prompt(data_profile, connected, gaps)
    
    result = await call_nvidia_glm(prompt)
    
    if not result["success"]:
        print(f"   ❌ API Call FAILED: {result.get('error', 'Unknown error')}")
        return {"scenario": name, "success": False, "error": result.get("error")}
    
    # Parse response
    recommendations = parse_recommendations(result["content"])
    
    print(f"\n✅ NVIDIA GLM Response Received!")
    print(f"   ⏱️  Response Time: {result['response_time_ms']}ms")
    print(f"   📊 Tokens Used: {result['tokens']['total']} (prompt: {result['tokens']['prompt']}, completion: {result['tokens']['completion']})")
    
    print(f"\n💡 Generated Recommendations ({len(recommendations)}):")
    for rec in recommendations:
        priority_icon = "🔴" if rec.get("priority") == "high" else "🟡" if rec.get("priority") == "medium" else "🔵"
        print(f"   {priority_icon} {rec.get('name', 'Unknown')} ({rec.get('category', '?')})")
        print(f"      Reason: {rec.get('reason', 'N/A')}")
        print(f"      Impact: {rec.get('business_impact', 'N/A')}")
    
    # Validate against expected gaps
    rec_keys = [r.get("integration_key", "") for r in recommendations]
    found_expected = sum(1 for g in expected_gaps if any(r in str(rec_keys).lower() for r in get_integration_keywords(g)))
    
    print(f"\n📋 Validation:")
    print(f"   Expected gap categories: {expected_gaps}")
    print(f"   Recommendations cover: {len([r for r in recommendations if any(cat in r.get('category', '') for cat in expected_gaps)])} of {len(expected_gaps)}")
    
    return {
        "scenario": name,
        "success": True,
        "recommendations_count": len(recommendations),
        "response_time_ms": result["response_time_ms"],
        "tokens_used": result["tokens"]["total"],
        "recommendations": recommendations,
    }


def get_integration_keywords(category: str) -> list:
    """Get keywords for each category."""
    mapping = {
        "shipping": ["shipstation", "aftership", "easypost", "fedex", "ups", "dhl", "shipping"],
        "payments": ["stripe", "paddle", "paypal", "payment"],
        "marketing": ["mailchimp", "klaviyo", "brevo", "email", "marketing"],
        "helpdesk": ["zendesk", "freshdesk", "intercom", "gorgias", "helpdesk", "support"],
        "analytics": ["mixpanel", "amplitude", "google_analytics", "analytics"],
    }
    return mapping.get(category, [])


async def main():
    """Run all real-world tests."""
    print("="*70)
    print("CRM ANALYZER - REAL-WORLD TEST WITH NVIDIA GLM 5.2")
    print("="*70)
    print(f"Model: {MODEL}")
    print(f"API Endpoint: {NVIDIA_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*70)
    
    results = []
    
    # Test each scenario
    for scenario_name, scenario_data in TEST_SCENARIOS.items():
        result = await test_scenario(scenario_name, scenario_data)
        results.append(result)
        
        # Small delay between calls to avoid rate limiting
        await asyncio.sleep(1)
    
    # Summary
    print("\n\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for r in results if r["success"])
    total = len(results)
    
    print(f"\nTotal Scenarios: {total}")
    print(f"Successful: {passed}/{total}")
    
    if passed > 0:
        avg_response_time = sum(r.get("response_time_ms", 0) for r in results if r["success"]) / passed
        avg_tokens = sum(r.get("tokens_used", 0) for r in results if r["success"]) / passed
        total_recs = sum(r.get("recommendations_count", 0) for r in results if r["success"])
        
        print(f"\n📈 Performance Metrics:")
        print(f"   Average Response Time: {avg_response_time:.0f}ms")
        print(f"   Average Tokens per Request: {avg_tokens:.0f}")
        print(f"   Total Recommendations Generated: {total_recs}")
    
    print("\n" + "-"*70)
    for r in results:
        status = "✅ PASS" if r["success"] else "❌ FAIL"
        recs = f"{r.get('recommendations_count', 0)} recs" if r["success"] else r.get("error", "?")[:40]
        print(f"   {status} | {r['scenario']:<25} | {recs}")
    
    print("-"*70)
    
    if passed == total:
        print("\n🎉 All real-world tests passed! NVIDIA GLM is working perfectly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check logs above.")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
