#!/usr/bin/env python3
"""
PARWA Live Demo Test - Simulates Real Customer Journey

This script tests the complete demo flow with REAL AI responses:
1. Create demo session
2. Chat with Jarvis using z-ai-web-dev-sdk
3. Test AI responses
4. Show dashboard results

Run: python backend/tests/test_live_demo.py
"""

import sys
import os
import json
import uuid
from datetime import datetime

# Add backend to path
sys.path.insert(0, '/home/z/my-project/parwa/backend')

def test_ai_sdk_direct():
    """Test: z-ai-web-dev-sdk returns real AI responses."""
    print("\n" + "="*60)
    print("🧪 TEST 1: z-ai-web-dev-sdk Direct Test")
    print("="*60)
    
    import subprocess
    
    messages = json.dumps([
        {"role": "system", "content": "You are Jarvis, a helpful AI assistant for PARWA customer support."},
        {"role": "user", "content": "Hello! I'm testing the PARWA demo. Can you help me understand how you can assist my e-commerce business?"}
    ])
    
    node_script = f"""
const ZAI = require('z-ai-web-dev-sdk').default;
(async () => {{
    const zai = await ZAI.create();
    const completion = await zai.chat.completions.create({{
        messages: {messages},
        temperature: 0.7,
        max_tokens: 500
    }});
    console.log(completion.choices[0].message.content);
}})();
"""
    
    result = subprocess.run(
        ["node", "-e", node_script],
        capture_output=True,
        text=True,
        timeout=30,
        cwd="/home/z/my-project/parwa"
    )
    
    if result.returncode == 0:
        print("✅ AI Response Received:")
        print("-" * 40)
        print(result.stdout.strip())
        print("-" * 40)
        return True
    else:
        print(f"❌ AI SDK Failed: {result.stderr}")
        return False


def test_image_generation():
    """Test: Image generation via z-ai-web-dev-sdk."""
    print("\n" + "="*60)
    print("🧪 TEST 2: Image Generation Test")
    print("="*60)
    
    import subprocess
    
    node_script = """
const ZAI = require('z-ai-web-dev-sdk').default;
(async () => {
    const zai = await ZAI.create();
    const response = await zai.images.generations.create({
        prompt: 'A professional customer support AI assistant robot helping customers',
        size: '1024x1024'
    });
    console.log('Image generated! Base64 length:', response.data[0].base64.length);
})();
"""
    
    result = subprocess.run(
        ["node", "-e", node_script],
        capture_output=True,
        text=True,
        timeout=60,
        cwd="/home/z/my-project/parwa"
    )
    
    if result.returncode == 0:
        print("✅ Image Generation Working:")
        print(result.stdout.strip())
        return True
    else:
        print(f"❌ Image Generation Failed: {result.stderr}")
        return False


def test_web_search():
    """Test: Web search via z-ai-web-dev-sdk."""
    print("\n" + "="*60)
    print("🧪 TEST 3: Web Search Test")
    print("="*60)
    
    import subprocess
    
    node_script = """
const ZAI = require('z-ai-web-dev-sdk').default;
(async () => {
    const zai = await ZAI.create();
    const results = await zai.functions.invoke('web_search', {
        query: 'PARWA AI customer support automation',
        num: 3
    });
    console.log('Search results:', JSON.stringify(results.slice(0, 3), null, 2));
})();
"""
    
    result = subprocess.run(
        ["node", "-e", node_script],
        capture_output=True,
        text=True,
        timeout=30,
        cwd="/home/z/my-project/parwa"
    )
    
    if result.returncode == 0:
        print("✅ Web Search Working:")
        print(result.stdout.strip())
        return True
    else:
        print(f"❌ Web Search Failed: {result.stderr}")
        return False


def test_demo_chat_flow():
    """Test: Complete demo chat flow with AI."""
    print("\n" + "="*60)
    print("🧪 TEST 4: Demo Chat Flow Simulation")
    print("="*60)
    
    try:
        from app.services.jarvis_service import (
            create_or_resume_session,
            send_message,
            check_message_limit,
        )
        from database.base import SessionLocal
        
        db = SessionLocal()
        
        # Create demo session
        user_id = str(uuid.uuid4())
        print(f"\n👤 Creating demo session for user: {user_id[:8]}...")
        
        session = create_or_resume_session(
            db=db,
            user_id=user_id,
            entry_source="landing_page",
            entry_params={"industry": "ecommerce", "variant": "parwa"}
        )
        
        print(f"✅ Session created: {str(session.id)[:8]}...")
        print(f"   Pack Type: {session.pack_type}")
        print(f"   Entry Source: landing_page")
        
        # Check message limit
        limit, remaining = check_message_limit(db, session)
        print(f"   Message Limit: {limit}/day")
        print(f"   Remaining: {remaining}")
        
        # Send test message
        print("\n💬 Sending message to Jarvis AI...")
        
        user_msg, ai_msg, knowledge = send_message(
            db=db,
            session_id=str(session.id),
            user_id=user_id,
            user_message="Hi Jarvis! I'm interested in PARWA for my e-commerce store. Can you tell me about the features?"
        )
        
        print(f"\n📝 User: {user_msg.content}")
        print(f"\n🤖 Jarvis: {ai_msg.content[:500]}...")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Demo Chat Failed: {str(e)}")
        return False


def test_onboarding_integration():
    """Test: Onboarding with welcome communications."""
    print("\n" + "="*60)
    print("🧪 TEST 5: Onboarding Integration Test")
    print("="*60)
    
    try:
        from app.services.onboarding_service import (
            get_or_create_session,
            accept_legal_consents,
            activate_ai,
            _generate_ai_greeting,
        )
        from database.base import SessionLocal
        from database.models.core import User, Company
        
        db = SessionLocal()
        
        # Create test user
        user_id = str(uuid.uuid4())
        company_id = str(uuid.uuid4())
        
        user = User(
            id=user_id,
            email=f"demo_{uuid.uuid4().hex[:8]}@test.com",
            hashed_password="test_hash",
            company_id=company_id,
            full_name="Demo User",
        )
        company = Company(
            id=company_id,
            name="Demo Company",
        )
        db.add(user)
        db.add(company)
        db.commit()
        
        print(f"\n👤 Test user created: {user.email}")
        
        # Test AI greeting generation
        print("\n🤖 Testing AI Greeting Generation...")
        greeting = _generate_ai_greeting(
            ai_name="Jarvis",
            ai_tone="professional",
            company_name="Demo Company"
        )
        print(f"   Generated Greeting: {greeting}")
        
        # Create onboarding session
        session = get_or_create_session(db, user_id, company_id)
        print(f"\n✅ Onboarding session created")
        
        # Accept legal consents
        print("\n📋 Accepting legal consents...")
        consent_result = accept_legal_consents(
            db=db,
            user_id=user_id,
            company_id=company_id,
            accept_terms=True,
            accept_privacy=True,
            accept_ai_data=True,
        )
        print(f"   ✅ {consent_result['message']}")
        
        # Test activation (with mocks for communications)
        print("\n🚀 Testing AI Activation...")
        import unittest.mock as mock
        with mock.patch('app.services.onboarding_service._send_welcome_email', return_value=True):
            with mock.patch('app.services.onboarding_service._send_onboarding_sms', return_value=True):
                with mock.patch('app.services.onboarding_service._generate_ai_greeting', return_value=greeting):
                    result = activate_ai(
                        db=db,
                        user_id=user_id,
                        company_id=company_id,
                        ai_name="Jarvis",
                        ai_tone="professional",
                    )
        
        print(f"   ✅ {result['message']}")
        print(f"   AI Name: {result['ai_name']}")
        print(f"   AI Tone: {result['ai_tone']}")
        print(f"   AI Greeting: {result['ai_greeting']}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Onboarding Test Failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all live demo tests."""
    print("\n" + "="*60)
    print("🎯 PARWA Live Demo Test Suite")
    print("="*60)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Test 1: AI SDK Direct
    results.append(("AI SDK Direct", test_ai_sdk_direct()))
    
    # Test 2: Image Generation
    results.append(("Image Generation", test_image_generation()))
    
    # Test 3: Web Search
    results.append(("Web Search", test_web_search()))
    
    # Test 4: Demo Chat Flow
    results.append(("Demo Chat Flow", test_demo_chat_flow()))
    
    # Test 5: Onboarding Integration
    results.append(("Onboarding Integration", test_onboarding_integration()))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {name}: {status}")
    
    print("-" * 40)
    print(f"   Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Demo flow is production-ready!")
    else:
        print(f"\n⚠️  {total - passed} tests failed. Check errors above.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
